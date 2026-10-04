#!/usr/bin/env python3
"""Collect what a walkthrough needs for one or more pull requests or local branches.

For each target it writes <out>/<repo-slug>/<target-id>/meta.json and diff.json. When an
earlier collection of the same target has a different head commit, the old files move to
history/<old-sha>/ first, so the page can show what changed since the last read.

Usage:
  collect.py 2521 2522                     PRs in the current repo (needs the gh CLI)
  collect.py owner/repo#12 https://github.com/o/r/pull/34
  collect.py --mine                        your open PRs in the current repo
  collect.py --mine --all-repos            your open PRs in every repo
  collect.py --branch my-feature [--base main]
                                           a local branch, no PR needed
Options:
  --out DIR      where walkthroughs live (default: $PR_WALKTHROUGH_HOME or ~/.cache/pr-walkthrough)
  --context N    unchanged lines kept around each change (default 4)

Prints one JSON summary on stdout: the target folders, titles, sizes and stack parents.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$')
PR_URL = re.compile(r'github\.com/([^/]+/[^/]+)/pull/(\d+)')
PR_REF = re.compile(r'^(?:([\w.-]+/[\w.-]+)#)?#?(\d+)$')
PR_FIELDS = (
    'number,title,body,url,author,state,isDraft,baseRefName,headRefName,headRefOid,baseRefOid,'
    'headRepositoryOwner,commits,labels,closingIssuesReferences,reviews,additions,deletions,createdAt,updatedAt'
)


class CollectError(Exception):
    pass


def sh(*args: str, cwd: str | None = None, check: bool = True) -> str:
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise CollectError(f'{" ".join(args[:4])}... failed: {(r.stderr or r.stdout).strip()[:400]}')
    return r.stdout


# ------------------------------------------------------------------ diffs


def parse_diff(text: str) -> list:
    """Unified diff -> [{path, old_path, status, hunks: [{header, lines: [{t, old, new, text}]}]}]."""
    files, cur, hunk = [], None, None
    old_no = new_no = 0
    for line in text.split('\n'):
        if line.startswith('diff --git '):
            m = re.match(r'diff --git a/(.*) b/(.*)', line)
            cur = {'path': m.group(2), 'old_path': m.group(1), 'status': 'modified', 'hunks': []}
            files.append(cur)
            hunk = None
        elif cur is None:
            continue
        elif line.startswith('new file mode'):
            cur['status'] = 'added'
        elif line.startswith('deleted file mode'):
            cur['status'] = 'deleted'
        elif line.startswith('rename from') or line.startswith('similarity index'):
            cur['status'] = 'renamed' if cur['status'] == 'modified' else cur['status']
        elif line.startswith(('--- ', '+++ ', 'index ', 'rename to', 'old mode', 'new mode', 'Binary files')):
            if line.startswith('Binary files'):
                cur['binary'] = True
            continue
        elif line.startswith('@@'):
            m = HUNK.match(line)
            old_no, new_no = int(m.group(1)), int(m.group(3))
            hunk = {'header': m.group(5).strip(), 'lines': []}
            cur['hunks'].append(hunk)
        elif hunk is not None and line[:1] in (' ', '+', '-'):
            t = {' ': 'ctx', '+': 'add', '-': 'del'}[line[0]]
            entry = {'t': t, 'text': line[1:]}
            if t in ('ctx', 'del'):
                entry['old'] = old_no
                old_no += 1
            if t in ('ctx', 'add'):
                entry['new'] = new_no
                new_no += 1
            hunk['lines'].append(entry)
    for f in files:
        lines = [ln for h in f['hunks'] for ln in h['lines']]
        f['added'] = sum(ln['t'] == 'add' for ln in lines)
        f['deleted'] = sum(ln['t'] == 'del' for ln in lines)
    return files


# ------------------------------------------------------------------ git and gh helpers


def git(clone: str, *args: str, check: bool = True) -> str:
    return sh('git', '-C', clone, *args, check=check)


def current_repo(cwd: str) -> str | None:
    out = sh('gh', 'repo', 'view', '--json', 'nameWithOwner', '-q', '.nameWithOwner', cwd=cwd, check=False).strip()
    return out or None


def remote_for(clone: str, repo: str) -> str | None:
    """The name of a remote of *clone* that points at github.com/<repo>, if any."""
    out = git(clone, 'remote', '-v', check=False)
    for line in out.splitlines():
        name, url = line.split()[:2]
        if re.search(rf'github\.com[:/]{re.escape(repo)}(\.git)?$', url):
            return name
    return None


def git_root(cwd: str) -> str | None:
    out = sh('git', '-C', cwd, 'rev-parse', '--show-toplevel', check=False).strip()
    return out or None


def strip_html_comments(s: str) -> str:
    return re.sub(r'<!--.*?-->', '', s or '', flags=re.S).strip()


# ------------------------------------------------------------------ targets


def resolve_targets(args, cwd: str) -> list:
    """Turn the command line into [{'kind': 'pr', 'repo', 'number'} | {'kind': 'branch', ...}]."""
    targets = []
    if args.branch:
        targets.append({'kind': 'branch', 'branch': args.branch, 'base': args.base})
    if args.mine:
        if args.all_repos:
            rows = json.loads(sh('gh', 'search', 'prs', '--author', '@me', '--state', 'open', '--limit', '100',
                                 '--json', 'repository,number', cwd=cwd))
            targets += [{'kind': 'pr', 'repo': r['repository']['nameWithOwner'], 'number': r['number']} for r in rows]
        else:
            repo = current_repo(cwd) or sys.exit('--mine needs to run inside a GitHub repo, or add --all-repos')
            rows = json.loads(sh('gh', 'pr', 'list', '-R', repo, '--author', '@me', '--state', 'open',
                                 '--limit', '100', '--json', 'number', cwd=cwd))
            targets += [{'kind': 'pr', 'repo': repo, 'number': r['number']} for r in rows]
    default_repo = None
    for t in args.targets:
        m = PR_URL.search(t)
        if m:
            targets.append({'kind': 'pr', 'repo': m.group(1), 'number': int(m.group(2))})
            continue
        m = PR_REF.match(t.strip())
        if not m:
            raise CollectError(f'not a PR number, owner/repo#N or PR URL: {t!r}')
        repo = m.group(1)
        if not repo:
            default_repo = default_repo or current_repo(cwd)
            if not default_repo:
                raise CollectError(f'{t}: run inside a GitHub repo, or write owner/repo#{m.group(2)}')
            repo = default_repo
        targets.append({'kind': 'pr', 'repo': repo, 'number': int(m.group(2))})
    seen, unique = set(), []
    for t in targets:
        key = (t['kind'], t.get('repo'), t.get('number'), t.get('branch'))
        if key not in seen:
            seen.add(key)
            unique.append(t)
    return unique


def collect_pr(t: dict, clone: str | None, context: int) -> dict:
    repo, n = t['repo'], t['number']
    meta = json.loads(sh('gh', 'pr', 'view', str(n), '-R', repo, '--json', PR_FIELDS))
    meta['kind'] = 'pr'
    meta['repo'] = repo
    meta['body'] = strip_html_comments(meta.get('body', ''))
    meta['commits'] = [
        {'oid': c['oid'], 'headline': c.get('messageHeadline', ''), 'body': c.get('messageBody', '')}
        for c in meta.get('commits', [])
    ]
    meta['reviews'] = [
        {'author': (r.get('author') or {}).get('login'), 'state': r.get('state'), 'body': strip_html_comments(r.get('body', ''))[:2000]}
        for r in meta.get('reviews', []) if r.get('body') or r.get('state') not in ('COMMENTED',)
    ]
    raw_comments = json.loads(sh('gh', 'api', '--paginate', f'repos/{repo}/pulls/{n}/comments', check=False) or '[]')
    meta['review_comments'] = [
        {'id': c['id'], 'reply_to': c.get('in_reply_to_id'), 'author': c['user']['login'], 'path': c.get('path'),
         'line': c.get('line') or c.get('original_line'), 'body': strip_html_comments(c.get('body', ''))[:2000]}
        for c in raw_comments
    ]
    meta['head_sha'] = meta['headRefOid']
    raw = None
    if clone:
        remote = remote_for(clone, repo)
        if remote:
            ref = f'refs/pr-walkthrough/{repo.replace("/", "__")}/{n}'
            git(clone, 'fetch', '-q', remote, f'+pull/{n}/head:{ref}', f'+{meta["baseRefName"]}:{ref}-base')
            base = git(clone, 'merge-base', f'{ref}-base', ref).strip()
            meta['diff_from'] = base
            raw = git(clone, 'diff', f'-U{context}', '--no-color', f'{base}..{ref}')
            meta['diff_source'] = 'git'
    if raw is None:
        raw = sh('gh', 'pr', 'diff', str(n), '-R', repo)
        meta['diff_source'] = 'gh'
    return {'meta': meta, 'raw': raw}


def collect_branch(t: dict, clone: str, context: int) -> dict:
    if not clone:
        raise CollectError('--branch needs to run inside the git repo that has the branch')
    base = t['base']
    if not base:
        head = git(clone, 'symbolic-ref', '--short', 'refs/remotes/origin/HEAD', check=False).strip()
        base = head.split('/', 1)[1] if head else 'main'
    branch = t['branch']
    head_sha = git(clone, 'rev-parse', branch).strip()
    merge_base = git(clone, 'merge-base', base, branch).strip()
    log = git(clone, 'log', '--reverse', '--format=%H%x1f%s%x1f%b%x1e', f'{merge_base}..{branch}')
    commits = []
    for rec in log.split('\x1e'):
        if rec.strip():
            oid, headline, body = (rec.strip().split('\x1f') + ['', ''])[:3]
            commits.append({'oid': oid, 'headline': headline, 'body': body.strip()})
    repo = current_repo(clone) or Path(clone).name
    meta = {
        'kind': 'branch', 'repo': repo, 'number': None, 'url': None,
        'title': commits[-1]['headline'] if commits else branch,
        'body': '\n\n'.join(c['body'] for c in commits if c['body']),
        'baseRefName': base, 'headRefName': branch, 'head_sha': head_sha, 'diff_from': merge_base,
        'commits': commits, 'reviews': [], 'review_comments': [], 'diff_source': 'git',
    }
    raw = git(clone, 'diff', f'-U{context}', '--no-color', f'{merge_base}..{head_sha}')
    return {'meta': meta, 'raw': raw}


def find_stack_parents(items: list, clone: str | None, context: int) -> None:
    """Mark PRs built on another PR of the batch, and narrow their diff to their own commits.

    A PR stacks on another when its base branch is the other's head branch, or (for PRs from
    a fork, which must all target a branch of the upstream repo) when the other's commits
    are a strict prefix of its own.
    """
    prs = [it for it in items if it['meta']['kind'] == 'pr']
    for it in prs:
        m = it['meta']
        mine = [c['oid'] for c in m['commits']]
        parent = None
        for other in prs:
            o = other['meta']
            if o is m or o['repo'] != m['repo']:
                continue
            theirs = [c['oid'] for c in o['commits']]
            if m['baseRefName'] == o['headRefName'] or (theirs and len(theirs) < len(mine) and mine[: len(theirs)] == theirs):
                if parent is None or len(theirs) > len(parent['meta']['commits']):
                    parent = other
        if parent is None:
            continue
        p = parent['meta']
        m['stack_parent'] = p['number']
        m['own_commits'] = [c for c in m['commits'] if c['oid'] not in {x['oid'] for x in p['commits']}]
        if clone and m.get('diff_source') == 'git':
            ref = f'refs/pr-walkthrough/{m["repo"].replace("/", "__")}/{m["number"]}'
            pref = f'refs/pr-walkthrough/{p["repo"].replace("/", "__")}/{p["number"]}'
            m['diff_from'] = git(clone, 'rev-parse', pref).strip()
            it['raw'] = git(clone, 'diff', f'-U{context}', '--no-color', f'{pref}..{ref}')
            m['diff_scope'] = 'own commits (the parent PR is reviewed on its own page)'


# ------------------------------------------------------------------ writing


def target_id(meta: dict) -> str:
    if meta['kind'] == 'pr':
        return f'pr-{meta["number"]}'
    return 'branch-' + re.sub(r'[^\w.-]+', '-', meta['headRefName'])


def write(item: dict, out: Path) -> dict:
    meta = item['meta']
    folder = out / meta['repo'].replace('/', '__') / target_id(meta)
    folder.mkdir(parents=True, exist_ok=True)
    previous = None
    old_meta = folder / 'meta.json'
    if old_meta.exists():
        old = json.loads(old_meta.read_text())
        if old.get('head_sha') != meta['head_sha']:
            previous = old.get('head_sha')
            dest = folder / 'history' / previous[:12]
            dest.mkdir(parents=True, exist_ok=True)
            for name in ('meta.json', 'diff.json', 'content.json', 'tests.json'):
                if (folder / name).exists():
                    shutil.move(str(folder / name), str(dest / name))
    files = parse_diff(item['raw'])
    diff = {'head_sha': meta['head_sha'], 'diff_from': meta.get('diff_from'), 'files': files}
    (folder / 'meta.json').write_text(json.dumps(meta, indent=1))
    (folder / 'diff.json').write_text(json.dumps(diff, indent=1))
    (folder / 'changes.diff').write_text(item['raw'])
    return {
        'id': target_id(meta), 'dir': str(folder), 'title': meta['title'], 'url': meta.get('url'),
        'head_sha': meta['head_sha'], 'previous_head': previous, 'stack_parent': meta.get('stack_parent'),
        'files': len(files), 'added': sum(f['added'] for f in files), 'deleted': sum(f['deleted'] for f in files),
        'has_content': (folder / 'content.json').exists(),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('targets', nargs='*', help='PR numbers, owner/repo#N or PR URLs')
    ap.add_argument('--mine', action='store_true', help='your open PRs')
    ap.add_argument('--all-repos', action='store_true', help='with --mine: every repo, not just this one')
    ap.add_argument('--branch', help='a local branch to walk through instead of a PR')
    ap.add_argument('--base', help='with --branch: the branch it is compared against (default: the default branch)')
    ap.add_argument('--out', default=os.environ.get('PR_WALKTHROUGH_HOME', str(Path.home() / '.cache' / 'pr-walkthrough')))
    ap.add_argument('--context', type=int, default=4)
    args = ap.parse_args()
    cwd = os.getcwd()
    clone = git_root(cwd)
    try:
        targets = resolve_targets(args, cwd)
        if not targets:
            ap.error('nothing to collect: give PR numbers or URLs, --mine, or --branch')
        items = [collect_pr(t, clone, args.context) if t['kind'] == 'pr' else collect_branch(t, clone, args.context)
                 for t in targets]
        find_stack_parents(items, clone, args.context)
        out = Path(args.out).expanduser()
        summary = [write(it, out) for it in items]
    except CollectError as exc:
        sys.exit(f'collect: {exc}')
    print(json.dumps({'out': str(Path(args.out).expanduser()), 'targets': summary}, indent=1))


if __name__ == '__main__':
    main()
