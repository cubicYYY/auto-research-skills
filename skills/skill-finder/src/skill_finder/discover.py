"""Discover skills inside a cloned repo.

A skill is any directory containing a `SKILL.md`. Upstream conventions vary:

- Single-skill repo:  <root>/SKILL.md
- Monorepo:           <root>/skills/<name>/SKILL.md
- Nested monorepo:    <root>/<any>/<name>/SKILL.md (rare; we still support it)

We discover by walking for `SKILL.md` files, but cap depth to avoid
descending into `node_modules`, build artifacts, etc.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SKILL_FILENAME = "SKILL.md"
MAX_DEPTH = 5
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    "dist", "build", ".tox", ".pytest_cache", "target",
}

_NAME_RE = re.compile(r"^\s*name\s*:\s*(.+?)\s*$", re.MULTILINE)
_DESC_RE = re.compile(r"^\s*description\s*:\s*(.+?)\s*$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


@dataclass
class DiscoveredSkill:
    """A skill found inside a cloned repo."""
    name: str
    description: str
    skill_md: Path

    @property
    def skill_dir(self) -> Path:
        return self.skill_md.parent


def _iter_skill_mds(root: Path) -> Iterable[Path]:
    root = root.resolve()
    stack = [(root, 0)]
    while stack:
        d, depth = stack.pop()
        if depth > MAX_DEPTH:
            continue
        try:
            entries = list(d.iterdir())
        except (PermissionError, FileNotFoundError):
            continue
        for entry in entries:
            if entry.is_symlink() and entry.is_dir():
                # Don't recurse into symlinks — avoid cycles into the same repo
                continue
            if entry.is_dir():
                if entry.name in SKIP_DIRS or entry.name.startswith("."):
                    continue
                stack.append((entry, depth + 1))
            elif entry.is_file() and entry.name == SKILL_FILENAME:
                yield entry


def _parse_frontmatter(text: str) -> tuple[str | None, str | None]:
    m = _FRONTMATTER_RE.match(text)
    body = m.group(1) if m else text[:2000]
    name_m = _NAME_RE.search(body)
    desc_m = _DESC_RE.search(body)
    name = name_m.group(1).strip().strip('"').strip("'") if name_m else None
    desc = desc_m.group(1).strip().strip('"').strip("'") if desc_m else None
    return name, desc


def discover(root: Path) -> list[DiscoveredSkill]:
    """Return every `SKILL.md` under `root` with a parseable name."""
    out: list[DiscoveredSkill] = []
    for sm in _iter_skill_mds(root):
        try:
            text = sm.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        name, desc = _parse_frontmatter(text)
        if not name:
            # Fall back to parent-dir name as a last resort.
            name = sm.parent.name
        out.append(DiscoveredSkill(
            name=name,
            description=(desc or "").strip(),
            skill_md=sm,
        ))
    # Dedupe: same name + same skill_dir → keep first.
    seen: set[tuple[str, Path]] = set()
    uniq: list[DiscoveredSkill] = []
    for s in out:
        key = (s.name, s.skill_dir)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(s)
    uniq.sort(key=lambda s: (s.name.lower(), str(s.skill_dir)))
    return uniq
