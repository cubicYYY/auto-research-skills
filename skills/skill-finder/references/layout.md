# Directory layout

## Canonical structure

```
<workspace>/
├── skill-repos/                          # vendored upstream repos
│   ├── <slug1>/                          # e.g. claude-skills
│   │   └── skills/<name>/SKILL.md        # nested layout (most common)
│   └── <slug2>/
│       └── SKILL.md                      # flat layout (single-skill repo)
└── .claude/
    └── skills/
        └── <name> -> ../../skill-repos/<slug>/.../<name>
```

### Why `skill-repos/` exists

Submodules alone can only expose an entire upstream repo at a fixed path.
When an upstream repo publishes N skills under its own `skills/`
subdirectory, submoduling it into `.claude/skills/<slug>` nests the
individual skills one level too deep — Claude Code's loader never sees
them at `.claude/skills/<name>/SKILL.md`.

`skill-repos/` keeps the upstream tree intact; `.claude/skills/` provides
the loader-visible view via symlinks.

### Why relative symlinks

- **Portable across checkouts.** `cp -r workspace/ elsewhere/` or another
  developer cloning the workspace onto their machine leaves the links
  valid, since they point at sibling-of-`.claude/skills/` paths, not
  absolute machine-specific paths.
- **Playing nice with git.** Relative symlinks are stored as plain text
  ("relative target") in the tree object; absolute ones bake in
  `/home/you/...` that never round-trips.

### Why **not** just symlink the whole upstream `skills/` dir

You could in principle do `.claude/skills -> skill-repos/<slug>/skills`.
Problems:

1. **Only works for one repo.** The moment you vendor a second upstream,
   you've already consumed the `.claude/skills` path.
2. **Loader confusion** — some Claude Code versions reject a symlinked
   `.claude/skills` root in favor of a real directory.
3. **No per-skill overrides** (renaming, prefixing, skipping a skill
   from a collection).

Per-skill symlinks give you a point of control per skill with zero
duplication of the upstream tree.

## Multi-repo example

```
workspace/
├── skill-repos/
│   ├── anthropics-skills/
│   │   └── skills/
│   │       ├── pdf/SKILL.md
│   │       ├── pptx/SKILL.md
│   │       └── docx/SKILL.md
│   ├── vercel-agent-skills/
│   │   └── skills/
│   │       ├── react-best-practices/SKILL.md
│   │       └── nextjs-perf/SKILL.md
│   └── our-skills/
│       └── skills/
│           ├── paper-search/SKILL.md
│           └── skill-finder/SKILL.md
└── .claude/
    └── skills/
        ├── pdf                    -> ../../skill-repos/anthropics-skills/skills/pdf
        ├── pptx                   -> ../../skill-repos/anthropics-skills/skills/pptx
        ├── docx                   -> ../../skill-repos/anthropics-skills/skills/docx
        ├── vercel-react-best-practices -> ../../skill-repos/vercel-agent-skills/skills/react-best-practices
        ├── vercel-nextjs-perf     -> ../../skill-repos/vercel-agent-skills/skills/nextjs-perf
        ├── paper-search           -> ../../skill-repos/our-skills/skills/paper-search
        └── skill-finder           -> ../../skill-repos/our-skills/skills/skill-finder
```

Notes:

- `anthropics-skills/skills/pdf` → `.claude/skills/pdf` (no prefix; names
  don't collide with existing entries).
- `vercel-agent-skills/skills/react-best-practices` → prefixed with
  `vercel-` via `--link-prefix vercel-` at install time.
- `our-skills/skills/skill-finder` → self-referential: the finder links
  itself.
