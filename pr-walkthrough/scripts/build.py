#!/usr/bin/env python3
"""Check and build walkthrough pages.

Each target folder (made by collect.py) holds meta.json, diff.json and the authored
content.json (see references/content-schema.md), plus an optional tests.json. This script
checks every page against its diff and writes:
  <target>/walkthrough.html     one self-contained page per PR or branch
  <repo>/index.html             every built page in that repo folder, in reading order
  <repo>/lessons.html           every lesson those pages use, from the ground up

Usage:
  build.py <repo-folder>             build every target in it that has a content.json
  build.py <target-folder> [...]     build these targets (the repo index is refreshed too)
Options:
  --title TEXT   the index page title (default: "Pull request walkthroughs")
  --check        only check; write nothing

Exit status 1 when a page fails its checks; the errors say what to fix.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
LINK = re.compile(r'\[\[([a-z0-9-]+)\|([^\]]+)\]\]')
CODE_LINK = re.compile(r'\[\[([^\[\]|:]+?):(\d+)(?:-(\d+))?\|([^\]]+)\]\]')
CODE_REF = re.compile(r'^([^:]+):(\d+)(?:-(\d+))?$')
MIN_COVERAGE = 0.9  # share of meaningful added lines in a source file that need an explanatory comment
BAD_CHARS = ('—', '–')  # em dash, en dash
RISKS = ('low', 'medium', 'high')
SOURCES = ('author-notes', 'pr-text', 'inferred')
REQUIRED = ['summary', 'before_after', 'problem', 'thinking', 'files', 'tests', 'risks', 'review']
MAX_MINUTES = 10.0

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure import estimate, secondary  # noqa: E402


class BuildError(Exception):
    pass


def load_json(path: Path, default=None):
    if not path.exists():
        if default is not None:
            return default
        raise BuildError(f'missing {path}')
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise BuildError(f'{path}: invalid JSON: {exc}') from exc


def walk_strings(obj, fn, path='$'):
    """Apply fn(path, s) to every string inside obj, returning a new structure."""
    if isinstance(obj, str):
        return fn(path, obj)
    if isinstance(obj, list):
        return [walk_strings(v, fn, f'{path}[{i}]') for i, v in enumerate(obj)]
    if isinstance(obj, dict):
        return {k: walk_strings(v, fn, f'{path}.{k}') for k, v in obj.items()}
    return obj


def check_text(where: str, lessons: dict, obj, errors: list, lengths: dict | None = None) -> set:
    """Report dash characters, unknown lesson links and code links that miss; return the lesson ids linked."""
    used = set()

    def fn(path, s):
        for ch in BAD_CHARS:
            if ch in s:
                errors.append(f'{where} {path}: contains a dash character {ch!r}; use a comma, a period or parentheses')
        if lengths is not None:
            for m in CODE_LINK.finditer(s):
                problem = ref_problem(m.group(1), int(m.group(2)), int(m.group(3) or m.group(2)), lengths)
                if problem:
                    errors.append(f'{where} {path}: code link [[{m.group(1)}:{m.group(2)}...]] {problem}')
        for m in LINK.finditer(s):
            if m.group(1) in lessons:
                used.add(m.group(1))
            else:
                errors.append(f'{where} {path}: unknown lesson link [[{m.group(1)}|...]]')
        return s

    walk_strings(obj, fn)
    return used


def render_links(obj):
    def fn(_p, s):
        s = CODE_LINK.sub(lambda m: f'<a class="cl" data-file="{html.escape(m.group(1).strip(), quote=True)}" data-a="{m.group(2)}" '
                                    f'data-b="{m.group(3) or m.group(2)}">{m.group(4)}</a>', s)
        return LINK.sub(lambda m: f'<a class="c" data-c="{m.group(1)}">{m.group(2)}</a>', s)

    return walk_strings(obj, fn)


# ---------------------------------------------------------------- code links and explanatory comments


def file_lengths(diff: dict) -> dict:
    """Line counts of every changed file whose whole text the page can show."""
    return {f['path']: len(f['head_text'].splitlines()) for f in diff['files'] if f.get('head_text') is not None}


def ref_problem(path: str, a: int, b: int, lengths: dict) -> str:
    path = path.strip()
    if path not in lengths:
        return f'names {path!r}, which is not a changed file the page can show'
    if not (1 <= a <= b <= lengths[path]):
        return f'asks for lines {a}-{b}, but {path} has {lengths[path]} lines'
    return ''


def check_code_refs(tid: str, content: dict, lengths: dict) -> list:
    """Every "code" field (a section, step, option or risk that opens code when clicked) must point at real lines."""
    errors = []

    def walk(o, where):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == 'code' and isinstance(v, str):
                    m = CODE_REF.match(v.strip())
                    problem = 'is not "path:line" or "path:first-last"' if not m else ref_problem(m.group(1), int(m.group(2)), int(m.group(3) or m.group(2)), lengths)
                    if problem:
                        errors.append(f'{tid} {where}.code {v!r}: {problem}')
                elif k != 'files':
                    walk(v, f'{where}.{k}')
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f'{where}[{i}]')

    walk(content, '$')
    for k, v in (content.get('code_refs') or {}).items():
        m = CODE_REF.match(str(v).strip())
        problem = 'is not "path:line" or "path:first-last"' if not m else ref_problem(m.group(1), int(m.group(2)), int(m.group(3) or m.group(2)), lengths)
        if problem:
            errors.append(f'{tid} code_refs.{k} {v!r}: {problem}')
    return errors


def trivial_lines(text: str) -> set:
    """Line numbers that need no comment of their own: blanks, comments, docstrings, lone brackets."""
    out, in_doc = set(), False
    for n, line in enumerate(text.splitlines(), 1):
        st = line.strip()
        quotes = st.count('\"\"\"') + st.count("\'\'\'")
        if in_doc or quotes:
            out.add(n)
            if quotes % 2:
                in_doc = not in_doc
            continue
        if not st or st.startswith(('#', '//', '/*', '*', '<!--')) or re.fullmatch(r'[\)\]\}\(\[\{,;:]+', st):
            out.add(n)
    return out


def check_annotations(tid: str, content: dict, diff: dict, lengths: dict) -> tuple[list, list]:
    """Explanatory comments must sit on real lines, and cover the added code of every source file."""
    errors, warnings = [], []
    by_path = {f['path']: f for f in diff['files']}
    for f in content.get('files', []):
        fd = by_path.get(f['path'])
        anns = f.get('annotations') or []
        covered = set()
        for i, an in enumerate(anns):
            rng = an.get('lines') or ([an['line'], an['line']] if an.get('line') else None)
            if not rng or not an.get('text', '').strip():
                errors.append(f'{tid} {f["path"]} annotations[{i}]: needs "line" (or "lines": [first, last]) and "text"')
                continue
            problem = ref_problem(f['path'], rng[0], rng[1], lengths)
            if problem:
                errors.append(f'{tid} {f["path"]} annotations[{i}]: {problem}')
                continue
            covered.update(range(rng[0], rng[1] + 1))
        if fd is None or fd.get('head_text') is None:
            continue
        skip = trivial_lines(fd['head_text'])
        added = sorted({ln['new'] for h in fd['hunks'] for ln in h['lines'] if ln['t'] == 'add'} - skip)
        if not added:
            continue
        missing = [n for n in added if n not in covered]
        share = 1 - len(missing) / len(added)
        if secondary(f['path']):
            if not anns:
                warnings.append(f'{tid} {f["path"]}: no explanatory comments; a short one per test or block helps the reader')
        elif share < MIN_COVERAGE:
            errors.append(f'{tid} {f["path"]}: explanatory comments cover {share:.0%} of its added lines (need {MIN_COVERAGE:.0%}); '
                          f'uncovered lines include {missing[:10]}')
    return errors, warnings


# ---------------------------------------------------------------- lessons


def load_lessons(repo_dir: Path) -> tuple[dict, dict]:
    """The skill's lesson library, plus <repo>/lessons.json for lessons a team adds itself."""
    lessons = {}
    for f in sorted((SKILL / 'lessons').glob('*.json')):
        if f.name != 'levels.json':
            lessons.update(load_json(f))
    lessons.update(load_json(repo_dir / 'lessons.json', default={}))
    for cid, c in lessons.items():
        c.setdefault('id', cid)
    levels = load_json(SKILL / 'lessons' / 'levels.json', default={})
    return lessons, levels


def ladder(wanted, lessons: dict) -> list:
    """Wanted lessons plus all their prerequisites, prerequisites first, lower levels first."""
    seen, order = set(), []

    def visit(cid, stack=()):
        if cid in seen or cid not in lessons:
            return
        if cid in stack:
            raise BuildError(f'lesson prerequisite cycle: {" -> ".join(stack + (cid,))}')
        for p in lessons[cid].get('prereqs', []):
            visit(p, stack + (cid,))
        seen.add(cid)
        order.append(cid)

    for cid in wanted:
        visit(cid)
    return sorted(order, key=lambda c: (lessons[c].get('level', 0), order.index(c)))


# ---------------------------------------------------------------- diff coverage


def flatten(file_diff: dict) -> list:
    return [{**ln, 'hunk': h_i} for h_i, h in enumerate(file_diff['hunks']) for ln in h['lines']]


def chunk_indices(chunk: dict, lines: list) -> list:
    idx = []
    for i, ln in enumerate(lines):
        if (chunk.get('old') and 'old' in ln and chunk['old'][0] <= ln['old'] <= chunk['old'][1]) or (
            chunk.get('new') and 'new' in ln and chunk['new'][0] <= ln['new'] <= chunk['new'][1]
        ):
            idx.append(i)
    return idx


def check_coverage(tid: str, content: dict, diff: dict) -> list:
    errors = []
    by_path = {f['path']: f for f in diff['files'] if f['hunks']}
    authored = [f['path'] for f in content.get('files', [])]
    for p in by_path:
        if p not in authored:
            errors.append(f'{tid}: file {p} is in the diff but not in content.files')
    for f in content.get('files', []):
        fd = by_path.get(f['path'])
        if fd is None:
            errors.append(f'{tid}: content.files has {f["path"]}, which has no changed lines in the diff')
            continue
        lines = flatten(fd)
        owner = {}
        for c_i, ch in enumerate(f.get('chunks', [])):
            idx = chunk_indices(ch, lines)
            if not idx:
                errors.append(f'{tid} {f["path"]} chunk {c_i} ({ch.get("old")}/{ch.get("new")}): matches no diff line')
                continue
            for i in range(min(idx), max(idx) + 1):
                if i in owner:
                    errors.append(f'{tid} {f["path"]}: chunks {owner[i]} and {c_i} overlap')
                    break
                owner[i] = c_i
            if not ch.get('html', '').strip():
                errors.append(f'{tid} {f["path"]} chunk {c_i}: empty html')
            if ch.get('risk') and ch['risk'] not in RISKS:
                errors.append(f'{tid} {f["path"]} chunk {c_i}: risk must be one of {RISKS}')
        for i, ln in enumerate(lines):
            if ln['t'] in ('add', 'del') and i not in owner:
                errors.append(f'{tid} {f["path"]}: {ln["t"]} line {ln.get("new", ln.get("old"))} not covered: {ln["text"][:60]!r}')
    return errors


def check_review(tid: str, content: dict, diff: dict) -> list:
    errors = []
    review = content.get('review') or {}
    by_path = {f['path']: flatten(f) for f in diff['files']}
    look = review.get('look_first') or []
    if not look:
        errors.append(f'{tid}: review.look_first is empty; name the 1 to 5 places a reviewer should read first')
    for i, it in enumerate(look):
        lines = by_path.get(it.get('path'))
        side = 'new' if it.get('new') else 'old'
        rng = it.get(side)
        if lines is None:
            errors.append(f'{tid}: review.look_first[{i}] names {it.get("path")!r}, which is not in the diff')
        elif not rng or not any(side in ln and rng[0] <= ln[side] <= rng[1] for ln in lines):
            errors.append(f'{tid}: review.look_first[{i}] range {rng} matches no line of {it["path"]}')
        if it.get('risk') and it['risk'] not in RISKS:
            errors.append(f'{tid}: review.look_first[{i}].risk must be one of {RISKS}')
        if not it.get('why'):
            errors.append(f'{tid}: review.look_first[{i}] needs a "why"')
    source = (content.get('thinking') or {}).get('source')
    if source not in SOURCES:
        errors.append(f'{tid}: thinking.source must be one of {SOURCES} (where the reasoning comes from)')
    return errors


# ---------------------------------------------------------------- changed since the last read


def line_keys(file_diff: dict) -> set:
    return {(ln['t'], ln['text']) for ln in flatten(file_diff) if ln['t'] in ('add', 'del')}


def changed_since(target: Path, content: dict, diff: dict) -> dict | None:
    """Compare with the newest snapshot in history/: which chunks hold lines the last read did not have."""
    hist = target / 'history'
    snaps = sorted((d for d in hist.iterdir() if (d / 'diff.json').exists()), key=lambda d: d.stat().st_mtime) if hist.exists() else []
    if not snaps:
        return None
    old = load_json(snaps[-1] / 'diff.json')
    old_meta = load_json(snaps[-1] / 'meta.json', default={})
    old_files = {f['path']: line_keys(f) for f in old['files']}
    for f in old['files']:
        old_files.setdefault(f.get('old_path', f['path']), line_keys(f))
    by_path = {f['path']: f for f in diff['files']}
    chunks, new_files = {}, []
    for f in content.get('files', []):
        fd = by_path.get(f['path'])
        if fd is None:
            continue
        if f['path'] not in old_files:
            new_files.append(f['path'])
        seen = old_files.get(f['path'], set())
        lines = flatten(fd)
        hits = []
        for c_i, ch in enumerate(f.get('chunks', [])):
            idx = chunk_indices(ch, lines)
            if idx and any(lines[i]['t'] in ('add', 'del') and (lines[i]['t'], lines[i]['text']) not in seen for i in range(min(idx), max(idx) + 1)):
                hits.append(c_i)
        if hits:
            chunks[f['path']] = hits
    return {'since': old_meta.get('head_sha') or old.get('head_sha') or snaps[-1].name, 'chunks': chunks, 'new_files': new_files}


# ---------------------------------------------------------------- pages


def page(title: str, data: dict) -> str:
    template = (SKILL / 'assets' / 'template.html').read_text()
    app = (SKILL / 'assets' / 'app.js').read_text()
    blob = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    return template.replace('{{TITLE}}', html.escape(title)).replace('{{DATA}}', blob).replace('{{APP}}', app)


def pr_info(meta: dict, target: Path) -> dict:
    head = meta.get('headRefName', '')
    owner = (meta.get('headRepositoryOwner') or {}).get('login')
    repo_owner = meta['repo'].split('/')[0]
    return {
        'id': target.name, 'folder': target.name, 'number': meta.get('number'), 'url': meta.get('url'), 'title': meta.get('title', target.name),
        'author': (meta.get('author') or {}).get('login') if isinstance(meta.get('author'), dict) else meta.get('author'),
        'isDraft': meta.get('isDraft', False), 'state': meta.get('state'), 'base': meta.get('baseRefName'),
        'head': f'{owner}:{head}' if owner and owner != repo_owner else head, 'head_sha': meta.get('head_sha'),
        'stack_parent': meta.get('stack_parent'), 'diff_scope': meta.get('diff_scope'),
    }


def first_sentence(s: str) -> str:
    text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', LINK.sub(r'\2', s or ''))).strip()
    m = re.match(r'(.+?[.!?])(\s|$)', text)
    return html.escape((m.group(1) if m else text)[:220])


def build_target(target: Path, lessons: dict, levels: dict, siblings: list, write: bool) -> tuple[dict, list]:
    meta = load_json(target / 'meta.json')
    diff = load_json(target / 'diff.json')
    content = load_json(target / 'content.json')
    tid = target.name
    errors = [f'{tid}: missing key {k}' for k in REQUIRED if k not in content]
    lengths = file_lengths(diff)
    used = check_text(tid, lessons, content, errors, lengths)
    for cid in content.get('concepts', []):
        if cid not in lessons:
            errors.append(f'{tid}: unknown lesson {cid} in concepts')
    for cid in content.get('concept_hooks', {}):
        if cid not in lessons:
            errors.append(f'{tid}: unknown lesson {cid} in concept_hooks')
    errors += check_coverage(tid, content, diff)
    errors += check_review(tid, content, diff)
    errors += check_code_refs(tid, content, lengths)
    ann_errors, ann_warnings = check_annotations(tid, content, diff, lengths)
    errors += ann_errors
    info = pr_info(meta, target)
    words, code, minutes, _ = estimate(content, diff)
    info.update({'files': len(diff['files']), 'added': sum(f['added'] for f in diff['files']),
                 'deleted': sum(f['deleted'] for f in diff['files']), 'minutes': round(minutes),
                 'short': first_sentence(content.get('summary', '')), 'built': not errors})
    warnings = list(ann_warnings)
    if minutes > MAX_MINUTES:
        warnings.append(f'{tid}: about {minutes} minutes to read (target {MAX_MINUTES:g}); fold supporting chunks and cut prose')
    if errors or not write:
        return info, errors + warnings
    lad = ladder(sorted(used | set(content.get('concepts', []))), lessons)
    changed = changed_since(target, content, diff)
    info['changed'] = bool(changed and (changed['chunks'] or changed['new_files']))
    data = {
        'kind': 'pr', 'repo': meta['repo'], 'pr': info, 'siblings': siblings, 'content': render_links(content),
        'diff': {'files': diff['files']}, 'changed': changed, 'tests': load_json(target / 'tests.json', default={}),
        'gh_anchor': {f['path']: hashlib.sha256(f['path'].encode()).hexdigest() for f in diff['files']},
        'concepts': render_links({c: lessons[c] for c in lad}), 'ladder': lad, 'levels': levels,
        'hooks': render_links(content.get('concept_hooks', {})),
    }
    title = f'#{info["number"]}: {info["title"]}' if info['number'] else info['title']
    (target / 'walkthrough.html').write_text(page(title, data))
    return info, warnings


def targets_in(path: Path) -> tuple[Path, list]:
    if (path / 'meta.json').exists():
        return path.parent, [path]
    return path, sorted((p for p in path.iterdir() if (p / 'meta.json').exists() and (p / 'content.json').exists()),
                        key=lambda p: (load_json(p / 'meta.json').get('number') or 0, p.name))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paths', nargs='+')
    ap.add_argument('--title', default='Pull request walkthroughs')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    failed = False
    repos: dict = {}
    for raw in args.paths:
        repo_dir, targets = targets_in(Path(raw).expanduser().resolve())
        repos.setdefault(repo_dir, []).extend(targets)
    for repo_dir, chosen in repos.items():
        lessons, levels = load_lessons(repo_dir)
        _, everything = targets_in(repo_dir)
        siblings = [{'id': t.name, 'folder': t.name, 'label': f'#{load_json(t / "meta.json").get("number")}' if load_json(t / 'meta.json').get('number') else t.name}
                    for t in everything]
        cards = {}
        for t in everything:
            try:
                info, msgs = build_target(t, lessons, levels, siblings, write=(t in chosen and not args.check))
            except BuildError as exc:
                info, msgs = None, [str(exc)]
            if t in chosen:
                for m in msgs:
                    print(m)
                failed |= bool(info is None or not info['built'])
            if info:
                cards[t.name] = info
        if args.check:
            continue
        prs = [cards[t.name] for t in everything if t.name in cards]
        all_used = set()
        for t in everything:
            all_used |= set(load_json(t / 'content.json').get('concepts', []))
        repo_name = load_json(everything[0] / 'meta.json')['repo'] if everything else repo_dir.name
        (repo_dir / 'index.html').write_text(page(args.title, {'kind': 'index', 'repo': repo_name, 'title': args.title, 'prs': prs, 'levels': levels}))
        lad = ladder(sorted(c for c in all_used if c in lessons), lessons)
        (repo_dir / 'lessons.html').write_text(page('Lessons', {'kind': 'lessons', 'repo': repo_name, 'ladder': lad, 'levels': levels,
                                                              'concepts': render_links({c: lessons[c] for c in lad})}))
        built = [p['id'] for p in prs if p['built'] and Path(repo_dir / p['id']) in chosen]
        print(f'built: {", ".join(built) or "(none)"} -> {repo_dir / "index.html"}')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
