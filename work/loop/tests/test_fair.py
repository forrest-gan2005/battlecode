"""Fair starts and shared lock ordering; all remote work is mocked."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_runner
from test_runner import card
import runner
from fair_queue import COUNTER, lock_taken, order_cards, read_fair, served


class FairTests(unittest.TestCase):
    setUp = test_runner.Tests.setUp
    tearDown = test_runner.Tests.tearDown

    def test_rotation_and_oldest_within_author(self):
        cs = [card(4, by='zhe'), card(3, by='junsing'), card(2, by='qwq'), card(1, by='zhe'), card(5, by='qwq')]
        self.assertEqual([c['number'] for c in order_cards(cs)], [1, 2, 3, 4, 5])

    def test_never_served_and_least_recent(self):
        cs = [card(1, by='zhe'), card(2, by='qwq'), card(3, by='junsing')]
        history = {'by:zhe': '2026-10-05T01:00:00+00:00', 'by:qwq': '2026-10-05T00:00:00+00:00'}
        self.assertEqual([c['number'] for c in order_cards(cs, history)], [3, 2, 1])

    def test_ai_share_tasks_and_no_humans(self):
        cs = [card(n, by='zhe') for n in range(1, 6)] + [card(6, by='ai')]
        self.assertEqual([c['number'] for c in order_cards(cs)], [1, 2, 3, 6, 4, 5])
        task = card(8, by='ai'); task['labels'].append({'name': 'type:task'})
        self.assertEqual([c['number'] for c in order_cards(cs + [task], {COUNTER: 3})][:2], [8, 6])
        self.assertEqual(order_cards([cs[-1]])[0]['number'], 6)

    def test_record_only_actual_ready_start(self):
        c = card(1, by='qwq')
        with patch.object(self.loop, 'board'):
            self.loop.transition(c, 'needs-info')
            history = read_fair(self.loop.fair_path)
            self.assertEqual(history[COUNTER], 1)
            self.assertIn('by:qwq', history)
            c['labels'][0]['name'] = 'status:needs-info'
            self.loop.transition(c, 'building')
            self.assertEqual(read_fair(self.loop.fair_path), history)
            ai = card(2, by='ai')
            self.loop.transition(ai, 'building')
            self.assertEqual(read_fair(self.loop.fair_path)[COUNTER], 0)

    def test_failed_transition_does_not_count(self):
        with patch.object(self.loop, 'board', side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError):
                self.loop.transition(card(1), 'building')
        self.assertFalse(self.loop.fair_path.exists())

    def test_lock_offer_order_in_one_poll(self):
        cs = [card(1, 'building', by='zhe'), card(2, 'testing', by='qwq'), card(3, 'building', by='junsing')]
        runner.write(self.loop.fair_path, {'by:zhe': '2026-10-05T01:00:00+00:00', 'by:qwq': '2026-10-05T00:00:00+00:00'})
        offered = []
        def offer(c):
            offered.append(c['number'])
            self.loop.available_job(c, {'attempt': 1, 'base': 'a' * 40}, 'build' if runner.state(c) == 'building' else 'outcome')
        with patch('meow_control.controls', return_value=False), patch.object(self.loop, 'cards_on_board', return_value=cs), \
             patch.object(self.loop, 'process', side_effect=offer), patch.object(self.loop, 'ladder'), \
             patch.object(self.loop, 'running_notices'), patch.object(self.loop, 'board'), \
             patch.object(self.loop, 'available_job', return_value=False):
            self.loop.tick()
        self.assertEqual(offered, [3, 2, 1])

    def test_board_uses_history(self):
        import test_tasks
        board = test_tasks.board
        cs = [card(1, by='zhe'), card(2, by='qwq')]
        with patch.object(board, 'read_fair', return_value={'by:zhe': '2026-10-05T01:00:00+00:00'}), \
             patch.object(board, 'gh', side_effect=[cs, []]), patch('builtins.print') as output:
            board.cmd_next(type('Args', (), {'state': None, 'wf': None})())
        self.assertTrue(output.call_args_list[0].args[0].startswith('#2 '))

    def test_missing_history(self):
        self.assertEqual(read_fair(self.root / 'missing.json'), {})

    def test_reorders_after_starts_within_one_poll(self):
        cs = [card(n, by='zhe') for n in range(1, 5)] + [card(5, by='ai')]
        started = []
        def start(c):
            started.append(c['number'])
            self.loop.transition(c, 'building')
        with patch('meow_control.controls', return_value=False), patch.object(self.loop, 'cards_on_board', return_value=cs), \
             patch.object(self.loop, 'process', side_effect=start), patch.object(self.loop, 'ladder'), \
             patch.object(self.loop, 'running_notices'), patch.object(self.loop, 'board'):
            self.loop.tick()
        self.assertEqual(started, [1, 2, 3, 5, 4])

    def test_ai_turn_is_used_up_by_one_ai_step(self):
        meta = {'attempt': 1, 'base': 'a' * 40}
        runner.write(self.loop.fair_path, {'by:zhe': '2026-10-05T01:00:00+00:00',
                                           'by:junsing': '2026-10-05T02:00:00+00:00', COUNTER: 3})

        def poll(starts=None):
            cs = [card(31, 'building', by='zhe'), card(34, 'building', by='junsing'),
                  card(23, 'testing', by='ai'), card(30, 'building', by='ai')]
            offered = []

            def offer(c):
                offered.append(c['number'])
                if c['number'] == starts:
                    self.loop.job(c, meta, 'verdict')
            with patch('meow_control.controls', return_value=False), patch.object(self.loop, 'cards_on_board', return_value=cs), \
                 patch.object(self.loop, 'process', side_effect=offer), patch.object(self.loop, 'ladder'), \
                 patch.object(self.loop, 'running_notices'), patch.object(self.loop, 'board'), \
                 patch.object(runner.subprocess, 'Popen', return_value=SimpleNamespace(pid=1, poll=lambda: 0)):
                self.loop.tick()
            return offered, read_fair(self.loop.fair_path)[COUNTER]

        # No AI card can use its turn: it stays due, and the human cards are still offered in the same poll.
        self.assertEqual(poll(), ([23, 30, 31, 34], 3))
        self.assertEqual(poll(), ([23, 30, 31, 34], 3))
        # One AI card gets a lock for a step that is not a start from ready: the turn is spent at once.
        self.assertEqual(poll(starts=23), ([23, 31, 34, 30], 0))
        self.assertEqual(poll(), ([31, 34, 23, 30], 0))

    def test_ai_turn_ignores_humans_tasks_and_the_ladder(self):
        meta = {'attempt': 1, 'base': 'a' * 40}
        task = card(8, 'building', by='ai'); task['labels'].append({'name': 'type:task'})
        ladder = card(0, by='ai')
        for c, step in ((card(31, 'building', by='zhe'), 'verdict'), (task, 'verdict'), (ladder, 'ladder')):
            runner.write(self.loop.fair_path, {COUNTER: 3})
            self.loop.launched = set()
            with patch.object(runner.subprocess, 'Popen') as launch:
                self.loop.job(c, meta, step)
                launch.assert_called_once()
            self.assertEqual(read_fair(self.loop.fair_path), {COUNTER: 3})
        self.assertEqual(lock_taken({COUNTER: 2, 'by:ai': 'x'}, card(5, by='ai')), {COUNTER: 0, 'by:ai': 'x'})
        self.assertEqual(order_cards([card(1, by='zhe'), card(2, by='ai'), card(3, by='ai')], {COUNTER: 3})[0]['number'], 2)
        self.assertEqual([c['number'] for c in order_cards([card(1, by='zhe'), card(2, by='ai'), card(3, by='ai')],
                                                           {COUNTER: 3})], [2, 1, 3])

    def test_history_lives_in_the_output_directory(self):
        self.assertEqual(runner.Loop(self.loop.args).fair_path, (self.root / 'out').resolve() / 'fair.json')
        self.assertNotIn(Path.home() / 'meow-loop-out', self.loop.fair_path.parents)
