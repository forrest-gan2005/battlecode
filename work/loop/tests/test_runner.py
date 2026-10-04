"""Offline regression checks. Never invokes real AI, games, git writes or GitHub writes."""
import argparse
import contextlib
import datetime
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import guard
import jobs
import runner


def card(n=1, status='ready', by='junsing', comments=None):
    return {'number': n, 'title': '[Idea] Test a general behaviour', 'body': 'A hypothesis',
            'createdAt': '2026-10-01T00:00:00Z', 'author': {'login': 'zhex0121' if by == 'zhe' else 'human'},
            'labels': [{'name': 'status:' + status}, {'name': 'by:' + by}], 'comments': comments or []}


def comment(body, when='2026-10-04T01:00:00Z', who='human', kind='User'):
    return {'body': body, 'created_at': when, 'user': {'login': who, 'type': kind}}


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.loop = runner.Loop(argparse.Namespace(repo=str(runner.REPO), out=str(self.root / 'out'),
                           cards=str(self.root / 'cards'), dry_run=False, game_env={}))
        self.loop.locks = self.root / 'locks'
        self.loop.launched = set()

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_fake_gh_only(self):
        cards = [card(9, by='ai'), card(5), card(7, by='zhe'),
                 card(10, 'needs-info', comments=[comment('Questions before we build', '2026-10-04T00:00:00Z'), comment('이렇게 해 주세요')]),
                 card(11, 'needs-look', by='zhe'), card(12, 'building'), card(13, 'testing'),
                 card(14, 'candidate'), card(15, 'tested'), card(16, 'smoke')]
        fixture = self.root / 'fixture.json'
        fixture.write_text(json.dumps(cards))
        gh = self.root / 'gh'
        gh.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['FAKE_LOG'], 'a') as f: f.write(json.dumps(args)+'\\n')
data = json.loads(Path(os.environ['FAKE_DATA']).read_text())
if args[:2] == ['issue','list']:
    print(json.dumps(data))
elif args[0] == 'api' and args[1].endswith('/comments'):
    n = int(args[1].split('/')[-2]); print(json.dumps([next(c['comments'] for c in data if c['number']==n)]))
else:
    raise SystemExit('unexpected gh call: '+str(args))
''')
        gh.chmod(0o755)
        log = self.root / 'gh.log'
        env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ['PATH'],
                   FAKE_LOG=str(log), FAKE_DATA=str(fixture))
        p = subprocess.run([sys.executable, runner.HERE / 'runner.py', '--once', '--dry-run',
                            '--out', self.root / 'out', '--cards', self.root / 'cards'],
                           env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertLess(p.stdout.index('#7 '), p.stdout.index('#5 '))
        self.assertLess(p.stdout.index('#5 '), p.stdout.index('#9 '))
        self.assertIn('human answer found → building', p.stdout)
        self.assertIn('wait/classify Zhe reply', p.stdout)
        self.assertIn('WORKERS=6 KEEP off', p.stdout)
        self.assertNotIn('#15 ', p.stdout)
        self.assertNotIn('#16 ', p.stdout)
        self.assertFalse((self.root / 'out').exists())
        self.assertFalse((self.root / 'cards').exists())
        calls = [json.loads(x) for x in log.read_text().splitlines()]
        self.assertTrue(all(x[:2] == ['issue', 'list'] or x[0] == 'api' and x[1].endswith('/comments') for x in calls))
        print('\nFake GitHub dry-run:\n' + p.stdout)

    def test_guard_denials_and_allowed_reads(self):
        for command in ('git push origin card/1', 'git -C /tmp push origin main',
                        '/usr/bin/git -c a=b push', 'gh pr create --title x', 'gh pr merge 1',
                        'gh api repos/x -X POST', 'node tools/submit.js active',
                        'node tools/online.js request 1', 'node tools/online.js activate 1',
                        'cat docs/api.txt', 'cat docs/discord.txt', 'x --confirm',
                        'rm -rf work/loop', 'python3 -c "danger()"', 'sh -c "git push"'):
            with self.subTest(command=command):
                self.assertIsNotNone(guard.check({'tool_name': 'Bash', 'tool_input': {'command': command}}))
        for command in ('git status --short', 'git commit -m implementation', 'gh issue view 1',
                        'python3 work/board.py next', 'node tools/online.js battles --json',
                        'node tools/online.js download 123'):
            self.assertIsNone(guard.check({'tool_name': 'Bash', 'tool_input': {'command': command}}), command)
        for tool, path in [('Read', 'docs/api.txt'), ('Edit', 'work/loop/runner.py'), ('Write', 'work/loop/settings.json')]:
            self.assertIsNotNone(guard.check({'tool_name': tool, 'tool_input': {'file_path': path}}))
        with patch.dict(os.environ, {'LOOP_TREE': str(self.root), 'LOOP_OUT': str(self.root / 'out')}):
            self.assertIsNone(guard.check({'tool_name': 'Write', 'cwd': str(self.root),
                                          'tool_input': {'file_path': 'mybot2/main.cpp'}}))
        with patch.dict(os.environ, {'LOOP_BATCH_LEASE': '0'}):
            self.assertIsNotNone(guard.check({'tool_name': 'Bash', 'tool_input': {'command': 'python3 work/ident.py bot'}}))
        with patch.dict(os.environ, {'LOOP_BATCH_LEASE': '1'}):
            self.assertIsNone(guard.check({'tool_name': 'Bash', 'tool_input': {'command': 'python3 work/ident.py bot'}}))

    def test_human_reply_order_language_and_zhe_identity(self):
        c = card(by='zhe', comments=[comment('OK', '2026-10-03T00:00:00Z', 'zhex0121'),
                  comment('ok', who='other'), comment('status', who='bot[bot]', kind='Bot'),
                  comment('아니요, 수정해주세요', who='zhex0121'),
                  comment('Answer from Zhe: 就是这个', who='meow[bot]', kind='Bot')])
        rs = runner.human_replies(c, '2026-10-04T00:00:00Z', zhe=True)
        self.assertEqual(len(rs), 2)
        self.assertIn('수정', rs[0]['body'])

    def test_non_zhe_look_pass_and_zhe_wait(self):
        for by in ('junsing', 'zhe'):
            c = card(1, 'needs-look', by)
            meta = {'attempt': 1, 'base': 'a' * 40, 'phase': 'look'}
            c['comments'] = [comment('<!-- card-loop ' + json.dumps(meta) + ' -->')]
            jobs.write(Path(self.loop.context(c, meta)['out']) / 'look.json', {'replays': ['a', 'b']})
            with patch.object(self.loop, 'transition') as transition:
                self.loop.process(c)
                if by == 'zhe':
                    transition.assert_not_called()
                else:
                    transition.assert_called_once_with(c, 'testing')

    def test_recover_comment_then_label_crash(self):
        c = card(status='building')
        key = 'look-1'
        c['comments'] = [comment('<!-- card-loop {"key":"look-1"} -->')]
        pending = self.loop.out / 'card-1/pending-post.json'
        jobs.write(pending, {'key': key, 'text': 'Already posted.', 'target': 'needs-look',
                             'kind': 'check', 'ask': False, 'metadata': {'base': 'a' * 40}})
        with patch.object(self.loop, 'board') as board, patch.object(self.loop, 'cmd') as cmd:
            self.loop.process(c)
            cmd.assert_not_called()
            board.assert_called_once_with('state', '1', 'needs-look')
        self.assertFalse(pending.exists())

    def test_freeze_blocks_before_any_mutation(self):
        class Frozen(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return runner.FREEZE
        with patch.object(runner.dt, 'datetime', Frozen), patch.object(self.loop, 'cmd') as cmd:
            self.loop.candidate(card(status='candidate'), {'phase': 'tested', 'commit': 'a' * 40})
            cmd.assert_not_called()

    def test_queued_tests_refresh_base(self):
        c = card(status='testing')
        meta = {'attempt': 1, 'base': 'a' * 40, 'commit': 'b' * 40}
        self.loop.save(c, meta)
        jobs.write(Path(self.loop.context(c, meta)['out']) / 'build.json', {})
        with patch.object(self.loop, 'latest_base', return_value='c' * 40), \
             patch.object(self.loop, 'new_attempt') as new, patch.object(self.loop, 'transition') as state:
            self.loop.process(c)
            new.assert_called_once()
            state.assert_called_once_with(c, 'building')

    def test_running_tests_mark_old_base(self):
        c = card(status='testing')
        meta = {'attempt': 1, 'base': 'a' * 40, 'commit': 'b' * 40}
        self.loop.save(c, meta)
        out = Path(self.loop.context(c, meta)['out'])
        jobs.write(out / 'build.json', {})
        jobs.write(out / 'jobs/outcome/job.json', {})
        with patch.object(self.loop, 'latest_base', return_value='c' * 40), \
             patch.object(self.loop, 'post') as post, patch.object(self.loop, 'available_job', return_value=False):
            self.loop.process(c)
            self.assertIn('old-base', post.call_args.args[1])
        self.assertTrue(self.loop.metadata(c)['old_base'])

    def test_lock_resources_and_finished_job_reuse(self):
        c = card()
        meta = {'attempt': 1, 'base': 'a' * 40}
        path = Path(self.loop.context(c, meta)['out']) / 'jobs/look'
        with jobs.lock(self.loop.locks / 'ai.lock'):
            self.assertFalse(self.loop.available_job(c, meta, 'look'))
        jobs.write(path / 'done.json', {'ok': True})
        with patch.object(subprocess, 'Popen') as launch:
            self.assertTrue(self.loop.available_job(c, meta, 'look'))
            launch.assert_not_called()
        with jobs.lock(self.loop.locks / 'batch.lock'):
            self.assertFalse(self.loop.available_job(c, meta, 'build'))
        self.assertFalse(jobs.busy(self.loop.locks / 'batch.lock'))

    def test_lease_survives_parent_fd_close(self):
        path = self.root / 'lease'
        with jobs.lock(path) as fd:
            p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(0.4)'], pass_fds=(fd,))
        try:
            self.assertTrue(jobs.busy(path))
        finally:
            p.wait(timeout=3)
        self.assertFalse(jobs.busy(path))

    def test_transpose_coordinates_portals_and_round_trip(self):
        text = 'MAP 2 3\nSYMMETRY x\nMAP_NAME sample\nTILE_COUNT 1\nTILE 1 2 1 9\nEDGE_COUNT 21\n'
        text += ''.join(f'EDGE {i} {2 if i in (0, 4) else 0} {4 if i == 0 else 0 if i == 4 else -1}\n' for i in range(21))
        text += 'DRAGON_COUNT 1\nDRAGON 0 2 1 2 0 2\nEND\n'
        t = jobs.transpose(text)
        self.assertIn('MAP 3 2', t)
        self.assertIn('SYMMETRY y', t)
        self.assertIn('TILE 2 1 1 9', t)
        self.assertIn('DRAGON 0 2 2 1 2 0', t)
        self.assertEqual(jobs.transpose(t).replace('sample_T_T', 'sample'), text)

    def test_summary_excludes_nonlongest_values_and_pairs_sides(self):
        rows = []
        for side in (0, 1):
            for tag in ('base', 'candidate'):
                rows.append({'tag': tag, 'map': 'sqheld_rooms_small_123', 'seed': 10, 'side': side,
                             'win': int((tag == 'candidate') == (side == 0)),
                             'how': 'longest' if side == 0 else 'elim', 'us': 8 if side == 0 else 0,
                             'them': 6 if side == 0 else 0})
        s = jobs.summary(rows)
        self.assertEqual(s['paired_flips'], {'plus': 1, 'minus': 1})
        self.assertEqual(s['base']['us'], 8)
        self.assertEqual(s['base']['longest_measured'], 1)
        self.assertIn('rooms', s['families'])

    def test_no_new_ladder_games_means_no_ai(self):
        jobs.write(self.loop.out / 'ladder.json', {'seen': ['42'], 'checked': 0})
        with patch.object(self.loop, 'cmd', return_value='[{"id":42,"at":"2026-10-03","wait":null}]'), \
             patch.object(self.loop, 'available_job') as ai:
            self.loop.ladder()
            ai.assert_not_called()

    def test_ambiguous_reply_never_approves(self):
        c = card(status='needs-look', by='zhe')
        meta = {'attempt': 1, 'base': 'a' * 40, 'phase': 'look'}
        c['comments'] = [comment('<!-- card-loop ' + json.dumps(meta) + ' -->', '2026-10-04T00:00:00Z'),
                         comment('어떤 판을 보나요?', who='zhex0121')]
        out = Path(self.loop.context(c, meta)['out'])
        jobs.write(out / 'look.json', {'replays': ['a', 'b']})
        jobs.write(out / 'reply.json', {'decision': 'unclear'})
        jobs.write(out / 'reply-input.json', runner.digest(runner.human_replies(c, '2026-10-04T00:00:00Z', zhe=True)))
        with patch.object(self.loop, 'available_job', return_value=True), patch.object(self.loop, 'transition') as trans:
            self.loop.process(c)
            trans.assert_not_called()


if __name__ == '__main__':
    unittest.main()


class DecisionTests(unittest.TestCase):
    """A reply after the results is the decision (/answer or a GitHub comment)."""

    def run_case(self, decision, by='junsing', who='someone'):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        loop = runner.Loop.__new__(runner.Loop)
        loop.status, loop.launched = {}, set()
        out = Path(tempfile.mkdtemp())
        c = card(7, 'tested', by, comments=[
            comment('Results <!-- card-loop {"phase": "tested", "attempt": 1} -->', '2026-10-04T10:00:00Z', 'juntegral'),
            comment('ship it', '2026-10-04T11:00:00Z', who)])
        def job(*args, **kwargs):  # the light job writes its classification
            runner.write(out / 'decide.json', {'decision': decision})
            return True
        with patch.object(loop, 'available_job', side_effect=job), patch.object(loop, 'transition') as tr, \
                patch.object(loop, 'new_attempt') as na, patch.object(loop, 'notice'):
            handled = loop.human_decision(c, {'attempt': 1}, out)
        return handled, tr, na

    def test_candidate_rejected_inconclusive_move_the_card(self):
        for d in ('candidate', 'rejected', 'inconclusive'):
            handled, tr, na = self.run_case(d)
            self.assertTrue(handled)
            self.assertEqual(tr.call_args.args[1], d)

    def test_revise_starts_a_new_attempt(self):
        handled, tr, na = self.run_case('revise')
        self.assertTrue(handled)
        na.assert_called_once()
        self.assertEqual(tr.call_args.args[1], 'building')

    def test_unclear_does_nothing_and_lets_ai_cards_decide(self):
        handled, tr, na = self.run_case('unclear')
        self.assertFalse(handled)
        tr.assert_not_called()

    def test_zhe_card_ignores_other_people(self):
        handled, tr, na = self.run_case('candidate', by='zhe', who='someone')
        self.assertFalse(handled)
        handled, tr, na = self.run_case('candidate', by='zhe', who='zhex0121')
        self.assertTrue(handled)
