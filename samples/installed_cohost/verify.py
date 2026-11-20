"""Build a Linux cohost using only pinned, relocated and independently installed SDKs."""
import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import signal
import subprocess
import tarfile
import tempfile


DB_TREE = "48e5337ad19060fa10ced5bd92896c2f76d1eb5a"
LINK_COMMIT = "a6d869efd8a5b3f2eb1f31e9b5c1a37392251867"
LINK_TREE = "e6ee8b6ef2c8f8bfd30e5ac90ae05d7811a12350"
OBS_COMMIT = "79fd8ced44a18bca574598ff683cd706ded16a60"
OBS_TREE = "fa87aed52ec6d748addacb2f8d57ac30e5976271"


class Failure(Exception):
    pass


def check(condition, label):
    if not condition:
        raise Failure(label)


def command(args, *, cwd, env, label, capture=False, timeout=180):
    with subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE if capture is True else capture or subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, start_new_session=True) as p:
        try:
            out, _ = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.wait(timeout=10)
            raise Failure(label) from None
        check(p.returncode == 0, label)
        return out.decode("utf-8") if out is not None else None


def safe_archive(source, target):
    with tarfile.open(source, "r:") as tar:
        members = tar.getmembers()
        check(len(members) <= 20000 and sum(m.size for m in members) <= 128 * 1024 * 1024, "source-size")
        seen = set()
        for m in members:
            name = PurePosixPath(m.name)
            check(not name.is_absolute() and not (".." in name.parts) and
                  (m.isdir() or m.isreg()) and name not in seen, "source-inventory")
            seen.add(name)
        tar.extractall(target, members=members, filter="data")


def stage_git(repo, ref, expected, target, env):
    rev = command(["git", "rev-parse", "--verify", ref + "^{commit}"],
                  cwd=repo, env=env, label="source-revision", capture=True).strip()
    check(re.fullmatch("[0-9a-f]{40}", rev) is not None, "source-revision-format")
    tree = command(["git", "rev-parse", "--verify", rev + "^{tree}"],
                   cwd=repo, env=env, label="source-tree", capture=True).strip()
    check(tree == expected, "source-tree-mismatch")
    target.mkdir()
    archive = target.with_suffix(".tar")
    with archive.open("wb") as out:
        command(["git", "archive", "--format=tar", rev],
                cwd=repo, env=env, label="source-archive", capture=out)
    safe_archive(archive, target)
    archive.unlink()


def digest_packages(prefixes):
    result = {}
    for root in prefixes:
        for p in sorted(root.rglob("*")):
            check(not p.is_symlink(), "package-symlink")
            if not p.is_dir():
                check(p.is_file(), "package-entry-type")
                with p.open("rb") as f:
                    result[p] = hashlib.file_digest(f, "sha256").digest()
    return result


def check_link(link_text, core, obs):
    tokens = shlex.split(link_text)
    check(tokens.count(str(core)) == 1, "link-archive-operand")
    if obs is None:
        check(not any("madobs" in t.lower() for t in tokens), "off-obs-link")
    else:
        check(tokens.count(str(obs)) == 1, "on-obs-archive-operand")


def check_loader(text, lib, on=False):
    lines = [line.strip() for line in text.splitlines()]
    pattern = r"libmaddb\.so => (.*) \(0x[0-9a-fA-F]+\)"
    matches = [re.fullmatch(pattern, entry) for entry in lines if "libmaddb.so" in entry]
    check(len(matches) == 1 and matches[0] and Path(matches[0].group(1)) == lib, "db-loader-selection")
    allowed = {"libmaddb.so", "libstdc++.so.6", "libgcc_s.so.1", "libc.so.6",
               "libm.so.6", "libpthread.so.0", "libdl.so.2", "librt.so.1",
               "linux-vdso.so.1", "ld-linux-x86-64.so.2"}
    if on:
        allowed.add("libz.so.1")
    names = []
    for line in lines:
        check("not found" not in line and re.search(r" \(0x[0-9a-fA-F]+\)$", line), "loader-closure")
        name = Path(line.split()[0]).name
        check(name in allowed and name not in names, "loader-closure")
        names.append(name)
    check(("libz.so.1" in names) == on, "loader-zlib-mode")


def verify(args):
    src = Path(__file__).resolve().parent
    root = src.parents[1]
    env = {k: os.environ[k] for k in ("PATH", "HOME", "CARGO_HOME", "RUSTUP_HOME") if k in os.environ}
    env.update(LC_ALL="C", RUSTUP_TOOLCHAIN="1.100.0", CARGO_NET_OFFLINE="true",
               GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null")
    os.umask(0o077)
    required = ("git", "cmake", "gcc", "g++", "make", "ar", "cargo", "ldd", "nm", "readelf")
    check(all(shutil.which(name) for name in required), "existing-toolchain")
    on = args.obs_repo is not None
    options = ["-G", "Unix Makefiles", "-DCMAKE_BUILD_TYPE=Release",
               "-DCMAKE_C_COMPILER=gcc", "-DCMAKE_CXX_COMPILER=g++"]
    with tempfile.TemporaryDirectory(prefix="mad-cohost-") as temp:
        work = Path(temp).resolve()
        source = work / "removed producers"
        source.mkdir()
        dbsrc, linksrc, obssrc = (source / kind for kind in ("db", "link", "obs"))
        stage_git(root, args.db_ref, DB_TREE, dbsrc, env)
        stage_git(args.link_repo, args.link_ref, LINK_TREE, linksrc, env)
        if on:
            stage_git(args.obs_repo, args.obs_ref, OBS_TREE, obssrc, env)
        app = work / "application"
        app.mkdir()
        for name in ("main.cc", "CMakeLists.txt"):
            shutil.copyfile(src / name, app / name)
        db = work / "relocated DB"
        link = work / "relocated Link"
        obs = work / "relocated observation" if on else None
        db_install, link_install = source / "db install", source / "link install"
        command(["bash", "scripts/install-linux-c-sdk.sh", db_install],
                cwd=dbsrc, env=env, label="db-install")
        command(["sh", "packaging/install-core.sh", link_install, source / "link objects"],
                cwd=linksrc, env=env, label="link-install")
        shutil.move(db_install, db)
        shutil.move(link_install, link)
        if on:
            adapters = app / "adapters"
            adapters.mkdir()
            shutil.copyfile(dbsrc / "adapters/obs/maddb_obs.h", adapters / "maddb_obs.h")
            shutil.copyfile(linksrc / "optional/madobs/queued_observer.hpp", adapters / "queued_observer.hpp")
            obs_build, obs_install = source / "obs build", source / "obs install"
            command(["cmake", "-S", obssrc, "-B", obs_build, *options, "-DBUILD_TESTING=OFF",
                     "-DMADOBS_BUILD_RUNTIME=ON", "-DMADOBS_BUILD_SHARED=OFF", "-DMADOBS_BUILD_JNI=OFF",
                     "-DMADOBS_PACKAGE_BORINGSSL=OFF", "-DIMOBS_BORINGSSL_ROOT=",
                     "-DIMOBS_BORINGSSL_INCLUDE=", "-DIMOBS_BORINGSSL_CRYPTO_LIB="],
                    cwd=work, env=env, label="obs-configure")
            command(["cmake", "--build", obs_build, "--parallel", "2"],
                    cwd=work, env=env, label="obs-build")
            command(["cmake", "--install", obs_build, "--prefix", obs_install],
                    cwd=work, env=env, label="obs-install")
            shutil.move(obs_install, obs)
        shutil.rmtree(source)
        check(not source.exists(), "producer-removal")
        packages = (db, link, obs) if on else (db, link)
        before = digest_packages(packages)
        db_lib, link_archive = db / "lib/libmaddb.so", link / "lib/libmadlink.a"
        obs_archive = obs / "lib/libmadobs_runtime.a" if on else None
        check(all(p in before for p in (db_lib, link_archive) + ((obs_archive,) if on else ())), "package-inputs")
        build = work / "consumer build"
        flags = ["-DCMAKE_EXPORT_COMPILE_COMMANDS=ON", "-DCOHOST_OBS=" + ("ON" if on else "OFF"),
                 "-DDB_PREFIX=" + str(db), "-DMadDB_DIR=" + str(db / "lib/cmake/MadDB"),
                 "-DLINK_PREFIX=" + str(link)]
        if on:
            flags += ["-DOBS_PREFIX=" + str(obs), "-DMadObs_DIR=" + str(obs / "lib/cmake/MadObs")]
        command(["cmake", "-S", app, "-B", build, *options, *flags], cwd=work, env=env, label="consumer-configure")
        check((build / "core-paths").read_text().splitlines() == [str(db_lib), str(link_archive)], "consumer-core-paths")
        if on:
            check((build / "obs-path").read_text() == str(obs_archive), "consumer-obs-path")
        else:
            check(not (build / "obs-path").exists() and not (app / "adapters").exists(), "off-package-absent")
        command(["cmake", "--build", build, "--parallel", "2"], cwd=work, env=env, label="consumer-build")
        link_text = (build / "CMakeFiles/cohost.dir/link.txt").read_text()
        compile_text = (build / "compile_commands.json").read_text()
        check(all(str(p) not in link_text and str(p) not in compile_text for p in (source, root)),
              "consumer-producer-fallback")
        check_link(link_text, link_archive, obs_archive)
        exe = build / "cohost"
        loader = command(["ldd", exe], cwd=work, env=env, label="consumer-loader", capture=True)
        check_loader(loader, db_lib, on)
        needed = command(["readelf", "-d", exe], cwd=work, env=env, label="consumer-needed", capture=True)
        check(needed.count("[libmaddb.so]") == 1 and str(db_lib) not in needed, "consumer-needed-by-name")
        symbols = command(["nm", "--defined-only", exe], cwd=work, env=env, label="consumer-symbols", capture=True)
        check(" T ml_create_tracked_v1\n" in symbols, "linked-tracked-core")
        observed = " T madobs_private_open_ex\n" in symbols and " T madobs_private_emit\n" in symbols
        check(observed if on else not re.search(r"\bmadobs_\w+", symbols), "obs-symbol-mode")
        sandbox = work / "fixture app private"
        sandbox.mkdir()
        argv = [exe, sandbox / "store.sqlite"]
        if on:
            argv.append(sandbox / "telemetry")
        result = command(argv, cwd=sandbox, env=env, label="cohost-runtime", capture=True, timeout=30)
        check(result == "PASS: installed cohost synthetic operations\n", "cohost-runtime-result")
        check(before == digest_packages(packages), "package-bytes-changed")
        if not on:
            check(not (sandbox / "telemetry").exists(), "off-storage-absent")
    print("PASS: installed Linux cohost " + ("ON" if on else "OFF"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-ref", default="HEAD^")
    parser.add_argument("--link-repo", type=Path, required=True)
    parser.add_argument("--link-ref", default=LINK_COMMIT)
    parser.add_argument("--obs-repo", type=Path)
    parser.add_argument("--obs-ref", default=OBS_COMMIT)
    verify(parser.parse_args())


if __name__ == "__main__":
    try:
        main()
    except Failure as err:
        raise SystemExit("FAIL: " + str(err)) from None
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError):
        raise SystemExit("FAIL: cohost infrastructure") from None
