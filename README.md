# Claude Code Skills Bundle

A monorepo of [Claude Code Skills](https://code.claude.com/docs/en/skills).
Each skill is a self-contained `SKILL.md` + CLI, installed into a shared
`uv` workspace so one `uv sync` at the repo root installs every skill's
console script into one `.venv`.

---

## Skills

| Skill | Description | Status |
|-------|-------------|--------|
| [`paper-search`](skills/paper-search/) | Search arXiv, OpenAlex, Semantic Scholar, CrossRef, Google Scholar, PaSa, and GitHub paper-lists. Rank with BM25 + citations + recency. Emit JSON / BibTeX / markdown. Optionally download PDFs. | ✅ Ready |
| [`skill-finder`](skills/skill-finder/) | Discover skill repos on GitHub, vendor them as submodules under `skill-repos/`, and expose individual skills into `.claude/skills/` via relative symlinks. Use to install, list, link, or audit other skills. | ✅ Ready |
| [`similar-code-search`](skills/similar-code-search/) | Novelty / prior-art check on GitHub before building a new tool or paper implementation. Ranks candidate repos by BM25 + popularity + recency + code-match and emits JSON or markdown. | ✅ Ready |
| [`paper-summarize`](skills/paper-summarize/) | Structured paper summary (TL;DR, problem, approach, results, contributions, limitations, keywords) via the Claude API. Accepts arXiv / DOI / URL / local PDF, supports cached follow-up Q&A on the same paper. | ✅ Ready |

Each skill folder contains:

- `SKILL.md` — Claude-facing manifest (the only file Claude reads at
  skill-load time).
- `README.md` — human-facing deploy / usage / limitations doc.
- `pyproject.toml` — a uv workspace member with its own console script.
- `src/` — the Python package.
- `examples/` — runnable demos.
- `references/` *(optional)* — on-demand docs Claude reads only when a
  specific condition fires (see each skill's `SKILL.md`).

---

## Requirements

- **Python ≥ 3.10**
- **[uv](https://docs.astral.sh/uv/)** (0.4+):
  `curl -LsSf https://astral.sh/uv/install.sh | sh`

Per-skill keys/env-vars are optional — see each skill's README.

---

## Deploy

One install for the whole bundle:

```bash
git clone <this-repo> ~/claude-skills/bundle
cd ~/claude-skills/bundle
uv sync
```

This creates `.venv/` at the repo root with **every** skill's CLI registered.
Verify:

```bash
uv run paper-search --help
```

Register each skill you want active with Claude Code by pointing its skill
loader at the relevant `skills/<name>/` directory (not the repo root). See
each skill's README for any per-skill deploy notes.

---

## Usage — as standalone executables

The top-level `pyproject.toml` is a real uv workspace: once `uv sync` has
run, every skill's `[project.scripts]` entry is a plain binary in `.venv/bin/`,
usable without Claude in the loop. Five equivalent invocation paths:

### 1. `uv run` from the repo root

```bash
uv run paper-search "flash attention" -s arxiv -n 5 --top 2 -f markdown
```

### 2. `uv run --directory …` from any cwd

```bash
cd /anywhere/else
uv run --directory ~/claude-skills/bundle paper-search "<query>"
```

### 3. Activated venv — just call the binary

```bash
source ~/claude-skills/bundle/.venv/bin/activate
which paper-search       # → .../bundle/.venv/bin/paper-search
paper-search "RAG survey" -s arxiv -n 3 --top 1 -f bibtex
```

### 4. As a Python library

Every skill's package is importable because `uv sync` installs it in editable
mode:

```python
from paper_search.core import score_batch, run_search
from paper_search.models import Paper
from paper_search.bibtex import to_bibtex

# Rank your own Paper objects
scored = score_batch([...], "attention", year_to=2026)

# Render any Paper as BibTeX
print(to_bibtex(scored[0]))
```

### 5. `uvx` — ephemeral, no clone

From a remote or a local path, without any pre-install:

```bash
# local path
uvx --from /path/to/bundle/skills/paper-search paper-search "transformer" --top 5

# or directly from a git URL (once the repo is published)
uvx --from git+https://github.com/you/bundle.git#subdirectory=skills/paper-search \
    paper-search "transformer" --top 5
```

---

## Usage — as a Claude Code Skill

Claude invokes each skill through its own `SKILL.md` — you shouldn't need to
wire anything beyond pointing the skill loader at the right `skills/<name>/`
folder. The underlying CLI is the same one the standalone paths above exercise,
so anything you've verified on the command line behaves identically when
Claude runs it.

---

## Adding a new skill

1. **Scaffold** a new folder under `skills/`:
   ```bash
   mkdir -p skills/<new-name>/src/<package_name>
   cd skills/<new-name>
   # author pyproject.toml with `[project.scripts] <new-name> = "..."`
   # author SKILL.md (see paper-search for reference)
   ```
2. **Register the workspace member** in the top-level `pyproject.toml`:
   ```toml
   [project]
   dependencies = ["paper-search", "<new-name>"]

   [tool.uv.sources]
   paper-search = { workspace = true }
   <new-name> = { workspace = true }
   ```
   The workspace glob (`members = ["skills/*"]`) already picks up the new
   folder; this step makes its console script available from the root.
3. **Re-sync**:
   ```bash
   uv sync
   uv run <new-name> --help
   ```
4. **Document** — add a row to the Skills table above with a link to
   `skills/<new-name>/`.

---

## Layout

```
bundle/
├── pyproject.toml        # uv workspace root, lists members as deps
├── uv.lock               # shared lockfile for the whole workspace
├── .venv/                # created by `uv sync`; one env for all skills
├── README.md             # this file
└── skills/
    └── paper-search/
        ├── SKILL.md      # Claude-facing manifest
        ├── README.md     # deploy + usage + limitations
        ├── pyproject.toml
        ├── src/paper_search/
        ├── examples/
        └── references/
```

---

## Contributing

- Keep skills self-contained. Shared utilities belong in a dedicated
  `skills/lib-*/` package with its own `pyproject.toml`, not in a top-level
  `src/` directory.
- Prefer one console script per skill, matching the folder name.
- Run the skill's `examples/*_offline.py` before opening a PR if one exists;
  they double as smoke tests.
- Follow the [agentskills.io](https://agentskills.io/home) conventions for
  each `SKILL.md` (frontmatter fields, description-with-triggers, on-demand
  references).

---

## License

MIT. Each skill may declare its own license in its `SKILL.md` frontmatter.
