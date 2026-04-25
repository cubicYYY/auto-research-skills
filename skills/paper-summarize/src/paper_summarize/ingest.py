"""Resolve a paper input (arXiv ID / DOI / URL / local PDF path) to text."""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

ARXIV_ABS_RE = re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
ARXIV_PDF_RE = re.compile(r"arxiv\.org/pdf/(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
ARXIV_BARE_RE = re.compile(r"^(?:arxiv:\s*)?(\d{4}\.\d{4,5})(?:v\d+)?$", re.IGNORECASE)
DOI_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)


@dataclass
class PaperSource:
    kind: str                   # "arxiv" | "doi" | "pdf" | "url"
    identifier: str             # the normalized key for cache / cite purposes
    text: str
    title: Optional[str] = None
    pdf_bytes: Optional[bytes] = None


def load(input_spec: str) -> PaperSource:
    """Resolve any of: arXiv ID / arXiv URL / DOI / arbitrary URL / local PDF path."""
    s = input_spec.strip()
    if not s:
        raise ValueError("empty input")

    # Local file?
    p = Path(s).expanduser()
    if p.exists() and p.is_file():
        return _from_pdf_file(p)

    # arXiv?
    for rx in (ARXIV_ABS_RE, ARXIV_PDF_RE):
        m = rx.search(s)
        if m:
            return _from_arxiv_id(m.group(1))
    m = ARXIV_BARE_RE.match(s)
    if m:
        return _from_arxiv_id(m.group(1))

    # DOI?
    m = DOI_RE.match(s)
    if m:
        return _from_doi(m.group(1))

    # Fallback: treat as URL
    if s.startswith("http://") or s.startswith("https://"):
        return _from_url(s)

    raise ValueError(f"could not interpret input: {input_spec!r}")


def _from_pdf_file(path: Path) -> PaperSource:
    data = path.read_bytes()
    text, title = _extract_pdf(data)
    return PaperSource(
        kind="pdf",
        identifier=str(path.resolve()),
        text=text,
        title=title,
        pdf_bytes=data,
    )


def _from_arxiv_id(arxiv_id: str) -> PaperSource:
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    with httpx.Client(timeout=60, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
        data = r.content
    text, title = _extract_pdf(data)
    return PaperSource(
        kind="arxiv",
        identifier=arxiv_id,
        text=text,
        title=title,
        pdf_bytes=data,
    )


def _from_doi(doi: str) -> PaperSource:
    """Best-effort DOI resolution: try CrossRef metadata for a PDF URL, else
    treat the DOI resolver URL as a generic URL fetch."""
    with httpx.Client(timeout=30, follow_redirects=True, headers={
        "User-Agent": "paper-summarize/0.1"
    }) as c:
        try:
            r = c.get(f"https://api.crossref.org/works/{doi}")
            r.raise_for_status()
            msg = ((r.json() or {}).get("message") or {})
            title = (msg.get("title") or [None])[0]
            # Look for a direct-link PDF in `link`
            pdf_url = None
            for link in msg.get("link") or []:
                if (link.get("content-type") or "").lower() == "application/pdf":
                    pdf_url = link.get("URL")
                    break
            if pdf_url:
                rr = c.get(pdf_url)
                if rr.status_code == 200 and rr.content[:4] == b"%PDF":
                    text, ttl = _extract_pdf(rr.content)
                    return PaperSource(
                        kind="doi", identifier=doi,
                        text=text, title=ttl or title, pdf_bytes=rr.content,
                    )
            # Fall through to generic URL fetch
        except httpx.HTTPError:
            pass

    return _from_url(f"https://doi.org/{doi}")


def _from_url(url: str) -> PaperSource:
    with httpx.Client(timeout=60, follow_redirects=True, headers={
        "User-Agent": "paper-summarize/0.1"
    }) as c:
        r = c.get(url)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "").lower()
        if "pdf" in ctype or r.content[:4] == b"%PDF":
            text, title = _extract_pdf(r.content)
            return PaperSource(kind="url", identifier=url, text=text, title=title, pdf_bytes=r.content)
        # Plain HTML / text — return as-is; model can still summarize
        return PaperSource(kind="url", identifier=url, text=r.text, title=None)


def _extract_pdf(data: bytes) -> tuple[str, Optional[str]]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    title = None
    try:
        meta = reader.metadata
        if meta and meta.title:
            title = str(meta.title).strip() or None
    except Exception:
        title = None
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    text = "\n".join(parts)
    # Light normalization: collapse runs of whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(), title
