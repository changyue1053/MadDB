#!/usr/bin/env python3
"""Packaging inspection only. Does not execute Swift, Rust or iOS."""
import plistlib
import re
from pathlib import Path
import struct
import subprocess
import sys


def inspect_macho(data, expected_platform):
    if len(data) < 32:
        raise ValueError('truncated Mach-O header')
    magic, cpu, subtype, filetype, count, size, _, _ = struct.unpack_from('<8I', data)
    if (magic, cpu, subtype, filetype) != (0xFEEDFACF, 0x0100000C, 0, 6):
        raise ValueError('requires thin arm64 MH_DYLIB')
    if 32 + size > len(data):
        raise ValueError('truncated Mach-O commands')
    offset, platforms, install_names = 32, [], []
    for _ in range(count):
        if offset + 8 > 32 + size:
            raise ValueError('truncated command')
        cmd, length = struct.unpack_from('<2I', data, offset)
        if length < 8 or offset + length > 32 + size:
            raise ValueError('invalid command length')
        if cmd == 0x32:  # LC_BUILD_VERSION
            if length < 24:
                raise ValueError('truncated build version')
            platform, minimum = struct.unpack_from('<2I', data, offset + 8)
            if minimum != 15 << 16:
                raise ValueError('unexpected minimum iOS deployment version')
            platforms.append(platform)
        if cmd in (0xD, 0xC, 0x80000018, 0x8000001F):
            if length < 24:
                raise ValueError('truncated dylib command')
            start = struct.unpack_from('<I', data, offset + 8)[0]
            if not 24 <= start < length:
                raise ValueError('invalid dylib name offset')
            raw = data[offset + start:offset + length]
            if b'\0' not in raw:
                raise ValueError('unterminated dylib name')
            name = raw.split(b'\0')[0].decode('utf-8')
            if cmd == 0xD:
                install_names.append(name)
            elif not (name.startswith(('/usr/lib/', '/System/Library/')) or
                      re.fullmatch(r'@rpath/libswift[A-Za-z0-9_]+\.dylib', name)):
                raise ValueError(f'non-system dynamic dependency: {name}')
        offset += length
    if offset != 32 + size or platforms != [expected_platform]:
        raise ValueError('wrong or missing Mach-O platform')
    if install_names != ['@rpath/MadDB.framework/MadDB']:
        raise ValueError('wrong framework install name')


def inspect_framework_plist(info, variant):
    sdk = 'iphonesimulator' if variant == 'simulator' else 'iphoneos'
    expected = dict(CFBundleIdentifier='io.maddb.sdk', CFBundleExecutable='MadDB',
                    CFBundlePackageType='FMWK', CFBundleInfoDictionaryVersion='6.0',
                    DTPlatformName=sdk, DTPlatformVersion='26.2',
                    DTSDKName=sdk + '26.2', DTXcode='2620', DTXcodeBuild='17C52',
                    MinimumOSVersion='15.0', CFBundleSupportedPlatforms=[
                        'iPhoneSimulator' if variant == 'simulator' else 'iPhoneOS'])
    for key, value in expected.items():
        if info.get(key) != value:
            raise ValueError(f'missing or mismatched framework metadata: {key}')
    if not isinstance(info.get('DTSDKBuild'), str) or not info['DTSDKBuild']:
        raise ValueError('missing SDK build provenance')


def inspect(root):
    info = plistlib.loads((root / 'Info.plist').read_bytes())
    libraries = info['AvailableLibraries']
    if len(libraries) != 2:
        raise ValueError('requires exactly two XCFramework slices')
    seen = set()
    for lib in libraries:
        variant = lib.get('SupportedPlatformVariant', '')
        if lib['SupportedPlatform'] != 'ios' or variant not in ('', 'simulator'):
            raise ValueError('unsupported platform/variant')
        if variant in seen or lib['SupportedArchitectures'] != ['arm64']:
            raise ValueError('duplicate variant or unexpected architecture')
        seen.add(variant)
        framework = root / lib['LibraryIdentifier'] / lib['LibraryPath']
        if framework.name != 'MadDB.framework':
            raise ValueError('wrong framework name')
        inspect_framework_plist(plistlib.loads((framework / 'Info.plist').read_bytes()), variant)
        inspect_macho((framework / 'MadDB').read_bytes(), 7 if variant else 2)
        module = 'arm64-apple-ios' + ('-simulator' if variant else '')
        interface = (framework / 'Modules/MadDB.swiftmodule' / (module + '.swiftinterface')).read_text()
        if 'CMadDB' in interface:
            raise ValueError('private C module leaked into public Swift interface')
        for required in ['LICENSE', 'THIRD_PARTY_NOTICES.md', 'DEPENDENCIES.md', 'third-party/provenance.json']:
            if not (framework / 'Resources/Notices' / required).is_file():
                raise ValueError(f'missing notice: {required}')
        # Hidden static archive symbols must not become the framework ABI.
        symbols = subprocess.check_output(['xcrun', 'nm', '-gjU', str(framework / 'MadDB')], text=True)
        if any(line.startswith(('_sqlite3_', '_maddb_')) for line in symbols.splitlines()):
            raise ValueError('private SQLite/C ABI symbol exported')
    print('PASS: two arm64 Mach-O platform slices, Swift interfaces, notices, hidden native symbols (not runtime)')


if __name__ == '__main__':
    inspect(Path(sys.argv[1]))
