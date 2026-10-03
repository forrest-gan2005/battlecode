#!/usr/bin/env python3
"""Mid-game split mechanism check from kept replays (work/ab2/<TAG>_<map>_<seed>_<side>.replay).

usage: python3 splitcheck.py BASE_TAG CAND_TAG [--maps a,b,...] [--dir DIR] [--lo 150] [--hi 300]
Per game, for our side: splits in rounds lo-hi (all; growth splits with a child of 2; growth splits by
parents longer than 4), units at r150/r200/r300, total and longest length at r300 and at the end,
deaths in rounds lo-hi by kind (self = wall or own body, body = another dragon's body, head = head-on),
feeding suicides, the queen's length at r300 and at the end (0 once dead), the opponent's units at
r200/r300, and the win. Paired by (map, seed, side).
"""
import argparse, glob, os, sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

SNAPS = (150, 200, 300)
FIELDS = ["spl", "gspl", "lspl", "u150", "u200", "u300", "tot300", "top300", "totend", "topend", "self", "body", "head", "suic",
          "q300", "qend", "ou200", "ou300", "win"]


def metrics(job):
    path, ours, lo, hi = job
    info, events, team_of = replay.parse(path)
    length = {}
    for line in info["map"].splitlines():
        p = line.split()
        if p and p[0] == "DRAGON":
            length[len(length)] = int(p[2])
    queen = min(i for i in length if team_of.get(i) == ours)
    out = dict.fromkeys(FIELDS, 0)
    snaps = {}

    def snap(r):
        mine = [l for i, l in length.items() if team_of.get(i) == ours]
        theirs = [l for i, l in length.items() if team_of.get(i) != ours]
        snaps[r] = (len(mine), sum(mine), len(theirs), length.get(queen, 0), max(mine, default=0))

    for e in events:
        for r in SNAPS:
            if r not in snaps and e["round"] >= r:
                snap(r)
        mine = team_of.get(e["id"]) == ours
        in_win = lo <= e["round"] <= hi
        if e["kind"] == "update":
            length[e["id"]] = e["length"]
        elif e["kind"] == "split":
            length[e["id"]] = e["parentLength"]
            length[e["child"]] = e["childLength"]
            if mine and in_win:
                out["spl"] += 1
                out["gspl"] += e["childLength"] == 2
                out["lspl"] += e["childLength"] == 2 and e["parentLength"] + 2 > 4
        elif e["kind"] == "death":
            length.pop(e["id"], None)
            if mine and in_win:
                reason = e["reason"]
                if reason in ("撞墙", "撞自己"):
                    out["self"] += 1
                elif reason == "撞别的龙身体":
                    out["body"] += 1
                elif reason == "头撞头":
                    out["head"] += 1
        elif e["kind"] == "action" and e["action"] == "suicide" and mine:
            out["suic"] += 1
    for r in SNAPS:
        if r not in snaps:
            snap(r)
    out["u150"], out["u200"], out["u300"] = snaps[150][0], snaps[200][0], snaps[300][0]
    out["tot300"], out["top300"] = snaps[300][1], snaps[300][4]
    mine = [l for i, l in length.items() if team_of.get(i) == ours]
    out["totend"], out["topend"] = sum(mine), max(mine, default=0)
    out["ou200"], out["ou300"] = snaps[200][2], snaps[300][2]
    out["q300"] = snaps[300][3]
    out["qend"] = length.get(queen, 0)
    out["win"] = int(info["winner"] == ours)
    return out


def collect(tag, maps, folder, lo, hi):
    jobs, keys = [], []
    for p in glob.glob(os.path.join(folder, f"{tag}_*.replay")):
        stem = os.path.basename(p)[len(tag) + 1:-len(".replay")]
        m, seed, side = stem.rsplit("_", 2)
        if maps and m not in maps:
            continue
        keys.append((m, seed, side))
        jobs.append((p, "A" if side == "0" else "B", lo, hi))
    with ProcessPoolExecutor(int(os.environ.get("WORKERS", "4"))) as ex:
        return dict(zip(keys, ex.map(metrics, jobs)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("cand")
    ap.add_argument("--maps")
    ap.add_argument("--dir", default=os.path.join(HERE, "ab2"))
    ap.add_argument("--lo", type=int, default=150)
    ap.add_argument("--hi", type=int, default=300)
    ap.add_argument("--per-map", action="store_true")
    a = ap.parse_args()
    maps = set(a.maps.split(",")) if a.maps else None
    base = collect(a.base, maps, a.dir, a.lo, a.hi)
    cand = base if a.cand == a.base else collect(a.cand, maps, a.dir, a.lo, a.hi)
    keys = sorted(set(base) & set(cand))
    if not keys:
        sys.exit("no paired replays found")
    if a.per_map:
        rows = defaultdict(list)
        for k in keys:
            rows[k[0]].append(k)
        print(f"{'map':34s} {'n':>3s} " + " ".join(f"{f:>13s}" for f in FIELDS))
        for m, ks in sorted(rows.items()):
            cells = [f"{sum(base[k][f] for k in ks) / len(ks):5.1f}>{sum(cand[k][f] for k in ks) / len(ks):5.1f}" for f in FIELDS]
            print(f"{m[:34]:34s} {len(ks):3d} " + " ".join(f"{c:>13s}" for c in cells))
    print(f"{len(keys)} paired games, per-game means, {a.base} -> {a.cand} (rounds {a.lo}-{a.hi} for splits and deaths)")
    for f in FIELDS:
        b = sum(base[k][f] for k in keys) / len(keys)
        c = sum(cand[k][f] for k in keys) / len(keys)
        print(f"  {f:7s} {b:8.2f} -> {c:8.2f}  ({c - b:+.2f})")


if __name__ == "__main__":
    main()
