"""Offline example: rank a synthetic batch against the query 'attention'.

Expected behavior:
  - "Attention Is All You Need" is #1 (highly cited AND on-topic).
  - FlashAttention / sparse-attention variants land in the top 4.
  - Off-topic papers sink.

Run:
    uv run python examples/attention_offline.py
"""
from __future__ import annotations

from paper_search.core import score_batch
from paper_search.models import Paper


def main() -> None:
    batch = [
        Paper(
            title="Attention Is All You Need",
            abstract=(
                "The dominant sequence transduction models are based on complex "
                "recurrent or convolutional neural networks. We propose a new simple "
                "network architecture, the Transformer, based solely on attention "
                "mechanisms, dispensing with recurrence and convolutions entirely."
            ),
            year=2017,
            arxiv_id="1706.03762",
            citation_count=173000,
            sources=["arxiv", "semantic_scholar"],
        ),
        Paper(
            title="FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness",
            abstract="We propose FlashAttention, an IO-aware exact attention algorithm.",
            year=2022,
            arxiv_id="2205.14135",
            citation_count=4050,
            sources=["arxiv"],
        ),
        Paper(
            title="FlashAttention-2: Faster Attention with Better Parallelism",
            abstract="Better parallelism and work partitioning for attention on modern GPUs.",
            year=2023,
            arxiv_id="2307.08691",
            citation_count=2516,
            sources=["arxiv"],
        ),
        Paper(
            title="Longformer: The Long-Document Transformer",
            abstract="Longformer's attention mechanism is a drop-in replacement with sparse attention for long documents.",
            year=2020,
            arxiv_id="2004.05150",
            citation_count=5200,
            sources=["arxiv"],
        ),
        Paper(
            title="Generating Long Sequences with Sparse Transformers",
            abstract="Sparse attention patterns reduce the quadratic cost of self-attention.",
            year=2019,
            arxiv_id="1904.10509",
            citation_count=2100,
            sources=["arxiv"],
        ),
        Paper(
            title="CBAM: Convolutional Block Attention Module",
            abstract="A simple attention module for convolutional networks.",
            year=2018,
            arxiv_id="1807.06521",
            citation_count=22000,
            sources=["arxiv"],
        ),
        Paper(
            title="ResNet: Deep Residual Learning for Image Recognition",
            abstract="We present a residual learning framework to ease the training of deep networks.",
            year=2016,
            arxiv_id="1512.03385",
            citation_count=200000,
            sources=["arxiv"],
        ),
        Paper(
            title="A Survey of Soil Microbial Diversity in Alpine Meadows",
            abstract="We survey microbial communities across alpine meadow soils.",
            year=2021,
            arxiv_id="2101.00000",
            citation_count=30,
            sources=["arxiv"],
        ),
    ]

    scored = score_batch(batch, "attention", year_to=2026)

    print("Ranking for query: 'attention'")
    print("-" * 72)
    for i, p in enumerate(scored, 1):
        cites = f"{p.citation_count:,}" if p.citation_count else "—"
        print(f" {i:>2}. [{p.score:.3f}] {p.title}")
        print(f"     cites={cites}  year={p.year}  arXiv:{p.arxiv_id}")

    titles = [p.title for p in scored]
    assert titles[0] == "Attention Is All You Need", \
        f"expected Vaswani at top, got: {titles[0]}"
    assert any("FlashAttention" in t for t in titles[:5]), titles[:5]
    assert any("Sparse" in t or "Longformer" in t for t in titles[:7]), titles[:7]
    off_topic = "A Survey of Soil Microbial Diversity in Alpine Meadows"
    assert titles.index(off_topic) == len(titles) - 1, \
        "off-topic soil paper should rank last"
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
