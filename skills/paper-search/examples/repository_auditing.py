"""Live example: Repository Auditing, invoked through the shell.

Mirrors exactly how Claude runs this as a Skill — via `uv run` against the
installed console script, not by importing the Python module. This catches
regressions in the SKILL.md contract (arg parsing, stdout format, exit
codes) that a pure-Python call would miss.

Run:
    uv run python examples/repository_auditing.py

Takes ~1–4 minutes. Requires network.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

QUERY = "software repository auditing security supply chain"
SKILL_DIR = Path(__file__).resolve().parent.parent
OUT_PATH = Path(__file__).parent / "repository_auditing.json"


def main() -> None:
    cmd = [
        "uv", "run", "--directory", str(SKILL_DIR), "paper-search",
        QUERY,
        "--top", "15",
        "--from", "2018",
        "--to", "2026",
        "--json",
    ]
    print("$ " + " ".join(_shell_quote(a) for a in cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode not in (0, 4):
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"paper-search exited {proc.returncode}")

    payload = json.loads(proc.stdout)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    papers = payload["papers"]
    print(
        f"Found {payload['total_candidates']} candidates across "
        f"{len(payload['sources_used'])} sources "
        f"({', '.join(payload['sources_used'])})."
    )
    print("-" * 72)
    for i, p in enumerate(papers, 1):
        cites = f"{p['citation_count']:,}" if p.get("citation_count") else "—"
        srcs = ", ".join(p.get("sources") or [])
        sc = p.get("score")
        sc_s = f"{sc:.3f}" if sc is not None else "—"
        print(f" {i:>2}. [{sc_s}] {p['title']}")
        print(f"     cites={cites}  year={p.get('year')}  sources=[{srcs}]")

    if payload.get("errors"):
        print("\nErrors:")
        for e in payload["errors"]:
            print(f"  {e['source']}: {e['error']}")

    print(f"\nExit code: {proc.returncode}  ·  wrote {OUT_PATH}")

    assert papers, "no papers returned — check network"
    assert len(papers) >= 10, f"expected ≥10 papers, got {len(papers)}"
    titles_blob = " || ".join(p["title"].lower() for p in papers)
    relevant = any(
        kw in titles_blob
        for kw in ("repositor", "audit", "supply chain", "vulnerab", "mining", "security")
    )
    assert relevant, "top results don't look topically relevant"
    print("Checks passed.")


def _shell_quote(s: str) -> str:
    if any(c in s for c in " \t\"'"):
        return '"' + s.replace('"', '\\"') + '"'
    return s


if __name__ == "__main__":
    main()
