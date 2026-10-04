"""Offline short names across runner jobs, comments, and ladder cards."""
import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import jobs
import runner
from card_names import card_ref, unique_slug, valid_slug
import test_loopfix1


class Names(unittest.TestCase):
    setUp = test_loopfix1.LoopFixTests.setUp

    def named_card(self):
        return {**self.card, 'number': 27, 'title': '[Idea] A full passage title',
                'labels': ['name:passage', 'by:ai', 'status:building']}

    def test_rules_and_collision(self):
        card = self.named_card()
        self.assertEqual(card_ref(card), '#27 passage')
        self.assertEqual(card_ref(dict(card, labels=[])), '#27 A full passage title')
        self.assertEqual(unique_slug('Passage', {'passage'}, 'passage'), 'passage-a')
        self.assertTrue(valid_slug(unique_slug('An exceptionallylongword across a map')))
        self.assertFalse(valid_slug('queen-hunt-extra'))

    def test_context_status_and_event_carry_name(self):
        card = self.named_card()
        ctx = self.loop.context(card, self.meta)
        self.assertEqual(ctx['title'], '#27 passage')
        self.assertEqual(ctx['full_title'], card['title'])
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            self.loop.notice(card, 'build started')
        self.assertIn('#27 passage', stream.getvalue())
        self.assertEqual(self.loop.status['27']['name'], 'passage')
        path = Path(ctx['out']) / 'jobs/build'
        jobs.append_event(path, {**ctx, 'step': 'build'}, 'start', 100000)
        event = json.loads((self.loop.out / 'events.jsonl').read_text())
        self.assertEqual(event['title'], '#27 passage')
        self.assertEqual(event['name'], 'passage')

    def test_comments_use_ref_without_doubling_name(self):
        card = self.named_card()
        for text in ('What we tried: #27 passage.\nDid it work: Yes.\nWho decides now: Loop.',
                     'Results for #27 are ready.'):
            with patch.object(self.loop, 'cmd'):
                self.loop.post(card, 'test-' + str(len(card['comments'])), text)
            body = card['comments'][-1]['body']
            self.assertIn('#27 passage', body)
            self.assertNotIn('passage passage', body)
            self.assertIn('[#27 passage](https://github.com/', body)

    def ladder(self, slugs):
        jobs.write(self.loop.out / 'ladder.json', {'pending': {'batch': 1, 'ids': ['42'], 'battles': []}})
        out = Path(self.loop.context(dict(self.card, number=0), self.meta)['out'])
        proposal = {'title': 'Queen hunt', 'summary': 'What we tried: Replay 42.\nDid it work: Supported.\nWho decides now: Loop.',
                    'Area': 'queen', 'Claim': 'Hunt', 'Evidence': 'Replay 42', 'Expected signal': 'Hunting',
                    "What would show it's wrong": 'No hunting'}
        jobs.write(out / 'ladder.json', [{**proposal, 'slug': slug} for slug in slugs])
        def gh(*args, **kwargs):
            if args[:2] == ('issue', 'list') and '--state' in args and args[args.index('--state')+1] == 'open':
                return [{'number': 31, 'title': '[Idea] Hunt', 'labels': ['name:queen-hunt']}]
            return []
        with patch.object(self.loop, 'latest_base', return_value=self.meta['base']), \
             patch.object(self.loop, 'ensure_tree'), patch.object(self.loop, 'available_job', return_value=True), \
             patch.object(self.loop, 'gh', side_effect=gh), patch.object(self.loop, 'cmd') as cmd:
            self.loop.ladder()
        return [call.args[0] for call in cmd.call_args_list if call.args[0][:3] == ['gh', 'issue', 'create']]

    def test_ladder_slugs_unique_across_existing_and_batch(self):
        calls = self.ladder(['queen-hunt', 'queen-hunt'])
        self.assertEqual(len(calls), 2)
        self.assertIn('name:queen-a', calls[0])
        self.assertIn('name:queen-b', calls[1])

    def test_ladder_rejects_invalid_slug(self):
        with self.assertRaisesRegex(ValueError, 'slug'):
            self.ladder(['Queen-Hunt'])
