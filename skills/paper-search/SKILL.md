---
name: paper-search
description: Search academic papers across arXiv, OpenAlex, Semantic Scholar, CrossRef, Google Scholar, PaSa, and GitHub paper-list repos. Rank with BM25 + citations + recency, emit JSON or BibTeX, and optionally download PDFs. Use when the user asks for papers, a literature survey, related work, citations, prior art, or a `.bib` file on a topic — even if they don't explicitly say "search"; also use when they paste a BibTeX entry and want similar or updated results.
license: MIT
allowed-tools: Bash(uv run *) Bash(date *) Bash(echo *) Bash(printenv *) Bash(pwd) Read
metadata:
  version: "0.1.0"
---

# paper-search

## Runtime context

- Current year: !`date +%Y`
- Skill directory: !`pwd`
- API keys — set (`y`) or unset (`n`):
  - `OPENALEX_EMAIL`: !`printenv OPENALEX_EMAIL >/dev/null && echo y || echo n` (polite pool; OpenAlex still works if unset)
  - `SEMANTIC_SCHOLAR_API_KEY`: !`printenv SEMANTIC_SCHOLAR_API_KEY >/dev/null && echo y || echo n` (higher S2 rate limit)
  - `GITHUB_TOKEN`: !`printenv GITHUB_TOKEN >/dev/null && echo y || echo n` (30 req/min for `-s github`; 10 if unset)
  - `SERPAPI_KEY`: !`printenv SERPAPI_KEY >/dev/null && echo y || echo n` (google_scholar proxy)

## Variables used in this file

- `${CLAUDE_SKILL_DIR}` — the skill's own directory. Always present at
  skill-load time. Used only as the `--directory` argument to `uv run` so
  the CLI resolves. **Never use this as the destination for user-visible
  output files** — it's inside the skill repo.
- `${USER_CWD}` — the user's current working directory (typically their
  project root) **at the moment the agent was invoked**. The CLI's cwd will
  be `${CLAUDE_SKILL_DIR}`, not this, so any relative path the user gives
  must be resolved against `${USER_CWD}` *before* being passed to the CLI.
- `${QUERY}` — the search query. **Construction rule:** if the user pastes a
  BibTeX entry, pass the entry *verbatim* as `${QUERY}` (the CLI extracts the
  title). Otherwise use the user's own words.
- `${YEAR}` — today's year; substitute `!`date +%Y`` literally in commands.

## The command

Use this exact template. Substitute the variables; do not add flags that
aren't listed here without a trigger from the table below.

```bash
uv run --directory "${CLAUDE_SKILL_DIR}" paper-search "${QUERY}" \
    --to !`date +%Y` -f json
```

**Canonical flags** (use these forms, not the aliases):

| Flag                 | Value space                                       | Default  |
|----------------------|---------------------------------------------------|----------|
| `-f, --format`       | `markdown` \| `json` \| `bibtex`                  | `json`*  |
| `-n, --total`        | integer                                           | `50`     |
| `--top`              | integer                                           | `20`     |
| `-s, --sources`      | comma list from: `arxiv, openalex, semantic_scholar, crossref, google_scholar, pasa, github` | `arxiv,openalex,semantic_scholar` |
| `--from`             | year (int)                                        | `to - 5` |
| `--to`               | year (int)                                        | current year |
| `-o, --output`       | directory path                                    | *none*   |

*Default for the CLI is `markdown`; for this skill the agent **must** pass
`-f json` unless a trigger in the table below overrides it.

Aliases `--json` and `--bibtex` are accepted but **do not use them**; pick
`-f json` or `-f bibtex` so there is exactly one form in the invocation
line.

## Trigger → override table

Apply each row only if its trigger matches. Rows are independent; multiple
can apply.

| Trigger (condition on user input or previous result)                                 | Change to the template                                   |
|--------------------------------------------------------------------------------------|----------------------------------------------------------|
| User explicitly asks for a `.bib` file, BibTeX output, or citations for LaTeX        | Replace `-f json` with `-f bibtex`                       |
| User explicitly asks for a human-readable summary / no JSON                          | Replace `-f json` with `-f markdown`                     |
| User pastes a BibTeX entry                                                           | No flag change — just use the entry as `${QUERY}`        |
| User explicitly says "download the PDFs" (or equivalent)                             | Add `-o <abs_dir>`. See **Resolving `-o` paths** below — never pass a relative path unless explicitly told; otherwise the CLI runs with cwd = `${CLAUDE_SKILL_DIR}`, so `./papers` lands *inside the skill folder*, which is confusing. |
| User asks for classic/foundational work, or uses words like "original", "seminal"    | Add `--from 2005`                                        |
| User asks for "recent" / "latest" without a year                                     | No change — default window is `now - 5 … now`            |
| User asks for a specific year range                                                  | Add `--from <lo> --to <hi>` (override the default `--to`)|
| User asks for "awesome lists", "survey repos", or "curated lists"                    | Add `-s arxiv,openalex,semantic_scholar,github`          |
| User asks specifically for Google Scholar or Scholar results                         | **First** run the `google_scholar` warning (see below). On confirmation, add `-s arxiv,openalex,semantic_scholar,google_scholar` |
| User asks for published-journal metadata specifically (not preprints)                | Add `-s arxiv,openalex,semantic_scholar,crossref`        |
| User asks for PaSa / LLM-agent search / AI-curated results                           | Add `-s arxiv,openalex,semantic_scholar,pasa`            |
| Previous call returned `total_candidates < 5` for the same query                     | Re-run with `-n 150 --top 30`                            |
| Previous call returned `total_candidates == 0` for the same query                    | Try one narrower sub-query from the user's phrasing, then stop |
| `errors[]` in previous result lists every source in `sources_used`                   | Stop — report the errors, do not retry                   |

### Resolving `-o` paths

The CLI runs with `cwd = ${CLAUDE_SKILL_DIR}` (that's what `uv run --directory …` does). Any relative path you pass to `-o` resolves against the skill folder — which is almost never what the user wants. Always pass an **absolute path under the user's project**:

1. Determine the user's project root. In order of preference:
   - The path the user literally typed if it was absolute (`/path/to/refs`).
   - `${USER_CWD}` — the shell cwd at the moment the agent was invoked.
     This is almost always the repo root the user is working in.
   - If neither is known, **ask** the user: *"Where should I save the PDFs?
     Give me an absolute path, or I'll use `$(pwd)/papers`."*
2. Join with the user's relative specifier, e.g. `papers/`, `./refs`,
   `out/pdfs`. If the user said "save to `./papers`", resolve to
   `${USER_CWD}/papers`, **not** `./papers`.
3. Pass the resulting absolute path to `-o`. Example:

   ```bash
   uv run --directory "${CLAUDE_SKILL_DIR}" paper-search "${QUERY}" \
       --to !`date +%Y` -f json -o "${USER_CWD}/papers"
   ```

After the run completes, tell the user the absolute destination in your
summary so there is no ambiguity (e.g. "Downloaded 10 PDFs to
`/home/you/project/papers/`").

**Never-do rules** (absolute):

- Never pass `-s <anything>` without including `arxiv,openalex,semantic_scholar` in the list. `-s` **replaces**, does not append.
- Never enable `google_scholar` without the user's explicit confirmation.
- Never run `python -m paper_search...` or activate a system Python. Only `uv run`.
- Never add `-o` unless the user asked for PDFs in so many words.
- Never pass a relative path to `-o` (see **Resolving `-o` paths**) unless explicitly told. The CLI's cwd is the skill folder, so `./papers` lands inside the skill repo.
- Never re-run more than twice for the same query.

### `google_scholar` confirmation script

Before adding `google_scholar`, emit exactly this message to the user and wait:

> Google Scholar scrapes the public site and may fail or temporarily block
> your host's IP from Scholar in a regular browser. Include it anyway?

Add it only if the user responds affirmatively in the next turn.

## Reading the result

The JSON schema returned from `-f json`:

```json
{
  "query": "...",
  "year_range": [<from>, <to>],
  "sources_used": ["arxiv", "openalex", ...],
  "total_candidates": 63,
  "papers": [
    {
      "title": "...",
      "authors": ["..."],
      "year": 2023,
      "venue": "...",
      "abstract": "...",
      "doi": "...",
      "arxiv_id": "...",
      "url": "...",
      "pdf_url": "...",
      "citation_count": 1234,
      "score": 0.92,
      "sources": ["arxiv", "semantic_scholar"],
      "downloaded_to": "/path/to/file.pdf",
      "bibtex": "@article{...}"
    }
  ],
  "errors": [{"source": "google_scholar", "error": "HTTP 429"}]
}
```

**Field semantics (unambiguous):**

- `score ∈ [0, 1]` — higher is better. Formula: `0.60·BM25_sigmoid + 0.30·log1p_citations + 0.10·gaussian_recency`. Papers are returned already sorted by `score` desc.
- `citation_count` — integer when known, `null` when the source did not
  provide one (arXiv, PaSa, GitHub). **Do not say "this paper has 0
  citations" when the field is `null`**; say "citation count unknown".
- `sources` — every adapter that returned this paper after dedupe. Length
  ≥ 2 means multiple sources agree.
- `total_candidates` — the deduped pool size *before* top-k truncation.
  Use this to decide the "low recall" trigger, not `len(papers)`.
- `errors` — may be empty. Each entry names a source and an error string.

## Summarizing for the user

Produce a numbered list. Per paper include, in this order:

1. Title (in italics or bold).
2. First 3 authors, then "et al." iff there are more.
3. Year (or "n.d." if `year` is null).
4. Citation count, formatted as `{N} citations` if known, else `citation count unknown`.
5. `arxiv_id` **or** `doi` **or** `url`, in that fallback order, as a link.

Do **not** paste the full JSON. Do **not** paste `abstract` unless the user asks. Do **not** paste `bibtex` unless the user asks.

## Exit codes

| Code | Meaning                                                                                       | Agent response |
|------|-----------------------------------------------------------------------------------------------|----------------|
| `0`  | Success.                                                                                      | Summarize `papers[]`. If `errors[]` is non-empty, also say "N of M sources errored". |
| `2`  | Bad arguments (the agent's invocation was wrong).                                             | Do not re-run blindly. Re-read this file, construct a valid command, retry once. |
| `3`  | All selected sources failed.                                                                  | Tell the user the search failed; list the errors. Do not retry. |
| `4`  | Partial — some sources errored but papers were returned.                                      | Same as `0`. Mention errored sources from `errors[]`. |

Any other exit code → treat as `3`.

## Gotchas (facts, not instructions)

These are properties of the tool, not rules for the agent:

- Recall is bounded by each source's own relevance search. If a paper is
  absent from all sources' per-query top-`n`, this skill cannot surface it.
- The CLI runs three default sources concurrently; total latency ≈ the
  slowest source (~5–30 s typical).
- PDF downloads take ~1 min per 20 PDFs (intentional throttling: 3
  concurrent, 1–3 s jitter, per-host serialized).
- Citation counts from `arxiv`, `pasa`, and `github` are always `null`.
- The first `-s github` run is slow (~30–60 s); subsequent runs hit the
  SQLite cache at `~/.cache/paper-search/resolved.sqlite` (30-day TTL).

## Two-pass keyword-boosted search (only if `paper-summarize` is available)

**Precondition:** this pattern requires the `paper-summarize` skill to be
installed in the same workspace. If `uv run paper-summarize --help` exits
non-zero, skip this section and stop after the first search.

When a user runs an initial search and then summarizes one or more of the
top hits, the summaries expose a `keywords[]` field (5–10 domain-specific
phrases per paper). Those keywords frequently contain terms the user didn't
think to include in the original query — re-running the search with them
appended routinely surfaces papers the first pass missed.

Do this **only** when all of the following hold:

1. The user has (or just) summarized ≥ 2 papers from the first search.
2. The JSON summaries are in the current context (you have their
   `keywords[]` arrays).

### Procedure

1. **Collect keywords.** Union every paper's `keywords[]` from the
   `paper-summarize` JSON outputs you have. Drop any that are already in
   the first-pass query (case-insensitive substring match).
2. **Cap at 5 new terms.** More than that dilutes the BM25 signal and
   starts outweighing the original query. Prefer terms that appear in ≥ 2
   summaries (signals cross-paper relevance), then by length (longer phrases
   are more specific).
3. **Re-run paper-search** with the enriched query, concatenated as a
   space-separated string:

   ```bash
   uv run --directory "${CLAUDE_SKILL_DIR}" paper-search \
       "${ORIGINAL_QUERY} ${KW1} ${KW2} ${KW3} ${KW4}" \
       --to !`date +%Y` -f json
   ```

   Do not change `-s` or `-n` from the first pass — only the query string.
4. **Compute the delta.** From the second-pass `papers[]`, drop any paper
   whose `arxiv_id` or `doi` appeared in the first pass. What remains is
   the keyword-boost recall.
5. **Report to the user** in this shape:
   - One line: "Second pass added N papers using keywords: `<kw1>, <kw2>, …`".
   - Then the usual paper summary format for the new papers only.
   - If N is 0, say so plainly — don't pretend the re-search helped.

### Never-do rules for this loop

- Never run the second pass without explicit summarize output — guessing
  keywords from your own knowledge defeats the point (the whole value is
  that these terms came from the papers themselves).
- Never chain a third pass off the second pass's summaries. Diminishing
  returns kick in fast; the user can ask again if they want another round.
- Never re-run the search when the first pass already returned ≥ 20 on-topic
  papers. The boost is for thin-recall cases.

## On-demand references

Read only when the matching condition fires. Do not pre-load.

- `references/ranking-formula.md` — **read when** the user asks why a paper
  is ranked where it is, or asks to change scoring weights.
- `references/sources.md` — **read when** a single source keeps erroring,
  or the user asks about coverage/quirks of a specific source.
- `references/env-vars.md` — **read when** the user wants to raise rate
  limits, add a key, or debug authentication.
