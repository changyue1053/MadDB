#!/usr/bin/env python3
"""Inspect actual AAR/APK ELF bytes. This cannot establish device compatibility."""
import pathlib
import struct
import sys
import zipfile


def check_elf(data, name):
    if len(data) < 64 or data[:6] != b'\x7fELF\x02\x01':
        raise ValueError(f'{name}: requires little-endian ELF64')
    if struct.unpack_from('<HH', data, 16) != (3, 183):
        raise ValueError(f'{name}: requires AArch64 shared library')
    phoff = struct.unpack_from('<Q', data, 32)[0]
    entsize, count = struct.unpack_from('<HH', data, 54)
    if entsize != 56 or count == 0 or phoff + entsize * count > len(data):
        raise ValueError(f'{name}: invalid program headers')
    loads = 0
    for index in range(count):
        start = phoff + index * entsize
        kind = struct.unpack_from('<I', data, start)[0]
        if kind != 1:
            continue
        offset, vaddr = struct.unpack_from('<QQ', data, start + 8)
        alignment = struct.unpack_from('<Q', data, start + 48)[0]
        if alignment < 16384 or alignment & (alignment - 1) or (offset - vaddr) % 16384:
            raise ValueError(f'{name}: LOAD segment is not 16 KiB aligned')
        loads += 1
    if not loads:
        raise ValueError(f'{name}: no LOAD segments')


def inspect(path, prefix):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP entries')
        libraries = {name for name in names if name.endswith('.so')}
        expected = {f'{prefix}/arm64-v8a/libmaddb.so', f'{prefix}/arm64-v8a/libmaddb_jni.so'}
        if libraries != expected:
            raise ValueError(f'Wrong ABI/library set: {libraries}')
        for name in sorted(expected):
            if prefix == 'lib' and archive.getinfo(name).compress_type != zipfile.ZIP_STORED:
                raise ValueError(f'{name}: APK native library must be stored uncompressed')
            check_elf(archive.read(name), name)
        if not any(name.endswith('maddb-notices/LICENSE') for name in names):
            raise ValueError('Missing bundled first-party notice')
        print(f'{path.name}: exact ARM64 library set and ELF 16 KiB LOAD alignment pass')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: inspect-android-package.py library.aar smoke.apk')
    inspect(pathlib.Path(sys.argv[1]), 'jni')
    inspect(pathlib.Path(sys.argv[2]), 'lib')
