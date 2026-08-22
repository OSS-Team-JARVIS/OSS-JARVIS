"""ProtegoRobotsGate 계약 테스트: robots.txt 준수 판정을 검증한다."""

from __future__ import annotations

import pytest

from http_harness import FakeResponse, make_server
from jarvis_crawler.crawl.robots import ProtegoRobotsGate

pytestmark = pytest.mark.asyncio

ROBOTS_TXT = b"User-agent: *\nDisallow: /private/\n"


def _gate() -> ProtegoRobotsGate:
    return ProtegoRobotsGate(timeout_seconds=3.0)


async def test_allowed_when_path_not_disallowed() -> None:
    routes = {"/robots.txt": FakeResponse(body=ROBOTS_TXT)}
    with make_server(routes) as base:
        assert await _gate().allowed(f"{base}/public/page") is True


async def test_disallowed_path_returns_false() -> None:
    routes = {"/robots.txt": FakeResponse(body=ROBOTS_TXT)}
    with make_server(routes) as base:
        assert await _gate().allowed(f"{base}/private/doc") is False


async def test_missing_robots_fails_open() -> None:
    with make_server({}) as base:  # robots.txt 없음(404)
        assert await _gate().allowed(f"{base}/anything") is True


async def test_unreachable_host_fails_open() -> None:
    with make_server({}) as base:
        url = f"{base}/anything"
    # 서버를 닫은 뒤 호출 → 연결 거부 상태
    assert await _gate().allowed(url) is True


async def test_robots_fetched_once_per_host() -> None:
    calls = {"count": 0}

    def robots() -> FakeResponse:
        calls["count"] += 1
        return FakeResponse(body=ROBOTS_TXT)

    with make_server({"/robots.txt": robots}) as base:
        gate = _gate()
        await gate.allowed(f"{base}/first")
        await gate.allowed(f"{base}/second")

    assert calls["count"] == 1
