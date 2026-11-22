"""Drive the installed Linux SDK processes and an independent SQLite witness."""
import os
from pathlib import Path
import selectors
import sqlite3
import subprocess
import sys
import time

# Fail/cleanup bounds, not timing assertions or performance guarantees.
BOUND = 30
NAMESPACE = "same.namespace"
KEY = "same-key"
ORIGINAL = bytes((0, 65, 255))
SENTINEL = bytes((0, 69, 252))
REPLACEMENT = bytes((0, 67, 254))
OTHER = bytes((0, 66, 128))


def expect(condition):
    if not condition:
        raise ValueError("contract")


def receive(peer, expected):
    """Accept exactly one short fixed receipt, including its delimiter."""
    expect(len(expected) < 16 and expected.endswith(b"\n"))
    deadline = time.monotonic() + BOUND
    received = bytearray()
    with selectors.DefaultSelector() as selector:
        selector.register(peer.stdout, selectors.EVENT_READ)
        while len(received) < len(expected):
            left = deadline - time.monotonic()
            expect(left > 0 and selector.select(left))
            chunk = os.read(peer.stdout.fileno(), len(expected) - len(received))
            expect(chunk)
            received.extend(chunk)
            expect(expected.startswith(received))


def signal(peer, value):
    # Only one fixed tiny command is in flight per acknowledged peer state.
    expect(peer.stdin.write(value) == len(value))
    peer.stdin.flush()


def short(binary, store, action):
    subprocess.run([str(binary), str(store), action], check=True, timeout=BOUND,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def rows(conn):
    return conn.execute("SELECT namespace,key,value FROM maddb_kv LIMIT 2").fetchall()


def run(app_a, app_b, work):
    a = work / "lock-a.sqlite"
    b = work / "lock-b.sqlite"
    expect(not any(p.exists() or p.is_symlink() for p in (a, b)))
    with subprocess.Popen([str(app_a), str(a), "lock-recovery"], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0) as peer:
        try:
            receive(peer, b"ready\n")
            # URI rw mode proves A's file exists; never create it through Python.
            witness = sqlite3.connect(a.as_uri() + "?mode=rw", uri=True, timeout=1,
                                      isolation_level=None)
            try:
                expect(witness.execute("PRAGMA journal_mode").fetchone() == ("delete",))
                witness.execute("BEGIN IMMEDIATE")
                expect(witness.in_transaction and rows(witness) == [(NAMESPACE, KEY, ORIGINAL)])
                count = witness.execute("UPDATE maddb_kv SET value=? WHERE namespace=? AND key=?",
                                        (SENTINEL, NAMESPACE, KEY)).rowcount
                expect(count == 1 and rows(witness) == [(NAMESPACE, KEY, SENTINEL)])
                signal(peer, b"locked\n")
                receive(peer, b"rejected\n")
                # A is still live and blocked on the pipe; witness still owns
                # A's write transaction while independent B commits and reopens.
                expect(witness.in_transaction and rows(witness) == [(NAMESPACE, KEY, SENTINEL)])
                short(app_b, b, "write")
                short(app_b, b, "read")
                expect(witness.in_transaction and rows(witness) == [(NAMESPACE, KEY, SENTINEL)])
                witness.execute("ROLLBACK")
                expect(not witness.in_transaction and rows(witness) == [(NAMESPACE, KEY, ORIGINAL)])
            finally:
                witness.close()
            signal(peer, b"released\n")
            peer.stdin.close()
            expect(peer.wait(timeout=BOUND) == 0)
            expect(peer.stdout.read(1) == b"")
            short(app_a, a, "read-replacement")
            short(app_b, b, "read")
            for db, expected in ((a, REPLACEMENT), (b, OTHER)):
                reader = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=1)
                try:
                    expect(rows(reader) == [(NAMESPACE, KEY, expected)])
                finally:
                    reader.close()
        finally:
            if peer.poll() is None:
                peer.kill()
                peer.wait(timeout=BOUND)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 4:
            raise ValueError("arguments")
        app_a, app_b, work = map(Path, sys.argv[1:])
        run(app_a, app_b, work.resolve(strict=True))
    except Exception:
        sys.exit("FAIL: installed-linux-cross-process-lock-contract")
