"""BibTeX emission and BibTeX-query detection."""
from __future__ import annotations

import re
import unicodedata

from paper_search.models import Paper

_STOPWORDS = {
    "a", "an", "the", "of", "for", "and", "or", "in", "on", "to",
    "with", "is", "are", "by", "as",
}
# Chars that are syntactically active in BibTeX field bodies and will break
# compilation if left raw. Title casing-protection with `{…}` is left to the
# caller — most consumers don't care.
_ESCAPE_CHARS = ("\\", "&", "%", "$", "#", "_")


def _ascii_slug(s: str, maxlen: int = 24) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z0-9]+", "", s).lower()
    return s[:maxlen] or "x"


def _first_surname(authors: list[str]) -> str:
    if not authors:
        return "anon"
    first = authors[0]
    if "," in first:
        surname = first.split(",", 1)[0]
    else:
        parts = first.split()
        surname = parts[-1] if parts else first
    return _ascii_slug(surname)


def _first_content_word(title: str) -> str:
    for w in re.findall(r"[A-Za-z0-9]+", title or ""):
        if w.lower() not in _STOPWORDS and len(w) > 1:
            return _ascii_slug(w)
    return "paper"


def cite_key(p: Paper) -> str:
    surname = _first_surname(p.authors)
    word = _first_content_word(p.title or "")
    year = str(p.year) if p.year else "nd"
    return f"{surname}_{word}_{year}"


def _escape(s: str) -> str:
    s = s.replace("\\", r"\textbackslash{}")
    for ch in _ESCAPE_CHARS[1:]:  # skip backslash (already handled)
        s = s.replace(ch, "\\" + ch)
    return s


def _entry_type(p: Paper) -> str:
    if p.venue:
        return "article"
    if p.arxiv_id and not p.doi:
        return "misc"
    if p.doi:
        return "article"
    return "misc"


def to_bibtex(p: Paper) -> str:
    """Render a Paper as a single BibTeX entry."""
    key = cite_key(p)
    etype = _entry_type(p)

    fields: list[tuple[str, str]] = []
    if p.title:
        fields.append(("title", p.title))
    if p.authors:
        fields.append(("author", " and ".join(p.authors)))
    if p.year:
        fields.append(("year", str(p.year)))
    if p.venue:
        # `journal` is the right key for @article; for @misc consumers tolerate it.
        fields.append(("journal" if etype == "article" else "howpublished", p.venue))
    if p.doi:
        fields.append(("doi", p.doi))
    if p.arxiv_id:
        fields.append(("eprint", p.arxiv_id))
        fields.append(("archivePrefix", "arXiv"))
    if p.url and not p.doi:
        fields.append(("url", p.url))
    if p.abstract:
        fields.append(("abstract", p.abstract))

    lines = [f"@{etype}{{{key},"]
    for name, val in fields:
        lines.append(f"  {name} = {{{_escape(val)}}},")
    lines.append("}")
    return "\n".join(lines)


def to_bibtex_all(papers: list[Paper]) -> str:
    return "\n\n".join(to_bibtex(p) for p in papers) + "\n"


_TITLE_PREFIX_RE = re.compile(r"\btitle\s*=\s*", re.IGNORECASE)


def _read_braced(s: str, start: int) -> str | None:
    """Read a balanced `{...}` field starting at `s[start] == '{'`.

    Handles one or more levels of nesting, which BibTeX uses for
    case-protection (`{{Attention} Is All You Need}`).
    """
    if start >= len(s) or s[start] != "{":
        return None
    depth = 0
    out = []
    i = start
    while i < len(s):
        c = s[i]
        if c == "{":
            depth += 1
            if depth > 1:
                out.append(c)
        elif c == "}":
            depth -= 1
            if depth == 0:
                return "".join(out)
            out.append(c)
        else:
            out.append(c)
        i += 1
    return None


def _read_quoted(s: str, start: int) -> str | None:
    if start >= len(s) or s[start] != '"':
        return None
    i = start + 1
    out = []
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            out.append(s[i + 1])
            i += 2
            continue
        if c == '"':
            return "".join(out)
        out.append(c)
        i += 1
    return None


def extract_query_from_bibtex(q: str) -> str | None:
    """If `q` looks like a BibTeX entry, pull out a reasonable search query.

    Returns `None` when the input doesn't look like BibTeX. Otherwise returns
    the title field (braces/quotes stripped, whitespace collapsed). This lets
    users paste a citation and still get a relevant search without adding a
    new flag — BM25 would otherwise tokenize the whole `@article{…}` blob
    including keys, authors, and the DOI, which tends to produce noise.
    """
    if not q:
        return None
    s = q.lstrip()
    if not s.startswith("@"):
        return None
    m = _TITLE_PREFIX_RE.search(s)
    if not m:
        return None
    after = m.end()
    if after >= len(s):
        return None
    body = _read_braced(s, after) if s[after] == "{" else _read_quoted(s, after)
    if body is None:
        return None
    body = re.sub(r"[{}]", "", body)
    body = re.sub(r"\s+", " ", body).strip()
    return body or None
