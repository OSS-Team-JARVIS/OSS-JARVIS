"""robots.txt compliance gate backed by protego."""

from __future__ import annotations

from typing import Final
from urllib.parse import urlsplit

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import CurlError
from protego import Protego

DEFAULT_USER_AGENT: str = "JARVISBot/0.1 (+https://github.com/OSS-Team-JARVIS/OSS-JARVIS)"
_HTTP_OK: Final[int] = 200


def _origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


class ProtegoRobotsGate:
    """도메인별 robots.txt 규칙을 캐싱하고 크롤링 허용 여부를 판정한다.

    robots.txt 가 없거나(404) 도달할 수 없으면 제한 없음으로 처리한다
    (RFC 9309: unavailable → crawl allowed). 실패를 차단보다 허용으로
    되돌리는 fail-open 정책이며, 파이프라인이 차단 URL만 별도 기록한다.
    """

    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: float = 10.0,
    ) -> None:
        """UA와 타임아웃 정책을 주입받아 초기화한다."""
        self._user_agent = user_agent
        self._timeout_seconds = timeout_seconds
        # 값이 None이면 해당 호스트는 제한 없음이 확정된 상태다.
        self._rules: dict[str, Protego | None] = {}

    async def allowed(self, url: str) -> bool:
        """``url`` 크롤링이 robots.txt 상 허용되는지 반환한다."""
        rules = await self._rules_for(url)
        if rules is None:
            return True
        return rules.can_fetch(url, self._user_agent)

    async def _rules_for(self, url: str) -> Protego | None:
        origin = _origin_of(url)
        if origin not in self._rules:
            self._rules[origin] = await self._load_rules(origin)
        return self._rules[origin]

    async def _load_rules(self, origin: str) -> Protego | None:
        body = await self._download_robots(f"{origin}/robots.txt")
        if body is None:
            return None
        return Protego.parse(body)

    async def _download_robots(self, robots_url: str) -> str | None:
        try:
            async with AsyncSession(timeout=self._timeout_seconds) as session:
                response = await session.get(robots_url)
        except CurlError:
            return None
        if response.status_code != _HTTP_OK:
            return None
        return response.text
