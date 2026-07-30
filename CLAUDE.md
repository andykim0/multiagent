# Team contract

Every agent in this project — the leader and all three specialists — loads this
file. Role-specific instructions live in `.claude/agents/`.

## Topology

The leader is the main Claude Code session. The reviewer and designer are Claude
subagents. The engineer is a thin Haiku bridge that shells out to the Codex CLI,
so the implementation is done by GPT-5.6 Sol on your ChatGPT sign-in.

Subagents can only report back to the leader; they cannot message each other.
Nesting is capped at 1 layer. The flat shape is enforced by configuration, not
convention.

Neither vendor is reached by API key. Claude Code uses your Claude plan login,
Codex uses your ChatGPT login. Do not set ANTHROPIC_API_KEY or CODEX_API_KEY —
either would silently switch that side to metered API billing.

## Artifact locations

    .agents/BRIEF.md              goal + acceptance criteria        (leader)
    .agents/prompts/<id>.md       dispatched work packets           (leader)
    .agents/critiques/<id>.rN.md  prompt critiques + 2nd opinions   (reviewer)
    .agents/design/               design.md tokens.json a11y.md     (designer)
    .agents/codex-in/<id>.md      instruction sent to Codex          (bridge)
    .agents/codex-out/<id>.md     Codex's reply + MODEL_USED stamp   (bridge)
    .agents/codex-logs/           Codex stderr, one file per run      (bridge)
    .agents/accepted/<id>.md      acceptance records                (leader)
    .agents/STATUS.md             live board                        (leader)

Implementation goes in the real source tree, not under `.agents/`.

## Reporting rules

- Return a short report, not file contents. Reference paths. Everything you
  return is spent from the leader's context window, and the leader runs the most
  expensive model in the team.
- End every report with this block and nothing after it:

      STATUS: done | blocked | needs_input
      ARTIFACTS: <paths you created or changed>
      SUMMARY: <=60 words
      RISKS: <one line, or "none">
      HANDOFF: <what the leader must know, <=40 words>

- `blocked` is a legitimate and useful outcome. Guessing is not. If the packet
  contradicts itself or depends on something that doesn't exist, say so and stop.
- Never claim a file exists without having created it. Never report a test as
  passing without having run it.
