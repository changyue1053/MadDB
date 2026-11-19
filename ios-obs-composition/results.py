"""Require exactly the real composition testcase, with no skips/failures."""
def verify(summary, tree):
    for key, value in {'totalTestCount':1,'passedTests':1,'failedTests':0,'skippedTests':0}.items():
        if type(summary.get(key)) is not int or summary[key] != value: raise ValueError('counts')
    if summary.get('expectedFailures', 0) != 0: raise ValueError('expected failures')
    pending = tree['testNodes'].copy(); seen = 0
    while pending:
        node = pending.pop()
        if node.get('result', 'Passed') != 'Passed': raise ValueError('status')
        if node.get('nodeType') == 'Test Case':
            if node.get('nodeIdentifier') not in ('MadDBObsCompositionTests/testSQLitePrivateEventsDrain', 'MadDBObsCompositionTests/testSQLitePrivateEventsDrain()') or node.get('result') != 'Passed': raise ValueError('case')
            seen += 1
        pending.extend(node.get('children', []))
    if seen != 1: raise ValueError('count')
