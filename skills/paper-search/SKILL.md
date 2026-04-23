---
name: paper-search
description: Search academic papers across arXiv, OpenAlex, Semantic Scholar, CrossRef, Google Scholar, PaSa, and GitHub paper-list repos. Rank with BM25 + citations + recency, emit JSON or BibTeX, and optionally download PDFs. Use when the user asks for papers, a literature survey, related work, citations, prior art, or a `.bib` file on a topic — even if they don't explicitly say "search"; also use when they paste a BibTeX entry and want similar or updated results.
license: MIT
allowed-tools: Bash(uv run *) Bash(date *) Bash(echo *) Bash(test *) Read
metadata:
  version: "0.1.0"
---

# paper-search

## Runtime context

- Current year: !`date +%Y`
- Skill directory: !`echo "${CLAUDE_SKILL_DIR:-$(pwd)}"`
- Provisioned API keys:
```!
[ -n "${OPENALEX_EMAIL:-}" ] && echo "  - OPENALEX_EMAIL: set (polite pool)" || echo "  - OPENALEX_EMAIL: unset (OpenAlex still works anonymously)"
[ -n "${SEMANTIC_SCHOLAR_API_KEY:-}" ] && echo "  - SEMANTIC_SCHOLAR_API_KEY: set (higher rate limit)" || echo "  - SEMANTIC_SCHOLAR_API_KEY: unset (S2 anonymous, slower)"
[ -n "${GITHUB_TOKEN:-}" ] && echo "  - GITHUB_TOKEN: set (30 req/min for -s github)" || echo "  - GITHUB_TOKEN: unset (github source capped at 10 req/min)"
[ -n "${SERPAPI_KEY:-}" ] && echo "  - SERPAPI_KEY: set (google_scholar proxy available)" || echo "  - SERPAPI_KEY: unset"
```

## Procedure

1. **Always invoke with `--json --to !`date +%Y``.** The JSON has a `bibtex`
   field per paper, so one call covers both summary-for-user and citation
   export.

   ```bash
   uv run --directory "${CLAUDE_SKILL_DIR}" paper-search "$ARGUMENTS" \
       --to !`date +%Y` --json
   ```

2. **Parse `papers[]`** and summarize for the user — title, first 3 authors
   + "et al." if more, year, citation count, `arxiv_id` or `doi`. Don't paste
   the full JSON unless asked.

3. **Decide whether to widen the search.** If the user's query is niche or
   returns <5 papers, re-run with `-n 150 --top 30`. If they want
   foundational work, add `--from 2005`.

4. **Add opt-in sources only when triggered** (see decision rules below).
   Never silently broaden `-s` — it shapes what the user gets.

5. **Handle exit codes:** `0` or `4` → present results (mention errored
   sources from `errors[]` if any). `3` → all sources failed, say so and
   stop — do not retry in a loop. `2` → the flags were wrong, fix and rerun.

## Decision rules (when to deviate from step 1)

| User says / asks for                                  | Do this                                                              |
|-------------------------------------------------------|----------------------------------------------------------------------|
| "A `.bib` / citations / LaTeX refs"                   | Add `--bibtex`, drop `--json`. Pipe to a file if they gave a path.   |
| Pastes a BibTeX entry                                 | Pass it through as the query — the CLI auto-extracts the title.     |
| "Download the PDFs"                                   | Add `-o <dir>`. Only after they've seen a result set they like.      |
| "Foundational / classic papers"                       | Add `--from 2005` (or earlier).                                      |
| "Awesome list / survey repo / curated list"           | Add `,github` to `-s` (repeat defaults — see below).                 |
| "Check Google Scholar"                                | Warn about IP-ban risk first. Only add `,google_scholar` if they confirm. |
| Wants published-journal metadata specifically         | Add `,crossref` to `-s`.                                             |
| "AI-curated / agent search / PaSa"                    | Add `,pasa` to `-s`.                                                 |
| Few results / low recall                              | Re-run with `-n 150 --top 30`.                                       |

**Opting-in footgun**: `-s` **replaces** the defaults, it does not append.
Always repeat `arxiv,openalex,semantic_scholar` when adding a source:

```bash
# ✅ defaults + github
-s arxiv,openalex,semantic_scholar,github

# ❌ queries only github, silently drops arxiv/openalex/s2
-s github
```

**Required warning before adding `google_scholar`:**
> Google Scholar scrapes the public site and may fail or temporarily block
> your host's IP from Scholar in a regular browser. Want me to include it?

Only add `google_scholar` if they confirm.

## Output (JSON)

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
      "downloaded_to": "/path/to/file.pdf",
      "bibtex": "@article{...}"
    }
  ],
  "errors": [{"source": "google_scholar", "error": "HTTP 429"}]
}
```

Scores are `[0, 1]` (`0.60·BM25 + 0.30·log-cite + 0.10·recency`). A paper's
`sources` list shows every adapter it was merged from after dedupe.

## Gotchas

- **Recall is capped by each source's own relevance search.** If a paper
  isn't in the source's per-query top-`n`, this skill cannot surface it.
  When a user expects a specific paper and it's missing, **don't assume the
  skill is broken** — try a narrower sub-query or raise `-n` before reporting
  back.
- **Citation counts are missing for arXiv/PaSa/GitHub refs.** The ranker
  treats unknown citation counts as `0.5` (neutral), not 0. Don't tell the
  user "this paper has 0 citations" when the field is missing.
- **`uv run paper-search` fails from the wrong cwd.** Always use
  `--directory "${CLAUDE_SKILL_DIR}"`, never bare `uv run paper-search`, or
  uv will try to resolve the script against the current directory's
  `pyproject.toml` and fail with `Failed to spawn: paper-search`.
- **PDF downloads are deliberately slow** (3 concurrent, 1–3 s jitter,
  per-host serialized). Budget ~1 min per 20 PDFs; don't interpret delay as
  failure.
- **The user's query may be a BibTeX entry.** If `$ARGUMENTS` starts with
  `@`, just pass it through — the CLI extracts the title. Do not manually
  parse it.

## On-demand references

Read these files only when the listed condition matches. Don't pre-load.

- `references/ranking-formula.md` — full scoring math and tuning rationale.
  **Read when** the user asks why a paper is ranked where it is, or wants to
  change weights.
- `references/sources.md` — per-source quirks (rate limits, known-missing
  fields, fallback behavior). **Read when** a specific source keeps erroring
  in `errors[]` or the user asks about coverage.
- `references/env-vars.md` — every env var, what it unlocks, how to get it.
  **Read when** the user wants to raise rate limits, add a key, or debug
  authentication.
