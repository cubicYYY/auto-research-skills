"""Summarize a paper via the Claude API using `messages.parse` + prompt caching.

The paper body goes into a cacheable `system` text block. The question (summary
instruction or a follow-up) is the `user` turn. Calling the same paper's body
again on the next request re-uses the cached prefix at ~0.1× input cost.
"""
from __future__ import annotations

import os
from typing import Literal, Optional

import anthropic

from paper_summarize.models import PaperSummary

DEFAULT_MODEL = "claude-sonnet-4-6"
OPUS_MODEL = "claude-opus-4-7"

# Minimum cacheable prefix is 2048 tokens for Sonnet 4.6, 4096 for Opus 4.7.
# Anything short of that will silently skip caching — we still pass the header,
# just log a note if the paper is obviously too short.
_TRUNCATE_CHARS = 180_000  # ~45k tokens; keeps us comfortably under 1M context

SYSTEM_HEADER = (
    "You are a senior research assistant summarizing an academic paper. "
    "Be precise and specific: prefer concrete nouns and numbers over vague prose. "
    "Do not hedge. If the paper does not state something, say so briefly rather "
    "than speculating. Base every claim on the paper text below."
)

USER_INSTRUCTION = (
    "Produce a structured summary of the paper. Fill every field of the output "
    "schema. 'tldr' must be a single sentence under 40 words. 'problem', "
    "'approach', and 'results' are each one tight paragraph. 'limitations' and "
    "'contributions' are bulleted lists. 'keywords' are 5-10 lowercase phrases. "
    "Use the exact numbers and terminology from the paper."
)


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def _build_system(paper_text: str, paper_ref: Optional[str]) -> list[dict]:
    """System is a list of content blocks. The paper body carries a
    `cache_control` breakpoint so repeat calls with the same paper re-use it.

    Putting the breakpoint on the *last* system block also caches everything
    before it, per prompt-caching semantics (render order is tools→system→messages).
    """
    body = paper_text[:_TRUNCATE_CHARS]
    return [
        {"type": "text", "text": SYSTEM_HEADER},
        {
            "type": "text",
            "text": (
                f"--- BEGIN PAPER{f' ({paper_ref})' if paper_ref else ''} ---\n"
                f"{body}\n"
                "--- END PAPER ---"
            ),
            # 1-hour TTL: summaries are often followed by several follow-up
            # questions across a research session. 5-minute default would
            # evict between a summary and the user reading it.
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        },
    ]


Model = Literal["sonnet", "opus"]


def _resolve_model(model: Model) -> str:
    return OPUS_MODEL if model == "opus" else DEFAULT_MODEL


def summarize(
    paper_text: str,
    *,
    model: Model = "sonnet",
    paper_ref: Optional[str] = None,
    max_tokens: int = 4000,
) -> tuple[PaperSummary, dict]:
    """Structured summary. Returns `(summary, usage_dict)`."""
    client = _client()
    response = client.messages.parse(
        model=_resolve_model(model),
        max_tokens=max_tokens,
        system=_build_system(paper_text, paper_ref),
        messages=[{"role": "user", "content": USER_INSTRUCTION}],
        output_format=PaperSummary,
    )
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
    }
    return response.parsed_output, usage


def ask(
    paper_text: str,
    question: str,
    *,
    model: Model = "sonnet",
    paper_ref: Optional[str] = None,
    max_tokens: int = 2000,
) -> tuple[str, dict]:
    """Unstructured follow-up Q&A over the same cached paper body.

    Because `system` is identical to what `summarize()` builds, the paper body
    cache is shared — a follow-up `ask()` right after `summarize()` on the same
    text reads the cache at ~0.1× cost.
    """
    client = _client()
    response = client.messages.create(
        model=_resolve_model(model),
        max_tokens=max_tokens,
        system=_build_system(paper_text, paper_ref),
        messages=[{"role": "user", "content": question}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
    }
    return text, usage
