"""Synthetic ldd-format checks, not actual runtime/link evidence."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import subprocess
import os
spec=importlib.util.spec_from_file_location('gate',Path(__file__).with_name('check-obs-runtime-dependencies.py'))
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class Dependencies(unittest.TestCase):
    expected=Path('/synthetic stage/lib/libmaddb.so')
    good='libmaddb.so => /synthetic stage/lib/libmaddb.so (0x1234)\nlibc.so.6 => /lib/libc.so.6 (0x1111)\n'
    def test_exact_staged_library(self):
        gate.verify(self.good,self.expected)
    def test_forbidden_and_missing(self):
        for line in ('libcurl.so.4 => /lib/libcurl.so.4 (0x1234)',
                     'libssl.so.3 => /lib/libssl.so.3 (0x1234)',
                     'libcrypto.so.3 => /lib/libcrypto.so.3 (0x1234)',
                     'libunknown.so => not found'):
            with self.assertRaises(ValueError): gate.verify(self.good+line,self.expected)
    def test_missing_duplicate_or_wrong_maddb(self):
        for value in ('',self.good+self.good,self.good.replace('/synthetic stage','/different')):
            with self.assertRaises(ValueError): gate.verify(value,self.expected)

    def test_diagnostic_categories(self):
        for text, reason in [('/synthetic stage/lib/libmaddb.so (0x1234)\n', 'direct-path'),
                             ('', 'missing'), (self.good+self.good, 'duplicate'),
                             (self.good.replace('/synthetic stage','/other'),'wrong-staged-library')]:
            with self.assertRaises(ValueError) as error: gate.verify(text,self.expected)
            self.assertEqual(str(error.exception),reason)
    def test_ldd_failure_and_environment(self):
        result=subprocess.CompletedProcess([],1,'partial output','private path')
        with patch.dict(os.environ,{'LD_LIBRARY_PATH':'private','LD_PRELOAD':'private','LD_AUDIT':'private'}), patch.object(gate.subprocess,'run',return_value=result) as call:
            with self.assertRaises(ValueError) as error: gate.inspect('synthetic',self.expected)
        self.assertEqual(str(error.exception),'ldd-failed')
        for key in ('LD_LIBRARY_PATH','LD_PRELOAD','LD_AUDIT'):
            self.assertNotIn(key,call.call_args.kwargs['env'])

if __name__=='__main__': unittest.main()
