import os, re, wipe
def ours_of(p):
    m = re.search(r'_(\d+)_([01])\.replay$', os.path.basename(p))
    if m and '/ab2' in os.path.abspath(p): return 'A' if m.group(2) == '0' else 'B'
    return wipe.ours_of(p)
