import hashlib
import tempfile
import unittest
from pathlib import Path
from project import create
from results import verify
ROOT=Path(__file__).resolve().parents[1]
class Tests(unittest.TestCase):
    def test_isolated_typed_project(self):
        original=(ROOT/'ios/Smoke/MadDBSmoke.xcodeproj/project.pbxproj').read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp); objects=create(ROOT,work/'consumer',work/'relocated SDK/MadDB.xcframework',work/'headers',work/'observer')
            for n in (62,63):
                self.assertNotIn('OTHER_LDFLAGS',objects[f'{n:024X}']['buildSettings'])
            for n in (64,65):
                s=objects[f'{n:024X}']['buildSettings']
                self.assertTrue(any('$(PLATFORM_NAME)/lib/libmadobs_runtime.a' in x for x in s['OTHER_LDFLAGS']))
                self.assertEqual(s['CLANG_CXX_LANGUAGE_STANDARD'],'c++17')
            self.assertEqual((work/'consumer/Tests/Bridge.cpp').read_bytes(),(ROOT/'ios-obs-composition/Bridge.cpp').read_bytes())
            self.assertEqual(objects[f'{8:024X}']['lastKnownFileType'],'sourcecode.swift')
            self.assertIn(f'{81:024X}', objects[f'{34:024X}']['files'])
        self.assertEqual(original,(ROOT/'ios/Smoke/MadDBSmoke.xcodeproj/project.pbxproj').read_bytes())
    def test_swift_boundary_no_db_c_calls(self):
        bridge=(ROOT/'ios-obs-composition/Bridge.cpp').read_text()
        for name in ('maddb_put(', 'maddb_get(', 'maddb_open', 'maddb_close(', 'maddb_obs.h'):
            self.assertNotIn(name, bridge)
        swift=(ROOT/'ios-obs-composition/Tests.swift').read_text()
        self.assertIn('import MadDB',swift)
        self.assertIn('try db.put(',swift)
        self.assertIn('try db.get(',swift)
    def test_exact_result(self):
        summary={'totalTestCount':1,'passedTests':1,'failedTests':0,'skippedTests':0}
        case={'nodeType':'Test Case','nodeIdentifier':'MadDBObsCompositionTests/testSQLitePrivateEventsDrain','result':'Passed'}
        verify(summary,{'testNodes':[case]})
        for key in summary:
            bad=dict(summary);bad[key]+=1
            with self.assertRaises(ValueError):verify(bad,{'testNodes':[case]})
        with self.assertRaises(ValueError):verify(summary,{'testNodes':[]})
        with self.assertRaises(ValueError):verify(summary,{'testNodes':[dict(case,nodeIdentifier='Other/test')]})
    def test_no_production_changes(self):
        text=(ROOT/'ios-obs-composition/verify.py').read_text()
        self.assertIn("PIN = '4af77ffa464a48307e5ff2d95f10b835919d205b'",text)
        self.assertIn("'-DIMOBS_BORINGSSL_CRYPTO_LIB='",text)
        self.assertIn("'-DMADOBS_PACKAGE_BORINGSSL=OFF'",text)
        self.assertIn("'CODE_SIGNING_ALLOWED=NO','build-for-testing'",text)
if __name__=='__main__':unittest.main()
