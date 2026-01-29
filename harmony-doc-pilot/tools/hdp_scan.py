"""Scan docs and build/update catalog."""

from __future__ import annotations

import argparse
import os
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from hdp_utils import (
    Asset,
    Section,
    Symbol,
    build_abs_path,
    extract_assets,
    extract_summary,
    extract_symbols,
    file_sha1,
    iter_text_files,
    load_config,
    norm_path,
    parse_sections,
    read_lines,
    rel_to_root,
)


def _db_path() -> str:
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str((data_dir / "catalog.sqlite").resolve())


def _init_db(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            mtime REAL,
            sha1 TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT,
            h1 TEXT,
            h2 TEXT,
            h3 TEXT,
            start_line INTEGER,
            end_line INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            kind TEXT,
            path TEXT,
            section_id INTEGER,
            line INTEGER,
            tags TEXT,
            summary TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT,
            owner_path TEXT,
            section_id INTEGER,
            alt TEXT,
            rel_path TEXT,
            line INTEGER
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sections_path ON sections(path)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_symbols_path ON symbols(path)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_assets_owner ON assets(owner_path)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name)")
    try:
        cur.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts
            USING fts5(name, summary, tags, content='symbols', content_rowid='id')
            """
        )
    except sqlite3.OperationalError:
        pass
    conn.commit()


def _load_prev_file(conn: sqlite3.Connection, path: str) -> Optional[Tuple[float, str]]:
    cur = conn.cursor()
    cur.execute("SELECT mtime, sha1 FROM files WHERE path = ?", (path,))
    row = cur.fetchone()
    if not row:
        return None
    return float(row[0]), str(row[1])


def _delete_by_path(conn: sqlite3.Connection, path: str) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM sections WHERE path = ?", (path,))
    cur.execute("DELETE FROM symbols WHERE path = ?", (path,))
    cur.execute("DELETE FROM assets WHERE owner_path = ?", (path,))


def _insert_sections(conn: sqlite3.Connection, sections: List[Section], lines: List[str]) -> List[Tuple[int, Section, str]]:
    cur = conn.cursor()
    result: List[Tuple[int, Section, str]] = []
    for sec in sections:
        summary = extract_summary(lines, sec.start_line, sec.end_line)
        cur.execute(
            """
            INSERT INTO sections(path, h1, h2, h3, start_line, end_line)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (sec.path, sec.h1, sec.h2, sec.h3, sec.start_line, sec.end_line),
        )
        result.append((cur.lastrowid, sec, summary))
    return result


def _find_section_id(section_rows: List[Tuple[int, Section, str]], line: int) -> Tuple[Optional[int], str]:
    matched: List[Tuple[int, Section, str]] = [r for r in section_rows if r[1].start_line <= line <= r[1].end_line]
    if not matched:
        return None, ""
    matched.sort(key=lambda r: (r[1].start_line, r[1].end_line), reverse=True)
    return matched[0][0], matched[0][2]


def _insert_symbols(conn: sqlite3.Connection, symbols: List[Symbol], section_rows: List[Tuple[int, Section, str]], tags: str, path: str) -> int:
    cur = conn.cursor()
    seen = set()
    count = 0
    for sym in symbols:
        key = (sym.name, sym.kind, sym.line)
        if key in seen:
            continue
        seen.add(key)
        section_id, summary = _find_section_id(section_rows, sym.line)
        cur.execute(
            """
            INSERT INTO symbols(name, kind, path, section_id, line, tags, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (sym.name, sym.kind, path, section_id, sym.line, tags, summary),
        )
        count += 1
    return count


def _insert_assets(conn: sqlite3.Connection, assets: List[Asset], section_rows: List[Tuple[int, Section, str]], owner_path: str, docs_root: str) -> int:
    cur = conn.cursor()
    count = 0
    for asset in assets:
        rel = asset.rel_path
        if rel.startswith("http://") or rel.startswith("https://"):
            continue
        abs_path = build_abs_path(str(Path(owner_path).parent), rel)
        section_id, _ = _find_section_id(section_rows, asset.line)
        cur.execute(
            """
            INSERT INTO assets(path, owner_path, section_id, alt, rel_path, line)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (abs_path, owner_path, section_id, asset.alt, rel, asset.line),
        )
        count += 1
    return count


def _rebuild_fts(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM symbols_fts")
        cur.execute("INSERT INTO symbols_fts(rowid, name, summary, tags) SELECT id, name, summary, tags FROM symbols")
        conn.commit()
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        pass


def scan(config_path: str) -> None:
    config = load_config(config_path)
    docs_root = norm_path(config["docs_root"])

    conn = sqlite3.connect(_db_path())
    _init_db(conn)

    start = time.time()
    files = list(iter_text_files(config))
    updated = 0
    skipped = 0
    sections_count = 0
    symbols_count = 0
    assets_count = 0

    for file_path in files:
        abs_path = norm_path(file_path)
        mtime = os.path.getmtime(abs_path)
        sha1 = file_sha1(abs_path)
        prev = _load_prev_file(conn, abs_path)
        if prev and prev[0] == mtime and prev[1] == sha1:
            skipped += 1
            continue

        _delete_by_path(conn, abs_path)

        lines = read_lines(abs_path)
        sections = parse_sections(abs_path, lines)
        if not sections:
            sections = [Section(path=abs_path, h1=None, h2=None, h3=None, start_line=1, end_line=len(lines))]
        section_rows = _insert_sections(conn, sections, lines)

        symbols = extract_symbols(lines)
        assets = extract_assets(lines)
        rel = rel_to_root(abs_path, docs_root)
        tags = ",".join(Path(rel).parts[:3])

        symbols_count += _insert_symbols(conn, symbols, section_rows, tags, abs_path)
        assets_count += _insert_assets(conn, assets, section_rows, abs_path, docs_root)

        conn.execute(
            "INSERT OR REPLACE INTO files(path, mtime, sha1) VALUES (?, ?, ?)",
            (abs_path, mtime, sha1),
        )
        updated += 1
        sections_count += len(sections)

    _rebuild_fts(conn)
    conn.commit()
    conn.close()

    elapsed = int((time.time() - start) * 1000)
    print(
        "scan_done",
        {
            "files_total": len(files),
            "files_updated": updated,
            "files_skipped": skipped,
            "sections": sections_count,
            "symbols": symbols_count,
            "assets": assets_count,
            "time_ms": elapsed,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    scan(args.config)


if __name__ == "__main__":
    main()
