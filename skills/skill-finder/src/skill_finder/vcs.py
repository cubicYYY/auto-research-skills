"""Thin wrappers over `git submodule` / `git clone` / plain-clone."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def repo_slug_from_url(clone_url: str) -> str:
    """`https://github.com/owner/name.git` → `name`. Used as the directory
    name under `skill-repos/` unless the caller overrides it."""
    u = urlparse(clone_url)
    last = u.path.rsplit("/", 1)[-1]
    return re.sub(r"\.git$", "", last) or "repo"


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def add_submodule(
    workspace_root: Path, clone_url: str, dest_relpath: Path
) -> None:
    """`git submodule add <url> <dest>`. `dest_relpath` must be relative to
    `workspace_root`."""
    dest_relpath = Path(dest_relpath)
    if dest_relpath.is_absolute():
        raise ValueError("dest_relpath must be relative to workspace_root")
    _run(["git", "submodule", "add", clone_url, str(dest_relpath)], cwd=workspace_root)
    _run(["git", "submodule", "update", "--init", "--recursive", str(dest_relpath)], cwd=workspace_root)


def plain_clone(clone_url: str, dest_abspath: Path) -> None:
    """Fallback when the workspace isn't a git repo yet — we can still clone
    the upstream into `skill-repos/` without `git submodule add`."""
    dest_abspath.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--depth", "1", clone_url, str(dest_abspath)],
                   check=True, capture_output=True, text=True)


def remove_submodule(workspace_root: Path, dest_relpath: Path) -> None:
    """Best-effort submodule removal. No-op if the path is not a submodule."""
    dest_relpath = Path(dest_relpath)
    abspath = (workspace_root / dest_relpath).resolve()
    # If it's a real submodule, `git submodule deinit -f` + `git rm -f`.
    try:
        _run(["git", "submodule", "deinit", "-f", str(dest_relpath)], cwd=workspace_root)
    except subprocess.CalledProcessError:
        pass
    try:
        _run(["git", "rm", "-f", str(dest_relpath)], cwd=workspace_root)
    except subprocess.CalledProcessError:
        # Fall back to plain rmtree — workspace may not be a git repo.
        if abspath.exists():
            _rmtree(abspath)


def _rmtree(p: Path) -> None:
    import shutil
    shutil.rmtree(p, ignore_errors=True)


def is_workspace_git_repo(workspace_root: Path) -> bool:
    return (workspace_root / ".git").exists()
