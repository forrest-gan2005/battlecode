#!/usr/bin/env python3
"""Card #31 unit test: drives a QH_SCOUT=true build one turn at a time on a small scripted board.

usage: python3 work/card_31_unit.py --out DIR [--source mybot2]
No engine and no games: the script writes the turn input a dragon would get and reads its MOVE/SONAR lines.
It builds DIR/qh-on (the source with the switch on) and checks who sends queen pings, what they say, and
where a hunter steps, including whether it takes a portal. Exit code 0 when every case holds.
"""
import argparse, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import card_31_check as codec

W, H = 40, 30
STEP = {'N': (0, -1), 'E': (1, 0), 'S': (0, 1), 'W': (-1, 0)}
TAG = codec.team_tag('A')
KEY = codec.make_key(W, H, TAG)


def cell_of(pos):
    return pos[1] * W + pos[0]


def facing(a, b):
    """Letter of the step from a to b."""
    dx, dy = (b[0] - a[0]) % W, (b[1] - a[1]) % H
    return {(1, 0): 'E', (W - 1, 0): 'W', (0, 1): 'S', (0, H - 1): 'N'}.get((dx, dy), 'N')


def line(head, direction, length):
    """Body cells from the head, trailing away opposite to `direction`."""
    dx, dy = STEP[direction]
    return [((head[0] - k * dx) % W, (head[1] - k * dy) % H) for k in range(length)]


class Board:
    """Tile sides: '.' open, 'w' kelp, or a portal id. north[(x, y)] / west[(x, y)] are that tile's north / west side."""

    def __init__(self, north=None, west=None):
        self.north, self.west = dict(north or {}), dict(west or {})

    def step(self, cell, ch):
        """Cell reached by one step; a portal keeps the direction and continues from its twin side."""
        x, y = cell
        table, at = {'N': (self.north, (x, y)), 'S': (self.north, (x, (y + 1) % H)),
                     'W': (self.west, (x, y)), 'E': (self.west, ((x + 1) % W, y))}[ch]
        token = table.get(at, '.')
        if token == 'w':
            raise RuntimeError(f'stepped into kelp at {cell} {ch}')
        if token == '.':
            return ((x + STEP[ch][0]) % W, (y + STEP[ch][1]) % H)
        twin = next(c for c, v in table.items() if v == token and c != at)
        return {'N': (twin[0], (twin[1] - 1) % H), 'S': twin, 'W': ((twin[0] - 1) % W, twin[1]), 'E': twin}[ch]


class Dragon:
    def __init__(self, binary, did, body, units=6, board=None):
        self.id, self.body, self.units, self.board = did, list(body), units, board or Board()
        self.proc = subprocess.Popen([binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.proc.stdin.write(f'ID {did}\nTEAM A\nMAP {W} {H}\nUNIT_LIMIT 100\n')

    def turn(self, rnd, others, pearls=(), wires=()):
        """others: {id: (team, body)}. Returns the parsed turn and applies the move to our body."""
        hx, hy = self.body[0]
        heading = facing(self.body[1], self.body[0]) if len(self.body) > 1 else 'N'
        out = [f'ROUND {rnd}', f'DIR {heading}', f'LENGTH {len(self.body)}', f'UNIT_COUNT {self.units}',
               f'NUM_MSGS {len(wires)}'] + [str(w) for w in wires]
        window = [((hx + lx - 3) % W, (hy + ly - 3) % H) for ly in range(7) for lx in range(7)]
        out += [f'{x} {y} {int((x, y) in pearls)} -1' for x, y in window]
        parts = []
        for did, (team, body) in {**others, self.id: ('A', self.body)}.items():
            for k, cell in enumerate(body):
                if cell in window:
                    face = facing(cell, body[k - 1]) if k else (facing(body[1], body[0]) if len(body) > 1 else 'N')
                    parts.append(f'{team} {did} {cell[0]} {cell[1]} {face} {int(k == 0)}')
        out += [f'DRAGON_BODIES {len(parts)}'] + parts
        out += [' '.join(str(self.board.north.get(((hx + lx - 3) % W, (hy + ly - 3) % H), '.')) for lx in range(7))
                for ly in range(8)]
        out += [' '.join(str(self.board.west.get(((hx + lx - 3) % W, (hy + ly - 3) % H), '.')) for lx in range(8))
                for ly in range(7)]
        self.proc.stdin.write('\n'.join(out) + '\n')
        self.proc.stdin.flush()
        move, sonar = '', []
        while True:
            text = self.proc.stdout.readline()
            if not text:
                raise RuntimeError('bot exited')
            q = text.split()
            if q[0] == 'ENDTURN':
                break
            if q[0] == 'MOVE':
                move = q[1]
            elif q[0] == 'SONAR':
                plain = codec.unseal(KEY, int(q[-1]), {})
                sonar.append(codec.parse(plain) if plain is not None else {'kind': 'unreadable'})
        free = (len(self.body) + 3) // 4
        for ch in move:
            self.body.insert(0, self.board.step(self.body[0], ch))
            self.body.pop()
        del self.body[max(2, len(self.body) - max(0, len(move) - free)):]
        return {'round': rnd, 'move': move, 'head': self.body[0],
                'pings': [m for m in sonar if m['kind'] == 'ping'],
                'leaders': [m for m in sonar if m['kind'] == 'leader']}

    def close(self):
        self.proc.kill()
        self.proc.wait()
        self.proc.stdin.close()
        self.proc.stdout.close()


def dist(a, b):
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return min(dx, W - dx) + min(dy, H - dy)


def beside(me, offset=(3, 2), length=5):
    """Their queen placed in our view, body trailing east."""
    head = ((me.body[0][0] + offset[0]) % W, (me.body[0][1] + offset[1]) % H)
    return {1: ('B', line(head, 'W', length))}


def ping(hunter, pos, when, **kw):
    return codec.seal(KEY, codec.pack_ping(TAG, hunter, cell_of(pos), when, **kw))


def leader(did, length, when, pos, state=0):
    return codec.seal(KEY, codec.pack_leader(TAG, did, length, when, pos[0], pos[1], state=state))


def cases(binary):
    results = []

    def check(name, ok, detail=''):
        results.append((name, bool(ok), str(detail)))

    def dragon(did, length):
        return Dragon(binary, did, line((10, 10), 'E', length))

    # 1. First finder: pings at once in at least 3 directions, walks to her and rams her head.
    me = dragon(7, 3)
    foe = {1: ('B', line((13, 12), 'W', 5))}
    turns, struck = [], None
    for rnd in range(30, 38):
        before = me.body[0]
        t = me.turn(rnd, foe)
        turns.append((before, t))
        if t['head'] == (13, 12):
            struck = rnd
            break
    first = turns[0][1]
    check('first finder pings at once', len(first['pings']) >= 3, first)
    check('ping says who and where', all(p['id'] == 7 and p['cell'] == cell_of((13, 12)) and p['when'] == 30 and
                                         not p['dead'] for p in first['pings']), first['pings'])
    check('hunter pings every turn', all(len(t['pings']) >= 3 for _, t in turns), [len(t['pings']) for _, t in turns])
    check('hunter closes in', all(dist(t['head'], (13, 12)) < dist(b, (13, 12)) for b, t in turns), turns)
    check('hunter rams her head', struck is not None and struck <= 34, struck)
    me.close()

    # 2. Round 20 or earlier: no hunter yet; from round 21 the finder goes.
    me = dragon(7, 3)
    log = {rnd: me.turn(rnd, beside(me)) for rnd in range(17, 23)}
    check('no hunter up to round 20', not any(log[r]['pings'] for r in range(17, 21)), {r: len(log[r]['pings']) for r in log})
    check('finder goes from round 21', len(log[21]['pings']) >= 3, log[21])
    me.close()

    # 3. A long dragon (5+) neither hunts nor pings.
    me = dragon(7, 5)
    log = [me.turn(rnd, beside(me)) for rnd in range(30, 34)]
    check('long dragon stays silent', not any(t['pings'] for t in log), log)
    me.close()

    # 4. Another hunter was heard: stay out for 20 rounds, then take the job.
    me = dragon(9, 3)
    log = {}
    for rnd in range(29, 52):
        foe = beside(me)
        log[rnd] = me.turn(rnd, foe, wires=[ping(7, foe[1][1][0], 29)] if rnd == 29 else ())
    check('heard a hunter: no hunt for 20 rounds', not any(log[r]['pings'] for r in range(29, 50)),
          {r: len(log[r]['pings']) for r in log})
    check('20 quiet rounds: finder takes over', len(log[50]['pings']) >= 3, log[50])
    me.close()

    # 5. Two hunters before the revenge phase: the lower id keeps the job.
    for other, keeps in ((7, False), (12, True)):
        me = dragon(9, 3)
        foe = beside(me)
        a = me.turn(30, foe)
        foe = beside(me)
        b = me.turn(31, foe, wires=[ping(other, foe[1][1][0], 31)])
        check(f'hunter 9 hears hunter {other}: {"keeps" if keeps else "yields"}',
              len(a['pings']) >= 3 and bool(b['pings']) == keeps, (a, b))
        me.close()

    # 6. Revenge phase: a small dragon told "our queen is dead" goes for a relayed position, only from round 100.
    far = (25, 10)
    for length, state, rounds, expect in ((3, 1, range(96, 103), 'from 100'), (5, 1, range(118, 122), 'never'),
                                          (3, 0, range(118, 122), 'never')):
        me = dragon(9, length)
        log = {}
        for rnd in rounds:
            before = me.body[0]
            log[rnd] = me.turn(rnd, {}, wires=[leader(4, 12, rnd, (30, 20), state), ping(7, far, rnd - 1, state=state)])
            log[rnd]['closer'] = dist(log[rnd]['head'], far) < dist(before, far)
        hunted = [r for r in log if log[r]['pings']]
        want = [r for r in log if r >= 100] if expect == 'from 100' else []
        check(f'revenge: length {length}, queen-dead state {state}: hunts {expect}', hunted == want, hunted)
        if want:
            check('revenge hunter relays her cell under its own id',
                  all(p['id'] == 9 and p['cell'] == cell_of(far) and p['when'] == r - 1 and p['state'] == 1
                      for r in want for p in log[r]['pings']), log[want[0]]['pings'])
            check('revenge hunter heads for her', all(log[r]['closer'] for r in want), {r: log[r]['head'] for r in want})
        me.close()

    # 7. Our queen vanishes and leaves pearls: the witness says "our queen is dead" in its leader messages.
    me = dragon(9, 3)
    queen = line((12, 12), 'W', 3)
    a = me.turn(150, {0: ('A', queen)})
    b = me.turn(151, {}, pearls=set(queen))
    check('queen in view: no claim', a['leaders'] and all(m['state'] == 0 for m in a['leaders']), a['leaders'])
    check('queen gone with pearls: claim sent', b['leaders'] and all(m['state'] == 1 for m in b['leaders']), b['leaders'])
    c = me.turn(152, {0: ('A', line((me.body[0][0], (me.body[0][1] + 2) % H), 'W', 3))})
    check('queen seen again: claim withdrawn', c['leaders'] and all(m['state'] == 2 for m in c['leaders']), c['leaders'])
    me.close()

    # 8. Their queen vanishes and leaves pearls: the hunt stops.
    me = dragon(7, 3)
    foe = beside(me)
    a = me.turn(30, foe)
    b = me.turn(31, {}, pearls=set(foe[1][1]))
    check('her corpse in view: hunt stops', len(a['pings']) >= 3 and not b['pings'], (a, b))
    me.close()

    # 9. Reached her last cell and she is gone (no corpse): stand down until a new sighting.
    me = dragon(7, 3)
    a = me.turn(30, {1: ('B', line((13, 10), 'W', 4))})
    log = [me.turn(rnd, {}) for rnd in range(31, 36)]
    check('lost her: stops pinging once at her last cell', len(a['pings']) >= 3 and not log[-1]['pings'],
          [len(t['pings']) for t in log])
    me.close()

    # 10. Portals: a hunter takes one only when the far tile is surely closer to her last cell.
    # Kelp between columns 11 and 12 over the whole view; the portal by our head comes out at (12, 8).
    fence = {(12, y): 'w' for y in range(7, 14)}
    me = Dragon(binary, 7, line((10, 10), 'E', 3), board=Board(north={(10, 10): 0, (12, 9): 0}, west=fence))
    t = me.turn(30, {1: ('B', line((13, 10), 'W', 4))})
    check('portal: far tile surely closer, the hunter takes it', t['move'][:1] == 'N' and len(t['pings']) >= 3, t)
    me.close()

    # The same portal with its other side never seen: the hunter goes round the kelp instead.
    me = Dragon(binary, 7, line((10, 10), 'E', 3), board=Board(north={(10, 10): 0, (30, 20): 0}, west=fence))
    t = me.turn(30, {1: ('B', line((13, 10), 'W', 4))})
    check('portal: other side unknown, the hunter stays', t['move'][:1] in ('E', 'S') and len(t['pings']) >= 3, t)
    me.close()

    # Revenge, her cell only heard of. The portal comes out one step nearer on paper, but nothing between its
    # far tile and her cell was ever seen, so it is not sure: the hunter walks.
    far = (25, 10)
    me = Dragon(binary, 9, line((10, 10), 'E', 3), board=Board(north={(10, 10): 0, (13, 10): 0}))
    log = [me.turn(rnd, {}, wires=[leader(4, 12, rnd, (30, 20), 1), ping(7, far, rnd - 1, state=1)])
           for rnd in range(100, 104)]
    check('portal: nearer on paper only, the revenge hunter walks',
          all(t['pings'] for t in log) and [t['head'] for t in log] == [(11 + k, 10) for k in range(4)],
          [(t['move'], t['head'], len(t['pings'])) for t in log])
    me.close()

    # Walled into a 3x3 room whose only way out is a portal with an unknown far side: no hunt, no pings.
    # (It needs three turns to leave the room, so all three are decided inside it.)
    room = Board(north={**{(x, 9): 'w' for x in (9, 10, 11)}, **{(x, 12): 'w' for x in (9, 10)}, (11, 12): 0,
                        (30, 20): 0},
                 west={**{(9, y): 'w' for y in (9, 10, 11)}, **{(12, y): 'w' for y in (9, 10, 11)}})
    me = Dragon(binary, 9, [(10, 10), (9, 10), (9, 9)], board=room)
    log = [me.turn(rnd, {}, wires=[leader(4, 12, rnd, (30, 20), 1), ping(7, far, rnd - 1, state=1)])
           for rnd in range(100, 103)]
    check('portal: sealed in with an unknown portal, no hunt', not any(t['pings'] for t in log),
          [(t['move'], t['head'], len(t['pings'])) for t in log])
    me.close()

    # Her cell is 3 open steps away and the portal's far tile is also 3 from her: not closer, the hunter walks.
    me = Dragon(binary, 7, line((10, 10), 'E', 3), board=Board(north={(10, 10): 0, (12, 9): 0}))
    t = me.turn(30, {1: ('B', line((13, 10), 'W', 4))})
    check('portal: far tile no nearer, the hunter walks', t['move'][:1] == 'E' and len(t['pings']) >= 3, t)
    me.close()
    return results


def build(source, out):
    dst = os.path.join(out, 'qh-on')
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    for name in os.listdir(source):
        if name != 'main.cpp' and name.endswith(('.hpp', '.h', '.toml')):
            shutil.copy(os.path.join(source, name), dst)
    text, n = re.subn(r'(constexpr bool QH_SCOUT = )false;', r'\g<1>true;', open(os.path.join(source, 'main.cpp')).read())
    assert n == 1, 'QH_SCOUT must be defined once, default false'
    open(os.path.join(dst, 'main.cpp'), 'w').write(text)
    binary = os.path.join(out, 'bot-on')
    subprocess.run(['c++', '-std=c++20', '-O2', os.path.join(dst, 'main.cpp'), '-o', binary], check=True)
    return binary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--source', default=os.path.join(os.path.dirname(HERE), 'mybot2'))
    ap.add_argument('--binary', help='test this build instead of compiling one (a switch-off build must fail)')
    a = ap.parse_args()
    results = cases(a.binary or build(a.source, a.out))
    for name, ok, detail in results:
        print(('OK   ' if ok else 'FAIL ') + name + ('' if ok else '  ' + detail[:600]))
    bad = sum(1 for _, ok, _ in results if not ok)
    print(f'{len(results) - bad} of {len(results)} cases hold')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
