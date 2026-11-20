"""Pinned installed Linux cohost, with MadObs API only and no runtime fallback."""
import argparse
import importlib.util
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location("approved_cohost_helpers",HERE.parent/"installed_cohost/verify.py")
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
DB_COMMIT="88d78e03d4ba0ec0aeee80ecd2c22cff759bb8fe"
DB_TREE="dbfdd0bd2bffa396ae87d69e980c2407c25100f5"
API_ONLY_FILES=frozenset((
    "include/madobs/observer.h", "include/madobs/privacy.h",
    "lib/cmake/MadObs/MadObsApiTargets.cmake", "lib/cmake/MadObs/MadObsConfig.cmake",
    "lib/cmake/MadObs/MadObsConfigVersion.cmake",
))

def check_inventory(prefix):
    base.check({p.relative_to(prefix).as_posix() for p in prefix.rglob("*")
                if not p.is_dir() or p.is_symlink()}==API_ONLY_FILES, "api-only-inventory")

def check_api_link(link_text, link_archive):
    base.check_link(link_text,link_archive,None)
    base.check(not any(arg == "-lz" or re.match(r"^libz\.(?:a|so(?:\..*)?)$",Path(arg).name)
                       for arg in shlex.split(link_text)), "api-only-zlib-link")


def check_symbols(symbols):
    base.check(" T ml_create_tracked_v1\n" in symbols, "linked-tracked-core")
    base.check(not re.search(r"\bmadobs_(?:private_|runtime_|create\b|start\b|stop\b|destroy\b|observer_for_runtime\b|emit_generic_event\b|check_private_batch\b)",symbols),
               "api-only-runtime-symbol")

def verify(args):
    env={k:os.environ[k] for k in ("PATH","HOME","CARGO_HOME","RUSTUP_HOME") if k in os.environ}
    env.update(LC_ALL="C",RUSTUP_TOOLCHAIN="1.100.0",CARGO_NET_OFFLINE="true",
               GIT_CONFIG_NOSYSTEM="1",GIT_CONFIG_GLOBAL="/dev/null",GIT_TERMINAL_PROMPT="0")
    os.umask(0o077)
    tools=("git","cmake","gcc","g++","make","ar","cargo","ldd","nm","readelf")
    base.check(all(shutil.which(t) for t in tools),"existing-toolchain")
    options=["-G","Unix Makefiles","-DCMAKE_BUILD_TYPE=Release","-DCMAKE_C_COMPILER=gcc",
             "-DCMAKE_CXX_COMPILER=g++","-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF",
             "-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF"]
    with tempfile.TemporaryDirectory(prefix="mad-cohost-api-") as tmp:
        work=Path(tmp).resolve()
        def run(cmd,label,cwd=work,**kwargs):
            return base.command(cmd,cwd=cwd,env=env,label=label,**kwargs)
        source=work/"producer sources"
        source.mkdir()
        dbsrc,linksrc,obssrc=(source/name for name in ("db","link","obs"))
        # Local materialization may have a different commit ID but the exact immutable
        # public parent tree. Hosted workflow independently requires the public parent SHA.
        base.stage_git(ROOT,"HEAD^",DB_TREE,dbsrc,env)
        base.stage_git(args.link_repo,base.LINK_COMMIT,base.LINK_TREE,linksrc,env)
        base.stage_git(args.obs_repo,base.OBS_COMMIT,base.OBS_TREE,obssrc,env)
        db,link,obs=(work/name for name in ("relocated DB","relocated Link","relocated API"))
        db_install,link_install,obs_install=(source/name for name in ("db prefix","link prefix","obs prefix"))
        run(["bash","scripts/install-linux-c-sdk.sh",db_install],"db-install",cwd=dbsrc)
        run(["sh","packaging/install-core.sh",link_install,source/"link objects"],"link-install",cwd=linksrc)
        obs_build=source/"obs build"
        run(["cmake","-S",obssrc,"-B",obs_build,*options,"-DBUILD_TESTING=OFF",
             "-DMADOBS_BUILD_RUNTIME=OFF","-DMADOBS_BUILD_SHARED=OFF","-DMADOBS_BUILD_JNI=OFF",
             "-DMADOBS_PACKAGE_BORINGSSL=OFF"],"api-only-configure")
        run(["cmake","--build",obs_build,"--parallel","2"],"api-only-build")
        run(["cmake","--install",obs_build,"--prefix",obs_install],"api-only-install")
        for origin,target in ((db_install,db),(link_install,link),(obs_install,obs)):
            shutil.move(origin,target)
        app=work/"application"
        adapters=app/"adapters"
        adapters.mkdir(parents=True)
        for name in ("main.cc","CMakeLists.txt","collector.hpp","collector_test.cc"):
            shutil.copyfile(HERE/name,app/name)
        shutil.copyfile(dbsrc/"adapters/obs/maddb_obs.h",adapters/"maddb_obs.h")
        shutil.copyfile(linksrc/"optional/madobs/queued_observer.hpp",adapters/"queued_observer.hpp")
        shutil.rmtree(source)
        base.check(not source.exists(),"producer-removal")
        before=base.digest_packages((db,link,obs))
        check_inventory(obs)
        db_lib,link_archive=db/"lib/libmaddb.so",link/"lib/libmadlink.a"
        run(["g++","-std=c++17","-Wall","-Wextra","-Wpedantic","-Werror",
             "-I",db/"include","-I",link/"include","-I",obs/"include","-I",adapters,
             app/"collector_test.cc","-o",work/"collector-probe"],"collector-fixture-build")
        run([work/"collector-probe"],"collector-fixture-run")
        build=work/"consumer build"
        run(["cmake","-S",app,"-B",build,*options,"-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
             "-DCOHOST_OBS_API=ON","-DDB_PREFIX="+str(db),"-DMadDB_DIR="+str(db/"lib/cmake/MadDB"),
             "-DLINK_PREFIX="+str(link),"-DOBS_PREFIX="+str(obs),"-DMadObs_DIR="+str(obs/"lib/cmake/MadObs")],
            "consumer-configure")
        base.check((build/"core-paths").read_text().splitlines()==[str(db_lib),str(link_archive)],"consumer-core-paths")
        base.check((build/"obs-api-path").read_text()==str(obs/"include"),"consumer-api-path")
        run(["cmake","--build",build,"--parallel","2"],"consumer-build")
        link_text=(build/"CMakeFiles/cohost.dir/link.txt").read_text()
        compile_text=(build/"compile_commands.json").read_text()
        base.check(all(str(p) not in link_text and str(p) not in compile_text for p in (source,ROOT)),
                   "consumer-producer-fallback")
        base.check(str(obs/"include") in compile_text,"consumer-api-headers")
        check_api_link(link_text,link_archive)
        exe=build/"cohost"
        base.check_loader(run(["ldd",exe],"consumer-loader",capture=True),db_lib,on=False)
        needed=run(["readelf","-d",exe],"consumer-needed",capture=True)
        base.check(needed.count("[libmaddb.so]")==1 and str(db_lib) not in needed,"consumer-needed-by-name")
        check_symbols(run(["nm","--defined-only",exe],"consumer-symbols",capture=True))
        sandbox=work/"fixture application"
        sandbox.mkdir()
        result=run([exe,sandbox/"store.sqlite"],"api-only-runtime",cwd=sandbox,capture=True,timeout=30)
        base.check(result=="PASS: API-only cohost synthetic operations and exact local 3+3\n","runtime-result")
        base.check({p.name for p in sandbox.iterdir()}=={"store.sqlite"},"api-only-storage")
        base.check(before==base.digest_packages((db,link,obs)),"package-bytes-changed")
    print("PASS: installed Linux API-only cohost, exact local 3+3 and one excluded observation")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--link-repo",type=Path,required=True)
    parser.add_argument("--obs-repo",type=Path,required=True)
    try:
        verify(parser.parse_args())
    except base.Failure as error:
        raise SystemExit("FAIL: "+str(error)) from None
    except (OSError,ValueError,subprocess.SubprocessError,tarfile.TarError):
        raise SystemExit("FAIL: API-only cohost infrastructure") from None
