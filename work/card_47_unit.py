#!/usr/bin/env python3
"""Card #47 unit test: drives an UPDATE_MAP=true build one turn at a time on a small scripted board.

usage: python3 work/card_47_unit.py --out DIR [--source mybot2] [--off BINARY]
No engine and no games: the script writes the turn input a dragon would get and reads its MOVE/SPLIT/SONAR lines.
It builds DIR/um-on (the source with the switch on) and checks what a splitting dragon sends, when it re-sends,
and what a dragon that hears the ping does next to one that does not. With --off it also checks that a
switch-off build sends no split ping and takes the same steps whether or not it is handed one.
Exit code 0 when every case holds.
"""
import argparse, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import card_47_check as codec

W, H = 40, 30
STEP = codec.STEP
TAG = codec.team_tag('A')
KEY = codec.make_key(W, H, TAG)


def facing(a, b):
    """Letter of the step from a to b."""
    dx, dy = (b[0] - a[0]) % W, (b[1] - a[1]) % H
    return {(1, 0): 'E', (W - 1, 0): 'W', (0, 1): 'S', (0, H - 1): 'N'}.get((dx, dy), 'N')


def line(head, direction, length):
    """Body cells from the head, trailing away opposite to `direction`."""
    dx, dy = STEP[direction]
    return [((head[0] - k * dx) % W, (head[1] - k * dy) % H) for k in range(length)]


def wire(end=None, spots=()):
    return codec.seal(KEY, codec.pack_split(TAG, W, H, end, spots))


class Board:
    """Tile sides: 'w' kelp, else open. north[(x, y)] / west[(x, y)] are that tile's north / west side."""

    def __init__(self, north=(), west=()):
        self.north, self.west = set(north), set(west)

    def open(self, cell, ch):
        x, y = cell
        return {'N': (x, y) not in self.north, 'S': (x, (y + 1) % H) not in self.north,
                'W': (x, y) not in self.west, 'E': ((x + 1) % W, y) not in self.west}[ch]


def corridor(y, x0, x1):
    """A one-tile-wide passage along row y from x0 to x1, shut at its west end (x0)."""
    xs = range(x0, x1 + 1)
    return Board(north={(x, y) for x in xs} | {(x, y + 1) for x in xs}, west={(x0, y)})


class Dragon:
    def __init__(self, binary, did, body, board=None, units=6):
        self.id, self.body, self.units, self.board = did, list(body), units, board or Board()
        self.proc = subprocess.Popen([binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.proc.stdin.write(f'ID {did}\nTEAM A\nMAP {W} {H}\nUNIT_LIMIT 100\n')

    def turn(self, rnd, others=None, pearls=None, wires=()):
        """others: {id: (team, body)}; pearls: a set, eaten ones are removed. Applies our action to our body."""
        others, pearls = others or {}, pearls if pearls is not None else set()
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
        out += [' '.join('w' if ((hx + lx - 3) % W, (hy + ly - 3) % H) in self.board.north else '.'
                         for lx in range(7)) for ly in range(8)]
        out += [' '.join('w' if ((hx + lx - 3) % W, (hy + ly - 3) % H) in self.board.west else '.'
                         for lx in range(8)) for ly in range(7)]
        self.proc.stdin.write('\n'.join(out) + '\n')
        self.proc.stdin.flush()
        move, split, sonar = '', 0, []
        while True:
            text = self.proc.stdout.readline()
            if not text:
                raise RuntimeError('bot exited')
            q = text.split()
            if q[0] == 'ENDTURN':
                break
            if q[0] == 'MOVE':
                move, split = q[1], 0
            elif q[0] == 'SPLIT':
                move, split = '', int(q[1])
            elif q[0] == 'SONAR':
                plain = codec.unseal(KEY, int(q[-1]), {})
                sonar.append((q[1], codec.parse(plain, W, H) if plain is not None else {'kind': 'unreadable'}))
        child, legal = None, True
        if split:
            child = list(reversed(self.body[-split:]))
            del self.body[-split:]
        for k, ch in enumerate(move):
            nxt = ((self.body[0][0] + STEP[ch][0]) % W, (self.body[0][1] + STEP[ch][1]) % H)
            if not self.board.open(self.body[0], ch) or nxt in self.body[:-1]:
                legal = False
                break
            self.body.insert(0, nxt)
            if nxt in pearls:
                pearls.discard(nxt)
            else:
                self.body.pop()
            if k >= (len(self.body) + 3) // 4 and len(self.body) > 2:
                self.body.pop()
        return {'round': rnd, 'move': move, 'split': split, 'child': child, 'legal': legal, 'head': self.body[0],
                'sonar': sonar, 'split_pings': [(d, m) for d, m in sonar if m['kind'] == 'split'],
                'leaders': [d for d, m in sonar if m['kind'] == 'leader']}

    def close(self):
        self.proc.kill()
        self.proc.wait()
        self.proc.stdin.close()
        self.proc.stdout.close()


def walk(binary, body, turns, board=None, pearls=(), wires=(), did=9, start=40):
    """A fresh dragon handed `wires` on its first turn; returns its turns."""
    me = Dragon(binary, did, body, board=board)
    lying = set(pearls)
    log = [me.turn(start + k, pearls=lying, wires=wires if k == 0 else ()) for k in range(turns)]
    me.close()
    return log


def cases(binary):
    results = []

    def check(name, ok, detail=''):
        results.append((name, bool(ok), str(detail)))

    # 1. A dragon at the shut end of a passage (x 10-15 on row 10) has no step left and splits. It has seen the
    # passage up to x 13 and the open side of that tile, so the gate it can vouch for is (14, 10): 4 tiles behind
    # it. Two pearls lie outside the child's view; the one nearer to the parent stays hers.
    hall = corridor(10, 10, 15)
    me = Dragon(binary, 7, line((10, 10), 'W', 4), board=hall)
    lying = {(9, 12), (8, 8)}
    t = me.turn(30, pearls=lying)
    pings = t['split_pings']
    msg = pings[0][1] if pings else {}
    check('dead end: it splits', t['split'] == 2, t)
    check('dead end: split ping in all four directions', sorted(d for d, _ in pings) == sorted('NESW'), t['sonar'])
    check('dead end: every copy is the same message', all(m == msg for _, m in pings), pings)
    check('dead end: gate, direction in and size', msg.get('end') == {'gate': (14, 10), 'dir': 'W', 'room': 4,
                                                                      'pearls': 0, 'on_map': True}, msg)
    check('dead end: the pearl spot nearer to the parent stays hers', msg.get('spots') == [((8, 8), False)], msg)
    check('dead end: no leader report on the split turn', not t['leaders'], t['sonar'])
    # The copy into her own neck leaves from her tail tip onto the child, so nothing is re-sent.
    kid = {8: ('A', t['child'])}
    later = [me.turn(rnd, others=kid, pearls=lying) for rnd in (31, 32)]
    check('dead end: ping aimed at the child, no re-send', not any(x['split_pings'] for x in later),
          [x['sonar'] for x in later])
    me.close()

    # 2. With the only pearl being the parent's own nearest, the dead end goes out alone.
    me = Dragon(binary, 7, line((10, 10), 'W', 4), board=hall)
    t = me.turn(30, pearls={(8, 8)})
    msg = t['split_pings'][0][1] if t['split_pings'] else {}
    check('dead end: sent even with no spot to tell', t['split'] == 2 and msg.get('end', {}) and
          msg['end']['room'] == 4 and msg['spots'] == [], t)
    me.close()

    # 3. Open country, a growth split with a bend in the body: no copy can reach the child on the split turn.
    # Three spots, no dead end. Next turn the parent steps south onto a pearl and is lined up: one re-send, east.
    bent = [(20, 15), (21, 15), (21, 16), (21, 17)]
    me = Dragon(binary, 7, bent)
    lying = {(20, 16), (17, 13), (23, 12)}
    t = me.turn(30, pearls=lying)
    pings = t['split_pings']
    msg = pings[0][1] if pings else {}
    check('open split: it splits off 2', t['split'] == 2, t)
    check('open split: split ping in all four directions', sorted(d for d, _ in pings) == sorted('NESW'), t['sonar'])
    check('open split: no dead end, the far pearl is the spot',
          msg.get('end', 0) is None and msg.get('spots') == [((23, 12), False)], msg)
    kid = {8: ('A', t['child'])}
    t1 = me.turn(31, others=kid, pearls=lying)
    t2 = me.turn(32, others=kid, pearls=lying)
    check('open split: parent steps south', t1['move'] == 'S', t1)
    check('open split: re-sent once, towards the child only', [d for d, _ in t1['split_pings']] == ['E'] and
          t1['split_pings'][0][1] == msg, t1['sonar'])
    check('open split: other directions carry the leader report again', len(t1['leaders']) == 3, t1['sonar'])
    check('open split: nothing more once a copy was aimed', not t2['split_pings'], t2['sonar'])
    me.close()

    # 4. Nothing to tell (no dead end, no pearl, no refill tile): the usual messages go out.
    me = Dragon(binary, 7, bent)
    t = me.turn(30)
    check('nothing to tell: split without a split ping', t['split'] == 2 and not t['split_pings'], t)
    me.close()

    # 4b. Passing it on. A dragon that was told a dead end and then splits in the open sends that dead end to its own
    # child (no pearl count: it is not looking at it), with two spots. One further than 16 tiles away is left out.
    for name, gate, sent in (('near', (26, 15), True), ('far', (2, 2), False)):
        me = Dragon(binary, 7, bent)
        t = me.turn(30, pearls={(17, 13), (23, 12)}, wires=[wire((gate, 'E', 5, 3))])
        msg = t['split_pings'][0][1] if t['split_pings'] else {}
        want = {'gate': gate, 'dir': 'E', 'room': 5, 'pearls': 0, 'on_map': True} if sent else None
        check(f'pass on: a told dead end {name} the child is {"sent on" if sent else "left out"}',
              t['split'] == 2 and msg.get('end', 0) == want and msg.get('spots') == [((23, 12), False)], t)
        me.close()

    # 5. Hearing a dead end. A length-3 dragon stands on the gate (16, 10) of the same passage, with one pearl two
    # tiles in. Not told, it goes in for the pearl. Told "6 tiles, 1 pearl", it stays out: one pearl does not pay.
    # Told the same with three pearls in view and more inside, the usual harvest rule sends it in.
    body = line((16, 10), 'W', 3)
    inside = lambda cell: cell[1] == 10 and 10 <= cell[0] <= 15
    plain = walk(binary, body, 6, board=hall, pearls={(14, 10)})
    told = walk(binary, body, 6, board=hall, pearls={(14, 10)}, wires=[wire(((16, 10), 'W', 6, 1))])
    rich = walk(binary, body, 1, board=hall, pearls={(15, 10), (14, 10), (13, 10)},
                wires=[wire(((16, 10), 'W', 6, 6))])
    check('hear dead end: not told, it walks in', plain[0]['move'][:1] == 'W', [x['move'] for x in plain])
    check('hear dead end: told, it stays out', not any(inside(x['head']) for x in told),
          [(x['move'], x['head']) for x in told])
    check('hear dead end: told, enough pearls inside, it goes in', rich[0]['move'][:1] == 'W', rich[0])

    # 6. The same told dead end does not wall anything else off: a dragon already inside, told, still walks out.
    out = walk(binary, [(13, 10), (12, 10), (11, 10)], 5, board=hall, wires=[wire(((16, 10), 'W', 6, 0))])
    check('hear dead end: told while inside, it walks out', out[-1]['head'][0] >= 16 and all(x['legal'] for x in out),
          [(x['move'], x['head']) for x in out])

    # 7. Hearing pearl spots in open country. Not told, the dragon does not go west; told a pearl five tiles west
    # (outside its view), it walks there and eats it. A refill tile four tiles west pulls it the same way.
    body = line((20, 15), 'W', 3)
    plain = walk(binary, body, 5, pearls={(15, 15)})
    told = walk(binary, body, 5, pearls={(15, 15)}, wires=[wire(None, [((15, 15), False)])])
    hot = walk(binary, body, 1, wires=[wire(None, [((16, 15), True)])])
    check('hear spot: not told, it does not head west', plain[0]['move'][:1] != 'W', [x['move'] for x in plain])
    check('hear spot: told a pearl, it walks there', any(x['head'] == (15, 15) for x in told),
          [(x['move'], x['head']) for x in told])
    check('hear spot: told a refill tile, it heads there', hot[0]['move'][:1] == 'W', hot[0])

    # 8. Spots carried with a dead end are read as offsets from its gate.
    far = walk(binary, body, 5, pearls={(15, 15)}, wires=[wire(((2, 2), 'N', 3, 0), [((15, 15), False)])])
    check('hear spot: pearl sent with a far dead end', any(x['head'] == (15, 15) for x in far),
          [(x['move'], x['head']) for x in far])

    # 9. A message naming tiles off the map changes nothing and breaks nothing.
    junk = codec.seal(KEY, (1 << 63) | (1 << 52) | (TAG << 53) | 0x3FFF | (0x3FFF << 15) | (0x3FFE << 30))
    odd = walk(binary, body, 5, pearls={(15, 15)}, wires=[junk])
    check('off-map tiles are ignored', [x['move'] for x in odd] == [x['move'] for x in plain],
          [x['move'] for x in odd])
    return results


def off_cases(binary):
    """A switch-off build: no split ping, and a handed ping changes no step."""
    results = []
    me = Dragon(binary, 7, line((10, 10), 'W', 4), board=corridor(10, 10, 15))
    t = me.turn(30, pearls={(9, 12), (8, 8)})
    me.close()
    results.append(('switch off: splits, sends no split ping', t['split'] == 2 and not t['split_pings'], str(t)))
    body = line((20, 15), 'W', 3)
    plain = walk(binary, body, 5, pearls={(15, 15)})
    told = walk(binary, body, 5, pearls={(15, 15)}, wires=[wire(None, [((15, 15), False)])])
    results.append(('switch off: a handed ping changes no step',
                    [x['move'] for x in plain] == [x['move'] for x in told], str([x['move'] for x in told])))
    return results


def build(source, out):
    dst = os.path.join(out, 'um-on')
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    for name in os.listdir(source):
        if name != 'main.cpp' and name.endswith(('.hpp', '.h', '.toml')):
            shutil.copy(os.path.join(source, name), dst)
    text, n = re.subn(r'(constexpr bool UPDATE_MAP = )false;', r'\g<1>true;', open(os.path.join(source, 'main.cpp')).read())
    assert n == 1, 'UPDATE_MAP must be defined once, default false'
    open(os.path.join(dst, 'main.cpp'), 'w').write(text)
    binary = os.path.join(out, 'um-on-bot')
    subprocess.run(['c++', '-std=c++20', '-O2', os.path.join(dst, 'main.cpp'), '-o', binary], check=True)
    return binary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--source', default=os.path.join(os.path.dirname(HERE), 'mybot2'))
    ap.add_argument('--binary', help='test this switch-on build instead of compiling one')
    ap.add_argument('--off', help='a switch-off build to check as well')
    ap.add_argument('--verbose', action='store_true', help='print the detail of every case, not only failed ones')
    a = ap.parse_args()
    results = cases(a.binary or build(a.source, a.out))
    if a.off:
        results += off_cases(a.off)
    for name, ok, detail in results:
        print(('OK   ' if ok else 'FAIL ') + name + ('' if ok and not a.verbose else '  ' + detail[:900]))
    bad = sum(1 for _, ok, _ in results if not ok)
    print(f'{len(results) - bad} of {len(results)} cases hold')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
