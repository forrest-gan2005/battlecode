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
        self.assertFalse(self.check(24)['late'])
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

    def test_waiting_discord_cadence_and_restart(self):
        self.timing['queue'] = 'ai lock'
        with patch('late.lock_reason', return_value=('waiting for #9 pool-check', 10, True,
                                                     [{'job': 'holder', 'late': True}])):
            self.check(0, resources=['ai'])
            for minute in (30, 60, 119, 120, 121, 239, 240):
                self.check(minute, resources=['ai'])
        posted = [e for e in self.events() if e['post']]
        self.assertEqual([e['elapsed_minutes'] for e in posted], [120, 240])
        self.assertEqual(posted[0]['reason'], 'waiting for #9 pool-check')
        self.assertEqual(posted[0]['new_start_at'], jobs.iso_time(1000 + 130 * 60))

    def test_running_discord_milestones_and_hourly(self):
        for minute in (24, 26, 38, 40, 41, 99, 100, 159, 160):
            self.check(minute)
        self.assertEqual([e['elapsed_minutes'] for e in self.events() if e['post']],
                         [26, 40, 100, 160])
        self.assertTrue(any(e['post'] is False for e in self.events()))

    def test_post_boundary_does_not_change_status_threshold(self):
        result = self.check(25)
        self.assertFalse(result['late'])
        self.assertTrue(self.events()[0]['post'])
        self.assertNotIn('notice', jobs.read(self.path / 'late.json'))

    def test_waiting_status_keeps_old_estimates_and_resets_on_running(self):
        self.timing['queue'] = 'batch lock'
        with patch('late.lock_reason', return_value=('waiting for #9 pool-check', 10, True, [])):
            self.check(0)
            result = self.check(15)
            self.assertTrue(result['late'])
            self.assertEqual(result['new_eta_minutes'], 30)
            for minute in (30, 60, 119, 120, 240):
                self.check(minute)
        self.assertEqual([e['elapsed_minutes'] for e in self.events() if e['post']], [120, 240])
        self.timing['queue'] = None
        self.spec['started'] = 1000 + 241 * 60
        jobs.write(self.path / 'job.json', self.spec)
        self.check(241)
        self.check(267)
        self.assertTrue(self.events()[-1]['post'])
        self.assertEqual(jobs.read(self.path / 'late.json')['posts'], 1)

    def test_brief_build_then_test_with_three_continuous_waiters(self):
        build = self.path
        self.spec['eta_minutes'] = 26
        self.spec['resources'] = ['ai']
        jobs.write(build / 'job.json', self.spec)
        test = self.root / 'card-31/attempt-1/jobs/outcome'
        spec = {**self.spec, 'step': 'outcome', 'eta_minutes': 77, 'started': 1000 + 65 * 60}
        waiters = [(self.root / f'card-{n}/attempt-1/jobs/build',
                    {'number': n, 'name': f'waiting-{n}'}) for n in (32, 33, 34)]
        for minute in range(157):
            holder = build if minute < 65 else test
            if minute == 65:
                jobs.write(build / 'done.json', {'ok': True})
                jobs.write(test / 'job.json', spec)
            with jobs.lock(holder / 'lease'):
                for path, card in waiters:
                    late.check_late(self.root, self.root / 'locks', card, 'build', path,
                                    {'eta_minutes': 20, 'queue': 'ai lock'}, resources=['ai'],
                                    now=1000 + minute * 60)
                late.check_late(self.root, self.root / 'locks', self.card,
                                'build' if minute < 65 else 'outcome', holder,
                                {'eta_minutes': 26 if minute < 65 else 77, 'queue': None},
                                now=1000 + minute * 60)
        posted = [e for e in self.events() if e['post']]
        self.assertEqual(len(posted), 5)
        running = [e for e in posted if not e['waiting']]
        self.assertEqual([e['elapsed_minutes'] for e in running], [33, 52])
        self.assertTrue(all(len(e['waiters']) == 3 for e in running))
        self.assertEqual([e['elapsed_minutes'] for e in posted if e['waiting']], [120] * 3)

    def test_five_minimum_and_longest_history(self):
        self.timing['eta_minutes'] = 2
        self.assertFalse(self.check(6)['late'])
        self.assertEqual(self.check(7)['new_eta_minutes'], 5)
        other = self.root / 'card-4/attempt-1/jobs/build'
        jobs.write(other / 'job.json', {'started': 100})
        jobs.write(other / 'done.json', {'finished': 100 + 80 * 60})
        self.assertEqual(self.check(13)['new_eta_minutes'], 67)

    def test_ai_log_latest_description_deduplicated_and_limited(self):
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
        self.assertTrue(reason.startswith('last description'))
        self.assertLessEqual(len(reason), 90)
        self.assertNotIn('tool calls', reason)

    def test_activity_dominant_checks_and_generic(self):
        for description, expected in [('Run identity check', 're-checking that it plays the same when off'),
                                      ('Run games', 'running games and checking how it plays')]:
            Path(self.spec['log']).write_text(json.dumps({'message': {'content': [
                {'type': 'tool_use', 'name': 'Bash', 'input': {'description': description}}]}}))
            self.assertEqual(late.ai_reason(self.spec), expected)
        Path(self.spec['log']).write_text('')
        self.assertEqual(late.ai_reason(self.spec), 'still editing and checking the change')

    def test_late_holder_covers_waiters_before_its_notice(self):
        holder = self.root / 'ladder/attempt-1/jobs/ladder'
        jobs.write(holder / 'job.json', {'number': 0, 'title': 'Ladder review', 'step': 'ladder',
                                        'out': str(holder.parent.parent), 'started': 1000,
                                        'eta_minutes': 17, 'resources': ['ai', 'batch']})
        self.timing['queue'] = 'ai lock'
        with jobs.lock(holder / 'lease'):
            self.check(0, resources=['ai'])
            result = self.check(22, resources=['ai'])
            self.assertEqual(result['covered_by'], [str(holder)])
            self.assertEqual(self.events(), [])
            other = self.root / 'card-30/attempt-1/jobs/build'
            late.check_late(self.root, self.root / 'locks', {'number': 30, 'name': 'big-map-trades'},
                            'build', other, {'queue': 'batch lock', 'eta_minutes': 20},
                            resources=['batch'], now=2320)
            late.check_late(self.root, self.root / 'locks', {'number': 0, 'title': 'Ladder review'},
                            'ladder', holder, {'queue': None, 'eta_minutes': 17}, now=2320)
            event = self.events()[0]
            self.assertEqual(len(self.events()), 1)
            self.assertEqual({c['number'] for c in event['waiters']}, {30, 31})
            self.assertEqual(result['holders'][0]['step'], 'ladder')
        jobs.write(holder / 'done.json', {'ok': True})
        result = self.check(23, resources=['ai'])
        self.assertNotIn('covered_by', result)
        self.assertEqual(len(self.events()), 2)

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
        self.assertIn('9 of 20 done', result['reason'])
        self.assertAlmostEqual(result['new_eta_minutes'], 11 / .3)

    def test_batch_unknown_not_infinite_or_zero(self):
        self.spec['step'] = 'outcome'
        jobs.write(self.path / 'job.json', self.spec)
        result = self.check(30)
        self.assertFalse(result['eta_known'])
        self.assertEqual(result['new_eta_minutes'], 15)
        self.assertEqual(result['reason'], 'checking game progress')

    def test_waiting_card_remaining_plus_own_and_then_running(self):
        holder = self.root / 'card-9/attempt-1/jobs/outcome'
        jobs.write(holder / 'job.json', {'number': 9, 'name': 'pool-check', 'title': 'Pool', 'step': 'outcome',
                                        'started': 1000, 'eta_minutes': 60, 'resources': ['batch']})
        self.timing['queue'] = 'batch lock'
        with jobs.lock(holder / 'lease'):
            self.assertFalse(self.check(0, resources=['batch'])['late'])
            self.assertFalse(self.check(14.9, resources=['batch'])['late'])
            result = self.check(15, resources=['batch'])
            self.assertIn('#9 pool-check', result['reason'])
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
            self.assertIn('pool validation', result['reason'])
            self.assertNotIn('unknown', result['reason'])
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
