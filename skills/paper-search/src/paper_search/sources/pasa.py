from __future__ import annotations

import os
import re
from typing import Any, Optional

import httpx

from paper_search.models import Paper, canonical_arxiv_id, canonical_doi

DEFAULT_ENDPOINT = "https://pasa-agent.ai/home"
ARXIV_ID_RE = re.compile(r"(?:arxiv\.org/(?:abs|pdf)/)(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)


class PasaSource:
    """ByteDance PaSa LLM-agent paper search.

    The public entry point is a web UI at https://pasa-agent.ai/home?query=...
    that returns an SPA shell. Override with `PASA_ENDPOINT` to point at the
    JSON API when you have access; otherwise the adapter falls back to
    extracting arXiv IDs from whatever HTML the page embeds and resolving
    them via arXiv's bulk `id_list` endpoint.
    """

    name = "pasa"
    needs_key = False

    async def search(
        self, query: str, *, year_from: int, year_to: int, limit: int
    ) -> list[Paper]:
        endpoint = os.environ.get("PASA_ENDPOINT", DEFAULT_ENDPOINT)
        async with httpx.AsyncClient(
            timeout=45, follow_redirects=True, headers={"User-Agent": "paper-search"}
        ) as client:
            r = await client.get(endpoint, params={"query": query})
            r.raise_for_status()
            ctype = r.headers.get("content-type", "").lower()
            if "json" in ctype:
                return _parse_json(r.json(), limit)
            # HTML fallback: pull arxiv IDs out of the page and hydrate from arXiv.
            aids = _extract_arxiv_ids(r.text)[:limit]
            if not aids:
                return []
            return await _hydrate_from_arxiv(client, aids, year_from, year_to, limit)


def _extract_arxiv_ids(html: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in ARXIV_ID_RE.finditer(html or ""):
        aid = canonical_arxiv_id(m.group(1))
        if aid in seen:
            continue
        seen.add(aid)
        out.append(aid)
    return out


async def _hydrate_from_arxiv(
    client: httpx.AsyncClient,
    ids: list[str],
    year_from: int,
    year_to: int,
    limit: int,
) -> list[Paper]:
    from paper_search.sources.github import _parse_arxiv_atom  # reuse parser

    out: list[Paper] = []
    for i in range(0, len(ids), 50):
        chunk = ids[i : i + 50]
        try:
            r = await client.get(
                "https://export.arxiv.org/api/query",
                params={"id_list": ",".join(chunk), "max_results": len(chunk)},
            )
            r.raise_for_status()
            out.extend(_parse_arxiv_atom(r.text))
        except Exception:
            continue
    kept: list[Paper] = []
    for p in out:
        if p.year is not None and (p.year < year_from or p.year > year_to):
            continue
        p.sources = ["pasa"]
        kept.append(p)
        if len(kept) >= limit:
            break
    return kept


def _parse_json(data: Any, limit: int) -> list[Paper]:
    items = []
    if isinstance(data, dict):
        items = data.get("papers") or data.get("results") or data.get("data") or []
    elif isinstance(data, list):
        items = data
    out: list[Paper] = []
    for it in items:
        p = _json_to_paper(it)
        if p is not None:
            out.append(p)
        if len(out) >= limit:
            break
    return out


def _json_to_paper(it: dict[str, Any]) -> Optional[Paper]:
    title = (it.get("title") or "").strip()
    if not title:
        return None
    doi = it.get("doi")
    doi = canonical_doi(doi) if doi else None
    arxiv_id = it.get("arxiv_id") or it.get("arxiv")
    arxiv_id = canonical_arxiv_id(arxiv_id) if arxiv_id else None
    authors = it.get("authors") or []
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(",") if a.strip()]
    year = it.get("year")
    try:
        year = int(year) if year else None
    except Exception:
        year = None
    return Paper(
        title=title,
        authors=list(authors),
        year=year,
        venue=it.get("venue"),
        abstract=it.get("abstract"),
        doi=doi,
        arxiv_id=arxiv_id,
        url=it.get("url"),
        pdf_url=it.get("pdf_url"),
        citation_count=it.get("citation_count"),
        sources=["pasa"],
    )
