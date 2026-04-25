from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class RepoHit:
    """A GitHub repository candidate."""
    full_name: str
    html_url: str
    description: str
    language: str | None
    topics: list[str] = field(default_factory=list)
    stars: int = 0
    forks: int = 0
    pushed_at: str = ""            # ISO date (YYYY-MM-DD)
    created_at: str = ""
    readme_excerpt: str | None = None   # populated lazily when we fetch READMEs
    matched_files: list[str] = field(default_factory=list)  # from code search
    score: float | None = None
    score_components: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CodeHit:
    """A single file-level match from GitHub code search."""
    repo_full_name: str
    path: str
    html_url: str
    sha: str


@dataclass
class SearchReport:
    query: str
    language: str | None
    repos: list[RepoHit]
    used: list[str]                # which search backends were hit
    errors: list[dict[str, str]]   # per-backend errors
