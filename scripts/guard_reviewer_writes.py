#!/usr/bin/env python3
"""PreToolUse hook: block the logic-reviewer writing outside .agents/critiques/."""
import json
import sys

ALLOWED = ".agents/critiques/"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not path:
        return 0

    if ALLOWED in path.replace("\\", "/"):
        return 0

    sys.stderr.write(
        "Blocked: the reviewer may only write under .agents/critiques/. "
        "Put fixes in your critique as text; the engineer applies them.\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
