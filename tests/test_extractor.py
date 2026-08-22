"""MainContentExtractor 단위 테스트.

네트워크 없이 로컬 HTML fixture만으로 본문 추출 계약(프로토콜 BodyExtractor)을
검증한다: 본문 보존, 노이즈 제거, 제목 추출, 글자 수 절단, 폴백, 완전 실패.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from jarvis_crawler.crawl import extractor as extractor_module
from jarvis_crawler.crawl.extractor import MainContentExtractor
from jarvis_crawler.types import (
    DEFAULT_MAX_CONTENT_CHARS,
    ExtractorName,
    FetchedDocument,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load_html(name: str) -> str:
    """fixture 파일을 UTF-8 문자열로 읽어온다."""
    return (FIXTURES / name).read_text(encoding="utf-8")


def _document(name: str = "article_ko.html") -> FetchedDocument:
    """fixture HTML을 FetchedDocument 계약으로 감싼다."""
    return FetchedDocument(
        url="https://example-daily.test/news/mcp-standard",
        final_url="https://example-daily.test/news/mcp-standard",
        status=200,
        html=_load_html(name),
        fetched_at=datetime(2026, 8, 22, 9, 0, tzinfo=UTC),
    )


def _always_none(html: str, url: str) -> tuple[str, str] | None:
    """폴백 경로 강제용 스텁: trafilatura가 항상 실패한 것처럼 동작한다."""
    return None


class TestMainContentExtractor:
    """Given 노이즈 포함 한국어 기사 HTML, When extract(), Then 계약 충족."""

    def test_extracts_korean_body_and_reports_trafilatura(self) -> None:
        result = MainContentExtractor().extract(
            _document(),
            max_chars=DEFAULT_MAX_CONTENT_CHARS,
        )

        assert "MCP가 사실상 표준" in result.content
        assert "개발 비용을 크게" in result.content
        assert result.extractor is ExtractorName.TRAFILATURA

    def test_drops_script_style_and_footer_noise(self) -> None:
        result = MainContentExtractor().extract(
            _document(),
            max_chars=DEFAULT_MAX_CONTENT_CHARS,
        )

        assert "tracking-pixel" not in result.content
        assert ".ad-banner" not in result.content
        assert "무단전재" not in result.content

    def test_title_comes_from_page_metadata(self) -> None:
        result = MainContentExtractor().extract(
            _document(),
            max_chars=DEFAULT_MAX_CONTENT_CHARS,
        )

        assert "AI 에이전트 시대" in result.title

    def test_truncates_to_exact_prefix_of_full_extraction(self) -> None:
        page = _document()
        full = MainContentExtractor().extract(
            page,
            max_chars=DEFAULT_MAX_CONTENT_CHARS,
        )
        truncated = MainContentExtractor().extract(page, max_chars=100)

        assert len(truncated.content) <= 100
        assert truncated.content == full.content[:100]

    def test_falls_back_to_newspaper4k_when_trafilatura_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(extractor_module, "_extract_with_trafilatura", _always_none)

        result = MainContentExtractor().extract(
            _document(),
            max_chars=DEFAULT_MAX_CONTENT_CHARS,
        )

        assert result.extractor is ExtractorName.NEWSPAPER4K
        assert "MCP가 사실상 표준" in result.content

    def test_returns_empty_content_for_text_free_page(self) -> None:
        result = MainContentExtractor().extract(
            _document("empty_page.html"),
            max_chars=DEFAULT_MAX_CONTENT_CHARS,
        )

        assert result.content == ""
