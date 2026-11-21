"""Portable red/green checks, never Simulator execution."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import plistlib
import struct
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest
import receipt_inventory as receipts
import verify
from prepare import prepare


class Gate(unittest.TestCase):
    def fixture(self):
        dylib=verify.linkage.MADDB_DYLIB
        sqlite="/usr/lib/libsqlite3.dylib"
        native="0000000000001234 (__TEXT,__text) external __ZN4immd7Journal4openE\n"
        native+="".join(f"                 (undefined) external {name} (from libsqlite3)\n"
                        for name in sorted(verify.SQLITE))
        return [[dylib,sqlite],["/usr/lib/libSystem.B.dylib"],native,"_public\n",
                "                 U _OBJC_CLASS_$_MadDualSQLiteDriver\n",
                ["@rpath/XCTest.framework/XCTest"]]

    def test_two_sqlite_providers_and_test_only_ingress(self):
        verify.native_boundaries(*self.fixture())
        for change in (
            {0:["/usr/lib/libsqlite3.dylib"]},
            {0:self.fixture()[0]+["@rpath/Other.framework/Other"]},
            {1:["/usr/lib/libsqlite3.dylib"]},
            {2:self.fixture()[2].replace("(from libsqlite3)","(from MadDB)")},
            {2:self.fixture()[2]+"000000000000AB12 (__TEXT,__text) external _sqlite3_reset\n"},
            {2:self.fixture()[2].replace("__ZN4immd7Journal4openE","_not_journal")},
            {3:"_sqlite3_step\n"},
            {3:"_maddb_open\n"},
            {4:self.fixture()[4]+"                 U __ZNK4immd7Journal8load_allEv\n"},
            {5:[verify.linkage.MADDB_DYLIB]},
            {5:["/usr/lib/libcurl.dylib"]},
        ):
            with self.assertRaises(verify.Failure):
                args=self.fixture()
                for i,replacement in change.items():
                    args[i]=replacement
                verify.native_boundaries(*args)

    def test_exact_native_result(self):
        summary={"totalTestCount":1,"passedTests":1,"failedTests":0,"skippedTests":0}
        case={"nodeType":"Test Case","nodeIdentifier":verify.EXACT_TEST+"()","result":"Passed"}
        verify.test_result(summary,{"testNodes":[case]})
        for nodes in ([case,case],[case|{"nodeIdentifier":"Wrong"}],[case|{"result":"Failed"}],[]):
            with self.assertRaises(verify.Failure):
                verify.test_result(summary,{"testNodes":nodes})

    def test_proven_app_owned_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            db=root/"prefix with spaces/MadDB.xcframework"
            journal=root/"different prefix/Journal"
            app=root/"app"
            graph=prepare(verify.ROOT/"ios/Smoke",app,db,journal)
            ref=lambda i:f"{i:024X}"
            self.assertEqual(graph[ref(6)]["path"],str(db))
            self.assertEqual(graph[ref(35)]["files"],[])
            self.assertIn("-lsqlite3",graph[ref(62)]["buildSettings"]["OTHER_LDFLAGS"])
            self.assertNotIn("OTHER_LDFLAGS",graph[ref(64)]["buildSettings"])
            self.assertEqual(graph[ref(64)]["buildSettings"]["BUNDLE_LOADER"],"$(TEST_HOST)")
            self.assertFalse((app/"generate_project.py").exists())

    def test_static_test_inputs_use_metadata_only(self):
        src=(verify.HERE/"JournalBridge.mm").read_text()
        self.assertIn("lstat(first, &a)",src)
        self.assertIn("a.st_dev != b.st_dev || a.st_ino != b.st_ino",src)
        self.assertNotIn("sqlite3_",src)
        self.assertNotIn("fopen(",src)
        self.assertNotIn("maddb.h",(verify.HERE/"App.swift").read_text())


class BuildOnly(unittest.TestCase):
    bundle="Debug-iphonesimulator/MadDBSmokeTests.xctest"
    uuid="12345678-9012-3456-7890-123456789012"

    def doc(self):
        return {receipts.TARGET:{"TestHostPath":"__TESTROOT__/"+receipts.HOST,
                                 "TestBundlePath":"__TESTROOT__/"+self.bundle}}

    def test_owned_simulator_is_never_booted_even_on_error(self):
        for fails in (False,True):
            with self.subTest(fails=fails), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve()
                calls=[]
                def mocked_run(label,*args,**kwargs):
                    calls.append((label,args))
                    if label=="xcode-version": return "Xcode 26.2\nBuild version 17C52"
                    if label=="sdk-version": return "26.2"
                    if label=="sim-create": return self.uuid
                    if label=="sim-build":
                        self.assertEqual(args[:2],("xcodebuild","build-for-testing"))
                        self.assertIn("platform=iOS Simulator,id="+self.uuid,args)
                        if fails: raise verify.Failure("sim-build")
                    elif label=="sim-delete":
                        self.assertEqual(args,("xcrun","simctl","delete",self.uuid))
                    else: self.fail("unexpected command")
                def mocked_packages(args,work):
                    (work/"smoke-graph").mkdir()
                    return root,root/"db",root/"journal"
                out=io.StringIO()
                with (patch.object(verify.platform,"system",return_value="Darwin"),
                      patch.object(verify.platform,"machine",return_value="arm64"),
                      patch.object(verify.os,"umask"),
                      patch.object(verify,"create_packages",side_effect=mocked_packages),
                      patch.object(verify,"prepare"),
                      patch.object(verify,"validate",return_value=(root,root/self.bundle)),
                      patch.object(verify,"inside",return_value=root),
                      patch.object(verify,"digest",return_value={}),
                      patch.object(receipts,"inventory",return_value=(b"private",("format-v1",))),
                      patch.object(verify,"run",side_effect=mocked_run), redirect_stdout(out)):
                    if fails:
                        with self.assertRaisesRegex(verify.Failure,"sim-build"):
                            verify.qualify(SimpleNamespace(build_only=True))
                    else:
                        verify.qualify(SimpleNamespace(build_only=True))
                self.assertEqual([label for label,_ in calls],
                                 ["xcode-version","sdk-version","sdk-version","sim-create","sim-build","sim-delete"])
                self.assertEqual("PASS: installed iOS dual SQLite build-only" in out.getvalue(),not fails)
                self.assertNotIn("private",out.getvalue())

    def test_receipt_file_bounds_and_containment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            plist=root/"only.xctestrun"
            with self.assertRaisesRegex(receipts.Rejected,"receipt-count"):
                receipts.inventory(root,[self.bundle])
            plist.write_bytes(plistlib.dumps(self.doc()))
            first=receipts.inventory(root,[self.bundle])
            self.assertEqual(first,receipts.inventory(root,[self.bundle]))
            self.assertEqual(first[1],("format-v1","expected-target","expected-host","expected-bundle"))
            extra=root/"second.xctestrun"
            extra.write_bytes(plist.read_bytes())
            with self.assertRaisesRegex(receipts.Rejected,"receipt-count"):
                receipts.inventory(root,[self.bundle])
            extra.unlink()
            plist.unlink()
            outside=root/"otherwise-valid.plist"
            outside.write_bytes(plistlib.dumps(self.doc()))
            plist.symlink_to(outside)
            with self.assertRaisesRegex(receipts.Rejected,"receipt-path"):
                receipts.inventory(root,[self.bundle])
            plist.unlink()
            plist.hardlink_to(outside)
            with self.assertRaisesRegex(receipts.Rejected,"receipt-path"):
                receipts.inventory(root,[self.bundle])
            plist.unlink()
            with plist.open("wb") as handle:
                handle.truncate(receipts.LIMIT+1)
            with self.assertRaisesRegex(receipts.Rejected,"receipt-size"):
                receipts.inventory(root,[self.bundle])
            plist.write_bytes(b"not a plist")
            with self.assertRaisesRegex(receipts.Rejected,"receipt-read"):
                receipts.inventory(root,[self.bundle])

    def test_repeated_keys_rejected_in_raw_xml_and_binary_at_each_level(self):
        def binary(objects):
            data=bytearray(b"bplist00")
            offsets=[]
            for content in objects:
                offsets.append(len(data))
                data.extend(content)
            end=len(data)
            data.extend(offsets)
            data.extend(struct.pack(">6xBBQQQ",1,1,len(objects),0,end))
            return bytes(data)

        repeated=b"<key>secret-key</key><string>one</string><key>secret-key</key><string>two</string>"
        def xml(children):
            return b'<?xml version="1.0" encoding="UTF-8"?>' + b'<plist version="1.0"><dict>' + children + b'</dict></plist>'
        cases=(
            # Explicit repeated dictionary keys in root and nested XML.
            xml(repeated),
            xml(b"<key>root</key><dict>"+repeated+b"</dict>"),
            # Binary plist keys deliberately reference distinct string
            # objects having the same value (not just a repeated index).
            binary([b"\xd2\x01\x02\x03\x04",b"\x51k",b"\x51k",b"\x10\x01",b"\x10\x02"]),
            binary([b"\xd1\x01\x02",b"\x51r",b"\xd2\x03\x04\x05\x06",
                    b"\x51k",b"\x51k",b"\x10\x01",b"\x10\x02"]),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            path=root/"receipt.xctestrun"
            for raw in cases:
                # Prove these are syntactically valid if overwrite is permitted.
                self.assertIsInstance(plistlib.loads(raw),dict)
                path.write_bytes(raw)
                with self.assertRaisesRegex(receipts.Rejected,"^receipt-duplicate-key$"):
                    receipts.inventory(root,[self.bundle])
            for fmt in (plistlib.FMT_XML,plistlib.FMT_BINARY):
                path.write_bytes(plistlib.dumps(self.doc(),fmt=fmt))
                self.assertEqual(receipts.inventory(root,[self.bundle])[1],
                                 ("format-v1","expected-target","expected-host","expected-bundle"))

    def test_xml_requires_single_top_dict_and_exact_nested_vocabulary(self):
        def envelope(inner):
            return b'<plist version="1.0">'+inner+b'</plist>'

        invalid=(
            envelope(b"<dict/><dict/>"),
            envelope(b"<array/>"),
            envelope(b""),
            b'<wrapper>'+envelope(b"<dict/>")+b'</wrapper>',
            envelope(b"<dict><key>foreign</key><wrapper><dict/></wrapper></dict>"),
            envelope(b"<dict><key>foreign</key><array><wrapper/></array></dict>"),
            envelope(b"<dict><key>missing-value</key></dict>"),
            envelope(b"<dict><key>missing-value</key><key>unexpected</key><true/></dict>"),
            envelope(b"<dict><string>value-without-key</string></dict>"),
            envelope(b"<dict><key><string>nested-in-key</string></key><true/></dict>"),
            b'<!DOCTYPE plist SYSTEM "https://example.invalid/never-load">'+envelope(b"<dict/>"),
            b'<!DOCTYPE plist [<!ENTITY local "unsafe">]>'+envelope(b"<dict/>"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            path=root/"receipt.xctestrun"
            for raw in invalid:
                path.write_bytes(raw)
                with self.assertRaisesRegex(receipts.Rejected,"^receipt-xml-shape$"):
                    receipts.inventory(root,[self.bundle])
            valid=plistlib.dumps(self.doc())
            self.assertIn(b'<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                          b'"http://www.apple.com/DTDs/PropertyList-1.0.dtd">',valid)
            path.write_bytes(valid)
            self.assertIn("expected-bundle",receipts.inventory(root,[self.bundle])[1])

    def test_inventory_fixed_observations_do_not_accept_launch(self):
        target=self.doc()[receipts.TARGET]|{
            "BlueprintName":receipts.TARGET,"TestHostPath":"/private/unexpected",
            "TestBundlePath":"__TESTROOT__/../private.xctest",
            "EnvironmentVariables":{"BAD_ENV":"/private/inject"},
            "TestingEnvironmentVariables":{"DYLD_INSERT_LIBRARIES":"/private/lib.dylib"},
            "OnlyTestIdentifiers":["private/method"]}
        cfg={"TestTargets":[target]}
        value={"__xctestrun_metadata__":{"FormatVersion":2},"TestConfigurations":[cfg]}
        self.assertEqual(receipts.describe(value,[self.bundle]),(
            "format-v2","expected-target","other-host","other-bundle",
            "scheme-env-present","loader-env-present","known-overrides-present"))
        with self.assertRaisesRegex(receipts.Rejected,"receipt-target-count"):
            receipts.describe(value|{"TestConfigurations":[{"TestTargets":[target,target]}]},[self.bundle])
        with self.assertRaisesRegex(receipts.Rejected,"receipt-version"):
            receipts.describe(value|{"__xctestrun_metadata__":{"FormatVersion":True}},[self.bundle])


if __name__=="__main__":
    unittest.main()
