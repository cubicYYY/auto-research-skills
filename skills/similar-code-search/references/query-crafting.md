# Query crafting

The single biggest factor in whether this skill returns useful results is
the query. GitHub's relevance search is keyword-heavy and does no semantic
expansion, so an overly-broad or overly-narrow query kills recall.

## Good vs bad

| ❌ Bad                        | ✅ Good                                                               |
|-------------------------------|-----------------------------------------------------------------------|
| `auditing`                    | `LLM agent for repository-level code auditing`                        |
| `pdf`                         | `PDF form filler CLI with LLM-generated values`                       |
| `rag`                         | `RAG pipeline with hybrid BM25 + dense retrieval over local PDFs`     |
| `scraper`                     | `arXiv paper scraper with citation graph export`                      |
| `skill`                       | `Claude Code skill finder that manages submodules and symlinks`       |

The pattern: **domain + function + technique or platform**.

## Checklist

Before running `similar-code-search`, the query should answer:

1. **Domain** — what field is the project in? (`academic papers`, `pdf`,
   `code review`, `deployment`)
2. **Function** — what does it do? (`search`, `summarize`, `audit`,
   `generate`, `compile`)
3. **Distinctive technique or surface** — how is it done, or what's the
   entry point? (`CLI`, `LLM agent`, `BM25`, `VS Code extension`,
   `browser extension`)

If any of the three are missing, recall is noisy. Ask the user for the
missing piece before running.

## Multi-pass search

For a thorough novelty check, run the skill 2–3 times with different
phrasings of the same idea. The ranker is deterministic per-query, so you'll
only discover new prior art by changing wording.

Example — project is "a CLI that finds prior art on GitHub":

```
similar-code-search "CLI tool for finding similar GitHub repositories"
similar-code-search "novelty check for open-source projects"
similar-code-search "prior art search GitHub repos CLI"
```

Union the top-10 from each; unique full_names are your real candidate pool.

## Language restriction

Pass `-l <language>` when the project stack is decided. It tightens
recall in the right direction. Avoid when the project could exist in
multiple languages — a JavaScript PDF tool might beat your Python plan,
but only if you don't filter it out.

## When the query is a spec, not a phrase

If the user hands you a README draft or a design doc, extract the
**one-sentence summary** and use that. Don't pass the whole doc — BM25
tokenizes everything and the ratio of signal to noise drops.

Example extraction:

> **User gives you:** *"We're building a tool that runs on the user's
> laptop, watches `git diff` in the background, and uses an LLM to
> suggest one-line commit messages based on the diff plus the last few
> commits."*
>
> **Query you run:** `LLM-based automatic git commit message suggester from diff`
