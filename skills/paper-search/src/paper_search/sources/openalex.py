from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

from paper_search.models import Paper, canonical_arxiv_id, canonical_doi


class OpenAlexSource:
    name = "openalex"
    needs_key = False

    async def search(
        self, query: str, *, year_from: int, year_to: int, limit: int
    ) -> list[Paper]:
        import pyalex
        from pyalex import Works

        email = os.environ.get("OPENALEX_EMAIL")
        if email:
            pyalex.config.email = email

        def _run() -> list[Paper]:
            works = (
                Works()
                .search(query)
                .filter(from_publication_date=f"{year_from}-01-01")
                .filter(to_publication_date=f"{year_to}-12-31")
            )
            out: list[Paper] = []
            try:
                for w in works.get(per_page=min(limit, 200)):
                    p = _to_paper(w)
                    if p is not None:
                        out.append(p)
                    if len(out) >= limit:
                        break
            except Exception:
                return out
            return out

        return await asyncio.to_thread(_run)


def _to_paper(w: dict[str, Any]) -> Optional[Paper]:
    title = (w.get("title") or w.get("display_name") or "").strip()
    if not title:
        return None
    authors = []
    for a in w.get("authorships") or []:
        name = ((a or {}).get("author") or {}).get("display_name")
        if name:
            authors.append(name)

    doi = w.get("doi")
    doi = canonical_doi(doi) if doi else None

    ids = w.get("ids") or {}
    arxiv_id = None
    arxiv_url = ids.get("arxiv") or ""
    if "arxiv.org/abs/" in arxiv_url:
        arxiv_id = canonical_arxiv_id(arxiv_url)

    loc = (w.get("primary_location") or {}) or {}
    pdf_url = loc.get("pdf_url")
    source = (loc.get("source") or {}) or {}
    venue = source.get("display_name")

    inv = w.get("abstract_inverted_index")
    abstract = _inv_index_to_text(inv) if inv else None

    return Paper(
        title=title,
        authors=authors,
        year=w.get("publication_year"),
        venue=venue,
        abstract=abstract,
        doi=doi,
        arxiv_id=arxiv_id,
        url=w.get("id"),
        pdf_url=pdf_url,
        citation_count=w.get("cited_by_count"),
        sources=["openalex"],
    )


def _inv_index_to_text(inv: dict[str, list[int]]) -> str:
    positions: list[tuple[int, str]] = []
    for word, idxs in (inv or {}).items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)
