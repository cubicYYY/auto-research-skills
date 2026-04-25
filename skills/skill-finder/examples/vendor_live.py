"""Live example: vendor a small upstream skill repo into a temp workspace.

Requires network. Uses the system `git` for cloning.

We pick a target programmatically via `skill-finder search` so this example
stays useful even as the skill ecosystem shifts.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from skill_finder.discover import discover
from skill_finder.github import search_skill_repos
from skill_finder.layout import Workspace
from skill_finder.vcs import plain_clone, repo_slug_from_url


def main() -> int:
    # Search for something small and well-known.
    hits = search_skill_repos("find skills", limit=5, min_stars=5)
    print(f"Top candidates:")
    for h in hits:
        print(f"  ★ {h.stars:>5}  {h.full_name}  {h.description}")
    if not hits:
        print("No hits — network/API issue.")
        return 1

    pick = hits[0]
    print(f"\nVendoring {pick.full_name} ...")

    tmp = Path(tempfile.mkdtemp(prefix="skill-finder-live-"))
    try:
        ws = Workspace(tmp)
        ws.ensure_dirs()
        slug = repo_slug_from_url(pick.clone_url)
        dest = ws.repos_dir / slug
        plain_clone(pick.clone_url, dest)

        skills = discover(dest)
        print(f"Discovered {len(skills)} skill(s) in {slug}:")
        for s in skills:
            print(f"  - {s.name}")
            if s.description:
                print(f"      {s.description[:100]}")

        if not skills:
            print("\nRepo had no SKILL.md files at any depth ≤ 5 — pick another.")
            return 1
        print(f"\nWorkspace: {tmp} (cleaned up on exit)")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
