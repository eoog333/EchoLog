from fastapi.testclient import TestClient

from app.main import app
from app.routers import transcribe


class FakeRTZRClient:
    def transcribe(self, audio_bytes, filename="audio.wav"):
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
                ]
            },
        }


def test_transcribe_response_keeps_raw_duplicates_and_deduplicates_reflection():
    original_client = transcribe._rtzr_client
    transcribe._rtzr_client = FakeRTZRClient()

    try:
        client = TestClient(app)
        response = client.post(
            "/api/transcribe",
            files={"file": ("recording.wav", b"RIFFfakewav", "audio/wav")},
        )
    finally:
        transcribe._rtzr_client = original_client

    assert response.status_code == 200
    body = response.json()
    assert (
        body["raw_transcript"]
        == "오늘은 발표 준비를 했습니다. 오늘은 발표 준비를 했습니다. 자료를 다시 읽었습니다."
    )
    assert body["reflection"] == "• 오늘은 발표 준비를 했습니다. 자료를 다시 읽었습니다."
    assert body["paragraphs"] == [
        {
            "text": "오늘은 발표 준비를 했습니다. 자료를 다시 읽었습니다.",
            "start_at": 0.0,
        }
    ]
    assert body["mode"] == "timeline"
