#!/usr/bin/env python3
"""Carry a walkthrough's notes onto a PR's new commits.

When collect.py finds a new head commit, it moves the old meta.json, diff.json and
content.json into history/<old-sha>/. This script maps the old content onto the new diff,
matching lines by their text, and writes content.json again. Only the notes whose lines
are gone are dropped. It then lists the changed lines no note covers yet, so the next
step writes notes for those lines only.

Usage: carry_notes.py <target-folder>
"""

from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path


def flat(diff: dict, path: str) -> list:
    for f in diff['files']:
        if f['path'] == path:
            return [ln for h in f['hunks'] for ln in h['lines']]
    return []


def line_maps(old_lines: list, new_lines: list) -> tuple[dict, dict]:
    a = [(ln['t'], ln['text']) for ln in old_lines]
    b = [(ln['t'], ln['text']) for ln in new_lines]
    m_new, m_old = {}, {}
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag != 'equal':
            continue
        for i, j in zip(range(i1, i2), range(j1, j2)):
            o, n = old_lines[i], new_lines[j]
            if o.get('new') is not None and n.get('new') is not None:
                m_new[o['new']] = n['new']
            if o.get('old') is not None and n.get('old') is not None:
                m_old[o['old']] = n['old']
    return m_new, m_old


def remap(rng: list, m: dict):
    xs = [m[x] for x in range(rng[0], rng[1] + 1) if x in m]
    return [min(xs), max(xs)] if xs else None


def uncovered(content: dict, diff: dict) -> list:
    out = []
    for f in diff['files']:
        authored = next((c for c in content['files'] if c['path'] == f['path']), {'chunks': []})
        for ln in (ln for h in f['hunks'] for ln in h['lines']):
            if ln['t'] == 'ctx':
                continue
            side, num = ('new', ln['new']) if ln['t'] == 'add' else ('old', ln['old'])
            if not any(ch.get(side) and ch[side][0] <= num <= ch[side][1] for ch in authored['chunks']):
                out.append(f'{f["path"]}: {ln["t"]} line {num}: {ln["text"][:70]!r}')
    return out


def main() -> None:
    target = Path(sys.argv[1])
    snaps = sorted((d for d in (target / 'history').iterdir() if (d / 'content.json').exists()), key=lambda d: d.stat().st_mtime) \
        if (target / 'history').exists() else []
    if not snaps:
        sys.exit('carry_notes: no earlier walkthrough in history/ to carry from')
    if (target / 'content.json').exists():
        sys.exit('carry_notes: content.json already exists; move it away first if you want to carry the old notes again')
    old_diff = json.loads((snaps[-1] / 'diff.json').read_text())
    content = json.loads((snaps[-1] / 'content.json').read_text())
    new_diff = json.loads((target / 'diff.json').read_text())
    new_paths = {f['path'] for f in new_diff['files']}
    dropped = []
    kept_files = []
    for f in content['files']:
        if f['path'] not in new_paths:
            dropped.append(f'{f["path"]}: the whole file left the PR')
            continue
        m_new, m_old = line_maps(flat(old_diff, f['path']), flat(new_diff, f['path']))
        keep = []
        for ch in f['chunks']:
            moved = dict(ch)
            ok = True
            for side, m in (('new', m_new), ('old', m_old)):
                if side in ch:
                    r = remap(ch[side], m)
                    if r is None:
                        ok = False
                    else:
                        moved[side] = r
            if ok:
                keep.append(moved)
            else:
                dropped.append(f'{f["path"]} {ch.get("old")}/{ch.get("new")}: {ch["html"][:70]}')
        kept_files.append({**f, 'chunks': keep})
    for p in sorted(new_paths - {f['path'] for f in kept_files}):
        kept_files.append({'path': p, 'role': '', 'chunks': []})
    content['files'] = kept_files
    look = []
    for it in (content.get('review') or {}).get('look_first', []):
        side = 'new' if it.get('new') else 'old'
        if it.get('path') in new_paths and it.get(side):
            m_new, m_old = line_maps(flat(old_diff, it['path']), flat(new_diff, it['path']))
            r = remap(it[side], m_new if side == 'new' else m_old)
            if r:
                look.append({**it, side: r})
    if content.get('review'):
        content['review']['look_first'] = look
    (target / 'content.json').write_text(json.dumps(content, indent=1, ensure_ascii=False))
    gaps = uncovered(content, new_diff)
    print(json.dumps({'carried_from': snaps[-1].name, 'dropped_notes': dropped, 'lines_needing_notes': gaps,
                      'next': 'Write notes for lines_needing_notes, recheck look_first, summary and risks, then run build.py.'}, indent=1))


if __name__ == '__main__':
    main()
