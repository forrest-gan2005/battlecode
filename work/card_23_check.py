#!/usr/bin/env python3
"""Card #23 mechanism check: does our queen stop dying by her own move (QUEEN_NO_TRAP)?

usage: python3 work/card_23_check.py --replays DIRECTORY --base base --candidate candidate --output FILE
Reads kept replays DIRECTORY/<tag>_<map>_<seed>_<side>.replay and pairs them by (map, seed, side).
Our queen is the dragon with id 0 or 1 on our team. Bot logs are not needed (the batch drops them).

How a queen death is classed:
  feed      her own last action was "suicide" in the round she died (she fed herself to our leader);
  head_on   an enemy head and hers collided;
  self      anything else: wall, her own body, another dragon's body, or no valid move.
"after split" = a self death at most one round after the queen herself split.
"after pearl" = a death at most 3 rounds after her length last grew.
"long" = she was 6 or longer before the death (before the split, when she split right before dying).
"queen rules on" = maps over 600 cells, where the live settings treat her as the queen.

Expectation, written before any game was run (all counts are over every pair):
  1. measurable: the base queen has at least 3 self deaths;
  2. drop: candidate self deaths are at most half of base;
  3. after split: at most 1 candidate self death comes right after a queen split;
  4. not traded: candidate self + head_on deaths are fewer than base self + head_on deaths.
passed = all four. Everything else (feeding deaths, deaths after a pearl, long-queen deaths, queen length, pearls,
wipe-outs, timeouts, wins, the split by map size) is reported but is not part of the check.

Exit code 0 when the measurement completed (even if passed is false); nonzero on missing or unreadable replays.
"""
import argparse, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

MID = 300
MIN_BASE_SELF = 3
MAX_AFTER_SPLIT = 1
PEARL_WINDOW = 3
LONG = 6
QUEEN_MIN_CELLS = 600
REASONS = dict(zip(replay.DEATH_REASONS, ('wall', 'own_body', 'other_body', 'head_on', 'no_move')))
SELF = ('wall', 'own_body', 'other_body', 'no_move')
EXPECTATION = ("Over all pairs: the base queen dies by her own move (wall, own body, another body, no move; feeding "
               "suicides excluded) at least 3 times; the candidate queen does so at most half as often; at most 1 "
               "candidate death of that kind comes right after a queen split; and candidate own-move plus head-on "
               "deaths together are fewer than base.")


def metrics(path, ours):
    info, events, team_of = replay.parse(path)
    queens = [i for i in (0, 1) if team_of.get(i) == ours]
    if len(queens) != 1 or team_of.get(1 - queens[0]) in (ours, None):
        raise ValueError(f'{path}: cannot identify one queen per team')
    qid = queens[0]
    length = {}
    cells = 0
    for line in info['map'].splitlines():
        q = line.split()
        if q and q[0] == 'MAP':
            cells = int(q[1]) * int(q[2])
        elif q and q[0] == 'DRAGON':
            length[len(length)] = int(q[2])
    if cells <= 0:
        raise ValueError(f'{path}: no map size')
    q_mid = None
    last_round = eaten = splits = queen_tle = team_tle = 0
    q_max = length.get(qid, 0)
    last_action = (None, -1)
    last_split = (-10, 0, 0)
    last_eat = -10
    death = None
    their_death = None
    for e in events:
        r = e['round']
        last_round = max(last_round, r)
        if q_mid is None and r >= MID:
            q_mid = 0 if death else length.get(qid, 0)
        if e['kind'] == 'update':
            if e['id'] == qid:
                grown = e['length'] - length.get(qid, e['length'])
                if grown > 0:
                    eaten += grown
                    last_eat = r
                q_max = max(q_max, e['length'])
            length[e['id']] = e['length']
        elif e['kind'] == 'split':
            if e['id'] == qid:
                splits += 1
                last_split = (r, e['parentLength'], length.get(qid, e['parentLength'] + e['childLength']))
            length[e['id']] = e['parentLength']
            length[e['child']] = e['childLength']
        elif e['kind'] == 'action':
            if e['id'] == qid:
                last_action = (e['action'], r)
                queen_tle += int(bool(e.get('tle')))
            if team_of.get(e['id']) == ours:
                team_tle += int(bool(e.get('tle')))
        elif e['kind'] == 'death':
            if e['id'] == qid and death is None:
                reason = REASONS.get(e['reason'], 'unknown')
                kind = ('feed' if last_action == ('suicide', r) else 'head_on' if reason == 'head_on'
                        else 'self' if reason in SELF else 'unknown')
                after_split = int(r - last_split[0] <= 1)
                now = length.get(qid, 0)
                death = {'round': r, 'reason': reason, 'kind': kind, 'length': now,
                         'after_split': after_split, 'split_left': last_split[1],
                         'length_before': last_split[2] if after_split else now,
                         'after_pearl': int(r - last_eat <= PEARL_WINDOW)}
            elif e['id'] == 1 - qid and their_death is None:
                their_death = r
            length.pop(e['id'], None)
    if q_mid is None:
        q_mid = 0 if death else length.get(qid, 0)
    mine = [l for i, l in length.items() if team_of.get(i) == ours]
    theirs = [l for i, l in length.items() if team_of.get(i) not in (ours, None)]
    return {'queen_id': qid, 'rounds': last_round, 'cells': cells, 'rules_on': int(cells > QUEEN_MIN_CELLS),
            'alive_end': int(death is None),
            'death_round': death['round'] if death else None, 'death_reason': death['reason'] if death else '',
            'death_kind': death['kind'] if death else '', 'death_length': death['length'] if death else None,
            'length_before': death['length_before'] if death else None,
            'after_split': death['after_split'] if death else 0, 'split_left': death['split_left'] if death else None,
            'after_pearl': death['after_pearl'] if death else 0,
            'q_max': q_max, 'q_mid': q_mid, 'q_end': 0 if death else length.get(qid, 0), 'eaten': eaten,
            'splits': splits, 'rounds_alive': death['round'] if death else last_round,
            'queen_tle': queen_tle, 'team_tle': team_tle,
            'their_queen_alive_end': int(their_death is None), 'longest_end': max(mine, default=0),
            'their_longest_end': max(theirs, default=0), 'total_end': sum(mine), 'their_total_end': sum(theirs),
            'wiped': int(not mine), 'their_wiped': int(not theirs), 'win': int(info['winner'] == ours)}


def collect(directory, tag):
    out = {}
    for p in sorted(glob.glob(os.path.join(directory, f'{tag}_*.replay'))):
        stem = os.path.basename(p)[len(tag) + 1:-len('.replay')]
        m, seed, side = stem.rsplit('_', 2)
        if side not in ('0', '1'):
            raise ValueError(f'{p}: unexpected side')
        out[(m, seed, side)] = metrics(p, 'A' if side == '0' else 'B')
    return out


def mean(values):
    values = list(values)
    return round(sum(values) / len(values), 2) if values else None


def tally(rows):
    count = lambda f: sum(1 for x in rows if f(x))
    self_rows = [x for x in rows if x['death_kind'] == 'self']
    head_rows = [x for x in rows if x['death_kind'] == 'head_on']
    rounds = sum(x['rounds_alive'] for x in rows)
    return {'games': len(rows),
            'alive_end': count(lambda x: x['alive_end']),
            'self': len(self_rows),
            'self_by_reason': {k: sum(1 for x in self_rows if x['death_reason'] == k) for k in SELF},
            'self_after_split': sum(x['after_split'] for x in self_rows),
            'self_after_split_left2': sum(1 for x in self_rows if x['after_split'] and x['split_left'] == 2),
            'self_after_pearl': sum(x['after_pearl'] for x in self_rows),
            'self_long': sum(1 for x in self_rows if x['length_before'] >= LONG),
            'self_within_100_rounds': sum(1 for x in self_rows if x['death_round'] <= 100),
            'head_on': len(head_rows),
            'head_on_after_pearl': sum(x['after_pearl'] for x in head_rows),
            'feed': count(lambda x: x['death_kind'] == 'feed'),
            'unknown': count(lambda x: x['death_kind'] == 'unknown'),
            'alive_mid': count(lambda x: x['q_mid'] > 0),
            'q_mid_mean_alive': mean(x['q_mid'] for x in rows if x['q_mid'] > 0),
            'q_end_mean_alive': mean(x['q_end'] for x in rows if x['alive_end']),
            'q_max_mean': mean(x['q_max'] for x in rows),
            'rounds_alive_mean': mean(x['rounds_alive'] for x in rows),
            'pearls': sum(x['eaten'] for x in rows),
            'pearls_per_100_rounds_alive': round(100.0 * sum(x['eaten'] for x in rows) / max(1, rounds), 2),
            'queen_splits': sum(x['splits'] for x in rows),
            'queen_tle': sum(x['queen_tle'] for x in rows),
            'team_tle': sum(x['team_tle'] for x in rows),
            'longest_end_mean': mean(x['longest_end'] for x in rows),
            'their_longest_end_mean': mean(x['their_longest_end'] for x in rows),
            'total_end_mean': mean(x['total_end'] for x in rows),
            'their_total_end_mean': mean(x['their_total_end'] for x in rows),
            'wiped': sum(x['wiped'] for x in rows),
            'their_wiped': sum(x['their_wiped'] for x in rows),
            'their_queen_alive_end': sum(x['their_queen_alive_end'] for x in rows),
            'wins_not_a_verdict': sum(x['win'] for x in rows)}


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
    b, c = tally([base[k] for k in keys]), tally([cand[k] for k in keys])
    checks = {'measurable': b['self'] >= MIN_BASE_SELF,
              'drop': 2 * c['self'] <= b['self'],
              'after_split': c['self_after_split'] <= MAX_AFTER_SPLIT,
              'not_traded': c['self'] + c['head_on'] < b['self'] + b['head_on']}
    passed = all(checks.values())
    per_map = {}
    for m in sorted({k[0] for k in keys}):
        ks = [k for k in keys if k[0] == m]
        per_map[m] = {'cells': base[ks[0]]['cells'], 'base': tally([base[k] for k in ks]),
                      'candidate': tally([cand[k] for k in ks])}
    by_rules = {}
    for name, flag in (('queen_rules_on', 1), ('queen_rules_off', 0)):
        ks = [k for k in keys if base[k]['rules_on'] == flag]
        if ks:
            by_rules[name] = {'base': tally([base[k] for k in ks]), 'candidate': tally([cand[k] for k in ks])}
    failed = [name for name, ok in checks.items() if not ok]
    same_fate = sum(1 for k in keys if (base[k]['death_round'], base[k]['death_reason'])
                    == (cand[k]['death_round'], cand[k]['death_reason']))
    note = (f"{len(keys)} pairs. Queen deaths by her own move (wall, own body, another body, no move): base {b['self']}, "
            f"candidate {c['self']}; of those right after a queen split: base {b['self_after_split']}, candidate "
            f"{c['self_after_split']}; within {PEARL_WINDOW} rounds of eating a pearl: base {b['self_after_pearl']}, "
            f"candidate {c['self_after_pearl']}; at length {LONG} or more: base {b['self_long']}, candidate "
            f"{c['self_long']}. Head-on deaths: base {b['head_on']}, candidate {c['head_on']} (after a pearl: base "
            f"{b['head_on_after_pearl']}, candidate {c['head_on_after_pearl']}); feeding suicides: base {b['feed']}, "
            f"candidate {c['feed']}; queen alive at the end: base {b['alive_end']}, candidate {c['alive_end']}; queen "
            f"pearls per 100 rounds alive: base {b['pearls_per_100_rounds_alive']}, candidate "
            f"{c['pearls_per_100_rounds_alive']}; queen timeouts: base {b['queen_tle']}, candidate {c['queen_tle']}. "
            f"Pairs where the queen met the same fate (round and cause) in both: {same_fate} of {len(keys)}. "
            + ('All four pre-registered checks held.' if passed else 'Failed checks: ' + ', '.join(failed) + '.'))
    result = {'passed': passed, 'note': note, 'expectation': EXPECTATION, 'checks': checks, 'pairs': len(keys),
              'identical_queen_fate_pairs': same_fate,
              'base': b, 'candidate': c, 'per_map': per_map, 'by_queen_rules': by_rules,
              'games': [{'map': k[0], 'seed': k[1], 'side': k[2], 'base': base[k], 'candidate': cand[k]} for k in keys]}
    with open(a.output, 'w') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(note)


if __name__ == '__main__':
    main()
