"""Initialize HarmonyDocPilot catalog (one-time or after docs update)."""

from __future__ import annotations

import argparse
import sys

from hdp_scan import scan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    scan(args.config)


if __name__ == "__main__":
    main()
