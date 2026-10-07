#!/usr/bin/env python3
"""Card #54 avoiding-long mechanism check (LONG_SAFETY): do our dragons of 31 or longer stay off the tiles an enemy
head can crash into this turn, and what do they do when no such tile is left?

usage: python3 work/card_54_check.py --replays DIR --base base --candidate candidate --output FILE
Replays are DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1), paired by (map, seed, side).

Who is judged: every action of one of our dragons that is 31 or longer when it decides, our queen (dragon id 0/1)
left out, she has her own rules from card 39. For each such action the check rebuilds, from the replay alone, what the
dragon could see (the 7x7 box around its head) and the rings the bot draws:

  free ring  = tiles a visible enemy head, the enemy queen aside, can walk onto this turn with its free steps
               (ceil(length/4): 1 for an enemy 2-4 long, 2 for 5-8, 3 for 9-12 ...; length = the most parts our dragon
               has seen of it in the last 3 rounds)
  pay ring   = one tile further, which that head only reaches by paying 1 length (a 2-long enemy cannot pay). An
               enemy whose visible body touches the edge of the view counts as one part longer, at least 3 long
  memory     = an enemy head our dragon saw in the last 3 rounds but cannot see now. It may stand on any tile it could
               have walked to at one step per round out of view, that is not in sight now and not behind where it was
               heading; the same two rings are drawn around all of those tiles (always free steps + 1)
  ringed     = in any of these. Kelp walls and portals are walked, bodies in view block.

  ending     = the tile the head is on once the action is done (its own tile if it split or did nothing). A split
               that leaves the dragon shorter than 31 is not counted as a long dragon's ending
  touch      = a tile it could step onto, or its own tile, was ringed (the rule had something to say)
  clean step = a tile it could step onto, not ringed, that is not a dead-end pocket (a pocket = it can reach neither
               its tail nor length + 2 tiles from there)
  avoidable  = touch, and a clean step was open
  stuck      = a tile it could step onto was ringed and no clean step was open
  way out    = stuck, but a run of 2+ steps to a tile in view that is not ringed and not a pocket exists: 'free' within
               its free steps (at most 6, the bot's stride cap), 'paid' up to 2 steps beyond its free steps
  clean ending possible = avoidable, or stuck with a way out, or stuck with no way out while its own tile is not
               ringed (it can split 2 off and stay)
  missed     = a clean ending was possible and the action still ended on a ringed tile

PASS RULE (fixed before any switch-on game was played; constants below):
  1. target seen: base shows at least TARGET_MIN missed endings, and the switch-on side has at least TOUCH_MIN
     decisions where a clean ending was possible (otherwise there is nothing to compare);
  2. cut: switch-on missed endings per decision where a clean ending was possible are at most CUT x base's;
  3. way out, judged only if it comes up: with at least EXIT_N switch-on stuck decisions that had a way out, at least
     EXIT_OK of them end on a tile that is not ringed;
  4. split, judged only if it comes up: with at least SPLIT_N switch-on stuck decisions that had no way out, at least
     SPLIT_OK of them are splits (2 off the tail, or everything but 2 when it is cornered on a ringed tile).
passed = 1 and 2, and 3 and 4 where they come up. target_seen = rule 1, mechanism_shown = rules 1 and 2.
Rules 3-4 report "not seen" below their minimum and do not fail the check then.
NOT part of the pass rule (16 games per side cannot settle them, the outcome A/B does): how often a 31+ dragon is
rammed and by what, pearls those dragons eat, length split off while stuck, lengths and wins.
The bot's own log lines are not used: the game runner drops them.
Known before any switch-on game, from running this check on base-only replays (base against base) kept by earlier
cards, whose bases are older, and by this build's identity run, 104 game views in all: 35028 decisions by 31+ dragons,
687 touch, 331 avoidable of which 11 ended ringed, 332 stuck (166 with a way out, 86 of those ended not ringed; 166
with none, 15 splits). So base already takes the clean step when one is open, and the switch is expected to show on
stuck turns; that is why the target counts missed endings of all three kinds and not the avoidable ones alone. Maps of
1200 tiles or fewer had almost no touch decisions in base (13 in 52 game views), so the run is mostly on larger maps.
"""
import argparse, glob, hashlib, json, os, sys, concurrent.futures as cf
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before any switch-on game)
TARGET_MIN = 5       # base missed endings needed to call the target seen
TOUCH_MIN = 20       # switch-on decisions with a clean ending possible needed to compare at all
CUT = 0.25           # switch-on missed endings per decision with a clean ending possible: at most this fraction of base's
EXIT_N = 5           # switch-on stuck decisions with a way out needed to judge the way-out rule
EXIT_OK = 0.75       # share of those that must end on a tile that is not ringed
SPLIT_N = 5          # switch-on stuck decisions with no way out needed to judge the split rule
SPLIT_OK = 0.75      # share of those that must be splits

LONG_MIN = 31        # LS_MIN_LENGTH
VIEW = 3             # the bot sees a 7x7 box around its head
GHOST_ROUNDS = 3     # how long the bot remembers an enemy head
FREE_DIV = 4         # free steps per turn = ceil(length / 4)
MIN_SIZE = 2         # a dragon cannot pay itself below this
START_SIZE = 3       # INITIAL_LENGTH: the least a half-hidden enemy is taken to be
PAY_STEPS = 1        # LS_PAY_STEPS: paid steps an enemy is expected to add
ESCAPE_COST = 2      # LS_ESCAPE_COST: the most length a long dragon pays to run out
RUN_MAX = 6          # STRIDE_MAX: the most steps of a free run
CAUSE = ['wall', 'self', 'body', 'headon', 'none']
DIRS = 'NESW'
OFFSET = {'N': (0, -1), 'E': (1, 0), 'S': (0, 1), 'W': (-1, 0)}


def load_map(text):
    """Returns W, H and step(cell, d) -> (next cell, through a portal) or None for kelp / an unpaired portal."""
    lines = text.splitlines()
    W, H = map(int, lines[0].split()[1:3])
    S = 2 * (W + 1)
    kind, pid_of, members = {}, {}, {}
    for l in lines:
        q = l.split()
        if not q or q[0] != 'EDGE':
            continue
        i, t = int(q[1]), int(q[2])
        if t == 0:
            continue
        y, r = divmod(i, S)
        if r < W + 1:
            if r == W:
                continue
            key = ('N', r, y % H)
        else:
            if y >= H:
                continue
            key = ('W', (r - (W + 1)) % W, y)
        if t >= kind.get(key, 0):
            kind[key] = t
            if t == 2 and len(q) > 3:
                pid_of[key] = int(q[3])
    for key, pid in pid_of.items():
        if kind.get(key) == 2:
            members.setdefault(pid, []).append(key)
    pair = {}
    for keys in members.values():
        if len(keys) == 2 and keys[0][0] == keys[1][0]:
            pair[keys[0]], pair[keys[1]] = keys[1], keys[0]

    def step(cell, d):
        x, y = cell
        if d == 'N':
            key, straight = ('N', x, y), (x, (y - 1) % H)
        elif d == 'S':
            key, straight = ('N', x, (y + 1) % H), (x, (y + 1) % H)
        elif d == 'W':
            key, straight = ('W', x, y), ((x - 1) % W, y)
        else:
            key, straight = ('W', (x + 1) % W, y), ((x + 1) % W, y)
        t = kind.get(key, 0)
        if t == 0:
            return straight, False
        other = pair.get(key) if t == 2 else None
        if other is None:
            return None
        _, bx, by = other
        if d == 'N':
            return (bx, (by - 1) % H), True
        if d == 'W':
            return ((bx - 1) % W, by), True
        return (bx, by), True

    return W, H, step


def gap(a, b, size):
    raw = abs(a - b)
    return min(raw, size - raw)


def signed_gap(a, b, size):
    g = (b - a) % size
    return g - size if 2 * g > size else g


def free_steps(parts):
    return max(1, (parts + FREE_DIV - 1) // FREE_DIV)


def full_reach(size):
    """Free plus paid steps of a dragon this long."""
    return free_steps(size) + max(0, size - MIN_SIZE)


def flood(step, starts, reach, blocked, target):
    """Steps a head on any of `starts` needs onto each tile within `reach`; also the steps onto `target`, or None."""
    dist = {s: 0 for s in starts}
    frontier = list(starts)
    touch = None
    for n in range(reach):
        nxt = []
        for cell in frontier:
            for d in DIRS:
                hop = step(cell, d)
                if hop is None:
                    continue
                to = hop[0]
                if to == target and touch is None:
                    touch = n + 1
                if to in dist or to in blocked:
                    continue
                dist[to] = n + 1
                nxt.append(to)
        frontier = nxt
    return dist, touch


def walk_dist(step, start, target, limit):
    """Steps from `start` onto `target`, bodies ignored, or None beyond `limit`."""
    seen = {start}
    frontier = [start]
    for n in range(limit):
        nxt = []
        for cell in frontier:
            for d in DIRS:
                hop = step(cell, d)
                if hop is None:
                    continue
                to = hop[0]
                if to == target:
                    return n + 1
                if to in seen:
                    continue
                seen.add(to)
                nxt.append(to)
        frontier = nxt
    return None


def fits(step, start, body, others):
    """Bot-style room test for stepping onto `start`: the dragon can reach its tail or at least length + 2 tiles."""
    size = len(body)
    free_at = {cell: size - k + 1 for k, cell in enumerate(body)}
    steps = {start: 1}
    frontier = [start]
    while frontier:
        nxt = []
        for cell in frontier:
            for d in DIRS:
                hop = step(cell, d)
                if hop is None:
                    continue
                to = hop[0]
                arrive = steps[cell] + 1
                if to in steps or to in others or arrive < free_at.get(to, 0):
                    continue
                steps[to] = arrive
                if to == body[-1] or len(steps) >= size + 2:
                    return True
                nxt.append(to)
        frontier = nxt
    return False


def one(job):
    path, side = job
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
    queen = next((i for i in (0, 1) if team_of.get(i) == ours), None)
    foe_queen = next((i for i in (0, 1) if team_of.get(i) != ours), None)
    c = Counter(games=1, win=int(winner == ours))
    track = hashlib.sha1()

    memory = {}          # our dragon -> {enemy: (round last seen, parts, head tile, heading)}
    last = {}            # our long dragon -> how its last finished action left it
    pending = None
    mover = None
    act_from, act_len = None, 0
    rnd = 0

    def heading(b):
        if len(b) < 2:
            return None
        for d in DIRS:
            hop = step(b[1], d)
            if hop is not None and hop[0] == b[0]:
                return d
        return None

    def sight(viewer):
        """Enemy heads in view, the enemy queen aside; also what the bot keeps in mind of them."""
        head = bodies[viewer][0]
        mind = memory.setdefault(viewer, {})
        foes = []
        for did, b in bodies.items():
            if not b or team_of.get(did) == ours or did == foe_queen:
                continue
            if gap(b[0][0], head[0], W) > VIEW or gap(b[0][1], head[1], H) > VIEW:
                continue
            inside = [cell for cell in b if gap(cell[0], head[0], W) <= VIEW and gap(cell[1], head[1], H) <= VIEW]
            was = mind.get(did)
            parts = max(len(inside), was[1]) if was and rnd - was[0] <= GHOST_ROUNDS else len(inside)
            mind[did] = (rnd, parts, b[0], heading(b))
            cut = any(gap(cell[0], head[0], W) == VIEW or gap(cell[1], head[1], H) == VIEW for cell in inside)
            foes.append((did, b[0], parts, len(inside), cut))
        return foes

    def look(viewer, foes):
        body = bodies[viewer]
        head = body[0]
        size = len(body)

        def in_view(cell):
            return gap(cell[0], head[0], W) <= VIEW and gap(cell[1], head[1], H) <= VIEW

        own = set(body)
        seen_block = set(own)
        seen_block.discard(body[-1])
        taken = set(own)
        others = set()
        for did, b in bodies.items():
            if not b or did == viewer:
                continue
            taken.update(b)
            inside = [cell for cell in b if in_view(cell)]
            seen_block.update(inside)
            others.update(inside)
        hit, pay, mem_hit, mem_pay = set(), set(), set(), set()
        own_zone = 0
        for did, at, parts, shown, cut in foes:
            free = free_steps(parts)
            guess = max(parts, shown + 1, START_SIZE) if cut else parts
            dist, touch = flood(step, [at], min(full_reach(guess), free + PAY_STEPS), seen_block, head)
            del dist[at]
            hit.update(t for t, n in dist.items() if n <= free)
            pay.update(dist)
            if touch is not None:
                own_zone = max(own_zone, 2 if touch <= free else 1)
        in_sight = {f[0] for f in foes}
        remembered = set()
        for did, (when, parts, at, face) in memory.get(viewer, {}).items():
            if did in in_sight or when >= rnd or rnd - when > GHOST_ROUNDS:
                continue
            fx, fy = OFFSET.get(face, (0, 0))
            spots = [t for t in flood(step, [at], rnd - when, seen_block, None)[0]
                     if not in_view(t) and signed_gap(at[0], t[0], W) * fx + signed_gap(at[1], t[1], H) * fy >= 0]
            if not spots:
                continue
            remembered.add(did)
            free = free_steps(parts)
            dist, touch = flood(step, spots, free + PAY_STEPS, seen_block, head)
            mem_hit.update(t for t, n in dist.items() if n <= free)
            mem_pay.update(dist)
            if touch is not None:
                own_zone = max(own_zone, 2 if touch <= free else 1)

        def zone(t):
            return 2 if t in hit or t in mem_hit else 1 if t in pay or t in mem_pay else 0

        walk = []
        for d in DIRS:
            hop = step(head, d)
            if hop is not None and not hop[1] and hop[0] not in taken:
                walk.append(hop[0])
        zones = {t: zone(t) for t in walk}
        roomy = {t: fits(step, t, body, others) for t in walk}
        ringed_step = any(zones.values())
        safe = any(zones[t] == 0 and roomy[t] for t in walk)
        stuck = ringed_step and not safe
        run = None
        if stuck:
            mine = min(free_steps(size), RUN_MAX)
            depth = {head: 0}
            frontier = [head]
            for n in range(min(full_reach(size), free_steps(size) + ESCAPE_COST)):
                nxt = []
                for cell in frontier:
                    for d in DIRS:
                        hop = step(cell, d)
                        if hop is None or hop[1]:
                            continue
                        to = hop[0]
                        if to in depth or to in taken or not in_view(to):
                            continue
                        depth[to] = n + 1
                        nxt.append(to)
                        if n + 1 >= 2 and run is None and zone(to) == 0 and fits(step, to, body, others):
                            run = 'free' if n + 1 <= mine else 'paid'
                frontier = nxt
                if run:
                    break
        return dict(id=viewer, start=head, len=size, rnd=rnd, view=bool(foes), saw=in_sight, mind=remembered,
                    seen_ring=hit | pay, zone=zone, own=own_zone, touch=own_zone > 0 or ringed_step, safe=safe,
                    stuck=stuck, run=run, short_foe=any(f[2] <= 5 for f in foes), seen=0, dead=False, cause=None,
                    child=0, kind='other', n=0)

    def close():
        nonlocal pending
        p, pending = pending, None
        if p is None:
            return
        did = p['id']
        avoidable = p['touch'] and p['safe']
        way = p['run'] if p['stuck'] else None
        stay = p['stuck'] and way is None and p['own'] == 0
        possible = avoidable or way is not None or stay
        c['decisions'] += 1
        c['possible'] += possible
        c['possible_by_staying'] += stay
        c['enemy_head_in_view'] += p['view']
        c['enemy_head_in_mind'] += bool(p['mind'])
        c['touch'] += p['touch']
        c['avoidable'] += avoidable
        c['stuck'] += p['stuck']
        c['stuck_way_out'] += way is not None
        c['stuck_no_way_out'] += p['stuck'] and way is None
        c['stuck_short_foe'] += p['stuck'] and p['short_foe']
        b = bodies.get(did)
        if p['dead'] or not b:
            c['died_acting'] += 1
            c['died_acting_' + (p['cause'] or 'other')] += 1
            c['avoidable_died_acting'] += avoidable
            last.pop(did, None)
            return
        after = len(b)
        moved = p['kind'] == 'move'
        if moved:
            end = b[0]
            where = p['zone'](end)
            source = 'seen' if end in p['seen_ring'] else 'remembered'
            cost = max(0, p['n'] - free_steps(p['len']))
            c['moves'] += 1
            c['multi_moves'] += p['n'] >= 2
            c['paid_moves'] += cost > 0
            c['length_paid'] += cost
            c['pearls'] += max(0, after - p['len'] + cost)
            c['path_checked'] += 1
            c['path_mismatch'] += p['seen'] != p['n']
        else:
            end = p['start']
            where = p['own']
            source = 'own_tile'
            c['splits' if p['kind'] == 'split' else 'other_actions'] += 1
            if p['kind'] == 'split':
                c['splits_of_2'] += p['child'] == MIN_SIZE
                c['splits_keeping_2'] += p['child'] == p['len'] - MIN_SIZE
                c['length_split_off'] += p['child']
                c['stuck_splits'] += p['stuck']
                c['stuck_length_split_off'] += p['child'] if p['stuck'] else 0
        # A split that leaves it shorter than 31 hands the body on: not a long dragon's ending.
        counted = moved or after >= LONG_MIN
        ringed = counted and where > 0
        c['ended_ringed'] += ringed
        if possible and ringed:
            c['missed'] += 1
            c['missed_' + ('avoidable' if avoidable else 'way_out' if way else 'stay')] += 1
            c['missed_free' if where == 2 else 'missed_pay'] += 1
        if avoidable and ringed:
            c['danger'] += 1
            c['danger_free' if where == 2 else 'danger_pay'] += 1
            c['danger_move' if moved else 'danger_stay'] += 1
            c['danger_' + source] += 1
        if way:
            c['exit_' + way] += 1
            c['exit_ok'] += not ringed
            c['exit_ok_by_run'] += moved and p['n'] >= 2 and not ringed
        elif p['stuck']:
            split = p['kind'] == 'split'
            c['noexit_split'] += split
            c['noexit_split_of_2'] += split and p['child'] == MIN_SIZE
            c['noexit_split_keeping_2'] += split and p['child'] == p['len'] - MIN_SIZE
            c['noexit_moved_ringed'] += moved and where > 0
            c['noexit_moved_out'] += moved and where == 0
            c['noexit_other'] += not split and not moved
        if after >= LONG_MIN:
            last[did] = dict(rnd=p['rnd'], ringed=ringed, avoidable=avoidable, stuck=p['stuck'], saw=p['saw'], mind=p['mind'])
        else:
            last.pop(did, None)

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if kind == 'roundStart':
            close()
            mover = None
            act_from, act_len = None, 0
            rnd = pl.i32(0)
            track.update(f'r{rnd}'.encode())
        elif kind == 'dragonAction':
            close()
            mover = pl.i32(0)
            a = pl.pointer(0)
            b = bodies.get(mover)
            act_from, act_len = (b[0], len(b)) if b else (None, 0)
            if not b or team_of.get(mover) != ours or mover == queen:
                continue
            foes = sight(mover)
            if a is None or len(b) < LONG_MIN:
                continue
            pending = look(mover, foes)
            what = a.u16(0)
            pending['kind'] = 'move' if what == 0 else 'split' if what == 1 else 'other'
            try:
                pending['n'] = max(1, len(a.pointer(0))) if what == 0 else 0
            except Exception:
                pending['n'] = 1
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            h = replay.point(pl.pointer(0))
            tp = replay.point(pl.pointer(1))
            track.update(f'u{did}{h}{tp}'.encode())
            b = bodies.setdefault(did, deque())
            if not b or b[0] != h:
                if b:
                    c['hops'] += 1
                    c['hop_mismatch'] += all((step(b[0], d) or (None,))[0] != h for d in DIRS)
                b.appendleft(h)
                if pending and did == pending['id']:
                    pending['seen'] += 1
            while len(b) > 1 and b[-1] != tp:
                b.pop()
        elif kind == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            track.update(f's{pa}{ch}'.encode())
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x) for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
            if pending and pa == pending['id']:
                pending['child'] = len(bodies[ch])
        elif kind == 'dragonDeath':
            did = pl.i32(0)
            r = pl.u16(4)
            track.update(f'd{did}{r}'.encode())
            b = bodies.pop(did, None)
            cause = CAUSE[r] if r < 5 else 'other'
            if pending and did == pending['id']:
                pending['dead'] = True
                pending['cause'] = cause
            if team_of.get(did) != ours or did == queen or not b or len(b) < LONG_MIN:
                continue
            c['long_deaths'] += 1
            c['long_deaths_' + cause] += 1
            c['long_death_length'] += len(b)
            if cause != 'headon' or mover == did:
                continue
            if team_of.get(mover) == ours:
                c['long_hit_by_teammate'] += 1
                continue
            c['rammed'] += 1
            c['rammed_length'] += len(b)
            c['rammer_short' if act_len <= 5 else 'rammer_long'] += 1
            was = last.get(did)
            if was is None:
                c['rammed_before_first_long_turn'] += 1
            else:
                c['rammed_after_ringed_ending' if was['ringed'] else 'rammed_after_clean_ending'] += 1
                c['rammed_ringed_avoidable'] += was['ringed'] and was['avoidable']
                c['rammed_ringed_stuck'] += was['ringed'] and was['stuck']
                c['rammer_was_in_view' if mover in was['saw'] else 'rammer_was_in_mind' if mover in was['mind']
                  else 'rammer_was_unseen'] += 1
            came = walk_dist(step, act_from, b[0], 14) if act_from else None
            if came is None:
                c['rammer_came_unknown'] += 1
            else:
                paid = came - free_steps(act_len)
                c['rammer_free' if paid <= 0 else 'rammer_paid_1' if paid == 1 else 'rammer_paid_more'] += 1
    close()
    longest = max((len(b) for did, b in bodies.items() if b and team_of.get(did) == ours and did != queen), default=0)
    c['long_alive_at_end'] = sum(1 for did, b in bodies.items()
                                 if b and team_of.get(did) == ours and did != queen and len(b) >= LONG_MIN)
    c['longest_other_than_queen_at_end'] = longest
    c['queen_final_len'] = len(bodies.get(queen) or ())
    c['foe_queen_final_len'] = len(bodies.get(foe_queen) or ())
    return W * H, dict(c), track.hexdigest()


def collect(directory, tag):
    jobs, keys = [], []
    for p in sorted(glob.glob(os.path.join(directory, f'{tag}_*.replay'))):
        stem = os.path.basename(p)[len(tag) + 1:-len('.replay')]
        m, seed, side = stem.rsplit('_', 2)
        jobs.append((p, side))
        keys.append((m, seed, side))
    with cf.ProcessPoolExecutor(int(os.environ.get('CHECK_WORKERS', '4'))) as pool:
        return dict(zip(keys, pool.map(one, jobs)))


def total(rows):
    s = Counter()
    for r in rows:
        s.update(r)
    return s


def share(a, b):
    return a / b if b else 0.0


def view(s):
    g = max(1, s['games'])
    return {
        'games': s['games'], 'wins': s['win'],
        'decisions_by_31plus_dragons': s['decisions'],
        'with_an_enemy_head_in_view': s['enemy_head_in_view'],
        'with_a_remembered_enemy_head': s['enemy_head_in_mind'],
        'touch_decisions': s['touch'],
        'clean_ending_possible_decisions': s['possible'],
        'missed_endings': s['missed'],
        'missed_endings_per_possible_decision': round(share(s['missed'], s['possible']), 4),
        'missed_endings_by_case': {'clean_step_open': s['missed_avoidable'], 'stuck_with_a_way_out': s['missed_way_out'],
                                   'stuck_could_split_and_stay': s['missed_stay']},
        'missed_endings_by_ring': {'free': s['missed_free'], 'pay': s['missed_pay']},
        'avoidable_decisions': s['avoidable'],
        'avoidable_ringed_endings': s['danger'],
        'avoidable_ringed_endings_per_avoidable_decision': round(share(s['danger'], s['avoidable']), 4),
        'avoidable_ringed_endings_by_ring': {'free': s['danger_free'], 'pay': s['danger_pay']},
        'avoidable_ringed_endings_by_action': {'moved_in': s['danger_move'], 'stayed': s['danger_stay']},
        'avoidable_ringed_endings_by_source': {'head_in_view': s['danger_seen'], 'remembered_head_only': s['danger_remembered'],
                                               'own_tile': s['danger_own_tile']},
        'avoidable_decisions_where_it_died_acting': s['avoidable_died_acting'],
        'all_ringed_endings': s['ended_ringed'],
        'stuck_decisions': s['stuck'],
        'stuck_with_a_short_enemy_in_view': s['stuck_short_foe'],
        'stuck_with_a_way_out': {'decisions': s['stuck_way_out'], 'free_run': s['exit_free'], 'paid_run': s['exit_paid'],
                                 'ended_not_ringed': s['exit_ok'], 'of_those_by_a_run_of_2plus': s['exit_ok_by_run']},
        'stuck_with_no_way_out': {'decisions': s['stuck_no_way_out'], 'split': s['noexit_split'],
                                  'split_2_off': s['noexit_split_of_2'], 'split_all_but_2_off': s['noexit_split_keeping_2'],
                                  'moved_onto_a_ringed_tile': s['noexit_moved_ringed'], 'moved_out': s['noexit_moved_out'],
                                  'no_action': s['noexit_other']},
        'splits': s['splits'], 'splits_while_stuck': s['stuck_splits'],
        'length_split_off_while_stuck': s['stuck_length_split_off'],
        'moves': s['moves'], 'multi_step_moves': s['multi_moves'], 'paid_moves': s['paid_moves'],
        'length_paid_for_moves': s['length_paid'],
        'pearls_eaten': s['pearls'], 'pearls_per_100_decisions': round(100 * share(s['pearls'], s['decisions']), 2),
        'died_acting': {k[len('died_acting_'):]: v for k, v in sorted(s.items()) if k.startswith('died_acting_')},
        'deaths_of_31plus_dragons': s['long_deaths'],
        'deaths_by_cause': {k[len('long_deaths_'):]: v for k, v in sorted(s.items()) if k.startswith('long_deaths_')},
        'rammed_by_an_enemy_head': s['rammed'],
        'rammed_per_1000_decisions': round(1000 * share(s['rammed'], s['decisions']), 2),
        'rammed_mean_length_lost': round(share(s['rammed_length'], s['rammed']), 1),
        'rammer_length': {'5_or_shorter': s['rammer_short'], 'longer': s['rammer_long']},
        'rammer_steps': {'free': s['rammer_free'], 'paid_1': s['rammer_paid_1'], 'paid_more': s['rammer_paid_more'],
                         'unknown': s['rammer_came_unknown']},
        'rammer_at_our_last_decision': {'in_view': s['rammer_was_in_view'], 'remembered': s['rammer_was_in_mind'],
                                        'unseen': s['rammer_was_unseen']},
        'rammed_after': {'a_ringed_ending': s['rammed_after_ringed_ending'], 'of_those_avoidable': s['rammed_ringed_avoidable'],
                         'of_those_stuck': s['rammed_ringed_stuck'], 'a_clean_ending': s['rammed_after_clean_ending'],
                         'no_long_turn_before': s['rammed_before_first_long_turn']},
        'hit_by_a_teammate_head': s['long_hit_by_teammate'],
        'long_dragons_alive_at_end_per_game': round(s['long_alive_at_end'] / g, 2),
        'longest_other_than_queen_at_end_per_game': round(s['longest_other_than_queen_at_end'] / g, 1),
        'queen_final_length_per_game': round(s['queen_final_len'] / g, 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--replays', required=True)
    ap.add_argument('--base', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    base = collect(a.replays, a.base)
    cand = collect(a.replays, a.candidate)
    if not base or not cand:
        sys.exit(f'no replays for {a.base!r} or {a.candidate!r} in {a.replays}')
    if set(base) != set(cand):
        sys.exit(f'unpaired replays: {sorted(set(base) ^ set(cand))}')
    keys = sorted(base)
    ball = total(base[k][1] for k in keys)
    call = total(cand[k][1] for k in keys)
    same = sum(base[k][2] == cand[k][2] for k in keys)
    maps = sorted({k[0] for k in keys})
    by_map = {}
    for m in maps:
        mk = [k for k in keys if k[0] == m]
        bm, cm = total(base[k][1] for k in mk), total(cand[k][1] for k in mk)
        by_map[m] = {'tiles': base[mk[0]][0], 'games_per_side': len(mk),
                     'pairs_playing_the_same_game': sum(base[k][2] == cand[k][2] for k in mk),
                     'base': {'decisions': bm['decisions'], 'touch': bm['touch'], 'clean_ending_possible': bm['possible'],
                              'missed_endings': bm['missed'], 'stuck': bm['stuck'], 'rammed': bm['rammed']},
                     'candidate': {'decisions': cm['decisions'], 'touch': cm['touch'], 'clean_ending_possible': cm['possible'],
                                   'missed_endings': cm['missed'], 'stuck': cm['stuck'], 'rammed': cm['rammed']}}

    brate, crate = share(ball['missed'], ball['possible']), share(call['missed'], call['possible'])
    target_seen = ball['missed'] >= TARGET_MIN and call['possible'] >= TOUCH_MIN
    cut_ok = target_seen and crate <= CUT * brate
    exit_seen = call['stuck_way_out'] >= EXIT_N
    exit_ok = share(call['exit_ok'], call['stuck_way_out']) >= EXIT_OK if exit_seen else None
    split_seen = call['stuck_no_way_out'] >= SPLIT_N
    split_ok = share(call['noexit_split'], call['stuck_no_way_out']) >= SPLIT_OK if split_seen else None
    passed = bool(target_seen and cut_ok and exit_ok is not False and split_ok is not False)
    why = []
    if ball['missed'] < TARGET_MIN:
        why.append(f"target not seen: base shows {ball['missed']} missed endings, {TARGET_MIN} needed")
    if call['possible'] < TOUCH_MIN:
        why.append(f"too little to compare: switch on has {call['possible']} decisions with a clean ending possible, "
                   f'{TOUCH_MIN} needed')
    if target_seen and not cut_ok:
        why.append(f'no cut: switch-on rate {crate:.3f} is above {CUT} x base rate {brate:.3f}')
    if exit_ok is False:
        why.append(f"way out not taken: {call['exit_ok']} of {call['stuck_way_out']} stuck decisions with a way out end "
                   f'on a tile that is not ringed, {EXIT_OK:.0%} needed')
    if split_ok is False:
        why.append(f"no split: {call['noexit_split']} of {call['stuck_no_way_out']} stuck decisions with no way out are "
                   f'splits, {SPLIT_OK:.0%} needed')

    def seen_text(flag, need):
        return '' if flag else f' (not seen: fewer than {need}, not judged)'

    bv, cv = view(ball), view(call)
    note = (
        f"{'PASS' if passed else 'FAIL'}. Measured from {len(keys)} paired games per side on {', '.join(maps)}. Ringed = a tile "
        f"an enemy head (their queen aside) reaches this turn on free steps or by paying 1 length, heads seen in the last 3 "
        f"rounds included. Decisions by our 31+ dragons (queen aside): base {ball['decisions']}, switch on {call['decisions']}; "
        f"with a ringed tile next to them or under them: {ball['touch']} -> {call['touch']}; of those where a clean ending "
        f"was possible (a clean step, a run out, or split 2 off and stay): {ball['possible']} -> {call['possible']}. Of those, "
        f"still ended on a ringed tile ('missed'): base {ball['missed']} ({brate:.1%}) -> switch on {call['missed']} "
        f"({crate:.1%}); by case, clean step open {ball['missed_avoidable']} of {ball['avoidable']} -> "
        f"{call['missed_avoidable']} of {call['avoidable']}, stuck with a way out {ball['missed_way_out']} -> "
        f"{call['missed_way_out']}, stuck but could split and stay {ball['missed_stay']} -> {call['missed_stay']}; free ring "
        f"{ball['missed_free']} -> {call['missed_free']}, pay ring {ball['missed_pay']} -> {call['missed_pay']}; ring of a "
        f"remembered head only (clean step open) {ball['danger_remembered']} -> {call['danger_remembered']}. Stuck decisions "
        f"(a ringed step and no clean step): "
        f"{ball['stuck']} -> {call['stuck']}; switch on, with a way out: {call['stuck_way_out']}, ended not ringed "
        f"{call['exit_ok']}" + seen_text(exit_seen, EXIT_N)
        + f"; switch on, no way out: {call['stuck_no_way_out']}, split {call['noexit_split']} (2 off "
        f"{call['noexit_split_of_2']}, all but 2 off {call['noexit_split_keeping_2']})" + seen_text(split_seen, SPLIT_N)
        + f". Not gated, small sample: length split off while stuck {ball['stuck_length_split_off']} -> "
        f"{call['stuck_length_split_off']}; 31+ dragons rammed by an enemy head {ball['rammed']} -> {call['rammed']} "
        f"(per 1000 decisions {bv['rammed_per_1000_decisions']} -> {cv['rammed_per_1000_decisions']}); of the switch-on rams, "
        f"after a ringed ending {call['rammed_after_ringed_ending']}, after a clean ending "
        f"{call['rammed_after_clean_ending']} (rammer in view {call['rammer_was_in_view']}, remembered "
        f"{call['rammer_was_in_mind']}, unseen {call['rammer_was_unseen']}); pearls eaten per 100 decisions "
        f"{bv['pearls_per_100_decisions']} -> {cv['pearls_per_100_decisions']}; wins {ball['win']} -> {call['win']}; pairs "
        f"that played the very same game with the switch on and off: {same} of {len(keys)}"
        + ('' if passed else '. NOT shown: ' + '; '.join(why)))
    out = {'passed': passed, 'note': note, 'target_seen': bool(target_seen), 'mechanism_shown': bool(target_seen and cut_ok),
           'way_out_rule_seen': bool(exit_seen), 'split_rule_seen': bool(split_seen),
           'pairs': len(keys), 'pairs_playing_the_same_game': same, 'maps': maps,
           'pass_rule': {'target_min': TARGET_MIN, 'touch_min': TOUCH_MIN, 'cut': CUT, 'exit_n': EXIT_N, 'exit_ok': EXIT_OK,
                         'split_n': SPLIT_N, 'split_ok': SPLIT_OK, 'target_seen': bool(target_seen), 'cut_ok': bool(cut_ok),
                         'base_rate': round(brate, 4), 'candidate_rate': round(crate, 4),
                         'way_out_rule_seen': bool(exit_seen), 'way_out_rule_ok': exit_ok,
                         'split_rule_seen': bool(split_seen), 'split_rule_ok': split_ok},
           'base': bv, 'candidate': cv, 'by_map': by_map,
           'model_check': {'moves_checked': ball['path_checked'] + call['path_checked'],
                           'moves_not_matching_head_updates': ball['path_mismatch'] + call['path_mismatch'],
                           'head_hops': ball['hops'] + call['hops'],
                           'hops_not_matching_walls_and_portals': ball['hop_mismatch'] + call['hop_mismatch']},
           'limits': ('measured from replays: the 7x7 view, kelp walls, portals, the remembered enemy size, heading and the '
                      '"body runs out of view" guess are rebuilt, so a few tiles can differ from what the bot marked (it only '
                      'walks portals it has seen both ends of, a step through a portal is not counted as a step here, the unit '
                      'cap that forbids a split is not rebuilt, tiles a feeder must keep off near the leader are not rebuilt, '
                      'and the dead-end test counts never-seen tiles as full room, so it calls fewer tiles dead ends than the '
                      'bot does); that is why the pass rule compares rates instead of asking for zero. The rings are the '
                      'bot\'s view of the danger, not the truth: enemies never seen, enemies longer than they look and '
                      'enemies paying more than 1 length are outside them, and the ram counts show how often that mattered. '
                      'How far a rammer came is its walking distance from where it stood when its action began, bodies '
                      'ignored. Pearls eaten are counted from length changes on moves. A long dragon that moves into an '
                      'enemy head itself, or drops to feed the leader, is counted under "died acting", not as an ending. '
                      'Rams, pearls, lengths and wins are raw counts from a small sample, not evidence of an outcome')}
    with open(a.output, 'w') as f:
        json.dump(out, f, indent=2)
        f.write('\n')
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        sys.exit(f'card 54 check failed: {exc}')
