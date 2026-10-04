#!/usr/bin/env python3
"""Card #18 mechanism check: does our queen keep and add length late (QUEEN_TOPUP) without dying more?

usage: python3 work/card_18_check.py --replays DIRECTORY --base base --candidate candidate --output FILE
Reads kept replays DIRECTORY/<tag>_<map>_<seed>_<side>.replay and pairs them by (map, seed, side).
Our queen is the dragon with id 0 or 1 on our team. Bot logs are not needed (the batch drops them).

S is the round the switch starts: the bot's grow round (150 on maps over 1,200 cells, 300 otherwise).
E = pairs where our queen is alive at round S in both variants (the games are the same up to S).
F = pairs in E whose queen is not sealed in (kelp-closed region of 8 cells or fewer, no portal).

Expectation for the second build, written before any game of it was run:
  1. measurable: at least 6 pairs in E and at least 4 in F;
  2. fires: in at least half of E the candidate queen's path differs from base after S
     (death round, final length, pearls eaten or splits);
  3. keeps length: 0 candidate queen suicides after S in E, and at most 1 candidate queen split after S in F;
  4. growth: in F more candidate than base queens finish alive at length 4 or more, and at least half of the
     candidate queens that finish alive are 4 or longer;
  5. survival: candidate queens alive at the end in E are not fewer than base.
passed = all five. Wins are reported but are not part of the check.

Exit code 0 when the measurement completed (even if passed is false); nonzero on missing or unreadable replays.
"""
import argparse, glob, json, os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

BIG_CELLS = 1200          # AGGRESSIVE_MAX_CELLS
START_BIG, START_SMALL = 150, 300   # LEADER_GROW_ROUND_BIG, LEADER_GROW_ROUND
SEALED_MAX = 8
TARGET = 4
MIN_E, MIN_F = 6, 4
MAX_SPLITS = 1
EXPECTATION = ("S = round the switch starts (150 on maps over 1,200 cells, else 300). E = pairs with our queen alive "
               "at S; F = those in E whose queen is not sealed in a kelp-closed region of 8 cells or fewer. "
               "Expect: at least 6 pairs in E and 4 in F; the candidate queen's path differs from base after S in at "
               "least half of E; 0 candidate queen suicides after S in E and at most 1 candidate queen split after S "
               "in F; in F more candidate than base queens finish alive at length 4+ and at least half of the "
               "surviving candidate queens are 4+; candidate queens alive at the end in E are not fewer than base.")
STEPS = ((0, -1), (1, 0), (0, 1), (-1, 0))


def region(width, height, edges, start):
    span = 2 * (width + 1)

    def kind(x, y, d):
        if d == 0:
            return edges.get(y * span + x, 0)
        if d == 2:
            return edges.get((y + 1) * span + x, 0)
        if d == 3:
            return edges.get(y * span + width + 1 + x, 0)
        return edges.get(y * span + width + 1 + x + 1, 0)

    seen = {start}
    todo = deque([start])
    portal = False
    while todo and len(seen) <= SEALED_MAX:
        x, y = todo.popleft()
        for d, (dx, dy) in enumerate(STEPS):
            k = kind(x, y, d)
            if k == 2:
                portal = True
            if k != 0:
                continue
            cell = ((x + dx) % width, (y + dy) % height)
            if cell not in seen:
                seen.add(cell)
                todo.append(cell)
    return len(seen), portal


def metrics(path, ours):
    root = replay.load(path).root()
    outcome = root.pointer(4)
    winner = ('A', 'B')[outcome.u16(6)] if outcome.u16(4) == 1 else None
    lines = root.text(0).splitlines()
    width, height = (int(v) for v in lines[0].split()[1:3])
    start_round = START_BIG if width * height > BIG_CELLS else START_SMALL
    edges, bodies, team_of = {}, {}, {}
    for q in (line.split() for line in lines):
        if not q:
            continue
        if q[0] == 'EDGE':
            edges[int(q[1])] = int(q[2])
        elif q[0] == 'DRAGON':
            team_of[len(bodies)] = 'A' if int(q[1]) == 0 else 'B'
            bodies[len(bodies)] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
    queens = [i for i in (0, 1) if team_of.get(i) == ours]
    if len(queens) != 1 or team_of.get(1 - queens[0]) == ours:
        raise ValueError(f'{path}: cannot identify one queen per team')
    qid = queens[0]
    rnd = last_round = 0
    dead = {}
    at_start = None
    eaten = splits = suicides = peak = 0
    suicide_round = -1

    def length(i):
        return 0 if i in dead else len(bodies.get(i, ()))

    def snapshot():
        if qid in dead or not bodies.get(qid):
            return {'len': 0, 'cells': 0, 'sealed': False}
        size, portal = region(width, height, edges, bodies[qid][0])
        return {'len': len(bodies[qid]), 'cells': size, 'sealed': size <= SEALED_MAX and not portal}

    for event in root.pointer(3):
        kind = replay.EVENT_NAMES[event.u16(0)]
        payload = event.pointer(0)
        if kind == 'roundStart':
            rnd = payload.i32(0)
            last_round = max(last_round, rnd)
            if at_start is None and rnd > start_round:
                at_start = snapshot()
        elif kind == 'dragonUpdate':
            did = payload.i32(0)
            head, tail = replay.point(payload.pointer(0)), replay.point(payload.pointer(1))
            body = bodies.setdefault(did, deque())
            before = len(body)
            if not body or body[0] != head:
                body.appendleft(head)
            while len(body) > 1 and body[-1] != tail:
                body.pop()
            if did == qid and rnd > start_round:
                eaten += max(0, len(body) - before)
                peak = max(peak, len(body))
        elif kind == 'dragonSplit':
            parent, child = payload.i32(0), payload.i32(4)
            bodies[parent] = deque(replay.point(p) for p in payload.pointer(0))
            bodies[child] = deque(replay.point(p) for p in payload.pointer(1))
            team_of[parent] = team_of[child] = ('A', 'B')[payload.u16(8)]
            if parent == qid and rnd > start_round:
                splits += 1
        elif kind == 'dragonAction':
            action = payload.pointer(0)
            if payload.i32(0) == qid and action is not None and action.u16(0) == 2:
                suicide_round = rnd
                if rnd > start_round:
                    suicides += 1
        elif kind == 'dragonDeath':
            did = payload.i32(0)
            reason = payload.u16(4)
            dead[did] = (rnd, replay.DEATH_REASONS[reason] if reason < 5 else '?')
    if at_start is None:
        at_start = snapshot()
    mine = [len(b) for i, b in bodies.items() if i not in dead and team_of.get(i) == ours]
    theirs = [len(b) for i, b in bodies.items() if i not in dead and team_of.get(i) not in (ours, None)]
    q_end, their_q = length(qid), length(1 - qid)
    return {'queen_id': qid, 'cells': width * height, 'start_round': start_round, 'rounds': last_round,
            'len_start': at_start['len'], 'alive_start': int(at_start['len'] > 0), 'region_cells': at_start['cells'],
            'sealed': int(at_start['sealed']), 'q_end': q_end, 'alive_end': int(q_end > 0),
            'q_peak_after_start': max(peak, at_start['len']), 'death_round': dead[qid][0] if qid in dead else None,
            'death_reason': dead[qid][1] if qid in dead else '',
            'death_by_suicide': int(qid in dead and dead[qid][0] == suicide_round),
            'eaten_after_start': eaten, 'splits_after_start': splits, 'suicides_after_start': suicides,
            'their_q_end': their_q, 'queen_tie': int(q_end > 0 and q_end == their_q),
            'longest_end': max(mine, default=0), 'their_longest_end': max(theirs, default=0),
            'win': int(winner == ours)}


def collect(directory, tag):
    out = {}
    for p in sorted(glob.glob(os.path.join(directory, f'{tag}_*.replay'))):
        stem = os.path.basename(p)[len(tag) + 1:-len('.replay')]
        m, seed, side = stem.rsplit('_', 2)
        if side not in ('0', '1'):
            raise ValueError(f'{p}: unexpected side')
        out[(m, seed, side)] = metrics(p, 'A' if side == '0' else 'B')
    return out


def path_of(x):
    return (x['death_round'], x['q_end'], x['eaten_after_start'], x['splits_after_start'])


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
    in_e = [k for k in keys if base[k]['alive_start'] and cand[k]['alive_start']]
    in_f = [k for k in in_e if not base[k]['sealed']]
    count = lambda rows, f: sum(1 for x in rows if f(x))
    mean = lambda xs: round(sum(xs) / len(xs), 2) if xs else None

    def side(group, rows):
        picked = [rows[k] for k in group]
        alive = count(picked, lambda x: x['alive_end'])
        long_ = count(picked, lambda x: x['alive_end'] and x['q_end'] >= TARGET)
        return {'alive_end': alive, 'alive_end_len4plus': long_, 'alive_end_len3minus': alive - long_,
                'end_length_mean_survivors': mean([x['q_end'] for x in picked if x['alive_end']]),
                'peak_length_mean': mean([x['q_peak_after_start'] for x in picked]),
                'pearls_after_start': sum(x['eaten_after_start'] for x in picked),
                'splits_after_start': sum(x['splits_after_start'] for x in picked),
                'suicides_after_start': sum(x['suicides_after_start'] for x in picked),
                'deaths_after_start': len(picked) - alive,
                'queen_ties_at_end': count(picked, lambda x: x['queen_tie'])}

    e = {'base': side(in_e, base), 'candidate': side(in_e, cand)}
    f = {'base': side(in_f, base), 'candidate': side(in_f, cand)}
    differ = count(in_e, lambda k: path_of(base[k]) != path_of(cand[k]))
    checks = {'measurable': len(in_e) >= MIN_E and len(in_f) >= MIN_F,
              'fires': bool(in_e) and 2 * differ >= len(in_e),
              'keeps_length': e['candidate']['suicides_after_start'] == 0 and f['candidate']['splits_after_start'] <= MAX_SPLITS,
              'growth': f['candidate']['alive_end_len4plus'] > f['base']['alive_end_len4plus'] and
                        f['candidate']['alive_end'] > 0 and
                        2 * f['candidate']['alive_end_len4plus'] >= f['candidate']['alive_end'],
              'survival': e['candidate']['alive_end'] >= e['base']['alive_end']}
    passed = all(checks.values())
    both = [k for k in in_e if base[k]['alive_end'] and cand[k]['alive_end']]
    result = {
        'passed': passed,
        'expectation': EXPECTATION,
        'checks': checks,
        'pairs': len(keys),
        'pairs_queen_alive_at_start': len(in_e),
        'pairs_queen_alive_at_start_not_sealed': len(in_f),
        'start_state_differs': count(keys, lambda k: (base[k]['len_start'], base[k]['sealed']) != (cand[k]['len_start'], cand[k]['sealed'])),
        'pairs_path_differs_after_start': differ,
        'alive_at_start': e,
        'alive_at_start_not_sealed': f,
        'both_survive_pairs': {'n': len(both),
                               'candidate_longer': count(both, lambda k: cand[k]['q_end'] > base[k]['q_end']),
                               'equal': count(both, lambda k: cand[k]['q_end'] == base[k]['q_end']),
                               'candidate_shorter': count(both, lambda k: cand[k]['q_end'] < base[k]['q_end'])},
        'wins_all_pairs_not_a_verdict': {'base': sum(base[k]['win'] for k in keys), 'candidate': sum(cand[k]['win'] for k in keys)},
        'games': [{'map': k[0], 'seed': k[1], 'side': k[2], 'base': base[k], 'candidate': cand[k]} for k in keys],
    }
    failed = [name for name, ok in checks.items() if not ok]
    result['note'] = (
        f"{len(in_e)} of {len(keys)} pairs had our queen alive when the switch starts, {len(in_f)} of them not sealed in. "
        f"Her path differs from base in {differ} of {len(in_e)}. Not-sealed queens alive at the end with length {TARGET}+: "
        f"base {f['base']['alive_end_len4plus']}, candidate {f['candidate']['alive_end_len4plus']}; alive at the end "
        f"(all {len(in_e)}): base {e['base']['alive_end']}, candidate {e['candidate']['alive_end']}; mean final length of "
        f"surviving not-sealed queens: base {f['base']['end_length_mean_survivors']}, candidate "
        f"{f['candidate']['end_length_mean_survivors']}; candidate queen suicides after the start: "
        f"{e['candidate']['suicides_after_start']}, splits (not sealed): {f['candidate']['splits_after_start']}. "
        + ('All five pre-registered checks held.' if passed else 'Failed checks: ' + ', '.join(failed) + '.'))
    with open(a.output, 'w') as out:
        json.dump(result, out, indent=2)
        out.write('\n')
    print(result['note'])


if __name__ == '__main__':
    main()
