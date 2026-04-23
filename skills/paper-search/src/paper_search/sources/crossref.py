from __future__ import annotations

import asyncio
from typing import Any, Optional

from paper_search.models import Paper, canonical_doi


class CrossrefSource:
    name = "crossref"
    needs_key = False

    async def search(
        self, query: str, *, year_from: int, year_to: int, limit: int
    ) -> list[Paper]:
        from habanero import Crossref

        def _run() -> list[Paper]:
            cr = Crossref(timeout=30)
            res = cr.works(
                query=query,
                limit=min(limit, 100),
                filter={
                    "from-pub-date": f"{year_from}-01-01",
                    "until-pub-date": f"{year_to}-12-31",
                    "type": "journal-article",
                },
            )
            out: list[Paper] = []
            try:
                items = ((res or {}).get("message") or {}).get("items") or []
                for it in items:
                    p = _to_paper(it)
                    if p is not None:
                        out.append(p)
                    if len(out) >= limit:
                        break
            except Exception:
                return out
            return out

        return await asyncio.to_thread(_run)


def _to_paper(it: dict[str, Any]) -> Optional[Paper]:
    titles = it.get("title") or []
    title = (titles[0] if titles else "").strip()
    if not title:
        return None

    authors = []
    for a in it.get("author") or []:
        given = (a or {}).get("given") or ""
        family = (a or {}).get("family") or ""
        name = f"{given} {family}".strip()
        if name:
            authors.append(name)

    year = None
    for key in ("issued", "published-print", "published-online", "created"):
        dp = ((it.get(key) or {}).get("date-parts") or [[]])[0]
        if dp and dp[0]:
            year = int(dp[0])
            break

    doi = it.get("DOI")
    doi = canonical_doi(doi) if doi else None

    container = (it.get("container-title") or [None])[0]
    url = it.get("URL")

    return Paper(
        title=title,
        authors=authors,
        year=year,
        venue=container,
        abstract=(it.get("abstract") or None),
        doi=doi,
        url=url,
        citation_count=it.get("is-referenced-by-count"),
        sources=["crossref"],
    )
