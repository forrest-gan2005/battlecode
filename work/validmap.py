import os, sys
def valid(path):
    L = open(path).read().splitlines()
    W, H = map(int, L[0].split()[1:3])
    kind = {}
    for l in L:
        p = l.split()
        if p and p[0] == 'EDGE':
            kind[int(p[1])] = int(p[2])
    def north(x, y): return y * 2 * (W + 1) + x
    def west(x, y): return y * 2 * (W + 1) + (W + 1) + x
    def edge(a, b):
        (x, y), (u, v) = a, b
        if x == u:
            if (v - y) % H == 1: return kind.get(north(x, v), 0)
            if (y - v) % H == 1: return kind.get(north(x, y), 0)
        if y == v:
            if (u - x) % W == 1: return kind.get(west(u, y), 0)
            if (x - u) % W == 1: return kind.get(west(x, y), 0)
        return -1
    for l in L:
        p = l.split()
        if p and p[0] == 'DRAGON':
            cells = [(int(p[3 + 2 * k]), int(p[4 + 2 * k])) for k in range(int(p[2]))]
            for a, b in zip(cells, cells[1:]):
                if edge(a, b) != 0:
                    return False
    return True
if __name__ == '__main__':
    for d in sys.argv[1:]:
        bad = [f for f in sorted(os.listdir(d)) if f.endswith('.map') and not valid(os.path.join(d, f))]
        print(d, 'bad', len(bad), bad)
