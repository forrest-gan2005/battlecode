import io, json, os, re, subprocess, sys, tarfile, threading, time, urllib.request
from urllib.parse import quote

SERVER = sys.argv[1].rstrip('/')
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else max(1, (os.cpu_count() or 4) // 2)
HOME = os.path.expanduser('~/bcw')
RESULT = re.compile(r'team ([AB]) wins after (\d+) rounds \(([^)]*)\)')
locks = {}
built = set()
LAST_ERROR = {}
locks_guard = threading.Lock()
done_count = [0]


def fetch(path):
    with urllib.request.urlopen(SERVER + path, timeout=60) as r:
        return r.status, r.read()


def lock_for(key):
    with locks_guard:
        return locks.setdefault(key, threading.Lock())


def ensure_bot(path, digest):
    target = os.path.join(HOME, 'bots', digest)
    with lock_for('dl' + digest):
        if not os.path.exists(os.path.join(target, 'main.cpp')):
            _, blob = fetch('/bot?path=' + quote(path))
            os.makedirs(target, exist_ok=True)
            with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as tar:
                tar.extractall(target)
    return target


def ensure_map(name):
    target = os.path.join(HOME, 'maps', name + '.map')
    with lock_for('map' + name):
        if not os.path.exists(target):
            _, blob = fetch('/map?name=' + quote(name))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            open(target, 'wb').write(blob)
    return target


def play(job):
    bot = ensure_bot(job['bot'], job['bot_hash'])
    opp = ensure_bot(job['opp'], job['opp_hash'])
    mp = ensure_map(job['map'])
    a, b = (bot, opp) if job['side'] == 0 else (opp, bot)
    ours = 'A' if job['side'] == 0 else 'B'
    key = job['bot_hash'] + job['opp_hash']
    lock = lock_for('build' + key)
    held = False
    if key not in built:
        lock.acquire()
        held = True
        if key in built:
            lock.release()
            held = False
    rp = os.path.join(HOME, 'replays', '%d_%s.replay' % (job['id'], threading.get_ident()))
    keep = job.get('keep')
    if keep:
        os.makedirs(os.path.dirname(rp), exist_ok=True)
    try:
        for attempt in range(3):
            proc = subprocess.run(['unswbc', 'run', mp, a, b] + (['-o', rp] if keep else ['--no-replay']) + ['--no-debug', '--seed', str(job['seed'])],
                                  capture_output=True, text=True)
            out = proc.stdout + proc.stderr
            m = RESULT.search(out)
            if m or 'draw' in out.lower():
                break
        else:
            sys.stderr.write('FAILED %s %s\n%s\n' % (job['tag'], job['map'], out[-400:]))
            LAST_ERROR[threading.get_ident()] = out[-400:]
            return None
    finally:
        built.add(key)
        if held:
            lock.release()
    r = dict(win=0, us=0, them=0, rounds=500, wiped=0, wiped_them=0, how='draw')
    if m:
        r['win'] = int(m.group(1) == ours)
        r['rounds'] = int(m.group(2))
        nums = re.findall(r'(\d+) to (\d+)', m.group(3))
        if nums:
            w, l = int(nums[0][0]), int(nums[0][1])
            r['us'], r['them'] = (w, l) if r['win'] else (l, w)
        why = m.group(3)
        r['how'] = 'elim' if 'elimination' in why else 'queen' if 'queen' in why else 'longest' if 'longest' in why else 'total'
        if 'elimination' in why:
            r['wiped' if not r['win'] else 'wiped_them'] = 1
    if keep and os.path.exists(rp):
        blob = open(rp, 'rb').read()
        req = urllib.request.Request(SERVER + '/replay?id=%d' % job['id'], data=blob, headers={'Content-Type': 'application/octet-stream'})
        for attempt in range(5):
            try:
                urllib.request.urlopen(req, timeout=120).read()
                break
            except Exception:
                time.sleep(5)
        os.remove(rp)
    return r


def loop():
    while True:
        try:
            status, body = fetch('/job')
        except Exception:
            time.sleep(10)
            continue
        if status == 204 or not body:
            time.sleep(10)
            continue
        job = json.loads(body)
        try:
            result = play(job)
        except Exception as e:
            sys.stderr.write('ERROR %s\n' % e)
            result = None
        data = json.dumps({'id': job['id'], 'result': result, 'error': LAST_ERROR.get(threading.get_ident(), '') if result is None else ''}).encode()
        req = urllib.request.Request(SERVER + '/result', data=data, headers={'Content-Type': 'application/json'})
        for attempt in range(5):
            try:
                urllib.request.urlopen(req, timeout=60).read()
                break
            except Exception:
                time.sleep(5)
        done_count[0] += 1
        if result is not None:
            print('done %d  (%s %s win=%d)' % (done_count[0], job['tag'], job['map'], result['win']), flush=True)


if __name__ == '__main__':
    os.makedirs(HOME, exist_ok=True)
    print('worker: %s with %d parallel games' % (SERVER, WORKERS), flush=True)
    threads = [threading.Thread(target=loop, daemon=True) for _ in range(WORKERS)]
    for t in threads:
        t.start()
    while True:
        time.sleep(60)
