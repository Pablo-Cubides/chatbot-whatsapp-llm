import hashlib
import hmac

import pytest

from src.services.whatsapp_cloud_provider import CloudProvider, verify_webhook, verify_webhook_signature

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("mode", "token", "env_token", "expected"),
    [
        ("subscribe", "ok-token", "ok-token", "123"),
        ("subscribe", "bad-token", "ok-token", None),
        ("unsubscribe", "ok-token", "ok-token", None),
    ],
)
def test_verify_webhook(mode: str, token: str, env_token: str, expected: str | None, monkeypatch) -> None:
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", env_token)
    challenge = "123"
    assert verify_webhook(mode, token, challenge) == expected


def test_verify_webhook_signature_valid_and_invalid(monkeypatch) -> None:
    payload = b'{"entry": []}'
    secret = "super-secret"
    monkeypatch.setenv("WHATSAPP_APP_SECRET", secret)

    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    valid_signature = f"sha256={digest}"

    assert verify_webhook_signature(payload, valid_signature) is True
    assert verify_webhook_signature(payload, "sha256=deadbeef") is False


def test_receive_message_text_normalization() -> None:
    provider = CloudProvider()
    normalized = provider.receive_message(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "573001112233",
                                        "timestamp": "1700000000",
                                        "type": "text",
                                        "text": {"body": "Hola"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
    )

    assert normalized is not None
    assert normalized.chat_id == "573001112233"
    assert normalized.text == "Hola"
