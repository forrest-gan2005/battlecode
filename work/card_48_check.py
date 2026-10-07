#!/usr/bin/env python3
"""Card #48 queen-sacrifice mechanism check (QUEEN_NO_FEED): with the switch on, does our queen stop dropping
her body to feed the leader, and is that the only thing the switch changes?

usage: python3 work/card_48_check.py --replays DIR --base base --candidate candidate --output FILE
Reads paired replays DIR/<tag>_<map>_<seed>_<side>.replay (side 0 = we are team A). The opponent is the base bot
in every game. A pair is the base game and the switch-on game of the same map, seed and side.

Words:
  queen           the dragon with id 0 or 1; each team has one. The game is decided by the queens' lengths.
  leader          the dragon the others feed late in the game. Here: our longest dragon other than the queen.
  drop            a dragon ends its turn with no action and dies on the spot ("no valid action"), which leaves its
                  body as pearls. It is how a feeder gives its length to the leader. With the release settings the
                  bot ends every other turn with a move or a split, so a drop is always a feeding drop. A turn the
                  game marks as timed out is counted apart.
  feeding rounds  rounds where the bot's feeding can be on: after round 400, or after round 200 once we have 56
                  dragons. Before round 201 it is never on, so the switch has nothing to change there.
  feeder call     rebuilt from the replay, for one queen turn: a map of 600 tiles or fewer (on bigger ones the
                  base queen is never a feeder), feeding rounds, we have more than 3 dragons, the leader is at
                  least twice her length, and its head is within 15 tiles of hers (wrap-aware). That is the rule
                  that makes a plain dragon a feeder. The bot uses what it has heard about the leader, the replay
                  has the true lengths, so this label is close, not exact.
  hunt call       feeding rounds, she is not our longest, and the enemy queen's head is in her 7x7 view with at
                  least 6 parts showing that are at least half her length: the feeding-phase rule that sends a
                  dragon head-on into a big enemy.
  first difference  the base and switch-on game of a pair are the same game, event for event, until the switch
                  changes a decision. The first turn that differs is that decision, from an identical position.

Expectation, written before any switch-on game was played (thresholds are the constants below):
  1. only the queen, only while feeding: every pair that differs has its first difference inside our own queen's
     turn, in a round after FEED_FROM. A pair whose queen is dead before that stays the same game to the end.
  2. target seen: queens run by the base bot (ours in the base games, the opponent's in every game) drop at least
     TARGET_MIN times in this run.
  3. never drops: our switch-on queen drops 0 times.
  4. it acted: at least ACTED_MIN pairs differ, so the switch had a queen decision to change.
passed = all four. target_seen = rule 2. mechanism_shown = rules 1, 3 and 4.
Reported, not part of the verdict (16 games per side cannot settle them): what kind of turn the first difference
was (feeder call, hunt call, neither); from that identical position, whether the switch-on queen ended her turn
farther from the leader's head than the base queen did (expected: farther more often than nearer); what became of
both queens after it; over all feeder-call turns, how often she stepped closer to the leader and how often she
ended within 3 tiles of its head; queen-on-queen head-on hits in feeding rounds; queens alive when feeding
starts, final queen lengths, wins, timeouts.
Known before any switch-on game, from this build's 20 switch-off identity games (old 10 maps, base against base):
the turns that end with no action and the bot's own feeding-drop log lines are the same 2,223 turns; 40 ordinary
feeders on the small maps, followed as if they were the queen, all had their drop found at the logged round with
the feeder-call label on; in their last 5 turns before the drop 135 of 177 were feeder calls and only 73 of those
135 stepped closer to the leader's head (feeders walk to a spot ahead of the leader, not to its head), so
"stepped closer" is a weak sign. On the three small maps of that set both queens were dead by round 160 in all 6
games, which is why the mechanism maps are picked for queens that start far apart.
The game runner drops the bot's log lines (--no-debug), so nothing here reads them.
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, os, sys
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# Expectation thresholds (fixed before any switch-on game)
TARGET_MIN = 2       # drops by base-bot queens needed to call the target seen
ACTED_MIN = 2        # pairs that must differ to say the switch acted
FEED_FROM = 200      # FEED_CAP_ROUND: feeding is never on at or before this round

FEED_ROUND = 400     # ENDGAME_ROUND
CAP_UNITS = 56       # FEED_CAP_UNITS
KEEP_UNITS = 3       # FEEDER_KEEP_UNITS
LEN_RATIO = 2        # FEED_LEN_RATIO
APPROACH = 15        # FEEDER_APPROACH
DIE_DIST = 3         # FEEDER_DIE_DIST
VIEW = 3             # the bot sees a 7x7 box around its head
HUNT_PARTS = 6       # END_HUNT_MIN_PARTS
HUNT_RATIO = 2       # END_HUNT_RATIO
SMALL_CELLS = 600    # QUEEN_MIN_CELLS: the base queen can only be a feeder at or below this
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
    W, H = map(int, text.splitlines()[0].split()[1:3])
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
        rival = bodies.get(foe)
        shown = 0
        if rival and gap(rival[0][0], head[0], W) <= VIEW and gap(rival[0][1], head[1], H) <= VIEW:
            shown = sum(gap(c[0], head[0], W) <= VIEW and gap(c[1], head[1], H) <= VIEW for c in rival)
        hunt = bool(feeding and len(body) < lead_len and shown >= HUNT_PARTS and shown * HUNT_RATIO >= len(body))
        return dict(round=rnd, len=len(body), start=list(head), end=list(head), units=len(mine), feeding=feeding,
                    lead_len=lead_len, lead_at=list(lead_at) if lead_at else None, lead_dist=lead_dist,
                    feeder_call=feeder, hunt_call=hunt, foe_queen_len=len(rival) if rival else 0, kind=None,
                    died=None, hit_foe_queen=False)

    turns = []                       # (round, mover, hash of what happened in that turn)
    queen_turns = {}                 # round -> our queen's turn
    drops = []                       # every turn a queen ended with no action
    fate = {q: dict(death_round=None, cause=None, own_move=None, len_at_death=None) for q in (queen, foe)}
    alive_at_feed = {queen: False, foe: False}
    c = Counter()
    rnd, mover, sig, pending = 0, None, None, None

    def close():
        nonlocal sig, pending
        if sig is not None:
            turns.append((rnd, mover, sig.hexdigest()[:16]))
        sig, pending = None, None

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
            if not b or b[0] != h:
                b.appendleft(h)
                if pending and did == queen:
                    pending['end'] = list(h)
            while len(b) > 1 and b[-1] != tp:
                b.pop()
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
            if pending:
                if did == queen:
                    pending['died'] = cause
                elif did == foe:
                    pending['hit_foe_queen'] = True
    close()
    for q in fate:
        fate[q]['final_len'] = len(bodies.get(q) or ())
        fate[q]['alive_at_feed'] = alive_at_feed[q]
    for t in queen_turns.values():
        t['closer'] = bool(t['lead_at'] and dist(t['end'], t['lead_at']) < t['lead_dist'])
        t['end_dist'] = dist(t['end'], t['lead_at']) if t['lead_at'] else None
    return dict(cells=W * H, win=int(winner == ours), queen_id=queen, turns=turns, queen_turns=queen_turns, drops=drops,
                queen=fate[queen], foe_queen=fate[foe], counts=dict(c))


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
    return {k: turn[k] for k in ('kind', 'len', 'start', 'end', 'lead_len', 'lead_dist', 'end_dist', 'feeder_call',
                                 'hunt_call', 'died', 'hit_foe_queen')}


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
                   candidate_queen_drops=[d for d in c['drops'] if d['who'] == 'ours'])
        if i is not None:
            rnd, mover, _ = (b['turns'] if i < len(b['turns']) else c['turns'])[i]
            bt, ct = b['queen_turns'].get(rnd), c['queen_turns'].get(rnd)
            both = i < len(b['turns']) and i < len(c['turns']) and b['turns'][i][:2] == c['turns'][i][:2]
            queen_turn = both and mover == b['queen_id'] and bt is not None and ct is not None
            row.update(first_difference_round=rnd, first_difference_in_queen_turn=bool(queen_turn),
                       first_difference_label=('feeder call' if bt and bt['feeder_call'] else
                                               'hunt call' if bt and bt['hunt_call'] else 'neither') if queen_turn else None,
                       base_turn=brief(bt) if queen_turn else None, candidate_turn=brief(ct) if queen_turn else None,
                       base_queen_after=after(b, rnd), candidate_queen_after=after(c, rnd))
        pairs.append(row)

    differ = [p for p in pairs if p['differs']]
    same = [p for p in pairs if not p['differs']]
    in_rule = [p for p in differ if p['first_difference_in_queen_turn'] and p['first_difference_round'] > FEED_FROM]
    labels = Counter(p['first_difference_label'] for p in in_rule)
    farther = sum(p['candidate_turn']['end_dist'] > p['base_turn']['end_dist'] for p in in_rule
                  if p['base_turn']['end_dist'] is not None)
    nearer = sum(p['candidate_turn']['end_dist'] < p['base_turn']['end_dist'] for p in in_rule
                 if p['base_turn']['end_dist'] is not None)
    level = sum(p['candidate_turn']['end_dist'] == p['base_turn']['end_dist'] for p in in_rule
                if p['base_turn']['end_dist'] is not None)

    def drops(rows, who):
        return [d for g in rows for d in g['drops'] if d['who'] == who and not d['timeout']]

    base_ours = drops(base.values(), 'ours')
    base_theirs = drops(base.values(), 'theirs') + drops(cand.values(), 'theirs')
    cand_ours = drops(cand.values(), 'ours')
    base_bot_drops = len(base_ours) + len(base_theirs)

    def feeder_turns(rows):
        t = [x for g in rows for x in g['queen_turns'].values() if x['feeder_call']]
        return dict(turns=len(t), games=sum(any(x['feeder_call'] for x in g['queen_turns'].values()) for g in rows),
                    stepped_closer=sum(x['closer'] for x in t), stepped_closer_share=share(sum(x['closer'] for x in t), len(t)),
                    ended_within_3=sum(x['end_dist'] <= DIE_DIST for x in t),
                    ended_within_3_share=share(sum(x['end_dist'] <= DIE_DIST for x in t), len(t)))

    def rams(rows):
        t = [x for g in rows for x in g['queen_turns'].values()
             if x['feeding'] and x['kind'] == 'move' and x['died'] == 'headon' and x['hit_foe_queen']]
        return dict(all=len(t), on_a_hunt_call=sum(x['hunt_call'] for x in t))

    def queens(rows):
        rows = list(rows)
        return dict(alive_when_feeding_starts=sum(g['queen']['alive_at_feed'] for g in rows),
                    alive_at_end=sum(g['queen']['death_round'] is None for g in rows),
                    final_length_sum=sum(g['queen']['final_len'] for g in rows),
                    foe_queen_final_length_sum=sum(g['foe_queen']['final_len'] for g in rows),
                    longer_queen_at_end=sum(g['queen']['final_len'] > g['foe_queen']['final_len'] for g in rows),
                    wins=sum(g['win'] for g in rows),
                    deaths_by_cause=dict(Counter(g['queen']['cause'] for g in rows if g['queen']['cause'])),
                    timeouts=sum(g['counts'].get('timeouts_ours', 0) for g in rows),
                    timeout_no_action_turns=sum(d['timeout'] for g in rows for d in g['drops'] if d['who'] == 'ours'))

    checks = {
        'only_queen_only_feeding': len(in_rule) == len(differ),
        'target_seen': base_bot_drops >= TARGET_MIN,
        'never_drops': len(cand_ours) == 0,
        'it_acted': len(differ) >= ACTED_MIN,
    }
    passed = all(checks.values())
    mechanism_shown = checks['only_queen_only_feeding'] and checks['never_drops'] and checks['it_acted']
    failed = [k for k, v in checks.items() if not v]
    dropped_after = sum(p['base_queen_after'].startswith('dropped') for p in differ)
    cand_alive_after = sum(p['candidate_queen_after'].startswith('alive') for p in differ)
    bq, cq = queens(base.values()), queens(cand.values())
    bf, cfeed = feeder_turns(base.values()), feeder_turns(cand.values())
    br, cr = rams(base.values()), rams(cand.values())
    small = sum(base[k]['cells'] <= SMALL_CELLS for k in keys)
    note = (
        f"{'PASS' if passed else 'FAIL'} ({'all four checks' if passed else 'failed: ' + ', '.join(failed)}). "
        f"{games} paired games, {small} on maps of {SMALL_CELLS} tiles or fewer. Drops (queen ends her turn with no "
        f"action and dies to feed the leader): base-bot queens {base_bot_drops} (ours in base games {len(base_ours)}, "
        f"the opponent's {len(base_theirs)}), our switch-on queen {len(cand_ours)}. Pairs that differ: {len(differ)} of "
        f"{games}; first difference inside our queen's own turn after round {FEED_FROM} in {len(in_rule)} of them "
        f"(on a feeder call {labels.get('feeder call', 0)}, on a hunt call {labels.get('hunt call', 0)}, neither "
        f"{labels.get('neither', 0)}). From that identical position the switch-on queen ended farther from the "
        f"leader's head than the base queen in {farther}, nearer in {nearer}, level in {level}. After it, the base "
        f"queen went on to drop in {dropped_after} of {len(differ)} pairs; the switch-on queen was alive at the end "
        f"in {cand_alive_after}. Our queen alive when feeding starts (round {FEED_ROUND + 1}): base "
        f"{bq['alive_when_feeding_starts']}, switch on {cq['alive_when_feeding_starts']} of {games}. Feeder-call "
        f"turns of our queen: base {bf['turns']} in {bf['games']} games (stepped closer to the leader "
        f"{bf['stepped_closer_share']}, ended within {DIE_DIST} tiles of its head {bf['ended_within_3_share']}), "
        f"switch on {cfeed['turns']} in {cfeed['games']} games (closer {cfeed['stepped_closer_share']}, within "
        f"{DIE_DIST} tiles {cfeed['ended_within_3_share']}). Our queen hitting the enemy queen head-on in feeding "
        f"rounds: base {br['all']} ({br['on_a_hunt_call']} on a hunt call), switch on {cr['all']} "
        f"({cr['on_a_hunt_call']}). Raw, not judged: queen length at the end, summed, ours:theirs base "
        f"{bq['final_length_sum']}:{bq['foe_queen_final_length_sum']}, switch on "
        f"{cq['final_length_sum']}:{cq['foe_queen_final_length_sum']}; wins base {bq['wins']}, switch on "
        f"{cq['wins']} of {games}.")
    out = {
        'passed': passed,
        'note': note,
        'target_seen': checks['target_seen'],
        'mechanism_shown': mechanism_shown,
        'checks': checks,
        'thresholds': {'TARGET_MIN': TARGET_MIN, 'ACTED_MIN': ACTED_MIN, 'FEED_FROM': FEED_FROM},
        'games': games,
        'games_on_small_maps': small,
        'queen_drops': {'base_bot_all': base_bot_drops, 'base_ours': len(base_ours), 'base_bot_opponent': len(base_theirs),
                        'candidate_ours': len(cand_ours)},
        'queen_drop_rounds': {'base_ours': sorted(d['round'] for d in base_ours),
                              'base_bot_opponent': sorted(d['round'] for d in base_theirs),
                              'candidate_ours': sorted(d['round'] for d in cand_ours)},
        'pairs_that_differ': len(differ),
        'pairs_same_game_to_the_end': len(same),
        'pairs_same_game_queen_dead_before_feeding': sum(not p['base_queen']['alive_at_feed'] for p in same),
        'pairs_first_difference_in_queen_turn_while_feeding': len(in_rule),
        'first_difference_rounds': sorted(p['first_difference_round'] for p in differ),
        'first_difference_labels': dict(labels),
        'first_difference_candidate_vs_base_distance_to_leader': {'farther': farther, 'nearer': nearer, 'level': level},
        'after_first_difference': {'base_queen_dropped': dropped_after, 'candidate_queen_alive_at_end': cand_alive_after},
        'feeder_call_turns': {'base': bf, 'candidate': cfeed},
        'queen_hits_enemy_queen_in_feeding_rounds': {'base': br, 'candidate': cr},
        'our_queen': {'base': bq, 'candidate': cq},
        'limits': 'The feeder call and hunt call are rebuilt from true lengths and positions; the bot acts on what it '
                  'has seen or heard, so the labels are close, not exact. The leader is taken to be our longest '
                  'other dragon. After the first difference the two games of a pair drift apart for many reasons, so '
                  'what became of the queens later, lengths and wins are raw numbers, not effects of the switch. A '
                  'queen that is dead before feeding starts shows nothing either way. "Stepped closer" is a weak '
                  'sign: ordinary feeders walk to a spot ahead of the leader, not to its head.',
        'pairs': pairs,
    }
    with open(a.output, 'w') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print(note)


if __name__ == '__main__':
    main()
