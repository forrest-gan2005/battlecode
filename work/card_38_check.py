#!/usr/bin/env python3
"""Card #38 queen-loop mechanism check, third build (QUEEN_CAREFUL): does our queen stop ending her turn on tiles
that leave her no room for the next two turns, without giving up portals, and does she close on enemy heads less?

usage: python3 work/card_38_check.py --replays DIR --base base --candidate candidate --output FILE
Replays are DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1), paired by (map, seed, side).

For every action of our queen it rebuilds, from the replay alone, what she could see when she decided (the 7x7 box
around her head) and where the action left her.

  ring 1      = tiles next to a tile that she could step onto on her next turn (kelp walls, her own body and other
                dragons' bodies in view block; a portal counts as a way on only on maps of 600 tiles or fewer,
                where the base bot lets the queen take portals)
  ring 2      = further tiles she could reach from ring 1 the turn after
  danger zone = tiles a visible enemy head (the enemy queen left out) can enter this turn, on its free steps or by
                paying length for up to 3 steps in all (the same zone card #39 uses)
  trap        = a tile with no ring 1, or with one ring-1 tile and no ring 2 (a dead end one step deep), or with
                every ring-1 tile inside the danger zone (a wall trap)
  tight       = not a trap, but ring 1 + ring 2 hold fewer than 4 tiles (a one-tile-wide corridor has 2)
  good step   = a tile she could step onto that is neither a trap nor in the danger zone
  trap choice = a decision where she could step onto a trap tile and also had a good step
  near enemy  = the closest enemy head in her view (the enemy queen included), by tile distance |dx| + |dy|
  room choice = a near-enemy decision where she had an open good step and also a step that is tight or a trap
  closed in   = her action ended nearer to that head than she started
  approach choice = a near-enemy decision where one good step led nearer and another good step did not
  screened    = a teammate's tile lies inside the box spanned by her ending tile and that head
  forced split = she split while she had no good step

The build's rule: a trap tile costs her a lot always; a tight tile costs her only while an enemy head is about.

PASS RULE (fixed before any switch-on game of this build was played; the constants are below):
  1. target seen: base shows at least TARGET_MIN tight-or-trap endings on room-choice decisions;
  2. cut: switch-on tight-or-trap endings per room-choice decision are at most CUT x base's;
  3. traps, judged only if base shows at least TARGET_MIN trap endings on trap-choice decisions: the switch-on
     rate per trap-choice decision is at most CUT x base's;
  4. approach, judged only if both sides show at least APPROACH_N approach choices: the switch-on share of them
     that closed in is not above base's;
  5. portals kept, judged only if base shows at least PORTAL_N queen portal moves on maps of 600 tiles or fewer:
     switch-on portal moves there are at least PORTAL_KEEP x base's.
Rules 3-5 report "not seen" below their minimum and do not fail the check then.
Wall deaths, forced splits (after a portal move or at a dead end), screened endings, lengths and wins by map size
are raw numbers and NOT part of the pass rule: 8 games per side per size cannot settle them, the outcome A/B does.
The bot's own log lines are not used: the game runner drops them.
Known before this build, from running this check on the base side of the second build's kept replays (trauma,
default, australia, weakhold; 16 games; the same bot source as this base; see the build's check-selftest folder):
base ended on a trap tile in only 2 of 61 trap-choice decisions, so rule 3 may well come out "not seen"; its
queen never took a portal there (none of those maps lets her), so this run adds the small "portals" map.
"""
import argparse, glob, hashlib, json, os, sys, concurrent.futures as cf
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before any switch-on game of this build)
TARGET_MIN = 5       # base endings needed to call the target seen (room choices), and to judge the trap rule
CUT = 0.5            # switch-on endings per choice decision: at most this fraction of base's
APPROACH_N = 20      # approach choices needed on each side to judge the approach rule
PORTAL_N = 4         # base queen portal moves on small maps needed to judge the portal rule
PORTAL_KEEP = 0.5    # switch-on small-map portal moves: at least this fraction of base's

VIEW = 3             # the bot sees a 7x7 box around its head
GHOST_ROUNDS = 3     # how long the bot remembers an enemy's size
FREE_DIV = 4         # free steps per turn = ceil(length / 4)
MIN_SIZE = 2
START_SIZE = 3
PAY_REACH = 3        # QS_PAY_REACH
MOBILITY = 4         # QC_MOBILITY: ring 1 + ring 2 below this is tight
NEAR = 6             # QC_NEAR: the furthest an enemy head in view can be
AFTER_PORTAL = 3     # rounds after a portal move in which a split or death is counted as "after a portal"
SMALL_CELLS = 600    # QUEEN_MIN_CELLS: base only has queen caution above this (or once home is closed off)
CAUSE = ['wall', 'self', 'body', 'headon', 'none']
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


def pay_reach(parts, shown, cut):
    """How far the bot expects this enemy to come this turn, paying included."""
    size = max(parts, shown + 1, START_SIZE) if cut else parts
    return max(free_steps(parts), min(free_steps(size) + max(0, size - MIN_SIZE), PAY_REACH))


def flood(step, start, reach, blocked):
    """Tiles a head on `start` can walk onto within `reach` steps."""
    seen = {start}
    frontier = [start]
    for _ in range(reach):
        nxt = []
        for cell in frontier:
            for d in DIRS:
                hop = step(cell, d)
                if hop is None or hop[0] in seen or hop[0] in blocked:
                    continue
                seen.add(hop[0])
                nxt.append(hop[0])
        frontier = nxt
    seen.discard(start)
    return seen


def rings(step, cell, blocked, free_at, turn, zone, leap):
    """Ring 1 and ring 2 sizes around `cell`, and how many ring-1 tiles lie outside the danger zone.
    `turn` = the step on which ring 1 is entered (own body tiles free by then count); `leap` = portals count."""
    first = []
    for d in DIRS:
        hop = step(cell, d)
        if hop is None or (hop[1] and not leap) or hop[0] in blocked or free_at.get(hop[0], 0) > turn:
            continue
        first.append(hop[0])
    second = set()
    for at in first:
        for d in DIRS:
            hop = step(at, d)
            if (hop is None or (hop[1] and not leap) or hop[0] == cell or hop[0] in blocked or
                    free_at.get(hop[0], 0) > turn + 1):
                continue
            second.add(hop[0])
    return len(first), len(second), sum(1 for t in first if t not in zone)


def kind_of(ring1, ring2, safe1):
    if ring1 == 0 or (ring1 == 1 and ring2 == 0) or safe1 == 0:
        return 'trap'
    return 'tight' if ring1 + ring2 < MOBILITY else 'open'


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
    memory = {}
    pending = None
    rnd = 0
    leap = W * H <= SMALL_CELLS      # the base bot lets the queen take portals only on these maps
    last_portal = -100
    tiles = set()

    def dist(a, b):
        return gap(a[0], b[0], W) + gap(a[1], b[1], H)

    def seen_from(head):
        """Other dragons' tiles in the 7x7 box around `head`, the teammates' ones separately."""
        others, mates = set(), set()
        for did, b in bodies.items():
            if did == queen or not b:
                continue
            inside = [t for t in b if gap(t[0], head[0], W) <= VIEW and gap(t[1], head[1], H) <= VIEW]
            others.update(inside)
            if team_of.get(did) == ours:
                mates.update(inside)
        return others, mates

    def look():
        body = bodies[queen]
        head = body[0]

        def in_view(cell):
            return gap(cell[0], head[0], W) <= VIEW and gap(cell[1], head[1], H) <= VIEW

        others, mates = seen_from(head)
        blocked = others | set(body)
        zone = set()
        heads = []
        for did, b in bodies.items():
            if did == queen or not b or team_of.get(did) == ours or not in_view(b[0]):
                continue
            heads.append(b[0])
            if did == foe_queen:
                continue
            inside = [t for t in b if in_view(t)]
            was = memory.get(did)
            parts = max(len(inside), was[1]) if was and rnd - was[0] <= GHOST_ROUNDS else len(inside)
            memory[did] = (rnd, parts)
            cut = any(gap(t[0], head[0], W) == VIEW or gap(t[1], head[1], H) == VIEW for t in inside)
            zone |= flood(step, b[0], pay_reach(parts, len(inside), cut), blocked - {body[-1]})
        free_at = {cell: len(body) - k + 1 for k, cell in enumerate(body)}
        steps, portals = {}, 0
        for d in DIRS:
            hop = step(head, d)
            if hop is None or hop[0] in blocked:
                continue
            if hop[1]:
                portals += 1
                continue
            steps[hop[0]] = kind_of(*rings(step, hop[0], others, free_at, 2, zone, leap))
        good = [t for t, k in steps.items() if k != 'trap' and t not in zone]
        foe = min(heads, key=lambda h: dist(head, h)) if heads else None
        near = dist(head, foe) if foe else None
        return dict(start=head, len=len(body), rnd=rnd, zone=zone, steps=steps, good=good, portal_open=portals,
                    trap_choice=bool(good) and 'trap' in steps.values(),
                    poor_choice=any(steps[t] == 'open' for t in good) and any(k != 'open' for k in steps.values()),
                    foe=foe, near=near,
                    approach_choice=bool(foe) and any(dist(t, foe) < near for t in good) and any(dist(t, foe) >= near for t in good),
                    kind='other', child=0, dead=False, cause=None, portal=False, hops=0)

    def close():
        nonlocal pending
        p, pending = pending, None
        if p is None:
            return
        body = bodies.get(queen)
        moved = p['kind'] == 'move'
        split = p['kind'] == 'split'
        forced = not p['good']
        track.update(f"{p['rnd']}{p['kind']}{body[0] if body else None}{p['child']}{p['dead']}".encode())
        c['decisions'] += 1
        c['moves'] += moved
        c['multi_moves'] += p['hops'] >= 2
        c['no_good_step'] += forced
        c['no_step_at_all'] += not p['steps']
        c['trap_choice'] += p['trap_choice']
        c['poor_choice'] += p['poor_choice']
        room_choice = p['poor_choice'] and p['foe'] is not None
        c['room_choice'] += room_choice
        c['near'] += p['foe'] is not None
        c['approach_choice'] += p['approach_choice']
        if split:
            after = rnd - last_portal <= AFTER_PORTAL
            c['splits'] += 1
            c['forced_splits'] += forced
            c['forced_splits_after_portal'] += forced and after
            c['forced_splits_at_dead_end'] += forced and not after and all(t not in p['zone'] for t in p['steps'])
            c['forced_splits_in_enemy_reach'] += forced and not after and any(t in p['zone'] for t in p['steps'])
            c['forced_splits_keeping_2'] += forced and p['child'] == p['len'] - MIN_SIZE and p['len'] > 2 * MIN_SIZE
            c['splits_after_portal'] += after
        if p['dead'] or not body:
            c['died_acting'] += 1
            c['trap_choice_died'] += p['trap_choice']
            return
        end = body[0]
        others, mates = seen_from(end)
        free_at = {cell: len(body) - k + 1 for k, cell in enumerate(body)}
        ring1, ring2, safe1 = rings(step, end, others, free_at, 1, p['zone'], leap)
        kind = kind_of(ring1, ring2, safe1)
        c['end_' + kind] += 1
        c['end_in_zone'] += end in p['zone']
        if moved:
            c['move_end_' + kind] += 1
            c['trap_choice_trap_end'] += p['trap_choice'] and kind == 'trap'
            c['poor_choice_poor_end'] += p['poor_choice'] and kind != 'open'
            c['room_choice_poor_end'] += room_choice and kind != 'open'
            if p['portal']:
                c['portal_end_' + kind] += 1
                c['portal_end_in_zone'] += end in p['zone']
        if p['foe'] is not None:
            now = dist(end, p['foe'])
            c['near_closed_in'] += now < p['near']
            c['near_moved_away'] += now > p['near']
            c['approach_choice_closed_in'] += p['approach_choice'] and now < p['near']
            c['near_screened'] += any(dist(end, m) > 0 and dist(m, p['foe']) > 0 and
                                      dist(end, m) + dist(m, p['foe']) == now for m in mates)
            c['near_with_mate_in_view'] += bool(mates)

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if kind == 'roundStart':
            close()
            rnd = pl.i32(0)
        elif kind == 'dragonAction':
            close()
            a = pl.pointer(0)
            if pl.i32(0) != queen or a is None or not bodies.get(queen):
                continue
            pending = look()
            what = a.u16(0)
            pending['kind'] = 'move' if what == 0 else 'split' if what == 1 else 'other'
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            h = replay.point(pl.pointer(0))
            tp = replay.point(pl.pointer(1))
            b = bodies.setdefault(did, deque())
            if not b or b[0] != h:
                if b:
                    ways = [step(b[0], d) for d in DIRS]
                    c['hops'] += 1
                    c['hop_mismatch'] += all((w or (None,))[0] != h for w in ways)
                    if did == queen:
                        tiles.add(h)
                        c['queen_hops'] += 1
                        if (h, True) in ways and (h, False) not in ways:
                            c['portal_moves'] += 1
                            last_portal = rnd
                            if pending:
                                pending['portal'] = True
                        if pending:
                            pending['hops'] += 1
                b.appendleft(h)
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
            bodies.pop(did, None)
            if did != queen:
                continue
            cause = CAUSE[r] if r < 5 else 'other'
            if pending:
                pending['dead'] = True
                pending['cause'] = cause
            c['queen_deaths'] += 1
            c[f'queen_deaths_{cause}'] += 1
            c['queen_death_round_sum'] += rnd
            c['queen_deaths_after_portal'] += rnd - last_portal <= AFTER_PORTAL
            c['queen_deaths_with_no_step'] += bool(pending) and not pending['steps']
    close()
    c['queen_alive_at_end'] = int(bool(bodies.get(queen)))
    c['queen_final_len'] = len(bodies.get(queen) or ())
    c['foe_queen_final_len'] = len(bodies.get(foe_queen) or ())
    c['queen_tiles'] = len(tiles)
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


def view(s):
    return {'games': s['games'], 'wins': s['win'],
            'queen_decisions': s['decisions'], 'queen_moves': s['moves'], 'queen_multi_step_moves': s['multi_moves'],
            'endings_by_room': {'open': s['end_open'], 'tight': s['end_tight'], 'trap': s['end_trap']},
            'room_choice_decisions': s['room_choice'], 'of_those_ending_tight_or_on_a_trap': s['room_choice_poor_end'],
            'tight_or_trap_endings_per_room_choice': round(share(s['room_choice_poor_end'], s['room_choice']), 4),
            'trap_choice_decisions': s['trap_choice'], 'of_those_ending_on_a_trap_tile': s['trap_choice_trap_end'],
            'of_those_dying_in_the_action': s['trap_choice_died'],
            'trap_endings_per_trap_choice': round(share(s['trap_choice_trap_end'], s['trap_choice']), 4),
            'open_or_not_choice_decisions': s['poor_choice'], 'of_those_ending_tight_or_trapped': s['poor_choice_poor_end'],
            'tight_or_trap_endings_per_such_choice': round(share(s['poor_choice_poor_end'], s['poor_choice']), 4),
            'decisions_with_no_good_step': s['no_good_step'], 'of_those_with_no_step_at_all': s['no_step_at_all'],
            'decisions_with_enemy_head_in_view': s['near'], 'of_those_closed_in': s['near_closed_in'],
            'of_those_moved_away': s['near_moved_away'],
            'approach_choice_decisions': s['approach_choice'], 'of_those_closed_in_by_choice': s['approach_choice_closed_in'],
            'closed_in_share_of_approach_choices': round(share(s['approach_choice_closed_in'], s['approach_choice']), 4),
            'endings_with_enemy_in_view_and_a_teammate_in_view': s['near_with_mate_in_view'],
            'endings_screened_by_a_teammate': s['near_screened'],
            'screened_share_of_enemy_in_view_endings': round(share(s['near_screened'], s['near'] - s['died_acting']), 4),
            'queen_portal_moves': s['portal_moves'],
            'portal_move_endings_by_room': {'open': s['portal_end_open'], 'tight': s['portal_end_tight'], 'trap': s['portal_end_trap']},
            'portal_move_endings_in_enemy_reach': s['portal_end_in_zone'],
            'queen_splits': s['splits'], 'forced_splits': s['forced_splits'],
            'forced_splits_by_place': {'within_3_rounds_of_a_portal_move': s['forced_splits_after_portal'],
                                       'walled_in_no_enemy_reach': s['forced_splits_at_dead_end'],
                                       'enemy_reach_on_a_step': s['forced_splits_in_enemy_reach']},
            'forced_splits_keeping_only_2': s['forced_splits_keeping_2'],
            'all_splits_within_3_rounds_of_a_portal_move': s['splits_after_portal'],
            'queen_deaths': s['queen_deaths'],
            'queen_deaths_by_cause': {k: s[f'queen_deaths_{k}'] for k in CAUSE if s[f'queen_deaths_{k}']},
            'queen_deaths_within_3_rounds_of_a_portal_move': s['queen_deaths_after_portal'],
            'queen_deaths_with_no_step_open': s['queen_deaths_with_no_step'],
            'queen_death_round_mean': round(share(s['queen_death_round_sum'], s['queen_deaths']), 1),
            'queen_alive_at_end': s['queen_alive_at_end'],
            'queen_final_length_per_game': round(share(s['queen_final_len'], s['games']), 2),
            'enemy_queen_final_length_per_game': round(share(s['foe_queen_final_len'], s['games']), 2),
            'different_tiles_per_100_queen_steps': round(100 * share(s['queen_tiles'], s['queen_hops']), 1)}


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
    hops = ball['hops'] + call['hops']
    if hops and ball['hop_mismatch'] + call['hop_mismatch'] > 0.005 * hops:
        sys.exit('head moves do not follow the rebuilt walls and portals; the measurement is not valid')
    same_track = sum(base[k][2] == cand[k][2] for k in keys)
    bv, cv = view(ball), view(call)

    def trap_rate(s):
        return share(s['trap_choice_trap_end'], s['trap_choice'])

    def approach_rate(s):
        return share(s['approach_choice_closed_in'], s['approach_choice'])

    def room_rate(s):
        return share(s['room_choice_poor_end'], s['room_choice'])

    target_seen = ball['room_choice_poor_end'] >= TARGET_MIN
    cut_ok = room_rate(call) <= CUT * room_rate(ball)
    trap_seen = ball['trap_choice_trap_end'] >= TARGET_MIN
    trap_ok = bool(trap_rate(call) <= CUT * trap_rate(ball)) if trap_seen else None
    approach_seen = min(ball['approach_choice'], call['approach_choice']) >= APPROACH_N
    approach_ok = bool(approach_rate(call) <= approach_rate(ball)) if approach_seen else None
    portal_seen = b['small']['portal_moves'] >= PORTAL_N
    portal_ok = bool(c['small']['portal_moves'] >= PORTAL_KEEP * b['small']['portal_moves']) if portal_seen else None
    passed = bool(target_seen and cut_ok and trap_ok is not False and approach_ok is not False and portal_ok is not False)
    why = []
    if not target_seen:
        why.append(f"base showed only {ball['room_choice_poor_end']} tight-or-trap endings where she had an open step with an "
                   f"enemy head in view (need {TARGET_MIN})")
    if not cut_ok:
        why.append('tight-or-trap endings per room-choice decision did not fall to half of base')
    if trap_ok is False:
        why.append('trap endings per trap-choice decision did not fall to half of base')
    if approach_ok is False:
        why.append('she closed in on the nearest enemy head more often than base when she had the choice')
    if portal_ok is False:
        why.append('she all but stopped taking portals on small maps')

    def seen_text(seen, need):
        return '' if seen else f' - NOT seen (needs {need})'

    def by_group(key):
        return ', '.join(f"{g} {b[g][key]} -> {c[g][key]}" for g in groups)

    def deaths(v):
        return f"{v['queen_deaths']} {v['queen_deaths_by_cause']}"

    def forced(v):
        f = v['forced_splits_by_place']
        return (f"{v['forced_splits']} (within 3 rounds of a portal move {f['within_3_rounds_of_a_portal_move']}, walled in "
                f"{f['walled_in_no_enemy_reach']}, enemy reach on a step {f['enemy_reach_on_a_step']})")

    note = (f"queen actions with an enemy head in view that end on a tight or trap tile (little room for the next two turns) "
            f"although she had an open step: base {ball['room_choice_poor_end']} of {ball['room_choice']} room-choice decisions "
            f"({room_rate(ball):.1%}) -> switch on {call['room_choice_poor_end']} of {call['room_choice']} ({room_rate(call):.1%}); "
            f"by map size (small = 600 tiles or fewer): "
            + ', '.join(f"{g} {b[g]['room_choice_poor_end']}/{b[g]['room_choice']} -> "
                        f"{c[g]['room_choice_poor_end']}/{c[g]['room_choice']} in {b[g]['games']} games" for g in groups)
            + f"; ending on a trap tile although she had a good step, enemy in view or not: base "
            f"{ball['trap_choice_trap_end']} of {ball['trap_choice']} trap-choice decisions ({trap_rate(ball):.1%}) -> switch on "
            f"{call['trap_choice_trap_end']} of {call['trap_choice']} ({trap_rate(call):.1%})" + seen_text(trap_seen, TARGET_MIN)
            + f"; tight or trap endings when an open step was there, no enemy needed (the build does not charge for tight tiles "
            f"then): {ball['poor_choice_poor_end']} of {ball['poor_choice']} -> "
            f"{call['poor_choice_poor_end']} of {call['poor_choice']}; all endings by room, base {bv['endings_by_room']} -> switch on "
            f"{cv['endings_by_room']}; closing in on the nearest enemy head in view when she had the choice: base "
            f"{ball['approach_choice_closed_in']} of {ball['approach_choice']} ({approach_rate(ball):.1%}) -> switch on "
            f"{call['approach_choice_closed_in']} of {call['approach_choice']} ({approach_rate(call):.1%})"
            + seen_text(approach_seen, APPROACH_N)
            + f"; endings with a teammate between her and that head: {bv['endings_screened_by_a_teammate']} of "
            f"{ball['near'] - ball['died_acting']} -> {cv['endings_screened_by_a_teammate']} of {call['near'] - call['died_acting']}"
            f"; queen portal moves {bv['queen_portal_moves']} -> {cv['queen_portal_moves']} ({by_group('portal_moves')})"
            + seen_text(portal_seen, PORTAL_N)
            + f", of those ending on a trap tile {ball['portal_end_trap']} -> {call['portal_end_trap']}, in enemy reach "
            f"{ball['portal_end_in_zone']} -> {call['portal_end_in_zone']}; not gated, {len(keys)} games each: forced splits base "
            f"{forced(bv)} -> switch on {forced(cv)}; queen deaths base {deaths(bv)} -> switch on {deaths(cv)}, wall deaths by map "
            f"size {by_group('queen_deaths_wall')}, deaths within 3 rounds of a portal move {ball['queen_deaths_after_portal']} -> "
            f"{call['queen_deaths_after_portal']}; queen alive at the end {bv['queen_alive_at_end']} -> {cv['queen_alive_at_end']}, "
            f"queen length at the end {bv['queen_final_length_per_game']} -> {cv['queen_final_length_per_game']} per game; wins "
            + ', '.join(f"{g} {b[g]['win']}/{b[g]['games']} -> {c[g]['win']}/{c[g]['games']}" for g in groups)
            + f"; different tiles per 100 queen steps {bv['different_tiles_per_100_queen_steps']} -> "
            f"{cv['different_tiles_per_100_queen_steps']}; pairs where the queen did exactly the same with the switch on and off "
            f"{same_track} of {len(keys)}" + ('' if passed else '. NOT shown: ' + '; '.join(why)))
    out = {'passed': passed, 'note': note, 'target_seen': bool(target_seen), 'trap_rule_seen': bool(trap_seen),
           'approach_rule_seen': bool(approach_seen), 'portal_rule_seen': bool(portal_seen),
           'pairs': len(keys), 'pairs_with_identical_queen_track': same_track, 'maps': sorted({k[0] for k in keys}),
           'pass_rule': {'target_min': TARGET_MIN, 'cut': CUT, 'approach_n': APPROACH_N, 'portal_n': PORTAL_N,
                         'portal_keep': PORTAL_KEEP, 'target_seen': bool(target_seen), 'cut_ok': bool(cut_ok),
                         'trap_rule_seen': bool(trap_seen), 'trap_rule_ok': trap_ok,
                         'approach_rule_seen': bool(approach_seen), 'approach_rule_ok': approach_ok,
                         'portal_rule_seen': bool(portal_seen), 'portal_rule_ok': portal_ok},
           'base': bv, 'candidate': cv,
           'by_map_size': {g: {'base': view(b[g]), 'candidate': view(c[g])} for g in groups},
           'model_check': {'head_hops': hops, 'hops_not_matching_walls_and_portals': ball['hop_mismatch'] + call['hop_mismatch']},
           'limits': ('measured from replays: the 7x7 view, kelp walls, portals and the danger zone are rebuilt, so a few tiles '
                      'can differ from what the bot marked (it counts edges it has never seen as open and only knows walls it '
                      'has seen; the checker uses the true walls, counts every paired portal on a small map as known to her, '
                      'and does not know when a closed-off home makes the bot ban portals on a small map); "trap" is the '
                      'checker\'s rebuild of the bot\'s two-turn room test, taken on the real position after her action; a '
                      'tight ending counts whenever an enemy head is in her view, while the bot also remembers a head for 3 '
                      'rounds; enemies out of sight are outside the danger zone; '
                      'the nearest enemy head is by tile distance, not walking distance; "forced" means no good step by this '
                      'rebuild, not that the bot had no other choice; why a step was chosen is not recorded, because the game '
                      'runner drops the bot\'s log lines; deaths, splits, lengths and wins are raw counts from a small sample, '
                      'not evidence of an outcome')}
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
        sys.exit(f'card 38 check failed: {exc}')
