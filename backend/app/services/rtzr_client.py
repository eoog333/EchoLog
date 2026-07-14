"""
RTZR STT API Client

인증 가이드: https://developers.rtzr.ai/docs/authentications/
Batch STT 가이드: https://developers.rtzr.ai/docs/stt-file/
"""

import logging
import copy
import json
import time
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://openapi.vito.ai"
REQUEST_TIMEOUT = (10, 60)  # 연결 10초, 응답 60초

# 원본 전사용 설정: 사용자가 말한 흐름을 최대한 그대로 보존합니다.
RAW_TRANSCRIBE_CONFIG = {
    "use_disfluency_filter": False,
    "use_paragraph_splitter": False,
    "use_itn": False,
}

# 시간순 기록용 설정: RTZR이 읽기 좋은 분석 단위를 만들도록 요청합니다.
CLEAN_TRANSCRIBE_CONFIG = {
    "use_disfluency_filter": True,
    "use_paragraph_splitter": True,
    "paragraph_splitter": {"max": 50},
    "use_itn": True,
    "use_word_timestamp": True,
}


def build_transcribe_config(
    keywords: list[str] | None = None,
    mode: str = "clean",
) -> dict:
    """원본 또는 시간순 기록용 RTZR 설정을 만듭니다."""
    if mode == "raw":
        config = copy.deepcopy(RAW_TRANSCRIBE_CONFIG)
    elif mode == "clean":
        config = copy.deepcopy(CLEAN_TRANSCRIBE_CONFIG)
    else:
        raise ValueError(f"지원하지 않는 전사 모드입니다: {mode}")

    cleaned_keywords = [keyword.strip() for keyword in keywords or [] if keyword.strip()]
    if cleaned_keywords:
        config["keywords"] = cleaned_keywords
    return config


class RTZRError(Exception):
    """RTZR API 관련 오류"""
    pass


class RTZRClient:
    """
    RTZR STT API 클라이언트

    사용 예시:
        client = RTZRClient(client_id="...", client_secret="...")
        result = client.transcribe(audio_bytes)
        print(result["results"]["utterances"])
    """

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    def get_token(self) -> str:
        """
        JWT 인증 토큰 발급.
        토큰 만료(6시간) 5분 전에 자동으로 갱신합니다.

        API: POST https://openapi.vito.ai/v1/authenticate
        """
        now = datetime.now()
        if self._token and self._token_expires_at and now < self._token_expires_at:
            return self._token

        logger.info("RTZR 인증 토큰 발급 요청")
        try:
            resp = requests.post(
                f"{BASE_URL}/v1/authenticate",
                headers={"accept": "application/json"},
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise RTZRError("RTZR 인증 서버에 연결할 수 없습니다.") from exc

        if not resp.ok:
            raise RTZRError(f"RTZR 인증에 실패했습니다. ({resp.status_code})")

        try:
            data = resp.json()
            self._token = data["access_token"]
        except (ValueError, KeyError, TypeError) as exc:
            raise RTZRError("RTZR 인증 응답 형식이 올바르지 않습니다.") from exc
        # 만료 6시간, 5분 여유를 두고 갱신
        self._token_expires_at = now + timedelta(hours=6) - timedelta(minutes=5)
        logger.info("RTZR 인증 토큰 발급 완료")
        return self._token

    def submit_transcription(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        keywords: list[str] | None = None,
        mode: str = "clean",
    ) -> str:
        """
        음성 파일 전사 요청 → transcribe_id 반환.

        API: POST https://openapi.vito.ai/v1/transcribe
        """
        token = self.get_token()
        logger.info(f"전사 요청 시작 (파일명: {filename}, 크기: {len(audio_bytes)} bytes)")

        try:
            resp = requests.post(
                f"{BASE_URL}/v1/transcribe",
                headers={
                    "accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                data={
                    "config": json.dumps(
                        build_transcribe_config(keywords, mode),
                        ensure_ascii=False,
                    )
                },
                files={"file": (filename, audio_bytes)},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise RTZRError("RTZR에 전사 요청을 전송할 수 없습니다.") from exc

        if not resp.ok:
            raise RTZRError(f"RTZR 전사 요청에 실패했습니다. ({resp.status_code})")

        try:
            transcribe_id = resp.json()["id"]
        except (ValueError, KeyError, TypeError) as exc:
            raise RTZRError("RTZR 전사 요청 응답 형식이 올바르지 않습니다.") from exc
        logger.info(f"전사 요청 완료 (transcribe_id: {transcribe_id})")
        return transcribe_id

    def get_result(self, transcribe_id: str) -> dict:
        """
        전사 결과 조회.

        API: GET https://openapi.vito.ai/v1/transcribe/{transcribe_id}

        Returns:
            status: "transcribing" | "completed" | "failed"
        """
        token = self.get_token()
        try:
            resp = requests.get(
                f"{BASE_URL}/v1/transcribe/{transcribe_id}",
                headers={
                    "accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise RTZRError("RTZR 전사 결과를 조회할 수 없습니다.") from exc

        if not resp.ok:
            raise RTZRError(f"RTZR 전사 결과 조회에 실패했습니다. ({resp.status_code})")

        try:
            result = resp.json()
        except ValueError as exc:
            raise RTZRError("RTZR 전사 결과 응답 형식이 올바르지 않습니다.") from exc

        if not isinstance(result, dict):
            raise RTZRError("RTZR 전사 결과 응답 형식이 올바르지 않습니다.")
        return result

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        poll_interval: int = 3,
        max_wait: int = 300,
        keywords: list[str] | None = None,
        mode: str = "clean",
    ) -> dict:
        """
        음성 파일 전사 요청 후 완료까지 폴링.

        Args:
            audio_bytes: 음성 파일 바이트
            filename: 파일명 (확장자로 포맷 추정)
            poll_interval: 폴링 간격 (초)
            max_wait: 최대 대기 시간 (초)
            keywords: 인식 정확도 향상을 위한 선택 키워드
            mode: "raw"(원본 전사) 또는 "clean"(시간순 기록용 전사)

        Returns:
            RTZR 전사 결과 dict (results.utterances 포함)
        """
        transcribe_id = self.submit_transcription(audio_bytes, filename, keywords, mode)

        started_at = time.monotonic()
        deadline = started_at + max_wait
        while time.monotonic() < deadline:
            result = self.get_result(transcribe_id)
            status = result.get("status")
            elapsed = int(time.monotonic() - started_at)

            if status == "completed":
                logger.info(f"전사 완료 ({elapsed}초 소요)")
                return result
            elif status == "failed":
                raise RTZRError("RTZR 전사 처리에 실패했습니다.")

            logger.debug(f"전사 진행 중... ({elapsed}초 경과, 상태: {status})")
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(poll_interval, remaining))

        raise RTZRError(f"전사 타임아웃 ({max_wait}초 초과)")
