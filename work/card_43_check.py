#!/usr/bin/env python3
"""Card #43 idle-exit mechanism check (IDLE_EXIT): does a dragon with nothing to eat nearby walk to the explored edge?

usage: python3 work/card_43_check.py --replays DIR --base base --candidate candidate --output FILE
Replays are DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1), paired by (map, seed, side).

"Explored edge" = a tile the dragon has seen that has an open side onto a tile it has never seen.

For every move of our dragons other than the queen (dragon 0 or 1) it rebuilds, from the replay alone, what that
dragon knew when it decided: the tiles it has seen so far (the 7x7 box around its head at each of its turns, starting
empty when it is born), the pearls it remembers on them (as last seen), the walls, and the other dragons inside its
current view. On that it repeats the bot's own search (over seen tiles, no portals, other dragons' bodies block).

A "stuck turn" is a move where all the card's conditions that a replay can show hold:
  the dragon has not grown for 20 rounds, it remembers no pearl within 6 steps, no enemy head is in its view,
  and there is an explored edge it can walk to.
"Toward the edge" = after its first step it is closer (in known steps) to an explored edge than its nearest one was.

Leaders and feeders are left out by the card, and a replay does not show those roles. The bot has no leader before
round 150 and no feeder before round 200, so the gate looks at rounds up to 150 only; all rounds are reported raw.

Pre-registered before any game with the switch on was played (see PASS RULE below). How long dragons stay stuck,
how much of the map they have seen, how often they grow, queen length and wins are raw numbers and NOT part of the
pass rule: 16 games per side cannot settle them, the A/B does.
"""
import argparse, glob, json, os, sys, concurrent.futures as cf
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before seeing results). Base alone already steps toward an edge on about two stuck turns in
# three (switch-off replays only: 68% on this build's old-10 identity games, 56% to 67% per map on older base
# replays of the mechanism maps), so the bar is set against base, not against zero.
TARGET_MIN = 200     # base must show at least this many stuck turns up to round 150 (target seen)
CHOICE_MIN = 40      # the candidate must face at least this many, so its share is not empty
SHARE_MIN = 0.7      # candidate: at least 70% of its stuck turns step toward the edge
MISS_CUT = 2 / 3     # and its share of stuck turns NOT stepping toward the edge is at most this fraction of base's

VIEW = 3             # the bot sees a 7x7 box around its head
IDLE_ROUNDS = 20
PEARL_STEPS = 6
EARLY = 150          # no leader before this round, no feeder before round 200
MARKS = (50, 100, 150)
LONG_SPELL = 30
WALL_TOLERANCE = 0.01


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
    occ = [-1] * cells
    for line in text.splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque(int(q[4 + 2 * k]) * W + int(q[3 + 2 * k]) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
            for cell in bodies[did]:
                occ[cell] = did
    queen = next((i for i in (0, 1) if team_of.get(i) == ours), None)
    rival = next((i for i in (0, 1) if team_of.get(i) != ours), None)
    c = Counter(games=1, win=int(winner == ours), cells=cells)
    pearls = bytearray(cells)
    team_seen = bytearray(cells)
    seen_n = 0
    state = {}
    boxes = {}
    stamp = [0] * cells
    dist = [0] * cells
    mark = 0
    pending = None
    rnd = 0
    spells, walks = [], []

    def box(head):
        got = boxes.get(head)
        if got is None:
            x0, y0 = head % W, head // W
            got = boxes[head] = [((y0 + dy) % H) * W + (x0 + dx) % W
                                 for dy in range(-VIEW, VIEW + 1) for dx in range(-VIEW, VIEW + 1)]
        return got

    def scan(start, seen, mem, blocked):
        """The bot's search: (a remembered pearl within 6 steps, steps to the nearest explored edge or -1, that tile)."""
        nonlocal mark
        mark += 1
        stamp[start] = mark
        dist[start] = 0
        queue = [start]
        at = 0
        edge = tile = -1
        while at < len(queue):
            cell = queue[at]
            at += 1
            steps = dist[cell]
            if steps > PEARL_STEPS:
                if edge >= 0:
                    break
            elif cell != start and mem[cell]:
                return True, -1, -1
            for d in range(4):
                if side[cell][d]:
                    continue
                nxt = nb[cell][d]
                if not seen[nxt]:
                    if edge < 0 and cell != start:
                        edge, tile = steps, cell
                    continue
                if stamp[nxt] == mark or nxt in blocked:
                    continue
                stamp[nxt] = mark
                dist[nxt] = steps + 1
                queue.append(nxt)
        return False, edge, tile

    def edge_within(start, seen, blocked, limit):
        """True when an explored edge is fewer than `limit` known steps from `start`."""
        nonlocal mark
        mark += 1
        stamp[start] = mark
        dist[start] = 0
        queue = [start]
        at = 0
        while at < len(queue):
            cell = queue[at]
            at += 1
            steps = dist[cell]
            if steps >= limit:
                return False
            for d in range(4):
                if side[cell][d]:
                    continue
                nxt = nb[cell][d]
                if not seen[nxt]:
                    return True
                if stamp[nxt] == mark or nxt in blocked:
                    continue
                stamp[nxt] = mark
                dist[nxt] = steps + 1
                queue.append(nxt)
        return False

    def end(did, st):
        """The dragon is no longer stuck: close its stuck spell and its walk."""
        if st['spell']:
            spells.append(dict(game=name, dragon=did, from_round=st['spell_from'], turns=st['spell']))
        if st['walk']:
            walks.append(dict(game=name, dragon=did, from_round=st['walk_from'], to_round=st['walk_to'],
                              steps=st['walk'], from_xy=[st['walk_at'] % W, st['walk_at'] // W]))
        st['spell'] = st['walk'] = 0

    def settle(first):
        """Judge the pending stuck turn once its first step (or no step) is known."""
        nonlocal pending
        p, pending = pending, None
        if p is None:
            return
        st = p['st']
        toward = False
        if first is None:
            c['stuck_no_step'] += 1
        else:
            d = nb[p['head']].index(first) if first in nb[p['head']] else -1
            if d < 0 or side[p['head']][d]:
                c['stuck_portal_steps'] += 1
            else:
                toward = edge_within(first, st['seen'], p['blocked'], p['edge'])
        for tag in (('all', 'early') if p['round'] <= EARLY else ('all',)):
            c[f'{tag}_stuck'] += 1
            c[f'{tag}_toward'] += toward
            c[f'{tag}_edge_steps'] += p['edge']
        if not st['spell']:
            st['spell_from'] = p['round']
        st['spell'] += 1
        if toward:
            if not st['walk']:
                st['walk_from'], st['walk_at'] = p['round'], p['head']
            st['walk'] += 1
            st['walk_to'] = p['round']
        elif st['walk']:
            walks.append(dict(game=name, dragon=p['did'], from_round=st['walk_from'], to_round=st['walk_to'],
                              steps=st['walk'], from_xy=[st['walk_at'] % W, st['walk_at'] // W]))
            st['walk'] = 0

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if kind == 'roundStart':
            settle(None)
            rnd = pl.i32(0)
            if rnd in MARKS:
                c[f'seen_r{rnd}'] = seen_n
                c[f'marks_r{rnd}'] = 1
        elif kind == 'tileChange':
            x, y = replay.point(pl.pointer(0))
            pearls[y * W + x] = 1 if pl.u32(0) == 1 else 0
        elif kind == 'dragonAction':
            settle(None)
            did = pl.i32(0)
            body = bodies.get(did)
            if team_of.get(did) != ours or did <= 1 or not body:
                continue
            head, length = body[0], len(body)
            st = state.get(did)
            if st is None:
                st = state[did] = dict(seen=bytearray(cells), mem=bytearray(cells), prev=0, grown=rnd, spell=0, walk=0)
            if length > st['prev']:
                if st['prev']:
                    c['grew_turns'] += 1
                    c['grew_turns_early'] += rnd <= EARLY
                st['grown'] = rnd
            st['prev'] = length
            seen, mem = st['seen'], st['mem']
            view = box(head)
            blocked = set()
            foe = False
            for t in view:
                seen[t] = 1
                mem[t] = pearls[t]
                if not team_seen[t]:
                    team_seen[t] = 1
                    seen_n += 1
                o = occ[t]
                if o >= 0 and o != did:
                    blocked.add(t)
                    other = bodies.get(o)
                    foe = foe or bool(other and team_of.get(o) != ours and other[0] == t)
            a = pl.pointer(0)
            if a is None or a.u16(0) != 0:
                continue
            early = rnd <= EARLY
            c['moves'] += 1
            c['early_moves'] += early
            if rnd - st['grown'] < IDLE_ROUNDS:
                end(did, st)
                continue
            c['idle_moves'] += 1
            c['early_idle_moves'] += early
            if foe:
                c['idle_enemy_in_view'] += 1
                c['early_idle_enemy_in_view'] += early
                end(did, st)
                continue
            near, edge, tile = scan(head, seen, mem, blocked)
            if near:
                c['idle_pearl_near'] += 1
                c['early_idle_pearl_near'] += early
                end(did, st)
                continue
            if edge < 0:
                c['idle_no_edge'] += 1
                c['early_idle_no_edge'] += early
                end(did, st)
                continue
            pending = dict(did=did, st=st, head=head, edge=edge, blocked=blocked, round=rnd)
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            hx, hy = replay.point(pl.pointer(0))
            tx, ty = replay.point(pl.pointer(1))
            h, tp = hy * W + hx, ty * W + tx
            b = bodies.setdefault(did, deque())
            if not b or b[0] != h:
                if b:
                    c['steps'] += 1
                    d = nb[b[0]].index(h) if h in nb[b[0]] else -1
                    if d < 0 or side[b[0]][d] == 2:
                        c['portal_steps'] += 1
                    elif side[b[0]][d]:
                        c['wall_steps'] += 1
                if pending and pending['did'] == did:
                    settle(h)
                b.appendleft(h)
                pearls[h] = 0
            while len(b) > 1 and b[-1] != tp:
                t = b.pop()
                if occ[t] == did:
                    occ[t] = -1
            for cell in (b[0], b[-1]):
                occ[cell] = did
        elif kind == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            for cell in bodies.get(pa, ()):
                if occ[cell] == pa:
                    occ[cell] = -1
            bodies[pa] = deque(replay.point(x)[1] * W + replay.point(x)[0] for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x)[1] * W + replay.point(x)[0] for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
            for d in (pa, ch):
                for cell in bodies[d]:
                    occ[cell] = d
            c['splits'] += team_of[pa] == ours
        elif kind == 'dragonDeath':
            did = pl.i32(0)
            if pending and pending['did'] == did:
                settle(None)
            for cell in bodies.pop(did, ()):
                if occ[cell] == did:
                    occ[cell] = -1
            if did in state:
                end(did, state.pop(did))
            c['deaths'] += team_of.get(did) == ours and did > 1
            c['queen_deaths'] += did == queen
    settle(None)
    for did, st in state.items():
        end(did, st)
    for m in MARKS:
        if not c[f'marks_r{m}']:
            c[f'seen_r{m}'] = seen_n
    c['queen_len_end'] = len(bodies.get(queen, ()))
    c['rival_queen_len_end'] = len(bodies.get(rival, ()))
    out = dict(c)
    out['spells'] = spells
    out['walks'] = walks
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
        s.update({k: v for k, v in r.items() if k not in ('spells', 'walks')})
    return s


def share(a, b):
    return a / b if b else 0.0


def view(rows):
    rows = list(rows)
    s = total(rows)
    spells = [x for r in rows for x in r['spells']]
    early_spells = [x['turns'] for x in spells if x['from_round'] <= EARLY]
    out = {'games': s['games'], 'wins': s['win'], 'moves': s['moves']}
    for tag, label in (('early', 'to_round_150'), ('all', 'all_rounds')):
        pre = '' if tag == 'all' else 'early_'
        out[label] = {'stuck_turns': s[f'{tag}_stuck'], 'toward_edge': s[f'{tag}_toward'],
                      'toward_share': round(share(s[f'{tag}_toward'], s[f'{tag}_stuck']), 4),
                      'mean_steps_to_edge': round(share(s[f'{tag}_edge_steps'], s[f'{tag}_stuck']), 1),
                      'moves': s[f'{pre}moves'], 'idle_moves': s[f'{pre}idle_moves'],
                      'idle_but_enemy_in_view': s[f'{pre}idle_enemy_in_view'],
                      'idle_but_pearl_within_6': s[f'{pre}idle_pearl_near'],
                      'idle_but_no_edge_left': s[f'{pre}idle_no_edge']}
    out.update({'stuck_spells_started_by_round_150': len(early_spells),
                'stuck_spell_mean_turns': round(share(sum(early_spells), len(early_spells)), 1),
                'stuck_spell_longest_turns': max(early_spells, default=0),
                f'stuck_spells_of_{LONG_SPELL}_turns_or_more': sum(x >= LONG_SPELL for x in early_spells),
                'map_share_seen_by_round': {str(m): round(share(s[f'seen_r{m}'], s['cells']), 3) for m in MARKS},
                'grew_turns_to_round_150_per_game': round(share(s['grew_turns_early'], s['games']), 1),
                'grew_turns_per_game': round(share(s['grew_turns'], s['games']), 1),
                'deaths_per_game': round(share(s['deaths'], s['games']), 1),
                'splits_per_game': round(share(s['splits'], s['games']), 1),
                'queen_deaths': s['queen_deaths'],
                'queen_length_end_per_game': round(share(s['queen_len_end'], s['games']), 1),
                'rival_queen_length_end_per_game': round(share(s['rival_queen_len_end'], s['games']), 1),
                'stuck_turns_without_a_step': s['stuck_no_step'], 'stuck_turns_through_a_portal': s['stuck_portal_steps'],
                'wall_steps': s['wall_steps'], 'portal_steps': s['portal_steps'], 'steps': s['steps']})
    return out


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
    bv, cv = view(base[k] for k in keys), view(cand[k] for k in keys)
    for label, v in ((a.base, bv), (a.candidate, cv)):
        if not v['moves']:
            sys.exit(f'no moves of our non-queen dragons found in the {label} replays; the measurement is not valid')
        if v['wall_steps'] > WALL_TOLERANCE * v['steps']:
            sys.exit(f"{label}: {v['wall_steps']} of {v['steps']} steps cross a wall; the map is not read correctly")

    be, ce = bv['to_round_150'], cv['to_round_150']
    target_seen = be['stuck_turns'] >= TARGET_MIN
    choice_ok = ce['stuck_turns'] >= CHOICE_MIN
    share_ok = ce['toward_share'] >= SHARE_MIN
    cut_ok = 1 - ce['toward_share'] <= MISS_CUT * (1 - be['toward_share'])
    passed = bool(target_seen and choice_ok and share_ok and cut_ok)
    why = []
    if not target_seen:
        why.append(f"base showed only {be['stuck_turns']} stuck turns by round {EARLY} (need {TARGET_MIN})")
    if not choice_ok:
        why.append(f"the candidate had only {ce['stuck_turns']} stuck turns by round {EARLY} (need {CHOICE_MIN})")
    if not share_ok:
        why.append(f"only {ce['toward_share']:.1%} of the candidate's stuck turns step toward the edge (need {SHARE_MIN:.0%})")
    if not cut_ok:
        why.append('the share of stuck turns not stepping toward the edge did not fall by a third against base')

    maps = sorted({k[0] for k in keys})
    by_map = {}
    for m in maps:
        mb, mc = (view(rows[k] for k in keys if k[0] == m) for rows in (base, cand))
        by_map[m] = {t: {'games': v['games'], 'wins': v['wins'], 'stuck_turns': v['to_round_150']['stuck_turns'],
                         'toward_edge': v['to_round_150']['toward_edge'], 'toward_share': v['to_round_150']['toward_share'],
                         'stuck_spell_mean_turns': v['stuck_spell_mean_turns'],
                         'map_share_seen_by_round': v['map_share_seen_by_round']}
                     for t, v in (('base', mb), ('candidate', mc))}

    def pick(rows, field, size):
        found = [x for k in keys for x in rows[k][field] if x['from_round'] <= EARLY]
        found.sort(key=lambda x: (-x[size], x['game'], x['from_round'], x['dragon']))
        return found[:8]

    def seen(v):
        return '/'.join(f"{v['map_share_seen_by_round'][str(m)]:.0%}" for m in MARKS)

    per_map = '; '.join(f"{m} {by_map[m]['base']['toward_edge']}/{by_map[m]['base']['stuck_turns']} -> "
                        f"{by_map[m]['candidate']['toward_edge']}/{by_map[m]['candidate']['stuck_turns']}" for m in maps)
    note = (f"stuck turns up to round {EARLY} (our non-queen dragon: no growth for {IDLE_ROUNDS} rounds, no remembered pearl "
            f"within {PEARL_STEPS} steps, no enemy head in view, an explored edge it can walk to) whose first step goes "
            f"toward the edge: base {be['toward_edge']}/{be['stuck_turns']} ({be['toward_share']:.1%}) -> switch on "
            f"{ce['toward_edge']}/{ce['stuck_turns']} ({ce['toward_share']:.1%}); per map {per_map}; all rounds "
            f"{bv['all_rounds']['toward_edge']}/{bv['all_rounds']['stuck_turns']} -> "
            f"{cv['all_rounds']['toward_edge']}/{cv['all_rounds']['stuck_turns']}; not gated, {len(keys)} games each: "
            f"a stuck spell lasts {bv['stuck_spell_mean_turns']} -> {cv['stuck_spell_mean_turns']} turns on average "
            f"(spells of {LONG_SPELL}+ turns {bv[f'stuck_spells_of_{LONG_SPELL}_turns_or_more']} -> "
            f"{cv[f'stuck_spells_of_{LONG_SPELL}_turns_or_more']}), map seen by our non-queen dragons by round "
            f"{'/'.join(map(str, MARKS))} {seen(bv)} -> {seen(cv)}, turns on which they grew by round {EARLY} per game "
            f"{bv['grew_turns_to_round_150_per_game']} -> {cv['grew_turns_to_round_150_per_game']}, their deaths per game "
            f"{bv['deaths_per_game']} -> {cv['deaths_per_game']}, queen length at the end "
            f"{bv['queen_length_end_per_game']} -> {cv['queen_length_end_per_game']} (rival queen "
            f"{bv['rival_queen_length_end_per_game']} -> {cv['rival_queen_length_end_per_game']}), queen deaths "
            f"{bv['queen_deaths']} -> {cv['queen_deaths']}, wins {bv['wins']} -> {cv['wins']}"
            + ('' if passed else '. NOT shown: ' + '; '.join(why)))
    out = {'passed': passed, 'note': note, 'target_seen': bool(target_seen), 'pairs': len(keys), 'maps': maps,
           'pass_rule': {'target_min': TARGET_MIN, 'choice_min': CHOICE_MIN, 'share_min': SHARE_MIN,
                         'miss_cut': round(MISS_CUT, 4), 'target_seen': bool(target_seen), 'choice_ok': bool(choice_ok),
                         'share_ok': bool(share_ok), 'cut_ok': bool(cut_ok)},
           'base': bv, 'candidate': cv, 'by_map': by_map,
           'examples': {'longest_walks_toward_the_edge': {'base': pick(base, 'walks', 'steps'),
                                                          'candidate': pick(cand, 'walks', 'steps')},
                        'longest_stuck_spells': {'base': pick(base, 'spells', 'turns'),
                                                 'candidate': pick(cand, 'spells', 'turns')}},
           'limits': ('measured from replays without bot logs: each dragon\'s memory is rebuilt as every 7x7 view it has had '
                      'since it was born (a split-off child starts empty), so single turns can be judged differently from '
                      'the bot; "toward the edge" accepts a step toward any explored edge that is nearer than the nearest '
                      'one was, because ties between equally near edges cannot be told apart; the gate stops at round 150 '
                      'because leaders and feeders, which the card leaves out, cannot be seen in a replay; dragons hunting '
                      'the enemy queen keep their own target and are still counted; a step is only pushed when it is safe '
                      'and within 2500 points of the best step, which a replay cannot show, so some misses are expected; '
                      'the two sides play different games after the first push, so the stuck turns are not the same '
                      'turns; that the queen is never pushed is in the code, not measured here; stuck spells, map seen, '
                      'growth, deaths, queen length and wins are raw counts from a small sample, not evidence of an outcome')}
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
        sys.exit(f'card 43 check failed: {exc}')
