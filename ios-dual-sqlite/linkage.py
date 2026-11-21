"""Bounded little-endian Mach-O validation for the isolated simulator acceptance."""
from pathlib import Path
import hashlib
import plistlib
import struct

MAX_BINARY = 64 * 1024 * 1024
MADDB_DYLIB = "@rpath/MadDB.framework/MadDB"
DYLIB_LOADS = {0xC, 0x20, 0x80000018, 0x8000001F, 0x80000023}

def require(condition):
    if not condition:
        raise ValueError("invalid app linkage")

def command_string(command, minimum):
    offset, = struct.unpack_from("<I", command, 8)
    require(minimum <= offset < len(command))
    raw, delim, _ = command[offset:].partition(b"\0")
    require(raw and delim)
    return raw.decode("ascii")

def binary_metadata(data, filetype):
    require(32 <= len(data) <= MAX_BINARY)
    magic, cpu, subtype, kind, count, size, _, _ = struct.unpack_from("<8I", data)
    require((magic, cpu, subtype & 0xffffff, kind) == (0xFEEDFACF, 0x0100000C, 0, filetype))
    require(count <= 1024 and size <= 1024 * 1024 and 32 + size <= len(data))
    pos, end = 32, 32 + size
    ids, loads, platforms, uuids, rpaths = [], [], [], [], []
    sections = {}
    for _ in range(count):
        require(pos + 8 <= end)
        code, width = struct.unpack_from("<II", data, pos)
        require(8 <= width <= end - pos and width % 8 == 0)
        command = data[pos:pos+width]
        if code in DYLIB_LOADS or code == 0xD:
            require(width >= 24)
            name = command_string(command, 24)
            (ids if code == 0xD else loads).append((code, name))
        elif code == 0x8000001C:
            require(width >= 16)
            rpaths.append(command_string(command, 12))
        elif code == 0x1B:
            require(width == 24)
            uuids.append(command[8:])
        elif code == 0x32:
            require(width >= 24)
            platforms.append(struct.unpack_from("<I", command, 8)[0])
        elif code == 0x19:
            require(width >= 72)
            nsects, = struct.unpack_from("<I", command, 64)
            require(nsects <= 128 and width == 72 + 80 * nsects)
            for i in range(nsects):
                start = 72 + 80 * i
                name, segment, _, length, offset, _, _, _, flags = struct.unpack_from(
                    "<16s16sQQIIIII", command, start)
                if filetype != 6 or not flags & 0x80000400 or length == 0:
                    continue
                require(segment == command[8:24] and bool(name.rstrip(b"\0")))
                # Only actual on-disk executable sections; never code-signature data.
                require(flags & 0xff not in (1, 12, 18) and end <= offset <= len(data) - length)
                identity = (segment.rstrip(b"\0"), name.rstrip(b"\0"))
                require(identity not in sections)
                sections[identity] = (length, hashlib.sha256(data[offset:offset+length]).digest())
        pos += width
    require(pos == end and platforms == [7] and len(uuids) == 1 and any(uuids[0]))
    if filetype == 2:
        require(not ids and [(code, name) for code, name in loads if "maddb" in name.lower()]
                == [(0xC, MADDB_DYLIB)])
        require(rpaths.count("@executable_path/Frameworks") == 1)
        require(all(path in ("@executable_path/Frameworks", "/usr/lib/swift") for path in rpaths))
    else:
        require(ids == [(0xD, MADDB_DYLIB)] and (b"__TEXT", b"__text") in sections)
    return uuids[0], sections

def regular_binary(path):
    require(path.is_file() and path.resolve(strict=True) == path and path.stat().st_size <= MAX_BINARY)
    return path.read_bytes()

def packaged_identity(package):
    entries = plistlib.loads((package / "Info.plist").read_bytes())["AvailableLibraries"]
    sims = [entry for entry in entries if entry.get("SupportedPlatformVariant") == "simulator"]
    require(len(sims) == 1)
    sim = sims[0]
    require(sim.get("SupportedPlatform") == "ios" and sim.get("SupportedArchitectures") == ["arm64"])
    require(sim.get("LibraryIdentifier") == "ios-arm64-simulator" and
            sim.get("LibraryPath") == "MadDB.framework")
    return binary_metadata(regular_binary(package / "ios-arm64-simulator/MadDB.framework/MadDB"), 6)

def verify_app(app, expected):
    binary_metadata(regular_binary(app / "MadDBSmoke"), 2)
    require(binary_metadata(regular_binary(app / "Frameworks/MadDB.framework/MadDB"), 6) == expected)
