"""Entry point for `python -m newb`."""

from newb._cli import main

if __name__ == "__main__":
    raise SystemExit(main() or 0)
