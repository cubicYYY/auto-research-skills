# similar-code-search

A Claude Code [Skill](https://code.claude.com/docs/en/skills) that searches
GitHub for existing projects overlapping with a proposed tool, library, or
paper implementation — a novelty / prior-art check before writing code.

## What it does

Given a query like *"LLM agent for repository-level code auditing"*, the
CLI:

1. Runs two GitHub repo searches (best-match + sort-by-stars) in parallel.
2. Runs a GitHub **code search** if `GITHUB_TOKEN` is set — this surfaces
   files whose contents match the query, which catches projects whose
   names/descriptions don't.
3. Merges the candidate pool, fetches READMEs for the top repos to enrich
   text context.
4. Ranks with a single absolute formula:
   ```
   score = 0.55·BM25_text + 0.25·popularity + 0.10·recency + 0.10·code_match
   ```
5. Returns JSON or a ranked markdown list.

All four components are in `[0, 1]`; `text` uses a sigmoid squash (not
batch max-norm) so a weak match stays weak.

## Requirements

- Python ≥ 3.10, `uv`.
- *(Strongly recommended)* a GitHub personal access token in
  `GITHUB_TOKEN`. Without it, search is limited to 10 req/min and
  code-search is disabled — expect thin results.

## Install

Part of the workspace bundle:

```bash
uv run similar-code-search --help
```

Or standalone:

```bash
uvx --from git+https://github.com/you/<bundle>#subdirectory=skills/similar-code-search \
    similar-code-search --help
```

## Commands

```bash
# Default novelty check
similar-code-search "LLM agent for repository-level code auditing"

# Restrict to a language
similar-code-search "BM25 academic paper search CLI" -l python

# Deep check before starting a long project
similar-code-search "diff-based PR review assistant" -n 80 --top 30 --readme-for 20

# JSON for scripting / agent consumption
similar-code-search "flash attention kernel" -f json
```

### Flags

| Flag             | Default     | Meaning |
|------------------|-------------|---------|
| positional       | —           | Query string (keywords or a short project description). |
| `-l / --language`| *none*      | GitHub-recognized language filter. |
| `--min-stars`    | `5`         | Minimum stars per candidate. Drop most dead projects. |
| `-n / --per-search` | `30`     | Results pulled per backend before merge. |
| `--top`          | `10`        | Repos to return after ranking. |
| `--readme-for`   | `10`        | Fetch READMEs for this many top candidates (enriches BM25). |
| `-f / --format`  | `markdown`  | `markdown` or `json`. |

### Exit codes

| Code | Meaning |
|------|---------|
| `0`  | Success. |
| `3`  | No results AND at least one backend errored (likely network / rate-limit). |
| `4`  | Partial — some backends errored but repos came back. |

## How the ranking works

**`text`** — tokenize `name + description + topics + readme_excerpt`, run
Okapi BM25 against the query, squash to `[0, 1]` with
`sigmoid(0.5 · (bm25 − 6))`. This is the most informative signal.

**`popularity`** — `log1p(stars) / log1p(batch_max_stars)`. Log-scaled so
one 100k-star project doesn't zero out the others.

**`recency`** — Gaussian on `pushed_at`, σ = 2 years. Unknown → 0.5 neutral.

**`code_match`** — `1.0` if GitHub's code-search returned a file-level hit
in this repo (via `GITHUB_TOKEN`). A strong signal when present; silent
when anonymous.

## Limitations

- **No token = thin recall.** The single biggest degrader. Code-search is
  entirely off without a token.
- **Keyword-based ranking.** Synonyms ("parse" vs "compile") break recall.
  For a thorough check, re-run with alternate phrasings.
- **Fork pollution.** Popular topics return many forks; the ranker
  doesn't fork-detect — scan manually.
- **GitHub's relevance is a black box.** Projects outside its top-`n` for
  your query are unrecoverable.
- **No semantic embeddings.** We deliberately don't pull in
  `sentence-transformers` (model-download cost for a CLI).
- **Rate limits are per-token.** A busy CI run can 429 you — set
  `GITHUB_TOKEN` to a dedicated PAT if you automate it.

## Examples

See [`examples/README.md`](examples/README.md):

- `examples/offline_ranking.py` — synthetic repo batch, no network.
- `examples/live_query.py` — real GitHub call.

## Architecture

See [`SKILL.md`](SKILL.md) for the Claude invocation contract and
[`references/`](references/) for query-crafting and rate-limit notes.
