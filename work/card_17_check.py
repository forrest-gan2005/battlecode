#!/usr/bin/env python3
"""Card #17 mechanism check (LG_AVENGE, attempt 2): once our queen is dead, short non-leaders go for theirs.

usage: python3 work/card_17_check.py --replays DIR --base base --candidate candidate --output FILE
Reads paired replays DIR/<tag>_<map>_<seed>_<side>.replay (side 0 = we are team A).

Expectation, written before any switch-on game was run:
  1. silent: a pair may differ only from a round >= HUNT_ROUND where our queen is already dead and
     theirs was alive within FRESH rounds; otherwise it is replay-identical to the end.
  2. no false alarm: our dragons never send "our queen is dead" while she is alive.
  3. trigger: in at least TRIGGER_SHARE of the games where our queen dies, our dragons send "our queen is dead".
  4. target seen: at least MIN_PAIRS "hunt pairs" (base game has our queen dead and theirs alive for
     MIN_WINDOW+ rounds from HUNT_ROUND on).
  5. hunt on: in more than half of the hunt pairs our dragons relay her position (only hunters' teams do).
  6. approach: in more than half of the hunt pairs our nearest hunter (alive, length <= MAX_LEN, not our
     longest) is on average closer to her head with the switch on, or she is killed in the hunt.
  7. kills: she dies in the hunt phase in more hunt pairs with the switch on than without.
  8. no wipe-out: in no hunt pair is our team wiped out with the switch on but not without.
passed = all eight. Fewer than MIN_PAIRS hunt pairs is "not shown", never a pass.
Exit code 0 for a completed measurement, nonzero for missing or unpaired replays.
"""
import argparse, glob, hashlib, json, os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

HUNT_ROUND = 300
MAX_LEN = 8
FRESH = 20
MIN_WINDOW = 20
MIN_PAIRS = 3
NEAR = 3
TRIGGER_SHARE = 1 / 3
REASONS = ['wall', 'self', 'body', 'head-on', 'no action']

# mybot2/sonar_codec.hpp, in Python: the check needs to read our own messages.
M64 = (1 << 64) - 1
SECRET = 0xE1DE70530C48DE42
CHECK_MASK = 0xFF << 55
TAG_MASK = 0x3 << 53
CIPHER_MASK = M64 & ~(CHECK_MASK | TAG_MASK)


def rotl(x, b):
    return ((x << b) | (x >> (64 - b))) & M64


def prf(key, m):
    k0, k1 = key
    v0, v1 = k0 ^ 0x736F6D6570736575, k1 ^ 0x646F72616E646F6D
    v2, v3 = k0 ^ 0x6C7967656E657261, k1 ^ 0x7465646279746573

    def rounds(n, v0, v1, v2, v3):
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
        return v0, v1, v2, v3

    tail = 8 << 56
    v3 ^= m
    v0, v1, v2, v3 = rounds(2, v0, v1, v2, v3)
    v0 ^= m
    v3 ^= tail
    v0, v1, v2, v3 = rounds(2, v0, v1, v2, v3)
    v0 ^= tail
    v2 ^= 0xFF
    v0, v1, v2, v3 = rounds(4, v0, v1, v2, v3)
    return v0 ^ v1 ^ v2 ^ v3


assert prf((0x0706050403020100, 0x0F0E0D0C0B0A0908), 0x0706050403020100) == 0x93F5F5799A932462


def make_key(width, height, tag):
    root = (SECRET, rotl(SECRET, 29) ^ 0xA5A5A5A5A5A5A5A5)
    game = (width << 40) | (height << 16) | (tag & 0x3)
    return prf(root, game), prf(root, game | (1 << 63))


def sonar_open(key, wire, streams):
    check = (wire & CHECK_MASK) >> 55
    if check not in streams:
        streams[check] = prf(key, CHECK_MASK | check) & CIPHER_MASK
    plain = (wire & (M64 & ~CHECK_MASK)) ^ streams[check]
    return plain if (prf(key, plain & (M64 & ~CHECK_MASK)) & 0xFF) == check else None


def scan(path, ours):
    """One pass over a replay for our side: digests, queen deaths, our sonar claims, the hunt phase."""
    root = replay.load(path).root()
    text = root.text(0)
    W, H = map(int, text.splitlines()[0].split()[1:3])
    bodies, team_of = {}, {}
    for line in text.splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
    queens = [i for i in (0, 1) if team_of.get(i) == ours]
    foes = [i for i in (0, 1) if i in team_of and team_of[i] != ours]
    if len(queens) != 1 or len(foes) != 1:
        raise ValueError(f'{path}: ids 0 and 1 are not one queen per team')
    q_us, q_them = queens[0], foes[0]
    tag = 0x2 if ours == 'A' else 0x1
    key, streams, opened = make_key(W, H, tag), {}, {}

    digests, h = {}, hashlib.sha1()
    death = {}
    rows = []
    stat = {'small_deaths': 0, 'deaths': 0, 'splits': 0, 'claims': 0, 'false_claims': 0, 'relays': 0,
            'relays_dead': 0, 'bad_sonar': 0}
    first = {'claim': None, 'relay': None}
    last_near = None
    killer_near = None
    rnd = 0

    def dist(a, b):
        dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
        return min(dx, W - dx) + min(dy, H - dy)

    def hunting():
        return rnd >= HUNT_ROUND and q_us not in bodies and q_them in bodies

    def snapshot():
        nonlocal last_near
        last_near = None
        if not hunting():
            return
        mine = {i: len(b) for i, b in bodies.items() if team_of.get(i) == ours}
        if not mine:
            return
        lead = min(mine, key=lambda i: (-mine[i], i))
        her = bodies[q_them][0]
        d = [dist(bodies[i][0], her) for i, n in mine.items() if i != lead and n <= MAX_LEN]
        last_near = min(d) if d else None
        rows.append((rnd, last_near))

    for ev in root.pointer(3):
        kind = replay.EVENT_NAMES[ev.u16(0)] if ev.u16(0) < len(replay.EVENT_NAMES) else '?'
        pl = ev.pointer(0)
        if kind == 'roundStart':
            if rnd:
                snapshot()
                digests[rnd] = h.hexdigest()
            rnd = pl.i32(0)
            h = hashlib.sha1()
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            head, tail = replay.point(pl.pointer(0)), replay.point(pl.pointer(1))
            h.update(f'u{did}{head}{tail}'.encode())
            body = bodies.setdefault(did, deque())
            if not body or body[0] != head:
                body.appendleft(head)
            while len(body) > 1 and body[-1] != tail:
                body.pop()
        elif kind == 'dragonSplit':
            parent, child = pl.i32(0), pl.i32(4)
            h.update(f's{parent}{child}'.encode())
            team = ('A', 'B')[pl.u16(8)]
            bodies[parent] = deque(replay.point(p) for p in pl.pointer(0))
            bodies[child] = deque(replay.point(p) for p in pl.pointer(1))
            team_of[parent] = team_of[child] = team
            if team == ours and hunting():
                stat['splits'] += 1
        elif kind == 'dragonDeath':
            did, reason = pl.i32(0), pl.u16(4)
            h.update(f'd{did}{reason}'.encode())
            if did in (q_us, q_them):
                death[did] = (rnd, REASONS[reason] if reason < len(REASONS) else '?')
                if did == q_them:
                    killer_near = last_near
            elif team_of.get(did) == ours and hunting():
                stat['deaths'] += 1
                stat['small_deaths'] += len(bodies.get(did, ())) <= MAX_LEN
            bodies.pop(did, None)
        elif kind == 'sonarPing':
            wire = pl.u64(16)
            if ((wire & TAG_MASK) >> 53) != tag:
                continue
            if wire not in opened:
                opened[wire] = sonar_open(key, wire, streams)
            plain = opened[wire]
            if plain is None:
                stat['bad_sonar'] += 1
                continue
            body = plain & ((1 << 55) - 1)
            state = None
            if plain >> 63 == 0:
                state = (body >> 13) & 0x3
            elif (body >> 38) & 0x7FFF == 0x15:
                state = (body >> 24) & 0x3
                stat['relays'] += 1
                stat['relays_dead'] += (body >> 23) & 1
                if first['relay'] is None:
                    first['relay'] = rnd
            if state is not None and state & 1:
                stat['claims'] += 1
                stat['false_claims'] += q_us in bodies
                if first['claim'] is None:
                    first['claim'] = rnd
    if rnd:
        snapshot()
        digests[rnd] = h.hexdigest()

    mine = [len(b) for i, b in bodies.items() if team_of.get(i) == ours]
    theirs = [len(b) for i, b in bodies.items() if team_of.get(i) != ours]
    measured = [r for r in rows if r[1] is not None]
    d_us, d_them = death.get(q_us), death.get(q_them)
    # Her death counts for the hunt only if our queen was already dead and the hunt phase had begun.
    in_hunt = bool(d_them and d_us and d_them[0] >= max(HUNT_ROUND, d_us[0]))
    return {
        'digests': digests,
        'rounds': rnd,
        'queen_death': d_us[0] if d_us else None,
        'foe_death': d_them[0] if d_them else None,
        'foe_death_reason': d_them[1] if d_them else None,
        'foe_killed_in_hunt': in_hunt,
        'hunter_near_before_kill': killer_near if in_hunt else None,
        'window_rounds': len(rows),
        'hunter_rounds': len(measured),
        'mean_nearest': round(sum(r[1] for r in measured) / len(measured), 2) if measured else None,
        'near_rounds': sum(1 for r in measured if r[1] <= NEAR),
        'deaths_in_hunt': stat['deaths'],
        'small_deaths_in_hunt': stat['small_deaths'],
        'splits_in_hunt': stat['splits'],
        'queen_dead_messages': stat['claims'],
        'queen_dead_messages_while_alive': stat['false_claims'],
        'first_queen_dead_message': first['claim'],
        'relay_messages': stat['relays'],
        'relay_messages_her_dead': stat['relays_dead'],
        'first_relay': first['relay'],
        'unreadable_own_sonar': stat['bad_sonar'],
        'end_only_their_queen': q_us not in bodies and q_them in bodies,
        'end_both_dead': q_us not in bodies and q_them not in bodies,
        'end_longest_us': max(mine, default=0),
        'end_longest_them': max(theirs, default=0),
        'end_total_us': sum(mine),
        'end_total_them': sum(theirs),
        'end_units_us': len(mine),
    }


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


def silent(diff, b):
    """Expectation 1, judged on the base game (the two games are the same up to the first difference)."""
    if diff is None:
        return True
    died, foe = b['queen_death'], b['foe_death']
    return died is not None and diff >= max(HUNT_ROUND, died) and (foe is None or foe >= diff - FRESH)


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

    pairs = []
    for key in sorted(base):
        ours = 'A' if key[2] == '0' else 'B'
        b, c = scan(base[key], ours), scan(cand[key], ours)
        diff = first_diff(b.pop('digests'), c.pop('digests'))
        p = {
            'map': key[0], 'seed': key[1], 'side': key[2], 'first_diff_round': diff,
            'silent_ok': silent(diff, b),
            'hunt_pair': b['window_rounds'] >= MIN_WINDOW and b['hunter_rounds'] >= MIN_WINDOW,
            'false_alarm': c['queen_dead_messages_while_alive'] > 0,
            'queen_died': c['queen_death'] is not None,
            'trigger': c['queen_death'] is not None and c['queen_dead_messages'] > 0,
            'hunt_on': c['relay_messages'] > 0,
            'wiped_only_with_switch': c['end_units_us'] == 0 and b['end_units_us'] > 0,
            'base': b, 'candidate': c,
        }
        if not p['hunt_pair']:
            p['closer'] = None
        elif c['foe_killed_in_hunt'] and not b['foe_killed_in_hunt']:
            p['closer'] = True
        elif c['mean_nearest'] is None or b['mean_nearest'] is None:
            p['closer'] = None
        else:
            p['closer'] = c['mean_nearest'] < b['mean_nearest']
        pairs.append(p)

    hunt = [p for p in pairs if p['hunt_pair']]
    died = [p for p in pairs if p['queen_died']]
    compared = [p for p in hunt if p['closer'] is not None]

    def count(rows, field):
        return sum(1 for p in rows if p[field])

    def total(rows, tag, field):
        return sum(int(p[tag][field] or 0) for p in rows)

    def mean(rows, tag, field):
        vals = [p[tag][field] for p in rows if p[tag][field] is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    def share(rows, tag):
        n = total(rows, tag, 'hunter_rounds')
        return round(total(rows, tag, 'near_rounds') / n, 3) if n else None

    kills_b, kills_c = total(hunt, 'base', 'foe_killed_in_hunt'), total(hunt, 'candidate', 'foe_killed_in_hunt')
    checks = {
        'silent': count(pairs, 'silent_ok') == len(pairs),
        'no_false_alarm': count(pairs, 'false_alarm') == 0,
        'trigger': bool(died) and count(died, 'trigger') >= TRIGGER_SHARE * len(died),
        'target_seen': len(hunt) >= MIN_PAIRS,
        'hunt_on': 2 * count(hunt, 'hunt_on') > len(hunt),
        'approach': 2 * count(compared, 'closer') > len(compared),
        'kills': kills_c > kills_b,
        'no_wipe_out': count(hunt, 'wiped_only_with_switch') == 0,
    }
    passed = all(checks.values())

    facts = (f"{len(hunt)} of {len(pairs)} pairs were hunt pairs (our queen dead, theirs alive for {MIN_WINDOW}+ rounds "
             f"from round {HUNT_ROUND}). 'Queen dead' was sent in {count(died, 'trigger')} of {len(died)} games where "
             f"our queen died, and in {count(pairs, 'false_alarm')} games while she was alive. "
             f"{count(pairs, 'silent_ok')} of {len(pairs)} pairs were silent outside the hunt. "
             f"Hunt switched on in {count(hunt, 'hunt_on')} of {len(hunt)} hunt pairs; nearest hunter closer in "
             f"{count(compared, 'closer')} of {len(compared)}; she was killed in the hunt {kills_c} times with the "
             f"switch on vs {kills_b} without; wiped out only with the switch on: {count(hunt, 'wiped_only_with_switch')}.")
    failed = [k for k, v in checks.items() if not v]
    if passed:
        note = 'Shown. ' + facts
    elif not checks['target_seen'] and all(v for k, v in checks.items() if k in ('silent', 'no_false_alarm')):
        note = f'Not shown: too few hunt pairs (need {MIN_PAIRS}). ' + facts
    else:
        note = f"Not shown, failed: {', '.join(failed)}. " + facts

    result = {
        'passed': bool(passed), 'note': note, 'checks': checks,
        'pairs': len(pairs),
        'silent_ok_pairs': count(pairs, 'silent_ok'),
        'identical_pairs': sum(1 for p in pairs if p['first_diff_round'] is None),
        'queen_died_pairs': len(died),
        'trigger_pairs': count(died, 'trigger'),
        'false_alarm_pairs': count(pairs, 'false_alarm'),
        'hunt_pairs': len(hunt),
        'hunt_on_pairs': count(hunt, 'hunt_on'),
        'hunt_on_outside_hunt_pairs': sum(1 for p in pairs if p['hunt_on'] and not p['hunt_pair']),
        'compared_pairs': len(compared), 'closer_pairs': count(compared, 'closer'),
        'mean_nearest_hunter': {t: mean(hunt, t, 'mean_nearest') for t in ('base', 'candidate')},
        'near_share': {t: share(hunt, t) for t in ('base', 'candidate')},
        'foe_queen_killed_in_hunt': {'base': kills_b, 'candidate': kills_c},
        'foe_queen_killed_head_on': {
            t: sum(1 for p in hunt if p[t]['foe_killed_in_hunt'] and p[t]['foe_death_reason'] == 'head-on')
            for t in ('base', 'candidate')},
        'deaths_in_hunt': {t: total(hunt, t, 'deaths_in_hunt') for t in ('base', 'candidate')},
        'splits_in_hunt': {t: total(hunt, t, 'splits_in_hunt') for t in ('base', 'candidate')},
        'wiped_only_with_switch': count(hunt, 'wiped_only_with_switch'),
        'end_only_their_queen': {t: total(pairs, t, 'end_only_their_queen') for t in ('base', 'candidate')},
        'end_both_dead': {t: total(pairs, t, 'end_both_dead') for t in ('base', 'candidate')},
        'hunt_pairs_end_longest': {t: {'us': mean(hunt, t, 'end_longest_us'), 'them': mean(hunt, t, 'end_longest_them')}
                                   for t in ('base', 'candidate')},
        'hunt_pairs_end_total': {t: {'us': mean(hunt, t, 'end_total_us'), 'them': mean(hunt, t, 'end_total_them')}
                                 for t in ('base', 'candidate')},
        'unreadable_own_sonar': {t: total(pairs, t, 'unreadable_own_sonar') for t in ('base', 'candidate')},
        'settings': {'hunt_round': HUNT_ROUND, 'max_len': MAX_LEN, 'fresh': FRESH, 'min_window': MIN_WINDOW,
                     'min_pairs': MIN_PAIRS, 'near': NEAR, 'trigger_share': round(TRIGGER_SHARE, 3)},
        'limits': 'Distances are grid distances with wrap, walls and portals ignored. Lengths come from replay '
                  'body tracking. "Queen dead" and relay counts are read from our own sonar messages (decoded with '
                  'the codec key); hunt state inside the bot is not in the replay. The two games of a pair diverge '
                  'once the hunt starts, so later rounds are not round-for-round comparable.',
        'games': pairs,
    }
    with open(a.output, 'w') as f:
        json.dump(result, f, indent=1)
    print(note)


if __name__ == '__main__':
    main()
