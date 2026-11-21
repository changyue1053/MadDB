"""Source-pinned installed iOS dual SQLite fixture. No subprocess logs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import linkage
from prepare import prepare

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PINS = {
    "db": ("4274af59b0f577ddd14de0cb710f73e7f10baa65", "5b3d00ffea99bfa0b1f81723aa7bff22b675f023"),
    "media": ("1b073a7e03870d3bf023d6f9ea752abf9cfbba99", "e008401e5ea61b6147092f44a31534bc60eb2702"),
}
EXACT_TEST = "MadDualSQLiteTests/testInstalledSQLiteProvidersRemainIndependent"
SQLITE = {"_sqlite3_open_v2", "_sqlite3_prepare_v2", "_sqlite3_step"}
class Failure(Exception):
    pass

def require(ok,label):
    if not ok:
        raise Failure(label)

def run(label,*argv,cwd=None,capture=False,timeout=600):
    env=os.environ.copy()
    env = {k:v for k,v in env.items() if k not in {"SDKROOT","PYTHONPATH"}
           and not k.startswith(("DYLD_","LD_","SIMCTL_CHILD_"))}
    env.update(DEVELOPER_DIR="/Applications/Xcode_26.2.app/Contents/Developer",
               CARGO_NET_OFFLINE="true", PYTHONDONTWRITEBYTECODE="1")
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
    require(path.resolve(strict=True)==path and path.is_relative_to(root) and path.exists(),"artifact-path")
    return path

def platform_proof(binary):
    require(run("binary-architecture","xcrun","lipo","-archs",binary,capture=True).split()==["arm64"],"binary-architecture")
    frames=re.findall(r"(?m)^\s*platform\s+(\w+)\s*$",
                      run("binary-platform","xcrun","vtool","-show-build",binary,capture=True))
    require(frames and all(x in {"7","IOSSIMULATOR"} for x in frames),"binary-platform")

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

def create_packages(args,work):
    packages=work/"relocated packages"
    packages.mkdir()
    db=packages/"MadDB.xcframework"
    journal=packages/"MadMedia Journal preview"
    with tempfile.TemporaryDirectory(prefix="producer-",dir=work) as tmp:
        producer=Path(tmp)
        db_source,media=producer/"db",producer/"media"
        stage_git("db",ROOT,args.db_ref,db_source)
        stage_git("media",args.media_repo,args.media_ref,media)
        run("db-install","bash","scripts/build-ios.sh",cwd=db_source)
        shutil.move(db_source/"build/ios/MadDB.xcframework",db)
        sdk=run("sim-sdk","xcrun","--sdk","iphonesimulator","--show-sdk-path",capture=True).strip()
        require((Path(sdk)/"usr/lib/libsqlite3.tbd").is_file(),"sqlite-sdk")
        # Only the already-proven installer, no producer App, engine or tests.
        code=("import sys; from pathlib import Path; "
              "sys.path.insert(0, 'ios-journal-preview'); from check import install; "
              "install(Path(sys.argv[1]), sys.argv[2])")
        installed=producer/"journal"
        installed.mkdir()
        run("journal-install",sys.executable,"-I","-B","-c",code,installed,sdk,cwd=media)
        shutil.move(installed/"consumer/Installed",journal)
        notices=journal/"share"
        notices.mkdir()
        shutil.copyfile(media/"THIRD_PARTY_NOTICES.md",notices/"THIRD_PARTY_NOTICES.md")
        shutil.copytree(media/"LICENSES",notices/"LICENSES")
        shutil.copytree(db_source/"ios/Smoke",work/"smoke-graph")
    require(not producer.exists(),"producer-deleted")
    archive=inside(journal,"lib/libmadmedia_journal_preview.a")
    require(run("journal-arch","xcrun","lipo","-archs",archive,capture=True).split()==["arm64"],"journal-arch")
    return packages,db,journal


def platform_loads(text):
    rows=text.splitlines()
    require(len(rows)>=2 and rows[0].endswith(":"),"load-format")
    loads=[]
    for line in rows[1:]:
        match=re.fullmatch(r"\s*(\S+) \(compatibility version [\d.]+, current version [\d.]+\)",line)
        require(match is not None,"load-format")
        loads.append(match[1])
    return loads


def native_boundaries(app_loads,db_loads,app_symbols,db_exports,test_symbols,test_loads):
    soname=re.compile(r"/usr/lib/libsqlite3(?:\.\d+)*\.dylib\Z")
    db_dylib=linkage.MADDB_DYLIB
    require(app_loads.count(db_dylib)==1 and sum(bool(soname.fullmatch(p)) for p in app_loads)==1,"app-load-boundary")
    xctest={"@rpath/XCTest.framework/XCTest", "@rpath/XCTestCore.framework/XCTestCore",
            "@rpath/XCTestSupport.framework/XCTestSupport"}
    for deps,is_test in ((app_loads,False),(db_loads,False),(test_loads,True)):
        require(all((p==db_dylib or p.startswith(("/usr/lib/", "/System/Library/Frameworks/"))
                     or (is_test and p in xctest))
                    and ".." not in p.split("/") and not re.search(r"curl|madmedia|madobs|madlink|\.debug\.dylib",p,re.I)
                    for p in deps),"dependency-boundary")
    require(not any(soname.fullmatch(p) for p in db_loads+test_loads) and db_dylib not in test_loads,
            "provider-load-boundary")
    require(not any(x.startswith(("_sqlite3_","_maddb_")) for x in db_exports.splitlines()),"mad-db-exports")
    for name in SQLITE:
        entries=[line for line in app_symbols.splitlines() if re.search(r"\b"+name+r"\b",line)]
        require(len(entries)==1 and re.fullmatch(
            r"\s*\(undefined\) external "+name+r" \(from libsqlite3(?:\.\d+)*\)\s*",entries[0]),
            "system-sqlite-imports")
    require(not re.search(r"(?m)^\s*[0-9a-fA-F]+\s+.*\b_sqlite3_\w+",app_symbols),"app-sqlite-definition")
    require(re.search(r"(?m)^\s*[0-9a-fA-F]+\s+.*\b__ZN4immd7Journal4open",app_symbols),"journal-in-app")
    require(re.search(r"(?m)^\s*U[ \t]+_OBJC_CLASS_\$_MadDualSQLiteDriver[ \t]*$",test_symbols)
            and not re.search(r"(?m)\b(?:_sqlite3_|_maddb_|_ds_journal_|__ZNK?4immd7Journal)",test_symbols),
            "test-ingress-only")


def validate(build,db):
    products=inside(build,"Build/Products/Debug-iphonesimulator")
    app=inside(products,"MadDBSmoke.app")
    binary=inside(app,"MadDBSmoke")
    framework=inside(app,"Frameworks/MadDB.framework/MadDB")
    linkage.verify_app(app,linkage.packaged_identity(db))
    require({p.name for p in (app/"Frameworks").iterdir()}=={"MadDB.framework"},"embedded-frameworks")
    def signature(path):
        run("code-signature","/usr/bin/codesign","--verify","--strict",path)
    signature(app)
    signature(framework.parent)
    platform_proof(binary)
    def loads(path):
        return platform_loads(run("load-commands","xcrun","otool","-L",path,capture=True))
    app_loads,fw_loads=loads(binary),loads(framework)
    # otool -L starts with the dylib's own ID.
    require(fw_loads[:1]==[linkage.MADDB_DYLIB],"framework-id")
    exports=run("framework-exports","xcrun","nm","-gjU",framework,capture=True)
    symbols=run("app-symbols","xcrun","nm","-m",binary,capture=True)
    require(re.search(r"\bTWOLEVEL\b",run("macho-flags","xcrun","otool","-hv",binary,capture=True)),
            "two-level-namespace")
    tests=[]
    for rel in ("MadDBSmokeTests.xctest/MadDBSmokeTests",
                "MadDBSmoke.app/PlugIns/MadDBSmokeTests.xctest/MadDBSmokeTests"):
        path=products/rel
        if path.exists() or path.is_symlink():
            test=inside(products,rel)
            platform_proof(test)
            signature(test.parent)
            native_boundaries(app_loads,fw_loads[1:],symbols,exports,
                              run("test-symbols","xcrun","nm",test,capture=True),loads(test))
            tests.append(test)
    require(tests,"test-missing")
    return (app,*[p.parent for p in tests])


def qualify(args):
    require(platform.system()=="Darwin" and platform.machine()=="arm64","stock-arm64-host")
    require(run("xcode-version","xcodebuild","-version",capture=True).splitlines()==
            ["Xcode 26.2","Build version 17C52"],"xcode-version")
    for sdk in ("iphoneos","iphonesimulator"):
        require(run("sdk-version","xcrun","--sdk",sdk,"--show-sdk-version",capture=True).strip()=="26.2","sdk-version")
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="mad-dual-sqlite-") as tmp:
        work=Path(tmp).resolve()
        packages,db,journal=create_packages(args,work)
        app=work/"independent app"
        prepare(work/"smoke-graph",app,db,journal)
        shutil.rmtree(work/"smoke-graph")
        before=digest(packages)
        build,result=work/"derived",work/"dual-sqlite.xcresult"
        uuid=run("sim-create","xcrun","simctl","create","MadDualSQLite",
                 "com.apple.CoreSimulator.SimDeviceType.iPhone-16",
                 "com.apple.CoreSimulator.SimRuntime.iOS-26-2",capture=True,timeout=60).strip()
        require(re.fullmatch(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}",uuid),"sim-uuid")
        try:
            run("sim-boot","xcrun","simctl","boot",uuid,timeout=90)
            run("sim-ready","xcrun","simctl","bootstatus",uuid,"-b",timeout=180)
            opts=("-project","MadDBSmoke.xcodeproj","-scheme","MadDBSmoke","-configuration","Debug",
                  "-destination","platform=iOS Simulator,id="+uuid,"-derivedDataPath",build,
                  "ARCHS=arm64","ONLY_ACTIVE_ARCH=YES","ENABLE_DEBUG_DYLIB=NO","-parallel-testing-enabled","NO",
                  "CODE_SIGNING_ALLOWED=YES","CODE_SIGN_IDENTITY=-","CODE_SIGNING_REQUIRED=NO")
            run("sim-build","xcodebuild","build-for-testing",*opts,cwd=app,timeout=420)
            products=validate(build,db)
            hashes=[digest(p) for p in products]
            run("sim-test","xcodebuild","test-without-building",*opts,"-resultBundlePath",result,cwd=app,timeout=420)
            require([digest(p) for p in products]==hashes and digest(packages)==before,"artifact-mutation")
            test_result(*(json.loads(run("xcresult","xcrun","xcresulttool","get","test-results",mode,
                                         "--path",result,"--compact",capture=True,timeout=45))
                          for mode in ("summary","tests")))
        finally:
            run("sim-delete","xcrun","simctl","delete",uuid,timeout=90)
    print("PASS: installed MadDB and MadMedia Journal independent SQLite stores in one iOS ARM64 simulator app")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--db-ref",default=PINS["db"][0])
    parser.add_argument("--media-repo",type=Path,required=True)
    parser.add_argument("--media-ref",default=PINS["media"][0])
    try:
        qualify(parser.parse_args())
    except Failure as error:
        raise SystemExit("FAIL: dual-sqlite-"+str(error)) from None
    except Exception:
        raise SystemExit("FAIL: dual-sqlite-infrastructure") from None
