from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener
from http.cookiejar import CookieJar

from .config import ParserConfig


@dataclass(frozen=True)
class FetchResult:
    url: str
    status_code: int
    text: str
    content_sha256: str
    fetched_at: str


class RateLimitedHttpClient:
    def __init__(self, config: ParserConfig, sleeper: Callable[[float], None] = time.sleep):
        self.config = config
        self._sleeper = sleeper
        self._last_request_at: float | None = None
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self._operational_cookie: str | None = None

    def get(self, url: str) -> FetchResult:
        return self._request("GET", url)

    def post_form(self, url: str, data: dict[str, str]) -> FetchResult:
        body = urlencode(data).encode("utf-8")
        return self._request("POST", url, body=body, content_type="application/x-www-form-urlencoded")

    def _request(self, method: str, url: str, body: bytes | None = None, content_type: str | None = None) -> FetchResult:
        last_error: Exception | None = None
        for attempt in range(self.config.retries + 1):
            self._wait()
            request = Request(url, data=body, method=method)
            request.add_header("User-Agent", "product-radar-parser/0.1 research parser; contact: local-user")
            cookie = self._cookie_header()
            if cookie:
                request.add_unredirected_header("Cookie", cookie)
            if content_type:
                request.add_header("Content-Type", content_type)
            try:
                with self._opener.open(request, timeout=self.config.timeout_seconds) as response:
                    raw = response.read()
                    result = self._result(response.geturl(), response.status, raw, response.headers.get_content_charset())
                    if self._accept_beget_cookie(result.text) and attempt < self.config.retries:
                        continue
                    return result
            except HTTPError as exc:
                raw = exc.read()
                if exc.code == 429 or exc.code in {500, 502, 503, 504}:
                    last_error = exc
                    if attempt < self.config.retries:
                        continue
                result = self._result(exc.geturl(), exc.code, raw, exc.headers.get_content_charset())
                if self._accept_beget_cookie(result.text) and attempt < self.config.retries:
                    continue
                return result
            except URLError as exc:
                last_error = exc
                if attempt >= self.config.retries:
                    raise
        assert last_error is not None
        raise last_error

    def _wait(self) -> None:
        now = time.monotonic()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            delay = random.uniform(self.config.min_delay_seconds, self.config.max_delay_seconds)
            remaining = delay - elapsed
            if remaining > 0:
                self._sleeper(remaining)
        self._last_request_at = time.monotonic()

    def _result(self, url: str, status_code: int, raw: bytes, charset: str | None) -> FetchResult:
        text = raw.decode(charset or "utf-8", errors="replace")
        return FetchResult(
            url=url,
            status_code=status_code,
            text=text,
            content_sha256=hashlib.sha256(raw).hexdigest(),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def _cookie_header(self) -> str:
        cookies = [value for value in [self.config.session_cookie, self._operational_cookie] if value]
        return "; ".join(cookies)

    def _accept_beget_cookie(self, text: str) -> bool:
        if "document.cookie='beget=begetok'" not in text:
            return False
        self._operational_cookie = "beget=begetok"
        return True
