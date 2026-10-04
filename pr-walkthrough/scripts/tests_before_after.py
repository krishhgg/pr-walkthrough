#!/usr/bin/env python3
"""Run a PR's tests on the code before the PR and with it, and write tests.json for the page.

"Before" is the PR's base commit with the PR's test files copied in, so a new test shows how the
old code behaves. "After" is the PR's head commit. Both run in temporary git worktrees of the
local clone; nothing in your checkout changes. Results come from JUnit XML, which most test
runners can write, so this works for any language.

Usage (run inside a local clone of the repo):
  tests_before_after.py <target-folder> --cmd "pytest {tests} --junitxml={junit}"
  tests_before_after.py <target-folder> --cmd "npx jest {tests} --reporters=jest-junit" --junit-path junit.xml
  tests_before_after.py <target-folder> --cmd "gotestsum --junitfile {junit} ./..." --tests ""
Options:
  --tests PATHS     space-separated test files to run (default: the test files the PR changes)
  --setup CMD       run once in each worktree before the tests (for example "npm ci")
  --junit-path P    where the runner writes its XML when it cannot take {junit} (relative to the worktree)
  --timeout SEC     per run (default 1800)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

TEST_FILE = re.compile(r'(^|/)(tests?|__tests__|spec|specs)/|(_test|\.test|\.spec)\.[a-z]+$|(^|/)test_[^/]+$')
HELPERS = ('conftest.py', 'setup_tests.py', 'jest.setup.js', 'jest.setup.ts', 'testutil.go')


def sh(cmd, cwd=None, timeout=None, shell=False):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, shell=shell)


def read_junit(path: Path) -> dict:
    out = {}
    if not path.exists():
        return out
    for case in ET.parse(path).getroot().iter('testcase'):
        name = '::'.join(x for x in (case.get('classname'), case.get('name')) if x)
        outcome, msg = 'passed', ''
        for tag in ('failure', 'error', 'skipped'):
            el = case.find(tag)
            if el is not None:
                outcome = {'failure': 'failed', 'error': 'error', 'skipped': 'skipped'}[tag]
                msg = (el.get('message') or el.text or '').strip().splitlines()[0][:200] if (el.get('message') or el.text) else ''
                break
        out[name] = {'outcome': outcome, 'message': msg}
    return out


def run_side(clone: str, sha: str, copy_from: str | None, files: list, args, label: str, work: Path) -> dict:
    tree = work / label
    sh(['git', '-C', clone, 'worktree', 'add', '--detach', str(tree), sha])
    try:
        if copy_from:
            for f in files:
                src = Path(copy_from) / f
                if src.exists():
                    (tree / f).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(src, tree / f)
        if args.setup:
            sh(args.setup, cwd=tree, timeout=args.timeout, shell=True)
        junit = work / f'{label}.xml'
        cmd = args.cmd.replace('{tests}', ' '.join(t for t in files if TEST_FILE.search(t))).replace('{junit}', str(junit))
        r = sh(cmd, cwd=tree, timeout=args.timeout, shell=True)
        if args.junit_path and (tree / args.junit_path).exists():
            shutil.copy(tree / args.junit_path, junit)
        res = read_junit(junit)
        if not res:
            res['__run__'] = {'outcome': 'error', 'message': (r.stdout + r.stderr).strip()[-300:]}
        return res
    finally:
        sh(['git', '-C', clone, 'worktree', 'remove', '--force', str(tree)])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('target')
    ap.add_argument('--cmd', required=True)
    ap.add_argument('--tests')
    ap.add_argument('--setup')
    ap.add_argument('--junit-path')
    ap.add_argument('--timeout', type=int, default=1800)
    args = ap.parse_args()
    target = Path(args.target)
    meta = json.loads((target / 'meta.json').read_text())
    diff = json.loads((target / 'diff.json').read_text())
    clone = sh(['git', 'rev-parse', '--show-toplevel']).stdout.strip() or sys.exit('run inside a local clone of the repo')
    if sh(['git', '-C', clone, 'cat-file', '-e', meta['head_sha']]).returncode:
        sys.exit(f'the head commit {meta["head_sha"][:8]} is not in this clone; run collect.py from inside the clone first')
    changed = [f['path'] for f in diff['files'] if f['status'] != 'deleted']
    files = args.tests.split() if args.tests is not None else [p for p in changed if TEST_FILE.search(p) or Path(p).name in HELPERS]
    with tempfile.TemporaryDirectory(prefix='pr-walkthrough-') as tmp:
        work = Path(tmp)
        after = run_side(clone, meta['head_sha'], None, files, args, 'after', work)
        head_tree = work / 'head-files'
        sh(['git', '-C', clone, 'worktree', 'add', '--detach', str(head_tree), meta['head_sha']])
        try:
            before = run_side(clone, meta['diff_from'], str(head_tree), files, args, 'before', work)
        finally:
            sh(['git', '-C', clone, 'worktree', 'remove', '--force', str(head_tree)])
    rows = []
    for name in sorted(set(before) | set(after)):
        b, a = before.get(name, {}), after.get(name, {})
        if b.get('outcome') == a.get('outcome') == 'passed' and len(rows) > 200:
            continue
        rows.append({'name': name, 'before': b.get('outcome'), 'after': a.get('outcome'), 'before_msg': b.get('message', '')})
    (target / 'tests.json').write_text(json.dumps({'command': args.cmd, 'rows': rows}, indent=1))
    fixed = sum(r['after'] == 'passed' and r['before'] != 'passed' for r in rows)
    broken = sum(r['after'] != 'passed' for r in rows)
    print(json.dumps({'tests': len(rows), 'fail_before_pass_after': fixed, 'not_passing_after': broken}, indent=1))


if __name__ == '__main__':
    main()
