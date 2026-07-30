#!/usr/bin/env bash
# Bridge: hand one work packet to GPT-5.6 Sol via the Codex CLI.
#
#   scripts/run_codex.sh <prompt-file> <output-file> [model] [effort]
#
# Auth is Codex's own ChatGPT sign-in — no API key is read or needed. Do NOT set
# CODEX_API_KEY; that would switch Codex to metered API billing.
#
# The prompt is passed via a file rather than a shell argument so that quotes,
# backticks and newlines in the packet can't be mangled by the shell.
#
# Sol on a ChatGPT account is unreliable right now (see SETUP.md), so a rejection
# falls back to Terra rather than failing the whole run. The output file records
# which model actually ran, so the leader is never misled about what produced the
# code.
set -uo pipefail

PROMPT_FILE="${1:?usage: run_codex.sh <prompt-file> <output-file> [model] [effort]}"
OUT_FILE="${2:?missing output file}"
MODEL="${3:-gpt-5.6-sol}"
EFFORT="${4:-high}"
FALLBACK="gpt-5.6-terra"

command -v codex >/dev/null 2>&1 || {
  echo "ERROR: codex not on PATH. npm i -g @openai/codex, then: codex login" >&2
  exit 127
}
[ -f "$PROMPT_FILE" ] || { echo "ERROR: no prompt file at $PROMPT_FILE" >&2; exit 2; }

mkdir -p "$(dirname "$OUT_FILE")" .agents/codex-logs
LOG=".agents/codex-logs/$(date -u +%Y%m%dT%H%M%SZ).stderr.log"

run() {
  local model="$1"
  # --sandbox workspace-write replaces the deprecated --full-auto.
  # Progress goes to stderr, the final message to stdout; -o also writes it.
  codex exec \
    --sandbox workspace-write \
    --skip-git-repo-check \
    --ephemeral \
    -m "$model" \
    -c model_reasoning_effort="$EFFORT" \
    -o "$OUT_FILE" \
    "$(cat "$PROMPT_FILE")" \
    >/dev/null 2>>"$LOG"
}

echo "codex: $MODEL effort=$EFFORT  (stderr -> $LOG)" >&2
run "$MODEL"
STATUS=$?

if [ $STATUS -ne 0 ] && grep -qi "not supported when using Codex with a ChatGPT account" "$LOG"; then
  echo "codex: $MODEL rejected on this ChatGPT account; retrying $FALLBACK" >&2
  MODEL="$FALLBACK"
  run "$MODEL"
  STATUS=$?
fi

if [ $STATUS -ne 0 ]; then
  echo "ERROR: codex exec failed (exit $STATUS). Last stderr lines:" >&2
  tail -20 "$LOG" >&2
  exit $STATUS
fi

# Stamp the provenance so nobody has to trust a summary about which model ran.
printf '\n\n---\nMODEL_USED: %s\nEFFORT: %s\nSTDERR_LOG: %s\n' \
  "$MODEL" "$EFFORT" "$LOG" >> "$OUT_FILE"
echo "codex: done as $MODEL -> $OUT_FILE" >&2
