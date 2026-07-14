"""
Reflection Generator

후처리된 전사 결과를 Reflection 텍스트로 변환합니다.

- LLM API 키가 있으면: 구어체 → 서술체 변환
- LLM API 키가 없으면: Timeline 형태 그대로 반환 (fallback)

설계 원칙:
    LLM은 문체를 다듬는 보조 역할만 수행합니다.
    새로운 사실을 추가하거나 내용을 변형하지 않습니다.
"""

import logging
from app.services.transcript_processor import ProcessedTranscript

logger = logging.getLogger(__name__)


def generate(processed: ProcessedTranscript, llm_api_key: str = "") -> dict:
    """
    ProcessedTranscript를 Reflection 텍스트로 변환합니다.

    Args:
        processed: 후처리된 전사 결과
        llm_api_key: LLM API 키 (없으면 Timeline 모드로 fallback)

    Returns:
        {
            "reflection": str,   # 출력 텍스트
            "mode": str          # "timeline" | "llm"
        }
    """
    if not llm_api_key:
        logger.info("LLM API 키 없음 → Timeline 모드로 반환")
        return {
            "reflection": processed.timeline_text,
            "mode": "timeline",
        }

    try:
        reflection = _call_llm(processed.timeline_text, llm_api_key)
        return {
            "reflection": reflection,
            "mode": "llm",
        }
    except Exception as e:
        logger.warning(f"LLM 호출 실패, Timeline 모드로 fallback: {e}")
        return {
            "reflection": processed.timeline_text,
            "mode": "timeline",
        }


def _call_llm(text: str, api_key: str) -> str:
    """
    LLM API를 호출하여 구어체를 서술체로 변환합니다.
    현재는 구현 placeholder입니다.
    """
    # TODO: LLM API 연동 (OpenAI / Gemini / Claude 등)
    # 예시 프롬프트:
    # SYSTEM: 당신은 사용자의 하루 기록을 정리하는 도우미입니다.
    #   규칙:
    #   1. 원본에 없는 새로운 사실을 추가하지 마세요.
    #   2. 시간 순서를 유지하세요.
    #   3. 구어체를 자연스러운 서술체로 다듬으세요.
    # USER: {text}
    logger.info("LLM 호출 (구현 예정)")
    return text  # 현재는 그대로 반환
