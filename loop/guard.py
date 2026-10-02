#!/usr/bin/env python3
import json, re, sys

BLOCK = re.compile(
    r"git\s+push|(^|[\s;&|(])gh\s|submit|online\.js|--confirm|"
    r"curl\b[^|;]*-X\s*(POST|PUT|PATCH|DELETE)|"
    r"/Users/quasarpark/01\. Project/[^\"']*/battlecode(?!-)\b[^\"']*\s*(>|rm\b|mv\b)",
    re.I,
)

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
cmd = (data.get("tool_input") or {}).get("command") or ""
if BLOCK.search(cmd):
    print("Blocked by loop guard: uploads, battle requests, git push, GitHub writes and changes to the main repo are not allowed in this loop.", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
