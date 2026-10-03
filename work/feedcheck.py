#!/usr/bin/env python3
"""Feeding mechanism check from kept replays (work/ab2/<TAG>_<map>_<seed>_<side>.replay).

usage: python3 feedcheck.py BASE_TAG CAND_TAG [--maps a,b,...]
Per game, for our side: suicides from round 300 on (feeding), the longest dragon at rounds 450 and at the end,
and our total length at the end. Prints per-map and overall means for both tags, paired by (map, seed, side).
"""
import argparse, glob, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay


def metrics(path, ours):
    info, events, team_of = replay.parse(path)
    length, feeds, longest450 = {}, 0, None
    for e in events:
        if longest450 is None and e["round"] >= 450:
            longest450 = max((l for i, l in length.items() if team_of.get(i) == ours), default=0)
        if e["kind"] == "update":
            length[e["id"]] = e["length"]
        elif e["kind"] == "death":
            length.pop(e["id"], None)
        elif e["kind"] == "action" and e["action"] == "suicide" and e["round"] >= 300 and team_of.get(e["id"]) == ours:
            feeds += 1
    mine = [l for i, l in length.items() if team_of.get(i) == ours]
    end_longest = max(mine, default=0)
    return {"feeds": feeds, "lead450": longest450 if longest450 is not None else end_longest,
            "lead_end": end_longest, "total_end": sum(mine), "win": int(info["winner"] == ours)}


def collect(tag, maps):
    out = {}
    for p in glob.glob(os.path.join(HERE, "ab2", f"{tag}_*.replay")):
        stem = os.path.basename(p)[len(tag) + 1:-len(".replay")]
        m, seed, side = stem.rsplit("_", 2)
        if maps and m not in maps:
            continue
        out[(m, seed, side)] = metrics(p, "A" if side == "0" else "B")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("cand")
    ap.add_argument("--maps")
    a = ap.parse_args()
    maps = set(a.maps.split(",")) if a.maps else None
    base, cand = collect(a.base, maps), collect(a.cand, maps)
    keys = sorted(set(base) & set(cand))
    if not keys:
        sys.exit("no paired replays found")
    fields = ["feeds", "lead450", "lead_end", "total_end", "win"]
    per_map = defaultdict(list)
    for k in keys:
        per_map[k[0]].append(k)
    print(f"{'map':34s} n  " + "  ".join(f"{f:>15s}" for f in fields))
    for m, ks in sorted(per_map.items()):
        cells = []
        for f in fields:
            b = sum(base[k][f] for k in ks) / len(ks)
            c = sum(cand[k][f] for k in ks) / len(ks)
            cells.append(f"{b:6.1f} → {c:6.1f}")
        print(f"{m[:34]:34s} {len(ks):2d}  " + "  ".join(f"{x:>15s}" for x in cells))
    print(f"{'ALL':34s} {len(keys):2d}  " + "  ".join(
        f"{sum(base[k][f] for k in keys) / len(keys):6.1f} → {sum(cand[k][f] for k in keys) / len(keys):6.1f}".rjust(15) for f in fields))


if __name__ == "__main__":
    main()
