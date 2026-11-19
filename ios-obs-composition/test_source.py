import hashlib
import tempfile
import unittest
from pathlib import Path
from project import create
from results import verify
from verify import simulator_products
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
    def test_actual_simulator_architecture_gate(self):
        swift=(ROOT/'ios-obs-composition/Tests.swift').read_text()
        self.assertIn('#if !targetEnvironment(simulator) || !arch(arm64)',swift)
        script=(ROOT/'ios-obs-composition/verify.py').read_text()
        self.assertNotIn("'spawn',uuid,'uname'",script)
        self.assertIn("'test-without-building'",script)
        self.assertIn("'MadDBSmokeTests.xctest/MadDBSmokeTests'",script)
        self.assertLess(script.index("'composition-build-for-testing'"),script.index("'simulator-product-arm64'"))
        self.assertLess(script.index("'simulator-product-arm64'"),script.index("'composition-test'"))
        self.assertIn("f'platform=iOS Simulator,id={uuid}'",script)
        self.assertIn("except (OSError,subprocess.SubprocessError):cleanup_failed=True",script)
    def test_hosted_product_layouts(self):
        for embedded in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);app=root/'MadDBSmoke.app/MadDBSmoke'
                app.parent.mkdir(parents=True);app.write_bytes(b'app')
                relative=('MadDBSmoke.app/PlugIns/' if embedded else '')+'MadDBSmokeTests.xctest/MadDBSmokeTests'
                test=root/relative;test.parent.mkdir(parents=True);test.write_bytes(b'test')
                self.assertEqual(set(simulator_products(root)),{app.resolve(),test.resolve()})
                alias=root/('MadDBSmokeTests.xctest/MadDBSmokeTests' if embedded else 'MadDBSmoke.app/PlugIns/MadDBSmokeTests.xctest/MadDBSmokeTests')
                alias.parent.mkdir(parents=True);alias.symlink_to(test)
                self.assertEqual(len(simulator_products(root)),2)
                alias.unlink();alias.write_bytes(b'other-test')
                self.assertEqual(len(simulator_products(root)),3)
    def test_missing_or_escaping_product(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'products';root.mkdir()
            app=root/'MadDBSmoke.app/MadDBSmoke';app.parent.mkdir();app.write_bytes(b'app')
            with self.assertRaises(ValueError):simulator_products(root)
            outside=Path(tmp)/'outside';outside.write_bytes(b'wrong')
            test=root/'MadDBSmokeTests.xctest/MadDBSmokeTests';test.parent.mkdir();test.symlink_to(outside)
            with self.assertRaises(ValueError):simulator_products(root)
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
