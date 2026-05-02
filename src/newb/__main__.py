"""Entry point for `python -m newb`."""

import sys

from newb._cli import _reorder_argv, main

if __name__ == "__main__":
    sys.argv[1:] = _reorder_argv(sys.argv[1:])
    raise SystemExit(main() or 0)
