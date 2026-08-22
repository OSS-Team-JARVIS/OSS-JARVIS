"""Search-layer contracts.

A provider wraps one search backend (Naver Open API, Serper.dev, DDGS).
The pipeline only ever depends on the :class:`SearchProvider` protocol.
"""

from __future__ import annotations

from typing import Protocol

from jarvis_crawler.types import SearchProviderName, SearchResult


class SearchProvider(Protocol):
    """Anything that can turn a keyword query into ranked results."""

    @property
    def name(self) -> SearchProviderName:
        """Provider identity used in results and failure records."""
        ...

    async def search(self, query: str, count: int) -> list[SearchResult]:
        """Run ``query`` and return up to ``count`` organic results.

        Raises:
            SearchProviderError: when the backend cannot answer at all.
        """
        ...
