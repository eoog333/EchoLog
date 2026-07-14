import asyncio
from types import SimpleNamespace

import httpx

from app.main import app
from app.routers import transcribe


class FakeRTZRClient:
    def __init__(self):
        self.modes = []

    def transcribe(self, audio_bytes, filename="audio.wav", keywords=None, mode="clean"):
        self.keywords = keywords
        self.modes.append(mode)
        return {
            "status": "completed",
            "results": {
                "utterances": [
                    {
                        "start_at": 0,
                        "duration": 1000,
                        "msg": "오늘은 발표 준비를 했습니다.",
                    },
                    {
                        "start_at": 1200,
                        "duration": 1000,
                        "msg": "오늘은 발표 준비를 했습니다.",
                    },
                    {
                        "start_at": 2600,
                        "duration": 1200,
                        "msg": "자료를 다시 읽었습니다.",
                    },
                ],
            },
        }


def test_transcribe_response_keeps_raw_duplicates_and_deduplicates_reflection(monkeypatch):
    fake_client = FakeRTZRClient()
    monkeypatch.setattr(transcribe, "_rtzr_client", fake_client)
    monkeypatch.setattr(
        transcribe,
        "get_settings",
        lambda: SimpleNamespace(llm_api_key=""),
    )

    async def post_transcription():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/api/transcribe",
                files={"file": ("recording.wav", b"RIFFfakewav", "audio/wav")},
                data={"keywords": "발표, 프로젝트, 발표"},
            )

    response = asyncio.run(post_transcription())

    assert response.status_code == 200
    body = response.json()
    assert (
        body["raw_transcript"]
        == "오늘은 발표 준비를 했습니다. 오늘은 발표 준비를 했습니다. 자료를 다시 읽었습니다."
    )
    assert body["reflection"] == "• 오늘은 발표 준비를 했습니다.\n• 자료를 다시 읽었습니다."
    assert body["paragraphs"] == [
        {"text": "오늘은 발표 준비를 했습니다.", "start_at": 0.0},
        {"text": "자료를 다시 읽었습니다.", "start_at": 2.6},
    ]
    assert body["mode"] == "timeline"
    assert body["processing"] == {"paragraph_count": 2, "duplicate_count": 1}
    assert fake_client.keywords == ["발표", "프로젝트"]
    assert fake_client.modes == ["raw", "clean"]
    assert body["timeline"] == [
        {
            "label": "00:00",
            "start_at": 0.0,
            "text": "오늘은 발표 준비를 했습니다. 자료를 다시 읽었습니다.",
        }
    ]
