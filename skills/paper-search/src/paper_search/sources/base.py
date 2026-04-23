from __future__ import annotations

from typing import Protocol, runtime_checkable

from paper_search.models import Paper


@runtime_checkable
class Source(Protocol):
    name: str
    needs_key: bool

    async def search(
        self,
        query: str,
        *,
        year_from: int,
        year_to: int,
        limit: int,
    ) -> list[Paper]: ...
