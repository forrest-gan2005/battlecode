#!/usr/bin/env python3
import datetime, glob, html, json, os, re, subprocess, time

ROOT = "/Users/quasarpark/meow-loop"
L = os.path.join(ROOT, "loop")
KST = datetime.timezone(datetime.timedelta(hours=9))
DEADLINE = datetime.datetime(2026, 10, 3, 15, 0, tzinfo=KST)
MIN_GAP = 40 * 60
WAVE_TIMEOUT = 75 * 60
LIMIT_BACKOFF = 30 * 60
STATUS = os.path.join(L, "status.json")
STOP = os.path.join(L, "STOP")
WAVE_MARK = "claude -p # meow overnight loop"
PHASE_KO = {"A": "A · 분석", "B": "B · 기준선과 흔들림 폭", "C": "C · 가설 반복"}
STATUS_KO = {"queued": "대기", "running": "진행 중", "candidate": "후보", "rejected": "기각", "inconclusive": "불확실"}


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
                        "summary": (d.get("result") or "")[:700],
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


def exit_ko(e):
    return {0: "정상", "0": "정상", "timeout": "시간 초과", "adopted": "정상"}.get(e, f"종료 코드 {e}")


def dashboard():
    st = load_status()
    r = st.get("runner", {})
    hyp = st.get("hypotheses", [])
    rows = "".join(
        f"<tr><td>{esc(h.get('id'))}</td><td>{esc(h.get('area'))}</td><td>{esc(h.get('title'))}</td>"
        f"<td><span class='pill {esc(h.get('status'))}'>{esc(STATUS_KO.get(h.get('status'), h.get('status')))}</span></td>"
        f"<td>{esc(h.get('held'))}</td><td>{esc(h.get('main'))}</td><td>{esc(h.get('confirm'))}</td><td>{esc(h.get('verdict'))}</td></tr>"
        for h in hyp) or "<tr><td colspan='8' class='muted'>아직 가설이 없어요. 첫 웨이브가 래더 분석으로 목록을 만들어요.</td></tr>"
    waves = "".join(
        f"<tr><td>{w.get('n')}</td><td>{fmt(w.get('start'))}</td><td>{w.get('minutes', '')}</td><td>{esc(exit_ko(w.get('exit')))}</td>"
        f"<td>{esc(w.get('turns'))}</td><td>{(w.get('tokens') or 0)/1e6:.1f}M</td><td class='sum'>{esc(w.get('summary'))}</td></tr>"
        for w in reversed(r.get("waves", []))) or "<tr><td colspan='7' class='muted'>아직 끝난 웨이브가 없어요.</td></tr>"
    running = "".join(f"<li>{esc(j.get('what'))} <span class='muted'>({esc(j.get('result_file'))}, {esc(j.get('started'))} 시작)</span></li>" for j in st.get("running", [])) or "<li class='muted'>백그라운드 작업 없음</li>"
    findings = "".join(f"<li>{esc(x)}</li>" for x in st.get("findings", [])) or "<li class='muted'>아직 없음</li>"
    base = st.get("baseline", {})
    noise = st.get("noise", {})
    phase = st.get("phase", "A")
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60"><title>meow 밤샘 루프</title><style>
:root{{--bg:#F3F5F4;--card:#fff;--ink:#132A2D;--muted:#5B7072;--line:#D3DDDB;--acc:#0B6E78;--ok:#1F7A50;--bad:#B42318;--warn:#A86400}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0D1A1C;--card:#13282B;--ink:#E2EDEB;--muted:#98B0AE;--line:#29443F;--acc:#4CC3CC;--ok:#52C98F;--bad:#F97066;--warn:#F0A93B}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,"Apple SD Gothic Neo","SF Pro Text",sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:24px 16px 48px;display:grid;gap:20px}}
h1{{margin:0;font-size:26px}} h2{{margin:0 0 10px;font-size:17px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;min-width:0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}}
.muted{{color:var(--muted)}} .big{{font-size:20px;font-weight:600}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}} th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{color:var(--muted);font-weight:500;font-size:12.5px}}
.scroll{{overflow-x:auto}} td.sum{{max-width:520px}}
.pill{{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;border:1px solid var(--line);white-space:nowrap}}
.pill.candidate{{border-color:var(--ok);color:var(--ok)}} .pill.rejected{{border-color:var(--bad);color:var(--bad)}}
.pill.running{{border-color:var(--acc);color:var(--acc)}} .pill.inconclusive{{border-color:var(--warn);color:var(--warn)}}
details summary{{cursor:pointer;font-weight:600}}
pre{{white-space:pre-wrap;font:12.5px/1.5 ui-monospace,Menlo,monospace;margin:10px 0 0;max-height:520px;overflow:auto}}
</style></head><body><div class="wrap">
<div><h1>meow 밤샘 루프</h1><div class="muted">Opus 5.5 · effort high · 로컬 전용, 업로드 없음 · 1분마다 새로고침 · {now().strftime('%m-%d %H:%M:%S')} KST 갱신</div></div>
<div class="grid">
<div class="card"><div class="muted">실행기</div><div class="big">{esc(r.get('state', '시작 전'))}</div><div class="muted">끝난 웨이브 {len(r.get('waves', []))}개 · {DEADLINE.strftime('%m-%d %H:%M')} KST가 되거나 loop/STOP 파일이 생기면 새 웨이브를 멈춰요</div></div>
<div class="card"><div class="muted">단계</div><div class="big">{esc(PHASE_KO.get(phase, phase))}</div><div>{esc(st.get('current', ''))}</div></div>
<div class="card"><div class="muted">기준선 (B61 vs v61)</div><div>처음 보는 지도: <b>{esc(base.get('held', '-'))}</b> · 공식 지도: <b>{esc(base.get('main', '-'))}</b></div><div class="muted">동일성: {esc(base.get('ident', '-'))}</div><div class="muted">흔들림 폭(위약): {esc(noise.get('placebo1', '-'))} / {esc(noise.get('placebo2', '-'))} {esc(noise.get('note', ''))}</div></div>
</div>
<div class="card"><h2>가설</h2><div class="scroll"><table><tr><th>번호</th><th>영역</th><th>아이디어</th><th>상태</th><th>처음 보는 지도</th><th>공식 지도</th><th>재확인</th><th>판정</th></tr>{rows}</table></div></div>
<div class="grid"><div class="card"><h2>지금 돌아가는 작업</h2><ul>{running}</ul></div><div class="card"><h2>발견</h2><ul>{findings}</ul></div></div>
<div class="card"><h2>웨이브 기록</h2><div class="scroll"><table><tr><th>#</th><th>시작 (KST)</th><th>분</th><th>종료</th><th>턴</th><th>토큰</th><th>요약</th></tr>{waves}</table></div></div>
<div class="grid"><div class="card"><details><summary>STATE.md 원문 (영어)</summary><pre>{esc(read(os.path.join(L, 'STATE.md')))}</pre></details></div>
<div class="card"><details><summary>LEDGER.md 최근 (영어)</summary><pre>{esc(tail(os.path.join(L, 'LEDGER.md'), 120))}</pre></details></div></div>
</div></body></html>"""
    tmp = os.path.join(L, "dashboard.html.tmp")
    with open(tmp, "w") as f:
        f.write(page)
    os.replace(tmp, os.path.join(L, "dashboard.html"))


def sleep_until(t):
    while now() < t:
        if os.path.exists(STOP):
            return
        dashboard()
        time.sleep(30)


def running_wave_pids():
    out = subprocess.run(["pgrep", "-f", WAVE_MARK], capture_output=True, text=True).stdout.split()
    return [int(x) for x in out if x.strip()]


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def finish(runner, n, start, out, err, exit_note):
    info = parse_wave(out)
    mins = round((now() - start).total_seconds() / 60)
    runner["waves"].append({"n": n, "start": start.isoformat(), "minutes": mins, "exit": exit_note, **info})
    save_runner(runner)
    dashboard()
    text = (info.get("summary") or "") + read(err)[-2000:]
    if re.search(r"usage limit|rate limit|limit reached|429", text, re.I):
        runner["state"] = "일시정지: 사용량 한도, 30분 뒤 다시 시도"
        save_runner(runner)
        sleep_until(now() + datetime.timedelta(seconds=LIMIT_BACKOFF))


def adopt(runner):
    pids = running_wave_pids()
    files = sorted(glob.glob(os.path.join(L, "waves", "w*.jsonl")))
    if not pids or not files:
        return None, len(runner["waves"]) + 1
    out = files[-1]
    n = int(os.path.basename(out)[1:4])
    start = datetime.datetime.fromtimestamp(os.stat(out).st_birthtime, KST)
    runner["state"] = f"웨이브 {n} 진행 중 ({start.strftime('%H:%M')}부터)"
    save_runner(runner)
    note = "adopted"
    while any(alive(p) for p in pids):
        if (now() - start).total_seconds() > WAVE_TIMEOUT:
            for p in pids:
                try:
                    os.kill(p, 15)
                except OSError:
                    pass
            note = "timeout"
            time.sleep(30)
            break
        dashboard()
        time.sleep(30)
    finish(runner, n, start, out, out[:-6] + ".err", note)
    return start, n + 1


def main():
    runner = load_status().get("runner", {})
    runner.setdefault("waves", [])
    last_start, n = adopt(runner)
    while True:
        if os.path.exists(STOP):
            runner["state"] = "중지됨 (STOP 파일)"
            break
        if now() >= DEADLINE:
            runner["state"] = "중지됨 (마감 시각 도달)"
            break
        if last_start:
            nxt = last_start + datetime.timedelta(seconds=MIN_GAP)
            if now() < nxt:
                runner["state"] = f"대기 중, 다음 웨이브 {nxt.strftime('%H:%M')} KST"
                save_runner(runner)
                sleep_until(nxt)
                continue
        with open(os.path.join(L, "PROMPT.md")) as f:
            base_prompt = f.read()
        start = now()
        last_start = start
        runner["state"] = f"웨이브 {n} 진행 중 ({start.strftime('%H:%M')}부터)"
        save_runner(runner)
        prompt = base_prompt + f"\n\nThis is wave {n}. The time now is {start.strftime('%Y-%m-%d %H:%M')} KST.\n"
        out = os.path.join(L, "waves", f"w{n:03d}.jsonl")
        err = os.path.join(L, "waves", f"w{n:03d}.err")
        exit_note = None
        with open(out, "w") as fo, open(err, "w") as fe:
            p = subprocess.Popen(wave_cmd(prompt), cwd=ROOT, stdout=fo, stderr=fe, stdin=subprocess.DEVNULL)
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
        finish(runner, n, start, out, err, exit_note or p.returncode)
        n += 1
    save_runner(runner)
    dashboard()


if __name__ == "__main__":
    main()
