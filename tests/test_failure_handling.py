from product_radar_parser.logging_config import redact


def test_redact_masks_credential_like_values():
    assert redact("Authorization: Bearer secret") == "[REDACTED]"
    assert redact("https://example.com/?access_token=secret") == "[REDACTED]"
    assert redact("ordinary message") == "ordinary message"
