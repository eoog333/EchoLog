"""
Reflection Generator

후처리된 전사 결과를 Reflection 텍스트로 변환합니다.

- 현재: Timeline 형태로 반환
- 향후 확장: LLM을 이용한 서술체 변환

설계 원칙:
    LLM 연동 전에도 핵심 후처리 결과는 독립적으로 사용할 수 있습니다.
"""

import logging
from app.services.transcript_processor import ProcessedTranscript

logger = logging.getLogger(__name__)


def generate(processed: ProcessedTranscript, llm_api_key: str = "") -> dict:
    """
    ProcessedTranscript를 Reflection 텍스트로 변환합니다.

    Args:
        processed: 후처리된 전사 결과
        llm_api_key: 향후 LLM 연동을 위해 예약된 API 키

    Returns:
        {
            "reflection": str,   # 출력 텍스트
            "mode": str          # 현재는 "timeline"
        }
    """
    if llm_api_key:
        logger.info("LLM API 키가 설정되어 있으나 연동은 향후 확장 예정입니다.")

    return {
        "reflection": processed.timeline_text,
        "mode": "timeline",
    }
