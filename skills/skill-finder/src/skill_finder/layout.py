"""Filesystem layout conventions.

A workspace managed by this skill looks like:

    <root>/
    ├── skill-repos/               # git submodules of skill source repos
    │   ├── claude-skills/         # e.g. anthropics/skills
    │   └── our-skills/
    └── .claude/
        └── skills/                # consumer-visible skill tree (symlinks)
            ├── pdf -> ../../skill-repos/claude-skills/skills/pdf
            └── paper-search -> ../../skill-repos/our-skills/skills/paper-search

The `skill-repos/` directory holds the upstream repos verbatim — useful when
one repo publishes *multiple* skills under its own `skills/` subdirectory
(which git submodules alone cannot expose at the right level). Individual
skills are then surfaced into `.claude/skills/` via symlinks so Claude Code's
skill loader sees them at the standard path.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPOS_DIRNAME = "skill-repos"
CLAUDE_SKILLS_DIR = Path(".claude") / "skills"


@dataclass(frozen=True)
class Workspace:
    root: Path

    @property
    def repos_dir(self) -> Path:
        return self.root / REPOS_DIRNAME

    @property
    def skills_dir(self) -> Path:
        return self.root / CLAUDE_SKILLS_DIR

    def ensure_dirs(self) -> None:
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)


def find_workspace(start: Path | None = None) -> Workspace:
    """Walk up from `start` (or cwd) looking for a directory that already
    contains `.claude/`, `skill-repos/`, or a `.git` marker. Falls back to
    cwd. We never silently descend into a parent repo that the user didn't
    ask about.
    """
    cur = (start or Path.cwd()).resolve()
    override = os.environ.get("SKILL_FINDER_ROOT")
    if override:
        return Workspace(Path(override).resolve())

    for cand in [cur, *cur.parents]:
        if (cand / ".claude").exists() or (cand / REPOS_DIRNAME).exists():
            return Workspace(cand)
        if (cand / ".git").exists():
            return Workspace(cand)
    return Workspace(cur)
