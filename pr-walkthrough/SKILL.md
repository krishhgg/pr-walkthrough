---
name: pr-walkthrough
description: Turn pull requests (or local branches) into local HTML walkthrough pages that a reviewer can read and understand in about 10 minutes, with what changed, why it changed (the author's reasoning, or an inferred reading clearly labelled), where to look first, what to check in each change, a link from each change to its line on GitHub for comments, lessons one click away for any term, and marks for what changed since the last read. Works on one PR, a list, a stacked set, or every PR you (or the agent) made. Use this whenever someone wants to review, understand, explain, catch up on, or walk through a PR or a set of PRs, says the diff is too big or hard to follow, asks "what does this PR do", "explain my PRs", "make walkthroughs for all the PRs you opened", or wants teammates to review agent-written PRs faster, even if they do not say "walkthrough".
---

# PR walkthrough

Make one self-contained HTML page per pull request: a review guide on top (change map, where to look
first, questions for the author), then a walkthrough that explains every changed line with the
reasoning behind it, the tests, the risks, and a library of lessons for any term a reader does not
know. The changed files sit in a VS Code style editor beside the text, with comments that explain the
code line by line, and clicking any part of the text opens the lines it talks about. Pages stay on the reader's machine; nothing is posted anywhere.

Everything a page says must be checkable against the diff, and the builder enforces it: every added
or removed line has exactly one note, every link resolves, and the page reads in about 10 minutes.
That discipline is what makes the page trustworthy enough to review from.

Paths below are relative to this skill's folder (the one holding this file). Scripts need Python 3,
git, and the GitHub CLI (`gh`, logged in) for PRs.

## 1. Collect

Run from inside a local clone of the repo when you can: the scripts then use git for exact diffs and
can tell a stacked PR's own commits from its parent's.

```bash
python3 scripts/collect.py 2521 2522            # PRs in this repo
python3 scripts/collect.py owner/repo#12 https://github.com/o/r/pull/34
python3 scripts/collect.py --mine                # your open PRs in this repo (--all-repos for every repo)
python3 scripts/collect.py --branch feature-x    # a local branch, no PR needed (--base main)
```

"All the PRs you made" means the PRs created in this session (you know their numbers or URLs), or,
if the user means their own, `--mine`. Collect a set in one call so stacks are found.

It prints a JSON summary: each target's folder (default `~/.cache/pr-walkthrough/<owner>__<repo>/pr-<n>/`,
override with `--out` or `$PR_WALKTHROUGH_HOME`), its size, its stack parent, and `previous_head` when an
earlier walkthrough of an older commit exists. Each folder holds `meta.json` (description, commits,
reviews, review comments), `diff.json` (the change with line numbers) and `changes.diff`.

## 2. Bring an existing page up to date (only when `previous_head` is set)

```bash
python3 scripts/carry_notes.py <target-folder>
```

It moves the old notes onto the new diff and lists only the lines that still need notes. Write those,
recheck the review guide, summary and risks against the new code, and skip to step 4. The page marks
everything that changed since the last read.

## 3. Write content.json

Read `references/authoring.md` (the order of work and the judgment calls), `references/content-schema.md`
(the exact shape and the checks) and `references/writing-style.md` (the voice). Then write
`<target-folder>/content.json`. The essentials:

- **Find the reasoning before writing.** Commit messages, the PR description, linked issues and review
  threads usually hold it. If you wrote the PR in this session, you are the author: use what you
  actually tried and rejected. Set `thinking.source` to `author-notes`, `pr-text` or `inferred`; the
  page shows the reader which, so never present a guess as the author's intent.
- **Review layer first.** `review.look_first` names the 1 to 5 riskiest places with a one-sentence
  why. Each chunk that carries behavior gets a `check`: one concrete thing to verify. `review.questions`
  holds real open questions only.
- **Walkthrough.** Summary, before and after, the problem, how the change was worked out, then every
  changed file in reading order, lines grouped into chunks by idea. Fold supporting chunks so the page
  stays near 10 minutes; tests, docs and lock files fold by themselves.
- **The code beside the text.** The page shows every changed file in an editor on the right, and the
  text drives it. Write `annotations` (comments drawn between the code lines, page only, never in the
  PR) that explain the added code step by step: what each step does and why it is written that way.
  They must cover at least 90% of the added code lines of each source file. Link claims to lines with
  `[[path:first-last|text]]`, and give sections `code_refs` so clicking a heading opens its code.
- **Lessons.** List the ideas the code uses in `concepts`; link terms with `[[lesson-id|text]]`. The
  library is in `lessons/` (general programming in `core.json`, LLM apps and agents in
  `pack-ai-agents.json`). Add a missing lesson to `<repo-folder>/lessons.json` rather than defining
  terms inline.
- **Real evidence.** If the PR's tests run locally, run them before and after with
  `scripts/tests_before_after.py <target-folder> --cmd "<runner> {tests} <junit flag> {junit}"` and
  describe the real outcomes. Never invent outputs or numbers.

For a PR over about 600 changed lines, or a batch of several PRs, split the writing across helpers
(subagents) as `references/authoring.md` describes: one helper per PR, or per group of files of a big
PR, each writing to its own file, merged before the build.

## 4. Build and check

```bash
python3 scripts/build.py <target-folder> [<target-folder> ...]   # or the repo folder to build all
```

Fix every error it prints and rerun until it says `built:`. A warning above 10 minutes means fold
more and cut prose, not drop coverage. It writes `<target>/walkthrough.html` per page and refreshes
`<repo-folder>/index.html` (every built page, stacks in reading order) and `<repo-folder>/lessons.html`.

## 5. Hand it over

Tell the user where the pages are and give a one-line summary per PR (its look-first item, any open
question). Pages are single files: open them in a browser. If the user is on another machine, offer to
serve the folder (`python3 -m http.server --directory <repo-folder> <port>`) and give the URL; serve only
that folder, never a directory holding secrets such as `.env` files.

## Rules of thumb

- Coverage is not negotiable; length is managed by folding, grouping and cutting words.
- Describe the code as it is at the collected head commit. If a reviewer comment led to a change,
  that is worth a sentence; unresolved threads belong in `review.questions`.
- Keep the page about this PR. A stacked PR's page covers only its own commits and links its parent.
- Nothing is posted to GitHub. The "Comment on GitHub" links only open the PR at the right line.
