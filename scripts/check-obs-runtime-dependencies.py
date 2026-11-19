"""Validate local ldd output without exposing paths or arbitrary diagnostics."""
from pathlib import Path
import re
import sys

def verify(text, expected):
    if 'not found' in text:
        raise ValueError('unresolved dependency')
    if re.search(r'\blib(?:curl|ssl|crypto)[^\s/]*', text):
        raise ValueError('forbidden dependency')
    # GNU/Linux ldd format; expected absolute staging path may contain spaces.
    matches = re.findall(r'^\s*libmaddb\.so\s+=>\s+(.+?)\s+\(0x[0-9a-fA-F]+\)\s*$', text, re.M)
    if matches != [str(expected)]:
        raise ValueError('wrong staged library')

def main():
    try:
        if len(sys.argv) != 3:
            raise ValueError('arguments')
        path = Path(sys.argv[2])
        if not path.is_absolute() or not path.is_file():
            raise ValueError('staged library absent')
        verify(Path(sys.argv[1]).read_text(), path)
    except Exception:
        print('FAIL: runtime-dependency-check', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__': sys.exit(main())
