#!/usr/bin/env python3
"""Card #48 queen-sacrifice mechanism check (QUEEN_NO_FEED, second build): with the switch on, does our queen stay
out of the feeding? She must not drop her body for the leader, not split after round 200, and not eat near the
leader. And is the queen the only thing the switch changes?

usage: python3 work/card_48_check.py --replays DIR --base base --candidate candidate --output FILE
Reads paired replays DIR/<tag>_<map>_<seed>_<side>.replay (side 0 = we are team A). The opponent is the base bot
in every game. A pair is the base game and the switch-on game of the same map, seed and side.

Words:
  queen           the dragon with id 0 or 1; each team has one. The game is decided by the queens' lengths.
  leader          the dragon the others feed late in the game. Here: our longest dragon other than the queen.
  drop            a dragon ends its turn with no action and dies on the spot ("no valid action"), which leaves its
                  body as pearls. It is how a feeder gives its length to the leader. A turn the game marks as timed
                  out is counted apart.
  feeding rounds  rounds where the bot's feeding can be on: after round 400, or after round 200 once we have 56
                  dragons.
  small map       600 tiles or fewer. Only there is the base queen a plain dragon (unless her home is closed off):
                  she can be a feeder and she splits like the others. On bigger maps she already keeps to the
                  queen's split rules and, once feeding starts, she is the one the others feed.
  view            the 7x7 box around her head, all the bot sees.
  open step       a neighbouring tile with no wall (kelp) in between and no dragon body on it, from which she can
                  reach at least 3 x her length + 8 free tiles or her own tail (the bot's own test for "not a dead
                  end", rebuilt from the replay with the bodies as they stand that turn).
  roomy step      the same with a lower bar: at least her length + 2 free tiles, or her own tail. With no roomy
                  step the bot calls her stuck and lets her split 2 off to wait in place.
  pressed         an enemy head is in her view at the start of her turn. The bot puts her safety first then, so
                  a split or a pearl taken on such a turn is not held against the switch.
  free split      she splits, in a round after 200, not pressed, with at least one roomy step. The switch stops the
                  growth split (4 into 2 and 2) and the split out of a tight spot; it leaves the splits she makes
                  when an enemy can hit her or when she is stuck.
  near the leader within 9 tiles of the leader's head, wrap-aware (LEADER_PEARL_RADIUS, the zone in which the bot
                  already tells plain dragons to leave pearls to the leader).
  free bite near the leader   in a feeding round she grows on a tile near the leader, where: the leader is longer
                  than her, it was our longest other dragon at her previous turn too and the tile was near its head
                  then as well (the bot goes by the last report it heard, so a leader that just changed or just
                  arrived does not count), she is not pressed, and she had an open step elsewhere.
  first difference  the base and switch-on game of a pair are the same game, event for event, until the switch
                  changes a decision. The first turn that differs is that decision, from an identical position.

Expectation, written before any game was played with this build's switch on (thresholds are the constants below):
  1. only the queen: every pair that differs has its first difference inside our own queen's turn, in a round
     after FIRST_FROM (200; 150 on maps over 1200 tiles, where the leader's zone starts earlier). A pair whose
     queen is dead before that stays the same game to the end.
  2. target seen: queens run by the base bot (ours in the base games, the opponent's in every game) drop at least
     TARGET_MIN times in this run, and our switch-on queen has at least EXPOSED_MIN turns of her own in feeding
     rounds on small maps, so the rules below had turns in which they could be broken.
  3. never drops: our switch-on queen drops 0 times, on any map.
  4. no free split: on small maps our switch-on queen makes 0 free splits.
  5. no free bite near the leader: on small maps our switch-on queen makes 0 free bites near the leader.
  6. it acted: at least ACTED_MIN pairs differ.
passed = all six. target_seen = rule 2. mechanism_shown = rules 1, 3, 4, 5 and 6.
Rules 4 and 5 are judged on small maps only. On bigger maps the switch does not change the split rules, and in
feeding the queen is the one being fed, so "leader = longest other dragon" is not who the bot feeds; the same
counts are reported for those maps without a verdict.
Reported, not part of the verdict (a few games cannot settle them): every split and every bite of our queen after
round 200 with its label; bites on a tile where one of our feeders dropped earlier, near the leader or not; how
often she ended a feeding turn within 1 and within 3 tiles of the leader's head; what the first difference was
and what became of both queens after it; queens alive when feeding starts, final queen lengths, wins, timeouts.
Known before any switch-on game of this build:
- from the first build's 16 pairs (same maps and seeds for tower_defense and default_small; the switch then only
  stopped the drop): this file run on those replays fails rules 4 and 5 and passes the rest. In default_small
  14800 side 1, the game the revision was asked for, the switch-on queen makes 4 free splits (rounds 416, 429,
  451, 463) and 6 bites near the leader, 2 of them free (rounds 413, 432) and 4 while pressed; 4 of her bites are
  on a tile where a feeder had dropped. In tower_defense 14801 side 1 the queen, base and switch-on alike, makes
  4 free splits before feeding (rounds 202, 286, 306, 368), so the base bot shows the split this build stops.
  In the base games of that run our queen was alive when feeding starts in 2 of 16 (tower_defense 14800 side 0,
  default_small 14800 side 1); on weakhold and snake_trap both queens were dead by round 121.
- from this build's 20 switch-off identity games (old 10 maps, 2 seeds): both queens were alive to the end on
  trauma (1152 tiles) and schooltime (2400 tiles) in all 4 games; in the other 16 no queen was alive at round 401.
The game runner drops the bot's log lines (--no-debug), so nothing here reads them.
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, os, sys
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import replay
from card_39_check import load_map

# Expectation thresholds (fixed before any game with this build's switch on)
TARGET_MIN = 2       # drops by base-bot queens needed to call the target seen
EXPOSED_MIN = 30     # feeding-round turns of our switch-on queen on small maps needed to call the target seen
ACTED_MIN = 2        # pairs that must differ to say the switch acted
FIRST_FROM = 200     # QUEEN_SPLIT_ROUND / FEED_CAP_ROUND: the switch changes nothing at or before this round
FIRST_FROM_BIG = 150 # LEADER_GROW_ROUND_BIG: on maps over BIG_CELLS tiles the leader's zone starts here

SPLIT_ROUND = 200    # QUEEN_SPLIT_ROUND
FEED_ROUND = 400     # ENDGAME_ROUND
FEED_FROM = 200      # FEED_CAP_ROUND
CAP_UNITS = 56       # FEED_CAP_UNITS
KEEP_UNITS = 3       # FEEDER_KEEP_UNITS
LEN_RATIO = 2        # FEED_LEN_RATIO
APPROACH = 15        # FEEDER_APPROACH
ZONE = 9             # LEADER_PEARL_RADIUS
VIEW = 3             # the bot sees a 7x7 box around its head
SMALL_CELLS = 600    # QUEEN_MIN_CELLS: the base queen is a plain dragon at or below this
BIG_CELLS = 1200     # AGGRESSIVE_MAX_CELLS
CAUSE = ['wall', 'self', 'body', 'headon', 'no_action']
QUEENS = (0, 1)


def gap(a, b, size):
    raw = abs(a - b)
    return min(raw, size - raw)


def scan(job):
    """One replay: every turn as a short hash, our queen's turns, queen drops and what became of both queens.
    `track` is None for the queens, or (our id, their id) to follow two other dragons (used to test this file)."""
    path, side, track = job
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
    queen = track[0] if track else next((i for i in QUEENS if team_of.get(i) == ours), None)
    foe = track[1] if track else next((i for i in QUEENS if team_of.get(i) != ours), None)
    small = W * H <= SMALL_CELLS

    def dist(a, b):
        return gap(a[0], b[0], W) + gap(a[1], b[1], H)

    def open_steps(body):
        """Neighbouring tiles of her head that are open steps, and how many are roomy steps (see the words above)."""
        taken = {c for b in bodies.values() for c in b}
        tail = body[-1]
        taken.discard(tail)
        need = 3 * len(body) + 8
        found, roomy = [], 0
        for d in 'NESW':
            first = step(body[0], d)
            if first is None or first[0] in taken:
                continue
            seen, frontier, reaches = {first[0]}, [first[0]], first[0] == tail
            while frontier and len(seen) < need and not reaches:
                nxt = []
                for cell in frontier:
                    for e in 'NESW':
                        h = step(cell, e)
                        if h is None or h[0] in taken or h[0] in seen:
                            continue
                        seen.add(h[0])
                        nxt.append(h[0])
                        reaches = reaches or h[0] == tail
                frontier = nxt
            if reaches or len(seen) >= need:
                found.append(list(first[0]))
            roomy += reaches or len(seen) >= len(body) + 2
        return found, roomy

    last = dict(lead=None, heads={})    # the leader and our heads at our queen's previous turn

    def look(rnd):
        body = bodies[queen]
        head = body[0]
        mine = {i: b for i, b in bodies.items() if b and team_of.get(i) == ours}
        rest = {i: len(b) for i, b in mine.items() if i != queen}
        lead = min(rest, key=lambda i: (-rest[i], i)) if rest else None
        feeding = rnd > FEED_ROUND or (rnd > FEED_FROM and len(mine) >= CAP_UNITS)
        lead_len = rest[lead] if lead is not None else 0
        lead_at = bodies[lead][0] if lead is not None else None
        lead_dist = dist(head, lead_at) if lead_at else None
        feeder = bool(small and feeding and len(mine) > KEEP_UNITS and lead is not None
                      and len(body) * LEN_RATIO <= lead_len and lead_dist <= APPROACH)
        pressed = any(b and team_of.get(i) != ours and gap(b[0][0], head[0], W) <= VIEW
                      and gap(b[0][1], head[1], H) <= VIEW for i, b in bodies.items())
        steps, roomy = open_steps(body) if rnd > SPLIT_ROUND else ([], 0)
        turn = dict(round=rnd, len=len(body), start=list(head), end=list(head), units=len(mine), feeding=feeding,
                    lead=lead, lead_len=lead_len, lead_at=list(lead_at) if lead_at else None, lead_dist=lead_dist,
                    lead_was=list(last['heads'][lead]) if lead is not None and last['lead'] == lead
                    and lead in last['heads'] else None,
                    feeder_call=feeder, pressed=pressed, open=steps, roomy=roomy,
                    path=[], bites=[], kind=None, died=None)
        last['lead'], last['heads'] = lead, {i: b[0] for i, b in mine.items()}
        return turn

    turns = []                       # (round, mover, hash of what happened in that turn)
    queen_turns = {}                 # round -> our queen's turn
    drops = []                       # every turn a queen ended with no action
    feeder_drops = {}                # tile -> rounds after FEED_FROM in which one of our other dragons dropped there
    fate = {q: dict(death_round=None, cause=None, own_move=None, len_at_death=None) for q in (queen, foe)}
    alive_at_feed = {queen: False, foe: False}
    len_at_feed = {queen: 0, foe: 0}
    c = Counter()
    rnd, mover, sig, pending, acted = 0, None, None, None, None

    def close():
        nonlocal sig, pending, acted
        if sig is not None:
            turns.append((rnd, mover, sig.hexdigest()[:16]))
        sig, pending, acted = None, None, None

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if kind == 'roundStart':
            close()
            rnd, mover = pl.i32(0), None
            if rnd == FEED_ROUND + 1:
                for q in alive_at_feed:
                    alive_at_feed[q] = bool(bodies.get(q))
                    len_at_feed[q] = len(bodies.get(q) or ())
        elif kind == 'turnStart':
            close()
            mover = pl.i32(0)
            sig = hashlib.sha1()
        elif kind == 'dragonAction':
            did = pl.i32(0)
            a = pl.pointer(0)
            what = a.u16(0) if a else 2
            tle = pl.bit(32)
            detail = ''
            if a is not None and what == 0:
                try:
                    detail = ','.join(str(x) for x in a.pointer(0))
                except Exception:
                    detail = '?'
            elif a is not None and what == 1:
                detail = str(a.i32(4))
            if sig is None:
                mover, sig = did, hashlib.sha1()
            sig.update(f'a{did}:{what}:{detail};'.encode())
            c['timeouts_ours' if team_of.get(did) == ours else 'timeouts_theirs'] += tle
            acted = (did, what, tle)
            if did in (queen, foe) and what == 2 and bodies.get(did):
                drops.append(dict(who='ours' if did == queen else 'theirs', round=rnd, len=len(bodies[did]),
                                  timeout=tle))
            if did == queen and bodies.get(queen):
                pending = look(rnd)
                pending['kind'] = ('move', 'split', 'timeout' if tle else 'drop')[min(what, 2)]
                queen_turns[rnd] = pending
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            h, tp = replay.point(pl.pointer(0)), replay.point(pl.pointer(1))
            if sig is not None:
                sig.update(f'u{did}:{h}:{tp};'.encode())
            b = bodies.setdefault(did, deque())
            before = len(b)
            moved = not b or b[0] != h
            if moved:
                b.appendleft(h)
            while len(b) > 1 and b[-1] != tp:
                b.pop()
            if pending and did == queen and moved:
                pending['end'] = list(h)
                pending['path'].append(list(h))
                if len(b) > before:
                    pending['bites'].append(list(h))
        elif kind == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x) for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
            if sig is not None:
                sig.update(f's{pa}:{ch}:{len(bodies[ch])};'.encode())
        elif kind == 'dragonDeath':
            did, r = pl.i32(0), pl.u16(4)
            b = bodies.pop(did, None)
            cause = CAUSE[r] if r < len(CAUSE) else 'other'
            if sig is not None:
                sig.update(f'd{did}:{r};'.encode())
            if did in fate and fate[did]['death_round'] is None:
                fate[did] = dict(death_round=rnd, cause=cause, own_move=mover == did, len_at_death=len(b or ()))
            if (cause == 'no_action' and b and did != queen and team_of.get(did) == ours and acted
                    and acted[0] == did and not acted[2] and rnd > FEED_FROM):
                c['feeder_drops_ours'] += 1
                for cell in b:
                    feeder_drops.setdefault(cell, []).append(rnd)
            if pending and did == queen:
                pending['died'] = cause
    close()
    for q in fate:
        fate[q]['final_len'] = len(bodies.get(q) or ())
        fate[q]['alive_at_feed'] = alive_at_feed[q]
        fate[q]['len_at_feed'] = len_at_feed[q]

    marks = []                       # our queen's splits and bites after round SPLIT_ROUND, labelled
    for t in queen_turns.values():
        t['end_dist'] = dist(t['end'], t['lead_at']) if t['lead_at'] else None
        if t['round'] <= SPLIT_ROUND:
            continue
        where = dict(round=t['round'], len=t['len'], at=t['start'], feeding=t['feeding'], pressed=t['pressed'],
                     open_steps=len(t['open']), roomy_steps=t['roomy'], lead_len=t['lead_len'],
                     lead_dist=t['lead_dist'])
        if t['kind'] == 'split':
            marks.append(dict(where, what='split', free=bool(not t['pressed'] and t['roomy'])))
        for n, cell in enumerate(t['bites']):
            near = bool(t['lead_at'] and dist(cell, t['lead_at']) <= ZONE)
            steady = bool(near and t['lead_was'] and dist(cell, t['lead_was']) <= ZONE)
            first = n == 0 and cell == t['path'][0]
            elsewhere = [o for o in t['open'] if o != cell] if first else [cell]
            dropped = [r for r in feeder_drops.get(tuple(cell), ()) if r <= t['round']]
            marks.append(dict(where, what='bite', tile=cell, near_leader=near,
                              to_leader=dist(cell, t['lead_at']) if t['lead_at'] else None,
                              leader_longer=t['lead_len'] > t['len'], leader_steady=steady,
                              open_step_elsewhere=bool(elsewhere),
                              feeder_dropped_here=max(dropped) if dropped else None,
                              free=bool(t['feeding'] and near and steady and t['lead_len'] > t['len']
                                        and not t['pressed'] and elsewhere)))
    return dict(cells=W * H, win=int(winner == ours), queen_id=queen, turns=turns, queen_turns=queen_turns, drops=drops,
                marks=marks, queen=fate[queen], foe_queen=fate[foe], counts=dict(c))


def collect(directory, tag):
    jobs, keys = [], []
    for p in sorted(glob.glob(os.path.join(directory, f'{tag}_*.replay'))):
        stem = os.path.basename(p)[len(tag) + 1:-len('.replay')]
        m, seed, side = stem.rsplit('_', 2)
        jobs.append((p, side, None))
        keys.append((m, seed, side))
    with cf.ProcessPoolExecutor(int(os.environ.get('CHECK_WORKERS', '4'))) as pool:
        return dict(zip(keys, pool.map(scan, jobs)))


def first_difference(base, cand):
    """Index into the turn lists of the first turn that differs, or None when the two games are the same game."""
    a, b = base['turns'], cand['turns']
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def brief(turn):
    if turn is None:
        return None
    out = {k: turn[k] for k in ('kind', 'len', 'start', 'end', 'lead_len', 'lead_dist', 'end_dist', 'feeding',
                                'feeder_call', 'pressed', 'died')}
    out['bit'] = bool(turn['bites'])
    out['open_steps'] = len(turn['open'])
    out['roomy_steps'] = turn['roomy']
    return out


def after(game, rnd):
    """What became of our queen from round `rnd` on."""
    drop = next((d for d in game['drops'] if d['who'] == 'ours' and d['round'] >= rnd and not d['timeout']), None)
    q = game['queen']
    if drop:
        return f"dropped in round {drop['round']} at length {drop['len']}"
    if q['death_round'] is not None:
        return f"died in round {q['death_round']} ({q['cause']}, {'her own move' if q['own_move'] else 'not her move'})"
    return f"alive at the end, length {q['final_len']}"


def share(n, d):
    return round(n / d, 3) if d else None


def tally(rows, small):
    """Our queen's splits, bites and feeding turns over the games whose map is small (or not)."""
    rows = [g for g in rows if (g['cells'] <= SMALL_CELLS) == small]
    marks = [m for g in rows for m in g['marks']]
    splits = [m for m in marks if m['what'] == 'split']
    bites = [m for m in marks if m['what'] == 'bite']
    fed = [m for m in bites if m['feeding']]
    turns = [t for g in rows for t in g['queen_turns'].values() if t['feeding']]
    known = [t for t in turns if t['end_dist'] is not None]
    return dict(games=len(rows), feeding_turns=len(turns),
                games_with_feeding_turns=sum(any(t['feeding'] for t in g['queen_turns'].values()) for g in rows),
                drops_by_our_other_dragons_after_200=sum(g['counts'].get('feeder_drops_ours', 0) for g in rows),
                splits_after_200=len(splits), free_splits=sum(m['free'] for m in splits),
                splits_pressed=sum(m['pressed'] for m in splits),
                splits_stuck=sum(not m['pressed'] and not m['roomy_steps'] for m in splits),
                bites_after_200=len(bites), bites_in_feeding=len(fed),
                bites_in_feeding_near_leader=sum(m['near_leader'] for m in fed),
                free_bites_near_leader=sum(m['free'] for m in fed),
                near_leader_bites_pressed=sum(m['near_leader'] and m['pressed'] for m in fed),
                near_leader_bites_no_open_step_elsewhere=sum(m['near_leader'] and not m['pressed']
                                                             and not m['open_step_elsewhere'] for m in fed),
                near_leader_bites_leader_not_steady=sum(m['near_leader'] and not m['pressed']
                                                        and m['open_step_elsewhere']
                                                        and not (m['leader_steady'] and m['leader_longer'])
                                                        for m in fed),
                bites_where_a_feeder_dropped=sum(m['feeder_dropped_here'] is not None for m in fed),
                bites_where_a_feeder_dropped_not_near_leader=sum(m['feeder_dropped_here'] is not None
                                                                 and not m['near_leader'] for m in fed),
                feeding_turns_ended_within_1_of_leader=sum(t['end_dist'] <= 1 for t in known),
                feeding_turns_ended_within_3_of_leader=sum(t['end_dist'] <= 3 for t in known),
                feeding_turns_ended_within_3_share=share(sum(t['end_dist'] <= 3 for t in known), len(known)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--replays', required=True)
    ap.add_argument('--base', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    base, cand = collect(a.replays, a.base), collect(a.replays, a.candidate)
    if not base or not cand:
        sys.exit('no replays found for one of the tags')
    if set(base) != set(cand):
        sys.exit(f'unpaired replays: {sorted(set(base) ^ set(cand))}')
    keys = sorted(base)
    games = len(keys)

    pairs = []
    for key in keys:
        b, c = base[key], cand[key]
        i = first_difference(b, c)
        row = dict(map=key[0], seed=key[1], side=key[2], cells=b['cells'], differs=i is not None,
                   base_win=b['win'], candidate_win=c['win'],
                   base_queen=b['queen'], candidate_queen=c['queen'],
                   base_queen_drops=[d for d in b['drops'] if d['who'] == 'ours'],
                   candidate_queen_drops=[d for d in c['drops'] if d['who'] == 'ours'],
                   base_queen_marks=b['marks'], candidate_queen_marks=c['marks'])
        if i is not None:
            rnd, mover, _ = (b['turns'] if i < len(b['turns']) else c['turns'])[i]
            bt, ct = b['queen_turns'].get(rnd), c['queen_turns'].get(rnd)
            both = i < len(b['turns']) and i < len(c['turns']) and b['turns'][i][:2] == c['turns'][i][:2]
            queen_turn = both and mover == b['queen_id'] and bt is not None and ct is not None
            label = None
            if queen_turn:
                near = any(m['what'] == 'bite' and m['round'] == rnd and m['near_leader'] for m in b['marks'])
                label = ('base queen drops' if bt['kind'] == 'drop' else
                         'base queen splits' if bt['kind'] == 'split' else
                         'base queen bites near the leader' if near else
                         'base queen is a feeder' if bt['feeder_call'] else 'other')
            row.update(first_difference_round=rnd, first_difference_in_queen_turn=bool(queen_turn),
                       first_difference_from=FIRST_FROM_BIG if b['cells'] > BIG_CELLS else FIRST_FROM,
                       first_difference_label=label,
                       base_turn=brief(bt) if queen_turn else None, candidate_turn=brief(ct) if queen_turn else None,
                       base_queen_after=after(b, rnd), candidate_queen_after=after(c, rnd))
        pairs.append(row)

    differ = [p for p in pairs if p['differs']]
    same = [p for p in pairs if not p['differs']]
    in_rule = [p for p in differ
               if p['first_difference_in_queen_turn'] and p['first_difference_round'] > p['first_difference_from']]
    labels = Counter(p['first_difference_label'] for p in in_rule)

    def drops(rows, who):
        return [d for g in rows for d in g['drops'] if d['who'] == who and not d['timeout']]

    base_ours = drops(base.values(), 'ours')
    base_theirs = drops(base.values(), 'theirs') + drops(cand.values(), 'theirs')
    cand_ours = drops(cand.values(), 'ours')
    base_bot_drops = len(base_ours) + len(base_theirs)

    def queens(rows):
        rows = list(rows)
        return dict(alive_when_feeding_starts=sum(g['queen']['alive_at_feed'] for g in rows),
                    alive_at_end=sum(g['queen']['death_round'] is None for g in rows),
                    length_when_feeding_starts_sum=sum(g['queen']['len_at_feed'] for g in rows),
                    final_length_sum=sum(g['queen']['final_len'] for g in rows),
                    foe_queen_final_length_sum=sum(g['foe_queen']['final_len'] for g in rows),
                    longer_queen_at_end=sum(g['queen']['final_len'] > g['foe_queen']['final_len'] for g in rows),
                    wins=sum(g['win'] for g in rows),
                    deaths_by_cause=dict(Counter(g['queen']['cause'] for g in rows if g['queen']['cause'])),
                    timeouts=sum(g['counts'].get('timeouts_ours', 0) for g in rows),
                    timeout_no_action_turns=sum(d['timeout'] for g in rows for d in g['drops'] if d['who'] == 'ours'))

    bs, cs = tally(base.values(), True), tally(cand.values(), True)
    bb, cb = tally(base.values(), False), tally(cand.values(), False)
    checks = {
        'only_queen': len(in_rule) == len(differ),
        'target_seen': base_bot_drops >= TARGET_MIN and cs['feeding_turns'] >= EXPOSED_MIN,
        'never_drops': len(cand_ours) == 0,
        'no_free_split': cs['free_splits'] == 0,
        'no_free_bite_near_leader': cs['free_bites_near_leader'] == 0,
        'it_acted': len(differ) >= ACTED_MIN,
    }
    passed = all(checks.values())
    mechanism_shown = all(v for k, v in checks.items() if k != 'target_seen')
    failed = [k for k, v in checks.items() if not v]
    dropped_after = sum(p['base_queen_after'].startswith('dropped') for p in differ)
    cand_alive_after = sum(p['candidate_queen_after'].startswith('alive') for p in differ)
    bq, cq = queens(base.values()), queens(cand.values())
    small = sum(base[k]['cells'] <= SMALL_CELLS for k in keys)
    note = (
        f"{'PASS' if passed else 'FAIL'} ({'all six checks' if passed else 'failed: ' + ', '.join(failed)}). "
        f"{games} paired games, {small} on maps of {SMALL_CELLS} tiles or fewer (small maps). Drops (queen ends her "
        f"turn with no action and dies to feed the leader): base-bot queens {base_bot_drops} (ours in base games "
        f"{len(base_ours)}, the opponent's {len(base_theirs)}), our switch-on queen {len(cand_ours)}. On small maps "
        f"our switch-on queen had {cs['feeding_turns']} turns in feeding rounds in {cs['games_with_feeding_turns']} "
        f"games (base {bs['feeding_turns']} in {bs['games_with_feeding_turns']}). Her splits after round "
        f"{SPLIT_ROUND} there: {cs['splits_after_200']}, of which free (no enemy head in her view and a step with "
        f"room to take) {cs['free_splits']}; base queen {bs['splits_after_200']}, free {bs['free_splits']}. Her bites "
        f"(growing on a tile) in feeding rounds there: {cs['bites_in_feeding']}, within {ZONE} tiles of the "
        f"leader's head {cs['bites_in_feeding_near_leader']}, of which free (leader steady and longer, no enemy "
        f"head in view, an open step elsewhere) {cs['free_bites_near_leader']}; base queen "
        f"{bs['bites_in_feeding']}, near {bs['bites_in_feeding_near_leader']}, free {bs['free_bites_near_leader']}. "
        f"Bites on a tile where one of our feeders had dropped: switch on {cs['bites_where_a_feeder_dropped']} "
        f"({cs['bites_where_a_feeder_dropped_not_near_leader']} of them not near the leader), base "
        f"{bs['bites_where_a_feeder_dropped']}. Feeding turns she ended within 3 tiles of the leader's head: switch "
        f"on {cs['feeding_turns_ended_within_3_of_leader']} of {cs['feeding_turns']} (within 1 tile "
        f"{cs['feeding_turns_ended_within_1_of_leader']}), base {bs['feeding_turns_ended_within_3_of_leader']} of "
        f"{bs['feeding_turns']}. Pairs that differ: {len(differ)} of {games}; first difference inside our queen's "
        f"own turn after the switch's first round in {len(in_rule)} of them ({dict(labels)}). After it, the base "
        f"queen went on to drop in {dropped_after} of {len(differ)} pairs; the switch-on queen was alive at the end "
        f"in {cand_alive_after}. Our queen alive when feeding starts (round {FEED_ROUND + 1}): base "
        f"{bq['alive_when_feeding_starts']}, switch on {cq['alive_when_feeding_starts']} of {games}. Bigger maps, "
        f"not judged for splits and bites: {games - small} games, switch-on queen feeding turns "
        f"{cb['feeding_turns']}, splits after round {SPLIT_ROUND} {cb['splits_after_200']} (base "
        f"{bb['splits_after_200']}), bites in feeding rounds {cb['bites_in_feeding']} (base "
        f"{bb['bites_in_feeding']}). Raw, not judged: queen length at the end, summed, ours:theirs base "
        f"{bq['final_length_sum']}:{bq['foe_queen_final_length_sum']}, switch on "
        f"{cq['final_length_sum']}:{cq['foe_queen_final_length_sum']}; wins base {bq['wins']}, switch on "
        f"{cq['wins']} of {games}.")
    out = {
        'passed': passed,
        'note': note,
        'target_seen': checks['target_seen'],
        'mechanism_shown': mechanism_shown,
        'checks': checks,
        'thresholds': {'TARGET_MIN': TARGET_MIN, 'EXPOSED_MIN': EXPOSED_MIN, 'ACTED_MIN': ACTED_MIN,
                       'FIRST_FROM': FIRST_FROM, 'FIRST_FROM_BIG': FIRST_FROM_BIG},
        'games': games,
        'games_on_small_maps': small,
        'queen_drops': {'base_bot_all': base_bot_drops, 'base_ours': len(base_ours), 'base_bot_opponent': len(base_theirs),
                        'candidate_ours': len(cand_ours)},
        'queen_drop_rounds': {'base_ours': sorted(d['round'] for d in base_ours),
                              'base_bot_opponent': sorted(d['round'] for d in base_theirs),
                              'candidate_ours': sorted(d['round'] for d in cand_ours)},
        'our_queen_small_maps': {'base': bs, 'candidate': cs},
        'our_queen_bigger_maps': {'base': bb, 'candidate': cb},
        'pairs_that_differ': len(differ),
        'pairs_same_game_to_the_end': len(same),
        'pairs_same_game_queen_dead_before_feeding': sum(not p['base_queen']['alive_at_feed'] for p in same),
        'pairs_first_difference_in_queen_turn_after_first_round': len(in_rule),
        'first_difference_rounds': sorted(p['first_difference_round'] for p in differ),
        'first_difference_labels': dict(labels),
        'after_first_difference': {'base_queen_dropped': dropped_after, 'candidate_queen_alive_at_end': cand_alive_after},
        'our_queen': {'base': bq, 'candidate': cq},
        'limits': 'The leader is taken to be our longest other dragon, and "near", "open step" and "feeder" are '
                  'rebuilt from true lengths and positions; the bot acts on what it has seen or heard, so the labels '
                  'are close, not exact. A bite near the leader that is not counted as free (enemy head in view, no '
                  'open step elsewhere, leader just changed) is listed per pair so a person can look at it. Whether '
                  'a pearl she ate was a dropped body or a fresh pearl on the same tile is not separated. Whether '
                  'her being near the leader cost it any length is not measured. After the first difference the two '
                  'games of a pair drift apart for many reasons, so what became of the queens later, lengths and '
                  'wins are raw numbers, not effects of the switch. A queen that is dead before round 200 shows '
                  'nothing either way.',
        'pairs': pairs,
    }
    with open(a.output, 'w') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print(note)


if __name__ == '__main__':
    main()
