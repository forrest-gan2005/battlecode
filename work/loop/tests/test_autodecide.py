"""AI decision policy and recovery; external actions are mocked."""
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


class AutoDecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.loop = runner.Loop(argparse.Namespace(repo=str(runner.REPO), out=str(root / 'out'),
                            cards=str(root / 'cards'), dry_run=False, game_env={}))
        self.loop.launched = set()
        self.card = {'number': 18, 'title': '[Idea] Test', 'labels': ['by:ai', 'status:tested'],
                     'comments': []}
        self.meta = {'attempt': 1, 'base': 'a' * 40, 'commit': 'b' * 40, 'phase': 'tested'}
        self.out = Path(self.loop.context(self.card, self.meta)['out'])
        self.result = {'identical_pairs': 10, 'total_pairs': 100,
                       'net': {'held': 0, 'transposed': 0, 'old10': 0},
                       'mechanism_shown': True, 'target_seen': True}
        jobs.write(self.out / 'verdict.json', self.result)
        (self.out / 'verdict.md').write_text('Evidence: the quiet gate blocks growth.')
        self.loop.save(self.card, self.meta)

    def decide(self, result=None):
        if result is not None:
            jobs.write(self.out / 'verdict.json', result)
        with patch.object(self.loop, 'latest_base', return_value='a' * 40), \
             patch.object(self.loop, 'post') as post:
            self.loop.process(self.card)
        return post

    def test_barely_at_boundary_revises_before_loss(self):
        self.result.update(identical_pairs=95)
        self.result['net']['held'] = -9
        post = self.decide(self.result)
        self.assertEqual(post.call_args.kwargs['target'], 'building')
        meta = self.loop.metadata(self.card)
        self.assertEqual(meta['attempt'], 2)
        self.assertEqual(meta['ai_revisions'], 1)
        self.assertIn("didn't fire: 95/100 pairs identical; revising once", post.call_args.kwargs['text'])
        self.assertIn('quiet gate blocks growth', meta['revision_evidence'])
        ctx = self.loop.context(self.card, meta)
        from string import Template
        prompt = Template((runner.HERE / 'prompts/build.md').read_text()).substitute(ctx)
        self.assertIn('quiet gate blocks growth', prompt)
        self.assertIn('make the intended behaviour actually trigger', prompt)

    def test_target_absent_also_revises(self):
        self.result['target_seen'] = False
        post = self.decide(self.result)
        self.assertEqual(post.call_args.kwargs['target'], 'building')
        self.assertIn('target behaviour never appeared', post.call_args.kwargs['text'])

    def test_second_barely_result_closes(self):
        self.meta.update(attempt=2, ai_revisions=1)
        self.loop.save(self.card, self.meta)
        out = Path(self.loop.context(self.card, self.meta)['out'])
        jobs.write(out / 'verdict.json', dict(self.result, target_seen=False))
        post = self.decide()
        self.assertEqual(post.call_args.kwargs['target'], 'inconclusive')
        self.assertTrue(post.call_args.kwargs['close'])
        self.assertEqual(self.loop.metadata(self.card)['attempt'], 2)

    def test_revision_limit_survives_main_refresh(self):
        with patch.object(self.loop, 'latest_base', return_value='c' * 40):
            meta = self.loop.new_attempt(self.card, dict(self.meta, ai_revisions=1,
                                          revision_evidence='Evidence'), 'Main changed.')
        self.assertEqual(meta['ai_revisions'], 1)
        self.assertEqual(meta['revision_evidence'], 'Evidence')

    def test_loss_on_held_or_combined_unseen(self):
        for held, transposed in ((-9, 0), (0, -9), (9, -18)):
            with self.subTest(held=held, transposed=transposed):
                self.loop.save(self.card, self.meta)
                self.result['net'].update(held=held, transposed=transposed)
                post = self.decide(self.result)
                self.assertEqual(post.call_args.kwargs['target'], 'rejected')
                self.assertTrue(post.call_args.kwargs['close'])

    def test_candidate_inclusive_boundaries(self):
        self.result['net'].update(held=9, old10=-9)
        post = self.decide(self.result)
        self.assertEqual(post.call_args.kwargs['target'], 'candidate')
        self.assertIn('One teammate OK', post.call_args.kwargs['text'])
        self.assertFalse(post.call_args.kwargs['close'])

    def test_coin_flip_and_blocked_promotions(self):
        for held, old, mechanism in ((8, 0, True), (-8, 0, True), (9, -10, True), (9, 0, False)):
            with self.subTest(held=held, old=old, mechanism=mechanism):
                self.loop.save(self.card, self.meta)
                self.result['net'].update(held=held, old10=old)
                self.result['mechanism_shown'] = mechanism
                post = self.decide(self.result)
                self.assertIsNone(post.call_args.kwargs['target'])
                self.assertEqual(post.call_args.kwargs['text'], runner.AI_COIN_FLIP)
                self.assertFalse(post.call_args.kwargs['close'])

    def test_humans_and_tasks_untouched(self):
        for labels in (['by:zhe', 'status:tested'], ['by:junsing', 'status:tested'],
                       ['by:ai', 'type:task', 'status:tested']):
            self.card['labels'] = labels
            with patch.object(self.loop, 'post') as post, patch.object(self.loop, 'available_job') as job:
                self.loop.process(self.card)
                post.assert_not_called()
                job.assert_not_called()

    def test_board_includes_existing_tested_ai_only(self):
        human = dict(self.card, number=19, labels=['by:zhe', 'status:tested'])
        task = dict(self.card, number=20, labels=['by:ai', 'type:task', 'status:tested'])
        with patch.object(self.loop, 'gh', side_effect=[[self.card, human, task], [[]]]):
            self.assertEqual([c['number'] for c in self.loop.cards_on_board()], [18])

    def test_legacy_396_of_400_revises_next_poll(self):
        (self.out / 'verdict.json').unlink()
        for name, count, differences in (('held', 160, 0), ('transposed', 160, 1), ('old10', 80, 3)):
            rows = []
            for seed in range(count):
                for tag in ('base', 'candidate'):
                    rows.append({'tag': tag, 'map': name, 'seed': seed, 'side': 0,
                                 'win': int(tag == 'candidate' and seed < differences)})
            jobs.write(self.out / f'{name}.json', rows)
        post = self.decide()
        self.assertIn('396/400', post.call_args.kwargs['text'])
        self.assertEqual(post.call_args.kwargs['target'], 'building')

    def test_legacy_without_barely_counts_recovers_fields(self):
        (self.out / 'verdict.json').unlink()
        with patch.object(self.loop, 'available_job', return_value=False) as job, \
             patch.object(self.loop, 'post') as post:
            self.loop.process(self.card)
        self.assertEqual(job.call_args.args[2], 'verdict-fields')
        post.assert_not_called()

    def test_malformed_fields_cannot_promote(self):
        for update in ({'target_seen': 'false'}, {'identical_pairs': 101}, {'total_pairs': 0},
                       {'net': {'held': 9}}, {'mechanism_shown': 1}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.decide(dict(self.result, **update))

    def test_revision_crash_does_not_start_another_attempt(self):
        self.decide(dict(self.result, target_seen=False))
        with patch.object(self.loop, 'latest_base') as base, patch.object(self.loop, 'post') as post:
            self.loop.process(self.card)
        base.assert_not_called()
        self.assertEqual(post.call_args.kwargs['target'], 'building')
        self.assertEqual(self.loop.metadata(self.card)['attempt'], 2)

    def test_failed_revision_post_keeps_one_attempt(self):
        jobs.write(self.out / 'verdict.json', dict(self.result, target_seen=False))
        with patch.object(self.loop, 'latest_base', return_value='a' * 40), \
             patch.object(self.loop, 'post', side_effect=RuntimeError('interrupted')):
            with self.assertRaises(RuntimeError):
                self.loop.process(self.card)
        meta = self.loop.metadata(self.card)
        self.assertEqual(meta['attempt'], 2)
        self.assertEqual(meta['ai_pending']['target'], 'building')
        with patch.object(self.loop, 'latest_base') as base, patch.object(self.loop, 'post') as post:
            self.loop.process(self.card)
        base.assert_not_called()
        self.assertEqual(post.call_args.kwargs['key'], 'ai-decision-1')

    def test_short_comment_deduplicates_and_recovers_closure(self):
        with patch.object(self.loop, 'board') as board, patch.object(self.loop, 'cmd') as cmd:
            self.loop.post(self.card, 'ai-decision-1', 'Worse; closing.', target='rejected', close=True,
                           metadata=dict(self.meta, key='tested-1'))
            self.loop.post(self.card, 'ai-decision-1', 'Worse; closing.', target='rejected', close=True,
                           metadata=dict(self.meta, key='tested-1'))
        comments = [call for call in cmd.call_args_list if call.args[0][:3] == ['gh', 'issue', 'comment']]
        closes = [call for call in cmd.call_args_list if call.args[0][:3] == ['gh', 'issue', 'close']]
        self.assertEqual(runner.records(self.card)[0]['key'], 'ai-decision-1')
        self.assertEqual(len(comments), 1)
        self.assertEqual(len(closes), 2)
        self.assertEqual(self.card['comments'][0]['body'].splitlines()[0], 'Worse; closing.')
        self.assertEqual(board.call_count, 2)

    def test_new_verdict_applies_immediately_after_tested_post(self):
        self.card['labels'] = ['by:ai', 'status:testing']
        self.meta.update(toggle='TEST')
        self.loop.save(self.card, self.meta)
        jobs.write(self.out / 'build.json', {})
        (self.out / 'verdict.md').write_text('What we tried: A change.\nDid it work: It fires.\nWho decides now: The loop.')
        self.result['net']['held'] = 9
        jobs.write(self.out / 'verdict.json', self.result)
        with patch.object(self.loop, 'latest_base', return_value=self.meta['base']), \
             patch.object(self.loop, 'available_job', return_value=True), patch.object(self.loop, 'post') as post:
            self.loop.process(self.card)
        self.assertEqual(post.call_args_list[0].kwargs['target'], 'tested')
        self.assertEqual(post.call_args_list[1].kwargs['target'], 'candidate')
        self.assertEqual(post.call_args_list[0].kwargs['metadata']['verdict'], self.result)


if __name__ == '__main__':
    unittest.main()
