"""Portable provenance, source ownership and exact result guard tests."""
import plistlib
from pathlib import Path
import tempfile
import unittest
import verify


class TestQualification(unittest.TestCase):
    def test_modes_link_sdk_only_to_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            db=root/"prefix space/MadDB.xcframework"
            link=root/"prefix space/MadLink.xcframework/ios-arm64-simulator/MadLink.framework/MadLink"
            obs=(root/"obs space/libobs.a",root/"obs space/Headers")
            for enabled in (False,True):
                dest=root/("on" if enabled else "off")
                objects=verify.prepare(verify.ROOT/"ios/Smoke",dest,db,link,obs if enabled else None)
                ref=lambda n:f"{n:024X}"
                app=objects[ref(62)]["buildSettings"]
                self.assertIn('"'+str(link)+'"',app["OTHER_LDFLAGS"])
                self.assertEqual('"'+str(obs[0])+'"' in app["OTHER_LDFLAGS"],enabled)
                self.assertEqual("HEADER_SEARCH_PATHS" in app,enabled)
                self.assertEqual(objects[ref(35)]["files"],[])
                self.assertEqual(objects[ref(33)]["files"],[ref(16)])
                self.assertIn(ref(81),objects[ref(30)]["files"])
                self.assertNotIn(ref(81),objects[ref(34)]["files"])

    def test_simulator_slice_and_private_headers_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            xc=Path(tmp).resolve()
            child=xc/"ios-arm64-simulator"
            child.mkdir()
            h=child/"Headers"
            for n in verify.HEADERS+("module.modulemap",):
                p=h/n;p.parent.mkdir(parents=True,exist_ok=True);p.touch()
            archive=child/"libmadobs_runtime.a";archive.touch()
            info={"AvailableLibraries":[{"SupportedPlatform":"ios","SupportedArchitectures":["arm64"]},
                {"SupportedPlatform":"ios","SupportedPlatformVariant":"simulator","SupportedArchitectures":["arm64"],
                 "LibraryIdentifier":child.name,"LibraryPath":archive.name,"HeadersPath":"Headers"}]}
            (xc/"Info.plist").write_bytes(plistlib.dumps(info))
            self.assertEqual(verify.select_sim(xc,archive.name,True),(archive,h))
            (h/"madobs/private.h").touch()
            with self.assertRaises(verify.Failure):
                verify.select_sim(xc,archive.name,True)

    def test_result_exact_case_only(self):
        summary={"totalTestCount":1,"passedTests":1,"failedTests":0,"skippedTests":0}
        test={"nodeType":"Test Case","nodeIdentifier":verify.EXACT_TEST+"()","result":"Passed"}
        verify.test_result(summary,{"testNodes":[test]})
        for cases in ([],[test,test],[test|{"result":"Failed"}],[test|{"nodeIdentifier":"Other/testFoo"}]):
            with self.assertRaises(verify.Failure):
                verify.test_result(summary,{"testNodes":cases})

    def test_app_test_bridge_source_boundaries(self):
        app=(verify.HERE/"App.swift").read_text()
        native=(verify.HERE/"Bridge.mm").read_text()
        test=(verify.HERE/"CohostTests.mm").read_text()
        self.assertIn("import MadDB",app)
        self.assertIn("MadCohostDriver.run",app)
        self.assertIn("MadCohostDriver run:",test)
        self.assertNotIn("madobs/",test)
        self.assertNotIn("maddb.h",native)
        self.assertNotIn("madobs/private.h",native)
        self.assertIn("madobs_sanitize_event",native)
        self.assertIn("madobs_emit_generic_event(s.observer,&clean)",native)
        self.assertIn("ml_next_completion_v1",native)


if __name__=="__main__":
    unittest.main()
