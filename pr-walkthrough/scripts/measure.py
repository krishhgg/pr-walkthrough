#!/usr/bin/env python3
"""Estimate a walkthrough's reading time the way the page counts it.

Open prose at 200 words a minute, open code lines at 60 a minute, half a minute per diagram.
Folded parts (test, doc and dependency files; chunks marked "fold"; unchanged context; the
lessons list) count only by their one-line summaries. The target is 10 minutes or less.

Usage: measure.py <target-folder> [...]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LINK = re.compile(r'\[\[[^|\]]+\|([^\]]+)\]\]')


def words(o) -> int:
    if isinstance(o, str):
        return len(re.sub(r'<[^>]+>', ' ', LINK.sub(r'\1', o)).split())
    if isinstance(o, list):
        return sum(words(x) for x in o)
    if isinstance(o, dict):
        return sum(words(v) for k, v in o.items() if k not in ('concepts', 'files', 'diagrams', 'concept_hooks', 'path', 'new', 'old', 'risk', 'source'))
    return 0


def secondary(path: str) -> bool:
    return bool(
        re.search(r'(^|/)(tests?|__tests__|spec|specs|testdata|fixtures)/', path)
        or re.search(r'(_test|\.test|\.spec)\.[a-z]+$', path)
        or re.search(r'\.(md|mdx|rst|lock|snap|svg)$', path)
        or re.search(r'(^|/)(requirements[^/]*\.txt|package-lock\.json|yarn\.lock|pnpm-lock\.yaml|go\.sum|Cargo\.lock)$', path)
    )


def estimate(content: dict, diff: dict) -> tuple[int, int, float, int]:
    """Return (words, open code lines, minutes, diagrams) for one page."""
    prose = 90  # headings, the reading tip, the legend, buttons and the facts line
    prose += words({k: v for k, v in content.items() if k not in ('files',)})
    prose += 6 * len(diff.get('files', []))  # the change map rows
    code = notes = 0
    for f in content.get('files', []):
        prose += 5 + words(f.get('role', ''))
        if secondary(f['path']):
            continue
        for ch in f.get('chunks', []):
            notes += words(ch.get('html', '')) + words(ch.get('check', '')) + 4
            if not ch.get('fold'):
                for side in ('new', 'old'):
                    if ch.get(side):
                        code += ch[side][1] - ch[side][0] + 1
    diagrams = len(content.get('diagrams', []))
    total = prose + notes
    return total, code, round(total / 200 + code / 60 + diagrams / 2, 1), diagrams


def main() -> None:
    for raw in sys.argv[1:]:
        target = Path(raw)
        content = json.loads((target / 'content.json').read_text())
        diff = json.loads((target / 'diff.json').read_text())
        w, code, minutes, d = estimate(content, diff)
        print(f'{target.name}: words={w} open_code_lines={code} diagrams={d} minutes={minutes}')


if __name__ == '__main__':
    main()
