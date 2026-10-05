"""Real edges preserve the legacy board, including transposed portal partners."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import jobs
import mkgen


def parse(text):
    lines = [line.split() for line in text.splitlines() if line.strip()]
    w, h = map(int, next(q for q in lines if q[0] == 'MAP')[1:])
    edges = {int(q[1]): tuple(map(int, q[2:])) for q in lines if q[0] == 'EDGE'}
    count = int(next(q for q in lines if q[0] == 'EDGE_COUNT')[1])
    tiles = {(int(q[1]), int(q[2])): tuple(map(int, q[3:])) for q in lines if q[0] == 'TILE'}
    dragons = [tuple(map(int, q[1:])) for q in lines if q[0] == 'DRAGON']
    return w, h, edges, count, tiles, dragons


def cells(board):
    w, h, edges, _, _, _ = board
    result = {}
    for y in range(h):
        for x in range(w):
            ids = (2 * y * (w + 1) + x, (2 * y + 1) * (w + 1) + x + 1,
                   2 * (y + 1) * (w + 1) + x, (2 * y + 1) * (w + 1) + x)
            result[x, y] = tuple(edges[i] for i in ids)
    return result


def with_padding(text):
    w, h, edges, _, _, _ = parse(text)
    out = []
    for line in text.splitlines():
        if line.startswith('EDGE_COUNT '):
            out.append(f'EDGE_COUNT {(2 * h + 1) * (w + 1)}')
            for i in range((2 * h + 1) * (w + 1)):
                kind, partner = edges.get(i, (0, -1))
                out.append(f'EDGE {i} {kind} {partner}')
        elif not line.startswith('EDGE '):
            out.append(line)
    return '\n'.join(out) + '\n'


def portal_map(padded):
    w, h = 3, 2
    lines = ['MAP 3 2', 'SYMMETRY xy', 'MAP_NAME portal_fixture', 'TILE_COUNT 6']
    lines += [f'TILE {x} {y} 1 {10 + x + 3 * y}' for y in range(h) for x in range(w)]
    edges = {i: (1 if i % 3 == 0 else 0, -1) for i in range(20)
             if padded or not (i // 4 % 2 == 0 and i % 4 == 3)}
    for i in (3, 11, 19):
        if i in edges:
            edges[i] = (0, -1)
    edges[1], edges[14] = (2, 14), (2, 1)
    lines += [f'EDGE_COUNT {len(edges)}'] + [f'EDGE {i} {k} {p}' for i, (k, p) in edges.items()]
    lines += ['DRAGON_COUNT 2', 'DRAGON 0 2 0 0 1 0', 'DRAGON 1 2 2 1 1 1', 'END']
    return '\n'.join(lines) + '\n'


class PaddingEdgeTests(unittest.TestCase):
    def assert_clean(self, text):
        w, h, edges, count, _, _ = parse(text)
        real = {i for i in range((2 * h + 1) * (w + 1))
                if not (i // (w + 1) % 2 == 0 and i % (w + 1) == w)}
        self.assertEqual(set(edges), real)
        self.assertEqual(count, len(real))

    def assert_same_board(self, left, right):
        a, b = parse(left), parse(right)
        self.assertEqual(a[:2], b[:2])
        self.assertEqual(a[4:], b[4:])
        for cell, sides in cells(a).items():
            with self.subTest(cell=cell):
                self.assertEqual(sides, cells(b)[cell])

    def test_generator_matches_before_change_cell_by_cell(self):
        old = (HERE / 'tests/legacy_generated_padding.txt').read_text()
        name, new = mkgen.make(1001, 'rooms', 'small')
        self.assertEqual(name, 'gen_rooms_small_1001')
        self.assert_same_board(old, new)
        self.assertEqual(with_padding(new), old)
        self.assert_clean(new)

    def test_generator_styles_have_only_real_edges(self):
        for style in mkgen.STYLES:
            for seed in range(1000, 1020):
                result = mkgen.make(seed, style, 'small')
                if result:
                    with self.subTest(style=style, seed=seed):
                        self.assert_clean(result[1])
                    break
            else:
                self.fail(f'no generated fixture for {style}')

    def test_transpose_accepts_both_formats_and_preserves_portals(self):
        old, new = portal_map(True), portal_map(False)
        self.assert_same_board(old, new)
        transposed = jobs.transpose(new)
        self.assertEqual(jobs.transpose(old), transposed)
        self.assert_clean(transposed)
        a, b = parse(new), parse(transposed)
        for (x, y), sides in cells(a).items():
            actual = cells(b)[y, x]
            for dest_side, source_side in enumerate((3, 2, 1, 0)):
                kind, partner = sides[source_side]
                if partner >= 0:
                    row, px = divmod(partner, a[0] + 1)
                    py, vertical = divmod(row, 2)
                    partner = (2 * px + 1 - vertical) * (a[1] + 1) + py
                self.assertEqual(actual[dest_side], (kind, partner))
        self.assertEqual(b[4], {(y, x): value for (x, y), value in a[4].items()})
        self.assertEqual(b[5], [(q[0], q[1], *[v for i in range(2, len(q), 2)
                                             for v in (q[i + 1], q[i])]) for q in a[5]])
        self.assert_same_board(new, jobs.transpose(transposed))

    def test_generated_transpose_reads_legacy_and_clean(self):
        old = (HERE / 'tests/legacy_generated_padding.txt').read_text()
        _, new = mkgen.make(1001, 'rooms', 'small')
        self.assertEqual(jobs.transpose(old), jobs.transpose(new))
        self.assert_clean(jobs.transpose(new))

    def test_portal_to_padding_and_bad_count_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'padding edge'):
            jobs.transpose(portal_map(False).replace('EDGE 1 2 14', 'EDGE 1 2 3'))
        with self.assertRaises(ValueError):
            jobs.transpose(portal_map(False).replace('EDGE_COUNT 17', 'EDGE_COUNT 16'))


if __name__ == '__main__':
    unittest.main()
