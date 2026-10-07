#!/usr/bin/env python3
"""Card #48 queen-sacrifice mechanism check (QUEEN_NO_FEED, third build): with the switch on, does our queen stay
out of the feeding? She must not drop her body for the leader, not split after round 200 unless forced, not eat
near the leader, not eat our own dragons' bodies in feeding rounds and not be picked as the leader there. And does
the switch change nothing else?

usage: python3 work/card_48_check.py --replays DIR --base base --candidate candidate --output FILE
Reads paired replays DIR/<tag>_<map>_<seed>_<side>.replay (side 0 = we are team A). The opponent is the base bot
in every game. A pair is the base game and the switch-on game of the same map, seed and side.

Words:
  queen           the dragon with id 0 or 1; each team has one. The game is decided by the queens' lengths.
  drop            a dragon ends its turn with no action and dies on the spot ("no valid action"). It is how a
                  feeder gives its length to the leader. A turn the game marks as timed out is counted apart.
  body pearl      a dead dragon leaves a pearl on every second tile of its body, head first. The replay says when
                  each pearl appears, so every pearl is told apart here: spawned by the map, or the body of one
                  named dragon (dropped as a feeder, or died another way).
  feeding rounds  rounds where the bot's feeding can be on: after round 400, or after round 200 once we have 56
                  dragons.
  the leader she knows   every turn a dragon sends its teammates a sonar message naming the leader it currently
                  believes in (id, length, position). This file decodes our own team's messages, so "the leader
                  she knows" is read from what the queen herself sent that turn, not guessed. A turn in which she
                  sent no such message counts as "knows none" (the bot sends none exactly then, except on a turn
                  all four pings carried a portal warning, where the previous turn's answer is kept).
  fed on purpose  on maps over 600 tiles, or when her home is closed off, the swarm picks the queen as the leader
                  in feeding and feeds her. Her messages then name herself. The rules about pearls do not apply
                  on such turns: those pearls are meant for her.
  true leader     our longest dragon other than the queen, from true lengths. Reported next to what she knew.
  view            the 7x7 box around her head, all the bot sees.
  open step       a neighbouring tile she can step on (no wall, no dragon on it, her own tail tile included: the
                  bot treats the tail as blocked for the next step) from which she can reach at least 3 x her
                  length + 8 free tiles or her own tail. This is the bot's own test for "not a dead end".
  roomy step      the same with a lower bar: her length + 2 free tiles, or her own tail. With no roomy step the
                  bot calls her stuck and lets her split 2 off to wait in place.
  pressed         an enemy head is in her view at the start of her turn. The bot puts her safety first then, so
                  a split or a pearl taken on such a turn is not held against the switch.
  free split      she splits, in a round after 200, not pressed, with at least one roomy step.
  clean step      an open step other than the one she took, not through a portal, whose tile holds no pearl she is
                  meant to leave. The bot gives up a pearl only when it has such a step.
  free bite near the leader   in a feeding round she grows on a tile within 9 tiles (wrap-aware) of the position
                  of the leader she knows, that leader is not herself, she is not pressed and had a clean step.
  watched         the body pearl's tile was in her view with one of our dragons on it at her last turn before the
                  death, and still in her view at her next turn. Then she saw the body turn into the pearl.
  inferable       when she first sees the body pearl, her last look at that tile showed no pearl and a spawn
                  countdown that had not run out yet (with INFER_MARGIN rounds to spare), or the tile never
                  spawns. Then no spawn explains the pearl, so it must be a body.
  free bite on our body   in a feeding round, on a turn she does not name herself leader, she grows on a body
                  pearl of one of our own dragons that was watched or inferable, not pressed, with a clean step.
  first difference  the base and switch-on game of a pair are the same game, event for event, until the switch
                  changes a decision. The first turn that differs is that decision, from an identical position.

Expectation, written before any game was played with this build's switch on (thresholds are the constants below):
  1. only what the switch covers: every pair that differs has its first difference (a) inside our own queen's
     turn, in a round after FIRST_FROM (200; 150 on maps over 1200 tiles), or (b) in the turn of another of our
     dragons, on a map of 600 tiles or fewer, at or after the first feeding round in which the base game has one
     of our dragons naming our queen as leader without the fed-on-purpose mark (the switch stops them picking
     her there).
  2. target seen: queens run by the base bot drop at least TARGET_MIN times in this run; our switch-on queen has
     at least EXPOSED_MIN feeding turns on which she does not name herself leader; and in at least BODY_MIN of those
     turns one of our dragons' body pearls lay on a tile she could step on.
  3. never drops: our switch-on queen drops 0 times, on any map.
  4. no free split: our switch-on queen makes 0 free splits, on any map.
  5. no free bite near the leader: 0 by our switch-on queen.
  6. it acted: at least ACTED_MIN pairs differ.
  7. no free bite on our body: 0 by our switch-on queen.
  8. not the leader: on maps of 600 tiles or fewer, in feeding rounds, our switch-on queen never names herself
     leader and no dragon of ours names her, unless the message carries the fed-on-purpose mark. (For the
     56-dragon kind of feeding a round counts here only with 58 or more dragons, see CAP_SLACK.)
passed = all eight. target_seen = rule 2. mechanism_shown = the other seven.
Reported, not part of the verdict: every split and bite of our queen after round 200 with its labels; bites on
our body pearls she could not tell from a spawned pearl (neither watched nor inferable); bites on turns she named
herself leader; bites near the true leader when she did not know of it; splits while
pressed or stuck; how often she ended a feeding turn within 1 and 3 tiles of the true leader; how often the base
bot's queen names herself leader or is named in feeding rounds; what became of both queens; lengths and wins.
Known before any switch-on game of this build, from the second build's replays (same maps and seeds):
- default_small 14800 side 1, switch on: the queen heard of leader 191 until round 453; its reports then went
  stale and from round 454 she and the dragons around her named HER the leader. The feeders that dropped next to
  her in rounds 454 to 457 dropped for her. Of her 20 bites in feeding, 5 were spawned pearls, 5 a feeder's
  dropped body and 10 the body of one of our dragons that died another way (6 of them the dead leader's).
- tower_defense 14801 side 1, round 331: the split the second check called free was a stuck split. Our own dragon
  96 had closed her 2x2 pocket; the old check counted her own tail tile as a step with room. This file no longer
  does. The bot has no growth split after round 200 with the switch on.
The game runner drops the bot's log lines (--no-debug), so nothing here reads them.
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, os, sys
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import replay
from card_39_check import load_map

# Expectation thresholds (fixed before any game with this build's switch on)
TARGET_MIN = 2       # drops by base-bot queens needed to call the target seen
EXPOSED_MIN = 30     # feeding turns on which our switch-on queen does not name herself leader, for target seen
BODY_MIN = 3         # of those, turns with one of our dragons' body pearls on a tile she could step on
ACTED_MIN = 2        # pairs that must differ to say the switch acted
FIRST_FROM = 200     # QUEEN_SPLIT_ROUND / FEED_CAP_ROUND: the switch changes nothing at or before this round
FIRST_FROM_BIG = 150 # LEADER_GROW_ROUND_BIG: on maps over BIG_CELLS tiles the leader's zone starts here

SPLIT_ROUND = 200    # QUEEN_SPLIT_ROUND
FEED_ROUND = 400     # ENDGAME_ROUND
FEED_FROM = 200      # FEED_CAP_ROUND
CAP_UNITS = 56       # FEED_CAP_UNITS
ZONE = 9             # LEADER_PEARL_RADIUS
SMALL_CELLS = 600    # QUEEN_MIN_CELLS: at or below this the swarm feeds the queen on purpose only in a queen game
INFER_MARGIN = 3     # rounds of slack before a pearl counts as "no spawn explains it" (the bot uses 1)
CAP_SLACK = 2        # the 56-dragon kind of feeding flips as dragons split and die within a round: rule 8 counts a
                     # round only at CAP_UNITS + CAP_SLACK or more, rule 1 already allows CAP_UNITS - CAP_SLACK
VIEW = 3             # the bot sees a 7x7 box around its head
BIG_CELLS = 1200     # AGGRESSIVE_MAX_CELLS
CAUSE = ['wall', 'self', 'body', 'headon', 'no_action']
QUEENS = (0, 1)

# Sonar wire format, as in mybot2/sonar_codec.hpp and pack_leader in mybot2/main.cpp.
M64 = (1 << 64) - 1
SECRET = 0xE1DE70530C48DE42
CHECK_MASK = 0xFF << 55
CIPHER_MASK = M64 ^ CHECK_MASK ^ (0x3 << 53)


def rotl(x, b):
    return ((x << b) | (x >> (64 - b))) % (1 << 64)


def prf(key, m):
    """SipHash-2-4 of one 8-byte block."""
    v = [key[0] ^ 0x736F6D6570736575, key[1] ^ 0x646F72616E646F6D, key[0] ^ 0x6C7967656E657261,
         key[1] ^ 0x7465646279746573]

    def rounds(n):
        for _ in range(n):
            v[0] = (v[0] + v[1]) % (1 << 64)
            v[1] = rotl(v[1], 13) ^ v[0]
            v[0] = rotl(v[0], 32)
            v[2] = (v[2] + v[3]) % (1 << 64)
            v[3] = rotl(v[3], 16) ^ v[2]
            v[0] = (v[0] + v[3]) % (1 << 64)
            v[3] = rotl(v[3], 21) ^ v[0]
            v[2] = (v[2] + v[1]) % (1 << 64)
            v[1] = rotl(v[1], 17) ^ v[2]
            v[2] = rotl(v[2], 32)
    tail = 8 << 56
    v[3] ^= m
    rounds(2)
    v[0] ^= m
    v[3] ^= tail
    rounds(2)
    v[0] ^= tail
    v[2] ^= 0xFF
    rounds(4)
    return v[0] ^ v[1] ^ v[2] ^ v[3]


assert prf((0x0706050403020100, 0x0F0E0D0C0B0A0908), 0x0706050403020100) == 0x93F5F5799A932462


def sonar_key(width, height, tag):
    root = (SECRET, rotl(SECRET, 29) ^ 0xA5A5A5A5A5A5A5A5)
    game = (width << 40) | (height << 16) | tag
    return prf(root, game), prf(root, game | (1 << 63))


def leader_report(key, tag, wire, width, height):
    """The leader a sonar message names, or None when it is another kind of message or not ours."""
    check = (wire >> 55) % 256
    plain = (wire ^ (check << 55)) ^ (prf(key, CHECK_MASK | check) & CIPHER_MASK)
    if prf(key, plain) % 256 != check or plain >> 63 or (plain >> 53) % 4 != tag:
        return None
    named = plain % 65536
    out = dict(id=named % 32768, on_purpose=named >= 32768, len=(plain >> 16) % 1024, when=(plain >> 28) % 512,
               pos=[(plain >> 37) % 128, (plain >> 44) % 128])
    if out['len'] <= 0 or out['pos'][0] >= width or out['pos'][1] >= height:
        return None
    return out


def gap(a, b, size):
    raw = abs(a - b)
    return min(raw, size - raw)


def scan(job):
    """One replay: every turn as a short hash, our queen's turns, queen drops and what became of both queens.
    `track` is None for the queens, or (our id, their id) to follow two other dragons (used to test this file)."""
    path, side, track = job
    ours = 'A' if side == '0' else 'B'
    root = replay.load(path).root()
    text = root.text(0)
    W, H, step = load_map(text)
    result = root.pointer(4)
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None
    bodies, team_of = {}, {}
    for line in text.splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
    queen = track[0] if track else next((i for i in QUEENS if team_of.get(i) == ours), None)
    foe = track[1] if track else next((i for i in QUEENS if team_of.get(i) != ours), None)
    tag = 2 if ours == 'A' else 1
    key = sonar_key(W, H, tag)
    decoded = {}

    def dist(a, b):
        return gap(a[0], b[0], W) + gap(a[1], b[1], H)

    def in_view(head, cell):
        return gap(head[0], cell[0], W) <= VIEW and gap(head[1], cell[1], H) <= VIEW

    pearl = {}                       # tile -> where the pearl lying there came from
    eaten = {}                       # tile -> (round, mover, pearl) for the pearl last taken from it
    dying = {}                       # tile -> the dragon that died on it in the current turn
    zero_at = {}                     # tile -> round its spawn countdown runs out (tiles that never spawn: absent)
    looked = {}                      # tile -> (round, had a pearl, zero_at then) at our queen's last look at it

    def kind_of(p):
        """'spawn', 'ours' (body of one of our dragons), 'theirs', or None for no pearl."""
        return None if p is None else 'spawn' if p['kind'] == 'spawn' else 'ours' if p['ours'] else 'theirs'

    def steps_from(body):
        """Her four neighbours: can she step there, is it an open step, a roomy step, and what pearl lies on it."""
        taken = {c for b in bodies.values() for c in b}
        tail = body[-1]
        free = taken - {tail}
        need = 3 * len(body) + 8
        out = []
        for d in 'NESW':
            first = step(body[0], d)
            if first is None or first[0] in taken:
                continue
            seen, frontier, reaches = {first[0]}, [first[0]], False
            while frontier and len(seen) < need and not reaches:
                nxt = []
                for cell in frontier:
                    for e in 'NESW':
                        h = step(cell, e)
                        if h is None or h[0] in free or h[0] in seen:
                            continue
                        seen.add(h[0])
                        nxt.append(h[0])
                        reaches = reaches or h[0] == tail
                frontier = nxt
            out.append(dict(tile=list(first[0]), open=bool(reaches or len(seen) >= need), portal=first[1],
                            roomy=bool(reaches or len(seen) >= len(body) + 2), pearl=kind_of(pearl.get(first[0]))))
        return out

    last = dict(ours_in_view=set(), said=None)    # from our queen's previous turn

    def units():
        return sum(1 for i, b in bodies.items() if b and team_of.get(i) == ours)

    def feeding_now(rnd):
        return rnd > FEED_ROUND or (rnd > FEED_FROM and units() >= CAP_UNITS)

    def look(rnd):
        body = bodies[queen]
        head = body[0]
        mine = {i: b for i, b in bodies.items() if b and team_of.get(i) == ours}
        rest = {i: len(b) for i, b in mine.items() if i != queen}
        lead = min(rest, key=lambda i: (-rest[i], i)) if rest else None
        lead_at = bodies[lead][0] if lead is not None else None
        pressed = any(b and team_of.get(i) != ours and in_view(head, b[0]) for i, b in bodies.items())
        for p in pearl.values():
            if p['kind'] == 'spawn':
                continue
            if p['after'] is None:
                p['after'] = in_view(head, p['tile'])
            if p['inferable'] is None and in_view(head, p['tile']):
                prev = looked.get(p['tile'])
                if prev is None:
                    p['inferable'] = p['tile'] not in zero_at
                else:
                    p['inferable'] = bool(not prev[1] and (prev[2] is None or prev[2] > rnd + INFER_MARGIN))
        for dx in range(-VIEW, VIEW + 1):
            for dy in range(-VIEW, VIEW + 1):
                cell = ((head[0] + dx) % W, (head[1] + dy) % H)
                looked[cell] = (rnd, cell in pearl, zero_at.get(cell))
        last['ours_in_view'] = {c for i, b in mine.items() if i != queen for c in b if in_view(head, c)}
        return dict(round=rnd, len=len(body), start=list(head), end=list(head), units=len(mine),
                    feeding=feeding_now(rnd), lead=lead, lead_len=rest[lead] if lead is not None else 0,
                    lead_at=list(lead_at) if lead_at else None,
                    lead_dist=dist(head, lead_at) if lead_at else None, lead_in_view=bool(lead_at and in_view(head, lead_at)),
                    pressed=pressed, steps=steps_from(body) if rnd > SPLIT_ROUND else [],
                    said=None, said_this_turn=False, pings=0, path=[], bites=[], kind=None, died=None)

    turns = []                       # (round, mover, hash of what happened in that turn)
    turn_ours = []                   # was that turn's mover one of our dragons
    queen_turns = {}                 # round -> our queen's turn
    drops = []                       # every turn a queen ended with no action
    named = []                       # (round, by our queen herself, surely a feeding round) for each turn of one
                                     # of our dragons that named our queen leader without the fed-on-purpose
                                     # mark in or next to a feeding round, on a map of SMALL_CELLS tiles or fewer
    fate = {q: dict(death_round=None, cause=None, own_move=None, len_at_death=None) for q in (queen, foe)}
    alive_at_feed = {queen: False, foe: False}
    len_at_feed = {queen: 0, foe: 0}
    c = Counter()
    on_purpose_from = None           # first round a report carried the fed-on-purpose mark
    rnd, mover, sig, pending, acted, named_turn = 0, None, None, None, None, None

    def close():
        nonlocal sig, pending, acted, named_turn
        if sig is not None:
            turns.append((rnd, mover, sig.hexdigest()[:16]))
            turn_ours.append(team_of.get(mover) == ours)
        if pending is not None:
            if not pending['said_this_turn']:
                # No leader message: she knows none, unless all four pings carried something else this turn.
                pending['said'] = last['said'] if pending['pings'] >= 4 else None
            last['said'] = pending['said']
        sig, pending, acted, named_turn = None, None, None, None

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if kind == 'roundStart':
            close()
            rnd, mover = pl.i32(0), None
            dying.clear()
            if rnd == FEED_ROUND + 1:
                for q in alive_at_feed:
                    alive_at_feed[q] = bool(bodies.get(q))
                    len_at_feed[q] = len(bodies.get(q) or ())
        elif kind == 'turnStart':
            close()
            mover = pl.i32(0)
            sig = hashlib.sha1()
            dying.clear()
        elif kind == 'pearlCountdown':
            zero_at[replay.point(pl.pointer(0))] = rnd + pl.i32(0)
        elif kind == 'tileChange':
            p = replay.point(pl.pointer(0))
            if pl.i32(0):
                pearl[p] = dying.get(p) and dict(dying[p], tile=p) or dict(kind='spawn', round=rnd, tile=p)
            elif p in pearl:
                eaten[p] = (rnd, mover, pearl.pop(p))
        elif kind == 'sonarPing':
            sender, wire = pl.i32(0), pl.u64(16)
            if team_of.get(sender) != ours:
                continue
            if wire not in decoded:
                decoded[wire] = leader_report(key, tag, wire, W, H)
            report = decoded[wire]
            if pending is not None and sender == queen:
                pending['pings'] += 1
                if report is not None:
                    pending['said'], pending['said_this_turn'] = report, True
            if report is None:
                continue
            if report['on_purpose'] and on_purpose_from is None:
                on_purpose_from = rnd
            if (report['id'] == queen and not report['on_purpose'] and W * H <= SMALL_CELLS and named_turn != sender
                    and (rnd > FEED_ROUND or (rnd > FEED_FROM and units() >= CAP_UNITS - CAP_SLACK))):
                named_turn = sender
                named.append((rnd, sender == queen, rnd > FEED_ROUND or units() >= CAP_UNITS + CAP_SLACK))
        elif kind == 'dragonAction':
            did = pl.i32(0)
            a = pl.pointer(0)
            what = a.u16(0) if a else 2
            tle = pl.bit(32)
            detail = ''
            if a is not None and what == 0:
                try:
                    detail = ','.join(str(x) for x in a.pointer(0))
                except Exception:
                    detail = '?'
            elif a is not None and what == 1:
                detail = str(a.i32(4))
            if sig is None:
                mover, sig = did, hashlib.sha1()
            sig.update(f'a{did}:{what}:{detail};'.encode())
            c['timeouts_ours' if team_of.get(did) == ours else 'timeouts_theirs'] += tle
            acted = (did, what, tle)
            if did in (queen, foe) and what == 2 and bodies.get(did):
                drops.append(dict(who='ours' if did == queen else 'theirs', round=rnd, len=len(bodies[did]),
                                  timeout=tle))
            if did == queen and bodies.get(queen):
                pending = look(rnd)
                pending['kind'] = ('move', 'split', 'timeout' if tle else 'drop')[min(what, 2)]
                queen_turns[rnd] = pending
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            h, tp = replay.point(pl.pointer(0)), replay.point(pl.pointer(1))
            if sig is not None:
                sig.update(f'u{did}:{h}:{tp};'.encode())
            b = bodies.setdefault(did, deque())
            before = len(b)
            moved = not b or b[0] != h
            if moved:
                b.appendleft(h)
            while len(b) > 1 and b[-1] != tp:
                b.pop()
            if pending and did == queen and moved:
                pending['end'] = list(h)
                pending['path'].append(list(h))
                if len(b) > before:
                    took = eaten.get(h)
                    took = took[2] if took and took[0] == rnd and took[1] == queen else pearl.get(h)
                    pending['bites'].append((list(h), took))
        elif kind == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x) for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
            if sig is not None:
                sig.update(f's{pa}:{ch}:{len(bodies[ch])};'.encode())
        elif kind == 'dragonDeath':
            did, r = pl.i32(0), pl.u16(4)
            b = bodies.pop(did, None)
            cause = CAUSE[r] if r < len(CAUSE) else 'other'
            if sig is not None:
                sig.update(f'd{did}:{r};'.encode())
            if did in fate and fate[did]['death_round'] is None:
                fate[did] = dict(death_round=rnd, cause=cause, own_move=mover == did, len_at_death=len(b or ()))
            dropped = bool(cause == 'no_action' and acted and acted[0] == did and not acted[2])
            mine = team_of.get(did) == ours
            if dropped and b and did != queen and mine and rnd > FEED_FROM:
                c['feeder_drops_ours'] += 1
            for cell in b or ():
                dying[cell] = dict(kind='drop' if dropped else 'death', ours=mine, id=did, len=len(b), round=rnd,
                                   before=mine and did != queen and cell in last['ours_in_view'], after=None,
                                   inferable=None)
            if pending and did == queen:
                pending['died'] = cause
    close()
    for q in fate:
        fate[q]['final_len'] = len(bodies.get(q) or ())
        fate[q]['alive_at_feed'] = alive_at_feed[q]
        fate[q]['len_at_feed'] = len_at_feed[q]

    marks = []                       # our queen's splits and bites after round SPLIT_ROUND, labelled
    for t in queen_turns.values():
        t['end_dist'] = dist(t['end'], t['lead_at']) if t['lead_at'] else None
        said = t['said']
        t['names_self'] = bool(said and said['id'] == queen)
        t['on_purpose'] = bool(said and said['id'] == queen and said['on_purpose'])
        knows = bool(said and said['id'] != queen)
        t['knows'] = dict(id=said['id'], len=said['len'], as_of=said['when'], at=said['pos']) if said else None
        t['knows_true_leader'] = bool(knows and said['id'] == t['lead'])

        def leave(tile, origin):
            """A pearl she is meant to leave on a turn she is not the one being fed."""
            return bool(not t['names_self'] and (origin == 'ours' or (origin and knows and dist(tile, said['pos']) <= ZONE)))

        t['body_chance'] = bool(t['feeding'] and not t['names_self'] and any(s['pearl'] == 'ours' for s in t['steps']))
        if t['round'] <= SPLIT_ROUND:
            continue
        roomy = sum(s['roomy'] for s in t['steps'])
        where = dict(round=t['round'], len=t['len'], at=t['start'], feeding=t['feeding'], pressed=t['pressed'],
                     steps=len(t['steps']), open_steps=sum(s['open'] for s in t['steps']), roomy_steps=roomy,
                     knows=t['knows'], names_self=t['names_self'], on_purpose=t['on_purpose'],
                     true_leader=t['lead'], true_leader_len=t['lead_len'],
                     true_leader_dist=t['lead_dist'])
        if t['kind'] == 'split':
            marks.append(dict(where, what='split', free=bool(not t['pressed'] and roomy)))
        for n, (cell, took) in enumerate(t['bites']):
            first = n == 0 and cell == t['path'][0]
            clean = bool(not first or any(s['open'] and not s['portal'] and s['tile'] != cell
                                          and not leave(s['tile'], s['pearl']) for s in t['steps']))
            origin = kind_of(took)
            body = took if origin in ('ours', 'theirs') else None
            watched = bool(body and body['before'] and body['after'])
            inferable = bool(body and body['inferable'])
            near_known = bool(knows and dist(cell, said['pos']) <= ZONE)
            near_true = bool(t['lead_at'] and dist(cell, t['lead_at']) <= ZONE)
            marks.append(dict(where, what='bite', tile=cell, pearl=origin,
                              body_of=body and dict(id=body['id'], how=body['kind'], round=body['round'], len=body['len']),
                              watched=watched, inferable=inferable, clean_step=clean, near_known_leader=near_known,
                              to_known_leader=dist(cell, said['pos']) if knows else None,
                              near_true_leader=near_true, to_true_leader=dist(cell, t['lead_at']) if t['lead_at'] else None,
                              free_near_leader=bool(t['feeding'] and near_known and not t['pressed'] and clean),
                              free_on_our_body=bool(t['feeding'] and origin == 'ours' and not t['names_self']
                                                    and (watched or inferable) and not t['pressed'] and clean)))
    for t in queen_turns.values():
        del t['said'], t['steps'], t['bites'], t['path']
    return dict(cells=W * H, win=int(winner == ours), queen_id=queen, turns=turns, turn_ours=turn_ours,
                queen_turns=queen_turns, drops=drops,
                marks=marks, queen=fate[queen], foe_queen=fate[foe], counts=dict(c), named=named,
                on_purpose_from=on_purpose_from)


def collect(directory, tag):
    jobs, keys = [], []
    for p in sorted(glob.glob(os.path.join(directory, f'{tag}_*.replay'))):
        stem = os.path.basename(p)[len(tag) + 1:-len('.replay')]
        m, seed, side = stem.rsplit('_', 2)
        jobs.append((p, side, None))
        keys.append((m, seed, side))
    with cf.ProcessPoolExecutor(int(os.environ.get('CHECK_WORKERS', '4'))) as pool:
        return dict(zip(keys, pool.map(scan, jobs)))


def first_difference(base, cand):
    """Index into the turn lists of the first turn that differs, or None when the two games are the same game."""
    a, b = base['turns'], cand['turns']
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def brief(turn):
    if turn is None:
        return None
    return {k: turn[k] for k in ('kind', 'len', 'start', 'end', 'feeding', 'pressed', 'knows', 'names_self',
                                 'lead', 'lead_len', 'lead_dist', 'end_dist', 'died')}


def after(game, rnd):
    """What became of our queen from round `rnd` on."""
    drop = next((d for d in game['drops'] if d['who'] == 'ours' and d['round'] >= rnd and not d['timeout']), None)
    q = game['queen']
    if drop:
        return f"dropped in round {drop['round']} at length {drop['len']}"
    if q['death_round'] is not None:
        return f"died in round {q['death_round']} ({q['cause']}, {'her own move' if q['own_move'] else 'not her move'})"
    return f"alive at the end, length {q['final_len']}"


def tally(rows):
    """Our queen's splits, bites and feeding turns over a set of games."""
    rows = list(rows)
    marks = [m for g in rows for m in g['marks']]
    splits = [m for m in marks if m['what'] == 'split']
    fed = [m for m in marks if m['what'] == 'bite' and m['feeding']]
    plain = [m for m in fed if not m['names_self']]          # bites on turns she is not the one being fed
    ours = [m for m in plain if m['pearl'] == 'ours']
    turns = [t for g in rows for t in g['queen_turns'].values() if t['feeding']]
    aloof = [t for t in turns if not t['names_self']]
    known = [t for t in turns if t['end_dist'] is not None]
    by_self = [n for g in rows for n in g['named'] if n[1] and n[2]]
    by_others = [n for g in rows for n in g['named'] if not n[1] and n[2]]
    return dict(games=len(rows), feeding_turns=len(turns),
                feeding_turns_fed_on_purpose=sum(t['on_purpose'] for t in turns),
                feeding_turns_not_naming_herself_leader=len(aloof),
                feeding_turns_with_our_body_pearl_in_reach=sum(t['body_chance'] for t in turns),
                feeding_turns_knowing_a_leader=sum(bool(t['knows']) and not t['names_self'] for t in turns),
                feeding_turns_knowing_the_true_leader=sum(t['knows_true_leader'] for t in turns),
                feeding_turns_naming_herself_leader=len(by_self),
                feeding_turns_named_leader_by_our_dragons=len(by_others),
                drops_by_our_other_dragons_after_200=sum(g['counts'].get('feeder_drops_ours', 0) for g in rows),
                splits_after_200=len(splits), free_splits=sum(m['free'] for m in splits),
                splits_pressed=sum(m['pressed'] for m in splits),
                splits_stuck=sum(not m['pressed'] and not m['roomy_steps'] for m in splits),
                bites_in_feeding=len(fed), bites_fed_on_purpose=sum(m['on_purpose'] for m in fed),
                bites_naming_herself_leader_unmarked=sum(m['names_self'] and not m['on_purpose'] for m in fed),
                bites_spawned_pearl=sum(m['pearl'] == 'spawn' for m in plain),
                bites_enemy_body=sum(m['pearl'] == 'theirs' for m in plain),
                bites_our_body=len(ours),
                bites_our_body_dropped_feeder=sum(m['body_of']['how'] == 'drop' for m in ours),
                bites_our_body_watched=sum(m['watched'] for m in ours),
                bites_our_body_inferable_only=sum(m['inferable'] and not m['watched'] for m in ours),
                bites_our_body_not_knowable=sum(not m['watched'] and not m['inferable'] for m in ours),
                bites_our_body_pressed=sum(m['pressed'] for m in ours),
                bites_our_body_no_clean_step=sum(not m['pressed'] and not m['clean_step'] for m in ours),
                free_bites_on_our_body=sum(m['free_on_our_body'] for m in plain),
                bites_near_known_leader=sum(m['near_known_leader'] for m in plain),
                free_bites_near_leader=sum(m['free_near_leader'] for m in plain),
                bites_near_true_leader=sum(m['near_true_leader'] for m in plain),
                bites_near_true_leader_not_known=sum(m['near_true_leader'] and not m['near_known_leader'] for m in plain),
                feeding_turns_ended_within_1_of_true_leader=sum(t['end_dist'] <= 1 for t in known),
                feeding_turns_ended_within_3_of_true_leader=sum(t['end_dist'] <= 3 for t in known))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--replays', required=True)
    ap.add_argument('--base', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    base, cand = collect(a.replays, a.base), collect(a.replays, a.candidate)
    if not base or not cand:
        sys.exit('no replays found for one of the tags')
    if set(base) != set(cand):
        sys.exit(f'unpaired replays: {sorted(set(base) ^ set(cand))}')
    keys = sorted(base)
    games = len(keys)

    pairs = []
    for key in keys:
        b, c = base[key], cand[key]
        i = first_difference(b, c)
        row = dict(map=key[0], seed=key[1], side=key[2], cells=b['cells'], differs=i is not None,
                   base_win=b['win'], candidate_win=c['win'],
                   fed_on_purpose_from={'base': b['on_purpose_from'], 'candidate': c['on_purpose_from']},
                   base_queen=b['queen'], candidate_queen=c['queen'],
                   base_queen_drops=[d for d in b['drops'] if d['who'] == 'ours'],
                   candidate_queen_drops=[d for d in c['drops'] if d['who'] == 'ours'],
                   base_queen_named_leader_rounds=sorted({n[0] for n in b['named']}),
                   candidate_queen_named_leader_rounds=sorted({n[0] for n in c['named']}),
                   base_queen_marks=b['marks'], candidate_queen_marks=c['marks'])
        if i is not None:
            rnd, mover, _ = (b['turns'] if i < len(b['turns']) else c['turns'])[i]
            bt, ct = b['queen_turns'].get(rnd), c['queen_turns'].get(rnd)
            both = i < len(b['turns']) and i < len(c['turns']) and b['turns'][i][:2] == c['turns'][i][:2]
            queen_turn = bool(both and mover == b['queen_id'] and bt is not None and ct is not None)
            first_from = FIRST_FROM_BIG if b['cells'] > BIG_CELLS else FIRST_FROM
            first_named = min((n[0] for n in b['named']), default=None)
            ours_turn = bool(both and b['turn_ours'][i])
            if queen_turn and rnd > first_from:
                label = ('base queen drops' if bt['kind'] == 'drop' else
                         'base queen splits' if bt['kind'] == 'split' else
                         'base queen names herself leader' if bt['names_self'] and not bt['on_purpose'] else
                         'base queen bites' if any(m['what'] == 'bite' and m['round'] == rnd for m in b['marks']) else
                         'other move of the queen')
            elif not queen_turn and ours_turn and first_named is not None and first_named <= rnd:
                label = 'our dragon, after the base game named the queen leader'
            else:
                label = None
            row.update(first_difference_round=rnd, first_difference_mover=mover,
                       first_difference_in_queen_turn=queen_turn, first_difference_from=first_from,
                       base_first_named_queen_leader_round=first_named,
                       first_difference_label=label, first_difference_covered=label is not None,
                       base_turn=brief(bt) if queen_turn else None, candidate_turn=brief(ct) if queen_turn else None,
                       base_queen_after=after(b, rnd), candidate_queen_after=after(c, rnd))
        pairs.append(row)

    differ = [p for p in pairs if p['differs']]
    same = [p for p in pairs if not p['differs']]
    covered = [p for p in differ if p['first_difference_covered']]
    labels = Counter(p['first_difference_label'] for p in covered)

    def drops(rows, who):
        return [d for g in rows for d in g['drops'] if d['who'] == who and not d['timeout']]

    base_ours = drops(base.values(), 'ours')
    base_theirs = drops(base.values(), 'theirs') + drops(cand.values(), 'theirs')
    cand_ours = drops(cand.values(), 'ours')
    base_bot_drops = len(base_ours) + len(base_theirs)

    def queens(rows):
        rows = list(rows)
        return dict(alive_when_feeding_starts=sum(g['queen']['alive_at_feed'] for g in rows),
                    alive_at_end=sum(g['queen']['death_round'] is None for g in rows),
                    length_when_feeding_starts_sum=sum(g['queen']['len_at_feed'] for g in rows),
                    final_length_sum=sum(g['queen']['final_len'] for g in rows),
                    foe_queen_final_length_sum=sum(g['foe_queen']['final_len'] for g in rows),
                    longer_queen_at_end=sum(g['queen']['final_len'] > g['foe_queen']['final_len'] for g in rows),
                    wins=sum(g['win'] for g in rows),
                    deaths_by_cause=dict(Counter(g['queen']['cause'] for g in rows if g['queen']['cause'])),
                    timeouts=sum(g['counts'].get('timeouts_ours', 0) for g in rows),
                    timeout_no_action_turns=sum(d['timeout'] for g in rows for d in g['drops'] if d['who'] == 'ours'))

    bs, cs = tally(base.values()), tally(cand.values())
    named_candidate = cs['feeding_turns_naming_herself_leader'] + cs['feeding_turns_named_leader_by_our_dragons']
    checks = {
        'only_what_the_switch_covers': len(covered) == len(differ),
        'target_seen': (base_bot_drops >= TARGET_MIN and cs['feeding_turns_not_naming_herself_leader'] >= EXPOSED_MIN
                        and cs['feeding_turns_with_our_body_pearl_in_reach'] >= BODY_MIN),
        'never_drops': len(cand_ours) == 0,
        'no_free_split': cs['free_splits'] == 0,
        'no_free_bite_near_leader': cs['free_bites_near_leader'] == 0,
        'it_acted': len(differ) >= ACTED_MIN,
        'no_free_bite_on_our_body': cs['free_bites_on_our_body'] == 0,
        'not_the_leader': named_candidate == 0,
    }
    passed = all(checks.values())
    mechanism_shown = all(v for k, v in checks.items() if k != 'target_seen')
    failed = [k for k, v in checks.items() if not v]
    dropped_after = sum(p['base_queen_after'].startswith('dropped') for p in differ)
    cand_alive_after = sum(p['candidate_queen_after'].startswith('alive') for p in differ)
    bq, cq = queens(base.values()), queens(cand.values())
    note = (
        f"{'PASS' if passed else 'FAIL'} ({'all eight checks' if passed else 'failed: ' + ', '.join(failed)}). "
        f"{games} paired games. Drops (queen ends her turn with no action and dies to feed the leader): base-bot "
        f"queens {base_bot_drops} (ours in base games {len(base_ours)}, the opponent's {len(base_theirs)}), our "
        f"switch-on queen {len(cand_ours)}. Our switch-on queen had {cs['feeding_turns']} turns in feeding rounds, "
        f"{cs['feeding_turns_not_naming_herself_leader']} of them without naming herself leader (base "
        f"{bs['feeding_turns']} and {bs['feeding_turns_not_naming_herself_leader']}); in "
        f"{cs['feeding_turns_with_our_body_pearl_in_reach']} of those one of our dragons' body pearls lay on a tile "
        f"she could step on (base {bs['feeding_turns_with_our_body_pearl_in_reach']}). Her bites (growing on a "
        f"tile) on those turns: {cs['bites_spawned_pearl']} spawned pearls, {cs['bites_enemy_body']} enemy bodies, "
        f"{cs['bites_our_body']} bodies of our own dragons ({cs['bites_our_body_dropped_feeder']} a dropped "
        f"feeder; {cs['bites_our_body_watched']} she had watched appear, {cs['bites_our_body_inferable_only']} "
        f"more that no spawn explains, {cs['bites_our_body_not_knowable']} she could not tell; "
        f"{cs['bites_our_body_pressed']} with an enemy head in view, {cs['bites_our_body_no_clean_step']} with no "
        f"clean step), free bites on our body {cs['free_bites_on_our_body']}; base queen "
        f"{bs['bites_spawned_pearl']} spawned, {bs['bites_our_body']} our bodies, free "
        f"{bs['free_bites_on_our_body']}. Bites on turns she named herself leader: without the fed-on-purpose "
        f"mark {cs['bites_naming_herself_leader_unmarked']} (base {bs['bites_naming_herself_leader_unmarked']}), "
        f"fed on purpose {cs['bites_fed_on_purpose']} (base {bs['bites_fed_on_purpose']}). Bites within {ZONE} "
        f"tiles of the leader she knew: "
        f"{cs['bites_near_known_leader']}, free {cs['free_bites_near_leader']} (base "
        f"{bs['bites_near_known_leader']}, free {bs['free_bites_near_leader']}); within {ZONE} of the true leader "
        f"when she did not know of it there: {cs['bites_near_true_leader_not_known']} (base "
        f"{bs['bites_near_true_leader_not_known']}). Feeding turns in which she named herself leader without "
        f"being fed on purpose: {cs['feeding_turns_naming_herself_leader']} (base "
        f"{bs['feeding_turns_naming_herself_leader']}); turns of our other dragons naming her so: "
        f"{cs['feeding_turns_named_leader_by_our_dragons']} (base {bs['feeding_turns_named_leader_by_our_dragons']}). "
        f"Her splits after round {SPLIT_ROUND}: {cs['splits_after_200']}, free (no enemy head in view and a step "
        f"with room) {cs['free_splits']}, with an enemy head in view {cs['splits_pressed']}, stuck "
        f"{cs['splits_stuck']}; base queen {bs['splits_after_200']}, free {bs['free_splits']}. Pairs that differ: "
        f"{len(differ)} of {games}; first difference covered by the switch in {len(covered)} of them "
        f"({dict(labels)}). After it, the base queen went on to drop in {dropped_after} of {len(differ)} pairs; the "
        f"switch-on queen was alive at the end in {cand_alive_after}. Our queen alive when feeding starts (round "
        f"{FEED_ROUND + 1}): base {bq['alive_when_feeding_starts']}, switch on {cq['alive_when_feeding_starts']} "
        f"of {games}. Raw, not judged: feeding turns she ended within 3 tiles of the true leader, switch on "
        f"{cs['feeding_turns_ended_within_3_of_true_leader']} of {cs['feeding_turns']}, base "
        f"{bs['feeding_turns_ended_within_3_of_true_leader']} of {bs['feeding_turns']}; queen length at the end, "
        f"summed, ours:theirs base {bq['final_length_sum']}:{bq['foe_queen_final_length_sum']}, switch on "
        f"{cq['final_length_sum']}:{cq['foe_queen_final_length_sum']}; wins base {bq['wins']}, switch on "
        f"{cq['wins']} of {games}.")
    out = {
        'passed': passed,
        'note': note,
        'target_seen': checks['target_seen'],
        'mechanism_shown': mechanism_shown,
        'checks': checks,
        'thresholds': {'TARGET_MIN': TARGET_MIN, 'EXPOSED_MIN': EXPOSED_MIN, 'BODY_MIN': BODY_MIN,
                       'ACTED_MIN': ACTED_MIN, 'FIRST_FROM': FIRST_FROM, 'FIRST_FROM_BIG': FIRST_FROM_BIG},
        'games': games,
        'queen_drops': {'base_bot_all': base_bot_drops, 'base_ours': len(base_ours), 'base_bot_opponent': len(base_theirs),
                        'candidate_ours': len(cand_ours)},
        'queen_drop_rounds': {'base_ours': sorted(d['round'] for d in base_ours),
                              'base_bot_opponent': sorted(d['round'] for d in base_theirs),
                              'candidate_ours': sorted(d['round'] for d in cand_ours)},
        'our_queen': {'base': dict(bs, **bq), 'candidate': dict(cs, **cq)},
        'pairs_that_differ': len(differ),
        'pairs_same_game_to_the_end': len(same),
        'pairs_same_game_queen_dead_before_feeding': sum(not p['base_queen']['alive_at_feed'] for p in same),
        'pairs_first_difference_covered': len(covered),
        'first_difference_rounds': sorted(p['first_difference_round'] for p in differ),
        'first_difference_labels': dict(labels),
        'after_first_difference': {'base_queen_dropped': dropped_after, 'candidate_queen_alive_at_end': cand_alive_after},
        'limits': 'Pearl origins, drops, splits and what each dragon told its team are exact, read from the replay. '
                  '"The leader she knows" is what she sent after her move; the bot decides on the same belief. '
                  '"Open step", "roomy step" and "pressed" are rebuilt from true positions, while the bot uses what '
                  'it has seen, so those labels are close, not exact; every split and bite is listed per pair so a '
                  'person can look. A body pearl she neither watched appear nor could infer from the tile\'s spawn '
                  'countdown looks like any other pearl to her, so bites on those are counted but not judged. An '
                  'enemy body she did not watch appear is left alone too. Whether her being near '
                  'the leader cost it any length is not measured. After the first difference the two games of a '
                  'pair drift apart for many reasons, so what became of the queens later, lengths and wins are raw '
                  'numbers, not effects of the switch. A queen that is dead before round 200 shows nothing either '
                  'way.',
        'pairs': pairs,
    }
    with open(a.output, 'w') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print(note)


if __name__ == '__main__':
    main()
