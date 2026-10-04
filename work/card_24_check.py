#!/usr/bin/env python3
"""Card #24 mechanism check: does a stalled tiny team break out of its home area (EC_BREAKOUT)?

usage: python3 work/card_24_check.py --replays DIRECTORY --base base --candidate candidate --output FILE
Reads kept replays DIRECTORY/<tag>_<map>_<seed>_<side>.replay and pairs them by (map, seed, side).
Bot logs are not needed (the batch drops them); everything is rebuilt from moves, splits and deaths.

Terms:
  stall signal   at the start of a round our team has 6 dragons or fewer and one of our dragons, not the queen
                 (id 0 or 1), has not grown for 30+ rounds. One such dragon for one round = one stalled dragon-round.
                 This is the replay-side view of the bot's trigger; the bot also skips its leader and feeders.
  fired pair     the base game shows its first stalled dragon-round at round 150 or earlier, so the mode has at
                 least 50 rounds to change what we measure at round 200.
  can-fire       wider test used only for the identity check: the same signal, but with the smallest team size seen
                 anywhere in the round. The bot cannot switch the mode on in a game where this never holds.

Expectation, written before any game was run (sums are over the fired pairs):
  1. fires: at least 4 fired pairs;
  2. untouched: every pair whose base game never reaches can-fire is replay-identical in base and candidate;
  3. cells: different cells our heads visited by round 200 are higher in candidate;
  4. pearls: pearls we ate in rounds 0-200 are higher in candidate;
  5. units: our dragons alive at round 200 are higher in candidate;
  6. deaths: our extra deaths before round 300 are fewer than our extra pearls eaten in rounds 0-200.
passed = all six. Stalled dragon-rounds, how each stall ended, final lengths and wins are reported, not checked.

Exit code 0 when the measurement completed (even if passed is false); nonzero on missing or unreadable replays.
"""
import argparse, glob, hashlib, json, os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

MAX_UNITS = 6
IDLE = 30
FIRE_BY = 150
MIN_FIRED = 4
CELLS_ROUND = 200
DEATHS_ROUND = 300
EXPECTATION = ("Written before any game was run. Stall signal = our team has 6 dragons or fewer and a non-queen "
               "dragon of ours has not grown for 30+ rounds. Fired pair = the base game first shows that signal at "
               "round 150 or earlier. Expected: at least 4 fired pairs; every pair where the signal can never fire is "
               "replay-identical in base and candidate; and summed over the fired pairs the candidate has more "
               "different cells visited by our heads by round 200, more pearls eaten in rounds 0-200, more of our "
               "dragons alive at round 200, and fewer extra deaths before round 300 than extra pearls eaten.")


def metrics(path, ours):
    root = replay.load(path).root()
    result = root.pointer(4)
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None
    bodies, team_of = {}, {}
    for line in root.text(0).splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
    queens = [i for i in (0, 1) if team_of.get(i) == ours]
    if len(queens) != 1:
        raise ValueError(f'{path}: cannot identify our queen')
    queen = queens[0]
    mine = lambda i: team_of.get(i) == ours
    units = lambda: sum(1 for i in bodies if mine(i))
    grown = {i: 0 for i in bodies}
    cells = {tuple(b[0]) for i, b in bodies.items() if mine(i) and b}
    h = hashlib.sha1()
    rnd, started = 0, False
    pearls = deaths = 0
    snap = {}
    stall_300 = stall_all = queen_stall = can_fire = 0
    first_fire = None
    pending, units_min = 0, 0
    episodes, ended = {}, []

    def close_round():
        nonlocal can_fire
        if started and units_min <= MAX_UNITS:
            can_fire += pending

    def take_snaps(force=False):
        if 'cells' not in snap and (force or rnd >= CELLS_ROUND):
            snap['cells'], snap['pearls'], snap['units'] = len(cells), pearls, units()
        if 'deaths' not in snap and (force or rnd >= DEATHS_ROUND):
            snap['deaths'] = deaths

    for ev in root.pointer(3):
        kind = replay.EVENT_NAMES[ev.u16(0)] if ev.u16(0) < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if kind == 'roundStart':
            close_round()
            rnd, started = pl.i32(0), True
            h.update(f"r{rnd}".encode())
            take_snaps()
            n = units_min = units()
            pending = 0
            for i in list(bodies):
                if not mine(i):
                    continue
                idle = rnd - grown[i] >= IDLE
                if i == queen:
                    queen_stall += int(idle and n <= MAX_UNITS)
                    continue
                pending += int(idle)
                stalled = idle and n <= MAX_UNITS
                if stalled:
                    stall_all += 1
                    stall_300 += int(rnd <= DEATHS_ROUND)
                    if first_fire is None:
                        first_fire = rnd
                    episodes.setdefault(i, rnd)
                elif i in episodes:
                    start = episodes.pop(i)
                    ate = grown[i] >= start
                    ended.append(('ate' if ate else 'team_grew', (grown[i] if ate else rnd) - start))
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            head, tail = replay.point(pl.pointer(0)), replay.point(pl.pointer(1))
            h.update(f"u{did}{head}{tail}".encode())
            body = bodies.setdefault(did, deque())
            was = len(body)
            if not body or body[0] != head:
                body.appendleft(head)
            while len(body) > 1 and body[-1] != tail:
                body.pop()
            if was and len(body) > was:
                grown[did] = rnd
                if mine(did):
                    pearls += len(body) - was
            grown.setdefault(did, rnd)
            if mine(did):
                cells.add(tuple(head))
        elif kind == 'dragonSplit':
            parent, child = pl.i32(0), pl.i32(4)
            h.update(f"s{parent}{child}".encode())
            team = ('A', 'B')[pl.u16(8)]
            bodies[parent] = deque(replay.point(p) for p in pl.pointer(0))
            bodies[child] = deque(replay.point(p) for p in pl.pointer(1))
            team_of[parent] = team_of[child] = team
            grown.setdefault(parent, rnd)
            grown[child] = rnd
            if team == ours and bodies[child]:
                cells.add(tuple(bodies[child][0]))
        elif kind == 'dragonDeath':
            did = pl.i32(0)
            h.update(f"d{did}{pl.u16(4)}".encode())
            if mine(did) and did in bodies:
                deaths += 1
                if did in episodes:
                    ended.append(('died', rnd - episodes.pop(did)))
            bodies.pop(did, None)
            units_min = min(units_min, units())
    if not started:
        raise ValueError(f'{path}: no rounds in replay')
    close_round()
    take_snaps(force=True)
    ended += [('open', rnd - start) for start in episodes.values()]
    ate = [d for k, d in ended if k == 'ate']
    our_len = [len(b) for i, b in bodies.items() if mine(i)]
    their_len = [len(b) for i, b in bodies.items() if not mine(i)]
    return {'rounds': rnd, 'digest': h.hexdigest(), 'first_fire': first_fire, 'can_fire_dragon_rounds': can_fire,
            'stalled_dragon_rounds_r300': stall_300, 'stalled_dragon_rounds': stall_all,
            'queen_idle_rounds_not_counted': queen_stall,
            'cells_r200': snap['cells'], 'pearls_r200': snap['pearls'], 'units_r200': snap['units'],
            'deaths_r300': snap['deaths'], 'pearls_total': pearls, 'deaths_total': deaths,
            'stalls': len(ended), 'stalls_ate': len(ate), 'stalls_died': sum(1 for k, _ in ended if k == 'died'),
            'stalls_team_grew': sum(1 for k, _ in ended if k == 'team_grew'),
            'stalls_open_at_end': sum(1 for k, _ in ended if k == 'open'),
            'rounds_to_eat_mean': round(sum(ate) / len(ate), 1) if ate else None,
            'longest_end': max(our_len, default=0), 'their_longest_end': max(their_len, default=0),
            'units_end': len(our_len), 'win': int(winner == ours)}


def collect(directory, tag):
    out = {}
    for p in sorted(glob.glob(os.path.join(directory, f'{tag}_*.replay'))):
        stem = os.path.basename(p)[len(tag) + 1:-len('.replay')]
        m, seed, side = stem.rsplit('_', 2)
        if side not in ('0', '1'):
            raise ValueError(f'{p}: unexpected side')
        out[(m, seed, side)] = metrics(p, 'A' if side == '0' else 'B')
    return out


SUMS = ('cells_r200', 'pearls_r200', 'units_r200', 'deaths_r300', 'stalled_dragon_rounds_r300', 'stalled_dragon_rounds',
        'stalls', 'stalls_ate', 'stalls_died', 'stalls_team_grew', 'stalls_open_at_end', 'pearls_total', 'deaths_total',
        'longest_end', 'their_longest_end', 'units_end')


def tally(rows):
    out = {'games': len(rows)}
    for f in SUMS:
        out[f] = sum(x[f] for x in rows)
    out['wins_not_a_verdict'] = sum(x['win'] for x in rows)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--replays', required=True)
    ap.add_argument('--base', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    if not os.path.isdir(a.replays):
        sys.exit(f'no replay directory: {a.replays}')
    base, cand = collect(a.replays, a.base), collect(a.replays, a.candidate)
    if not base or not cand:
        sys.exit('missing replays for base or candidate')
    if set(base) != set(cand):
        odd = sorted(set(base) ^ set(cand))
        sys.exit(f'unpaired replays: {odd[:6]}')
    keys = sorted(base)
    fired = [k for k in keys if base[k]['first_fire'] is not None and base[k]['first_fire'] <= FIRE_BY]
    late = [k for k in keys if base[k]['first_fire'] is not None and base[k]['first_fire'] > FIRE_BY]
    never = [k for k in keys if base[k]['can_fire_dragon_rounds'] == 0]
    never_same = [k for k in never if base[k]['digest'] == cand[k]['digest']]
    b, c = tally([base[k] for k in fired]), tally([cand[k] for k in fired])
    more_pearls = c['pearls_r200'] - b['pearls_r200']
    more_deaths = c['deaths_r300'] - b['deaths_r300']
    checks = {'fires': len(fired) >= MIN_FIRED,
              'untouched': len(never_same) == len(never),
              'cells': c['cells_r200'] > b['cells_r200'],
              'pearls': more_pearls > 0,
              'units': c['units_r200'] > b['units_r200'],
              'deaths': more_deaths < more_pearls}
    passed = all(checks.values())
    failed = [name for name, ok in checks.items() if not ok]
    per_map = {}
    for m in sorted({k[0] for k in keys}):
        ks = [k for k in keys if k[0] == m]
        fs = [k for k in ks if k in fired]
        per_map[m] = {'pairs': len(ks), 'fired_pairs': len(fs),
                      'never_can_fire_pairs': sum(1 for k in ks if k in never),
                      'identical_pairs': sum(1 for k in ks if base[k]['digest'] == cand[k]['digest']),
                      'fired_base': tally([base[k] for k in fs]), 'fired_candidate': tally([cand[k] for k in fs]),
                      'all_base': tally([base[k] for k in ks]), 'all_candidate': tally([cand[k] for k in ks])}
    note = (f"{len(keys)} pairs; the stall signal (6 dragons or fewer, a non-queen dragon without growth for 30+ rounds) "
            f"first showed by round {FIRE_BY} in {len(fired)} base games, only later in {len(late)}, and could never "
            f"fire in {len(never)} ({len(never_same)} of those replay-identical). ")
    if fired:
        note += (f"Over the fired pairs, base vs candidate: cells visited by round 200 {b['cells_r200']} vs "
                 f"{c['cells_r200']}; pearls eaten in rounds 0-200 {b['pearls_r200']} vs {c['pearls_r200']}; our "
                 f"dragons at round 200 {b['units_r200']} vs {c['units_r200']}; our deaths before round 300 "
                 f"{b['deaths_r300']} vs {c['deaths_r300']}; stalled dragon-rounds in rounds 1-300 "
                 f"{b['stalled_dragon_rounds_r300']} vs {c['stalled_dragon_rounds_r300']}; stalls that ended by eating "
                 f"{b['stalls_ate']} of {b['stalls']} vs {c['stalls_ate']} of {c['stalls']}, by dying "
                 f"{b['stalls_died']} vs {c['stalls_died']}. ")
    if not checks['fires']:
        note += (f"Fewer than {MIN_FIRED} fired pairs, so the break-out behaviour was not measurable on these maps; "
                 "this is not evidence for or against it. ")
    note += 'All six pre-registered checks held.' if passed else 'Failed checks: ' + ', '.join(failed) + '.'
    result = {'passed': passed, 'note': note, 'expectation': EXPECTATION, 'checks': checks, 'pairs': len(keys),
              'fired_pairs': len(fired), 'late_fired_pairs': len(late), 'never_can_fire_pairs': len(never),
              'never_can_fire_identical': len(never_same),
              'identical_pairs': sum(1 for k in keys if base[k]['digest'] == cand[k]['digest']),
              'fired_base': b, 'fired_candidate': c,
              'all_base': tally([base[k] for k in keys]), 'all_candidate': tally([cand[k] for k in keys]),
              'per_map': per_map,
              'games': [{'map': k[0], 'seed': k[1], 'side': k[2], 'fired': k in fired, 'base': base[k],
                         'candidate': cand[k]} for k in keys]}
    with open(a.output, 'w') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(note)


if __name__ == '__main__':
    main()
