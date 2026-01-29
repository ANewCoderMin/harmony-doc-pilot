"""HarmonyDocPilot shared utilities."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

_CLASS_RE = re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_][\w]*)\b")
_INTERFACE_RE = re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_][\w]*)\b")
_ENUM_RE = re.compile(r"^\s*(?:export\s+)?enum\s+([A-Za-z_][\w]*)\b")
_FUNCTION_RE = re.compile(r"^\s*(?:export\s+)?function\s+([A-Za-z_][\w]*)\b")
_STRUCT_RE = re.compile(r"^\s*struct\s+([A-Za-z_][\w]*)\b")
_COMPONENT_DECORATOR_RE = re.compile(r"^\s*@Component\b")

_CALL_LIKE_RE = re.compile(r"\b([A-Za-z_][\w]*)\s*\(")
_CALL_LIKE_STOPWORDS = {
    "if",
    "for",
    "while",
    "switch",
    "return",
    "new",
    "function",
    "class",
    "interface",
    "enum",
    "struct",
    "catch",
    "map",
    "filter",
    "reduce",
}


@dataclass
class Section:
    path: str
    h1: Optional[str]
    h2: Optional[str]
    h3: Optional[str]
    start_line: int
    end_line: int


@dataclass
class Symbol:
    name: str
    kind: str
    line: int


@dataclass
class Asset:
    alt: str
    rel_path: str
    line: int


def load_config(path: str) -> Dict:
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("需要安装 PyYAML（pip install pyyaml）") from exc

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def norm_path(path: str) -> str:
    return str(Path(path).resolve())


def file_sha1(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def read_lines(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines()


def iter_text_files(config: Dict) -> Iterable[str]:
    root = Path(config["docs_root"])
    include_scopes = [root / p for p in config.get("include_scopes", [])]
    exclude_scopes = set(config.get("exclude_scopes", []))
    text_exts = set(config.get("text_extensions", []))

    for scope in include_scopes:
        if not scope.exists():
            continue
        for path in scope.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if any(rel.startswith(ex + "/") or rel == ex for ex in exclude_scopes):
                continue
            if path.suffix.lower() not in text_exts:
                continue
            yield str(path.resolve())


def parse_sections(path: str, lines: List[str]) -> List[Section]:
    headings: List[Tuple[int, int, str]] = []
    for idx, line in enumerate(lines, start=1):
        m = _HEADING_RE.match(line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        headings.append((idx, level, title))

    sections: List[Section] = []
    if not headings:
        return sections

    for i, (line_no, level, title) in enumerate(headings):
        end_line = len(lines)
        for j in range(i + 1, len(headings)):
            next_line, next_level, _ = headings[j]
            if next_level <= level:
                end_line = next_line - 1
                break

        h1 = h2 = h3 = None
        for k in range(i, -1, -1):
            prev_line, prev_level, prev_title = headings[k]
            if prev_level == 1 and h1 is None:
                h1 = prev_title
            if prev_level == 2 and h2 is None:
                h2 = prev_title
            if prev_level == 3 and h3 is None:
                h3 = prev_title
        sections.append(Section(path=path, h1=h1, h2=h2, h3=h3, start_line=line_no, end_line=end_line))

    return sections


def extract_assets(lines: List[str]) -> List[Asset]:
    assets: List[Asset] = []
    for idx, line in enumerate(lines, start=1):
        for m in _IMAGE_RE.finditer(line):
            alt = m.group(1).strip()
            rel = m.group(2).strip()
            assets.append(Asset(alt=alt, rel_path=rel, line=idx))
    return assets


def extract_symbols(lines: List[str]) -> List[Symbol]:
    symbols: List[Symbol] = []
    pending_component = False

    for idx, line in enumerate(lines, start=1):
        if _COMPONENT_DECORATOR_RE.match(line):
            pending_component = True
            continue

        m = _CLASS_RE.match(line)
        if m:
            symbols.append(Symbol(name=m.group(1), kind="class", line=idx))
            pending_component = False
            continue

        m = _INTERFACE_RE.match(line)
        if m:
            symbols.append(Symbol(name=m.group(1), kind="interface", line=idx))
            pending_component = False
            continue

        m = _ENUM_RE.match(line)
        if m:
            symbols.append(Symbol(name=m.group(1), kind="enum", line=idx))
            pending_component = False
            continue

        m = _FUNCTION_RE.match(line)
        if m:
            symbols.append(Symbol(name=m.group(1), kind="function", line=idx))
            pending_component = False
            continue

        m = _STRUCT_RE.match(line)
        if m:
            kind = "component" if pending_component else "struct"
            symbols.append(Symbol(name=m.group(1), kind=kind, line=idx))
            pending_component = False
            continue

        if "(" in line:
            for m in _CALL_LIKE_RE.finditer(line):
                name = m.group(1)
                if name in _CALL_LIKE_STOPWORDS:
                    continue
                if len(name) < 3:
                    continue
                symbols.append(Symbol(name=name, kind="call", line=idx))

    return symbols


def extract_summary(lines: List[str], start_line: int, end_line: int) -> str:
    content = []
    in_para = False
    start_idx = min(max(start_line, 1), len(lines))
    end_idx = min(max(end_line, 1), len(lines))
    for line in lines[start_idx:end_idx]:
        stripped = line.strip()
        if not stripped:
            if in_para:
                break
            continue
        if stripped.startswith("#"):
            continue
        in_para = True
        content.append(stripped)
        if sum(len(s) for s in content) > 300:
            break
    return " ".join(content)[:400]


def section_text(lines: List[str], start_line: int, end_line: int) -> str:
    start = max(start_line - 1, 0)
    end = min(end_line, len(lines))
    return "\n".join(lines[start:end])


def rel_to_root(abs_path: str, root: str) -> str:
    return Path(abs_path).resolve().relative_to(Path(root).resolve()).as_posix()


def build_abs_path(root: str, rel_path: str) -> str:
    return str((Path(root) / rel_path).resolve())
