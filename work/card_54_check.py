#!/usr/bin/env python3
"""Card #54 avoiding-long mechanism check (LONG_SAFETY, attempt 3): do our dragons of 31 or longer stay off the tiles
an enemy head can crash into this turn, what do they do when no such tile is left, and are the rings drawn large
enough for an enemy that is only partly in view? New in attempt 3 (Zhe, 10-08): a stuck dragon keeps 2 and sends the
rest off even when it does not know where its tail is; the check also follows the body that left.

usage: python3 work/card_54_check.py --replays DIR --base base --candidate candidate --output FILE [--events DIR]
Replays are DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1), paired by (map, seed, side).
--events DIR also writes one <replay>.events.jsonl per replay: every judged decision that touched a ring, and every
ram, with round and tile, for picking replays. It does not change the result.

Who is judged: every action of one of our dragons that is 31 or longer when it decides, our queen (dragon id 0/1)
left out, she has her own rules from card 39. For each such action the check rebuilds, from the replay alone, what the
dragon could see (the 7x7 box around its head) and the rings the bot draws:

  free ring  = tiles a visible enemy head, the enemy queen aside, can walk onto this turn with its free steps
               (ceil(size/4): 1 for an enemy 2-4 long, 2 for 5-8, 3 for 9-12 ...)
  pay ring   = one tile further, which that head only reaches by paying 1 length (a 2-long enemy cannot pay)
  size       = whole enemy in view: the parts in view (or the most seen in the last 3 rounds).
               Body runs out of the view (a part on the view's edge), new in attempt 2: the most parts our dragon has
               ever had in view of that enemy, if it once saw it whole and that was more than the stub now in view;
               otherwise the most parts it has ever had in view of any enemy (their queen aside). Never less than the
               stub + 1, never less than 3. Each of our dragons keeps this memory for itself, from its first turn
  memory     = an enemy head our dragon saw in the last 3 rounds but cannot see now. It may stand on any tile it could
               have walked to at one step per round out of view, that is not in sight now and not behind where it was
               heading; the same two rings are drawn around all of those tiles, with the size rule above
  ringed     = in any of these. Kelp walls and portals are walked, bodies in view block
  heads      = how many of those heads reach a tile on free steps, and how many reach it at all

  ending     = where the long body is once the action is done: the head's tile after a move, its own tile after a
               split that leaves it 31+, and the tail-end tile after a split that sends 31+ off as a new dragon
  touch      = a tile it could step onto, or its own tile, was ringed (the rule had something to say)
  clean step = a tile it could step onto, not ringed, that is not a dead-end pocket (a pocket = it can reach neither
               its tail nor length + 2 tiles from there)
  avoidable  = touch, and a clean step was open
  stuck      = a tile it could step onto was ringed and no clean step was open
  way out    = stuck, but a run of 2+ steps to a tile in view that is not ringed and not a pocket exists: 'free' within
               its free steps (at most 6, the bot's stride cap), 'paid' up to 2 steps beyond its free steps
  no way out = stuck without one. The card's answer then, in this order (jun's revision of 10-08, for Zhe):
               keep 2  = the head keeps 2 and the rest leaves from the tail end as its own dragon; open when our team
                         is below the 64-dragon cap and either the dragon does not know where its tail is ('blind',
                         new in attempt 3) or the tail-end tile is not ringed and has room
               stay    = its own tile is not ringed and it can split: 2 off the tail and it stays (ends clean)
               least bad tile = otherwise it moves: a pay-ring tile over a free-ring tile, then the tile fewer heads
                         reach
  clean ending possible = avoidable, or a way out, or no way out with stay open or with keep 2 open and the tail end
               not inside the rings our dragon draws (a blind split cannot know that; the check reads the real tail)
  body that left = the child of a keep-2 split made while stuck with no way out. Followed for its birth round and the
               two after: its first turn (a child of 31+ is judged like any long dragon), whether it splits again in
               the round it was born (a chain), whether it is rammed; and whether the 2 left behind are rammed
  missed     = a clean ending was possible and the long body still ended on a ringed tile

PASS RULE (fixed before any game was played with this attempt's switch on; constants below):
  1. target seen: base shows at least TARGET_MIN missed endings, and the switch-on side has at least TOUCH_MIN
     decisions where a clean ending was possible (otherwise there is nothing to compare);
  2. cut: switch-on missed endings per decision where a clean ending was possible are at most CUT x base's;
  3. way out, judged only if it comes up: with at least EXIT_N switch-on stuck decisions that had a way out, at least
     EXIT_OK of them end on a tile that is not ringed;
  4. no way out, split open, judged only if it comes up: with at least STUCK_N switch-on decisions that are stuck
     with no way out and have keep 2 or stay open, at least STUCK_OK of them take that split (a keep-2 split always
     counts; 2 off and stay counts only where keep 2 is not open and its own tile is not ringed);
  5. no way out, no split open, judged only if it comes up: with at least STUCK_N such switch-on decisions, at least
     STUCK_OK of them are a move that ends on no worse a ring than the best single step.
     In 4 and 5 a move that ends outside the rings after all also counts (the bot found a way the check did not),
     and a split that leaves a 31+ dragon standing on a ringed tile never counts (attempt 1's fault);
  6. rams the ring is there to stop, judged only if it comes up: a 'near ram in view' = one of our 31+ dragons is
     rammed by an enemy head that was in view at the dragon's last decision and came on its free steps or 1 paid
     step. With at least RAM_N of them in base, switch-on near rams in view per 1000 decisions are at most RAM_CUT x
     base's.
  7. this attempt's change, judged only if it comes up: with at least BLIND_N switch-on decisions that are stuck with
     no way out, the tail not known and our team below the cap, at least STUCK_OK of them keep 2 (a move that ends
     outside the rings after all also counts).
passed = 1 and 2, and 3 to 7 where they come up. target_seen = rule 1, mechanism_shown = rules 1 and 2 and rule 7 seen
and met. Rules 3-7 report "not seen" below their minimum and do not fail the check then.
NOT part of the pass rule (16 games per side cannot settle them, the outcome A/B does): all rams on 31+ dragons, the
length lost to rams per game, pearls those dragons eat, length shed by stuck splits, lengths and wins, and everything
about the body that left (first turn, chains, rams within 2 rounds).
The bot's own log lines are not used: the game runner drops them.

KNOWN BEFORE any game with attempt 3's switch on, from running this check on the 32 replays attempt 2 kept (16 base
against base, 16 with attempt 2's switch on; same maps and seeds as this run):
  - stuck with no way out, the tail not known and the team below the cap: base 69 (kept 2: 0, moved out of the rings
    5, moved onto a ringed tile 64); attempt 2's switch 71 (kept 2: 0, moved out 11, onto a ringed tile 45, 2 off the
    tail and stayed on a clean tile 15). So rule 7 stands at 11 of 71 before this change and rule 4, with blind
    counted as open, at 25 of 85. Missed endings by the new definition: base 216 of 569, attempt 2's switch 44 of 478.
  - the body that left, attempt 2's switch: 15 stuck keep-2 splits (all with the tail known), 13 children still 31+;
    1 of those 13 was stuck with no way out on its first turn; 1 child rammed within 2 rounds (44 length); the 2 left
    behind rammed within 2 rounds once. No chain yet, because a fresh child could not split.

KNOWN BEFORE attempt 2, kept for reference, from running the attempt-2 check on the 32 replays attempt 1 kept (16
base against base, 16 with attempt 1's switch on; same maps as this run):
  - ring size against real lengths, base games: our 31+ dragons saw an enemy head 3123 times, 2819 of them with the
    body running out of view. 1603 of those 2819 enemies were really 2-4 long. Attempt 1's stub rule sized 1094 of
    the 2819 below their real free steps and 35 above. The new rule sizes 797 below and 1224 above; 1030 of the 1603
    short ones are taken for longer than they are, and of the 599 that are really 13 or longer 559 are still sized
    too small. Almost all (2796) are sized from the longest enemy seen, because an enemy our dragon once saw whole
    is rare. So the new rings are larger everywhere, not larger where the enemy is long.
  - what larger rings mean, same base games redrawn: decisions with a ringed tile next to or under the head 332 ->
    617, stuck 133 -> 314, stuck with no way out 55 -> 130 (keep 2 open 25, stay open 13, no split open 92: team at
    the cap 19, tail not known 69, tail end ringed 15). Base already ends 89 of 91 no-split cases on the least bad
    ring, so rule 5 guards against a regression; rules 2, 3, 4 and 6 are where the switch has to show.
  - rams, attempt 1's switch-on games: 69 rams with the rammer in view, 34 of them near (free steps or 1 paid). With
    the new rings redrawn, 23 of those 34 follow an ending the new rings mark and 11 follow one they still leave
    clean (10: ring drawn too small). Base games: 47 near rams in view of 110 rams.
"""
import argparse, glob, hashlib, json, os, sys, concurrent.futures as cf
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before any game with this attempt's switch on)
TARGET_MIN = 5       # base missed endings needed to call the target seen
TOUCH_MIN = 20       # switch-on decisions with a clean ending possible needed to compare at all
CUT = 0.25           # switch-on missed endings per decision with a clean ending possible: at most this fraction of base's
EXIT_N = 5           # switch-on stuck decisions with a way out needed to judge the way-out rule
EXIT_OK = 0.75       # share of those that must end on a tile that is not ringed
STUCK_N = 5          # switch-on stuck decisions with no way out needed to judge rule 4, and again rule 5
STUCK_OK = 0.75      # share of those that must take the card's answer for their case
RAM_N = 10           # base near rams in view needed to judge the ram rule
RAM_CUT = 0.5        # switch-on near rams in view per 1000 decisions: at most this fraction of base's

LONG_MIN = 31        # LS_MIN_LENGTH
VIEW = 3             # the bot sees a 7x7 box around its head
GHOST_ROUNDS = 3     # how long the bot remembers an enemy head
FREE_DIV = 4         # free steps per turn = ceil(length / 4)
MIN_SIZE = 2         # a dragon cannot pay itself below this
START_SIZE = 3       # INITIAL_LENGTH: the least a half-hidden enemy is taken to be
PAY_STEPS = 1        # LS_PAY_STEPS: paid steps an enemy is expected to add
ESCAPE_COST = 2      # LS_ESCAPE_COST: the most length a long dragon pays to run out
RUN_MAX = 6          # STRIDE_MAX: the most steps of a free run
UNIT_CAP = 64        # dragons a team may have alive; at the cap a split is refused (work/plan.md, and the last look)
TAIL_ROOM = 5        # tiles the tail end must reach for the rest to leave from it (CHILD_MIN_ROOM 4, plus itself)
CHILD_ROUNDS = 2     # 'soon' for the body that left: its birth round and the two after
BLIND_N = 5          # switch-on no-way-out decisions with the tail not known needed to judge rule 7
CAUSE =['wall', 'self', 'body', 'headon', 'none']
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


def has_room(step, start, taken, want):
    """True when `want` tiles, `start` included, can be walked from `start` without entering a body."""
    seen = {start}
    frontier = [start]
    while frontier and len(seen) < want:
        nxt = []
        for cell in frontier:
            for d in DIRS:
                hop = step(cell, d)
                if hop is None or hop[0] in seen or hop[0] in taken:
                    continue
                seen.add(hop[0])
                nxt.append(hop[0])
        frontier = nxt
    return len(seen) >= want


def one(job):
    path, side, keep_events = job
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
    events = []

    memory = {}          # our dragon -> {enemy: (round last seen, parts, head tile, heading)}: the 3-round head memory
    sizes = {}           # our dragon -> {enemy: [most parts seen whole, most parts seen, parts last seen, cut then]}
    longest = {}         # our dragon -> most parts it has had in view of any enemy
    known = {}           # our dragon -> how many of its own body tiles, from the head, it knows
    last = {}            # our long dragon -> how its last finished action left it
    born = {}            # child of a stuck keep-2 split -> {rnd, depth, blind, len}
    keepers = {}         # the 2-long piece a stuck keep-2 split left behind -> round
    pending = None
    mover = None
    act_from, act_len = None, 0
    rnd = 0

    def note(t, **row):
        if keep_events:
            events.append(dict(t=t, **row))

    def heading(b):
        if len(b) < 2:
            return None
        for d in DIRS:
            hop = step(b[1], d)
            if hop is not None and hop[0] == b[0]:
                return d
        return None

    def guess(viewer, did, shown):
        """Size taken for an enemy whose body runs out of the view."""
        rec = sizes[viewer].get(did)
        base = rec[1] if rec and rec[0] > shown else longest.get(viewer, 0)
        return max(base, shown + 1, START_SIZE)

    def sight(viewer):
        """Enemy heads in view, the enemy queen aside; also updates what the bot keeps in mind."""
        body = bodies[viewer]
        head = body[0]

        def in_view(cell):
            return gap(cell[0], head[0], W) <= VIEW and gap(cell[1], head[1], H) <= VIEW

        k = min(max(known.get(viewer, 1), 1), len(body))
        while k < len(body) and in_view(body[k]):
            k += 1
        known[viewer] = k
        mind = memory.setdefault(viewer, {})
        size = sizes.setdefault(viewer, {})
        shown = {}
        for did, b in bodies.items():
            if not b or team_of.get(did) == ours or did == foe_queen:
                continue
            inside = [cell for cell in b if in_view(cell)]
            if not inside:
                continue
            headed = in_view(b[0])
            cut = any(gap(cell[0], head[0], W) == VIEW or gap(cell[1], head[1], H) == VIEW for cell in inside)
            rec = size.setdefault(did, [0, 0, 0, False])
            rec[1] = max(rec[1], len(inside))
            rec[2], rec[3] = len(inside), cut
            if headed and not cut:
                rec[0] = max(rec[0], len(inside))
            longest[viewer] = max(longest.get(viewer, 0), len(inside))
            if headed:
                shown[did] = (b, len(inside), cut)
        foes = []
        for did, (b, count, cut) in shown.items():
            was = mind.get(did)
            parts = max(count, was[1]) if was and rnd - was[0] <= GHOST_ROUNDS else count
            mind[did] = (rnd, parts, b[0], heading(b))
            old_free = free_steps(parts)
            if cut:
                parts = max(parts, guess(viewer, did, count))
            foes.append(dict(id=did, at=b[0], parts=parts, shown=count, cut=cut, real=len(b), old_free=old_free))
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
        units = 0
        for did, b in bodies.items():
            if not b:
                continue
            units += team_of.get(did) == ours
            if did == viewer:
                continue
            taken.update(b)
            inside = [cell for cell in b if in_view(cell)]
            seen_block.update(inside)
            others.update(inside)
        hitc, payc = Counter(), Counter()
        seen_ring = set()
        own_zone = 0
        reach_of = {}
        for f in foes:
            free = free_steps(f['parts'])
            full = max(f['parts'], f['shown'] + 1, START_SIZE) if f['cut'] else f['parts']
            reach = min(full_reach(full), free + PAY_STEPS)
            reach_of[f['id']] = reach
            dist, touch = flood(step, [f['at']], reach, seen_block, head)
            del dist[f['at']]
            for t, n in dist.items():
                payc[t] += 1
                hitc[t] += n <= free
            seen_ring.update(dist)
            if touch is not None:
                own_zone = max(own_zone, 2 if touch <= free else 1)
            real_free = free_steps(f['real'])
            c['heads_in_view'] += 1
            c['heads_cut'] += f['cut']
            if f['cut']:
                c['cut_undersized_old_rule'] += f['old_free'] < real_free
                c['cut_oversized_old_rule'] += f['old_free'] > real_free
                c['cut_short'] += real_free == 1
                c['cut_short_oversized'] += real_free == 1 and free > 1
                c['cut_long'] += real_free >= 4
                c['cut_long_undersized'] += real_free >= 4 and free < real_free
                c['cut_undersized'] += free < real_free
                c['cut_oversized'] += free > real_free
                c[f'size_real{min(real_free, 5)}_took{min(free, 5)}'] += 1
                c[f'size_real{min(real_free, 5)}_old{min(f["old_free"], 5)}'] += 1
                c['cut_sized_from_longest'] += not (sizes[viewer][f['id']][0] > f['shown'])
            else:
                c['whole_undersized'] += free < real_free
        in_sight = {f['id'] for f in foes}
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
            rec = sizes[viewer].get(did)
            if rec and rec[3]:
                parts = max(parts, guess(viewer, did, rec[2]))
            free = free_steps(parts)
            dist, touch = flood(step, spots, free + PAY_STEPS, seen_block, head)
            for t, n in dist.items():
                payc[t] += 1
                hitc[t] += n <= free
            if touch is not None:
                own_zone = max(own_zone, 2 if touch <= free else 1)

        def zone(t):
            return 2 if hitc[t] else 1 if payc[t] else 0

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
        tail = body[-1]
        capped = units >= UNIT_CAP
        tail_known = known.get(viewer, 1) >= size
        tail_fit = zone(tail) == 0 and has_room(step, tail, taken - {tail}, TAIL_ROOM)
        # Attempt 3: a tail the dragon does not know no longer holds keep 2 back ('blind').
        keep2 = bool(stuck and run is None and not capped and (not tail_known or tail_fit))
        blind = keep2 and not tail_known
        stay = bool(stuck and run is None and not capped and own_zone == 0 and not keep2)
        pool = [t for t in walk if roomy[t]] or walk
        best_zone = min((zones[t] for t in pool), default=0)
        fewest = min(((hitc[t], payc[t]) for t in pool if zones[t] == best_zone), default=(0, 0))
        return dict(id=viewer, start=head, tail=tail, len=size, rnd=rnd, view=bool(foes), saw=in_sight, mind=remembered,
                    seen_ring=seen_ring, zone=zone, heads=lambda t: (hitc[t], payc[t]), own=own_zone,
                    touch=own_zone > 0 or ringed_step, safe=safe, stuck=stuck, run=run, keep2=keep2, stay=stay,
                    capped=capped, tail_known=tail_known, tail_zone=zone(tail), units=units, best_zone=best_zone,
                    blind=blind, tail_fit=tail_fit, fresh=born.get(viewer, {}).get('rnd') == rnd, child_id=None,
                    fewest=fewest, reach=reach_of, short_foe=any(f['parts'] <= 5 for f in foes), seen=0, dead=False,
                    cause=None, child=0, kind='other', n=0)

    def close():
        nonlocal pending
        p, pending = pending, None
        if p is None:
            return
        did = p['id']
        avoidable = p['touch'] and p['safe']
        way = p['run'] if p['stuck'] else None
        noexit = p['stuck'] and way is None
        # A blind keep 2 is a clean ending only where the tail end turns out not to be ringed.
        possible = avoidable or way is not None or (p['keep2'] and p['tail_zone'] == 0) or p['stay']
        c['decisions'] += 1
        c['possible'] += possible
        c['enemy_head_in_view'] += p['view']
        c['enemy_head_in_mind'] += bool(p['mind'])
        c['touch'] += p['touch']
        c['avoidable'] += avoidable
        c['stuck'] += p['stuck']
        c['stuck_way_out'] += way is not None
        c['stuck_no_way_out'] += noexit
        c['stuck_short_foe'] += p['stuck'] and p['short_foe']
        c['noexit_keep2_open'] += p['keep2']
        c['noexit_stay_open'] += p['stay']
        c['noexit_no_split_open'] += noexit and not p['keep2'] and not p['stay']
        c['noexit_at_cap'] += noexit and p['capped']
        c['noexit_tail_unknown'] += noexit and not p['capped'] and not p['tail_known']
        c['noexit_tail_ringed'] += noexit and not p['capped'] and p['tail_known'] and p['tail_zone'] > 0
        c['noexit_tail_cramped'] += noexit and not p['capped'] and p['tail_known'] and p['tail_zone'] == 0 and not p['tail_fit']
        c['child_first_turns'] += p['fresh']
        c['child_first_touch'] += p['fresh'] and p['touch']
        c['child_first_stuck'] += p['fresh'] and p['stuck']
        c['child_first_noexit'] += p['fresh'] and noexit
        b = bodies.get(did)
        if p['dead'] or not b:
            c['died_acting'] += 1
            c['died_acting_' + (p['cause'] or 'other')] += 1
            c['child_first_died_acting'] += p['fresh']
            c['avoidable_died_acting'] += avoidable
            c['noexit_died_acting'] += noexit
            if p['touch']:
                note('died_acting', rnd=p['rnd'], id=did, len=p['len'], kind=p['kind'], n=p['n'], cause=p['cause'],
                     stuck=p['stuck'], way=way, start=p['start'])
            last.pop(did, None)
            return
        after = len(b)
        moved = p['kind'] == 'move'
        split = p['kind'] == 'split'
        kept2 = split and p['child'] == p['len'] - MIN_SIZE
        two_off = split and p['child'] == MIN_SIZE
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
            counted = True
        else:
            # The long body sits on its own tile, or leaves from the tail end when 31+ went off as the child.
            stays = after >= LONG_MIN
            leaves = split and p['child'] >= LONG_MIN
            end = p['start'] if stays or not leaves else p['tail']
            where = max(p['own'] if stays else 0, p['tail_zone'] if leaves else 0)
            source = 'own_tile'
            counted = stays or leaves
            c['splits' if split else 'other_actions'] += 1
            if split:
                c['splits_of_2'] += two_off
                c['splits_keeping_2'] += kept2
                c['length_split_off'] += p['child']
                c['stuck_splits'] += p['stuck']
                c['stuck_length_shed'] += MIN_SIZE if p['stuck'] and (kept2 or two_off) else 0
                c['stuck_split_stays_ringed'] += p['stuck'] and stays and p['own'] > 0
        ringed = counted and where > 0
        c['ended_ringed'] += ringed
        c['child_first_ended_ringed'] += p['fresh'] and ringed
        if noexit and kept2:
            depth = born[did]['depth'] + 1 if p['fresh'] else 1
            c['kept2_children'] += 1
            c['kept2_children_31plus'] += p['child'] >= LONG_MIN
            c['kept2_child_length'] += p['child']
            c['kept2_tail_end_ringed'] += p['tail_zone'] > 0
            c['kept2_by_a_child_born_this_round'] += p['fresh']
            c[f'kept2_depth{min(depth, 4)}'] += 1
            keepers[did] = p['rnd']
            if p['child_id'] is not None:
                born[p['child_id']] = dict(rnd=p['rnd'], depth=depth, blind=p['blind'], len=p['child'])
        if noexit and p['blind']:
            c['blind_open'] += 1
            c['blind_kept_2'] += kept2
            c['blind_moved_out'] += moved and where == 0
            c['blind_moved_ringed'] += moved and where > 0
            c['blind_other'] += not kept2 and not moved
            c['blind_child_length'] += p['child'] if kept2 else 0
            c['blind_tail_end_ringed'] += kept2 and p['tail_zone'] > 0
        if possible and ringed:
            c['missed'] += 1
            c['missed_' + ('avoidable' if avoidable else 'way_out' if way else 'split_open')] += 1
            c['missed_free' if where == 2 else 'missed_pay'] += 1
        if avoidable and ringed:
            c['danger'] += 1
            c['danger_free' if where == 2 else 'danger_pay'] += 1
            c['danger_move' if moved else 'danger_stay'] += 1
            c['danger_' + source] += 1
        answer = None
        if way:
            c['exit_' + way] += 1
            c['exit_ok'] += not ringed
            c['exit_ok_by_run'] += moved and p['n'] >= 2 and not ringed
        elif p['stuck']:
            least = moved and where <= p['best_zone']
            if kept2:
                did_what = 'split_kept_2'
            elif two_off:
                did_what = 'split_2_off_clean_tile' if p['own'] == 0 else 'split_2_off_ringed_tile'
            elif split:
                did_what = 'split_other'
            elif moved and where == 0:
                did_what = 'moved_out'
            elif least:
                did_what = 'least_bad_tile'
            elif moved:
                did_what = 'moved_worse_tile'
            else:
                did_what = 'no_action'
            c['noexit_' + did_what] += 1
            c['noexit_least_bad_fewest_heads'] += least and where > 0 and p['n'] == 1 and p['heads'](end) == p['fewest']
            c['noexit_least_bad_single_step'] += least and where > 0 and p['n'] == 1
            c['noexit_least_bad_pay_ring'] += least and where == 1
            c['noexit_least_bad_free_ring'] += least and where == 2
            want = 'keep2' if p['keep2'] else 'stay' if p['stay'] else 'move'
            answer = (kept2 or did_what == 'moved_out' or (want == 'stay' and did_what == 'split_2_off_clean_tile')
                      or (want == 'move' and did_what == 'least_bad_tile'))
            c['noexit_answered'] += answer
            c['noexit_want_' + want] += 1
            c['noexit_want_' + want + '_answered'] += answer
        if p['touch']:
            note('touch', rnd=p['rnd'], id=did, len=p['len'], after=after, kind=p['kind'], n=p['n'], child=p['child'],
                 start=p['start'], end=end, avoidable=avoidable, stuck=p['stuck'], way=way, keep2_open=p['keep2'],
                 stay_open=p['stay'], capped=p['capped'], tail_known=p['tail_known'], tail_zone=p['tail_zone'],
                 blind=p['blind'], fresh=p['fresh'],
                 own=p['own'], where=where, ringed=ringed, possible=possible, answered=answer, units=p['units'],
                 saw=sorted(p['saw']), mind=sorted(p['mind']),
                 foes=[(f, len(bodies[f]), bodies[f][0], p['reach'].get(f)) for f in sorted(p['saw'] | p['mind'])
                       if bodies.get(f)])
        mark = dict(rnd=p['rnd'], ringed=ringed, avoidable=avoidable, stuck=p['stuck'], saw=p['saw'], mind=p['mind'],
                    reach=p['reach'])
        if after >= LONG_MIN:
            last[did] = mark
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
                if did in known:
                    known[did] += 1
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
            if pa in known:
                known[pa] = min(known[pa], len(bodies[pa]))
            if pending and pa == pending['id']:
                pending['child'] = len(bodies[ch])
                pending['child_id'] = ch
        elif kind == 'dragonDeath':
            did = pl.i32(0)
            r = pl.u16(4)
            track.update(f'd{did}{r}'.encode())
            b = bodies.pop(did, None)
            cause = CAUSE[r] if r < 5 else 'other'
            if pending and did == pending['id']:
                pending['dead'] = True
                pending['cause'] = cause
            hit = cause == 'headon' and mover != did and team_of.get(mover) != ours and b
            kid = born.get(did)
            if kid and rnd - kid['rnd'] <= CHILD_ROUNDS:
                c['child_dead_soon'] += 1
                c['child_dead_soon_length'] += len(b or ())
                if hit:
                    c['child_rammed_soon'] += 1
                    c['child_rammed_soon_length'] += len(b)
                    c['child_rammed_soon_blind'] += kid['blind']
                    c['child_rammed_same_round'] += rnd == kid['rnd']
                    note('child_rammed', rnd=rnd, id=did, len=len(b), born=kid['rnd'], blind=kid['blind'], rammer=mover,
                         rammer_len=act_len)
            if did in keepers and rnd - keepers[did] <= CHILD_ROUNDS and hit:
                c['keeper_rammed_soon'] += 1
                c['keeper_rammed_soon_length'] += len(b)
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
            came = walk_dist(step, act_from, b[0], 14) if act_from else None
            paid = None if came is None else came - free_steps(act_len)
            how = 'unknown' if paid is None else 'free' if paid <= 0 else 'paid_1' if paid == 1 else 'paid_more'
            c['rammer_' + how] += 1
            if was is None:
                seen = 'none'
                c['rammed_before_first_long_turn'] += 1
            else:
                seen = 'in_view' if mover in was['saw'] else 'in_mind' if mover in was['mind'] else 'unseen'
                c['rammed_after_ringed_ending' if was['ringed'] else 'rammed_after_clean_ending'] += 1
                c['rammed_ringed_avoidable'] += was['ringed'] and was['avoidable']
                c['rammed_ringed_stuck'] += was['ringed'] and was['stuck']
                c['rammer_was_' + seen] += 1
                if seen == 'in_view':
                    c['ram_in_view_length'] += len(b)
                    near = how in ('free', 'paid_1')
                    c['ram_in_view_' + ('ringed' if was['ringed'] else 'clean') + '_' + how] += 1
                    c['ram_in_view_near'] += near
                    c['ram_in_view_near_length'] += len(b) if near else 0
                    c['ram_in_view_near_short_rammer'] += near and act_len <= 5
                    if near and not was['ringed']:
                        c['ram_in_view_clean_near'] += 1
                        c['ram_in_view_clean_near_length'] += len(b)
                        # Ring drawn smaller than the walk it took, or the walk fits and something stood in the way.
                        small = came > was['reach'].get(mover, 0)
                        c['ram_in_view_clean_near_' + ('ring_too_small' if small else 'ring_blocked')] += 1
            note('rammed', rnd=rnd, id=did, len=len(b), at=b[0], rammer=mover, rammer_len=act_len, rammer_from=act_from,
                 came=came, rammer_free=free_steps(act_len), how=how, rammer_seen=seen, last_rnd=was and was['rnd'],
                 last_ringed=was and was['ringed'], last_stuck=was and was['stuck'],
                 ring_reach=was and was['reach'].get(mover))
    close()
    longest_end = max((len(b) for did, b in bodies.items() if b and team_of.get(did) == ours and did != queen), default=0)
    c['long_alive_at_end'] = sum(1 for did, b in bodies.items()
                                 if b and team_of.get(did) == ours and did != queen and len(b) >= LONG_MIN)
    c['longest_other_than_queen_at_end'] = longest_end
    c['queen_final_len'] = len(bodies.get(queen) or ())
    c['foe_queen_final_len'] = len(bodies.get(foe_queen) or ())
    return W * H, dict(c), track.hexdigest(), events


def collect(directory, tag, events_dir):
    jobs, keys = [], []
    for p in sorted(glob.glob(os.path.join(directory, f'{tag}_*.replay'))):
        stem = os.path.basename(p)[len(tag) + 1:-len('.replay')]
        m, seed, side = stem.rsplit('_', 2)
        jobs.append((p, side, bool(events_dir)))
        keys.append((m, seed, side))
    with cf.ProcessPoolExecutor(int(os.environ.get('CHECK_WORKERS', '4'))) as pool:
        rows = list(pool.map(one, jobs))
    if events_dir:
        os.makedirs(events_dir, exist_ok=True)
        for (p, _, _), row in zip(jobs, rows):
            name = os.path.basename(p)[:-len('.replay')] + '.events.jsonl'
            with open(os.path.join(events_dir, name), 'w') as f:
                for e in row[3]:
                    f.write(json.dumps(e) + '\n')
    return dict(zip(keys, rows))


def total(rows):
    s = Counter()
    for r in rows:
        s.update(r)
    return s


def share(a, b):
    return a / b if b else 0.0


def view(s):
    g = max(1, s['games'])
    in_view = s['rammer_was_in_view']
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
                                   'stuck_with_a_split_open': s['missed_split_open']},
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
        'stuck_with_no_way_out': {
            'decisions': s['stuck_no_way_out'],
            'what_was_open': {'keep_2_split': s['noexit_keep2_open'], '2_off_and_stay_on_a_clean_tile': s['noexit_stay_open'],
                              'no_split': s['noexit_no_split_open']},
            'why_keep_2_was_not_open': {'team_at_the_64_cap': s['noexit_at_cap'],
                                        'tail_known_and_its_end_ringed': s['noexit_tail_ringed'],
                                        'tail_known_and_its_end_cramped': s['noexit_tail_cramped']},
            'tail_not_known_team_below_the_cap': {
                'decisions': s['blind_open'], 'kept_2': s['blind_kept_2'], 'moved_out_of_the_rings': s['blind_moved_out'],
                'moved_onto_a_ringed_tile': s['blind_moved_ringed'], 'other': s['blind_other'],
                'length_sent_off': s['blind_child_length'],
                'of_the_kept_2_tail_end_inside_the_parents_rings': s['blind_tail_end_ringed']},
            'what_it_did': {'split_kept_2': s['noexit_split_kept_2'],
                            'split_2_off_and_stayed_on_a_clean_tile': s['noexit_split_2_off_clean_tile'],
                            'split_2_off_and_stayed_on_a_ringed_tile': s['noexit_split_2_off_ringed_tile'],
                            'other_split': s['noexit_split_other'],
                            'least_bad_tile': s['noexit_least_bad_tile'],
                            'moved_onto_a_worse_tile': s['noexit_moved_worse_tile'],
                            'moved_out_of_the_rings': s['noexit_moved_out'],
                            'died_acting': s['noexit_died_acting'], 'no_action': s['noexit_no_action']},
            'least_bad_tile_detail': {'on_the_pay_ring': s['noexit_least_bad_pay_ring'],
                                      'on_the_free_ring': s['noexit_least_bad_free_ring'],
                                      'single_steps': s['noexit_least_bad_single_step'],
                                      'of_those_on_the_tile_fewest_heads_reach': s['noexit_least_bad_fewest_heads']},
            'took_the_cards_answer': s['noexit_answered'],
            'by_what_was_open': {'keep_2': [s['noexit_want_keep2_answered'], s['noexit_want_keep2']],
                                 'stay': [s['noexit_want_stay_answered'], s['noexit_want_stay']],
                                 'move': [s['noexit_want_move_answered'], s['noexit_want_move']]}},
        'bodies_that_left_by_a_stuck_keep_2': {
            'all': s['kept2_children'], 'still_31plus': s['kept2_children_31plus'], 'length': s['kept2_child_length'],
            'tail_end_inside_the_parents_rings': s['kept2_tail_end_ringed'],
            'first_turn_of_those_31plus': {
                'turns': s['child_first_turns'], 'ringed_tile_next_to_or_under_the_head': s['child_first_touch'],
                'stuck': s['child_first_stuck'], 'stuck_with_no_way_out': s['child_first_noexit'],
                'ended_ringed': s['child_first_ended_ringed'], 'died_acting': s['child_first_died_acting']},
            'split_again_the_round_it_was_born': s['kept2_by_a_child_born_this_round'],
            'keep_2_splits_by_chain_position_4_means_4_or_more': {str(k): s[f'kept2_depth{k}'] for k in range(1, 5)},
            'dead_within_2_rounds': s['child_dead_soon'], 'length_of_those': s['child_dead_soon_length'],
            'rammed_within_2_rounds': s['child_rammed_soon'], 'length_lost_to_those_rams': s['child_rammed_soon_length'],
            'of_those_rams_the_birth_round': s['child_rammed_same_round'],
            'of_those_rams_after_a_blind_split': s['child_rammed_soon_blind'],
            'the_2_left_behind_rammed_within_2_rounds': s['keeper_rammed_soon']},
        'splits': s['splits'], 'splits_while_stuck': s['stuck_splits'],
        'length_shed_by_stuck_splits': s['stuck_length_shed'],
        'stuck_splits_leaving_a_31plus_dragon_on_a_ringed_tile': s['stuck_split_stays_ringed'],
        'moves': s['moves'], 'multi_step_moves': s['multi_moves'], 'paid_moves': s['paid_moves'],
        'length_paid_for_moves': s['length_paid'],
        'pearls_eaten': s['pearls'], 'pearls_per_100_decisions': round(100 * share(s['pearls'], s['decisions']), 2),
        'died_acting': {k[len('died_acting_'):]: v for k, v in sorted(s.items()) if k.startswith('died_acting_')},
        'deaths_of_31plus_dragons': s['long_deaths'],
        'deaths_by_cause': {k[len('long_deaths_'):]: v for k, v in sorted(s.items()) if k.startswith('long_deaths_')},
        'rammed_by_an_enemy_head': s['rammed'],
        'rammed_per_1000_decisions': round(1000 * share(s['rammed'], s['decisions']), 2),
        'length_lost_to_rams': s['rammed_length'],
        'length_lost_to_rams_per_game': round(s['rammed_length'] / g, 1),
        'rammed_mean_length_lost': round(share(s['rammed_length'], s['rammed']), 1),
        'rammer_length': {'5_or_shorter': s['rammer_short'], 'longer': s['rammer_long']},
        'rammer_steps': {'free': s['rammer_free'], 'paid_1': s['rammer_paid_1'], 'paid_more': s['rammer_paid_more'],
                         'unknown': s['rammer_unknown']},
        'rammer_at_our_last_decision': {'in_view': in_view, 'remembered': s['rammer_was_in_mind'],
                                        'unseen': s['rammer_was_unseen']},
        'rammed_after': {'a_ringed_ending': s['rammed_after_ringed_ending'], 'of_those_avoidable': s['rammed_ringed_avoidable'],
                         'of_those_stuck': s['rammed_ringed_stuck'], 'a_clean_ending': s['rammed_after_clean_ending'],
                         'no_long_turn_before': s['rammed_before_first_long_turn']},
        'rams_with_the_rammer_in_view': {
            'all': in_view, 'length_lost': s['ram_in_view_length'],
            'near_free_or_1_paid': s['ram_in_view_near'],
            'near_per_1000_decisions': round(1000 * share(s['ram_in_view_near'], s['decisions']), 2),
            'near_length_lost': s['ram_in_view_near_length'],
            'near_by_a_rammer_5_or_shorter': s['ram_in_view_near_short_rammer'],
            'after_a_clean_ending': {'free': s['ram_in_view_clean_free'], 'paid_1': s['ram_in_view_clean_paid_1'],
                                     'paid_more': s['ram_in_view_clean_paid_more'], 'unknown': s['ram_in_view_clean_unknown']},
            'after_a_ringed_ending': {'free': s['ram_in_view_ringed_free'], 'paid_1': s['ram_in_view_ringed_paid_1'],
                                      'paid_more': s['ram_in_view_ringed_paid_more'],
                                      'unknown': s['ram_in_view_ringed_unknown']},
            'clean_ending_and_free_or_1_paid': s['ram_in_view_clean_near'],
            'clean_ending_and_free_or_1_paid_share': round(share(s['ram_in_view_clean_near'], in_view), 4),
            'clean_ending_and_free_or_1_paid_length_lost': s['ram_in_view_clean_near_length'],
            'of_those_ring_drawn_too_small': s['ram_in_view_clean_near_ring_too_small'],
            'of_those_ring_large_enough_but_tile_not_marked': s['ram_in_view_clean_near_ring_blocked']},
        'enemy_heads_in_view_of_31plus_dragons': {
            'all': s['heads_in_view'], 'body_running_out_of_view': s['heads_cut'],
            'of_those_sized_below_their_real_free_steps_by_the_old_rule': s['cut_undersized_old_rule'],
            'of_those_sized_above_their_real_free_steps_by_the_old_rule': s['cut_oversized_old_rule'],
            'of_those_sized_below_their_real_free_steps': s['cut_undersized'],
            'of_those_sized_above_their_real_free_steps': s['cut_oversized'],
            'really_2_to_4_long': s['cut_short'], 'of_those_taken_for_longer': s['cut_short_oversized'],
            'really_13_or_longer': s['cut_long'], 'of_those_sized_too_small': s['cut_long_undersized'],
            'of_those_sized_from_the_longest_enemy_seen': s['cut_sized_from_longest'],
            'whole_in_view_sized_below_their_real_free_steps': s['whole_undersized'],
            'free_steps_taken_by_real_free_steps_5_means_5_or_more': {
                f'real_{r}': {f'took_{t}': s[f'size_real{r}_took{t}'] for t in range(1, 6)} for r in range(1, 6)},
            'same_table_for_the_old_stub_rule': {
                f'real_{r}': {f'took_{t}': s[f'size_real{r}_old{t}'] for t in range(1, 6)} for r in range(1, 6)}},
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
    ap.add_argument('--events')
    a = ap.parse_args()
    base = collect(a.replays, a.base, a.events)
    cand = collect(a.replays, a.candidate, a.events)
    if not base or not cand:
        sys.exit(f'no replays for {a.base!r} or {a.candidate!r} in {a.replays}')
    if set(base) != set(cand):
        sys.exit(f'unpaired replays: {sorted(set(base) ^ set(cand))}')
    keys = sorted(base)
    ball = total(base[k][1] for k in keys)
    call = total(cand[k][1] for k in keys)
    same = sum(base[k][2] == cand[k][2] for k in keys)
    maps = sorted({k[0] for k in keys})
    cells = ('decisions', 'touch', 'possible', 'missed', 'stuck', 'stuck_no_way_out', 'rammed', 'rammed_length')
    by_map = {}
    for m in maps:
        mk = [k for k in keys if k[0] == m]
        bm, cm = total(base[k][1] for k in mk), total(cand[k][1] for k in mk)
        by_map[m] = {'tiles': base[mk[0]][0], 'games_per_side': len(mk),
                     'pairs_playing_the_same_game': sum(base[k][2] == cand[k][2] for k in mk),
                     'base': {x: bm[x] for x in cells}, 'candidate': {x: cm[x] for x in cells}}

    brate, crate = share(ball['missed'], ball['possible']), share(call['missed'], call['possible'])
    target_seen = ball['missed'] >= TARGET_MIN and call['possible'] >= TOUCH_MIN
    cut_ok = target_seen and crate <= CUT * brate
    exit_seen = call['stuck_way_out'] >= EXIT_N
    exit_ok = share(call['exit_ok'], call['stuck_way_out']) >= EXIT_OK if exit_seen else None
    split_n = call['noexit_want_keep2'] + call['noexit_want_stay']
    split_took = call['noexit_want_keep2_answered'] + call['noexit_want_stay_answered']
    split_seen = split_n >= STUCK_N
    split_ok = share(split_took, split_n) >= STUCK_OK if split_seen else None
    move_n, move_took = call['noexit_want_move'], call['noexit_want_move_answered']
    move_seen = move_n >= STUCK_N
    move_ok = share(move_took, move_n) >= STUCK_OK if move_seen else None
    ram_seen = ball['ram_in_view_near'] >= RAM_N
    bnear = 1000 * share(ball['ram_in_view_near'], ball['decisions'])
    cnear = 1000 * share(call['ram_in_view_near'], call['decisions'])
    ram_ok = cnear <= RAM_CUT * bnear if ram_seen else None
    blind_n = call['blind_open']
    blind_took = call['blind_kept_2'] + call['blind_moved_out']
    blind_seen = blind_n >= BLIND_N
    blind_ok = share(blind_took, blind_n) >= STUCK_OK if blind_seen else None
    passed = bool(target_seen and cut_ok and exit_ok is not False and split_ok is not False and move_ok is not False
                  and ram_ok is not False and blind_ok is not False)
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
        why.append(f'no way out, split not taken: {split_took} of {split_n} decisions with keep 2 or stay open took it, '
                   f'{STUCK_OK:.0%} needed')
    if move_ok is False:
        why.append(f'no way out, not the least bad tile: {move_took} of {move_n} decisions with no split open ended on '
                   f'no worse a ring than the best single step, {STUCK_OK:.0%} needed')
    if blind_ok is False:
        why.append(f'tail not known, split not taken: {blind_took} of {blind_n} stuck decisions with no way out, the tail '
                   f'not known and the team below the cap kept 2 (or moved out of the rings), {STUCK_OK:.0%} needed')
    if ram_ok is False:
        why.append(f"near rams in view not cut: {call['ram_in_view_near']} ({cnear:.2f} per 1000 decisions) against base "
                   f"{ball['ram_in_view_near']} ({bnear:.2f}), at most {RAM_CUT} x base allowed")

    def seen_text(flag, need):
        return '' if flag else f' (not seen: fewer than {need}, not judged)'

    bv, cv = view(ball), view(call)
    g = max(1, len(keys))
    note = (
        f"{'PASS' if passed else 'FAIL'}. Measured from {len(keys)} paired games per side on {', '.join(maps)}. Ringed = a tile "
        f"an enemy head (their queen aside) reaches this turn on free steps or by paying 1 length, heads seen in the last 3 "
        f"rounds included; an enemy only partly in view is sized from what our dragon has seen before, not from the stub. "
        f"Decisions by our 31+ dragons (queen aside): base {ball['decisions']}, switch on {call['decisions']}; with a ringed "
        f"tile next to them or under them: {ball['touch']} -> {call['touch']}; of those where a clean ending was possible "
        f"(a clean step, a run out, or a split): {ball['possible']} -> {call['possible']}. Of those, still ended on a ringed "
        f"tile ('missed'): base {ball['missed']} ({brate:.1%}) -> switch on {call['missed']} ({crate:.1%}); by case, clean "
        f"step open {ball['missed_avoidable']} of {ball['avoidable']} -> {call['missed_avoidable']} of {call['avoidable']}, "
        f"stuck with a way out {ball['missed_way_out']} -> {call['missed_way_out']}, stuck with a split open "
        f"{ball['missed_split_open']} -> {call['missed_split_open']}. Stuck decisions (a ringed step and no clean step): "
        f"{ball['stuck']} -> {call['stuck']}; switch on, with a way out: {call['stuck_way_out']}, ended not ringed "
        f"{call['exit_ok']}" + seen_text(exit_seen, EXIT_N)
        + f". STUCK WITH NO WAY OUT, switch on: {call['stuck_no_way_out']}; split kept 2 {call['noexit_split_kept_2']}, "
        f"2 off and stayed on a clean tile {call['noexit_split_2_off_clean_tile']}, 2 off and stayed on a ringed tile "
        f"{call['noexit_split_2_off_ringed_tile']}, least bad tile {call['noexit_least_bad_tile']} (pay ring "
        f"{call['noexit_least_bad_pay_ring']}, free ring {call['noexit_least_bad_free_ring']}), moved onto a worse tile "
        f"{call['noexit_moved_worse_tile']}, moved out {call['noexit_moved_out']}, other "
        f"{call['noexit_split_other'] + call['noexit_no_action'] + call['noexit_died_acting']}. With keep 2 or stay open: "
        f"{split_took} of {split_n} took the split" + seen_text(split_seen, STUCK_N)
        + f"; with no split open: {move_took} of {move_n} ended on no worse a ring than the best single step"
        + seen_text(move_seen, STUCK_N)
        + f" (base, same counts: kept 2 {ball['noexit_split_kept_2']}, least bad tile {ball['noexit_least_bad_tile']}, "
        f"worse tile {ball['noexit_moved_worse_tile']} of {ball['stuck_no_way_out']}). Keep 2 was not open because: team at "
        f"the 64 cap {call['noexit_at_cap']}, tail known and its end ringed {call['noexit_tail_ringed']}, tail known and "
        f"its end cramped {call['noexit_tail_cramped']}. THIS ATTEMPT'S CHANGE, tail not known and team below the cap: "
        f"{blind_n} stuck decisions with no way out (base {ball['blind_open']}); kept 2 {call['blind_kept_2']} (base "
        f"{ball['blind_kept_2']}), moved out {call['blind_moved_out']}, moved onto a ringed tile "
        f"{call['blind_moved_ringed']}, other {call['blind_other']}" + seen_text(blind_seen, BLIND_N)
        + f"; length sent off by those splits {call['blind_child_length']}; tail end inside the parent's own rings "
        f"{call['blind_tail_end_ringed']}. THE BODY THAT LEFT, switch on, all stuck keep-2 splits: "
        f"{call['kept2_children']} ({call['kept2_children_31plus']} still 31+, {call['kept2_child_length']} length); on "
        f"its first turn stuck with no way out {call['child_first_noexit']} of {call['child_first_turns']}; split again "
        f"the round it was born {call['kept2_by_a_child_born_this_round']} (chain position 1 / 2 / 3 / 4+: "
        f"{call['kept2_depth1']} / {call['kept2_depth2']} / {call['kept2_depth3']} / {call['kept2_depth4']}); rammed within "
        f"2 rounds {call['child_rammed_soon']} ({call['child_rammed_soon_length']} length; base "
        f"{ball['child_rammed_soon']}, {ball['child_rammed_soon_length']}); the 2 left behind rammed within 2 rounds "
        f"{call['keeper_rammed_soon']}. Stuck splits that left a 31+ dragon on a ringed tile: "
        f"{ball['stuck_split_stays_ringed']} -> {call['stuck_split_stays_ringed']}. RAMS ON 31+ DRAGONS: {ball['rammed']} "
        f"-> {call['rammed']}; LENGTH LOST TO RAMS PER GAME {ball['rammed_length'] / g:.1f} -> "
        f"{call['rammed_length'] / g:.1f}. RAMMER IN VIEW at our last decision: {ball['rammer_was_in_view']} -> "
        f"{call['rammer_was_in_view']}; of those on free steps or 1 paid ('near'): {ball['ram_in_view_near']} -> "
        f"{call['ram_in_view_near']} ({bnear:.2f} -> {cnear:.2f} per 1000 decisions)" + seen_text(ram_seen, RAM_N)
        + f"; switch-on near rams after an ending outside the rings: {call['ram_in_view_clean_near']} (ring drawn too small "
        f"{call['ram_in_view_clean_near_ring_too_small']}, ring large enough but tile not marked "
        f"{call['ram_in_view_clean_near_ring_blocked']}). Ring size, switch on: {call['heads_cut']} sightings of an enemy "
        f"head whose body ran out of view; sized below its real free steps {call['cut_undersized']} (the old stub rule "
        f"would have: {call['cut_undersized_old_rule']}), above {call['cut_oversized']}; of {call['cut_short']} that were "
        f"really 2-4 long {call['cut_short_oversized']} were taken for longer, of {call['cut_long']} really 13 or longer "
        f"{call['cut_long_undersized']} were still sized too small. Not gated, small sample: length shed by stuck splits "
        f"{ball['stuck_length_shed']} -> "
        f"{call['stuck_length_shed']}; pearls eaten per 100 decisions {bv['pearls_per_100_decisions']} -> "
        f"{cv['pearls_per_100_decisions']}; wins {ball['win']} -> {call['win']}; pairs that played the very same game with "
        f"the switch on and off: {same} of {len(keys)}"
        + ('' if passed else '. NOT shown: ' + '; '.join(why)))
    out = {'passed': passed, 'note': note, 'target_seen': bool(target_seen),
           'mechanism_shown': bool(target_seen and cut_ok and blind_ok),
           'blind_rule_seen': bool(blind_seen),
           'way_out_rule_seen': bool(exit_seen), 'split_rule_seen': bool(split_seen),
           'least_bad_rule_seen': bool(move_seen), 'ram_rule_seen': bool(ram_seen),
           'pairs': len(keys), 'pairs_playing_the_same_game': same, 'maps': maps,
           'pass_rule': {'target_min': TARGET_MIN, 'touch_min': TOUCH_MIN, 'cut': CUT, 'exit_n': EXIT_N, 'exit_ok': EXIT_OK,
                         'stuck_n': STUCK_N, 'stuck_ok': STUCK_OK, 'ram_n': RAM_N, 'ram_cut': RAM_CUT,
                         'target_seen': bool(target_seen), 'cut_ok': bool(cut_ok),
                         'base_rate': round(brate, 4), 'candidate_rate': round(crate, 4),
                         'way_out_rule_seen': bool(exit_seen), 'way_out_rule_ok': exit_ok,
                         'split_rule_seen': bool(split_seen), 'split_rule_ok': split_ok,
                         'split_rule_counts': [split_took, split_n],
                         'least_bad_rule_seen': bool(move_seen), 'least_bad_rule_ok': move_ok,
                         'least_bad_rule_counts': [move_took, move_n],
                         'blind_n': BLIND_N, 'blind_rule_seen': bool(blind_seen), 'blind_rule_ok': blind_ok,
                         'blind_rule_counts': [blind_took, blind_n],
                         'ram_rule_seen': bool(ram_seen), 'ram_rule_ok': ram_ok,
                         'near_rams_in_view': [ball['ram_in_view_near'], call['ram_in_view_near']],
                         'near_rams_in_view_per_1000_decisions': [round(bnear, 3), round(cnear, 3)]},
           'base': bv, 'candidate': cv, 'by_map': by_map,
           'model_check': {'moves_checked': ball['path_checked'] + call['path_checked'],
                           'moves_not_matching_head_updates': ball['path_mismatch'] + call['path_mismatch'],
                           'head_hops': ball['hops'] + call['hops'],
                           'hops_not_matching_walls_and_portals': ball['hop_mismatch'] + call['hop_mismatch']},
           'limits': ('measured from replays: the 7x7 view, kelp walls, portals, each dragon\'s memory of enemy sizes, '
                      'heading, how much of its own body it knows and the 64-dragon cap are rebuilt, so a few tiles can '
                      'differ from what the bot marked (it only walks portals it has seen both ends of, a step through a '
                      'portal is not counted as a step here, heads a teammate reported by sonar are not rebuilt, tiles a '
                      'feeder must keep off near the leader are not rebuilt, the room at the tail end is a plain 5-tile '
                      'walk, and the dead-end test counts never-seen tiles as full room, so it calls fewer tiles dead '
                      'ends than the bot does); that is why the pass rule compares rates instead of asking for zero. The '
                      'rings are the bot\'s view of the danger, not the truth: enemies never seen, enemies longer than '
                      'anything our dragon has seen and enemies paying more than 1 length are outside them, and the ram '
                      'counts show how often that mattered. Base rows use the same rings although base does not draw '
                      'them. How far a rammer came is its walking distance from where it stood when its action began, '
                      'bodies ignored. "Ring drawn too small" = that walk is longer than the ring the check drew for '
                      'that head at our last decision. Pearls eaten are counted from length changes on moves. A long '
                      'dragon that moves into an enemy head itself, or drops to feed the leader, is counted under "died '
                      'acting", not as an ending. Rams, lengths lost, pearls and wins are raw counts from a small '
                      'sample, not evidence of an outcome')}
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
