# multiagent

A small, reusable **multi-agent team setup for Claude Code**, plus the first thing built with it: `csvstats`, a zero-dependency CSV summary CLI with 21 tests.

Built in a short sprint and imported in one commit.

## What's in here

```
.claude/agents/
  project-leader.md      plans work, splits it into packets, owns acceptance
  logic-reviewer.md      critiques packets before dispatch and second-guesses returned
                         implementations (Opus); cannot edit files, and a PreToolUse
                         hook refuses its Write calls
  software-engineer.md   hands a finalised packet to an external model (GPT-5.6 Sol via
                         the Codex CLI) and reports back — the only seat that produces
                         source. Runs on Haiku on purpose: it makes no engineering
                         decisions, so the frontier model is spent on review instead
  uiux-designer.md       reviews / proposes interface changes (no Edit tool)
.claude/settings.json    wires log_subagent.py to SubagentStart / SubagentStop
scripts/
  guard_reviewer_writes.py   PreToolUse hook declared in logic-reviewer.md; refuses the
                             Write tool by file path
  log_subagent.py            appends every subagent hand-off to a run log
  run_codex.sh               bridges one packet to the external implementer and stamps
                             MODEL_USED / EFFORT into the output, so the leader always
                             knows which model produced the code
init.sh                    bootstraps the team in a new repo; warns if ANTHROPIC_API_KEY /
                           CODEX_API_KEY / OPENAI_API_KEY is set so a run cannot silently
                           switch to metered billing
csvstats.py                the CLI produced by the team
tests/                     21 tests + fixtures
SETUP.md                   how to bootstrap the team in a new repo
```

The design rule: **a reviewer that can quietly "fix" code is not a reviewer.** The reviewer seat gets the strongest model and no write path; the engineer seat is a thin bridge whose output is stamped with the model that actually ran. The write-guard is deliberately narrow — it gates the `Write` tool by path, so shell writes are out of scope, which is why the reviewer's tool list also excludes `Edit`.

## csvstats

Prints column-level statistics for a CSV — type inference, count / missing, min / max / mean / median / stdev for numeric columns — and is deliberately strict about edge cases: ragged rows, header-only files, whitespace-only cells, non-finite numbers. One test asserts that every import is from the standard library, so it stays dependency-free.

```bash
python csvstats.py tests/fixtures/sample.csv
pytest                      # 21 tests
```

## Using the team in another project

See [`SETUP.md`](SETUP.md). Copy `.claude/`, `scripts/`, and run `init.sh`.
