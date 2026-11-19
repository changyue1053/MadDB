#!/usr/bin/env python3
"""Synthetic format regressions, never runtime evidence."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('inspector', Path(__file__).with_name('inspect-ios-package.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(platform=2, cpu=0x0100000C):
    name = b'@rpath/MadDB.framework/MadDB\0'
    name += b'\0' * (-len(name) % 8)
    commands = struct.pack('<6I', 0x32, 24, platform, 15 << 16, 26 << 16, 0)
    commands += struct.pack('<6I', 0xD, 24 + len(name), 24, 0, 0, 0) + name
    return struct.pack('<8I', 0xFEEDFACF, cpu, 0, 6, 2, len(commands), 0, 0) + commands


class InspectionTests(unittest.TestCase):
    def test_device_and_simulator(self):
        module.inspect_macho(fixture(), 2)
        module.inspect_macho(fixture(7), 7)

    def test_wrong_variant(self):
        with self.assertRaises(ValueError):
            module.inspect_macho(fixture(), 7)

    def test_wrong_architecture(self):
        with self.assertRaises(ValueError):
            module.inspect_macho(fixture(cpu=0x01000007), 2)

    def test_truncation(self):
        with self.assertRaises(ValueError):
            module.inspect_macho(fixture()[:-1], 2)


class FrameworkMetadataTests(unittest.TestCase):
    def fixture(self, variant=''):
        sdk = 'iphonesimulator' if variant else 'iphoneos'
        return dict(CFBundleIdentifier='io.maddb.sdk', CFBundleExecutable='MadDB',
                    CFBundlePackageType='FMWK', CFBundleInfoDictionaryVersion='6.0',
                    DTPlatformName=sdk, DTPlatformVersion='26.2',
                    DTSDKName=sdk + '26.2', DTSDKBuild='synthetic-build',
                    DTXcode='2620', DTXcodeBuild='17C52', MinimumOSVersion='15.0',
                    CFBundleSupportedPlatforms=['iPhoneSimulator' if variant else 'iPhoneOS'])

    def test_both_variants(self):
        for variant in ('', 'simulator'):
            module.inspect_framework_plist(self.fixture(variant), variant)

    def test_required_metadata_is_not_optional(self):
        for key in ('CFBundleInfoDictionaryVersion', 'DTPlatformName', 'DTSDKName', 'DTSDKBuild'):
            info = self.fixture()
            del info[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.inspect_framework_plist(info, '')

    def test_device_metadata_rejected_for_simulator(self):
        with self.assertRaises(ValueError):
            module.inspect_framework_plist(self.fixture(), 'simulator')


if __name__ == '__main__':
    unittest.main()
