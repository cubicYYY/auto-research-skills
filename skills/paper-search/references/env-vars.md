# Environment variables

None are required; unset variables just mean lower rate limits or fallback
behavior. Load order: actual process env > `skills/paper-search/.env` (via
`python-dotenv`, read on every `uv run`).

## Reference

| Var                         | Source affected    | Effect if **set**                              | Effect if **unset**                                      | How to obtain |
|-----------------------------|--------------------|------------------------------------------------|----------------------------------------------------------|---------------|
| `OPENALEX_EMAIL`            | `openalex`         | "Polite pool" — higher throughput.             | Common pool, slower but still works.                     | Any email you own. No signup. |
| `SEMANTIC_SCHOLAR_API_KEY`  | `semantic_scholar` | Higher rate limit, fewer 429s on large runs.   | Anonymous S2 — expect occasional 429s beyond 100 RPM.    | Free via the partner form: <https://www.semanticscholar.org/product/api#Partner-Form>. |
| `GITHUB_TOKEN`              | `github`           | 30 req/min; large queries complete in one pass. | 10 req/min; large queries will stall or partial-fail.   | Fine-grained PAT, scope: **public-repo read** only. |
| `SERPAPI_KEY`               | `google_scholar`   | Paid SerpAPI proxy — avoids direct-scrape bans. | Direct scrape via `scholarly` — IP-ban risk.            | <https://serpapi.com/>. Paid. |
| `PASA_ENDPOINT`             | `pasa`             | Adapter parses the JSON API at this URL.        | Falls back to scraping `pasa-agent.ai/home` HTML.        | Internal ByteDance / private beta URL, when known. |

## Setting them

```bash
# One-time setup (preferred)
cp skills/paper-search/.env.example skills/paper-search/.env
# then edit .env and fill in values

# Or inline for a single call
OPENALEX_EMAIL=you@example.com \
SEMANTIC_SCHOLAR_API_KEY=... \
  uv run paper-search "<query>"
```

No restart needed — the CLI re-reads `.env` on every `uv run`.

## Verification

The Runtime-context block at the top of `SKILL.md` runs a `test -n` check on
each variable at skill-load time and reports which are `set`/`unset`. If a
variable you just added still shows "unset", make sure:

1. `.env` is in `skills/paper-search/` (not the repo root).
2. No leading/trailing whitespace around the `=`.
3. You're running `uv run` from a shell that inherits the env, or let the CLI
   load `.env` itself (it will — via `python-dotenv`).

## Anti-patterns

- **Don't** put keys in `pyproject.toml`, CLI flags, or the invocation
  command. `.env` or process env only.
- **Don't** commit `.env` — it's in `.gitignore`.
- **Don't** set every variable "just in case". Only `OPENALEX_EMAIL` is
  essentially free; the others have real costs (SerpAPI billing,
  S2 signup, PAT management) and the defaults work fine without them for
  most queries.
