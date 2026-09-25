#!/usr/bin/env python3
"""极简协议驱动器：用来复现 bot 的特定决策，不是真引擎。

只实现了环面地图、海草边、珍珠、分裂、按 id 顺序行动、声呐下一回合全队可见；
没有传送门、没有引擎积分。用法:

    ./sim.py mybot stale_len          # 分裂后声呐还在广播旧长度？
    ./sim.py mybot deadend_short      # 8 节龙进死胡同会不会逃生分裂
    ./sim.py mybot deadend_long       # 28 节龙同上
    ./sim.py mybot child_boxed        # 常规分裂把子龙放进死角
    ./sim.py mybot feeder             # 喂食角色是否每 5 回合被剥夺
    ./sim.py mybot perf               # 64x64 单龙每回合耗时
    ./sim.py mybot all

第一个参数是 bot 目录（自动用 g++ 编译）或可执行文件。
"""
import os
import random
import resource
import subprocess
import sys
import tempfile

DIRS = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}


class Sim:
    def __init__(self, w, h, unit_limit=10, start_round=1):
        self.w, self.h = w, h
        self.unit_limit = unit_limit
        self.round = start_round
        self.kelp = set()        # frozenset({cellA, cellB})
        self.pearls = set()
        self.dragons = {}        # id -> dict(team, cells[head first], facing, proc)
        self.next_id = 0
        self.inbox = {}          # team -> 上一回合发出的声呐
        self.log = []

    def wrap(self, x, y):
        return (x % self.w, y % self.h)

    def step(self, cell, d):
        dx, dy = DIRS[d]
        return self.wrap(cell[0] + dx, cell[1] + dy)

    def add_wall(self, cell, d):
        self.kelp.add(frozenset({cell, self.step(cell, d)}))

    def is_kelp(self, a, b):
        return frozenset({a, b}) in self.kelp

    def corridor(self, y, x0, x1, close_west=True, close_east=True):
        for x in range(x0, x1 + 1):
            self.add_wall((x, y), "N")
            self.add_wall((x, y), "S")
        if close_west:
            self.add_wall((x0, y), "W")
        if close_east:
            self.add_wall((x1, y), "E")

    def spawn(self, binary, team, cells, facing):
        did = self.next_id
        self.next_id += 1
        proc = subprocess.Popen([binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, bufsize=1)
        proc.stdin.write(f"ID {did}\nTEAM {team}\nMAP {self.w} {self.h}\nUNIT_LIMIT {self.unit_limit}\n")
        proc.stdin.flush()
        self.dragons[did] = {"team": team, "cells": list(cells), "facing": facing, "proc": proc}
        return did

    def occupied(self):
        occ = {}
        for did, d in self.dragons.items():
            for k, c in enumerate(d["cells"]):
                occ[c] = (did, k)
        return occ

    def facing_of(self, d, k):
        if k == 0:
            return d["facing"]
        here, ahead = d["cells"][k], d["cells"][k - 1]
        for name in DIRS:
            if self.step(here, name) == ahead:
                return name
        return d["facing"]

    def send_turn(self, did):
        d = self.dragons[did]
        head = d["cells"][0]
        occ = self.occupied()
        team_units = sum(1 for x in self.dragons.values() if x["team"] == d["team"])
        msgs = self.inbox.get(d["team"], [])
        out = [f"ROUND {self.round}", f"DIR {d['facing']}", f"LENGTH {len(d['cells'])}",
               f"UNIT_COUNT {team_units}", f"NUM_MSGS {len(msgs)}"]
        out += [str(m) for m in msgs]
        tiles = []
        for ly in range(7):
            for lx in range(7):
                p = self.wrap(head[0] + lx - 3, head[1] + ly - 3)
                tiles.append(p)
                out.append(f"{p[0]} {p[1]} {1 if p in self.pearls else 0} -1")
        parts = []
        for p in tiles:
            if p in occ:
                odid, k = occ[p]
                od = self.dragons[odid]
                parts.append(f"{od['team']} {odid} {p[0]} {p[1]} {self.facing_of(od, k)} {1 if k == 0 else 0}")
        out.append(f"DRAGON_BODIES {len(parts)}")
        out += parts
        for ly in range(8):
            row = []
            for lx in range(7):
                below = self.wrap(head[0] + lx - 3, head[1] + ly - 3)
                row.append("w" if self.is_kelp(self.step(below, "N"), below) else ".")
            out.append(" ".join(row))
        for ly in range(7):
            row = []
            for lx in range(8):
                right = self.wrap(head[0] + lx - 3, head[1] + ly - 3)
                row.append("w" if self.is_kelp(self.step(right, "W"), right) else ".")
            out.append(" ".join(row))
        d["proc"].stdin.write("\n".join(out) + "\n")
        d["proc"].stdin.flush()

    def read_turn(self, did):
        d = self.dragons[did]
        action, sonar, logs = None, [], []
        while True:
            line = d["proc"].stdout.readline()
            if not line:
                raise RuntimeError(f"bot {did} 关闭了 stdout; stderr={d['proc'].stderr.read()!r}")
            tok = line.split()
            if not tok:
                continue
            if tok[0] == "ENDTURN":
                break
            if tok[0] in ("MOVE", "SPLIT"):
                action = tok
            elif tok[0] == "SONAR":
                sonar.append(int(tok[-1]))
            elif tok[0] == "LOG":
                logs.append(" ".join(tok[1:]))
        return action, sonar, logs

    def close(self, did):
        d = self.dragons.pop(did)
        d["proc"].stdin.write("ENDGAME\n")
        d["proc"].stdin.flush()
        d["proc"].wait(timeout=5)
        return d

    def kill(self, did, reason):
        d = self.close(did)
        for c in d["cells"]:
            self.pearls.add(c)
        self.log.append(f"r{self.round} #{did} 死亡 len={len(d['cells'])} 原因={reason}")

    def apply(self, binary, did, action):
        d = self.dragons[did]
        if action is None:
            self.kill(did, "无动作")
            return
        if action[0] == "SPLIT":
            k = int(action[1])
            cells = d["cells"]
            if k < 2 or len(cells) - k < 2:
                self.kill(did, "非法分裂")
                return
            child = list(reversed(cells[len(cells) - k:]))
            d["cells"] = cells[:len(cells) - k]
            facing = "N"
            for name in DIRS:
                if self.step(child[0], name) == child[1]:
                    facing = OPPOSITE[name]
            cid = self.spawn(binary, d["team"], child, facing)
            self.log.append(f"r{self.round} #{did} 分裂 {k} -> 子龙 #{cid} 头={child[0]} 父龙剩 {len(d['cells'])}")
            return
        mv = action[1]
        if len(mv) != 1:
            self.kill(did, "不支持冲刺")
            return
        head = d["cells"][0]
        new = self.step(head, mv)
        if self.is_kelp(head, new):
            self.kill(did, f"在 {head} 向 {mv} 撞海草")
            return
        occ = self.occupied()
        if new in occ:
            odid, k = occ[new]
            self.kill(did, f"向 {mv} 撞到 #{odid} 第 {k} 节 {new}")
            return
        grow = new in self.pearls
        self.pearls.discard(new)
        d["cells"].insert(0, new)
        if not grow:
            d["cells"].pop()
        d["facing"] = mv

    def run(self, binary, rounds, verbose=False, on_turn=None):
        for _ in range(rounds):
            sent = {}
            for did in sorted(self.dragons):
                if did not in self.dragons:
                    continue
                self.send_turn(did)
                action, sonar, logs = self.read_turn(did)
                d = self.dragons[did]
                sent.setdefault(d["team"], []).extend(sonar)
                if on_turn:
                    on_turn(self, did, action, sonar, logs)
                if verbose:
                    print(f"r{self.round} #{did} len={len(d['cells'])} head={d['cells'][0]} -> {action} {logs}")
                self.apply(binary, did, action)
            self.inbox = sent
            self.round += 1
            if not self.dragons:
                break
        self.final = {d: len(v["cells"]) for d, v in self.dragons.items()}
        for did in list(self.dragons):
            self.close(did)

    def survivors(self):
        return getattr(self, "final", {d: len(v["cells"]) for d, v in self.dragons.items()})


def decode_leader(msg):
    body = msg & ((1 << 55) - 1)
    return {"id": body & 0xFFFF, "len": (body >> 16) & 0xFFF, "when": (body >> 28) & 0x1FF}


def build(target):
    if os.path.isdir(target):
        out = os.path.join(tempfile.mkdtemp(prefix="simbot_"), "bot")
        subprocess.check_call(["g++", "-std=c++20", "-O2", "-o", out, os.path.join(target, "main.cpp")])
        return out
    return os.path.abspath(target)


def scenario_stale_len(binary):
    print("场景 stale_len：4 节龙在第 10 回合分裂成 2 节，之后广播的领队长度应该变成 2。")
    sim = Sim(20, 20, start_round=10)
    sim.spawn(binary, "A", [(10, 10), (9, 10), (8, 10), (7, 10)], "E")

    def hook(s, did, action, sonar, logs):
        if sonar:
            dec = decode_leader(sonar[0])
            print(f"  r{s.round} #{did} 实际长度={len(s.dragons[did]['cells'])} 广播: 领队#{dec['id']} "
                  f"长度={dec['len']} when={dec['when']}  动作={action}")
    sim.run(binary, 4, on_turn=hook)
    print("  " + "\n  ".join(sim.log))


def scenario_deadend(binary, pearls):
    print(f"场景 deadend：封闭走廊 x=2..40，龙一路吃 {pearls} 颗珍珠长到 {3 + pearls} 节后撞上东端死胡同。")
    sim = Sim(50, 20, start_round=350)
    sim.corridor(10, 2, 40)
    for x in range(13, 13 + pearls):
        sim.pearls.add((x, 10))
    sim.spawn(binary, "A", [(12, 10), (11, 10), (10, 10)], "E")
    sim.run(binary, 40)
    print("  " + "\n  ".join(sim.log))
    print(f"  幸存: {sim.survivors()}")


def scenario_child_boxed(binary):
    print("场景 child_boxed：4 节龙的尾巴顶在走廊死角，常规分裂后子龙头在死角。")
    sim = Sim(20, 20, start_round=10)
    sim.corridor(10, 5, 8, close_east=False)
    sim.spawn(binary, "A", [(8, 10), (7, 10), (6, 10), (5, 10)], "E")
    sim.run(binary, 6, verbose=True)
    print("  " + "\n  ".join(sim.log))
    print(f"  幸存: {sim.survivors()}")


def scenario_feeder(binary):
    print("场景 feeder：第 410 回合，20 节领队向东走，三条 2 节小龙在南边 9 格。F=本回合有投放目标。")
    print("  （需要 bot 每回合 LOG FEED <feed_index>，默认编译没有，这里只能从死亡日志判断是否送成）")
    sim = Sim(40, 40, unit_limit=10, start_round=410)
    sim.spawn(binary, "A", [(20 - k, 10) for k in range(20)], "E")
    for x in (22, 26, 30):
        sim.spawn(binary, "A", [(x, 20), (x, 21)], "N")
    for x in range(21, 40):
        sim.pearls.add((x, 10))
    rows = {}

    def hook(s, did, action, sonar, logs):
        for l in logs:
            t = l.split()
            if t and t[0] == "FEED":
                rows.setdefault(did, []).append("F" if int(t[1]) >= 0 else "-")
            if t and t[0] == "FEEDDIE":
                rows.setdefault(did, []).append("DIE")
    sim.run(binary, 30, on_turn=hook)
    for did, marks in sorted(rows.items()):
        if did != 0:
            print(f"  #{did}: " + " ".join(marks))
    print("  " + "\n  ".join(sim.log))
    print(f"  幸存: {sim.survivors()}")


def scenario_perf(binary):
    print("场景 perf：64x64 单龙 140 回合，bot 进程 CPU 时间。")
    sim = Sim(64, 64, start_round=350)
    rng = random.Random(1)
    for _ in range(700):
        sim.pearls.add((rng.randrange(64), rng.randrange(64)))
    sim.spawn(binary, "A", [(32, 32), (31, 32), (30, 32)], "E")
    turns = [0]

    def hook(*_):
        turns[0] += 1
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    sim.run(binary, 140, on_turn=hook)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    print(f"  {turns[0]} 个龙回合, CPU {cpu * 1000:.0f} ms -> {cpu * 1000 / max(1, turns[0]):.2f} ms/回合; "
          f"最终长度 {sim.survivors()}; 死亡 {sim.log}")


SCENARIOS = {
    "stale_len": scenario_stale_len,
    "deadend_short": lambda b: scenario_deadend(b, 5),
    "deadend_long": lambda b: scenario_deadend(b, 25),
    "child_boxed": scenario_child_boxed,
    "feeder": scenario_feeder,
    "perf": scenario_perf,
}

if __name__ == "__main__":
    if len(sys.argv) != 3 or (sys.argv[2] != "all" and sys.argv[2] not in SCENARIOS):
        print(__doc__)
        sys.exit(2)
    bot = build(sys.argv[1])
    names = list(SCENARIOS) if sys.argv[2] == "all" else [sys.argv[2]]
    for name in names:
        SCENARIOS[name](bot)
        print()
