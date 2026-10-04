# Decision log: keep one while you make a PR

A walkthrough is only as honest as its reasoning section. Reasoning written down while the work
happens is far better than reasoning reconstructed from a diff afterwards. When you (an agent or a
person) make a PR that may be walked through later, keep a short log as you go and leave it where
the walkthrough can find it: in the PR description under a "Decision log" heading, or in a file the
walkthrough author is pointed to. Do not commit it to the repo unless the team wants that.

Keep each entry to a few lines. Record what happened, not a polished story.

```markdown
## Decision log: <PR title>

### What I noticed
- <the symptom, with the real output or numbers>

### How I confirmed it
- <the test, run or trace that proved the cause>

### Options
- <option A>: chosen, because <reason>
- <option B>: rejected, because <reason>

### What review changed
- <reviewer or bot>: <finding> -> <fixed / declined, and why>

### Known limits
- <what this PR deliberately does not cover>
```

A walkthrough built from such a log sets `thinking.source` to `author-notes`, and the page tells the
reader the reasoning came from the author.
