---
name: skill-finder
description: Discover, install, and organize Claude Code skills. Search GitHub for skill-collection repos, vendor them as git submodules under `skill-repos/`, and expose individual skills into `.claude/skills/` via relative symlinks. Use when the user asks to "find a skill for X", "install a skill", "add the pdf skill", "wire up vercel-labs/agent-skills", "what skills do we have", or otherwise wants to extend Claude Code's capabilities — even if they don't say "skill-finder" by name. Also use when the user has already cloned a repo full of skills and needs them surfaced at the right path.
license: MIT
allowed-tools: Bash(uv run *) Bash(date *) Bash(echo *) Bash(printenv *) Bash(pwd) Bash(ls *) Bash(git *) Read
metadata:
  version: "0.1.0"
---

# skill-finder

## Runtime context

- Current working directory: !`pwd`
- Workspace appears to have `.claude/skills/`: !`test -d .claude/skills && echo yes || echo no`
- Workspace appears to have `skill-repos/`: !`test -d skill-repos && echo yes || echo no`
- `GITHUB_TOKEN` set: !`printenv GITHUB_TOKEN >/dev/null && echo y || echo n` (unset = 10 req/min search limit)

## Why this skill exists (layout, not marketing)

Many upstream skill repos publish **multiple** skills under a `skills/`
subdirectory (e.g. `anthropics/skills`, `vercel-labs/agent-skills`). Cloning
such a repo as a git submodule into `.claude/skills/<repo>` would nest the
skills one level too deep — Claude Code's loader expects
`.claude/skills/<skill-name>/SKILL.md`, not
`.claude/skills/<repo>/skills/<skill-name>/SKILL.md`.

Layout this skill maintains:

```
workspace/
├── skill-repos/                            # git submodules (upstream repos, verbatim)
│   ├── claude-skills/                      # e.g. anthropics/skills
│   │   └── skills/pdf/SKILL.md
│   └── our-skills/
│       └── skills/paper-search/SKILL.md
└── .claude/
    └── skills/                             # symlinks Claude Code actually reads
        ├── pdf -> ../../skill-repos/claude-skills/skills/pdf
        └── paper-search -> ../../skill-repos/our-skills/skills/paper-search
```

Symlinks are **relative**, so the tree moves with the workspace.

## Variables used in this file

- `${WORKSPACE}` — the workspace root (the directory that will contain
  `skill-repos/` and `.claude/skills/`). Default: auto-detected by walking
  up from cwd looking for `.claude/`, `skill-repos/`, or a `.git` marker.
  **Always pass `--workspace "${WORKSPACE}"` explicitly** when the user
  might be invoking from a subdirectory.
- `${REPO}` — GitHub shorthand (`owner/name`) or a full git URL.
- `${SKILL}` — an individual skill name (`pdf`, `paper-search`). Disambiguate
  across repos with `<repo>/<skill>` (e.g. `claude-skills/pdf`).

## Procedure

Pick the branch that matches the user's intent. Only one branch applies per
turn.

### Branch A — user wants a skill but doesn't know which repo

1. `skill-finder search "<keywords>" --json` — get candidate repos by stars.
2. Present the top 3–5 to the user with name, stars, description. **Do not
   install without confirmation** — some repos have hundreds of skills.
3. When the user picks one, proceed to Branch B.

### Branch B — user names a repo to install

Run:
```bash
uv run skill-finder --workspace "${WORKSPACE}" add "${REPO}" --json
```

This: clones (or submodules, if the workspace is a git repo) the repo under
`${WORKSPACE}/skill-repos/<slug>/`, discovers every `SKILL.md` inside, and
creates relative symlinks in `.claude/skills/` for each one.

- Add `--link-prefix vendor-` if the user wants to avoid name collisions
  with existing skills.
- Add `--no-link` if the user asked to vendor the repo but not surface its
  skills yet (rare; default is to link).
- Add `--name <dirname>` if multiple repos resolve to the same slug.

Report back: the repo directory, each skill name + description, and the
symlink paths created. Tell the user to restart / re-load Claude Code for
the new skills to register.

### Branch C — user names a specific skill already vendored

```bash
uv run skill-finder --workspace "${WORKSPACE}" link "${SKILL}" --json
```

Use `<repo>/<skill>` when the name alone is ambiguous. Pass `--as-name
<alt>` to rename on link.

### Branch D — user asks what's installed / available

```bash
uv run skill-finder --workspace "${WORKSPACE}" list --json
```

Parse the `repos` array and the `linked` map. In the summary, mark each
skill as **linked** (`●`) or **unlinked** (`○`), grouped by repo.

### Branch E — user wants to remove a skill

- Remove one repo (and all its symlinks):
  ```bash
  uv run skill-finder --workspace "${WORKSPACE}" remove <repo-dirname>
  ```
- Remove just one symlink: delete the file directly with `rm
  .claude/skills/<name>` (it's a symlink; the underlying repo stays).

### Branch F — something looks broken

```bash
uv run skill-finder --workspace "${WORKSPACE}" doctor --json
```

Lists broken symlinks, symlinks pointing at targets without a `SKILL.md`,
and cloned repos with zero skills. Exit code `1` if problems exist.

## Trigger → branch table

| User says / asks                                                      | Branch |
|-----------------------------------------------------------------------|--------|
| "Find a skill for X", "is there a skill that does Y"                  | A → B  |
| "Install `<owner/repo>`", "add the anthropics skills"                 | B      |
| "Add just the `pdf` skill" (repo already vendored)                    | C      |
| "What skills do I have installed?", "list my skills"                  | D      |
| "Uninstall `<repo>`", "remove `<skill>`"                              | E      |
| "My skills are broken", a symlink is red in the editor                | F      |
| User types a GitHub URL or shorthand without context                  | B      |

## Output schema (`--json`)

`search`:
```json
{"query": "...", "repos": [{"full_name": "...", "stars": 1234, "description": "...",
                            "clone_url": "...", "html_url": "...",
                            "updated_at": "YYYY-MM-DD", "default_branch": "main"}]}
```

`add`:
```json
{"repo_dir": "skill-repos/<slug>", "mode": "submodule|clone",
 "skills": [{"name": "...", "skill_dir": "skill-repos/<slug>/skills/<name>"}]}
```

`list`:
```json
{"repos": [{"repo": "<slug>", "skills": [{"name": "...",
                                         "skill_dir": "...",
                                         "description": "..."}]}],
 "linked": {"<skill>": "<relative-symlink-target>"}}
```

`doctor`:
```json
{"workspace": "/abs/path", "problems": ["broken symlink: ...", "..."]}
```

## Never-do rules

- Never `rm -rf` inside `skill-repos/`. Use `skill-finder remove <repo>` so
  the matching submodule / symlinks go too.
- Never create an **absolute** symlink. The CLI uses relative ones; don't
  hand-edit `.claude/skills/` with `ln -s /abs/path …`.
- Never overwrite an existing **real directory** at a link path. The CLI
  refuses by default; only pass `--force` if the user explicitly confirmed.
- Never install a repo with fewer than ~5 stars unless the user named it
  explicitly. (The search defaults filter with `--min-stars 5`.)
- Never skip the restart/reload hint — Claude Code doesn't re-scan
  `.claude/skills/` mid-session.

## Gotchas

- **Claude Code needs a reload.** After `add` or `link`, the new skills
  won't appear until the user restarts Claude Code (or invokes whatever
  reload command their version provides).
- **Workspace must be a git repo for `submodule` mode.** If it isn't, the
  CLI falls back to `git clone --depth 1`. Tell the user when this happens
  — they'll want `git init` first if they care about pinning versions.
- **Symlinks on Windows** require Developer Mode or admin. On WSL they
  work fine inside the WSL filesystem but not across the `\\wsl$` mount.
- **Name collisions** across repos resolve to whichever the linker sees
  first unless you pass `--link-prefix` or `--as-name`.
- **Discovery walks up to 5 directories deep** and skips `node_modules`,
  `.venv`, `dist`, etc. If an upstream repo buries skills deeper, run
  `skill-finder doctor` to spot the silent miss.

## On-demand references

- `references/layout.md` — full directory-layout spec + rationale. **Read
  when** the user asks *why* submodules + symlinks instead of plain
  submodules.
- `references/faq.md` — upgrade/pinning, multi-workspace, CI checkout.
  **Read when** the user asks about updating a vendored repo, using the
  same `skill-repos/` across multiple projects, or CI concerns.
