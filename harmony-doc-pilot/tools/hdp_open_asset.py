"""Open asset on macOS."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args()

    path = os.path.abspath(args.path)
    if not os.path.exists(path):
        print(f"not_found: {path}", file=sys.stderr)
        raise SystemExit(1)

    subprocess.run(["open", path], check=False)


if __name__ == "__main__":
    main()
