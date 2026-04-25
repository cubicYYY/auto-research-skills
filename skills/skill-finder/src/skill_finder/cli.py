from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from skill_finder.discover import discover
from skill_finder.github import resolve_spec, search_skill_repos
from skill_finder.layout import Workspace, find_workspace
from skill_finder.symlink import create_link, plan_link, remove_link
from skill_finder.vcs import (
    add_submodule,
    is_workspace_git_repo,
    plain_clone,
    remove_submodule,
    repo_slug_from_url,
)


def _emit(args, payload: dict) -> None:
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_search(args: argparse.Namespace) -> int:
    try:
        hits = search_skill_repos(args.query, limit=args.limit, min_stars=args.min_stars)
    except Exception as e:
        print(f"error: GitHub search failed: {e}", file=sys.stderr)
        return 3
    if args.json:
        _emit(args, {
            "query": args.query,
            "repos": [
                {"full_name": h.full_name, "stars": h.stars, "description": h.description,
                 "clone_url": h.clone_url, "html_url": h.html_url,
                 "updated_at": h.updated_at, "default_branch": h.default_branch}
                for h in hits
            ],
        })
        return 0
    if not hits:
        print("No repos matched. Try different keywords or lower --min-stars.")
        return 0
    print(f"Found {len(hits)} skill-repo candidates for {args.query!r}:\n")
    for h in hits:
        print(f"  ★ {h.stars:>5}  {h.full_name}")
        if h.description:
            print(f"          {h.description}")
        print(f"          {h.html_url}")
    print("\nNext: `skill-finder add <owner/repo>` to submodule one of these.")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    ws = _resolve_ws(args)
    ws.ensure_dirs()

    try:
        clone_url = resolve_spec(args.repo)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    dest_name = args.name or repo_slug_from_url(clone_url)
    dest_rel = Path("skill-repos") / dest_name
    dest_abs = ws.root / dest_rel

    if dest_abs.exists():
        print(f"error: {dest_rel} already exists. Use `--name` to rename, "
              f"or `skill-finder remove {dest_name}` first.", file=sys.stderr)
        return 2

    try:
        if is_workspace_git_repo(ws.root):
            add_submodule(ws.root, clone_url, dest_rel)
            mode = "submodule"
        else:
            plain_clone(clone_url, dest_abs)
            mode = "clone"
    except Exception as e:
        print(f"error: git failed: {e}", file=sys.stderr)
        return 3

    skills = discover(dest_abs)
    print(f"Added {clone_url} as {mode} at {dest_rel}")
    print(f"Discovered {len(skills)} skill(s):")
    for s in skills:
        print(f"  - {s.name}  ({s.skill_dir.relative_to(ws.root)})")

    if args.link:
        linked = []
        for s in skills:
            link_name = args.link_prefix + s.name if args.link_prefix else s.name
            plan = plan_link(ws.root, link_name, s.skill_dir, ws.skills_dir)
            if plan.conflict_reason and not args.force:
                print(f"  ! skip {link_name}: {plan.conflict_reason}")
                continue
            create_link(plan, force=args.force)
            linked.append((link_name, s.skill_dir))
        if linked:
            print(f"Linked {len(linked)} skill(s) into {ws.skills_dir.relative_to(ws.root)}:")
            for name, tgt in linked:
                print(f"  - {name} -> {tgt.relative_to(ws.root)}")

    if args.json:
        _emit(args, {
            "repo_dir": str(dest_rel),
            "mode": mode,
            "skills": [{"name": s.name, "skill_dir": str(s.skill_dir.relative_to(ws.root))}
                       for s in skills],
        })
    return 0


def cmd_link(args: argparse.Namespace) -> int:
    ws = _resolve_ws(args)
    ws.ensure_dirs()

    target = _locate_skill(ws, args.skill)
    if target is None:
        print(f"error: no skill named {args.skill!r} found under skill-repos/. "
              f"Run `skill-finder list` to see what's available.", file=sys.stderr)
        return 2

    link_name = args.as_name or target.name
    plan = plan_link(ws.root, link_name, target.skill_dir, ws.skills_dir)
    if plan.conflict_reason and not args.force:
        print(f"error: {plan.conflict_reason}. Pass --force to overwrite.", file=sys.stderr)
        return 2
    create_link(plan, force=args.force)
    print(f"Linked {plan.link.relative_to(ws.root)} -> {plan.target.relative_to(ws.root)}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    ws = _resolve_ws(args)
    if not ws.repos_dir.exists():
        print("No skill-repos/ yet. `skill-finder add <repo>` to start.")
        return 0

    repos: list[dict] = []
    for repo_dir in sorted(ws.repos_dir.iterdir()):
        if not repo_dir.is_dir():
            continue
        skills = discover(repo_dir)
        repos.append({
            "repo": repo_dir.name,
            "skills": [{"name": s.name, "skill_dir": str(s.skill_dir.relative_to(ws.root)),
                        "description": s.description} for s in skills],
        })

    linked: dict[str, str] = {}
    if ws.skills_dir.exists():
        for entry in sorted(ws.skills_dir.iterdir()):
            if entry.is_symlink():
                linked[entry.name] = os.readlink(entry)

    if args.json:
        _emit(args, {"repos": repos, "linked": linked})
        return 0

    if not repos:
        print("No skill-repos/ directories yet.")
    for r in repos:
        print(f"{r['repo']}:")
        for s in r["skills"]:
            mark = "●" if s["name"] in linked else "○"
            print(f"  {mark} {s['name']}")
            if s["description"]:
                desc = s["description"]
                print(f"      {desc[:110] + ('…' if len(desc) > 110 else '')}")
    if linked:
        print(f"\nLinked into {ws.skills_dir.relative_to(ws.root)}:")
        for name, tgt in linked.items():
            print(f"  - {name} -> {tgt}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    ws = _resolve_ws(args)
    repo_dir = ws.repos_dir / args.repo
    if not repo_dir.exists():
        print(f"error: {args.repo} not found under skill-repos/", file=sys.stderr)
        return 2

    # Remove any symlinks that currently point into this repo.
    removed_links: list[str] = []
    if ws.skills_dir.exists():
        for entry in ws.skills_dir.iterdir():
            if not entry.is_symlink():
                continue
            try:
                resolved = (ws.skills_dir / os.readlink(entry)).resolve()
            except OSError:
                continue
            if str(resolved).startswith(str(repo_dir.resolve())):
                if remove_link(entry):
                    removed_links.append(entry.name)

    try:
        remove_submodule(ws.root, Path("skill-repos") / args.repo)
    except Exception as e:
        print(f"warning: git removal failed: {e}", file=sys.stderr)

    print(f"Removed {args.repo}" + (f" and {len(removed_links)} link(s)" if removed_links else ""))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    ws = _resolve_ws(args)
    ws.ensure_dirs()
    problems: list[str] = []

    if ws.skills_dir.exists():
        for entry in ws.skills_dir.iterdir():
            if entry.is_symlink():
                target = (ws.skills_dir / os.readlink(entry)).resolve()
                if not target.exists():
                    problems.append(f"broken symlink: {entry.relative_to(ws.root)} -> "
                                    f"{os.readlink(entry)}")
                elif not (target / "SKILL.md").exists():
                    problems.append(f"symlink target has no SKILL.md: "
                                    f"{entry.relative_to(ws.root)}")

    if ws.repos_dir.exists():
        for repo in ws.repos_dir.iterdir():
            if not repo.is_dir():
                continue
            if not discover(repo):
                problems.append(f"no SKILL.md found in {repo.relative_to(ws.root)}")

    if args.json:
        _emit(args, {"workspace": str(ws.root), "problems": problems})
        return 0 if not problems else 1

    if not problems:
        print(f"OK — workspace {ws.root} is healthy.")
        return 0
    print(f"{len(problems)} problem(s) in {ws.root}:")
    for p in problems:
        print(f"  - {p}")
    return 1


def _resolve_ws(args: argparse.Namespace) -> Workspace:
    if args.workspace:
        return Workspace(Path(args.workspace).resolve())
    return find_workspace()


def _locate_skill(ws: Workspace, name: str):
    """Find a DiscoveredSkill by name across all cloned repos. Also accepts
    `<repo>/<name>` to disambiguate when multiple repos publish the same name."""
    if "/" in name:
        repo, _, sk = name.partition("/")
        repos = [ws.repos_dir / repo]
    else:
        sk = name
        repos = sorted(ws.repos_dir.iterdir()) if ws.repos_dir.exists() else []

    for repo in repos:
        if not repo.exists() or not repo.is_dir():
            continue
        for s in discover(repo):
            if s.name == sk:
                return s
    return None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="skill-finder",
        description="Discover Claude Code skill repos, add as submodules, and "
                    "symlink individual skills into .claude/skills/.",
    )
    p.add_argument("--workspace", default=None,
                   help="Absolute path to the workspace root. Default: auto-detected.")
    p.add_argument("--json", action="store_true",
                   help="Emit machine-readable JSON for parsing.")

    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="Search GitHub for skill-collection repos.")
    s.add_argument("query", help="Keywords (e.g. 'pdf', 'react testing').")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--min-stars", type=int, default=5)
    s.set_defaults(func=cmd_search)

    a = sub.add_parser("add", help="Add a skill repo as a git submodule (or plain clone) "
                                   "under skill-repos/, then optionally link its skills.")
    a.add_argument("repo", help="`owner/name` or full git URL.")
    a.add_argument("--name", default=None,
                   help="Override the directory name under skill-repos/.")
    a.add_argument("--link", action="store_true", default=True,
                   help="Also create .claude/skills/<skill> symlinks for every "
                        "SKILL.md found (default).")
    a.add_argument("--no-link", dest="link", action="store_false",
                   help="Skip symlink creation — just vendor the repo.")
    a.add_argument("--link-prefix", default="",
                   help="Prefix added to each linked skill name (e.g. 'vendor-').")
    a.add_argument("--force", action="store_true",
                   help="Overwrite existing symlinks/files at the link path.")
    a.set_defaults(func=cmd_add)

    l = sub.add_parser("link", help="Create a .claude/skills/<name> symlink for "
                                    "an already-cloned skill.")
    l.add_argument("skill", help="Skill name (optionally `repo/name` to disambiguate).")
    l.add_argument("--as-name", default=None,
                   help="Use this as the link name instead of the skill's own name.")
    l.add_argument("--force", action="store_true",
                   help="Overwrite if something exists at the link path.")
    l.set_defaults(func=cmd_link)

    ls = sub.add_parser("list", help="List all repos under skill-repos/ and their skills.")
    ls.set_defaults(func=cmd_list)

    rm = sub.add_parser("remove", help="Remove a skill repo (and any symlinks into it).")
    rm.add_argument("repo", help="The directory name under skill-repos/.")
    rm.set_defaults(func=cmd_remove)

    dr = sub.add_parser("doctor", help="Check for broken symlinks and empty repos.")
    dr.set_defaults(func=cmd_doctor)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
