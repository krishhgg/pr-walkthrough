# pr-walkthrough

A skill for Claude Code and Codex that turns pull requests into local HTML pages you can review
from in about 10 minutes, instead of scrolling a long diff.

Each page has:

- **A review guide.** A change map (files grouped as code, tests, config and docs), the places to look
  first with the risk in each, and open questions for the author.
- **The change, explained.** What changed and why, before and after, how the change was worked out
  (from the author's own notes when there are any, and labelled as an inferred reading when there
  are not), every changed line with a note, the tests, and the risks.
- **Review helpers on every change.** Whether it adds, removes or changes code, what to check there,
  and a link that opens that exact line on GitHub so you can leave a comment.
- **Lessons one click away.** Every technical term links to a short lesson, from "what is a function"
  up to concurrency, testing and LLM agents. Readers who know the basics skip them; learners click.
- **"Updated since you last read".** Re-run it after new commits and the page marks what changed.

It works on one PR, a list, a stack of PRs built on each other, your open PRs, or every PR an agent
opened in a session ("make walkthroughs for all the PRs you made"), with an index page for the set.
Pages stay on your machine; nothing is posted to GitHub.

## Install

Requirements: git, Python 3.9 or newer, and the GitHub CLI (`gh auth login`) for PRs.

```bash
git clone https://github.com/krishhgg/pr-walkthrough.git ~/.local/share/pr-walkthrough
~/.local/share/pr-walkthrough/install.sh
```

That makes the skill available to every coding agent on the machine. It links the skill into
`~/.agents/skills`, which many agents read directly (Codex, Cursor, Gemini CLI, OpenCode, Amp,
Cline, Factory and others), and into the skills folder of each other agent you have installed
(Claude Code, Kiro, Qwen Code, Goose, Windsurf, Crush and more). Run `install.sh` again to update.

With Node, the [skills.sh](https://skills.sh) installer works too:
`npx skills add krishhgg/pr-walkthrough -g` (update with `npx skills update -g`).

## Use

Ask in plain words, from inside a clone of the repo:

- "Walk me through PR 2521."
- "Make walkthroughs for all the PRs you opened today."
- "I need to review #812 and #815, they're huge."
- "Catch me up on my open PRs." (uses `--mine`)
- "Explain what my branch `feature-x` changes before I open a PR."

The agent collects the PRs, writes each page, checks it (every changed line must have a note and
every link must resolve), and tells you where the pages are: by default
`~/.cache/pr-walkthrough/<owner>__<repo>/`, with `index.html` for the set. Set `PR_WALKTHROUGH_HOME`
to keep them elsewhere. Working on a remote machine? Ask the agent to serve the folder and open the
URL it gives you.

## For agents that write PRs

The reasoning section is only as good as what was written down at the time. If agents on your team
open PRs, have them keep the short decision log in `pr-walkthrough/references/decision-log.md` (what
was noticed, how it was confirmed, the options, what review changed) and put it in the PR description.
Walkthroughs built from it show the reasoning as the author's own.

## Lessons

The library lives in `pr-walkthrough/lessons/`: `core.json` for general programming, git, testing and
review, and `pack-ai-agents.json` for LLM apps and agents. A team can add its own lessons in
`<walkthrough-folder>/<owner>__<repo>/lessons.json`; good general lessons are worth sending back here.

## Layout

```
pr-walkthrough/            the skill folder (what you install)
  SKILL.md                 when and how the agent uses it
  scripts/                 collect.py, carry_notes.py, build.py, measure.py, tests_before_after.py
  assets/                  the page template and its script
  references/              content schema, writing style, authoring guide, decision log
  lessons/                 the lessons library
```

## License

MIT. See `LICENSE`.
