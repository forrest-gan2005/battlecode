"""Offline confirmed-control and adoption checks; no real AI, games, git or remote calls."""
import json
import os
from pathlib import Path
import types
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jobs
import guard
import meow_control as control
import runner
import test_runner
from test_runner import card


class Controls(unittest.TestCase):
    setUp = test_runner.Tests.setUp
    tearDown = test_runner.Tests.tearDown

    def request(self, action, **kw):
        req = {'id': 'request-1', 'action': action, 'requester_id': '746389534832328824',
               'thread_id': '99', 'audit': 'via /meow by 준싱', **kw}
        jobs.write(self.loop.out / 'meow-requests' / (req['id'] + '.json'), req)
        return req

    def test_pause_resume_persist_and_do_not_kill_jobs(self):
        self.request('pause_runner')
        with patch.object(self.loop, 'cmd', side_effect=AssertionError('No process/remote action')):
            self.assertTrue(control.controls(self.loop))
            self.assertTrue(control.controls(self.loop))
            self.request('resume_runner', id='request-2')
            self.assertFalse(control.controls(self.loop))
        self.assertFalse(jobs.read(self.loop.out / 'meow-control.json')['paused'])
        self.assertTrue(jobs.read(self.loop.out / 'meow-results/request-1.json')['ok'])

    def test_force_candidate_overrides_old_remote_metadata(self):
        c = card(status='tested', by='ai')
        c['state'] = 'OPEN'
        old = {'attempt': 1, 'base': 'a' * 40, 'commit': 'b' * 40, 'phase': 'look',
               'ai_pending': {'target': 'rejected'}}
        c['comments'] = [{'body': '<!-- card-loop ' + json.dumps(old) + ' -->'}]
        self.loop.save(c, old)
        self.request('set_state', card=1, state='candidate', force=True, _state='tested')
        with patch.object(control, 'issue', return_value=c), patch.object(self.loop, 'cmd'), \
             patch.object(self.loop, 'transition') as transition:
            control.controls(self.loop)
            control.controls(self.loop)
        transition.assert_called_once_with(c, 'candidate')
        meta = self.loop.metadata(c)
        self.assertTrue(meta['force_override'])
        self.assertEqual(meta['phase'], 'tested')
        self.assertNotIn('ai_pending', meta)
        with patch.object(self.loop, 'verdict_fields', side_effect=AssertionError('Overridden decision')):
            self.loop.auto_decide(c, meta)

    def test_interrupted_control_does_not_repeat_side_effects(self):
        self.request('set_state', card=1, state='candidate', force=True)
        jobs.write(self.loop.out / 'meow-receipts/request-1.json', {'state': 'executing'})
        with patch.object(self.loop, 'cmd'), patch.object(control, 'issue', side_effect=AssertionError('must not retry')):
            control.controls(self.loop)
        self.assertFalse(jobs.read(self.loop.out / 'meow-results/request-1.json')['ok'])

    def test_use_branch_pins_commit_skips_build_step(self):
        c = card(status='tested')
        c['state'] = 'OPEN'
        self.request('use_branch_as_impl', card=1, commit='b' * 40, _state='tested')
        with patch.object(control, 'issue', return_value=c), patch.object(self.loop, 'cmd') as cmd, \
             patch.object(self.loop, 'transition') as transition, patch.object(self.loop, 'latest_base', return_value='a' * 40):
            control.controls(self.loop)
        meta = self.loop.metadata(c)
        self.assertEqual(meta['impl_commit'], 'b' * 40)
        self.assertIn('--detach', cmd.call_args_list[1].args[0])
        transition.assert_called_once_with(c, 'building')
        c['labels'][0]['name'] = 'status:building'
        with patch.object(self.loop, 'latest_base', return_value='a' * 40), patch.object(self.loop, 'prepare', return_value=self.loop.context(c, meta)), \
             patch.object(self.loop, 'available_job', return_value=False) as job:
            self.loop.process(c)
        self.assertEqual(job.call_args.args[2], 'adopt')
        self.assertNotIn('build', [x.args[2] for x in job.call_args_list])

    def test_adoption_guard_reads_code_writes_only_output(self):
        out = self.root / 'out'
        with patch.dict(os.environ, {'LOOP_STEP': 'adopt', 'LOOP_OUT': str(out), 'LOOP_TREE': str(self.root / 'tree')}):
            self.assertIsNotNone(guard.check({'tool_name': 'Write', 'cwd': str(self.root), 'tool_input': {'file_path': 'tree/mybot2/main.cpp'}}))
            self.assertIsNone(guard.check({'tool_name': 'Write', 'cwd': str(self.root), 'tool_input': {'file_path': str(out / 'build.json')}}))
            self.assertIsNotNone(guard.check({'tool_name': 'Bash', 'tool_input': {'command': 'git commit -am edit'}}))

    def test_identity_failure_is_reported_not_a_rollback(self):
        self.request('identity_notice', pr=12, base='a' * 40, commit='b' * 40, audit='via /meow by 준싱\n⚠️ forced by 준싱: urgent')
        with patch.object(control, 'submit_job', return_value={'ok': False, 'error': 'DIFF on map'}), \
             patch.object(self.loop, 'cmd') as cmd:
            control.controls(self.loop)
        result = jobs.read(self.loop.out / 'meow-results/request-1.json')
        self.assertFalse(result['ok'])
        self.assertIn('WARNING', result['message'])
        self.assertEqual(cmd.call_args.args[0][:3], ['gh', 'pr', 'comment'])
        self.assertIn('⚠️ forced by 준싱: urgent', result['message'])

    def test_identity_turns_new_toggle_off_and_checks_40(self):
        out = self.root / 'job'
        out.mkdir()
        def export(repo, commit, dest, fds):
            dest.mkdir(parents=True)
            (dest / 'main.cpp').write_text('constexpr bool OLD = true;\n' +
                ('constexpr bool NEW = true;\n' if commit == 'b' * 40 else ''))
        spec = {'repo': str(self.root), 'out': str(out), 'base': 'a' * 40, 'commit': 'b' * 40, 'step': 'identity_notice'}
        for ending, raises in [('identical', False), ('1 differ', True)]:
            with patch.object(control, 'export', side_effect=export), patch.object(control, 'stage', return_value=out / 'harness'), \
                 patch.object(control, 'run', side_effect=['', '', '\n'.join(['OK x'] * 40 + [ending])]):
                if raises:
                    with self.assertRaisesRegex(ValueError, 'notification only'):
                        control.job(spec, [])
                else:
                    control.job(spec, [])
            code = (out / 'selected/mybot2/main.cpp').read_text()
            self.assertIn('NEW = false', code)
            self.assertIn('OLD = true', code)
            import shutil
            shutil.rmtree(out / 'selected')
            shutil.rmtree(out / 'base')

    def test_pair_request_uses_pinned_commit_unranked_and_budget(self):
        out = self.root / 'job'
        out.mkdir()
        def export(repo, commit, dest, fds):
            dest.mkdir(parents=True)
            (dest / 'main.cpp').write_text('constexpr bool TEST = false;')
        smoke = types.SimpleNamespace(active=lambda: {'id': 61}, main=Mock(return_value=0))
        spec = {'repo': str(self.root), 'out': str(out), 'commit': 'b' * 40, 'step': 'pair-online',
                'previous_id': 61, 'toggle': 'TEST', 'id': 'a1', 'force': True}
        with patch.object(control, 'export', side_effect=export), patch.object(control, 'run'), \
             patch.object(jobs, 'load_module', return_value=smoke):
            control.job(spec, [])
        args = smoke.main.call_args.args[0]
        self.assertNotIn('--ranked', args)
        self.assertEqual(args[args.index('--games') + 1], '60')
        self.assertEqual(args[args.index('--top') + 1], '1')
        self.assertIn('TEST = true', (out / 'selected/mybot2/main.cpp').read_text())
        self.assertIsNone(smoke.check_freeze())

    def test_worker_kind_meow_is_dispatched_once(self):
        path = self.root / 'job'
        jobs.write(path / 'job.json', {'kind': 'meow', 'resources': [], 'locks': str(self.root / 'locks')})
        with patch.object(control, 'job') as job:
            jobs.worker(path)
            jobs.worker(path)
        job.assert_called_once()


if __name__ == '__main__':
    unittest.main()
