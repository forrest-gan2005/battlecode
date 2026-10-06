"""Offline: any teammate may answer for a by:zhe card; tool posts under jun's login still never count."""
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

AFTER = '2026-10-04T00:00:00Z'
ZHE, QWQ, JUN = 'zhex0121', 'forrest-gan2005', 'juntegral'
MARKER = '<!-- card-loop {"key": "look-1", "phase": "look", "attempt": 1} -->'
# What tools write under jun's GitHub login.
TOOL_POSTS = ('Results are in.\n\n' + MARKER,
              'Answer from QWQ: go\n\n' + MARKER,
              'Questions before we build\n1. What happens near a wall?',
              '[check] by `card-loop` · ② Board loop\nWhat we tried: a small run.',
              '[test] by `card-loop` · ② Board loop\nWhat we tried: the outcome run.',
              '**Online check: no gain, no clear harm.**\n\nPosted by Claude for jun.',
              'Applied set_state to #43.\n\nvia /meow by jun',
              'Answer from jun (written by Claude acting for him): revise.')


def bodies(c, zhe=True):
    return [r['body'] for r in runner.human_replies(c, AFTER, zhe=zhe)]


class WhoCounts(unittest.TestCase):
    def test_teammate_logins_count_on_a_zhe_card(self):
        c = card(by='zhe', comments=[comment('zhe says', who=ZHE), comment('qwq says', who=QWQ),
                                     comment('stranger says', who='someone')])
        self.assertEqual(bodies(c), ['zhe says', 'qwq says'])

    def test_relayed_answers_name_any_teammate(self):
        relayed = ['Answer from Zhe: 就是这个', 'Answer from QWQ: build it as asked', 'Answer from jun: 그대로 가자',
                   'Reply from qwq : ok', 'Answer from jun: go\n\nvia /meow by jun']
        c = card(by='zhe', comments=[comment(b, who=JUN) for b in relayed]
                 + [comment('Answer from QWQ: from the bot account', who='meow[bot]', kind='Bot'),
                    comment('Answer from Claude: not a teammate', who=JUN),
                    comment('I have an Answer from QWQ: not at the start', who=JUN)])
        self.assertEqual(bodies(c), relayed + ['Answer from QWQ: from the bot account'])

    def test_tool_posts_under_juns_login_never_count_on_a_zhe_card(self):
        c = card(by='zhe', comments=[comment(b, who=JUN) for b in TOOL_POSTS + ('a bare comment',)])
        self.assertEqual(bodies(c), [])

    def test_zhe_card_is_never_looser_than_other_cards(self):
        every = [comment(b, who=who, kind=kind) for b in TOOL_POSTS + ('a bare comment', 'Answer from QWQ: go')
                 for who, kind in ((ZHE, 'User'), (QWQ, 'User'), (JUN, 'User'), ('someone', 'User'), ('meow[bot]', 'Bot'))]
        strict, loose = bodies(card(by='zhe', comments=every)), bodies(card(by='qwq', comments=every), zhe=False)
        self.assertTrue(strict)
        self.assertLess(len(strict), len(loose))
        self.assertTrue(all(b in loose for b in strict))
        # Marker, question and check/test posts stay out whoever posts them.
        self.assertFalse(any(b in strict or b in loose for b in TOOL_POSTS[:5]))

    def test_other_cards_keep_their_rule(self):
        c = card(by='qwq', comments=[comment('a bare comment', who=JUN), comment('anyone', who='someone'),
                                     comment(TOOL_POSTS[0], who=JUN), comment(TOOL_POSTS[2], who=JUN),
                                     comment('status', who='bot[bot]', kind='Bot')])
        self.assertEqual(bodies(c, zhe=False), ['a bare comment', 'anyone'])

    def test_login_overrides(self):
        c = card(by='zhe', comments=[comment('zhe', who='zhe-alt'), comment('qwq', who='qwq-alt'),
                                     comment('old', who=QWQ), comment('no login', who='')])
        with patch.dict(os.environ, {'LOOP_ZHE_LOGIN': 'zhe-alt', 'LOOP_QWQ_LOGIN': 'qwq-alt'}):
            self.assertEqual(bodies(c), ['zhe', 'qwq'])
        with patch.dict(os.environ, {'LOOP_QWQ_LOGIN': ''}):
            self.assertEqual(bodies(c), [])


class ProxySteps(unittest.TestCase):
    setUp = test_runner.Tests.setUp
    tearDown = test_runner.Tests.tearDown

    def shared_card(self, status, *replies):
        c = card(43, status, 'zhe')
        c['labels'].append({'name': 'by:qwq'})
        self.meta = {'attempt': 1, 'base': 'a' * 40, 'phase': 'look'}
        first = ('Questions before we build\nZhe: when should she leave?' if status == 'needs-info'
                 else '<!-- card-loop ' + json.dumps(self.meta) + ' -->')
        c['comments'] = [comment(first, AFTER, JUN), *replies]
        return c

    def test_questions_accept_a_teammate(self):
        for reply, moved in ((comment('leave when the exit is closer', who=QWQ), True),
                             (comment('Answer from QWQ: leave when the exit is closer', who=JUN), True),
                             (comment('Answer from jun: Zhe is asleep, build the simple version', who=JUN), True),
                             (comment('leave when the exit is closer', who=ZHE), True),
                             (comment(TOOL_POSTS[5], who=JUN), False),
                             (comment('a bare comment', who=JUN), False)):
            with self.subTest(body=reply['body'], who=reply['user']['login']):
                with patch.object(self.loop, 'transition') as transition:
                    self.loop.process(self.shared_card('needs-info', reply))
                if moved:
                    transition.assert_called_once()
                    self.assertEqual(transition.call_args.args[1], 'building')
                else:
                    transition.assert_not_called()

    def look(self, reply, decision):
        c = self.shared_card('needs-look', reply)
        out = Path(self.loop.context(c, self.meta)['out'])
        jobs.write(out / 'look.json', {'replays': ['a', 'b']})
        def job(*args, **kwargs):
            jobs.write(out / 'reply.json', {'decision': decision})
            return True
        with patch.object(self.loop, 'available_job', side_effect=job) as available, \
                patch.object(self.loop, 'transition') as transition, \
                patch.object(self.loop, 'new_attempt') as new_attempt:
            self.loop.process(c)
        return available, transition, new_attempt

    def test_look_reply_from_a_teammate_is_classified(self):
        for reply in (comment('that is what he meant', who=QWQ), comment('Answer from jun: looks right', who=JUN),
                      comment('Answer from QWQ: looks right', who=JUN), comment('yes', who=ZHE)):
            with self.subTest(body=reply['body']):
                available, transition, new_attempt = self.look(reply, 'ok')
                self.assertEqual(available.call_args.args[1]['replies'], [reply])
                transition.assert_called_once()
                self.assertEqual(transition.call_args.args[1], 'testing')
        available, transition, new_attempt = self.look(comment('hunters should not stand down', who=QWQ), 'revise')
        new_attempt.assert_called_once()
        self.assertEqual(transition.call_args.args[1], 'building')

    def test_look_keeps_waiting_on_tool_posts(self):
        for body in TOOL_POSTS + ('a bare comment',):
            with self.subTest(body=body):
                available, transition, new_attempt = self.look(comment(body, who=JUN), 'ok')
                available.assert_not_called()
                transition.assert_not_called()

    def test_dry_status_names_teammates(self):
        c = self.shared_card('needs-look')
        self.loop.dry(c)
        self.assertIn('Zhe or a teammate', self.loop.status['43']['step'])
        self.loop.dry(self.shared_card('needs-info', comment('leave when the exit is closer', who=QWQ)))
        self.assertEqual(self.loop.status['43']['step'], 'human answer found → building')
        self.loop.dry(self.shared_card('needs-info', comment('a bare comment', who=JUN)))
        self.assertEqual(self.loop.status['43']['step'], 'wait for human answer after questions')


if __name__ == '__main__':
    unittest.main()
