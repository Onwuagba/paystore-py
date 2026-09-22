"""Tests for HTTPClient's error classification and retry behavior."""

from unittest.mock import MagicMock

import httpx
import pytest

from paystore.core.config import Config
from paystore.core.exceptions import (
    AuthenticationError,
    NetworkError,
    ProviderError,
    RateLimitError,
)
from paystore.core.http_client import HTTPClient


@pytest.fixture
def client():
    return HTTPClient(Config(provider="paystack", api_key="sk_test_mock"))


def _http_status_error(status_code: int, headers=None) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(status_code, request=request, headers=headers)
    return httpx.HTTPStatusError("error", request=request, response=response)


@pytest.mark.parametrize("status_code", [401, 403])
def test_get_raises_authentication_error(client, monkeypatch, status_code):
    monkeypatch.setattr(
        client.client, "get", MagicMock(side_effect=_http_status_error(status_code))
    )
    with pytest.raises(AuthenticationError):
        client.get("https://example.com")


def test_post_raises_authentication_error_without_retry(client, monkeypatch):
    mock_get = MagicMock(side_effect=_http_status_error(401))
    monkeypatch.setattr(client.client, "post", mock_get)
    with pytest.raises(AuthenticationError):
        client.post("https://example.com", data={})
    assert mock_get.call_count == 1


def test_get_retries_then_raises_rate_limit_error(client, monkeypatch):
    monkeypatch.setattr("paystore.core.http_client.time.sleep", lambda _: None)
    mock_get = MagicMock(side_effect=_http_status_error(429))
    monkeypatch.setattr(client.client, "get", mock_get)
    with pytest.raises(RateLimitError):
        client.get("https://example.com")
    assert mock_get.call_count == 3  # initial + 2 retries


def test_get_respects_retry_after_header(client, monkeypatch):
    sleep_calls = []
    monkeypatch.setattr(
        "paystore.core.http_client.time.sleep", lambda s: sleep_calls.append(s)
    )
    mock_get = MagicMock(
        side_effect=_http_status_error(429, headers={"Retry-After": "3"})
    )
    monkeypatch.setattr(client.client, "get", mock_get)
    with pytest.raises(RateLimitError):
        client.get("https://example.com")
    assert sleep_calls == [3.0, 3.0]


def test_get_caps_retry_after_at_max(client, monkeypatch):
    sleep_calls = []
    monkeypatch.setattr(
        "paystore.core.http_client.time.sleep", lambda s: sleep_calls.append(s)
    )
    mock_get = MagicMock(
        side_effect=_http_status_error(429, headers={"Retry-After": "9999"})
    )
    monkeypatch.setattr(client.client, "get", mock_get)
    with pytest.raises(RateLimitError):
        client.get("https://example.com")
    assert all(s == 30.0 for s in sleep_calls)


def test_get_falls_back_to_backoff_for_invalid_retry_after(client, monkeypatch):
    sleep_calls = []
    monkeypatch.setattr(
        "paystore.core.http_client.time.sleep", lambda s: sleep_calls.append(s)
    )
    mock_get = MagicMock(
        side_effect=_http_status_error(429, headers={"Retry-After": "not-a-number"})
    )
    monkeypatch.setattr(client.client, "get", mock_get)
    with pytest.raises(RateLimitError):
        client.get("https://example.com")
    assert sleep_calls == [0.5, 1.0]


def test_get_retries_5xx_then_succeeds(client, monkeypatch):
    monkeypatch.setattr("paystore.core.http_client.time.sleep", lambda _: None)
    request = httpx.Request("GET", "https://example.com")
    ok_response = httpx.Response(200, json={"status": True}, request=request)
    mock_get = MagicMock(side_effect=[_http_status_error(503), ok_response])
    monkeypatch.setattr(client.client, "get", mock_get)
    result = client.get("https://example.com")
    assert result == {"status": True}
    assert mock_get.call_count == 2


def test_get_gives_up_on_4xx_without_retry(client, monkeypatch):
    mock_get = MagicMock(side_effect=_http_status_error(400))
    monkeypatch.setattr(client.client, "get", mock_get)
    with pytest.raises(ProviderError):
        client.get("https://example.com")
    assert mock_get.call_count == 1


def test_get_retries_network_error_then_raises(client, monkeypatch):
    monkeypatch.setattr("paystore.core.http_client.time.sleep", lambda _: None)
    request = httpx.Request("GET", "https://example.com")
    mock_get = MagicMock(side_effect=httpx.ConnectError("boom", request=request))
    monkeypatch.setattr(client.client, "get", mock_get)
    with pytest.raises(NetworkError):
        client.get("https://example.com")
    assert mock_get.call_count == 3


def test_post_form_raises_network_error_without_retry(client, monkeypatch):
    request = httpx.Request("POST", "https://example.com")
    mock_post = MagicMock(side_effect=httpx.ConnectError("boom", request=request))
    monkeypatch.setattr(client.client, "post", mock_post)
    with pytest.raises(NetworkError):
        client.post_form("https://example.com", data={})
    assert mock_post.call_count == 1


def test_raised_exceptions_suppress_the_original_httpx_cause(client, monkeypatch):
    """
    httpx.HTTPStatusError's default message embeds the full URL, and some
    providers (Remita) embed credentials in the URL path — so the raw
    httpx exception must never ride along as __cause__/__context__,
    or a normal traceback would print it and leak the secret.
    """
    monkeypatch.setattr(
        client.client, "get", MagicMock(side_effect=_http_status_error(401))
    )
    try:
        client.get("https://example.com")
    except AuthenticationError as e:
        assert e.__cause__ is None
    else:
        pytest.fail("expected AuthenticationError")


def test_network_error_message_never_includes_the_full_url(client, monkeypatch):
    secret_url = (
        "https://api.example.com/echannelsvc/MERCHANT/SECRET_API_KEY/status.reg"
    )
    request = httpx.Request("GET", secret_url)
    monkeypatch.setattr(
        client.client,
        "get",
        MagicMock(side_effect=httpx.ConnectError("boom", request=request)),
    )
    with pytest.raises(NetworkError) as excinfo:
        client.get(secret_url)
    assert "SECRET_API_KEY" not in str(excinfo.value)


def test_get_logs_are_scrubbed_of_url_path(client, monkeypatch, caplog):
    secret_url = (
        "https://api.example.com/echannelsvc/MERCHANT/SECRET_API_KEY/status.reg"
    )
    monkeypatch.setattr(
        client.client,
        "get",
        MagicMock(
            return_value=httpx.Response(
                200, json={"ok": True}, request=httpx.Request("GET", secret_url)
            )
        ),
    )
    with caplog.at_level("DEBUG", logger="paystore.http"):
        client.get(secret_url)
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "SECRET_API_KEY" not in log_text
    assert "api.example.com" in log_text
