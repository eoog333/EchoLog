import logging
import time

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.services import reflection_generator, transcript_processor
from app.services.rtzr_client import RTZRClient, RTZRError

logger = logging.getLogger(__name__)
router = APIRouter()

# RTZRClient 인스턴스 (앱 생명주기 동안 재사용 → 토큰 캐싱 효과)
_rtzr_client: RTZRClient | None = None
MAX_KEYWORDS = 5


def get_rtzr_client() -> RTZRClient:
    global _rtzr_client
    if _rtzr_client is None:
        settings = get_settings()
        _rtzr_client = RTZRClient(
            client_id=settings.rtzr_client_id,
            client_secret=settings.rtzr_client_secret,
        )
    return _rtzr_client


def get_raw_transcript(rtzr_result: dict) -> str:
    """RTZR가 반환한 utterance 텍스트를 후처리 없이 합칩니다."""
    utterances = rtzr_result.get("results", {}).get("utterances", [])
    return " ".join(
        utterance.get("msg", "").strip()
        for utterance in utterances
        if utterance.get("msg", "").strip()
    )


def parse_keywords(raw_keywords: str) -> list[str]:
    """쉼표로 입력된 키워드를 정리해 RTZR 요청 형식으로 변환합니다."""
    keywords: list[str] = []
    seen: set[str] = set()
    for keyword in raw_keywords.split(","):
        cleaned = keyword.strip()
        if cleaned and cleaned not in seen:
            keywords.append(cleaned)
            seen.add(cleaned)
        if len(keywords) == MAX_KEYWORDS:
            break
    return keywords


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    keywords: str = Form(""),
):
    """
    음성 파일을 받아 전사하고 Reflection을 반환합니다.

    Request:
        multipart/form-data { file: audio (wav/mp3/m4a/webm 등) }

    Response:
        {
            "reflection": str,       # 정제된 회고 텍스트
            "raw_transcript": str,   # RTZR 필터 전 원본 전사 텍스트
            "timeline": [...],       # 시간순 기록 문단 목록
            "processing": {...},     # 적용된 후처리 정보
            "mode": str,             # 현재는 "timeline"
            "processing_time": float # 처리 시간(초)
        }
    """
    start_time = time.time()

    # 지원 포맷 확인 (RTZR 지원: mp4, m4a, mp3, amr, flac, wav)
    supported = {"audio/wav", "audio/mpeg", "audio/mp4", "audio/webm",
                 "audio/x-m4a", "audio/flac", "audio/amr", "video/webm"}
    if file.content_type and file.content_type not in supported:
        logger.warning(f"지원하지 않는 포맷: {file.content_type}")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="파일이 비어 있습니다.")

    filename = file.filename or "audio.wav"
    keyword_list = parse_keywords(keywords)
    logger.info(f"파일 수신: {filename} ({len(audio_bytes)} bytes)")

    try:
        # 1. RTZR 원본 전사: 필터 없이 사용자가 말한 흐름을 보존합니다.
        client = get_rtzr_client()
        raw_rtzr_result = await run_in_threadpool(
            client.transcribe,
            audio_bytes,
            filename=filename,
            keywords=keyword_list,
            mode="raw",
        )
        raw_transcript = get_raw_transcript(raw_rtzr_result)

        # 2. RTZR 정리 전사: 시간순 기록을 만들 분석 단위를 받습니다.
        clean_rtzr_result = await run_in_threadpool(
            client.transcribe,
            audio_bytes,
            filename=filename,
            keywords=keyword_list,
            mode="clean",
        )
        processed = transcript_processor.process(clean_rtzr_result)
        timeline = transcript_processor.build_timeline(processed)

        # 3. Reflection 생성
        settings = get_settings()
        result = reflection_generator.generate(processed, llm_api_key=settings.llm_api_key)

        processing_time = round(time.time() - start_time, 2)

        return JSONResponse(content={
            "reflection": result["reflection"],
            "raw_transcript": raw_transcript,
            "timeline": [
                {
                    "label": section.label,
                    "start_at": section.start_at,
                    "text": section.text,
                }
                for section in timeline
            ],
            "paragraphs": [
                {
                    "text": event.text,
                    "start_at": event.start_at,
                }
                for event in processed.events
            ],
            "mode": result["mode"],
            "processing": {
                "paragraph_count": len(processed.events),
                "duplicate_count": processed.duplicate_count,
            },
            "processing_time": processing_time,
        })

    except RTZRError as e:
        logger.error(f"RTZR 오류: {e}")
        raise HTTPException(status_code=502, detail=f"STT 처리 오류: {e}") from e
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="서버에서 음성 처리 중 오류가 발생했습니다.",
        ) from e
