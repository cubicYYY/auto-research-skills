"""Manage the symlink farm at `.claude/skills/<name>`."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LinkPlan:
    link: Path            # .claude/skills/<name>
    target: Path          # skill-repos/<repo>/skills/<name>
    exists: bool
    conflict_reason: str | None  # non-None → can't overwrite safely


def plan_link(
    workspace_root: Path,
    link_name: str,
    target_abs: Path,
    skills_dir: Path,
) -> LinkPlan:
    link = skills_dir / link_name
    exists = link.exists() or link.is_symlink()
    reason: str | None = None
    if exists:
        if link.is_symlink():
            try:
                current = (skills_dir / os.readlink(link)).resolve()
            except OSError:
                current = link.resolve()
            if current == target_abs.resolve():
                reason = None  # already correct; OK to overwrite (no-op)
            else:
                reason = f"symlink exists and points elsewhere: {os.readlink(link)!r}"
        elif link.is_dir():
            reason = "a real directory exists at this path (not a symlink)"
        else:
            reason = "a file exists at this path"
    return LinkPlan(link=link, target=target_abs, exists=exists, conflict_reason=reason)


def create_link(plan: LinkPlan, *, force: bool = False) -> None:
    """Create a **relative** symlink from `plan.link` → `plan.target`.

    Relative is important: the symlink must keep pointing at the right place
    when the whole workspace is moved (e.g. checked out on another machine
    or into a different parent path).
    """
    if plan.conflict_reason and not force:
        raise FileExistsError(plan.conflict_reason)
    if plan.exists:
        # already-exists case: either identical (no-op) or force-overwrite
        try:
            plan.link.unlink()
        except IsADirectoryError:
            import shutil
            shutil.rmtree(plan.link)
    plan.link.parent.mkdir(parents=True, exist_ok=True)
    rel = os.path.relpath(plan.target, start=plan.link.parent)
    os.symlink(rel, plan.link)


def remove_link(link_path: Path) -> bool:
    """Remove only if it's actually a symlink. Refuse to delete real dirs/files."""
    if not link_path.is_symlink():
        return False
    link_path.unlink()
    return True
