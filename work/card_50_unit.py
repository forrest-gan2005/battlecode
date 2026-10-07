#!/usr/bin/env python3
"""Card #50 revenge-hunt unit test: drives a QH_REVENGE_LONG=true build and the build as it is, one turn at a time.

usage: python3 work/card_50_unit.py --out DIR [--source mybot2]
No engine and no games: card #31's driver writes the turn input a dragon would get and reads its SONAR lines.
The board is 100x100 and empty, so a dragon can walk 60 rounds to a relayed cell without reaching it.
It builds DIR/rl-on (the source with the switch on) and DIR/rl-off (the source untouched) and checks for how
many rounds a dragon keeps hunting on one sighting. Exit code 0 when every case holds.
"""
import argparse, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import card_31_unit as unit

unit.W, unit.H = 100, 100
unit.KEY = unit.codec.make_key(unit.W, unit.H, unit.TAG)
FAR = (55, 40)
BOSS = (80, 80)


def hunted(log):
    return [r for r in sorted(log) if log[r]['pings']]


def run(binary, length, rounds, sighting, state=1, target=FAR, queen_at=None):
    """One dragon (id 9) told about the leader every round; `sighting` = (round heard, round she was seen)."""
    me = unit.Dragon(binary, 9, unit.line((10, 10), 'E', length))
    log = {}
    for rnd in rounds:
        wires = [unit.leader(4, 12, rnd, BOSS, state)]
        if rnd == sighting[0]:
            wires.append(unit.ping(7, target, sighting[1], state=state))
        others = {}
        if queen_at is not None and rnd == queen_at:
            others = {0: ('A', unit.line((me.body[0][0], (me.body[0][1] + 2) % unit.H), 'W', 3))}
        before = me.body[0]
        log[rnd] = me.turn(rnd, others, wires=wires)
        log[rnd]['before'] = before
    me.close()
    return log


def cases(on, off):
    results = []

    def check(name, ok, detail=''):
        results.append((name, bool(ok), str(detail)))

    # 1. Our queen is dead, round 100+, her cell 75 steps away, heard once: 60 rounds with the switch, 20 without.
    log = run(on, 3, range(100, 166), (100, 99))
    check('switch on: hunts while the sighting is 60 rounds old or less', hunted(log) == list(range(100, 160)),
          hunted(log))
    check('switch on: every ping keeps the round she was seen and her cell',
          all(p['id'] == 9 and p['when'] == 99 and p['cell'] == unit.cell_of(FAR) and p['state'] == 1 and not p['dead']
              for r in log for p in log[r]['pings']), log[130]['pings'])
    closer = sum(1 for r in range(100, 160) if unit.dist(log[r]['head'], FAR) < unit.dist(log[r]['before'], FAR))
    check('switch on: the hunter walks towards her cell all that time', closer >= 55, closer)
    log = run(off, 3, range(100, 126), (100, 99))
    check('switch off: hunts for 20 rounds as now', hunted(log) == list(range(100, 120)), hunted(log))

    # 2. Before round 100 nothing changes; from round 100 a sighting it could not use before counts if 60 or less old.
    log = run(on, 3, range(60, 126), (60, 59))
    check('switch on: no revenge hunt before round 100, then until the sighting is 61 rounds old',
          hunted(log) == list(range(100, 120)), hunted(log))
    log = run(off, 3, range(60, 126), (60, 59))
    check('switch off: a sighting 41 rounds old is never used', hunted(log) == [], hunted(log))

    # 3. Nobody said our queen is dead: no hunt on a relayed sighting, old or new.
    log = run(on, 3, range(100, 106), (100, 75), state=0)
    check('switch on: our queen not known dead, no hunt', hunted(log) == [], hunted(log))

    # 4. Our queen shows up alive: back to 20 rounds at once, and it stays so after she leaves the view.
    log = run(on, 3, range(100, 106), (100, 75), queen_at=102)
    check('switch on: our queen seen alive, a 27-round-old sighting is dropped', hunted(log) == [100, 101], hunted(log))

    # 5. Only dragons of 4 or less: a dragon of 5 never hunts, a dragon of 4 does.
    log = run(on, 5, range(100, 104), (100, 75))
    check('switch on: length 5 does not hunt', hunted(log) == [], hunted(log))
    log = run(on, 4, range(100, 104), (100, 75))
    check('switch on: length 4 hunts', hunted(log) == list(range(100, 104)), hunted(log))

    # 6. Her cell 30 steps away: with the switch the hunter gets there, finds it empty and stands down for good.
    near = (40, 10)
    log = run(on, 3, range(100, 141), (100, 99), target=near)
    last = max(hunted(log), default=None)
    check('switch on: reaches a cell 30 steps away', last is not None and unit.dist(log[last]['head'], near) <= 1,
          (last, log[last]['head'] if last else None))
    check('switch on: stands down at her empty cell though the sighting is under 60 rounds old',
          last is not None and last < 135 and hunted(log) == list(range(100, last + 1)), hunted(log))
    log = run(off, 3, range(100, 141), (100, 99), target=near)
    last = max(hunted(log), default=None)
    check('switch off: gives up 20 rounds in, still short of her cell',
          last == 119 and unit.dist(log[last]['head'], near) > 1, (last, log[last]['head'] if last else None))
    return results


def build(source, out, name, switch):
    dst = os.path.join(out, name)
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    for other in os.listdir(source):
        if other != 'main.cpp' and other.endswith(('.hpp', '.h', '.toml')):
            shutil.copy(os.path.join(source, other), dst)
    text = open(os.path.join(source, 'main.cpp')).read()
    assert len(re.findall(r'constexpr bool QH_REVENGE_LONG = false;', text)) == 1, 'QH_REVENGE_LONG must be default off'
    if switch:
        text = text.replace('constexpr bool QH_REVENGE_LONG = false;', 'constexpr bool QH_REVENGE_LONG = true;')
    open(os.path.join(dst, 'main.cpp'), 'w').write(text)
    binary = os.path.join(dst, 'bot')
    subprocess.run(['c++', '-std=c++20', '-O2', os.path.join(dst, 'main.cpp'), '-o', binary], check=True)
    return binary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--source', default=os.path.join(os.path.dirname(HERE), 'mybot2'))
    a = ap.parse_args()
    results = cases(build(a.source, a.out, 'rl-on', True), build(a.source, a.out, 'rl-off', False))
    for name, ok, detail in results:
        print(('OK   ' if ok else 'FAIL ') + name + ('' if ok else '  ' + detail[:600]))
    bad = sum(1 for _, ok, _ in results if not ok)
    print(f'{len(results) - bad} of {len(results)} cases hold')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
