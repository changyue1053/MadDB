"""Portable red/green checks, never Simulator execution."""
from pathlib import Path
import tempfile
import unittest
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


if __name__=="__main__":
    unittest.main()
