"""Live: issue a real GitHub search and print the top-5.

Requires network. Much better recall with GITHUB_TOKEN set.
"""
from __future__ import annotations

import os
import sys

from similar_code_search.core import run


QUERY = "LLM agent for repository-level code auditing"


def main() -> int:
    if not os.environ.get("GITHUB_TOKEN"):
        print("warning: GITHUB_TOKEN unset — expect thin results.", file=sys.stderr)

    report = run(QUERY, language="python", min_stars=5, per_search=25,
                 fetch_readme_for=8)

    print(f"Query: {QUERY!r}")
    print(f"Backends used: {', '.join(report.used) or '(none)'}")
    print(f"Total candidates: {len(report.repos)}")
    print()
    for i, r in enumerate(report.repos[:5], 1):
        sc = f"{r.score:.2f}" if r.score is not None else "—"
        c = r.score_components
        comp_s = f"(text={c['text']:.2f} pop={c['popularity']:.2f} "
        comp_s += f"rec={c['recency']:.2f} cm={c['code_match']:.1f})"
        print(f" {i}. [{sc}] {r.full_name} ★ {r.stars:,}  {comp_s}")
        if r.description:
            print(f"    {r.description}")
        print(f"    {r.html_url}")

    if report.errors:
        print("\nErrors:")
        for e in report.errors:
            print(f"  - {e['backend']}: {e['error']}")

    return 0 if report.repos else 1


if __name__ == "__main__":
    sys.exit(main())
