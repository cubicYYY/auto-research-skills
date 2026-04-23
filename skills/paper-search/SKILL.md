---
name: paper-search
description: Search arXiv, OpenAlex, Semantic Scholar, CrossRef, Google Scholar, PaSa, and GitHub paper-lists for academic papers matching a query; rank with BM25 and optionally download PDFs.
when_to_use: The user asks for papers, a literature survey, related work, citations on a topic, or wants to download PDFs.
argument-hint: "<query>" [options]
allowed-tools: Bash(uv run *), Bash(date *), Bash(echo *), Bash(test *)
---

# paper-search

## Runtime context (injected at skill load)

- Current year: !`date +%Y`
- Skill directory: !`echo "${CLAUDE_SKILL_DIR:-$(pwd)}"`
- Provisioned API keys:
```!
[ -n "${OPENALEX_EMAIL:-}" ] && echo "  - OPENALEX_EMAIL: set (polite pool)" || echo "  - OPENALEX_EMAIL: unset (OpenAlex still works anonymously)"
[ -n "${SEMANTIC_SCHOLAR_API_KEY:-}" ] && echo "  - SEMANTIC_SCHOLAR_API_KEY: set (higher rate limit)" || echo "  - SEMANTIC_SCHOLAR_API_KEY: unset (S2 anonymous, slower)"
[ -n "${GITHUB_TOKEN:-}" ] && echo "  - GITHUB_TOKEN: set (30 req/min for -s github)" || echo "  - GITHUB_TOKEN: unset (github source capped at 10 req/min)"
[ -n "${SERPAPI_KEY:-}" ] && echo "  - SERPAPI_KEY: set (google_scholar proxy available)" || echo "  - SERPAPI_KEY: unset"
```

## Primary invocation

Always run with `--json` so the output is machine-readable, and always pass
`--to !`date +%Y`` so the upper year bound is today's year:

```bash
uv run --directory "${CLAUDE_SKILL_DIR}" paper-search "$ARGUMENTS" \
    --to !`date +%Y` --json
```

Summarize the returned `papers[]` for the user — include title, authors (first
three + "et al." if more), year, citation count, and `arxiv_id` / `doi` if
present. Do **not** paste the entire JSON unless the user asks.

## Flags

| Flag             | Default                             | Use when |
|------------------|-------------------------------------|----------|
| positional       | —                                   | **Required.** The query — keywords or a short description. |
| `-n / --total`   | `50`                                | Pull more candidates per source if recall seems low. Increase to 100–200 for niche topics. |
| `--top`          | `20`                                | Number of papers to return after ranking. Raise for broader survey, lower for quick look. |
| `-s / --sources` | `arxiv,openalex,semantic_scholar`   | Add opt-in sources (see below). Comma-separated. |
| `--from`         | `year_to - 5`                       | Lower year bound. Loosen for classic/foundational queries. |
| `--to`           | current year                        | Upper year bound. Inject with `!`date +%Y``. |
| `-o / --output`  | *none*                              | Directory to download PDFs into. Only pass if user explicitly asked. |
| `--json`         | off — **always pass** for parsing   | Always on for agent use. Each paper in the JSON also has a `bibtex` field. |
| `--bibtex`       | off                                 | Emit BibTeX instead of JSON/markdown. Use when the user asks for a `.bib` file or citations. |

## Sources

| Source             | In default? | When to opt in |
|--------------------|-------------|----------------|
| `arxiv`            | ✅           | Always — preprints, no key needed. |
| `openalex`         | ✅           | Always — broad metadata graph with citation counts. |
| `semantic_scholar` | ✅           | Always — fills gaps OpenAlex misses. |
| `crossref`         | opt-in       | Add if user wants published-journal coverage specifically. |
| `google_scholar`   | opt-in       | **Warn first.** Scraped, aggressive IP blocking. Only when user explicitly asks. |
| `pasa`             | opt-in       | LLM-agent search; add when user wants AI-curated results. |
| `github`           | opt-in       | When user wants awesome-list / survey-style coverage. Honors `~/.cache/paper-search/resolved.sqlite` (30-day TTL). |

### Opting in to more sources

The `-s` flag takes a **comma-separated list**, and it **replaces** the default
set — it does not append. Always repeat the three defaults explicitly when
adding opt-in sources, otherwise you lose arxiv/openalex/s2:

```bash
# ✅ defaults + github
-s arxiv,openalex,semantic_scholar,github

# ❌ github ONLY — you just dropped the three defaults
-s github
```

**Decision rules for which opt-in to add:**

| User says / asks for                                               | Add to `-s`                                           |
|--------------------------------------------------------------------|-------------------------------------------------------|
| "Awesome list", "survey repo", "curated list", a topic-area README | `github`                                              |
| "Google Scholar says…", "check Scholar"                            | `google_scholar` (warn first — may fail / IP-ban)    |
| Published-journal coverage (DOI / ISBN-level metadata)             | `crossref`                                            |
| "AI-curated", "agent search", "PaSa"                               | `pasa`                                                |
| Everything (comprehensive mega-sweep)                              | `arxiv,openalex,semantic_scholar,crossref,pasa,github` (skip `google_scholar` unless explicitly asked) |

**Before adding `google_scholar`, tell the user:**
> "Google Scholar scrapes the public site and may fail or temporarily block
> your host's IP from Scholar in a regular browser. Want me to include it
> anyway?"

Only add it if they confirm.

**Key requirements (all sources work without keys, but some are rate-limited).**
The Runtime-context block at the top of this file already shows which keys are
currently set. If the user wants an opt-in source to work reliably and the
relevant key is **unset**, tell them what to do:

| Source             | Related env var             | Effect if unset                                       | How the user sets it |
|--------------------|-----------------------------|-------------------------------------------------------|----------------------|
| `openalex`         | `OPENALEX_EMAIL`            | Still works, slower "common pool".                    | Put `OPENALEX_EMAIL=you@example.com` in `skills/paper-search/.env` (or shell env). |
| `semantic_scholar` | `SEMANTIC_SCHOLAR_API_KEY`  | Still works, lower rate limit — expect occasional 429s. | Request a free key at `https://www.semanticscholar.org/product/api#Partner-Form`, then add it to `.env`. |
| `github`           | `GITHUB_TOKEN`              | 10 req/min; large queries will stall.                 | Create a fine-grained PAT with **public-repo read** scope, put it in `.env` as `GITHUB_TOKEN=…`. |
| `google_scholar`   | `SERPAPI_KEY` (optional)    | Direct scrape via `scholarly`; may IP-ban.            | Paid SerpAPI key in `.env` as `SERPAPI_KEY=…` if available. |
| `pasa`             | `PASA_ENDPOINT` (optional)  | Falls back to scraping `pasa-agent.ai/home` HTML.     | Set `PASA_ENDPOINT` to a JSON API when one is published. |

Copy `skills/paper-search/.env.example` → `skills/paper-search/.env`, fill in
values. The CLI loads `.env` automatically via `python-dotenv`. No restart
needed — each `uv run` picks it up.

## Output to parse

```json
{
  "query": "...",
  "year_range": [2021, 2026],
  "sources_used": ["arxiv", "openalex", "semantic_scholar"],
  "total_candidates": 63,
  "papers": [
    {
      "title": "...", "authors": ["..."], "year": 2023, "venue": "...",
      "abstract": "...", "doi": "...", "arxiv_id": "...",
      "url": "...", "pdf_url": "...", "citation_count": 1234,
      "score": 0.92, "sources": ["arxiv", "semantic_scholar"],
      "downloaded_to": "/path/to/file.pdf"
    }
  ],
  "errors": [{"source": "google_scholar", "error": "HTTP 429"}]
}
```

Scores are in `[0, 1]` (BM25 text × 0.60 + log-cite × 0.30 + recency × 0.10).
A paper's `sources` list shows every adapter it was merged from after dedupe.

## Exit codes

- `0` — clean success.
- `2` — bad arguments (you passed invalid flags — fix the command).
- `3` — **all** sources failed (network issue or every source is down; report
  this to the user, don't retry blindly).
- `4` — partial: some sources errored, but papers were returned. Present the
  results; optionally mention which sources failed from `errors[]`.

Treat `0` and `4` identically for the user-facing summary.

## Common patterns

**Literature survey on a topic** (default, just run it):
```bash
uv run --directory "${CLAUDE_SKILL_DIR}" paper-search "<topic>" --to !`date +%Y` --json
```

**Niche topic with low recall** (pull more candidates per source):
```bash
uv run --directory "${CLAUDE_SKILL_DIR}" paper-search "<topic>" -n 150 --top 30 --to !`date +%Y` --json
```

**Download PDFs** (only after user confirms they want them):
```bash
uv run --directory "${CLAUDE_SKILL_DIR}" paper-search "<topic>" -o ./papers --to !`date +%Y` --json
```

**Include awesome-list coverage**:
```bash
uv run --directory "${CLAUDE_SKILL_DIR}" paper-search "<topic>" -s arxiv,openalex,semantic_scholar,github --to !`date +%Y` --json
```

**Foundational / classic papers** (widen the year window):
```bash
uv run --directory "${CLAUDE_SKILL_DIR}" paper-search "<topic>" --from 2005 --to !`date +%Y` --json
```

**User asks for a `.bib` / citations**:
```bash
uv run --directory "${CLAUDE_SKILL_DIR}" paper-search "<topic>" --top 10 --bibtex --to !`date +%Y`
```

**User pastes a BibTeX entry as the query** (just pass it through — the
CLI auto-extracts the title so BM25 doesn't tokenize the whole entry):
```bash
uv run --directory "${CLAUDE_SKILL_DIR}" paper-search "$BIBTEX_ENTRY" --json --to !`date +%Y`
```

## Caveats

- **Recall is bounded by each source's own relevance search.** If a paper
  isn't in the per-source top-`n`, the ranker can't surface it. For low
  recall, consider splitting the query or raising `-n`.
- **Google Scholar can IP-ban the host.** Never add `google_scholar` without
  explicit user intent; warn the user it may fail or get blocked.
- **GitHub source caps at 15 refs per repo** and caches resolved DOIs/arXiv
  IDs for 30 days — first run is slow, subsequent runs are fast.
- **PDF downloads are rate-limited** (3 concurrent, 1–3 s jitter, per-host
  serialized). Downloading 20 PDFs takes ~1 minute minimum.
