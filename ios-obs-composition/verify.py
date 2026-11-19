"""Opt-in composition runner. Raw output never escapes temporary local files."""
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from project import create
from results import verify

ROOT = Path(__file__).resolve().parents[1]
PIN = '4af77ffa464a48307e5ff2d95f10b835919d205b'

def run(args, stage, env=None, capture=False, timeout=600):
    print('START: '+stage, flush=True)
    with tempfile.TemporaryFile() as log:
        try:
            subprocess.run([str(x) for x in args], env=env, stdout=log, stderr=log, check=True, timeout=timeout)
            if capture:
                log.seek(0); data = log.read(8*1024*1024+1)
                if len(data)>8*1024*1024: raise ValueError('bounded output')
                answer = data.decode()
            else: answer = None
        except Exception:
            print('FAIL: '+stage, flush=True); raise RuntimeError('stage failed') from None
    print('PASS: '+stage, flush=True)
    return answer

def main():
    if os.environ.get('MADDB_IOS_OBS') != 'ON': raise ValueError('explicit ON required')
    if platform.system()!='Darwin' or platform.machine()!='arm64': raise ValueError('Apple ARM64')
    env = dict(os.environ, DEVELOPER_DIR='/Applications/Xcode_26.2.app/Contents/Developer', RUSTUP_TOOLCHAIN='1.100.0')
    if run(['xcodebuild','-version'],'apple-preflight',env,True).strip() != 'Xcode 26.2\nBuild version 17C52': raise ValueError('Xcode')
    out=ROOT/'build/ios-obs-composition';out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out) as tmp:
        work=Path(tmp); package=work/'relocated SDK';package.mkdir()
        # Existing DB production script runs unchanged in a detached disposable source.
        with tempfile.TemporaryDirectory(dir=work) as dbtmp:
            db=Path(dbtmp); tar=db/'source.tar'
            run(['git','-C',ROOT,'archive','--format=tar','-o',tar,'HEAD'],'db-source',env)
            import tarfile
            with tarfile.open(tar) as t:t.extractall(db,filter='data')
            run(['bash',db/'scripts/build-ios.sh'],'db-package',env,timeout=1500)
            shutil.move(db/'build/ios/MadDB.xcframework',package/'MadDB.xcframework')
            headers=package/'include';headers.mkdir()
            # No MadDB C ABI headers: consumer uses only the shipping Swift module.
        # Exact public runtime, anonymous transport and clean CMake environment.
        prefixes=package/'observer';prefixes.mkdir()
        with tempfile.TemporaryDirectory(dir=work) as obstmp:
            obs=Path(obstmp);home=obs/'home';home.mkdir();source=obs/'source'
            clean={k:env[k] for k in ('PATH','DEVELOPER_DIR')};clean.update(HOME=str(home),LC_ALL='C',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_TERMINAL_PROMPT='0')
            git=['git','-c','credential.helper=','-c','http.extraHeader=']
            run(git+['init',source],'obs-init',clean)
            git+=['-C',str(source)]
            run(git+['fetch','--depth=1','--no-tags','https://github.com/changyue1053/MadObs.git',PIN],'obs-public-fetch',clean)
            if run(git+['rev-parse','FETCH_HEAD'],'obs-pin',clean,True).strip()!=PIN:raise ValueError('pin')
            run(git+['checkout','--detach','FETCH_HEAD'],'obs-checkout',clean)
            for sdk in ('iphoneos','iphonesimulator'):
                sdkroot=run(['xcrun','--sdk',sdk,'--show-sdk-path'],'sdk-path',env,True).strip()
                if run(['xcrun','--sdk',sdk,'--show-sdk-version'],'sdk-version',env,True).strip()!='26.2':raise ValueError('SDK')
                build=obs/(sdk+'-build');prefix=prefixes/sdk
                run(['cmake','-S',source,'-B',build,'-G','Xcode','-DCMAKE_SYSTEM_NAME=iOS',f'-DCMAKE_OSX_SYSROOT={sdkroot}','-DCMAKE_OSX_ARCHITECTURES=arm64','-DCMAKE_OSX_DEPLOYMENT_TARGET=15.0','-DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_ALLOWED=NO',f'-DCMAKE_INSTALL_PREFIX={prefix}','-DBUILD_TESTING=OFF','-DMADOBS_BUILD_RUNTIME=ON','-DMADOBS_BUILD_SHARED=OFF','-DMADOBS_BUILD_JNI=OFF','-DMADOBS_PACKAGE_BORINGSSL=OFF','-DIMOBS_SAN=','-DIMOBS_BORINGSSL_ROOT=','-DIMOBS_BORINGSSL_INCLUDE=','-DIMOBS_BORINGSSL_CRYPTO_LIB=',f'-DZLIB_INCLUDE_DIR={sdkroot}/usr/include',f'-DZLIB_LIBRARY={sdkroot}/usr/lib/libz.tbd'],'obs-configure',clean)
                run(['cmake','--build',build,'--config','Release','--target','imobs_core','--parallel','3'],'obs-build',clean)
                run(['cmake','--install',build,'--config','Release'],'obs-install',clean)
                archive=prefix/'lib/libmadobs_runtime.a'
                with archive.open('rb') as stream:
                    if stream.read(8)!=b'!<arch>\n':raise ValueError('archive')
                if run(['xcrun','lipo','-archs',archive],'obs-arm64',env,True).strip()!='arm64':raise ValueError('arch')
        consumer=work/'consumer'
        create(ROOT,consumer,package/'MadDB.xcframework',headers,prefixes)
        base=['xcodebuild','-project',consumer/'MadDBSmoke.xcodeproj','-scheme','MadDBSmoke','ARCHS=arm64','ONLY_ACTIVE_ARCH=YES']
        run(base+['-destination','generic/platform=iOS','-derivedDataPath',work/'device','CODE_SIGNING_ALLOWED=NO','build-for-testing'],'unsigned-device-link',env,timeout=900)
        runtime='com.apple.CoreSimulator.SimRuntime.iOS-26-2'
        available=json.loads(run(['xcrun','simctl','list','runtimes','available','-j'],'simulator-runtime',env,True))
        if not any(r['identifier']==runtime and r['isAvailable'] for r in available['runtimes']):raise ValueError('runtime')
        uuid=run(['xcrun','simctl','create','MadDB-Obs-Composition','com.apple.CoreSimulator.SimDeviceType.iPhone-16',runtime],'simulator-create',env,True).strip()
        try:
            run(['xcrun','simctl','boot',uuid],'simulator-boot',env)
            run(['xcrun','simctl','bootstatus',uuid,'-b'],'simulator-ready',env)
            if run(['xcrun','simctl','spawn',uuid,'uname','-m'],'simulator-arm64',env,True).strip()!='arm64':raise ValueError('sim arch')
            result=work/'composition.xcresult'
            run(base+['-destination',f'platform=iOS Simulator,id={uuid}','-destination-timeout','120','-derivedDataPath',work/'simulator','-resultBundlePath',result,'-parallel-testing-enabled','NO','CODE_SIGNING_ALLOWED=YES','CODE_SIGN_IDENTITY=-','CODE_SIGNING_REQUIRED=NO','test'],'composition-test',env,timeout=1200)
            summary=json.loads(run(['xcrun','xcresulttool','get','test-results','summary','--path',result],'result-summary',env,True))
            tree=json.loads(run(['xcrun','xcresulttool','get','test-results','tests','--path',result],'result-cases',env,True))
            verify(summary,tree)
            print('PASS: exact SQLite private-event runtime composition; no device execution',flush=True)
        finally:
            for action in ('shutdown','delete'):
                subprocess.run(['xcrun','simctl',action,uuid],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
if __name__=='__main__':
    try:main()
    except Exception:
        print('FAIL: ios-obs-composition');raise SystemExit(1) from None
