# skill-finder

A Claude Code [Skill](https://code.claude.com/docs/en/skills) for discovering
and organizing other skills. Search GitHub for skill-collection repos, vendor
them as git submodules (or plain clones), and expose individual skills into
`.claude/skills/` via **relative symlinks**.

## Why symlinks instead of submodules-only

Many upstream skill repos publish **multiple** skills under a `skills/`
subdirectory:

```
anthropics/skills
└── skills/
    ├── pdf/SKILL.md
    ├── pptx/SKILL.md
    └── docx/SKILL.md
```

Claude Code's loader expects `<workspace>/.claude/skills/<skill>/SKILL.md` —
one skill per top-level directory. Submodules alone can't satisfy that: a
submodule of `anthropics/skills` at `.claude/skills/anthropics-skills/`
would nest every skill one level too deep.

`skill-finder` solves this by:

1. Cloning / submoduling the upstream repo **verbatim** under
   `skill-repos/<slug>/`.
2. Discovering every `SKILL.md` inside.
3. Creating one relative symlink per skill at
   `.claude/skills/<skill>` → `../../skill-repos/<slug>/skills/<skill>`.

```
workspace/
├── skill-repos/                                    # managed by skill-finder
│   ├── claude-skills/   (submodule of anthropics/skills)
│   └── our-skills/      (submodule of your monorepo)
└── .claude/
    └── skills/
        ├── pdf          -> ../../skill-repos/claude-skills/skills/pdf
        ├── pptx         -> ../../skill-repos/claude-skills/skills/pptx
        └── paper-search -> ../../skill-repos/our-skills/skills/paper-search
```

The symlinks are relative, so moving / re-cloning the workspace Just Works.

## Requirements

- Python ≥ 3.10, `uv`.
- `git` on `$PATH`.
- *(Optional)* `GITHUB_TOKEN` for higher search-API rate limits.
- **A filesystem that supports symlinks** (native Linux/macOS, or Windows
  with Developer Mode / inside WSL).

## Install

If you installed this repo as a uv workspace, `skill-finder` is already
registered as a console script:

```bash
uv run skill-finder --help
```

Or install it on its own:

```bash
uvx --from git+https://github.com/you/<this-bundle>#subdirectory=skills/skill-finder \
    skill-finder --help
```

## Commands

### `search`

Search GitHub for skill-collection repos.

```bash
skill-finder search "pdf"
skill-finder search "react testing" --limit 20 --min-stars 10
skill-finder search "claude" --json
```

### `add`

Vendor a repo + link all its skills.

```bash
# Auto-detect workspace (walks up for .claude/ or .git)
skill-finder add anthropics/skills

# Explicit workspace, custom dirname, prefix to avoid name collisions
skill-finder --workspace ~/projects/my-app add vercel-labs/agent-skills \
    --name vercel-skills --link-prefix vercel-
```

After running, **restart Claude Code** — it doesn't rescan `.claude/skills/`
mid-session.

### `link`

Create a single symlink for an already-vendored skill.

```bash
skill-finder link pdf
skill-finder link claude-skills/pdf --as-name anthropic-pdf
skill-finder link paper-search --force        # overwrite existing link
```

### `list`

What's installed and linked, per repo.

```bash
skill-finder list
```

Output uses `●` for linked skills, `○` for vendored-but-unlinked.

### `remove`

Remove an entire vendored repo and any symlinks pointing into it.

```bash
skill-finder remove claude-skills
```

To drop just one symlink without removing the repo, `rm
.claude/skills/<name>` is sufficient (it's a symlink; the repo stays).

### `doctor`

Find broken symlinks and empty repos.

```bash
skill-finder doctor
# Exit 0 = healthy, 1 = problems listed on stdout
```

## Flags

| Flag            | Default          | Meaning                                                                 |
|-----------------|------------------|-------------------------------------------------------------------------|
| `--workspace`   | auto-detected    | Absolute path to the workspace root.                                    |
| `--json`        | off              | Machine-readable output for scripting / Claude consumption.             |
| `--name`        | repo slug        | (`add`) Override the directory name under `skill-repos/`.               |
| `--no-link`     | off              | (`add`) Vendor the repo but don't create symlinks.                      |
| `--link-prefix` | `""`             | (`add`) Prefix added to each linked skill (e.g. `vendor-`).             |
| `--as-name`     | skill's own name | (`link`) Use this as the symlink filename.                              |
| `--force`       | off              | (`add`, `link`) Overwrite existing files at the link path.              |

## Workspace detection

Without `--workspace`, the CLI walks up from cwd looking for any of:

1. A directory already containing `.claude/`.
2. A directory already containing `skill-repos/`.
3. A directory with a `.git` marker.

Override with `--workspace /abs/path` or `SKILL_FINDER_ROOT=/abs/path`
in the environment.

## Examples

See [`examples/README.md`](examples/README.md).

## Limitations

- **Claude Code reloads aren't automatic.** After adding or linking, the user
  must restart / reload.
- **Symlinks are filesystem-dependent.** Windows without Developer Mode and
  cross-`\\wsl$` mounts will reject them.
- **Upstream layouts vary.** Discovery walks up to 5 directories deep and
  skips `node_modules`, `.venv`, `dist`, etc. Unusual nesting may silently
  miss skills — run `skill-finder doctor`.
- **`npx skills`-style skill registries not supported.** This skill works
  against arbitrary GitHub repos via git submodules, not a curated
  package-manager registry. If you want `skills.sh`-style discovery, that's
  a different tool.
- **No version pinning beyond submodule HEAD.** `git submodule update
  --remote` bumps to latest; pin by committing the recorded submodule SHA.

## Architecture

See [`SKILL.md`](SKILL.md) for the Claude-facing contract and
[`references/`](references/) for deeper notes.
