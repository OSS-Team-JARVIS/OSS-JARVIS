"""CffiPageFetcher 계약 테스트: 로컬 HTTP 서버 대상(외부 네트워크 불필요)."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from http_harness import FakeResponse, article_bytes, make_server
from jarvis_crawler.crawl.fetcher import CffiPageFetcher
from jarvis_crawler.types import FetchedDocument, FetchFailureReason

pytestmark = pytest.mark.asyncio


def _fast_fetcher(
    *,
    timeout: float = 3.0,
    max_attempts: int = 2,
    delay_range: tuple[float, float] = (0.0, 0.0),
    retry_wait_base: float = 0.01,
) -> CffiPageFetcher:
    """테스트용 고속 페처: 딜레이·백오프를 제거해 실행 시간을 안정화한다."""
    return CffiPageFetcher(
        timeout=timeout,
        max_attempts=max_attempts,
        delay_range=delay_range,
        retry_wait_base=retry_wait_base,
    )


async def test_success_returns_document_with_utc_timestamp() -> None:
    with make_server({"/news/1": FakeResponse(body=article_bytes())}) as base:
        outcome = await _fast_fetcher().fetch(f"{base}/news/1")

    assert isinstance(outcome, FetchedDocument)
    assert outcome.status == 200
    assert "MCP가 사실상 표준" in outcome.html
    assert outcome.final_url.endswith("/news/1")
    assert outcome.fetched_at.utcoffset() == timedelta(0)


async def test_http_error_maps_to_failed_fetch() -> None:
    with make_server({}) as base:  # 라우트 없음 → 전부 404
        outcome = await _fast_fetcher().fetch(f"{base}/missing")

    assert outcome.reason is FetchFailureReason.HTTP_ERROR
    assert "404" in outcome.detail


async def test_timeout_maps_to_timeout_failure() -> None:
    routes = {"/slow": FakeResponse(delay=2.0, body=article_bytes())}
    with make_server(routes) as base:
        outcome = await _fast_fetcher(timeout=0.5).fetch(f"{base}/slow")

    assert outcome.reason is FetchFailureReason.TIMEOUT


async def test_redirect_records_final_url() -> None:
    routes = {
        "/old": FakeResponse(status=301, headers={"Location": "/new"}),
        "/new": FakeResponse(body=article_bytes()),
    }
    with make_server(routes) as base:
        outcome = await _fast_fetcher().fetch(f"{base}/old")

    assert isinstance(outcome, FetchedDocument)
    assert outcome.final_url.endswith("/new")
    assert "MCP가 사실상 표준" in outcome.html


async def test_retries_429_then_succeeds() -> None:
    calls = {"count": 0}

    def flaky() -> FakeResponse:
        calls["count"] += 1
        if calls["count"] < 2:
            return FakeResponse(status=429, headers={"Retry-After": "0"})
        return FakeResponse(body=article_bytes())

    with make_server({"/flaky": flaky}) as base:
        outcome = await _fast_fetcher(max_attempts=3).fetch(f"{base}/flaky")

    assert isinstance(outcome, FetchedDocument)
    assert calls["count"] == 2


async def test_gives_up_after_max_attempts_on_persistent_503() -> None:
    calls = {"count": 0}

    def broken() -> FakeResponse:
        calls["count"] += 1
        return FakeResponse(status=503)

    with make_server({"/broken": broken}) as base:
        outcome = await _fast_fetcher(max_attempts=2).fetch(f"{base}/broken")

    assert outcome.reason is FetchFailureReason.HTTP_ERROR
    assert "503" in outcome.detail
    assert calls["count"] == 2


async def test_euc_kr_page_decoded_via_charset_detection() -> None:
    raw = "본문 인코딩 감지 확인".encode("euc-kr")
    routes = {
        "/legacy": FakeResponse(headers={"Content-Type": "text/html"}, body=raw),
    }
    with make_server(routes) as base:
        outcome = await _fast_fetcher().fetch(f"{base}/legacy")

    assert isinstance(outcome, FetchedDocument)
    assert "인코딩 감지" in outcome.html


async def test_same_host_requests_are_serialized() -> None:
    log: list[tuple[float, float]] = []
    routes = {
        "/a": FakeResponse(delay=0.08, body=b"A"),
        "/b": FakeResponse(delay=0.08, body=b"B"),
    }
    with make_server(routes, request_log=log) as base:
        fetcher = _fast_fetcher(delay_range=(0.05, 0.05))
        await asyncio.gather(
            fetcher.fetch(f"{base}/a"),
            fetcher.fetch(f"{base}/b"),
        )

    assert len(log) == 2
    intervals = sorted(log)
    assert intervals[0][1] <= intervals[1][0] + 1e-6
