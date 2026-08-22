"""검색→페치→추출을 묶는 파이프라인 오케스트레이터(M4).

설계 원칙: 부분 실패가 전체를 죽이지 않는다. 한 URL의 실패는
:class:`FailedFetch` 로 기록되고 나머지 URL 처리는 계속된다.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Final, Protocol
from urllib.parse import urlsplit, urlunsplit

from jarvis_crawler.types import (
    DEFAULT_MAX_CONTENT_CHARS,
    CrawledPage,
    FailedFetch,
    FetchFailureReason,
    ResearchBundle,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from jarvis_crawler.crawl.base import BodyExtractor, PageFetcher, RobotsGate
    from jarvis_crawler.types import SearchResult

_DEFAULT_MAX_PAGES: Final[int] = 8


class SearchGateway(Protocol):
    """파이프라인이 의존하는 최소 검색 능력(SearchChain과 구조적으로 호환)."""

    async def search(self, query: str, count: int) -> list[SearchResult]:
        """질의로 URL 후보 목록을 반환한다."""
        ...


def normalize_url(url: str) -> str:
    """중복 판정용 정규화: fragment 제거, 경로 트레일링 슬래시 통일."""
    parts = urlsplit(url)
    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def pick_unique_urls(results: Sequence[SearchResult], limit: int) -> list[str]:
    """정규화 키로 중복을 걷어내고 등장 순서대로 상위 ``limit``개를 남긴다."""
    seen: dict[str, str] = {}
    for result in results:
        key = normalize_url(result.url)
        if key not in seen:
            seen[key] = result.url
        if len(seen) >= limit:
            break
    return list(seen.values())


class ResearchPipeline:
    """search→dedup→robots→fetch→extract를 순서대로 조립하는 진입점."""

    def __init__(  # noqa: PLR0913 (협력자 주입형 생성자)
        self,
        *,
        chain: SearchGateway,
        fetcher: PageFetcher,
        robots: RobotsGate,
        extractor: BodyExtractor,
        max_pages: int = _DEFAULT_MAX_PAGES,
        max_chars: int = DEFAULT_MAX_CONTENT_CHARS,
    ) -> None:
        """네 협력자와 페이지·본문 상한 정책을 주입받아 초기화한다."""
        self._chain = chain
        self._fetcher = fetcher
        self._robots = robots
        self._extractor = extractor
        self._max_pages = max_pages
        self._max_chars = max_chars

    async def run(self, query: str, count: int = 10) -> ResearchBundle:
        """검색부터 추출까지 실행해 성공·실패를 분류한 번들을 반환한다."""
        candidates = await self._chain.search(query, count)
        picked = pick_unique_urls(candidates, self._max_pages)
        outcomes = await asyncio.gather(
            *(self._process_single(url) for url in picked),
        )
        pages = tuple(o for o in outcomes if isinstance(o, CrawledPage))
        failures = tuple(o for o in outcomes if isinstance(o, FailedFetch))
        return ResearchBundle(query=query, pages=pages, failures=failures)

    async def crawl_urls(
        self,
        urls: Sequence[str],
        *,
        max_chars: int | None = None,
    ) -> ResearchBundle:
        """검색 없이 URL 목록을 직접 크롤링한다(MCP crawl 도구용).

        정규화 키로 중복을 제거하고 등장 순서를 유지한다. 검색 결과와
        달리 ``max_pages`` 상한을 적용하지 않는다(목록 크기는 호출자가 책임진다).
        """
        seen: dict[str, str] = {}
        for url in urls:
            key = normalize_url(url)
            if key not in seen:
                seen[key] = url
        outcomes = await asyncio.gather(
            *(self._process_single(url, max_chars=max_chars) for url in seen.values()),
        )
        pages = tuple(o for o in outcomes if isinstance(o, CrawledPage))
        failures = tuple(o for o in outcomes if isinstance(o, FailedFetch))
        return ResearchBundle(query="", pages=pages, failures=failures)

    async def _process_single(
        self,
        url: str,
        *,
        max_chars: int | None = None,
    ) -> CrawledPage | FailedFetch:
        """한 URL에 대해 robots 확인→페치→추출을 수행한다."""
        effective_max_chars = self._max_chars if max_chars is None else max_chars
        if not await self._robots.allowed(url):
            return FailedFetch(
                url=url,
                reason=FetchFailureReason.ROBOTS_DISALLOWED,
                detail="robots.txt가 이 경로의 크롤링을 금지한다",
            )
        outcome = await self._fetcher.fetch(url)
        if isinstance(outcome, FailedFetch):
            return outcome
        extracted = self._extractor.extract(outcome, max_chars=effective_max_chars)
        if not extracted.content.strip():
            # 추출기 계약: 빈 본문은 파이프라인이 실패로 재분류한다.
            return FailedFetch(
                url=url,
                reason=FetchFailureReason.EXTRACT_EMPTY,
                detail="본문 추출 결과가 빈 문자열이다",
            )
        return CrawledPage(
            url=outcome.url,
            final_url=outcome.final_url,
            status=outcome.status,
            title=extracted.title,
            content=extracted.content,
            content_length=len(extracted.content),
            extractor=extracted.extractor,
            fetched_at=outcome.fetched_at,
        )


def build_default_pipeline(
    *,
    max_pages: int = _DEFAULT_MAX_PAGES,
    max_chars: int = DEFAULT_MAX_CONTENT_CHARS,
) -> ResearchPipeline:
    """환경변수와 실전 컴포넌트로 파이프라인을 조립한다.

    무거운 의존성(curl_cffi·protego·trafilatura)은 이 함수가 처음
    호출될 때만 임포트한다. 모듈 임포트 비용을 테스트에서 제외하기
    위해서다.
    """
    from jarvis_crawler.crawl.extractor import MainContentExtractor  # noqa: PLC0415
    from jarvis_crawler.crawl.fetcher import CffiPageFetcher  # noqa: PLC0415
    from jarvis_crawler.crawl.robots import ProtegoRobotsGate  # noqa: PLC0415
    from jarvis_crawler.search.chain import chain_from_env  # noqa: PLC0415

    return ResearchPipeline(
        chain=chain_from_env(),
        fetcher=CffiPageFetcher(),
        robots=ProtegoRobotsGate(),
        extractor=MainContentExtractor(),
        max_pages=max_pages,
        max_chars=max_chars,
    )


async def research(query: str, *, count: int = 10) -> dict[str, Any]:
    """기본 구성으로 끝까지 돌려 JSON 직렬화 가능한 dict를 반환한다.

    검색 체인 전체가 실패하면 :class:`SearchChainError` 가 그대로
    올라간다(호출자가 처리).
    """
    bundle = await build_default_pipeline().run(query, count=count)
    payload: dict[str, Any] = json.loads(bundle.to_json())
    return payload
