"""Score candidate repos for similarity to the user's query.

Design:

    score(repo) = 0.55 · text  +  0.25 · popularity  +  0.10 · recency
                + 0.10 · code_match

- `text` is BM25 over tokenized `name + description + topics + readme_excerpt`,
  squashed through a sigmoid (absolute, batch-independent — matches the
  paper-search ranker).
- `popularity` is `log1p(stars) / log1p(batch_max_stars)`, with 0 star-repos
  scoring 0 (low signal).
- `recency` is a Gaussian around "now" on `pushed_at`, σ = 2 years.
- `code_match` is a 0/1 indicator bumped by the presence of code-search hits
  in this repo (proxy for a file-level name/term match).

Returns the same list with `score` and `score_components` populated, sorted
desc by score.
"""
from __future__ import annotations

import datetime as _dt
import math
import re
from typing import Iterable

from rank_bm25 import BM25Okapi

from similar_code_search.models import CodeHit, RepoHit

TEXT_WEIGHT = 0.55
POP_WEIGHT = 0.25
RECENCY_WEIGHT = 0.10
CODE_WEIGHT = 0.10
BM25_PIVOT = 6.0
BM25_SCALE = 0.5
RECENCY_SIGMA_YEARS = 2.0


def _tokenize(s: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if t]


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _years_since(iso_date: str) -> float | None:
    try:
        d = _dt.date.fromisoformat(iso_date)
    except (TypeError, ValueError):
        return None
    today = _dt.date.today()
    return (today - d).days / 365.25


def _repo_text(r: RepoHit) -> str:
    parts = [r.full_name.replace("/", " "), r.description or "", " ".join(r.topics)]
    if r.readme_excerpt:
        parts.append(r.readme_excerpt)
    return " ".join(parts)


def score_repos(
    repos: list[RepoHit], query: str, code_hits: Iterable[CodeHit] = ()
) -> list[RepoHit]:
    if not repos:
        return repos

    corpus = [_tokenize(_repo_text(r)) for r in repos]
    q_tokens = _tokenize(query)
    try:
        bm25 = BM25Okapi(corpus)
        raw_bm25 = bm25.get_scores(q_tokens) if q_tokens else [0.0] * len(repos)
    except Exception:
        raw_bm25 = [0.0] * len(repos)

    max_stars = max((r.stars for r in repos), default=0)
    log_max = math.log1p(max_stars) if max_stars > 0 else 0.0

    code_hit_repos = {ch.repo_full_name for ch in code_hits}

    # Aggregate per-repo matched files from code search for explainability.
    per_repo_files: dict[str, list[str]] = {}
    for ch in code_hits:
        per_repo_files.setdefault(ch.repo_full_name, []).append(ch.path)

    for repo, raw in zip(repos, raw_bm25):
        text = _sigmoid(BM25_SCALE * (float(raw) - BM25_PIVOT))

        if log_max > 0 and repo.stars > 0:
            popularity = math.log1p(repo.stars) / log_max
        else:
            popularity = 0.0

        years = _years_since(repo.pushed_at)
        if years is None:
            recency = 0.5
        else:
            recency = math.exp(-(years * years) / (2.0 * RECENCY_SIGMA_YEARS * RECENCY_SIGMA_YEARS))

        code_match = 1.0 if repo.full_name in code_hit_repos else 0.0

        repo.score = (
            TEXT_WEIGHT * text
            + POP_WEIGHT * popularity
            + RECENCY_WEIGHT * recency
            + CODE_WEIGHT * code_match
        )
        repo.score_components = {
            "text": round(text, 4),
            "popularity": round(popularity, 4),
            "recency": round(recency, 4),
            "code_match": round(code_match, 4),
        }
        if repo.full_name in per_repo_files:
            # Keep up to 5 example files for the report.
            repo.matched_files = per_repo_files[repo.full_name][:5]

    repos.sort(key=lambda r: (r.score or 0.0, r.stars, r.pushed_at), reverse=True)
    return repos
