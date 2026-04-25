# Examples

Runnable demos of the `paper-search` CLI and ranking logic.

## Offline — ranking on a synthetic batch

Shows the scorer pick *Attention Is All You Need* over flash/sparse variants
given the query `"attention"`. No network.

```bash
uv run python examples/attention_offline.py
```

## Live — end-to-end CLI

Runs the actual CLI against arXiv + OpenAlex + Semantic Scholar. Expect ~1–4
minutes depending on source latency.

```bash
uv run python examples/attention_live.py
```

Or invoke the CLI directly:

```bash
uv run paper-search "attention" --top 15 --from 2015 --to 2026
```

The top hit should be *Attention Is All You Need*; FlashAttention and sparse-
attention papers (Longformer, sparse transformers, radial attention) should
appear in the top ~20.

## Live — Repository Auditing

Realistic research-assistant use case: pull recent work on auditing /
mining software repositories (security, supply chain, vulnerabilities).
Prints a ranked list and writes the full JSON payload to
`examples/repository_auditing.json` so you can inspect downstream.

```bash
uv run python examples/repository_auditing.py
```

## Live — Keyword-Boosted Two-Pass Search

Demonstrates the `paper-search` × `paper-summarize` composition from
SKILL.md: pass 1 search → summarize top-3 → union `keywords[]`, drop
terms already in the query, cap at 4 → pass 2 search → print the delta.

Requires `paper-summarize` in the same workspace and `ANTHROPIC_API_KEY`;
gracefully degrades to pass 1 only if either is missing.

```bash
uv run python examples/keyword_boosted_search.py
```
