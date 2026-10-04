#!/usr/bin/env python3
"""Card #18 mechanism check: does our queen top up late (QUEEN_TOPUP) without dying more?

usage: python3 work/card_18_check.py --replays DIRECTORY --base base --candidate candidate --output FILE
Reads kept replays DIRECTORY/<tag>_<map>_<seed>_<side>.replay and pairs them by (map, seed, side).
Our queen is the dragon with id 0 or 1 on our team. Bot logs are not needed (the batch drops them).

Expectation, written before any game was run (P300 = pairs where our queen is alive at round 300 in both):
  1. measurable: at least 6 pairs in P300;
  2. growth: more candidate than base queens in P300 finish alive at length 4 or more, and at least half of
     the candidate queens that finish alive are 4 or longer;
  3. survival: candidate queens alive at the end in P300 are at most 1 fewer than base;
  4. no late feeding death: 0 candidate queen suicides after round 300.
passed = all four. Wins are reported but are not part of the check.

Exit code 0 when the measurement completed (even if passed is false); nonzero on missing or unreadable replays.
"""
import argparse, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

LATE = 300
TARGET = 4
MIN_PAIRS = 6
SURVIVAL_SLACK = 1
EXPECTATION = ("In pairs where our queen is alive at round 300: more candidate than base queens finish alive at "
               "length 4+, at least half of the surviving candidate queens are 4+, candidate survival to the end is "
               "at most 1 game lower than base, and the candidate queen never suicides after round 300. "
               "Needs at least 6 such pairs.")


def metrics(path, ours):
    info, events, team_of = replay.parse(path)
    queens = [i for i in (0, 1) if team_of.get(i) == ours]
    if len(queens) != 1 or team_of.get(1 - queens[0]) == ours:
        raise ValueError(f'{path}: cannot identify one queen per team')
    qid = queens[0]
    start = {}
    for line in info['map'].splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            start[len(start)] = int(q[2])
    length = dict(start)
    dead = {}
    q300 = None
    peak = eaten = splits = suicides = last_round = 0
    at = {}
    for e in events:
        r = e['round']
        last_round = max(last_round, r)
        if q300 is None and r >= LATE:
            q300 = 0 if qid in dead else length.get(qid, 0)
        for mark in (400, 450):
            if mark not in at and r >= mark:
                at[mark] = 0 if qid in dead else length.get(qid, 0)
        if e['kind'] == 'update':
            if e['id'] == qid and r > LATE:
                eaten += max(0, e['length'] - length.get(qid, e['length']))
                peak = max(peak, e['length'])
            length[e['id']] = e['length']
        elif e['kind'] == 'split':
            length[e['id']] = e['parentLength']
            length[e['child']] = e['childLength']
            if e['id'] == qid and r > LATE:
                splits += 1
        elif e['kind'] == 'death':
            dead[e['id']] = (r, e['reason'])
            length.pop(e['id'], None)
        elif e['kind'] == 'action' and e['action'] == 'suicide' and e['id'] == qid and r > LATE:
            suicides += 1
    if q300 is None:
        q300 = 0
    mine = [l for i, l in length.items() if team_of.get(i) == ours]
    theirs = [l for i, l in length.items() if team_of.get(i) not in (ours, None)]
    q_end = 0 if qid in dead else length.get(qid, 0)
    their_q = 0 if (1 - qid) in dead else length.get(1 - qid, 0)
    return {'queen_id': qid, 'rounds': last_round, 'q300': q300, 'q400': at.get(400), 'q450': at.get(450),
            'q_end': q_end, 'q_peak_late': max(peak, q300 if q_end else 0), 'alive300': int(q300 > 0),
            'alive_end': int(q_end > 0), 'death_round': dead[qid][0] if qid in dead else None,
            'death_reason': dead[qid][1] if qid in dead else '', 'eaten_late': eaten, 'splits_late': splits,
            'suicides_late': suicides, 'their_q_end': their_q,
            'queen_tie': int(q_end > 0 and q_end == their_q), 'longest_end': max(mine, default=0),
            'their_longest_end': max(theirs, default=0), 'win': int(info['winner'] == ours)}


def collect(directory, tag):
    out = {}
    for p in sorted(glob.glob(os.path.join(directory, f'{tag}_*.replay'))):
        stem = os.path.basename(p)[len(tag) + 1:-len('.replay')]
        m, seed, side = stem.rsplit('_', 2)
        if side not in ('0', '1'):
            raise ValueError(f'{p}: unexpected side')
        out[(m, seed, side)] = metrics(p, 'A' if side == '0' else 'B')
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
    p300 = [k for k in keys if base[k]['alive300'] and cand[k]['alive300']]
    b = [base[k] for k in p300]
    c = [cand[k] for k in p300]
    count = lambda rows, f: sum(1 for x in rows if f(x))
    mean = lambda xs: round(sum(xs) / len(xs), 2) if xs else None
    alive_b, alive_c = count(b, lambda x: x['alive_end']), count(c, lambda x: x['alive_end'])
    long_b = count(b, lambda x: x['alive_end'] and x['q_end'] >= TARGET)
    long_c = count(c, lambda x: x['alive_end'] and x['q_end'] >= TARGET)
    suicides_c = sum(x['suicides_late'] for x in c)
    checks = {'measurable': len(p300) >= MIN_PAIRS,
              'growth': long_c > long_b and alive_c > 0 and 2 * long_c >= alive_c,
              'survival': alive_c >= alive_b - SURVIVAL_SLACK,
              'no_late_suicide': suicides_c == 0}
    passed = all(checks.values())
    both = [k for k in p300 if base[k]['alive_end'] and cand[k]['alive_end']]
    result = {
        'passed': passed,
        'expectation': EXPECTATION,
        'checks': checks,
        'pairs': len(keys),
        'pairs_queen_alive_r300': len(p300),
        'r300_state_differs': count(keys, lambda k: base[k]['q300'] != cand[k]['q300']),
        'queen_alive_end': {'base': alive_b, 'candidate': alive_c},
        'queen_alive_end_len4plus': {'base': long_b, 'candidate': long_c},
        'queen_alive_end_len3minus': {'base': alive_b - long_b, 'candidate': alive_c - long_c},
        'queen_end_length_mean_survivors': {'base': mean([x['q_end'] for x in b if x['alive_end']]),
                                            'candidate': mean([x['q_end'] for x in c if x['alive_end']])},
        'both_survive_pairs': {'n': len(both),
                               'candidate_longer': count(both, lambda k: cand[k]['q_end'] > base[k]['q_end']),
                               'equal': count(both, lambda k: cand[k]['q_end'] == base[k]['q_end']),
                               'candidate_shorter': count(both, lambda k: cand[k]['q_end'] < base[k]['q_end'])},
        'queen_pearls_after_r300': {'base': sum(x['eaten_late'] for x in b), 'candidate': sum(x['eaten_late'] for x in c)},
        'queen_splits_after_r300': {'base': sum(x['splits_late'] for x in b), 'candidate': sum(x['splits_late'] for x in c)},
        'queen_suicides_after_r300': {'base': sum(x['suicides_late'] for x in b), 'candidate': suicides_c},
        'queen_deaths_after_r300': {'base': len(p300) - alive_b, 'candidate': len(p300) - alive_c},
        'queen_ties_at_end': {'base': count(b, lambda x: x['queen_tie']), 'candidate': count(c, lambda x: x['queen_tie'])},
        'wins_all_pairs_not_a_verdict': {'base': sum(base[k]['win'] for k in keys), 'candidate': sum(cand[k]['win'] for k in keys)},
        'games': [{'map': k[0], 'seed': k[1], 'side': k[2], 'base': base[k], 'candidate': cand[k]} for k in keys],
    }
    failed = [name for name, ok in checks.items() if not ok]
    result['note'] = (
        f"{len(p300)} of {len(keys)} pairs had our queen alive at round 300. In those, queens alive at the end with "
        f"length {TARGET}+: base {long_b}, candidate {long_c}; alive at the end: base {alive_b}, candidate {alive_c}; "
        f"mean final length of surviving queens: base {result['queen_end_length_mean_survivors']['base']}, candidate "
        f"{result['queen_end_length_mean_survivors']['candidate']}; candidate queen suicides after round 300: {suicides_c}. "
        + ('All four pre-registered checks held.' if passed else 'Failed checks: ' + ', '.join(failed) + '.'))
    with open(a.output, 'w') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(result['note'])


if __name__ == '__main__':
    main()
