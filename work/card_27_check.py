#!/usr/bin/env python3
"""Card #27 mechanism check: do short dragons leave a walled start room through its one-wide exit (TERRAIN_PASSAGE)?

usage: python3 work/card_27_check.py --replays DIRECTORY --base base --candidate candidate --output FILE
Reads kept replays DIRECTORY/<tag>_<map>_<seed>_<side>.replay and pairs them by (map, seed, side).
Bot logs are not needed (the batch drops them). Terrain is read from the map inside each replay, never from its name.

Terms (all from the map's open edges; portal links are left out):
  bridge         an open edge whose removal cuts the map in two: the step through a one-wide passage or doorway.
  room / area    cells joined without crossing a bridge. An area has 4+ cells (a dragon can turn around there).
  loop-free cell a cell whose room has fewer than 4 cells: a one-wide corridor or dead end.
  start room     the rooms our dragons start in.
  walled start   the start room holds at most 25% of the map, touches no portal, and a bridge leads on to an area.
  open map       no bridge and no portal anywhere.
  maze-like map  at least 25% of the enterable cells are loop-free.
  home share     of all our dragon-rounds in rounds 100-199 (one dragon alive at one round start), the share whose
                 head is inside the start room. If the game ends before round 100, the whole game is used.
  target pair    a walled-start pair whose base game has a home share of 0.5 or more: our dragons mostly stay in.
                 This is the pin the card describes.

Expectation, written before any game was run with the switch on:
  1. target_seen: at least 4 target pairs;
  2. fires: in at least 75% of the target pairs the candidate's home share is at most half of the base's;
  3. goes_through: in at least 75% of the target pairs a candidate head stands in another area by round 100;
  4. cells: summed over the target pairs, the candidate's heads visit more different cells by round 100;
  5. growth: summed over the target pairs, the candidate eats more pearls by round 200 or has more dragons at round 100;
  6. deaths: summed over all pairs, our extra deaths before round 200 are not more than our extra pearls by round 200;
  7. dead_ends: on maze-like maps, extra deaths of our short (length 4 or less) dragons on loop-free cells before
     round 200 are not more than our extra pearls by round 200 there;
  8. open_identical: every open-map pair is replay-identical in base and candidate.
passed = all eight (7 and 8 hold trivially when the run has no such map, and the note says so).
Reported, not checked: the first round one of our heads is outside the start room and whether that meets the card's
timing (20 rounds where the bot's centre pull is off, 15 rounds after it ends where it is on; the pull's map-size
rule is copied from the bot's CENTER_* constants), queen deaths, stalled dragon-rounds (the #24 counter with the queen
included: our team has 6 dragons or fewer and a dragon has not grown for 30+ rounds), final lengths and wins.
Not measurable here: transposed or mirrored copies of a map (the loop's outcome run covers those).

Exit code 0 when the measurement completed (even if passed is false); nonzero on missing or unreadable replays.
"""
import argparse, glob, hashlib, json, os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

ROOM_SHARE = 0.25
AREA_MIN = 4
MAZE_SHARE = 0.25
WINDOW = (100, 200)
PIN_SHARE = 0.5
CELLS_ROUND = 100
PEARLS_ROUND = 200
SHORT = 4
MIN_TARGET = 4
SHARE_NEEDED = 0.75
STALL_UNITS = 6
STALL_IDLE = 30
CAUSES = ('wall', 'own_body', 'other_body', 'head_on', 'no_move')
EXPECTATION = ("Written before any game was run with the switch on. Rooms are found from each replay's map: cells "
               "joined without crossing a one-wide step (bridge). Home share = the share of our dragon-rounds in "
               "rounds 100-199 spent with the head inside our start room. Target pair = our start room holds at most "
               "25% of the map, has no portal, a one-wide exit leads to an area of 4+ cells, and the base game's home "
               "share is 0.5 or more. Expected: at least 4 target pairs; in at least 75% of them the candidate's home "
               "share is at most half of the base's and a candidate head stands in another area by round 100; summed "
               "over them the candidate visits more cells by round 100 and has more pearls by round 200 or more "
               "dragons at round 100; over all pairs extra deaths before round 200 are not more than extra pearls by "
               "round 200; on maze-like maps extra deaths of short dragons on one-wide cells are not more than extra "
               "pearls; and every pair on a map with no one-wide step and no portal is replay-identical.")


def terrain(text):
    W = H = 0
    kind = {}
    for line in text.splitlines():
        q = line.split()
        if not q:
            continue
        if q[0] == 'MAP':
            W, H = int(q[1]), int(q[2])
        elif q[0] == 'EDGE':
            kind[int(q[1])] = int(q[2])
    if W <= 0 or H <= 0:
        raise ValueError('replay map has no size')
    row = 2 * (W + 1)
    adj = {(x, y): [] for x in range(W) for y in range(H)}
    portal = set()
    for y in range(H):
        for x in range(W):
            for other, k in (((x, (y - 1) % H), kind.get(y * row + x, 0)),
                             (((x - 1) % W, y), kind.get(y * row + W + 1 + x, 0))):
                if k == 0 and other != (x, y):
                    adj[(x, y)].append(other)
                    adj[other].append((x, y))
                elif k == 2:
                    portal.update(((x, y), other))
    # Bridges by lowlink; a doubled edge between two cells is not a bridge.
    disc, low, bridges, t = {}, {}, set(), 0
    for root in adj:
        if root in disc:
            continue
        disc[root] = low[root] = t
        t += 1
        stack = [[root, None, iter(adj[root]), False]]
        while stack:
            frame = stack[-1]
            v, parent = frame[0], frame[1]
            deeper = False
            for u in frame[2]:
                if u == parent and not frame[3]:
                    frame[3] = True
                elif u in disc:
                    low[v] = min(low[v], disc[u])
                else:
                    disc[u] = low[u] = t
                    t += 1
                    stack.append([u, v, iter(adj[u]), False])
                    deeper = True
                    break
            if not deeper:
                stack.pop()
                if parent is not None:
                    low[parent] = min(low[parent], low[v])
                    if low[v] > disc[parent]:
                        bridges.add(frozenset((v, parent)))
    room, sizes = {}, []
    for c in adj:
        if c in room:
            continue
        room[c] = len(sizes)
        queue = [c]
        for v in queue:
            for u in adj[v]:
                if u not in room and frozenset((u, v)) not in bridges:
                    room[u] = room[c]
                    queue.append(u)
        sizes.append(len(queue))
    return {'W': W, 'H': H, 'adj': adj, 'portal': portal, 'bridges': bridges, 'room': room, 'sizes': sizes}


def out_by(W, H):
    cells = W * H
    long_map = W >= 2 * H
    pull = cells <= 1000 and (long_map or cells <= 700)
    return ((60 if long_map else 30) + 15) if pull else 20


def metrics(path, ours):
    root = replay.load(path).root()
    result = root.pointer(4)
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None
    text = root.text(0)
    ter = terrain(text)
    room, sizes, adj = ter['room'], ter['sizes'], ter['adj']
    bodies, team_of = {}, {}
    for line in text.splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
    mine = lambda i: team_of.get(i) == ours
    starts = [bodies[i][0] for i in bodies if mine(i)]
    if not starts:
        raise ValueError(f'{path}: no dragons for team {ours}')
    home = {room[c] for c in starts}
    home_cells = sum(sizes[k] for k in home)
    # Does a bridge out of the start room lead on to another area?
    seen = {c for c in adj if room[c] in home}
    queue = list(seen)
    exits = sum(1 for c in seen for n in adj[c] if room[n] not in home)
    leads_on = False
    for v in queue:
        for u in adj[v]:
            if u in seen:
                continue
            seen.add(u)
            if sizes[room[u]] >= AREA_MIN:
                leads_on = True
            else:
                queue.append(u)
    enterable = sum(1 for c in adj if adj[c])
    loop_free = sum(1 for c in adj if adj[c] and sizes[room[c]] < AREA_MIN)
    cells = ter['W'] * ter['H']
    if not ter['bridges'] and not ter['portal']:
        kind = 'open'
    elif home_cells <= ROOM_SHARE * cells and leads_on and not any(c in ter['portal'] for c in adj if room[c] in home):
        kind = 'walled'
    else:
        kind = 'other'
    queens = [i for i in (0, 1) if mine(i)]
    queen = queens[0] if len(queens) == 1 else None

    units = lambda: sum(1 for i in bodies if mine(i))
    grown = {i: 0 for i in bodies}
    visited = set(starts)
    h = hashlib.sha1()
    rnd = pearls = deaths = branch_short = stalled = 0
    first_out = first_area = queen_out = queen_death = None
    stay = {'window': [0, 0], 'game': [0, 0]}   # [dragon-rounds at home, dragon-rounds]
    snap = {}
    death_rows = []

    def take(force=False):
        if 'cells' not in snap and (force or rnd >= CELLS_ROUND):
            snap['cells'], snap['units'] = len(visited), units()
        if 'pearls' not in snap and (force or rnd >= PEARLS_ROUND):
            snap['pearls'], snap['deaths'], snap['branch_short'], snap['stalled'] = pearls, deaths, branch_short, stalled

    def seen_head(did, head):
        nonlocal first_out, first_area, queen_out
        visited.add(head)
        if room[head] in home:
            return
        if first_out is None:
            first_out = rnd
        if first_area is None and sizes[room[head]] >= AREA_MIN:
            first_area = rnd
        if did == queen and queen_out is None:
            queen_out = rnd

    for ev in root.pointer(3):
        which = ev.u16(0)
        name = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if name == 'roundStart':
            rnd = pl.i32(0)
            h.update(f"r{rnd}".encode())
            take()
            alive = [i for i in bodies if mine(i) and bodies[i]]
            at_home = sum(1 for i in alive if room[tuple(bodies[i][0])] in home)
            for key in ('game',) + (('window',) if WINDOW[0] <= rnd < WINDOW[1] else ()):
                stay[key][0] += at_home
                stay[key][1] += len(alive)
            if len(alive) <= STALL_UNITS:
                stalled += sum(1 for i in alive if rnd - grown.get(i, rnd) >= STALL_IDLE)
        elif name == 'dragonUpdate':
            did = pl.i32(0)
            head, tail = replay.point(pl.pointer(0)), replay.point(pl.pointer(1))
            h.update(f"u{did}{head}{tail}".encode())
            body = bodies.setdefault(did, deque())
            was = len(body)
            if not body or body[0] != head:
                body.appendleft(head)
            while len(body) > 1 and body[-1] != tail:
                body.pop()
            grown.setdefault(did, rnd)
            if was and len(body) > was:
                grown[did] = rnd
                if mine(did):
                    pearls += len(body) - was
            if mine(did):
                seen_head(did, tuple(head))
        elif name == 'dragonSplit':
            parent, child = pl.i32(0), pl.i32(4)
            h.update(f"s{parent}{child}".encode())
            team = ('A', 'B')[pl.u16(8)]
            bodies[parent] = deque(replay.point(p) for p in pl.pointer(0))
            bodies[child] = deque(replay.point(p) for p in pl.pointer(1))
            team_of[parent] = team_of[child] = team
            grown.setdefault(parent, rnd)
            grown[child] = rnd
            if team == ours and bodies[child]:
                seen_head(child, tuple(bodies[child][0]))
        elif name == 'dragonDeath':
            did = pl.i32(0)
            reason = pl.u16(4)
            h.update(f"d{did}{reason}".encode())
            body = bodies.pop(did, deque())
            if mine(did):
                deaths += 1
                head = tuple(body[0]) if body else None
                place = ('unknown' if head is None else 'start_room' if room[head] in home
                         else 'loop_free' if sizes[room[head]] < AREA_MIN else 'area')
                branch_short += int(len(body) <= SHORT and place == 'loop_free')
                if did == queen and queen_death is None:
                    queen_death = rnd
                if rnd < PEARLS_ROUND:
                    death_rows.append({'round': rnd, 'id': did, 'length': len(body), 'place': place,
                                       'cause': CAUSES[reason] if reason < len(CAUSES) else 'unknown'})
    take(force=True)
    used = stay['window'] if stay['window'][1] else stay['game']
    mine_len = [len(b) for i, b in bodies.items() if mine(i)]
    their_len = [len(b) for i, b in bodies.items() if team_of.get(i) not in (ours, None)]
    return {'kind': kind, 'cells': cells, 'start_room_cells': home_cells, 'exits': exits, 'out_by': out_by(ter['W'], ter['H']),
            'maze_like': bool(enterable and loop_free >= MAZE_SHARE * enterable), 'loop_free_cells': loop_free,
            'home_share': round(used[0] / used[1], 4) if used[1] else 0.0, 'home_rounds': used[0], 'dragon_rounds': used[1],
            'first_out': first_out, 'first_area': first_area, 'queen_out': queen_out, 'queen_death': queen_death,
            'cells_100': snap['cells'], 'units_100': snap['units'], 'pearls_200': snap['pearls'],
            'deaths_200': snap['deaths'], 'branch_short_200': snap['branch_short'], 'stalled_200': snap['stalled'],
            'deaths_before_200': death_rows, 'rounds': rnd, 'longest_end': max(mine_len, default=0),
            'their_longest_end': max(their_len, default=0), 'win': int(winner == ours), 'digest': h.hexdigest()}


def collect(directory, tag):
    out = {}
    for p in sorted(glob.glob(os.path.join(directory, f'{tag}_*.replay'))):
        stem = os.path.basename(p)[len(tag) + 1:-len('.replay')]
        m, seed, side = stem.rsplit('_', 2)
        if side not in ('0', '1'):
            raise ValueError(f'{p}: unexpected side')
        out[(m, seed, side)] = metrics(p, 'A' if side == '0' else 'B')
    return out


def by(rnd, limit):
    return rnd is not None and rnd <= limit


def tally(rows):
    total = lambda f: sum(x[f] for x in rows)
    place = {}
    for x in rows:
        for d in x['deaths_before_200']:
            key = f"{d['place']}:{d['cause']}:{'short' if d['length'] <= SHORT else 'long'}"
            place[key] = place.get(key, 0) + 1
    return {'games': len(rows),
            'home_share': [x['home_share'] for x in rows],
            'home_share_pooled': round(total('home_rounds') / total('dragon_rounds'), 4) if rows and total('dragon_rounds') else None,
            'first_out': [x['first_out'] for x in rows], 'first_area': [x['first_area'] for x in rows],
            'out_by_100': sum(by(x['first_out'], CELLS_ROUND) for x in rows),
            'area_by_100': sum(by(x['first_area'], CELLS_ROUND) for x in rows),
            'out_by_card_timing': sum(by(x['first_out'], x['out_by']) for x in rows),
            'queen_out_by_100': sum(by(x['queen_out'], CELLS_ROUND) for x in rows),
            'queen_deaths_before_200': sum(1 for x in rows if x['queen_death'] is not None and x['queen_death'] < PEARLS_ROUND),
            'cells_100': total('cells_100'), 'units_100': total('units_100'), 'pearls_200': total('pearls_200'),
            'deaths_200': total('deaths_200'), 'branch_short_200': total('branch_short_200'),
            'stalled_200': total('stalled_200'), 'deaths_by_place_cause_length': dict(sorted(place.items())),
            'longest_end': total('longest_end'), 'their_longest_end': total('their_longest_end'),
            'wins_not_a_verdict': total('win')}


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
        sys.exit(f'unpaired replays: {sorted(set(base) ^ set(cand))[:6]}')
    keys = sorted(base)
    walled = [k for k in keys if base[k]['kind'] == 'walled']
    target = [k for k in walled if base[k]['home_share'] >= PIN_SHARE]
    opened = [k for k in keys if base[k]['kind'] == 'open']
    maze = [k for k in keys if base[k]['maze_like']]
    same = [k for k in keys if base[k]['digest'] == cand[k]['digest']]
    fired = [k for k in target if 2 * cand[k]['home_share'] <= base[k]['home_share']]
    B = lambda ks: tally([base[k] for k in ks])
    C = lambda ks: tally([cand[k] for k in ks])
    tb, tc, ab, ac, mb, mc = B(target), C(target), B(keys), C(keys), B(maze), C(maze)
    need = SHARE_NEEDED * len(target)
    checks = {'target_seen': len(target) >= MIN_TARGET,
              'fires': bool(target) and len(fired) >= need,
              'goes_through': bool(target) and tc['area_by_100'] >= need,
              'cells': bool(target) and tc['cells_100'] > tb['cells_100'],
              'growth': bool(target) and (tc['pearls_200'] > tb['pearls_200'] or tc['units_100'] > tb['units_100']),
              'deaths': ac['deaths_200'] - ab['deaths_200'] <= ac['pearls_200'] - ab['pearls_200'],
              'dead_ends': mc['branch_short_200'] - mb['branch_short_200'] <= mc['pearls_200'] - mb['pearls_200'],
              'open_identical': all(k in same for k in opened)}
    passed = all(checks.values())
    per_map = {}
    for m in sorted({k[0] for k in keys}):
        ks = [k for k in keys if k[0] == m]
        first = base[ks[0]]
        per_map[m] = {'kind': first['kind'], 'maze_like': first['maze_like'], 'cells': first['cells'],
                      'start_room_cells': sorted({base[k]['start_room_cells'] for k in ks}), 'out_by': first['out_by'],
                      'target_pairs': sum(k in target for k in ks), 'fired_pairs': sum(k in fired for k in ks),
                      'identical_pairs': sum(k in same for k in ks), 'base': B(ks), 'candidate': C(ks)}
    failed = [name for name, ok in checks.items() if not ok]
    note = (f"{len(keys)} pairs: {len(walled)} with a walled start, {len(opened)} on open maps, {len(maze)} on maze-like "
            f"maps; {len(same)} replay-identical. Target pairs (walled start, base spends half or more of its "
            f"dragon-rounds in rounds 100-199 inside the start room): {len(target)}. In those: candidate's share inside "
            f"at most half of base's in {len(fired)}; pooled share inside base {tb['home_share_pooled']}, candidate "
            f"{tc['home_share_pooled']}; a head outside the start room by round 100: base {tb['out_by_100']}, candidate "
            f"{tc['out_by_100']}; standing in another area by round 100: candidate {tc['area_by_100']}; out by the "
            f"card's timing: candidate {tc['out_by_card_timing']}; cells visited by round 100: base {tb['cells_100']}, "
            f"candidate {tc['cells_100']}; pearls by round 200: base {tb['pearls_200']}, candidate {tc['pearls_200']}; "
            f"dragons at round 100: base {tb['units_100']}, candidate {tc['units_100']}; stalled dragon-rounds by round "
            f"200: base {tb['stalled_200']}, candidate {tc['stalled_200']}. All pairs: deaths before round 200 base "
            f"{ab['deaths_200']}, candidate {ac['deaths_200']}; pearls by round 200 base {ab['pearls_200']}, candidate "
            f"{ac['pearls_200']}; queen deaths before round 200 base {ab['queen_deaths_before_200']}, candidate "
            f"{ac['queen_deaths_before_200']}. Maze-like maps: short dragons dying on one-wide cells before round 200 "
            f"base {mb['branch_short_200']}, candidate {mc['branch_short_200']}"
            + ('' if maze else ' (no maze-like map in this run)') + f". Open-map pairs identical: "
            f"{sum(k in same for k in opened)} of {len(opened)}" + ('' if opened else ' (no open map in this run)') + '. '
            + ('All eight pre-registered checks held.' if passed else 'Failed checks: ' + ', '.join(failed) + '.')
            + ' Transposed or mirrored copies are not measured here.')
    result = {'passed': passed, 'note': note, 'expectation': EXPECTATION, 'checks': checks,
              'target_seen': checks['target_seen'], 'mechanism_shown': passed,
              'pairs': len(keys), 'identical_pairs': len(same), 'walled_pairs': len(walled), 'target_pairs': len(target),
              'fired_pairs': len(fired), 'open_pairs': len(opened), 'maze_like_pairs': len(maze),
              'target': {'base': tb, 'candidate': tc}, 'all': {'base': ab, 'candidate': ac},
              'maze_like': {'base': mb, 'candidate': mc}, 'per_map': per_map,
              'games': [{'map': k[0], 'seed': k[1], 'side': k[2], 'target': k in target, 'fired': k in fired,
                         'identical': k in same,
                         'base': {f: v for f, v in base[k].items() if f != 'digest'},
                         'candidate': {f: v for f, v in cand[k].items() if f != 'digest'}} for k in keys]}
    with open(a.output, 'w') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(note)


if __name__ == '__main__':
    main()
