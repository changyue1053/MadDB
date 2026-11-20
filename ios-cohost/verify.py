"""Source-pinned installed iOS cohost. Stages never print subprocess output."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import subprocess
import tarfile
import tempfile
from prepare import prepare

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
PINS={
    "db-api":("951ed05a210a2e722edf79fc6f5a6cd8acbd53b8","21eace33e39a16fe4e5b97b121fdd2361b8adb31"),
    "db":("b60392d56be3ef3f7fd1db2c9547e98a535aa0d1","b231055e5421f64cf5063e21088fab1dcc35006f"),
    "link":("80c9d8ffd23a5911b4f2eb71b5408b1d57717f2a","d2fd4ed05b6bd29d65b3011a6febce99dc912a4a"),
    "obs":("af06c481226fe9abddae5218e022f52683784e3e","4ac71eee165885687a8a4c90ebfaf85a00b098a7"),
}
EXACT_TEST="MadCohostTests/testInstalledSdkCohost"
HEADERS=("madobs/runtime.h","madobs/observer.h","madobs/privacy.h","imobs/imobs_c.h")

class Failure(Exception):
    pass

def require(ok,label):
    if not ok:
        raise Failure(label)

def run(label,*argv,cwd=None,capture=False,timeout=600):
    env=os.environ.copy()
    for k in ("SDKROOT","PYTHONPATH","DYLD_LIBRARY_PATH","DYLD_INSERT_LIBRARIES"):
        env.pop(k,None)
    with tempfile.TemporaryFile() as log:
        try:
            subprocess.run(argv,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                           timeout=timeout,check=True)
        except (OSError,subprocess.SubprocessError):
            raise Failure(label) from None
        if capture:
            log.seek(0); output=log.read(2*1024*1024+1)
            require(len(output)<=2*1024*1024,label)
            return output.decode()

def stage_git(role,repo,ref,target):
    rev=run("git-commit","git","-C",repo,"rev-parse","--verify",ref+"^{commit}",capture=True).strip()
    tree=run("git-tree","git","-C",repo,"rev-parse","--verify",rev+"^{tree}",capture=True).strip()
    require(tree==PINS[role][1],"git-tree-mismatch")
    tar=target.with_suffix(".tar")
    run("git-archive","git","-C",repo,"archive","--format=tar","-o",tar,rev)
    target.mkdir()
    with tarfile.open(tar) as archive:
        files=archive.getmembers()
        require(len(files)<=20000 and sum(x.size for x in files)<=128*1024*1024,"source-size")
        require(all((x.isfile() or x.isdir()) and not Path(x.name).is_absolute() and
                    ".." not in Path(x.name).parts for x in files), "source-members")
        require(len({x.name for x in files})==len(files),"source-members")
        archive.extractall(target,members=files,filter="data")
    tar.unlink()

def digest(root):
    result={}
    for p in sorted(root.rglob("*")):
        require(not p.is_symlink(),"artifact-symlink")
        if not p.is_dir():
            require(p.is_file(),"artifact-type")
            with p.open("rb") as f:
                result[str(p.relative_to(root))]=hashlib.file_digest(f,"sha256").digest()
    return result

def inside(root,rel):
    path=root/rel
    require(path.resolve()==path and path.is_relative_to(root) and path.exists(),"artifact-path")
    return path

def select_sim(xc,name,library_only=False):
    info=plistlib.loads(inside(xc,"Info.plist").read_bytes())
    libraries=info["AvailableLibraries"]
    require(len(libraries)==2 and {x.get("SupportedPlatformVariant","") for x in libraries}=={"","simulator"}
            and all(x["SupportedPlatform"]=="ios" and x["SupportedArchitectures"]==["arm64"] for x in libraries),
            "artifact-slices")
    sim=next(x for x in libraries if x.get("SupportedPlatformVariant")=="simulator")
    require(sim["LibraryIdentifier"]=="ios-arm64-simulator","artifact-simulator-slice")
    base=inside(xc,"ios-arm64-simulator")
    if not library_only:
        require(sim["LibraryPath"]==name+".framework","framework-path")
        return inside(base,f"{name}.framework/{name}")
    require(sim["LibraryPath"]==name and sim["HeadersPath"]=="Headers","archive-path")
    headers=inside(base,"Headers")
    require({str(x.relative_to(headers)) for x in headers.rglob("*") if x.is_file()}==
            set(HEADERS)|{"module.modulemap"},"obs-public-headers")
    return inside(base,name),headers

def make_obs(source,work,dest):
    args=[]
    for variant,sdk in (("device","iphoneos"),("simulator","iphonesimulator")):
        sdkroot=Path(run("obs-sdk","xcrun","--sdk",sdk,"--show-sdk-path",capture=True).strip())
        prefix=work/(variant+" installed")
        build=work/(variant+" build")
        zlib=sdkroot/"usr/lib/libz.tbd"
        require(zlib.is_file() and (sdkroot/"usr/include/zlib.h").is_file(),"obs-target-zlib")
        run("obs-configure","cmake","-S",source,"-B",build,"-G","Xcode","-DCMAKE_SYSTEM_NAME=iOS",
            f"-DCMAKE_OSX_SYSROOT={sdkroot}","-DCMAKE_OSX_ARCHITECTURES=arm64","-DCMAKE_OSX_DEPLOYMENT_TARGET=15.0",
            "-DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_ALLOWED=NO",f"-DCMAKE_INSTALL_PREFIX={prefix}",
            "-DBUILD_TESTING=OFF","-DMADOBS_BUILD_RUNTIME=ON","-DMADOBS_BUILD_SHARED=OFF","-DMADOBS_BUILD_JNI=OFF",
            "-DMADOBS_PACKAGE_BORINGSSL=OFF","-DIMOBS_SAN=","-DIMOBS_BORINGSSL_ROOT=",
            "-DIMOBS_BORINGSSL_INCLUDE=","-DIMOBS_BORINGSSL_CRYPTO_LIB=",
            f"-DZLIB_INCLUDE_DIR={sdkroot}/usr/include",f"-DZLIB_LIBRARY={zlib}")
        run("obs-build","cmake","--build",build,"--config","Release","--target","imobs_core","--parallel","3")
        run("obs-install","cmake","--install",build,"--config","Release")
        headers=work/(variant+" headers")
        headers.mkdir()
        for name in HEADERS:
            p=headers/name;p.parent.mkdir(exist_ok=True);shutil.copyfile(prefix/"include"/name,p)
        (headers/"module.modulemap").write_text('module MadObsRuntime { header "madobs/runtime.h" export * }\n')
        args.extend(("-library",prefix/"lib/libmadobs_runtime.a","-headers",headers))
    run("obs-package","xcodebuild","-create-xcframework",*args,"-output",dest)

API_ONLY_FILES={"include/madobs/observer.h","include/madobs/privacy.h",
                "lib/cmake/MadObs/MadObsApiTargets.cmake","lib/cmake/MadObs/MadObsConfig.cmake",
                "lib/cmake/MadObs/MadObsConfigVersion.cmake"}

def api_inventory(prefix):
    require(set(digest(prefix))==API_ONLY_FILES,"api-only-inventory")
    return inside(prefix,"include")

def make_obs_api(source,work,dest):
    build=work/"api-only build"
    prefix=work/"api-only prefix"
    run("api-only-configure","cmake","-S",source,"-B",build,
        "-DBUILD_TESTING=OFF","-DMADOBS_BUILD_RUNTIME=OFF","-DMADOBS_BUILD_SHARED=OFF",
        "-DMADOBS_BUILD_JNI=OFF","-DMADOBS_PACKAGE_BORINGSSL=OFF",
        "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF","-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF")
    run("api-only-install","cmake","--install",build,"--prefix",prefix)
    shutil.move(prefix,dest)

def prove_api_target(work, prefix):
    src=work/"api target probe"
    src.mkdir()
    (src/"CMakeLists.txt").write_text(
        'cmake_minimum_required(VERSION 3.20)\nproject(ApiProbe NONE)\n'
        'find_package(MadObs 0.1.0 EXACT CONFIG REQUIRED PATHS "${ROOT}" NO_DEFAULT_PATH)\n'
        'if(NOT TARGET MadObs::api OR TARGET MadObs::runtime)\n'
        '  message(FATAL_ERROR "unexpected MadObs targets")\nendif()\n'
        'get_target_property(kind MadObs::api TYPE)\n'
        'get_target_property(headers MadObs::api INTERFACE_INCLUDE_DIRECTORIES)\n'
        'get_target_property(links MadObs::api INTERFACE_LINK_LIBRARIES)\n'
        'if(NOT kind STREQUAL "INTERFACE_LIBRARY" OR NOT headers STREQUAL "${ROOT}/include" OR links)\n'
        '  message(FATAL_ERROR "unexpected MadObs link interface")\nendif()\n')
    run("api-only-target","cmake","-S",src,"-B",work/"api target build",
        "-DROOT="+str(prefix),"-DMadObs_DIR="+str(prefix/"lib/cmake/MadObs"),
        "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF","-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF")

def verify_api_link_absence(syms,loads):
    require(not re.search(r"(?m)\s_madobs_(?:create|start|stop|destroy|private_\w+|runtime_\w+|emit_generic_event|observer_for_runtime|check_private_batch)\s*$",syms),
            "api-only-runtime-symbols")
    require(not re.search(r"(?im)^\s*\S*(?:/libz\.|libmadobs|MadObsRuntime)",loads),"api-only-runtime-loads")

def create_packages(args,work):
    packages=work/"separately relocated packages"
    packages.mkdir()
    with tempfile.TemporaryDirectory(prefix="producers-",dir=work) as tmp:
        source=Path(tmp)
        stage_git("db-api" if args.obs_api else "db",ROOT,args.db_ref,source/"db")
        stage_git("link",args.link_repo,args.link_ref,source/"link")
        db,link=(packages/f"{name}.xcframework" for name in ("MadDB","MadLink"))
        run("db-package","bash","scripts/build-ios.sh",cwd=source/"db")
        shutil.move(source/"db/build/ios/MadDB.xcframework",db)
        run("link-package","python3","-B","-c",
            'import sys,shutil; from pathlib import Path; sys.path.insert(0,"ios"); '
            'from sdk_package import build_package; _, package=build_package(Path.cwd()); '
            'shutil.move(package,Path(sys.argv[1]))',link,cwd=source/"link")
        obs=None
        if args.obs_repo:
            stage_git("obs",args.obs_repo,args.obs_ref,source/"obs")
            if args.obs_api:
                obs=packages/"MadObs API prefix"
                make_obs_api(source/"obs",source,obs)
            else:
                obs=packages/"MadObsRuntime.xcframework"
                built=source/"MadObsRuntime.xcframework"
                make_obs(source/"obs",source,built)
                shutil.move(built,obs)
        # Reuse the exact source-pinned, signature-insensitive Swift framework assertion.
        matcher=source/"db/scripts/ios_two_apps_linkage.py"
        spec=importlib.util.spec_from_file_location("maddb_package_linkage",matcher)
        helper=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
    require(not source.exists(),"producer-removal")
    return packages,db,link,obs,helper

def platform_proof(binary):
    require(run("binary-architecture","xcrun","lipo","-archs",binary,capture=True).split()==["arm64"],"binary-architecture")
    frames=re.findall(r"(?m)^\s*platform\s+(\w+)\s*$",
                      run("binary-platform","xcrun","vtool","-show-build",binary,capture=True))
    require(frames and all(x in {"7","IOSSIMULATOR"} for x in frames),"binary-platform")

def defined(text, sym):
    return re.search(r"(?m)\s[Tt]\s+_"+re.escape(sym)+r"\s*$",text) is not None

def test_result(summary,cases):
    require(all(type(summary.get(k)) is int and summary[k]==expected for k,expected in
                (("totalTestCount",1),("passedTests",1),("failedTests",0),("skippedTests",0))),"result-count")
    require(summary.get("testStatus","Passed")=="Passed" and summary.get("expectedFailures",0)==0,"result-status")
    names=[]
    def check_nodes(nodes):
        require(isinstance(nodes,list),"result-tree")
        for n in nodes:
            require(isinstance(n,dict) and n.get("result","Passed")=="Passed","result-status")
            if n.get("nodeType")=="Test Case":
                require(n.get("result")=="Passed" and isinstance(n.get("nodeIdentifier"),str),"result-case")
                names.append(n["nodeIdentifier"].removesuffix("()"))
            check_nodes(n.get("children",[]))
    check_nodes(cases["testNodes"])
    require(names==[EXACT_TEST],"result-name")

def validate_app(build,db,helper,enabled,*,api=False):
    parent=inside(build,"Build/Products/Debug-iphonesimulator")
    app=inside(parent,"MadDBSmoke.app")
    binary=inside(app,"MadDBSmoke")
    helper.verify_app(app,helper.packaged_identity(db))
    platform_proof(binary)
    syms=run("app-symbols","xcrun","nm","-U",binary,capture=True)
    required=("ml_create_tracked_v1","ml_send_tracked_v1","ml_next_completion_v1","mco_open")
    require(all(defined(syms,s) for s in required),"app-link-ownership")
    if enabled:
        require(all(defined(syms,s) for s in ("madobs_create","madobs_emit_generic_event",
                                             "madobs_check_private_batch")),"app-obs-symbols")
    elif not api:
        require(not re.search(r"(?m)\s_madobs_\w+\s*$",syms),"off-obs-symbols")
    embedded=app/"Frameworks"
    loads=run("app-loads","xcrun","otool","-L",binary,capture=True)
    if api: verify_api_link_absence(syms,loads)
    require(not (embedded/"MadLink.framework").exists() and not (embedded/"MadObsRuntime.framework").exists()
            and not any(name in loads for name in ("MadLink.framework", "MadObsRuntime", "libmadobs", "libmadlink")),
            "static-not-dynamic")
    tests=[]
    for rel in ("MadDBSmokeTests.xctest/MadDBSmokeTests",
                "MadDBSmoke.app/PlugIns/MadDBSmokeTests.xctest/MadDBSmokeTests"):
        if (parent/rel).exists():
            test=inside(parent,rel)
            platform_proof(test)
            references=run("test-symbols","xcrun","nm",test,capture=True)
            require(re.search(r"(?m)^\s*U[ \t]+_OBJC_CLASS_\$_MadCohostDriver[ \t]*$",references) and
                    not re.search(r"(?m)\s_(?:ml_|madobs_|maddb_|mco_)\w+\s*$",references),
                    "test-app-ingress-only")
            dependencies=run("test-loads","xcrun","otool","-L",test,capture=True)
            require(not any(name in dependencies for name in ("MadDB.framework","MadLink.framework","MadObsRuntime")),
                    "test-no-sdk-links")
            tests.append(test)
    require(tests,"test-bundle-missing")
    return (binary,*tests)

def qualify(args):
    require(not args.obs_api or args.obs_repo is not None,"api-only-explicit-pin")
    require(platform.system()=="Darwin" and platform.machine()=="arm64","stock-arm64-host")
    require(run("xcode-version","xcodebuild","-version",capture=True).splitlines()==
            ["Xcode 26.2","Build version 17C52"],"xcode-version")
    for sdk in ("iphoneos","iphonesimulator"):
        require(run("sdk-version","xcrun","--sdk",sdk,"--show-sdk-version",capture=True).strip()=="26.2","sdk-version")
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="mad-ios-cohost-") as tmp:
        work=Path(tmp).resolve()
        packages,db,link,obs,helper=create_packages(args,work)
        require(args.obs_repo or obs is None,"off-no-obs")
        before=digest(packages)
        link_archive=select_sim(link,"MadLink")
        api_headers=api_inventory(obs) if args.obs_api else None
        if api_headers is not None:
            prove_api_target(work,obs)
            probe=work/"api collector probe"
            run("api-collector-compile","xcrun","clang++","-std=c++17","-Wall","-Wextra","-Wpedantic","-Werror",
                "-I",api_headers,HERE/"api_collector_test.cc","-o",probe)
            run("api-collector-fixture",probe,cwd=work,timeout=30)
        obs_paths=select_sim(obs,"libmadobs_runtime.a",True) if obs and not args.obs_api else None
        for archive in (link_archive,*((obs_paths[0],) if obs_paths else ())):
            require(run("archive-arch","xcrun","lipo","-archs",archive,capture=True).split()==["arm64"],"archive-arch")
            with archive.open("rb") as f:
                require(f.read(8)==b"!<arch>\n","archive-type")
        folder=work/"independent app"
        prepare(ROOT/"ios/Smoke",folder,db,link_archive,obs_paths,api_headers=api_headers)
        build=work/"simulator build"
        result=work/"result.xcresult"
        udid=run("sim-create","xcrun","simctl","create","MadInstalledCohost",
                 "com.apple.CoreSimulator.SimDeviceType.iPhone-16",
                 "com.apple.CoreSimulator.SimRuntime.iOS-26-2",capture=True).strip()
        require(re.fullmatch(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}",udid),"sim-uuid")
        try:
            run("sim-boot","xcrun","simctl","boot",udid)
            run("sim-ready","xcrun","simctl","bootstatus",udid,"-b")
            opts=("-project","MadDBSmoke.xcodeproj","-scheme","MadDBSmoke","-configuration","Debug",
                  "-destination","platform=iOS Simulator,id="+udid,"-derivedDataPath",build,
                  "ARCHS=arm64","ONLY_ACTIVE_ARCH=YES","ENABLE_DEBUG_DYLIB=NO","-parallel-testing-enabled","NO",
                  "CODE_SIGNING_ALLOWED=YES","CODE_SIGN_IDENTITY=-","CODE_SIGNING_REQUIRED=NO")
            run("sim-build","xcodebuild","build-for-testing",*opts,cwd=folder)
            artifacts=validate_app(build,db,helper,obs_paths is not None,api=args.obs_api)
            hashes={p:hashlib.sha256(p.read_bytes()).digest() for p in artifacts}
            run("sim-test","xcodebuild","test-without-building",*opts,"-resultBundlePath",result,cwd=folder)
            require(all(hashlib.sha256(p.read_bytes()).digest()==d for p,d in hashes.items()),"binary-mutation")
            test_result(*(json.loads(run("xcresult","xcrun","xcresulttool","get","test-results",
                                        mode,"--path",result,capture=True)) for mode in ("summary","tests")))
            require(digest(packages)==before,"package-mutation")
        finally:
            run("sim-delete","xcrun","simctl","delete",udid)
    print("PASS: independent app-owned installed iOS cohost "+("API-only exact local 3+3" if args.obs_api else "ON" if args.obs_repo else "OFF"))

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--db-ref",default="HEAD^")
    parser.add_argument("--link-repo",type=Path,required=True)
    parser.add_argument("--link-ref",default=PINS["link"][0])
    parser.add_argument("--obs-api",action="store_true")
    parser.add_argument("--obs-repo",type=Path)
    parser.add_argument("--obs-ref",default=PINS["obs"][0])
    try:
        qualify(parser.parse_args())
    except Failure as e:
        raise SystemExit("FAIL: "+str(e)) from None
    except Exception:
        raise SystemExit("FAIL: qualification infrastructure") from None
