"""jarvis_crawler — Team JARVIS 자율 웹 서칭·크롤링 엔진.

키워드를 받아 검색 → 페이지 수집 → 본문 추출까지 수행하고,
요약 보고서 파트가 소비할 수 있는 JSON을 반환한다.
"""

from jarvis_crawler.types import (
    DEFAULT_MAX_CONTENT_CHARS,
    CrawledPage,
    ExtractedContent,
    ExtractorName,
    FailedFetch,
    FetchOutcome,
    FetchFailureReason,
    FetchedDocument,
    ResearchBundle,
    SearchResult,
    SearchProviderName,
)

__all__ = [
    "DEFAULT_MAX_CONTENT_CHARS",
    "CrawledPage",
    "ExtractedContent",
    "ExtractorName",
    "FailedFetch",
    "FetchFailureReason",
    "FetchedDocument",
    "FetchOutcome",
    "ResearchBundle",
    "SearchResult",
    "SearchProviderName",
]
