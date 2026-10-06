#!/usr/bin/env python3
"""Card #38 queen-loop mechanism check (QUEEN_LOOP): does our queen circle a 2x2 square when no pearl is close, and
does she step off when an enemy head comes near?

usage: python3 work/card_38_check.py --replays DIR --base base --candidate candidate --output FILE
Replays are DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1), paired by (map, seed, side).

Everything is rebuilt from the replay alone; the game runner drops the bot's own log lines.

  decision   = one action of our queen (dragon 0 or 1 on our side). She acts once a round.
  lap step   = a one-tile move that brings her head back to where it was four actions ago, the four tiles in between
               forming a 2x2 square, each of those four actions a one-tile move. So the first three steps of a loop
               are not lap steps (they cannot be told from walking); every step after that is.
  loop       = a run of lap steps in a row, plus the three steps before it ("lead-in").
  loop share = lap steps before round UNTIL / her decisions before round UNTIL.
  steady loop = a loop of at least STEADY lap steps in a row (two more full laps after the first). The bot without
               the switch also walks a lap now and then, and circles inside a closed-off home; those are counted the
               same way on both sides.
  on the loop = a decision right after a lap step, before round UNTIL, 2-3 long, on a square more than HOME_CLEAR
               tiles from her spawn tile (only there can the new rule be the one moving her). Her square is the four
               tiles of that lap; "going on" = her next action is a one-tile move to the next tile of the square in
               the same direction.
  view       = the 7x7 box around her head. Only what is in it counts as seen.
  reach      = how far an enemy head can come in one turn: free steps (ceil(length / 4)) plus one step per length
               it can pay down to 2. Length = the most parts of it she saw in the last 3 rounds; a body that runs
               out of her view counts as one longer, and at least 3. A head not seen for 1-3 rounds keeps its last
               tile and gets 1 more reach per round unseen.
  margin     = walking distance from an enemy head to a tile (kelp walls and portals walked, other dragons' bodies
               in view block) minus that head's reach. "tight" = some tile of her square has margin below MARGIN.
  true tight = the same with the real length of every enemy head in view (the replay knows it, she does not).
  pushed off = on the loop, tight, and she did not go on. The heads that made it tight are remembered with the tile
               and round she last saw them.
  near a pusher = a lap step on a square with a tile within AWAY_TILES of such a head's last seen tile, less than
               AWAY_ROUNDS rounds after she last saw it.
  quiet      = a decision before round UNTIL with her 2-3 long, more than HOME_CLEAR tiles from her spawn tile, no
               enemy head seen in the last 3 rounds, and no pearl in view within PEARL_STEPS walking steps. This is
               the situation the card is about; it is counted the same way with the switch off and on.
  tiles per 100 = different tiles her head stood on before round UNTIL, per 100 decisions.

PASS RULE (fixed before any switch-on game was played; the constants are below):
  1. target seen: with the switch off she has at least QUIET_MIN quiet decisions;
  2. she loops: switch-on loop share is at least LOOP_SHARE_MIN, and at least LOOP_SHARE_GAIN above switch-off;
  3. she roams less: switch-on tiles per 100 is below switch-off;
  4. she steps off, judged only if it comes up: with at least TIGHT_N switch-on decisions on the loop that are
     tight, she goes on in at most TIGHT_STAY of them. When it is tight the new rule lets go and the normal move
     rules pick her step; they can pick the next tile of the square by themselves, so this is not expected to be
     zero. A loop that never let go would go on nearly every time;
  5. she stays away, judged only if it comes up: with at least PUSH_N switch-on push-offs, at most NEAR_MAX of them
     are followed by a lap step near that pusher (the normal move rules can walk a lap there by themselves);
  6. the square is where the card says, judged only with at least PLACE_N switch-on lap steps in steady loops: at
     most PLACE_BAD of them more than switch-off's own count are within HOME_CLEAR tiles of her spawn tile, the
     same for a portal on or beside the square, and the same for steps taken 4 or longer.
Rules 4-6 report "not seen" below their minimum and do not fail the check then.
Deaths, rams, lengths, pearls eaten and wins are raw numbers and NOT part of the pass rule: 16 games per side cannot
settle them, the outcome A/B does.
Known before any switch-on game, from running this check on the 20 switch-off identity games (old 10 maps, both
queens of each game, so 40 queen-games; output in the build's check-selftest folder): see the build's expectation.
"""
import argparse, glob, hashlib, json, os, sys, concurrent.futures as cf
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before any switch-on game)
QUIET_MIN = 100        # switch-off quiet decisions needed to call the target seen
LOOP_SHARE_MIN = 0.10  # switch-on lap steps per decision before round UNTIL (the card's "10%+")
LOOP_SHARE_GAIN = 0.08 # and at least this much above switch-off
TIGHT_N = 10           # switch-on tight decisions on the loop needed to judge stepping off
TIGHT_STAY = 0.70      # share of those where she may go on (the normal move rules pick the same tile now and then)
PUSH_N = 5             # switch-on push-offs needed to judge staying away
NEAR_MAX = 0.30        # share of push-offs that may be followed by a lap step near the pusher
PLACE_N = 20           # switch-on lap steps in steady loops needed to judge where the square is
PLACE_BAD = 0.02       # share of those, beyond switch-off's own count, that may break each placement rule
STEADY = 8             # lap steps in a row that make a steady loop

# The bot's constants (mybot2/main.cpp)
UNTIL = 300            # QL_UNTIL: no loop from this round on
MAX_LEN = 3            # QL_MAX_LENGTH
MARGIN = 2             # QL_MARGIN: she steps off below this
PEARL_STEPS = 4        # QL_PEARL_STEPS
HOME_CLEAR = 4         # QL_HOME_CLEAR
AWAY_TILES = 4         # QL_AWAY_TILES
AWAY_ROUNDS = 8        # QL_AWAY_ROUNDS
VIEW = 3               # the bot sees a 7x7 box around its head
GHOST_ROUNDS = 3       # how long the bot remembers an enemy head
FREE_DIV = 4           # free steps per turn = ceil(length / 4)
MIN_SIZE = 2           # a dragon cannot pay itself below this
START_SIZE = 3         # INITIAL_LENGTH: the least a half-hidden enemy is taken to be
CAUSE = ['wall', 'self', 'body', 'headon', 'none']
DIRS = 'NESW'
MARKS = (100, 200, 300)


def load_map(text):
    """Returns W, H, step(cell, d) -> (next cell, through a portal) or None for kelp / an unpaired portal, and
    gate(cell) -> True if one of the tile's four edges is a portal."""
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

    def edge(cell, d):
        x, y = cell
        if d == 'N':
            return ('N', x, y), (x, (y - 1) % H)
        if d == 'S':
            return ('N', x, (y + 1) % H), (x, (y + 1) % H)
        if d == 'W':
            return ('W', x, y), ((x - 1) % W, y)
        return ('W', (x + 1) % W, y), ((x + 1) % W, y)

    def step(cell, d):
        key, straight = edge(cell, d)
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

    def gate(cell):
        return any(kind.get(edge(cell, d)[0], 0) == 2 for d in DIRS)

    return W, H, step, gate


def gap(a, b, size):
    raw = abs(a - b)
    return min(raw, size - raw)


def full_reach(size):
    """Free plus paid steps of a dragon this long."""
    size = max(size, MIN_SIZE)
    return (size + FREE_DIV - 1) // FREE_DIV + size - MIN_SIZE


def margins(step, foes, key, blocked, own):
    """Lowest (walking distance - reach) per tile over `foes`, for tiles below MARGIN + 1; and which foe is lowest.
    Her own tiles are measured but not walked through, as in the bot."""
    low = {}
    for foe in foes:
        reach = foe[key]
        if reach is None:
            continue
        seen = {foe['at']}
        frontier = [foe['at']]
        for n in range(reach + MARGIN):
            nxt = []
            for cell in frontier:
                for d in DIRS:
                    hop = step(cell, d)
                    if hop is None:
                        continue
                    to = hop[0]
                    if to in seen or to in blocked:
                        continue
                    seen.add(to)
                    value = n + 1 - reach
                    if to not in low or value < low[to][0]:
                        low[to] = (value, foe['id'])
                    if to not in own:
                        nxt.append(to)
            frontier = nxt
    return low


def square_of(cells, W, H):
    """The four tiles as a 2x2 square, or None."""
    cells = set(cells)
    xs, ys = sorted({c[0] for c in cells}), sorted({c[1] for c in cells})
    if len(cells) != 4 or len(xs) != 2 or len(ys) != 2 or gap(xs[0], xs[1], W) != 1 or gap(ys[0], ys[1], H) != 1:
        return None
    return cells if cells == {(x, y) for x in xs for y in ys} else None


def one(job):
    path, side = job
    ours = 'A' if side == '0' else 'B'
    root = replay.load(path).root()
    text = root.text(0)
    W, H, step, gate = load_map(text)
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
    c = Counter(games=1, win=int(winner == ours))
    track = hashlib.sha1()
    if queen is None:
        raise ValueError(f'{path}: no queen on our side')
    spawn = bodies[queen][0]

    def far(a, b):
        return gap(a[0], b[0], W) + gap(a[1], b[1], H)

    pearls = set()
    memory = {}          # enemy id -> (round last seen, parts, tile)
    pushers = {}         # enemy id -> [tile, round last seen, True once a lap step came near]
    trail = [spawn]      # her head after each action
    single = []          # was that action a one-tile move
    lap = []             # was that action a lap step
    rounds = []          # round of each action
    stood = set()
    run = Counter()      # the loop she is on: lap steps, and how many of them break a placement rule
    pending = None
    mover = None
    rnd = 0
    alive = True

    def look():
        body = bodies[queen]
        head = body[0]

        def in_view(cell):
            return gap(cell[0], head[0], W) <= VIEW and gap(cell[1], head[1], H) <= VIEW

        def on_edge(cell):
            return gap(cell[0], head[0], W) == VIEW or gap(cell[1], head[1], H) == VIEW

        own = set(body)
        own.discard(body[-1])
        others, foes = set(), []
        for did, b in bodies.items():
            if did == queen or not b:
                continue
            inside = [cell for cell in b if in_view(cell)]
            others.update(inside)
            if team_of.get(did) == ours or not in_view(b[0]):
                continue
            was = memory.get(did)
            parts = max(len(inside), was[1]) if was and rnd - was[0] <= GHOST_ROUNDS else len(inside)
            memory[did] = (rnd, parts, b[0])
            cut = any(on_edge(cell) for cell in inside)
            size = max(parts, len(inside) + 1, START_SIZE) if cut else parts
            foes.append(dict(id=did, at=b[0], seen=rnd, reach=full_reach(size), true=full_reach(len(b))))
            if did in pushers:
                pushers[did][0], pushers[did][1] = b[0], rnd
        for did, (seen, parts, at) in memory.items():
            if seen != rnd and rnd - seen <= GHOST_ROUNDS:
                foes.append(dict(id=did, at=at, seen=seen, reach=full_reach(parts) + rnd - seen, true=None))
        for did in [d for d, p in pushers.items() if rnd - p[1] >= AWAY_ROUNDS]:
            del pushers[did]

        # A pearl in view within PEARL_STEPS walking steps, portals not taken.
        low = margins(step, foes, 'reach', others, own) if foes else {}
        pearl = safe_pearl = False
        seen = {head}
        frontier = [(head, True)]
        for n in range(PEARL_STEPS):
            nxt = []
            for cell, safe in frontier:
                for d in DIRS:
                    hop = step(cell, d)
                    if hop is None or hop[1]:
                        continue
                    to = hop[0]
                    if to in seen or to in others or to in own or not in_view(to):
                        continue
                    seen.add(to)
                    ok = safe and low.get(to, (MARGIN,))[0] >= MARGIN
                    if to in pearls:
                        pearl = True
                        safe_pearl = safe_pearl or ok
                    nxt.append((to, ok))
            frontier = nxt
        p = dict(rnd=rnd, start=head, end=head, len=len(body), n=0, seen=0, dead=False, cause=None,
                 foes=len(foes), pearl=pearl, safe_pearl=safe_pearl, on=False, other_lap=False,
                 quiet=(rnd < UNTIL and MIN_SIZE <= len(body) <= MAX_LEN and not foes and not pearl
                        and far(head, spawn) > HOME_CLEAR))
        if lap and lap[-1]:
            cells = trail[-4:]
            p['other_lap'] = not (rnd < UNTIL and len(body) <= MAX_LEN and all(far(t, spawn) > HOME_CLEAR for t in cells))
        if lap and lap[-1] and not p['other_lap']:
            p['on'] = True
            p['square'] = cells
            p['expect'] = cells[0]
            p['blocked'] = cells[0] in others
            tight = [low[t] for t in cells if t in low and low[t][0] < MARGIN]
            p['tight'] = bool(tight)
            p['pushed_by'] = {foe['id']: (foe['at'], foe['seen']) for foe in foes if any(t[1] == foe['id'] for t in tight)}
            real = margins(step, foes, 'true', others, own) if foes else {}
            p['true_tight'] = any(t in real and real[t][0] < MARGIN for t in cells)
        return p

    def flush():
        if run['n'] >= STEADY:
            c['steady_loops'] += 1
            for name, value in run.items():
                c['steady_' + name] += value
        run.clear()

    def close():
        nonlocal pending
        p, pending = pending, None
        if p is None:
            return
        moved = p['kind'] == 'move' and not p['dead']
        one_step = moved and p['n'] == 1 and p['seen'] == 1
        trail.append(p['end'])
        single.append(one_step)
        rounds.append(p['rnd'])
        k = len(single) - 1
        cells = trail[-4:]
        is_lap = (k >= 3 and all(single[-4:]) and trail[-5] == trail[-1] and square_of(cells, W, H) is not None)
        lap.append(is_lap)
        track.update(f"{p['rnd']}{p['kind']}{p['end']}{p['dead']}".encode())
        early = p['rnd'] < UNTIL
        c['decisions'] += 1
        c['decisions_early'] += early
        c['short_early'] += early and p['len'] <= MAX_LEN
        c['quiet'] += p['quiet']
        c['foe_seen_early'] += early and p['foes'] > 0
        c['pearl_near_early'] += early and p['pearl']
        c['moves'] += p['kind'] == 'move'
        c['path_mismatch'] += p['kind'] == 'move' and not p['dead'] and p['seen'] != p['n']
        if early and not p['dead']:
            stood.add(p['end'])
        if not is_lap:
            flush()
        else:
            beside = set(cells)
            for x, y in cells:
                beside.update(((x, (y - 1) % H), (x, (y + 1) % H), ((x - 1) % W, y), ((x + 1) % W, y)))
            flags = dict(n=1, home=any(far(t, spawn) <= HOME_CLEAR for t in cells), portal=any(gate(t) for t in beside),
                         long=p['len'] > MAX_LEN)
            for name, value in flags.items():
                run[name] += value
            c['lap_steps'] += 1
            c['lap_steps_early' if early else 'lap_steps_late'] += 1
            c['lap_quiet'] += p['quiet']
            c['lap_long'] += flags['long']
            c['lap_home'] += flags['home']
            c['lap_portal'] += flags['portal']
            c['lap_pearl'] += any(t in pearls for t in beside)
            for did, rec in pushers.items():
                if not rec[2] and any(far(t, rec[0]) <= AWAY_TILES for t in cells):
                    rec[2] = True
                    c['push_then_near'] += 1
            if not (k >= 1 and lap[-2]):
                c['loops'] += 1
                c['lead_in_steps_early'] += sum(r < UNTIL for r in rounds[-4:-1])
        c['other_lap_decisions'] += p['other_lap']
        if p['on']:
            went_on = one_step and p['end'] == p['expect']
            c['on_loop'] += 1
            c['on_loop_went_on'] += went_on
            c['on_loop_tight'] += p['tight']
            c['on_loop_tight_went_on'] += p['tight'] and went_on
            c['on_loop_true_tight'] += p['true_tight']
            c['on_loop_true_tight_went_on'] += p['true_tight'] and went_on
            c['on_loop_true_tight_unseen'] += p['true_tight'] and not p['tight']
            if not went_on:
                why = ('tight' if p['tight'] else 'late' if p['rnd'] >= UNTIL else 'pearl' if p['safe_pearl']
                       else 'long' if p['len'] > MAX_LEN else 'blocked' if p['blocked'] else 'foe_seen' if p['foes'] else 'other')
                c['left_' + why] += 1
                c['left_died'] += p['dead']
                if p['tight']:
                    c['push_offs'] += 1
                    for did, (at, seen) in p['pushed_by'].items():
                        pushers[did] = [at, seen, False]

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if kind == 'roundStart':
            close()
            mover = None
            rnd = pl.i32(0)
            for mark in MARKS:
                if rnd == mark and alive and bodies.get(queen):
                    c[f'alive_r{mark}'] += 1
                    c[f'len_sum_r{mark}'] += len(bodies[queen])
        elif kind == 'tileChange':
            at = replay.point(pl.pointer(0))
            if pl.u32(0) == 1:
                pearls.add(at)
            else:
                pearls.discard(at)
        elif kind == 'dragonAction':
            close()
            mover = pl.i32(0)
            a = pl.pointer(0)
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
            before = len(b)
            hopped = bool(b) and b[0] != h
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
            # A step that leaves the dragon one longer ate a pearl.
            if hopped and len(b) > before and team_of.get(did) == ours:
                c['team_eats_r50'] += rnd <= 50
                c['team_eats_r100'] += rnd <= 100
                c['queen_eats_early'] += did == queen and rnd < UNTIL
        elif kind == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x) for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
            c['queen_splits_early'] += pa == queen and rnd < UNTIL
        elif kind == 'dragonDeath':
            did = pl.i32(0)
            r = pl.u16(4)
            bodies.pop(did, None)
            if did != queen:
                continue
            cause = CAUSE[r] if r < 5 else 'other'
            alive = False
            if pending:
                pending['dead'] = True
                pending['cause'] = cause
            on_loop = bool(lap and lap[-1]) and not pending
            c['queen_deaths'] += 1
            c['queen_deaths_early'] += rnd < UNTIL
            c[f'queen_deaths_{cause}'] += 1
            c['queen_death_round_sum'] += rnd
            if cause == 'headon' and mover != queen:
                c['queen_rammed'] += 1
                c['queen_rammed_on_loop'] += on_loop
            elif cause == 'headon':
                c['queen_own_ram'] += 1
            c['queen_died_on_loop'] += on_loop
    close()
    flush()
    c['tiles_stood_early'] = len(stood)
    c['queen_alive_end'] = int(alive)
    c['queen_final_len'] = len(bodies.get(queen) or ()) if alive else 0
    return 'small' if W * H <= 600 else 'big', dict(c), track.hexdigest()


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


def pct(a, b):
    return round(100 * share(a, b), 1)


def view(s):
    g = max(1, s['games'])
    left = {k: s['left_' + k] for k in ('tight', 'pearl', 'blocked', 'long', 'late', 'foe_seen', 'other') if s['left_' + k]}
    return {'games': s['games'], 'wins': s['win'],
            'queen_decisions': s['decisions'], 'queen_decisions_before_r300': s['decisions_early'],
            'of_those_2_or_3_long': s['short_early'], 'share_2_or_3_long_pct': pct(s['short_early'], s['decisions_early']),
            'quiet_decisions': s['quiet'], 'quiet_share_pct': pct(s['quiet'], s['decisions_early']),
            'decisions_with_an_enemy_head_seen_before_r300': s['foe_seen_early'],
            'decisions_with_a_pearl_within_4_steps_before_r300': s['pearl_near_early'],
            'lap_steps_before_r300': s['lap_steps_early'], 'lap_steps_from_r300': s['lap_steps_late'],
            'loop_share_pct': pct(s['lap_steps_early'], s['decisions_early']),
            'loops': s['loops'], 'lap_steps_per_loop': round(share(s['lap_steps'], s['loops']), 1),
            'loop_share_with_lead_in_pct': pct(s['lap_steps_early'] + s['lead_in_steps_early'], s['decisions_early']),
            'lap_steps_on_quiet_decisions': s['lap_quiet'], 'loop_share_of_quiet_pct': pct(s['lap_quiet'], s['quiet']),
            'tiles_stood_on_before_r300': s['tiles_stood_early'],
            'tiles_per_100_decisions': round(100 * share(s['tiles_stood_early'], s['decisions_early']), 1),
            'steady_loops': s['steady_loops'], 'lap_steps_in_steady_loops': s['steady_n'],
            'steady_lap_steps_within_4_of_spawn': s['steady_home'],
            'steady_lap_steps_with_a_portal_on_or_beside': s['steady_portal'],
            'steady_lap_steps_4_or_longer': s['steady_long'],
            'decisions_after_a_lap_step_where_the_rule_cannot_apply': s['other_lap_decisions'],
            'on_the_loop_decisions': s['on_loop'], 'of_those_going_on': s['on_loop_went_on'],
            'on_the_loop_tight': s['on_loop_tight'], 'tight_and_went_on': s['on_loop_tight_went_on'],
            'on_the_loop_true_tight': s['on_loop_true_tight'], 'true_tight_and_went_on': s['on_loop_true_tight_went_on'],
            'true_tight_she_could_not_tell': s['on_loop_true_tight_unseen'],
            'left_the_loop_because': left, 'died_on_the_action_that_left_the_loop': s['left_died'],
            'push_offs': s['push_offs'], 'push_offs_followed_by_a_lap_step_near_the_pusher': s['push_then_near'],
            'lap_steps_within_4_of_spawn': s['lap_home'], 'lap_steps_with_a_portal_on_or_beside': s['lap_portal'],
            'lap_steps_with_a_pearl_on_or_beside': s['lap_pearl'], 'lap_steps_4_or_longer': s['lap_long'],
            'queen_deaths': s['queen_deaths'], 'queen_deaths_before_r300': s['queen_deaths_early'],
            'queen_alive_at_end': s['queen_alive_end'],
            'queen_deaths_by_cause': {k: s[f'queen_deaths_{k}'] for k in CAUSE + ['other'] if s[f'queen_deaths_{k}']},
            'queen_rammed_by_an_enemy_head': s['queen_rammed'], 'of_those_right_after_a_lap_step': s['queen_rammed_on_loop'],
            'queen_died_right_after_a_lap_step': s['queen_died_on_loop'], 'queen_rammed_a_head_herself': s['queen_own_ram'],
            'queen_death_round_mean': round(share(s['queen_death_round_sum'], s['queen_deaths']), 1),
            'queen_alive_and_mean_length_at': {f'r{m}': [s[f'alive_r{m}'], round(share(s[f'len_sum_r{m}'], s[f'alive_r{m}']), 2)]
                                               for m in MARKS},
            'queen_final_length_per_game': round(s['queen_final_len'] / g, 2),
            'queen_pearls_eaten_before_r300': s['queen_eats_early'], 'queen_splits_before_r300': s['queen_splits_early'],
            'team_pearls_eaten_by_r50_per_game': round(s['team_eats_r50'] / g, 1),
            'team_pearls_eaten_by_r100_per_game': round(s['team_eats_r100'] / g, 1)}


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
    moves = ball['moves'] + call['moves']
    hops = ball['hops'] + call['hops']
    if moves and ball['path_mismatch'] + call['path_mismatch'] > 0.02 * moves:
        sys.exit('replay moves do not line up with head updates; the measurement is not valid')
    if hops and ball['hop_mismatch'] + call['hop_mismatch'] > 0.005 * hops:
        sys.exit('head moves do not follow the rebuilt walls and portals; the measurement is not valid')
    bv, cv = view(ball), view(call)

    def loop_share(s):
        return share(s['lap_steps_early'], s['decisions_early'])

    def tiles(s):
        return share(s['tiles_stood_early'], s['decisions_early'])

    target_seen = ball['quiet'] >= QUIET_MIN
    loops_ok = loop_share(call) >= LOOP_SHARE_MIN and loop_share(call) - loop_share(ball) >= LOOP_SHARE_GAIN
    roam_ok = tiles(call) < tiles(ball)
    tight_seen = call['on_loop_tight'] >= TIGHT_N
    tight_ok = bool(share(call['on_loop_tight_went_on'], call['on_loop_tight']) <= TIGHT_STAY) if tight_seen else None
    push_seen = call['push_offs'] >= PUSH_N
    push_ok = bool(share(call['push_then_near'], call['push_offs']) <= NEAR_MAX) if push_seen else None
    place_seen = call['steady_n'] >= PLACE_N
    place_keys = ('steady_home', 'steady_portal', 'steady_long')
    place_ok = bool(all(call[k] - ball[k] <= PLACE_BAD * call['steady_n'] for k in place_keys)) if place_seen else None
    passed = bool(target_seen and loops_ok and roam_ok and tight_ok is not False and push_ok is not False
                  and place_ok is not False)
    why = []
    if not target_seen:
        why.append(f"target not seen: switch-off shows {ball['quiet']} quiet decisions, needs {QUIET_MIN}")
    if not loops_ok:
        why.append(f"loop share {cv['loop_share_pct']}% with the switch on (switch off {bv['loop_share_pct']}%), needs "
                   f"{round(100 * LOOP_SHARE_MIN)}% and {round(100 * LOOP_SHARE_GAIN)} points above switch-off")
    if not roam_ok:
        why.append(f"tiles per 100 decisions did not go down ({bv['tiles_per_100_decisions']} -> {cv['tiles_per_100_decisions']})")
    if tight_ok is False:
        why.append(f"she went on in {call['on_loop_tight_went_on']} of {call['on_loop_tight']} tight decisions on the loop")
    if push_ok is False:
        why.append(f"{call['push_then_near']} of {call['push_offs']} push-offs were followed by a lap step near the pusher")
    if place_ok is False:
        why.append(f"square placement in steady loops: near spawn {ball['steady_home']} -> {call['steady_home']}, by a portal "
                   f"{ball['steady_portal']} -> {call['steady_portal']}, taken 4+ long {ball['steady_long']} -> "
                   f"{call['steady_long']}, of {call['steady_n']} switch-on steady lap steps")

    def seen_text(seen, need):
        return '' if seen else f' (not seen: fewer than {need}, not judged)'

    note = (f"QUEEN_LOOP {'shown' if passed else 'NOT shown'} on {len(keys)} paired games. "
            f"Loop share (lap steps per queen decision before r{UNTIL}): switch off {bv['loop_share_pct']}% "
            f"({ball['lap_steps_early']} of {ball['decisions_early']}) -> switch on {cv['loop_share_pct']}% "
            f"({call['lap_steps_early']} of {call['decisions_early']}); with the three lead-in steps of each loop "
            f"{bv['loop_share_with_lead_in_pct']}% -> {cv['loop_share_with_lead_in_pct']}%; loops {ball['loops']} -> {call['loops']}, "
            f"lap steps per loop {bv['lap_steps_per_loop']} -> {cv['lap_steps_per_loop']}. "
            f"Quiet decisions (2-3 long, away from spawn, no enemy head seen, no pearl within {PEARL_STEPS} steps): "
            f"{ball['quiet']} -> {call['quiet']}, of those lap steps {ball['lap_quiet']} -> {call['lap_quiet']}"
            + seen_text(target_seen, QUIET_MIN)
            + f". Share of her decisions before r{UNTIL} at length 2-3: {bv['share_2_or_3_long_pct']}% -> "
            f"{cv['share_2_or_3_long_pct']}%. Tiles her head stood on per 100 decisions: {bv['tiles_per_100_decisions']} -> "
            f"{cv['tiles_per_100_decisions']}. Stepping off: on the loop with a seen head inside reach + {MARGIN - 1} of the square, "
            f"switch off {ball['on_loop_tight']} decisions, went on in {ball['on_loop_tight_went_on']} -> "
            f"switch on {call['on_loop_tight']} decisions, went on in {call['on_loop_tight_went_on']}"
            + seen_text(tight_seen, TIGHT_N)
            + f"; by the enemy's real length {call['on_loop_true_tight']} decisions, went on in "
            f"{call['on_loop_true_tight_went_on']} (she could not tell in {call['on_loop_true_tight_unseen']}). Why she left the loop, "
            f"switch on: {cv['left_the_loop_because']}. Push-offs {ball['push_offs']} -> {call['push_offs']}, followed by a lap "
            f"step near the pusher {ball['push_then_near']} -> {call['push_then_near']}" + seen_text(push_seen, PUSH_N)
            + f". Square placement, lap steps in steady loops ({STEADY}+ lap steps in a row) {ball['steady_n']} -> "
            f"{call['steady_n']}: within {HOME_CLEAR} of spawn {ball['steady_home']} -> {call['steady_home']}, portal on or beside "
            f"{ball['steady_portal']} -> {call['steady_portal']}, taken 4+ long {ball['steady_long']} -> {call['steady_long']}"
            + seen_text(place_seen, PLACE_N)
            + f"; all lap steps {ball['lap_steps']} -> {call['lap_steps']}: within {HOME_CLEAR} of spawn {ball['lap_home']} -> "
            f"{call['lap_home']}, pearl on or beside {ball['lap_pearl']} -> {call['lap_pearl']} (not gated)"
            + f". Not gated, {len(keys)} games each: queen deaths {bv['queen_deaths']} -> {cv['queen_deaths']}, rammed by an enemy head "
            f"{bv['queen_rammed_by_an_enemy_head']} -> {cv['queen_rammed_by_an_enemy_head']} (right after a lap step "
            f"{bv['of_those_right_after_a_lap_step']} -> {cv['of_those_right_after_a_lap_step']}), alive at the end "
            f"{bv['queen_alive_at_end']} -> {cv['queen_alive_at_end']}, mean death round {bv['queen_death_round_mean']} -> "
            f"{cv['queen_death_round_mean']}, queen pearls eaten before r{UNTIL} {bv['queen_pearls_eaten_before_r300']} -> "
            f"{cv['queen_pearls_eaten_before_r300']}, team pearls by r100 per game {bv['team_pearls_eaten_by_r100_per_game']} -> "
            f"{cv['team_pearls_eaten_by_r100_per_game']}, wins {bv['wins']} -> {cv['wins']}, pairs where the queen did exactly the "
            f"same with the switch on and off {same_track} of {len(keys)}"
            + ('' if passed else '. NOT shown: ' + '; '.join(why)))
    out = {'passed': passed, 'note': note, 'target_seen': bool(target_seen),
           'pairs': len(keys), 'pairs_with_identical_queen_track': same_track, 'maps': sorted({k[0] for k in keys}),
           'pass_rule': {'quiet_min': QUIET_MIN, 'loop_share_min': LOOP_SHARE_MIN, 'loop_share_gain': LOOP_SHARE_GAIN,
                         'tight_n': TIGHT_N, 'tight_stay': TIGHT_STAY, 'push_n': PUSH_N, 'near_max': NEAR_MAX,
                         'place_n': PLACE_N, 'place_bad': PLACE_BAD, 'steady': STEADY,
                         'target_seen': bool(target_seen), 'loops_ok': bool(loops_ok), 'roams_less_ok': bool(roam_ok),
                         'step_off_rule_seen': bool(tight_seen), 'step_off_rule_ok': tight_ok,
                         'stay_away_rule_seen': bool(push_seen), 'stay_away_rule_ok': push_ok,
                         'placement_rule_seen': bool(place_seen), 'placement_rule_ok': place_ok},
           'base': bv, 'candidate': cv,
           'by_map_group': {g: {'base': view(b[g]), 'candidate': view(c[g])} for g in groups},
           'by_map': {m: {'base': view(total(base[k][1] for k in keys if k[0] == m)),
                          'candidate': view(total(cand[k][1] for k in keys if k[0] == m))} for m in sorted({k[0] for k in keys})},
           'model_check': {'queen_moves': moves, 'moves_not_matching_head_updates': ball['path_mismatch'] + call['path_mismatch'],
                           'head_hops': hops, 'hops_not_matching_walls_and_portals': ball['hop_mismatch'] + call['hop_mismatch']},
           'limits': ('measured from replays: the 7x7 view, kelp walls, portals and the remembered enemy size are rebuilt, so a '
                      'few tiles can differ from what the bot marked (it only walks portals it has already seen both ends of); '
                      'a lap step needs a full lap, so the first three steps of every loop are not counted in the loop share '
                      '(the lead-in line adds them back); "tight" is her view of the danger, not the truth: enemies out of '
                      'sight and enemies longer than they look are outside it, and the "real length" counts show how often '
                      'that mattered for heads in view; why she left a loop is a rebuild in a fixed order (tight, round 300, '
                      'pearl, length, next tile taken, a head seen, other), not the bot\'s own reason; the square-quality '
                      'rules (open sides, exits, not a pocket) are not rebuilt; deaths, lengths, pearls and wins are raw '
                      'counts from a small sample against the release bot, which does not hunt queens, so they are not '
                      'evidence of an outcome')}
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
