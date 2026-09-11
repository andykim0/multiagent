# multiagent

A small, reusable **multi-agent team setup for Claude Code**, plus the first thing built with it: `csvstats`, a CSV summary CLI with 21 tests.

## What's in here

```
.claude/agents/
  project-leader.md      plans work, splits it into tasks, owns acceptance
  software-engineer.md   implements; the only role allowed to write source
  logic-reviewer.md      reviews for correctness; cannot edit files
  uiux-designer.md       reviews / proposes interface changes
.claude/settings.json    hooks that wire the guards below into every run
scripts/
  guard_reviewer_writes.py   blocks file writes when the active agent is a reviewer
  log_subagent.py            appends every subagent hand-off to a run log
  run_codex.sh               runs an external model as a second-opinion reviewer
csvstats.py                the CLI produced by the team
tests/                     21 tests + fixtures (ragged rows, quoted fields, non-finite values, …)
SETUP.md                   how to bootstrap the team in a new repo
```

The point of the guard scripts: a reviewer that can quietly "fix" code is not a reviewer. `guard_reviewer_writes.py` runs as a pre-tool hook and refuses writes from review roles, so the engineer role stays the single writer and every change goes through an actual review hand-off.

## csvstats

Prints column-level statistics for a CSV — type inference, counts, min / max / mean, distinct values — and is deliberately strict about edge cases (ragged rows, header-only files, whitespace-only cells, non-finite numbers).

```bash
python csvstats.py tests/fixtures/sample.csv
pytest                      # 21 tests
```

## Using the team in another project

See [`SETUP.md`](SETUP.md). Copy `.claude/`, `scripts/`, and run `init.sh`.
