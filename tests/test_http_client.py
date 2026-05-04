from __future__ import annotations

from email.message import Message

from product_radar_parser.config import ParserConfig, normalize_session_cookie
from product_radar_parser.http_client import RateLimitedHttpClient


class FakeResponse:
    status = 200

    def __init__(self):
        self.headers = Message()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return b"ok"

    def geturl(self):
        return "https://productradar.ru/private"


class FakeOpener:
    def __init__(self):
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        return FakeResponse()


def test_session_cookie_is_sent_but_not_returned():
    config = ParserConfig(session_cookie="wordpress_logged_in=secret", min_delay_seconds=0, max_delay_seconds=0)
    client = RateLimitedHttpClient(config, sleeper=lambda _: None)
    fake_opener = FakeOpener()
    client._opener = fake_opener

    result = client.get("https://productradar.ru/private")

    assert fake_opener.requests[0].get_header("Cookie") == "wordpress_logged_in=secret"
    assert "secret" not in repr(result)
    assert not hasattr(result, "headers")


def test_config_repr_does_not_include_session_cookie():
    config = ParserConfig(session_cookie="wordpress_logged_in=secret")

    assert "secret" not in repr(config)


def test_cookie_header_prefix_is_accepted_and_stripped():
    assert normalize_session_cookie("Cookie: wordpress_logged_in=secret; other=value") == "wordpress_logged_in=secret; other=value"


def test_session_cookie_with_cookie_prefix_is_sent_as_cookie_value():
    config = ParserConfig(session_cookie="Cookie: wordpress_logged_in=secret", min_delay_seconds=0, max_delay_seconds=0)
    client = RateLimitedHttpClient(config, sleeper=lambda _: None)
    fake_opener = FakeOpener()
    client._opener = fake_opener

    client.get("https://productradar.ru/private")

    assert fake_opener.requests[0].get_header("Cookie") == "wordpress_logged_in=secret"
