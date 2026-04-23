from __future__ import annotations

import os
import re
from typing import Any, Optional

import httpx

from paper_search.cache import ResolvedCache
from paper_search.models import Paper, canonical_arxiv_id, canonical_doi

ARXIV_ID_RE = re.compile(
    r"(?:arxiv[:/]\s*|arxiv\.org/abs/)(\d{4}\.\d{4,5})(v\d+)?", re.IGNORECASE
)
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s)\]\"'<>]+)", re.IGNORECASE)

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
GITHUB_RAW_URL = "https://raw.githubusercontent.com/{repo}/{branch}/README.md"
PER_REPO_CAP = 15
MAX_REPOS = 5


class GithubSource:
    """Finds `awesome-*` paper lists, extracts arXiv/DOI refs, and resolves in bulk."""

    name = "github"
    needs_key = False

    async def search(
        self, query: str, *, year_from: int, year_to: int, limit: int
    ) -> list[Paper]:
        token = os.environ.get("GITHUB_TOKEN")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "paper-search"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=30, headers=headers) as client:
            repos = await _find_repos(client, query)
            arxiv_ids: list[str] = []
            dois: list[str] = []
            for repo in repos[:MAX_REPOS]:
                a_ids, d_ids = await _extract_refs(client, repo)
                # Keep the most recently added (bottom-of-list heuristic)
                a_ids = _dedupe_preserve(a_ids)[-PER_REPO_CAP:]
                d_ids = _dedupe_preserve(d_ids)[-PER_REPO_CAP:]
                arxiv_ids.extend(a_ids)
                dois.extend(d_ids)

            arxiv_ids = _dedupe_preserve(arxiv_ids)
            dois = _dedupe_preserve(dois)

            cache = ResolvedCache()
            try:
                resolved: list[Paper] = []

                need_arxiv: list[str] = []
                for aid in arxiv_ids:
                    cached = cache.get(f"arxiv:{aid}")
                    if cached is not None:
                        cached.sources = sorted(set(cached.sources) | {"github"})
                        resolved.append(cached)
                    else:
                        need_arxiv.append(aid)
                if need_arxiv:
                    fresh = await _bulk_arxiv(client, need_arxiv)
                    for p in fresh:
                        if p.arxiv_id:
                            cache.put(f"arxiv:{canonical_arxiv_id(p.arxiv_id)}", p)
                    resolved.extend(fresh)

                need_doi: list[str] = []
                for doi in dois:
                    cached = cache.get(f"doi:{doi}")
                    if cached is not None:
                        cached.sources = sorted(set(cached.sources) | {"github"})
                        resolved.append(cached)
                    else:
                        need_doi.append(doi)
                if need_doi:
                    fresh = await _bulk_crossref(client, need_doi)
                    for p in fresh:
                        if p.doi:
                            cache.put(f"doi:{canonical_doi(p.doi)}", p)
                    resolved.extend(fresh)

                # Filter by year window
                kept: list[Paper] = []
                for p in resolved:
                    if p.year is not None and (p.year < year_from or p.year > year_to):
                        continue
                    if "github" not in p.sources:
                        p.sources.append("github")
                    kept.append(p)
                return kept[:limit]
            finally:
                cache.close()


def _dedupe_preserve(xs: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in xs:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


async def _find_repos(client: httpx.AsyncClient, query: str) -> list[str]:
    q = f"awesome {query} papers in:name,description,readme stars:>20"
    try:
        r = await client.get(
            GITHUB_SEARCH_URL, params={"q": q, "per_page": MAX_REPOS, "sort": "stars"}
        )
        r.raise_for_status()
        items = (r.json() or {}).get("items") or []
        return [it["full_name"] for it in items if it.get("full_name")]
    except Exception:
        return []


async def _extract_refs(client: httpx.AsyncClient, repo: str) -> tuple[list[str], list[str]]:
    text = ""
    for branch in ("main", "master"):
        url = GITHUB_RAW_URL.format(repo=repo, branch=branch)
        try:
            r = await client.get(url)
            if r.status_code == 200:
                text = r.text
                break
        except Exception:
            continue
    if not text:
        return [], []
    arxiv_ids = [canonical_arxiv_id(m.group(1)) for m in ARXIV_ID_RE.finditer(text)]
    dois = [canonical_doi(m.group(1)) for m in DOI_RE.finditer(text)]
    return arxiv_ids, dois


async def _bulk_arxiv(client: httpx.AsyncClient, ids: list[str]) -> list[Paper]:
    if not ids:
        return []
    # arXiv API accepts id_list with commas; chunk defensively at 50.
    out: list[Paper] = []
    for chunk in _chunks(ids, 50):
        try:
            r = await client.get(
                "https://export.arxiv.org/api/query",
                params={"id_list": ",".join(chunk), "max_results": len(chunk)},
            )
            r.raise_for_status()
            out.extend(_parse_arxiv_atom(r.text))
        except Exception:
            continue
    return out


def _chunks(xs: list[str], n: int):
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


_ENTRY_RE = re.compile(r"<entry>(.*?)</entry>", re.DOTALL)
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL)
_SUMMARY_RE = re.compile(r"<summary>(.*?)</summary>", re.DOTALL)
_ID_RE = re.compile(r"<id>(.*?)</id>", re.DOTALL)
_PUB_RE = re.compile(r"<published>(\d{4})", re.DOTALL)
_AUTHOR_RE = re.compile(r"<author>\s*<name>(.*?)</name>", re.DOTALL)
_DOI_TAG_RE = re.compile(r"<arxiv:doi[^>]*>(.*?)</arxiv:doi>", re.DOTALL)


def _parse_arxiv_atom(xml: str) -> list[Paper]:
    out: list[Paper] = []
    for block in _ENTRY_RE.findall(xml):
        id_m = _ID_RE.search(block)
        id_url = (id_m.group(1).strip() if id_m else "") or ""
        aid = canonical_arxiv_id(id_url) if id_url else None
        if not aid:
            continue
        title = (_TITLE_RE.search(block).group(1).strip() if _TITLE_RE.search(block) else "").replace("\n", " ")
        summary_m = _SUMMARY_RE.search(block)
        abstract = summary_m.group(1).strip().replace("\n", " ") if summary_m else None
        authors = [a.strip() for a in _AUTHOR_RE.findall(block)]
        year = None
        pub_m = _PUB_RE.search(block)
        if pub_m:
            year = int(pub_m.group(1))
        doi_m = _DOI_TAG_RE.search(block)
        doi = canonical_doi(doi_m.group(1).strip()) if doi_m else None
        out.append(
            Paper(
                title=title,
                authors=authors,
                year=year,
                abstract=abstract,
                doi=doi,
                arxiv_id=aid,
                url=id_url,
                pdf_url=id_url.replace("/abs/", "/pdf/") if "/abs/" in id_url else None,
                sources=["github"],
            )
        )
    return out


async def _bulk_crossref(client: httpx.AsyncClient, dois: list[str]) -> list[Paper]:
    """CrossRef has no true batch endpoint; fetch each DOI's canonical work.

    We keep this serial (with tiny delay-free parallelism via gather) and small
    because the caller already caps the DOI set hard.
    """
    import asyncio as _asyncio

    async def one(doi: str) -> Optional[Paper]:
        try:
            r = await client.get(
                f"https://api.crossref.org/works/{doi}",
                headers={"User-Agent": "paper-search"},
            )
            r.raise_for_status()
            msg = (r.json() or {}).get("message") or {}
            return _crossref_to_paper(msg)
        except Exception:
            return None

    results = await _asyncio.gather(*(one(d) for d in dois))
    return [p for p in results if p is not None]


def _crossref_to_paper(msg: dict[str, Any]) -> Optional[Paper]:
    titles = msg.get("title") or []
    title = (titles[0] if titles else "").strip()
    if not title:
        return None
    authors = []
    for a in msg.get("author") or []:
        name = f"{(a.get('given') or '').strip()} {(a.get('family') or '').strip()}".strip()
        if name:
            authors.append(name)
    year = None
    for key in ("issued", "published-print", "published-online", "created"):
        dp = ((msg.get(key) or {}).get("date-parts") or [[]])[0]
        if dp and dp[0]:
            year = int(dp[0])
            break
    doi = msg.get("DOI")
    doi = canonical_doi(doi) if doi else None
    container = (msg.get("container-title") or [None])[0]
    return Paper(
        title=title,
        authors=authors,
        year=year,
        venue=container,
        abstract=msg.get("abstract"),
        doi=doi,
        url=msg.get("URL"),
        citation_count=msg.get("is-referenced-by-count"),
        sources=["github"],
    )
