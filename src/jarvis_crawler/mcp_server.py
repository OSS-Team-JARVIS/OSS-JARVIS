"""MCP 서버 노출 계층(M5): web_search·crawl 두 도구만 제공한다.

설계 문서 §4.4의 에이전트 진입점이다. mcp SDK 2.x의 고수준
:class:`MCPServer` 를 stdio 전송으로 구동한다. 도구 함수는 모듈 수준
팩토리(_chain_factory·_pipeline_factory)를 호출 시점에 조회하므로
테스트에서 monkeypatch로 갈아끼울 수 있다.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from mcp.server.mcpserver import MCPServer

from jarvis_crawler.errors import CrawlerError, SearchChainError, SearchProviderError
from jarvis_crawler.pipeline import build_default_pipeline
from jarvis_crawler.search.chain import SearchChain, chain_from_env, make_provider
from jarvis_crawler.types import DEFAULT_MAX_CONTENT_CHARS

if TYPE_CHECKING:
    from jarvis_crawler.pipeline import SearchGateway
    from jarvis_crawler.types import SearchResult

mcp = MCPServer("jarvis-crawler")


def _default_chain(engine: str | None) -> SearchGateway:
    """엔진 미지정 시 폴백 체인, 지정 시 단일 프로바이더 체인을 만든다."""
    if engine is None:
        return chain_from_env()
    return SearchChain([make_provider(engine)])


_chain_factory = _default_chain
_pipeline_factory = build_default_pipeline


def _serialize_results(results: list[SearchResult]) -> str:
    """검색 결과 목록을 에이전트 친화적 JSON 배열 문자열로 직렬화한다."""
    payload = [
        {
            "url": result.url,
            "title": result.title,
            "snippet": result.snippet,
            "rank": result.rank,
            "provider": str(result.provider.value),
        }
        for result in results
    ]
    return json.dumps(payload, ensure_ascii=False)


@mcp.tool()
async def web_search(
    query: str,
    engine: str | None = None,
    count: int = 10,
) -> str:
    """키워드로 웹 검색해 결과를 JSON 배열 문자열로 반환한다.

    engine은 naver|serper|ddgs 중 하나로, 미지정 시 네이버→Serper→DDGS
    폴백 체인을 사용한다. 성공 시 ``[{url, title, snippet, rank,
    provider}, ...]``, 실패 시 ``{"error": "..."}`` JSON을 돌려준다.
    """
    try:
        gateway = _chain_factory(engine.strip().lower() if engine else None)
        results = await gateway.search(query, count)
    except (ValueError, SearchProviderError, SearchChainError) as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    return _serialize_results(results)


@mcp.tool()
async def crawl(urls: list[str], max_chars: int = DEFAULT_MAX_CONTENT_CHARS) -> str:
    """URL 목록을 직접 크롤링해 본문과 실패 목록 JSON을 반환한다.

    robots.txt 확인→페치→본문 추출 순서로 처리하며 한 URL의 실패는
    나머지 처리를 막지 않는다. 반환 형태는
    ``{"query": "", "results": [...], "failures": [...]}`` 이다.
    """
    try:
        pipeline = _pipeline_factory()
        bundle = await pipeline.crawl_urls(urls, max_chars=max_chars)
    except CrawlerError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    return bundle.to_json()


def main() -> None:
    """표준 입출력(stdio) 전송으로 MCP 서버를 구동한다(Claude Desktop 등에서 사용)."""
    mcp.run()


if __name__ == "__main__":
    main()
