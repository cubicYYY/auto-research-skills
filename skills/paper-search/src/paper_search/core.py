from __future__ import annotations

import asyncio
import math
import re
from dataclasses import dataclass
from typing import Optional

from rank_bm25 import BM25Okapi

from paper_search.models import Paper
from paper_search.sources.base import Source

TEXT_WEIGHT = 0.60
CITE_WEIGHT = 0.30
RECENCY_WEIGHT = 0.10
BM25_PIVOT = 6.0
BM25_SCALE = 0.5
RECENCY_SIGMA_SQ = 3.0 * 3.0


@dataclass
class SearchResult:
    papers: list[Paper]
    total_candidates: int
    sources_used: list[str]
    errors: list[dict[str, str]]


@dataclass
class SourceOutcome:
    source: str
    papers: list[Paper]
    error: Optional[str] = None


def _tokenize(s: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if t]


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _all_keys(p: Paper) -> list[str]:
    from paper_search.models import (
        canonical_arxiv_id,
        canonical_doi,
        normalized_title_key,
    )

    keys: list[str] = []
    if p.doi:
        keys.append(f"doi:{canonical_doi(p.doi)}")
    if p.arxiv_id:
        keys.append(f"arxiv:{canonical_arxiv_id(p.arxiv_id)}")
    nt = normalized_title_key(p.title or "")
    if nt:
        keys.append(f"title:{nt}")
    return keys


def dedupe(papers: list[Paper]) -> list[Paper]:
    """Union-find merge: any two papers that share DOI, arXiv id, or normalized
    title collapse into one. A single weak/junk key (e.g. an alt-DOI from
    OpenAlex) no longer blocks a merge that the other keys clearly support."""

    parent: dict[int, int] = {}

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    key_owner: dict[str, int] = {}
    for idx, p in enumerate(papers):
        parent[idx] = idx
        for k in _all_keys(p):
            if k in key_owner:
                union(idx, key_owner[k])
            else:
                key_owner[k] = idx

    groups: dict[int, Paper] = {}
    for idx, p in enumerate(papers):
        root = find(idx)
        if root in groups:
            groups[root] = _merge(groups[root], p)
        else:
            groups[root] = p.model_copy(deep=True)
    return list(groups.values())


def _merge(a: Paper, b: Paper) -> Paper:
    def pick(x, y):
        if x in (None, "", 0):
            return y
        if y in (None, "", 0):
            return x
        return x

    out = a.model_copy(deep=True)
    out.title = a.title if len(a.title) >= len(b.title) else b.title
    out.authors = a.authors if len(a.authors) >= len(b.authors) else b.authors
    out.year = pick(a.year, b.year)
    out.venue = pick(a.venue, b.venue)
    # Keep the richer abstract
    ab_a = a.abstract or ""
    ab_b = b.abstract or ""
    out.abstract = ab_a if len(ab_a) >= len(ab_b) else ab_b
    out.doi = pick(a.doi, b.doi)
    out.arxiv_id = pick(a.arxiv_id, b.arxiv_id)
    out.url = pick(a.url, b.url)
    out.pdf_url = pick(a.pdf_url, b.pdf_url)
    out.citation_count = max(a.citation_count or 0, b.citation_count or 0) or None
    out.sources = sorted(set(a.sources) | set(b.sources))
    return out


def score_batch(papers: list[Paper], query: str, year_to: int) -> list[Paper]:
    if not papers:
        return papers

    corpus = [_tokenize(f"{p.title} {p.abstract or ''}") for p in papers]
    q_tokens = _tokenize(query)
    try:
        bm25 = BM25Okapi(corpus)
        raw_scores = bm25.get_scores(q_tokens) if q_tokens else [0.0] * len(papers)
    except Exception:
        raw_scores = [0.0] * len(papers)

    known_cites = [p.citation_count for p in papers if p.citation_count is not None]
    max_cite = max(known_cites) if known_cites else 0
    log_max = math.log1p(max_cite) if max_cite > 0 else 0.0
    neutral_cite = 0.5  # for papers where the source did not supply a count

    for p, raw in zip(papers, raw_scores):
        text = _sigmoid(BM25_SCALE * (float(raw) - BM25_PIVOT))

        if p.citation_count is None:
            cite = neutral_cite
        elif log_max > 0 and p.citation_count > 0:
            cite = math.log1p(p.citation_count) / log_max
        else:
            cite = 0.0

        if p.year is None:
            recency = 0.5
        else:
            delta = year_to - int(p.year)
            recency = math.exp(-(delta * delta) / (2.0 * RECENCY_SIGMA_SQ))

        p.score = (
            TEXT_WEIGHT * text + CITE_WEIGHT * cite + RECENCY_WEIGHT * recency
        )

    papers.sort(
        key=lambda x: (
            x.score or 0.0,
            x.citation_count or 0,
            x.year or 0,
        ),
        reverse=True,
    )
    return papers


async def fan_out(
    sources: list[Source],
    query: str,
    *,
    year_from: int,
    year_to: int,
    per_source: int,
) -> list[SourceOutcome]:
    async def one(src: Source) -> SourceOutcome:
        try:
            papers = await src.search(
                query, year_from=year_from, year_to=year_to, limit=per_source
            )
            for p in papers:
                if src.name not in p.sources:
                    p.sources.append(src.name)
            return SourceOutcome(source=src.name, papers=papers)
        except Exception as e:  # noqa: BLE001
            return SourceOutcome(source=src.name, papers=[], error=repr(e))

    return await asyncio.gather(*(one(s) for s in sources))


async def run_search(
    sources: list[Source],
    query: str,
    *,
    year_from: int,
    year_to: int,
    per_source: int,
    top: int,
) -> SearchResult:
    outcomes = await fan_out(
        sources, query, year_from=year_from, year_to=year_to, per_source=per_source
    )

    all_papers: list[Paper] = []
    errors: list[dict[str, str]] = []
    used: list[str] = []
    for o in outcomes:
        if o.error:
            errors.append({"source": o.source, "error": o.error})
        else:
            used.append(o.source)
        all_papers.extend(o.papers)

    merged = dedupe(all_papers)
    scored = score_batch(merged, query, year_to=year_to)
    return SearchResult(
        papers=scored[:top],
        total_candidates=len(merged),
        sources_used=used,
        errors=errors,
    )
