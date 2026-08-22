"""Typed exception hierarchy for jarvis_crawler.

Every error raised by this package subclasses :class:`CrawlerError` and
carries typed fields — never bare strings.
"""

from __future__ import annotations

from dataclasses import dataclass

from jarvis_crawler.types import SearchProviderName


@dataclass(frozen=True, slots=True)
class ProviderAttempt:
    """One failed provider call recorded while walking a search chain."""

    provider: SearchProviderName
    detail: str


class CrawlerError(Exception):
    """Base type for every error this package raises."""


class SearchProviderError(CrawlerError):
    """A single search backend failed to answer a query."""

    def __init__(self, provider: SearchProviderName, detail: str) -> None:
        self.provider = provider
        self.detail = detail
        super().__init__(f"[{provider}] {detail}")


class SearchChainError(CrawlerError):
    """Every provider in the chain failed; carries per-provider attempts."""

    def __init__(self, attempts: tuple[ProviderAttempt, ...]) -> None:
        self.attempts = attempts
        summary = "; ".join(f"[{a.provider}] {a.detail}" for a in attempts)
        super().__init__(f"all providers failed: {summary}")
