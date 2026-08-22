"""Polite page fetching over curl_cffi with TLS impersonation."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from random import SystemRandom
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit

from charset_normalizer import from_bytes
from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import CurlError, Timeout

if TYPE_CHECKING:
    from curl_cffi.requests.models import Response

from jarvis_crawler.types import (
    FailedFetch,
    FetchedDocument,
    FetchFailureReason,
    FetchOutcome,
)

_MAX_HTTP_SUCCESS_STATUS: Final[int] = 399
_RETRYABLE_STATUSES: Final[frozenset[int]] = frozenset({403, 429, 500, 502, 503, 504})
_MAX_RETRY_AFTER_SECONDS: Final[float] = 30.0
_RNG: Final[SystemRandom] = SystemRandom()


class CffiPageFetcher:
    """curl_cffi AsyncSession 래퍼: TLS 위장·재시도·도메인 직렬화 담당.

    같은 호스트 요청은 잠금으로 직렬화되고, 직전 요청 종료 후 최소
    ``delay_range`` 구간의 무작위 간격을 유지한다(politeness).
    """

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        max_attempts: int = 3,
        delay_range: tuple[float, float] = (1.0, 3.0),
        retry_wait_base: float = 1.0,
        impersonate: str = "chrome",
    ) -> None:
        """페치 정책 파라미터를 주입받아 초기화한다."""
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._delay_range = delay_range
        self._retry_wait_base = retry_wait_base
        self._impersonate = impersonate
        self._session: AsyncSession | None = None
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._last_done_at: dict[str, float] = {}

    async def fetch(self, url: str) -> FetchOutcome:
        """``url``을 내려와 문서 또는 기록된 실패로 반환한다."""
        host = urlsplit(url).netloc
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            await self._politeness_pause(host)
            outcome = await self._fetch_with_retries(url)
            self._last_done_at[host] = time.monotonic()
            return outcome

    async def _politeness_pause(self, host: str) -> None:
        last = self._last_done_at.get(host)
        if last is None:
            return
        remaining = _RNG.uniform(*self._delay_range) - (time.monotonic() - last)
        if remaining > 0:
            await asyncio.sleep(remaining)

    async def _fetch_with_retries(self, url: str) -> FetchOutcome:
        session = self._ensure_session()
        attempt = 1
        while True:
            try:
                response = await session.get(url)
            except Timeout as exc:
                return FailedFetch(
                    url=url,
                    reason=FetchFailureReason.TIMEOUT,
                    detail=str(exc),
                )
            except CurlError as exc:
                return FailedFetch(
                    url=url,
                    reason=FetchFailureReason.UNKNOWN,
                    detail=f"{type(exc).__name__}: {exc}",
                )

            status = response.status_code
            if status <= _MAX_HTTP_SUCCESS_STATUS:
                return self._to_document(url, response)
            if status in _RETRYABLE_STATUSES and attempt < self._max_attempts:
                retry_after = _header_value(response.headers, "Retry-After")
                await asyncio.sleep(self._retry_delay(retry_after, attempt))
                attempt += 1
                continue
            return FailedFetch(
                url=url,
                reason=FetchFailureReason.HTTP_ERROR,
                detail=f"HTTP {status}",
            )

    def _ensure_session(self) -> AsyncSession:
        if self._session is None:
            self._session = AsyncSession(
                impersonate=self._impersonate,
                timeout=self._timeout,
            )
        return self._session

    def _to_document(self, url: str, response: Response) -> FetchOutcome:
        if not response.content:
            html = ""
        else:
            best = from_bytes(response.content).best()
            html = str(best) if best is not None else ""
            if not html.strip() and response.content:
                return FailedFetch(
                    url=url,
                    reason=FetchFailureReason.DECODE_ERROR,
                    detail="charset-normalizer가 디코딩에 실패했다",
                )
        return FetchedDocument(
            url=url,
            final_url=str(response.url),
            status=response.status_code,
            html=html,
            fetched_at=datetime.now(UTC),
        )

    def _retry_delay(self, retry_after: str | None, attempt: int) -> float:
        backoff = self._retry_wait_base * (2 ** (attempt - 1))
        wait = backoff + _RNG.uniform(0.0, backoff * 0.25)
        if retry_after is not None and retry_after.strip().isdigit():
            declared = min(float(retry_after), _MAX_RETRY_AFTER_SECONDS)
            wait = max(wait, declared)
        return wait


def _header_value(headers: object, name: str) -> str | None:
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    value = getter(name)
    return value if isinstance(value, str) else None
