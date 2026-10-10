#!/usr/bin/env python3
"""Paired sparring pool. --n counts seeds; every seed plays both seats.

Results include queen length (zero when dead), not ab2's winning tiebreak
score. Raw JSON and replay evidence accompany each Markdown report.
"""
import argparse
import concurrent.futures as cf
from contextlib import contextmanager
from collections import defaultdict, deque
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid

import ab2
sys.path.insert(0, ab2.ROOT)
import replay

ROOT = Path(ab2.ROOT)
HERE = Path(__file__).resolve().parent
QUICK = ['tower_defense', 'trophy', 'australia', 'islands', 'default', 'schooltime']


def spec(value):
    source, sep, rest = value.partition(':')
    toggles = {}
    for item in rest.split(',') if sep and rest else []:
        key, eq, val = item.partition('=')
        if not eq or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key) or not re.fullmatch(r'true|false|-?\d+(?:\.\d+)?', val):
            raise ValueError('invalid toggle: ' + item)
        if key in toggles:
            raise ValueError('duplicate toggle: ' + key)
        toggles[key] = val
    return dict(source=source, toggles=toggles)


def literal(value):
    return str(value).lower() if isinstance(value, bool) else str(value)


@contextmanager
def batch_lock(path=None):
    path = path or Path.home() / '.meow-card-loop-locks' / 'batch.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('waiting for the batch lock', file=sys.stderr, flush=True)
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def local_engine(run_dir):
    # The copied venv's console-script shebang can still name the live checkout.
    # Invoke it explicitly with THIS worktree's interpreter instead.
    bindir = HERE / 'bc127' / 'bin'
    if (bindir / 'unswbc').is_file():
        shimdir = run_dir / 'bin'
        shimdir.mkdir()
        shim = shimdir / 'unswbc'
        shim.write_text('#!/bin/sh\nexec ' + shlex.join([str(bindir / 'python3'), str(bindir / 'unswbc')]) + ' "$@"\n')
        shim.chmod(0o755)
        os.environ['PATH'] = str(shimdir) + os.pathsep + os.environ['PATH']


def family(name):
    # Reporting categories only; no map-specific bot behavior.
    match = re.match(r'(?:held_|fresh_)?(blobs|islands|open|portalrooms|portals|rooms|stripes)_', name)
    if match:
        return match[1]
    if name in ('tower_defense', 'stronghold', 'weakhold', 'autarky', 'dilemma', 'queen_of_spades'):
        return 'rooms / walled starts'
    if name in ('islands', 'portals', 'stripes', 'maze'):
        return 'islands / portals / maze'
    if name in ('australia', 'around_unsw', 'big_empty', 'unsw'):
        return 'large open'
    return 'other official'


def replay_metrics(path, side):
    root = replay.load(path).root()
    result = root.pointer(4)
    bodies, teams, queens = {}, {}, {}
    for line in root.text(0).splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did, team = len(bodies), int(q[1])
            bodies[did] = deque((int(q[3 + 2*k]), int(q[4 + 2*k])) for k in range(int(q[2])))
            teams[did] = team
            queens.setdefault(team, did)
    actor, actor_length, round_no = None, 0, 0
    deaths = []
    timeouts = [0, 0]
    for ev in root.pointer(3):
        kind, p = replay.EVENT_NAMES[ev.u16(0)], ev.pointer(0)
        if kind == 'roundStart':
            round_no = p.i32(0)
        elif kind == 'turnStart':
            actor = p.i32(0)
            actor_length = len(bodies.get(actor, ()))
        elif kind == 'dragonUpdate':
            did = p.i32(0)
            head, tail = replay.point(p.pointer(0)), replay.point(p.pointer(1))
            body = bodies.setdefault(did, deque())
            if not body or body[0] != head:
                body.appendleft(head)
            while len(body) > 1 and body[-1] != tail:
                body.pop()
        elif kind == 'dragonSplit':
            parent, child, team = p.i32(0), p.i32(4), p.u16(8)
            bodies[parent] = deque(replay.point(x) for x in p.pointer(0))
            bodies[child] = deque(replay.point(x) for x in p.pointer(1))
            teams[parent] = teams[child] = team
        elif kind == 'dragonDeath':
            did, reason = p.i32(0), p.u16(4)
            deaths.append(dict(round=round_no, victim=did, team=teams[did], reason=reason,
                               queen=queens[teams[did]] == did, actor=actor,
                               actor_team=teams.get(actor), actor_length=actor_length,
                               victim_length=len(bodies.get(did, ()))))
            bodies.pop(did, None)
        elif kind == 'dragonAction' and p.bit(32):
            timeouts[teams[p.i32(0)]] += 1
    caused = [d for d in deaths if d['reason'] == 3 and d['actor_team'] == side and d['team'] != side]
    queen_deaths = [d for d in deaths if d['queen'] and d['team'] != side]
    # The first initial dragon per team is the queen. Reconstruct its final
    # body using the same update/split rules as replay.py, including elimination.
    scores = [len(bodies.get(queens[s], ())) for s in (0, 1)]
    winner = result.u16(6) if result.u16(4) == 1 else None
    return dict(win=int(winner == side), us=scores[side], them=scores[1-side],
                enemy_queen_deaths=len(queen_deaths),
                enemy_queen_kills=sum(d['queen'] for d in caused),
                head_on_caused=len(caused),
                small_head_on_caused=sum(d['actor_length'] <= 6 for d in caused),
                small_queen_kills=sum(d['queen'] and d['actor_length'] <= 6 for d in caused),
                big_head_on_caused=sum(d['victim_length'] >= 12 for d in caused),
                late_big_head_on_caused=sum(d['victim_length'] >= 12 and d['round'] >= 300 for d in caused),
                timeouts=timeouts[side], enemy_timeouts=timeouts[1-side],
                death_events=deaths)


def play(job):
    tag, bot, opp, m, seed, side = job
    path = Path(ab2.OUT) / f'{tag}_{m}_{seed}_{side}.replay'
    path.parent.mkdir(parents=True, exist_ok=True)
    a, b = (bot, opp) if side == 0 else (opp, bot)
    cmd = ['unswbc', 'run', ab2.mp(m), a, b, '-o', str(path), '--no-debug', '--seed', str(seed)]
    if not os.environ.get('NOSANDBOX'):
        cmd.append('--sandbox')
    # Same invocation/verdict logic as ab2.play, with retained diagnostics and
    # a bounded wall time. Failed games abort instead of biasing the pairing.
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          timeout=int(os.environ.get('POOL_GAME_TIMEOUT', '600')))
    output = proc.stdout + proc.stderr
    path.with_suffix('.log').write_text(output)
    result, ok = ab2.parse(output, 'AB'[side])
    if proc.returncode or not ok or not path.is_file():
        raise RuntimeError(f'game failed: {tag} {m} {seed} {side}: {output[-1000:]}')
    metrics = replay_metrics(path, side)
    if metrics['win'] != result['win']:
        raise ValueError(f'replay/verdict winner mismatch: {path}')
    return dict(tag=tag, map=m, seed=seed, side=side, family=family(m),
                **result, **metrics, replay=str(path.relative_to(ROOT)),
                runtime_errors=[line for line in output.splitlines()
                                if re.search(r'timed? out|timeout|ran out of time|exited|crash|exceeded|broken pipe', line, re.I)])


def run(configs, opponents, maps, n, out):
    workers = int(os.environ.get('WORKERS', '6'))
    if workers < 1 or n < 1:
        raise ValueError('WORKERS and --n must be positive')
    for m in maps:
        if not re.fullmatch(r'[\w-]+', m):
            raise ValueError('invalid map name: ' + m)
        ab2.mp(m)
    run_id = 'pool_' + uuid.uuid4().hex[:12]
    run_dir = ROOT / 'tune_runs' / 'pool' / run_id
    run_dir.mkdir(parents=True)
    ab2.OUT = str(run_dir / 'replays')
    rows, provenance = [], {}
    local_engine(run_dir)
    os.environ['KEEP'] = '1'
    os.environ.pop('FAST', None)
    bots = {}
    for name, config in {**configs, **{'opp_' + k: v for k, v in opponents.items()}}.items():
        sets = [(k, literal(v)) for k, v in config['toggles'].items()]
        bot = ab2.build(run_id + '_' + name, sets, config['source'])
        bots[name] = bot
        provenance[name] = dict(config, built=bot, files={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(bot).iterdir()) if p.is_file()})
        # Compile before dispatch, avoiding concurrent builds of one bot.
        bindir = HERE / 'bc127' / 'bin'
        subprocess.run([str(bindir / 'python3'), '-c',
            'from unswbc.project import Project; import sys; Project.from_dir(sys.argv[1]).compile()', bot],
            check=True, cwd=ROOT, stdout=sys.stderr)
    seed0 = int(os.environ.get('SEED0', '100'))
    jobs = [(tag + '__' + opp, bots[tag], bots['opp_' + opp], m, seed0 + k, side)
            for m in maps for k in range(n) for side in (0, 1) for opp in opponents for tag in configs]
    meta = dict(configs=provenance, maps=maps, seeds=list(range(seed0, seed0+n)), workers=workers,
                nosandbox=bool(os.environ.get('NOSANDBOX')), expected_games=len(jobs), run_dir=str(run_dir),
                engine_sha256=hashlib.sha256((HERE / 'bc127' / 'lib' / 'python3.13' /
                    'site-packages' / 'unswbc' / 'unswbc_engine.wasm').read_bytes()).hexdigest(),
                map_hashes={m: hashlib.sha256(Path(ab2.mp(m)).read_bytes()).hexdigest() for m in maps})
    raw = Path(str(out) + '.rows.json')
    raw.parent.mkdir(parents=True, exist_ok=True)
    def save():
        raw.write_text(json.dumps(dict(metadata=meta, rows=rows), indent=2) + '\n')
    save()
    with batch_lock():
        with cf.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(play, job): job for job in jobs}
            try:
                for future in cf.as_completed(futures):
                    row = future.result()
                    row['tag'], row['opponent'] = row['tag'].split('__')
                    rows.append(row)
                    save()
                    if len(rows) % 12 == 0 or len(rows) == len(jobs):
                        print(f'{len(rows)}/{len(jobs)} games finished', file=sys.stderr, flush=True)
            finally:
                save()
    return rows


def stats(rows):
    if not rows:
        raise ValueError('no results')
    paired = defaultdict(dict)
    for r in rows:
        key = (r['opponent'], r['map'], r['seed'], r['side'])
        if r['tag'] in paired[key]:
            raise ValueError('duplicate row')
        paired[key][r['tag']] = r
    if any(set(p) != {'BASE', 'CAND'} for p in paired.values()):
        raise ValueError('unpaired results')
    pairs = [(p['BASE'], p['CAND']) for p in paired.values()]
    n = len(pairs)
    b, c = (sum(p[i]['win'] for p in pairs) for i in (0, 1))
    plus = sum(c['win'] and not b['win'] for b, c in pairs)
    minus = sum(b['win'] and not c['win'] for b, c in pairs)
    means = [f'{sum(b[k] for b,c in pairs)/n:.1f}→{sum(c[k] for b,c in pairs)/n:.1f}' for k in ('us', 'them')]
    zero = f'{sum(b["us"] == 0 for b,c in pairs)}→{sum(c["us"] == 0 for b,c in pairs)}'
    return [n, b, c, plus, minus, plus-minus, *means, zero]


def report(rows, base, cand):
    total = stats(rows)
    lines = [f'What we tried: {base} → {cand}, paired against the sparring pool.',
             f'Did it work: CAND win change {total[5]:+d} across {total[0]} matched games; score-0 {total[-1]}.',
             'Who decides: the human maintainer; this is local evidence, not a promotion gate.', '',
             'Games = matched slots per build (two actual games per slot). Scores are mean final queen lengths.',
             'A dead queen scores 0 even if other dragons survive; wins also include elimination and tiebreaks.', '']
    def table(title, groups):
        lines.extend([title, '', '| Group | Games | BASE wins | CAND wins | + | − | Net | us BASE→CAND | them BASE→CAND | us=0 BASE→CAND |',
                      '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|'])
        for label, rs in groups:
            lines.append('| ' + ' | '.join(map(str, [label, *stats(rs)])) + ' |')
        lines.append('')
    table('Per opponent', [(op, [r for r in rows if r['opponent'] == op]) for op in sorted({r['opponent'] for r in rows})] + [('TOTAL', rows)])
    table('Per map family (opponents pooled)', [(f, [r for r in rows if r['family'] == f]) for f in sorted({r['family'] for r in rows})])
    table('Per seat (opponents pooled)', [(s, [r for r in rows if r['side'] == i]) for i,s in enumerate(('A', 'B'))])
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('base')
    p.add_argument('cand')
    select = p.add_mutually_exclusive_group()
    select.add_argument('--maps')
    select.add_argument('--set', choices=['held', 'new', 'quick'], default='quick')
    p.add_argument('--n', type=int, default=2, help='seeds per map, each in both seats (default 2)')
    p.add_argument('--out', type=Path, default=HERE / 'pool-results.md')
    args = p.parse_args()
    maps = args.maps.split(',') if args.maps else QUICK if args.set == 'quick' else (HERE / (args.set + 'set.txt')).read_text().strip().split(',')
    if len(set(maps)) != len(maps):
        p.error('duplicate maps')
    opponents = json.loads((HERE / 'pool.json').read_text())
    rows = run({'BASE': spec(args.base), 'CAND': spec(args.cand)}, opponents, maps, args.n, args.out)
    md = report(rows, args.base, args.cand)
    args.out.write_text(md + '\n')
    print(md)


if __name__ == '__main__':
    main()
