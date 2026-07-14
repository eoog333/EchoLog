"""
Transcript Post Processor

RTZR STT 전사 결과를 사람이 읽기 좋은 형태로 후처리합니다.

처리 흐름:
    RTZR utterances
        ↓ parse_utterances()   — utterance 목록 파싱
        ↓ sort_by_time()       — start_at 기준 시간순 정렬
        ↓ remove_duplicates()  — 유사 문장 제거 (SequenceMatcher)
        ↓ group_into_events()  — 시간 간격 기준 사건 단위 그룹핑
        ↓ ProcessedTranscript  — 후처리 완료 결과
"""

import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# 중복 판단 유사도 임계값 (0~1, 높을수록 엄격)
DUPLICATE_THRESHOLD = 0.8

# 인접 발화가 이 시간 안에 반복된 경우에만 STT 중복으로 판단
DUPLICATE_MAX_GAP_SECONDS = 3.0

# 사건 구분 시간 간격 (초): 이보다 긴 침묵이면 다른 사건으로 간주
EVENT_GAP_SECONDS = 10.0


@dataclass
class Utterance:
    """RTZR utterance 단위"""
    start_at: float   # 시작 시간 (초)
    end_at: float     # 종료 시간 (초)
    msg: str          # 발화 텍스트


@dataclass
class Event:
    """사건 단위 (연속된 utterance 그룹)"""
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

    @property
    def timeline_text(self) -> str:
        """
        LLM 없이 출력하는 Timeline 형태.
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

        utterances.append(Utterance(
            start_at=start_at_ms / 1000.0,  # ms → 초
            end_at=end_at_ms / 1000.0,
            msg=msg,
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


def group_into_events(utterances: list[Utterance]) -> list[Event]:
    """
    시간 간격 기준으로 utterance를 사건 단위로 그룹핑.
    앞 utterance 종료 시간과 현재 시작 시간의 차이가
    EVENT_GAP_SECONDS 이상이면 새 사건으로 시작합니다.
    """
    if not utterances:
        return []

    events: list[Event] = []
    current_event = Event(utterances=[utterances[0]])

    for prev, curr in zip(utterances, utterances[1:]):
        gap = curr.start_at - prev.end_at
        if gap >= EVENT_GAP_SECONDS:
            events.append(current_event)
            current_event = Event(utterances=[curr])
        else:
            current_event.utterances.append(curr)

    events.append(current_event)
    logger.info(f"사건 그룹핑 완료: {len(events)}개 사건")
    return events


def process(rtzr_result: dict) -> ProcessedTranscript:
    """
    RTZR 전사 결과를 후처리 파이프라인에 통과시킵니다.

    Args:
        rtzr_result: RTZR API GET /v1/transcribe/{id} 응답 dict

    Returns:
        ProcessedTranscript (events, raw_utterances)
    """
    utterances = parse_utterances(rtzr_result)
    utterances = sort_by_time(utterances)
    utterances = remove_duplicates(utterances)
    events = group_into_events(utterances)

    return ProcessedTranscript(events=events, raw_utterances=utterances)
