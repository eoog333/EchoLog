"""
Transcript Post Processor

RTZR STT 전사 결과를 사람이 읽기 좋은 형태로 후처리합니다.

처리 흐름:
    RTZR utterances
        ↓ parse_utterances()   — utterance 목록 파싱
        ↓ sort_by_time()       — start_at 기준 시간순 정렬
        ↓ remove_duplicates()  — 유사 문장 제거 (SequenceMatcher)
        ↓ to_paragraph_events() — RTZR 문단 단위 유지
        ↓ ProcessedTranscript  — 후처리 완료 결과
"""

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# 중복 판단 유사도 임계값 (0~1, 높을수록 엄격)
DUPLICATE_THRESHOLD = 0.8

# 인접 발화가 이 시간 안에 반복된 경우에만 STT 중복으로 판단
DUPLICATE_MAX_GAP_SECONDS = 3.0

# 시간순 기록 문단 규칙: 문장 끝에서만 2~3문장씩 묶습니다.
MIN_PARAGRAPH_SENTENCES = 2
MAX_PARAGRAPH_SENTENCES = 3

TIME_PATTERNS = (
    (re.compile(r"새벽"), "새벽"),
    (re.compile(r"아침"), "아침"),
    (re.compile(r"오전"), "오전"),
    (re.compile(r"점심"), "점심"),
    (re.compile(r"낮"), "낮"),
    (re.compile(r"오후"), "오후"),
    (re.compile(r"저녁"), "저녁"),
    (re.compile(r"밤"), "밤"),
    (re.compile(r"출근\s*전"), "출근 전"),
    (re.compile(r"출근\s*후"), "출근 후"),
    (re.compile(r"퇴근\s*후"), "퇴근 후"),
    (re.compile(r"(?:오전|오후)\s*\d{1,2}시(?:\s*(?:반|\d{1,2}분))?"), None),
    (re.compile(r"\d{1,2}시(?:\s*(?:반|\d{1,2}분))?"), None),
)

@dataclass
class Utterance:
    """RTZR utterance 단위"""
    start_at: float   # 시작 시간 (초)
    end_at: float     # 종료 시간 (초)
    msg: str          # 발화 텍스트
    words: list["WordTimestamp"] = field(default_factory=list)


@dataclass
class WordTimestamp:
    """RTZR 단어별 타임스탬프 단위."""
    start_at: float
    end_at: float
    text: str


@dataclass
class Event:
    """RTZR가 분리한 문단 단위."""
    utterances: list[Utterance] = field(default_factory=list)

    @property
    def start_at(self) -> float:
        return self.utterances[0].start_at if self.utterances else 0.0

    @property
    def text(self) -> str:
        return " ".join(u.msg for u in self.utterances)


@dataclass
class ProcessedTranscript:
    """후처리 완료 결과"""
    events: list[Event]
    raw_utterances: list[Utterance]
    duplicate_count: int = 0

    @property
    def timeline_text(self) -> str:
        """
        LLM 없이 출력하는 문단 목록 형태.
        예시:
            • 오늘 발표가 있었는데 긴장이 됐어요.
            • 저녁에는 교회 연습을 다녀왔어요.
        """
        lines = [f"• {event.text}" for event in self.events if event.text.strip()]
        return "\n".join(lines)

    @property
    def full_text(self) -> str:
        """전체 전사 텍스트 (원본 순서)"""
        return " ".join(u.msg for u in self.raw_utterances)


@dataclass
class TimelineSection:
    """시간순 기록 화면에 표시할 문단."""
    label: str
    start_at: float
    text: str


@dataclass
class Sentence:
    text: str
    start_at: float
    time_label: str | None = None
    is_complete: bool = False


def parse_utterances(rtzr_result: dict) -> list[Utterance]:
    """
    RTZR API 응답에서 utterance 목록을 파싱합니다.

    RTZR 응답 구조:
        results.utterances[].start_at  — 시작 시간 (ms)
        results.utterances[].duration  — 발화 길이 (ms)
        results.utterances[].msg       — 발화 텍스트
    """
    raw = rtzr_result.get("results", {}).get("utterances", [])
    utterances = []
    for u in raw:
        msg = u.get("msg", "").strip()
        if not msg:
            continue
        start_at_ms = u.get("start_at", 0)
        end_at_ms = u.get("end_at")
        if end_at_ms is None:
            end_at_ms = start_at_ms + u.get("duration", 0)

        words = []
        for word in u.get("words", []):
            text = str(word.get("text", "")).strip()
            if not text:
                continue
            word_start_at = word.get("start_at", start_at_ms)
            word_end_at = word_start_at + word.get("duration", 0)
            words.append(WordTimestamp(
                start_at=word_start_at / 1000.0,
                end_at=word_end_at / 1000.0,
                text=text,
            ))

        utterances.append(Utterance(
            start_at=start_at_ms / 1000.0,  # ms → 초
            end_at=end_at_ms / 1000.0,
            msg=msg,
            words=words,
        ))
    logger.info(f"utterance 파싱 완료: {len(utterances)}개")
    return utterances


def sort_by_time(utterances: list[Utterance]) -> list[Utterance]:
    """start_at 기준 시간순 정렬"""
    return sorted(utterances, key=lambda u: u.start_at)


def _similarity(a: str, b: str) -> float:
    """두 문자열의 유사도 계산 (0~1)"""
    return SequenceMatcher(None, a, b).ratio()


def remove_duplicates(utterances: list[Utterance]) -> list[Utterance]:
    """
    유사도 기반 중복 발화 제거.
    직전 발화와 시간상 가깝고 유사도가 DUPLICATE_THRESHOLD 이상인 경우만
    STT 중복으로 판단합니다. 다른 사건에서 반복된 내용은 보존합니다.
    """
    if not utterances:
        return []

    result = [utterances[0]]
    for current in utterances[1:]:
        previous = result[-1]
        gap = current.start_at - previous.end_at
        is_duplicate = (
            gap <= DUPLICATE_MAX_GAP_SECONDS
            and _similarity(current.msg, previous.msg) >= DUPLICATE_THRESHOLD
        )
        if not is_duplicate:
            result.append(current)

    removed = len(utterances) - len(result)
    if removed:
        logger.info(f"중복 발화 {removed}개 제거")
    return result


def to_paragraph_events(utterances: list[Utterance]) -> list[Event]:
    """시간 침묵을 추정하지 않고 RTZR 문단 단위를 그대로 유지합니다."""
    events = [Event(utterances=[utterance]) for utterance in utterances]
    logger.info(f"RTZR 문단 유지 완료: {len(events)}개 문단")
    return events


def format_timestamp(seconds: float) -> str:
    """초 단위 시각을 화면용 MM:SS 형태로 바꿉니다."""
    total_seconds = max(0, int(seconds))
    minutes, remaining_seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{remaining_seconds:02d}"


def _find_time_label(
    text: str,
    words: list[WordTimestamp],
    default_start_at: float,
) -> tuple[str | None, float]:
    for pattern, fixed_label in TIME_PATTERNS:
        match = pattern.search(text)
        if match:
            # 문장 중간의 "저녁 먹고"처럼 이어지는 표현은 경계로 쓰지 않습니다.
            if match.start() != 0:
                return None, default_start_at
            label = fixed_label or match.group(0).replace(" ", "")
            search_from = 0
            for word in words:
                word_index = text.find(word.text, search_from)
                if word_index == -1:
                    continue
                if word_index <= match.start() < word_index + len(word.text):
                    return label, word.start_at
                search_from = word_index + len(word.text)
            return label, default_start_at
    return None, default_start_at


def _split_utterance_into_sentences(utterance: Utterance) -> list[Sentence]:
    """RTZR 발화를 문장 부호 기준으로 나누고 시간 표현을 표시합니다."""
    chunks = [
        chunk.strip()
        for chunk in re.findall(r"[^.!?]+[.!?]+|[^.!?]+$", utterance.msg)
        if chunk.strip()
    ]
    if not chunks:
        return []

    sentences = []
    for chunk in chunks:
        time_label, time_start_at = _find_time_label(
            chunk,
            utterance.words,
            utterance.start_at,
        )
        sentences.append(Sentence(
            text=chunk,
            start_at=time_start_at if time_label else utterance.start_at,
            time_label=time_label,
            is_complete=bool(re.search(r"[.!?]+$", chunk)),
        ))
    return sentences


def _build_section(sentences: list[Sentence]) -> TimelineSection:
    first = sentences[0]
    return TimelineSection(
        label=format_timestamp(first.start_at),
        start_at=first.start_at,
        text=" ".join(sentence.text for sentence in sentences),
    )


def build_timeline(processed: ProcessedTranscript) -> list[TimelineSection]:
    """
    발화의 실제 순서를 보존한 채 시간순 문단을 만듭니다.

    문장 맨 앞의 시간 표현만 분리 힌트로 사용하고, 화면에는 실제 녹음 시각을 표시합니다.
    침묵 길이·문맥 유사도 점수는 사용하지 않습니다.
    """
    sentences = [
        sentence
        for utterance in processed.raw_utterances
        for sentence in _split_utterance_into_sentences(utterance)
    ]
    if not sentences:
        return []

    sections: list[TimelineSection] = []
    current: list[Sentence] = []

    for sentence in sentences:
        has_time_boundary = (
            bool(sentence.time_label)
            and len(current) >= MIN_PARAGRAPH_SENTENCES
        )
        if has_time_boundary:
            sections.append(_build_section(current))
            current = []

        current.append(sentence)
        if len(current) >= MAX_PARAGRAPH_SENTENCES and sentence.is_complete:
            sections.append(_build_section(current))
            current = []

    if current:
        # 마지막 한 문장 조각은 이전 문단에 붙여 화면이 잘게 쪼개지지 않게 합니다.
        if len(current) < MIN_PARAGRAPH_SENTENCES and sections:
            previous = sections[-1]
            sections[-1] = TimelineSection(
                label=previous.label,
                start_at=previous.start_at,
                text=f"{previous.text} {current[0].text}",
            )
        else:
            sections.append(_build_section(current))

    logger.info(f"시간순 기록 생성 완료: {len(sections)}개 구간")
    return sections


def process(rtzr_result: dict) -> ProcessedTranscript:
    """
    RTZR 전사 결과를 후처리 파이프라인에 통과시킵니다.

    Args:
        rtzr_result: RTZR API GET /v1/transcribe/{id} 응답 dict

    Returns:
        ProcessedTranscript (events, raw_utterances, duplicate_count)
    """
    parsed_utterances = sort_by_time(parse_utterances(rtzr_result))
    utterances = remove_duplicates(parsed_utterances)
    events = to_paragraph_events(utterances)

    return ProcessedTranscript(
        events=events,
        raw_utterances=utterances,
        duplicate_count=len(parsed_utterances) - len(utterances),
    )
