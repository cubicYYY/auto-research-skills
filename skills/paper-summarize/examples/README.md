# Examples

## Offline — verify ingestion + schema without an API key

Exercises `ingest.load()` on a synthetic local PDF and asserts the structured
schema validates. No network, no ANTHROPIC_API_KEY required.

```bash
uv run python examples/ingest_offline.py
```

## Live — real arXiv summary + cached follow-up

Summarizes an arXiv paper, then asks a follow-up question on the same paper
and confirms the cache was read. Requires network + `ANTHROPIC_API_KEY`.

```bash
uv run python examples/summarize_live.py
```
