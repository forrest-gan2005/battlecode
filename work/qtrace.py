import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc
f, ours, q, r0, r1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
info, out, team_of = bc.walk(f)
l0 = info['map'].splitlines()[0].split(); W, H = int(l0[1]), int(l0[2])
def d(a, b): return min(abs(a[0]-b[0]), W-abs(a[0]-b[0])) + min(abs(a[1]-b[1]), H-abs(a[1]-b[1]))
heads = {}; lens = {}
for e in out:
    if e[1] > r1: break
    if e[0] == 'move' and e[4]:
        heads[e[2]] = e[4]; lens[e[2]] = e[6]
        if e[1] >= r0 and (e[2] == q or (q in heads and d(e[4], heads[q]) <= 6)):
            print(e[1], 'Q' if e[2] == q else ('ally' if team_of.get(e[2]) == team_of[q] else 'FOE'), e[2], e[3], '->', e[4], 'len', e[6], 'dQ', d(e[4], heads[q]) if q in heads else '-')
    elif e[0] == 'death':
        if e[1] >= r0 and (e[2] == q or (q in heads and heads.get(e[2]) and d(heads[e[2]], heads[q]) <= 6)): print(e[1], 'DEATH', e[2], team_of.get(e[2]), 'code', e[3], 'len', lens.get(e[2]))
        heads.pop(e[2], None)
    elif e[0] == 'split' and e[1] >= r0 and e[2] == q: print(e)
