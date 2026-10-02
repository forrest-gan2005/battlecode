#!/usr/bin/env python3
"""解析 .replay 文件（gzip + packed Cap'n Proto），输出可统计的事件流。

用法:
    ./replay.py 文件.replay            打印整局摘要
    ./replay.py 文件.replay --json     输出逐回合 JSON
"""
import gzip
import json
import struct
import sys
from collections import defaultdict, deque

EVENT_NAMES = [
    "roundStart", "turnStart", "pearlCountdown", "tileChange", "dragonAction",
    "engineLog", "dragonLog", "dragonIndicator", "debugDraw", "dragonUpdate",
    "dragonSplit", "dragonDeath", "sonarPing",
]
DEATH_REASONS = ["撞墙", "撞自己", "撞别的龙身体", "头撞头", "无有效动作"]
END_REASONS = ["一方被消灭", "回合用尽"]
FACINGS = ["N", "E", "S", "W"]


def unpack_packed(data):
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        tag = data[i]
        i += 1
        if tag == 0:
            out += bytes(8)
            count = data[i]
            i += 1
            out += bytes(8 * count)
            continue
        word = bytearray(8)
        for bit in range(8):
            if tag & (1 << bit):
                word[bit] = data[i]
                i += 1
        out += word
        if tag == 0xFF:
            count = data[i]
            i += 1
            out += data[i:i + 8 * count]
            i += 8 * count
    return bytes(out)


class Message:
    def __init__(self, raw):
        count = struct.unpack_from("<I", raw, 0)[0] + 1
        sizes = struct.unpack_from("<%dI" % count, raw, 4)
        start = 4 + 4 * count
        if start % 8:
            start += 8 - start % 8
        self.segments = []
        for size in sizes:
            self.segments.append(raw[start:start + 8 * size])
            start += 8 * size

    def root(self):
        return follow(self, 0, 0)

    def word(self, seg, index):
        return struct.unpack_from("<Q", self.segments[seg], 8 * index)[0]


class Struct:
    __slots__ = ("msg", "seg", "data", "dwords", "pwords")

    def __init__(self, msg, seg, data, dwords, pwords):
        self.msg, self.seg, self.data = msg, seg, data
        self.dwords, self.pwords = dwords, pwords

    def _bytes(self, offset, size):
        base = 8 * self.data + offset
        if offset + size > 8 * self.dwords:
            return bytes(size)
        return self.msg.segments[self.seg][base:base + size]

    def i32(self, off):
        return struct.unpack("<i", self._bytes(off, 4))[0]

    def u32(self, off):
        return struct.unpack("<I", self._bytes(off, 4))[0]

    def u16(self, off):
        return struct.unpack("<H", self._bytes(off, 2))[0]

    def u64(self, off):
        return struct.unpack("<Q", self._bytes(off, 8))[0]

    def bit(self, index):
        byte = self._bytes(index // 8, 1)
        return bool(byte[0] & (1 << (index % 8)))

    def pointer(self, index):
        if index >= self.pwords:
            return None
        return follow(self.msg, self.seg, self.data + self.dwords + index)

    def text(self, index):
        val = self.pointer(index)
        if val is None:
            return ""
        return bytes(val.raw_bytes()).rstrip(b"\x00").decode("utf8", "replace")


class List:
    __slots__ = ("msg", "seg", "start", "count", "elem", "dwords", "pwords")

    def __init__(self, msg, seg, start, count, elem, dwords=0, pwords=0):
        self.msg, self.seg, self.start = msg, seg, start
        self.count, self.elem = count, elem
        self.dwords, self.pwords = dwords, pwords

    def raw_bytes(self):
        return self.msg.segments[self.seg][self.start:self.start + self.count]

    def __len__(self):
        return self.count

    def __iter__(self):
        step = self.dwords + self.pwords
        for k in range(self.count):
            if self.elem == 7:
                yield Struct(self.msg, self.seg, self.start // 8 + k * step,
                             self.dwords, self.pwords)
            elif self.elem == 3:
                yield struct.unpack_from("<H", self.msg.segments[self.seg],
                                         self.start + 2 * k)[0]
            else:
                raise NotImplementedError("list element size %d" % self.elem)


def follow(msg, seg, word_index):
    ptr = msg.word(seg, word_index)
    if ptr == 0:
        return None
    kind = ptr & 3
    if kind == 2:
        pad_seg = (ptr >> 32) & 0xFFFFFFFF
        pad_off = (ptr >> 3) & 0x1FFFFFFF
        if (ptr >> 2) & 1:
            raise NotImplementedError("double far pointer")
        return follow(msg, pad_seg, pad_off)
    offset = (ptr >> 2) & 0x3FFFFFFF
    if offset >= 0x20000000:
        offset -= 0x40000000
    target = word_index + 1 + offset
    if kind == 0:
        dwords = (ptr >> 32) & 0xFFFF
        pwords = (ptr >> 48) & 0xFFFF
        return Struct(msg, seg, target, dwords, pwords)
    elem = (ptr >> 32) & 7
    count = (ptr >> 35) & 0x1FFFFFFF
    if elem == 7:
        tag = msg.word(seg, target)
        items = (tag >> 2) & 0x3FFFFFFF
        dwords = (tag >> 32) & 0xFFFF
        pwords = (tag >> 48) & 0xFFFF
        return List(msg, seg, 8 * (target + 1), items, 7, dwords, pwords)
    if elem == 2:
        return List(msg, seg, 8 * target, count, 2)
    return List(msg, seg, 8 * target, count, elem)


def point(struct_or_none):
    if struct_or_none is None:
        return None
    return (struct_or_none.i32(0), struct_or_none.i32(4))


def load(path):
    with open(path, "rb") as handle:
        blob = handle.read()
    if blob[:2] == b"\x1f\x8b":
        blob = gzip.decompress(blob)
    return Message(unpack_packed(blob))


def parse(path):
    msg = load(path)
    root = msg.root()
    result = root.pointer(4)
    standings = {}
    for name, index in (("A", 0), ("B", 1)):
        side = result.pointer(index)
        standings[name] = {
            "dragons": side.i32(0),
            "longest": side.i32(4),
            "total": side.i32(8),
        }
    info = {
        "format": root.u32(0),
        "botA": root.text(1),
        "botB": root.text(2),
        "map": root.text(0),
        "terminated": result.bit(0),
        "endReason": END_REASONS[result.u16(2)] if result.u16(2) < 2 else "?",
        "winner": ("A", "B")[result.u16(6)] if result.u16(4) == 1 else None,
        "standings": standings,
    }

    bodies = {}
    team_of = {}
    for line in info["map"].splitlines():
        parts = line.split()
        if parts and parts[0] == "DRAGON":
            team = "A" if int(parts[1]) == 0 else "B"
            cells = [(int(parts[3 + 2 * k]), int(parts[4 + 2 * k]))
                     for k in range(int(parts[2]))]
            did = len(bodies)
            bodies[did] = deque(cells)
            team_of[did] = team

    events = []
    round_no = 0
    for event in root.pointer(3):
        which = event.u16(0)
        payload = event.pointer(0)
        kind = EVENT_NAMES[which] if which < len(EVENT_NAMES) else str(which)
        if kind == "roundStart":
            round_no = payload.i32(0)
        elif kind == "dragonUpdate":
            did = payload.i32(0)
            head = point(payload.pointer(0))
            tail = point(payload.pointer(1))
            body = bodies.setdefault(did, deque())
            if not body or body[0] != head:
                body.appendleft(head)
            while len(body) > 1 and body[-1] != tail:
                body.pop()
            events.append({"round": round_no, "kind": "update", "id": did,
                           "length": len(body)})
        elif kind == "dragonSplit":
            parent = payload.i32(0)
            child = payload.i32(4)
            team = ("A", "B")[payload.u16(8)]
            pbody = deque(point(p) for p in payload.pointer(0))
            cbody = deque(point(p) for p in payload.pointer(1))
            bodies[parent] = pbody
            bodies[child] = cbody
            team_of[parent] = team
            team_of[child] = team
            events.append({"round": round_no, "kind": "split", "id": parent,
                           "child": child, "team": team,
                           "parentLength": len(pbody), "childLength": len(cbody)})
        elif kind == "dragonDeath":
            did = payload.i32(0)
            reason = payload.u16(4)
            events.append({"round": round_no, "kind": "death", "id": did,
                           "team": team_of.get(did, "?"),
                           "length": len(bodies.get(did, ())),
                           "reason": DEATH_REASONS[reason] if reason < 5 else "?"})
            bodies.pop(did, None)
        elif kind == "dragonAction":
            did = payload.i32(0)
            action = payload.pointer(0)
            usage = payload.pointer(1)
            which_action = action.u16(0) if action else 0
            action_names = ("move", "split", "suicide")
            entry = {"round": round_no, "kind": "action", "id": did,
                     "action": action_names[which_action] if which_action < len(action_names) else str(which_action),
                     "tle": payload.bit(32),
                     "points": usage.u64(0) if usage else 0}
            if which_action == 1:
                entry["childSize"] = action.i32(4)
            events.append(entry)
        elif kind == "dragonLog":
            events.append({"round": round_no, "kind": "log",
                           "id": payload.i32(0), "text": payload.text(0)})
    return info, events, team_of


def summarise(path):
    info, events, team_of = parse(path)
    print(f"地图: {[l for l in info['map'].splitlines() if l.startswith('MAP_NAME')]}")
    print(f"A = {info['botA']}   B = {info['botB']}")
    print(f"结束: {info['endReason']}  胜者: {info['winner']}  终止: {info['terminated']}")
    for side in ("A", "B"):
        s = info["standings"][side]
        print(f"  team {side}: 存活 {s['dragons']} 条  最长 {s['longest']}  总长 {s['total']}")

    length_at = defaultdict(dict)
    deaths = defaultdict(list)
    splits = defaultdict(int)
    points_max = defaultdict(int)
    tle = defaultdict(int)
    eaten = defaultdict(int)
    turns = defaultdict(int)
    previous = {}
    for e in events:
        team = team_of.get(e["id"], "?")
        if e["kind"] == "update":
            length_at[e["round"]][e["id"]] = e["length"]
            turns[team] += 1
            was = previous.get(e["id"])
            if was is not None and e["length"] > was:
                eaten[team] += e["length"] - was
            previous[e["id"]] = e["length"]
        elif e["kind"] == "split":
            previous[e["id"]] = e["parentLength"]
            previous[e["child"]] = e["childLength"]
            splits[e["team"]] += 1
        elif e["kind"] == "death":
            deaths[e["team"]].append(e)
        elif e["kind"] == "action":
            points_max[team] = max(points_max[team], e["points"])
            if e["tle"]:
                tle[team] += 1

    print()
    for side in ("A", "B"):
        rows = deaths[side]
        by_reason = defaultdict(int)
        for d in rows:
            by_reason[d["reason"]] += 1
        order = sorted(by_reason.items(), key=lambda kv: -kv[1])
        rate = 100 * eaten[side] / max(1, turns[side])
        print(f"team {side}: 吃珍珠 {eaten[side]} 颗  效率 {rate:.1f} 颗/100龙回合  "
              f"分裂 {splits[side]} 次  死亡 {len(rows)} 条  超时 {tle[side]}")
        print("   死因: " + ", ".join(f"{k} x{v}" for k, v in order))
        big = sorted(rows, key=lambda d: -d["length"])[:8]
        if big:
            print("   死掉的最长的龙: " + ", ".join(
                f"r{d['round']} #{d['id']} {d['length']}节({d['reason']})" for d in big))
    return info, events, team_of, length_at


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
        print(__doc__)
        sys.exit(2)
    target = sys.argv[1]
    if "--json" in sys.argv:
        info, events, team_of = parse(target)
        json.dump({"info": {k: v for k, v in info.items() if k != "map"},
                   "events": events, "teams": team_of},
                  sys.stdout, ensure_ascii=False)
    else:
        summarise(target)
