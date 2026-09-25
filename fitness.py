#!/usr/bin/env python3
"""从 `unswbc run ... -v` 的输出里还原每队的长度曲线。

需要两个 bot 都用 DEBUG_STATS = true 编译（每回合输出 `LOG STAT <长度>`）。
用法: unswbc run maps/x.map A B --sandbox -v 2>&1 | ./fitness.py
"""

import re
import sys
from collections import defaultdict

HEADER = re.compile(r"^round (\d+): bot (\d+) \(team ([AB])\) stdout:")
STAT = re.compile(r"^LOG STAT (\d+)")
DEATH = re.compile(r"^round (\d+): bot (\d+) \(team ([AB])\) died: (.+)")
RESULT = re.compile(r"^(team [AB] wins|draw) .*")

# (team, round) -> {bot: length}
lengths = defaultdict(dict)
deaths = defaultdict(lambda: defaultdict(int))
result = "?"
current = None

for line in sys.stdin:
    line = line.rstrip("\n")

    header = HEADER.match(line)
    if header:
        current = (header.group(3), int(header.group(1)), int(header.group(2)))
        continue

    stat = STAT.match(line)
    if stat and current:
        team, rnd, bot = current
        lengths[(team, rnd)][bot] = int(stat.group(1))
        continue

    death = DEATH.match(line)
    if death:
        deaths[death.group(3)][death.group(4)] += 1
        continue

    if RESULT.match(line):
        result = line.split(" (")[0]

print(f"结果: {result}")
for team in ("A", "B"):
    rounds = sorted(r for (t, r) in lengths if t == team)
    if not rounds:
        print(f"team {team}: 没有 STAT 数据（DEBUG_STATS 没开？）")
        continue

    final = lengths[(team, rounds[-1])]
    peak_round, peak = max(
        ((r, max(lengths[(team, r)].values())) for r in rounds), key=lambda p: p[1]
    )
    total_deaths = sum(deaths[team].values())
    reasons = ", ".join(f"{k} x{v}" for k, v in sorted(deaths[team].items(), key=lambda p: -p[1]))

    print(
        f"team {team}: 末回合 {rounds[-1]}  存活 {len(final)} 条  "
        f"最长 {max(final.values())}  总长 {sum(final.values())}  "
        f"（全场峰值 {peak} @r{peak_round}）  死亡 {total_deaths}  [{reasons}]"
    )
