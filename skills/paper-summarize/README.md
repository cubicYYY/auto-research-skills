# paper-summarize

A Claude Code [Skill](https://code.claude.com/docs/en/skills) that turns an
academic paper (arXiv ID, DOI, URL, or local PDF) into a structured summary
via the Claude API. Follow-up questions on the same paper are cached — the
paper body loads once and subsequent calls hit the cache at ~0.1× input cost.

## What you get

Structured fields returned as Markdown or JSON:

- `title`, `authors`
- `tldr` — one sentence
- `problem` / `approach` / `results` — one paragraph each
- `contributions`, `limitations` — bullet lists
- `keywords` — 5–10 tags

Plus `_usage` in JSON mode (input/output/cache-read/cache-write tokens).

## Requirements

- Python ≥ 3.10, `uv`.
- **`ANTHROPIC_API_KEY`** — required. Get one at
  <https://console.anthropic.com/>. Set it in your shell or a `.env` file.
- Network access to:
  - `api.anthropic.com` (always)
  - `arxiv.org` (for arXiv IDs / URLs)
  - `api.crossref.org` (for DOIs)
  - The original host (for arbitrary URLs)

## Install

As part of the bundle workspace:

```bash
uv run paper-summarize --help
```

Standalone:

```bash
uvx --from git+https://github.com/you/<bundle>#subdirectory=skills/paper-summarize \
    paper-summarize --help
```

## Usage

```bash
# Structured markdown summary (default)
paper-summarize 1706.03762

# From a DOI
paper-summarize 10.48550/arXiv.1706.03762

# From a URL
paper-summarize https://arxiv.org/abs/2205.14135

# From a local PDF
paper-summarize ~/papers/flash-attention.pdf

# JSON for scripts / agents
paper-summarize 1706.03762 -f json

# Free-form follow-up (paper body is cached from a prior call)
paper-summarize 1706.03762 -q "How does this handle variable sequence lengths?"

# Use Opus for a deeper read
paper-summarize 1706.03762 -m opus
```

### Flags

| Flag           | Default      | Meaning |
|----------------|--------------|---------|
| positional     | —            | arXiv ID (`1706.03762`), arXiv URL, DOI, any HTTPS URL, or a local PDF path. |
| `-m, --model`  | `sonnet`     | `sonnet` (= `claude-sonnet-4-6`) or `opus` (= `claude-opus-4-7`). |
| `-q, --ask`    | *none*       | Free-form question. Runs Q&A over the cached paper body instead of a structured summary. |
| `-f, --format` | `markdown`   | `markdown` or `json`. |
| `--max-tokens` | `4000` / `2000` | Override response cap (summary / Q&A defaults). |

### Exit codes

| Code | Meaning |
|------|---------|
| `0`  | Success. |
| `2`  | Bad input — missing `ANTHROPIC_API_KEY`, or input spec not recognized. |
| `3`  | Empty extracted text — usually a scanned PDF with no OCR layer. |

## How prompt caching works here

The paper body is placed in a `system` text block with a **1-hour** ephemeral
`cache_control` breakpoint. On the first call, you pay a ~2× cache-write
premium for those tokens; every subsequent call with the same input (same
paper, any model run) reads the cache at ~0.1× input cost.

Concretely, for a 45k-token paper on Sonnet 4.6 at list prices
(`$3.00 / 1M` input, `$15.00 / 1M` output):

- First call: ~45k × 2× = ~$0.27 cache write + a few hundred output tokens.
- Follow-up call: ~45k × 0.1× = ~$0.014 cache read + output tokens.

So the break-even for the 1-hour TTL is roughly: two calls per paper justify
the write premium. A research session with 3–5 follow-up questions on the
same paper is exactly the workload this is tuned for.

Model caches are **separate**. Calling the same paper on Sonnet then Opus
pays a fresh write on Opus.

## Limitations

- **No OCR.** Scanned PDFs without a text layer produce empty extraction and
  exit 3. Run `ocrmypdf` or similar first.
- **Truncation at ~45k tokens.** Very long papers (books, surveys, theses)
  have their tail silently dropped. If this matters, pre-extract the section
  of interest and pass it as a `.txt` → `.pdf` converted file, or run against
  a specific section.
- **Cache is model-scoped and 1-hour TTL.** Leaving a summary overnight and
  coming back the next day costs a fresh write.
- **No multi-paper synthesis.** Each paper is its own cache entry; comparing
  two papers requires two calls and synthesis on the agent side.
- **Summary quality is model-dependent.** Sonnet 4.6 is accurate and
  appropriately concise; for adversarial or heavily mathematical papers,
  `-m opus` is worth the 2× cost.

## Examples

See [`examples/README.md`](examples/README.md).

## Architecture

See [`SKILL.md`](SKILL.md) for the Claude invocation contract and
[`references/`](references/) for API / caching / ingestion details.
