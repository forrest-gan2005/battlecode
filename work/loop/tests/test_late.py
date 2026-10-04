"""Offline missed-estimate, evidence and restart regression tests."""
import argparse
import concurrent.futures as cf
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jobs
import runner
import late


class LateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'card-31/attempt-1/jobs/build'
        self.spec = {'number': 31, 'name': 'queen-hunt', 'title': 'Queen hunt', 'step': 'build',
                     'out': str(self.path.parent.parent), 'started': 1000, 'eta_minutes': 20,
                     'log': str(self.root / 'stream.jsonl'), 'resources': ['ai', 'batch'], 'seed0': 100}
        jobs.write(self.path / 'job.json', self.spec)
        self.card = {'number': 31, 'title': 'Queen hunt', 'name': 'queen-hunt'}
        self.timing = {'eta_minutes': 20, 'queue': None}

    def check(self, minutes, **kw):
        return late.check_late(self.root, self.root / 'locks', self.card, self.spec['step'],
                               self.path, self.timing, now=1000 + minutes * 60, **kw)

    def events(self):
        return list(late.json_rows(self.root / 'events.jsonl'))

    def test_threshold_repeat_restart_and_crash_recovery(self):
        self.assertFalse(self.check(25)['late'])
        self.assertTrue(self.check(26)['late'])
        state = (self.path / 'late.json').read_text()
        first = self.events()[0]
        self.assertAlmostEqual(first['new_eta_minutes'], 7.8)
        self.assertEqual(first['level'], 1)
        self.check(30)
        self.check(33.8)
        self.assertEqual(len(self.events()), 1)
        self.check(34)
        self.assertEqual(self.events()[-1]['level'], 2)
        (self.path / 'late.json').write_text(state)
        self.check(35)
        self.assertEqual(len(self.events()), 2)
        self.assertEqual(jobs.read(self.path / 'late.json')['notice'], self.events()[-1])
        jobs.write(self.path / 'done.json', {'ok': True})
        self.assertFalse(self.check(90)['late'])

    def test_five_minimum_and_longest_history(self):
        self.timing['eta_minutes'] = 2
        self.assertFalse(self.check(6)['late'])
        self.assertEqual(self.check(7)['new_eta_minutes'], 5)
        other = self.root / 'card-4/attempt-1/jobs/build'
        jobs.write(other / 'job.json', {'started': 100})
        jobs.write(other / 'done.json', {'finished': 100 + 80 * 60})
        self.assertEqual(self.check(13)['new_eta_minutes'], 67)

    def test_ai_log_counts_descriptions_and_limit(self):
        blocks = [{'type': 'tool_use', 'id': str(i), 'name': name, 'input': args}
                  for i, (name, args) in enumerate([
                      ('Read', {'file_path': 'mybot2/main.cpp'}),
                      ('Edit', {'file_path': 'mybot2/main.cpp'}),
                      ('Bash', {'command': 'python work/ident.py candidate', 'description': 'Run identity check'}),
                      ('Bash', {'command': 'c++ main.cpp', 'description': 'Build bot'}),
                      ('Bash', {'command': 'python replay.py x', 'description': 'Read replay'}),
                      ('Bash', {'command': 'sed -n 1,200p main.cpp', 'description': 'Read bot'}),
                      ('Bash', {'command': 'echo x', 'description': 'Last description ' + 'x' * 500})])]
        record = {'type': 'assistant', 'message': {'content': blocks}}
        Path(self.spec['log']).write_text(json.dumps(record) + '\ninvalid\n' + json.dumps(record) + '\n')
        reason = self.check(26)['reason']
        for text in ('7 tool calls', '2 reads', '1 edits', '1 identity checks', '1 builds', '1 game/replay runs', 'Read bot', 'Last description'):
            self.assertIn(text, reason)
        self.assertLessEqual(len(reason), 300)

    def test_batch_rows_replays_deduplicated_and_unrelated_ignored(self):
        self.spec['step'] = 'mechanism'
        jobs.write(self.path / 'job.json', self.spec)
        out = Path(self.spec['out'])
        jobs.write(out / 'mechanism-plan.json', {'sets': {'mechanism': {'maps': ['tiny'], 'games_per_map_per_variant': 10}}})
        rows = [{'tag': tag, 'map': 'tiny', 'seed': 100 + k // 2, 'side': k % 2}
                for tag in ('base', 'candidate') for k in range(4)]
        jobs.write(out / 'mechanism.json', rows[:2])
        (out / 'mechanism.rows.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\npartial')
        replays = out / 'replays'
        replays.mkdir()
        (replays / 'base_tiny_100_0.replay').write_text('done')
        (replays / 'base_tiny_102_0.replay').write_text('done')
        (replays / 'base_unrelated_100_0.replay').write_text('done')
        result = self.check(30)
        self.assertIn('9 of 20 done, 0.3/min', result['reason'])
        self.assertAlmostEqual(result['new_eta_minutes'], 11 / .3)

    def test_batch_unknown_not_infinite_or_zero(self):
        self.spec['step'] = 'outcome'
        jobs.write(self.path / 'job.json', self.spec)
        result = self.check(30)
        self.assertFalse(result['eta_known'])
        self.assertEqual(result['new_eta_minutes'], 15)
        self.assertIn('unknown', result['reason'])

    def test_waiting_card_remaining_plus_own_and_then_running(self):
        holder = self.root / 'card-9/attempt-1/jobs/outcome'
        jobs.write(holder / 'job.json', {'number': 9, 'name': 'pool-check', 'title': 'Pool', 'step': 'outcome',
                                        'started': 1000, 'eta_minutes': 60, 'resources': ['batch']})
        self.timing['queue'] = 'batch lock'
        with jobs.lock(holder / 'lease'):
            self.assertFalse(self.check(0, resources=['batch'])['late'])
            self.assertFalse(self.check(14.9, resources=['batch'])['late'])
            result = self.check(15, resources=['batch'])
            self.assertIn('#9 pool-check outcome (about 45m remaining)', result['reason'])
            self.assertEqual(result['new_eta_minutes'], 65)
            self.assertEqual(result['new_start_at'], jobs.iso_time(1000 + 60 * 60))
            self.check(30, resources=['batch'])
            self.assertEqual(len(self.events()), 1)
            self.check(61, resources=['batch'])
            self.assertFalse(self.events()[-1]['eta_known'])
        self.timing['queue'] = None
        self.spec['started'] = 1000 + 62 * 60
        jobs.write(self.path / 'job.json', self.spec)
        self.assertFalse(self.check(62)['late'])
        self.check(90)
        self.assertEqual(self.events()[-1]['level'], 3)

    def test_waiting_external_lsof_and_unknown_retry(self):
        self.timing['queue'] = 'batch lock'
        replies = [type('R', (), {'stdout': 'p42\ncPython\nf3\nlW\n'})(),
                   type('R', (), {'stdout': 'python3 work/pool.py validate'})()]
        with jobs.lock(self.root / 'locks/batch.lock'), patch('late.subprocess.run', side_effect=replies) as run:
            self.check(0, resources=['batch'])
            result = self.check(18, resources=['batch'])
            self.assertIn('pool validation (work/pool.py) (pid 42)', result['reason'])
            self.assertIn('unknown, checking again in 15 min', result['reason'])
            self.assertEqual(run.call_args_list[0].args[0][0], 'lsof')
            self.check(32, resources=['batch'])
            self.assertEqual(len(self.events()), 1)
        with patch('late.external_holder', return_value=None):
            self.check(34, resources=['batch'])
        self.assertEqual(len(self.events()), 2)

    def test_runner_status_and_paused_running_scan(self):
        loop = runner.Loop(argparse.Namespace(repo=str(self.root), out=str(self.root), cards=str(self.root), dry_run=False))
        loop.locks = self.root / 'locks'
        with jobs.lock(self.path / 'lease'), patch('jobs.time.time', return_value=2800):
            loop.running_notices()
        info = loop.status['31']
        self.assertTrue(info['late'])
        self.assertIn('reason', info)
        self.assertIn('new_eta_at', info)
        self.assertEqual(self.events()[0]['name'], 'queen-hunt')

    def test_ab3_writes_progress_with_replays_disabled(self):
        out = self.root / 'outcome.json'
        fake = SimpleNamespace(ROOT=str(self.root), build=lambda *a: 'fake-bot',
                               play=lambda job: (job[0], job[3], {'win': True, 'us': 4, 'them': 2}))
        argv = ['ab3.py', 'tiny', 'base', '2', str(out), 'base@base:', 'candidate@candidate:FLAG=true']
        with patch.dict(sys.modules, {'ab2': fake}), patch.object(sys, 'argv', argv), \
             patch.dict(os.environ, {'WORKERS': '2', 'SEED0': '100'}, clear=True), \
             patch('concurrent.futures.ProcessPoolExecutor', cf.ThreadPoolExecutor):
            runpy.run_path(str(runner.REPO / 'work/ab3.py'), run_name='__main__')
        rows = list(late.json_rows(self.root / 'outcome.rows.jsonl'))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows, jobs.read(out))
        self.assertEqual({r['tag'] for r in rows}, {'base', 'candidate'})


if __name__ == '__main__':
    unittest.main()
