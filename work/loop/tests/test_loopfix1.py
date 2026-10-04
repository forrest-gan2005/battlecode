"""Card presentation and quiet progress regressions; all external actions are mocked."""
import argparse
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jobs
import runner


class LoopFixTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.loop = runner.Loop(argparse.Namespace(
            repo=str(runner.REPO), out=str(self.root / 'out'),
            cards=str(self.root / 'cards'), dry_run=False, game_env={}))
        self.loop.locks = self.root / 'locks'
        self.loop.launched = set()
        self.card = {'number': 15, 'title': '[Idea] Test', 'body': '', 'comments': [],
                     'labels': ['by:ai', 'status:building']}
        self.meta = {'attempt': 1, 'base': 'a' * 40}
        self.out = Path(self.loop.context(self.card, self.meta)['out'])

    def test_title_prefixes(self):
        for title in ('Once our queen is dead', '[Idea] Once our queen is dead',
                      '[Task] Once our queen is dead',
                      ' [idea] [TASK][Idea]  Once our queen is dead  '):
            with self.subTest(title=title):
                self.assertEqual(runner.idea_title(title), '[Idea] Once our queen is dead')
        self.assertEqual(runner.idea_title('Use [Task] evidence'), '[Idea] Use [Task] evidence')
        with self.assertRaises(ValueError):
            runner.idea_title('[Idea] [Task] ')

    def test_ladder_normalizes_title_and_cached_approval_summary(self):
        pending = {'batch': 1, 'ids': ['42'], 'battles': []}
        jobs.write(self.loop.out / 'ladder.json', {'pending': pending})
        ladder_card = dict(self.card, number=0)
        out = Path(self.loop.context(ladder_card, self.meta)['out'])
        proposal = {'title': '[Idea] [Task] Once our queen is dead',
                    'summary': 'What we tried: Review game 42.\nDid it work: A supported idea.\n'
                               'Who decides now: Any teammate. One OK lets the loop build it.',
                    'Area': 'queen', 'Claim': 'Keep growing', 'Evidence': 'Replay 42',
                    'Expected signal': 'More growth', "What would show it's wrong": 'No growth'}
        jobs.write(out / 'ladder.json', [proposal])
        with patch.object(self.loop, 'latest_base', return_value=self.meta['base']), \
             patch.object(self.loop, 'ensure_tree'), \
             patch.object(self.loop, 'available_job', return_value=True), \
             patch.object(self.loop, 'gh', return_value=[]), \
             patch.object(self.loop, 'cmd') as cmd:
            self.loop.ladder()
        argv = cmd.call_args.args[0]
        self.assertEqual(argv[argv.index('--title') + 1], '[Idea] Once our queen is dead')
        body = Path(argv[argv.index('--body-file') + 1]).read_text()
        self.assertEqual(body.splitlines()[2], 'Who decides now: ' + runner.AI_DECISION)
        self.assertNotIn('One OK lets the loop build it', body)
        self.assertIn('status:ready', argv)
        prompt = (runner.HERE / 'prompts/ladder.md').read_text()
        self.assertIn('Who decides now: ' + runner.AI_DECISION, prompt)

    def test_attempt_and_build_completion_are_local(self):
        with patch.object(self.loop, 'latest_base', return_value=self.meta['base']), \
             patch.object(self.loop, 'post') as post:
            meta = self.loop.new_attempt(self.card, {}, 'First build.')
            post.assert_not_called()
        self.assertEqual(self.loop.metadata(self.card), meta)
        self.assertIn('First build.', self.loop.status['15']['step'])
        jobs.write(self.out / 'jobs/build/job.json', {})
        jobs.write(self.out / 'built.json', {'commit': 'b' * 40, 'toggle': 'TEST'})
        with patch.object(self.loop, 'prepare', return_value=self.loop.context(self.card, meta)), \
             patch.object(self.loop, 'available_job', side_effect=[True, False]), \
             patch.object(self.loop, 'cmd'), patch.object(self.loop, 'post') as post:
            self.loop.process(self.card)
            post.assert_not_called()
        self.assertTrue(self.loop.metadata(self.card)['pushed'])
        self.assertIn('toggle-off check passed', self.loop.status['15']['step'])

    def test_job_start_wait_done_never_comment(self):
        for step in ('clarify', 'build', 'mechanism', 'outcome', 'task'):
            with self.subTest(step=step), \
                 patch.object(self.loop, 'post') as post, \
                 patch.object(self.loop, 'cmd', return_value=''), \
                 patch.object(runner.subprocess, 'Popen') as launch:
                self.loop.launched = set()
                launch.return_value.pid = 1234
                self.assertFalse(self.loop.job(self.card, self.meta, step))
                self.assertEqual(self.loop.status['15']['step'], 'started ' + step)
                self.assertEqual(self.loop.status['15']['pid'], 1234)
                path = self.out / 'jobs' / step
                self.assertEqual(self.loop.status['15']['job'], str(path))
                with patch.object(runner, 'busy', return_value=True):
                    self.assertFalse(self.loop.job(self.card, self.meta, step))
                self.assertEqual(self.loop.status['15']['step'], step + ' running')
                jobs.write(path / 'done.json', {'ok': True})
                self.assertTrue(self.loop.job(self.card, self.meta, step))
                self.assertEqual(self.loop.status['15']['step'], step + ' done')
                post.assert_not_called()
                launch.assert_called_once()
        with jobs.lock(self.loop.locks / 'ai.lock'), patch.object(self.loop, 'post') as post:
            self.assertFalse(self.loop.job(self.card, self.meta, 'look'))
            self.assertIn('waiting for ai lock', self.loop.status['15']['step'])
            post.assert_not_called()

    def test_restart_discards_only_pending_routine_comments(self):
        path = self.loop.out / 'card-15/pending-post.json'
        for key in ('attempt-1', 'built-1', 'batch-1-mechanism', 'batch-1-outcome'):
            with self.subTest(key=key):
                jobs.write(path, {'key': key, 'text': 'Started a step.', 'metadata': self.meta})
                with patch.object(self.loop, 'prepare', return_value=self.loop.context(self.card, self.meta)), \
                     patch.object(self.loop, 'latest_base', return_value=self.meta['base']), \
                     patch.object(self.loop, 'available_job', return_value=False), \
                     patch.object(self.loop, 'post') as post:
                    self.loop.save(self.card, self.meta)
                    self.loop.process(self.card)
                    post.assert_not_called()
                self.assertFalse(path.exists())

    def test_human_facing_pending_posts_are_recovered(self):
        for key, kind, ask in (('questions-1', None, True), ('look-1', 'check', False),
                               ('tested-1', 'test', False), ('task-tested-1', 'check', False),
                               ('build-failed-1', None, False), ('task-failed-1', 'check', False),
                               ('old-base-1', None, False), ('candidate-card-15', None, False)):
            with self.subTest(key=key):
                self.card['comments'] = []
                pending = {'key': key, 'text': 'Questions before we build\nWhich behaviour?' if ask
                           else 'What we tried: Check.\nDid it work: See evidence.\nWho decides now: A teammate.',
                           'target': None, 'kind': kind, 'ask': ask, 'metadata': self.meta}
                jobs.write(self.loop.out / 'card-15/pending-post.json', pending)
                with patch.object(self.loop, 'board') as board, patch.object(self.loop, 'cmd') as cmd:
                    self.loop.process(self.card)
                if ask or kind:
                    board.assert_called_once()
                    cmd.assert_not_called()
                else:
                    cmd.assert_called_once()
                self.assertEqual(runner.records(self.card)[0]['key'], key)

    def test_progress_reaches_status_and_heartbeat(self):
        def progress(card):
            self.loop.notice(card, 'mechanism waiting for batch lock')
        with patch.object(self.loop, 'cards_on_board', return_value=[self.card]), \
             patch.object(self.loop, 'process', side_effect=progress), \
             patch.object(self.loop, 'ladder'), patch.object(self.loop, 'board') as board, \
             patch.object(self.loop, 'post') as post:
            self.loop.tick()
            post.assert_not_called()
        snapshot = jobs.read(self.loop.out / 'status.json')
        self.assertEqual(snapshot['cards']['15']['step'], 'mechanism waiting for batch lock')
        self.assertEqual(board.call_args.args[0], 'heartbeat')
        self.assertIn('#15: mechanism waiting for batch lock', board.call_args.args[-1])


if __name__ == '__main__':
    unittest.main()
