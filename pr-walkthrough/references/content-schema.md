# content.json: what a walkthrough page says

One `content.json` per target folder (next to `meta.json` and `diff.json` from `collect.py`).
All HTML strings follow `writing-style.md` and may link a lesson with `[[lesson-id|shown text]]`
(ids from the skill's `lessons/*.json` or the repo's own `lessons.json`). `build.py` checks
everything under "Checks" and refuses to build a page that fails them.

```json
{
  "summary": "<p>3 to 5 plain sentences: what this PR changes for someone using the code, and why.</p>",
  "before_after": {"before": "<p>What happens today, concretely.</p>", "after": "<p>What happens with this PR.</p>"},
  "background": "<p>Only the context this PR needs: what this part of the code does. Optional.</p>",
  "problem": "<p>The bug or need, with real output or numbers where there are any.</p>",
  "diagrams": [{"id": "d1", "title": "Sentence-case title", "caption": "<p>What to look at.</p>", "kind": "flow", "spec": {}}],
  "concepts": ["function", "dictionary", "exception"],
  "concept_hooks": {"exception": "Where this idea shows up in this PR, in one sentence."},
  "thinking": {
    "source": "author-notes",
    "steps": [{"title": "What was noticed", "html": "<p>...</p>"}, {"title": "How it was confirmed", "html": "<p>...</p>"}],
    "options": [
      {"name": "Raise the limit everywhere", "html": "<p>How it would work.</p>", "verdict": "rejected", "why": "<p>...</p>"},
      {"name": "Give long text its own budget", "html": "<p>...</p>", "verdict": "chosen", "why": "<p>...</p>"}
    ],
    "decision": "<p>The final design in one or two sentences.</p>",
    "lesson": "<p>The general habit this PR shows, in one sentence.</p>"
  },
  "review": {
    "look_first": [
      {"path": "src/cache.py", "new": [40, 58], "risk": "high", "why": "The lock now covers the read and the write; check that nothing slow runs inside it."}
    ],
    "questions": ["<p>Why is the timeout 300 seconds and not configurable per tool?</p>"]
  },
  "files": [
    {
      "path": "src/cache.py",
      "role": "<p>What this file is for, in one sentence.</p>",
      "chunks": [
        {"new": [40, 58], "html": "<p>What these lines do and why.</p>", "check": "That the lock is released on the error path too.", "risk": "high"},
        {"old": [12, 15], "new": [12, 13], "html": "<p>A replacement: old lines out, new lines in.</p>", "fold": true},
        {"old": [90, 91], "html": "<p>Lines removed with nothing in their place.</p>"}
      ]
    }
  ],
  "tests": "<p>How the tests prove the change: what each new test checks and whether it fails without the fix.</p>",
  "risks": [{"risk": "<p>What could go wrong.</p>", "answer": "<p>Why it won't, or how it is handled.</p>"}]
}
```

## The review fields

- `thinking.source` says where the reasoning on the page comes from, and the page shows it as a label:
  - `author-notes`: the author's own record (a decision log, the agent's notes, its session). Strongest.
  - `pr-text`: the PR description, commit messages, linked issues and review threads.
  - `inferred`: read from the code by the reviewer. Write it as an informed reading ("this looks
    meant to..."), never as the author's stated intent.
- `review.look_first`: 1 to 5 places, riskiest first. Each names a `path`, a line range on the `new`
  side (or `old` for removed code), a `risk` (`high`, `medium` or `low`) and a one-sentence `why`
  that says what could break there. The page links each item to its chunk.
- `review.questions`: optional. Things the reviewer should ask the author because the code and the
  PR text do not answer them. Leave them out when there are none; do not invent filler questions.
- Per chunk, `check` is one sentence telling the reviewer what to verify in those lines ("that the
  retry stops after 3 attempts", "that a missing key returns 404, not 500"). Give it to chunks that
  carry behavior; skip it on plumbing, docs and obvious renames. `risk` is optional per chunk.
- The page adds the rest by itself: a change map (files grouped as code, tests, config and docs,
  with sizes), an added, removed or changed label on every chunk, a "Comment on GitHub" link to each
  chunk's first changed line, and "updated since you last read" marks after new commits.

## Line numbers in chunks

- `new: [a, b]` are line numbers after the PR (the `+` side); `old: [a, b]` before it (the `-` side).
  Both are inclusive. Take them from `diff.json`: `files[].hunks[].lines[]` carry `t` (ctx, add,
  del), `old`, `new` and `text`.
- Every `add` and `del` line belongs to exactly one chunk of its file. Unchanged lines may sit inside
  a chunk when they help; otherwise the page folds them. Chunks never overlap; order them top to bottom.
- Every file with changed lines appears in `files`, in reading order: the main logic first, then
  supporting code, then tests, config and docs.

## Diagram kinds

- `flow`: `{"nodes": [{"id": "a", "label": "Parse request", "col": 0, "row": 0, "tone": "plain|good|bad|accent"}], "edges": [{"from": "a", "to": "b", "label": "optional"}]}`. At most 4 columns, 6 rows.
- `sequence`: `{"actors": ["Client", "Server", "DB"], "steps": [{"from": "Client", "to": "Server", "label": "POST /items", "tone": "plain|good|bad"}]}`.
- `compare`: `{"left": {"title": "Before", "tone": "bad", "items": ["..."]}, "right": {"title": "With this PR", "tone": "good", "items": ["..."]}}`.
- `bars`: `{"unit": "ms", "rows": [{"label": "Before", "value": 420, "tone": "bad"}, {"label": "After", "value": 90, "tone": "good"}]}`.
- `strip`: `{"segments": [{"text": "kept part", "kind": "keep"}, {"text": "... dropped ...", "kind": "drop"}], "note": "optional"}`.

## Length budget: 10 minutes

A reader should read the page, understand the change and move on in 10 minutes. `build.py` warns
above 10 (`measure.py <folder>` shows the estimate): about 1,300 words of open prose and at most 150
open code lines.

- `summary` up to 80 words; `before_after` up to 60 words a side; `background` up to 120; `problem`
  up to 150; at most 2 diagrams.
- `thinking`: 2 or 3 short steps, at most 2 options, a one-line decision and a one-line lesson.
- `tests` up to 120 words; `risks` up to 3 items of up to 40 words.
- Chunk notes: 1 to 3 short sentences. `"fold": true` keeps the note visible and hides the code until
  opened; use it for plumbing, docstrings, logging, signature threading and repetitive entries.
  Leave open only the chunks that carry the main idea.
- Test, doc, lock and dependency files fold automatically. Give each a one-sentence `role` and one
  chunk per test function whose note says what that test proves.
- A PR too big to explain in 10 minutes is a finding: say so in `review.questions` ("could this be
  split into ...?") and fold harder rather than drop coverage.

## Optional: tests.json

`{"command": "pytest tests/test_cache.py", "rows": [{"name": "test_lock_released_on_error", "before": "failed", "after": "passed", "before_msg": "AssertionError: ..."}]}`.
`scripts/tests_before_after.py` writes it from real runs; the page shows it as a folded table.

## Checks (build fails on any)

- JSON parses; `summary`, `before_after`, `problem`, `thinking`, `files`, `tests`, `risks` and `review` exist.
- Every `[[id|text]]`, `concepts` and `concept_hooks` id is a known lesson; no em or en dash characters.
- Every changed line is covered exactly once; every chunk hits a diff line; chunks do not overlap.
- `review.look_first` has 1 or more items, each pointing at real lines, with a `why`; `risk` values
  are `low`, `medium` or `high`; `thinking.source` is one of the three sources.
