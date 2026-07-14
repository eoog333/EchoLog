import json

import requests

from app.services.rtzr_client import REQUEST_TIMEOUT, RTZRClient, RTZRError


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 400

    def json(self):
        return self._payload


def test_get_token_uses_network_timeout(monkeypatch):
    captured = {}

    def fake_post(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse({"access_token": "test-token"})

    monkeypatch.setattr(requests, "post", fake_post)

    client = RTZRClient("client-id", "client-secret")

    assert client.get_token() == "test-token"
    assert captured["timeout"] == REQUEST_TIMEOUT


def test_get_token_converts_network_error_to_rtzr_error(monkeypatch):
    def fake_post(*args, **kwargs):
        raise requests.Timeout("connection timed out")

    monkeypatch.setattr(requests, "post", fake_post)

    client = RTZRClient("client-id", "client-secret")

    try:
        client.get_token()
    except RTZRError as exc:
        assert str(exc) == "RTZR 인증 서버에 연결할 수 없습니다."
    else:
        raise AssertionError("RTZRError가 발생해야 합니다.")


def test_submit_transcription_uses_clean_config_and_sends_keywords(monkeypatch):
    captured = {}

    def fake_post(*args, **kwargs):
        captured.update(kwargs)
        if args[0].endswith("/authenticate"):
            return FakeResponse({"access_token": "test-token"})
        return FakeResponse({"id": "transcribe-id"})

    monkeypatch.setattr(requests, "post", fake_post)
    client = RTZRClient("client-id", "client-secret")

    assert client.submit_transcription(b"audio", keywords=["면접", "발표"], mode="clean") == "transcribe-id"

    config = json.loads(captured["data"]["config"])
    assert config["paragraph_splitter"] == {"max": 50}
    assert config["use_disfluency_filter"] is True
    assert config["use_itn"] is True
    assert config["use_word_timestamp"] is True
    assert "use_insight" not in config
    assert config["keywords"] == ["면접", "발표"]


def test_submit_transcription_uses_unfiltered_raw_config(monkeypatch):
    captured = {}

    def fake_post(*args, **kwargs):
        captured.update(kwargs)
        if args[0].endswith("/authenticate"):
            return FakeResponse({"access_token": "test-token"})
        return FakeResponse({"id": "transcribe-id"})

    monkeypatch.setattr(requests, "post", fake_post)
    client = RTZRClient("client-id", "client-secret")

    client.submit_transcription(b"audio", mode="raw")

    config = json.loads(captured["data"]["config"])
    assert config == {
        "use_disfluency_filter": False,
        "use_paragraph_splitter": False,
        "use_itn": False,
    }
