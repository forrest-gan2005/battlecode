"""Offline ETA and durable step-event checks."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jobs
import runner


class EtaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def record(self, index, step='build', minutes=10):
        path = self.root / f'card-{index}' / 'attempt-1' / 'jobs' / step
        spec = {'number': index, 'title': 'Test', 'step': step, 'resources': ['ai'],
                'out': str(path.parent.parent), 'started': 10000 + index * 100000}
        jobs.write(path / 'job.json', spec)
        jobs.write(path / 'done.json', {'ok': True, 'finished': spec['started'] + minutes * 60})
        return path, spec

    def test_defaults_and_last_ten_median(self):
        for step, default in jobs.ETA_DEFAULTS.items():
            self.assertEqual(jobs.eta_minutes(self.root, step), default)
        self.record(0, minutes=1000)
        self.assertEqual(jobs.eta_minutes(self.root, 'build'), 20)
        for i in range(1, 11):
            self.record(i, minutes=i)
        self.assertEqual(jobs.eta_minutes(self.root, 'build'), 5.5)
        self.assertEqual(jobs.eta_minutes(self.root, 'task'), 15)

    def test_real_legacy_fields(self):
        for i, minutes in enumerate((4, 8)):
            path, spec = self.record(i, 'look', minutes)
            jobs.write(path / 'running.json', {'started': spec.pop('started')})
            jobs.write(path / 'job.json', spec)
        self.assertEqual(jobs.eta_minutes(self.root, 'look'), 6)

    def test_lock_wait_and_status(self):
        path, spec = self.record(1, 'outcome', 30)
        (path / 'done.json').unlink()
        spec.update(resources=['batch'], started=1000, eta_minutes=30)
        jobs.write(path / 'job.json', spec)
        with jobs.lock(path / 'lease'), patch('jobs.time.time', return_value=1600):
            self.assertEqual(jobs.remaining_wait(self.root, ['batch']), 20)
            self.assertEqual(jobs.remaining_wait(self.root, ['ai']), 0)
            loop = runner.Loop(argparse.Namespace(repo=str(self.root), out=str(self.root), cards=str(self.root), dry_run=False))
            loop.job_notice({'number': 7, 'labels': [{'name': 'status:ready'}]}, 'mechanism',
                            self.root / 'missing', 'mechanism waiting', queue='batch lock', resources=['batch'])
            info = loop.status['7']
            self.assertEqual(info['wait_minutes'], 20)
            self.assertEqual(info['queue'], 'batch lock')
            self.assertIsNone(info['step_started'])
            self.assertEqual(info['eta_at'], jobs.iso_time(1600 + 50 * 60))

    def test_worker_events_success_failure_and_no_duplicate(self):
        for index, fails in enumerate((False, True)):
            path, spec = self.record(index)
            (path / 'done.json').unlink()
            spec.update(kind='ai', locks=str(self.root / 'locks'))
            jobs.write(path / 'job.json', spec)
            with patch('jobs.ai', side_effect=RuntimeError('fake failure') if fails else None), patch('jobs.time.time', side_effect=[1000, 1120]):
                jobs.worker(path)
            jobs.worker(path)
        rows = [json.loads(line) for line in (self.root / 'events.jsonl').read_text().splitlines()]
        self.assertEqual([r['event'] for r in rows], ['start', 'done', 'start', 'failed'])
        self.assertEqual(rows[1]['minutes'], 2)
        self.assertEqual(rows[3]['note'], 'fake failure')
        self.assertEqual(rows[0]['eta_minutes'], 20)
        self.assertEqual(rows[0]['card'], 0)
