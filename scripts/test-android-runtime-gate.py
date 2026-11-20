#!/usr/bin/env python3
"""Synthetic shell-command regression only: no adb/device/runtime execution."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('test-android-device.sh').resolve()
MOCK = '''#!/usr/bin/env python3
import os,sys
args=sys.argv[1:]
assert args[:2] == ['-s','synthetic-target'], args
args=args[2:]
with open(os.environ['MOCK_CALLS'],'a') as f: f.write(' '.join(args)+'\\n')
if args == ['shell','uname','-m']: print(os.environ['MOCK_MACHINE']+'\\r')
elif args == ['shell','getprop','ro.product.cpu.abi']: print(os.environ['MOCK_ABI']+'\\r')
elif args == ['shell','getconf','PAGE_SIZE']: print(os.environ['MOCK_PAGE']+'\\r')
elif args[:2] == ['install','-r']: print('synthetic install response')
elif args == ['shell','am','instrument','-w','-r','-e','maddb_expected_page_size',os.environ['EXPECTED_PAGE_SIZE'],'io.maddb.smoke.test/android.test.InstrumentationTestRunner']: print(os.environ['MOCK_RESULT'])
else: raise AssertionError(args)
'''


class GateTests(unittest.TestCase):
    def run_case(self, machine='aarch64', abi='arm64-v8a', page='4096', expected='4096', ok=False, legacy=False, instrument_result=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'adb').write_text(MOCK)
            (root/'adb').chmod(0o755)
            env = dict(os.environ, PATH=tmp+os.pathsep+os.environ['PATH'],
                       ANDROID_SERIAL='synthetic-target', EXPECTED_PAGE_SIZE=expected,
                       MOCK_MACHINE=machine, MOCK_ABI=abi, MOCK_PAGE=page, MOCK_CALLS=str(root/'calls'),
                       MOCK_RESULT=instrument_result if instrument_result is not None else 'OK (1 test)')
            env.pop('REQUIRE_16K', None)
            if legacy: env['REQUIRE_16K']='1'
            result = subprocess.run(['bash', str(SCRIPT)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode == 0, ok, result.stderr)
            calls = (root/'calls').read_text() if (root/'calls').exists() else ''
            self.assertEqual('install -r' in calls, ok or instrument_result is not None)
            self.assertEqual('instrument -w -r -e maddb_expected_page_size '+expected+' ' in calls,
                             ok or instrument_result is not None)
            self.assertNotIn('devices', calls)
            self.assertNotIn('connect', calls)

    def test_arm64_4k(self): self.run_case(ok=True)
    def test_arm64_16k(self): self.run_case(machine='arm64', page='16384', expected='16384', ok=True)
    def test_x86_translation_rejected(self): self.run_case(machine='x86_64')
    def test_nonprimary_arm_rejected(self): self.run_case(abi='x86_64')
    def test_32bit_primary_rejected(self): self.run_case(abi='armeabi-v7a')
    def test_wrong_page_size(self): self.run_case(page='16384')
    def test_missing_mode(self): self.run_case(expected='')
    def test_unsupported_mode(self): self.run_case(expected='8192')
    def test_failed_result_cannot_pass_with_success_marker(self):
        self.run_case(instrument_result='OK (1 test)\nINSTRUMENTATION_FAILED')

    def test_legacy_mode_fails_closed(self): self.run_case(legacy=True)


if __name__ == '__main__': unittest.main()
