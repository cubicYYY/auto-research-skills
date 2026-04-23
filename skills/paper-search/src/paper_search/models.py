from __future__ import annotations

import re
import unicodedata
from typing import Optional

from pydantic import BaseModel, Field


class Paper(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    citation_count: Optional[int] = None
    sources: list[str] = Field(default_factory=list)
    score: Optional[float] = None
    downloaded_to: Optional[str] = None

    def dedupe_key(self) -> str:
        if self.doi:
            return f"doi:{canonical_doi(self.doi)}"
        if self.arxiv_id:
            return f"arxiv:{canonical_arxiv_id(self.arxiv_id)}"
        return f"title:{normalized_title_key(self.title)}"


_DOI_PREFIX_RE = re.compile(r"^https?://(?:dx\.)?doi\.org/", re.IGNORECASE)


def canonical_doi(doi: str) -> str:
    return _DOI_PREFIX_RE.sub("", doi.strip()).lower()


_ARXIV_VERSION_RE = re.compile(r"v\d+$", re.IGNORECASE)


def canonical_arxiv_id(arxiv_id: str) -> str:
    s = arxiv_id.strip()
    s = re.sub(r"^arxiv:\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^https?://arxiv\.org/abs/", "", s, flags=re.IGNORECASE)
    s = _ARXIV_VERSION_RE.sub("", s)
    return s.lower()


def normalized_title_key(title: str) -> str:
    decomposed = unicodedata.normalize("NFKD", title)
    stripped = decomposed.encode("ascii", "ignore").decode("ascii")
    alnum = re.sub(r"[^a-z0-9]+", "", stripped.lower())
    return alnum[:50]
