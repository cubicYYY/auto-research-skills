---
name: paper-summarize
description: Summarize academic papers into a structured technical brief (problem, method/components, key design decisions & formulas, evaluation/metrics, contributions). Accepts arXiv IDs, DOIs, URLs, or local PDFs — one or many. Use when the user asks to "summarize this paper", "explain what this paper does", "TL;DR this arXiv link", "give me the key findings of X", or pastes a paper reference after using `paper-search`. Also use when the user asks follow-up questions about a paper they just had summarized.
license: MIT
allowed-tools: Read, Write, WebFetch, Skill, Bash(date *), Bash(python *), Bash(uv *), Bash(mkdir -p *), Bash(ls *)
metadata:
  version: "0.4.0"
---

# paper-summarize

Produce a structured, technical summary of a paper. Everything runs
**inline in the conversation** — extract the paper text with the tools
below, then write the summary yourself. No external API call, no CLI
invocation from this skill.

## Runtime context

- Current year: !`date +%Y`

## Inputs

`${INPUT}` — one **or many** of:

- An arXiv ID (`1706.03762`) or arXiv URL (`https://arxiv.org/abs/1706.03762`).
- A DOI (`10.48550/arXiv.1706.03762`) or DOI URL.
- Any HTTPS URL — PDF or landing page.
- An absolute local PDF path.

`${SUMMARY_DIR}` — *optional* absolute directory where each summary is
written as a Markdown file. Sources, in order of preference:

1. A directory the user explicitly named for summaries
   ("save the summaries to `…`", "write them into `…`").
2. The PDF directory that `paper-search` downloaded into — summaries
   go **alongside the PDFs** when `paper-search` triggered this skill
   and passed its `-o` directory through.
3. Unset → behavior depends on how many inputs there are (see
   "Batch mode" below).

## Procedure

1. **Decide: single input or batch?**
   - `${INPUT}` count == 1 → produce the summary **inline** in chat.
     Only write to disk if `${SUMMARY_DIR}` is explicitly set.
   - `${INPUT}` count ≥ 2 → this is **batch mode**. See "Batch mode"
     below before doing anything else.

2. **Extract the paper text.** For each input, try these in order and
   use the first that applies:
   - **If a `pdf` skill is loaded** — delegate to it and take back the
     extracted text. Preferred path: dedicated PDF skills handle
     scanned pages, complex layouts, and tables better than plain
     reads.
   - **Python libraries** — use `pypdf`, `pdf2image`, or `pdfplumber`
     if really needed (complex layouts, table extraction, or when
     `Read`'s PDF output is garbled).
   - **Local PDF path** — use `Read` on the path. Claude Code's
     `Read` can ingest `.pdf` files directly.
   - **arXiv ID / arXiv URL** — normalize to
     `https://arxiv.org/pdf/{id}.pdf` and `WebFetch` it.
   - **DOI** — `WebFetch` `https://doi.org/{doi}` and follow to the
     PDF. If the publisher is paywalled and the page is HTML, tell
     the user and stop — don't summarize a login wall.
   - **Any other URL** — `WebFetch` it.

   If extraction comes back empty or almost-empty (typical for scanned
   PDFs with no text layer), skip that input. Do not retry. In batch
   mode, note the skip in the report and keep going.

3. **Produce the summary.** Default output follows the template below.
   Every section is required unless the user asked for brief mode (see
   "Brief mode"). Prefer the paper's own vocabulary, numbers, and
   formulas over paraphrase. Do not invent anything the paper doesn't
   state.

4. **Write to disk if `${SUMMARY_DIR}` is set.** See "Writing summary
   files".

5. **Follow-up questions on the same paper.** Answer directly from the
   extracted text already in this conversation. Only re-extract if
   that context was dropped (e.g. after a long gap or a compaction).

## Batch mode

When the user gives ≥ 2 inputs:

1. **If `${SUMMARY_DIR}` is already known** (user named it, or
   `paper-search` passed one through) — go ahead; write one Markdown
   file per paper; emit a short inline roll-up (one line per paper).
2. **If `${SUMMARY_DIR}` is unknown** — **stop and ask** before
   summarizing. Use this message verbatim:

   > You've given me N papers. Where should I save the summaries?
   > Reply with an absolute directory path, or "inline" to dump all
   > N summaries into chat instead.

   Wait for the reply.
   - Absolute path → `mkdir -p` and use it as `${SUMMARY_DIR}`.
   - `"inline"` / "in chat" / "here" → proceed inline, but warn the
     user that N long briefs in one response is going to be a lot.
     Offer brief mode (see "Brief mode") as an alternative.
   - Anything else → ask again; don't guess.

3. **Never** guess a directory ("I'll put them in `./summaries`") —
   it lands inside the skill folder if you're wrong, and the user
   can't find them.

### Context-window protocol (critical)

Batch summarization can blow up your context fast. A single 45k-token
paper fully extracted, summarized, and kept in memory is already
substantial; 10 papers held simultaneously will typically push past
the point where quality degrades or earlier turns get dropped.

**Process papers one-by-one, not in parallel:**

1. Pick the next unprocessed paper.
2. Extract its text (one source at a time — `Read`, `WebFetch`, or
   the `pdf` skill).
3. Write the full summary to `${SUMMARY_DIR}/<slug>.md` via `Write`.
4. **Drop the extracted text.** Do not keep it in working memory for
   later papers — the file on disk is the authoritative copy.
5. Emit a single roll-up line (`- <title> → <path>`) as you go so the
   user sees progress.
6. Move to the next paper. Repeat.

This pattern keeps the working-set roughly bounded to one paper's
text at a time, independent of batch size.

**Never do the following in batch mode:**

- Never extract all N papers up front and then summarize. That holds
  N × 45k tokens in context and is the single biggest way to
  blow up a batch run.
- Never skip writing to disk and carry summaries "for the roll-up"
  — the final per-paper line only needs the title and path, which
  you already know from the filename.
- Never re-read a summary file you just wrote to "verify" it. Trust
  the `Write`.
- Never paste the full summary back into chat after writing it to
  disk unless the user asks. The roll-up line is the receipt.

**If the user chose `"inline"`** (≥ 2 papers, no disk) — the same
one-by-one rule applies, but be even more conservative: switch to
brief mode (one TL;DR + 2 bullets per paper) if N ≥ 4, and tell the
user you're doing so. Full briefs for ≥ 4 papers inline is almost
always a mistake.

## Writing summary files

When `${SUMMARY_DIR}` is set:

1. `mkdir -p "${SUMMARY_DIR}"` once, upfront.
2. For each paper, choose a stable filename:
   - Prefer the arXiv ID: `2308.14460.md`.
   - Else the DOI, slugified: `10-48550-arxiv-2308-14460.md`.
   - Else a title slug, truncated to 60 chars:
     `steam-simulating-the-interactive-behavior-of-programmers.md`.
   - Collisions → append `-2`, `-3`, …
3. Write the full template (not brief mode) via `Write`. The file's
   content is exactly what you would have printed inline — the `===`
   banners, every section, no preamble, no trailing chatter.
4. **Match filenames to downloaded PDFs when possible.** If
   `paper-search` downloaded `2308.14460.pdf` into the same directory,
   your summary should be `2308.14460.md` — same basename.
5. After all writes, emit one inline line per paper:

   ```
   - <title> → <abs path to .md>
   ```

   And a closing line: `Wrote N summaries to ${SUMMARY_DIR}/`.

## Output template

Use this exact shape. The `===` banners are literal — keep them.
Omit a header line (e.g. `DOI:`) when the paper doesn't have that
identifier; don't write `(not available)`.

```
Paper: <title>[ — <subtitle>]
Authors: <first>, <second>, <third>[, et al.]
Year: <year>[; <journal/conf version year>, <venue>]
arXiv: <id if arxiv>
DOI: <doi if available and distinct from arxiv>

================================================================
PROBLEM SOLVED
================================================================
<One or two paragraphs. Name the gap or question in concrete terms:
what's broken, what's missing, what prior approaches get wrong. State
the motivating problem the way the paper frames it.>

================================================================
METHOD / COMPONENTS
================================================================
<Numbered or lettered components. For each: name, role, inputs,
outputs, and sub-steps for pipelines. Preserve the paper's own
component names and vocabulary. Include stage order for multi-stage
systems.>

================================================================
KEY DESIGN DECISIONS / FORMULAS
================================================================
- <Bullet points. Hyperparameters, loss functions, algorithmic
  choices, base models, pinned versions, token budgets, decoding
  strategies, retrieval configs, ablation-relevant knobs.>
- <Include numerical values exactly as given (temperatures, top-k,
  sequence lengths, learning rates, epoch counts, etc.).>
- <Include formulas in plain text if short, or name them (e.g.
  "BM25 over buggy method + buggy line; top-3 kept").>

================================================================
EVALUATION / METRICS
================================================================
Benchmark: <names, splits, sizes, filters>

Metrics:
  - <metric name>: <definition / direction (higher or lower is better)>
  - ...

Main results (<metric set>):
  <method>           <score1> / <score2> / <score3>
  <method>           ...
  <paper's system>   ...   (mark SOTA / best if applicable)
  → <deltas vs strongest baseline, in pp or %>

Ablation:
  <compact table of component-added-on-top, with deltas>

<Include uniqueness counts, generalization to other benchmarks, or
error analysis when the paper reports them.>

================================================================
CONTRIBUTIONS (paper's framing)
================================================================
- <As the authors enumerate them — don't invent.>
- <Keep each bullet to one sentence.>
```

### Section-by-section expectations

- **PROBLEM SOLVED.** State the problem; don't describe the solution
  here. If the paper has a concrete motivating example, name it.
- **METHOD / COMPONENTS.** Reproduce the architecture. A reader who
  skipped the paper should know component names, stage order, and what
  each stage receives and emits. No prose-only description of a
  multi-stage system — use a structured list.
- **KEY DESIGN DECISIONS / FORMULAS.** This is the section that
  distinguishes a technical brief from a blog post. Hyperparameters,
  decoding settings, pinned model versions, retrieval details, loss
  terms. If the paper pinned a specific model version
  (e.g. `gpt-3.5-turbo-0301`), say so.
- **EVALUATION / METRICS.** Benchmark name(s), split sizes, metrics
  with directions, main table reproduced compactly, ablations with
  deltas, any uniqueness / generalization numbers.
- **CONTRIBUTIONS.** Mirror the paper's own list. Don't editorialize.

## Brief mode

When the user asks for a TL;DR, a one-liner, an elevator pitch, or
otherwise signals they want less — replace the full template with:

```
<Title> — <first 3 authors, et al. if more> (<year>)
TL;DR: <one sentence, ≤ 40 words, plain language, no hedging.>
- <contribution or limitation bullet>
- <contribution or limitation bullet>
```

Promote to the full template if the user then asks for "more", "full
summary", "details", or follows up with a methods question.

## Keywords (for `paper-search` composition)

The `paper-search` two-pass keyword-boost loop needs 5–10 lowercase
domain phrases per paper. **Keywords are not part of the default
output.** Only emit them when:

- The user asks for keywords / tags / labels, or
- You are feeding `paper-search` next (see "Composes with
  `paper-search`").

Format, when emitted:

```
Keywords: <kw1>, <kw2>, <kw3>, ...
```

Pick phrases the paper itself uses — method names, task names, domain
terms — not generic ML vocabulary.

## Trigger → action table

| User says / asks                                                          | Action                                                         |
|---------------------------------------------------------------------------|----------------------------------------------------------------|
| "Summarize / explain this paper", gives **one** arXiv/DOI/URL/PDF         | Extract → full template, inline.                               |
| Gives **≥ 2** papers, no directory                                         | Ask where to save (see "Batch mode"); then extract + write.    |
| Gives **≥ 2** papers, names a directory                                    | Use that as `${SUMMARY_DIR}`; extract + write; roll-up inline. |
| `paper-search` invoked this skill with a PDF directory                     | Use that as `${SUMMARY_DIR}`; summaries go alongside PDFs.     |
| "TL;DR / one-liner / elevator pitch"                                      | Extract → brief mode.                                          |
| "What does `<paper>` say about `<topic>`?"                                | Extract (if not already) → answer directly from the text.      |
| Pastes an arXiv link after a `paper-search` call                          | Extract → full template.                                       |
| "Give me the results / F1 / accuracy / numbers"                           | Lead with the EVALUATION / METRICS section; drop the rest.     |
| "Read this PDF" + filepath                                                | Extract → full template.                                       |
| "Deep read" / "careful analysis" / "every detail"                         | Full template; expand KEY DESIGN DECISIONS with every knob.    |
| Follow-up question on the same paper                                      | Reuse in-context text; don't re-extract.                       |
| "Compare this to the previous paper we summarized"                        | Extract both if needed, then synthesize in your own response.  |
| "Give me keywords for `<paper>`" or next step is another `paper-search`   | Emit the `Keywords:` line (see "Keywords").                    |

## Never-do rules

- Never invent numbers, dataset sizes, hyperparameters, or results the
  paper doesn't state. If a field can't be filled from the paper,
  write `(not reported)` under it.
- Never paraphrase a formula into prose if the paper gives the
  formula. Reproduce it.
- Never drop the `===` banner separators — downstream tools and the
  user's eyes both rely on them.
- Never claim the summary is "verified" or "fact-checked" — it's a
  read of the paper, not a review.
- Never retry on an empty extraction. Tell the user (or note in the
  batch report) and skip.
- Never summarize a login / paywall HTML page and present it as the
  paper's content. If the fetch lands on one, say so.
- Never emit the `Keywords:` line inside the full template — it's a
  separate, on-demand block.
- Never assume a summary directory. If the user gave multiple papers
  without one, **ask**. A wrong guess lands inside the skill folder.
- Never write summaries to a relative path. `${SUMMARY_DIR}` must be
  absolute before `Write`.
- Never extract multiple papers in parallel in batch mode. Process
  one-by-one, write each to disk, drop its text, then move on. See
  "Context-window protocol" — parallel extraction blows up the
  context window on any batch larger than ~3 papers.

## Composes with `paper-search`

`paper-search` invokes this skill by default (see its SKILL.md →
"Two-pass keyword-boosted search"). When it does, it passes through
its `-o` directory as `${SUMMARY_DIR}` so summaries land **alongside
the downloaded PDFs** with matching basenames (e.g. `2308.14460.pdf`
next to `2308.14460.md`). If `paper-search` ran without `-o` (no PDFs
downloaded), it may still call this skill for the two-pass keyword
loop — in that case summaries stay inline and only the `Keywords:`
lines are harvested.
