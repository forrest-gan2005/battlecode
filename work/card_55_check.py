#!/usr/bin/env python3
"""Card #55 queen-fallback mechanism check (QUEEN_FALLBACK): when our queen is outnumbered in her own view, does she
keep away from the enemy heads and close on her fall-back target?

usage: python3 work/card_55_check.py --replays DIR --base base --candidate candidate --output FILE
Reads paired replays DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1; side 0 = we are team A).

Words (all rebuilt from the replay, no map names):
  queen          our dragon with id 0 or 1. Her length decides the game; a dead queen scores 0.
  view           the 7x7 square of tiles around her head (the map wraps round), at the start of her turn.
  outnumbered    enemy heads in view >= our heads in view, herself counted. A draw counts (Zhe's answer), so alone
                 with one enemy head in view is outnumbered. Only heads in view this turn count.
  home           the tile her head stood on at the start of the game.
  company spot   where she last stood with a teammate's head in view and more of ours than theirs, kept 40 rounds.
  target         home or the company spot, whichever is nearer on foot (real walls, no portals, bodies ignored).
  ends farther   of her outnumbered turns that she survives: the straight-line distance (wrap-around, as the bot
                 measures it) from her head to the nearest enemy head that was in view is larger after her turn
                 than before it. Enemy heads are taken where they stood when her turn began. "Ends nearer" is the
                 same test the other way.
  pull is open   a step toward the target was free at the start of her turn and did not bring her nearer to any
                 enemy head in view. Those are the turns the built rule pulls her to the target; on the others the
                 pull is dropped by design and only keep-away applies.

Expectation, written before any switch-on game was played (thresholds are the constants below):
  1. target seen: base has at least MIN_OUT_TURNS outnumbered queen turns, in at least MIN_GAME_SHARE of the games,
     and the candidate has at least MIN_OPEN_TURNS outnumbered turns where the pull is open.
  2. nothing else changes: every pair plays the same game up to the round of the candidate's first outnumbered
     queen turn (the card: when she is not outnumbered she moves as with the switch off).
  3. keeps away: of her outnumbered turns, the share that ends farther from the nearest enemy head is at least
     AWAY_GAIN higher in the candidate than in base.
  4. falls back: of her outnumbered turns where the pull is open, at least PULL_SHARE end nearer the target on foot
     in the candidate, and the turns that do not ("misses") are a share at least MISS_CUT smaller than base's.
passed = all four.
One gate was changed after the first draft, also before any switch-on game: gate 4 first read "that share is at
least 0.15 higher than in base". The toggle-off identity replays (old 10 maps, both builds play the same game) showed
base already ends nearer the target on 72% of its pull-open turns, which put that gate at 87%, close to the ceiling,
so it became the miss rule. Gates 1 to 3 are as first written.
Reported, not part of the verdict: the card's own wording of the signal (share of ALL outnumbered turns that end
nearer the target / nearer home, "most" = above one half, base expected at or below one half), the first outnumbered
turn of each pair (the same position in both games: did the two builds move differently), how much of the game she
is outnumbered, how often the rule switches off and on again within a few turns, and the card's "what would show it
is wrong" numbers: queen alive at round 100 and 150, how she died and whether she was outnumbered in view on her last
turns before dying, her length and pearls, the team's pearls by round 100, time spent near home, wins, timeouts, CPU.
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before any switch-on game was played)
MIN_OUT_TURNS = 40     # outnumbered queen turns base must show over the whole run
MIN_GAME_SHARE = 0.5   # share of base games with at least one outnumbered queen turn
MIN_OPEN_TURNS = 20    # candidate turns with the pull open needed to judge the fall-back
AWAY_GAIN = 0.10       # candidate's ends-farther share minus base's
PULL_SHARE = 0.50      # candidate's ends-nearer-the-target share on turns where the pull is open
MISS_CUT = 1 / 3       # pull-open turns that do not end nearer the target: candidate's share <= (1 - this) x base's

# The bot's settings this check mirrors (mybot2/main.cpp).
VIEW = 3               # VISION_RADIUS
MEMORY = 40            # QF_MEMORY
GUARD_RADIUS = 5       # QF_GUARD_RADIUS, reported only

LAST_TURNS = 3         # "outnumbered before she died" looks at her last this-many turns
FLIP_GAP = 3           # the rule coming back on within this many of her turns counts as off-and-on
HOME_NEAR = 6          # "near home" = this many steps on foot or fewer
HOME_FROM = 60         # time near home is counted from this round
REASONS = ['wall', 'self', 'body', 'head-on', 'no action']
BUILT_AS = (
    "How the card was built (switch QUEEN_FALLBACK, off by default). Each turn the queen counts heads in her 7x7 "
    "view, herself included; enemy heads >= our heads is outnumbered (a draw counts, Zhe's answer 1; only heads in "
    "view this turn). The rule is on exactly on those turns and off the moment we are strictly more (answer 4). "
    "While on: (a) keep-away, the existing switched-off queen guard turned on for her: a step that ends 5 tiles or "
    "fewer from an enemy head (in view, or seen in the last 3 rounds) is charged 1500 points per tile inside that "
    "range, plus her dead-end charge on every map size; (b) a pull of 300 points per tile on foot toward her "
    "target, less than one tile of keep-away and less than her head-on, enemy-reach and dead-end charges (answer "
    "2: closer to the target only when equally safe); the target is her start tile or the company "
    "spot, whichever is nearer on foot (answer 3); the pull is dropped for the turn when every free step toward "
    "the target brings her nearer to an enemy head in view; (c) the opening centre pull and card 51's pull to "
    "unseen tiles are off for her, and so is the barren-area route. It applies on every map size, all game. "
    "Builder's reading, say if wrong: a company spot needs a teammate's head in view (alone with no enemy she is "
    "1 against 0 on every tile, which would put the target one step behind her and never at home); her existing "
    "rule for going at the enemy queen when the normal dragon rules say so runs before step scoring and is not "
    "changed; teammates do nothing new.")


def gap(a, b, size):
    raw = abs(a - b)
    return min(raw, size - raw)


class Board:
    """Walls and start dragons of the map text inside a replay."""

    def __init__(self, text):
        W = H = 0
        E = {}
        self.bodies, self.team_of = {}, {}
        for line in text.splitlines():
            q = line.split()
            if not q:
                continue
            if q[0] == 'MAP':
                W, H = int(q[1]), int(q[2])
            elif q[0] == 'EDGE':
                E[int(q[1])] = max(E.get(int(q[1]), 0), int(q[2]))
            elif q[0] == 'DRAGON':
                did = len(self.bodies)
                self.bodies[did] = [int(q[4 + 2 * k]) * W + int(q[3 + 2 * k]) for k in range(int(q[2]))]
                self.team_of[did] = 'A' if int(q[1]) == 0 else 'B'
        if not W or not H:
            raise ValueError('replay carries no map size')
        self.W, self.H = W, H
        # Side ids run in rows of W + 1: a row of north sides, then a row of west sides. Generated maps also carry
        # the wrap-around copies (bottom row, right column); official maps leave those ids out.
        R = W + 1

        def kind(ids):
            return max(E.get(i, 0) for i in ids)

        def north(x, y):
            return kind([2 * y * R + x] + ([2 * H * R + x] if y == 0 else []))

        def west(x, y):
            return kind([(2 * y + 1) * R + x] + ([(2 * y + 1) * R + W] if x == 0 else []))

        # Per tile, in N E S W order: neighbour and side kind (0 open, 1 kelp, 2 portal).
        self.nb, self.side = [], []
        for y in range(H):
            for x in range(W):
                self.nb.append((((y - 1) % H) * W + x, y * W + (x + 1) % W, ((y + 1) % H) * W + x, y * W + (x - 1) % W))
                self.side.append((north(x, y), west((x + 1) % W, y), north(x, (y + 1) % H), west(x, y)))
        self._walks = {}

    def far(self, a, b):
        """Straight-line distance with wrap-around, as the bot's keep-away measures it."""
        W = self.W
        return gap(a % W, b % W, W) + gap(a // W, b // W, self.H)

    def in_view(self, head, cell):
        W = self.W
        return gap(cell % W, head % W, W) <= VIEW and gap(cell // W, head // W, self.H) <= VIEW

    def walk(self, start):
        """Steps on foot from every tile to `start`: open sides only, bodies ignored, -1 = no way."""
        dist = self._walks.get(start)
        if dist is None:
            dist = [-1] * (self.W * self.H)
            dist[start] = 0
            queue = deque([start])
            while queue:
                c = queue.popleft()
                for d in range(4):
                    n = self.nb[c][d]
                    if self.side[c][d] == 0 and dist[n] < 0:
                        dist[n] = dist[c] + 1
                        queue.append(n)
            self._walks[start] = dist
        return dist


def scan(path, ours):
    """One pass over a replay for our side."""
    root = replay.load(path).root()
    board = Board(root.text(0))
    W = board.W
    result = root.pointer(4)
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None
    bodies = {i: deque(b) for i, b in board.bodies.items()}
    team_of = dict(board.team_of)
    queen = next((i for i in (0, 1) if team_of.get(i) == ours), None)
    if queen is None:
        raise ValueError(f'{path}: no queen for team {ours}')
    home = bodies[queen][0]
    to_home = board.walk(home)

    stat = {k: 0 for k in (
        'q_turns', 'out_turns', 'out_alone', 'out_done', 'out_moved', 'away', 'closer', 'closes_any', 'inside_guard_end',
        'tgt_turns', 'tgt_nearer', 'tgt_farther', 'tgt_is_spot', 'home_turns', 'home_nearer',
        'open_turns', 'open_nearer', 'open_farther', 'died_on_out_turn', 'episodes', 'restarts',
        'late_turns', 'late_near_home', 'pearls_100', 'q_pearls_100', 'q_pearls', 'tle', 'points_max')}
    spot = spot_round = None
    pend = None            # her outnumbered turn in progress
    first = None           # her first outnumbered turn of the game
    first_out = None
    recent = deque(maxlen=LAST_TURNS)   # outnumbered or not, her last turns
    was_out = False
    since_off = None       # her turns since the rule last went off
    q_death = q_reason = None
    out_before_death = None
    q_len = {100: None, 150: None}
    digests, h = {}, hashlib.sha1()
    rnd = 0

    def mine(did):
        return team_of.get(did) == ours

    def settle():
        """Close her outnumbered turn: where did she end?"""
        nonlocal pend
        if pend is None:
            return
        p, pend = pend, None
        body = bodies.get(queen)
        if not body:
            stat['died_on_out_turn'] += 1
            p['died'] = True
            return
        end = body[0]
        start = p['start']
        before = min(board.far(start, f) for f in p['foes'])
        after = min(board.far(end, f) for f in p['foes'])
        p.update(end=end, away=after > before, closer=after < before)
        stat['out_done'] += 1
        stat['out_moved'] += end != start
        stat['away'] += after > before
        stat['closer'] += after < before
        stat['closes_any'] += any(board.far(end, f) < board.far(start, f) for f in p['foes'])
        stat['inside_guard_end'] += after <= GUARD_RADIUS
        field = p['field']
        if field is not None and field[start] >= 1:
            nearer = field[end] >= 0 and field[end] < field[start]
            farther = field[end] < 0 or field[end] > field[start]
            p['nearer'] = nearer
            stat['tgt_turns'] += 1
            stat['tgt_nearer'] += nearer
            stat['tgt_farther'] += farther
            stat['tgt_is_spot'] += p['is_spot']
            if p['open']:
                stat['open_turns'] += 1
                stat['open_nearer'] += nearer
                stat['open_farther'] += farther
        if to_home[start] >= 1:
            stat['home_turns'] += 1
            stat['home_nearer'] += 0 <= to_home[end] < to_home[start]

    def queen_turn():
        nonlocal spot, spot_round, pend, first, first_out, was_out, since_off
        body = bodies[queen]
        head = body[0]
        friends, foes = [], []
        taken = set()
        for did, b in bodies.items():
            if not b:
                continue
            taken.update(b)
            if did != queen and board.in_view(head, b[0]):
                (friends if mine(did) else foes).append(b[0])
        out = len(foes) >= 1 + len(friends)
        stat['q_turns'] += 1
        recent.append(out)
        if rnd >= HOME_FROM:
            stat['late_turns'] += 1
            stat['late_near_home'] += 0 <= to_home[head] <= HOME_NEAR
        if not out:
            if friends:
                spot, spot_round = head, rnd
            if was_out:
                since_off = 0
            elif since_off is not None:
                since_off += 1
            was_out = False
            return
        stat['out_turns'] += 1
        stat['out_alone'] += not friends
        if not was_out:
            stat['episodes'] += 1
            stat['restarts'] += since_off is not None and since_off < FLIP_GAP
        was_out = True
        if first_out is None:
            first_out = rnd
        # Target: home or the company spot, whichever is nearer on foot.
        field, is_spot = (to_home if to_home[head] >= 0 else None), False
        if spot is not None and rnd - spot_round <= MEMORY:
            other = board.walk(spot)
            if other[head] >= 0 and (field is None or other[head] < field[head]):
                field, is_spot = other, True
        open_step = False
        if field is not None and field[head] >= 1:
            for d in range(4):
                n = board.nb[head][d]
                if board.side[head][d] != 0 or n in taken or not 0 <= field[n] < field[head]:
                    continue
                if not any(board.far(n, f) < board.far(head, f) for f in foes):
                    open_step = True
        pend = {'round': rnd, 'start': head, 'foes': foes, 'friends': len(friends), 'field': field,
                'is_spot': is_spot, 'open': open_step}
        if first is None:
            first = pend

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else '?'
        pl = ev.pointer(0)
        if kind == 'roundStart':
            settle()
            digests[rnd] = h.hexdigest()
            rnd = pl.i32(0)
            h = hashlib.sha1()
            if rnd in q_len:
                q_len[rnd] = len(bodies[queen]) if bodies.get(queen) else 0
        elif kind == 'turnStart':
            settle()
        elif kind == 'dragonAction':
            settle()
            did = pl.i32(0)
            if not mine(did) or not bodies.get(did):
                continue
            usage = pl.pointer(1)
            stat['points_max'] = max(stat['points_max'], usage.u64(0) if usage else 0)
            stat['tle'] += pl.bit(32)
            if did == queen:
                queen_turn()
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            hx, hy = replay.point(pl.pointer(0))
            tx, ty = replay.point(pl.pointer(1))
            head, tail = hy * W + hx, ty * W + tx
            h.update(f'u{did}{(hx, hy)}{(tx, ty)}'.encode())
            body = bodies.setdefault(did, deque())
            before = len(body)
            if not body or body[0] != head:
                body.appendleft(head)
            while len(body) > 1 and body[-1] != tail:
                body.pop()
            if mine(did) and before > 0 and len(body) > before:
                stat['pearls_100'] += rnd <= 100
                if did == queen:
                    stat['q_pearls'] += 1
                    stat['q_pearls_100'] += rnd <= 100
        elif kind == 'dragonSplit':
            parent, child = pl.i32(0), pl.i32(4)
            h.update(f's{parent}{child}'.encode())
            team = ('A', 'B')[pl.u16(8)]
            for did, part in ((parent, pl.pointer(0)), (child, pl.pointer(1))):
                bodies[did] = deque(replay.point(p)[1] * W + replay.point(p)[0] for p in part)
                team_of[did] = team
        elif kind == 'dragonDeath':
            did, reason = pl.i32(0), pl.u16(4)
            h.update(f'd{did}{reason}'.encode())
            bodies.pop(did, None)
            if did == queen and q_death is None:
                q_death = rnd
                q_reason = REASONS[reason] if reason < len(REASONS) else str(reason)
                out_before_death = any(recent)
                settle()
    settle()
    digests[rnd] = h.hexdigest()
    alive = bool(bodies.get(queen))
    for mark in q_len:
        if q_len[mark] is None:
            q_len[mark] = len(bodies[queen]) if alive else 0
    if first is not None:
        first = {'enemy_heads': len(first['foes']),
                 **{k: first.get(k) for k in ('round', 'start', 'end', 'friends', 'away', 'closer', 'nearer', 'open',
                                              'died')}}
    return {'digests': digests, 'size': [board.W, board.H], 'tiles': board.W * board.H, 'rounds': rnd,
            'win': int(winner == ours), 'first_out_round': first_out, 'first_out_turn': first,
            'queen_death_round': q_death, 'queen_death_reason': q_reason, 'outnumbered_before_death': out_before_death,
            'queen_len_100': q_len[100], 'queen_len_150': q_len[150], 'queen_len_end': len(bodies[queen]) if alive else 0,
            **stat}


def job(args):
    return scan(*args)


def first_diff(a, b):
    for r in sorted(set(a) | set(b)):
        if a.get(r) != b.get(r):
            return r
    return None


def collect(directory, tag):
    out = {}
    for p in sorted(glob.glob(os.path.join(directory, f'{tag}_*.replay'))):
        stem = os.path.basename(p)[len(tag) + 1:-len('.replay')]
        m, seed, side = stem.rsplit('_', 2)
        out[(m, seed, side)] = p
    return out


def ratio(a, b):
    return round(a / b, 3) if b else None


def mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 2) if values else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--replays', required=True)
    ap.add_argument('--base', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    base, cand = collect(a.replays, a.base), collect(a.replays, a.candidate)
    if not base or set(base) != set(cand):
        sys.exit(f'missing or unpaired replays: base {len(base)}, candidate {len(cand)}, '
                 f'unpaired {sorted(set(base) ^ set(cand))[:5]}')
    keys = sorted(base)
    jobs = [(src[k], 'A' if k[2] == '0' else 'B') for k in keys for src in (base, cand)]
    with cf.ProcessPoolExecutor(int(os.environ.get('WORKERS', '4'))) as pool:
        scans = list(pool.map(job, jobs))

    tags = ('base', 'candidate')
    pairs = []
    for n, k in enumerate(keys):
        b, c = scans[2 * n], scans[2 * n + 1]
        diff = first_diff(b.pop('digests'), c.pop('digests'))
        fb, fc = b['first_out_turn'], c['first_out_turn']
        same_start = bool(fb and fc and fb['round'] == fc['round'] and fb['start'] == fc['start'])
        pairs.append({'map': k[0], 'seed': k[1], 'side': k[2], 'first_diff_round': diff,
                      'silent_ok': diff is None or (c['first_out_round'] is not None and diff >= c['first_out_round']),
                      'first_turn_same_position': same_start,
                      'first_turn_moves_differ': bool(same_start and fb.get('end') != fc.get('end')),
                      'base': b, 'candidate': c})

    def total(group, tag, field):
        return sum(int(p[tag][field] or 0) for p in group)

    def both(group, field):
        return {t: total(group, t, field) for t in tags}

    def share(group, top, bottom):
        return {t: ratio(total(group, t, top), total(group, t, bottom)) for t in tags}

    def games(group, test):
        return {t: sum(1 for p in group if test(p[t])) for t in tags}

    def block(group):
        firsts = [p for p in group if p['first_turn_same_position']]
        differ = [p for p in firsts if p['first_turn_moves_differ']]

        def first_count(sel, tag, field):
            return sum(1 for p in sel if p[tag]['first_out_turn'].get(field))

        deaths = {t: {} for t in tags}
        for p in group:
            for t in tags:
                r = p[t]['queen_death_reason']
                if r is not None:
                    deaths[t][r] = deaths[t].get(r, 0) + 1
        return {
            'games': len(group),
            'queen_turns': both(group, 'q_turns'),
            'outnumbered_turns': both(group, 'out_turns'),
            'outnumbered_share_of_queen_turns': share(group, 'out_turns', 'q_turns'),
            'outnumbered_turns_with_no_teammate_in_view': both(group, 'out_alone'),
            'games_with_an_outnumbered_turn': games(group, lambda s: s['out_turns'] > 0),
            'first_outnumbered_round_mean': {t: mean([p[t]['first_out_round'] for p in group]) for t in tags},
            'ends_farther_from_nearest_enemy_head': both(group, 'away'),
            'ends_farther_share': share(group, 'away', 'out_done'),
            'ends_nearer_to_nearest_enemy_head': both(group, 'closer'),
            'ends_nearer_share': share(group, 'closer', 'out_done'),
            'ends_nearer_to_any_enemy_head_in_view': both(group, 'closes_any'),
            'ends_within_5_tiles_of_an_enemy_head_share': share(group, 'inside_guard_end', 'out_done'),
            'moved_share': share(group, 'out_moved', 'out_done'),
            'died_on_an_outnumbered_turn': both(group, 'died_on_out_turn'),
            'turns_off_the_target': both(group, 'tgt_turns'),
            'ends_nearer_target': both(group, 'tgt_nearer'),
            'ends_nearer_target_share': share(group, 'tgt_nearer', 'tgt_turns'),
            'ends_farther_from_target_share': share(group, 'tgt_farther', 'tgt_turns'),
            'target_was_the_company_spot': both(group, 'tgt_is_spot'),
            'ends_nearer_home_share': share(group, 'home_nearer', 'home_turns'),
            'pull_open_turns': both(group, 'open_turns'),
            'pull_open_ends_nearer_target': both(group, 'open_nearer'),
            'pull_open_ends_nearer_target_share': share(group, 'open_nearer', 'open_turns'),
            'pull_open_ends_farther_from_target_share': share(group, 'open_farther', 'open_turns'),
            'rule_on_spells': both(group, 'episodes'),
            'spells_restarting_within_3_turns': both(group, 'restarts'),
            'first_turn_pairs_same_position': len(firsts),
            'first_turn_moves_differ': len(differ),
            'first_turn_ends_farther': {t: first_count(firsts, t, 'away') for t in tags},
            'first_turn_ends_nearer_enemy': {t: first_count(firsts, t, 'closer') for t in tags},
            'first_turn_ends_nearer_target': {t: first_count(firsts, t, 'nearer') for t in tags},
            'queen_alive_round_100': games(group, lambda s: s['queen_len_100'] > 0),
            'queen_alive_round_150': games(group, lambda s: s['queen_len_150'] > 0),
            'queen_alive_at_end': games(group, lambda s: s['queen_len_end'] > 0),
            'queen_deaths_by_cause': deaths,
            'queen_deaths_outnumbered_on_last_3_turns': games(group, lambda s: bool(s['outnumbered_before_death'])),
            'queen_deaths_not_outnumbered_on_last_3_turns': games(
                group, lambda s: s['queen_death_round'] is not None and not s['outnumbered_before_death']),
            'queen_length_round_100_mean': {t: mean([p[t]['queen_len_100'] for p in group]) for t in tags},
            'queen_length_round_150_mean': {t: mean([p[t]['queen_len_150'] for p in group]) for t in tags},
            'queen_length_end_mean': {t: mean([p[t]['queen_len_end'] for p in group]) for t in tags},
            'queen_pearls_by_round_100': both(group, 'q_pearls_100'),
            'queen_pearls': both(group, 'q_pearls'),
            'team_pearls_by_round_100': both(group, 'pearls_100'),
            'near_home_share_from_round_60': share(group, 'late_near_home', 'late_turns'),
            'wins': both(group, 'win'),
            'timeouts': both(group, 'tle'),
            'cpu_points_max': {t: max((p[t]['points_max'] for p in group), default=0) for t in tags},
        }

    w = block(pairs)
    by_map = {m: block([p for p in pairs if p['map'] == m]) for m in sorted({p['map'] for p in pairs})}
    silent = sum(1 for p in pairs if p['silent_ok'])
    n = len(pairs)
    away, pull = w['ends_farther_share'], w['pull_open_ends_nearer_target_share']
    target_seen = (w['outnumbered_turns']['base'] >= MIN_OUT_TURNS and
                   w['games_with_an_outnumbered_turn']['base'] >= MIN_GAME_SHARE * n and
                   w['pull_open_turns']['candidate'] >= MIN_OPEN_TURNS)
    checks = {
        'target_seen': target_seen,
        'nothing_else_changes': silent == n,
        'keeps_away': (target_seen and away['base'] is not None and away['candidate'] is not None and
                       away['candidate'] - away['base'] >= AWAY_GAIN),
        'falls_back': (target_seen and pull['candidate'] is not None and pull['candidate'] >= PULL_SHARE and
                       (pull['base'] is None or 1 - pull['candidate'] <= (1 - MISS_CUT) * (1 - pull['base']) + 1e-9)),
    }
    passed = all(checks.values())

    def pct(v):
        return 'n/a' if v is None else f'{100 * v:.0f}%'

    def two(d, f=str):
        return f"{f(d['base'])} -> {f(d['candidate'])}"

    def causes(d):
        return ', '.join(f'{k} {v}' for k, v in sorted(d.items())) or 'none'

    failed = [k for k, v in checks.items() if not v]
    lit = w['ends_nearer_target_share']
    note = (
        f"{'PASS' if passed else 'FAIL'} ({'all four checks' if passed else 'failed: ' + ', '.join(failed)}). "
        f"{n} paired games on {len(by_map)} maps, base -> candidate throughout. Outnumbered queen turns "
        f"{two(w['outnumbered_turns'])} ({two(w['outnumbered_share_of_queen_turns'], pct)} of her turns; in "
        f"{two(w['games_with_an_outnumbered_turn'])} games; alone in view on "
        f"{two(w['outnumbered_turns_with_no_teammate_in_view'])}). Keep-away: turns that end farther from the nearest "
        f"enemy head {two(away, pct)} (gate: +{AWAY_GAIN:.2f}), that end nearer {two(w['ends_nearer_share'], pct)}. "
        f"Fall-back: on turns where the pull is open ({two(w['pull_open_turns'])} turns) she ends nearer the target "
        f"on {two(pull, pct)} (gate: {PULL_SHARE:.2f} and a third fewer misses than base). The card's own wording, all outnumbered "
        f"turns: ends nearer the target {two(lit, pct)}, nearer home {two(w['ends_nearer_home_share'], pct)} (card: "
        f"most turns with the switch on, not with it off). Target was the company spot on "
        f"{two(w['target_was_the_company_spot'])} turns. First outnumbered turn of a pair, same position in both "
        f"games: {w['first_turn_pairs_same_position']} pairs, moves differ in {w['first_turn_moves_differ']}; ends "
        f"farther from the enemy {two(w['first_turn_ends_farther'])}, nearer the target "
        f"{two(w['first_turn_ends_nearer_target'])}. Same game up to the candidate's first outnumbered turn in "
        f"{silent}/{n} pairs. Rule-on spells {two(w['rule_on_spells'])}, coming back on within {FLIP_GAP} of her "
        f"turns {two(w['spells_restarting_within_3_turns'])}. What would show it is wrong (small counts, not a "
        f"verdict): queen alive at round 100 {two(w['queen_alive_round_100'])}, at 150 "
        f"{two(w['queen_alive_round_150'])}, at the end {two(w['queen_alive_at_end'])} of {n}; her deaths by cause "
        f"base [{causes(w['queen_deaths_by_cause']['base'])}], candidate "
        f"[{causes(w['queen_deaths_by_cause']['candidate'])}]; deaths with no outnumbered turn among her last "
        f"{LAST_TURNS} {two(w['queen_deaths_not_outnumbered_on_last_3_turns'])} (the card: attackers from outside "
        f"her view); her mean length at round 100 {two(w['queen_length_round_100_mean'])}, at 150 "
        f"{two(w['queen_length_round_150_mean'])}; her pearls by round 100 {two(w['queen_pearls_by_round_100'])}; "
        f"team pearls by round 100 {two(w['team_pearls_by_round_100'])}; her turns within {HOME_NEAR} steps of home "
        f"from round {HOME_FROM} {two(w['near_home_share_from_round_60'], pct)}. Wins {two(w['wins'])} of {n} (not a "
        f"verdict). Timeouts {two(w['timeouts'])}.")
    out = {
        'passed': passed,
        'note': note,
        'target_seen': target_seen,
        'checks': checks,
        'thresholds': {'MIN_OUT_TURNS': MIN_OUT_TURNS, 'MIN_GAME_SHARE': MIN_GAME_SHARE,
                       'MIN_OPEN_TURNS': MIN_OPEN_TURNS, 'AWAY_GAIN': AWAY_GAIN, 'PULL_SHARE': PULL_SHARE,
                       'MISS_CUT': round(MISS_CUT, 3), 'VIEW': VIEW, 'MEMORY': MEMORY, 'GUARD_RADIUS': GUARD_RADIUS,
                       'LAST_TURNS': LAST_TURNS, 'FLIP_GAP': FLIP_GAP, 'HOME_NEAR': HOME_NEAR, 'HOME_FROM': HOME_FROM},
        'built_as': BUILT_AS,
        'games': n,
        'pairs_same_until_first_outnumbered_turn': silent,
        'all_games': w,
        'by_map': by_map,
        'limits': 'Outnumbered, the company spot and the target are rebuilt from head positions in the replay, not '
                  'read from the bot. The rebuild walks the real walls; the bot walks the walls it has seen and '
                  'treats unseen sides as open, so the two targets can differ on a few turns. "Pull is open" checks '
                  'that a step toward the target was free and not nearer to an enemy head; it does not rebuild her '
                  'threat, dead-end and room rules, which may still forbid that step. After the first outnumbered '
                  'turn the two games of a pair are different games, so the shares compare two sets of positions; '
                  'only the first-turn rows compare the same position. The local opponent is our own release. '
                  'Four games a map: deaths, lengths and pearls are small counts and no verdict on outcomes.',
        'pairs': pairs,
    }
    with open(a.output, 'w') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print(note)


if __name__ == '__main__':
    main()
