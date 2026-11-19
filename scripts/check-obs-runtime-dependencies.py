"""Fail-closed local ELF dependency check; only fixed diagnostic labels escape."""
from pathlib import Path
import os
import re
import subprocess
import sys

REASONS = frozenset(('unresolved', 'forbidden', 'direct-path', 'missing', 'duplicate',
                     'wrong-staged-library', 'staged-library-absent', 'arguments',
                     'ldd-failed', 'unexpected'))

def verify(text, expected):
    if 'not found' in text:
        raise ValueError('unresolved')
    if re.search(r'\blib(?:curl|ssl|crypto)[^\s/]*', text):
        raise ValueError('forbidden')
    # Do not silently accept absolute DT_NEEDED spelling in place of the recipe.
    if re.search(r'^\s*/.+/libmaddb\.so\s+\(0x[0-9a-fA-F]+\)\s*$', text, re.M):
        raise ValueError('direct-path')
    matches = re.findall(r'^\s*libmaddb\.so\s+=>\s+(.+?)\s+\(0x[0-9a-fA-F]+\)\s*$', text, re.M)
    if not matches:
        raise ValueError('missing')
    if len(matches) != 1:
        raise ValueError('duplicate')
    if matches[0] != str(expected):
        raise ValueError('wrong-staged-library')

def inspect(binary, expected):
    env = dict(os.environ)
    for key in ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'LD_AUDIT'):
        env.pop(key, None)
    env['LC_ALL'] = 'C'
    try:
        result = subprocess.run(['ldd', str(binary)], env=env, capture_output=True,
                                text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        raise ValueError('ldd-failed') from None
    if result.returncode != 0:
        raise ValueError('ldd-failed')
    verify(result.stdout, expected)

def main():
    try:
        if len(sys.argv) != 3:
            raise ValueError('arguments')
        path = Path(sys.argv[2])
        if not path.is_absolute() or not path.is_file():
            raise ValueError('staged-library-absent')
        inspect(Path(sys.argv[1]), path)
    except Exception as error:
        reason = str(error) if isinstance(error, ValueError) and str(error) in REASONS else 'unexpected'
        print('FAIL: runtime-dependency-' + reason, file=sys.stderr)
        return 1
    print('PASS: exact staged runtime dependencies')
    return 0

if __name__ == '__main__': sys.exit(main())
