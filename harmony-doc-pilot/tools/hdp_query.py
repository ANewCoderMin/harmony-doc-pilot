"""Query docs and output JSON candidates/evidence/assets."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from hdp_utils import (
    extract_summary,
    load_config,
    norm_path,
    parse_sections,
    read_lines,
    rel_to_root,
    section_text,
)


_STOPWORDS = {
    "the",
    "and",
    "or",
    "for",
    "with",
    "from",
    "into",
    "when",
    "what",
    "how",
    "why",
    "where",
    "which",
    "this",
    "that",
    "这些",
    "那些",
    "怎么",
    "如何",
    "请问",
    "一个",
    "有没有",
    "官方",
    "推荐",
    "候选",
    "列表",
    "给出",
    "筛选",
    "附",
    "来源",
    "配图",
}


def _db_path() -> str:
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    return str((data_dir / "catalog.sqlite").resolve())


def _tokenize(q: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z_][\w]*|[\u4e00-\u9fff]{1,4}", q)
    out = []
    for t in tokens:
        lt = t.lower()
        if lt in _STOPWORDS:
            continue
        if len(t) <= 1:
            continue
        out.append(t)
    return list(dict.fromkeys(out))


def _fts_candidates(conn: sqlite3.Connection, keywords: List[str], topk: int) -> List[Dict]:
    if not keywords:
        return []
    cur = conn.cursor()
    query = " OR ".join(keywords[:10])
    try:
        cur.execute(
            """
            SELECT s.id, s.name, s.kind, s.path, s.section_id, s.line, s.summary, s.tags
            FROM symbols_fts f
            JOIN symbols s ON s.id = f.rowid
            WHERE symbols_fts MATCH ?
            LIMIT ?
            """,
            (query, topk),
        )
        rows = cur.fetchall()
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        rows = []
    return [
        {
            "id": r[0],
            "name": r[1],
            "kind": r[2],
            "path": r[3],
            "section_id": r[4],
            "line": r[5],
            "summary": r[6],
            "tags": r[7],
            "source": "catalog",
        }
        for r in rows
    ]


def _like_candidates(conn: sqlite3.Connection, keywords: List[str], topk: int) -> List[Dict]:
    if not keywords:
        return []
    cur = conn.cursor()
    clauses = []
    params: List[str] = []
    for kw in keywords[:10]:
        clauses.append("name LIKE ? OR summary LIKE ? OR tags LIKE ?")
        params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])
    sql = (
        "SELECT id, name, kind, path, section_id, line, summary, tags FROM symbols WHERE "
        + " OR ".join(clauses)
        + " LIMIT ?"
    )
    params.append(str(topk))
    cur.execute(sql, params)
    rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "name": r[1],
            "kind": r[2],
            "path": r[3],
            "section_id": r[4],
            "line": r[5],
            "summary": r[6],
            "tags": r[7],
            "source": "catalog_like",
        }
        for r in rows
    ]


def _rg_candidates(config: Dict, keywords: List[str]) -> List[Dict]:
    if not keywords:
        return []
    root = Path(config["docs_root"]).resolve()
    include_scopes = [root / p for p in config.get("include_scopes", [])]
    exclude_scopes = config.get("exclude_scopes", [])
    text_exts = config.get("text_extensions", [])
    rg_conf = config.get("ripgrep", {})
    context_lines = int(rg_conf.get("context_lines", 30))
    max_hits_per_file = int(rg_conf.get("max_hits_per_file", 20))
    max_files = int(rg_conf.get("max_files", 200))

    pattern = "|".join(re.escape(k) for k in keywords[:10])
    candidates: List[Dict] = []
    files_seen = set()

    for scope in include_scopes:
        if not scope.exists():
            continue
        cmd = [
            "rg",
            "-n",
            "--no-heading",
            "-m",
            str(max_hits_per_file),
            "-C",
            str(context_lines),
            pattern,
            str(scope),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            return []
        if proc.returncode not in (0, 1):
            continue
        lines = proc.stdout.splitlines()
        for line in lines:
            if not line or line.startswith("--"):
                continue
            m = re.match(r"^(.*?):(\d+):(.*)$", line)
            if not m:
                continue
            path = m.group(1)
            rel = Path(path).resolve().relative_to(root).as_posix()
            if any(rel.startswith(ex + "/") or rel == ex for ex in exclude_scopes):
                continue
            if Path(path).suffix.lower() not in text_exts:
                continue
            if path not in files_seen:
                files_seen.add(path)
                if len(files_seen) > max_files:
                    break
            candidates.append({"path": path, "line": int(m.group(2)), "text": m.group(3), "source": "rg"})

    return candidates


def _load_sections_for_path(conn: sqlite3.Connection, path: str) -> List[Dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, h1, h2, h3, start_line, end_line FROM sections WHERE path = ? ORDER BY start_line",
        (path,),
    )
    rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "h1": r[1],
            "h2": r[2],
            "h3": r[3],
            "start_line": r[4],
            "end_line": r[5],
        }
        for r in rows
    ]


def _section_for_line(sections: List[Dict], line: int) -> Optional[Dict]:
    for sec in sections:
        if sec["start_line"] <= line <= sec["end_line"]:
            return sec
    return None


def _merge_candidates(candidates: List[Dict]) -> List[Dict]:
    seen = {}
    for c in candidates:
        key = (c.get("path"), c.get("section_id"), c.get("name"))
        if key in seen:
            continue
        seen[key] = c
    return list(seen.values())


def _load_assets(conn: sqlite3.Connection, section_id: Optional[int]) -> List[Dict]:
    if not section_id:
        return []
    cur = conn.cursor()
    cur.execute(
        "SELECT path, rel_path, alt FROM assets WHERE section_id = ?",
        (section_id,),
    )
    return [{"abs_path": r[0], "rel_path": r[1], "alt": r[2]} for r in cur.fetchall()]


def query(config_path: str, q: str, topk: int, final: int, with_images: bool) -> Dict:
    config = load_config(config_path)
    docs_root = norm_path(config["docs_root"])
    keywords = _tokenize(q)
    start = time.time()

    conn = sqlite3.connect(_db_path())

    catalog_hits = _fts_candidates(conn, keywords, topk)
    if not catalog_hits:
        catalog_hits = _like_candidates(conn, keywords, topk)

    rg_hits = _rg_candidates(config, keywords)

    evidence: List[Dict] = []
    candidates: List[Dict] = []
    assets: List[Dict] = []

    # Build candidates from catalog hits
    for hit in catalog_hits:
        sections = _load_sections_for_path(conn, hit["path"])
        sec = None
        for s in sections:
            if s["id"] == hit["section_id"]:
                sec = s
                break
        if sec is None:
            sec = _section_for_line(sections, hit["line"])
        section_id = sec["id"] if sec else None

        section_title = {
            "h1": sec["h1"] if sec else None,
            "h2": sec["h2"] if sec else None,
            "h3": sec["h3"] if sec else None,
        }

        candidates.append(
            {
                "name": hit["name"],
                "kind": hit["kind"],
                "path": hit["path"],
                "section": section_title,
                "section_id": section_id,
                "summary": hit.get("summary") or "",
                "score_hint": 50,
                "source": hit["source"],
            }
        )

        if sec:
            lines = read_lines(hit["path"])
            text = section_text(lines, sec["start_line"], sec["end_line"])
            evidence.append(
                {
                    "path": hit["path"],
                    "start_line": sec["start_line"],
                    "end_line": sec["end_line"],
                    "text": text,
                    "section_id": sec["id"],
                }
            )
            if with_images:
                assets.extend(_load_assets(conn, sec["id"]))

    # Build candidates from rg hits
    for hit in rg_hits:
        sections = _load_sections_for_path(conn, hit["path"])
        sec = _section_for_line(sections, hit["line"])
        section_id = sec["id"] if sec else None
        section_title = {
            "h1": sec["h1"] if sec else None,
            "h2": sec["h2"] if sec else None,
            "h3": sec["h3"] if sec else None,
        }
        name = hit["text"].strip()[:80]
        candidates.append(
            {
                "name": name,
                "kind": "snippet",
                "path": hit["path"],
                "section": section_title,
                "section_id": section_id,
                "summary": "",
                "score_hint": 30,
                "source": "rg",
            }
        )
        if sec:
            lines = read_lines(hit["path"])
            text = section_text(lines, sec["start_line"], sec["end_line"])
            evidence.append(
                {
                    "path": hit["path"],
                    "start_line": sec["start_line"],
                    "end_line": sec["end_line"],
                    "text": text,
                    "section_id": sec["id"],
                }
            )
            if with_images:
                assets.extend(_load_assets(conn, sec["id"]))

    merged = _merge_candidates(candidates)

    # Deduplicate evidence by section_id
    seen_evidence = set()
    uniq_evidence = []
    for e in evidence:
        key = (e["path"], e["section_id"])
        if key in seen_evidence:
            continue
        seen_evidence.add(key)
        uniq_evidence.append(e)

    # Deduplicate assets
    seen_assets = set()
    uniq_assets = []
    for a in assets:
        key = (a["abs_path"], a.get("rel_path"))
        if key in seen_assets:
            continue
        seen_assets.add(key)
        uniq_assets.append(a)

    elapsed = int((time.time() - start) * 1000)
    result = {
        "meta": {
            "query": q,
            "keywords": keywords,
            "docs_root": docs_root,
            "include_scopes": config.get("include_scopes", []),
            "exclude_scopes": config.get("exclude_scopes", []),
            "time_ms": elapsed,
        },
        "candidates": merged[:topk],
        "evidence": uniq_evidence,
        "assets": uniq_assets if with_images else [],
        "stats": {
            "rg_hits": len(rg_hits),
            "catalog_hits": len(catalog_hits),
            "merged_sections": len(uniq_evidence),
            "final_candidates": min(len(merged), topk),
        },
    }
    conn.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--q", required=True)
    parser.add_argument("--topk", type=int, default=25)
    parser.add_argument("--final", type=int, default=6)
    parser.add_argument("--with-images", action="store_true")
    args = parser.parse_args()

    result = query(args.config, args.q, args.topk, args.final, args.with_images)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
