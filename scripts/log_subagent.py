#!/usr/bin/env python3
"""SubagentStart / SubagentStop hook: append one line to .agents/timeline.jsonl."""
import datetime
import json
import pathlib
import sys


def main() -> int:
    event = sys.argv[1] if len(sys.argv) > 1 else "?"
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    out = pathlib.Path(".agents")
    out.mkdir(exist_ok=True)
    line = {
        "t": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "ev": event,
        "agent": payload.get("agent_type", "?"),
    }
    with (out / "timeline.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
