from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

from paper_search.models import Paper, canonical_arxiv_id, canonical_doi


class SemanticScholarSource:
    name = "semantic_scholar"
    needs_key = False

    async def search(
        self, query: str, *, year_from: int, year_to: int, limit: int
    ) -> list[Paper]:
        from semanticscholar import SemanticScholar

        api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or None

        def _run() -> list[Paper]:
            sch = SemanticScholar(api_key=api_key, timeout=30)
            results = sch.search_paper(
                query,
                limit=min(limit, 100),
                year=f"{year_from}-{year_to}",
                fields=[
                    "title",
                    "authors",
                    "year",
                    "venue",
                    "abstract",
                    "externalIds",
                    "openAccessPdf",
                    "citationCount",
                    "url",
                ],
            )
            out: list[Paper] = []
            try:
                for r in results:
                    p = _to_paper(r.raw_data if hasattr(r, "raw_data") else dict(r))
                    if p is not None:
                        out.append(p)
                    if len(out) >= limit:
                        break
            except Exception:
                return out
            return out

        return await asyncio.to_thread(_run)


def _to_paper(r: dict[str, Any]) -> Optional[Paper]:
    title = (r.get("title") or "").strip()
    if not title:
        return None
    ext = r.get("externalIds") or {}
    doi = ext.get("DOI")
    doi = canonical_doi(doi) if doi else None
    arxiv_id = ext.get("ArXiv")
    arxiv_id = canonical_arxiv_id(arxiv_id) if arxiv_id else None

    pdf_url = None
    oap = r.get("openAccessPdf") or {}
    if isinstance(oap, dict):
        pdf_url = oap.get("url")

    authors = []
    for a in r.get("authors") or []:
        name = (a or {}).get("name") if isinstance(a, dict) else None
        if name:
            authors.append(name)

    return Paper(
        title=title,
        authors=authors,
        year=r.get("year"),
        venue=r.get("venue") or None,
        abstract=r.get("abstract"),
        doi=doi,
        arxiv_id=arxiv_id,
        url=r.get("url"),
        pdf_url=pdf_url,
        citation_count=r.get("citationCount"),
        sources=["semantic_scholar"],
    )
