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

from jobs import OLD_MAPS, busy, lock, read, stage, worker, write

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


def priority(card):
    names = labels(card)
    return (0 if 'type:task' in names else 1 if 'by:zhe' in names else 3 if 'by:ai' in names else 2,
            card.get('createdAt', ''), card['number'])


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
            if state(card) not in ACTIVE:
                continue
            pages = self.gh('api', f"repos/{GH_REPO}/issues/{card['number']}/comments", '--paginate', '--slurp')
            card['comments'] = [c for page in pages for c in page]
            cards.append(card)
        return sorted(cards, key=priority)

    def notice(self, card, text, metadata=None):
        key = str(card['number'])
        self.status[key] = {**(metadata or {}), 'state': state(card), 'step': text}
        print(f"#{key} [{state(card)}] {text}", flush=True)

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

    def post(self, card, key, text, target=None, kind=None, ask=False, metadata=None):
        """A remote marker repairs a crash between comment creation and label replacement."""
        marker = {'key': key, **(metadata or {})}
        if not ask and not text.startswith(PREFIXES[0]):
            text = ("What we tried: Move this card's next step forward.\n"
                    f"Did it work: {text}\nWho decides now: "
                    + ('The author and required teammate approvers review the PR.' if key.startswith('candidate-')
                       else 'The loop continues; people decide acceptance.'))
        pending = self.out / f"card-{card['number']}" / 'pending-post.json'
        write(pending, {'key': key, 'text': text, 'target': target, 'kind': kind, 'ask': ask, 'metadata': metadata})
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
        pending.unlink(missing_ok=True)

    def latest_base(self):
        self.cmd(['git', 'fetch', 'origin', 'main'])
        return self.cmd(['git', 'rev-parse', 'origin/main'])

    def metadata(self, card):
        local = read(self.out / f"card-{card['number']}" / 'card.json', {})
        for r in records(card):
            if 'attempt' in r and (not local or r['attempt'] >= local.get('attempt', 0)):
                local = {**local, **r}
        return local

    def save(self, card, meta):
        write(self.out / f"card-{card['number']}" / 'card.json', meta)

    def context(self, card, meta):
        out = self.out / f"card-{card['number']}" / f"attempt-{meta.get('attempt', 0)}"
        return {'number': card['number'], 'title': card['title'], 'body': card.get('body', ''),
                'comments': json.dumps(card.get('comments', []), ensure_ascii=False),
                'base': meta.get('base', 'not selected yet'), 'repo': str(self.repo),
                'tree': str(self.cards / f"card-{card['number']}"), 'out': str(out),
                'card_out': str(self.out / f"card-{card['number']}"),
                'sandbox': str(out / 'harness'), 'old_maps': OLD_MAPS,
                'swarm': str(SWARM), 'seed0': 10000 + card['number'] * 100,
                'metadata': json.dumps(meta, ensure_ascii=False)}

    def ensure_tree(self, card, meta):
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

    def job(self, card, meta, step, light=False, output=None):
        ctx = self.context(card, meta)
        path = Path(ctx['out']) / 'jobs' / step
        done = read(path / 'done.json')
        if done:
            if not done['ok']:
                raise RuntimeError(f"{step} failed: {done['error']} (remove this job's done.json after fixing the cause)")
            self.notice(card, f'{step} done')
            return True
        if busy(path / 'lease'):
            self.notice(card, f'{step} running')
            return False
        resources = ['batch'] if step in ('mechanism', 'outcome') else ['ai']
        if step in ('build', 'task'):
            resources.append('batch')
        if any(busy(self.locks / f'{r}.lock') for r in resources):
            self.notice(card, f'{step} waiting for {" + ".join(resources)} lock')
            return False
        if 'batch' in resources:
            processes = self.cmd(['ps', '-axo', 'command='])
            if any(re.search(r'(?:^|/|\s)(?:unswbc(?:-clean\.py)?\s+run|(?:ab3|ident)\.py\s)', line)
                   for line in processes.splitlines()):
                self.notice(card, f'{step} waiting for an existing local game batch')
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
                                    'game_env': self.args.game_env})
        with (path / 'supervisor.log').open('a') as log_file:
            child = subprocess.Popen([sys.executable, str(HERE / 'runner.py'), '--job', str(path)],
                                     stdin=subprocess.DEVNULL, stdout=log_file, stderr=log_file, start_new_session=True)
            self.children.append(child)
        # Reserve within this tick too: workers may not yet have acquired their locks.
        self.launched.update(resources)
        self.notice(card, f'started {step}', metadata={
            'attempt': meta.get('attempt', 0), 'base': meta['base'],
            'job': str(path), 'pid': child.pid})
        return False

    def available_job(self, card, meta, step, **kwargs):
        path = Path(self.context(card, meta)['out']) / 'jobs' / step
        required = {'batch'} if step in ('mechanism', 'outcome') else {'ai'}
        if step in ('build', 'task'):
            required.add('batch')
        if self.launched & required and not (path / 'done.json').exists():
            self.notice(card, f'{step} queued behind this tick’s job')
            return False
        return self.job(card, meta, step, **kwargs)

    def new_attempt(self, card, meta, reason):
        meta = {'attempt': meta.get('attempt', 0) + 1, 'base': self.latest_base(),
                'reason': reason, 'seed0': 10000 + card['number'] * 100}
        self.save(card, meta)
        self.notice(card, f"Building against main `{meta['base']}`. {reason}", metadata=meta)
        return meta

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
            if not meta.get('base'):
                meta = self.new_attempt(card, meta, 'Resuming from the building label.')
            # A human may manually request a revision using the label alone.
            if meta.get('failed') or meta.get('phase') in ('look', 'tested'):
                meta = self.new_attempt(card, meta, 'The card was returned to building for revision.')
            build_step = 'task' if is_task(card) else 'build'
            if not (Path(self.context(card, meta)['out']) / f'jobs/{build_step}/job.json').exists():
                if self.latest_base() != meta['base']:
                    meta = self.new_attempt(card, meta, 'Main changed while this card was waiting; use the current release.')
            ctx = self.prepare(card, meta)
            out = Path(ctx['out'])
            if is_task(card):
                self.build_task(card, meta, ctx)
                return
            try:
                if not self.available_job(card, meta, 'build'):
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
            if not meta.get('pushed'):
                self.cmd(['git', 'push', 'origin', f"{meta['commit']}:refs/heads/card/{card['number']}"], ctx['tree'])
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
            if latest != meta['base']:
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
            meta['phase'] = 'tested'
            self.save(card, meta)
            self.post(card, f"tested-{meta['attempt']}", text, target='tested', kind='test', metadata=meta)
        elif s == 'candidate':
            self.candidate(card, meta)

    def build_task(self, card, meta, ctx):
        out = Path(ctx['out'])
        try:
            if not self.available_job(card, meta, 'task'):
                return
        except RuntimeError as exc:
            meta['failed'] = True
            self.save(card, meta)
            note = ('this changes play; make it an idea card or fix it'
                    if 'identity failed' in str(exc) else str(exc))
            self.post(card, f"task-failed-{meta['attempt']}",
                      f"What we tried: {card['title']}.\nDid it work: No; {note}.\n"
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
                    old_base=self.latest_base() != meta['base'])
        self.save(card, meta)
        if not meta.get('pushed'):
            self.cmd(['git', 'push', 'origin', f"{meta['commit']}:refs/heads/card/{card['number']}"], ctx['tree'])
            meta['pushed'] = True
            self.save(card, meta)
        check = built['task_check']
        comparison = ('the recorded old base' if meta.get('old_base')
                      else 'the current base (latest main release)')
        text = (f"What we tried: {card['title']}.\n"
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
        if dt.datetime.now(KST) >= FREEZE:
            self.notice(card, 'freeze: no candidate branch or PR creation')
            return
        if meta.get('phase') != 'tested' or not meta.get('commit'):
            self.notice(card, 'candidate needs recorded test evidence first')
            return
        if self.latest_base() != meta['base'] or meta.get('old_base'):
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
        if not is_task(card):
            source = self.cmd(['git', 'show', f"{meta['commit']}:mybot2/main.cpp"])
            source, count = re.subn(rf"(constexpr bool {meta['toggle']} = )false;", r'\g<1>true;', source)
        if count != 1:
            raise ValueError('candidate switch not found exactly once')
        manifest = {'version': version, 'workflow': 3 if 'by:ai' in labels(card) else 1 if 'by:zhe' in labels(card) else 2,
                    'changes': [card['title']], 'results': {'held': 'Not run for task cards.' if is_task(card) else 'See linked issue for paired results.',
                    'main': 'Old 10 maps ×2 seeds; replay-identical.' if is_task(card) else 'Old 10 maps ×8; see linked issue.',
                    'mechanism': read(out / 'built.json')['task_check']['note'] if is_task(card) else read(out / 'look.json')['note'],
                    'cpu': 'Not separately measured; no release approval implied.'},
                    'bot_dir': 'mybot2', 'issues': [card['number']], 'pr': None,
                    'base_commit': meta['base'], 'candidate_commit': meta['commit']}
        # Git data API creates the candidate branch without a second git-push target.
        payload = {'base_tree': self.gh('api', f"repos/{GH_REPO}/git/commits/{meta['commit']}")['tree']['sha'],
                   'tree': [{'path': 'mybot2/main.cpp', 'mode': '100644', 'type': 'blob', 'content': source + '\n'},
                            {'path': f'candidates/{version}.json', 'mode': '100644', 'type': 'blob',
                             'content': json.dumps(manifest, indent=2) + '\n'}]}
        if is_task(card):
            payload['tree'] = payload['tree'][1:]
        remote = self.gh('api', f'repos/{GH_REPO}/git/matching-refs/heads/{branch}')
        remote = [r for r in remote if r['ref'] == f'refs/heads/{branch}']
        if not remote:
            tree = self.gh('api', f'repos/{GH_REPO}/git/trees', payload=payload)
            commit = self.gh('api', f'repos/{GH_REPO}/git/commits', payload={
                'message': f'Prepare candidate {version}', 'tree': tree['sha'], 'parents': [meta['commit']]})
            if dt.datetime.now(KST) >= FREEZE:
                self.notice(card, 'freeze reached; candidate publication stopped')
                return
            self.gh('api', f'repos/{GH_REPO}/git/refs', payload={'ref': f'refs/heads/{branch}', 'sha': commit['sha']})
        body = out / 'candidate-pr.md'
        body.write_text(f'What we tried: {card["title"]}.\nDid it work: See the measured results in #{card["number"]}.\n'
                        f'Who decides now: The author and required teammate approvers review this revision.\n\n'
                        + ('Task preserves play against the current base (latest main release). ' if is_task(card) else f'Enables `{meta["toggle"]}`. ')
                        + f'Base `{meta["base"]}`; implementation `{meta["commit"]}`.\n'
                        f'Results and optional smoke request: #{card["number"]}. No upload is performed by this runner.\n')
        if dt.datetime.now(KST) < FREEZE:
            url = self.cmd(['gh', 'pr', 'create', '--repo', GH_REPO, '--base', 'main', '--head', branch,
                            '--title', f'Candidate {version}', '--body-file', body])
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
        elif s == 'testing':
            action = f'resume outcome ab3: held ×2, _T ×2, old10 ×8; WORKERS=8 KEEP off SEED0={10000 + card["number"] * 100} → verdict → tested'
        else:
            action = 'freeze: block candidate' if dt.datetime.now(KST) >= FREEZE else 'verify current-base evidence → candidate branch and PR (author already selected candidate)'
        self.notice(card, action)

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
        if not pending:
            battles = json.loads(self.cmd(['node', SWARM / 'tools/online.js', 'battles', '--json']))
            ids = sorted(str(b['id']) for b in battles if b.get('at') and not b.get('wait'))
            new = [i for i in ids if i not in cached.get('seen', [])]
            if not new:
                write(self.out / 'ladder.json', {**cached, 'checked': time.time()})
                return
            pending = {'ids': new, 'batch': int(time.time()), 'battles': battles}
            cached['pending'] = pending
            write(self.out / 'ladder.json', cached)
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
        for i, proposal in enumerate(proposals):
            key = f"ladder-{pending['batch']}-{i}"
            # Search all issues to avoid duplicates if killed just after issue creation.
            found = self.gh('issue', 'list', '--repo', GH_REPO, '--state', 'all', '--search', f'"{key}" in:body', '--json', 'number')
            if found:
                continue
            fields = ('Area', 'Claim', 'Evidence', 'Expected signal', "What would show it's wrong")
            if any(not proposal.get(f) for f in (*fields, 'title')):
                raise ValueError('ladder card missing Idea template fields')
            lines = summary_text(proposal['summary']).splitlines()
            lines[2] = PREFIXES[2] + AI_DECISION
            text = '\n'.join(lines) + '\n\n### Idea by\nAI\n\n'
            text += '\n\n'.join(f'### {f}\n{proposal[f]}' for f in fields)
            text += f'\n\n<!-- {key} -->\n'
            path = out / f'idea-{i}.md'
            path.write_text(text)
            self.cmd(['gh', 'issue', 'create', '--repo', GH_REPO, '--title', idea_title(proposal['title']),
                      '--body-file', path, '--label', 'by:ai', '--label', 'status:ready', '--label', 'wf:3'])
        write(self.out / 'ladder.json', {'checked': time.time(), 'seen': sorted(set(cached.get('seen', []) + pending['ids']))})

    def tick(self):
        self.launched = set()
        self.status = {}
        for card in self.cards_on_board():
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
            snapshot = {'updated': dt.datetime.now(KST).isoformat(), 'loop': 'card-loop', 'cards': self.status,
                        'batch_running': busy(self.locks / 'batch.lock'), 'ai_running': busy(self.locks / 'ai.lock')}
            write(self.out / 'status.json', snapshot)
            active = bool(snapshot['batch_running'] or snapshot['ai_running'] or self.launched)
            self.board('heartbeat', '--state', 'running' if active else 'idle', '--step',
                       f"{len(self.status)} active cards; batch={snapshot['batch_running']}, AI={snapshot['ai_running']}"
                       + ''.join(f"; #{number}: {info.get('step', info.get('error', ''))}"
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
