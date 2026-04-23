from paper_search.sources.arxiv import ArxivSource
from paper_search.sources.crossref import CrossrefSource
from paper_search.sources.github import GithubSource
from paper_search.sources.google_scholar import GoogleScholarSource
from paper_search.sources.openalex import OpenAlexSource
from paper_search.sources.pasa import PasaSource
from paper_search.sources.semantic_scholar import SemanticScholarSource

REGISTRY = {
    "arxiv": ArxivSource,
    "openalex": OpenAlexSource,
    "semantic_scholar": SemanticScholarSource,
    "crossref": CrossrefSource,
    "google_scholar": GoogleScholarSource,
    "pasa": PasaSource,
    "github": GithubSource,
}

DEFAULT_SOURCES = ["arxiv", "openalex", "semantic_scholar"]
ALL_SOURCES = list(REGISTRY.keys())

__all__ = ["REGISTRY", "DEFAULT_SOURCES", "ALL_SOURCES"]
