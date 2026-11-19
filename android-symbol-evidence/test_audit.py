import unittest,tempfile,zipfile
from pathlib import Path
from audit import ABI,Failure,symbols,dynamic,packaged

def table(extra=(),change=None):
    rows=['0: 00000000 0 NOTYPE LOCAL DEFAULT UND']
    for name in sorted(ABI):rows.append(f'{len(rows)}: 00001000 8 FUNC GLOBAL DEFAULT 12 {name}')
    for row in extra:rows.append(f'{len(rows)}: {row}')
    if change:rows[1]=rows[1].replace(*change)
    return f"Symbol table '.dynsym' contains {len(rows)} entries:\n Num: Value Size Type Bind Vis Ndx Name\n"+'\n'.join(rows)+'\n'
class Tests(unittest.TestCase):
    def test_valid_import_weak_and_static_distinction(self):
        text=table(['00000000 0 FUNC GLOBAL DEFAULT UND malloc@LIBC (2)','00000000 0 NOTYPE WEAK DEFAULT UND weak_import'])
        text+="Symbol table '.symtab' contains 1 entries:\n0: 00001000 8 FUNC GLOBAL DEFAULT 12 sqlite3_open\n"
        symbols(text,'libmaddb.so')
    def test_defined_unexpected_weak_and_sqlite_rejected(self):
        for name,binding in [('sqlite3_open','GLOBAL'),('unrelated','GLOBAL'),('weak_export','WEAK')]:
            with self.assertRaises(Failure):symbols(table([f'00001000 8 FUNC {binding} DEFAULT 12 {name}']),'libmaddb.so')
    def test_missing_shape_and_truncation(self):
        for text in [table(change=('GLOBAL','WEAK')),table(change=('DEFAULT','PROTECTED')),table().replace('maddb_put','other'),table().rsplit('\n',2)[0],"Symbol table '.symtab' contains 1 entries:\n0: 0 0 NOTYPE LOCAL DEFAULT UND"]:
            with self.assertRaises(Failure):symbols(text,'libmaddb.so')
    def test_dynamic_metadata(self):
        good='0 (SONAME) Library soname: [libmaddb_jni.so]\n0 (NEEDED) Shared library: [libmaddb.so]\n0 (NEEDED) Shared library: [libc.so]\n'
        dynamic(good,'libmaddb_jni.so')
        for bad in [good.replace('libc.so','libsqlite3.so'),good+'0 (RUNPATH) [/secret]',good+ '0 (SONAME) [libmaddb_jni.so]',good.replace('libmaddb.so','other.so')]:
            with self.assertRaises(Failure):dynamic(bad,'libmaddb_jni.so')
    def test_packaged_bytes_not_build_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'input.aar'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('jni/arm64-v8a/libmaddb.so',b'core')
                z.writestr('jni/arm64-v8a/libmaddb_jni.so',b'jni')
            self.assertEqual(packaged(p,'jni'),{'libmaddb.so':b'core','libmaddb_jni.so':b'jni'})
            with self.assertRaises(Failure):packaged(p,'lib')
    def test_source_allowlist(self):
        root=Path(__file__).resolve().parents[1]
        import re
        names=set(re.findall(r'#\[no_mangle\]\s*pub (?:unsafe )?extern "C" fn (\w+)',(root/'src/ffi.rs').read_text()))
        self.assertEqual(names,ABI)
        jni=(root/'android/maddb/src/main/c/maddb_jni.c').read_text()
        self.assertEqual(re.findall(r'JNIEXPORT\s+\w+\s+JNICALL\s+(\w+)',jni),['JNI_OnLoad'])
if __name__=='__main__':unittest.main()
