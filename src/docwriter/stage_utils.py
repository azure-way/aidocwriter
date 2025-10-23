from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Tuple, Set

SECTION_START_RE = re.compile(r"<!-- SECTION:(?P<id>[^:]+):START -->")


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
