# API details

Exact shape of the Claude API call, cache-control placement, and the
structured-output schema.

## Models

| Mode    | Model ID              | Context | Max output tokens |
|---------|-----------------------|---------|-------------------|
| `sonnet`| `claude-sonnet-4-6`   | 1M      | 64K               |
| `opus`  | `claude-opus-4-7`     | 1M      | 128K              |

The CLI defaults to `sonnet`. Adaptive thinking is **not** enabled by default
here — summarization does not benefit meaningfully from it and it raises
latency. If you want to enable it, edit `summarize.py` and add
`thinking={"type": "adaptive"}` + `output_config={"effort": "medium"}` to
the `messages.parse` / `messages.create` call.

## Structured output

We use `client.messages.parse(output_format=PaperSummary)`, where
`PaperSummary` is a `pydantic.BaseModel`. The SDK translates it to a
`json_schema` and validates the response, so `response.parsed_output` is a
typed `PaperSummary` instance — not raw JSON.

If you add fields to `PaperSummary`, update both:

- `models.py` — the schema itself.
- The `USER_INSTRUCTION` string in `summarize.py` — Claude follows this for
  each field's format.

Fields supported by structured outputs are a subset of JSON Schema. The
SDK strips unsupported constraints (see the [Claude API skill's
`shared/tool-use-concepts.md`](../../paper-search/SKILL.md) reference or the
platform docs for the current list).

## Prompt caching

### Where the breakpoint goes

```python
system = [
    {"type": "text", "text": SYSTEM_HEADER},         # stable instruction
    {"type": "text", "text": PAPER_BODY,              # cacheable
     "cache_control": {"type": "ephemeral", "ttl": "1h"}},
]
messages = [{"role": "user", "content": USER_INSTRUCTION or question}]
```

Render order is `tools → system → messages`. There are no tools here, so the
breakpoint on the last system block caches everything up through the paper
body. The user turn (summary instruction *or* a follow-up question) lives
after the breakpoint and changes per call without invalidating the cache.

### Why 1-hour TTL, not 5-minute

The 1-hour TTL doubles the write premium (2× vs 1.25×) but the dominant
failure mode we care about is: user asks for a summary, reads it for 10
minutes, asks a follow-up. The 5-minute TTL evicts that cache and we pay the
write premium again. 1 hour covers realistic reading sessions.

Break-even:
- **5-min TTL**: 2 calls (1.25× write + 0.1× read = 1.35× vs 2× uncached).
- **1-hour TTL**: 3 calls (2× write + 0.2× read = 2.2× vs 3× uncached).

For the "summarize + 3–5 follow-ups" workload this skill targets, 1-hour
wins.

### Verifying cache hits

In `response.usage`:

- `cache_creation_input_tokens` — tokens just written to cache.
- `cache_read_input_tokens` — tokens served from cache.
- `input_tokens` — tokens processed at full price.

The CLI surfaces all three in the `_usage` JSON block. If a follow-up shows
`cache_read_input_tokens: 0`, something changed in the prefix — usually one
of:

- `${INPUT}` differs (different URL / DOI / path → different body).
- `--model` was flipped between calls (cache is per-model).
- A code edit changed `SYSTEM_HEADER` or the `_build_system` layout.

## `messages.parse` vs `messages.create`

- `summarize()` uses `messages.parse` + `PaperSummary` — structured JSON,
  validated server-side.
- `ask()` uses `messages.create` — free-form text response.

Both share the same `system` construction, so the paper body cache is shared
between them. A `summarize` followed by an `ask` on the same paper hits the
cache.

## Tuning knobs (where to edit)

| Want to...                          | Edit                          |
|-------------------------------------|-------------------------------|
| Add/remove schema fields            | `models.py` + `USER_INSTRUCTION` in `summarize.py` |
| Change token truncation             | `_TRUNCATE_CHARS` in `summarize.py` |
| Enable adaptive thinking            | Add `thinking=...` to the `messages.parse` call |
| Change default model                | `DEFAULT_MODEL` in `summarize.py` |
| Change cache TTL                    | `cache_control` dict in `_build_system` |
