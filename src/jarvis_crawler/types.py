"""Core data contracts shared across every jarvis_crawler module.

These frozen dataclasses are the single source of truth for data flowing
between the search layer, the crawl layer, and the report pipeline.
Serialization to JSON (for the summarizer part) is defined on
:class:`ResearchBundle`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final


class SearchProviderName(StrEnum):
    """Identifies which search backend produced a result."""

    NAVER = "naver"
    SERPER = "serper"
    DDGS = "ddgs"


class FetchFailureReason(StrEnum):
    """Why fetching or extracting one URL did not succeed."""

    ROBOTS_DISALLOWED = "robots_disallowed"
    HTTP_ERROR = "http_error"
    TIMEOUT = "timeout"
    DECODE_ERROR = "decode_error"
    EXTRACT_EMPTY = "extract_empty"
    UNKNOWN = "unknown"


class ExtractorName(StrEnum):
    """Which main-content extraction library produced the text."""

    TRAFILATURA = "trafilatura"
    NEWSPAPER4K = "newspaper4k"


DEFAULT_MAX_CONTENT_CHARS: Final[int] = 10_000


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One organic result returned by a search provider."""

    url: str
    title: str
    snippet: str
    rank: int
    provider: SearchProviderName


@dataclass(frozen=True, slots=True)
class FetchedDocument:
    """Raw HTML successfully downloaded for one URL."""

    url: str
    final_url: str
    status: int
    html: str
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class ExtractedContent:
    """Main-body text extracted from a fetched document."""

    url: str
    title: str
    content: str
    extractor: ExtractorName


@dataclass(frozen=True, slots=True)
class FailedFetch:
    """One URL we gave up on; kept so failures stay auditable."""

    url: str
    reason: FetchFailureReason
    detail: str


FetchOutcome = FetchedDocument | FailedFetch


@dataclass(frozen=True, slots=True)
class CrawledPage:
    """One successfully crawled page handed to the summarizer part.

    ``fetched_at`` must be a timezone-aware UTC datetime.
    """

    url: str
    final_url: str
    status: int
    title: str
    content: str
    content_length: int
    extractor: ExtractorName
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class ResearchBundle:
    """Final pipeline output: crawled pages plus recorded failures."""

    query: str
    pages: tuple[CrawledPage, ...]
    failures: tuple[FailedFetch, ...]

    def to_json(self, *, indent: int | None = None) -> str:
        """Serialize to UTF-8 JSON; datetimes become ISO-8601 strings."""
        return json.dumps(
            _bundle_payload(self),
            ensure_ascii=False,
            indent=indent,
        )


def _bundle_payload(
    bundle: ResearchBundle,
) -> dict[str, str | list[dict[str, str | int]]]:
    """Build the JSON-ready dict for a bundle (internal helper)."""
    return {
        "query": bundle.query,
        "results": [_page_payload(p) for p in bundle.pages],
        "failures": [_failure_payload(f) for f in bundle.failures],
    }


def _page_payload(page: CrawledPage) -> dict[str, str | int]:
    """Build the JSON-ready dict for one crawled page (internal)."""
    return {
        "url": page.url,
        "final_url": page.final_url,
        "status": page.status,
        "title": page.title,
        "content": page.content,
        "content_length": page.content_length,
        "extractor": str(page.extractor.value),
        "fetched_at": page.fetched_at.isoformat(),
    }


def _failure_payload(failure: FailedFetch) -> dict[str, str]:
    """Build the JSON-ready dict for one failed fetch (internal)."""
    return {
        "url": failure.url,
        "reason": str(failure.reason.value),
        "detail": failure.detail,
    }
