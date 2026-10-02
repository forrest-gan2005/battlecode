#!/usr/bin/env python3
import datetime, html, json, os, re, subprocess, sys, time

ROOT = "/Users/quasarpark/meow-loop"
L = os.path.join(ROOT, "loop")
KST = datetime.timezone(datetime.timedelta(hours=9))
DEADLINE = datetime.datetime(2026, 10, 3, 15, 0, tzinfo=KST)
MIN_GAP = 40 * 60
WAVE_TIMEOUT = 75 * 60
LIMIT_BACKOFF = 30 * 60
STATUS = os.path.join(L, "status.json")
STOP = os.path.join(L, "STOP")


def now():
    return datetime.datetime.now(KST)


def load_status():
    try:
        with open(STATUS) as f:
            return json.load(f)
    except Exception:
        return {}


def save_runner(runner):
    st = load_status()
    st["runner"] = runner
    tmp = STATUS + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STATUS)


def wave_cmd(prompt):
    return [
        "claude", "-p", prompt,
        "--model", "opus", "--effort", "high",
        "--permission-mode", "bypassPermissions",
        "--settings", os.path.join(L, "settings.json"),
        "--output-format", "stream-json", "--verbose",
        "--disallowedTools", "Bash(git push:*)", "Bash(gh:*)", "Bash(unswbc submit:*)",
    ]


def parse_wave(path):
    res = {}
    try:
        with open(path) as f:
            for line in f:
                if '"type":"result"' not in line.replace(" ", ""):
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("type") == "result":
                    u = d.get("usage") or {}
                    res = {
                        "turns": d.get("num_turns"),
                        "cost_usd": d.get("total_cost_usd"),
                        "is_error": d.get("is_error"),
                        "summary": (d.get("result") or "")[:600],
                        "tokens": sum(u.get(k, 0) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")),
                    }
    except OSError:
        pass
    return res


def fmt(t):
    return datetime.datetime.fromisoformat(t).astimezone(KST).strftime("%m-%d %H:%M") if t else ""


def esc(x):
    return html.escape(str(x if x is not None else ""))


def tail(path, n):
    try:
        with open(path) as f:
            return "".join(f.readlines()[-n:])
    except OSError:
        return ""


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def dashboard():
    st = load_status()
    r = st.get("runner", {})
    hyp = st.get("hypotheses", [])
    rows = "".join(
        f"<tr><td>{esc(h.get('id'))}</td><td>{esc(h.get('area'))}</td><td>{esc(h.get('title'))}</td>"
        f"<td><span class='pill {esc(h.get('status'))}'>{esc(h.get('status'))}</span></td>"
        f"<td>{esc(h.get('held'))}</td><td>{esc(h.get('main'))}</td><td>{esc(h.get('confirm'))}</td><td>{esc(h.get('verdict'))}</td></tr>"
        for h in hyp) or "<tr><td colspan='8' class='muted'>No hypotheses yet. The first wave builds the queue from the ladder analysis.</td></tr>"
    waves = "".join(
        f"<tr><td>{w.get('n')}</td><td>{fmt(w.get('start'))}</td><td>{w.get('minutes', '')}</td><td>{esc(w.get('exit'))}</td>"
        f"<td>{esc(w.get('turns'))}</td><td>{(w.get('tokens') or 0)/1e6:.1f}M</td><td class='sum'>{esc(w.get('summary'))}</td></tr>"
        for w in reversed(r.get("waves", []))) or "<tr><td colspan='7' class='muted'>No finished waves yet.</td></tr>"
    running = "".join(f"<li>{esc(j.get('what'))} <span class='muted'>({esc(j.get('result_file'))}, started {esc(j.get('started'))})</span></li>" for j in st.get("running", [])) or "<li class='muted'>No background runs.</li>"
    findings = "".join(f"<li>{esc(x)}</li>" for x in st.get("findings", [])) or "<li class='muted'>None yet.</li>"
    base = st.get("baseline", {})
    noise = st.get("noise", {})
    state_line = esc(r.get("state", "not started"))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60"><title>meow Loop</title><style>
:root{{--bg:#F3F5F4;--card:#fff;--ink:#132A2D;--muted:#5B7072;--line:#D3DDDB;--acc:#0B6E78;--ok:#1F7A50;--bad:#B42318;--warn:#A86400}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0D1A1C;--card:#13282B;--ink:#E2EDEB;--muted:#98B0AE;--line:#29443F;--acc:#4CC3CC;--ok:#52C98F;--bad:#F97066;--warn:#F0A93B}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,"SF Pro Text","Helvetica Neue",sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:24px 16px 48px;display:grid;gap:20px}}
h1{{margin:0;font-size:26px}} h2{{margin:0 0 10px;font-size:17px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;min-width:0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}}
.muted{{color:var(--muted)}} .big{{font-size:20px;font-weight:600}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}} th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{color:var(--muted);font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.04em}}
.scroll{{overflow-x:auto}} td.sum{{max-width:520px}}
.pill{{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;border:1px solid var(--line)}}
.pill.candidate{{border-color:var(--ok);color:var(--ok)}} .pill.rejected{{border-color:var(--bad);color:var(--bad)}}
.pill.running{{border-color:var(--acc);color:var(--acc)}} .pill.inconclusive{{border-color:var(--warn);color:var(--warn)}}
pre{{white-space:pre-wrap;font:12.5px/1.5 ui-monospace,Menlo,monospace;margin:0;max-height:520px;overflow:auto}}
</style></head><body><div class="wrap">
<div><h1>meow overnight loop</h1><div class="muted">Opus 5.5 · effort high · local only, no uploads · page refreshes every minute · updated {now().strftime('%m-%d %H:%M:%S')} KST</div></div>
<div class="grid">
<div class="card"><div class="muted">Runner</div><div class="big">{state_line}</div><div class="muted">Waves done: {len(r.get('waves', []))} · new waves stop at {DEADLINE.strftime('%m-%d %H:%M')} KST or when loop/STOP exists</div></div>
<div class="card"><div class="muted">Phase</div><div class="big">{esc(st.get('phase', 'A'))}</div><div>{esc(st.get('current', ''))}</div></div>
<div class="card"><div class="muted">Baseline (B61 vs v61)</div><div>held-out: <b>{esc(base.get('held', '-'))}</b> · main: <b>{esc(base.get('main', '-'))}</b></div><div class="muted">identity: {esc(base.get('ident', '-'))}</div><div class="muted">noise: {esc(noise.get('placebo1', '-'))} / {esc(noise.get('placebo2', '-'))} {esc(noise.get('note', ''))}</div></div>
</div>
<div class="card"><h2>Hypotheses</h2><div class="scroll"><table><tr><th>id</th><th>area</th><th>idea</th><th>status</th><th>held-out</th><th>main</th><th>confirm</th><th>verdict</th></tr>{rows}</table></div></div>
<div class="grid"><div class="card"><h2>Running now</h2><ul>{running}</ul></div><div class="card"><h2>Findings</h2><ul>{findings}</ul></div></div>
<div class="card"><h2>Waves</h2><div class="scroll"><table><tr><th>#</th><th>start (KST)</th><th>min</th><th>exit</th><th>turns</th><th>tokens</th><th>summary</th></tr>{waves}</table></div></div>
<div class="grid"><div class="card"><h2>STATE.md</h2><pre>{esc(read(os.path.join(L, 'STATE.md')))}</pre></div>
<div class="card"><h2>LEDGER.md (latest)</h2><pre>{esc(tail(os.path.join(L, 'LEDGER.md'), 120))}</pre></div></div>
</div></body></html>"""
    tmp = os.path.join(L, "dashboard.html.tmp")
    with open(tmp, "w") as f:
        f.write(page)
    os.replace(tmp, os.path.join(L, "dashboard.html"))


def sleep_until(t, runner):
    while now() < t:
        if os.path.exists(STOP):
            return
        dashboard()
        time.sleep(30)


def main():
    with open(os.path.join(L, "PROMPT.md")) as f:
        base_prompt = f.read()
    runner = load_status().get("runner", {})
    runner.setdefault("waves", [])
    last_start = None
    n = len(runner["waves"]) + 1
    while True:
        if os.path.exists(STOP):
            runner["state"] = "stopped (STOP file)"
            break
        if now() >= DEADLINE:
            runner["state"] = "stopped (deadline reached)"
            break
        if last_start:
            nxt = last_start + datetime.timedelta(seconds=MIN_GAP)
            if now() < nxt:
                runner["state"] = f"waiting, next wave at {nxt.strftime('%H:%M')} KST"
                save_runner(runner)
                sleep_until(nxt, runner)
                continue
        start = now()
        last_start = start
        runner["state"] = f"running wave {n} since {start.strftime('%H:%M')} KST"
        save_runner(runner)
        prompt = base_prompt + f"\n\nThis is wave {n}. The time now is {start.strftime('%Y-%m-%d %H:%M')} KST.\n"
        out = os.path.join(L, "waves", f"w{n:03d}.jsonl")
        err = os.path.join(L, "waves", f"w{n:03d}.err")
        with open(out, "w") as fo, open(err, "w") as fe:
            p = subprocess.Popen(wave_cmd(prompt), cwd=ROOT, stdout=fo, stderr=fe, stdin=subprocess.DEVNULL)
            exit_note = None
            while p.poll() is None:
                if (now() - start).total_seconds() > WAVE_TIMEOUT:
                    p.terminate()
                    try:
                        p.wait(60)
                    except subprocess.TimeoutExpired:
                        p.kill()
                    exit_note = "timeout"
                    break
                dashboard()
                time.sleep(30)
        info = parse_wave(out)
        rc = p.returncode
        mins = round((now() - start).total_seconds() / 60)
        entry = {"n": n, "start": start.isoformat(), "minutes": mins, "exit": exit_note or rc, **info}
        runner["waves"].append(entry)
        save_runner(runner)
        dashboard()
        text = (info.get("summary") or "") + read(err)[-2000:]
        if re.search(r"usage limit|rate limit|limit reached|429", text, re.I):
            runner["state"] = "paused: usage limit, retrying in 30 min"
            save_runner(runner)
            sleep_until(now() + datetime.timedelta(seconds=LIMIT_BACKOFF), runner)
        n += 1
    save_runner(runner)
    dashboard()


if __name__ == "__main__":
    main()
