"""Offline end-to-end: build a fake vendored layout, link everything, assert.

No network, no git operations — exercises discover + plan_link + create_link
against a synthetic `skill-repos/` tree.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from skill_finder.discover import discover
from skill_finder.layout import Workspace
from skill_finder.symlink import create_link, plan_link


SKILL_MD = """---
name: {name}
description: {desc}
---

# {name}

body
"""


def build_fake_repo(repo_dir: Path, skills: list[tuple[str, str]], *, nested: bool = True) -> None:
    """Create `repo_dir/skills/<name>/SKILL.md` (nested) or `repo_dir/SKILL.md`
    (flat, single-skill)."""
    for name, desc in skills:
        if nested:
            sd = repo_dir / "skills" / name
        else:
            sd = repo_dir
        sd.mkdir(parents=True, exist_ok=True)
        (sd / "SKILL.md").write_text(SKILL_MD.format(name=name, desc=desc))


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="skill-finder-offline-"))
    try:
        ws = Workspace(tmp)
        ws.ensure_dirs()

        # Two fake repos — one monorepo-style, one single-skill
        mono = ws.repos_dir / "claude-skills"
        build_fake_repo(mono, [
            ("pdf", "Extract text from PDF files."),
            ("pptx", "Create PowerPoint decks."),
        ])
        single = ws.repos_dir / "tiny-skill"
        build_fake_repo(single, [("tiny", "Does one small thing.")], nested=False)

        all_skills = []
        for repo in [mono, single]:
            found = discover(repo)
            print(f"{repo.name}: found {len(found)} skill(s)")
            for s in found:
                print(f"  - {s.name}: {s.description}")
                all_skills.append(s)
            print()

        # Link them all
        for s in all_skills:
            plan = plan_link(ws.root, s.name, s.skill_dir, ws.skills_dir)
            create_link(plan, force=True)

        # Verify every symlink points into skill-repos/ relatively
        for s in all_skills:
            link = ws.skills_dir / s.name
            assert link.is_symlink(), link
            target = os.readlink(link)
            assert not os.path.isabs(target), f"absolute target: {target}"
            resolved = (ws.skills_dir / target).resolve()
            assert resolved == s.skill_dir.resolve(), (resolved, s.skill_dir)
            assert (resolved / "SKILL.md").exists(), resolved
            print(f"✓ {link.name} -> {target}")

        print(f"\nAll {len(all_skills)} links created and validated in {tmp}")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
