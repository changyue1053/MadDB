"""Portable validation of the orchestrator; never substitutes for installed SDK CI."""
import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().with_name("lock_recovery.py")
spec = importlib.util.spec_from_file_location("lock_recovery", SOURCE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

# An independent process fixture, intentionally not the MadDB package.
PEER = r"""
import sqlite3, sys
from pathlib import Path
path, phase = sys.argv[1:]
with sqlite3.connect(path, timeout=0, isolation_level=None) as db:
    def get():
        return db.execute('SELECT value FROM maddb_kv').fetchone()[0]
    def put(value):
        db.execute('UPDATE maddb_kv SET value=?', (value,))
    if phase in ('write', 'lock-recovery'):
        db.execute('CREATE TABLE maddb_kv(namespace TEXT,key TEXT,value BLOB)')
        db.execute('INSERT INTO maddb_kv VALUES (?,?,?)',
                   ('same.namespace','same-key',
                    bytes((0,65,255)) if phase == 'lock-recovery' else B_VALUE))
    if phase == 'read':
        assert get() == B_VALUE
    elif phase == 'read-replacement':
        assert get() == bytes((0,67,254))
    elif phase == 'lock-recovery':
        print('ready', flush=True)
        assert sys.stdin.readline() == 'locked\n'
        assert get() == bytes((0,65,255))
        try:
            put(bytes((0,68,253)))
        except sqlite3.OperationalError as error:
            assert error.sqlite_errorcode == sqlite3.SQLITE_BUSY
        else:
            raise AssertionError('lock missing')
        assert get() == bytes((0,65,255))
        print(RECEIPT, flush=True)
        assert sys.stdin.readline() == 'released\n'
        assert get() == bytes((0,65,255))
        put(bytes((0,67,254)))
"""


class Orchestration(unittest.TestCase):
    def drive(self, receipt="rejected", other=bytes((0, 66, 128))):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp).resolve()
            peer = work / "peer"
            peer.write_text(f"#!{sys.executable}\nRECEIPT={receipt!r}\nB_VALUE={other!r}\n" + PEER)
            peer.chmod(0o700)
            return subprocess.run([sys.executable, "-I", str(SOURCE), str(peer), str(peer), str(work)],
                                  text=True, capture_output=True, timeout=15, check=False)

    def test_witness_sees_real_lock_and_recovers(self):
        result = self.drive()
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_bad_receipt_and_wrong_final_store_are_rejected(self):
        for result in (self.drive(receipt="unexpected-sensitive-shape"),
                       self.drive(other=bytes((0, 65, 255)))):
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "FAIL: installed-linux-cross-process-lock-contract\n")

    def test_dead_peer_and_timeout_are_bounded(self):
        gate.BOUND = 0.02
        try:
            for code in ("", "import time;time.sleep(5)"):
                with subprocess.Popen([sys.executable, "-I", "-c", code],
                                      stdout=subprocess.PIPE) as proc:
                    try:
                        with self.assertRaises(ValueError):
                            gate.receive(proc, b"ready\n")
                    finally:
                        if proc.poll() is None:
                            proc.kill()
        finally:
            gate.BOUND = 30


if __name__ == "__main__":
    unittest.main()
