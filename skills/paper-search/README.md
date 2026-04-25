# Paper Search Skill

A Claude Code [Skill](https://code.claude.com/docs/en/skills) that searches
academic papers across arXiv, Semantic Scholar, OpenAlex, CrossRef, Google
Scholar, PaSa, and GitHub paper-list repos, ranks them with BM25 + citation
+ recency, and optionally downloads PDFs.

---

## Requirements

- **Python ≥ 3.10**
- **[uv](https://docs.astral.sh/uv/)** (0.4+). Install:
  `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Network access to the source APIs you enable. All defaults (arXiv, OpenAlex,
  Semantic Scholar) work anonymously.
- *(Optional)* a git checkout of this repo; `uv run` handles everything else.

### Optional API keys

None are required. Setting them raises rate limits or unlocks extra sources.

| Env var                    | Effect                                                  |
|----------------------------|---------------------------------------------------------|
| `OPENALEX_EMAIL`           | Puts you in OpenAlex's faster "polite pool".            |
| `SEMANTIC_SCHOLAR_API_KEY` | Higher S2 rate limit.                                   |
| `GITHUB_TOKEN`             | Raises GitHub rate limit 10 → 30 req/min (for `-s github`). |
| `SERPAPI_KEY`              | Optional proxy for `-s google_scholar`.                 |
| `PASA_ENDPOINT`            | Override the default PaSa URL when a JSON API is known. |

Copy `.env.example` to `.env` (in this directory) and fill in what you have.

---

## Deploy — as a Claude Code Skill

1. **Clone** somewhere Claude can read:
   ```bash
   git clone <this-repo> ~/claude-skills/paper-search-skill
   ```
2. **Install deps** (one-time; `uv sync` at the repo root resolves the
   workspace and installs every skill's console script into one `.venv`):
   ```bash
   cd ~/claude-skills/paper-search-skill
   uv sync
   ```
3. **Register the skill folder** with Claude Code (point the skill loader at
   `skills/paper-search/`; refer to the [Skills docs](https://code.claude.com/docs/en/skills)
   for your Claude Code version's discovery rules).
4. **Verify** — works from the repo root, any subdirectory with `--directory`,
   or inside the skill folder:
   ```bash
   uv run paper-search --help                                    # from repo root
   uv run --directory ~/claude-skills/paper-search-skill paper-search --help   # from anywhere
   cd skills/paper-search && uv run paper-search --help          # from skill dir
   ```

Claude will then pick up `SKILL.md` and invoke the CLI through `uv run` —
see [`SKILL.md`](SKILL.md) for the exact shell invocation, flag guidance,
and output contract that Claude uses.

---

## Deploy — as a standalone CLI

Exactly the same setup, minus the skill registration:

```bash
git clone <this-repo>
cd paper-search-skill
uv sync
uv run paper-search "attention" --top 10 --json
```

---

## Usage

Run from the repo root (recommended) or the skill folder:

```bash
uv run paper-search "<query>" [options]
```

From any other directory, point `uv` at the repo root:

```bash
uv run --directory /abs/path/to/paper-search-skill paper-search "<query>" [options]
```

### Common commands

```bash
# Survey on a topic (default sources: arxiv, openalex, semantic_scholar)
uv run paper-search "diffusion models for protein design"

# Machine-readable JSON (what Claude uses)
uv run paper-search "attention" --json

# Niche topic: pull more candidates per source, return more results
uv run paper-search "repository auditing LLM" -n 150 --top 30

# Download PDFs to ./papers
uv run paper-search "flash attention" -o ./papers

# Widen the year window for foundational work
uv run paper-search "transformer architecture" --from 2015 --to 2024

# Add an opt-in source (github awesome-lists)
uv run paper-search "graph neural networks" -s arxiv,openalex,semantic_scholar,github

# Emit BibTeX for every result
uv run paper-search "retrieval augmented generation" --bibtex --top 10 > refs.bib

# Paste a BibTeX entry as the query — the title is auto-extracted
uv run paper-search '@article{v2017, title={Attention Is All You Need}, year={2017}}' --top 5
```

### Flags

| Flag             | Default                             | Meaning |
|------------------|-------------------------------------|---------|
| positional       | —                                   | Query (keywords or free-form). |
| `-n / --total`   | `50`                                | Candidates to pull from each source before ranking. |
| `--top`          | `20`                                | Papers to return after ranking. |
| `-s / --sources` | `arxiv,openalex,semantic_scholar`   | Comma list from `arxiv, semantic_scholar, openalex, crossref, google_scholar, pasa, github`. |
| `--from`         | `year_to - 5`                       | Lower year bound (inclusive). |
| `--to`           | current year                        | Upper year bound (inclusive). |
| `-o / --output`  | *none*                              | If set, download PDFs here. |
| `--json`         | off                                 | Emit JSON instead of markdown (each paper gets a `bibtex` field too). |
| `--bibtex`       | off                                 | Emit BibTeX entries instead of markdown. Cite-key is `surname_word_year`. |

Exit codes: `0` success · `2` bad arguments · `3` all sources failed ·
`4` partial (some sources errored but results returned).

### Sources

| Source             | In default? | Needs key? | Notes |
|--------------------|-------------|------------|-------|
| `arxiv`            | ✅           | no         | Preprints. |
| `openalex`         | ✅           | no         | Broad metadata + citations. |
| `semantic_scholar` | ✅           | no         | Fills gaps OpenAlex misses. |
| `crossref`         | opt-in       | no         | Published-journal metadata. |
| `google_scholar`   | opt-in       | no         | ⚠️ aggressive IP blocking (see limitations). |
| `pasa`             | opt-in       | no         | ByteDance LLM-agent search. |
| `github`           | opt-in       | no         | awesome-list / paper-list repos. |

### Opting in to more sources

`-s` takes a **comma-separated list** and **replaces** the default set (it
does not append). Always repeat `arxiv,openalex,semantic_scholar` when adding
opt-in sources:

```bash
# ✅ defaults + github awesome-lists
uv run paper-search "<query>" -s arxiv,openalex,semantic_scholar,github

# ✅ everything except google_scholar (the "comprehensive" option)
uv run paper-search "<query>" -s arxiv,openalex,semantic_scholar,crossref,pasa,github

# ❌ only github — silently drops the three defaults
uv run paper-search "<query>" -s github
```

**When to reach for each opt-in:**

- **`github`** — You want awesome-list / survey-style coverage. First run is
  slow (regex-extracts arXiv IDs / DOIs from READMEs and bulk-resolves them);
  subsequent runs hit the 30-day SQLite cache at
  `~/.cache/paper-search/resolved.sqlite`. Works better with `GITHUB_TOKEN`.
- **`crossref`** — You want published-journal DOIs specifically (OpenAlex
  already wraps most of this, so only add if you see gaps).
- **`google_scholar`** — Last resort. `scholarly` scrapes the public site and
  Google can block your IP from Scholar in a regular browser. Only enable if
  you understand the risk.
- **`pasa`** — LLM-agent search from ByteDance. Useful for AI-curated
  results on topics where keyword search falls short. Endpoint is a web SPA
  by default; override via `PASA_ENDPOINT` when a JSON API is known.

**Enabling a source reliably usually means also setting the right env var.**
Copy `.env.example` → `.env` in this directory, fill in what you have, and
the CLI loads it automatically via `python-dotenv`:

| Source             | Related env var             | Effect if unset                                       | How to get it |
|--------------------|-----------------------------|-------------------------------------------------------|---------------|
| `openalex`         | `OPENALEX_EMAIL`            | Still works — slower common pool.                     | Any email you own — signals "polite pool" to OpenAlex. |
| `semantic_scholar` | `SEMANTIC_SCHOLAR_API_KEY`  | Works but expect occasional 429s on large queries.    | Free key at <https://www.semanticscholar.org/product/api#Partner-Form>. |
| `github`           | `GITHUB_TOKEN`              | 10 req/min; large queries stall.                      | Fine-grained PAT, **public-repo read** scope only. |
| `google_scholar`   | `SERPAPI_KEY` (optional)    | Direct scrape; IP-ban risk.                           | Paid SerpAPI key. |
| `pasa`             | `PASA_ENDPOINT` (optional)  | Falls back to scraping `pasa-agent.ai/home` HTML.     | JSON endpoint URL when you have one. |

None are required. Unset keys just mean lower rate limits or a scrape-based
fallback — no source hard-fails for lack of a key.

### Examples

Runnable demos in [`examples/`](examples/):

- `attention_offline.py` — offline ranking sanity-check, no network, <1s.
- `attention_live.py` — live CLI against the three default sources.
- `repository_auditing.py` — realistic research-assistant run via subprocess
  (exactly the shell path Claude uses).

```bash
uv run python examples/attention_offline.py
uv run python examples/attention_live.py
uv run python examples/repository_auditing.py
```

---

## Limitations

- **Recall is bounded by each source's own relevance search.** If a paper
  isn't in a source's per-query top-`n`, the local ranker can't surface it.
  Cross-source union helps but doesn't fully fix it — for low recall, split
  the query or raise `-n`.
- **Google Scholar can get your IP banned.** `scholarly` scrapes the public
  site; Google detects automated traffic and may block the host (affecting
  normal browser usage too). Only enable when the user explicitly asks.
- **PaSa web UI returns an SPA shell.** The default
  `https://pasa-agent.ai/home?query=…` endpoint yields HTML; the adapter
  regex-extracts arXiv IDs from it and hydrates via arXiv. If/when a JSON
  API becomes public, set `PASA_ENDPOINT` and the adapter will parse it
  directly.
- **GitHub source caps at 15 refs per repo** (top-5 repos) to keep the
  resolver cost bounded. First run is slow; resolved DOI/arXiv metadata is
  cached for 30 days in `~/.cache/paper-search/resolved.sqlite`.
- **CrossRef lacks a true batch DOI endpoint.** The adapter fans out
  `asyncio.gather` over individual `/works/{doi}` requests, which caps
  realistic GitHub-source throughput at ~50 DOIs per query.
- **PDF downloads are deliberately slow.** 3 concurrent requests, 1–3 s
  jitter, per-host serialization, 3 retries on 5xx/429. Downloading 20 PDFs
  takes ~1 minute minimum — this is to avoid tripping arXiv / university
  mirrors' throttling.
- **No embedding-based ranking.** BM25 only. Off-topic but lexically-close
  titles can rank higher than semantically-similar ones. A
  `sentence-transformers` extra was explicitly rejected for install-size
  reasons.
- **Citation counts are missing for some sources.** arXiv, PaSa, and raw
  GitHub refs don't carry citation data; those papers get `cite = 0.5`
  (neutral) rather than 0, but you still lose signal on that axis.
- **Invocation path matters.** `uv run paper-search` works from the repo
  root (it's a uv workspace) or from `skills/paper-search/`. From any other
  cwd, pass `--directory /abs/path/to/paper-search-skill`.

---

## Troubleshooting

| Symptom                                                    | Fix |
|------------------------------------------------------------|-----|
| `error: Failed to spawn: paper-search`                     | Run `uv sync` at the repo root first, then invoke from the repo root or pass `--directory /abs/path/to/paper-search-skill`. |
| `ModuleNotFoundError: No module named 'paper_search'` when using `python -m` | Don't call the system `python`. Use `uv run paper-search …` or activate `.venv/bin/activate` first. |
| `exit code 3` (all sources failed)                         | Network / API outage. Try again in a minute; check `errors[]` in JSON output for details. |
| `google_scholar` always errors                             | Your host IP is likely rate-limited or blocked. Drop it from `-s`, or set `SERPAPI_KEY`. |
| Top-ranked paper is off-topic despite a specific query     | Raise `-n` (e.g. `-n 150`), or narrow the query — recall is source-bound. |
| `github` source returns nothing                            | Check `GITHUB_TOKEN`; unauthenticated search is heavily rate-limited. |
| PDF downloads hang / time out                              | arXiv/mirror throttling. Reduce `--top` or run during off-peak hours. |
| Claude can't find the skill                                | Confirm the skill loader is pointed at this directory (the one containing `SKILL.md`), not the repo root. |

---

## Architecture

See [`SKILL.md`](SKILL.md) for the Claude invocation contract. Deeper design
notes (ranking formula, per-source quirks, env-var reference) live under
[`references/`](references/).
