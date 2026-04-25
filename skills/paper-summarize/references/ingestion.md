# Ingestion — how each input type is resolved

The CLI accepts four input shapes. `ingest.py` decides which path to take
from the input string alone.

## Dispatch order (first match wins)

1. **Local file path.** If `Path(input).is_file()`, treat as PDF.
2. **arXiv URL** — regex matches `arxiv.org/abs/…` or `arxiv.org/pdf/…`.
3. **Bare arXiv ID** — regex matches `^(arxiv:)?\d{4}\.\d{4,5}(v\d+)?$`.
4. **DOI** — regex matches `^(https?://(dx\.)?doi\.org/)?10\.\d{4,9}/…`.
5. **Generic URL** — anything starting with `http(s)://` falls back to URL fetch.

Anything else raises `ValueError`.

## Per-path details

### Local PDF

- Read bytes, run `pypdf.PdfReader` over pages, concatenate `extract_text()`.
- Extract `metadata.title` if present for the `PaperSource.title`.
- No OCR. If the PDF is a scanned image with no text layer, extraction
  returns empty and the CLI exits 3.

### arXiv (ID or URL)

- Normalize to `arxiv_id` (strip version suffix, strip URL wrapping).
- Fetch `https://arxiv.org/pdf/{arxiv_id}.pdf` with a 60s timeout.
- Feed to `pypdf` as above.
- Note: arXiv throttles aggressively when hit repeatedly. Bulk scripts should
  space calls — this skill assumes interactive use and doesn't retry-loop.

### DOI

1. Look up metadata at `https://api.crossref.org/works/{doi}`.
2. If the response includes a direct PDF link (`link[].content-type ==
   application/pdf`), fetch that URL, validate the `%PDF` magic, and feed to
   `pypdf`. Also capture the CrossRef title.
3. Fallback: `GET https://doi.org/{doi}` and follow redirects. If the final
   response is a PDF, use it. Otherwise treat as HTML (rare, low quality).

CrossRef's direct PDF links are publisher-dependent — many publishers
(Springer, Elsevier, IEEE) require a subscription, in which case this falls
through to the HTML resolver page, which is usually useless for summarization.
Users without institutional access to paywalled papers will have better luck
passing an open-access link or a locally-downloaded PDF.

### Arbitrary URL

- `GET` with follow-redirects and `User-Agent: paper-summarize/0.1`.
- If response is PDF (by `Content-Type` or `%PDF` magic), extract via `pypdf`.
- Otherwise return the raw text — the model will summarize it as-is, but
  expect worse quality than from a real PDF.

## Limits

- **Single fetch per call.** No batching, no parallelism. The caller (Claude)
  should not fan out a dozen summaries at once in a single turn — hit arXiv
  serially, or the host will rate-limit.
- **No OCR.** `pypdf` can't read scanned pages. If you need OCR, preprocess
  with `ocrmypdf` and pass the resulting searchable PDF.
- **No HTML-to-markdown cleanup.** For URL inputs that land on HTML, the raw
  page text is what Claude sees. Boilerplate nav / cookie banners / footers
  are all in there.
- **Paywalled PDFs** fail at the CrossRef direct-link step and fall through
  to an HTML error page.

## Adding a source

If you want to add (e.g.) Semantic Scholar as a PDF source:

1. Add a regex to detect the input shape (e.g. `semanticscholar.org/paper/…`).
2. Add a `_from_s2(...)` function that returns a `PaperSource` with `kind=s2`.
3. Wire it into the dispatch list in `load()`.
4. Ensure `_extract_pdf(bytes)` handles the bytes as-is (it should).

No changes needed in `summarize.py` — it only cares about `text`.

## Failure modes you might hit

| Symptom                                      | Cause / fix |
|----------------------------------------------|-------------|
| `exit 3`: extracted text empty               | Scanned PDF. Run OCR first. |
| `HTTPStatusError: 403` on a DOI              | Paywall. Use an open-access URL or a local PDF. |
| `HTTPStatusError: 429` on repeated arXiv fetches | Backoff 60s. Don't loop. |
| Garbled text with mixed-case noise           | PDF with unusual encoding. `pypdf` best-effort; try converting with `pdftotext -layout` and passing the text file. |
| "could not interpret input"                  | Input matched no dispatch. Pass a full URL or local path. |
