import hashlib, io, json, os, queue, tarfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PORT = int(os.environ.get('DIST_PORT', '8765'))
LEASE = 900
HERE = os.path.dirname(os.path.abspath(__file__))


def bot_hash(path):
    h = hashlib.sha1()
    for name in ('main.cpp', 'helper.hpp', 'bot.toml'):
        p = os.path.join(path, name)
        if os.path.exists(p):
            h.update(name.encode())
            h.update(open(p, 'rb').read())
    return h.hexdigest()[:16]


def bot_tar(path):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:
        for name in ('main.cpp', 'helper.hpp', 'bot.toml'):
            p = os.path.join(path, name)
            if os.path.exists(p):
                tar.add(p, arcname=name)
    return buf.getvalue()


class Board:
    def __init__(self, jobs, mapper, replay_path=None):
        self.jobs = list(jobs)
        self.mapper = mapper
        self.replay_path = replay_path
        self.todo = queue.Queue()
        for k in range(len(self.jobs)):
            self.todo.put(k)
        self.lease = {}
        self.done = {}
        self.lock = threading.Lock()
        self.remote = 0
        self.hashes = {}
        self.errors = []

    def take(self):
        with self.lock:
            now = time.time()
            for k, t in list(self.lease.items()):
                if k not in self.done and now - t > LEASE:
                    del self.lease[k]
                    self.todo.put(k)
        while True:
            try:
                k = self.todo.get_nowait()
            except queue.Empty:
                return None
            with self.lock:
                if k in self.done:
                    continue
                self.lease[k] = time.time()
            return k

    def finish(self, k, result, remote=False):
        with self.lock:
            if k not in self.done:
                self.done[k] = result
                if remote:
                    self.remote += 1

    def complete(self):
        with self.lock:
            return len(self.done) == len(self.jobs)

    def describe(self, k):
        tag, bot, opp, m, seed, side = self.jobs[k]
        for path in (bot, opp):
            if path not in self.hashes:
                self.hashes[path] = bot_hash(path)
        return dict(id=k, tag=tag, bot=bot, bot_hash=self.hashes[bot], opp=opp, opp_hash=self.hashes[opp],
                    map=m, seed=seed, side=side, keep=self.replay_path is not None)


def serve(board):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, code, body=b'', kind='application/json'):
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            if url.path == '/job':
                k = board.take()
                if k is None:
                    self.send(204 if not board.complete() else 410)
                    return
                self.send(200, json.dumps(board.describe(k)).encode())
            elif url.path == '/bot':
                self.send(200, bot_tar(q['path'][0]), 'application/gzip')
            elif url.path == '/map':
                self.send(200, open(board.mapper(q['name'][0]), 'rb').read(), 'text/plain')
            elif url.path == '/status':
                with board.lock:
                    body = dict(total=len(board.jobs), done=len(board.done), remote=board.remote, leased=len(board.lease) - len(set(board.lease) & set(board.done)))
                self.send(200, json.dumps(body).encode())
            elif url.path == '/errors':
                self.send(200, json.dumps(board.errors[-20:]).encode())
            elif url.path == '/worker.py':
                self.send(200, open(os.path.join(HERE, 'worker.py'), 'rb').read(), 'text/plain')
            else:
                self.send(404)

        def do_POST(self):
            url = urlparse(self.path)
            if url.path == '/replay':
                k = int(parse_qs(url.query)['id'][0])
                body = self.rfile.read(int(self.headers['Content-Length']))
                if board.replay_path and 0 <= k < len(board.jobs):
                    path = board.replay_path(board.jobs[k])
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    open(path, 'wb').write(body)
                self.send(200, b'{}')
                return
            if url.path != '/result':
                self.send(404)
                return
            data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            k = int(data['id'])
            if 0 <= k < len(board.jobs):
                board.finish(k, data.get('result'), remote=True)
                if data.get('error'):
                    board.errors.append((board.jobs[k][3], data['error'][-300:]))
            self.send(200, b'{}')

    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def run(jobs, play, mapper, local_workers, replay_path=None):
    board = Board(jobs, mapper, replay_path)
    server = serve(board)

    def local_loop():
        while True:
            k = board.take()
            if k is None:
                if board.complete():
                    return
                time.sleep(2)
                continue
            try:
                _, _, r = play(board.jobs[k])
            except Exception:
                r = None
            board.finish(k, r)

    threads = [threading.Thread(target=local_loop) for _ in range(local_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    while not board.complete():
        time.sleep(2)
    server.shutdown()
    print(f'remote games {board.remote} of {len(jobs)}', flush=True)
    return [board.done[k] for k in range(len(jobs))]
