from __future__ import annotations

import asyncio
from typing import Any, Optional

from paper_search.models import Paper


class GoogleScholarSource:
    """Scrapes Google Scholar via `scholarly`. Opt-in only — aggressive IP blocking."""

    name = "google_scholar"
    needs_key = False

    async def search(
        self, query: str, *, year_from: int, year_to: int, limit: int
    ) -> list[Paper]:
        from scholarly import scholarly

        def _run() -> list[Paper]:
            out: list[Paper] = []
            try:
                it = scholarly.search_pubs(query, year_low=year_from, year_high=year_to)
                for _ in range(limit):
                    try:
                        raw = next(it)
                    except StopIteration:
                        break
                    p = _to_paper(raw)
                    if p is not None:
                        out.append(p)
            except Exception:
                return out
            return out

        return await asyncio.to_thread(_run)


def _to_paper(raw: dict[str, Any]) -> Optional[Paper]:
    b = raw.get("bib") or {}
    title = (b.get("title") or "").strip()
    if not title:
        return None

    authors = b.get("author") or []
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(" and ") if a.strip()]

    year = None
    try:
        if b.get("pub_year"):
            year = int(b["pub_year"])
    except Exception:
        year = None

    return Paper(
        title=title,
        authors=list(authors),
        year=year,
        venue=b.get("venue"),
        abstract=b.get("abstract"),
        url=raw.get("pub_url") or raw.get("eprint_url"),
        pdf_url=raw.get("eprint_url"),
        citation_count=raw.get("num_citations"),
        sources=["google_scholar"],
    )
