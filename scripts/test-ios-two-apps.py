#!/usr/bin/env python3
"""Job-owned simulator only. Raw system output is not published."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from ios_two_apps_linkage import packaged_identity, verify_app

ROOT = Path(__file__).resolve().parents[1]
IDS = ("org.example.maddb.acceptance.a", "org.example.maddb.acceptance.b")
VALUES = ([0, 65, 255, 17], [0, 66, 255, 29])
RUNTIME = "com.apple.CoreSimulator.SimRuntime.iOS-26-2"
DEVICE = "com.apple.CoreSimulator.SimDeviceType.iPhone-16"

def require(condition):
    if not condition:
        raise RuntimeError("acceptance check failed")

def run(*args, timeout=120):
    return subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True, text=True, timeout=timeout).stdout.strip()

def sim(*args, **kwargs):
    return run("xcrun", "simctl", *args, **kwargs)

def manifest(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).digest()
            for p in root.rglob("*") if p.is_file()}

def owned_container(path, simulator):
    resolved = Path(path).resolve(strict=True)
    base = (Path.home() / "Library/Developer/CoreSimulator/Devices" / simulator /
            "data/Containers/Data/Application").resolve(strict=True)
    require(resolved.parent == base and uuid.UUID(resolved.name))
    return resolved

def evidence(path, bundle, nonce, phase, pid, sentinel):
    require(not path.is_symlink() and path.is_file() and path.stat().st_size < 2048)
    row = json.loads(path.read_text())
    require(isinstance(row, dict) and type(row.get("pid")) is int)
    require(isinstance(row.get("value"), list) and all(type(v) is int for v in row["value"]))
    require(row == {"bundle": bundle, "nonce": nonce, "phase": phase,
                    "pid": pid, "value": sentinel})

def observe(container, bundle, nonce, phase, pid, sentinel):
    support = container / "Library/Application Support/MadDBTwoApps"
    result = support / f"result-{nonce}-{phase}.json"
    for _ in range(80):
        if result.exists():
            require(support.resolve(strict=True) == support)
            evidence(result, bundle, nonce, phase, pid, sentinel)
            store = support / "store.sqlite"
            require(not store.is_symlink() and store.is_file())
            return
        time.sleep(0.25)
    raise RuntimeError("fresh evidence absent")

def acceptance():
    stage = "apple-preflight"
    simulator = None
    try:
        os.environ["DEVELOPER_DIR"] = "/Applications/Xcode_26.2.app/Contents/Developer"
        require(run("uname", "-m") == "arm64")
        require(run("xcodebuild", "-version") == "Xcode 26.2\nBuild version 17C52")
        available = json.loads(sim("list", "runtimes", "available", "-j"))["runtimes"]
        require(any(item["identifier"] == RUNTIME and item["isAvailable"] for item in available))
        stage = "owned-simulator"
        created = sim("create", "MadDB-two-apps-" + str(uuid.uuid4()), DEVICE, RUNTIME)
        require(str(uuid.UUID(created)).lower() == created.lower())
        simulator = created
        sim("boot", simulator)
        sim("bootstatus", simulator, "-b", timeout=180)
        with tempfile.TemporaryDirectory(prefix="maddb-two-apps-") as temporary:
            stage = "relocate-sdk"
            work = Path(temporary).resolve(strict=True)
            project = work / "ios/Smoke"
            package = ROOT / "build/ios/MadDB.xcframework"
            relocated = work / "build/ios/MadDB.xcframework"
            shutil.copytree(ROOT / "ios/Smoke", project)
            shutil.copytree(package, relocated, symlinks=True)
            original = manifest(package)
            require(original and manifest(relocated) == original)
            expected_binary = packaged_identity(relocated)
            containers = []
            for index, bundle in enumerate(IDS):
                stage = ("build-app-a", "build-app-b")[index]
                products = work / ("products-" + str(index))
                run("xcodebuild", "-project", str(project / "MadDBSmoke.xcodeproj"),
                    "-scheme", "MadDBSmoke", "-configuration", "Release",
                    "-destination", "platform=iOS Simulator,id=" + simulator,
                    "-derivedDataPath", str(work / ("derived-" + str(index))),
                    "CONFIGURATION_BUILD_DIR=" + str(products),
                    "PRODUCT_BUNDLE_IDENTIFIER=" + bundle, "ARCHS=arm64", "ONLY_ACTIVE_ARCH=YES",
                    "CODE_SIGNING_ALLOWED=YES", "CODE_SIGN_IDENTITY=-", "CODE_SIGNING_REQUIRED=NO",
                    "build", timeout=300)
                app = products / "MadDBSmoke.app"
                require(plistlib.loads((app / "Info.plist").read_bytes())["CFBundleIdentifier"] == bundle)
                require(run("xcrun", "lipo", "-archs", str(app / "MadDBSmoke")) == "arm64")
                require(manifest(relocated) == original)
                stage = ("linkage-app-a", "linkage-app-b")[index]
                verify_app(app, expected_binary)
                print("PASS: " + stage + " packaged simulator binary identity", flush=True)
                stage = ("install-app-a", "install-app-b")[index]
                sim("install", simulator, str(app))
                containers.append(owned_container(sim("get_app_container", simulator, bundle, "data"), simulator))
            stage = "distinct-owned-containers"
            require(containers[0] != containers[1])
            print("PASS: distinct owned application data containers", flush=True)
            nonce = str(uuid.uuid4())
            writers = []
            for phase in ("write", "read"):
                pids = []
                for index, bundle in enumerate(IDS):
                    stage = phase + ("-app-a", "-app-b")[index]
                    output = sim("launch", simulator, bundle, "--maddb-two-apps", nonce, phase)
                    match = re.fullmatch(re.escape(bundle) + r": ([1-9][0-9]*)", output)
                    require(match)
                    pid = int(match[1])
                    require(pid not in pids and (phase == "write" or pid not in writers))
                    pids.append(pid)
                    observe(containers[index], bundle, nonce, phase, pid, VALUES[index])
                    print("PASS: " + stage + " exact synthetic sentinel", flush=True)
                for index, bundle in enumerate(IDS):
                    stage = "terminate-" + phase + ("-app-a", "-app-b")[index]
                    sim("terminate", simulator, bundle)
                if phase == "write":
                    writers = pids
    except Exception:
        print("FAIL: " + stage, file=sys.stderr)
        return 1
    finally:
        if simulator is not None:
            try:
                sim("shutdown", simulator)
            except (OSError, subprocess.SubprocessError):
                pass
            try:
                sim("delete", simulator)
            except (OSError, subprocess.SubprocessError):
                print("FAIL: owned-simulator-cleanup", file=sys.stderr)
                return 1
    print("PASS: two ARM64 simulator apps reopened independent stores", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(acceptance())
