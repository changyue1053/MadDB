"""Synthetic exact-result tests, never iOS execution evidence."""
import copy
import importlib.util
from pathlib import Path
import re
import unittest
spec=importlib.util.spec_from_file_location('gate',Path(__file__).with_name('check-ios-test-results.py'))
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
def fixture():
    return ({'totalTestCount':10,'passedTests':10,'failedTests':0,'skippedTests':0},
            {'testNodes':[{'nodeType':'Test Case','nodeIdentifier':'MadDBSmokeTests/'+name+'()',
                           'result':'Passed'} for name in gate.EXPECTED]})
class Results(unittest.TestCase):
    def test_exact(self): gate.verify(*fixture())
    def test_matches_source_names(self):
        text=(Path(__file__).resolve().parents[1]/'ios/Smoke/Tests/MadDBSmokeTests.swift').read_text()
        self.assertEqual(tuple(re.findall(r'    func (test\w+)\(',text)),gate.EXPECTED)
    def test_new_case_missing_fails(self):
        a,b=fixture();b['testNodes'].pop()
        with self.assertRaises(gate.ResultRejected):gate.verify(a,b)
    def test_not_summary_only(self):
        a,_=fixture()
        with self.assertRaises(gate.ResultRejected):gate.verify(a,{})
    def test_duplicate_skip_wrong_count(self):
        for mode in ('duplicate','skip','count','name'):
            a,b=fixture()
            if mode=='duplicate':b['testNodes'][-1]=copy.deepcopy(b['testNodes'][0])
            if mode=='skip':b['testNodes'][-1]['result']='Skipped'
            if mode=='count':a['passedTests']=9
            if mode=='name':b['testNodes'][-1]['nodeIdentifier']='Other/testUnexpected()'
            with self.assertRaises(gate.ResultRejected):gate.verify(a,b)
if __name__=='__main__':unittest.main()
