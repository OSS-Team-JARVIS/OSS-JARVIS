"""네이버 Open API 웹문서 검색 프로바이더(M3)."""

from __future__ import annotations

import asyncio
import html
import re
import time
from typing import Any, Final

from jarvis_crawler.search._http_json import JsonHttpClient
from jarvis_crawler.types import SearchProviderName, SearchResult

DEFAULT_BASE_URL: Final[str] = "https://openapi.naver.com/v1/search/webkr.json"
# 네이버 Open API 초당 25회 제한 준수용 최소 요청 간격.
MIN_REQUEST_INTERVAL_SECONDS: Final[float] = 0.04
_MAX_DISPLAY: Final[int] = 100
_TAG_PATTERN: Final[re.Pattern[str]] = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    """네이버 응답에 섞인 <b> 태그와 HTML 엔티티를 제거한다."""
    return html.unescape(_TAG_PATTERN.sub("", text)).strip()


class NaverProvider:
    """X-Naver-Client-{Id,Secret} 인증 웹문서 검색(display ≤ 100, 초당 25회 제한).

    자격 증명은 환경변수 ``NAVER_CLIENT_ID`` / ``NAVER_CLIENT_SECRET`` 값을
    생성자로 주입받는다(조립은 :func:`jarvis_crawler.search.chain.chain_from_env`).
    """

    def __init__(  # noqa: PLR0913 (정책 파라미터 주입형 생성자)
        self,
        *,
        client_id: str,
        client_secret: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 10.0,
        max_attempts: int = 3,
        retry_wait_base: float = 0.5,
        min_request_interval: float = MIN_REQUEST_INTERVAL_SECONDS,
    ) -> None:
        """자격 증명과 정책 파라미터를 주입받아 초기화한다."""
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        }
        self._min_interval = min_request_interval
        self._last_call_at: float | None = None
        self._http = JsonHttpClient(
            provider=SearchProviderName.NAVER,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            retry_wait_base=retry_wait_base,
        )

    @property
    def name(self) -> SearchProviderName:
        """프로바이더 식별자(:attr:`SearchProviderName.NAVER`)."""
        return SearchProviderName.NAVER

    async def search(self, query: str, count: int) -> list[SearchResult]:
        """초당 요청 한도를 지키며 네이버 웹문서 검색 결과를 반환한다."""
        await self._respect_rate_limit()
        payload: dict[str, Any] = await self._http.get_json(
            self._base_url,
            headers=self._headers,
            params={
                "query": query,
                "display": min(max(count, 1), _MAX_DISPLAY),
                "start": 1,
                "sort": "sim",
            },
        )
        self._mark_called()
        items: list[dict[str, Any]] = payload.get("items") or []
        return [
            SearchResult(
                url=str(item.get("link", "")),
                title=_clean(str(item.get("title", ""))),
                snippet=_clean(str(item.get("description", ""))),
                rank=index + 1,
                provider=SearchProviderName.NAVER,
            )
            for index, item in enumerate(items[:count])
        ]

    async def _respect_rate_limit(self) -> None:
        last = self._last_call_at
        if last is None:
            return
        remaining = self._min_interval - (time.monotonic() - last)
        if remaining > 0:
            await asyncio.sleep(remaining)

    def _mark_called(self) -> None:
        self._last_call_at = time.monotonic()
