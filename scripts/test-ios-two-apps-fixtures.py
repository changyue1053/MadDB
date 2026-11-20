"""Synthetic local fixtures for the host validator; no simulator execution."""
import importlib.util
import json
from pathlib import Path
import tempfile
import struct
import unittest
from unittest.mock import patch
import uuid

from ios_two_apps_linkage import binary_metadata, verify_app, MADDB_DYLIB

spec = importlib.util.spec_from_file_location("gate", Path(__file__).with_name("test-ios-two-apps.py"))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

def string_cmd(code, name, offset):
    data = name.encode("ascii") + b"\0"
    width = (offset + len(data) + 7) & ~7
    return struct.pack("<III", code, width, offset) + bytes(offset-12) + data + bytes(width-offset-len(data))

def macho(kind, *, payload=b"CODE", signature=b"sign1", identifier=b"A"*16,
          dependencies=(MADDB_DYLIB,), platform=7, runpath="@executable_path/Frameworks"):
    commands = [struct.pack("<6I", 0x32, 24, platform, 0, 0, 0),
                struct.pack("<2I16s", 0x1b, 24, identifier)]
    if kind == 2:
        commands.append(string_cmd(0x8000001c, runpath, 12))
        commands.extend(string_cmd(0xc, dep, 24) for dep in dependencies)
    else:
        commands.append(string_cmd(0xd, MADDB_DYLIB, 24))
        pos = 32 + sum(map(len, commands)) + 152
        seg = struct.pack("<2I16s4Q4I", 0x19, 152, b"__TEXT", 0, 0, 0, 0, 0, 0, 1, 0)
        sec = struct.pack("<16s16s2Q8I", b"__text", b"__TEXT", 0, len(payload), pos,
                          0, 0, 0, 0x80000400, 0, 0, 0)
        commands.append(seg + sec)
    header = struct.pack("<8I", 0xfeedfacf, 0x0100000c, 0, kind, len(commands),
                         sum(map(len, commands)), 0, 0)
    return header + b"".join(commands) + payload + signature

class AcceptanceFixtures(unittest.TestCase):
    def test_macho_identity_ignores_signature_but_not_code_or_uuid(self):
        original = binary_metadata(macho(6), 6)
        self.assertEqual(original, binary_metadata(macho(6, signature=b"different signature"), 6))
        self.assertNotEqual(original, binary_metadata(macho(6, payload=b"FAKE"), 6))
        self.assertNotEqual(original, binary_metadata(macho(6, identifier=b"B"*16), 6))
        for invalid in (macho(6, platform=2), macho(6, payload=b""), macho(6)[:35]):
            with self.assertRaises(ValueError): binary_metadata(invalid, 6)

    def test_app_dependency_is_exact_and_singular(self):
        binary_metadata(macho(2), 2)
        for deps in ((), (MADDB_DYLIB, MADDB_DYLIB), ("/tmp/MadDB.framework/MadDB",),
                     (MADDB_DYLIB, "@rpath/MadDBOther.framework/MadDBOther")):
            with self.assertRaises(ValueError): binary_metadata(macho(2, dependencies=deps), 2)
        with self.assertRaises(ValueError): binary_metadata(macho(2, runpath="/tmp/Frameworks"), 2)

    def test_app_rejects_replaced_embedded_framework(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Path(temp).resolve()
            (app / "MadDBSmoke").write_bytes(macho(2))
            native = app / "Frameworks/MadDB.framework/MadDB"
            native.parent.mkdir(parents=True)
            native.write_bytes(macho(6, signature=b"resigned"))
            verify_app(app, binary_metadata(macho(6), 6))
            native.write_bytes(macho(6, payload=b"FAKE"))
            with self.assertRaises(ValueError):
                verify_app(app, binary_metadata(macho(6), 6))

    def test_evidence_rejects_stale_cross_app_or_inexact_results(self):
        bundle = gate.IDS[0]
        row = dict(bundle=bundle, nonce="fresh", phase="read", pid=7, value=gate.VALUES[0])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "result.json"
            def verify(data):
                path.write_text(json.dumps(data))
                gate.evidence(path, bundle, "fresh", "read", 7, gate.VALUES[0])
            verify(row)
            for change in (dict(nonce="old"), dict(phase="write"), dict(pid=8),
                           dict(bundle=gate.IDS[1]), dict(value=gate.VALUES[1]),
                           dict(value=[False, 65, 255, 17]), dict(extra=True)):
                with self.assertRaises(RuntimeError):
                    verify({**row, **change})

    def test_owned_containment(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            sim = str(uuid.uuid4())
            parent = home / "Library/Developer/CoreSimulator/Devices" / sim / "data/Containers/Data/Application"
            owned = parent / str(uuid.uuid4())
            owned.mkdir(parents=True)
            outside = home / str(uuid.uuid4())
            outside.mkdir()
            alias = parent / str(uuid.uuid4())
            alias.symlink_to(outside, target_is_directory=True)
            with patch.object(gate.Path, "home", return_value=home):
                self.assertEqual(gate.owned_container(owned, sim), owned.resolve())
                for invalid in (outside, alias):
                    with self.assertRaises(RuntimeError):
                        gate.owned_container(invalid, sim)

    def test_package_manifest_rejects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file = root / "package"
            file.write_bytes(b"first")
            first = gate.manifest(root)
            file.write_bytes(b"other")
            self.assertNotEqual(first, gate.manifest(root))

if __name__ == "__main__":
    unittest.main()
