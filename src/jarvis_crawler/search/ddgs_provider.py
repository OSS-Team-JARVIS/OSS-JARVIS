"""DDGS(DuckDuckGo 무료 검색) 폴백 프로바이더(M3)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Final

from ddgs import DDGS
from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from jarvis_crawler.errors import SearchProviderError
from jarvis_crawler.types import SearchProviderName, SearchResult

if TYPE_CHECKING:
    from collections.abc import Callable

_RETRYABLE_ERRORS: Final[tuple[type[Exception], ...]] = (
    RatelimitException,
    TimeoutException,
)


class DdgsProvider:
    """동기 ddgs 라이브러리를 스레드로 실행하고 레이트리밋 시 백오프한다.

    API 키가 필요 없어 어떤 환경에서도 동작하는 최후 폴백이다.
    """

    def __init__(
        self,
        *,
        client_factory: Callable[[], Any] | None = None,
        max_attempts: int = 3,
        retry_wait_base: float = 1.0,
    ) -> None:
        """테스트용 클라이언트 팩토리와 재시도 정책을 주입받는다."""
        self._make_client: Callable[[], Any] = client_factory or DDGS
        self._max_attempts = max_attempts
        self._retry_wait_base = retry_wait_base

    @property
    def name(self) -> SearchProviderName:
        """프로바이더 식별자(:attr:`SearchProviderName.DDGS`)."""
        return SearchProviderName.DDGS

    async def search(self, query: str, count: int) -> list[SearchResult]:
        """쿼리를 검색해 최대 ``count``개 결과를 랭킹과 함께 반환한다."""
        try:
            rows = await self._text_with_retry(query, count)
        except DDGSException as exc:
            raise SearchProviderError(
                SearchProviderName.DDGS,
                f"{type(exc).__name__}: {exc}",
            ) from exc
        return [
            SearchResult(
                url=str(row.get("href") or row.get("link") or ""),
                title=str(row.get("title", "")),
                snippet=str(row.get("body") or row.get("snippet") or ""),
                rank=index + 1,
                provider=SearchProviderName.DDGS,
            )
            for index, row in enumerate(rows[:count])
        ]

    async def _text_with_retry(self, query: str, count: int) -> list[dict[str, Any]]:
        client = self._make_client()
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._max_attempts),
                wait=wait_exponential(multiplier=self._retry_wait_base),
                retry=retry_if_exception_type(_RETRYABLE_ERRORS),
                reraise=True,
            ):
                with attempt:
                    return await asyncio.to_thread(
                        client.text,
                        query,
                        max_results=count,
                    )
        except _RETRYABLE_ERRORS as exc:
            raise SearchProviderError(
                SearchProviderName.DDGS,
                f"{self._max_attempts}회 시도 후에도 레이트리밋: {exc}",
            ) from exc
        raise AssertionError("도달 불가: 반복문은 반환 또는 예외로만 벗어난다")
