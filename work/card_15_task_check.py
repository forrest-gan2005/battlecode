#!/usr/bin/env python3
"""Card #15 check: our sonar messages round-trip, and forged or unkeyed ones are rejected.

usage: python3 work/card_15_task_check.py --output OUT.json [--trials N] [--replays IDENT_DIR]
Compiles work/card_15_sonar_test.cpp against mybot2/sonar_codec.hpp (the codec the bot ships), runs it, and
checks that mybot2/main.cpp sends and receives every sonar message through that codec.
With --replays (the identity check's replay directory) it also opens every message the new bot sent in those
games and compares it with the message the previous version sent at the same point of the same game.
"""
import argparse, glob, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import replay

MIN_REJECT = 0.99
KINDS = {0xA5: 'mouth', 0x5A: 'sight', 0x3C: 'zone'}


def pings(path):
    root = replay.load(path).root()
    size = next(l.split()[1:3] for l in root.text(0).splitlines() if l.startswith('MAP '))
    rows = []
    for ev in root.pointer(3):
        if ev.u16(0) < len(replay.EVENT_NAMES) and replay.EVENT_NAMES[ev.u16(0)] == 'sonarPing':
            pl = ev.pointer(0)
            rows.append((pl.u64(0), pl.u64(8), pl.u64(24), pl.u64(16)))
    return size, rows


def in_game(directory, binary):
    """Pair each candidate replay with the base-vs-base replay of the same map and seed."""
    lines = set()
    kinds = {'leader': 0, 'mouth': 0, 'sight': 0, 'zone': 0, 'other': 0}
    games = total = 0
    for ref_path in sorted(glob.glob(os.path.join(directory, 'refbase_*.replay'))):
        size, ref = pings(ref_path)
        for side, tag in (('A', 2), ('B', 1)):
            path = ref_path.replace('refbase_', f'candidate{side}_')
            if not os.path.exists(path):
                raise ValueError(f'missing {os.path.basename(path)}')
            cand = pings(path)[1]
            if len(cand) != len(ref) or any(c[:3] != r[:3] for c, r in zip(cand, ref)):
                raise ValueError(f'sonar events differ from base in {os.path.basename(path)}')
            games += 1
            total += len(ref)
            for c, r in zip(cand, ref):
                mine = ((r[3] >> 53) & 0x3) == tag
                lines.add(f"{'S' if mine else 'F'} {size[0]} {size[1]} {tag} {c[3]} {r[3]}")
                if mine:
                    kind = 'leader' if r[3] >> 63 == 0 else KINDS.get((r[3] >> 38) & 0x7FFF, 'other')
                    kinds[kind] += 1
    # Bots repeat the same message in several directions and rounds; count each distinct one once.
    raw = subprocess.run([binary, 'replay'], input='\n'.join(sorted(lines)) + '\n', check=True, capture_output=True,
                         text=True, timeout=600).stdout
    return {'games': games, 'sonar_events': total, **json.loads(raw), 'sent_events_by_kind': kinds}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', required=True)
    ap.add_argument('--trials', type=int, default=200000)
    ap.add_argument('--replays')
    a = ap.parse_args()
    out_dir = os.path.dirname(os.path.abspath(a.output))
    os.makedirs(out_dir, exist_ok=True)
    binary = os.path.join(out_dir, 'card_15_sonar_test')
    result = {'passed': False, 'note': 'the sonar codec check did not run'}
    try:
        subprocess.run(['c++', '-std=c++20', '-O2', os.path.join(HERE, 'card_15_sonar_test.cpp'), '-o', binary],
                       check=True, timeout=600)
        raw = subprocess.run([binary, str(a.trials)], check=True, capture_output=True, text=True, timeout=600).stdout
        m = json.loads(raw)
        n = m['trials']
        source = open(os.path.join(ROOT, 'mybot2', 'main.cpp')).read()
        wiring = {'old_checksum_uses': source.count('sonar_checksum'),
                  'seal_calls': source.count('sonar_codec::seal(sonar_key, '),
                  'open_calls': source.count('sonar_codec::open(sonar_key, '),
                  'pack_functions': sum(source.count(f' pack_{k}(') > 0 for k in ('leader', 'mouth', 'sight', 'zone'))}
        reject = {k: round(1 - v / n, 5) for k, v in m['forgery_accepted'].items()}
        reject['every_flip'] = round(1 - m['every_flip']['accepted'] / m['every_flip']['tried'], 5)
        failures = []
        failures += [f'{k} round trip {v}/{n}' for k, v in m['round_trip'].items() if v != n]
        failures += [f'{k} forgeries rejected only {v:.2%}' for k, v in reject.items() if v < MIN_REJECT]
        if m['tag_kept'] != 5 * n:
            failures.append('team tag bits changed on the wire')
        if not 0.45 <= m['scrambled_bit_fraction'] <= 0.55:
            failures.append(f"body bits not scrambled ({m['scrambled_bit_fraction']})")
        if m['keys']['distinct'] != m['keys']['made']:
            failures.append('two map sizes or teams share a key')
        if wiring != {'old_checksum_uses': 0, 'seal_calls': 4, 'open_calls': 1, 'pack_functions': 4}:
            failures.append(f'main.cpp does not route all sonar messages through the codec: {wiring}')
        games = 'not measured (no --replays)'
        seen = ''
        limits = 'random tests are codec-level; the 8-bit check lets about 1 in 256 blind forgeries through'
        if a.replays:
            games = in_game(a.replays, binary)
            if games['sent'] == 0 or games['sent_decode_to_old_message'] != games['sent']:
                failures.append(f"in-game messages: {games['sent_decode_to_old_message']}/{games['sent']} decode to "
                                'the previous version\'s message')
            if games['foreign_unchanged'] != games['foreign']:
                failures.append('the previous version on the other team sent different messages than in its own game')
            if games['foreign_pass_check_and_tag'] != 0:
                failures.append(f"{games['foreign_pass_check_and_tag']} unkeyed in-game messages were accepted")
            seen = (f"; in the {games['games']} identity games all {games['sent']} distinct messages the new bot sent "
                    "decode to exactly what the previous version sent, and none of the "
                    f"{games['foreign']} distinct unkeyed messages from the other team are accepted")
            unseen = [k for k in ('leader', 'mouth', 'sight', 'zone') if not games['sent_events_by_kind'][k]]
            if unseen:
                limits += f"; no {'/'.join(unseen)} messages occur in these games, so only the random tests cover them"
        worst = min(reject.values())
        result = {'passed': not failures,
                  'note': (f'our sonar messages decode back exactly for every kind (leader, mouth, sight, zone; {n} random '
                           f'bodies each) and at least {worst:.2%} of forgeries in every class (old XOR scheme, wrong '
                           f'key, flipped bits, random values) are rejected{seen}'
                           if not failures else 'the sonar codec check FAILED: ' + '; '.join(failures)),
                  'trials_per_class': n, 'round_trip_ok': m['round_trip'], 'forgery_reject_rate': reject,
                  'forgery_accepted': m['forgery_accepted'], 'every_flip': m['every_flip'],
                  'scrambled_bit_fraction': m['scrambled_bit_fraction'], 'keys': m['keys'], 'wiring': wiring,
                  'in_game': games,
                  'limits': limits}
    except Exception as exc:
        result = {'passed': False, 'note': f'the sonar codec check could not finish: {exc}'}
    with open(a.output, 'w') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
