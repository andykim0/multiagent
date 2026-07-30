#!/usr/bin/env bash
# Install the 4-role team into a project.
#
#   ./init.sh /path/to/your/project     # existing repo
#   ./init.sh ~/new-project             # creates the directory if missing
#
# Never overwrites your CLAUDE.md or .claude/settings.json. If either already
# exists it writes a *.team file beside it and tells you what to merge.

set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:-}"

if [ -z "$DEST" ]; then
  echo "usage: ./init.sh /path/to/your/project" >&2
  exit 1
fi

mkdir -p "$DEST"
DEST="$(cd "$DEST" && pwd)"

if [ "$SRC" = "$DEST" ]; then
  echo "source and destination are the same directory; nothing to do." >&2
  exit 1
fi

echo "==> installing into $DEST"

# --- agent definitions + hook scripts: safe to copy, they're ours ------------
mkdir -p "$DEST/.claude/agents" "$DEST/scripts"
cp "$SRC/.claude/agents/"*.md "$DEST/.claude/agents/"
cp "$SRC/scripts/"*.py "$SRC/scripts/"*.sh "$DEST/scripts/"
  chmod +x "$DEST/scripts/"*.sh
echo "    .claude/agents/  4 agent definitions"
echo "    scripts/         2 hooks + codex bridge"

# --- CLAUDE.md: every agent loads this, so don't clobber a existing one ------
if [ -f "$DEST/CLAUDE.md" ]; then
  cp "$SRC/CLAUDE.md" "$DEST/CLAUDE.team.md"
  MERGE_CLAUDE=1
  echo "    CLAUDE.md        EXISTS — wrote CLAUDE.team.md instead"
else
  cp "$SRC/CLAUDE.md" "$DEST/CLAUDE.md"
  MERGE_CLAUDE=0
  echo "    CLAUDE.md        team contract"
fi

# --- settings.json: same treatment ------------------------------------------
if [ -f "$DEST/.claude/settings.json" ]; then
  cp "$SRC/.claude/settings.json" "$DEST/.claude/settings.team.json"
  MERGE_SETTINGS=1
  echo "    settings.json    EXISTS — wrote .claude/settings.team.json instead"
else
  cp "$SRC/.claude/settings.json" "$DEST/.claude/settings.json"
  MERGE_SETTINGS=0
  echo "    settings.json    depth cap + timeline hooks"
fi

# --- working directories the agents write into -------------------------------
mkdir -p "$DEST/.agents/prompts" "$DEST/.agents/critiques" \
         "$DEST/.agents/design" "$DEST/.agents/accepted" \
         "$DEST/.agents/codex-in" "$DEST/.agents/codex-out" \
         "$DEST/.agents/codex-logs"
echo "    .agents/         prompts critiques design accepted codex-in/out/logs"

# --- keep run artifacts out of git, keep the config in ----------------------
if [ -d "$DEST/.git" ] || [ -f "$DEST/.gitignore" ]; then
  touch "$DEST/.gitignore"
  grep -qxF '.agents/' "$DEST/.gitignore" || {
    printf '\n# multiagent run artifacts (config in .claude/ stays tracked)\n.agents/\n' \
      >> "$DEST/.gitignore"
    echo "    .gitignore       added .agents/"
  }
fi

# --- verify ------------------------------------------------------------------
echo
echo "==> verifying"
MISSING=0
for f in .claude/agents/project-leader.md .claude/agents/logic-reviewer.md \
         .claude/agents/software-engineer.md .claude/agents/uiux-designer.md \
         scripts/guard_reviewer_writes.py scripts/log_subagent.py \
         scripts/run_codex.sh; do
  if [ -f "$DEST/$f" ]; then echo "    ok    $f"; else echo "    MISS  $f"; MISSING=1; fi
done

if command -v python3 >/dev/null 2>&1; then
  echo "    ok    python3 ($(python3 --version 2>&1))  — required by the hooks"
else
  echo "    MISS  python3 — the hooks need it on PATH"; MISSING=1
fi

if command -v claude >/dev/null 2>&1; then
  echo "    ok    claude ($(claude --version 2>&1 | head -1))"
  echo "          need v2.1.170+ for the fable alias, v2.1.217+ for the depth cap"
else
  echo "    MISS  claude not on PATH — npm i -g @anthropic-ai/claude-code"; MISSING=1
fi

if command -v codex >/dev/null 2>&1; then
  echo "    ok    codex ($(codex --version 2>&1 | head -1))"
else
  echo "    MISS  codex not on PATH — npm i -g @openai/codex, then: codex login"
  MISSING=1
fi

for VAR in ANTHROPIC_API_KEY CODEX_API_KEY OPENAI_API_KEY; do
  if [ -n "${!VAR:-}" ]; then
    echo "    warn  $VAR is set — this setup is login-only; unset it to avoid"
    echo "          silently switching to metered API billing"
  fi
done

echo
[ "${MERGE_CLAUDE:-0}" = 1 ] && cat <<'MSG'
!! MERGE NEEDED: append CLAUDE.team.md into your CLAUDE.md, then delete it.
   Every agent loads CLAUDE.md — the artifact paths and reporting rules must be
   in it or the specialists won't know where to write.
MSG
[ "${MERGE_SETTINGS:-0}" = 1 ] && cat <<'MSG'
!! MERGE NEEDED: copy the "env" and "hooks" keys from
   .claude/settings.team.json into your .claude/settings.json, then delete it.
   Without CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1 the specialists can spawn
   their own subagents and your flat topology stops being flat.
MSG

cat <<MSG
==> start the team:

    cd $DEST
    claude --agent project-leader

  Then give it a task. Accept the workspace-trust prompt on first run, or the
  reviewer's write-guard hook is skipped.

==> check the topology actually ran:

    cat .agents/timeline.jsonl     # logic-reviewer must start BEFORE software-engineer
    ls .agents/critiques/          # empty means step 2 was skipped
MSG

exit $MISSING
