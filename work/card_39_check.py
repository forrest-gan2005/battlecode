#!/usr/bin/env python3
"""Card #39 queen-safety mechanism check (QUEEN_SAFETY, second build): does our queen stay off tiles an enemy head can
hit, what does she do when she is trapped, and how does she treat the enemy queen?

usage: python3 work/card_39_check.py --replays DIR --base base --candidate candidate --output FILE
Replays are DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1), paired by (map, seed, side).

For every action of our queen it rebuilds, from the replay alone, what she could see when she decided (the 7x7 box
around her head) and the "hit zone": every tile a visible enemy head can walk onto this turn with its free steps
(ceil(length/4): 1 for length 2-4, 2 for 5-8, 3 for 9-12 ...; length = the most parts she has seen of that enemy in
the last 3 rounds, as the bot remembers it). Kelp walls and portals are walked, other dragons' bodies block.
New in this build: the ENEMY QUEEN is left out of the hit zone (our queen is meant to treat her like any other
dragon), and is tracked on her own.

  step-in   = she moved and her head ended on a hit-zone tile
  contact   = at least one tile she could walk onto was in the hit zone (the rule had something to say)
  stuck     = contact, and no tile she could walk onto was both outside the hit zone and roomy enough (a dead-end
              pocket where she can reach neither her tail nor length + 2 tiles does not count as a way out)
  wait      = she split 2 off her tail and stayed where she was. It only helps when her own tile is out of reach,
              and needs a queen of length 4+
  trapped   = stuck, and waiting is no use: she is shorter than 4, or an enemy head can also reach the tile she is on
  avoidable = she was not stuck, or she was stuck but could wait
  QS log    = with the switch on the bot writes one log line on a turn it found no safe step: "sprint" (left on free
              steps), "wait", "paid" (left by paying length for extra steps) or "plain" (trapped: moved by the normal
              dragon rules for that turn). These are the bot's own marks, read from the replay.
  go        = the enemy queen's head is in view and the normal dragon rules say "hit her": our queen is 4 or shorter,
              their queen looks at least as long (on maps over 1200 tiles: 5+ and at least 2 longer), we are not
              outnumbered in view and her head is within ram reach; or their queen looks 10+ long and 4+ longer than
              ours. Only judged early (round <= 300, or <= 150 on maps over 1200 tiles), while the bot's trade rule is
              surely on and our queen is not yet the leader.

PASS RULE (fixed before any switch-on game of this build was played; the constants are below):
  1. target seen: base shows at least TARGET_MIN avoidable step-ins;
  2. cut: switch-on avoidable step-ins per avoidable contact decision are at most CUT x base's, overall and in each
     map-size group (600 tiles or fewer / bigger) where base shows at least TARGET_MIN;
  3. waiting, judged only if it comes up: with at least STUCK_MIN switch-on stuck decisions where she could wait, at
     least STUCK_OK of them end without a step-in;
  4. trapped, judged only if it comes up: with at least TRAP_MIN switch-on trapped decisions, the bot's own QS log
     shows on at least TRAP_OK of them that it also found no safe step and took the fallback path;
  5. enemy queen, judged only if it comes up: with at least GO_MIN switch-on "go" decisions, at least GO_OK of them
     end with our queen hitting the enemy queen head-on that turn.
Rules 3-5 report "not seen" below their minimum and do not fail the check then.
What the trapped queen then does (step-in, hit a head herself, left the zone, died), queen deaths, rams, lengths and
wins are raw numbers and NOT part of the pass rule: 16 games per side cannot settle them, the outcome A/B does.
Known before this build (first build's run, same 4 maps, 16 games per side): base 5 avoidable step-ins in 66 contact
decisions, switch on 0 in 70; trapped (then "cornered, 2-3 long") 4 in base and 10 with the switch on, all step-ins.
"""
import argparse, glob, json, os, sys, concurrent.futures as cf
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before any switch-on game of this build)
TARGET_MIN = 5       # base avoidable step-ins needed to call the target seen (overall and per map group)
CUT = 0.25           # switch-on avoidable step-ins per avoidable contact decision: at most this fraction of base's
STUCK_MIN = 5        # switch-on stuck decisions where she could wait, needed to judge the waiting rule
STUCK_OK = 0.75      # share of those that must end without a step-in
TRAP_MIN = 5         # switch-on trapped decisions needed to judge the trapped rule
TRAP_OK = 0.70       # share of those where the bot's own QS log must show the fallback path
GO_MIN = 3           # switch-on "go" decisions needed to judge the enemy-queen rule
GO_OK = 0.75         # share of those that must end with our queen hitting the enemy queen

VIEW = 3             # the bot sees a 7x7 box around its head
GHOST_ROUNDS = 3     # how long the bot remembers an enemy's size
FREE_DIV = 4         # free steps per turn = ceil(length / 4)
WAIT_MIN = 4         # shortest queen that can split 2 off and keep 2
SMALL_CELLS = 600    # QUEEN_MIN_CELLS: base only has queen caution above this (or once home is closed off)
SOFT_MAX = 8         # QUEEN_REACH_MAX
BOLD_CELLS = 1200    # AGGRESSIVE_MAX_CELLS: at or below, an equal-length trade counts as worth it
TRADE_MAX = 4        # TRADE_MAX_LENGTH: only dragons this short trade
HUNT_MAX = 10        # HUNT_MAX_LENGTH
HUNT_PARTS = 10      # HUNT_MIN_PARTS
HUNT_MARGIN = 4
QS_TAGS = ('sprint', 'wait', 'paid', 'plain')
CAUSE = ['wall', 'self', 'body', 'headon', 'none']
DIRS = 'NESW'


def load_map(text):
    """Returns W, H and step(cell, d) -> (next cell, through a portal) or None for kelp / an unpaired portal."""
    lines = text.splitlines()
    W, H = map(int, lines[0].split()[1:3])
    S = 2 * (W + 1)
    kind, pid_of, members = {}, {}, {}
    for l in lines:
        q = l.split()
        if not q or q[0] != 'EDGE':
            continue
        i, t = int(q[1]), int(q[2])
        if t == 0:
            continue
        y, r = divmod(i, S)
        if r < W + 1:
            if r == W:
                continue
            key = ('N', r, y % H)
        else:
            if y >= H:
                continue
            key = ('W', (r - (W + 1)) % W, y)
        if t >= kind.get(key, 0):
            kind[key] = t
            if t == 2 and len(q) > 3:
                pid_of[key] = int(q[3])
    for key, pid in pid_of.items():
        if kind.get(key) == 2:
            members.setdefault(pid, []).append(key)
    pair = {}
    for keys in members.values():
        if len(keys) == 2 and keys[0][0] == keys[1][0]:
            pair[keys[0]], pair[keys[1]] = keys[1], keys[0]

    def step(cell, d):
        x, y = cell
        if d == 'N':
            key, straight = ('N', x, y), (x, (y - 1) % H)
        elif d == 'S':
            key, straight = ('N', x, (y + 1) % H), (x, (y + 1) % H)
        elif d == 'W':
            key, straight = ('W', x, y), ((x - 1) % W, y)
        else:
            key, straight = ('W', (x + 1) % W, y), ((x + 1) % W, y)
        t = kind.get(key, 0)
        if t == 0:
            return straight, False
        other = pair.get(key) if t == 2 else None
        if other is None:
            return None
        _, bx, by = other
        if d == 'N':
            return (bx, (by - 1) % H), True
        if d == 'W':
            return ((bx - 1) % W, by), True
        return (bx, by), True

    return W, H, step


def gap(a, b, size):
    raw = abs(a - b)
    return min(raw, size - raw)


def free_steps(parts):
    return max(1, (parts + FREE_DIV - 1) // FREE_DIV)


def soft_reach(parts):
    return min(SOFT_MAX, max(2, (parts + FREE_DIV - 1) // FREE_DIV + parts - 1))


def flood(step, start, reach, blocked, target):
    """Tiles a head on `start` can walk onto within `reach` steps; also whether it can walk onto `target`."""
    dist = {start: 0}
    frontier = [start]
    reached, touches = set(), False
    for n in range(reach):
        nxt = []
        for cell in frontier:
            for d in DIRS:
                hop = step(cell, d)
                if hop is None:
                    continue
                to = hop[0]
                if to == target:
                    touches = True
                if to in dist or to in blocked:
                    continue
                dist[to] = n + 1
                reached.add(to)
                nxt.append(to)
        frontier = nxt
    return reached, touches


def walk_dist(step, start, target, blocked, limit):
    """Steps from `start` onto `target` through free tiles, or None beyond `limit`."""
    seen = {start}
    frontier = [start]
    for n in range(limit):
        nxt = []
        for cell in frontier:
            for d in DIRS:
                hop = step(cell, d)
                if hop is None:
                    continue
                to = hop[0]
                if to == target:
                    return n + 1
                if to in seen or to in blocked:
                    continue
                seen.add(to)
                nxt.append(to)
        frontier = nxt
    return None


def fits(step, start, body, others):
    """Bot-style room test for the queen stepping onto `start`: she can reach her tail or at least length + 2 tiles."""
    size = len(body)
    free_at = {cell: size - k + 1 for k, cell in enumerate(body)}
    steps = {start: 1}
    frontier = [start]
    while frontier:
        nxt = []
        for cell in frontier:
            for d in DIRS:
                hop = step(cell, d)
                if hop is None:
                    continue
                to = hop[0]
                arrive = steps[cell] + 1
                if to in steps or to in others or arrive < free_at.get(to, 0):
                    continue
                steps[to] = arrive
                if to == body[-1] or len(steps) >= size + 2:
                    return True
                nxt.append(to)
        frontier = nxt
    return False


def go_rule(size, parts, rnd, cells, allies, enemies, units, dist):
    """The normal dragon rules for hitting an enemy head, applied to the enemy queen. None = not judged this late."""
    bold = cells <= BOLD_CELLS
    if rnd > (300 if bold else 150):
        return None
    reach = (size + FREE_DIV - 1) // FREE_DIV + size - 2
    hunt = size <= HUNT_MAX and parts >= HUNT_PARTS and parts >= size + HUNT_MARGIN
    worth = parts >= size if bold else parts >= max(5, size + 2)
    trade = size <= TRADE_MAX and units >= (1 if bold else 8) and allies + 1 - enemies >= 1 and worth
    if dist is None:
        return False
    return bool((hunt and dist <= min(reach, 8)) or (trade and dist <= min(reach, 3 if bold else 4)))


def one(job):
    path, side = job
    ours = 'A' if side == '0' else 'B'
    root = replay.load(path).root()
    text = root.text(0)
    W, H, step = load_map(text)
    result = root.pointer(4)
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None
    bodies, team_of = {}, {}
    for line in text.splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
    queen = next((i for i in (0, 1) if team_of.get(i) == ours), None)
    foe_queen = next((i for i in (0, 1) if team_of.get(i) != ours), None)
    c = Counter(games=1, win=int(winner == ours))
    events = list(root.pointer(3))

    # The bot's own QS marks, by round.
    marks = {}
    rnd = 0
    for ev in events:
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        if kind == 'roundStart':
            rnd = ev.pointer(0).i32(0)
        elif kind == 'dragonLog':
            pl = ev.pointer(0)
            words = pl.text(0).split()
            if pl.i32(0) == queen and len(words) >= 2 and words[0] == 'QS' and words[1] in QS_TAGS:
                marks[rnd] = words[1]
                c['qs_' + words[1]] += 1

    memory = {}
    pending = None
    exposed = None       # how her last finished action left her: 'step-in', 'stayed' (waited with her tile in reach) or None
    mover = None
    rnd = 0

    def look():
        body = bodies[queen]
        head = body[0]

        def in_view(cell):
            return gap(cell[0], head[0], W) <= VIEW and gap(cell[1], head[1], H) <= VIEW

        own = set(body)
        seen_block = set(own)
        true_block = set(own)
        seen_block.discard(body[-1])
        true_block.discard(body[-1])
        taken = set(own)
        others = set()
        foes, far, friends = [], [], []
        rival = None
        units = 0
        for did, b in bodies.items():
            if not b:
                continue
            units += team_of.get(did) == ours
            if did == queen:
                continue
            taken.update(b)
            true_block.update(b)
            inside = [cell for cell in b if in_view(cell)]
            seen_block.update(inside)
            others.update(inside)
            if team_of.get(did) == ours:
                if in_view(b[0]):
                    friends.append((b[0], len(inside)))
                continue
            if in_view(b[0]):
                was = memory.get(did)
                parts = max(len(inside), was[1]) if was and rnd - was[0] <= GHOST_ROUNDS else len(inside)
                memory[did] = (rnd, parts)
                if did == foe_queen:
                    rival = (b[0], parts, len(inside))
                else:
                    foes.append((b[0], parts, len(b)))
            elif did != foe_queen and gap(b[0][0], head[0], W) + gap(b[0][1], head[1], H) <= free_steps(len(b)) + 1:
                far.append((b[0], len(b)))
        hit, near, soft, true_hit = set(), set(), set(), set()
        head_hit = False
        for at, parts, real in foes:
            zone, touches = flood(step, at, free_steps(parts), seen_block, head)
            hit |= zone
            head_hit = head_hit or touches
            near |= flood(step, at, 1, seen_block, head)[0]
            soft |= flood(step, at, soft_reach(parts), seen_block, head)[0]
            true_hit |= flood(step, at, free_steps(real), true_block, head)[0]
        for at, real in far:
            true_hit |= flood(step, at, free_steps(real), true_block, head)[0]
        rival_zone, go = set(), None
        if rival:
            at, parts, shown = rival
            rival_zone = flood(step, at, free_steps(parts), seen_block, head)[0] - hit
            go = go_rule(len(body), shown, rnd, W * H, len(friends), len(foes) + 1, units, walk_dist(step, head, at, taken, 8))
        walk = []
        for d in DIRS:
            hop = step(head, d)
            if hop is not None and not hop[1] and hop[0] not in taken:
                walk.append(hop[0])
        contact = any(t in hit for t in walk)
        safe = contact and any(t not in hit and fits(step, t, body, others) for t in walk)
        return dict(start=head, end=head, len=len(body), rnd=rnd, view=bool(foes), hit=hit, near=near, soft=soft,
                    true_hit=true_hit, head_hit=head_hit, contact=contact, stuck=contact and not safe,
                    all_hit=contact and all(t in hit for t in walk), rival=bool(rival), rival_zone=rival_zone, go=go,
                    seen=0, dead=False, cause=None, killed=set())

    def close():
        nonlocal pending, exposed
        p, pending = pending, None
        if p is None:
            return
        exposed = None
        can = p['len'] >= WAIT_MIN and not p['head_hit']
        tier = 'stuck_wait' if can else 'trapped'
        avoidable = can or not p['stuck']
        mark = marks.get(p['rnd'])
        c['decisions'] += 1
        c['view'] += p['view']
        c['contact'] += p['contact']
        c['contact_avoidable'] += p['contact'] and avoidable
        c['stuck'] += p['stuck']
        c['stuck_all_hit'] += p['all_hit']
        c['stuck_wait'] += p['stuck'] and can
        c['trapped'] += p['stuck'] and not can
        c['trapped_short'] += p['stuck'] and p['len'] < WAIT_MIN
        c['trapped_own_tile'] += p['stuck'] and p['len'] >= WAIT_MIN and p['head_hit']
        if p['stuck'] and mark:
            c[tier + '_marked'] += 1
            c[f'{tier}_mark_{mark}'] += 1
        c['marked_not_stuck'] += bool(mark) and not p['stuck']
        hit_rival = foe_queen in p['killed'] and p['dead']
        c['rival_seen'] += p['rival']
        c['queen_hit_rival'] += hit_rival
        if p['rival'] and p['go'] is not None:
            c['rival_judged'] += 1
            c['go'] += p['go']
            c['go_hit'] += p['go'] and hit_rival
            c['no_go_hit'] += (not p['go']) and hit_rival
        if mark == 'plain':
            c['plain_turns'] += 1
            c['plain_own_ram'] += p['dead'] and p['cause'] == 'headon'
            c['plain_died_other'] += p['dead'] and p['cause'] != 'headon'
        if p['kind'] == 'split':
            c['waits'] += 1
            c['waits_stuck'] += p['stuck']
            c['waits_contact'] += p['contact']
            c['waits_stuck_own_tile_in_reach'] += p['stuck'] and p['head_hit']
            if p['stuck']:
                c[tier + '_did_wait'] += 1
            if p['head_hit']:
                exposed = 'stayed'
            return
        if p['kind'] != 'move':
            c['other_actions'] += 1
            if p['stuck']:
                c[tier + '_other'] += 1
            return
        c['moves'] += 1
        c['multi_moves'] += p['n'] >= 2
        c['moves_view'] += p['view']
        if p['dead']:
            c['moves_died'] += 1
            if p['stuck']:
                c[tier + ('_own_ram' if p['cause'] == 'headon' else '_died')] += 1
            return
        c['path_checked'] += 1
        c['path_mismatch'] += p['seen'] != p['n']
        end = p['end']
        inside = end in p['hit']
        c['stepin'] += inside
        c['stepin_avoidable'] += inside and avoidable
        c['stepin_next_to_head'] += end in p['near']
        c['stepin_true'] += end in p['true_hit']
        c['soft_end'] += end in p['soft']
        c['rival_moves'] += p['rival']
        c['rival_zone_end'] += end in p['rival_zone']
        if mark == 'plain':
            c['plain_step_in'] += inside
            c['plain_left_zone'] += not inside
        if p['stuck']:
            c[tier + ('_in' if inside else '_out')] += 1
        if inside:
            exposed = 'step-in'

    for ev in events:
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if kind == 'roundStart':
            close()
            mover = None
            rnd = pl.i32(0)
        elif kind == 'dragonAction':
            close()
            mover = pl.i32(0)
            a = pl.pointer(0)
            if mover != queen or a is None or not bodies.get(queen):
                continue
            pending = look()
            what = a.u16(0)
            pending['kind'] = 'move' if what == 0 else 'split' if what == 1 else 'other'
            try:
                pending['n'] = max(1, len(a.pointer(0))) if what == 0 else 0
            except Exception:
                pending['n'] = 1
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            h = replay.point(pl.pointer(0))
            tp = replay.point(pl.pointer(1))
            b = bodies.setdefault(did, deque())
            if not b or b[0] != h:
                if b:
                    c['hops'] += 1
                    c['hop_mismatch'] += all((step(b[0], d) or (None,))[0] != h for d in DIRS)
                b.appendleft(h)
                if pending and did == queen:
                    pending['seen'] += 1
                    pending['end'] = h
            while len(b) > 1 and b[-1] != tp:
                b.pop()
        elif kind == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x) for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
        elif kind == 'dragonDeath':
            did = pl.i32(0)
            r = pl.u16(4)
            b = bodies.pop(did, None)
            cause = CAUSE[r] if r < 5 else 'other'
            if pending:
                pending['killed'].add(did)
            if did == foe_queen and cause == 'headon' and mover == foe_queen and pending is None:
                c['rival_moved_into_a_head'] += 1
            if did != queen:
                continue
            if pending:
                pending['dead'] = True
                pending['cause'] = cause
            c['queen_deaths'] += 1
            c[f'queen_deaths_{cause}'] += 1
            c['queen_death_round_sum'] += rnd
            c['queen_death_short'] += len(b or ()) < WAIT_MIN
            if cause == 'headon' and mover == queen:
                c['queen_own_ram'] += 1
            elif cause == 'headon':
                c['queen_rammed'] += 1
                c['queen_rammed_by_rival'] += mover == foe_queen
                c['queen_rammed_after_step_in'] += exposed == 'step-in'
                c['queen_rammed_after_staying'] += exposed == 'stayed'
    close()
    c['queen_final_len'] = len(bodies.get(queen) or ())
    c['foe_queen_final_len'] = len(bodies.get(foe_queen) or ())
    return 'small' if W * H <= SMALL_CELLS else 'big', dict(c)


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
        s.update(r)
    return s


def share(a, b):
    return a / b if b else 0.0


def stuck_view(s, tier):
    return {'decisions': s[tier], 'waited': s[tier + '_did_wait'], 'left_the_zone': s[tier + '_out'],
            'stepped_in': s[tier + '_in'], 'hit_a_head_herself': s[tier + '_own_ram'], 'died_moving': s[tier + '_died'],
            'other': s[tier + '_other'], 'with_a_bot_QS_mark': s[tier + '_marked'],
            'bot_QS_marks': {t: s[f'{tier}_mark_{t}'] for t in QS_TAGS if s[f'{tier}_mark_{t}']}}


def view(s):
    g = max(1, s['games'])
    return {'games': s['games'], 'wins': s['win'],
            'queen_decisions': s['decisions'], 'with_enemy_head_in_view': s['view'],
            'contact_decisions': s['contact'], 'avoidable_contact_decisions': s['contact_avoidable'],
            'step_ins': s['stepin'], 'avoidable_step_ins': s['stepin_avoidable'],
            'avoidable_step_ins_per_contact': round(share(s['stepin_avoidable'], s['contact_avoidable']), 4),
            'step_ins_right_next_to_a_head': s['stepin_next_to_head'],
            'step_ins_by_true_enemy_length': s['stepin_true'],
            'stuck_decisions': s['stuck'], 'of_those_with_every_walkable_tile_in_the_zone': s['stuck_all_hit'],
            'stuck_could_wait': stuck_view(s, 'stuck_wait'),
            'stuck_could_wait_no_step_in_share': round(share(s['stuck_wait_did_wait'] + s['stuck_wait_out'], s['stuck_wait']), 4),
            'trapped': stuck_view(s, 'trapped'),
            'trapped_shorter_than_4': s['trapped_short'], 'trapped_4plus_with_own_tile_in_reach': s['trapped_own_tile'],
            'trapped_with_a_bot_QS_mark_share': round(share(s['trapped_marked'], s['trapped']), 4),
            'bot_QS_marks': {t: s['qs_' + t] for t in QS_TAGS},
            'bot_QS_marks_where_rebuild_saw_a_safe_step': s['marked_not_stuck'],
            'bot_plain_turns': {'turns': s['plain_turns'], 'stepped_in': s['plain_step_in'], 'ended_outside_the_zone': s['plain_left_zone'],
                                'hit_a_head_herself': s['plain_own_ram'], 'died_otherwise': s['plain_died_other']},
            'enemy_queen_in_view_decisions': s['rival_seen'], 'of_those_judged_early': s['rival_judged'],
            'go_decisions': s['go'], 'go_decisions_ending_in_a_hit': s['go_hit'],
            'go_hit_share': round(share(s['go_hit'], s['go']), 4),
            'hits_on_enemy_queen_without_go': s['no_go_hit'], 'our_queen_hit_enemy_queen': s['queen_hit_rival'],
            'moves_with_enemy_queen_in_view': s['rival_moves'],
            'of_those_ending_where_only_the_enemy_queen_could_hit': s['rival_zone_end'],
            'queen_waits': s['waits'], 'queen_waits_while_stuck': s['waits_stuck'],
            'waits_while_stuck_with_her_own_tile_in_reach': s['waits_stuck_own_tile_in_reach'],
            'length_shed_by_stuck_waits': 2 * s['waits_stuck'],
            'queen_moves': s['moves'], 'queen_multi_step_moves': s['multi_moves'],
            'queen_moves_with_enemy_in_view': s['moves_view'], 'of_those_ending_inside_wider_danger_zone': s['soft_end'],
            'wider_danger_zone_share': round(share(s['soft_end'], s['moves_view']), 4),
            'queen_deaths': s['queen_deaths'],
            'queen_deaths_by_cause': {k: s[f'queen_deaths_{k}'] for k in CAUSE if s[f'queen_deaths_{k}']},
            'queen_deaths_while_shorter_than_4': s['queen_death_short'],
            'queen_rammed_by_enemy_head': s['queen_rammed'], 'of_those_by_the_enemy_queen': s['queen_rammed_by_rival'],
            'rammed_right_after_a_step_in': s['queen_rammed_after_step_in'],
            'rammed_after_waiting_in_reach': s['queen_rammed_after_staying'],
            'queen_rammed_a_head_herself': s['queen_own_ram'],
            'queen_death_round_mean': round(share(s['queen_death_round_sum'], s['queen_deaths']), 1),
            'queen_final_length_per_game': round(s['queen_final_len'] / g, 2),
            'enemy_queen_final_length_per_game': round(s['foe_queen_final_len'] / g, 2)}


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
    groups = ('small', 'big')
    b = {g: total(base[k][1] for k in keys if base[k][0] == g) for g in groups}
    c = {g: total(cand[k][1] for k in keys if cand[k][0] == g) for g in groups}
    ball, call = total(b.values()), total(c.values())
    moves = ball['path_checked'] + call['path_checked']
    hops = ball['hops'] + call['hops']
    if moves and ball['path_mismatch'] + call['path_mismatch'] > 0.02 * moves:
        sys.exit('replay moves do not line up with head updates; the measurement is not valid')
    if hops and ball['hop_mismatch'] + call['hop_mismatch'] > 0.005 * hops:
        sys.exit('head moves do not follow the rebuilt walls and portals; the measurement is not valid')

    bv, cv = view(ball), view(call)

    def rate(s):
        return share(s['stepin_avoidable'], s['contact_avoidable'])

    target_seen = ball['stepin_avoidable'] >= TARGET_MIN
    cut_ok = rate(call) <= CUT * rate(ball)
    group_rule = {}
    for g in groups:
        seen = b[g]['stepin_avoidable'] >= TARGET_MIN
        group_rule[g] = {'games': b[g]['games'], 'target_seen': bool(seen),
                         'cut_ok': bool(rate(c[g]) <= CUT * rate(b[g])) if seen else None}
    groups_ok = all(r['cut_ok'] for r in group_rule.values() if r['target_seen'])
    wait_seen = call['stuck_wait'] >= STUCK_MIN
    wait_ok = cv['stuck_could_wait_no_step_in_share'] >= STUCK_OK if wait_seen else None
    trap_seen = call['trapped'] >= TRAP_MIN
    trap_ok = cv['trapped_with_a_bot_QS_mark_share'] >= TRAP_OK if trap_seen else None
    go_seen = call['go'] >= GO_MIN
    go_ok = cv['go_hit_share'] >= GO_OK if go_seen else None
    passed = bool(target_seen and cut_ok and groups_ok and wait_ok is not False and trap_ok is not False and go_ok is not False)
    why = []
    if not target_seen:
        why.append(f"base showed only {ball['stepin_avoidable']} avoidable step-ins (need {TARGET_MIN})")
    if not cut_ok:
        why.append('avoidable step-ins per contact decision did not fall to a quarter of base')
    if not groups_ok:
        why.append('the cut failed on ' + ' and '.join(g for g, r in group_rule.items() if r['target_seen'] and not r['cut_ok']) + ' maps')
    if wait_ok is False:
        why.append('a queen who could wait still stepped in too often when every move was dangerous')
    if trap_ok is False:
        why.append('on trapped turns the bot too rarely marked that it found no safe step')
    if go_ok is False:
        why.append('our queen too rarely hit the enemy queen when the normal rules said go')

    def stuck_text(v, key):
        s = v[key]
        return (f"{s['decisions']} (waited {s['waited']}, left the zone {s['left_the_zone']}, stepped in {s['stepped_in']}, "
                f"hit a head herself {s['hit_a_head_herself']}, died moving {s['died_moving']})")

    unseen = [g for g, r in group_rule.items() if not r['target_seen']]
    plain = cv['bot_plain_turns']
    note = (f"queen moves that end where a visible enemy head (the enemy queen left out) can hit her with its free steps although "
            f"she could have avoided it: base {bv['avoidable_step_ins']} in {bv['avoidable_contact_decisions']} contact decisions "
            f"({bv['avoidable_step_ins_per_contact']:.1%}) -> switch on {cv['avoidable_step_ins']} in "
            f"{cv['avoidable_contact_decisions']} ({cv['avoidable_step_ins_per_contact']:.1%}); by map group: "
            + ', '.join(f"{g} {b[g]['stepin_avoidable']}/{b[g]['contact_avoidable']} -> "
                        f"{c[g]['stepin_avoidable']}/{c[g]['contact_avoidable']} in {b[g]['games']} games" for g in groups)
            + (f" ({' and '.join(unseen)} maps: too few base step-ins to judge on their own)" if unseen else '')
            + f"; no safe step but she could wait: base {stuck_text(bv, 'stuck_could_wait')} -> switch on "
            f"{stuck_text(cv, 'stuck_could_wait')}"
            + ('' if wait_seen else f" - waiting rule NOT seen (needs {STUCK_MIN})")
            + f"; trapped (no safe step, waiting no use): base {stuck_text(bv, 'trapped')} -> switch on {stuck_text(cv, 'trapped')}, "
            f"the bot marked {cv['trapped']['with_a_bot_QS_mark']} of those {cv['trapped']['decisions']} itself {cv['trapped']['bot_QS_marks']}"
            + ('' if trap_seen else f" - trapped rule NOT seen (needs {TRAP_MIN})")
            + f"; bot's own marks with the switch on: {cv['bot_QS_marks']}, and on its {plain['turns']} plain-rule turns she stepped in "
            f"{plain['stepped_in']}, ended outside the zone {plain['ended_outside_the_zone']}, hit a head herself "
            f"{plain['hit_a_head_herself']}, died otherwise {plain['died_otherwise']}"
            f"; enemy queen in view: {bv['enemy_queen_in_view_decisions']} -> {cv['enemy_queen_in_view_decisions']} decisions, "
            f"'go' by the normal rules {bv['go_decisions']} -> {cv['go_decisions']}, of those ending with our queen hitting her "
            f"{bv['go_decisions_ending_in_a_hit']} -> {cv['go_decisions_ending_in_a_hit']}"
            + ('' if go_seen else f" - enemy-queen rule NOT seen (needs {GO_MIN})")
            + f", all hits on the enemy queen by ours {bv['our_queen_hit_enemy_queen']} -> {cv['our_queen_hit_enemy_queen']}, moves ending "
            f"where only the enemy queen could hit her {bv['of_those_ending_where_only_the_enemy_queen_could_hit']}/"
            f"{bv['moves_with_enemy_queen_in_view']} -> {cv['of_those_ending_where_only_the_enemy_queen_could_hit']}/"
            f"{cv['moves_with_enemy_queen_in_view']}"
            f"; not gated, {len(keys)} games each: all step-ins {bv['step_ins']} -> {cv['step_ins']}, moves ending inside the "
            f"wider x4 danger zone {bv['wider_danger_zone_share']:.1%} -> {cv['wider_danger_zone_share']:.1%} of moves with an "
            f"enemy head in view, queen deaths {bv['queen_deaths']} -> {cv['queen_deaths']} (rammed by an enemy head "
            f"{bv['queen_rammed_by_enemy_head']} -> {cv['queen_rammed_by_enemy_head']}, of those right after a step-in "
            f"{bv['rammed_right_after_a_step_in']} -> {cv['rammed_right_after_a_step_in']}; rammed a head herself "
            f"{bv['queen_rammed_a_head_herself']} -> {cv['queen_rammed_a_head_herself']}), queen length at the end "
            f"{bv['queen_final_length_per_game']} -> {cv['queen_final_length_per_game']} per game, length shed by waits "
            f"{bv['length_shed_by_stuck_waits']} -> {cv['length_shed_by_stuck_waits']}, wins {bv['wins']} -> {cv['wins']}"
            + ('' if passed else '. NOT shown: ' + '; '.join(why)))
    out = {'passed': passed, 'note': note, 'target_seen': bool(target_seen), 'waiting_rule_seen': bool(wait_seen),
           'trapped_rule_seen': bool(trap_seen), 'enemy_queen_rule_seen': bool(go_seen),
           'pairs': len(keys), 'maps': sorted({k[0] for k in keys}),
           'pass_rule': {'target_min': TARGET_MIN, 'cut': CUT, 'stuck_min': STUCK_MIN, 'stuck_ok': STUCK_OK,
                         'trap_min': TRAP_MIN, 'trap_ok': TRAP_OK, 'go_min': GO_MIN, 'go_ok': GO_OK,
                         'target_seen': bool(target_seen), 'cut_ok': bool(cut_ok), 'by_map_group': group_rule,
                         'groups_ok': bool(groups_ok), 'waiting_rule_seen': bool(wait_seen), 'waiting_rule_ok': wait_ok,
                         'trapped_rule_seen': bool(trap_seen), 'trapped_rule_ok': trap_ok,
                         'enemy_queen_rule_seen': bool(go_seen), 'enemy_queen_rule_ok': go_ok},
           'base': bv, 'candidate': cv,
           'by_map_group': {g: {'base': view(b[g]), 'candidate': view(c[g])} for g in groups},
           'model_check': {'queen_moves_checked': moves, 'moves_not_matching_head_updates': ball['path_mismatch'] + call['path_mismatch'],
                           'head_hops': hops, 'hops_not_matching_walls_and_portals': ball['hop_mismatch'] + call['hop_mismatch']},
           'limits': ('measured from replays: the 7x7 view, kelp walls, portals and the remembered enemy size are rebuilt, so a few '
                      'tiles can differ from what the bot marked (it only walks portals it has already seen both ends of, the unit '
                      'cap that forbids a split is not rebuilt, and the dead-end test counts never-seen tiles as full room, so it '
                      'calls fewer tiles dead ends than the bot does); the QS marks are the bot\'s own log lines and exist only '
                      'with the switch on; the "go" rule is a rebuild of the normal trade and hunt rules from what was in view '
                      '(the unit cap and the leader state are not rebuilt, so it is only judged early in the game); whether the '
                      'trapped queen\'s move equals what a normal dragon would do is by construction of the code, not measured; '
                      'enemies out of sight and enemies paying length for extra steps are not in the hit zone; deaths, lengths '
                      'and wins are raw counts from a small sample, not evidence of an outcome')}
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
        sys.exit(f'card 39 check failed: {exc}')
