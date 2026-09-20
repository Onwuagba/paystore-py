"""Tests for Config, particularly secret masking."""

from paystore.core.config import Config


def test_repr_masks_secrets():
    config = Config(
        provider="paystack",
        api_key="sk_test_SUPERSECRET1234",
        webhook_secret="whsec_ANOTHERSECRET",
        api_secret="alsosecret",
    )
    text = repr(config)
    assert "SUPERSECRET1234" not in text
    assert "ANOTHERSECRET" not in text
    assert "alsosecret" not in text


def test_str_masks_secrets():
    config = Config(provider="paystack", api_key="sk_test_SUPERSECRET1234")
    text = str(config)
    assert "SUPERSECRET1234" not in text


def test_masked_repr_shows_last_four_chars():
    config = Config(provider="paystack", api_key="sk_test_SUPERSECRET1234")
    assert "***1234" in repr(config)


def test_unmasked_fields_still_shown_in_full():
    config = Config(provider="paystack", api_key="sk_test_key", environment="sandbox")
    assert "provider='paystack'" in repr(config)
    assert "environment='sandbox'" in repr(config)


def test_actual_secret_values_still_accessible():
    config = Config(provider="paystack", api_key="sk_test_SUPERSECRET1234")
    assert config.api_key == "sk_test_SUPERSECRET1234"


def test_short_secret_is_fully_masked_not_partially_exposed():
    config = Config(provider="paystack", api_key="ab")
    assert "***" in repr(config)
    assert "ab" not in repr(config)


def test_none_secrets_are_not_masked_into_a_string():
    config = Config(provider="paystack", api_key="sk_test_key")
    assert "webhook_secret=None" in repr(config)
