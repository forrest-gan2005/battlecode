#!/usr/bin/env python3
"""GitHub-label-driven card loop. --dry-run performs reads only; --once is one poll."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from string import Template

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from card_names import card_ref, card_name, unique_slug, valid_slug
from fair_queue import priority, order_cards, read_fair, served

from jobs import OLD_MAPS, busy, lock, read, stage, worker, write, eta_minutes, step_timing, remaining_wait

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
GH_REPO = 'forrest-gan2005/battlecode'
ZHE_LOGIN = 'zhex0121'
SWARM = REPO.parent / 'unsw-swarm'
KST = dt.timezone(dt.timedelta(hours=9))
FREEZE = dt.datetime(2026, 10, 8, 20, tzinfo=KST)
ACTIVE = {'ready', 'needs-info', 'building', 'needs-look', 'testing', 'candidate'}
MARK = re.compile(r'<!-- card-loop (\{.*?\}) -->', re.S)
PREFIXES = ('What we tried: ', 'Did it work: ', 'Who decides now: ')
AI_IDENTICAL_RATIO = 0.95
AI_NET_THRESHOLD = 9
AI_MAX_REVISIONS = 1
AI_COIN_FLIP = 'coin flip locally; a 30:30 online pair test would settle it (tools/smoke.py pair)'

AI_DECISION = "The loop builds and tests it now; one teammate's OK is needed only before it ships."


def idea_title(title):
    title = re.sub(r'^(?:\s*\[(?:Idea|Task)\]\s*)+', '', title.strip(), flags=re.I).strip()
    if not title:
        raise ValueError('ladder card title is empty after removing prefixes')
    return '[Idea] ' + title


def routine_post(key):
    return bool(re.fullmatch(r'(?:attempt-\d+|built-\d+|batch-\d+-[\w-]+)', key))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]


def labels(card):
    return {x['name'] if isinstance(x, dict) else x for x in card.get('labels', [])}


def is_task(card):
    return 'type:task' in labels(card)


def state(card):
    states = [x[7:] for x in labels(card) if x.startswith('status:')]
    return states[0] if len(states) == 1 else 'conflicting-labels'


def records(card):
    result = []
    for c in card.get('comments', []):
        for m in MARK.finditer(c.get('body', '')):
            try:
                result.append(json.loads(m.group(1)))
            except ValueError:
                pass
    return result


def human_replies(card, after, zhe=False):
    # GitHub bot comments and our marker-bearing comments never count as answers.
    author = card.get('author', {}).get('login')
    # by:zhe cards created through meowbot may have the bot as issue author.
    wanted = os.environ.get('LOOP_ZHE_LOGIN', ZHE_LOGIN) if zhe else None
    result = []
    for c in card.get('comments', []):
        user = c.get('user') or c.get('author') or {}
        login = user.get('login', '')
        body = c.get('body', '')
        if c.get('created_at', c.get('createdAt', '')) <= after:
            continue
        forwarded = bool(re.search(r'^(?:Reply|Answer) from Zhe\s*:', body, re.I))
        if MARK.search(body):
            continue
        if (user.get('type') == 'Bot' or login.endswith('[bot]')) and not forwarded:
            continue
        if body.startswith('Questions before we build') or '[check] by `card-loop`' in body or '[test] by `card-loop`' in body:
            continue
        if zhe and login != wanted:
            # meowbot's copied Discord answer must name the speaker explicitly.
            if not forwarded:
                continue
        result.append(c)
    return result


def summary_text(text):
    lines = text.strip().splitlines()
    if len(lines) < 3 or any(not s.startswith(p) or not s[len(p):].strip() for s, p in zip(lines, PREFIXES)):
        raise ValueError('GitHub result must start with the three plain summary lines')
    return text.strip()


class Loop:
    def __init__(self, args):
        self.args = args
        self.repo = Path(args.repo).resolve()
        self.out = Path(args.out).expanduser().resolve()
        self.cards = Path(args.cards).expanduser().resolve()
        self.fair_path = Path.home() / "meow-loop-out/fair.json"
        # Machine-global even with different --out directories or repository worktrees.
        self.locks = Path.home() / '.meow-card-loop-locks'
        self.status = {}
        self.children = []

    def cmd(self, argv, cwd=None, data=None, raw=False):
        proc = subprocess.run([str(x) for x in argv], cwd=cwd or self.repo, input=data,
                              capture_output=True, text=True, timeout=120)
        if proc.returncode:
            raise RuntimeError(f'{argv[0]} {argv[1]} failed: {proc.stderr.strip()[:400]}')
        return proc.stdout if raw else proc.stdout.strip()

    def gh(self, *args, payload=None):
        argv = ['gh', *args]
        if payload is not None:
            argv += ['--input', '-']
        result = self.cmd(argv, data=json.dumps(payload) if payload is not None else None)
        return json.loads(result) if result else None

    def cards_on_board(self):
        rows = self.gh('issue', 'list', '--repo', GH_REPO, '--state', 'open', '--limit', '1000',
                       '--json', 'number,title,body,labels,createdAt,author')
        cards = []
        for card in rows:
            if not (card['title'].lower().startswith('[idea]') or is_task(card)):
                continue
            ai_done = ('by:ai' in labels(card) and not is_task(card)
                       and state(card) in {'tested', 'rejected', 'inconclusive'})
            # Tested cards stay polled so a reply after the results can act as the decision.
            if state(card) not in ACTIVE and state(card) != 'tested' and not ai_done:
                continue
            pages = self.gh('api', f"repos/{GH_REPO}/issues/{card['number']}/comments", '--paginate', '--slurp')
            card['comments'] = [c for page in pages for c in page]
            if state(card) == 'tested' and not ai_done and not any(r.get('phase') == 'tested' for r in records(card)):
                continue  # tested by hand, no loop results to decide on
            cards.append(card)
        return order_cards(cards, read_fair(self.fair_path))

    def notice(self, card, text, metadata=None):
        key = str(card['number'])
        self.status[key] = {**self.status.get(key, {}), **(metadata or {}), 'state': state(card), 'step': text, 'title': card_ref(card), 'name': card_name(card)}
        print(f"{card_ref(card)} [{state(card)}] {text}", flush=True)

    def board(self, *args, base=None):
        if self.args.dry_run:
            raise RuntimeError('dry-run attempted board mutation')
        argv = [*args, '--loop', 'card-loop', '--wf', '2']
        if base:
            # board.py otherwise stamps current main on results from an older base.
            return self.cmd([sys.executable, HERE / 'runner.py', '--board-base', base,
                             '--repo', self.repo, '--board-args', json.dumps(argv)])
        return self.cmd([sys.executable, self.repo / 'work/board.py', *argv])

    def transition(self, card, target):
        self.board('state', str(card['number']), target)
        if state(card) == 'ready' and target in {'building', 'needs-info'}:
            write(self.fair_path, served(read_fair(self.fair_path), card))

    def post(self, card, key, text, target=None, kind=None, ask=False, metadata=None, close=False):
        """A remote marker repairs a crash between comment creation and label replacement."""
        marker = {**(metadata or {}), 'key': key}
        if not ask and not key.startswith('ai-decision-') and not text.startswith(PREFIXES[0]):
            text = (f"What we tried: Move {card_ref(card)} to its next step.\n"
                    f"Did it work: {text}\nWho decides now: "
                    + ('The author and required teammate approvers review the PR.' if key.startswith('candidate-')
                       else 'The loop continues; people decide acceptance.'))
        text = re.sub(r'(?<![\w/])#' + str(card['number']) + r'\b(?![\w-])' + (r'(?!' + re.escape(' ' + card_ref(card).split(' ', 1)[1]) + ')' if ' ' in card_ref(card) else ''), card_ref(card), text)
        text += f'\n\nCard: [{card_ref(card)}](https://github.com/{GH_REPO}/issues/{card["number"]})'
        pending = self.out / f"card-{card['number']}" / 'pending-post.json'
        write(pending, {'key': key, 'text': text, 'target': target, 'kind': kind, 'ask': ask, 'metadata': metadata, 'close': close})
        if not any(r.get('key') == key for r in records(card)):
            dest = self.out / f"card-{card['number']}" / f'post-{digest(key)}.md'
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text.rstrip() + '\n\n<!-- card-loop ' + json.dumps(marker) + ' -->\n')
            if ask:
                self.board('ask', str(card['number']), '--file', str(dest))
            elif kind:
                self.board('report', str(card['number']), '--kind', kind, '--file', str(dest), '--state', target,
                           base=(metadata or {}).get('base'))
            else:
                self.cmd(['gh', 'issue', 'comment', str(card['number']), '--repo', GH_REPO, '--body-file', dest])
            card['comments'].append({'body': dest.read_text(), 'created_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                                     'user': {'login': 'card-loop', 'type': 'Bot'}})
        if target:
            self.transition(card, target)
        if close:
            self.cmd(['gh', 'issue', 'close', str(card['number']), '--repo', GH_REPO])
        pending.unlink(missing_ok=True)

    def latest_base(self):
        self.cmd(['git', 'fetch', 'origin', 'main'])
        return self.cmd(['git', 'rev-parse', 'origin/main'])

    def base_moved(self, base):
        # Only bot code counts: docs/work/tools commits on main must not restart or stale a card.
        latest = self.latest_base()
        if latest == base:
            return False
        try:
            return bool(self.cmd(['git', 'diff', '--name-only', base, latest, '--', 'mybot2']).strip())
        except RuntimeError:
            return True  # unknown base: be safe and treat it as moved

    def metadata(self, card):
        local = read(self.out / f"card-{card['number']}" / 'card.json', {})
        for r in records(card):
            if 'attempt' in r and (not local or r['attempt'] > local.get('attempt', 0)
                                   or (r['attempt'] == local.get('attempt', 0) and not local.get('meow_control'))):
                local = {**local, **r}
        return local

    def save(self, card, meta):
        write(self.out / f"card-{card['number']}" / 'card.json', meta)

    def context(self, card, meta):
        out = self.out / f"card-{card['number']}" / f"attempt-{meta.get('attempt', 0)}"
        return {'number': card['number'], 'title': card_ref(card), 'name': card_name(card), 'full_title': card['title'], 'body': card.get('body', ''),
                'comments': json.dumps(card.get('comments', []), ensure_ascii=False),
                'base': meta.get('base', 'not selected yet'), 'repo': str(self.repo),
                'tree': meta.get('impl_tree', str(self.cards / f"card-{card['number']}")), 'out': str(out),
                'card_out': str(self.out / f"card-{card['number']}"),
                'sandbox': str(out / 'harness'), 'old_maps': OLD_MAPS,
                'swarm': str(SWARM), 'seed0': 10000 + card['number'] * 100,
                'metadata': json.dumps(meta, ensure_ascii=False),
                'revision_evidence': meta.get('revision_evidence', 'No automatic revision requested.')}

    def ensure_tree(self, card, meta):
        if meta.get('impl_commit'):
            tree = Path(meta['impl_tree'])
            if self.cmd(['git', 'rev-parse', 'HEAD'], tree) != meta['impl_commit']:
                raise ValueError('Selected implementation worktree changed.')
            if self.cmd(['git', 'status', '--porcelain'], tree):
                raise ValueError('Selected implementation worktree is dirty.')
            return tree
        tree = self.cards / f"card-{card['number']}"
        branch = f"card/{card['number']}"
        if not tree.exists():
            tree.parent.mkdir(parents=True, exist_ok=True)
            known = self.cmd(['git', 'branch', '--list', branch])
            if known:
                self.cmd(['git', 'worktree', 'add', tree, branch])
            else:
                remote = self.cmd(['git', 'ls-remote', '--heads', 'origin', branch])
                if remote:
                    self.cmd(['git', 'fetch', 'origin', f'{branch}:refs/heads/{branch}'])
                    self.cmd(['git', 'worktree', 'add', tree, branch])
                else:
                    self.cmd(['git', 'worktree', 'add', '-b', branch, tree, meta['base']])
        if self.cmd(['git', 'branch', '--show-current'], tree) != branch:
            raise ValueError(f'{tree} is not on {branch}')
        return tree

    def prepare(self, card, meta):
        tree = self.ensure_tree(card, meta)
        ctx = self.context(card, meta)
        out = Path(ctx['out'])
        base = out / 'base'
        if not (out / 'base-ready.json').exists():
            base.mkdir(parents=True, exist_ok=True)
            # Materialise exactly the released source at the recorded commit.
            files = self.cmd(['git', 'ls-tree', '-r', '--name-only', meta['base'], '--', 'mybot2']).splitlines()
            for name in files:
                rel = Path(name).relative_to('mybot2')
                dst = base / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(self.cmd(['git', 'show', f"{meta['base']}:{name}"], raw=True))
            if not (base / 'main.cpp').exists():
                raise ValueError('origin/main has no mybot2/main.cpp release source')
            write(out / 'base-ready.json', {'commit': meta['base']})
        stage(self.repo, tree, out, base)
        return ctx

    def job_notice(self, card, step, path, text, queue=None, resources=(), metadata=None):
        from late import check_late
        queued = [info['job'] for info in self.status.values()
                  if info.get('job') and not info.get('queue')]
        wait = remaining_wait(self.out, resources, queued) if queue else 0
        timing = step_timing(self.out, step, path, wait=wait, queue=queue)
        timing.update(check_late(self.out, self.locks, card, step, path,
                                 {**timing, 'name': card_name(card)}, resources, queued))
        self.notice(card, text, {**timing, 'job': str(path), **(metadata or {})})

    def running_notices(self):
        for file in self.out.glob('**/jobs/*/job.json'):
            if not (file.parent / 'done.json').exists() and busy(file.parent / 'lease'):
                spec = read(file)
                if self.status.get(str(spec['number']), {}).get('job') == str(file.parent):
                    continue
                card = {'number': spec['number'], 'title': spec['title'],
                        'labels': ['status:running'] + (['name:' + spec['name']] if spec.get('name') else [])}
                self.job_notice(card, spec['step'], file.parent, f"{spec['step']} running")

    def short_step_waiting(self, card):
        """Another card's short game step (from the last tick's status) goes before a long outcome run."""
        ai_free = 'ai' not in self.launched and not busy(self.locks / 'ai.lock')
        for number, info in (read(self.out / 'status.json', {}).get('cards') or {}).items():
            if number == str(card['number']) or not isinstance(info, dict) or 'batch' not in (info.get('queue') or ''):
                continue
            kind = info.get('step_kind')
            if kind == 'mechanism' or (kind in ('build', 'task', 'adopt') and ai_free):
                return True
        return False

    def job(self, card, meta, step, light=False, output=None):
        ctx = self.context(card, meta)
        path = Path(ctx['out']) / 'jobs' / step
        done = read(path / 'done.json')
        if done:
            if not done['ok']:
                raise RuntimeError(f"{step} failed: {done['error']} (remove this job's done.json after fixing the cause)")
            self.job_notice(card, step, path, f'{step} done')
            return True
        if busy(path / 'lease'):
            self.job_notice(card, step, path, f'{step} running')
            return False
        resources = ['batch'] if step in ('mechanism', 'outcome') else ['ai']
        if step in ('build', 'task', 'adopt'):
            resources.append('batch')
        if any(busy(self.locks / f'{r}.lock') for r in resources):
            self.job_notice(card, step, path, f'{step} waiting for {" + ".join(resources)} lock',
                            queue=' + '.join(resources) + ' lock', resources=resources)
            return False
        if step == 'outcome' and self.short_step_waiting(card):
            self.job_notice(card, step, path, 'outcome waiting for shorter steps first',
                            queue='batch lock', resources=resources)
            return False
        if 'batch' in resources:
            import shutil
            if shutil.disk_usage(self.out).free < 21 * 1024**3:
                self.job_notice(card, step, path, f'{step} waiting for 21 GB free disk space', queue='21 GB free disk space')
                return False
            processes = self.cmd(['ps', '-axo', 'command='])
            if any(re.search(r'(?:^|/|\s)(?:unswbc(?:-clean\.py)?\s+run|(?:ab3|ident)\.py\s)', line)
                   for line in processes.splitlines()):
                self.job_notice(card, step, path, f'{step} waiting for an existing local game batch', queue='existing local game batch', resources=['batch'])
                return False
        path.mkdir(parents=True, exist_ok=True)
        if not (path / 'job.json').exists():
            prompt = ''
            if step not in ('mechanism', 'outcome'):
                common = (HERE / 'prompts/common.md').read_text()
                prompt = Template(common + '\n' + (HERE / f'prompts/{step}.md').read_text()).substitute(ctx)
            (path / 'prompt.md').write_text(prompt)
            stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            write(path / 'job.json', {**ctx, 'step': step, 'kind': 'batch' if step in ('mechanism', 'outcome') else 'ai',
                                    'prompt': str(path / 'prompt.md'), 'log': str(self.out / f"card-{card['number']}" / f'{step}-{stamp}.jsonl'),
                                    'resources': resources, 'locks': str(self.locks), 'light': light, 'output': output,
                                    'started': time.time(), 'eta_minutes': eta_minutes(self.out, step),
                                    'game_env': self.args.game_env, 'impl_commit': meta.get('impl_commit'), 'task': is_task(card)})
        spec = read(path / 'job.json')
        spec.update(started=time.time(), eta_minutes=eta_minutes(self.out, step))
        write(path / 'job.json', spec)
        with (path / 'supervisor.log').open('a') as log_file:
            child = subprocess.Popen(['nice', '-n', '10', sys.executable, str(HERE / 'runner.py'), '--job', str(path)],
                                     stdin=subprocess.DEVNULL, stdout=log_file, stderr=log_file, start_new_session=True)
            self.children.append(child)
        # Reserve within this tick too: workers may not yet have acquired their locks.
        self.launched.update(resources)
        self.job_notice(card, step, path, f'started {step}', metadata={
            'attempt': meta.get('attempt', 0), 'base': meta['base'],
            'job': str(path), 'pid': child.pid})
        return False

    def available_job(self, card, meta, step, **kwargs):
        path = Path(self.context(card, meta)['out']) / 'jobs' / step
        required = {'batch'} if step in ('mechanism', 'outcome') else {'ai'}
        if step in ('build', 'task', 'adopt'):
            required.add('batch')
        if self.launched & required and not (path / 'done.json').exists():
            self.job_notice(card, step, path, f'{step} queued behind this tick’s job',
                            queue=' + '.join(sorted(self.launched & required)) + ' lock', resources=required)
            return False
        return self.job(card, meta, step, **kwargs)

    def new_attempt(self, card, meta, reason, **updates):
        meta = {'attempt': meta.get('attempt', 0) + 1, 'base': self.latest_base(),
                'reason': reason, 'seed0': 10000 + card['number'] * 100,
                **{k: meta[k] for k in ('ai_revisions', 'revision_evidence', 'impl_commit', 'impl_tree') if k in meta}, **updates}
        self.save(card, meta)
        self.notice(card, f"Building against main `{meta['base']}`. {reason}", metadata=meta)
        return meta

    def verdict_fields(self, card, meta, out):
        result = read(out / 'verdict.json') or meta.get('verdict')
        if result is None:
            for record in reversed(records(card)):
                if record.get('attempt') == meta.get('attempt') and record.get('verdict'):
                    result = record['verdict']
                    break
        if result is None:
            return None
        if not isinstance(result, dict):
            raise ValueError('verdict.json must contain an object')
        for key in ('identical_pairs', 'total_pairs'):
            if type(result.get(key)) is not int:
                raise ValueError(f'verdict.json needs integer {key}')
        if not 0 <= result['identical_pairs'] <= result['total_pairs'] or result['total_pairs'] <= 0:
            raise ValueError('verdict.json has invalid pair counts')
        if any(type(result.get(k)) is not bool for k in ('mechanism_shown', 'target_seen')):
            raise ValueError('verdict.json needs mechanism_shown and target_seen booleans')
        net = result.get('net', {})
        if (not isinstance(net, dict) or not {'held', 'old10'} <= net.keys()
                or any(type(n) is not int for n in net.values())):
            raise ValueError('verdict.json needs integer net per set, including held and old10')
        return result

    def legacy_pair_counts(self, out):
        """Recover old recorded-outcome identity without reading verdict prose."""
        identical = total = 0
        for name in ('held', 'transposed', 'old10'):
            rows = read(out / f'{name}.json')
            if not rows:
                return None
            paired = {}
            for row in rows:
                key = (row['map'], row['seed'], row['side'])
                tag = row['tag']
                if tag not in ('base', 'candidate') or tag in paired.setdefault(key, {}):
                    raise ValueError('duplicate or unknown legacy result row')
                paired[key][tag] = {k: v for k, v in row.items() if k != 'tag'}
            if any(set(pair) != {'base', 'candidate'} for pair in paired.values()):
                raise ValueError('incomplete legacy A/B pairs')
            total += len(paired)
            identical += sum(pair['base'] == pair['candidate'] for pair in paired.values())
        return {'identical_pairs': identical, 'total_pairs': total}

    def auto_decide(self, card, meta):
        if meta.get('force_override') or 'by:ai' not in labels(card) or is_task(card):
            return
        # Persist before posting so a crash cannot spend the revision twice.
        pending = meta.get('ai_pending')
        if pending:
            if pending['target'] is None and any(r.get('key') == pending['key'] for r in records(card)):
                self.notice(card, 'coin flip locally; waiting for a human')
            else:
                self.post(card, **pending, metadata=meta)
            return
        out = Path(self.context(card, meta)['out'])
        attempt = meta.get('attempt', 0)
        key = f'ai-decision-{attempt}'
        if any(r.get('key') == key for r in records(card)):
            self.notice(card, 'AI decision already posted; waiting for a human')
            return
        result = self.verdict_fields(card, meta, out)
        if result is None:
            # Legacy cards with overwhelmingly unchanged outcomes can revise now.
            counts = self.legacy_pair_counts(out)
            if counts and counts['identical_pairs'] / counts['total_pairs'] >= AI_IDENTICAL_RATIO:
                result = counts
            else:
                if not self.available_job(card, meta, 'verdict-fields'):
                    return
                result = self.verdict_fields(card, meta, out)
                if result is None:
                    raise ValueError('missing verdict.json after evidence recovery')
        barely = result['identical_pairs'] / result['total_pairs'] >= AI_IDENTICAL_RATIO
        if barely or result.get('target_seen') is False:
            reason = (f"{result['identical_pairs']}/{result['total_pairs']} pairs identical"
                      if barely else 'the target behaviour never appeared')
            if meta.get('ai_revisions', 0) < AI_MAX_REVISIONS:
                evidence = (out / 'verdict.md').read_text() if (out / 'verdict.md').exists() else ''
                if not evidence:
                    evidence = '\n'.join(c.get('body', '') for c in card.get('comments', [])
                                         if any(r.get('key') == f'tested-{attempt}'
                                                for r in records({'comments': [c]})))
                revised = dict(meta, ai_revisions=meta.get('ai_revisions', 0) + 1,
                               revision_evidence=json.dumps(result) + '\n' + evidence)
                target, close = 'building', False
                text = f"didn't fire: {reason}; revising once"
                meta = self.new_attempt(card, revised, text, phase='building',
                                        ai_pending={'key': key, 'text': text, 'target': target, 'close': close})
            else:
                target, close = 'inconclusive', True
                text = f"didn't fire again: {reason}; closing as inconclusive."
        else:
            net = result['net']
            unseen = sum(net.get(n, 0) for n in ('held', 'fresh', 'transposed'))
            if net['held'] <= -AI_NET_THRESHOLD or unseen <= -AI_NET_THRESHOLD:
                target, close = 'rejected', True
                text = f"Clearly worse: held-out net {net['held']:+d}, combined unseen {unseen:+d}; closing as rejected."
            elif (net['held'] >= AI_NET_THRESHOLD and result['mechanism_shown']
                  and net['old10'] >= -AI_NET_THRESHOLD):
                target, close = 'candidate', False
                text = (f"Clearly better: held-out net {net['held']:+d}, mechanism shown, old maps {net['old10']:+d}; "
                        'the loop prepares the candidate PR. One teammate OK is still needed to merge.')
            else:
                target, close = None, False
                text = AI_COIN_FLIP
        pending = {'key': key, 'text': text, 'target': target, 'close': close}
        meta['ai_pending'] = pending
        self.save(card, meta)
        self.post(card, **pending, metadata=meta)

    def process(self, card):
        pending = read(self.out / f"card-{card['number']}" / 'pending-post.json')
        if pending:
            if routine_post(pending['key']):
                self.notice(card, pending['text'], metadata=pending.get('metadata'))
                (self.out / f"card-{card['number']}" / 'pending-post.json').unlink()
            else:
                self.post(card, **pending)
                return
        s = state(card)
        meta = self.metadata(card)
        ctx = self.context(card, meta)
        out = Path(ctx['out'])
        if s == 'ready':
            # A failure marker invalidates all earlier completed step artifacts.
            if meta.get('failed'):
                meta = self.new_attempt(card, meta, 'Retry after the previous check failed.')
            if not meta.get('base'):
                meta = self.new_attempt(card, meta, 'First build for this card.')
            self.ensure_tree(card, meta)
            if is_task(card):
                self.transition(card, 'building')
                return
            if self.available_job(card, meta, 'clarify'):
                ctx = self.context(card, meta)
                decision = read(Path(ctx['out']) / 'clarify.json')
                if not isinstance(decision, dict) or not isinstance(decision.get('needs_info'), bool):
                    raise ValueError('clarify.json must contain needs_info: bool')
                if ('by:zhe' in labels(card) and not is_task(card)) or decision['needs_info']:
                    text = (Path(ctx['out']) / 'questions.md').read_text().strip()
                    if not text:
                        raise ValueError('missing clarification questions')
                    self.post(card, f"questions-{meta['attempt']}", text, target='needs-info', ask=True,
                              metadata={'attempt': meta['attempt'], 'phase': 'questions'})
                else:
                    self.transition(card, 'building')
        elif s == 'needs-info':
            questions = [c for c in card['comments'] if c['body'].startswith('Questions before we build') or
                         any(r.get('phase') == 'questions' for r in records({'comments': [c]}))]
            if not questions:
                self.notice(card, 'questions missing; clarify before waiting')
                if not meta.get('base'):
                    meta = self.new_attempt(card, meta, 'Recover the missing clarification.')
                self.ensure_tree(card, meta)
                if self.available_job(card, meta, 'clarify'):
                    text = (Path(self.context(card, meta)['out']) / 'questions.md').read_text()
                    self.post(card, f"questions-{meta['attempt']}", text, target='needs-info', ask=True,
                              metadata={'attempt': meta['attempt'], 'phase': 'questions'})
            elif human_replies(card, questions[-1].get('created_at', questions[-1].get('createdAt', '')), zhe='by:zhe' in labels(card)):
                self.transition(card, 'building')
            else:
                self.notice(card, 'waiting for a human answer')
        elif s == 'building':
            if meta.get('ai_pending', {}).get('target') == 'building':
                meta.pop('ai_pending')
                self.save(card, meta)
            if not meta.get('base'):
                meta = self.new_attempt(card, meta, 'Resuming from the building label.')
            # A human may manually request a revision using the label alone.
            if meta.get('failed') or meta.get('phase') in ('look', 'tested'):
                meta = self.new_attempt(card, meta, 'The card was returned to building for revision.')
            build_step = 'adopt' if meta.get('impl_commit') else 'task' if is_task(card) else 'build'
            if not (Path(self.context(card, meta)['out']) / f'jobs/{build_step}/job.json').exists():
                if self.base_moved(meta['base']):
                    meta = self.new_attempt(card, meta, 'Main changed while this card was waiting; use the current release.')
            ctx = self.prepare(card, meta)
            out = Path(ctx['out'])
            if is_task(card):
                self.build_task(card, meta, ctx)
                return
            try:
                if not self.available_job(card, meta, build_step):
                    return
            except RuntimeError as exc:
                meta['failed'] = True
                self.save(card, meta)
                self.post(card, f"build-failed-{meta['attempt']}",
                          'What we tried: Build this idea with its switch off first.\n'
                          f'Did it work: No; {str(exc)}.\nWho decides now: The loop retries from ready; the author can update the card.',
                          target='ready', metadata=meta)
                return
            built = read(out / 'built.json')
            if not built:
                raise ValueError('missing verified build')
            meta.update(commit=built['commit'], toggle=built['toggle'])
            self.save(card, meta)
            if not meta.get('pushed') and not meta.get('impl_commit'):
                self.cmd(['git', 'push', '--force', 'origin', f"{meta['commit']}:refs/heads/card/{card['number']}"], ctx['tree'])  # card/N is loop-owned; revisions rebuild it
                meta['pushed'] = True
                self.save(card, meta)
                self.notice(card,
                            f"The toggle-off check passed against `{meta['base']}`. Code: `{meta['commit']}`. Small replay check is next.",
                            metadata=meta)
            if not self.available_job(card, meta, 'mechanism'):
                return
            if not self.available_job(card, meta, 'look'):
                return
            picks = read(out / 'look.json')
            if not isinstance(picks, dict) or not 2 <= len(picks.get('replays', [])) <= 3 or not picks.get('note'):
                raise ValueError('look.json needs 2–3 replay paths and a note')
            for path in picks['replays']:
                p = Path(path).resolve()
                if not p.is_file() or not p.is_relative_to((out / 'replays').resolve()):
                    raise ValueError('look replay must exist in this attempt’s replay directory')
            write(self.out / f"card-{card['number']}" / 'look.json', picks)
            text = summary_text((out / 'look.md').read_text())
            text += '\n\nReplay files on this Mac:\n' + '\n'.join(f'- `{p}`' for p in picks['replays'])
            meta['phase'] = 'look'
            self.post(card, f"look-{meta['attempt']}", text, target='needs-look', kind='check', metadata=meta)
            self.save(card, meta)
        elif s == 'needs-look':
            if is_task(card):
                self.transition(card, 'building')
                return
            looks = [c for c in card['comments'] if any(r.get('phase') == 'look' for r in records({'comments': [c]}))]
            if not looks or not (out / 'look.json').exists():
                self.notice(card, 'missing replay evidence; return to building to regenerate it')
                self.transition(card, 'building')
                return
            if 'by:zhe' not in labels(card):
                self.transition(card, 'testing')
                return
            replies = human_replies(card, looks[-1].get('created_at', looks[-1].get('createdAt', '')), zhe=True)
            if not replies:
                self.notice(card, 'waiting for Zhe’s look reply')
                return
            response_id = digest(replies)
            # A new reply has its own light job; completed older classifications cannot be reused.
            light_meta = dict(meta, replies=replies)
            light_step = 'reply'
            response_dir = out / 'replies' / response_id
            response_dir.mkdir(parents=True, exist_ok=True)
            # Store latest replies in context; one classification per attempt, uncertain waits for a new reply.
            prev = read(out / 'reply-input.json')
            if prev != response_id:
                jobdir = out / 'jobs/reply'
                if busy(jobdir / 'lease'):
                    return
                if jobdir.exists():
                    jobdir.rename(out / 'replies' / f"job-{prev or time.time_ns()}")
                (out / 'reply.json').unlink(missing_ok=True)
                write(out / 'reply-input.json', response_id)
            if self.available_job(card, light_meta, light_step, light=True, output='reply.json'):
                answer = read(out / 'reply.json').get('decision')
                if answer == 'ok':
                    self.transition(card, 'testing')
                elif answer == 'revise':
                    self.new_attempt(card, meta, 'Zhe requested a revision; use the reply in the card comments.')
                    self.transition(card, 'building')
                else:
                    self.notice(card, 'reply does not clearly approve or request a revision; waiting')
        elif s == 'testing':
            if is_task(card):
                self.transition(card, 'building')
                return
            if not meta.get('commit') or not (out / 'build.json').exists():
                self.notice(card, 'test inputs missing; rebuild from the recorded card branch')
                self.transition(card, 'building')
                return
            job_started = (out / 'jobs/outcome/job.json').exists()
            latest = self.latest_base()
            if self.base_moved(meta['base']):
                if not job_started:
                    self.new_attempt(card, meta, 'Main changed before testing; rebuild and check identity against the new release.')
                    self.transition(card, 'building')
                    return
                self.post(card, f"old-base-{meta['attempt']}",
                          f"These results use old base `{meta['base']}`; main is now `{latest}`. Refresh before shipping.")
                meta['old_base'] = True
                self.save(card, meta)
            if not self.available_job(card, meta, 'outcome'):
                return
            if not self.available_job(card, meta, 'verdict'):
                return
            text = summary_text((out / 'verdict.md').read_text())
            if meta.get('old_base'):
                text += f"\n\n**old base**: tested `{meta['base']}`, current main `{latest}`. Refresh before shipping."
            text += f"\n\nTested base: `{meta['base']}`; candidate: `{meta['commit']}`; switch: `{meta['toggle']}=true`; SEED0={ctx['seed0']}."
            if 'by:ai' in labels(card):
                result = self.verdict_fields(card, meta, out)
                if result is not None:
                    meta['verdict'] = result
            meta['phase'] = 'tested'
            self.save(card, meta)
            self.post(card, f"tested-{meta['attempt']}", text, target='tested', kind='test', metadata=meta)
            self.auto_decide(card, meta)
        elif s == 'tested':
            if not self.human_decision(card, meta, out):
                self.auto_decide(card, meta)
        elif s in ('rejected', 'inconclusive'):
            if meta.get('ai_pending', {}).get('close'):
                self.post(card, **meta['ai_pending'], metadata=meta)
        elif s == 'candidate':
            self.candidate(card, meta)

    def human_decision(self, card, meta, out):
        """A reply after the results (/answer or a GitHub comment) is the decision. True once a reply is being handled."""
        results = [c for c in card['comments'] if any(r.get('phase') == 'tested' for r in records({'comments': [c]}))]
        if not results:
            return False
        after = results[-1].get('created_at', results[-1].get('createdAt', ''))
        replies = human_replies(card, after, zhe='by:zhe' in labels(card))
        if not replies:
            return False
        response_id = digest(replies)
        (out / 'decisions').mkdir(parents=True, exist_ok=True)
        if read(out / 'decide-input.json') != response_id:
            jobdir = out / 'jobs/decide'
            if busy(jobdir / 'lease'):
                return True
            if jobdir.exists():
                jobdir.rename(out / 'decisions' / f"job-{time.time_ns()}")
            (out / 'decide.json').unlink(missing_ok=True)
            write(out / 'decide-input.json', response_id)
        if not self.available_job(card, dict(meta, replies=replies), 'decide', light=True, output='decide.json'):
            return True
        answer = (read(out / 'decide.json') or {}).get('decision')
        if answer in ('candidate', 'rejected', 'inconclusive'):
            self.transition(card, answer)
        elif answer == 'revise':
            self.new_attempt(card, meta, 'The author asked for a revision after the results; use the reply in the card comments.')
            self.transition(card, 'building')
        else:
            self.notice(card, 'reply after the results is not a clear decision; waiting')
            return False  # AI cards still decide themselves
        return True

    def build_task(self, card, meta, ctx):
        out = Path(ctx['out'])
        try:
            if not self.available_job(card, meta, 'adopt' if meta.get('impl_commit') else 'task'):
                return
        except RuntimeError as exc:
            meta['failed'] = True
            self.save(card, meta)
            note = ('this changes play; make it an idea card or fix it'
                    if 'identity failed' in str(exc) else str(exc))
            self.post(card, f"task-failed-{meta['attempt']}",
                      f"What we tried: {card_ref(card)}.\nDid it work: No; {note}.\n"
                      'Who decides now: The author can update the card; the loop retries from ready.',
                      target='ready', kind='check', metadata=meta)
            return
        task = read(out / 'task.json')
        if task.get('needs_info'):
            text = (out / 'questions.md').read_text().strip()
            if not text.startswith('Questions before we build'):
                raise ValueError('missing task clarification questions')
            # Answers must get a fresh implementation job, not reuse this completed one.
            meta['failed'] = True
            self.save(card, meta)
            self.post(card, f"questions-{meta['attempt']}", text, target='needs-info', ask=True,
                      metadata=meta)
            return
        built = read(out / 'built.json')
        if not built or built.get('task_check', {}).get('passed') is not True:
            raise ValueError('missing verified task build and task-specific check')
        meta.update(commit=built['commit'], phase='tested', task=True,
                    old_base=self.base_moved(meta['base']))
        self.save(card, meta)
        if not meta.get('pushed') and not meta.get('impl_commit'):
            self.cmd(['git', 'push', '--force', 'origin', f"{meta['commit']}:refs/heads/card/{card['number']}"], ctx['tree'])  # card/N is loop-owned; revisions rebuild it
            meta['pushed'] = True
            self.save(card, meta)
        check = built['task_check']
        comparison = ('the recorded old base' if meta.get('old_base')
                      else 'the current base (latest main release)')
        text = (f"What we tried: {card_ref(card)}.\n"
                f"Did it work: Yes; play stayed replay-identical to {comparison} and {check['note']}.\n"
                'Who decides now: The author chooses candidate, rejected, or inconclusive.\n\n'
                + ('Old base: main changed during these checks; refresh before shipping.\n'
                   if meta.get('old_base') else '')
                + f"Base: `{meta['base']}`; implementation: `{meta['commit']}`.\n"
                f"Identity: old 10 maps × 2 seeds, both sides; 40 OK comparisons. Log: `{out / 'ident.log'}`.\n"
                f"Task-specific check: `{json.dumps(task['check'])}`; log: `{out / 'task-check.log'}`.\n"
                f"Check evidence: `{json.dumps(check, ensure_ascii=False)}`.")
        self.post(card, f"task-tested-{meta['attempt']}", text, target='tested', kind='check', metadata=meta)

    def candidate(self, card, meta):
        if dt.datetime.now(KST) >= FREEZE and not meta.get('force_override'):
            self.notice(card, 'freeze: no candidate branch or PR creation')
            return
        if meta.get('phase') != 'tested' or not meta.get('commit'):
            self.notice(card, 'candidate needs recorded test evidence first')
            return
        if (self.base_moved(meta['base']) or meta.get('old_base')) and not meta.get('force_override'):
            self.notice(card, 'old base: fresh tests are required before preparing a candidate')
            return
        version = f"card-{card['number']}-{meta['commit'][:10]}"
        branch = f'candidate/{version}'
        existing = self.gh('pr', 'list', '--repo', GH_REPO, '--head', branch, '--state', 'all', '--json', 'number,url')
        if existing:
            self.notice(card, f"candidate PR already exists: {existing[0]['url']}")
            return
        out = Path(self.context(card, meta)['out'])
        source = ''
        count = 1
        if not is_task(card) and meta.get('toggle'):
            source = self.cmd(['git', 'show', f"{meta['commit']}:mybot2/main.cpp"])
            source, count = re.subn(rf"(constexpr bool {meta['toggle']} = )false;", r'\g<1>true;', source)
        if count != 1:
            raise ValueError('candidate switch not found exactly once')
        manifest = {'version': version, 'workflow': 3 if 'by:ai' in labels(card) else 1 if 'by:zhe' in labels(card) else 2,
                    'changes': [card['title']], 'results': {'held': 'Not run for task cards.' if is_task(card) else 'See linked issue for paired results.',
                    'main': 'Old 10 maps ×2 seeds; replay-identical.' if is_task(card) else 'Old 10 maps ×8; see linked issue.',
                    'mechanism': (read(out / 'built.json', {}).get('task_check') or {}).get('note', 'Checks skipped by Force.') if is_task(card) else read(out / 'look.json', {}).get('note', 'Checks skipped by Force.'),
                    'cpu': 'Not separately measured; no release approval implied.'},
                    'bot_dir': 'mybot2', 'issues': [card['number']], 'pr': None,
                    'base_commit': meta['base'], 'candidate_commit': meta['commit']}
        if meta.get('force_override'):
            manifest['results'] = {k: 'Forced: checks may be skipped or use an old base; see issue audit.'
                                   for k in ('held', 'main', 'mechanism', 'cpu')}
        # Git data API creates the candidate branch without a second git-push target.
        payload = {'base_tree': self.gh('api', f"repos/{GH_REPO}/git/commits/{meta['commit']}")['tree']['sha'],
                   'tree': [{'path': 'mybot2/main.cpp', 'mode': '100644', 'type': 'blob', 'content': source + '\n'},
                            {'path': f'candidates/{version}.json', 'mode': '100644', 'type': 'blob',
                             'content': json.dumps(manifest, indent=2) + '\n'}]}
        if is_task(card) or not meta.get('toggle'):
            payload['tree'] = payload['tree'][1:]
        remote = self.gh('api', f'repos/{GH_REPO}/git/matching-refs/heads/{branch}')
        remote = [r for r in remote if r['ref'] == f'refs/heads/{branch}']
        if not remote:
            tree = self.gh('api', f'repos/{GH_REPO}/git/trees', payload=payload)
            commit = self.gh('api', f'repos/{GH_REPO}/git/commits', payload={
                'message': f'Prepare candidate {version}', 'tree': tree['sha'], 'parents': [meta['commit']]})
            if dt.datetime.now(KST) >= FREEZE and not meta.get('force_override'):
                self.notice(card, 'freeze reached; candidate publication stopped')
                return
            self.gh('api', f'repos/{GH_REPO}/git/refs', payload={'ref': f'refs/heads/{branch}', 'sha': commit['sha']})
        body = out / 'candidate-pr.md'
        body.write_text(f'Card: [{card_ref(card)}](https://github.com/{GH_REPO}/issues/{card["number"]})\n\n'
                        f'What we tried: {card_ref(card)}.\nDid it work: See the measured results in {card_ref(card)}.\n'
                        f'Who decides now: The author and required teammate approvers review this revision.\n\n'
                        + ('Checks overridden by a member; see the audit below. ' if meta.get('force_override') else 'Task preserves play against the current base (latest main release). ' if is_task(card) else f'Enables `{meta.get("toggle", "selected implementation")}`. ')
                        + f'Base `{meta["base"]}`; implementation `{meta["commit"]}`.\n'
                        f'Results and optional smoke request: {card_ref(card)}. No upload is performed by this runner.\n'
                        + ('\n' + meta['force_reason'] if meta.get('force_override') else ''))
        if dt.datetime.now(KST) < FREEZE or meta.get('force_override'):
            url = self.cmd(['gh', 'pr', 'create', '--repo', GH_REPO, '--base', 'main', '--head', branch,
                            '--title', f'Candidate {card_ref(card)}', '--body-file', body])
            self.post(card, f'candidate-{version}', f'The candidate is ready for human review: {url}')

    def dry(self, card):
        s = state(card)
        meta = self.metadata(card)
        if is_task(card) and s == 'ready':
            action = 'building (task; questions only if unclear)'
        elif is_task(card) and s in ('building', 'needs-look', 'testing'):
            action = 'task implementation + old10 ×2 identity + task-specific check → tested (no A/B)'
        elif s == 'ready':
            action = 'clarify → ask (always for Zhe; otherwise if unclear) or building'
        elif s == 'needs-info':
            q = [c for c in card['comments'] if c['body'].startswith('Questions before we build')]
            action = 'wait for human answer after questions'
            if not q:
                action = 'clarify and ask missing questions'
            elif human_replies(card, q[-1].get('created_at', q[-1].get('createdAt', '')), zhe='by:zhe' in labels(card)):
                action = 'human answer found → building'
        elif s == 'building':
            action = 'resume build + identity → push card/N → mechanism batch (KEEP=1) → look → needs-look'
        elif s == 'needs-look':
            action = 'wait/classify Zhe reply (ok / revise)' if 'by:zhe' in labels(card) else 'auto-pass → testing'
        elif s == 'tested':
            action = 'apply AI verdict thresholds; revise once, close, candidate, or wait for online pair test'
        elif s in ('rejected', 'inconclusive'):
            action = 'recover pending AI closure if needed'
        elif s == 'testing':
            action = f'resume outcome ab3: held ×2, _T ×2, old10 ×8; WORKERS=6 KEEP off SEED0={10000 + card["number"] * 100} → verdict → tested'
        else:
            action = 'freeze: block candidate' if dt.datetime.now(KST) >= FREEZE else 'verify current-base evidence → candidate branch and PR (author already selected candidate)'
        self.notice(card, action)

    def cards_busy(self):
        return bool(self.launched or busy(self.locks / 'batch.lock')
                    or any(info.get('queue') for info in self.status.values()))

    def ladder(self):
        cached = read(self.out / 'ladder.json', {})
        if time.time() - cached.get('checked', 0) < 4 * 3600:
            return
        if self.args.dry_run:
            print('Track 3: due; would read battles, skip AI without new completed games (no online calls in dry-run)')
            return
        if 'ai' in self.launched or busy(self.locks / 'ai.lock'):
            return
        pending = cached.get('pending')
        path = self.out / 'card-0' / f"attempt-{pending['batch']}" / 'jobs' / 'ladder' if pending else None
        # Cards come first: a review only starts when nothing is running or queued.
        if not (path and (path / 'job.json').exists()) and self.cards_busy():
            return
        if not pending:
            battles = json.loads(self.cmd(['node', SWARM / 'tools/online.js', 'battles', '--json']))
            # Ranked games only; our own test battles are reviewed by the pair reports.
            ranked = [b for b in battles if b.get('at') and not b.get('wait') and b.get('ranked')]
            new = sorted(str(b['id']) for b in ranked if str(b['id']) not in cached.get('seen', []))
            if not new:
                write(self.out / 'ladder.json', {**cached, 'checked': time.time()})
                return
            pending = {'ids': new, 'batch': int(time.time()), 'battles': [b for b in ranked if str(b['id']) in new]}
            cached['pending'] = pending
            write(self.out / 'ladder.json', cached)
        elif not (read(path / 'done.json') or {'ok': True})['ok']:
            # A failed or timed-out review is dropped; the next one takes newer games.
            print(f"Track 3: review {pending['batch']} failed, skipping its games", flush=True)
            write(self.out / 'ladder.json', {'checked': time.time(), 'seen': sorted(set(cached.get('seen', []) + pending['ids']))})
            return
        card = {'number': 0, 'title': '[Idea] Ladder review', 'body': json.dumps(pending), 'comments': [],
                'labels': [{'name': 'by:ai'}, {'name': 'status:ready'}]}
        meta = {'attempt': pending['batch'], 'base': self.latest_base()}
        self.ensure_tree(card, meta)
        if not self.available_job(card, meta, 'ladder'):
            return
        out = Path(self.context(card, meta)['out'])
        proposals = read(out / 'ladder.json')
        if not isinstance(proposals, list) or len(proposals) > 2:
            raise ValueError('ladder must return at most two cards')
        open_cards = self.gh('issue', 'list', '--repo', GH_REPO, '--state', 'open', '--limit', '1000',
                             '--json', 'number,title,labels') or []
        used = {card_name(c) for c in open_cards}
        for i, proposal in enumerate(proposals):
            key = f"ladder-{pending['batch']}-{i}"
            # Search all issues to avoid duplicates if killed just after issue creation.
            found = self.gh('issue', 'list', '--repo', GH_REPO, '--state', 'all', '--search', f'"{key}" in:body', '--json', 'number')
            if found:
                continue
            fields = ('Area', 'Claim', 'Evidence', 'Expected signal', "What would show it's wrong")
            if any(not proposal.get(f) for f in (*fields, 'title')):
                raise ValueError('ladder card missing Idea template fields')
            if not valid_slug(proposal.get('slug')):
                raise ValueError('ladder card slug must be 1–2 lowercase words, at most 16 characters')
            slug = unique_slug(proposal['title'], used, proposal['slug'])
            used.add(slug)
            label = 'name:' + slug
            existing = self.gh('label', 'list', '--repo', GH_REPO, '--search', label, '--limit', '1000', '--json', 'name') or []
            if not any(row['name'] == label for row in existing):
                self.cmd(['gh', 'label', 'create', label, '--repo', GH_REPO, '--color', 'bfd4f2', '--description', 'Short card name'])
            lines = summary_text(proposal['summary']).splitlines()
            lines[2] = PREFIXES[2] + AI_DECISION
            text = '\n'.join(lines) + '\n\n### Idea by\nAI\n\n'
            text += '\n\n'.join(f'### {f}\n{proposal[f]}' for f in fields)
            text += f'\n\n<!-- {key} -->\n'
            path = out / f'idea-{i}.md'
            path.write_text(text)
            self.cmd(['gh', 'issue', 'create', '--repo', GH_REPO, '--title', idea_title(proposal['title']),
                      '--body-file', path, '--label', 'by:ai', '--label', 'status:ready', '--label', 'wf:3', '--label', label])
        write(self.out / 'ladder.json', {'checked': time.time(), 'seen': sorted(set(cached.get('seen', []) + pending['ids']))})

    def tick(self):
        self.launched = set()
        self.status = {}
        from meow_control import controls
        if controls(self):
            self.running_notices()
            write(self.out / 'status.json', {'updated': dt.datetime.now(KST).isoformat(), 'paused': True,
                                           'cards': self.status,
                                           'message': 'Paused by a member; running jobs finish normally.'})
            return
        pending_cards = self.cards_on_board()
        while pending_cards:
            card = order_cards(pending_cards, read_fair(self.fair_path))[0]
            pending_cards.remove(card)
            try:
                if self.args.dry_run:
                    self.dry(card)
                else:
                    self.process(card)
            except Exception as exc:
                self.notice(card, f'needs attention: {exc}')
        try:
            self.ladder()
        except Exception as exc:
            self.status['ladder'] = {'error': str(exc)}
            print(f'Track 3: {exc}', flush=True)
        if not self.args.dry_run:
            self.running_notices()
            snapshot = {'updated': dt.datetime.now(KST).isoformat(), 'loop': 'card-loop', 'cards': self.status,
                        'batch_running': busy(self.locks / 'batch.lock'), 'ai_running': busy(self.locks / 'ai.lock')}
            write(self.out / 'status.json', snapshot)
            active = bool(snapshot['batch_running'] or snapshot['ai_running'] or self.launched)
            self.board('heartbeat', '--state', 'running' if active else 'idle', '--step',
                       f"{len(self.status)} active cards; batch={snapshot['batch_running']}, AI={snapshot['ai_running']}"
                       + ''.join(f"; {info.get('title', number)}: {info.get('step', info.get('error', ''))}"
                                 for number, info in self.status.items()))
        self.children = [p for p in self.children if p.poll() is None]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--repo', default=str(REPO))
    ap.add_argument('--out', default='~/meow-loop-out')
    ap.add_argument('--cards', default='~/meow-cards')
    ap.add_argument('--job', help=argparse.SUPPRESS)
    ap.add_argument('--board-base', help=argparse.SUPPRESS)
    ap.add_argument('--board-args', help=argparse.SUPPRESS)
    ap.add_argument('--game-env', action='append', default=[], metavar='KEY=VALUE', help='explicit local engine environment')
    a = ap.parse_args()
    if a.board_base:
        if not re.fullmatch(r'[0-9a-f]{40}', a.board_base):
            ap.error('invalid recorded base commit')
        from jobs import load_module
        board = load_module('loop_board', Path(a.repo) / 'work/board.py')
        board.base_commit = lambda: a.board_base
        sys.argv = ['board.py', *json.loads(a.board_args)]
        board.main()
        return
    a.game_env = dict(x.split('=', 1) for x in a.game_env)
    if set(a.game_env) - {'PATH', 'NOSANDBOX'}:
        ap.error('--game-env only accepts PATH or NOSANDBOX; pairing settings are fixed')
    if a.job:
        worker(a.job)
        return
    loop = Loop(a)
    if a.dry_run:
        loop.tick()
        return
    with lock(loop.locks / 'runner.lock') as fd:
        if fd is None:
            sys.exit('card-loop is already running on this Mac')
        while True:
            try:
                loop.tick()
            except Exception as exc:
                write(loop.out / 'status.json', {'updated': time.time(), 'error': str(exc)})
                print(f'poll failed: {exc}', file=sys.stderr, flush=True)
            if a.once:
                break
            time.sleep(180)


if __name__ == '__main__':
    main()
