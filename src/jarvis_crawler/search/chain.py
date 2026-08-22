"""검색 폴백 체인과 환경변수 기반 구성 헬퍼(M3)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from jarvis_crawler.errors import ProviderAttempt, SearchChainError, SearchProviderError
from jarvis_crawler.search.ddgs_provider import DdgsProvider
from jarvis_crawler.search.naver import NaverProvider
from jarvis_crawler.search.serper import SerperProvider
from jarvis_crawler.types import SearchProviderName

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from jarvis_crawler.search.base import SearchProvider
    from jarvis_crawler.types import SearchResult


class SearchChain:
    """프로바이더를 순서대로 시도하고 첫 성공에서 결과를 반환한다.

    전부 실패하면 프로바이더별 사유를 담은 :class:`SearchChainError` 를 낸다.
    """

    def __init__(self, providers: Sequence[SearchProvider]) -> None:
        """폴백 순서대로 프로바이더 목록을 받는다(빈 목록 불가)."""
        if not providers:
            raise ValueError("최소 한 개의 프로바이더가 필요하다")
        self._providers: tuple[SearchProvider, ...] = tuple(providers)

    @property
    def providers(self) -> tuple[SearchProvider, ...]:
        """구성된 프로바이더 목록(구성 검증·로깅용)."""
        return self._providers

    async def search(self, query: str, count: int) -> list[SearchResult]:
        """첫 성공 프로바이더의 결과를 반환하고, 전부 실패하면 집계 오류를 낸다."""
        attempts: list[ProviderAttempt] = []
        for provider in self._providers:
            try:
                return await provider.search(query, count)
            except SearchProviderError as exc:
                attempts.append(
                    ProviderAttempt(provider=exc.provider, detail=exc.detail),
                )
        raise SearchChainError(tuple(attempts))


def chain_from_env(environ: Mapping[str, str] | None = None) -> SearchChain:
    """환경변수 키가 설정된 프로바이더만으로 체인을 구성한다.

    사용 키: ``NAVER_CLIENT_ID``·``NAVER_CLIENT_SECRET``, ``SERPER_API_KEY``.
    DDGS는 키가 필요 없으므로 항상 마지막 폴백으로 포함된다.
    """
    env = os.environ if environ is None else environ
    providers: list[SearchProvider] = []
    naver_id = env.get("NAVER_CLIENT_ID")
    naver_secret = env.get("NAVER_CLIENT_SECRET")
    if naver_id and naver_secret:
        providers.append(NaverProvider(client_id=naver_id, client_secret=naver_secret))
    serper_key = env.get("SERPER_API_KEY")
    if serper_key:
        providers.append(SerperProvider(api_key=serper_key))
    providers.append(DdgsProvider())
    return SearchChain(providers)


def make_provider(
    name: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> SearchProvider:
    """엔진 별칭 하나로 환경변수 기반 단일 프로바이더를 만든다.

    MCP ``web_search`` 도구의 ``engine`` 인자 처리용이다. 체인 구성과
    달리 자격 증명이 없으면 조용히 건너뛰지 않고 :class:`ValueError` 를 낸다.
    """
    env = os.environ if environ is None else environ
    key = name.strip().lower()
    if key == SearchProviderName.NAVER.value:
        client_id = env.get("NAVER_CLIENT_ID")
        client_secret = env.get("NAVER_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise ValueError(
                "네이버 자격 증명(NAVER_CLIENT_ID·NAVER_CLIENT_SECRET)이 없다",
            )
        return NaverProvider(client_id=client_id, client_secret=client_secret)
    if key == SearchProviderName.SERPER.value:
        api_key = env.get("SERPER_API_KEY")
        if not api_key:
            raise ValueError("Serper 자격 증명(SERPER_API_KEY)이 없다")
        return SerperProvider(api_key=api_key)
    if key == SearchProviderName.DDGS.value:
        return DdgsProvider()
    supported = ", ".join(member.value for member in SearchProviderName)
    raise ValueError(f"지원하지 않는 검색 엔진이다: {name} (지원 목록: {supported})")
