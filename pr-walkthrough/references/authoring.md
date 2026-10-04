# Writing one walkthrough

Read `content-schema.md` and `writing-style.md` first. This file is the order of work and the
judgment calls.

## 1. Learn the change before writing anything

- Read `meta.json`: title, description, commits (their messages often hold the real reasoning),
  linked issues, reviews and `review_comments`. A review thread that ended in a change is reasoning
  worth a sentence on the page.
- Read `diff.json` and `changes.diff`. For context around a hunk, read the file at the head commit
  (`git show <head_sha>:<path>` in a local clone, or `gh api repos/<repo>/contents/<path>?ref=<sha>`).
- Find the reasoning, best source first, and set `thinking.source` to match:
  1. `author-notes`: a decision log (see `decision-log.md`), notes the author left in the repo or the
     PR, or your own memory of writing the PR in this session. If you wrote the PR, you are the
     author: write the thinking from what you actually did and rejected.
  2. `pr-text`: the PR description, commit messages, issues and review threads.
  3. `inferred`: only the code. Say so, keep it short, and put open points in `review.questions`.
- If the PR's tests can run locally, run them before and after (`scripts/tests_before_after.py`).
  Real outcomes beat descriptions of tests.

## 2. Write the review layer first

It is what a reviewer reads first, and choosing it forces you to find the risky parts.
- `look_first`: the places where a mistake would hurt most (concurrency, security checks, data
  migrations, error paths, public interfaces, deleted safety checks), riskiest first, 1 to 5 items.
- Risk levels: `high` means a mistake breaks users or data or opens a hole; `medium` means wrong
  behavior in some cases; `low` means cosmetic or easy to spot.
- A `check` on every chunk that carries behavior: one concrete thing to verify, phrased so the
  reviewer can answer yes or no.
- `questions` only for real gaps the code and PR text leave open.

## 3. Write the walkthrough

- `summary` and `before_after`: what changes for someone using the code. Concrete.
- `background` only when the reader needs context about this part of the code to follow the change.
- `problem`: the bug or need, with real output if there is any.
- `thinking`: what was noticed, how it was confirmed, the options weighed and why one won.
- `files`: every changed file, main logic first. Group lines into chunks by idea. Fold supporting
  chunks. One chunk per test function, saying what it proves.
- `concepts`: the lessons the code needs (the builder adds prerequisites). `concept_hooks` may say,
  in one sentence each, where a lesson's idea shows up in this PR; the lesson panel shows it.
- If a lesson the page needs does not exist, add it to `<repo-folder>/lessons.json` in the same shape
  as `lessons/core.json` (id, title, level, prereqs, short, body, optional example). Keep it general so
  other pages can reuse it.

## 4. Check and build

`python3 scripts/build.py <target-folder>` until it prints `built:` with no errors. Fix warnings about
length by folding and cutting, not by dropping coverage. Then reread the page text once against
`writing-style.md`.

## Big PRs: split the work

When a PR changes more than about 600 lines, write the review layer, summary, problem and thinking
yourself, then give groups of files to helpers (subagents) in parallel. Each helper writes the
`files` entries for its group into a separate file (for example `content.part-2.json` holding a
`files` list), following the schema and the style. Merge the parts into `content.json` in reading
order, then build. Helpers must not edit `content.json` directly, so they cannot overwrite each
other.

## Batches: "all the PRs I made"

Collect them in one `collect.py` call so stacks are found (a PR built on another covers only its own
commits). Write and build each page; one helper per PR works well, as each page is independent once
collected. Build the repo folder last, so `index.html` lists them in reading order with the stack drawn.

## After new commits

Run `collect.py` again for the PR. If it reports a `previous_head`, run `scripts/carry_notes.py
<target-folder>`: it moves the old notes onto the new diff and lists only the lines that need notes.
Write those, recheck `look_first`, the summary and the risks against the new code, and build. The page
marks what changed since the last read.
