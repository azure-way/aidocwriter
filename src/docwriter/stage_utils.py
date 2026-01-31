from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Tuple, Set

SECTION_START_RE = re.compile(r"<!-- SECTION:(?P<id>[^:]+):START -->")
HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.+)$")
HEADING_NUMBER_PREFIX_RE = re.compile(r"^\d+(?:\.\d+)*(?:\.)?\s+")
TITLE_PAGE_START = "<!-- TITLE_PAGE_START -->"
TITLE_PAGE_END = "<!-- TITLE_PAGE_END -->"
TOC_START = "<!-- TABLE_OF_CONTENTS_START -->"
TOC_END = "<!-- TABLE_OF_CONTENTS_END -->"
SLUG_INVALID_RE = re.compile(r"[^a-z0-9\- ]+", re.IGNORECASE)
SLUG_SEP_RE = re.compile(r"[\s\-]+")


def extract_sections(text: str) -> Dict[str, str]:
    sections: Dict[str, str] = {}
    for match in SECTION_START_RE.finditer(text):
        sid = match.group("id")
        start_idx = match.start()
        end_marker = f"<!-- SECTION:{sid}:END -->"
        end_idx = text.find(end_marker, match.end())
        if end_idx == -1:
            continue
        end_idx += len(end_marker)
        sections[sid] = text[start_idx:end_idx]
    return sections


def merge_revised_markdown(original: str, revised: str) -> str:
    if not revised.strip():
        return original
    revised_sections = extract_sections(revised)
    if not revised_sections:
        return revised
    original_sections = extract_sections(original)
    if not original_sections:
        return revised
    updated = original
    for sid, section_text in revised_sections.items():
        original_section = original_sections.get(sid)
        if not original_section:
            continue
        inner = section_text.replace(f"<!-- SECTION:{sid}:START -->", "").replace(
            f"<!-- SECTION:{sid}:END -->", ""
        ).strip()
        if not inner or "content unchanged" in inner.lower():
            continue
        updated = updated.replace(original_section, section_text)
    return updated


def parse_review_guidance(raw: Any) -> Tuple[str, Set[str]]:
    if not isinstance(raw, str):
        return "", set()
    raw = raw.strip()
    if not raw:
        return "", set()
    sections: Set[str] = set()
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = raw

    lines: list[str] = []

    def _handle_item(key: str, value: Any) -> None:
        if key == "section_id" and isinstance(value, (str, int)):
            sections.add(str(value))
        elif isinstance(value, (str, int, float)):
            lines.append(str(value))
        elif isinstance(value, dict):
            for k, val in value.items():
                _handle_item(k, val)
        elif isinstance(value, list):
            for item in value:
                _handle_item(key, item)

    if isinstance(parsed, dict):
        for key, val in parsed.items():
            _handle_item(key, val)
    elif isinstance(parsed, list):
        for item in parsed:
            _handle_item("item", item)
    else:
        lines.append(str(parsed))

    guidance_text = "\n".join(line for line in lines if line).strip()
    if not guidance_text:
        guidance_text = json.dumps(parsed, ensure_ascii=False)
    return guidance_text, sections


def find_placeholder_sections(markdown: str) -> Set[str]:
    placeholders: Set[str] = set()
    sections = extract_sections(markdown)
    for sid, section_text in sections.items():
        inner = section_text.replace(f"<!-- SECTION:{sid}:START -->", "").replace(
            f"<!-- SECTION:{sid}:END -->", ""
        ).strip()
        inner_lower = inner.lower()
        if "content unchanged" in inner_lower or "placeholder" in inner_lower:
            placeholders.add(sid)
    return placeholders


def number_markdown_headings(markdown: str) -> str:
    counters = [0] * 6
    numbered_lines: list[str] = []
    in_title_page = False
    in_code_block = False
    trailing_newline = "\n" if markdown.endswith("\n") else ""

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            numbered_lines.append(line)
            continue
        if in_code_block:
            numbered_lines.append(line)
            continue
        if TITLE_PAGE_START in line:
            in_title_page = True
            numbered_lines.append(line)
            continue
        if TITLE_PAGE_END in line:
            in_title_page = False
            numbered_lines.append(line)
            continue

        match = HEADING_RE.match(line)
        if not match or in_title_page:
            numbered_lines.append(line)
            continue

        hashes = match.group("hashes")
        level = len(hashes)
        text = match.group("text").strip()
        text = HEADING_NUMBER_PREFIX_RE.sub("", text, count=1).strip()

        for idx in range(level - 1):
            if counters[idx] == 0:
                counters[idx] = 1
        counters[level - 1] += 1
        for idx in range(level, len(counters)):
            counters[idx] = 0

        numbering_parts = [str(counters[idx]) for idx in range(level) if counters[idx] > 0]
        numbering = ".".join(numbering_parts)
        if numbering:
            numbered_line = f"{hashes} {numbering} {text}".rstrip()
        else:
            numbered_line = f"{hashes} {text}".rstrip()
        numbered_lines.append(numbered_line)

    return "\n".join(numbered_lines) + trailing_newline


def _slugify_heading(text: str) -> str:
    normalized = SLUG_INVALID_RE.sub("", text or "")
    normalized = normalized.lower()
    parts = [part for part in SLUG_SEP_RE.split(normalized) if part]
    return "-".join(parts) or "section"


def insert_table_of_contents(markdown: str) -> str:
    """Insert a TOC after the title page (or at the top) with anchors matching heading IDs."""
    if TOC_START in markdown:
        return markdown

    lines = markdown.splitlines()
    in_code = False
    in_title = False
    headings: list[Tuple[int, str, str]] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if TITLE_PAGE_START in line:
            in_title = True
            continue
        if TITLE_PAGE_END in line:
            in_title = False
            continue
        match = HEADING_RE.match(line)
        if not match or in_title:
            continue
        level = len(match.group("hashes"))
        text = match.group("text").strip()
        slug = _slugify_heading(text)
        headings.append((level, text, slug))

    if not headings:
        return markdown

    toc_lines = [TOC_START, "## Table of Contents"]
    for level, text, slug in headings:
        indent = "  " * max(0, level - 2)
        toc_lines.append(f"{indent}- [{text}](#{slug})")
    toc_lines.append(TOC_END)
    toc_block = "\n".join(toc_lines) + "\n\n"

    if TITLE_PAGE_END in markdown:
        insert_at = markdown.index(TITLE_PAGE_END) + len(TITLE_PAGE_END)
        return markdown[:insert_at] + "\n\n" + toc_block + markdown[insert_at:]

    return toc_block + markdown
