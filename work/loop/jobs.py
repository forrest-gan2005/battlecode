"""Detached job supervisor and local harness adapters; no third-party imports."""
import contextlib
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
OLD_MAPS = 'default,trauma,queen_of_spades,schooltime,portals_v0,slithery_fight_v0,autarky_v0,devil_v0,prisoners_dilemma_v0,trophy'


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    os.replace(tmp, path)


@contextlib.contextmanager
def lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield None
            return
        yield f.fileno()


def busy(path):
    if not Path(path).exists():
        return False
    with lock(path) as fd:
        return fd is None


def run(argv, cwd, env=None, timeout=3600, fds=(), log=None, stdin=None):
    """Children retain leases even if this supervisor is killed."""
    target = open(log, 'a') if log else subprocess.PIPE
    try:
        p = subprocess.Popen([str(x) for x in argv], cwd=cwd, env=env,
                             stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                             stdout=target, stderr=subprocess.STDOUT, text=True,
                             start_new_session=True, pass_fds=tuple(fds))
        try:
            output, _ = p.communicate(stdin, timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.communicate()
            raise RuntimeError(f'Job timed out after {timeout}s')
        if p.returncode:
            raise RuntimeError(f'{Path(str(argv[0])).name} exited {p.returncode}; see {log or output}')
        return output or ''
    finally:
        if log:
            target.close()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def transpose(text):
    """Transpose generated maps, including padded edge IDs and portal partners."""
    lines = [x.split() for x in text.splitlines() if x.strip()]
    w, h = map(int, next(x for x in lines if x[0] == 'MAP')[1:3])
    edges = [x for x in lines if x[0] == 'EDGE']
    count = int(next(x for x in lines if x[0] == 'EDGE_COUNT')[1])
    if count != (2 * h + 1) * (w + 1):
        raise ValueError('transpose requires the generated-map padded edge format')
    def eid(i):
        row, x = divmod(int(i), w + 1)
        y, vertical = divmod(row, 2)
        if (not vertical and x >= w) or (vertical and y >= h):
            return None
        return (2 * x + (1 - vertical)) * (h + 1) + y
    mapped = {}
    for e in edges:
        dest = eid(e[1])
        if dest is not None:
            partner = int(e[3])
            partner = eid(partner) if partner >= 0 else -1
            if partner is None:
                raise ValueError('portal points at a padding edge')
            mapped[dest] = (e[2], str(partner))
    out = []
    for q in lines:
        k = q[0]
        if k == 'MAP':
            q[1:3] = [str(h), str(w)]
        elif k == 'SYMMETRY':
            q[1] = {'x': 'y', 'y': 'x', 'xy': 'xy'}[q[1]]
        elif k == 'MAP_NAME':
            q[-1] += '_T'
        elif k == 'TILE':
            q[1], q[2] = q[2], q[1]
        elif k == 'DRAGON':
            for i in range(3, len(q), 2):
                q[i], q[i + 1] = q[i + 1], q[i]
        elif k == 'EDGE_COUNT':
            out.append(f'EDGE_COUNT {(2 * w + 1) * (h + 1)}')
            for i in range((2 * w + 1) * (h + 1)):
                kind, partner = mapped.get(i, ('0', '-1'))
                out.append(f'EDGE {i} {kind} {partner}')
            continue
        elif k == 'EDGE':
            continue
        out.append(' '.join(q))
    return '\n'.join(out) + '\n'


def stage(repo, tree, out, base):
    sandbox = out / 'harness'
    if (out / 'harness-ready.json').exists():
        return sandbox
    work = sandbox / 'work'
    work.mkdir(parents=True, exist_ok=True)
    for name in ('ab2.py', 'ab3.py', 'ident.py', 'feedcheck.py'):
        shutil.copy2(repo / 'work' / name, work / name)
    shutil.copy2(repo / 'replay.py', sandbox / 'replay.py')
    ab = load_module('loop_ab2', work / 'ab2.py')
    for directory in ab.MAP_DIRS:
        source = repo / directory
        dest = sandbox / directory
        if source.exists() and not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.symlink_to(source, target_is_directory=True)
    for dest, source in ((sandbox / 'base', base), (sandbox / 'candidate', tree / 'mybot2'),
                         (work / 'ab2', out / 'replays')):
        source.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.symlink_to(source, target_is_directory=True)
    write(out / 'harness-ready.json', {'base': str(base), 'tree': str(tree)})
    return sandbox


def plan(path):
    p = read(path)
    if not isinstance(p, dict):
        raise ValueError('build must write build.json')
    if not re.fullmatch(r'[A-Z][A-Z0-9_]*', p.get('toggle', '')):
        raise ValueError('one named boolean toggle is required')
    maps = p.get('mechanism_maps', [])
    n = p.get('mechanism_games_per_map', 4)
    if not maps or not all(re.fullmatch(r'[\w-]+', m) for m in maps):
        raise ValueError('mechanism_maps must contain map names')
    if n % 2 or not 16 <= len(maps) * n * 2 <= 32:
        raise ValueError('mechanism run must have 16–32 games, paired starting sides')
    check = Path(p.get('check', ''))
    if check.is_absolute() or '..' in check.parts or check.suffix != '.py' or not str(check).startswith('work/'):
        raise ValueError('check must be a Python file under work/')
    return p


def summary(rows):
    tags = {t: [r for r in rows if r['tag'] == t] for t in ('base', 'candidate')}
    def measure(rs):
        longest = [r for r in rs if r['how'] == 'longest']
        return {'games': len(rs), 'wins': sum(r['win'] for r in rs),
                'longest_measured': len(longest),
                'us': sum(r['us'] for r in longest) / len(longest) if longest else None,
                'them': sum(r['them'] for r in longest) / len(longest) if longest else None,
                'total_length': 'not measured',
                'side_wins': {str(s): {'games': sum(r['side'] == s for r in rs),
                                      'wins': sum(r['win'] for r in rs if r['side'] == s)} for s in (0, 1)}}
    base = {(r['map'], r['seed'], r['side']): r for r in tags['base']}
    plus = minus = 0
    for r in tags['candidate']:
        b = base[(r['map'], r['seed'], r['side'])]
        plus += bool(r['win'] and not b['win'])
        minus += bool(b['win'] and not r['win'])
    families = {}
    for r in rows:
        family = re.sub(r'^(?:(?:sqheld|sqgen|held|fresh|gen)_)+', '', r['map'])
        family = re.sub(r'_(small|medium|large)_\d+(_T)?$', '', family)
        families.setdefault(family, []).append(r)
    return {'base': measure(tags['base']), 'candidate': measure(tags['candidate']),
            'paired_flips': {'plus': plus, 'minus': minus},
            'families': {f: {t: measure([r for r in rs if r['tag'] == t]) for t in tags}
                         for f, rs in families.items()},
            'limitation': 'ab3 us/them are longest only for how=longest; other endings and total length are not measured.'}


def batch(spec, fds):
    repo, tree, out = map(Path, (spec['repo'], spec['tree'], spec['out']))
    sandbox = Path(spec['sandbox'])
    p = plan(out / 'build.json')
    env = os.environ.copy()
    for key in ('KEEP', 'FAST', 'DIST', 'NOSANDBOX'):
        env.pop(key, None)
    env.update(WORKERS='8', SEED0=str(spec['seed0']))
    env.update(spec.get('game_env', {}))
    sets = {'mechanism': (p['mechanism_maps'], p.get('mechanism_games_per_map', 4))}
    if spec['step'] == 'outcome':
        held = []
        for name in ('heldset_sq.txt', 'freshset.txt'):
            held.extend(x.strip() for x in (repo / 'work' / name).read_text().split(',') if x.strip())
        held = list(dict.fromkeys(held))
        ab = load_module('loop_ab2', sandbox / 'work/ab2.py')
        # A dedicated search directory avoids writing through shared map symlinks.
        target = sandbox / 'loop_maps'
        target.mkdir(exist_ok=True)
        for m in held:
            (target / (m + '_T.map')).write_text(transpose(Path(ab.mp(m)).read_text()))
        script = sandbox / 'work/ab2.py'
        content = script.read_text()
        if "'loop_maps', " not in content:
            script.write_text(content.replace('MAP_DIRS = [', "MAP_DIRS = ['loop_maps', ", 1))
        sets = {'held': (held, 2), 'transposed': ([m + '_T' for m in held], 2),
                'old10': (OLD_MAPS.split(','), 8)}
    else:
        env['KEEP'] = '1'
    write(out / (spec['step'] + '-plan.json'),
          {'base': spec['base'], 'seed0': spec['seed0'], 'workers': 8, 'keep': spec['step'] == 'mechanism',
           'sets': {name: {'maps': maps, 'games_per_map_per_variant': n} for name, (maps, n) in sets.items()}})
    results = {}
    for name, (maps, n) in sets.items():
        dest = out / f'{name}.json'
        argv = [sys.executable, sandbox / 'work/ab3.py', ','.join(maps), 'base', str(n), dest,
                'base@base:', f"candidate@candidate:{p['toggle']}=true"]
        if not dest.exists():
            run(argv, sandbox, env, timeout=24 * 3600, fds=fds, log=out / f'{name}.log')
        rows = read(dest)
        expected = {(t, m, spec['seed0'] + k // 2, k % 2)
                    for m in maps for k in range(n) for t in ('base', 'candidate')}
        actual = {(r['tag'], r['map'], r['seed'], r['side']) for r in rows}
        if len(rows) != len(expected) or actual != expected:
            dest.rename(out / f'{name}-incomplete-{time.time_ns()}.json')
            raise ValueError(f'{name}: missing/duplicate game rows; incomplete results retained')
        results[name] = summary(rows)
    write(out / f"{spec['step']}-summary.json", results)
    if spec['step'] == 'outcome':
        write(out / 'stats.json', results)
    if spec['step'] == 'mechanism':
        run([sys.executable, tree / p['check'], '--replays', out / 'replays',
             '--base', 'base', '--candidate', 'candidate', '--output', out / 'check.json'],
            tree, env, fds=fds, log=out / 'check.log')
        check = read(out / 'check.json')
        if not isinstance(check, dict) or not isinstance(check.get('passed'), bool) or not check.get('note'):
            raise ValueError('check must write {passed: bool, note: str, ...measurements}')
        # smoke_pick adapter: each local replay becomes a game in its online input format.
        adapter = out / 'smoke-picks'
        adapter.mkdir(exist_ok=True)
        games = []
        for i, r in enumerate(read(out / 'mechanism.json')):
            src = out / 'replays' / f"{r['tag']}_{r['map']}_{r['seed']}_{r['side']}.replay"
            dst = adapter / f'M{i}.replay'
            if not dst.exists():
                dst.symlink_to(src)
            games.append({'gameId': i, 'teamAId': 1119 if r['side'] == 0 else 0,
                          'teamBId': 1119 if r['side'] == 1 else 0, 'mapName': r['map'], 'source': str(src)})
        write(adapter / 'index.json', {'games': games})
        run([sys.executable, Path(spec['swarm']) / 'tools/smoke_pick.py', adapter, '--n', '3'],
            tree, env, fds=fds, log=out / 'smoke-pick.log')


def ai(spec, fds):
    step = spec['step']
    out = Path(spec['out'])
    env = os.environ.copy()
    env.update(spec.get('game_env', {}))
    env.update(LOOP_GUARD=str(HERE / 'guard.py'), CARD_LOOP_GUARD=str(HERE / 'guard.py'),
               CARD_LOOP_GAMES='1' if step == 'build' else '0', LOOP_STEP=step,
               LOOP_TREE=spec['tree'], LOOP_OUT=str(out), LOOP_BATCH_LEASE='1' if step == 'build' else '0')
    prompt = Path(spec['prompt']).read_text()
    if spec.get('light'):
        argv = ['claude', '-p', '--model', 'claude-sonnet-5-5', '--effort', 'medium',
                '--tools', '', '--no-session-persistence']
        if not (out / spec['output']).exists():
            result = run(argv, spec['tree'], env, fds=fds, stdin=prompt)
            # No tools: light steps return exactly one JSON object on stdout.
            write(out / spec['output'], json.loads(result))
            Path(spec['log']).write_text(json.dumps({'type': 'result', 'result': result}) + '\n')
    else:
        argv = ['claude', '-p', '--model', 'opus', '--effort', 'high', '--permission-mode',
                'bypassPermissions', '--settings', str(HERE / 'settings.json'),
                '--output-format', 'stream-json', '--verbose']
        def completed():
            last = None
            if Path(spec['log']).exists():
                for line in Path(spec['log']).read_text().splitlines():
                    try:
                        item = json.loads(line)
                    except ValueError:
                        continue
                    if item.get('type') == 'result':
                        last = item
            return last is not None and not last.get('is_error')
        # A crash after Claude's result but before done.json must not spend another AI step.
        if not completed():
            run(argv, spec['tree'], env, fds=fds, stdin=prompt, log=spec['log'])
        if not completed():
            raise ValueError('Claude did not finish successfully')
    if step == 'build':
        p = plan(out / 'build.json')
        source = (Path(spec['tree']) / 'mybot2/main.cpp').read_text()
        if len(re.findall(rf"constexpr bool {p['toggle']} = false;", source)) != 1:
            raise ValueError('new toggle must be default-off')
        run(['c++', '-std=c++20', '-O2', Path(spec['tree']) / 'mybot2/main.cpp', '-o', out / 'bot-off'],
            spec['tree'], env, fds=fds, log=out / 'compile.log')
        # ident.py returns zero even on DIFF: require its final sentinel and all 40 comparisons.
        ident = out / 'ident.log'
        env.update(REF='base', IDENT_MAPS=OLD_MAPS, IDENT_SEEDS='2')
        text = run([sys.executable, Path(spec['sandbox']) / 'work/ident.py', 'candidate'],
                   spec['sandbox'], env, fds=fds)
        ident.write_text(text)
        if text.strip().splitlines()[-1:] != ['identical'] or len(re.findall(r'^OK\s', text, re.M)) != 40:
            raise ValueError('toggle-off identity failed; see ident.log')
        run(['git', 'merge-base', '--is-ancestor', spec['base'], 'HEAD'], spec['tree'], fds=fds)
        head = run(['git', 'rev-parse', 'HEAD'], spec['tree'], fds=fds).strip()
        if run(['git', 'status', '--porcelain', '--untracked-files=no'], spec['tree'], fds=fds).strip():
            raise ValueError('build left tracked changes uncommitted')
        if head == spec['base']:
            raise ValueError('build did not commit its implementation')
        if run(['git', 'branch', '--show-current'], spec['tree'], fds=fds).strip() != f"card/{spec['number']}":
            raise ValueError('build changed branch')
        write(out / 'built.json', {'commit': head, 'toggle': p['toggle']})


def worker(path):
    path = Path(path)
    spec = read(path / 'job.json')
    with contextlib.ExitStack() as stack:
        fds = []
        for lease in [path / 'lease', *[Path(spec['locks']) / f'{x}.lock' for x in sorted(spec['resources'])]]:
            fd = stack.enter_context(lock(lease))
            if fd is None:
                return
            fds.append(fd)
        if (path / 'done.json').exists():
            return
        write(path / 'running.json', {'pid': os.getpid(), 'started': time.time(), 'resources': spec['resources']})
        try:
            if spec['kind'] == 'ai':
                ai(spec, fds)
            else:
                batch(spec, fds)
            result = {'ok': True}
        except Exception as exc:
            result = {'ok': False, 'error': str(exc)}
        write(path / 'done.json', {**result, 'finished': time.time()})
