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
