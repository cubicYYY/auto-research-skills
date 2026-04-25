# Examples

## Offline — synthetic repo batch

Runs the scorer against a hand-built batch of fake repos and asserts the
ranking behaves sensibly. No network.

```bash
uv run python examples/offline_ranking.py
```

## Live — GitHub call

Issues a real query against GitHub, fetches a few READMEs, and prints the
top-5. Requires network and (strongly recommended) `GITHUB_TOKEN`.

```bash
uv run python examples/live_query.py
```
