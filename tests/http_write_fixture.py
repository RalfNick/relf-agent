"""Owned real loopback writer with an independent durable effect ledger."""

import json
import socket
import sqlite3
import threading
from contextlib import closing, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@contextmanager
def write_endpoint(root):
    calls, started, release, ended = [], threading.Event(), threading.Event(), threading.Event()
    database = root / "business.sqlite"
    with closing(sqlite3.connect(database)) as db, db:
        db.execute("CREATE TABLE effects (effect_key TEXT PRIMARY KEY, result TEXT NOT NULL)")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def write(self):
            try:
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                values = json.loads(raw)
                calls.append(
                    {
                        "method": self.command,
                        "path": self.path,
                        "headers": dict(self.headers),
                        "body": raw,
                    }
                )
                with closing(sqlite3.connect(database)) as db, db:
                    db.execute("BEGIN IMMEDIATE")
                    found = db.execute(
                        "SELECT result FROM effects WHERE effect_key=?", (values["effect_key"],)
                    ).fetchone()
                    if found:
                        result = json.loads(found[0])
                    else:
                        result = {"value": values["value"], "effect_key": values["effect_key"]}
                        db.execute(
                            "INSERT INTO effects VALUES (?,?)",
                            (values["effect_key"], json.dumps(result)),
                        )
                started.set()
                if self.path == "/hang":
                    assert release.wait(5), "Owned HTTP fixture release exceeded original barrier"
                if self.path == "/lost" and len(calls) == 1:
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
                content = b"" if self.path == "/empty" else json.dumps(result).encode()
                self.send_response(204 if self.path == "/empty" else 200)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                try:
                    self.wfile.write(content)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            finally:
                ended.set()

        do_PUT = write
        do_PATCH = write

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls, started, release, ended
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join()


def effects(root):
    with closing(sqlite3.connect(root / "business.sqlite")) as db:
        return [
            (key, json.loads(value))
            for key, value in db.execute(
                "SELECT effect_key,result FROM effects ORDER BY effect_key"
            )
        ]
