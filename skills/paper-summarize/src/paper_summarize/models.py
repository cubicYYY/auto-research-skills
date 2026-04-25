from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class PaperSummary(BaseModel):
    """Structured summary schema — this is what the Claude API returns."""

    title: Optional[str] = Field(
        default=None,
        description="Paper title as stated by the authors. Null if not recoverable.",
    )
    authors: List[str] = Field(
        default_factory=list,
        description="First-author-first list of authors, if stated.",
    )
    tldr: str = Field(
        description="One-sentence summary (≤ 40 words). Plain language, no hedging.",
    )
    problem: str = Field(
        description="The specific problem or question the paper addresses. One paragraph.",
    )
    approach: str = Field(
        description="How the paper approaches the problem — method, model, architecture, technique. One paragraph.",
    )
    results: str = Field(
        description="Main quantitative or qualitative results. Include numbers where available.",
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Limitations the paper acknowledges OR that are evident from the method/results.",
    )
    contributions: List[str] = Field(
        default_factory=list,
        description="Distinct contributions enumerated as concise bullets.",
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="5-10 topical keywords useful for search/indexing.",
    )
