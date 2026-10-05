"""Offline deferred Force requests: progress, cancellation and unchanged controls."""
import datetime as dt
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jobs
import meow_control as control
import test_runner
from test_runner import card


class DeferredForce(unittest.TestCase):
    setUp = test_runner.Tests.setUp
    tearDown = test_runner.Tests.tearDown

    def setup_request(self, state='building', **updates):
        self.card = card(status=state)
        self.meta = {'attempt': 3, 'base': 'a' * 40, 'commit': 'b' * 40}
        self.loop.save(self.card, self.meta)
        self.req = dict(id='force-1', action='set_state', card=1, state='candidate',
                        force=True, after_build=True, attempt=3, _state='building',
                        requester_id='member', thread_id='99', audit='via /meow by jun\n⚠️ forced by jun: checked locally',
                        created=dt.datetime.now(dt.timezone.utc).isoformat())
        self.req.update(updates)
        jobs.write(self.loop.out / 'meow-requests/force-1.json', self.req)

    def poll(self, base_moved=False):
        with patch.object(control, 'issue', return_value=self.card), \
                patch.object(self.loop, 'cmd') as cmd, \
                patch.object(self.loop, 'transition') as transition, \
                patch.object(self.loop, 'base_moved', return_value=base_moved):
            control.controls(self.loop)
        return cmd, transition

    def result(self):
        return jobs.read(self.loop.out / 'meow-results/force-1.json')

    def test_waits_through_build_mechanism_and_look_without_receipt(self):
        self.setup_request()
        for phase in ('building', 'mechanism', 'look'):
            self.meta['phase'] = phase
            self.loop.save(self.card, self.meta)
            cmd, transition = self.poll()
            cmd.assert_not_called()
            transition.assert_not_called()
            self.assertIsNone(self.result())
            self.assertFalse((self.loop.out / 'meow-receipts/force-1.json').exists())
            self.assertNotIn('force_override', self.loop.metadata(self.card))

    def test_wait_then_apply_same_attempt_at_needs_look_once_with_audit(self):
        self.setup_request()
        self.poll()
        self.card['labels'][0]['name'] = 'status:needs-look'
        cmd, transition = self.poll()
        transition.assert_called_once_with(self.card, 'candidate')
        self.assertTrue(self.result()['ok'])
        self.assertIn(self.req['audit'], self.result()['message'])
        self.assertIn(self.req['audit'], cmd.call_args.args[0][-1])
        meta = self.loop.metadata(self.card)
        self.assertTrue(meta['force_override'])
        self.assertEqual(meta['force_reason'], self.req['audit'])
        self.assertEqual(meta['phase'], 'tested')
        cmd, transition = self.poll()
        cmd.assert_not_called()
        transition.assert_not_called()

    def test_later_same_attempt_is_accepted(self):
        self.setup_request(state='tested')
        _, transition = self.poll()
        transition.assert_called_once_with(self.card, 'candidate')
        self.assertTrue(self.result()['ok'])

    def test_new_attempt_is_refused_even_while_building(self):
        self.setup_request()
        self.meta['attempt'] = 4
        self.loop.save(self.card, self.meta)
        _, transition = self.poll()
        transition.assert_not_called()
        self.assertFalse(self.result()['ok'])
        self.assertIn('new build attempt', self.result()['message'])

    def test_failed_build_is_refused(self):
        self.setup_request(state='ready')
        self.meta['failed'] = True
        self.loop.save(self.card, self.meta)
        _, transition = self.poll()
        transition.assert_not_called()
        self.assertFalse(self.result()['ok'])
        self.assertIn('This build failed', self.result()['message'])
        self.assertNotIn('ValueError', self.result()['message'])

    def test_failed_worker_before_metadata_update_is_refused(self):
        self.setup_request()
        out = Path(self.loop.context(self.card, self.meta)['out'])
        jobs.write(out / 'jobs/build/done.json', {'ok': False, 'error': 'build broke'})
        _, transition = self.poll()
        transition.assert_not_called()
        self.assertIn('This build failed', self.result()['message'])

    def test_expired_request_refused_even_if_build_is_ready(self):
        self.setup_request(state='needs-look', created=(dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=6)).isoformat())
        _, transition = self.poll()
        transition.assert_not_called()
        self.assertFalse(self.result()['ok'])
        self.assertIn('expired after six hours', self.result()['message'])

    def test_expired_request_refused_while_building(self):
        self.setup_request(created=(dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=7)).isoformat())
        _, transition = self.poll()
        transition.assert_not_called()
        self.assertIn('expired after six hours', self.result()['message'])

    def test_current_base_and_commit_are_required(self):
        self.setup_request(state='needs-look')
        _, transition = self.poll(base_moved=True)
        transition.assert_not_called()
        self.assertIn('Main changed again', self.result()['message'])

    def test_no_commit_cannot_use_old_candidate(self):
        self.setup_request(state='needs-look')
        self.meta.pop('commit')
        self.loop.save(self.card, self.meta)
        _, transition = self.poll()
        transition.assert_not_called()
        self.assertIn('no recorded commit', self.result()['message'])

    def test_ordinary_force_keeps_state_guard(self):
        self.setup_request(state='needs-look', after_build=False)
        _, transition = self.poll()
        transition.assert_not_called()
        self.assertFalse(self.result()['ok'])
        self.assertIn('Card moved after confirmation; request a fresh preview.', self.result()['message'])

    def test_ordinary_force_still_overrides_base_without_expiry(self):
        self.setup_request(state='tested', _state='tested', after_build=False,
                           created='2020-01-01T00:00:00Z')
        _, transition = self.poll(base_moved=True)
        transition.assert_called_once_with(self.card, 'candidate')
        self.assertTrue(self.result()['ok'])

    def test_deferred_request_does_not_bypass_locks(self):
        self.setup_request(state='needs-look')
        for lock in ('ai.lock', 'batch.lock'):
            with jobs.lock(self.loop.locks / lock):
                cmd, transition = self.poll()
            cmd.assert_not_called()
            transition.assert_not_called()
            self.assertIsNone(self.result())

    def test_deferred_flag_does_not_bypass_other_actions(self):
        self.setup_request(state='needs-look', force=False)
        _, transition = self.poll()
        transition.assert_not_called()
        self.assertIn('only supported for forced candidate', self.result()['message'])


if __name__ == '__main__':
    unittest.main()
