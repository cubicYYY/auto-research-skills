from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from paper_search.models import Paper, canonical_arxiv_id


class ArxivSource:
    name = "arxiv"
    needs_key = False

    async def search(
        self, query: str, *, year_from: int, year_to: int, limit: int
    ) -> list[Paper]:
        import arxiv

        def _run() -> list[Paper]:
            client = arxiv.Client(page_size=min(limit, 100), delay_seconds=3.0, num_retries=2)
            search = arxiv.Search(
                query=query,
                max_results=limit,
                sort_by=arxiv.SortCriterion.Relevance,
            )
            out: list[Paper] = []
            try:
                for r in client.results(search):
                    year = _year_of(r.published)
                    if year is not None and (year < year_from or year > year_to):
                        continue
                    aid = canonical_arxiv_id(r.get_short_id())
                    out.append(
                        Paper(
                            title=(r.title or "").strip(),
                            authors=[a.name for a in (r.authors or [])],
                            year=year,
                            venue=(r.journal_ref or None),
                            abstract=(r.summary or "").strip(),
                            doi=r.doi,
                            arxiv_id=aid,
                            url=r.entry_id,
                            pdf_url=r.pdf_url,
                            sources=["arxiv"],
                        )
                    )
                    if len(out) >= limit:
                        break
            except Exception:
                return out
            return out

        return await asyncio.to_thread(_run)


def _year_of(dt) -> Optional[int]:
    if not dt:
        return None
    if isinstance(dt, datetime):
        return dt.year
    try:
        return int(str(dt)[:4])
    except Exception:
        return None
