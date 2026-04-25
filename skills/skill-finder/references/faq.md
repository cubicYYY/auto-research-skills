# FAQ

## How do I update a vendored repo?

If the workspace is a git repo and the entry under `skill-repos/` is a real
submodule:

```bash
git submodule update --remote skill-repos/<slug>
git commit -m "bump <slug>"
```

If it was plain-cloned (workspace wasn't a git repo at add time):

```bash
cd skill-repos/<slug>
git pull
```

Either way, the symlinks in `.claude/skills/` still work — they point at
paths, not at commits.

## How do I pin a vendored repo to a specific commit / tag / branch?

Submodule mode: `cd skill-repos/<slug> && git checkout <sha|tag|branch>`,
then commit the updated submodule pointer at the workspace root.

Plain-clone mode: `cd skill-repos/<slug> && git checkout <sha|tag|branch>`.
Since there's no submodule pointer, this is purely a local decision — your
next `git pull` may fast-forward past it.

## Can I share one `skill-repos/` across multiple workspaces?

Yes, and it's a reasonable way to avoid re-cloning the same upstreams.

```bash
mkdir -p ~/shared/skill-repos
# Vendor upstreams once, shared:
(cd ~/shared && skill-finder add anthropics/skills)
# Each workspace gets its own symlink view:
cd ~/projects/A && ln -s ~/shared/skill-repos skill-repos
cd ~/projects/A && skill-finder link pdf
cd ~/projects/B && ln -s ~/shared/skill-repos skill-repos
cd ~/projects/B && skill-finder link pdf --as-name docs-pdf
```

Caveat: if you `skill-finder remove` from workspace A, the shared
`skill-repos/` is touched and workspace B's symlinks will break.
`skill-finder doctor` in workspace B will flag it.

## What about CI?

If your workspace is a git repo and `skill-repos/` entries are submodules,
CI needs to recurse:

```bash
git clone --recurse-submodules <workspace-url>
# or if already cloned:
git submodule update --init --recursive
```

The `.claude/skills/` symlinks are plain text files in the git tree and
check out correctly with no extra step.

## Can I exclude a skill from a collection I've vendored?

Yes — `skill-finder add <repo>` creates one symlink per discovered skill,
but each symlink is independent. To exclude one:

```bash
rm .claude/skills/<unwanted-skill>
```

The underlying repo stays. To avoid the link getting recreated on the next
`skill-finder link` run, keep a note or add it to a project-local ignore
list (skill-finder doesn't maintain one itself — keep it simple).

## What does `doctor` check?

- Symlinks under `.claude/skills/` with non-existent targets.
- Symlinks pointing at directories that no longer contain a `SKILL.md`.
- Directories under `skill-repos/` with no `SKILL.md` anywhere inside
  (usually means the upstream layout changed and discovery didn't find it).

## Name collisions across repos?

By default, `skill-finder add` links with the skill's own `name` (from its
`SKILL.md` frontmatter). Two upstream repos publishing a skill called `pdf`
will collide — the second `add` will skip-with-warning per conflicting link
unless `--force` is passed.

Mitigations:

- Use `--link-prefix vendor-` at `add` time to namespace a whole collection.
- Use `skill-finder link <repo>/<skill> --as-name <alt>` after the fact.

## Does this work on Windows?

Symlinks on Windows require Developer Mode (Settings → Privacy & Security →
For Developers) *or* admin privileges. Without them, `skill-finder add`
will fail with `OSError: [WinError 1314]` when it tries to symlink.

Inside WSL (`wsl.exe`) it works natively as long as the workspace lives on
the WSL filesystem, not the `/mnt/c/...` mount.

## Does it work with private repos?

Set `GITHUB_TOKEN` and use an HTTPS clone URL the token can access, or use
`git@github.com:owner/name.git` SSH form if your SSH agent has a key.
`skill-finder` shells out to `git`, so whatever auth works for `git clone`
at the command line works here.
