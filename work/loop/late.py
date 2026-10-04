"""Explain missed estimates from local evidence; persist one notice per deadline."""
from collections import Counter, deque
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
import time

from card_names import card_ref
from jobs import append_event, busy, eta_minutes, iso_time, job_start, read, write


def compact(text, limit=300):
    text = ' '.join(str(text).split())
    return text if len(text) <= limit else text[:limit - 1] + '…'


def json_rows(path):
    try:
        with Path(path).open() as stream:
            for line in stream:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
    except OSError:
        return


def ai_reason(spec):
    counts, activities, seen, last = Counter(), Counter(), set(), deque(maxlen=2)
    for item in json_rows(spec.get('log', '')):
        if not isinstance(item, dict):
            continue
        message = item.get('message') or {}
        blocks = message.get('content', []) if isinstance(message, dict) else []
        for block in blocks if isinstance(blocks, list) else []:
            if not isinstance(block, dict) or block.get('type') != 'tool_use':
                continue
            key = block.get('id')
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            name = block.get('name', 'unknown')
            counts[name] += 1
            args = block.get('input') or {}
            if not isinstance(args, dict):
                args = {}
            desc = args.get('description') or args.get('command') or args.get('file_path') or name
            last.append(compact(desc, 72))
            command = str(args.get('command', ''))
            evidence = str(desc) + ' ' + command
            if name == 'Read' or (name == 'Bash' and re.search(r'\b(cat|sed|head|tail|rg|grep)\b', command)):
                activities['reads'] += 1
            if name in ('Edit', 'Write', 'MultiEdit'):
                activities['edits'] += 1
            if name == 'Bash':
                if re.search(r'\bident(?:ity)?(?:\.py)?\b|fingerprint', evidence, re.I):
                    activities['identity checks'] += 1
                elif re.search(r'\b(?:c\+\+|g\+\+|clang\+\+|cmake\b|make\b|build\b)', evidence, re.I):
                    activities['builds'] += 1
                elif re.search(r'\b(ab[23]\.py|unswbc|replay|games?|runq)\b', evidence, re.I):
                    activities['game/replay runs'] += 1
    summary = ', '.join(f'{n} {name}' for name, n in activities.items())
    types = ', '.join(f'{n} {name}' for name, n in counts.items())
    reason = f'still working: {sum(counts.values())} tool calls so far'
    if summary or types:
        reason += ' (' + compact(summary or types, 110) + ')'
    reason += '; last: ' + ('; '.join(repr(x) for x in last) if last else 'no tool descriptions available')
    return compact(reason)


def longest_run(root, step):
    longest = 0
    for path in Path(root).glob(f'**/jobs/{step}/done.json'):
        try:
            done = read(path)
            longest = max(longest, (done['finished'] - job_start(path.parent)) / 60)
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return longest


def batch_progress(spec, elapsed):
    out, step = Path(spec['out']), spec['step']
    try:
        plan = read(out / f'{step}-plan.json', {})
    except ValueError:
        plan = {}
    planned, done = 0, set()
    for name, group in plan.get('sets', {}).items():
        expected = {(tag, m, spec['seed0'] + k // 2, k % 2)
                    for tag in ('base', 'candidate') for m in group['maps']
                    for k in range(group['games_per_map_per_variant'])}
        planned += len(expected)
        try:
            rows = read(out / f'{name}.json', [])
        except ValueError:
            rows = []
        for row in [*rows, *json_rows(out / f'{name}.rows.jsonl')]:
            if isinstance(row, dict):
                key = tuple(row.get(k) for k in ('tag', 'map', 'seed', 'side'))
                if key in expected:
                    done.add((name, key))
        for key in expected:
            replay = out / 'replays' / ('_'.join(map(str, key)) + '.replay')
            if replay.exists() and replay.stat().st_size and replay.stat().st_mtime >= spec.get('started', 0):
                done.add((name, key))
    count = len(done)
    rate = count / elapsed if elapsed > 0 else 0
    if not planned or not rate:
        return 'game progress unavailable; unknown, checking again in 15 min', 15, False
    if count >= planned:
        return f'all {planned} games done; post-game checks still running', 5, True
    return (f'games are slower than planned: {count} of {planned} done, {rate:.1f}/min',
            max(5, (planned - count) / rate), True)


def external_holder(path):
    try:
        result = subprocess.run(['lsof', '-nP', '-Fpcfl', str(path)], capture_output=True, text=True, timeout=5)
        holders, current = [], None
        for line in result.stdout.splitlines():
            if line.startswith('p'):
                current = {'pid': line[1:], 'command': 'process', 'locked': False}
                holders.append(current)
            elif current is not None and line.startswith('c'):
                current['command'] = line[1:]
            elif current is not None and line.startswith('l') and line[1:] in ('W', 'w'):
                current['locked'] = True
        if not holders:
            return None
        holder = next((h for h in holders if h['locked']), holders[0])
        result = subprocess.run(['ps', '-p', holder['pid'], '-o', 'command='], capture_output=True, text=True, timeout=5)
        command = result.stdout.strip() or holder['command']
        scripts = re.findall(r'(?:[\w./-]+/)?[\w-]+\.py\b', command)
        description = 'pool validation (work/pool.py)' if any(s.endswith('/pool.py') for s in scripts) else compact(command, 100)
        return f"{description} (pid {holder['pid']})"
    except (OSError, subprocess.SubprocessError):
        return None


def lock_reason(root, locks, resources, path, now, queued=()):
    holders, remaining, unknown, matched = [], [], False, set()
    for file in Path(root).glob('**/jobs/*/job.json'):
        job = file.parent
        if job == Path(path) or (job / 'done.json').exists():
            continue
        try:
            spec = read(file)
            shared = set(resources) & set(spec.get('resources', []))
            if not shared or not (busy(job / 'lease') or str(job) in queued):
                continue
            late = read(job / 'late.json', {}).get('notice', {})
            if late.get('waiting') or late.get('started') != iso_time(job_start(job, spec)):
                late = {}
            deadline = (dt.datetime.fromisoformat(late['new_eta_at']).timestamp() if late.get('new_eta_at')
                        else job_start(job, spec) + spec.get('eta_minutes', eta_minutes(root, spec['step'])) * 60)
            left = (deadline - now) / 60
            matched.update(shared)
            if left <= 0 or late.get('eta_known') is False:
                unknown = True
                estimate = 'estimate overdue'
            else:
                remaining.append(left)
                estimate = f'about {left:.0f}m remaining'
            holders.append(f"{card_ref(spec)} {spec['step']} ({estimate})")
        except (OSError, ValueError, TypeError, KeyError):
            continue
    for resource in sorted(set(resources) - matched):
        lockfile = Path(locks) / f'{resource}.lock'
        if busy(lockfile):
            holders.append(external_holder(lockfile) or f'{resource} lock holder unidentified')
            unknown = True
    if not holders:
        unknown = True
    reason = 'waiting for ' + '; '.join(holders) if holders else 'lock holder unidentified'
    if unknown:
        reason += '; unknown, checking again in 15 min'
    return compact(reason), max(remaining, default=0), not unknown


def check_late(root, locks, card, step, path, timing, resources=(), queued=(), now=None):
    now = time.time() if now is None else now
    path = Path(path)
    waiting = bool(timing.get('queue'))
    state = read(path / 'late.json', {})
    if (path / 'done.json').exists():
        return {'late': False}
    spec = read(path / 'job.json', {})
    started = job_start(path, spec) if spec and not waiting else None
    phase = 'waiting' if waiting else f'running:{started}'
    if state.get('phase') != phase:
        state = {'phase': phase, 'started': now if waiting else started, 'level': state.get('level', 0)}
    if state['started'] is None:
        return {'late': False}
    elapsed = max(0, (now - state['started']) / 60)
    planned = timing['eta_minutes']
    prior = state.get('notice')
    due = (now > state['deadline'] if prior else elapsed >= 15 if waiting
           else elapsed > planned * 1.25 and elapsed - planned >= 5)
    if due:
        known, wait = True, None
        if waiting:
            reason, wait, known = lock_reason(root, locks, resources, path, now, queued)
            minutes = wait + planned if known else 15
        elif step in ('mechanism', 'outcome'):
            reason, minutes, known = batch_progress(spec, elapsed)
        else:
            reason = ai_reason(spec)
            minutes = max(5, max(elapsed * 1.3, longest_run(root, step)) - elapsed)
        event_spec = {**spec, 'out': str(path.parent.parent), 'step': step,
                      'number': card['number'], 'title': card.get('title', ''),
                      'name': card.get('name') or timing.get('name', ''), 'eta_minutes': planned}
        level = state['level'] + 1
        deadline = now + (wait if waiting and known else minutes) * 60
        notice = append_event(path, event_spec, 'late', now,
                              event_id=f'{path}:{phase}:{state["started"]}:{level}', level=level,
                              started=iso_time(state['started']), planned_minutes=planned,
                              elapsed_minutes=elapsed, reason=compact(reason), waiting=waiting,
                              queue=timing.get('queue'), new_eta_minutes=minutes,
                              new_eta_at=iso_time(now + minutes * 60), eta_known=known,
                              new_start_at=iso_time(deadline) if waiting and known else None,
                              next_check_at=iso_time(deadline))
        state.update(level=level, notice=notice,
                     deadline=dt.datetime.fromisoformat(notice['next_check_at']).timestamp())
    write(path / 'late.json', state)
    notice = state.get('notice')
    return ({'late': True, **{k: notice[k] for k in ('reason', 'new_eta_minutes', 'new_eta_at',
             'new_start_at', 'eta_known', 'level')}, 'elapsed_minutes': elapsed,
             'waiting_started': iso_time(state['started']) if waiting else None}
            if notice else {'late': False})
