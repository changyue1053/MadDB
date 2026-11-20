"""Portable negative contract tests, no SDK builds, downloads or device access."""
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("verify", Path(__file__).with_name("verify.py"))
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class Guards(unittest.TestCase):
    def test_archive_regular_source_and_unsafe_members(self):
        for name, kind in (("valid/header", tarfile.REGTYPE), ("../escape", tarfile.REGTYPE),
                           ("/absolute", tarfile.REGTYPE), ("symlink", tarfile.SYMTYPE)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as base:
                path = Path(base)
                extract = path / "stage"
                extract.mkdir()
                with tarfile.open(path / "x.tar", "w") as dst:
                    info = tarfile.TarInfo(name)
                    info.type = kind
                    if kind == tarfile.REGTYPE:
                        info.size = 1
                        dst.addfile(info, io.BytesIO(b"a"))
                    else:
                        info.linkname = "valid/header"
                        dst.addfile(info)
                if name == "valid/header":
                    verify.safe_archive(path / "x.tar", extract)
                    self.assertEqual((extract / name).read_bytes(), b"a")
                else:
                    with self.assertRaises(verify.Failure):
                        verify.safe_archive(path / "x.tar", extract)
                    self.assertFalse(list(extract.iterdir()))

    def test_link_requires_exact_archives_and_off_absence(self):
        core, obs = Path("/relocated Link/libmadlink.a"), Path("/relocated Obs/libmadobs_runtime.a")
        good = 'g++ main.o "/relocated Link/libmadlink.a"'
        verify.check_link(good, core, None)
        verify.check_link(good + ' "/relocated Obs/libmadobs_runtime.a"', core, obs)
        for command, opt in ((good + " -lmadobs_runtime", None), (good, obs),
                             (good.replace("/relocated Link", "/producer"), None),
                             (good + ' "/relocated Link/libmadlink.a"', None)):
            with self.assertRaises(verify.Failure):
                verify.check_link(command, core, opt)

    def test_loader_staged_by_name_and_fail_closed(self):
        lib = Path("/relocated DB/lib/libmaddb.so")
        valid = "\tlibmaddb.so => /relocated DB/lib/libmaddb.so (0x1234)\n"
        verify.check_loader(valid, lib)
        zlib = "libz.so.1 => /system/libz.so.1 (0x5)"
        verify.check_loader(valid + zlib, lib, on=True)
        with self.assertRaises(verify.Failure):
            verify.check_loader(valid, lib, on=True)
        for invalid in (valid.replace("relocated", "producer"),
                        "/relocated DB/lib/libmaddb.so (0x1234)",
                        valid + valid, valid + zlib, valid + "libcurl.so.4 => /system/libcurl.so.4 (0x5)",
                        valid + "libX.so.1 => not found"):
            with self.assertRaises(verify.Failure):
                verify.check_loader(invalid, lib)

    def test_inventory_digest_changed_or_unsafe(self):
        with tempfile.TemporaryDirectory() as base:
            root = Path(base)
            p = root / "archive"
            p.write_bytes(b"one")
            before = verify.digest_packages((root,))
            p.write_bytes(b"two")
            self.assertNotEqual(verify.digest_packages((root,)), before)
            (root / "link").symlink_to(p)
            with self.assertRaises(verify.Failure):
                verify.digest_packages((root,))


if __name__ == "__main__":
    unittest.main()
