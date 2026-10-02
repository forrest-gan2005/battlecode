import json, re, os, sys
from collections import defaultdict
T = ['/Users/forrest/.claude/projects/-Users-UNSW-battlecode/ccc05066-2729-4a51-8833-2b8980c24570.jsonl',
     '/Users/forrest/.claude/projects/-Users-UNSW-battlecode/a1528ab5-8f7c-49d8-a2a1-c4b5363e1290.jsonl',
     '/Users/forrest/.claude/projects/-Users-UNSW-battlecode/482a6d87-d9d5-4d91-9363-d653f774ade7.jsonl']
SCR = re.compile(r'/private/tmp/claude-501/[^/]+/[0-9a-f-]+/scratchpad/')
HEREDOC = re.compile(r"cat\s*(>>?)\s*([\w./-]+)\s*<<\s*'?(\w+)'?\n(.*?)\n\3(?:\n|$)", re.S)
events = defaultdict(list)
pending = {}
seq = 0
def key(path):
    return os.path.basename(path)
def strip_read(text):
    lines = text.split('\n')
    out = []
    for l in lines:
        m = re.match(r'^\s*\d+\t(.*)$', l)
        if m: out.append(m.group(1))
        elif l.strip() == '': continue
        else: return None
    return '\n'.join(out) + '\n'
for t in T:
    for line in open(t):
        try: d = json.loads(line)
        except Exception: continue
        msg = d.get('message') or {}
        content = msg.get('content')
        if not isinstance(content, list): continue
        for c in content:
            if not isinstance(c, dict): continue
            if c.get('type') == 'tool_use':
                seq += 1
                name = c.get('name'); inp = c.get('input') or {}
                if name == 'Write' and 'scratchpad' in inp.get('file_path', ''):
                    events[key(inp['file_path'])].append((seq, 'full', inp.get('content', ''), t))
                elif name == 'Edit' and 'scratchpad' in inp.get('file_path', ''):
                    events[key(inp['file_path'])].append((seq, 'edit', (inp.get('old_string'), inp.get('new_string'), inp.get('replace_all')), t))
                elif name == 'Read' and 'scratchpad' in inp.get('file_path', '') and not inp.get('offset') and not inp.get('limit'):
                    pending[c.get('id')] = (seq, key(inp['file_path']), t)
                elif name == 'Bash':
                    cmd = inp.get('command', '')
                    if 'scratchpad' not in cmd and 'cd /private/tmp' not in cmd:
                        pass
                    for m in HEREDOC.finditer(cmd):
                        op, path, _, body = m.groups()
                        events[key(path)].append((seq, 'full' if op == '>' else 'append', body + '\n', t))
                    for k in re.findall(r"(?:sed -i|open\('([\w.]+)'\s*,\s*'w'\)|p\s*=\s*'([\w.]+)')", cmd):
                        for f in k:
                            if f: events[f].append((seq, 'touch', cmd[:3000], t))
                    m2 = re.findall(r"sed -i ''[^\n]*?\s([\w./-]+\.(?:py|txt|sh))\b", cmd)
                    for f in m2: events[key(f)].append((seq, 'touch', cmd[:3000], t))
            elif c.get('type') == 'tool_result':
                tid = c.get('tool_use_id')
                if tid in pending:
                    s, k, tt = pending.pop(tid)
                    body = c.get('content')
                    if isinstance(body, list):
                        body = ''.join(x.get('text', '') for x in body if isinstance(x, dict))
                    if isinstance(body, str):
                        txt = strip_read(body)
                        if txt: events[k].append((s, 'full', txt, tt))
json.dump({k: v for k, v in events.items()}, open('events.json', 'w'))
for k, v in sorted(events.items()):
    kinds = [e[1] for e in v]
    last_full = max([i for i, e in enumerate(v) if e[1] == 'full'], default=-1)
    after = [e[1] for e in v[last_full+1:]] if last_full >= 0 else kinds
    print('%-22s events %3d last_full %s after: %s' % (k, len(v), last_full >= 0, ','.join(after)[:80]))
