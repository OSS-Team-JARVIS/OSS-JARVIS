"""파이프라인 오케스트레이터와 CLI 진입점 테스트(M4).

모든 의존성(검색 체인·페처·robots 게이트·추출기)은 가짜로 주입해
네트워크 없이 오케스트레이션 규칙만 검증한다.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from jarvis_crawler.cli import main
from jarvis_crawler.errors import ProviderAttempt, SearchChainError
from jarvis_crawler.pipeline import ResearchPipeline
from jarvis_crawler.types import (
    CrawledPage,
    ExtractedContent,
    ExtractorName,
    FailedFetch,
    FetchedDocument,
    FetchFailureReason,
    ResearchBundle,
    SearchProviderName,
    SearchResult,
)


class FakeChain:
    """검색 결과를 스크립트대로 반환하는 가짜 체인."""

    def __init__(
        self,
        results: list[SearchResult],
        error: Exception | None = None,
    ) -> None:
        self._results = results
        self._error = error

    async def search(self, query: str, count: int) -> list[SearchResult]:
        if self._error is not None:
            raise self._error
        return self._results[:count]


class FakeFetcher:
    """URL별로 준비된 결과를 돌려주고 호출 목록을 남긴다."""

    def __init__(self, scripted: dict[str, FailedFetch] | None = None) -> None:
        self.calls: list[str] = []
        self._scripted = scripted or {}

    async def fetch(self, url: str) -> Any:
        self.calls.append(url)
        scripted = self._scripted.get(url)
        if scripted is not None:
            return scripted
        return FetchedDocument(
            url=url,
            final_url=url,
            status=200,
            html=f"<html>{url}</html>",
            fetched_at=datetime.now(UTC),
        )


class FakeRobots:
    """차단 집합에 담긴 URL만 거부하는 가짜 게이트."""

    def __init__(self, denied: set[str]) -> None:
        self._denied = denied

    async def allowed(self, url: str) -> bool:
        return url not in self._denied


class FakeExtractor:
    """``empty_for``에 담긴 URL은 빈 본문을 내보내는 가짜 추출기."""

    def __init__(self, empty_for: set[str]) -> None:
        self._empty_for = empty_for

    def extract(
        self,
        document: FetchedDocument,
        *,
        max_chars: int,
    ) -> ExtractedContent:
        content = "" if document.url in self._empty_for else f"본문-{document.url}"
        return ExtractedContent(
            url=document.url,
            title=f"제목-{document.url}",
            content=content[:max_chars],
            extractor=ExtractorName.TRAFILATURA,
        )


def _result(rank: int, url: str | None = None) -> SearchResult:
    return SearchResult(
        url=url or f"https://example{rank}.com/a",
        title=f"제목{rank}",
        snippet="요약",
        rank=rank,
        provider=SearchProviderName.DDGS,
    )


def _pipeline(
    chain: FakeChain,
    fetcher: FakeFetcher,
    robots: FakeRobots,
    extractor: FakeExtractor,
    *,
    max_pages: int = 8,
) -> ResearchPipeline:
    return ResearchPipeline(
        chain=chain,
        fetcher=fetcher,
        robots=robots,
        extractor=extractor,
        max_pages=max_pages,
    )


@pytest.mark.asyncio
async def test_run_returns_bundle_with_crawled_pages() -> None:
    chain = FakeChain([_result(1, "https://a.com/x"), _result(2, "https://b.com/y")])
    fetcher = FakeFetcher()
    pipeline = _pipeline(chain, fetcher, FakeRobots(set()), FakeExtractor(set()))

    bundle = await pipeline.run("AI 트렌드")

    assert bundle.query == "AI 트렌드"
    assert [p.url for p in bundle.pages] == ["https://a.com/x", "https://b.com/y"]
    assert bundle.failures == ()
    first = bundle.pages[0]
    assert first.title == "제목-https://a.com/x"
    assert first.content_length == len(first.content)
    assert first.extractor is ExtractorName.TRAFILATURA


@pytest.mark.asyncio
async def test_run_deduplicates_normalized_urls() -> None:
    urls = ["https://a.com/x", "https://a.com/x#section", "https://a.com/x/"]
    chain = FakeChain([_result(i + 1, u) for i, u in enumerate(urls)])
    fetcher = FakeFetcher()
    pipeline = _pipeline(chain, fetcher, FakeRobots(set()), FakeExtractor(set()))

    await pipeline.run("q")

    assert fetcher.calls == ["https://a.com/x"]


@pytest.mark.asyncio
async def test_run_limits_fetches_to_max_pages() -> None:
    chain = FakeChain([_result(i + 1) for i in range(5)])
    fetcher = FakeFetcher()
    pipeline = _pipeline(
        chain,
        fetcher,
        FakeRobots(set()),
        FakeExtractor(set()),
        max_pages=2,
    )

    bundle = await pipeline.run("q")

    assert [p.url for p in bundle.pages] == [
        "https://example1.com/a",
        "https://example2.com/a",
    ]
    assert len(fetcher.calls) == 2


@pytest.mark.asyncio
async def test_run_records_robots_denial_without_aborting() -> None:
    chain = FakeChain(
        [_result(1, "https://blocked.com/a"), _result(2, "https://open.com/b")],
    )
    fetcher = FakeFetcher()
    pipeline = _pipeline(
        chain,
        fetcher,
        FakeRobots({"https://blocked.com/a"}),
        FakeExtractor(set()),
    )

    bundle = await pipeline.run("q")

    assert fetcher.calls == ["https://open.com/b"]
    assert [p.url for p in bundle.pages] == ["https://open.com/b"]
    denial = bundle.failures[0]
    assert denial.url == "https://blocked.com/a"
    assert denial.reason is FetchFailureReason.ROBOTS_DISALLOWED


@pytest.mark.asyncio
async def test_run_reclassifies_empty_extraction_as_failure() -> None:
    chain = FakeChain([_result(1, "https://empty.com/a")])
    pipeline = _pipeline(
        chain,
        FakeFetcher(),
        FakeRobots(set()),
        FakeExtractor({"https://empty.com/a"}),
    )

    bundle = await pipeline.run("q")

    assert bundle.pages == ()
    failure = bundle.failures[0]
    assert failure.reason is FetchFailureReason.EXTRACT_EMPTY
    assert failure.url == "https://empty.com/a"


@pytest.mark.asyncio
async def test_run_passes_through_fetch_failures() -> None:
    bad_url = "https://bad.com/x"
    good_url = "https://good.com/y"
    chain = FakeChain([_result(1, bad_url), _result(2, good_url)])
    scripted_failure = FailedFetch(
        url=bad_url,
        reason=FetchFailureReason.HTTP_ERROR,
        detail="HTTP 500",
    )
    fetcher = FakeFetcher({bad_url: scripted_failure})
    pipeline = _pipeline(chain, fetcher, FakeRobots(set()), FakeExtractor(set()))

    bundle = await pipeline.run("q")

    assert [p.url for p in bundle.pages] == [good_url]
    assert bundle.failures == (scripted_failure,)


@pytest.mark.asyncio
async def test_run_propagates_search_chain_error() -> None:
    chain_error = SearchChainError(
        (ProviderAttempt(provider=SearchProviderName.NAVER, detail="HTTP 401"),),
    )
    pipeline = _pipeline(
        FakeChain([], error=chain_error),
        FakeFetcher(),
        FakeRobots(set()),
        FakeExtractor(set()),
    )

    with pytest.raises(SearchChainError):
        await pipeline.run("q")


@pytest.mark.asyncio
async def test_crawl_urls_deduplicates_and_bundles() -> None:
    urls = ["https://a.com/x", "https://a.com/x/", "https://b.com/y"]
    fetcher = FakeFetcher()
    pipeline = _pipeline(
        FakeChain([]),
        fetcher,
        FakeRobots(set()),
        FakeExtractor(set()),
    )

    bundle = await pipeline.crawl_urls(urls)

    assert bundle.query == ""
    assert [p.url for p in bundle.pages] == ["https://a.com/x", "https://b.com/y"]
    assert fetcher.calls == ["https://a.com/x", "https://b.com/y"]
    assert bundle.failures == ()


@pytest.mark.asyncio
async def test_crawl_urls_records_failures_and_respects_max_chars() -> None:
    blocked_url = "https://blocked.com/a"
    bad_url = "https://bad.com/x"
    good_url = "https://good.com/y"
    scripted_failure = FailedFetch(
        url=bad_url,
        reason=FetchFailureReason.HTTP_ERROR,
        detail="HTTP 500",
    )
    fetcher = FakeFetcher({bad_url: scripted_failure})
    pipeline = _pipeline(
        FakeChain([]),
        fetcher,
        FakeRobots({blocked_url}),
        FakeExtractor(set()),
    )

    bundle = await pipeline.crawl_urls([blocked_url, bad_url, good_url], max_chars=3)

    assert [p.url for p in bundle.pages] == [good_url]
    assert bundle.pages[0].content_length == 3
    reasons = {f.url: f.reason for f in bundle.failures}
    assert reasons[blocked_url] is FetchFailureReason.ROBOTS_DISALLOWED
    assert reasons[bad_url] is FetchFailureReason.HTTP_ERROR


class StubPipeline:
    """run()이 미리 준비한 번들을 반환하는 CLI용 스터브."""

    def __init__(self, bundle: ResearchBundle, error: Exception | None = None) -> None:
        self._bundle = bundle
        self._error = error
        self.received_query: str | None = None
        self.received_count: int | None = None

    async def run(self, query: str, count: int) -> ResearchBundle:
        self.received_query = query
        self.received_count = count
        if self._error is not None:
            raise self._error
        return self._bundle


def _bundle_fixture() -> ResearchBundle:
    page = CrawledPage(
        url="https://a.com/x",
        final_url="https://a.com/x",
        status=200,
        title="제목",
        content="본문",
        content_length=2,
        extractor=ExtractorName.TRAFILATURA,
        fetched_at=datetime(2026, 8, 22, tzinfo=UTC),
    )
    failure = FailedFetch(
        url="https://b.com/y",
        reason=FetchFailureReason.TIMEOUT,
        detail="초과",
    )
    return ResearchBundle(query="AI 트렌드", pages=(page,), failures=(failure,))


def test_main_writes_bundle_json(tmp_path: Path) -> None:
    out_path = tmp_path / "out.json"
    stub = StubPipeline(_bundle_fixture())
    output_arg = str(out_path)

    exit_code = main(
        ["AI 트렌드", "--count", "5", "--output", output_arg],
        pipeline_factory=lambda **_: stub,
    )

    assert exit_code == 0
    assert stub.received_query == "AI 트렌드"
    assert stub.received_count == 5
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["query"] == "AI 트렌드"
    assert payload["results"][0]["url"] == "https://a.com/x"
    assert payload["failures"][0]["reason"] == "timeout"


def test_main_reports_chain_error_with_exit_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    chain_error = SearchChainError(
        (ProviderAttempt(provider=SearchProviderName.NAVER, detail="HTTP 401"),),
    )
    stub = StubPipeline(_bundle_fixture(), error=chain_error)

    exit_code = main(["q"], pipeline_factory=lambda **_: stub)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "naver" in captured.err
