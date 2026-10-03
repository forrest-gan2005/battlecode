"""Additional job-level checks; all commands are mocked or harmless Python children."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import jobs
import runner


class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.loop = runner.Loop(argparse.Namespace(repo=str(HERE.parents[1]), out=str(self.root / 'out'),
                            cards=str(self.root / 'trees'), dry_run=False, game_env={}))
        self.loop.locks = self.root / 'locks'
        self.loop.launched = set()
        self.card = dict(number=3, title='[Idea] test', body='', labels=[{'name': 'status:building'}],
                         comments=[], author={'login': 'zhe'})
        self.meta = {'attempt': 1, 'base': 'a' * 40}
        self.ctx = self.loop.context(self.card, self.meta)
        self.out = Path(self.ctx['out'])
        self.out.mkdir(parents=True)

    def test_fixture_dry_run(self):
        bindir = self.root / 'bin'
        bindir.mkdir()
        gh = bindir / 'gh'
        gh.write_bytes((HERE / 'tests/fake-gh').read_bytes())
        gh.chmod(0o755)
        env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ['PATH'],
                   FAKE_GH_DATA=str(HERE / 'tests/cards.json'))
        result = subprocess.run([sys.executable, str(HERE / 'runner.py'), '--once', '--dry-run',
                  '--out', str(self.root / 'must-not-exist')], env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for text in ('ab3:', 'wait/classify Zhe reply', 'auto-pass'):
            self.assertIn(text, result.stdout)
        self.assertFalse((self.root / 'must-not-exist').exists())
        self.assertLess(result.stdout.index('#1 '), result.stdout.index('#10 '))

    def test_batch_blocks_build_but_not_clarify(self):
        with jobs.lock(self.loop.locks / 'batch.lock'), patch.object(subprocess, 'Popen') as popen:
            self.assertFalse(self.loop.available_job(self.card, self.meta, 'build'))
            popen.assert_not_called()
            self.loop.available_job(self.card, self.meta, 'clarify')
            popen.assert_called_once()
        spec = jobs.read(self.out / 'jobs/clarify/job.json')
        self.assertEqual(spec['resources'], ['ai'])
        self.assertTrue(Path(spec['prompt']).exists())

    def test_same_tick_reservation(self):
        with patch.object(subprocess, 'Popen') as popen:
            self.loop.available_job(self.card, self.meta, 'clarify')
            self.loop.available_job(self.card, self.meta, 'look')
            popen.assert_called_once()

    def test_build_identity_rejects_zero_exit_diff(self):
        tree = Path(self.ctx['tree'])
        (tree / 'mybot2').mkdir(parents=True)
        (tree / 'mybot2/main.cpp').write_text('constexpr bool FD_TEST = false;')
        jobs.write(self.out / 'build.json', {'toggle': 'FD_TEST', 'mechanism_maps': ['one', 'two'],
                  'mechanism_games_per_map': 4, 'check': 'work/check.py'})
        (self.out / 'prompt.md').write_text('build')
        (self.out / 'ai.jsonl').write_text('{"type":"result","is_error":false}\n')
        spec = dict(self.ctx, step='build', prompt=str(self.out / 'prompt.md'), log=str(self.out / 'ai.jsonl'))
        with patch.object(jobs, 'run', side_effect=['', 'OK a\nDIFF b\n1 differ\n']):
            with self.assertRaisesRegex(ValueError, 'identity failed'):
                jobs.ai(spec, [])
        self.assertFalse((self.out / 'built.json').exists())

    def test_incomplete_ab3_rows_fail(self):
        jobs.write(self.out / 'build.json', {'toggle': 'FD_TEST', 'mechanism_maps': ['one', 'two'],
                  'mechanism_games_per_map': 4, 'check': 'work/check.py'})
        def fake_run(argv, *args, **kwargs):
            jobs.write(argv[5], [])
        with patch.object(jobs, 'run', side_effect=fake_run):
            with self.assertRaisesRegex(ValueError, 'missing/duplicate'):
                jobs.batch(dict(self.ctx, step='mechanism'), [])
        self.assertFalse((self.out / 'mechanism.json').exists())
        self.assertEqual(len(list(self.out.glob('mechanism-incomplete-*.json'))), 1)

    def test_worker_done_and_restart_no_duplicate(self):
        path = self.out / 'jobs/look'
        jobs.write(path / 'job.json', dict(self.ctx, kind='ai', resources=['ai'], locks=str(self.loop.locks)))
        with patch.object(jobs, 'ai') as ai:
            jobs.worker(path)
            jobs.worker(path)
            ai.assert_called_once()
        self.assertTrue(jobs.read(path / 'done.json')['ok'])
        self.assertIn('pid', jobs.read(path / 'running.json'))

    def test_worker_error_is_recorded(self):
        path = self.out / 'jobs/look'
        jobs.write(path / 'job.json', dict(self.ctx, kind='ai', resources=['ai'], locks=str(self.loop.locks)))
        with patch.object(jobs, 'ai', side_effect=RuntimeError('mock timeout')):
            jobs.worker(path)
        self.assertFalse(jobs.read(path / 'done.json')['ok'])
        self.assertFalse(jobs.busy(self.loop.locks / 'ai.lock'))

    def test_ai_result_survives_supervisor_crash(self):
        (self.out / 'prompt.md').write_text('look')
        (self.out / 'look.jsonl').write_text('{"type":"result","is_error":false}\n')
        spec = dict(self.ctx, step='look', prompt=str(self.out / 'prompt.md'), log=str(self.out / 'look.jsonl'))
        with patch.object(jobs, 'run') as call:
            jobs.ai(spec, [])
            call.assert_not_called()

    def test_timeout_kills_harmless_child(self):
        with self.assertRaisesRegex(RuntimeError, 'timed out'):
            jobs.run([sys.executable, '-c', 'import time; time.sleep(30)'], self.root, timeout=0.05)

    def test_invalid_mechanism_size(self):
        path = self.root / 'bad.json'
        jobs.write(path, {'toggle': 'FD_TEST', 'mechanism_maps': ['one'], 'mechanism_games_per_map': 3, 'check': 'work/check.py'})
        with self.assertRaisesRegex(ValueError, '16–32'):
            jobs.plan(path)

    def test_running_nonloop_batch_waits(self):
        with patch.object(self.loop, 'cmd', return_value='/usr/bin/unswbc run map base candidate'), \
             patch.object(subprocess, 'Popen') as popen:
            self.assertFalse(self.loop.available_job(self.card, self.meta, 'build'))
            popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
