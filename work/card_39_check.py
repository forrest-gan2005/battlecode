#!/usr/bin/env python3
"""Card #39 queen-safety mechanism check (QUEEN_SAFETY, third build): does our queen also stay off tiles an enemy
head can only hit by paying length, and what does she do when every tile, her own included, is in reach?

usage: python3 work/card_39_check.py --replays DIR --base base --candidate candidate --output FILE
Replays are DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1), paired by (map, seed, side).

For every action of our queen it rebuilds, from the replay alone, what she could see when she decided (the 7x7 box
around her head) and two zones around every visible enemy head, the enemy queen left out:

  free-hit zone = tiles that head can walk onto this turn with its free steps (ceil(length/4): 1 for length 2-4,
                  2 for 5-8, 3 for 9-12 ...; length = the most parts she has seen of that enemy in the last 3 rounds)
  pay ring      = further tiles it can only reach by also paying length (1 length per extra step, never below 2
                  long), up to PAY_REACH steps in all: a 3-long enemy reaches 2 tiles, a 4-long or longer one 3.
                  An enemy whose visible body touches the edge of her view may be longer than it looks, so it
                  counts as one part longer than she sees, and at least 3 long
  danger zone   = both together. Kelp walls and portals are walked, other dragons' bodies block.

  ending    = the tile her head is on once her action is done: where she moved to, or her own tile if she split or
              did nothing
  touch     = a tile she could step onto, or her own tile, was in the danger zone (the rule had something to say)
  safe step = a tile she could step onto, outside the danger zone, that is not a dead-end pocket (a pocket = she
              can reach neither her tail nor length + 2 tiles from it)
  stuck     = touch, and no safe step
  way out   = stuck, but she can still end the turn outside the danger zone, in the order the bot tries them:
              run free = a run of 2+ steps on her free steps to a tile in view outside the zone that is not a pocket;
              wait     = she splits 2 off her tail and stays. Needs a queen 4+ long and her own tile outside the zone;
              run paid = the same run, paying 1 length per extra step (a 3-long queen can pay for one)
  avoidable = she had a safe step, or she was stuck with a way out
  ring-stuck = stuck only because of the pay ring: a pay-ring tile that is not a pocket was open to her, so by the
              second build's rule (free-hit zone only) she had a step to take and would have taken it
  keep-2    = stuck with no way out, 4+ long, so her own tile is in the danger zone too: she splits (length - 2) off
              and stays, so the queen keeps 2 and the rest leaves as a child. Only told apart from a plain 2-split
              when she is 5+ long
  pay pick  = stuck with no way out, shorter than 4 (cannot split), and she could step both onto a pay-ring tile
              that is not a pocket and onto a free-hit tile: she should take the pay-ring tile
  go        = the enemy queen's head is in view and the normal dragon rules say "hit her" (unchanged from the
              second build; only judged early in the game)

PASS RULE (fixed before any switch-on game of this build was played; the constants are below):
  1. target seen: base shows at least TARGET_MIN avoidable endings in the danger zone;
  2. cut: switch-on avoidable danger endings per avoidable touch decision are at most CUT x base's, overall and in
     each map-size group (600 tiles or fewer / bigger) where base shows at least TARGET_MIN;
  3. this build's own rules came up: rule 4 or rule 5 reached its minimum (rules 1-2 and 6-7 are also met by the
     second build, see below, so they cannot show what is new);
  4. ring, judged only if it comes up: with at least RING_N switch-on ring-stuck decisions that had a way out, at
     least RING_OK of them end outside the danger zone;
  5. keep-2, judged only if it comes up: with at least KEEP_N switch-on splits by a stuck queen 5+ long with no way
     out, at least KEEP_OK of them split exactly (length - 2) off;
  6. way out of any kind, judged only if it comes up: with at least EXIT_N switch-on stuck decisions that had a way
     out, at least EXIT_OK of them end outside the danger zone;
  7. pay pick, judged only if it comes up: with at least PICK_N switch-on pay-pick decisions where she moved and
     lived, at most PICK_BAD of them end on a free-hit tile;
  8. free-hit zone, judged only if base shows at least TARGET_MIN avoidable endings inside it: the switch-on rate is
     at most CUT x base's (the first two builds' rule, kept so the new ring does not undo it);
  9. enemy queen, judged only if it comes up: with at least GO_MIN switch-on "go" decisions, at least GO_OK of them
     end with our queen hitting the enemy queen head-on that turn.
Rules 4-9 report "not seen" below their minimum and do not fail the check then; rule 3 does fail it.
Queen deaths, who rammed her and from how far, lengths and wins are raw numbers and NOT part of the pass rule: 16
games per side cannot settle them, the outcome A/B does.
The bot's own log lines are not used: the game runner drops them (--no-debug), so the second build's "QS" marks could
never be read.
Known before this build, from running this check on the second build's kept replays (same 4 maps, older base, the
second build as "switch on", 16 games per side; see the build's check-selftest folder): rules 1-2, 6 and 7 were
already met there; 7 of the queen's 9 ram deaths with the switch on came from a 3-long enemy paying 1 length to hit
her from 2 tiles away; and she was shorter than 4 on 19 of her 21 stuck turns, where neither a wait nor a keep-2
split is possible. So rule 3 may well come out "not seen".
Fourth build: the same bot code moved onto a newer main, no rule changed, so the pass rule and every constant below
are carried over as they were. The third build's run on the older main had rule 3 "not seen" (ring-stuck with a way
out 2 of the 3 needed, keep-2 at 5+ long 0 of 3); the rule is kept anyway, not loosened to fit that.
"""
import argparse, glob, hashlib, json, os, sys, concurrent.futures as cf
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before any switch-on game of this build)
TARGET_MIN = 5       # base avoidable danger endings needed to call the target seen (overall and per group)
CUT = 0.25           # switch-on avoidable danger endings per avoidable touch decision: at most this fraction of base's
RING_N = 3           # switch-on decisions stuck only by the pay ring that had a way out, needed to judge the ring rule
RING_OK = 0.75       # share of those that must end outside the danger zone
EXIT_N = 5           # switch-on stuck decisions with a way out (any kind), needed to judge the way-out rule
EXIT_OK = 0.75       # share of those that must end outside the danger zone
KEEP_N = 3           # switch-on splits by a stuck queen 5+ long with no way out, needed to judge keep-2
KEEP_OK = 0.75       # share of those that must split exactly (length - 2) off
PICK_N = 5           # switch-on pay-pick decisions (moved and lived) needed to judge the pay pick
PICK_BAD = 0.25      # share of those that may end on a free-hit tile
GO_MIN = 3           # switch-on "go" decisions needed to judge the enemy-queen rule
GO_OK = 0.75         # share of those that must end with our queen hitting the enemy queen

VIEW = 3             # the bot sees a 7x7 box around its head
GHOST_ROUNDS = 3     # how long the bot remembers an enemy's size
FREE_DIV = 4         # free steps per turn = ceil(length / 4)
MIN_SIZE = 2         # a dragon cannot pay itself below this
START_SIZE = 3       # INITIAL_LENGTH: the least a half-hidden enemy is taken to be
PAY_REACH = 3        # QS_PAY_REACH: how far an enemy is expected to come when it pays
RUN_MAX = 6          # STRIDE_MAX: the most steps the bot runs in one turn
WAIT_MIN = 4         # shortest queen that can split 2 off and keep 2
SMALL_CELLS = 600    # QUEEN_MIN_CELLS: base only has queen caution above this (or once home is closed off)
SOFT_MAX = 8         # QUEEN_REACH_MAX
BOLD_CELLS = 1200    # AGGRESSIVE_MAX_CELLS: at or below, an equal-length trade counts as worth it
TRADE_MAX = 4        # TRADE_MAX_LENGTH: only dragons this short trade
HUNT_MAX = 10        # HUNT_MAX_LENGTH
HUNT_PARTS = 10      # HUNT_MIN_PARTS
HUNT_MARGIN = 4
CAUSE = ['wall', 'self', 'body', 'headon', 'none']
ZONE = ['out', 'pay', 'free']
DIRS = 'NESW'


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


def free_steps(parts):
    return max(1, (parts + FREE_DIV - 1) // FREE_DIV)


def full_reach(size):
    """Free plus paid steps of a dragon this long."""
    return free_steps(size) + max(0, size - MIN_SIZE)


def pay_reach(parts, shown, cut):
    """How far the bot expects this enemy to come this turn, paying included."""
    size = max(parts, shown + 1, START_SIZE) if cut else parts
    return max(free_steps(parts), min(full_reach(size), PAY_REACH))


def soft_reach(parts):
    return min(SOFT_MAX, max(2, (parts + FREE_DIV - 1) // FREE_DIV + parts - 1))


def flood(step, start, reach, blocked, target):
    """Steps a head on `start` needs onto each tile within `reach`; also the steps it needs onto `target`, or None."""
    dist = {start: 0}
    frontier = [start]
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
    del dist[start]
    return dist, touch


def walk_dist(step, start, target, blocked, limit):
    """Steps from `start` onto `target` through free tiles, or None beyond `limit`."""
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
                if to in seen or to in blocked:
                    continue
                seen.add(to)
                nxt.append(to)
        frontier = nxt
    return None


def fits(step, start, body, others):
    """Bot-style room test for the queen stepping onto `start`: she can reach her tail or at least length + 2 tiles."""
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


def go_rule(size, parts, rnd, cells, allies, enemies, units, dist):
    """The normal dragon rules for hitting an enemy head, applied to the enemy queen. None = not judged this late."""
    bold = cells <= BOLD_CELLS
    if rnd > (300 if bold else 150):
        return None
    reach = (size + FREE_DIV - 1) // FREE_DIV + size - 2
    hunt = size <= HUNT_MAX and parts >= HUNT_PARTS and parts >= size + HUNT_MARGIN
    worth = parts >= size if bold else parts >= max(5, size + 2)
    trade = size <= TRADE_MAX and units >= (1 if bold else 8) and allies + 1 - enemies >= 1 and worth
    if dist is None:
        return False
    return bool((hunt and dist <= min(reach, 8)) or (trade and dist <= min(reach, 3 if bold else 4)))


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
    events = list(root.pointer(3))
    track = hashlib.sha1()

    memory = {}
    pending = None
    left = None          # how her last finished action left her: (zone of her ending, 'move' or 'stay'), or None
    mover = None
    act_from, act_len = None, 0
    rnd = 0

    def look():
        body = bodies[queen]
        head = body[0]

        def in_view(cell):
            return gap(cell[0], head[0], W) <= VIEW and gap(cell[1], head[1], H) <= VIEW

        def on_edge(cell):
            return gap(cell[0], head[0], W) == VIEW or gap(cell[1], head[1], H) == VIEW

        own = set(body)
        seen_block = set(own)
        true_block = set(own)
        seen_block.discard(body[-1])
        true_block.discard(body[-1])
        taken = set(own)
        others = set()
        foes, far, friends = [], [], []
        rival = None
        units = 0
        for did, b in bodies.items():
            if not b:
                continue
            units += team_of.get(did) == ours
            if did == queen:
                continue
            taken.update(b)
            true_block.update(b)
            inside = [cell for cell in b if in_view(cell)]
            seen_block.update(inside)
            others.update(inside)
            if team_of.get(did) == ours:
                if in_view(b[0]):
                    friends.append((b[0], len(inside)))
                continue
            if in_view(b[0]):
                was = memory.get(did)
                parts = max(len(inside), was[1]) if was and rnd - was[0] <= GHOST_ROUNDS else len(inside)
                memory[did] = (rnd, parts)
                if did == foe_queen:
                    rival = (b[0], parts, len(inside))
                else:
                    foes.append((b[0], parts, len(inside), any(on_edge(cell) for cell in inside), len(b)))
            elif did != foe_queen and gap(b[0][0], head[0], W) + gap(b[0][1], head[1], H) <= min(full_reach(len(b)), 12) + 1:
                far.append((b[0], len(b)))
        hit, pay, soft, true_hit, true_reach = set(), set(), set(), set(), set()
        own_zone = 0
        cut_foes = 0
        for at, parts, shown, cut, real in foes:
            free = free_steps(parts)
            dist, touch = flood(step, at, pay_reach(parts, shown, cut), seen_block, head)
            hit.update(t for t, n in dist.items() if n <= free)
            pay.update(dist)
            if touch is not None:
                own_zone = max(own_zone, 2 if touch <= free else 1)
            cut_foes += cut
            soft.update(flood(step, at, soft_reach(parts), seen_block, head)[0])
        for at, real in [(f[0], f[4]) for f in foes] + far:
            dist = flood(step, at, min(full_reach(real), 12), true_block, head)[0]
            true_hit.update(t for t, n in dist.items() if n <= free_steps(real))
            true_reach.update(dist)
        pay -= hit
        rival_zone, go = set(), None
        if rival:
            at, parts, shown = rival
            rival_zone = set(flood(step, at, free_steps(parts), seen_block, head)[0]) - hit
            go = go_rule(len(body), shown, rnd, W * H, len(friends), len(foes) + 1, units, walk_dist(step, head, at, taken, 8))
        walk = []
        for d in DIRS:
            hop = step(head, d)
            if hop is not None and not hop[1] and hop[0] not in taken:
                walk.append(hop[0])
        zone = {t: 2 if t in hit else 1 if t in pay else 0 for t in walk}
        roomy = {t: fits(step, t, body, others) for t in walk}
        touch = own_zone > 0 or any(zone.values())
        safe = any(zone[t] == 0 and roomy[t] for t in walk)
        # A run of 2+ steps this turn to a tile in view outside the danger zone: 'free' on her free steps, 'paid' if
        # it costs length (she cannot pay herself below 2, and the bot runs at most 6 steps).
        run = None
        if touch and not safe:
            mine = free_steps(len(body))
            depth = {head: 0}
            frontier = [head]
            for n in range(min(full_reach(len(body)), RUN_MAX)):
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
                        if n + 1 >= 2 and run is None and to not in hit and to not in pay and fits(step, to, body, others):
                            run = 'free' if n + 1 <= mine else 'paid'
                frontier = nxt
        return dict(start=head, end=head, len=len(body), rnd=rnd, view=bool(foes), hit=hit, pay=pay, soft=soft,
                    true_hit=true_hit, true_reach=true_reach, own=own_zone, touch=touch, safe=safe, run=run,
                    stuck=touch and not safe, step_free=any(z == 2 for z in zone.values()),
                    step_pay=any(z == 1 for z in zone.values()), ring=any(zone[t] == 1 and roomy[t] for t in walk),
                    pick=any(zone[t] == 1 and roomy[t] for t in walk) and any(z == 2 for z in zone.values()),
                    boxed=not walk, cut=cut_foes, rival=bool(rival), rival_zone=rival_zone, go=go,
                    seen=0, dead=False, cause=None, killed=set(), child=0)

    def close():
        nonlocal pending, left
        p, pending = pending, None
        if p is None:
            return
        left = None
        long = p['len'] >= WAIT_MIN
        way = tier = None
        if p['stuck']:
            way = 'run_free' if p['run'] == 'free' else 'wait' if long and p['own'] == 0 else 'run_paid' if p['run'] else None
            tier = 'exit' if way else 'keep' if long else 'short'
        avoidable = p['touch'] and (p['safe'] or way is not None)
        moved = p['kind'] == 'move'
        track.update(f"{p['rnd']}{p['kind']}{p['end']}{p['child']}{p['dead']}".encode())
        c['decisions'] += 1
        c['view'] += p['view']
        c['view_cut'] += p['cut'] > 0
        c['touch'] += p['touch']
        c['touch_own'] += p['own'] > 0
        c['touch_free'] += p['step_free'] or p['own'] == 2
        c['touch_avoidable'] += avoidable
        c['touch_safe'] += p['touch'] and p['safe']
        c['stuck'] += p['stuck']
        c['boxed'] += p['stuck'] and p['boxed']
        if tier:
            c['stuck_' + tier] += 1
            c['stuck_len3'] += p['len'] == 3
            c['stuck_len2'] += p['len'] == 2
        if way:
            c['exit_' + way] += 1
        ring = p['stuck'] and p['ring']
        c['ring_stuck'] += ring
        c['ring_exit'] += ring and way is not None
        c['ring_keep'] += ring and tier == 'keep'
        c['ring_short'] += ring and tier == 'short'
        pick = tier == 'short' and p['pick']
        c['pick'] += pick
        c['short_all_free'] += tier == 'short' and not p['step_pay'] and not p['boxed']
        hit_rival = foe_queen in p['killed'] and p['dead']
        c['rival_seen'] += p['rival']
        c['queen_hit_rival'] += hit_rival
        if p['rival'] and p['go'] is not None:
            c['rival_judged'] += 1
            c['go'] += p['go']
            c['go_hit'] += p['go'] and hit_rival
            c['no_go_hit'] += (not p['go']) and hit_rival
        if moved and p['dead']:
            c['moves'] += 1
            c['moves_died'] += 1
            if tier:
                c[f'stuck_{tier}_' + ('own_ram' if p['cause'] == 'headon' else 'died')] += 1
            return
        if moved:
            c['moves'] += 1
            c['multi_moves'] += p['n'] >= 2
            c['moves_view'] += p['view']
            c['path_checked'] += 1
            c['path_mismatch'] += p['seen'] != p['n']
            end = p['end']
            where = 2 if end in p['hit'] else 1 if end in p['pay'] else 0
            c['soft_end'] += end in p['soft']
            c['rival_moves'] += p['rival']
            c['rival_zone_end'] += end in p['rival_zone']
        else:
            end = p['start']
            where = p['own']
            split = p['kind'] == 'split'
            c['splits' if split else 'other_actions'] += 1
            if split:
                c['splits_stuck'] += p['stuck']
                c['splits_own_in_zone'] += p['own'] > 0
                c['splits_own_in_zone_with_safe_step'] += p['own'] > 0 and p['safe']
                c['length_split_off_while_stuck'] += p['child'] if p['stuck'] else 0
                keep2 = p['child'] == p['len'] - MIN_SIZE
                if tier == 'keep':
                    c['keep_splits'] += 1
                    c['keep_splits_keep2'] += keep2
                    if p['len'] > WAIT_MIN:
                        c['keep5_splits'] += 1
                        c['keep5_splits_keep2'] += keep2
                if way == 'wait' and p['len'] > WAIT_MIN:
                    c['wait5_splits'] += 1
                    c['wait5_splits_of_2'] += p['child'] == MIN_SIZE
        how = 'move' if moved else 'stay'
        if way and not where:
            c[f'exit_{way}_ok'] += 1
            c['ring_exit_ok'] += ring
        c[f'end_{ZONE[where]}'] += p['touch']
        c['end_true_hit'] += end in p['true_hit']
        c['end_true_reach'] += end in p['true_reach']
        if avoidable and where:
            c['danger'] += 1
            c[f'danger_{ZONE[where]}'] += 1
            c[f'danger_{how}'] += 1
        c['danger_free_base'] += avoidable and (p['step_free'] or p['own'] == 2)
        if tier:
            c[f'stuck_{tier}_{how}_{ZONE[where]}'] += 1
        if pick and moved:
            c['pick_moved'] += 1
            c[f'pick_{ZONE[where]}'] += 1
        if where:
            left = (ZONE[where], how, 'no_way_out' if tier in ('keep', 'short') else 'avoidable' if avoidable else 'other')

    for ev in events:
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if kind == 'roundStart':
            close()
            mover = None
            act_from, act_len = None, 0
            rnd = pl.i32(0)
        elif kind == 'dragonAction':
            close()
            mover = pl.i32(0)
            a = pl.pointer(0)
            b = bodies.get(mover)
            act_from, act_len = (b[0], len(b)) if b else (None, 0)
            if mover != queen or a is None or not bodies.get(queen):
                continue
            pending = look()
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
            b = bodies.setdefault(did, deque())
            if not b or b[0] != h:
                if b:
                    c['hops'] += 1
                    c['hop_mismatch'] += all((step(b[0], d) or (None,))[0] != h for d in DIRS)
                b.appendleft(h)
                if pending and did == queen:
                    pending['seen'] += 1
                    pending['end'] = h
            while len(b) > 1 and b[-1] != tp:
                b.pop()
        elif kind == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x) for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
            if pending and pa == queen:
                pending['child'] = len(bodies[ch])
        elif kind == 'dragonDeath':
            did = pl.i32(0)
            r = pl.u16(4)
            b = bodies.pop(did, None)
            cause = CAUSE[r] if r < 5 else 'other'
            if pending:
                pending['killed'].add(did)
            if did == foe_queen and cause == 'headon' and mover == foe_queen and pending is None:
                c['rival_moved_into_a_head'] += 1
            if did != queen:
                continue
            if pending:
                pending['dead'] = True
                pending['cause'] = cause
            c['queen_deaths'] += 1
            c[f'queen_deaths_{cause}'] += 1
            c['queen_death_round_sum'] += rnd
            c['queen_death_short'] += len(b or ()) < WAIT_MIN
            if cause == 'headon' and mover == queen:
                c['queen_own_ram'] += 1
            elif cause == 'headon':
                c['queen_rammed'] += 1
                c['queen_rammed_by_rival'] += mover == foe_queen
                c['rammed_after_' + (f'{left[1]}_in_{left[0]}' if left else 'ending_outside')] += 1
                if left:
                    c['rammed_in_zone_' + left[2]] += 1
                    c['rammed_in_zone_short'] += len(b or ()) < WAIT_MIN
                came = walk_dist(step, act_from, b[0], set(), 12) if b and act_from else None
                if came is None:
                    c['rammer_unknown'] += 1
                else:
                    paid = came > free_steps(act_len)
                    c['rammer_paid' if paid else 'rammer_free'] += 1
                    if paid:
                        c[f'rammer_paid_len{min(act_len, 5)}'] += 1
                        c['rammer_paid_within_ring'] += came <= PAY_REACH
    close()
    c['queen_final_len'] = len(bodies.get(queen) or ())
    c['foe_queen_final_len'] = len(bodies.get(foe_queen) or ())
    return 'small' if W * H <= SMALL_CELLS else 'big', dict(c), track.hexdigest()


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


def stuck_view(s, tier):
    def n(*names):
        return sum(s[f'stuck_{tier}_{name}'] for name in names)
    return {'decisions': s['stuck_' + tier],
            'stayed_on_a_tile_out_of_reach': n('stay_out'), 'moved_out_of_the_danger_zone': n('move_out'),
            'moved_onto_a_pay_ring_tile': n('move_pay'), 'moved_onto_a_free_hit_tile': n('move_free'),
            'stayed_on_a_pay_ring_tile': n('stay_pay'), 'stayed_on_a_free_hit_tile': n('stay_free'),
            'hit_a_head_herself': n('own_ram'), 'died_moving': n('died')}


def view(s):
    g = max(1, s['games'])
    return {'games': s['games'], 'wins': s['win'],
            'queen_decisions': s['decisions'], 'with_enemy_head_in_view': s['view'],
            'of_those_with_an_enemy_body_running_out_of_view': s['view_cut'],
            'touch_decisions': s['touch'], 'of_those_with_her_own_tile_in_the_zone': s['touch_own'],
            'of_those_with_a_free_hit_tile': s['touch_free'], 'of_those_with_a_safe_step': s['touch_safe'],
            'avoidable_touch_decisions': s['touch_avoidable'],
            'avoidable_danger_endings': s['danger'],
            'avoidable_danger_endings_per_touch': round(share(s['danger'], s['touch_avoidable']), 4),
            'avoidable_danger_endings_by_zone': {'free_hit': s['danger_free'], 'pay_ring': s['danger_pay']},
            'avoidable_danger_endings_by_action': {'moved_in': s['danger_move'], 'stayed_in': s['danger_stay']},
            'avoidable_decisions_with_a_free_hit_tile': s['danger_free_base'],
            'avoidable_free_hit_endings_per_such_decision': round(share(s['danger_free'], s['danger_free_base']), 4),
            'endings_of_touch_decisions': {'out_of_reach': s['end_out'], 'pay_ring': s['end_pay'], 'free_hit': s['end_free']},
            'stuck_decisions': s['stuck'], 'of_those_with_no_tile_to_step_onto': s['boxed'],
            'stuck_by_queen_length': {'2': s['stuck_len2'], '3': s['stuck_len3'],
                                      '4_or_more': s['stuck'] - s['stuck_len2'] - s['stuck_len3']},
            'stuck_with_a_way_out': stuck_view(s, 'exit'),
            'way_out_by_kind': {k: {'decisions': s['exit_' + k], 'ended_outside_the_zone': s[f'exit_{k}_ok']}
                                for k in ('run_free', 'wait', 'run_paid')},
            'way_out_taken_share': round(share(s['stuck_exit_stay_out'] + s['stuck_exit_move_out'], s['stuck_exit']), 4),
            'ring_stuck_decisions': s['ring_stuck'],
            'ring_stuck_by_case': {'with_a_way_out': s['ring_exit'], 'no_way_out_4plus': s['ring_keep'],
                                   'no_way_out_shorter_than_4': s['ring_short']},
            'ring_stuck_with_a_way_out_ended_outside': s['ring_exit_ok'],
            'ring_way_out_taken_share': round(share(s['ring_exit_ok'], s['ring_exit']), 4),
            'stuck_4plus_no_way_out': stuck_view(s, 'keep'),
            'splits_there': s['keep_splits'], 'of_those_splitting_length_minus_2_off': s['keep_splits_keep2'],
            'splits_there_5plus_long': s['keep5_splits'],
            'of_those_5plus_splitting_length_minus_2_off': s['keep5_splits_keep2'],
            'keep_2_share_5plus': round(share(s['keep5_splits_keep2'], s['keep5_splits']), 4),
            'waits_5plus_long_with_own_tile_out_of_reach': s['wait5_splits'], 'of_those_splitting_2_off': s['wait5_splits_of_2'],
            'stuck_shorter_than_4_no_way_out': stuck_view(s, 'short'),
            'of_those_with_only_free_hit_tiles_to_step_onto': s['short_all_free'],
            'pay_pick_decisions': s['pick'], 'pay_pick_moved_and_lived': s['pick_moved'],
            'pay_pick_endings': {'pay_ring': s['pick_pay'], 'free_hit': s['pick_free'], 'out_of_reach': s['pick_out']},
            'pay_pick_free_hit_share': round(share(s['pick_free'], s['pick_moved']), 4),
            'enemy_queen_in_view_decisions': s['rival_seen'], 'of_those_judged_early': s['rival_judged'],
            'go_decisions': s['go'], 'go_decisions_ending_in_a_hit': s['go_hit'],
            'go_hit_share': round(share(s['go_hit'], s['go']), 4),
            'hits_on_enemy_queen_without_go': s['no_go_hit'], 'our_queen_hit_enemy_queen': s['queen_hit_rival'],
            'moves_with_enemy_queen_in_view': s['rival_moves'],
            'of_those_ending_where_only_the_enemy_queen_could_hit': s['rival_zone_end'],
            'queen_splits': s['splits'], 'queen_splits_while_stuck': s['splits_stuck'],
            'queen_splits_with_own_tile_in_the_zone': s['splits_own_in_zone'],
            'of_those_with_a_safe_step_free': s['splits_own_in_zone_with_safe_step'],
            'length_split_off_while_stuck': s['length_split_off_while_stuck'],
            'queen_moves': s['moves'], 'queen_multi_step_moves': s['multi_moves'],
            'queen_moves_with_enemy_in_view': s['moves_view'], 'of_those_ending_inside_wider_danger_zone': s['soft_end'],
            'wider_danger_zone_share': round(share(s['soft_end'], s['moves_view']), 4),
            'endings_an_enemy_could_reach_on_free_steps_by_true_length': s['end_true_hit'],
            'endings_an_enemy_could_reach_paying_by_true_length': s['end_true_reach'],
            'queen_deaths': s['queen_deaths'],
            'queen_deaths_by_cause': {k: s[f'queen_deaths_{k}'] for k in CAUSE if s[f'queen_deaths_{k}']},
            'queen_deaths_while_shorter_than_4': s['queen_death_short'],
            'queen_rammed_by_enemy_head': s['queen_rammed'], 'of_those_by_the_enemy_queen': s['queen_rammed_by_rival'],
            'rammed_by_where_her_last_action_left_her': {
                'moved_onto_a_free_hit_tile': s['rammed_after_move_in_free'], 'stayed_on_a_free_hit_tile': s['rammed_after_stay_in_free'],
                'moved_onto_a_pay_ring_tile': s['rammed_after_move_in_pay'], 'stayed_on_a_pay_ring_tile': s['rammed_after_stay_in_pay'],
                'outside_both_as_she_saw_it': s['rammed_after_ending_outside']},
            'rammed_in_the_zone_by_her_choice_there': {'stuck_with_no_way_out': s['rammed_in_zone_no_way_out'],
                                                       'avoidable': s['rammed_in_zone_avoidable'],
                                                       'other': s['rammed_in_zone_other']},
            'rammed_in_the_zone_while_shorter_than_4': s['rammed_in_zone_short'],
            'rammer_came_on_free_steps': s['rammer_free'], 'rammer_paid_length': s['rammer_paid'],
            'rammer_paid_by_its_length': {k: s[f'rammer_paid_len{n}'] for k, n in (('2', 2), ('3', 3), ('4', 4), ('5_or_more', 5))
                                          if s[f'rammer_paid_len{n}']},
            'rammer_paid_from_within_3_tiles': s['rammer_paid_within_ring'], 'rammer_path_unknown': s['rammer_unknown'],
            'queen_rammed_a_head_herself': s['queen_own_ram'],
            'queen_death_round_mean': round(share(s['queen_death_round_sum'], s['queen_deaths']), 1),
            'queen_final_length_per_game': round(s['queen_final_len'] / g, 2),
            'enemy_queen_final_length_per_game': round(s['foe_queen_final_len'] / g, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--replays', required=True)
    ap.add_argument('--base', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    base, cand = collect(a.replays, a.base), collect(a.replays, a.candidate)
    if not base or set(base) != set(cand):
        sys.exit(f'missing or unpaired replays in {a.replays}: {len(base)} {a.base}, {len(cand)} {a.candidate}')
    keys = sorted(base)
    groups = ('small', 'big')
    b = {g: total(base[k][1] for k in keys if base[k][0] == g) for g in groups}
    c = {g: total(cand[k][1] for k in keys if cand[k][0] == g) for g in groups}
    ball, call = total(b.values()), total(c.values())
    same_track = sum(base[k][2] == cand[k][2] for k in keys)
    moves = ball['path_checked'] + call['path_checked']
    hops = ball['hops'] + call['hops']
    if moves and ball['path_mismatch'] + call['path_mismatch'] > 0.02 * moves:
        sys.exit('replay moves do not line up with head updates; the measurement is not valid')
    if hops and ball['hop_mismatch'] + call['hop_mismatch'] > 0.005 * hops:
        sys.exit('head moves do not follow the rebuilt walls and portals; the measurement is not valid')

    bv, cv = view(ball), view(call)

    def rate(s):
        return share(s['danger'], s['touch_avoidable'])

    def free_rate(s):
        return share(s['danger_free'], s['danger_free_base'])

    target_seen = ball['danger'] >= TARGET_MIN
    cut_ok = rate(call) <= CUT * rate(ball)
    group_rule = {}
    for g in groups:
        seen = b[g]['danger'] >= TARGET_MIN
        group_rule[g] = {'games': b[g]['games'], 'target_seen': bool(seen),
                         'cut_ok': bool(rate(c[g]) <= CUT * rate(b[g])) if seen else None}
    groups_ok = all(r['cut_ok'] for r in group_rule.values() if r['target_seen'])
    free_seen = ball['danger_free'] >= TARGET_MIN
    free_ok = bool(free_rate(call) <= CUT * free_rate(ball)) if free_seen else None
    ring_seen = call['ring_exit'] >= RING_N
    ring_ok = bool(cv['ring_way_out_taken_share'] >= RING_OK) if ring_seen else None
    exit_seen = call['stuck_exit'] >= EXIT_N
    exit_ok = bool(cv['way_out_taken_share'] >= EXIT_OK) if exit_seen else None
    keep_seen = call['keep5_splits'] >= KEEP_N
    keep_ok = bool(cv['keep_2_share_5plus'] >= KEEP_OK) if keep_seen else None
    pick_seen = call['pick_moved'] >= PICK_N
    pick_ok = bool(cv['pay_pick_free_hit_share'] <= PICK_BAD) if pick_seen else None
    go_seen = call['go'] >= GO_MIN
    go_ok = bool(cv['go_hit_share'] >= GO_OK) if go_seen else None
    new_seen = ring_seen or keep_seen
    passed = bool(target_seen and cut_ok and groups_ok and new_seen and
                  all(x is not False for x in (free_ok, ring_ok, exit_ok, keep_ok, pick_ok, go_ok)))
    why = []
    if not target_seen:
        why.append(f"base showed only {ball['danger']} avoidable danger endings (need {TARGET_MIN})")
    if not cut_ok:
        why.append('avoidable danger endings per touch decision did not fall to a quarter of base')
    if not groups_ok:
        why.append('the cut failed on ' + ' and '.join(g for g, r in group_rule.items() if r['target_seen'] and not r['cut_ok']) + ' maps')
    if not new_seen:
        why.append(f"this build's own rules did not come up often enough to judge (stuck by the pay ring with a way out "
                   f"{call['ring_exit']}, needs {RING_N}; keep-2 splits by a queen 5+ long {call['keep5_splits']}, needs {KEEP_N}); "
                   f"the queen was shorter than 4 on {call['stuck_len2'] + call['stuck_len3']} of her {call['stuck']} stuck turns")
    if free_ok is False:
        why.append('avoidable endings on free-hit tiles did not fall to a quarter of base')
    if ring_ok is False:
        why.append('a queen stuck only by the pay ring still ended in the danger zone too often although she had a way out')
    if exit_ok is False:
        why.append('a stuck queen with a way out still ended in the danger zone too often')
    if keep_ok is False:
        why.append('a stuck queen 5+ long with no way out too rarely split (length - 2) off')
    if pick_ok is False:
        why.append('a stuck short queen took the free-hit tile over the pay-ring tile too often')
    if go_ok is False:
        why.append('our queen too rarely hit the enemy queen when the normal rules said go')

    def stuck_text(v, key):
        s = v[key]
        return (f"{s['decisions']} (stayed out of reach {s['stayed_on_a_tile_out_of_reach']}, moved out {s['moved_out_of_the_danger_zone']}, "
                f"moved onto a pay-ring tile {s['moved_onto_a_pay_ring_tile']}, onto a free-hit tile {s['moved_onto_a_free_hit_tile']}, "
                f"stayed in reach {s['stayed_on_a_pay_ring_tile'] + s['stayed_on_a_free_hit_tile']}, "
                f"hit a head herself {s['hit_a_head_herself']}, died moving {s['died_moving']})")

    def ram_text(v):
        r = v['rammed_by_where_her_last_action_left_her']
        return (f"{v['queen_rammed_by_enemy_head']} (after ending on a free-hit tile "
                f"{r['moved_onto_a_free_hit_tile'] + r['stayed_on_a_free_hit_tile']}, on a pay-ring tile "
                f"{r['moved_onto_a_pay_ring_tile'] + r['stayed_on_a_pay_ring_tile']}, outside both {r['outside_both_as_she_saw_it']}; "
                f"rammer paid length {v['rammer_paid_length']}, came on free steps {v['rammer_came_on_free_steps']})")

    def seen_text(seen, need):
        return '' if seen else f' - NOT seen (needs {need})'

    def way_text(v):
        w = v['way_out_by_kind']
        return ', '.join(f"{name} {w[k]['decisions']}/{w[k]['ended_outside_the_zone']}"
                         for k, name in (('run_free', 'run on free steps'), ('wait', 'wait'), ('run_paid', 'run by paying')))

    unseen = [g for g, r in group_rule.items() if not r['target_seen']]
    note = (f"queen actions that end on a tile a visible enemy head (the enemy queen left out) can hit this turn, on free steps or "
            f"by paying length, although she could have avoided it: base {bv['avoidable_danger_endings']} in "
            f"{bv['avoidable_touch_decisions']} touch decisions ({bv['avoidable_danger_endings_per_touch']:.1%}) -> switch on "
            f"{cv['avoidable_danger_endings']} in {cv['avoidable_touch_decisions']} ({cv['avoidable_danger_endings_per_touch']:.1%}); "
            f"of those on free-hit tiles {ball['danger_free']} -> {call['danger_free']}, on pay-ring tiles {ball['danger_pay']} -> "
            f"{call['danger_pay']}; by moving in {ball['danger_move']} -> {call['danger_move']}, by staying (split) {ball['danger_stay']} "
            f"-> {call['danger_stay']}; by map group: "
            + ', '.join(f"{g} {b[g]['danger']}/{b[g]['touch_avoidable']} -> {c[g]['danger']}/{c[g]['touch_avoidable']} "
                        f"in {b[g]['games']} games" for g in groups)
            + (f" ({' and '.join(unseen)} maps: too few base cases to judge on their own)" if unseen else '')
            + f"; free-hit zone alone (first two builds' rule): base {ball['danger_free']} in {ball['danger_free_base']} -> switch on "
            f"{call['danger_free']} in {call['danger_free_base']}" + seen_text(free_seen, TARGET_MIN)
            + f"; stuck decisions {bv['stuck_decisions']} -> {cv['stuck_decisions']}, by queen length base {bv['stuck_by_queen_length']} "
            f"-> switch on {cv['stuck_by_queen_length']}; stuck with a way out: base {stuck_text(bv, 'stuck_with_a_way_out')} -> switch "
            f"on {stuck_text(cv, 'stuck_with_a_way_out')}, by kind of way out (decisions / ended outside) base {way_text(bv)} -> switch "
            f"on {way_text(cv)}" + seen_text(exit_seen, EXIT_N)
            + f"; stuck only because of the pay ring (a roomy pay-ring tile was open, new in this build): base {bv['ring_stuck_decisions']} "
            f"{bv['ring_stuck_by_case']} -> switch on {cv['ring_stuck_decisions']} {cv['ring_stuck_by_case']}, of those with a way out "
            f"ending outside the zone {bv['ring_stuck_with_a_way_out_ended_outside']} -> {cv['ring_stuck_with_a_way_out_ended_outside']}"
            + seen_text(ring_seen, RING_N)
            + f"; stuck, 4+ long, no way out: base {stuck_text(bv, 'stuck_4plus_no_way_out')} -> switch on "
            f"{stuck_text(cv, 'stuck_4plus_no_way_out')}; her splits there when 5+ long: base "
            f"{bv['splits_there_5plus_long']} ({bv['of_those_5plus_splitting_length_minus_2_off']} split length - 2 off) -> switch on "
            f"{cv['splits_there_5plus_long']} ({cv['of_those_5plus_splitting_length_minus_2_off']} split length - 2 off)"
            + seen_text(keep_seen, KEEP_N)
            + f"; stuck, shorter than 4, no way out: base {stuck_text(bv, 'stuck_shorter_than_4_no_way_out')} -> switch on "
            f"{stuck_text(cv, 'stuck_shorter_than_4_no_way_out')}; pay pick (a pay-ring tile and a free-hit tile both open, moved and lived): "
            f"base {bv['pay_pick_moved_and_lived']} with {bv['pay_pick_endings']['free_hit']} ending on the free-hit tile -> switch on "
            f"{cv['pay_pick_moved_and_lived']} with {cv['pay_pick_endings']['free_hit']}" + seen_text(pick_seen, PICK_N)
            + f"; enemy queen in view: {bv['enemy_queen_in_view_decisions']} -> {cv['enemy_queen_in_view_decisions']} decisions, 'go' by "
            f"the normal rules {bv['go_decisions']} -> {cv['go_decisions']}, of those ending with our queen hitting her "
            f"{bv['go_decisions_ending_in_a_hit']} -> {cv['go_decisions_ending_in_a_hit']}" + seen_text(go_seen, GO_MIN)
            + f"; not gated, {len(keys)} games each: queen deaths {bv['queen_deaths']} -> {cv['queen_deaths']}, rammed by an enemy head "
            f"base {ram_text(bv)} -> switch on {ram_text(cv)}, rammed a head herself {bv['queen_rammed_a_head_herself']} -> "
            f"{cv['queen_rammed_a_head_herself']}, queen splits {bv['queen_splits']} -> {cv['queen_splits']} (with her own tile in the "
            f"zone {bv['queen_splits_with_own_tile_in_the_zone']} -> {cv['queen_splits_with_own_tile_in_the_zone']}), length split off "
            f"while stuck {bv['length_split_off_while_stuck']} -> {cv['length_split_off_while_stuck']}, queen multi-step moves "
            f"{bv['queen_multi_step_moves']} -> {cv['queen_multi_step_moves']}, queen length at the end "
            f"{bv['queen_final_length_per_game']} -> {cv['queen_final_length_per_game']} per game, wins {bv['wins']} -> {cv['wins']}, "
            f"pairs where the queen did exactly the same with the switch on and off {same_track} of {len(keys)}"
            + ('' if passed else '. NOT shown: ' + '; '.join(why)))
    out = {'passed': passed, 'note': note, 'target_seen': bool(target_seen), 'new_rules_seen': bool(new_seen),
           'ring_rule_seen': bool(ring_seen), 'keep_2_rule_seen': bool(keep_seen), 'way_out_rule_seen': bool(exit_seen),
           'pay_pick_rule_seen': bool(pick_seen), 'free_hit_rule_seen': bool(free_seen), 'enemy_queen_rule_seen': bool(go_seen),
           'pairs': len(keys), 'pairs_with_identical_queen_track': same_track, 'maps': sorted({k[0] for k in keys}),
           'pass_rule': {'target_min': TARGET_MIN, 'cut': CUT, 'ring_n': RING_N, 'ring_ok': RING_OK, 'exit_n': EXIT_N,
                         'exit_ok': EXIT_OK, 'keep_n': KEEP_N,
                         'keep_ok': KEEP_OK, 'pick_n': PICK_N, 'pick_bad': PICK_BAD, 'go_min': GO_MIN, 'go_ok': GO_OK,
                         'target_seen': bool(target_seen), 'cut_ok': bool(cut_ok), 'by_map_group': group_rule,
                         'groups_ok': bool(groups_ok), 'new_rules_seen': bool(new_seen),
                         'ring_rule_seen': bool(ring_seen), 'ring_rule_ok': ring_ok,
                         'way_out_rule_seen': bool(exit_seen), 'way_out_rule_ok': exit_ok,
                         'free_hit_rule_seen': bool(free_seen), 'free_hit_rule_ok': free_ok,
                         'keep_2_rule_seen': bool(keep_seen), 'keep_2_rule_ok': keep_ok,
                         'pay_pick_rule_seen': bool(pick_seen), 'pay_pick_rule_ok': pick_ok,
                         'enemy_queen_rule_seen': bool(go_seen), 'enemy_queen_rule_ok': go_ok},
           'base': bv, 'candidate': cv,
           'by_map_group': {g: {'base': view(b[g]), 'candidate': view(c[g])} for g in groups},
           'model_check': {'queen_moves_checked': moves, 'moves_not_matching_head_updates': ball['path_mismatch'] + call['path_mismatch'],
                           'head_hops': hops, 'hops_not_matching_walls_and_portals': ball['hop_mismatch'] + call['hop_mismatch']},
           'limits': ('measured from replays: the 7x7 view, kelp walls, portals, the remembered enemy size and the "body runs out of '
                      'view" guess are rebuilt, so a few tiles can differ from what the bot marked (it only walks portals it has '
                      'already seen both ends of, the unit cap that forbids a split is not rebuilt, and the dead-end test counts '
                      'never-seen tiles as full room, so it calls fewer tiles dead ends than the bot does); the zones are the bot\'s '
                      'view of the danger, not the truth: enemies out of sight, enemies longer than they look and enemies paying '
                      'for more than 3 steps are outside them, and the two "by true length" counts show how often that mattered; '
                      'how far a rammer came is its walking distance from where it stood when its action began, bodies ignored; '
                      'the "go" rule is a rebuild of the normal trade and hunt rules from what was in view and is only judged '
                      'early in the game; that the trapped queen\'s move equals what a normal dragon would do is by construction '
                      'of the code, not measured; the bot\'s own log lines are not recorded by the game runner and are not used; '
                      'deaths, lengths and wins are raw counts from a small sample, not evidence of an outcome')}
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
        sys.exit(f'card 39 check failed: {exc}')
