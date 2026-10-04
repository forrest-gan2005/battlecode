#!/usr/bin/env python3
"""Connect a loop to the card board (GitHub issues) and the "Loop status" issue.

usage:
  board.py next [--state S] [--wf W]             pick the next ready card, or list a state
  board.py state N S [--note FILE]              replace the state and update Loop status
  board.py claim N                              alias for state N building
  board.py report N --kind test|check --file F --state S
                                                post a summary-first result and set its state
  board.py ask N --file F                        post questions and set needs-info
  board.py ready N                               alias for state N ready
  board.py heartbeat --loop NAME --wf W [--state running|idle|stopped] [--issue N] [--step TEXT] [--machine M]
  board.py remove --loop NAME                    drop a loop from the Loop status board
  board.py migrate [--apply]                     preview old-label migration; apply safe changes
State commands accept --loop NAME, --wf W, --machine M (defaults: hostname, 2, hostname).
Requires the GitHub CLI (gh) with write access to the repo.
"""
import argparse, datetime, json, os, re, socket, subprocess, sys, tempfile

from card_names import card_ref as format_card_ref
from fair_queue import priority, order_cards, read_fair

REPO = "forrest-gan2005/battlecode"
STATUS_TITLE = "Loop status"
KST = datetime.timezone(datetime.timedelta(hours=9))
STATES = "ready needs-info building needs-look testing tested candidate smoke kept rejected inconclusive untested".split()
LEGACY = {"loop:ready", "loop:running", "status:in-progress"}
WF = {"1": "① Zhe's workflow", "2": "② Board loop", "3": "③ Full-AI workflow"}


def gh(*args, parse=True):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"gh {' '.join(args[:2])} failed: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout) if parse and r.stdout.strip() else r.stdout


def card_ref(card):
    if isinstance(card, dict):
        return format_card_ref(card)
    issue = gh("issue", "view", str(card), "--repo", REPO, "--json", "number,title,labels")
    return format_card_ref({**issue, 'number': card})


def now():
    return datetime.datetime.now(KST)


def base_commit():
    for args in (["git", "fetch", "origin", "main"], ["git", "rev-parse", "origin/main"]):
        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"{' '.join(args)} failed: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def status_issue():
    issues = gh("issue", "list", "--repo", REPO, "--state", "open", "--search", f"{STATUS_TITLE} in:title", "--json", "number,title,body")
    for i in issues:
        if i["title"].strip() == STATUS_TITLE:
            return i
    sys.exit("Loop status issue not found")


def read_loops(body):
    m = re.search(r"<!-- loops-json\s*(\{.*?\})\s*-->", body or "", re.S)
    return json.loads(m.group(1)).get("loops", {}) if m else {}


def render(loops):
    head = ("This issue is the live status board for every loop. Loops update it automatically with `work/board.py heartbeat`; "
            "please don't edit it by hand. meowbot shows it in Discord with `/loop` and `/board`.\n\n")
    blob = "<!-- loops-json\n" + json.dumps({"loops": loops}, indent=1, ensure_ascii=False) + "\n-->\n\n"
    rows = ["| Loop | Workflow | Machine | State | Working on | Step | Since (KST) | Updated (KST) |", "|---|---|---|---|---|---|---|---|"]
    for name, l in sorted(loops.items()):
        issue = l.get("ref") or card_ref(l["issue"]) if l.get("issue") else "-"
        rows.append(f"| {name} | {WF.get(str(l.get('wf')), l.get('wf'))} | {l.get('machine', '-')} | {l.get('state', '-')} | {issue} | "
                    f"{l.get('step') or '-'} | {l.get('since', '-')} | {l.get('updated', '-')} |")
    if len(rows) == 2:
        rows.append("| no loop has reported yet | | | | | | | |")
    return head + blob + "\n".join(rows) + "\n"


def heartbeat(loop, wf, state="running", issue=None, step=None, machine=None):
    st = status_issue()
    loops = read_loops(st["body"])
    cur = loops.get(loop, {})
    t = now().strftime("%m-%d %H:%M")
    if cur.get("state") != state or cur.get("issue") != issue:
        cur["since"] = t
    cur.update(ref=card_ref(issue) if issue else None, wf=str(wf), state=state, issue=issue, step=step, machine=machine or cur.get("machine") or socket.gethostname().split(".")[0], updated=t)
    loops[loop] = cur
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(render(loops))
    gh("issue", "edit", str(st["number"]), "--repo", REPO, "--body-file", f.name, parse=False)
    os.unlink(f.name)


def remove_loop(loop):
    st = status_issue()
    loops = read_loops(st["body"])
    if loops.pop(loop, None) is None:
        return False
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(render(loops))
    gh("issue", "edit", str(st["number"]), "--repo", REPO, "--body-file", f.name, parse=False)
    os.unlink(f.name)
    return True


def cmd_next(a):
    q = gh("issue", "list", "--repo", REPO, "--state", "open", "--label", f"status:{a.state or 'ready'}",
           "--limit", "1000", "--json", "number,title,labels,body,createdAt")
    if a.wf:
        q = [i for i in q if any(l["name"] == f"wf:{a.wf}" for l in i["labels"])]
    q = order_cards(q, read_fair())
    if not q:
        print("queue empty")
        return
    for i in q if a.state else q[:1]:
        labels = ", ".join(l["name"] for l in i["labels"])
        print(f"{card_ref(i)}\nlabels: {labels}\n\n{i['body']}")
        pages = gh("api", f"repos/{REPO}/issues/{i['number']}/comments", "--paginate", "--slurp")
        for page in pages:
            for c in page:
                print(f"\n--- comment by {c['user']['login']} · {c['created_at']} ---\n{c['body']}")


def set_state(n, state, labels=None):
    if labels is None:
        labels = gh("issue", "view", str(n), "--repo", REPO, "--json", "labels")["labels"]
    edit = ["issue", "edit", str(n), "--repo", REPO]
    for label in labels:
        name = label["name"]
        if name != f"status:{state}" and (name.startswith("status:") or name in LEGACY):
            edit += ["--remove-label", name]
    gh(*edit, "--add-label", f"status:{state}", parse=False)


def comment(n, body):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(body)
    try:
        gh("issue", "comment", str(n), "--repo", REPO, "--body-file", f.name, parse=False)
    finally:
        os.unlink(f.name)


def cmd_state(a):
    if a.note:
        with open(a.note) as f:
            comment(a.n, f.read())
    set_state(a.n, a.state)
    heartbeat(a.loop, a.wf, a.state, a.n, f"status:{a.state}", a.machine)
    print(f"{card_ref(a.n)} status:{a.state}")


def cmd_report(a):
    with open(a.file) as f:
        text = f.read().rstrip()
    lines = text.splitlines()
    prefixes = ("What we tried: ", "Did it work: ", "Who decides now: ")
    if len(lines) < 3 or any(not line.startswith(prefix) or not line[len(prefix):].strip()
                             for line, prefix in zip(lines, prefixes)):
        sys.exit("report file must start with the three plain summary lines from docs/LOOP.md")
    body = (f"{text}\n\n<sub>[{a.kind}] by `{a.loop}` · base main@{base_commit()} · "
            f"{now().strftime('%m-%d %H:%M')} KST</sub>\n")
    comment(a.n, body)
    cmd_state(a)


def cmd_ask(a):
    with open(a.file) as f:
        text = f.read().strip()
    if not text.startswith("Questions before we build"):
        text = "Questions before we build\n\n" + text
    comment(a.n, text + "\n")
    cmd_state(a)


def cmd_migrate(a):
    cards = gh("issue", "list", "--repo", REPO, "--state", "open", "--limit", "1000",
               "--json", "number,title,labels")
    for i in cards:
        if not i["title"].startswith("[Idea]"):
            continue
        names = {l["name"] for l in i["labels"]}
        states = {s for s in names if s.startswith("status:")}
        if names & {"status:in-progress", "loop:running"} or "status:tested" in names:
            print(f"#{i['number']}: review progress/results manually; labels unchanged")
            continue
        if len(states) > 1 or ("loop:ready" in names and states - {"status:ready", "status:untested"}):
            print(f"#{i['number']}: conflicting states; review manually; labels unchanged")
            continue
        if "loop:ready" in names:
            print(f"#{i['number']}: remove {', '.join(sorted((states - {'status:ready'}) | {'loop:ready'}))}; add status:ready")
            if a.apply:
                set_state(i["number"], "ready", i["labels"])
        else:
            print(f"#{i['number']}: keep labels")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("next"); p.add_argument("--wf"); p.add_argument("--state", choices=STATES)
    for name in ("state", "claim", "report", "ask", "ready"):
        p = sub.add_parser(name); p.add_argument("n", type=int)
        p.add_argument("--loop", default=socket.gethostname().split(".")[0]); p.add_argument("--wf", default="2")
        p.add_argument("--machine"); p.set_defaults(note=None)
        if name == "state":
            p.add_argument("state", choices=STATES); p.add_argument("--note")
        elif name == "report":
            p.add_argument("--kind", choices=["test", "check"], required=True)
            p.add_argument("--file", required=True); p.add_argument("--state", choices=STATES, required=True)
        elif name == "ask":
            p.add_argument("--file", required=True); p.set_defaults(state="needs-info")
        else:
            p.set_defaults(state="building" if name == "claim" else "ready")
    p = sub.add_parser("heartbeat"); p.add_argument("--loop", required=True); p.add_argument("--wf", required=True)
    p.add_argument("--state", default="running", choices=["running", "idle", "stopped"]); p.add_argument("--issue", type=int)
    p.add_argument("--step"); p.add_argument("--machine")
    p = sub.add_parser("remove"); p.add_argument("--loop", required=True)
    p = sub.add_parser("migrate"); p.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.cmd == "next":
        cmd_next(a)
    elif a.cmd in ("state", "claim", "ready"):
        cmd_state(a)
    elif a.cmd == "report":
        cmd_report(a)
    elif a.cmd == "ask":
        cmd_ask(a)
    elif a.cmd == "migrate":
        cmd_migrate(a)
    elif a.cmd == "heartbeat":
        heartbeat(a.loop, a.wf, a.state, a.issue, a.step, a.machine)
        print("heartbeat sent")
    elif a.cmd == "remove":
        print("removed" if remove_loop(a.loop) else "no such loop")


if __name__ == "__main__":
    main()
