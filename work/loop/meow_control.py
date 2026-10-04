"""Consume confirmed /meow requests inside the runner lease; never start/stop the poller."""
from pathlib import Path
import re
import shutil
import sys

from jobs import OLD_MAPS, busy, read, run, stage, write


def issue(loop, number):
    card = loop.gh('issue', 'view', str(number), '--repo', 'forrest-gan2005/battlecode',
                   '--json', 'number,title,body,state,labels,createdAt,author,comments')
    if not card['title'].lower().startswith(('[idea]', '[task]')):
        raise ValueError('Only idea/task cards may be controlled.')
    return card


def result(loop, req, ok, message):
    text = message + '\n\n' + req['audit']
    number = req.get('card', req.get('pr'))
    if number:
        loop.cmd(['gh', 'pr' if 'pr' in req else 'issue', 'comment', str(number),
                  '--repo', 'forrest-gan2005/battlecode', '--body', text])
    write(loop.out / 'meow-results' / (req['id'] + '.json'), {'ok': ok, 'message': text})


def submit_job(loop, req, step, spec):
    path = loop.out / 'meow-jobs' / req['id']
    done = read(path / 'done.json')
    if done:
        return done
    if busy(path / 'lease') or busy(loop.locks / 'batch.lock') or 'batch' in loop.launched:
        return None
    if shutil.disk_usage(loop.out).free < 21 * 1024**3:
        return None
    processes = loop.cmd(['ps', '-axo', 'command='])
    if re.search(r'(?:unswbc(?:-clean\.py)?\s+run|(?:ab3|ident)\.py\s)', processes):
        return None
    path.mkdir(parents=True, exist_ok=True)
    write(path / 'job.json', dict(spec, kind='meow', step=step, resources=['batch'], locks=str(loop.locks),
                                  repo=str(loop.repo), out=str(path), game_env=loop.args.game_env))
    import subprocess
    with (path / 'supervisor.log').open('a') as log:
        child = subprocess.Popen(['nice', '-n', '10', sys.executable, str(Path(__file__).with_name('runner.py')),
                                  '--job', str(path)], stdin=subprocess.DEVNULL, stdout=log,
                                 stderr=log, start_new_session=True)
    loop.children.append(child)
    loop.launched.add('batch')
    return None


def controls(loop):
    if loop.args.dry_run:
        return False
    control = read(loop.out / 'meow-control.json', {'paused': False})
    for path in sorted((loop.out / 'meow-requests').glob('*.json'), key=lambda p: p.stat().st_mtime_ns):
        req = read(path)
        receipt_path = loop.out / 'meow-receipts' / path.name
        receipt = read(receipt_path, {})
        if receipt.get('state') in {'done', 'error'}:
            continue
        if receipt.get('state') == 'executing':
            result(loop, req, False, 'Interrupted control request; inspect remote state before retrying.')
            write(receipt_path, {'state': 'error'})
            continue
        try:
            action = req['action']
            if action in {'pause_runner', 'resume_runner'}:
                control.update(paused=action == 'pause_runner', requester=req['requester_id'], audit=req['audit'])
                write(loop.out / 'meow-control.json', control)
                result(loop, req, True, 'Runner paused between jobs.' if control['paused'] else 'Runner resumed.')
                write(receipt_path, {'state': 'done'})
                continue
            if control['paused']:
                continue
            if action == 'identity_notice':
                done = submit_job(loop, req, 'identity_notice', req)
                if done:
                    result(loop, req, done['ok'], 'Post-force old-10 toggle-off identity: '
                           + ('passed (40 replay comparisons).' if done['ok'] else 'WARNING: ' + done.get('error', 'failed')))
                    write(receipt_path, {'state': 'done'})
                continue
            if action == 'queue_test' and req['kind'] == 'pair-online':
                card = issue(loop, req['card'])
                if not req.get('commit'):
                    raise ValueError('No implementation commit; select a branch before requesting an online pair.')
                done = submit_job(loop, req, 'pair-online', req)
                if done:
                    result(loop, req, done['ok'], 'Unranked paired online test: '
                           + ('completed; rollback verified; see job log.' if done['ok'] else done.get('error', 'failed')))
                    write(receipt_path, {'state': 'done'})
                continue
            if busy(loop.locks / 'ai.lock') or busy(loop.locks / 'batch.lock') or loop.launched:
                continue
            card = issue(loop, req['card'])
            meta = loop.metadata(card)
            state = next((l['name'][7:] for l in card['labels'] if l['name'].startswith('status:')), 'untested')
            if req.get('_state') and state != req['_state']:
                raise ValueError('Card moved after confirmation; request a fresh preview.')
            write(receipt_path, {'state': 'executing'})
            if action == 'use_branch_as_impl':
                commit = req['commit']
                if not re.fullmatch('[0-9a-f]{40}', commit):
                    raise ValueError('A pinned commit is required.')
                loop.cmd(['git', 'fetch', 'origin', commit])
                tree = loop.cards / f"card-{card['number']}-impl-{commit[:12]}"
                if not tree.exists():
                    loop.cmd(['git', 'worktree', 'add', '--detach', tree, commit])
                meta = loop.new_attempt(card, meta, 'Use the member-selected implementation; skip AI coding.',
                                        impl_commit=commit, impl_tree=str(tree), commit=commit)
                loop.transition(card, 'building')
            elif action == 'set_state':
                target = req['state']
                if target == 'candidate' and not meta.get('commit'):
                    raise ValueError('Candidate still needs code; select a branch/commit first.')
                meta.update(force_override=True, force_reason=req['audit'], meow_control=req['id'])
                meta.pop('ai_pending', None)
                if target == 'candidate':
                    meta['phase'] = 'tested'
                if card.get('state') == 'CLOSED':
                    loop.cmd(['gh', 'issue', 'reopen', str(card['number']), '--repo', 'forrest-gan2005/battlecode'])
                loop.save(card, meta)
                loop.transition(card, target)
            elif action == 'queue_test':
                if not meta.get('commit'):
                    raise ValueError('Test requires an implementation commit.')
                out = Path(loop.context(card, meta)['out'])
                if not (out / 'build.json').exists():
                    raise ValueError('Test plan is missing; use_branch_as_impl prepares one without rewriting code.')
                name = 'mechanism' if req['kind'] == 'mechanism' else 'outcome'
                # Preserve earlier evidence while allowing an explicit rerun to get fresh artifacts.
                archive = out / ('before-meow-' + req['id'])
                archive.mkdir(exist_ok=True)
                names = (['mechanism.json', 'mechanism-summary.json', 'look.json', 'check.json'] if name == 'mechanism'
                         else ['held.json', 'transposed.json', 'old10.json', 'stats.json', 'verdict.json', 'verdict.md'])
                for filename in names:
                    if (out / filename).exists():
                        (out / filename).rename(archive / filename)
                for job in ([name, 'look'] if name == 'mechanism' else [name, 'verdict']):
                    source = out / 'jobs' / job
                    if source.exists():
                        source.rename(archive / ('job-' + job))
                meta.update(phase='meow-retest', force_override=bool(req.get('force')), meow_control=req['id'])
                loop.save(card, meta)
                loop.transition(card, 'building' if name == 'mechanism' else 'testing')
            else:
                raise ValueError('Unknown confirmed runner request.')
            result(loop, req, True, f"Applied {action} to #{card['number']}.")
            write(receipt_path, {'state': 'done'})
        except Exception as exc:
            result(loop, req, False, f'Control request needs review: {type(exc).__name__}: {exc}')
            write(receipt_path, {'state': 'error'})
    return control['paused']


def export(repo, commit, destination, fds):
    files = run(['git', 'ls-tree', '-r', '--name-only', commit, '--', 'mybot2'], repo, fds=fds).splitlines()
    if not files:
        raise ValueError('Commit has no mybot2 source.')
    for name in files:
        rel = Path(name).relative_to('mybot2')
        if '..' in rel.parts:
            raise ValueError('Invalid git path.')
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(run(['git', 'show', f'{commit}:{name}'], repo, fds=fds))


def job(spec, fds):
    repo, out = Path(spec['repo']), Path(spec['out'])
    env = __import__('os').environ.copy()
    env.update(spec.get('game_env', {}))
    env['WORKERS'] = '6'
    if shutil.disk_usage(out).free < 21 * 1024**3:
        raise RuntimeError('Less than 21 GB free; no games started.')
    run(['git', 'fetch', 'origin', spec['commit']], repo, fds=fds)
    candidate = out / 'selected' / 'mybot2'
    export(repo, spec['commit'], candidate, fds)
    if spec['step'] == 'pair-online':
        # An explicit confirmed queue request authorizes this fixed, unranked 30:30 pair.
        swarm = repo.parent / 'unsw-swarm'
        from jobs import load_module
        smoke = load_module('meow_confirmed_smoke', swarm / 'tools/smoke.py')
        if smoke.active()['id'] != spec['previous_id']:
            raise ValueError('Pair baseline changed after confirmation; request a new preview.')
        if spec.get('toggle'):
            text = (candidate / 'main.cpp').read_text()
            text, count = re.subn(rf"(constexpr bool {re.escape(spec['toggle'])} = )false;", r'\g<1>true;', text)
            if count != 1:
                raise ValueError('Selected online toggle is not present exactly once.')
            (candidate / 'main.cpp').write_text(text)
        if spec.get('force'):
            smoke.check_freeze = lambda: None
        code = smoke.main(['pair', str(candidate), '--name', 'meow-' + spec['id'][:24],
                           '--top', '1', '--games', '60', '--confirm'])
        if code:
            raise RuntimeError('Pair stopped; inspect the smoke state and rollback instructions before retrying.')
        return
    if spec.get('base_from_parent'):
        spec['base'] = run(['git', 'rev-parse', spec['commit'] + '^1'], repo, fds=fds).strip()
        if not re.fullmatch('[0-9a-f]{40}', spec['base']):
            raise ValueError('Could not identify the actual previous main commit.')
    run(['git', 'fetch', 'origin', spec['base']], repo, fds=fds)
    base = out / 'base'
    export(repo, spec['base'], base, fds)
    before, after = (base / 'main.cpp').read_text(), (candidate / 'main.cpp').read_text()
    old = dict(re.findall(r'constexpr bool\s+(\w+)\s*=\s*(true|false);', before))
    toggles = [name for name, value in re.findall(r'constexpr bool\s+(\w+)\s*=\s*(true|false);', after)
               if value == 'true' and old.get(name) != 'true']
    for name in toggles:
        after = re.sub(rf'(constexpr bool\s+{re.escape(name)}\s*=\s*)true;', r'\g<1>false;', after)
    (candidate / 'main.cpp').write_text(after)
    sandbox = stage(repo, candidate.parent, out, base)
    env.update(REF='base', IDENT_MAPS=OLD_MAPS, IDENT_SEEDS='2')
    text = run([sys.executable, sandbox / 'work/ident.py', 'candidate'], sandbox, env, fds=fds)
    (out / 'ident.log').write_text(text)
    if text.strip().splitlines()[-1:] != ['identical'] or len(re.findall(r'^OK\s', text, re.M)) != 40:
        raise ValueError('Toggle-off identity failed; notification only, merged code is unchanged. See ' + str(out / 'ident.log'))
