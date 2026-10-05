#!/usr/bin/env python3
"""Card #36 queen-dead-end mechanism check (QUEEN_DEAD_END): does the queen stop stepping into places she cannot be
sure to fit in?

usage: python3 work/card_36_check.py --replays DIR --base base --candidate candidate --output FILE
Replays are DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1), paired by (map, seed, side).

For every move of our queen it rebuilds, from the replay alone, what she knew when she decided: the tiles she has
seen so far (the 7x7 box around her head at each of her turns), the walls on those tiles, her own body, and the
other dragons inside her current view. For each step she could take it recomputes two of the bot's counts:

  known room  tiles reachable over seen tiles and known open sides only, counted up to length + 2; reaching her own
              tail counts as enough. This is the card's new rule: below length + 2 the step "does not surely fit".
  room        the release's count: unseen tiles can be walked through and count half. "Roomy" means at least
              3 x length + 8, the size at which the release applies no tightness or dead-end penalty of any kind.

A "choice" is a queen turn that offers at least one step that does not surely fit AND at least one step that surely
fits and is roomy. "Walked in" is a choice where she took a step that does not surely fit. Moves made for other
reasons (escapes, hunts, rams) need an enemy nearby, so the gate looks at calm turns only: no enemy head within
6 tiles of her head.

Pre-registered before any game was played (see PASS RULE below). Real dead-end entries (counted on the true map,
no fog), queen deaths, queen length, wins and CPU are reported as raw numbers and are NOT part of the pass rule:
16 games per side cannot settle them, the A/B does.
"""
import argparse, glob, json, os, sys, concurrent.futures as cf
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before seeing results)
TARGET_MIN = 12      # base must show at least this many calm walk-ins (target seen)
CHOICE_MIN = 20      # the candidate must face at least this many calm choices, so its share is not empty
CUT = 0.25           # candidate's calm walk-in share must be at most this fraction of base's

VIEW = 3             # the bot sees a 7x7 box around its head
CALM_GAP = 6
CAUSE = ['wall', 'self', 'body', 'headon', 'none']
WALL_TOLERANCE = 0.01
UNMODELLED_TOLERANCE = 0.2


def load_board(text):
    """Neighbours and side kinds (0 open, 1 kelp, 2 portal) per tile, in N E S W order."""
    W = H = 0
    E = {}
    for line in text.splitlines():
        q = line.split()
        if not q:
            continue
        if q[0] == 'MAP':
            W, H = int(q[1]), int(q[2])
        elif q[0] == 'EDGE':
            E[int(q[1])] = int(q[2])
    if not W or not H:
        raise ValueError('replay carries no map size')
    # Side ids run in rows of W + 1: a row of north sides, then a row of west sides. Generated maps also
    # carry the wrap-around copies (bottom row, right column); official maps leave those ids out.
    R = W + 1

    def north(x, y):
        return [2 * y * R + x] + ([2 * H * R + x] if y == 0 else [])

    def west(x, y):
        return [(2 * y + 1) * R + x] + ([(2 * y + 1) * R + W] if x == 0 else [])

    def kind(ids):
        return max(E.get(i, 0) for i in ids)

    nb, side = [], []
    for y in range(H):
        for x in range(W):
            nb.append((((y - 1) % H) * W + x, y * W + (x + 1) % W, ((y + 1) % H) * W + x, y * W + (x - 1) % W))
            side.append((kind(north(x, y)), kind(west((x + 1) % W, y)), kind(north(x, (y + 1) % H)), kind(west(x, y))))
    return W, H, nb, side


def gap(a, b, size):
    raw = abs(a - b)
    return min(raw, size - raw)


def one(job):
    path, side_tag = job
    ours = 'A' if side_tag == '0' else 'B'
    name = os.path.basename(path)[:-len('.replay')]
    root = replay.load(path).root()
    text = root.text(0)
    W, H, nb, side = load_board(text)
    cells = W * H
    result = root.pointer(4)
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None
    bodies, team_of = {}, {}
    for line in text.splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque(int(q[4 + 2 * k]) * W + int(q[3 + 2 * k]) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
    queen = next((i for i in (0, 1) if team_of.get(i) == ours), None)
    rival = next((i for i in (0, 1) if team_of.get(i) != ours), None)
    c = Counter(games=1, win=int(winner == ours))
    seen = bytearray(cells)
    stamp = [0] * cells
    steps = [0] * cells
    mark = 0
    pending = None
    boxed_before = False
    rnd = 0
    examples = []

    def look(head):
        x0, y0 = head % W, head // W
        for dy in range(-VIEW, VIEW + 1):
            row = ((y0 + dy) % H) * W
            for dx in range(-VIEW, VIEW + 1):
                seen[row + (x0 + dx) % W] = 1

    def in_view(cell, head):
        return gap(cell % W, head % W, W) <= VIEW and gap(cell // W, head // W, H) <= VIEW

    def known_room(start, need, free_at, blocked, tail):
        nonlocal mark
        mark += 1
        stamp[start] = mark
        steps[start] = 1
        queue = [start]
        at = 0
        while at < len(queue) and len(queue) < need:
            cell = queue[at]
            at += 1
            arrive = steps[cell] + 1
            for d in range(4):
                if side[cell][d]:
                    continue
                nxt = nb[cell][d]
                if stamp[nxt] == mark or not seen[nxt] or nxt in blocked:
                    continue
                if arrive < free_at.get(nxt, 0):
                    continue
                if nxt == tail:
                    return need
                stamp[nxt] = mark
                steps[nxt] = arrive
                queue.append(nxt)
        return min(len(queue), need)

    def roomy(start, cap, free_at, blocked, tail):
        """The release's room count from `start`: (reaches cap, reaches tail)."""
        nonlocal mark
        mark += 1
        stamp[start] = mark
        steps[start] = 1
        queue = [start]
        at = 0
        room = 0.0
        tail_hit = False
        while at < len(queue):
            cell = queue[at]
            at += 1
            room += 1.0 if seen[cell] else 0.5
            tail_hit = tail_hit or cell == tail
            if room >= cap:
                return True, tail_hit
            arrive = steps[cell] + 1
            for d in range(4):
                nxt = nb[cell][d]
                if side[cell][d] and (seen[cell] or seen[nxt]):
                    continue
                if stamp[nxt] == mark or nxt in blocked:
                    continue
                if arrive < free_at.get(nxt, 0):
                    continue
                stamp[nxt] = mark
                steps[nxt] = arrive
                queue.append(nxt)
        return False, tail_hit

    def true_room(start, need, free_at, blocked, tail):
        """Same count on the true map: every tile and wall as it is, every other dragon in the way."""
        nonlocal mark
        mark += 1
        stamp[start] = mark
        steps[start] = 1
        queue = [start]
        at = 0
        while at < len(queue) and len(queue) < need:
            cell = queue[at]
            at += 1
            arrive = steps[cell] + 1
            for d in range(4):
                if side[cell][d]:
                    continue
                nxt = nb[cell][d]
                if stamp[nxt] == mark or nxt in blocked:
                    continue
                if arrive < free_at.get(nxt, 0):
                    continue
                if nxt == tail:
                    return need
                stamp[nxt] = mark
                steps[nxt] = arrive
                queue.append(nxt)
        return min(len(queue), need)

    def decide(body):
        head = body[0]
        length = len(body)
        need = length + 2
        cap = 3 * length + 8
        free_at = {cell: length - offset + 1 for offset, cell in enumerate(body)}
        tail = body[-1]
        everyone = {cell for d, b in bodies.items() if d != queen for cell in b}
        visible = {cell for cell in everyone if in_view(cell, head)}
        foes = [b[0] for d, b in bodies.items() if b and team_of.get(d) != ours]
        calm = all(max(gap(f % W, head % W, W), gap(f // W, head // W, H)) > CALM_GAP for f in foes)
        options = {}
        for d in range(4):
            dest = nb[head][d]
            if side[head][d] or dest in visible or dest in free_at:
                continue
            known = known_room(dest, need, free_at, visible, tail)
            enough, tail_hit = roomy(dest, cap, free_at, visible, tail)
            options[dest] = dict(known=known, fits=known >= need, clean=known >= need and enough,
                                 old_dead=not enough and not tail_hit,
                                 real=true_room(dest, need, free_at, everyone, tail) >= need)
        return dict(head=head, length=length, need=need, calm=calm, options=options, first=None, round=rnd)

    def close():
        nonlocal pending, boxed_before
        p, pending = pending, None
        if p is None:
            return
        if p['first'] is None:
            c['queen_moves_without_step'] += 1
            return
        c['queen_moves'] += 1
        c['calm_moves'] += p['calm']
        opts = p['options']
        chosen = opts.get(p['first'])
        if chosen is None:
            c['unmodelled_moves'] += 1
            return
        some_fail = any(not o['fits'] for o in opts.values())
        some_clean = any(o['clean'] for o in opts.values())
        choice = some_fail and some_clean
        walked = choice and not chosen['fits']
        for tag in (('all', 'calm') if p['calm'] else ('all',)):
            c[f'{tag}_choices'] += choice
            c[f'{tag}_walk_ins'] += walked
            c[f'{tag}_no_fit_steps'] += not chosen['fits']
            c[f'{tag}_nothing_fits_turns'] += not any(o['fits'] for o in opts.values())
            c[f'{tag}_old_dead_steps'] += chosen['old_dead']
        if walked and p['calm']:
            examples.append(dict(game=name, round=p['round'], x=p['head'] % W, y=p['head'] // W, length=p['length'],
                                 known_tiles=chosen['known'], needed=p['need']))
        boxed = not chosen['real']
        c['real_boxed_turns'] += boxed
        if boxed and not boxed_before:
            c['real_dead_end_entries'] += 1
            c['real_dead_end_entries_avoidable'] += any(o['real'] for o in opts.values())
        boxed_before = boxed

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if kind == 'roundStart':
            close()
            rnd = pl.i32(0)
            if rnd == 300:
                c['queen_len_r300'] = len(bodies.get(queen, ()))
        elif kind == 'dragonAction':
            close()
            if pl.i32(0) != queen or queen is None or not bodies.get(queen):
                continue
            usage = pl.pointer(1)
            if usage:
                c['cpu_max'] = max(c['cpu_max'], usage.u64(0))
            look(bodies[queen][0])
            a = pl.pointer(0)
            if a is None:
                continue
            if a.u16(0) == 1:
                c['queen_splits'] += 1
                c['queen_splits_after_r200'] += rnd > 200
            if a.u16(0) == 0:
                pending = decide(bodies[queen])
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            hx, hy = replay.point(pl.pointer(0))
            tx, ty = replay.point(pl.pointer(1))
            h, tp = hy * W + hx, ty * W + tx
            b = bodies.setdefault(did, deque())
            before = len(b)
            if not b or b[0] != h:
                if b:
                    c['steps'] += 1
                    d = nb[b[0]].index(h) if h in nb[b[0]] else -1
                    if d < 0 or side[b[0]][d] == 2:
                        c['portal_steps'] += 1
                    elif side[b[0]][d]:
                        c['wall_steps'] += 1
                b.appendleft(h)
                if pending and did == queen and pending['first'] is None:
                    pending['first'] = h
            while len(b) > 1 and b[-1] != tp:
                b.pop()
            if did == queen and before > 0 and len(b) > before:
                c['queen_pearls'] += 1
        elif kind == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x)[1] * W + replay.point(x)[0] for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x)[1] * W + replay.point(x)[0] for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
        elif kind == 'dragonDeath':
            did = pl.i32(0)
            r = pl.u16(4)
            bodies.pop(did, None)
            if did == queen:
                c['queen_deaths'] += 1
                c[f"queen_deaths_{CAUSE[r] if r < 5 else 'other'}"] += 1
    close()
    c['queen_len_end'] = len(bodies.get(queen, ()))
    c['rival_queen_len_end'] = len(bodies.get(rival, ()))
    examples.sort(key=lambda e: (e['known_tiles'] - e['needed'], e['round']))
    out = dict(c)
    out['examples'] = examples[:2]
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
        s.update({k: v for k, v in r.items() if k != 'examples'})
        s['cpu_max'] = cpu
    return s


def share(a, b):
    return a / b if b else 0.0


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
    b, c = total(base[k] for k in keys), total(cand[k] for k in keys)
    for label, s in ((a.base, b), (a.candidate, c)):
        if not s['queen_moves']:
            sys.exit(f'no queen moves found in the {label} replays; the measurement is not valid')
        if s['wall_steps'] > WALL_TOLERANCE * s['steps']:
            sys.exit(f"{label}: {s['wall_steps']} of {s['steps']} steps cross a wall; the map is not read correctly")
        if s['unmodelled_moves'] > UNMODELLED_TOLERANCE * s['queen_moves']:
            sys.exit(f"{label}: {s['unmodelled_moves']} of {s['queen_moves']} queen moves are not modelled; "
                     'the measurement is not valid')

    def view(s):
        out = {'games': s['games'], 'wins': s['win'], 'queen_moves': s['queen_moves'], 'calm_queen_moves': s['calm_moves']}
        for tag in ('calm', 'all'):
            out[tag] = {'choices': s[f'{tag}_choices'], 'walk_ins': s[f'{tag}_walk_ins'],
                        'walk_in_share': round(share(s[f'{tag}_walk_ins'], s[f'{tag}_choices']), 4),
                        'steps_that_do_not_surely_fit': s[f'{tag}_no_fit_steps'],
                        'turns_where_nothing_surely_fits': s[f'{tag}_nothing_fits_turns'],
                        'steps_into_old_rule_dead_ends': s[f'{tag}_old_dead_steps']}
        out.update({'real_dead_end_entries': s['real_dead_end_entries'],
                    'real_dead_end_entries_avoidable': s['real_dead_end_entries_avoidable'],
                    'real_boxed_turns': s['real_boxed_turns'],
                    'queen_deaths': s['queen_deaths'],
                    'queen_deaths_by_cause': {k: s[f'queen_deaths_{k}'] for k in CAUSE + ['other'] if s[f'queen_deaths_{k}']},
                    'queen_splits': s['queen_splits'], 'queen_splits_after_r200': s['queen_splits_after_r200'],
                    'queen_pearls_per_game': round(share(s['queen_pearls'], s['games']), 1),
                    'queen_length_r300_per_game': round(share(s['queen_len_r300'], s['games']), 1),
                    'queen_length_end_per_game': round(share(s['queen_len_end'], s['games']), 1),
                    'rival_queen_length_end_per_game': round(share(s['rival_queen_len_end'], s['games']), 1),
                    'cpu_max_points': s['cpu_max'],
                    'unmodelled_queen_moves': s['unmodelled_moves'], 'wall_steps': s['wall_steps'],
                    'portal_steps': s['portal_steps'], 'steps': s['steps']})
        return out

    bv, cv = view(b), view(c)
    target_seen = bv['calm']['walk_ins'] >= TARGET_MIN
    choice_ok = cv['calm']['choices'] >= CHOICE_MIN
    cut_ok = cv['calm']['walk_in_share'] <= CUT * bv['calm']['walk_in_share']
    passed = bool(target_seen and choice_ok and cut_ok)
    why = []
    if not target_seen:
        why.append(f"base showed only {bv['calm']['walk_ins']} calm walk-ins (need {TARGET_MIN})")
    if not choice_ok:
        why.append(f"the candidate faced only {cv['calm']['choices']} calm choices (need {CHOICE_MIN})")
    if not cut_ok:
        why.append('the walk-in share did not fall to a quarter of base')

    def pick(rows):
        found = [e for k in keys for e in rows[k]['examples']]
        found.sort(key=lambda e: (e['known_tiles'] - e['needed'], e['game'], e['round']))
        return found[:8]

    note = (f"calm queen turns that offered both a step that surely fits and one that does not; she took the one that does "
            f"not: base {bv['calm']['walk_ins']}/{bv['calm']['choices']} ({bv['calm']['walk_in_share']:.1%}) -> "
            f"switch on {cv['calm']['walk_ins']}/{cv['calm']['choices']} ({cv['calm']['walk_in_share']:.1%}); "
            f"all turns, enemy near or not: {bv['all']['walk_ins']}/{bv['all']['choices']} -> "
            f"{cv['all']['walk_ins']}/{cv['all']['choices']}; turns where no step surely fits: "
            f"{bv['all']['turns_where_nothing_surely_fits']} -> {cv['all']['turns_where_nothing_surely_fits']} of "
            f"{bv['queen_moves']} -> {cv['queen_moves']} queen moves; "
            f"not gated, {len(keys)} games each: real dead-end entries (true map) {bv['real_dead_end_entries']} -> "
            f"{cv['real_dead_end_entries']}, queen deaths {bv['queen_deaths']} -> {cv['queen_deaths']}, queen length at "
            f"the end {bv['queen_length_end_per_game']} -> {cv['queen_length_end_per_game']}, queen pearls/game "
            f"{bv['queen_pearls_per_game']} -> {cv['queen_pearls_per_game']}, wins {bv['wins']} -> {cv['wins']}, "
            + (f"peak queen CPU {bv['cpu_max_points']} -> {cv['cpu_max_points']}" if bv['cpu_max_points'] or cv['cpu_max_points']
               else 'CPU not measured (these replays carry no CPU counter)')
            + ('' if passed else '. NOT shown: ' + '; '.join(why)))
    out = {'passed': passed, 'note': note, 'target_seen': bool(target_seen), 'pairs': len(keys),
           'maps': sorted({k[0] for k in keys}),
           'pass_rule': {'target_min': TARGET_MIN, 'choice_min': CHOICE_MIN, 'cut': CUT,
                         'target_seen': bool(target_seen), 'choice_ok': bool(choice_ok), 'cut_ok': bool(cut_ok)},
           'base': bv, 'candidate': cv,
           'examples': {'base': pick(base), 'candidate': pick(cand)},
           'limits': ('measured from replays without bot logs: her memory is rebuilt as every 7x7 view she has had, the '
                      'check assumes she knows where her tail is and ignores how pearls delay her tail, so single turns can '
                      'be judged differently from the bot; portals are not walked (the queen does not use them); calm = no '
                      'enemy head within 6 tiles, so escapes, hunts and rams are left out of the gate; the tail-out-of-sight '
                      'rule and the length + 8 margin are not measured separately (no bot logs); real dead-end entries, '
                      'deaths, length, pearls, wins and CPU are raw counts from a small sample, not evidence of an outcome')}
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
        sys.exit(f'card 36 check failed: {exc}')
