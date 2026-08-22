"""네이버·Serper 공용: 재시도가 붙은 JSON HTTP 호출 헬퍼(M3 내부 전용)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import httpx2
from httpx2 import HTTPError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from jarvis_crawler.errors import SearchProviderError

if TYPE_CHECKING:
    from jarvis_crawler.types import SearchProviderName

RETRYABLE_STATUSES: Final[frozenset[int]] = frozenset({429, 500, 502, 503, 504})
_HTTP_ERROR_FLOOR: Final[int] = 400


class _TransientHttpError(Exception):
    """재시도 대상 상태코드(429·5xx)를 tenacity에 전달하는 내부 신호."""


class JsonHttpClient:
    """지정 프로바이더 명의로 JSON API를 호출하고 일시 오류만 재시도한다.

    429·500·502·503·504는 ``retry_wait_base`` 배율의 지수백오프로 재시도하고,
    그 외 4xx는 즉시 :class:`SearchProviderError` 로 변환한다.
    """

    def __init__(
        self,
        *,
        provider: SearchProviderName,
        timeout_seconds: float = 10.0,
        max_attempts: int = 3,
        retry_wait_base: float = 0.5,
    ) -> None:
        """호출 명의가 될 프로바이더와 재시도 정책을 주입받는다."""
        self._provider = provider
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._retry_wait_base = retry_wait_base

    async def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any],
    ) -> Any:
        """JSON GET 요청(쿼리 파라미터 포함)."""
        return await self._request_json("GET", url, headers=headers, params=params)

    async def post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json_body: dict[str, Any],
    ) -> Any:
        """JSON POST 요청(요청 본문은 ``json_body``)."""
        return await self._request_json("POST", url, headers=headers, json=json_body)

    async def _request_json(self, method: str, url: str, **kwargs: Any) -> Any:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._max_attempts),
                wait=wait_exponential(multiplier=self._retry_wait_base),
                retry=retry_if_exception_type(_TransientHttpError),
                reraise=True,
            ):
                with attempt:
                    return await self._request_once(method, url, kwargs)
        except _TransientHttpError as exc:
            raise SearchProviderError(
                self._provider,
                f"{self._max_attempts}회 시도 후 실패: {exc}",
            ) from exc
        except HTTPError as exc:
            raise SearchProviderError(
                self._provider,
                f"{type(exc).__name__}: {exc}",
            ) from exc

    async def _request_once(
        self,
        method: str,
        url: str,
        kwargs: dict[str, Any],
    ) -> Any:
        async with httpx2.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.request(method, url, **kwargs)
        status = response.status_code
        if status in RETRYABLE_STATUSES:
            raise _TransientHttpError(f"HTTP {status}")
        if status >= _HTTP_ERROR_FLOOR:
            raise SearchProviderError(self._provider, f"HTTP {status}")
        return response.json()
