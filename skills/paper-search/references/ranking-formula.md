# Ranking formula

One weighted sum, all components in `[0, 1]`:

```
score(p) = 0.60 · text(p) + 0.30 · cite(p) + 0.10 · recency(p)
```

## Components

**`text(p)`** — Okapi BM25 (`rank-bm25`, `k1=1.5, b=0.75`) over the tokenized
`title + " " + abstract` of the deduped candidate pool, queried with the
tokenized user query. Raw BM25 is unbounded and batch-dependent; we squash
with a sigmoid around a fixed pivot to get an **absolute** score:

```
text(p) = 1 / (1 + exp(-0.5 · (bm25(p) - 6)))
```

Why sigmoid, not batch max-norm: relative normalization makes a weak match in
a weak batch look as strong as an excellent one. The sigmoid preserves
ordering but anchors score magnitude.

**`cite(p)`** — `log1p(citations) / log1p(batch_max)` when a count is known,
else `0.5` (neutral). Heavy-tail compression with log1p so Vaswani-level
(~170k cites) doesn't drown Flash-level (~4k).

Sources that don't carry citation counts (arXiv, PaSa, GitHub refs) get the
neutral `0.5`, not `0`. Rationale: arXiv-only papers shouldn't be penalised
against OpenAlex/S2 hits purely for lacking metadata.

**`recency(p)`** — Gaussian decay centred on the upper year bound (`--to`):

```
recency(p) = exp( - (year_to - year(p))² / 18 )     σ = 3
```

Paper from `year_to` → 1.0, from `year_to - 3` → ~0.61, from `year_to - 6` →
~0.14. Unknown year → 0.5 (neutral).

**Tie-break**: citation count, then recency.

## Worked example

Query `"diffusion models for protein design"`, `year_to = 2026`.
*RFdiffusion* (2023, 1,240 cites, raw BM25 = 14.2). Batch max cites = 20,000.

```
text    = 1 / (1 + exp(-0.5·(14.2 - 6)))   ≈ 0.984
cite    = log1p(1240) / log1p(20000)        ≈ 0.720
recency = exp(-(2026-2023)²/18)             ≈ 0.607

score = 0.60·0.984 + 0.30·0.720 + 0.10·0.607 ≈ 0.867
```

## Tuning the weights

Constants live in `src/paper_search/core.py`:

```python
TEXT_WEIGHT     = 0.60
CITE_WEIGHT     = 0.30
RECENCY_WEIGHT  = 0.10
BM25_PIVOT      = 6.0     # sigmoid centre
BM25_SCALE      = 0.5     # sigmoid steepness
RECENCY_SIGMA_SQ = 9.0    # σ = 3 years
```

Common tweaks:
- Bump `RECENCY_WEIGHT` (and drop `CITE_WEIGHT`) when the user cares about
  *recent* work above *highly-cited* work.
- Raise `BM25_PIVOT` to make the sigmoid stricter — weak text matches get
  pushed further down.
- Set `CITE_WEIGHT = 0` for coverage queries where citation bias would hide
  new work.
