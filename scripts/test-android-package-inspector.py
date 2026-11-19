#!/usr/bin/env python3
"""Synthetic ZIP/ELF format regressions only, NOT Android build/runtime proof."""
import contextlib
import importlib.util
import io
import pathlib
import struct
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location(
    'inspector', pathlib.Path(__file__).with_name('inspect-android-package.py'))
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


def minimal_elf():
    # Minimal synthetic program header sufficient for the format inspector.
    # It is deliberately not an executable shared library.
    data = bytearray(120)
    data[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<HH', data, 16, 3, 183)
    struct.pack_into('<Q', data, 32, 64)
    struct.pack_into('<HH', data, 54, 56, 1)
    struct.pack_into('<I', data, 64, 1)
    struct.pack_into('<Q', data, 112, 16384)
    return data


class PackageInspectorTests(unittest.TestCase):
    def inspect_fixture(self, prefix, compression):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'synthetic.zip'
            with zipfile.ZipFile(path, 'w', compression=compression) as archive:
                for library in ['libmaddb.so', 'libmaddb_jni.so']:
                    archive.writestr(f'{prefix}/arm64-v8a/{library}', minimal_elf())
                archive.writestr('assets/maddb-notices/LICENSE', 'fixture')
            with contextlib.redirect_stdout(io.StringIO()):
                inspector.inspect(path, prefix)

    def test_apk_stored_native_libraries_accepted(self):
        self.inspect_fixture('lib', zipfile.ZIP_STORED)

    def test_apk_compressed_native_libraries_rejected(self):
        with self.assertRaisesRegex(ValueError, 'must be stored uncompressed'):
            self.inspect_fixture('lib', zipfile.ZIP_DEFLATED)

    def test_aar_compressed_native_libraries_remain_allowed(self):
        self.inspect_fixture('jni', zipfile.ZIP_DEFLATED)


if __name__ == '__main__':
    unittest.main()
