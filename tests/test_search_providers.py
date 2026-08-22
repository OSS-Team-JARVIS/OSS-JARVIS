"""검색 계층 계약 테스트: 네이버·Serper는 로컬 모의 서버, DDGS는 가짜 클라이언트."""

from __future__ import annotations

import json

import pytest
from ddgs.exceptions import RatelimitException

from http_harness import FakeResponse, RecordedRequest, make_server
from jarvis_crawler.errors import SearchChainError, SearchProviderError
from jarvis_crawler.search.chain import SearchChain, chain_from_env
from jarvis_crawler.search.ddgs_provider import DdgsProvider
from jarvis_crawler.search.naver import NaverProvider
from jarvis_crawler.search.serper import SerperProvider
from jarvis_crawler.types import SearchProviderName, SearchResult

pytestmark = pytest.mark.asyncio

NAVER_BASE_PATH = "/v1/search/webkr.json"
SERPER_PATH = "/search"


def _naver_payload() -> bytes:
    items = [
        {
            "title": "<b>MCP</b> 소개",
            "link": "https://a.example/1",
            "description": "설명 <b>하나</b>",
        },
        {"title": "두 번째", "link": "https://a.example/2", "description": "설명 둘"},
    ]
    return json.dumps({"items": items}, ensure_ascii=False).encode()


def _serper_payload() -> bytes:
    organic = [
        {"title": "t1", "link": "https://g.example/1", "snippet": "s1", "position": 1},
        {"title": "t2", "link": "https://g.example/2", "snippet": "s2"},
    ]
    return json.dumps({"organic": organic}, ensure_ascii=False).encode()


async def test_naver_parses_items_strips_html_and_records_request() -> None:
    received: list[RecordedRequest] = []
    routes = {NAVER_BASE_PATH: FakeResponse(body=_naver_payload())}
    with make_server(routes, received=received) as base:
        provider = NaverProvider(
            client_id="cid",
            client_secret="csec",
            base_url=f"{base}{NAVER_BASE_PATH}",
            min_request_interval=0.0,
        )
        results = await provider.search("mcp", 3)

    assert [r.url for r in results] == ["https://a.example/1", "https://a.example/2"]
    assert results[0].title == "MCP 소개"
    assert "<" not in results[0].title + results[0].snippet
    assert [r.rank for r in results] == [1, 2]
    assert all(r.provider is SearchProviderName.NAVER for r in results)

    request = received[0]
    assert request.method == "GET"
    assert request.path.startswith(f"{NAVER_BASE_PATH}?")
    assert "query=mcp" in request.path
    assert "display=3" in request.path
    assert request.headers["x-naver-client-id"] == "cid"
    assert request.headers["x-naver-client-secret"] == "csec"


async def test_naver_auth_failure_raises_without_retry() -> None:
    calls = {"count": 0}

    def unauthorized() -> FakeResponse:
        calls["count"] += 1
        return FakeResponse(status=401, body=b'{"errorMessage":"auth"}')

    with make_server({NAVER_BASE_PATH: unauthorized}) as base:
        provider = NaverProvider(
            client_id="x",
            client_secret="y",
            base_url=f"{base}{NAVER_BASE_PATH}",
            min_request_interval=0.0,
        )
        with pytest.raises(SearchProviderError) as exc_info:
            await provider.search("q", 5)

    assert exc_info.value.provider is SearchProviderName.NAVER
    assert "401" in exc_info.value.detail
    assert calls["count"] == 1


async def test_serper_posts_api_key_and_parses_organic() -> None:
    received: list[RecordedRequest] = []
    routes = {SERPER_PATH: FakeResponse(body=_serper_payload())}
    with make_server(routes, received=received) as base:
        provider = SerperProvider(api_key="sk", base_url=f"{base}{SERPER_PATH}")
        results = await provider.search("mcp", 2)

    assert [r.url for r in results] == ["https://g.example/1", "https://g.example/2"]
    assert results[0].rank == 1
    assert results[1].rank == 2
    assert all(r.provider is SearchProviderName.SERPER for r in results)

    request = received[0]
    assert request.method == "POST"
    assert request.headers["x-api-key"] == "sk"
    assert json.loads(request.body) == {"q": "mcp", "num": 2}


async def test_serper_retries_429_then_succeeds() -> None:
    calls = {"count": 0}

    def flaky() -> FakeResponse:
        calls["count"] += 1
        if calls["count"] < 2:
            return FakeResponse(status=429)
        return FakeResponse(body=_serper_payload())

    with make_server({SERPER_PATH: flaky}) as base:
        provider = SerperProvider(
            api_key="sk",
            base_url=f"{base}{SERPER_PATH}",
            max_attempts=3,
            retry_wait_base=0.01,
        )
        results = await provider.search("mcp", 2)

    assert len(results) == 2
    assert calls["count"] == 2


DDGS_ROWS: list[dict[str, object]] = [
    {"title": "T", "href": "https://d.example/1", "body": "B"},
]
ScriptStep = list[dict[str, object]] | Exception


class _FakeDdgsClient:
    """DDGS.text 계약을 따르는 스크립트 기반 가짜 클라이언트."""

    def __init__(self, script: list[ScriptStep]) -> None:
        self._script = script
        self.calls: list[dict[str, object]] = []

    def text(self, query: str, **kwargs: object) -> list[dict[str, object]]:
        step = self._script.pop(0)
        self.calls.append({"query": query, **kwargs})
        if isinstance(step, BaseException):
            raise step
        return step


async def test_ddgs_maps_rows_and_passes_max_results() -> None:
    client = _FakeDdgsClient([DDGS_ROWS])
    provider = DdgsProvider(client_factory=lambda: client)
    results = await provider.search("mcp", 5)

    assert client.calls == [{"query": "mcp", "max_results": 5}]
    assert results[0].url == "https://d.example/1"
    assert results[0].title == "T"
    assert results[0].snippet == "B"
    assert results[0].rank == 1
    assert results[0].provider is SearchProviderName.DDGS


async def test_ddgs_recovers_after_one_ratelimit() -> None:
    client = _FakeDdgsClient([RatelimitException("slow down"), DDGS_ROWS])
    provider = DdgsProvider(client_factory=lambda: client, retry_wait_base=0.01)
    results = await provider.search("mcp", 5)

    assert len(results) == 1
    assert len(client.calls) == 2


async def test_ddgs_gives_up_after_max_ratelimits() -> None:
    client = _FakeDdgsClient([RatelimitException("x")] * 3)
    provider = DdgsProvider(
        client_factory=lambda: client,
        max_attempts=3,
        retry_wait_base=0.01,
    )

    with pytest.raises(SearchProviderError) as exc_info:
        await provider.search("mcp", 5)

    assert len(client.calls) == 3
    assert exc_info.value.provider is SearchProviderName.DDGS


class _StubProvider:
    """SearchProvider 프로토콜을 만족하는 최소 스텁."""

    def __init__(
        self,
        name: SearchProviderName,
        outcome: list[SearchResult] | Exception,
    ) -> None:
        self._name = name
        self._outcome = outcome
        self.calls = 0

    @property
    def name(self) -> SearchProviderName:
        return self._name

    async def search(self, query: str, count: int) -> list[SearchResult]:
        self.calls += 1
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return list(self._outcome)


def _result(provider: SearchProviderName) -> SearchResult:
    return SearchResult(
        url="https://x.example/",
        title="t",
        snippet="s",
        rank=1,
        provider=provider,
    )


async def test_chain_returns_first_success_without_calling_rest() -> None:
    ok = _StubProvider(SearchProviderName.NAVER, [_result(SearchProviderName.NAVER)])
    never = _StubProvider(
        SearchProviderName.SERPER,
        SearchProviderError(SearchProviderName.SERPER, "호출되면 안 됨"),
    )

    results = await SearchChain([ok, never]).search("mcp", 5)

    assert [r.provider for r in results] == [SearchProviderName.NAVER]
    assert ok.calls == 1
    assert never.calls == 0


async def test_chain_aggregates_all_failures() -> None:
    boom_a = _StubProvider(
        SearchProviderName.NAVER,
        SearchProviderError(SearchProviderName.NAVER, "HTTP 401"),
    )
    boom_b = _StubProvider(
        SearchProviderName.SERPER,
        SearchProviderError(SearchProviderName.SERPER, "HTTP 429"),
    )

    with pytest.raises(SearchChainError) as exc_info:
        await SearchChain([boom_a, boom_b]).search("mcp", 5)

    assert [a.provider for a in exc_info.value.attempts] == [
        SearchProviderName.NAVER,
        SearchProviderName.SERPER,
    ]
    assert boom_a.calls == 1
    assert boom_b.calls == 1
    assert "HTTP 401" in str(exc_info.value)


async def test_chain_requires_at_least_one_provider() -> None:
    with pytest.raises(ValueError, match="최소 한 개"):
        SearchChain([])


async def test_chain_from_env_builds_available_providers() -> None:
    full_env = {
        "NAVER_CLIENT_ID": "i",
        "NAVER_CLIENT_SECRET": "s",
        "SERPER_API_KEY": "k",
    }

    names = [p.name for p in chain_from_env(full_env).providers]

    assert names == [
        SearchProviderName.NAVER,
        SearchProviderName.SERPER,
        SearchProviderName.DDGS,
    ]
    assert [p.name for p in chain_from_env({}).providers] == [SearchProviderName.DDGS]
