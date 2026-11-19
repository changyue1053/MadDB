"""Nonshipping packaged-byte export evidence. Never prints symbols or paths."""
import argparse,hashlib,os,re,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ABI={'maddb_abi_version','maddb_open','maddb_open_memory','maddb_close','maddb_put','maddb_get','maddb_remove'}
EXPECTED={'libmaddb.so':ABI,'libmaddb_jni.so':{'JNI_OnLoad'}}
class Failure(Exception):pass

def symbols(text,library):
    section=None;seen=False;exports=set();rows=0;declared=0
    for line in text.splitlines():
        header=re.fullmatch(r"Symbol table '([^']+)' contains ([0-9]+) entries:",line.strip())
        if header:
            section=header[1]
            if section=='.dynsym':
                if seen:raise Failure('dynamic-table')
                seen=True;declared=int(header[2])
            continue
        if section!='.dynsym' or not line.strip() or line.strip().startswith('Num:'):continue
        match=re.fullmatch(r'\s*(\d+):\s+([0-9a-fA-F]+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)(?:\s+(.*))?',line)
        if not match:raise Failure('dynamic-format')
        number,value,size,kind,binding,visibility,index,name=match.groups()
        if int(number)!=rows:raise Failure('dynamic-format')
        rows+=1;name=(name or '').strip()
        if index=='UND':continue # Undefined GLOBAL/WEAK are imports, not exports.
        if binding=='LOCAL' or visibility in ('HIDDEN','INTERNAL'):continue
        if binding not in ('GLOBAL','WEAK','UNIQUE','GNU_UNIQUE') or visibility not in ('DEFAULT','PROTECTED'):raise Failure('dynamic-format')
        if name.startswith('sqlite3_'):raise Failure('sqlite-export')
        if name not in EXPECTED[library]:raise Failure('unexpected-export')
        if name in exports or kind!='FUNC' or binding!='GLOBAL' or visibility!='DEFAULT':raise Failure('export-shape')
        exports.add(name)
    if not seen or not rows or rows!=declared:raise Failure('dynamic-table')
    if exports!=EXPECTED[library]:raise Failure('missing-export')

def dynamic(text,library):
    sonames=re.findall(r'\(SONAME\).*?\[([^\]]+)\]',text)
    needed=re.findall(r'\(NEEDED\).*?\[([^\]]+)\]',text)
    if sonames!=[library]:raise Failure('soname')
    allowed={'libc.so','libm.so','libdl.so'}
    if library=='libmaddb_jni.so':allowed.add('libmaddb.so')
    if not needed or len(needed)!=len(set(needed)) or not set(needed)<=allowed:raise Failure('needed')
    if 'libc.so' not in needed or (library=='libmaddb_jni.so' and 'libmaddb.so' not in needed):raise Failure('needed')
    if re.search(r'\((?:RPATH|RUNPATH|TEXTREL)\)|\bTEXTREL\b',text):raise Failure('dynamic-policy')

def packaged(path,prefix):
    with zipfile.ZipFile(path) as z:
        entries=z.infolist();names=[x.filename for x in entries]
        expected={f'{prefix}/arm64-v8a/{name}' for name in EXPECTED}
        if len(names)!=len(set(names)) or {n for n in names if n.endswith('.so')}!=expected:raise Failure('package-layout')
        result={}
        for name in EXPECTED:
            entry=z.getinfo(f'{prefix}/arm64-v8a/{name}')
            if not 0<entry.file_size<=64*1024*1024:raise Failure('package-size')
            result[name]=z.read(entry)
        return result

def bounded(args):
    with tempfile.TemporaryFile() as out:
        try:subprocess.run([str(x) for x in args],stdout=out,stderr=out,timeout=30,check=True)
        except (OSError,subprocess.SubprocessError):raise Failure('reader-execution') from None
        out.seek(0);data=out.read(1024*1024+1)
        if len(data)>1024*1024:raise Failure('reader-output-bound')
        try:return data.decode('utf-8')
        except UnicodeError:raise Failure('reader-format') from None

def reader(sdk):
    ndk=sdk/'ndk/28.2.13676358';values=[]
    for line in (ndk/'source.properties').read_text().splitlines():
        if line.strip().startswith('Pkg.Revision'):
            key,sep,value=line.partition('=')
            if not sep or key.strip()!='Pkg.Revision':raise Failure('ndk-receipt')
            values.append(value.strip())
    if values!=['28.2.13676358']:raise Failure('ndk-receipt')
    tool=ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf'
    if not tool.is_file() or not os.access(tool,os.X_OK):raise Failure('reader-missing')
    return tool

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--sdk',required=True);parser.add_argument('--aar',required=True);parser.add_argument('--apk',required=True);args=parser.parse_args()
    tool=reader(Path(args.sdk).resolve());aar=packaged(Path(args.aar),'jni');apk=packaged(Path(args.apk),'lib')
    if aar!=apk:raise Failure('aar-apk-byte-mismatch')
    # Invoke the existing package/alignment checks unchanged; discard their raw paths.
    bounded([sys.executable,ROOT/'scripts/inspect-android-package.py',args.aar,args.apk])
    with tempfile.TemporaryDirectory() as tmp:
        for name,data in aar.items():
            path=Path(tmp)/name;path.write_bytes(data)
            symbols(bounded([tool,'--dyn-syms','--wide',path]),name)
            dynamic(bounded([tool,'--dynamic','--wide',path]),name)
    print('PASS: exact AAR/APK bytes, declared dynamic ABI, SONAME and system dependencies; no coexistence/runtime claim')
if __name__=='__main__':
    try:main()
    except Failure as error:print('FAIL: android-symbol-'+str(error));raise SystemExit(1) from None
    except Exception:print('FAIL: android-symbol-input');raise SystemExit(1) from None
