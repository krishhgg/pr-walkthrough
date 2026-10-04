#!/usr/bin/env bash
# Install (or update) pr-walkthrough for every coding agent on this machine.
#
#   git clone https://github.com/krishhgg/pr-walkthrough.git ~/.local/share/pr-walkthrough
#   ~/.local/share/pr-walkthrough/install.sh
#
# Run it again any time to update. It links the skill into ~/.agents/skills, which many
# agents read directly (Codex, Cursor, Gemini CLI, OpenCode, Amp, Cline, Factory and others),
# and into the skills folder of every other agent whose home folder exists here (Claude Code,
# Kiro, Qwen Code, Goose, Windsurf, Crush and others). Agents that are not installed get nothing.
# Set PR_WALKTHROUGH_SRC to keep the clone somewhere else.
set -euo pipefail

REPO_URL="https://github.com/krishhgg/pr-walkthrough.git"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${PR_WALKTHROUGH_SRC:-$HERE}"
if [ ! -f "$SRC/pr-walkthrough/SKILL.md" ]; then
  SRC="${PR_WALKTHROUGH_SRC:-$HOME/.local/share/pr-walkthrough}"
  if [ -d "$SRC/.git" ]; then git -C "$SRC" pull --ff-only -q; else git clone -q "$REPO_URL" "$SRC"; fi
elif [ -d "$SRC/.git" ] && git -C "$SRC" remote get-url origin >/dev/null 2>&1; then
  git -C "$SRC" pull --ff-only -q || echo "note: could not fast-forward $SRC; using it as it is"
fi
SKILL="$SRC/pr-walkthrough"
SHARED="$HOME/.agents/skills/pr-walkthrough"

link() {  # link <skills-dir> <target>
  local dir="$1" target="$2" dest="$1/pr-walkthrough"
  mkdir -p "$dir"
  if [ -L "$dest" ] || [ ! -e "$dest" ]; then
    ln -sfn "$target" "$dest"
    echo "  linked  ${dest/#$HOME/~}"
  else
    echo "  skipped ${dest/#$HOME/~} (a real folder is already there; remove it to link)"
  fi
}

echo "pr-walkthrough from ${SKILL/#$HOME/~}"
link "$HOME/.agents/skills" "$SKILL"

# Agents with their own skills folder, from the skills.sh agent table. The folder before
# "/skills" (or the first part of it) must already exist, so only installed agents get a link.
while read -r rel; do
  [ -z "$rel" ] && continue
  home="${rel%/skills}"
  top="${home%%/*}"
  if [ -d "$HOME/$home" ] || { [ "$top" != ".config" ] && [ -d "$HOME/$top" ]; }; then
    link "$HOME/$rel" "$SHARED"
  fi
done <<'AGENTS'
.adal/skills
.aider-desk/skills
.astrbot/data/skills
.augment/skills
.autohand/skills
.bob/skills
.claude/skills
.codeartsdoer/skills
.codebuddy/skills
.codeium/windsurf/skills
.codemaker/skills
.codestudio/skills
.commandcode/skills
.config/crush/skills
.config/devin/skills
.config/goose/skills
.config/kimchi/harness/skills
.continue/skills
.forge/skills
.fx/skills
.grok/skills
.hermes/skills
.iflow/skills
.inferencesh/skills
.jazz/skills
.junie/skills
.kiro/skills
.kode/skills
.lingma/skills
.mcpjam/skills
.minimax/skills
.moxby/skills
.mux/skills
.neovate/skills
.ona/skills
.openclaw/skills
.openhands/skills
.pi/agent/skills
.pochi/skills
.posit/assistant/skills
.qoder-cn/skills
.qoder/skills
.qwen/skills
.reasonix/skills
.roo/skills
.rovodev/skills
.snowflake/cortex/skills
.tabnine/agent/skills
.terramind/skills
.tinycloud/skills
.trae-cn/skills
.trae/skills
.vibe/skills
.zcode/skills
.zencoder/skills
.codex/skills
AGENTS

echo "Done. Start a new agent session and ask it to walk you through a PR."
