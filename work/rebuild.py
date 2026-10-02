import json, sys
ev = json.load(open('events.json'))
def build(name):
    v = ev.get(name, [])
    fulls = [i for i, e in enumerate(v) if e[1] == 'full']
    if not fulls: return None, []
    i0 = fulls[-1]
    text = v[i0][2]
    touches = []
    for e in v[i0+1:]:
        if e[1] == 'edit':
            old, new, allr = e[2]
            if old in text: text = text.replace(old, new) if allr else text.replace(old, new, 1)
            else: touches.append(('EDIT-MISS', old[:80]))
        elif e[1] == 'append': text += e[2]
        elif e[1] == 'touch': touches.append(('TOUCH', e[2]))
    return text, touches
if __name__ == '__main__':
    for name in sys.argv[1:]:
        text, touches = build(name)
        if text is None: print('NO FULL', name); continue
        open(name, 'w').write(text)
        print('wrote', name, len(text), 'touches', len(touches))
        for t in touches:
            print('  ---', t[0]); print('  ' + t[1][:1500].replace('\n', '\n  '))
