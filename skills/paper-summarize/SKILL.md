---
name: paper-summarize
description: Summarize academic papers into structured sections (TL;DR, problem, approach, results, contributions, limitations, keywords) via the Claude API. Accepts arXiv IDs, DOIs, URLs, or local PDFs. Supports follow-up Q&A on the same paper with prompt caching so repeat calls on the same paper are cheap. Use when the user asks to "summarize this paper", "explain what this paper does", "TL;DR this arXiv link", "give me the key findings of X", or pastes a paper reference after using `paper-search`. Also use when the user asks follow-up questions about a paper they just had summarized.
license: MIT
allowed-tools: Bash(uv run *) Bash(date *) Bash(echo *) Bash(printenv *) Bash(pwd) Read
metadata:
  version: "0.1.0"
---

# paper-summarize

## Runtime context

- Current year: !`date +%Y`
- Skill dir: !`pwd`

## Variables used in this file

- `${CLAUDE_SKILL_DIR}` — this skill's directory. Always pass
  `--directory "${CLAUDE_SKILL_DIR}"` to `uv run`, never bare `uv run …`.
- `${INPUT}` — arXiv ID (`1706.03762`), arXiv URL, DOI
  (`10.48550/arXiv.1706.03762`), any HTTPS URL to a PDF, or an absolute local
  PDF path. Pass exactly what the user gave; the CLI normalizes it.
- `${USER_CWD}` — the user's cwd. The CLI **does not** write files (output is
  to stdout), so this matters less here than in `paper-search`, but still use
  absolute paths if the user asks you to redirect output to a file.

## The command

Default — structured summary, markdown out:

```bash
uv run --directory "${CLAUDE_SKILL_DIR}" paper-summarize "${INPUT}"
```

Agent-friendly (JSON for downstream parsing):

```bash
uv run --directory "${CLAUDE_SKILL_DIR}" paper-summarize "${INPUT}" -f json
```

Follow-up question on the same paper (cached body, cheap):

```bash
uv run --directory "${CLAUDE_SKILL_DIR}" paper-summarize "${INPUT}" \
    -q "How does this compare to <X>?" -f json
```

## Canonical flags

| Flag            | Value space               | Default                                         |
|-----------------|---------------------------|-------------------------------------------------|
| positional      | arXiv / DOI / URL / path  | **required**                                    |
| `-m, --model`   | `sonnet` \| `opus`        | `sonnet` (= `claude-sonnet-4-6`)                |
| `-q, --ask`     | question string           | *none* — if set, does Q&A instead of summary     |
| `-f, --format`  | `markdown` \| `json`      | `markdown`                                      |
| `--max-tokens`  | int                       | `4000` for summary, `2000` for `--ask`          |

## Procedure

1. **Parse the user's intent.** If the user wants a summary, run the default
   command. If the user asks a specific question about a paper ("what's the
   F1 score on SQuAD?", "how do they handle OOV tokens?"), use `-q <question>`.
2. **Always pass `-f json`** when running in agent mode — the JSON preserves
   all fields (`title`, `authors`, `tldr`, `problem`, `approach`, `results`,
   `contributions`, `limitations`, `keywords`) and a `_usage` block for token
   accounting.
3. **Summarize from the JSON**, don't dump it. For the user, format as:
   - Title + authors (one line)
   - TL;DR (bold)
   - 2–4 bullets from `contributions` + `limitations` combined
   - A single "see full paper at <url>" link if the input was a URL/arXiv ID.
   Include `results` verbatim only if the user asked about results.
4. **For follow-up questions**, re-run with the same `${INPUT}` and `-q`.
   The paper body is cached for 1 hour — expect `cache_read_input_tokens` in
   the usage block to be close to the first-call `cache_creation_input_tokens`.
   Mention to the user when a follow-up hit the cache ("cheaper than the first
   call").
5. **Model selection.** Default to `sonnet` — it's plenty for most summaries
   and half the cost of Opus. Switch to `-m opus` when the user says "deep
   dive", "careful analysis", "opus please", or when the paper is heavily
   technical (new ML architecture papers, theoretical CS proofs, etc.).
6. **Handle exit codes:** `0` = success. `2` = bad input (unrecognized input
   spec, or the CLI printed a configuration error to stderr — relay it
   verbatim to the user and stop, do not retry). `3` = empty extracted text
   (scanned PDF with no OCR — tell the user this and stop, do not retry).
   Any other code → treat as `3`.

## Trigger → action table

| User says / asks                                                                     | Action                                                      |
|--------------------------------------------------------------------------------------|-------------------------------------------------------------|
| "Summarize / TL;DR / explain this paper", gives an arXiv/DOI/URL/PDF                 | Default command. Summarize from JSON.                       |
| "What does <paper> say about <topic>?"                                               | `-q "<topic question>"` (Q&A mode).                         |
| Pastes an arXiv link after a `paper-search` call                                     | Default command. Summarize from JSON.                       |
| "Give me the results / F1 / accuracy / numbers"                                      | `-q "What are the main quantitative results?"` if structured summary is insufficient; otherwise just extract from `results` field. |
| "Read this PDF" + filepath                                                           | Default command with the path as `${INPUT}`.                |
| "Do a deep read" / "be careful" / "opus please"                                      | Add `-m opus`.                                              |
| Several follow-ups on the same paper                                                 | Keep calling with the **same** `${INPUT}` + `-q`. Cache hits are automatic. |
| "Compare this to the previous paper we summarized"                                   | Summarize each paper independently (they share no cache), then synthesize in your own response. |

## Never-do rules

- Never paste the full JSON or the full `results` / `approach` / `problem`
  paragraphs verbatim into chat unless the user asked for the raw output.
  The structured summary is long — extract, don't dump.
- Never call the CLI without `--directory "${CLAUDE_SKILL_DIR}"` — it's a
  uv-managed project; bare `uv run paper-summarize` fails from most cwds.
- Never switch `${INPUT}` between follow-ups if you want cache reuse. Cache
  is keyed on the paper body (normalized) — different URL / different arXiv ID
  = different cache entry.
- Never upgrade to `opus` silently for cost reasons you invent. If the user
  hasn't asked, stay on `sonnet`.
- Never retry on a scanned-PDF failure (`exit 3`). Tell the user the PDF has
  no extractable text; they need an OCR pass first. This skill does not do OCR.
- Never claim the summary is "verified" or "fact-checked" — it's a model
  read of the paper, not a review.

## Reading the JSON output

```json
{
  "title": "...",
  "authors": ["..."],
  "tldr": "One-sentence summary, ≤ 40 words.",
  "problem": "One paragraph.",
  "approach": "One paragraph.",
  "results": "One paragraph with numbers.",
  "contributions": ["...", "..."],
  "limitations": ["...", "..."],
  "keywords": ["...", "..."],
  "_paper_ref": "1706.03762",
  "_usage": {
    "input_tokens": 123,
    "output_tokens": 456,
    "cache_creation_input_tokens": 45678,
    "cache_read_input_tokens": 0
  }
}
```

- **`_usage.cache_read_input_tokens > 0`** on a follow-up call means the paper
  body was served from cache (~0.1× price). That's the expected behavior.
- **`_usage.cache_creation_input_tokens` > 0 on the first call** is the write
  premium (~1.25× for 5-minute TTL, 2× for 1-hour — we use 1-hour). Budget
  for one write per paper per hour.

## Gotchas

- **Paper body is truncated to ~180k characters** (~45k tokens) before
  sending. Very long papers (books, 100+ page surveys) get their tail cut.
  If the user cares about the last section, ask them to pass the raw PDF
  with `pdftotext` / `pdftk` pre-extraction or point at the specific section.
- **Scanned PDFs extract no text.** `pypdf` does not do OCR. The CLI exits 3
  with a clear error; tell the user and stop.
- **Sonnet 4.6 minimum cacheable prefix is 2048 tokens.** Papers shorter
  than ~10 KB (unusual — maybe a workshop abstract) will not cache; usage
  will show `cache_creation_input_tokens: 0`. Not a bug.
- **Cache is per-model.** Switching between `sonnet` and `opus` on the same
  paper pays a fresh cache write on the other model.
- **arXiv PDFs can hang** when arXiv is rate-limiting. The CLI will just
  time out after 60s — if this happens, retry once, then fall back to a DOI
  or direct URL if the user has one.

## Composes with `paper-search`

The `keywords[]` field returned in each summary is designed to feed back
into `paper-search` as a second-pass query boost. If the user summarized
≥ 2 papers from a prior `paper-search` run and asks for broader coverage,
see **"Two-pass keyword-boosted search"** in `paper-search/SKILL.md` for
the exact procedure. The gist: union the `keywords[]` from the summaries,
drop terms already in the original query, cap at 4 new terms, re-run
`paper-search` with the enriched query, and report only the new papers.

## On-demand references

- `references/api-details.md` — exact Claude API call shape (model IDs,
  `cache_control` placement, `output_format` schema). **Read when** the user
  asks about token costs, why cache hit rate is low, or wants to change the
  system prompt.
- `references/ingestion.md` — how each input type is resolved (arXiv bulk
  endpoint, DOI → CrossRef → PDF link, raw URL, local PDF). **Read when** an
  input consistently fails to extract or the user wants to add a new source.
