"""
RTZR STT API Client

인증 가이드: https://developers.rtzr.ai/docs/authentications/
Batch STT 가이드: https://developers.rtzr.ai/docs/stt-file/
"""

import json
import time
import logging
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://openapi.vito.ai"

# RTZR STT 요청 설정
# - use_disfluency_filter: 추임새(어, 음, 그) 제거
# - use_paragraph_splitter: 의미 단위 문단 분리 (후처리에 유리)
# - use_itn: 숫자/단위 표기 변환 (예: 삼 → 3)
TRANSCRIBE_CONFIG = {
    "use_disfluency_filter": True,
    "use_paragraph_splitter": True,
    "paragraph_splitter": {"max": 100},
    "use_itn": True,
}


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
        resp = requests.post(
            f"{BASE_URL}/v1/authenticate",
            headers={"accept": "application/json"},
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        if not resp.ok:
            raise RTZRError(f"인증 실패 ({resp.status_code}): {resp.text}")

        data = resp.json()
        self._token = data["access_token"]
        # 만료 6시간, 5분 여유를 두고 갱신
        self._token_expires_at = now + timedelta(hours=6) - timedelta(minutes=5)
        logger.info("RTZR 인증 토큰 발급 완료")
        return self._token

    def submit_transcription(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        """
        음성 파일 전사 요청 → transcribe_id 반환.

        API: POST https://openapi.vito.ai/v1/transcribe
        """
        token = self.get_token()
        logger.info(f"전사 요청 시작 (파일명: {filename}, 크기: {len(audio_bytes)} bytes)")

        resp = requests.post(
            f"{BASE_URL}/v1/transcribe",
            headers={
                "accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            data={"config": json.dumps(TRANSCRIBE_CONFIG)},
            files={"file": (filename, audio_bytes)},
        )
        if not resp.ok:
            raise RTZRError(f"전사 요청 실패 ({resp.status_code}): {resp.text}")

        transcribe_id = resp.json()["id"]
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
        resp = requests.get(
            f"{BASE_URL}/v1/transcribe/{transcribe_id}",
            headers={
                "accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        if not resp.ok:
            raise RTZRError(f"결과 조회 실패 ({resp.status_code}): {resp.text}")

        return resp.json()

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        poll_interval: int = 3,
        max_wait: int = 300,
    ) -> dict:
        """
        음성 파일 전사 요청 후 완료까지 폴링.

        Args:
            audio_bytes: 음성 파일 바이트
            filename: 파일명 (확장자로 포맷 추정)
            poll_interval: 폴링 간격 (초)
            max_wait: 최대 대기 시간 (초)

        Returns:
            RTZR 전사 결과 dict (results.utterances 포함)
        """
        transcribe_id = self.submit_transcription(audio_bytes, filename)

        elapsed = 0
        while elapsed < max_wait:
            result = self.get_result(transcribe_id)
            status = result.get("status")

            if status == "completed":
                logger.info(f"전사 완료 ({elapsed}초 소요)")
                return result
            elif status == "failed":
                raise RTZRError(f"전사 실패: {result}")

            logger.debug(f"전사 진행 중... ({elapsed}초 경과, 상태: {status})")
            time.sleep(poll_interval)
            elapsed += poll_interval

        raise RTZRError(f"전사 타임아웃 ({max_wait}초 초과)")
