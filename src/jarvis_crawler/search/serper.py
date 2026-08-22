"""Serper.dev Google 검색 프록시 프로바이더(M3)."""

from __future__ import annotations

from typing import Any, Final

from jarvis_crawler.search._http_json import JsonHttpClient
from jarvis_crawler.types import SearchProviderName, SearchResult

DEFAULT_BASE_URL: Final[str] = "https://google.serper.dev/search"


class SerperProvider:
    """X-API-KEY 인증 POST 검색 — 응답의 organic 배열을 파싱한다.

    API 키는 환경변수 ``SERPER_API_KEY`` 값을 생성자로 주입받는다
    (조립은 :func:`jarvis_crawler.search.chain.chain_from_env`).
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 10.0,
        max_attempts: int = 3,
        retry_wait_base: float = 0.5,
    ) -> None:
        """API 키와 정책 파라미터를 주입받아 초기화한다."""
        self._endpoint = base_url.rstrip("/")
        self._api_key = api_key
        self._http = JsonHttpClient(
            provider=SearchProviderName.SERPER,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            retry_wait_base=retry_wait_base,
        )

    @property
    def name(self) -> SearchProviderName:
        """프로바이더 식별자(:attr:`SearchProviderName.SERPER`)."""
        return SearchProviderName.SERPER

    async def search(self, query: str, count: int) -> list[SearchResult]:
        """Serper Google 검색 API에 POST로 질의해 결과를 반환한다."""
        payload: dict[str, Any] = await self._http.post_json(
            self._endpoint,
            headers={"X-API-KEY": self._api_key},
            json_body={"q": query, "num": count},
        )
        organic: list[dict[str, Any]] = payload.get("organic") or []
        results: list[SearchResult] = []
        for index, item in enumerate(organic[:count]):
            position = item.get("position")
            rank = int(position) if position else index + 1
            results.append(
                SearchResult(
                    url=str(item.get("link", "")),
                    title=str(item.get("title", "")),
                    snippet=str(item.get("snippet", "")),
                    rank=rank,
                    provider=SearchProviderName.SERPER,
                ),
            )
        return results
