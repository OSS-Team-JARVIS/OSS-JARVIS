"""MCP 서버 도구(web_search·crawl) 테스트(M5).

네트워크 없이 검색 체인과 파이프라인을 가짜로 갈아끼워 도구 계약과
MCPServer 등록·직렬화 경로만 검증한다.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from jarvis_crawler import mcp_server as server_module
from jarvis_crawler.errors import ProviderAttempt, SearchChainError
from jarvis_crawler.types import (
    CrawledPage,
    ExtractorName,
    FailedFetch,
    FetchFailureReason,
    ResearchBundle,
    SearchProviderName,
    SearchResult,
)


class ScriptedGateway:
    """search 결과를 스크립트대로 돌려주고 호출 인자를 남기는 가짜 게이트."""

    def __init__(
        self,
        results: list[SearchResult],
        error: Exception | None = None,
    ) -> None:
        self._results = results
        self._error = error
        self.received_query: str | None = None
        self.received_count: int | None = None

    async def search(self, query: str, count: int) -> list[SearchResult]:
        """호출 인자를 기록한 뒤 스크립트된 결과(또는 오류)를 낸다."""
        self.received_query = query
        self.received_count = count
        if self._error is not None:
            raise self._error
        return self._results[:count]


class EngineSpyFactory:
    """엔진 인자를 기록하고 준비된 게이트를 돌려주는 팩토리 스파이."""

    def __init__(self, gateway: ScriptedGateway) -> None:
        self._gateway = gateway
        self.engines: list[str | None] = []

    def __call__(self, engine: str | None) -> ScriptedGateway:
        self.engines.append(engine)
        return self._gateway


class StubCrawlPipeline:
    """crawl_urls 호출을 기록하고 준비된 번들을 반환하는 스터브."""

    def __init__(self, bundle: ResearchBundle) -> None:
        self._bundle = bundle
        self.calls: list[tuple[list[str], int]] = []

    async def crawl_urls(
        self,
        urls: list[str],
        *,
        max_chars: int,
    ) -> ResearchBundle:
        """호출 인자를 기록하고 준비된 번들을 그대로 돌려준다."""
        self.calls.append((urls, max_chars))
        return self._bundle


def _result(rank: int, url: str | None = None) -> SearchResult:
    return SearchResult(
        url=url or f"https://example{rank}.com/a",
        title=f"제목{rank}",
        snippet="요약",
        rank=rank,
        provider=SearchProviderName.DDGS,
    )


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
    return ResearchBundle(query="", pages=(page,), failures=(failure,))


@pytest.mark.asyncio
async def test_web_search_returns_json_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = ScriptedGateway([_result(1), _result(2)])
    spy = EngineSpyFactory(gateway)
    monkeypatch.setattr(server_module, "_chain_factory", spy)

    payload = json.loads(await server_module.web_search("AI 트렌드", count=2))

    assert spy.engines == [None]
    assert gateway.received_query == "AI 트렌드"
    assert gateway.received_count == 2
    assert [item["url"] for item in payload] == [
        "https://example1.com/a",
        "https://example2.com/a",
    ]
    assert payload[0]["provider"] == "ddgs"
    assert payload[0]["rank"] == 1
    assert payload[0]["title"] == "제목1"


@pytest.mark.asyncio
async def test_web_search_normalizes_single_engine_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = ScriptedGateway([_result(1)])
    spy = EngineSpyFactory(gateway)
    monkeypatch.setattr(server_module, "_chain_factory", spy)

    await server_module.web_search("q", engine=" NAVER ")

    assert spy.engines == ["naver"]


@pytest.mark.asyncio
async def test_web_search_unknown_engine_reports_error_without_network() -> None:
    # 실제 기본 팩토리를 쓴다: make_provider가 네트워크 전에 ValueError를 내야 한다.
    payload = json.loads(await server_module.web_search("q", engine="gibberish"))

    assert "error" in payload
    assert "gibberish" in payload["error"]


@pytest.mark.asyncio
async def test_web_search_chain_failure_reports_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chain_error = SearchChainError(
        (ProviderAttempt(provider=SearchProviderName.NAVER, detail="HTTP 401"),),
    )
    gateway = ScriptedGateway([], error=chain_error)
    monkeypatch.setattr(
        server_module,
        "_chain_factory",
        lambda engine: gateway,
    )

    payload = json.loads(await server_module.web_search("q"))

    assert "error" in payload
    assert "naver" in payload["error"]
    assert "HTTP 401" in payload["error"]


@pytest.mark.asyncio
async def test_crawl_forwards_urls_and_max_chars_to_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = StubCrawlPipeline(_bundle_fixture())
    monkeypatch.setattr(server_module, "_pipeline_factory", lambda: stub)

    raw = await server_module.crawl(["https://a.com/x"], max_chars=1234)
    payload = json.loads(raw)

    assert stub.calls == [(["https://a.com/x"], 1234)]
    assert payload["query"] == ""
    assert payload["results"][0]["url"] == "https://a.com/x"
    assert payload["failures"][0]["reason"] == "timeout"


@pytest.mark.asyncio
async def test_server_lists_exactly_two_tools() -> None:
    tools = await server_module.mcp.list_tools()

    assert {tool.name for tool in tools} == {"web_search", "crawl"}


@pytest.mark.asyncio
async def test_call_tool_roundtrip_through_mcp_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = ScriptedGateway([_result(1)])
    monkeypatch.setattr(server_module, "_chain_factory", lambda engine: gateway)

    result = await server_module.mcp.call_tool("web_search", {"query": "q"})

    assert result.is_error is False
    text = result.content[0].text
    assert isinstance(text, str)
    payload: list[dict[str, object]] = json.loads(text)
    assert payload[0]["url"] == "https://example1.com/a"
