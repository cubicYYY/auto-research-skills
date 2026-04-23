# Per-source notes

Detailed quirks of each source adapter. Consult when a source keeps erroring
or the user asks about coverage.

## `arxiv` (default, no key)

- Backed by `arxiv` PyPI client over the public Atom API.
- **Sort**: relevance. The per-query top-`n` is what arXiv's own relevance
  ranker returns — if a paper isn't there, our ranker cannot surface it.
- **No citation counts.** `citation_count` will always be `None`, ranker
  uses the neutral `0.5` fallback.
- **Rate limit**: 3s delay between requests baked into the client.
- **Common error**: network timeout during abstract fetch — usually
  recoverable by rerunning.

## `openalex` (default, no key)

- Backed by `pyalex`. Anonymous access works but is in the "common pool".
- **Raises rate limit** when `OPENALEX_EMAIL` is set ("polite pool").
- Provides citation counts, venue, DOI. Sometimes returns synthetic DOIs
  (e.g. `10.65215/...`) that don't match any other source — the union-find
  dedupe handles this via shared normalized-title keys.
- Abstracts come as an inverted index and are reconstructed server-side.

## `semantic_scholar` (default, no key)

- Backed by `semanticscholar` PyPI client.
- `SEMANTIC_SCHOLAR_API_KEY` raises the rate limit; without it, expect
  occasional `HTTP 429`/`ConnectionRefusedError` on large queries.
- Best coverage for CS/ML papers; sometimes missing for niche domains.
- Provides citation counts and PDF URLs (`openAccessPdf`).

## `crossref` (opt-in, no key)

- Backed by `habanero`. Journal-article bias — filters by
  `type=journal-article`.
- Low recall compared to OpenAlex (OpenAlex already wraps CrossRef data).
- Add specifically when the user wants DOI-level metadata beyond what
  OpenAlex surfaces.
- No true batch endpoint; the GitHub source resolves DOIs one at a time via
  `asyncio.gather`, capped.

## `google_scholar` (opt-in, no key)

- **Warn the user first** (see SKILL.md). `scholarly` scrapes the public
  site; Google aggressively rate-limits and IP-bans automated traffic.
- `SERPAPI_KEY` can be used as a paid proxy to sidestep bans.
- Citation counts yes, abstracts sometimes, PDFs via `eprint_url`.
- Common error: `HTTP 429` or captcha redirect — if you see this, drop the
  source and report to the user.

## `pasa` (opt-in, no key)

- ByteDance LLM-agent paper search. Default endpoint
  `https://pasa-agent.ai/home?query=…` returns an SPA shell (HTML).
- Fallback behavior: regex-extract arXiv IDs from the HTML and hydrate via
  arXiv's bulk `id_list` endpoint.
- Override with `PASA_ENDPOINT=<json-api-url>` when one is known to parse
  JSON directly.
- Recall varies heavily by topic — strong on ML/NLP, weak on other fields.

## `github` (opt-in, no key)

Non-obvious — see the flow described in top-level `README.md`. Key facts:

- Queries `awesome <topic> papers in:name,description,readme stars:>20`.
- Top 5 repos only; capped at 15 references per repo (tail bias —
  "most-recently-added" heuristic).
- Extracted arXiv IDs and DOIs are bulk-resolved via arXiv `id_list` and
  CrossRef per-DOI gather.
- **SQLite cache** at `~/.cache/paper-search/resolved.sqlite` with 30-day
  TTL — first run is slow (~30-60s), subsequent runs hit cache.
- `GITHUB_TOKEN` raises the rate limit from 10 → 30 req/min.

## Dedupe behavior (all sources)

Union-find across three keys:

1. DOI (lowercased, `https://doi.org/` stripped)
2. arXiv ID (version suffix stripped: `1706.03762v3` → `1706.03762`)
3. Normalized title (NFKD-fold, lowercase, strip non-alphanumerics,
   truncate to 50 chars)

Two papers sharing **any** key collapse. This catches the OpenAlex-synthetic-
DOI case where one source has the real arXiv ID and the other has an
arbitrary DOI — both match on the title key.
