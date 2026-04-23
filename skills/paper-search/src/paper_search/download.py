from __future__ import annotations

import asyncio
import random
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

from paper_search.models import Paper

MAX_CONCURRENT = 3
RETRIES = 3
BASE_BACKOFF = 2.0


def _safe_filename(p: Paper) -> str:
    base = p.arxiv_id or p.doi or p.title or "paper"
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base)[:120].strip("._-") or "paper"
    return f"{base}.pdf"


async def download_all(papers: list[Paper], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    host_locks: dict[str, asyncio.Lock] = {}

    def host_lock(url: str) -> asyncio.Lock:
        host = urlparse(url).netloc
        if host not in host_locks:
            host_locks[host] = asyncio.Lock()
        return host_locks[host]

    async with httpx.AsyncClient(
        timeout=60, follow_redirects=True, headers={"User-Agent": "paper-search"}
    ) as client:
        async def one(p: Paper) -> None:
            url = p.pdf_url or _pdf_from_arxiv(p.arxiv_id)
            if not url:
                return
            dest = out_dir / _safe_filename(p)
            if dest.exists():
                p.downloaded_to = str(dest)
                return
            async with sem:
                async with host_lock(url):
                    ok = await _fetch(client, url, dest)
                    if ok:
                        p.downloaded_to = str(dest)
                    await asyncio.sleep(random.uniform(1.0, 3.0))

        await asyncio.gather(*(one(p) for p in papers))


def _pdf_from_arxiv(arxiv_id: Optional[str]) -> Optional[str]:
    if not arxiv_id:
        return None
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


async def _fetch(client: httpx.AsyncClient, url: str, dest: Path) -> bool:
    for attempt in range(RETRIES):
        try:
            r = await client.get(url)
            if r.status_code in (429, 500, 502, 503, 504):
                await asyncio.sleep(BASE_BACKOFF * (2**attempt))
                continue
            r.raise_for_status()
            ctype = r.headers.get("content-type", "").lower()
            if "pdf" not in ctype and not url.lower().endswith(".pdf"):
                return False
            dest.write_bytes(r.content)
            return True
        except httpx.HTTPError:
            await asyncio.sleep(BASE_BACKOFF * (2**attempt))
    return False
