"""데모·개발용 CLI 진입점(M4): 질의 하나로 리서치 JSON 파일을 뽑아낸다."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from jarvis_crawler.errors import SearchChainError
from jarvis_crawler.pipeline import build_default_pipeline
from jarvis_crawler.types import DEFAULT_MAX_CONTENT_CHARS

if TYPE_CHECKING:
    from collections.abc import Callable

    from jarvis_crawler.pipeline import ResearchPipeline


def build_parser() -> argparse.ArgumentParser:
    """CLI 인자 해석기를 만든다."""
    parser = argparse.ArgumentParser(
        prog="jarvis_crawler",
        description="키워드로 검색, 크롤링, 본문 추출을 수행해 JSON으로 저장한다",
    )
    parser.add_argument("query", help="검색 질의")
    parser.add_argument("--count", type=int, default=10, help="검색 결과 요청 수")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=8,
        help="실제 크롤링할 최대 페이지 수",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CONTENT_CHARS,
        help="페이지당 본문 최대 글자 수",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="출력 JSON 경로(기본: research_<타임스탬프>.json)",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    pipeline_factory: Callable[..., ResearchPipeline] = build_default_pipeline,
) -> int:
    """질의로 파이프라인을 실행하고 번들을 JSON 파일로 기록한다.

    검색 체인 전체가 실패하면 프로바이더별 사유를 stderr에 남기고 1을
    반환한다.
    """
    args = build_parser().parse_args(argv)
    pipeline = pipeline_factory(max_pages=args.max_pages, max_chars=args.max_chars)
    try:
        bundle = asyncio.run(pipeline.run(args.query, count=args.count))
    except SearchChainError as exc:
        details = "; ".join(
            f"{attempt.provider.value}: {attempt.detail}" for attempt in exc.attempts
        )
        print(f"검색 실패: {details}", file=sys.stderr)
        return 1
    output_path = (
        Path(args.output)
        if args.output is not None
        else Path(datetime.now().astimezone().strftime("research_%Y%m%d_%H%M%S.json"))
    )
    output_path.write_text(bundle.to_json(indent=2), encoding="utf-8")
    summary = f"{len(bundle.pages)}페이지 수집, {len(bundle.failures)}건 실패"
    print(f"{summary} -> {output_path}")
    return 0
