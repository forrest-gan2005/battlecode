"""Task route regression tests; AI, games and remote operations are mocked."""
import datetime
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jobs
import runner
import test_runner
from test_runner import card, comment
import test_loop

spec = importlib.util.spec_from_file_location('board', runner.REPO / 'work/board.py')
board = importlib.util.module_from_spec(spec)
spec.loader.exec_module(board)


def task(n=1, status='building', by='zhe'):
    c = card(n, status, by)
    c['title'] = '[Task] Refactor sonar'
    c['labels'].append({'name': 'type:task'})
    return c


# Use the existing setup without collecting its tests again.
class TaskTests(unittest.TestCase):
    setUp = test_runner.Tests.setUp
    tearDown = test_runner.Tests.tearDown

    def setup_task(self):
        c = task()
        meta = {'attempt': 1, 'base': 'a' * 40}
        self.loop.save(c, meta)
        ctx = self.loop.context(c, meta)
        out = Path(ctx['out'])
        jobs.write(out / 'task.json', {'needs_info': False, 'check': ['python3', 'work/check.py']})
        jobs.write(out / 'built.json', {'commit': 'b' * 40, 'task_check': {'passed': True, 'note': 'round trips pass'}})
        return c, meta, ctx, out

    def test_priority_shared_with_board_and_oldest_first(self):
        cs = [card(1, by='zhe'), card(2), card(3, by='ai'), task(5, by='ai'), task(4)]
        for key in (runner.priority, board.priority):
            self.assertEqual([c['number'] for c in sorted(cs, key=key)], [4, 5, 1, 2, 3])
        cs[-1]['createdAt'] = '2026-10-03T00:00:00Z'
        for key in (runner.priority, board.priority):
            self.assertEqual([c['number'] for c in sorted(cs, key=key)], [5, 4, 1, 2, 3])

    def test_board_next_picks_task_before_zhe(self):
        with patch.object(board, 'gh', side_effect=[[card(by='zhe'), task(2, 'ready', 'ai')], []]), \
             patch('builtins.print') as output:
            board.cmd_next(type('Args', (), {'state': None, 'wf': None})())
        self.assertTrue(output.call_args_list[0].args[0].startswith('#2 [Task]'))

    def test_board_discovers_task_label_and_filters_inactive(self):
        c = task(status='ready')
        with patch.object(self.loop, 'gh', side_effect=[[card(2), c, task(3, 'tested')], [], [], []]):
            self.assertEqual([x['number'] for x in self.loop.cards_on_board()], [1, 2])
            self.assertTrue(runner.is_task(c))

    def test_zhe_task_ready_skips_clarify(self):
        c, meta, ctx, out = self.setup_task()
        c['labels'][0]['name'] = 'status:ready'
        with patch.object(self.loop, 'ensure_tree'), patch.object(self.loop, 'available_job') as job, \
             patch.object(self.loop, 'transition') as transition:
            self.loop.process(c)
        job.assert_not_called()
        transition.assert_called_once_with(c, 'building')

    def test_task_build_goes_directly_to_tested(self):
        c, meta, ctx, out = self.setup_task()
        with patch.object(self.loop, 'latest_base', return_value=meta['base']), \
             patch.object(self.loop, 'prepare', return_value=ctx), \
             patch.object(self.loop, 'available_job', return_value=True) as job, \
             patch.object(self.loop, 'cmd') as cmd, patch.object(self.loop, 'post') as post:
            self.loop.process(c)
        job.assert_called_once()
        self.assertEqual(job.call_args.args[0], c)
        self.assertEqual(job.call_args.args[2], 'task')
        cmd.assert_called_once_with(['git', 'push', '--force', 'origin', 'b' * 40 + ':refs/heads/card/1'], ctx['tree'])
        self.assertEqual(post.call_args.kwargs['target'], 'tested')
        self.assertEqual(post.call_args.kwargs['kind'], 'check')
        runner.summary_text(post.call_args.args[2])
        self.assertEqual(self.loop.metadata(c)['phase'], 'tested')

    def test_identity_failure_returns_ready_with_exact_note(self):
        c, meta, ctx, out = self.setup_task()
        with patch.object(self.loop, 'available_job', side_effect=RuntimeError('identity failed')), \
             patch.object(self.loop, 'post') as post, patch.object(self.loop, 'cmd') as cmd:
            self.loop.build_task(c, meta, ctx)
        cmd.assert_not_called()
        self.assertEqual(post.call_args.kwargs['target'], 'ready')
        self.assertIn('this changes play; make it an idea card or fix it', post.call_args.args[2])
        self.assertTrue(self.loop.metadata(c)['failed'])

    def test_completion_failure_returns_ready_without_push(self):
        c, meta, ctx, out = self.setup_task()
        with patch.object(self.loop, 'available_job', side_effect=RuntimeError('task-specific check failed')), \
             patch.object(self.loop, 'post') as post, patch.object(self.loop, 'cmd') as cmd:
            self.loop.build_task(c, meta, ctx)
        cmd.assert_not_called()
        self.assertEqual(post.call_args.kwargs['target'], 'ready')
        self.assertIn('task-specific check failed', post.call_args.args[2])

    def test_unclear_task_asks_then_fresh_attempt_after_answer(self):
        c, meta, ctx, out = self.setup_task()
        jobs.write(out / 'task.json', {'needs_info': True})
        (out / 'questions.md').write_text('Questions before we build\nWhich messages must be rejected?')
        with patch.object(self.loop, 'available_job', return_value=True), patch.object(self.loop, 'post') as post:
            self.loop.build_task(c, meta, ctx)
        self.assertEqual(post.call_args.kwargs['target'], 'needs-info')
        self.assertTrue(post.call_args.kwargs['ask'])
        c['labels'][0]['name'] = 'status:needs-info'
        c['comments'] = [comment('Questions before we build', '2026-10-04T00:00:00Z'), comment('Reject invalid signatures', who='someone-else')]
        with patch.object(self.loop, 'transition') as transition:
            self.loop.process(c)
        transition.assert_not_called()  # Zhe's card: only Zhe's answer counts
        c['comments'].append(comment('Reject invalid signatures', who='zhex0121'))
        with patch.object(self.loop, 'transition') as transition:
            self.loop.process(c)
        transition.assert_called_once_with(c, 'building')
        c['labels'][0]['name'] = 'status:building'
        with patch.object(self.loop, 'latest_base', return_value=meta['base']), \
             patch.object(self.loop, 'post'), patch.object(self.loop, 'prepare', return_value=ctx), \
             patch.object(self.loop, 'build_task') as build:
            self.loop.process(c)
        self.assertEqual(build.call_args.args[1]['attempt'], 2)

    def test_task_requires_both_ai_and_batch_leases(self):
        c, meta, ctx, out = self.setup_task()
        for resource in ('ai', 'batch'):
            with jobs.lock(self.loop.locks / f'{resource}.lock'), patch.object(runner.subprocess, 'Popen') as launch:
                self.assertFalse(self.loop.available_job(c, meta, 'task'))
                launch.assert_not_called()
        jobs.write(out / 'jobs/task/done.json', {'ok': True})
        with patch.object(runner.subprocess, 'Popen') as launch:
            self.assertTrue(self.loop.available_job(c, meta, 'task'))
            launch.assert_not_called()

    def test_task_job_uses_task_prompt_and_both_resources(self):
        c, meta, ctx, out = self.setup_task()
        with patch.object(self.loop, 'cmd', return_value=''), patch.object(self.loop, 'post'), \
             patch.object(runner.subprocess, 'Popen'):
            self.assertFalse(self.loop.available_job(c, meta, 'task'))
        spec = jobs.read(out / 'jobs/task/job.json')
        self.assertEqual(spec['resources'], ['ai', 'batch'])
        text = Path(spec['prompt']).read_text()
        self.assertIn('Implement this task card without changing play', text)
        self.assertIn('card_1_task_check.py', text)
        self.assertIn('latest main release', text)

    def test_old_base_task_results_are_annotated(self):
        c, meta, ctx, out = self.setup_task()
        with patch.object(self.loop, 'available_job', return_value=True), \
             patch.object(self.loop, 'latest_base', return_value='c' * 40), \
             patch.object(self.loop, 'cmd'), patch.object(self.loop, 'post') as post:
            self.loop.build_task(c, meta, ctx)
        self.assertTrue(meta['old_base'])
        self.assertIn('recorded old base', post.call_args.args[2])
        self.assertIn('refresh before shipping', post.call_args.args[2])

    def test_candidate_task_blocks_stale_base_before_github(self):
        c, meta, ctx, out = self.setup_task()
        meta.update(phase='tested', commit='b' * 40)
        with patch.object(self.loop, 'latest_base', return_value='c' * 40), \
             patch.object(self.loop, 'gh') as gh:
            self.loop.candidate(c, meta)
        gh.assert_not_called()

    def test_candidate_keeps_implementation_tree_and_usual_approval(self):
        c, meta, ctx, out = self.setup_task()
        meta.update(phase='tested', commit='b' * 40)
        class BeforeFreeze(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.datetime(2026, 10, 4, tzinfo=tz)
        with patch.object(runner.dt, 'datetime', BeforeFreeze), \
             patch.object(self.loop, 'latest_base', return_value=meta['base']), \
             patch.object(self.loop, 'gh', side_effect=[[], {'tree': {'sha': 'implementation-tree'}}, [],
                                                       {'sha': 'new-tree'}, {'sha': 'candidate-commit'}, {}]) as gh, \
             patch.object(self.loop, 'cmd') as cmd, patch.object(self.loop, 'post'):
            self.loop.candidate(c, meta)
        payload = gh.call_args_list[3].kwargs['payload']
        self.assertEqual(payload['base_tree'], 'implementation-tree')
        self.assertEqual(len(payload['tree']), 1)
        self.assertTrue(payload['tree'][0]['path'].startswith('candidates/'))
        self.assertEqual(cmd.call_args.args[0][:3], ['gh', 'pr', 'create'])
        self.assertIn('required teammate approvers', (out / 'candidate-pr.md').read_text())


class TaskWorkerTests(unittest.TestCase):
    setUp = test_loop.JobTests.setUp

    def setup_worker(self, needs_info=False):
        tree = Path(self.ctx['tree'])
        (tree / 'mybot2').mkdir(parents=True)
        (tree / 'mybot2/main.cpp').write_text('int main() {}')
        jobs.write(self.out / 'task.json', {'needs_info': needs_info, 'check': ['python3', 'work/check.py']})
        (self.out / 'prompt.md').write_text('task')
        (self.out / 'ai.jsonl').write_text('{"type":"result","is_error":false}\n')
        return dict(self.ctx, step='task', prompt=str(self.out / 'prompt.md'), log=str(self.out / 'ai.jsonl'))

    def fake_run(self, passed=True, identity=None):
        def run(argv, cwd, env=None, **kwargs):
            if argv[0] == 'c++':
                self.assertEqual(env['LOOP_BATCH_LEASE'], '1')
                return ''
            if str(argv[1]).endswith('ident.py'):
                self.assertEqual(env['REF'], 'base')
                self.assertEqual(env['IDENT_MAPS'], jobs.OLD_MAPS)
                self.assertEqual(env['IDENT_SEEDS'], '2')
                return identity if identity is not None else 'OK comparison\n' * 40 + 'identical\n'
            if argv == ['python3', 'work/check.py']:
                jobs.write(self.out / 'task-check.json', {'passed': passed, 'note': 'fake messages rejected'})
                return ''
            if argv[:2] == ['git', 'rev-parse']:
                return 'b' * 40
            if argv[:3] == ['git', 'branch', '--show-current']:
                return 'card/3'
            return ''
        return run

    def test_verified_task_build_without_toggle_or_ab(self):
        spec = self.setup_worker()
        with patch.object(jobs, 'run', side_effect=self.fake_run()) as run:
            jobs.ai(spec, [])
        built = jobs.read(self.out / 'built.json')
        self.assertEqual(built['commit'], 'b' * 40)
        self.assertTrue(built['task_check']['passed'])
        self.assertNotIn('toggle', built)
        self.assertFalse(any('ab3.py' in str(call.args[0]) for call in run.call_args_list))

    def test_zero_exit_identity_diff_cannot_pass_task(self):
        spec = self.setup_worker()
        with patch.object(jobs, 'run', side_effect=self.fake_run(identity='OK a\nDIFF b\n1 differ\n')):
            with self.assertRaisesRegex(ValueError, 'this changes play; make it an idea card or fix it'):
                jobs.ai(spec, [])
        self.assertFalse((self.out / 'built.json').exists())

    def test_task_check_false_cannot_pass(self):
        spec = self.setup_worker()
        with patch.object(jobs, 'run', side_effect=self.fake_run(passed=False)):
            with self.assertRaisesRegex(ValueError, 'task-specific check failed'):
                jobs.ai(spec, [])
        self.assertFalse((self.out / 'built.json').exists())

    def test_stale_check_evidence_cannot_pass(self):
        spec = self.setup_worker()
        jobs.write(self.out / 'task-check.json', {'passed': True, 'note': 'old evidence'})
        def run(argv, *args, **kwargs):
            if argv == ['python3', 'work/check.py']:
                return ''
            return self.fake_run()(argv, *args, **kwargs)
        with patch.object(jobs, 'run', side_effect=run):
            with self.assertRaisesRegex(ValueError, 'task-specific check failed'):
                jobs.ai(spec, [])

    def test_unclear_task_runs_no_compile_or_games(self):
        spec = self.setup_worker(needs_info=True)
        with patch.object(jobs, 'run') as run:
            jobs.ai(spec, [])
            run.assert_not_called()
        self.assertFalse((self.out / 'built.json').exists())
