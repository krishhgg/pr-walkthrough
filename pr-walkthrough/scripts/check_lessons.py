"""Check the lesson library before sending a change (run it after editing lessons/*.json).

Errors (exit 1): files parse, ids and fields, prereqs resolve (core prereqs in core, pack prereqs in
core or pack, prereq level not above the lesson's), every [[id|text]] resolves (core links only into
core), example code and notes line up, banned characters, project words, hyphen used as a dash,
raw '<' or '&' in HTML fields, body length 80 to 200 words.
Warnings: filler vocabulary, possible mid-sentence colons.
"""
import json
import re
import sys
from pathlib import Path

LESSONS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / 'lessons'

errors, warnings = [], []
err = errors.append
warn = warnings.append

core = json.loads((LESSONS / 'core.json').read_text())
pack = json.loads((LESSONS / 'pack-ai-agents.json').read_text())
levels = json.loads((LESSONS / 'levels.json').read_text())
both = {**core, **pack}

LINK = re.compile(r'\[\[([a-z0-9-]+)\|([^\]]+)\]\]')
BAD_CHARS = {'—': 'em dash', '–': 'en dash', '‒': 'figure dash', '―': 'bar',
             '−': 'minus sign', '‘': 'curly quote', '’': 'curly quote',
             '“': 'curly quote', '”': 'curly quote', '…': 'ellipsis char'}
# Words that must not appear in shared lessons: project names, people, internal file names.
# Lessons in this library are general; a team keeping its own lessons can list its words here.
PROJECT: list = []
FILLER = ['additionally', 'crucial', 'delve', 'enhance', 'fostering', 'pivotal', 'robust',
          'seamless', 'showcase', 'leverage', 'utilize', 'comprehensive', 'landscape', 'tapestry',
          'testament', 'vibrant', 'enduring', 'garner', 'interplay', 'intricate', 'in order to',
          'not just', 'serves as', 'boasts']
ALLOWED_TAGS = re.compile(r'</?(p|ul|ol|li|code|b)>')
KEYS = {'id', 'title', 'level', 'prereqs', 'short', 'body', 'example'}
EX_KEYS = {'title', 'code', 'notes', 'lang'}


def strip_code(html):
    return re.sub(r'<code>.*?</code>', ' ', html, flags=re.S)


def words(html):
    text = re.sub(r'<[^>]+>', ' ', LINK.sub(lambda m: m.group(2), html))
    return len(text.split())


def check_html(where, s):
    for m in re.finditer(r'<', s):
        if not ALLOWED_TAGS.match(s, m.start()):
            err(f'{where}: raw "<" at ...{s[m.start():m.start() + 20]!r}')
    for m in re.finditer(r'&', s):
        if not re.match(r'&(lt|gt|amp|quot|#\d+);', s[m.start():]):
            err(f'{where}: raw "&" at ...{s[m.start():m.start() + 12]!r}')


def prose_checks(where, s, is_html=True):
    prose = strip_code(s) if is_html else s
    if re.search(r'(?<=\w) - (?=\w)|(?<=\w) -- (?=\w)|(?<=\w)--(?=\w)', prose):
        err(f'{where}: hyphen used as a dash')
    low = prose.lower()
    for f in FILLER:
        if re.search(r'\b' + re.escape(f) + r'\b', low):
            warn(f'{where}: filler word {f!r}')
    plain = re.sub(r'<[^>]+>', ' ', LINK.sub(lambda m: m.group(2), prose))
    for m in re.finditer(r'\w: [a-z]', plain):
        warn(f'{where}: possible mid-sentence colon ...{plain[max(0, m.start() - 30):m.end() + 20]!r}')


def all_strings(c):
    yield 'title', c['title']
    yield 'short', c['short']
    yield 'body', c['body']
    yield 'example.title', c['example']['title']
    yield 'example.code', c['example']['code']
    for i, n in enumerate(c['example']['notes']):
        yield f'example.notes[{i}]', n


for fname, lib in (('core', core), ('pack', pack)):
    for cid, c in lib.items():
        w = f'{fname}:{cid}'
        if set(c) != KEYS:
            err(f'{w}: keys {sorted(c)}')
        if c.get('id') != cid:
            err(f'{w}: id field {c.get("id")!r}')
        if not isinstance(c['level'], int) or str(c['level']) not in levels:
            err(f'{w}: bad level {c["level"]!r}')
        allowed = core if fname == 'core' else both
        for p in c['prereqs']:
            if p not in allowed:
                err(f'{w}: prereq {p} not in {"core" if fname == "core" else "core or pack"}')
            elif both[p]['level'] > c['level']:
                err(f'{w}: prereq {p} has a higher level')
        ex = c['example']
        if not set(ex) <= EX_KEYS or not {'title', 'code', 'notes'} <= set(ex):
            err(f'{w}: example keys {sorted(ex)}')
        if len(ex['code'].split('\n')) != len(ex['notes']):
            err(f'{w}: {len(ex["code"].split(chr(10)))} code lines but {len(ex["notes"])} notes')
        for i, (line, note) in enumerate(zip(ex['code'].split('\n'), ex['notes'])):
            if line.strip() and not note:
                err(f'{w}: code line {i + 1} has no note')
        n = words(c['body'])
        if not 80 <= n <= 200:
            err(f'{w}: body has {n} words')
        if c['title'][0].islower() and c['title'].split()[0] not in (
                'if,', 'for', 'while', 'break', 'return', 'def', 'lambda', 'import', 'self',
                'try', 'raise', 'finally', 'dataclass', 'staticmethod', 'assert', 'pytest',
                'git', 'f-string', '__init__'):
            warn(f'{w}: title starts lower case: {c["title"]!r}')
        for field, s in all_strings(c):
            fw = f'{w} {field}'
            for ch, name in BAD_CHARS.items():
                if ch in s:
                    err(f'{fw}: contains {name}')
            for pat in PROJECT:
                for m in re.finditer(pat, s, flags=re.I):
                    err(f'{fw}: project word {m.group(0)!r}')
            for m in LINK.finditer(s):
                target = m.group(1)
                if fname == 'core' and target not in core:
                    err(f'{fw}: link [[{target}|...]] not in core')
                elif target not in both:
                    err(f'{fw}: link [[{target}|...]] unknown')
            if field in ('short', 'body') or field.startswith('example.notes'):
                check_html(fw, s)
            if field != 'example.code':
                prose_checks(fw, s, is_html=field in ('short', 'body') or field.startswith('example.notes'))
            if 'wave_hook' in c:
                err(f'{w}: wave_hook still present')

if any(levels.get(str(k)) is None for k in range(1, 12)):
    err('levels.json is missing a level')

print(f'core.json: {len(core)} lessons; pack-ai-agents.json: {len(pack)} lessons')
lens = sorted(words(c['body']) for c in both.values())
print(f'body words: min {lens[0]}, median {lens[len(lens) // 2]}, max {lens[-1]}')
for w_ in warnings:
    print('WARN', w_)
for e in errors:
    print('ERROR', e)
print(f'{len(errors)} errors, {len(warnings)} warnings')
sys.exit(1 if errors else 0)
