"""Portable negative controls for package/node provenance, not native cohost proof."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("gate",HERE/"verify.py")
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class Checks(unittest.TestCase):
    def test_inventory_rejects_runtime_unknown_or_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in gate.API_ONLY_FILES:
                p=root/name
                p.parent.mkdir(parents=True,exist_ok=True)
                p.touch()
            gate.check_inventory(root)
            for name in ("include/madobs/private.h","lib/libmadobs_runtime.a","lib/libz.so.1"):
                p=root/name
                p.touch()
                with self.assertRaises(gate.base.Failure): gate.check_inventory(root)
                p.unlink()
            (root/"alias").symlink_to(root/"include",target_is_directory=True)
            with self.assertRaises(gate.base.Failure): gate.check_inventory(root)

    def test_symbols_reject_runtime_exports_but_allow_header_inline(self):
        good="0000 T ml_create_tracked_v1\n0000 W madobs_observer_emit_private\n"
        gate.check_symbols(good)
        with self.assertRaises(gate.base.Failure): gate.check_symbols("no actual Link")
        for name in ("madobs_create","madobs_private_open_ex","madobs_observer_for_runtime","madobs_emit_generic_event"):
            with self.assertRaises(gate.base.Failure): gate.check_symbols(good+"0000 T "+name+"\n")

    def test_same_linked_dylib_without_zlib(self):
        lib=Path("/example space/libmaddb.so")
        line="libmaddb.so => "+str(lib)+" (0x111)\n"
        gate.base.check_loader(line,lib,on=False)
        for text in (line+"libz.so.1 => /example (0x112)\n",line.replace("example","different"),line+line):
            with self.assertRaises(gate.base.Failure): gate.base.check_loader(text,lib,on=False)

    def test_link_tokens_reject_runtime_and_static_or_dynamic_zlib(self):
        archive=Path("/space here/libmadlink.a")
        command='g++ cohost.o "/space here/libmadlink.a" -lmaddb'
        gate.check_api_link(command,archive)
        for extra in ("-lz","/prefix/libz.a","/path/libz.so.1","/prefix/libmadobs_runtime.a"):
            with self.assertRaises(gate.base.Failure): gate.check_api_link(command+" "+extra,archive)

    def test_prior_workflows_and_consumers_are_separate(self):
        cmake=(HERE/"CMakeLists.txt").read_text()
        self.assertIn("MadObs::api",cmake)
        self.assertNotIn("target_link_libraries(cohost PRIVATE MadObs::runtime)",cmake)
        self.assertIn("option(COHOST_OBS_API",cmake)
        source=(HERE/"main.cc").read_text()
        self.assertIn("maddb_obs_put",source)
        self.assertIn("queue.enqueue_state(event.state)",source)
        self.assertIn("maddb_obs_report_result(&port,MADDB_OBS_REMOVE,removed)==MADOBS_EMITTED",source)
        for forbidden in ("madobs/private.h","madobs/runtime.h","madobs_private_open","argv[2]"):
            self.assertNotIn(forbidden,source)

if __name__=="__main__": unittest.main()
