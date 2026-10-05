#!/usr/bin/env python3
"""Card #34 mechanism check (KEEP_GUARDS): do a few of our dragons stay near our queen through the feeding phase,
is it only a few, and does the switch stay quiet where no guard is named?

usage: python3 work/card_34_check.py --replays DIR --base base --candidate candidate --output FILE
Replays are DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1), paired by (map, seed, side).

Everything is rebuilt from the replay alone (no bot logs). While our queen (dragon id 0/1) is alive it counts our
other dragons around her head at the start of every round:
  guard slots = those within 6 cells, counted up to 3, from round 420 on (are guards there?)
  crowded round = a round with 4 or more of ours inside her 7x7 view, counted from her first guard list to the end
                  of the game (does the cap hold for the whole feeding phase?). The base game of a pair is counted
                  from the same round.
The replay also records every sonar ping, so the queen's guard list is decoded from her own pings, and for each of
our dragons the newest list a ping has delivered to it. A pair where a list reached at least one of our dragons is
an "acting" pair; in every other pair the switch must change nothing at all.

Pre-registered before any game of this build was played (see PASS RULE). Queen survival, splits, rams and wins are
reported as raw numbers and are NOT part of the pass rule: the local opponent is our own bot, which does not hunt a
lone queen, and 12 games per side cannot settle an outcome.
"""
import argparse, glob, hashlib, json, os, sys, concurrent.futures as cf
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before seeing results)
SAME_UNTIL = 200     # every pair must be replay-identical through this round (feeding cannot start earlier)
QUIET_PAIRS = 2      # quiet: at least this many pairs where no list reached any of ours, and all of them identical to base
TARGET_ROUNDS = 300  # base needs at least this many late rounds with our queen alive, over all games
TARGET_MAX = 2.0     # ... and must fill at most this many of the 3 slots on average (the hole is there)
ACTING_ROUNDS = 150  # guards: base needs at least this many late rounds with our queen alive in the acting pairs
FILLED_MIN = 1.5     # ... switch on fills at least this many of the 3 slots on average there
FILLED_GAIN = 0.5    # ... and at least this much above base
ALONE_CUT = 0.5      # ... and rounds with nobody near her at most this fraction of base's share
CROWD_EXTRA = 0.05   # cap: share of crowded rounds from her first list on at most base's share plus this
CROWD_MAP_ROUNDS = 100  # ... over all acting pairs, and on every map with at least this many such rounds in both
FED_MIN_LEN = 10     # "fed as before" is read on pairs where the base queen ended at least this long, both queens alive
FED_PAIRS = 2        # ... it needs at least this many such pairs
FED_RATIO = 0.75     # ... and her mean end length there must be at least this fraction of base's

LATE = 420           # late window: feeding is on everywhere (it starts after round 300 or 400)
NEAR = 6             # "within about 6 cells" (the card)
SIGHT = 3            # her 7x7 view
SLOTS = 3            # KG_COUNT
HOLD = 3             # round starts in a row inside her view before a dragon counts as staying (reported only)
ROSTER_FRESH = 10    # KG_FRESH: a guard list older than this is ignored by the bot
KEEP = 10            # KG_KEEP: the queen lists a dragon for this many rounds after it was last in her view
FEED_FROM = 200
AFTER = 20           # "the queen survived that approach" = still alive this many rounds later
CAUSE = ['wall', 'self', 'body', 'headon', 'none']

# Sonar wire format, ported from mybot2/sonar_codec.hpp (same secret) so the queen's guard list can be read.
M64 = (1 << 64) - 1
SECRET = 0xE1DE70530C48DE42
CHECK_MASK = 0xFF << 55
CIPHER_MASK = M64 & ~(CHECK_MASK | (0x3 << 53))


def rotl(x, b):
    return ((x << b) | (x >> (64 - b))) & M64


def prf(key, m):
    k0, k1 = key
    v0, v1 = k0 ^ 0x736F6D6570736575, k1 ^ 0x646F72616E646F6D
    v2, v3 = k0 ^ 0x6C7967656E657261, k1 ^ 0x7465646279746573

    def rounds(n):
        nonlocal v0, v1, v2, v3
        for _ in range(n):
            v0 = (v0 + v1) & M64
            v1 = rotl(v1, 13) ^ v0
            v0 = rotl(v0, 32)
            v2 = (v2 + v3) & M64
            v3 = rotl(v3, 16) ^ v2
            v0 = (v0 + v3) & M64
            v3 = rotl(v3, 21) ^ v0
            v2 = (v2 + v1) & M64
            v1 = rotl(v1, 17) ^ v2
            v2 = rotl(v2, 32)

    tail = 8 << 56
    v3 ^= m
    rounds(2)
    v0 ^= m
    v3 ^= tail
    rounds(2)
    v0 ^= tail
    v2 ^= 0xFF
    rounds(4)
    return v0 ^ v1 ^ v2 ^ v3


assert prf((0x0706050403020100, 0x0F0E0D0C0B0A0908), 0x0706050403020100) == 0x93F5F5799A932462


def make_key(width, height, tag):
    root = (SECRET, rotl(SECRET, 29) ^ 0xA5A5A5A5A5A5A5A5)
    game = (width << 40) | (height << 16) | (tag & 3)
    return (prf(root, game), prf(root, game | (1 << 63)))


def sonar_open(key, wire, streams):
    check = (wire & CHECK_MASK) >> 55
    if check not in streams:
        streams[check] = prf(key, CHECK_MASK | check) & CIPHER_MASK
    plain = (wire & M64 & ~CHECK_MASK) ^ streams[check]
    return plain if (prf(key, plain) & 0xFF) == check else None


def gap(a, b, size):
    raw = abs(a - b)
    return min(raw, size - raw)


def step(a, b, size):
    d = (a - b) % size
    return d - size if d > size // 2 else d


def one(job):
    path, side = job
    ours = 'A' if side == '0' else 'B'
    root = replay.load(path).root()
    text = root.text(0)
    W, H = map(int, text.splitlines()[0].split()[1:3])
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
    foe_queen = next((i for i in (0, 1) if team_of.get(i) not in (None, ours)), None)
    if queen is None:
        raise ValueError(f'no queen (dragon 0/1) for team {ours} in {path}')
    key, streams = make_key(W, H, 2 if ours == 'A' else 1), {}
    c = Counter(games=1, win=int(winner == ours), cells=W * H)
    prefix, sha = {}, hashlib.sha1()
    rnd, mover, last_round = 0, None, 0
    queen_died = None
    threat_on = False
    approaches, rams = [], []
    streak = Counter()   # round starts in a row inside her view
    heard = {}           # dragon -> (round the list was made, cut) of the newest guard list a ping delivered to it
    told = {}            # dragon -> last round it saw her while a fresh list named it
    duty = {}            # dragon -> at its last turn a fresh list named it and it had seen her within the last 10 rounds
    view_n = {}          # round -> how many of ours were inside her view at its start (rounds after 200, queen alive)
    sent = {}            # round -> cut in the list the queen sent that round
    seen_cut = {}        # round -> cut her view over the last KEEP rounds calls for
    roll = {}            # dragon -> last round it was in her view at her turn

    def manh(a, b):
        return gap(a[0], b[0], W) + gap(a[1], b[1], H)

    def cheb(a, b):
        return max(gap(a[0], b[0], W), gap(a[1], b[1], H))

    def mine():
        return [d for d, b in bodies.items() if b and d != queen and team_of.get(d) == ours]

    def units():
        return sum(1 for d, b in bodies.items() if b and team_of.get(d) == ours)

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if kind == 'roundStart':
            rnd = pl.i32(0)
            last_round = rnd
            prefix[rnd] = sha.hexdigest()
            sha.update(f'r{rnd}'.encode())
            alive = bool(bodies.get(queen))
            for mark in (300, 400):
                if rnd == mark:
                    c[f'reach{mark}'] += 1
                    c[f'queen_alive{mark}'] += alive
                    c[f'few_units{mark}'] += units() <= 5
                    c[f'units{mark}'] += units()
            if not alive:
                streak.clear()
            elif rnd > FEED_FROM:
                qb = bodies[queen]
                qh = qb[0]
                team = mine()
                threat = any(b and team_of.get(d) != ours and manh(b[0], qh) <= NEAR for d, b in bodies.items())
                c['threat_rounds'] += threat
                if threat and not threat_on:
                    approaches.append((rnd, sum(1 for d in team if manh(bodies[d][0], qh) <= NEAR)))
                threat_on = threat
                view = [d for d in team if cheb(bodies[d][0], qh) <= SIGHT]
                for d in list(streak):
                    if d not in view:
                        del streak[d]
                for d in view:
                    streak[d] += 1
                view_n[rnd] = len(view)
                if rnd >= LATE:
                    n6 = sum(1 for d in team if manh(bodies[d][0], qh) <= NEAR)
                    holders = [d for d in view if streak[d] >= HOLD]
                    on_duty = sum(1 for d in team if duty.get(d))
                    c['late_duty_near'] += sum(1 for d in team if duty.get(d) and manh(bodies[d][0], qh) <= NEAR)
                    c['late_duty_view'] += sum(1 for d in view if duty.get(d))
                    c['late_rounds'] += 1
                    c['late_filled'] += min(n6, SLOTS)
                    c['late_filled_sight'] += min(len(view), SLOTS)
                    c['late_alone'] += n6 == 0
                    c['late_full'] += n6 >= SLOTS
                    c['late_units'] += units()
                    c['late_view'] += len(view)
                    c['late_view4'] += len(view) > SLOTS
                    c['late_view5'] += len(view) > SLOTS + 1
                    c['late_hold'] += len(holders)
                    c['late_hold4'] += len(holders) > SLOTS
                    c['late_hold_untold'] += sum(1 for d in holders if not duty.get(d))
                    c['late_duty'] += on_duty
                    c['late_duty4'] += on_duty > SLOTS
                    heads = [bodies[d][0] for d in team]
                    c['late_head_next'] += any(manh(h, qh) == 1 for h in heads)
                    if len(qb) > 1:
                        dx, dy = step(qh[0], qb[1][0], W), step(qh[1], qb[1][1], H)
                        if abs(dx) + abs(dy) == 1:
                            c['late_head_front'] += ((qh[0] + dx) % W, (qh[1] + dy) % H) in heads
                    held = {}
                    for d, b in bodies.items():
                        for cell in b:
                            held[cell] = d
                    around = [((qh[0] + dx) % W, (qh[1] + dy) % H) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
                    free = sum(1 for cell in around if cell not in held)
                    by_ours = any(held.get(cell) not in (None, queen) and team_of.get(held[cell]) == ours for cell in around)
                    c['late_free'] += free
                    c['late_boxed'] += free == 0
                    c['late_tight_ours'] += free <= 1 and by_ours
        elif kind == 'turnStart':
            did = pl.i32(0)
            if rnd > FEED_FROM and team_of.get(did) == ours and bodies.get(did) and bodies.get(queen):
                qh = bodies[queen][0]
                if did == queen:
                    for d in mine():
                        if cheb(bodies[d][0], qh) <= SIGHT:
                            roll[d] = rnd
                    ids = sorted((d for d, r in roll.items() if rnd - r <= KEEP), reverse=True)
                    seen_cut[rnd] = ids[SLOTS - 1] if len(ids) >= SLOTS else 0
                else:
                    sees = cheb(bodies[did][0], qh) <= SIGHT
                    got = heard.get(did)
                    fresh = got is not None and rnd - got[0] <= ROSTER_FRESH
                    named = fresh and (got[1] == 0 or did >= got[1])
                    if sees and named:
                        told[did] = rnd
                    duty[did] = named and rnd - told.get(did, -1000) <= ROSTER_FRESH
                    if rnd >= LATE and sees:
                        c['view_turns'] += 1
                        c['view_turns_told'] += fresh
                        c['view_turns_named'] += named
        elif kind == 'dragonAction':
            mover = pl.i32(0)
            usage = pl.pointer(1)
            if usage and team_of.get(mover) == ours:
                c['cpu_max'] = max(c['cpu_max'], usage.u64(0))
            a = pl.pointer(0)
            if a is not None and a.u16(0) == 2 and team_of.get(mover) == ours:
                c['suicides'] += 1
                c['feeds'] += rnd > FEED_FROM
                c['feeds_late'] += rnd >= LATE
                c['queen_suicides'] += mover == queen
        elif kind == 'sonarPing':
            sender = pl.i32(0)
            if rnd > FEED_FROM and team_of.get(sender) == ours:
                plain = sonar_open(key, pl.u64(16), streams)
                c['pings'] += 1
                c['pings_read'] += plain is not None
                ident = plain & 0xFFFF if plain is not None and not plain >> 63 else 0
                if ident & 0x4000 and (ident & 1) == queen:
                    when, cut = (plain >> 28) & 0x1FF, (ident >> 1) & 0x1FFF
                    if sender == queen and when == rnd:
                        sent[rnd] = cut
                    hit = pl.i32(12)
                    if pl.u16(6) and hit != queen and team_of.get(hit) == ours:
                        c['lists_reaching_ours'] += 1
                        if hit not in heard or when >= heard[hit][0]:
                            heard[hit] = (when, cut)
                            c['lists_delivered'] += rnd >= LATE
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            h = replay.point(pl.pointer(0))
            tp = replay.point(pl.pointer(1))
            sha.update(f'u{did}{h}{tp}'.encode())
            b = bodies.setdefault(did, deque())
            before = len(b)
            if not b or b[0] != h:
                b.appendleft(h)
            while len(b) > 1 and b[-1] != tp:
                b.pop()
            if rnd >= LATE and len(b) > before > 0 and team_of.get(did) == ours and bodies.get(queen):
                if did == queen:
                    c['late_queen_ate'] += len(b) - before
                elif cheb(h, bodies[queen][0]) <= SIGHT:
                    c['late_others_ate'] += len(b) - before
        elif kind == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            sha.update(f's{pa}{ch}'.encode())
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x) for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
            c['queen_splits'] += pa == queen and rnd > FEED_FROM
            for memory in (heard, told, duty, streak):
                memory.pop(ch, None)
        elif kind == 'dragonDeath':
            did = pl.i32(0)
            r = pl.u16(4)
            sha.update(f'd{did}{r}'.encode())
            cause = CAUSE[r] if r < 5 else 'other'
            b = bodies.get(did)
            if team_of.get(did) == ours and b:
                if did == queen:
                    queen_died = rnd
                    c[f'queen_death_{cause}'] += 1
                    c['queen_death_own_turn'] += mover == queen
                    c['queen_death_ours_next'] += any(manh(bodies[d][0], b[0]) <= 2 for d in mine())
                elif cause == 'headon' and rnd > FEED_FROM and bodies.get(queen) and manh(b[0], bodies[queen][0]) <= NEAR + 2:
                    rams.append((rnd, mover == did))
                if did != queen and rnd > FEED_FROM:
                    c[f'late_death_{cause}'] += 1
            bodies.pop(did, None)
            for memory in (heard, told, duty, streak):
                memory.pop(did, None)
    prefix[last_round + 1] = sha.hexdigest()

    def held_on(r):
        return queen_died is None or queen_died > r + AFTER

    alive = bool(bodies.get(queen))
    c['queen_alive_end'] = int(alive)
    c['last_round'] = last_round
    c['units_end'] = units()
    lens = [len(b) for d, b in bodies.items() if b and team_of.get(d) == ours]
    c['total_end'] = sum(lens)
    c['queen_len_end'] = len(bodies[queen]) if alive else 0
    c['kept_back_end'] = sum(lens) - c['queen_len_end']
    foe_alive = bool(foe_queen is not None and bodies.get(foe_queen))
    c['foe_queen_alive_end'] = int(foe_alive)
    c['foe_queen_len_end'] = len(bodies[foe_queen]) if foe_alive else 0
    if alive:
        n6 = sum(1 for d in mine() if manh(bodies[d][0], bodies[queen][0]) <= NEAR)
        c['end_near'] = n6
        c['end_has_guard'] = int(n6 >= 1)
        c['end_full'] = int(n6 >= SLOTS)
    late_sent = [r for r in sent if r >= LATE]
    c['lists_sent'] = len(late_sent)
    c['lists_sent_wanting'] = sum(sent[r] == 0 for r in late_sent)
    c['lists_match_view'] = sum(sent[r] == seen_cut.get(r) for r in late_sent)
    c['approaches'] = len(approaches)
    c['approaches_survived'] = sum(held_on(r) for r, _ in approaches)
    c['approaches_guarded'] = sum(n > 0 for _, n in approaches)
    c['approaches_guarded_survived'] = sum(held_on(r) for r, n in approaches if n > 0)
    c['guard_rams'] = sum(1 for _, own in rams if own)
    c['guard_rams_survived'] = sum(held_on(r) for r, own in rams if own)
    c['guards_rammed'] = sum(1 for _, own in rams if not own)
    out = dict(c)
    out['prefix'] = prefix
    out['queen_died'] = queen_died
    out['view_n'] = view_n
    out['first_list'] = min(sent) if sent else None
    return out


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
        cpu = max(s['cpu_max'], r.get('cpu_max', 0))
        s.update({k: v for k, v in r.items() if isinstance(v, int)})
        s['cpu_max'] = cpu
    return s


def share(a, b):
    return a / b if b else 0.0


def crowding(row, start):
    """Rounds from `start` on with our queen alive: [rounds, those with 4+ of ours in her view, those with 5+]."""
    counts = [n for r, n in row['view_n'].items() if r >= start]
    return [len(counts), sum(n > SLOTS for n in counts), sum(n > SLOTS + 1 for n in counts)]


def first_diff(b, c):
    """First round whose events differ between the two games of a pair; None when the games are identical."""
    last = max(max(b['prefix']), max(c['prefix']))
    for r in range(2, last + 1):
        if b['prefix'].get(r) != c['prefix'].get(r):
            return r - 1
    return None


def view(s):
    games = s['games']
    late = s['late_rounds']
    return {
        'games': games, 'wins': s['win'], 'cpu_max_points': s['cpu_max'],
        'late_rounds_queen_alive': late,
        'slots_filled_mean': round(share(s['late_filled'], late), 3),
        'slots_filled_mean_in_her_view': round(share(s['late_filled_sight'], late), 3),
        'late_rounds_alone': s['late_alone'], 'late_rounds_all_slots': s['late_full'],
        'alone_share': round(share(s['late_alone'], late), 3),
        'in_her_view_mean': round(share(s['late_view'], late), 2),
        'late_rounds_4_or_more_in_her_view': s['late_view4'],
        'crowd_rounds': s['late_view5'],
        'crowd_share': round(share(s['late_view5'], late), 3),
        'staying_3_rounds_in_her_view_mean': round(share(s['late_hold'], late), 2),
        'late_rounds_4_or_more_staying': s['late_hold4'],
        'staying_without_being_named_mean': round(share(s['late_hold_untold'], late), 2),
        'pearls_eaten_late_by_queen': s['late_queen_ate'],
        'pearls_eaten_late_by_others_in_her_view': s['late_others_ate'],
        'named_guards_mean': round(share(s['late_duty'], late), 2),
        'named_guards_within_6_mean': round(share(s['late_duty_near'], late), 2),
        'named_guards_in_her_view_mean': round(share(s['late_duty_view'], late), 2),
        'late_rounds_more_than_3_named': s['late_duty4'],
        'guard_lists_sent_by_queen': s['lists_sent'], 'of_those_asking_for_more_guards': s['lists_sent_wanting'],
        'of_those_matching_her_view': s['lists_match_view'], 'guard_lists_delivered': s['lists_delivered'],
        'guard_list_pings_reaching_ours_after_r200': s['lists_reaching_ours'],
        'turns_in_her_view': s['view_turns'], 'of_those_with_a_fresh_list': s['view_turns_told'],
        'of_those_named': s['view_turns_named'],
        'sonar_pings_read': [s['pings_read'], s['pings']],
        'late_rounds_our_head_next_to_hers': s['late_head_next'],
        'late_rounds_our_head_in_front_of_hers': s['late_head_front'],
        'free_cells_next_to_her_head_mean': round(share(s['late_free'], late), 2),
        'late_rounds_no_free_cell': s['late_boxed'],
        'late_rounds_1_or_0_free_with_ours_next_to_her': s['late_tight_ours'],
        'queen_splits_after_r200': s['queen_splits'],
        'our_dragons_late_mean': round(share(s['late_units'], late), 1),
        'games_reaching_r300': s['reach300'], 'games_reaching_r400': s['reach400'],
        'games_5_or_fewer_dragons_at_r300': s['few_units300'], 'games_5_or_fewer_dragons_at_r400': s['few_units400'],
        'queen_alive_at_r400': s['queen_alive400'], 'queen_alive_at_end': s['queen_alive_end'],
        'queen_deaths_by_cause': {k: s[f'queen_death_{k}'] for k in CAUSE if s[f'queen_death_{k}']},
        'queen_deaths_on_her_own_turn': s['queen_death_own_turn'],
        'queen_deaths_with_ours_within_2': s['queen_death_ours_next'],
        'queen_fed_herself': s['queen_suicides'],
        'end_games_with_a_guard_near': s['end_has_guard'], 'end_games_with_all_slots': s['end_full'],
        'our_dragons_at_end_mean': round(share(s['units_end'], games), 1),
        'queen_len_end_mean_when_alive': round(share(s['queen_len_end'], s['queen_alive_end']), 1),
        'kept_back_len_end_mean': round(share(s['kept_back_end'], games), 1),
        'total_len_end_mean': round(share(s['total_end'], games), 1),
        'both_queens_alive_at_end': s['both_queens_end'], 'of_those_our_queen_longer': s['both_ours_longer'],
        'feeds_after_r200': s['feeds'], 'feeds_from_r420': s['feeds_late'],
        'enemy_approaches': s['approaches'], 'approaches_queen_alive_20_rounds_later': s['approaches_survived'],
        'approaches_with_a_guard_near': s['approaches_guarded'],
        'guarded_approaches_queen_alive_20_rounds_later': s['approaches_guarded_survived'],
        'guard_rams': s['guard_rams'], 'guard_rams_queen_alive_20_rounds_later': s['guard_rams_survived'],
        'guards_rammed_by_enemy': s['guards_rammed'],
        'rounds_enemy_head_near_queen': s['threat_rounds'],
    }


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
    for rows in (base, cand):
        for r in rows.values():
            both = r['queen_alive_end'] and r['foe_queen_alive_end']
            r['both_queens_end'] = int(both)
            r['both_ours_longer'] = int(both and r['queen_len_end'] > r['foe_queen_len_end'])
    diffs = {k: first_diff(base[k], cand[k]) for k in keys}
    changed = sorted(d for d in diffs.values() if d is not None)
    early = sorted('_'.join(k) for k, d in diffs.items() if d is not None and d <= SAME_UNTIL)
    b, c = total(base[k] for k in keys), total(cand[k] for k in keys)
    bv, cv = view(b), view(c)
    saved = sum(1 for k in keys if cand[k]['queen_alive_end'] and not base[k]['queen_alive_end'])
    lost = sum(1 for k in keys if base[k]['queen_alive_end'] and not cand[k]['queen_alive_end'])
    fed = [k for k in keys if base[k]['queen_len_end'] >= FED_MIN_LEN and cand[k]['queen_alive_end']]
    fed_base = share(sum(base[k]['queen_len_end'] for k in fed), len(fed))
    fed_cand = share(sum(cand[k]['queen_len_end'] for k in fed), len(fed))
    fed_ratio = share(fed_cand, fed_base)
    fed_dead = sum(1 for k in keys if base[k]['queen_len_end'] >= FED_MIN_LEN and not cand[k]['queen_alive_end'])
    by_map = {}
    for m in sorted({k[0] for k in keys}):
        mb, mc = total(base[k] for k in keys if k[0] == m), total(cand[k] for k in keys if k[0] == m)
        both = lambda name, per: [round(share(mb[name], mb[per]), 2), round(share(mc[name], mc[per]), 2)]
        by_map[m] = {'cells': mb['cells'] // max(1, mb['games']), 'games': mb['games'],
                     'late_rounds_queen_alive': [mb['late_rounds'], mc['late_rounds']],
                     'slots_filled_mean': both('late_filled', 'late_rounds'),
                     'late_rounds_alone': [mb['late_alone'], mc['late_alone']],
                     'late_rounds_4_or_more_in_her_view': [mb['late_view4'], mc['late_view4']],
                     'crowd_rounds': [mb['late_view5'], mc['late_view5']],
                     'pearls_eaten_late_by_queen': [mb['late_queen_ate'], mc['late_queen_ate']],
                     'pearls_eaten_late_by_others_in_her_view': [mb['late_others_ate'], mc['late_others_ate']],
                     'named_guards_mean': both('late_duty', 'late_rounds'),
                     'named_guards_within_6_mean': both('late_duty_near', 'late_rounds'),
                     'named_guards_in_her_view_mean': both('late_duty_view', 'late_rounds'),
                     'pairs_where_a_list_reached_ours': sum(1 for k in keys if k[0] == m and cand[k].get('lists_reaching_ours', 0) > 0),
                     'pairs_identical_to_base': sum(1 for k in keys if k[0] == m and diffs[k] is None),
                     'first_list_rounds': sorted(cand[k]['first_list'] for k in keys if k[0] == m and cand[k]['first_list'] is not None),
                     'guard_lists_sent_by_queen': [mb['lists_sent'], mc['lists_sent']],
                     'turns_in_her_view_with_a_fresh_list': [f"{mb['view_turns_told']}/{mb['view_turns']}",
                                                             f"{mc['view_turns_told']}/{mc['view_turns']}"],
                     'late_rounds_our_head_next_to_hers': [mb['late_head_next'], mc['late_head_next']],
                     'late_rounds_no_free_cell': [mb['late_boxed'], mc['late_boxed']],
                     'queen_splits_after_r200': [mb['queen_splits'], mc['queen_splits']],
                     'feeds_after_r200': [mb['feeds'], mc['feeds']],
                     'guard_rams': [mb['guard_rams'], mc['guard_rams']],
                     'queen_alive_at_end': [mb['queen_alive_end'], mc['queen_alive_end']],
                     'queen_len_end_mean_when_alive': both('queen_len_end', 'queen_alive_end'),
                     'our_dragons_at_end_mean': both('units_end', 'games'),
                     'wins': [mb['win'], mc['win']]}

    # Acting pairs: a guard list reached at least one of our dragons with the switch on. Everywhere else it must do nothing.
    acting = [k for k in keys if cand[k].get('lists_reaching_ours', 0) > 0]
    quiet = [k for k in keys if k not in acting]
    quiet_changed = sorted('_'.join(k) for k in quiet if diffs[k] is not None)
    ab, ac = view(total(base[k] for k in acting)), view(total(cand[k] for k in acting))
    crowd_pairs, crowd_maps, crowd_all = {}, {}, [[0, 0, 0], [0, 0, 0]]
    for k in acting:
        start = cand[k]['first_list']
        if start is None:
            continue
        both = [crowding(base[k], start), crowding(cand[k], start)]
        crowd_pairs['_'.join(k)] = {'first_list_round': start, 'base': both[0], 'candidate': both[1]}
        per_map = crowd_maps.setdefault(k[0], [[0, 0, 0], [0, 0, 0]])
        for which in (0, 1):
            for i in range(3):
                per_map[which][i] += both[which][i]
                crowd_all[which][i] += both[which][i]

    def crowd_ok(pair):
        return pair[1][0] > 0 and share(pair[1][1], pair[1][0]) <= share(pair[0][1], pair[0][0]) + CROWD_EXTRA

    crowd_bad_maps = sorted(m for m, pair in crowd_maps.items()
                            if min(pair[0][0], pair[1][0]) >= CROWD_MAP_ROUNDS and not crowd_ok(pair))

    prefix_ok = not early
    quiet_ok = len(quiet) >= QUIET_PAIRS and not quiet_changed
    target_seen = bv['late_rounds_queen_alive'] >= TARGET_ROUNDS and bv['slots_filled_mean'] <= TARGET_MAX
    guards_ok = (ab['late_rounds_queen_alive'] >= ACTING_ROUNDS and ac['late_rounds_queen_alive'] > 0 and
                 ac['slots_filled_mean'] >= FILLED_MIN and
                 ac['slots_filled_mean'] >= ab['slots_filled_mean'] + FILLED_GAIN and
                 ac['alone_share'] <= ALONE_CUT * ab['alone_share'])
    cap_ok = crowd_ok(crowd_all) and not crowd_bad_maps
    fed_ok = len(fed) >= FED_PAIRS and fed_ratio >= FED_RATIO
    passed = bool(prefix_ok and quiet_ok and target_seen and guards_ok and cap_ok and fed_ok)
    why = []
    if not prefix_ok:
        why.append(f'{len(early)} pairs differ at or before round {SAME_UNTIL}, before feeding can start')
    if not quiet_ok:
        why.append(f'the switch is not quiet where no guard is named (needs {QUIET_PAIRS}+ pairs where no list reached any '
                   f'of ours, all identical to base; got {len(quiet)} such pairs, {len(quiet_changed)} of them differ)')
    if not target_seen:
        why.append(f"base did not show the hole (needs {TARGET_ROUNDS}+ late rounds with the queen alive and at most "
                   f"{TARGET_MAX} slots filled; got {bv['late_rounds_queen_alive']} rounds, {bv['slots_filled_mean']} filled)")
    if not guards_ok:
        why.append(f'guards are not there in the acting pairs (needs {ACTING_ROUNDS}+ base late rounds there, {FILLED_MIN} of 3 '
                   f'slots, base + {FILLED_GAIN}, and at most {ALONE_CUT:.0%} of base\'s rounds alone)')
    if not cap_ok:
        why.append(f'the cap does not hold from her first list on (rounds with 4+ of ours in her view may be at most base\'s '
                   f'share + {CROWD_EXTRA:.0%}, over all acting pairs and on every map with {CROWD_MAP_ROUNDS}+ such rounds'
                   + (f'; over on {", ".join(crowd_bad_maps)}' if crowd_bad_maps else '') + ')')
    if not fed_ok:
        why.append(f'the queen is not fed as before (needs {FED_PAIRS}+ pairs where base ended {FED_MIN_LEN}+ long with both '
                   f'alive, and at least {FED_RATIO:.0%} of base\'s length there; got {len(fed)} pairs, {fed_ratio:.0%})')
    cb, cc = crowd_all
    note = (f"Acting pairs (a guard list reached one of ours): {len(acting)}/{len(keys)}. Quiet pairs: {len(quiet)}, of which "
            f"{len(quiet_changed)} differ from base. "
            f"Guards there, acting pairs, rounds {LATE}+ with our queen alive ({ab['late_rounds_queen_alive']} base, "
            f"{ac['late_rounds_queen_alive']} switch on): slots filled (ours within {NEAR} cells, max 3) "
            f"{ab['slots_filled_mean']} -> {ac['slots_filled_mean']}, nobody near her {ab['alone_share']:.0%} -> {ac['alone_share']:.0%}; "
            f"over all pairs {bv['slots_filled_mean']} -> {cv['slots_filled_mean']}, {bv['alone_share']:.0%} -> {cv['alone_share']:.0%}. "
            f"Cap, acting pairs, from her first list to the end: rounds with 4+ of ours in her view {cb[1]} of {cb[0]} -> "
            f"{cc[1]} of {cc[0]} ({share(cb[1], cb[0]):.1%} -> {share(cc[1], cc[0]):.1%}); with 5+ {cb[2]} -> {cc[2]}. "
            f"Fed as before: her end length in the {len(fed)} pairs where base ended {FED_MIN_LEN}+ long and she lived "
            f"{fed_base:.1f} -> {fed_cand:.1f} ({fed_ratio:.0%}); she died with the switch in {fed_dead} more such pairs. "
            f"Guard list: sent by the queen in {cv['guard_lists_sent_by_queen']} late rounds, named guards holding per late round "
            f"{cv['named_guards_mean']} ({cv['named_guards_within_6_mean']} within {NEAR} cells, "
            f"{cv['named_guards_in_her_view_mean']} in her view). "
            f"Pairs that differ: {len(changed)}/{len(keys)}, earliest at round {changed[0] if changed else 'never'}. "
            f"Not gated, {len(keys)} games each: pearls eaten late by her {bv['pearls_eaten_late_by_queen']} -> "
            f"{cv['pearls_eaten_late_by_queen']} and by others in her view {bv['pearls_eaten_late_by_others_in_her_view']} -> "
            f"{cv['pearls_eaten_late_by_others_in_her_view']}, our head next to hers {bv['late_rounds_our_head_next_to_hers']} -> "
            f"{cv['late_rounds_our_head_next_to_hers']} rounds, queen splits after r200 {bv['queen_splits_after_r200']} -> "
            f"{cv['queen_splits_after_r200']}, queen alive at end {bv['queen_alive_at_end']} -> {cv['queen_alive_at_end']} "
            f"(saved {saved}, lost {lost}), feeds after r200 {bv['feeds_after_r200']} -> {cv['feeds_after_r200']}, "
            f"guard rams {bv['guard_rams']} -> {cv['guard_rams']}, games with 5 or fewer dragons at r400 "
            f"{bv['games_5_or_fewer_dragons_at_r400']} -> {cv['games_5_or_fewer_dragons_at_r400']}, queen fed herself "
            f"{bv['queen_fed_herself']} -> {cv['queen_fed_herself']}, wins {bv['wins']} -> {cv['wins']}"
            + ('' if passed else '. NOT shown: ' + '; '.join(why)))
    out = {'passed': passed, 'note': note, 'target_seen': bool(target_seen), 'pairs': len(keys),
           'maps': sorted({k[0] for k in keys}),
           'pass_rule': {'same_until_round': SAME_UNTIL, 'quiet_pairs': QUIET_PAIRS, 'target_rounds': TARGET_ROUNDS,
                         'target_max': TARGET_MAX, 'acting_rounds': ACTING_ROUNDS,
                         'filled_min': FILLED_MIN, 'filled_gain': FILLED_GAIN, 'alone_cut': ALONE_CUT,
                         'crowd_extra': CROWD_EXTRA, 'crowd_map_rounds': CROWD_MAP_ROUNDS,
                         'fed_min_len': FED_MIN_LEN, 'fed_pairs': FED_PAIRS,
                         'fed_ratio': FED_RATIO, 'prefix_ok': bool(prefix_ok), 'quiet_ok': bool(quiet_ok),
                         'target_seen': bool(target_seen),
                         'guards_ok': bool(guards_ok), 'cap_ok': bool(cap_ok), 'fed_ok': bool(fed_ok)},
           'acting_pairs': sorted('_'.join(k) for k in acting),
           'quiet_pairs': sorted('_'.join(k) for k in quiet), 'quiet_pairs_that_differ': quiet_changed,
           'crowding_from_first_list': {
               'columns': ['rounds with our queen alive', 'with 4+ of ours in her view', 'with 5+'],
               'acting_pairs_base': cb, 'acting_pairs_candidate': cc,
               'share_4_or_more': [round(share(cb[1], cb[0]), 3), round(share(cc[1], cc[0]), 3)],
               'by_map_base_then_candidate': crowd_maps, 'maps_over_the_limit': crowd_bad_maps, 'by_pair': crowd_pairs},
           'acting_pairs_base': ab, 'acting_pairs_candidate': ac,
           'fed_as_before': {'pairs': len(fed), 'base_queen_len_mean': round(fed_base, 1),
                             'candidate_queen_len_mean': round(fed_cand, 1), 'ratio': round(fed_ratio, 3),
                             'pairs_where_she_died_with_the_switch': fed_dead},
           'base': bv, 'candidate': cv, 'by_map_base_then_candidate': by_map,
           'pairs_that_differ': len(changed), 'first_differing_rounds': changed, 'pairs_differing_too_early': early,
           'queen_alive_at_end_pairs': {'saved_by_switch': saved, 'lost_with_switch': lost},
           'limits': ('measured from replays without bot logs. A guard slot is any of our dragons within 6 cells of the queen. '
                      'A crowded round has 4 or more of our heads inside her 7x7 view, whatever their reason for being there; '
                      'it is counted from the round she sent her first guard list with the switch on, and the base game of the '
                      'pair is counted from that same round. An acting pair is one where a ping carrying a guard list hit one '
                      'of our dragons after round 200; a quiet pair is any other, and "identical" there means the same moves, '
                      'splits and deaths in every round. '
                      'A named guard is rebuilt from the sonar pings: at its last turn the newest guard list a ping had '
                      'delivered to it was at most 10 rounds old and named it, and it had seen her within the last 10 rounds '
                      'while named; the last-10-rounds release is '
                      'not modelled, and base sends no lists so its named counts are 0 by construction. "Matching her view" '
                      'compares the list she sent with the 3 newest of ours seen in her view over the last 10 rounds; where the '
                      'fed dragon is not the queen the bot leaves that dragon out, which this does not model. Pearls eaten by '
                      'others in her view are length gained by our other dragons while inside her view. Free cells next to '
                      'her head count dragon bodies only, not walls. A guard ram is one of ours dying head-on on its own move '
                      'within 8 cells of the queen after round 200; base counts the same events. cpu_max_points is 0 when the '
                      'replays carry no CPU counter. Survival, splits, rams and wins are raw counts from a small sample '
                      'against our own bot, not evidence of an outcome')}
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
        sys.exit(f'card 34 check failed: {exc}')
