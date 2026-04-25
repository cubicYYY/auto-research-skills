# GitHub rate limits & token scopes

## Search API

GitHub's search endpoints have their **own, separate** rate limit from the
rest of the API:

| Auth                                 | Search limit  | Other API limit |
|--------------------------------------|---------------|-----------------|
| No token                             | 10 req/min    | 60 req/hour     |
| Personal access token (PAT)          | 30 req/min    | 5,000 req/hour  |
| Fine-grained token                   | 30 req/min    | 5,000 req/hour  |
| GitHub App installation token        | 30 req/min    | 15,000 req/hour |

Per run this skill issues:

- 1 × repo search (`best-match`)
- 1 × repo search (`sort=stars`)
- 1 × code search (only if token)
- Up to `--readme-for` × README fetches (default 10)
- Up to 20 × repo-detail fetches if code-search surfaces unknown repos

A token run ≈ 35–40 requests; ~3 concurrent runs will trigger search
rate-limiting without a token.

## Required token scopes

For this skill, minimum:

- Classic PATs: `public_repo` (read-only).
- Fine-grained PATs: select **"Public Repositories (read-only)"**.

**No `repo` (private access) is needed** unless you want the skill to
return private repositories you own. The code-search endpoint respects the
token's visibility — a public-only token searches only public code.

## Diagnosing errors

| Symptom                                                           | Cause                                                                       |
|-------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `HTTP 403: rate limit exceeded`                                   | Unauthenticated run hit 10/min, or authenticated hit 30/min.                |
| `HTTP 422: validation failed` on code-search                      | Anonymous code-search (not allowed). Set `GITHUB_TOKEN`.                    |
| `HTTP 401: bad credentials`                                       | Expired / revoked token. Re-create PAT.                                     |
| `HTTP 200` with empty `items`                                     | Query too narrow (zero matches), or all filtered by `--min-stars`.          |
| Code-search `errors[]` entry only, repo search fine               | Token lacks read permission on a repo that matched. Usually safe to ignore. |

## Multi-run strategies

For a thorough novelty check you often want to issue 3–5 queries. To stay
well under the rate limit without waiting:

1. **Use a dedicated PAT** for agentic runs — don't share one token
   across a developer's daily work and a loop of `similar-code-search`.
2. **Cache results** at the caller level if you re-query the same project
   repeatedly. The skill itself does not cache.
3. **Check the response headers** `x-ratelimit-remaining` and
   `x-ratelimit-reset` if you're scripting around it. The CLI doesn't
   expose these yet; set `GITHUB_TOKEN` and spread calls over time.

## Comparing with `gh` CLI

The `gh search` CLI is also a valid interactive tool, but this skill
differs in two ways:

- It **merges** repo + code + stars-sorted results into one ranked list.
- It applies a **BM25 + popularity + recency + code-match** score, so the
  output is agent-parseable JSON with explainable components.

Use `gh search repos …` for quick interactive browsing; use this skill for
structured novelty checks before making a go/no-go decision.
