#!/usr/bin/env python3
"""Fail-closed compatibility guard for the retired real-LM lifecycle path."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    """Reject real LM Studio lifecycle control without invoking an external CLI."""

    parser = argparse.ArgumentParser(
        description="Retired real LM Studio lifecycle compatibility guard."
    )
    parser.add_argument("--startup-script", required=True)
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--identifier", required=True)
    parser.parse_args(argv)
    print(
        "LM Studio is externally managed; this compatibility entrypoint never "
        "starts, stops, or reconfigures the provider. "
        "Provide a ready HTTP API and use LMSTUDIO_OWNERSHIP=external.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
