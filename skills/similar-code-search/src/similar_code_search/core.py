"""Pipeline: fan out to GitHub repo/code search, merge, score, return."""
from __future__ import annotations

import os

import httpx

from similar_code_search.github import fetch_readme_excerpt, search_code, search_repos
from similar_code_search.models import CodeHit, RepoHit, SearchReport
from similar_code_search.scoring import score_repos


def run(
    query: str,
    *,
    language: str | None = None,
    min_stars: int = 5,
    per_search: int = 30,
    fetch_readme_for: int = 10,
) -> SearchReport:
    """Execute the full search.

    `fetch_readme_for`: READMEs of this many top repo-search results get
    fetched to enrich the BM25 corpus. Code-search hits are merged in as a
    `code_match` boost and an aggregated `matched_files` list per repo.
    """
    errors: list[dict[str, str]] = []
    used: list[str] = []
    repos: list[RepoHit] = []
    code: list[CodeHit] = []

    from similar_code_search.github import _headers  # keep one client for connection reuse
    headers = _headers()

    with httpx.Client(timeout=30, headers=headers) as client:
        # --- repo search (always) ---
        try:
            repos = search_repos(
                query, language=language, min_stars=min_stars,
                limit=per_search, client=client,
            )
            used.append("repos")
        except Exception as e:
            errors.append({"backend": "repos", "error": repr(e)})

        # --- repo search variant: sort by stars, to surface established work ---
        try:
            extra = search_repos(
                query, language=language, min_stars=min_stars,
                sort="stars", limit=max(10, per_search // 2), client=client,
            )
            # merge new repos by full_name
            existing = {r.full_name for r in repos}
            repos.extend(r for r in extra if r.full_name not in existing)
            used.append("repos-by-stars")
        except Exception as e:
            errors.append({"backend": "repos-by-stars", "error": repr(e)})

        # --- code search (only if GITHUB_TOKEN is set) ---
        if os.environ.get("GITHUB_TOKEN"):
            try:
                code = search_code(query, language=language, limit=per_search, client=client)
                used.append("code")
                # Fold any code-hit repos into the candidate pool so the
                # ranker sees them even if repo search missed them.
                seen = {r.full_name for r in repos}
                hit_repo_names = {ch.repo_full_name for ch in code if ch.repo_full_name not in seen}
                for full_name in list(hit_repo_names)[:20]:
                    try:
                        r = client.get(f"https://api.github.com/repos/{full_name}")
                        if r.status_code == 200:
                            d = r.json()
                            repos.append(RepoHit(
                                full_name=d.get("full_name", full_name),
                                html_url=d.get("html_url", ""),
                                description=(d.get("description") or "").strip(),
                                language=d.get("language"),
                                topics=list(d.get("topics") or []),
                                stars=int(d.get("stargazers_count") or 0),
                                forks=int(d.get("forks_count") or 0),
                                pushed_at=(d.get("pushed_at") or "")[:10],
                                created_at=(d.get("created_at") or "")[:10],
                            ))
                    except httpx.HTTPError:
                        continue
            except Exception as e:
                errors.append({"backend": "code", "error": repr(e)})

        # --- README enrichment for the top candidates ---
        if repos:
            # Sort by stars first so we enrich likely-relevant ones (BM25 will
            # re-rank after). Cheap hint, not the final order.
            repos.sort(key=lambda r: r.stars, reverse=True)
            for r in repos[:fetch_readme_for]:
                r.readme_excerpt = fetch_readme_excerpt(r.full_name, client=client)

    ranked = score_repos(repos, query, code_hits=code)
    return SearchReport(
        query=query, language=language, repos=ranked,
        used=used, errors=errors,
    )
