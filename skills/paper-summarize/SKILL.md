---
name: paper-summarize
description: Summarize academic papers into structured sections (TL;DR, problem, approach, results, contributions, limitations, keywords). Accepts arXiv IDs, DOIs, URLs, or local PDFs. Use when the user asks to "summarize this paper", "explain what this paper does", "TL;DR this arXiv link", "give me the key findings of X", or pastes a paper reference after using `paper-search`. Also use when the user asks follow-up questions about a paper they just had summarized.
license: MIT
allowed-tools: Read, WebFetch, Skill, Bash(date *)
metadata:
  version: "0.2.0"
---

# paper-summarize

Produce a structured summary of a paper. Everything runs **inline in the
conversation** — extract the paper text with the tools below, then write the
summary yourself. No external API call, no CLI invocation from this skill.

## Runtime context

- Current year: !`date +%Y`

## Inputs

`${INPUT}` — one of:

- An arXiv ID (`1706.03762`) or arXiv URL (`https://arxiv.org/abs/1706.03762`).
- A DOI (`10.48550/arXiv.1706.03762`) or DOI URL.
- Any HTTPS URL — PDF or landing page.
- An absolute local PDF path.

## Procedure

1. **Extract the paper text.** Try these in order; use the first one that
   applies:
   - **If a `pdf` skill is loaded** — delegate to it and take back the
     extracted text. This is the preferred path: dedicated PDF skills handle
     scanned pages, complex layouts, and tables better than plain reads.
   - **Python libraries** — use Python's libraries like `pypdf` `pdf2image` `pdfplumber` if really needed.
   - **Local PDF path** — use `Read` on the path. Claude Code's `Read` can
     ingest `.pdf` files directly.
   - **arXiv ID / arXiv URL** — normalize to
     `https://arxiv.org/pdf/{id}.pdf` and `WebFetch` it.
   - **DOI** — `WebFetch` `https://doi.org/{doi}` and follow to the PDF. If
     the publisher is paywalled and the page is HTML, tell the user and stop
     — don't summarize a login wall.
   - **Any other URL** — `WebFetch` it.

   If the extraction comes back empty or almost-empty (typical for scanned
   PDFs with no text layer), stop. Do not retry. Tell the user the PDF has
   no extractable text and suggest an OCR pass (e.g. `ocrmypdf`) first.

2. **Write the structured summary.** Read the extracted text and produce
   every field below from the paper itself — no placeholders, no guesses:

   | Field           | Shape                                                                    |
   |-----------------|--------------------------------------------------------------------------|
   | `title`         | As stated by the authors.                                                |
   | `authors`       | First-author-first list, "et al." after the third when displaying.       |
   | `tldr`          | One sentence, ≤ 40 words, plain language, no hedging.                    |
   | `problem`       | One tight paragraph: the gap or question the paper addresses.            |
   | `approach`      | One tight paragraph: method, model, architecture, technique.             |
   | `results`       | One paragraph with the paper's actual numbers (metrics, datasets, deltas).|
   | `contributions` | Bulleted list of distinct contributions.                                 |
   | `limitations`   | Bulleted list — acknowledged by the authors, or evident from the method. |
   | `keywords`      | 5–10 lowercase topical phrases useful for search.                        |

3. **Format for the user.** Don't dump every field verbatim. Default
   output is:
   - **Title** (bold) + first 3 authors ("et al." if there are more) + year
     if known.
   - **TL;DR.** one sentence.
   - 2–4 bullets pulled from `contributions` + `limitations` combined.
   - A link back to the paper if the input was an arXiv ID / URL / DOI.

   Include `results`, `approach`, or `problem` paragraphs only when the
   user asked for them specifically, or asked for a "full" / "detailed"
   summary.

4. **Follow-up questions on the same paper.** Answer directly from the
   extracted text you already have in this conversation. Only re-extract
   if that context has been dropped (e.g. after a long gap or a compaction).

## Trigger → action table

| User says / asks                                                         | Action                                                         |
|--------------------------------------------------------------------------|----------------------------------------------------------------|
| "Summarize / TL;DR / explain this paper", gives an arXiv/DOI/URL/PDF     | Extract → structured summary → short format.                   |
| "What does `<paper>` say about `<topic>`?"                               | Extract (if not already) → answer directly from the text.      |
| Pastes an arXiv link after a `paper-search` call                         | Extract → structured summary.                                  |
| "Give me the results / F1 / accuracy / numbers"                          | Focus the output on `results` verbatim.                        |
| "Read this PDF" + filepath                                               | Extract → structured summary.                                  |
| "Deep read" / "careful analysis"                                         | Produce the full field set (including `approach` + `problem`). |
| Follow-up question on the same paper                                     | Reuse in-context text; don't re-extract.                       |
| "Compare this to the previous paper we summarized"                       | Extract both, then synthesize in your own response.            |

## Never-do rules

- Never dump all nine fields verbatim unless the user asked for the raw
  structured output. Extract the useful bits, don't flood.
- Never invent numbers or claims the paper doesn't state. If something
  isn't in the text, say so plainly instead of guessing.
- Never claim the summary is "verified" or "fact-checked" — it's a read
  of the paper, not a review.
- Never retry on an empty extraction. Tell the user and stop.
- Never summarize a login / paywall HTML page and present it as the
  paper's content. If the fetch lands on one, say so.

## Composes with `paper-search`

When the user has summarized ≥ 2 papers and wants broader coverage, the
`keywords` lists you produced can seed a second-pass `paper-search`. See
`paper-search/SKILL.md` → "Two-pass keyword-boosted search" for the exact
procedure. The only contract this skill owes that loop is: each summary
exposes a `keywords` list of 5–10 lowercase domain phrases.
