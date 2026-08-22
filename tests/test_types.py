"""Contract tests for jarvis_crawler.types and jarvis_crawler.errors."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from jarvis_crawler.errors import (
    ProviderAttempt,
    SearchChainError,
    SearchProviderError,
)
from jarvis_crawler.types import (
    CrawledPage,
    ExtractorName,
    FailedFetch,
    FetchFailureReason,
    ResearchBundle,
    SearchProviderName,
    SearchResult,
)

FETCHED_AT = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)


def _page(content: str = "본문 텍스트") -> CrawledPage:
    return CrawledPage(
        url="https://example.com/ai",
        final_url="https://example.com/ai",
        status=200,
        title="AI 트렌드",
        content=content,
        content_length=len(content),
        extractor=ExtractorName.TRAFILATURA,
        fetched_at=FETCHED_AT,
    )


class TestFrozenContracts:
    def test_raises_frozen_instance_error_when_search_result_mutated(self):
        # Given
        result = SearchResult(
            url="https://a.com", title="t", snippet="s", rank=1,
            provider=SearchProviderName.NAVER,
        )
        # When
        with pytest.raises(FrozenInstanceError) as excinfo:
            setattr(result, "url", "https://b.com")
        # Then
        assert "cannot assign to field" in str(excinfo.value).lower()

    def test_raises_frozen_instance_error_when_bundle_mutated(self):
        # Given
        bundle = ResearchBundle(query="q", pages=(), failures=())
        # When / Then
        with pytest.raises(FrozenInstanceError):
            bundle.query = "other"


class TestResearchBundleJson:
    def test_keeps_korean_text_when_serialized_to_json(self):
        # Given
        bundle = ResearchBundle(
            query="최신 AI 트렌드", pages=(_page("한국어 본문입니다"),), failures=()
        )
        # When
        parsed = json.loads(bundle.to_json())
        # Then
        assert parsed["query"] == "최신 AI 트렌드"
        assert parsed["results"][0]["content"] == "한국어 본문입니다"

    def test_serializes_datetime_as_iso8601_string(self):
        # Given
        bundle = ResearchBundle(query="q", pages=(_page(),), failures=())
        # When
        parsed = json.loads(bundle.to_json())
        # Then
        assert parsed["results"][0]["fetched_at"] == "2026-08-22T12:00:00+00:00"

    def test_records_failures_alongside_results(self):
        # Given
        failure = FailedFetch(
            url="https://blocked.example.com/x",
            reason=FetchFailureReason.ROBOTS_DISALLOWED,
            detail="disallow /x",
        )
        bundle = ResearchBundle(query="q", pages=(_page(),), failures=(failure,))
        # When
        parsed = json.loads(bundle.to_json())
        # Then
        assert parsed["failures"][0]["reason"] == "robots_disallowed"
        assert parsed["failures"][0]["detail"] == "disallow /x"

    def test_uses_extractor_enum_value_not_repr(self):
        # Given
        bundle = ResearchBundle(query="q", pages=(_page(),), failures=())
        # When
        raw = bundle.to_json()
        # Then
        assert '"extractor": "trafilatura"' in raw


class TestTypedErrors:
    def test_formats_provider_name_and_detail_when_provider_error_raised(self):
        # When
        error = SearchProviderError(
            provider=SearchProviderName.SERPER, detail="401 unauthorized"
        )
        # Then
        assert error.provider is SearchProviderName.SERPER
        assert "[serper] 401 unauthorized" in str(error)

    def test_lists_every_attempt_when_chain_error_raised(self):
        # Given
        attempts = (
            ProviderAttempt(provider=SearchProviderName.NAVER, detail="quota"),
            ProviderAttempt(provider=SearchProviderName.DDGS, detail="ratelimit"),
        )
        # When
        error = SearchChainError(attempts)
        # Then
        assert len(error.attempts) == 2
        assert "[naver] quota" in str(error)
        assert "[ddgs] ratelimit" in str(error)
