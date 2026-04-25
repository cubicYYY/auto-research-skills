---
name: similar-code-search
description: Search GitHub for existing repositories that overlap with a proposed tool, library, or paper implementation — a novelty/prior-art check before the user invests time building something new. Use when the user says "what's out there for X", "has someone already built Y", "is this new?", "novelty check", "prior art on GitHub", "find similar repos", or describes a project idea and asks whether to proceed. Also use when reviewing a plan: scan GitHub before green-lighting implementation work.
license: MIT
allowed-tools: Bash(uv run *) Bash(date *) Bash(echo *) Bash(printenv *) Bash(pwd) Read
metadata:
  version: "0.1.0"
---

# similar-code-search

## Runtime context

- Current working directory: !`pwd`
- `GITHUB_TOKEN` set: !`printenv GITHUB_TOKEN >/dev/null && echo y || echo n` (unset = 10 req/min, no code-search, thin results)

## Variables used in this file

- `${QUERY}` — a **specific, descriptive** phrase summarizing the project
  idea. Bare one-word queries ("transformer", "compiler") are almost useless
  — GitHub returns tens of thousands. Prefer `"LLM agent for repository-level
  code auditing"` over `"auditing"`.
- `${LANG}` — optional GitHub-recognized language name (e.g. `python`,
  `typescript`, `rust`). Pass with `-l` when the user has declared the
  target language.
- `${YEAR}` — today's year; substitute `!`date +%Y`` literally in commands.

## The command

```bash
uv run similar-code-search "${QUERY}" -f json
```

Optional extensions:

- `-l <language>` — restrict to a language. Use when the user has a
  specific stack in mind.
- `-n 50 --top 20` — widen when the first run feels sparse.
- `--min-stars 20` — filter weak/abandoned repos. The default (5) already
  drops most dead projects.
- `-f markdown` — only when the user explicitly asks for a human-readable
  summary instead of JSON.

## Procedure

1. **Construct `${QUERY}` carefully.** Restate the user's project in
   ≤ 20 content words. Include domain + function + technique, e.g.
   `"PDF form filler with LLM tool-use for pre-filled values"`, not
   `"pdf filler"`. One-word queries → ask for more detail first.
2. Run the CLI with `-f json`.
3. **Parse the JSON.** Each `repos[i]` has: `full_name`, `html_url`, `stars`,
   `pushed_at`, `description`, `topics`, `score` (in `[0, 1]`), and
   `score_components` (text / popularity / recency / code_match).
4. **Present the top 5–10 to the user in this order**, grouped by
   novelty-threat level:
   - **Direct overlap** (`score ≥ 0.55` and description mentions the core
     function) — "this is already built; read it before starting".
   - **Partial overlap** (`0.35 ≤ score < 0.55`, or shares topic but not
     function) — "consider these as reference / starting points".
   - **Tangential** (below `0.35`) — list briefly; usually safe to ignore.
5. **End with a verdict**: one sentence saying whether the space is
   crowded, contested, or open. Back it up with the repo counts and the
   top 2–3 most-similar by name.
6. **Do not claim novelty without evidence.** If fewer than 5 real
   candidates came back (thin results) or `GITHUB_TOKEN` is unset, say
   "I did a GitHub novelty pass with limited recall; a deeper search may
   turn up more."

## Reading `score_components`

All four are in `[0, 1]`; higher is better.

- `text` — BM25 over repo name + description + topics + README excerpt,
  sigmoid-squashed. **The most informative component.** ≥ 0.7 means the
  README and description strongly match the query.
- `popularity` — `log1p(stars) / log1p(batch_max_stars)`. Big numbers mean
  the prior-art repo is mature / well-known.
- `recency` — Gaussian on `pushed_at`, σ = 2 years. `0.9+` means actively
  maintained; below `0.3` means stale.
- `code_match` — `1.0` iff GitHub's code-search returned a file-level match
  in this repo (requires `GITHUB_TOKEN`). A strong positive signal when
  it's `1.0`; absence means nothing on anonymous runs.

Use `score_components` in your narrative: *"RepoAudit (score 0.78, text=0.92, active: pushed 3 weeks ago) directly implements the idea — read it first."*

## Output schema (`-f json`)

```json
{
  "query": "...",
  "language": "python",
  "backends_used": ["repos", "repos-by-stars", "code"],
  "total_candidates": 42,
  "repos": [
    {
      "full_name": "owner/name",
      "html_url": "https://github.com/owner/name",
      "description": "...",
      "language": "Python",
      "topics": ["...", "..."],
      "stars": 1234,
      "forks": 56,
      "pushed_at": "2026-03-21",
      "created_at": "2024-08-01",
      "readme_excerpt": "...",
      "matched_files": ["src/auditor.py"],
      "score": 0.82,
      "score_components": {"text": 0.91, "popularity": 0.73, "recency": 0.88, "code_match": 1.0}
    }
  ],
  "errors": [{"backend": "code", "error": "..."}]
}
```

## Trigger → override table

| User says / asks                                            | Change to the command                                        |
|-------------------------------------------------------------|--------------------------------------------------------------|
| Names a specific language / stack                           | Add `-l <language>`                                          |
| "Shallow check" / "quick scan"                              | Drop `--top` to `5`, keep `-n 30`                            |
| "Deep check" / "thorough" / "make sure nothing exists"      | Add `-n 80 --top 30 --readme-for 20`                         |
| Wants markdown not JSON                                     | `-f markdown`                                                |
| First run returned < 5 results                              | Re-run with `--min-stars 0 -n 60`                            |
| Query was bare / one-word                                   | **Ask for more detail** before running — do not run yet      |

## Never-do rules

- Never declare something "novel" after one run with an unset
  `GITHUB_TOKEN` — say you had limited recall.
- Never summarize only by stars. A recent, well-scored repo with 50 stars
  may be more relevant than a 20k-star project that happens to share
  keywords.
- Never include a repo in the "direct overlap" tier without checking its
  `description` actually matches the function — high `text` score can
  come from README lexical overlap alone.
- Never run without `${QUERY}` containing at least a domain word and a
  function word. If the user's prompt doesn't provide both, **ask**.

## Gotchas

- **`GITHUB_TOKEN` unset is the single biggest recall killer.** The
  unauth search limit is 10 req/min and code-search is disabled entirely.
  The first line of the CLI's stderr tells you this; relay the warning
  to the user.
- **GitHub's relevance ranker is keyword-heavy.** A project that uses
  synonyms ("parse", "compile", "analyze") instead of the query's terms
  may be missed. Mitigation: re-run with different phrasings if the
  first pass looks thin.
- **Forks dominate some queries.** Topics like "LLM agent framework"
  return dozens of `langchain-ts` forks. The BM25 ranker here mostly
  punts on this — scan the top 20 manually and skip obvious forks.
- **Code-search matches file contents**, not semantics. A repo full of
  `def attention(...)` will match `"attention"` even if the goal is
  unrelated.
- **Created vs pushed**: `pushed_at` is the last commit; `created_at` is
  the repo's birth. Recency score uses `pushed_at`. A repo pushed
  yesterday but created 6 years ago is still "active".

## On-demand references

- `references/query-crafting.md` — how to turn a vague idea into a
  query that retrieves actual prior art. **Read when** the user's first
  query was too broad or returned nothing.
- `references/rate-limits.md` — exact GitHub search rate limits, token
  scopes needed, how to diagnose 403s. **Read when** the CLI returns
  `errors[]` with HTTP codes or the user asks about API quota.
