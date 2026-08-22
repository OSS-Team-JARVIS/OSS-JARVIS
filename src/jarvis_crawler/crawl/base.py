"""Crawl-layer contracts.

Three narrow capabilities, each with a Protocol so implementations
(curl_cffi fetcher, trafilatura extractor, protego robots gate) can be
swapped and tested independently.
"""

from __future__ import annotations

from typing import Protocol

from jarvis_crawler.types import ExtractedContent, FetchOutcome, FetchedDocument


class PageFetcher(Protocol):
    """Downloads a URL politely (delays, retries, TLS impersonation)."""

    async def fetch(self, url: str) -> FetchOutcome:
        """Fetch ``url``, returning a document or a recorded failure."""
        ...


class RobotsGate(Protocol):
    """Decides whether a URL may be crawled according to robots.txt."""

    async def allowed(self, url: str) -> bool:
        """Return True when crawling ``url`` is permitted."""
        ...


class BodyExtractor(Protocol):
    """Strips boilerplate from raw HTML down to the article body."""

    def extract(
        self,
        document: FetchedDocument,
        *,
        max_chars: int,
    ) -> ExtractedContent:
        """Extract main content, truncated to ``max_chars`` characters."""
        ...
