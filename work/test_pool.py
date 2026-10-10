"""Accounting checks; these do not launch games or acquire the batch lock."""
import unittest
import fcntl
from pathlib import Path
import select
import subprocess
import sys
import tempfile
from unittest.mock import patch

import pool


class Struct:
    def __init__(self, ints=None, pointers=None, text='', bits=()):
        self.ints, self.pointers = ints or {}, pointers or {}
        self.string, self.bits = text, bits

    def i32(self, offset):
        return self.ints.get(offset, 0)

    u16 = i32

    def pointer(self, index):
        return self.pointers.get(index)

    def text(self, index):
        return self.string

    def bit(self, index):
        return index in self.bits


def event(kind, payload):
    return Struct({0: pool.replay.EVENT_NAMES.index(kind)}, {0: payload})


class PoolAccounting(unittest.TestCase):
    def test_lock_waits_until_released(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'batch.lock'
            with path.open('a') as handle:
                fcntl.flock(handle, fcntl.LOCK_EX)
                code = ('from pathlib import Path; import pool, sys\n'
                        'with pool.batch_lock(Path(sys.argv[1])): print("acquired", flush=True)\n')
                child = subprocess.Popen([sys.executable, '-c', code, str(path)],
                    cwd=pool.HERE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    self.assertTrue(select.select([child.stderr], [], [], 5)[0])
                    self.assertEqual(child.stderr.readline().strip(), 'waiting for the batch lock')
                    self.assertIsNone(child.poll())
                    self.assertFalse(select.select([child.stdout], [], [], 0.05)[0])
                    fcntl.flock(handle, fcntl.LOCK_UN)
                    stdout, stderr = child.communicate(timeout=5)
                    self.assertEqual((child.returncode, stdout.strip(), stderr), (0, 'acquired', ''))
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.communicate()

    def test_paired_flips_and_zero_even_when_base_wins(self):
        b = dict(tag='BASE', opponent='hunter', map='trophy', seed=100,
                 side=0, win=1, us=0, them=0)
        c = dict(b, tag='CAND', win=0, them=10)
        self.assertEqual(pool.stats([c, b]),
                         [1, 1, 0, 0, 1, -1, '0.0→0.0', '0.0→10.0', '1→1'])
        for rows in ([], [b], [b, b, c]):
            with self.assertRaises(ValueError):
                pool.stats(rows)

    def test_dead_queen_with_surviving_child_and_attributed_ram(self):
        # A's queen dies on a wall; its child then initiates a ram on B's queen.
        # A wins elimination with a surviving child, but its queen score is zero.
        point = lambda x: Struct({0: x, 4: 0})
        events = [
            event('dragonSplit', Struct({0: 0, 4: 2, 8: 0},
                  {0: [point(0), point(1)], 1: [point(2), point(3)]})),
            event('turnStart', Struct({0: 0})),
            event('dragonDeath', Struct({0: 0, 4: 0})),
            event('turnStart', Struct({0: 2})),
            event('dragonAction', Struct({0: 2}, bits=(32,))),
            event('dragonDeath', Struct({0: 1, 4: 3})),
        ]
        result = Struct({4: 1, 6: 0})
        root = Struct(pointers={3: events, 4: result}, text=
                      'DRAGON 0 4 0 0 1 0 2 0 3 0\nDRAGON 1 2 5 0 6 0')
        with patch.object(pool.replay, 'load') as load:
            load.return_value.root.return_value = root
            a = pool.replay_metrics('fixture', 0)
            b = pool.replay_metrics('fixture', 1)
        self.assertEqual((a['win'], a['us'], a['them']), (1, 0, 0))
        self.assertEqual((a['enemy_queen_kills'], a['small_queen_kills'],
                          a['head_on_caused'], a['timeouts']), (1, 1, 1, 1))
        self.assertEqual((b['enemy_queen_deaths'], b['enemy_queen_kills'],
                          b['head_on_caused']), (1, 0, 0))

    def test_specs_reject_ambiguous_or_unsafe_toggles(self):
        self.assertEqual(pool.spec('mybot2:QUEEN_HUNT=true')['toggles'],
                         {'QUEEN_HUNT': 'true'})
        for bad in ('mybot2:A=1,A=2', 'mybot2:X=1;bad', 'mybot2:X'):
            with self.assertRaises(ValueError):
                pool.spec(bad)


if __name__ == '__main__':
    unittest.main()
