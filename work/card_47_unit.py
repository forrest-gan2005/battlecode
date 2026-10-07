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


def wire(end=None, spots=(), relay=False):
    return codec.seal(KEY, codec.pack_split(TAG, W, H, end, spots, relay))


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


def pen():
    """A shut room (x 10-13, y 10-14, 20 tiles) whose only door leads east from (13, 12) into a hall
    (x 14-19, y 8-16, 54 tiles: too big to be a dead end itself). The room is a dead end with gate (14, 12)."""
    north = ({(x, 10) for x in range(10, 14)} | {(x, 15) for x in range(10, 14)} |
             {(x, 8) for x in range(14, 20)} | {(x, 17) for x in range(14, 20)})
    west = ({(10, y) for y in range(10, 15)} | {(14, y) for y in range(8, 17) if y != 12} |
            {(20, y) for y in range(8, 17)})
    return Board(north=north, west=west)


class Dragon:
    def __init__(self, binary, did, body, board=None, units=6):
        self.id, self.body, self.units, self.board = did, list(body), units, board or Board()
        self.proc = subprocess.Popen([binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.proc.stdin.write(f'ID {did}\nTEAM A\nMAP {W} {H}\nUNIT_LIMIT 100\n')

    def turn(self, rnd, others=None, pearls=None, wires=(), timers=None):
        """others: {id: (team, body)}; pearls: a set, eaten ones are removed; timers: {tile: rounds until a pearl
        spawns there}, other tiles never spawn. Applies our action to our body."""
        others, pearls, timers = others or {}, pearls if pearls is not None else set(), timers or {}
        hx, hy = self.body[0]
        heading = facing(self.body[1], self.body[0]) if len(self.body) > 1 else 'N'
        out = [f'ROUND {rnd}', f'DIR {heading}', f'LENGTH {len(self.body)}', f'UNIT_COUNT {self.units}',
               f'NUM_MSGS {len(wires)}'] + [str(w) for w in wires]
        window = [((hx + lx - 3) % W, (hy + ly - 3) % H) for ly in range(7) for lx in range(7)]
        out += [f'{x} {y} {int((x, y) in pearls)} {timers.get((x, y), -1)}' for x, y in window]
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


def walk(binary, body, turns, board=None, pearls=(), wires=(), did=9, start=40, timers=None):
    """A fresh dragon handed `wires` on its first turn; returns its turns. `timers` are held still (not counted down)."""
    me = Dragon(binary, did, body, board=board)
    lying = set(pearls)
    log = [me.turn(start + k, pearls=lying, wires=wires if k == 0 else (), timers=timers) for k in range(turns)]
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

    # 4b. Passing it on at a split. A dragon that was told a dead end and then splits in the open sends that dead end
    # to its own child with two spots; the pearl count goes along only when it was heard this turn or the one before.
    # One further than 16 tiles away is left out.
    for name, gate, sent in (('near', (26, 15), True), ('far', (2, 2), False)):
        me = Dragon(binary, 7, bent)
        t = me.turn(30, pearls={(17, 13), (23, 12)}, wires=[wire((gate, 'E', 5, 3))])
        msg = t['split_pings'][0][1] if t['split_pings'] else {}
        want = {'gate': gate, 'dir': 'E', 'room': 5, 'pearls': 3, 'on_map': True} if sent else None
        check(f'pass on: a told dead end {name} the child is {"sent on" if sent else "left out"}',
              t['split'] == 2 and msg.get('end', 0) == want and msg.get('spots') == [((23, 12), False)], t)
        me.close()
    # Told three turns before it splits (it first walks two tiles to a pearl): the dead end goes on without a count.
    old = walk(binary, line((20, 15), 'W', 3), 4, pearls={(18, 15)}, wires=[wire(((26, 15), 'E', 5, 3))], start=30)
    at = next((k for k, x in enumerate(old) if x['split']), None)
    msg = old[at]['split_pings'][0][1] if at is not None and old[at]['split_pings'] else {}
    check('pass on: an older pearl count is not sent on', at is not None and at >= 2 and
          msg.get('end') == {'gate': (26, 15), 'dir': 'E', 'room': 5, 'pearls': None, 'on_map': True},
          [(x['move'], x['split'], x['split_pings'][:1]) for x in old])
    # A spot inside a dead end she knows is left out: the pearl at (23, 12) is that dead end's first tile.
    me = Dragon(binary, 7, bent)
    t = me.turn(30, pearls={(17, 13), (23, 12)}, wires=[wire(((22, 12), 'E', 5, 3))])
    msg = t['split_pings'][0][1] if t['split_pings'] else {}
    check('pass on: a spot inside the dead end is left out',
          t['split'] == 2 and msg.get('end', {}) and msg['end']['gate'] == (22, 12) and msg.get('spots') == [], t)
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

    # 10. Alert. A length-3 dragon walks into the passage (gate (16, 10), shut at x 10) with nobody to tell it. Until
    # it has seen the shut end it sends nothing new. From then on, every turn, all four pings carry the dead end and
    # the pearls it counts inside, split or no split. One pearl lies two tiles in, one on the last tile.
    me = Dragon(binary, 9, line((16, 10), 'W', 3), board=hall)
    lying = {(14, 10), (10, 10)}
    log = [me.turn(40 + k, pearls=lying) for k in range(7)]
    me.close()
    first = next((k for k, x in enumerate(log) if x['split_pings']), None)
    alerts = log[first:] if first is not None else []
    ends = [m.get('end') or {} for x in alerts for _, m in x['split_pings']]
    quiet = [x for x in alerts if not x['split']]
    # The shut end (x 10) comes into view with the head on x 13; the alert goes out with the step to x 12.
    check('alert: nothing new before the shut end is in view', first is not None and log[first]['head'] == (12, 10),
          [(x['move'], x['split'], x['head'], len(x['split_pings'])) for x in log])
    check('alert: all four directions, every turn from then on',
          bool(alerts) and all(sorted(d for d, _ in x['split_pings']) == sorted('NESW') for x in alerts),
          [(x['move'], x['split'], [d for d, _ in x['split_pings']]) for x in log])
    check('alert: the same dead end each time', bool(ends) and all(
        (e.get('gate'), e.get('dir'), e.get('room')) == ((16, 10), 'W', 6) for e in ends), ends[:8])
    check('alert: sent on turns without a split, with no spots and not marked passed-on',
          len(quiet) >= 2 and all(not m['spots'] and not m['relay'] for x in quiet for _, m in x['split_pings']),
          [(x['move'], x['split']) for x in alerts])
    check('alert: pearl count follows what is left inside',
          [x['split_pings'][0][1]['end']['pearls'] for x in quiet][:3] == [1, 1, 0],
          [(x['move'], x['split_pings'][0][1]['end']['pearls']) for x in alerts])
    check('alert: no leader report on an alert turn', bool(alerts) and not any(x['leaders'] for x in alerts),
          [x['sonar'] for x in alerts][:2])
    # The count is "pearls there or due": a tile whose spawn timer is about to run out counts, a slow one does not.
    for name, wait, want in (('about to spawn', 3, 2), ('far from spawning', 30, 1)):
        due = walk(binary, line((16, 10), 'W', 3), 5, board=hall, pearls={(14, 10), (10, 10)}, timers={(11, 10): wait})
        got = [x['split_pings'][0][1]['end']['pearls'] for x in due if x['split_pings'] and not x['split']][:1]
        check(f'alert: a tile {name} {"counts" if want == 2 else "does not count"} as a pearl', got == [want],
              [(x['move'], x['split'], [m['end'] for _, m in x['split_pings'][:1]]) for x in due])
    # A dragon going round and round in a sealed 2x2 box is not in a dead end: the tile behind it is no gate.
    box = Board(north={(10, 10), (11, 10), (10, 12), (11, 12)}, west={(10, 10), (10, 11), (12, 10), (12, 11)})
    laps = walk(binary, [(10, 10), (11, 10)], 6, board=box)
    check('alert: none from a dragon circling in a sealed box', not any(x['split_pings'] for x in laps) and
          all(x['legal'] and x['move'] for x in laps), [(x['move'], x['head'], len(x['split_pings'])) for x in laps])

    # 11. Passing it on once. A dragon in the open that hears a dead end new to it sends it on that same turn in all
    # four directions, marked as a passed-on copy, with the pearl count and no spots. Hearing it again, or hearing a
    # copy that was already passed on, sends nothing.
    body = line((20, 15), 'W', 3)
    want = {'gate': (5, 5), 'dir': 'N', 'room': 4, 'pearls': 1, 'on_map': True}
    heard = walk(binary, body, 3, wires=[wire(((5, 5), 'N', 4, 1))])
    sent = heard[0]['split_pings']
    check('relay: a new dead end goes out once, all four directions', sorted(d for d, _ in sent) == sorted('NESW') and
          all(m['relay'] and m['end'] == want and not m['spots'] for _, m in sent) and
          not any(x['split_pings'] for x in heard[1:]), [x['sonar'] for x in heard])
    me = Dragon(binary, 9, body)
    again = [me.turn(40 + k, wires=[wire(((5, 5), 'N', 4, 1))]) for k in range(2)]
    me.close()
    check('relay: heard a second time, not sent again', len(again[0]['split_pings']) == 4 and not again[1]['split_pings'],
          [x['sonar'] for x in again])
    copy = walk(binary, body, 2, wires=[wire(((5, 5), 'N', 4, 1), relay=True)])
    check('relay: a passed-on copy is not passed on again', not any(x['split_pings'] for x in copy),
          [x['sonar'] for x in copy])
    # A dragon keeps the 16 dead ends nearest to it. Told 16 nearby ones and then one far away in the same turn,
    # the far one is not kept, so the copy it sends on is the last nearby one.
    near = [((10 + k, 20), 'N', 3, 0) for k in range(16)]
    many = walk(binary, body, 1, wires=[wire(end) for end in near + [((0, 0), 'N', 3, 0)]])
    sent = {m['end']['gate'] for _, m in many[0]['split_pings'] if m['end']}
    check('memory: a 17th dead end further away than the 16 it holds is not kept', sent == {(25, 20)}, sent)

    # 12. The charge. A length-3 dragon stands on the gate of the 20-tile room in pen(), a pearl on the room's first
    # tile. Not told, it goes in. Told the room is a dead end with one pearl (or told without a count, seeing the
    # one pearl), it stays out and does not come back to the gate: with fewer than 2 pearls nothing in there is a
    # target. With two pearls, told or seen, no charge: it still stays out here (a 20-tile room is not one the
    # harvest rule sends it into) but the pearls keep pulling it back to the gate, as before this change.
    yard = pen()
    body = line((14, 12), 'W', 3)
    room = lambda cell: 10 <= cell[0] <= 13 and 10 <= cell[1] <= 14
    one, two = {(13, 12)}, {(13, 12), (12, 12)}
    gate = ((14, 12), 'W', 20)
    back = lambda log: any(x['head'] == (14, 12) for x in log[1:])
    steps = lambda log: [(x['move'], x['head']) for x in log]
    plain = walk(binary, body, 1, board=yard, pearls=one)
    check('charge: not told, one pearl inside, it goes in', plain[0]['move'][:1] == 'W', plain[0])
    soon, late = {(12, 12): 2}, {(12, 12): 30}
    for name, lying, count, pulled, clocks in (
            ('told one pearl', one, 1, False, None), ('told without a count, sees one', one, None, False, None),
            ('told two pearls', two, 2, True, None), ('told without a count, sees two', two, None, True, None),
            ('told one pearl, sees two', two, 1, True, None),
            ('told without a count, sees one and a tile about to spawn', one, None, True, soon),
            ('told without a count, sees one and a tile far from spawning', one, None, False, late)):
        log = walk(binary, body, 4, board=yard, pearls=lying, wires=[wire(gate + (count,))], timers=clocks)
        check(f'charge: {name}, it stays out', not any(room(x['head']) for x in log) and all(x['legal'] for x in log),
              steps(log))
        check(f'charge: {name}, {"the pearls still pull it back to the gate" if pulled else "it does not come back to the gate"}',
              back(log) == pulled, steps(log))
    # A cost, not a wall: on the gate of the passage with no other step (kelp both sides, its own body behind),
    # told "6 tiles, no pearls", it still goes in rather than stand still.
    long_hall = corridor(10, 10, 18)
    only = walk(binary, line((16, 10), 'W', 3), 1, board=long_hall, wires=[wire(((16, 10), 'W', 6, 0))])
    check('charge: no other step, it still goes in', only[0]['move'][:1] == 'W' and only[0]['legal'], only[0])
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
    hall = corridor(10, 10, 15)
    me = Dragon(binary, 9, line((16, 10), 'W', 3), board=hall)
    lying = {(14, 10), (10, 10)}
    log = [me.turn(40 + k, pearls=lying) for k in range(6)]
    me.close()
    results.append(('switch off: walking into a dead end sends no alert', not any(x['split_pings'] for x in log),
                    str([x['sonar'] for x in log])[:600]))
    bare = walk(binary, body, 2)
    heard = walk(binary, body, 2, wires=[wire(((5, 5), 'N', 4, 1))])
    results.append(('switch off: a handed dead end is not passed on', not any(x['split_pings'] for x in heard) and
                    [x['move'] for x in heard] == [x['move'] for x in bare], str([x['sonar'] for x in heard])[:600]))
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
