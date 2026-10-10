#!/usr/bin/env python3
"""Eight matched games per style against live; retain attributable ram events."""
import argparse
import json
from pathlib import Path
import pool


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=pool.HERE / 'pool-styles.md')
    p.add_argument('--hunter-spec', help='optional replacement hunter spec')
    a = p.parse_args()
    configs = json.loads((pool.HERE / 'pool.json').read_text())
    variants = {k: configs[k] for k in ('live', 'hunter', 'rammer', 'assassin')}
    if a.hunter_spec:
        variants = {'live': configs['live'], 'hunter': pool.spec(a.hunter_spec)}
    rows = pool.run(variants, {'live': configs['live']},
                    ['tower_defense', 'trophy', 'default', 'schooltime'], 1, a.out)
    lines = ['What we tried: each style vs live on four maps, seed 100, both seats.',
             'Did it work: inspect attributed kills below; eight games cannot establish general strength.',
             'Who decides: the human maintainer.', '',
             '| Style / seat | Games | Wins | Enemy queen deaths | Queen kills caused | By length ≤6 | Head-on deaths caused | By length ≤6 | Victim ≥12 | Late victim ≥12 | TLE | Runtime errors |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for tag in variants:
        for side in (None, 0, 1):
            rs = [r for r in rows if r['tag'] == tag and (side is None or r['side'] == side)]
            values = [len(rs)] + [sum(r[k] for r in rs) for k in ('win', 'enemy_queen_deaths', 'enemy_queen_kills', 'small_queen_kills', 'head_on_caused', 'small_head_on_caused', 'big_head_on_caused', 'late_big_head_on_caused', 'timeouts')] + [sum(len(r['runtime_errors']) for r in rs)]
            lines.append('| ' + ' | '.join(map(str, [tag + (' / all' if side is None else ' / ' + 'AB'[side]), *values])) + ' |')
    lines += ['', 'Caused = enemy dies head-on during our dragon’s turn; excludes enemy-initiated collisions, wall deaths and starvation.',
              'Actor length is measured at turn start. Full death events, maps, seats, seeds and source hashes are in the JSON sidecar.']
    a.out.write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
