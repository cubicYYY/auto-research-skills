"""Thin GitHub Search wrapper (public endpoint, optional token)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
UA = "skill-finder/0.1"


@dataclass
class RepoHit:
    full_name: str          # "owner/name"
    html_url: str
    clone_url: str          # HTTPS
    stars: int
    description: str
    default_branch: str
    updated_at: str


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "User-Agent": UA}
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def search_skill_repos(query: str, *, limit: int = 10, min_stars: int = 5) -> list[RepoHit]:
    """Search GitHub for repositories that look like skill collections.

    We bias the query toward repos that (a) mention skills and (b) are plausible
    collections (path-in-name, description, or README), sorted by stars.
    """
    q_parts = [
        query.strip(),
        "(claude skills OR agent-skills OR agent skills)",
        f"stars:>={min_stars}",
    ]
    q = " ".join(x for x in q_parts if x)
    params = {"q": q, "sort": "stars", "order": "desc", "per_page": min(limit, 30)}
    with httpx.Client(timeout=30, headers=_headers()) as c:
        r = c.get(GITHUB_SEARCH_URL, params=params)
        r.raise_for_status()
        items = (r.json() or {}).get("items", []) or []
    return [_to_hit(it) for it in items[:limit]]


def _to_hit(it: dict[str, Any]) -> RepoHit:
    return RepoHit(
        full_name=it.get("full_name") or "",
        html_url=it.get("html_url") or "",
        clone_url=it.get("clone_url") or "",
        stars=int(it.get("stargazers_count") or 0),
        description=(it.get("description") or "").strip(),
        default_branch=it.get("default_branch") or "main",
        updated_at=(it.get("updated_at") or "")[:10],
    )


def resolve_spec(spec: str) -> str:
    """Normalize `owner/name`, a full HTTPS URL, or an ssh URL to an HTTPS
    clone URL. Accepts the shorthand `owner/name` that users tend to type."""
    s = spec.strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    if s.startswith("git@"):
        # git@github.com:owner/name.git → https://github.com/owner/name.git
        _, _, rest = s.partition(":")
        return f"https://github.com/{rest}"
    if "/" in s and " " not in s:
        return f"https://github.com/{s}.git"
    raise ValueError(f"cannot interpret repo spec: {spec!r}")
