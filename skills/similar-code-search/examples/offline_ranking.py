"""Offline: rank a synthetic repo batch, assert the likely-relevant repo wins.

No network. Exercises scoring.score_repos against a hand-built pool.
"""
from __future__ import annotations

import sys

from similar_code_search.models import CodeHit, RepoHit
from similar_code_search.scoring import score_repos


def main() -> int:
    batch = [
        RepoHit(
            full_name="acme/repo-audit",
            html_url="https://github.com/acme/repo-audit",
            description="LLM agent for repository-level code auditing. "
                        "Performs data-flow analysis with LLM-guided exploration.",
            language="Python",
            topics=["llm", "code-audit", "security"],
            stars=1200,
            forks=80,
            pushed_at="2026-03-10",
            created_at="2024-09-01",
            readme_excerpt="RepoAudit is an autonomous LLM agent for "
                           "repository-level code auditing. It explores "
                           "the codebase on demand by analyzing data-flow facts.",
        ),
        RepoHit(
            full_name="old/pdf-merger",
            html_url="https://github.com/old/pdf-merger",
            description="Merge PDF files in Python. Unrelated to auditing.",
            language="Python",
            topics=["pdf"],
            stars=5,
            forks=0,
            pushed_at="2019-02-03",
            created_at="2018-12-01",
            readme_excerpt="A tiny PDF merger, zero deps.",
        ),
        RepoHit(
            full_name="big/security-scanner",
            html_url="https://github.com/big/security-scanner",
            description="Static analysis security scanner (no LLM).",
            language="Go",
            topics=["security", "static-analysis"],
            stars=30000,
            forks=2100,
            pushed_at="2026-01-20",
            created_at="2018-05-10",
            readme_excerpt="Fast Go-based security scanner; uses data-flow "
                           "but no LLM agents.",
        ),
        RepoHit(
            full_name="forky/repo-audit-fork",
            html_url="https://github.com/forky/repo-audit-fork",
            description="Fork of acme/repo-audit with minor patches.",
            language="Python",
            topics=["llm", "code-audit"],
            stars=3,
            forks=0,
            pushed_at="2025-08-01",
            created_at="2025-07-30",
            readme_excerpt="Fork of RepoAudit.",
        ),
    ]
    code_hits = [
        CodeHit(repo_full_name="acme/repo-audit",
                path="src/auditor.py", html_url="", sha=""),
    ]

    ranked = score_repos(batch, "LLM agent for repository-level code auditing",
                         code_hits=code_hits)

    print(f"{'rank':<5}{'score':<8}{'text':<7}{'pop':<7}{'rec':<7}{'cm':<5}repo")
    for i, r in enumerate(ranked, 1):
        c = r.score_components
        print(f"{i:<5}{r.score:<8.3f}"
              f"{c['text']:<7.2f}{c['popularity']:<7.2f}"
              f"{c['recency']:<7.2f}{c['code_match']:<5.1f}"
              f"{r.full_name}")

    top = ranked[0]
    assert top.full_name == "acme/repo-audit", (
        f"expected acme/repo-audit at top, got {top.full_name}"
    )
    # big/security-scanner has more stars but should lose on text score
    names = [r.full_name for r in ranked]
    assert names.index("acme/repo-audit") < names.index("big/security-scanner"), names
    # pdf-merger should be last (wrong domain + stale + low stars)
    assert names[-1] == "old/pdf-merger", names

    print("\n✓ ranking behaves as expected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
