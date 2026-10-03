#!/usr/bin/env python3
"""Connect a loop to the idea board (GitHub issues) and the "Loop status" issue.

usage:
  board.py next [--wf 1|2|3]                      print the next idea labelled loop:ready (oldest first)
  board.py claim N --loop NAME --wf W [--machine M]  mark #N as being worked on and update Loop status
  board.py report N --kind test|check --file F [--status tested|rejected|inconclusive] --loop NAME
                                                  post F as a [test]/[check] comment, release #N, set its status
  board.py heartbeat --loop NAME --wf W [--state running|idle|stopped] [--issue N] [--step TEXT] [--machine M]
  board.py ready N                                put #N in the loop queue
  board.py remove --loop NAME                     drop a loop from the Loop status board
Requires the GitHub CLI (gh) with write access to the repo.
"""
import argparse, datetime, json, os, re, socket, subprocess, sys, tempfile

REPO = "forrest-gan2005/battlecode"
STATUS_TITLE = "Loop status"
KST = datetime.timezone(datetime.timedelta(hours=9))
WF = {"1": "① Zhe's workflow", "2": "② Board loop", "3": "③ Full-AI workflow"}


def gh(*args, parse=True):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"gh {' '.join(args[:2])} failed: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout) if parse and r.stdout.strip() else r.stdout


def now():
    return datetime.datetime.now(KST)


def base_commit():
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


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
        issue = f"#{l['issue']}" if l.get("issue") else "-"
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
    cur.update(wf=str(wf), state=state, issue=issue, step=step, machine=machine or cur.get("machine") or socket.gethostname().split(".")[0], updated=t)
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
    q = gh("issue", "list", "--repo", REPO, "--state", "open", "--label", "loop:ready", "--limit", "100", "--json", "number,title,labels,body,createdAt")
    q = [i for i in q if not any(l["name"] == "loop:running" for l in i["labels"])]
    if a.wf:
        q = [i for i in q if any(l["name"] == f"wf:{a.wf}" for l in i["labels"])]
    if not q:
        print("queue empty")
        return
    i = sorted(q, key=lambda x: x["createdAt"])[0]
    labels = ", ".join(l["name"] for l in i["labels"])
    print(f"#{i['number']} {i['title']}\nlabels: {labels}\n\n{i['body']}")


def cmd_claim(a):
    gh("issue", "edit", str(a.n), "--repo", REPO, "--add-label", "loop:running", parse=False)
    heartbeat(a.loop, a.wf, "running", a.n, "claimed", a.machine)
    print(f"claimed #{a.n}")


def cmd_report(a):
    tag = "[test]" if a.kind == "test" else "[check]"
    with open(a.file) as f:
        text = f.read().strip()
    body = f"{tag} by `{a.loop}` · base main@{base_commit()} · {now().strftime('%m-%d %H:%M')} KST\n\n{text}\n"
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(body)
    gh("issue", "comment", str(a.n), "--repo", REPO, "--body-file", f.name, parse=False)
    os.unlink(f.name)
    edit = ["issue", "edit", str(a.n), "--repo", REPO, "--remove-label", "loop:running"]
    if a.status:
        edit += ["--remove-label", "status:untested", "--remove-label", "status:in-progress", "--remove-label", "loop:ready",
                 "--add-label", f"status:{a.status}"]
    subprocess.run(["gh", *edit], capture_output=True, text=True)
    heartbeat(a.loop, a.wf, "idle", None, f"reported #{a.n}" + (f" ({a.status})" if a.status else ""), a.machine)
    print(f"reported on #{a.n}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("next"); p.add_argument("--wf")
    p = sub.add_parser("claim"); p.add_argument("n", type=int); p.add_argument("--loop", required=True); p.add_argument("--wf", required=True); p.add_argument("--machine")
    p = sub.add_parser("report"); p.add_argument("n", type=int); p.add_argument("--kind", choices=["test", "check"], required=True)
    p.add_argument("--file", required=True); p.add_argument("--status", choices=["tested", "rejected", "inconclusive"])
    p.add_argument("--loop", required=True); p.add_argument("--wf", required=True); p.add_argument("--machine")
    p = sub.add_parser("heartbeat"); p.add_argument("--loop", required=True); p.add_argument("--wf", required=True)
    p.add_argument("--state", default="running", choices=["running", "idle", "stopped"]); p.add_argument("--issue", type=int)
    p.add_argument("--step"); p.add_argument("--machine")
    p = sub.add_parser("ready"); p.add_argument("n", type=int)
    p = sub.add_parser("remove"); p.add_argument("--loop", required=True)
    a = ap.parse_args()
    if a.cmd == "next":
        cmd_next(a)
    elif a.cmd == "claim":
        cmd_claim(a)
    elif a.cmd == "report":
        cmd_report(a)
    elif a.cmd == "heartbeat":
        heartbeat(a.loop, a.wf, a.state, a.issue, a.step, a.machine)
        print("heartbeat sent")
    elif a.cmd == "remove":
        print("removed" if remove_loop(a.loop) else "no such loop")
    elif a.cmd == "ready":
        gh("issue", "edit", str(a.n), "--repo", REPO, "--add-label", "loop:ready", parse=False)
        print(f"#{a.n} queued")


if __name__ == "__main__":
    main()
