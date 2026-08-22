"""Main-content extraction: trafilatura primary, newspaper4k fallback."""

from __future__ import annotations

import re
import warnings

import trafilatura

from jarvis_crawler.types import (
    DEFAULT_MAX_CONTENT_CHARS,
    ExtractedContent,
    ExtractorName,
    FetchedDocument,
)


def _extract_with_trafilatura(html: str, url: str) -> tuple[str, str] | None:
    """trafilatura로 본문(markdown)과 제목을 추출한다. 실패 시 None."""
    text = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        favor_recall=True,
    )
    if not text or not text.strip():
        return None
    metadata = trafilatura.extract_metadata(html)
    title = str(metadata.title) if metadata is not None and metadata.title else ""
    return text, title


def _korean_tokenizer(text: str) -> list[str]:
    """한국어 어절 토크나이저: newspaper ko 모듈의 nltk 하드 의존(nltk+punkt) 대체용."""
    return re.findall(r"[가-힣A-Za-z0-9]+", text)


def _extract_with_newspaper(html: str, url: str) -> tuple[str, str] | None:
    """newspaper4k로 본문과 제목을 추출한다(trafilatura 폴백). 실패 시 None."""
    # 지연 임포트: newspaper는 임포트 비용이 커서 필요할 때만 로드한다.
    # nltk 미설치 경고는 파싱에 무해하지만 pytest가 에러로 승격하므로 여기서만 억제.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        from newspaper import Article
        from newspaper.languages import ko as ko_lang

        # newspaper ko.py의 tokenizer는 nltk+punkt 데이터를 강요하므로 경량 대체로 교체.
        # 접미사 기반 find_stopwords(한국어 불용어 처리)는 라이브러리 것을 그대로 쓴다.
        ko_lang.tokenizer = _korean_tokenizer

        article = Article(url)
        article.download(input_html=html)
        article.parse()
    text = article.text or ""
    if not text.strip():
        return None
    return text, article.title or ""


class MainContentExtractor:
    """본문 추출기: trafilatura 1차 → newspaper4k 폴백.

    두 추출기 모두 빈 결과를 내면 ``content=""`` 인 ExtractedContent를
    반환한다. 파이프라인이 이를 :attr:`FetchFailureReason.EXTRACT_EMPTY`
    실패로 재분류하는 것이 계약이다.
    """

    def extract(
        self,
        document: FetchedDocument,
        *,
        max_chars: int = DEFAULT_MAX_CONTENT_CHARS,
    ) -> ExtractedContent:
        """HTML에서 본문을 추출해 ``max_chars`` 자로 절단해 반환한다."""
        primary = _extract_with_trafilatura(document.html, document.url)
        if primary is not None:
            return _to_content(document, primary, ExtractorName.TRAFILATURA, max_chars)
        secondary = _extract_with_newspaper(document.html, document.url)
        if secondary is not None:
            return _to_content(document, secondary, ExtractorName.NEWSPAPER4K, max_chars)
        return ExtractedContent(
            url=document.url,
            title="",
            content="",
            extractor=ExtractorName.NEWSPAPER4K,
        )


def _to_content(
    document: FetchedDocument,
    extracted: tuple[str, str],
    name: ExtractorName,
    max_chars: int,
) -> ExtractedContent:
    """(본문, 제목) 튜플을 계약 타입으로 변환하고 절단한다."""
    text, title = extracted
    return ExtractedContent(
        url=document.url,
        title=title,
        content=text[:max_chars],
        extractor=name,
    )
