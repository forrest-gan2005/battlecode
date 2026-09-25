#!/usr/bin/env python3
"""本地对战模拟器（协议 3）。不是真引擎，但把已经从回放里核实过的规则都实现了：

- 按 id 顺序行动；头撞头双方都死；走进自己尾巴刚离开的格子也死
- 冲刺：每一步都判碰撞和吃珠，第 2 步起每步先扣一节尾巴，扣不起就死
- 声呐：直线射出，环绕、穿传送门，射到第一个海草或龙身为止，送给被射中的龙（不分队），回声计数
- 珍珠：TILE 的两个数是刷新间隔范围，吃掉后重新掷；死龙每节变珍珠
- 传送门：同向配对，穿过后沿原方向从另一端出来
- 胜负：一方全灭直接输；否则比最长的龙，再比总长，再平局

用法:
    ./sim.py play maps/devil.map mybot swarm            # 跑一局，打印结果和死因
    ./sim.py play maps/big_empty.map mybot swarm --rounds 200 --seed 3
    ./sim.py series mybot swarm maps/devil.map maps/trophy.map ...   # 每张图先后手各一局
    ./sim.py regress mybot                              # 之前的回归场景

bot 参数是目录（自动 g++ 编译）或可执行文件。
"""
import os
import random
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict

DIRS = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
MAX_ROUNDS = 500
REASON_WALL, REASON_SELF, REASON_BODY, REASON_HEAD, REASON_NOACTION, REASON_SPRINT = (
    "撞墙", "撞自己", "撞别的龙身体", "头撞头", "无有效动作", "冲刺耗尽")


class GameMap:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.kelp = set()          # ('H'|'V', x, y) 规范边：H = (x,y) 的北边, V = (x,y) 的西边
        self.portal = {}           # 规范边 -> id
        self.portal_ends = defaultdict(list)
        self.schedule = {}         # cell -> (min, max)
        self.dragons = []          # (team, [cells])
        self.name = "?"

    @staticmethod
    def load(path):
        lines = open(path, encoding="utf-8").read().splitlines()
        w, h = map(int, lines[0].split()[1:3])
        m = GameMap(w, h)
        stride = w + 1
        for l in lines:
            p = l.split()
            if not p:
                continue
            if p[0] == "MAP_NAME":
                m.name = " ".join(p[1:])
            elif p[0] == "TILE":
                lo, hi = int(p[3]), int(p[4])
                if hi > 0:
                    m.schedule[(int(p[1]), int(p[2]))] = (max(1, lo), max(1, hi))
            elif p[0] == "EDGE":
                row, col = divmod(int(p[1]), stride)
                key = ("H" if row % 2 == 0 else "V", col % w, (row // 2) % h)
                if p[2] == "1":
                    m.kelp.add(key)
                elif p[2] == "2":
                    m.portal[key] = int(p[3])
                    m.portal_ends[int(p[3])].append(key)
            elif p[0] == "DRAGON":
                cells = [(int(p[3 + 2 * k]), int(p[4 + 2 * k])) for k in range(int(p[2]))]
                m.dragons.append(("A" if p[1] == "0" else "B", cells))
        return m

    @staticmethod
    def empty(w, h, name="synthetic"):
        m = GameMap(w, h)
        m.name = name
        return m

    def wrap(self, x, y):
        return (x % self.w, y % self.h)

    def edge(self, cell, d):
        x, y = cell
        if d == "N":
            return ("H", x, y)
        if d == "S":
            return ("H", x, (y + 1) % self.h)
        if d == "W":
            return ("V", x, y)
        return ("V", (x + 1) % self.w, y)

    def add_wall(self, cell, d):
        self.kelp.add(self.edge(cell, d))

    def step(self, cell, d):
        """None if kelp; otherwise the destination cell, following portals in the direction of travel."""
        key = self.edge(cell, d)
        if key in self.kelp:
            return None
        if key in self.portal:
            ends = self.portal_ends[self.portal[key]]
            other = [e for e in ends if e != key]
            if not other:
                return None
            o = other[0]
            if o[0] == "H":
                return (o[1], (o[2] - 1) % self.h) if d == "N" else (o[1], o[2])
            return ((o[1] - 1) % self.w, o[2]) if d == "W" else (o[1], o[2])
        dx, dy = DIRS[d]
        return self.wrap(cell[0] + dx, cell[1] + dy)

    def edge_token(self, cell, d):
        key = self.edge(cell, d)
        if key in self.kelp:
            return "w"
        if key in self.portal:
            return str(self.portal[key])
        return "."


class Dragon:
    __slots__ = ("id", "team", "cells", "entry", "proc", "inbox", "echo", "binary", "born", "last_input")

    def __init__(self, did, team, cells, facing, proc, binary, born):
        self.id, self.team, self.cells = did, team, list(cells)
        # entry[k] = 进入 cells[k] 时的移动方向；头的朝向 = entry[0]，身体 k 的朝向 = entry[k-1]
        self.entry = [facing] * len(cells)
        self.proc, self.binary, self.born = proc, binary, born
        self.inbox, self.echo = [], [0, 0, 0, 0, 0]

    def facing(self, k):
        return self.entry[0] if k == 0 else self.entry[k - 1]


class Sim:
    def __init__(self, gmap, unit_limit=64, seed=0, start_round=0):
        self.m = gmap
        self.unit_limit = unit_limit
        self.rng = random.Random(seed)
        self.round = start_round
        self.pearls = set()
        self.countdown = {c: self.rng.randint(lo, hi) for c, (lo, hi) in gmap.schedule.items()}
        self.dragons = {}
        self.next_id = 0
        self.log = []
        self.deaths = defaultdict(Counter)
        self.rams = Counter()      # (撞方队, 被撞方队, 是否冲刺) -> 次数
        self.ram_segments = Counter()
        self.ram_victims = Counter()    # (被撞方队, 长度段) -> 次数
        self.sprints = Counter()        # (队, "总数"/"存活") -> 多步移动次数
        self.pearls_eaten = Counter()
        self.splits = Counter()
        self.max_len_seen = Counter()
        self.stats = []
        self.verbose = False
        self.winner = None
        self.end_reason = None

    # ---------- geometry helpers
    def occupied(self):
        occ = {}
        for d in self.dragons.values():
            for k, c in enumerate(d.cells):
                occ[c] = (d.id, k)
        return occ

    def team_units(self, team):
        return sum(1 for d in self.dragons.values() if d.team == team)

    # ---------- dragons
    def spawn(self, binary, team, cells, facing=None):
        did = self.next_id
        self.next_id += 1
        if facing is None:
            facing = "N"
            if len(cells) > 1:
                for name in DIRS:
                    if self.m.step(cells[1], name) == cells[0]:
                        facing = name
        proc = subprocess.Popen([binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, bufsize=1)
        proc.stdin.write(f"ID {did}\nTEAM {team}\nMAP {self.m.w} {self.m.h}\nUNIT_LIMIT {self.unit_limit}\n")
        proc.stdin.flush()
        d = Dragon(did, team, cells, facing, proc, binary, self.round)
        # 初始身体的朝向按几何推
        for k in range(1, len(cells)):
            for name in DIRS:
                if self.m.step(cells[k], name) == cells[k - 1]:
                    d.entry[k - 1] = name
        self.dragons[did] = d
        return d

    def close(self, d):
        try:
            d.proc.stdin.write("ENDGAME\n")
            d.proc.stdin.flush()
            d.proc.wait(timeout=5)
        except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
            d.proc.kill()

    def kill(self, d, reason):
        self.dragons.pop(d.id, None)
        for c in d.cells:
            self.pearls.add(c)
        self.deaths[d.team][reason] += 1
        self.log.append(f"r{self.round} #{d.id}({d.team}) 死亡 len={len(d.cells)} {reason}")
        self.close(d)

    # ---------- protocol
    def send_turn(self, d):
        head = d.cells[0]
        occ = self.occupied()
        out = [f"ROUND {self.round}", f"DIR {d.facing(0)}", f"LENGTH {len(d.cells)}",
               f"UNIT_COUNT {self.team_units(d.team)}", f"NUM_MSGS {len(d.inbox)}"]
        out += [str(msg) for msg in d.inbox]
        d.inbox = []
        out.append("ECHOES " + " ".join(str(v) for v in d.echo))
        d.echo = [0, 0, 0, 0, 0]
        tiles = []
        for ly in range(7):
            for lx in range(7):
                p = self.m.wrap(head[0] + lx - 3, head[1] + ly - 3)
                tiles.append(p)
                out.append(f"{p[0]} {p[1]} {1 if p in self.pearls else 0} {self.countdown.get(p, -1) if p not in self.pearls else -1}")
        parts = []
        for p in tiles:
            if p in occ:
                odid, k = occ[p]
                od = self.dragons[odid]
                parts.append(f"{od.team} {odid} {p[0]} {p[1]} {od.facing(k)} {1 if k == 0 else 0}")
        out.append(f"DRAGON_BODIES {len(parts)}")
        out += parts
        for ly in range(8):
            row = []
            for lx in range(7):
                below = self.m.wrap(head[0] + lx - 3, head[1] + ly - 3)
                row.append(self.m.edge_token(below, "N"))
            out.append(" ".join(row))
        for ly in range(7):
            row = []
            for lx in range(8):
                right = self.m.wrap(head[0] + lx - 3, head[1] + ly - 3)
                row.append(self.m.edge_token(right, "W"))
            out.append(" ".join(row))
        d.last_input = out
        try:
            d.proc.stdin.write("\n".join(out) + "\n")
            d.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def read_turn(self, d):
        action, sonar, logs = None, {}, []
        while True:
            try:
                line = d.proc.stdout.readline()
            except (OSError, ValueError):
                line = ""
            if not line:
                err = d.proc.stderr.read() if d.proc.stderr else ""
                logs.append(f"[bot 进程退出: {err.strip()[:200]}]")
                return None, sonar, logs
            tok = line.split()
            if not tok:
                continue
            if tok[0] == "ENDTURN":
                break
            if tok[0] in ("MOVE", "SPLIT"):
                action = tok
            elif tok[0] == "SONAR":
                if len(tok) == 3 and tok[1] in DIRS:
                    sonar[tok[1]] = int(tok[2])
                elif len(tok) == 2:
                    for name in DIRS:
                        sonar[name] = int(tok[1])
            elif tok[0] == "LOG":
                logs.append(" ".join(tok[1:]))
        return action, sonar, logs

    # ---------- actions
    def apply(self, d, action):
        if action is None:
            self.kill(d, REASON_NOACTION)
            return
        if action[0] == "SPLIT":
            k = int(action[1])
            if k < 2 or len(d.cells) - k < 2 or self.team_units(d.team) >= self.unit_limit:
                self.kill(d, REASON_NOACTION)
                return
            child_cells = list(reversed(d.cells[len(d.cells) - k:]))
            child_entry = [OPPOSITE[e] for e in reversed(d.entry[len(d.cells) - k:])]
            d.cells = d.cells[:len(d.cells) - k]
            d.entry = d.entry[:len(d.cells)]
            child = self.spawn(d.binary, d.team, child_cells)
            # 子龙朝向：头的朝向 = 背对父龙
            child.entry = [None] * len(child_cells)
            for kk in range(1, len(child_cells)):
                for name in DIRS:
                    if self.m.step(child_cells[kk], name) == child_cells[kk - 1]:
                        child.entry[kk - 1] = name
            child.entry[-1] = child.entry[-2] if len(child_cells) > 1 else "N"
            for kk in range(len(child_cells)):
                if child.entry[kk] is None:
                    child.entry[kk] = "N"
            self.splits[d.team] += 1
            self.log.append(f"r{self.round} #{d.id}({d.team}) 分裂 {k} -> #{child.id} 头={child_cells[0]} 父龙剩 {len(d.cells)}")
            return
        moves = list(action[1]) if len(action) > 1 else []
        if not moves or any(ch not in DIRS for ch in moves):
            self.kill(d, REASON_NOACTION)
            return
        if len(moves) > 1:
            self.sprints[(d.team, "总数")] += 1
        for j, mv in enumerate(moves):
            if j >= 1:
                if len(d.cells) < 2:
                    self.kill(d, REASON_SPRINT)
                    return
                d.cells.pop()
                d.entry.pop()
            head = d.cells[0]
            new = self.m.step(head, mv)
            if new is None:
                self.kill(d, REASON_WALL)
                return
            occ = self.occupied()
            if new in occ:
                odid, k = occ[new]
                if odid == d.id:
                    self.kill(d, REASON_SELF)
                    return
                other = self.dragons[odid]
                if k == 0:
                    self.rams[(d.team, other.team, len(moves) > 1)] += 1
                    self.ram_segments[(d.team, "付出")] += len(d.cells)
                    self.ram_segments[(d.team, "换掉")] += len(other.cells)
                    bucket = "<=3" if len(other.cells) <= 3 else "4-7" if len(other.cells) <= 7 else "8-15" if len(other.cells) <= 15 else "16+"
                    self.ram_victims[(other.team, bucket)] += 1
                    self.kill(other, REASON_HEAD)
                    self.kill(d, REASON_HEAD)
                else:
                    self.kill(d, REASON_BODY)
                return
            grow = new in self.pearls
            if grow:
                self.pearls.discard(new)
                self.pearls_eaten[d.team] += 1
                lo_hi = self.m.schedule.get(new)
                if lo_hi:
                    self.countdown[new] = self.rng.randint(*lo_hi)
            d.cells.insert(0, new)
            d.entry.insert(0, mv)
            if not grow:
                d.cells.pop()
                d.entry.pop()
        if len(moves) > 1:
            self.sprints[(d.team, "存活")] += 1
        self.max_len_seen[d.team] = max(self.max_len_seen[d.team], len(d.cells))

    def cast_sonars(self, d, sonar):
        if d.id not in self.dragons:
            return
        occ = self.occupied()
        limit = self.m.w + self.m.h
        for name in ("N", "E", "S", "W"):
            if name not in sonar:
                continue
            cell, direction, refracted = d.cells[0], name, False
            for _ in range(limit):
                nxt = self.m.step(cell, direction)
                if nxt is None:
                    d.echo[0] += 1
                    break
                cell = nxt
                if cell in occ:
                    odid, k = occ[cell]
                    if odid == d.id and not refracted:
                        # 全反射：从尾巴沿尾巴背离身体的方向射出
                        tail_k = len(d.cells) - 1
                        cell = d.cells[tail_k]
                        direction = OPPOSITE[d.facing(tail_k)]
                        refracted = True
                        continue
                    other = self.dragons[odid]
                    other.inbox.append(sonar[name])
                    if other.team == d.team:
                        d.echo[2 if k == 0 else 1] += 1
                    else:
                        d.echo[4 if k == 0 else 3] += 1
                    break

    def spawn_pearls(self):
        occ = self.occupied()
        for c in list(self.countdown):
            t = self.countdown[c]
            if t > 0:
                self.countdown[c] = t - 1
            elif c not in self.pearls and c not in occ:
                self.pearls.add(c)
                self.countdown[c] = -1
            # t == 0 但格子被占：下回合再试

    # ---------- game loop
    def snapshot(self):
        row = {}
        for t in "AB":
            ls = [len(d.cells) for d in self.dragons.values() if d.team == t]
            row[t] = (len(ls), max(ls) if ls else 0, sum(ls))
        return row

    def run(self, rounds=MAX_ROUNDS, on_turn=None):
        for _ in range(rounds):
            self.spawn_pearls()
            if self.round % 50 == 0:
                self.stats.append((self.round, self.snapshot()))
            for did in sorted(self.dragons):
                d = self.dragons.get(did)
                if d is None:
                    continue
                self.send_turn(d)
                action, sonar, logs = self.read_turn(d)
                if on_turn:
                    on_turn(self, d, action, sonar, logs)
                if self.verbose:
                    print(f"r{self.round} #{d.id}({d.team}) len={len(d.cells)} head={d.cells[0]} -> {action} {logs}")
                self.apply(d, action)
                self.cast_sonars(d, sonar)
            self.round += 1
            alive = {t: self.team_units(t) for t in "AB"}
            if alive["A"] == 0 or alive["B"] == 0:
                self.end_reason = "一方全灭"
                self.winner = "A" if alive["A"] else ("B" if alive["B"] else None)
                break
        if self.end_reason is None:
            self.end_reason = "回合用尽"
            snap = self.snapshot()
            if snap["A"][1] != snap["B"][1]:
                self.winner = "A" if snap["A"][1] > snap["B"][1] else "B"
            elif snap["A"][2] != snap["B"][2]:
                self.winner = "A" if snap["A"][2] > snap["B"][2] else "B"
        self.final = self.snapshot()
        self.stats.append((self.round, self.final))
        for d in list(self.dragons.values()):
            self.close(d)
        return self.winner

    def report(self, names):
        f = self.final
        print(f"{self.m.name}: {self.end_reason}，胜者 {self.winner or '平局'}   "
              f"A={names['A']} B={names['B']}")
        for t in "AB":
            print(f"  {t} ({names[t]}): 存活 {f[t][0]} 最长 {f[t][1]} 总长 {f[t][2]}  吃珠 {self.pearls_eaten[t]} 分裂 {self.splits[t]}  "
                  f"死亡 {sum(self.deaths[t].values())} [{', '.join(f'{k} x{v}' for k, v in self.deaths[t].most_common())}]")
        ram_lines = []
        for (a, b, sprint), n in sorted(self.rams.items()):
            ram_lines.append(f"{a} 撞 {b} {n} 次{'(冲刺)' if sprint else '(单步)'}")
        if ram_lines:
            print("  头撞头: " + "; ".join(ram_lines) +
                  f"; A 付出 {self.ram_segments[('A', '付出')]} 换掉 {self.ram_segments[('A', '换掉')]}"
                  f"; B 付出 {self.ram_segments[('B', '付出')]} 换掉 {self.ram_segments[('B', '换掉')]}")
        for t in "AB":
            v = {b: self.ram_victims[(t, b)] for b in ("<=3", "4-7", "8-15", "16+")}
            if any(v.values()):
                print(f"  {t} 被撞死的龙按长度: {v}")
            if self.sprints[(t, "总数")]:
                print(f"  {t} 多步移动 {self.sprints[(t, '总数')]} 次，其中走完还活着（脱身）{self.sprints[(t, '存活')]} 次")
        print("  每 50 回合 (存活/最长/总长): " + "  ".join(
            f"r{r}:{s['A'][0]}/{s['A'][1]}/{s['A'][2]}|{s['B'][0]}/{s['B'][1]}/{s['B'][2]}" for r, s in self.stats))


def build(target):
    if os.path.isdir(target):
        out = os.path.join(tempfile.mkdtemp(prefix="simbot_"), "bot")
        subprocess.check_call(["g++", "-std=c++20", "-O2", "-o", out, os.path.join(target, "main.cpp")])
        return out
    return os.path.abspath(target)


def play(map_path, bot_a, bot_b, rounds=MAX_ROUNDS, seed=0, verbose=False, unit_limit=64, quiet=False):
    gmap = GameMap.load(map_path)
    sim = Sim(gmap, unit_limit=unit_limit, seed=seed)
    sim.verbose = verbose
    binaries = {"A": bot_a, "B": bot_b}
    for team, cells in gmap.dragons:
        sim.spawn(binaries[team], team, cells)
    sim.run(rounds)
    if not quiet:
        sim.report({"A": os.path.basename(bot_a.rstrip("/")), "B": os.path.basename(bot_b.rstrip("/"))})
    return sim


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    opts = {"rounds": MAX_ROUNDS, "seed": 0, "verbose": False, "limit": 64}
    args = []
    i = 2
    while i < len(argv):
        if argv[i] == "--rounds":
            opts["rounds"] = int(argv[i + 1]); i += 2
        elif argv[i] == "--seed":
            opts["seed"] = int(argv[i + 1]); i += 2
        elif argv[i] == "--limit":
            opts["limit"] = int(argv[i + 1]); i += 2
        elif argv[i] == "-v":
            opts["verbose"] = True; i += 1
        else:
            args.append(argv[i]); i += 1
    if cmd == "play":
        map_path, a, b = args[0], build(args[1]), build(args[2])
        play(map_path, a, b, opts["rounds"], opts["seed"], opts["verbose"], opts["limit"])
    elif cmd == "series":
        left, right, maps = build(args[0]), build(args[1]), args[2:]
        ln, rn = os.path.basename(args[0].rstrip("/")), os.path.basename(args[1].rstrip("/"))
        score = Counter()
        for mp in maps:
            for a, b, la, lb in ((left, right, ln, rn), (right, left, rn, ln)):
                sim = play(mp, a, b, opts["rounds"], opts["seed"], False, opts["limit"], quiet=True)
                f = sim.final
                w = {"A": la, "B": lb}.get(sim.winner, "平局")
                score[w] += 1
                print(f"{os.path.basename(mp):22s} A={la:8s} B={lb:8s} -> {w:8s} {sim.end_reason} r{sim.round}  "
                      f"A {f['A'][0]}/{f['A'][1]}/{f['A'][2]}  B {f['B'][0]}/{f['B'][1]}/{f['B'][2]}  "
                      f"撞头 A→B {sum(n for (x, y, _), n in sim.rams.items() if x == 'A' and y == 'B')} "
                      f"B→A {sum(n for (x, y, _), n in sim.rams.items() if x == 'B' and y == 'A')}")
        print("----")
        print(f"{ln}: {score[ln]} 胜   {rn}: {score[rn]} 胜   平: {score['平局']}")
    elif cmd == "regress":
        import regress
        regress.run_all(build(args[0]))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
