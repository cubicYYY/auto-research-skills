"""Thin wrapper over the GitHub Search API (repos + code).

No external dependencies beyond `httpx`. Auth via `GITHUB_TOKEN` env var.
Without a token the unauth rate limit is very low (10 req/min for search),
so the CLI warns loudly when the token is missing.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from similar_code_search.models import CodeHit, RepoHit

GITHUB_API = "https://api.github.com"
UA = "similar-code-search/0.1"


def _headers(*, code_search: bool = False) -> dict[str, str]:
    accept = "application/vnd.github.text-match+json" if code_search else "application/vnd.github+json"
    h = {"Accept": accept, "User-Agent": UA}
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def search_repos(
    query: str,
    *,
    language: str | None = None,
    min_stars: int = 0,
    sort: str = "best-match",   # or "stars" | "updated"
    limit: int = 30,
    client: httpx.Client | None = None,
) -> list[RepoHit]:
    qs = [query.strip()]
    if language:
        qs.append(f"language:{language}")
    if min_stars > 0:
        qs.append(f"stars:>={min_stars}")
    params: dict[str, Any] = {
        "q": " ".join(qs),
        "per_page": min(limit, 100),
    }
    if sort != "best-match":
        params["sort"] = sort
        params["order"] = "desc"

    own = client is None
    c = client or httpx.Client(timeout=30, headers=_headers())
    try:
        r = c.get(f"{GITHUB_API}/search/repositories", params=params)
        r.raise_for_status()
        items = (r.json() or {}).get("items") or []
    finally:
        if own:
            c.close()

    out: list[RepoHit] = []
    for it in items[:limit]:
        out.append(RepoHit(
            full_name=it.get("full_name", ""),
            html_url=it.get("html_url", ""),
            description=(it.get("description") or "").strip(),
            language=it.get("language"),
            topics=list(it.get("topics") or []),
            stars=int(it.get("stargazers_count") or 0),
            forks=int(it.get("forks_count") or 0),
            pushed_at=(it.get("pushed_at") or "")[:10],
            created_at=(it.get("created_at") or "")[:10],
        ))
    return out


def search_code(
    query: str,
    *,
    language: str | None = None,
    limit: int = 30,
    client: httpx.Client | None = None,
) -> list[CodeHit]:
    """Code-search requires a token (anon is refused with 422)."""
    if not os.environ.get("GITHUB_TOKEN"):
        return []

    qs = [query.strip()]
    if language:
        qs.append(f"language:{language}")
    params = {"q": " ".join(qs), "per_page": min(limit, 100)}

    own = client is None
    c = client or httpx.Client(timeout=30, headers=_headers(code_search=True))
    try:
        r = c.get(f"{GITHUB_API}/search/code", params=params)
        if r.status_code >= 400:
            # Code search can be disabled for the token; don't explode the caller.
            return []
        items = (r.json() or {}).get("items") or []
    finally:
        if own:
            c.close()

    out: list[CodeHit] = []
    for it in items[:limit]:
        repo = (it.get("repository") or {}).get("full_name", "")
        out.append(CodeHit(
            repo_full_name=repo,
            path=it.get("path", ""),
            html_url=it.get("html_url", ""),
            sha=it.get("sha", ""),
        ))
    return out


def fetch_readme_excerpt(
    full_name: str, *, client: httpx.Client | None = None, chars: int = 4000
) -> str | None:
    """Fetch README (raw) and return the first `chars` chars. Best-effort."""
    own = client is None
    c = client or httpx.Client(timeout=30, headers=_headers())
    try:
        r = c.get(f"{GITHUB_API}/repos/{full_name}/readme",
                  headers={"Accept": "application/vnd.github.raw"})
        if r.status_code != 200:
            return None
        text = r.text
        return text[:chars]
    except httpx.HTTPError:
        return None
    finally:
        if own:
            c.close()
