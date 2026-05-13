"""Command line entry point for the TemiAgent backend."""

from __future__ import annotations

import logging

from temi_backend.agent_core import AgentCore


def main() -> None:
    """Start the TemiAgent backend using environment-based configuration."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    AgentCore().run()


if __name__ == "__main__":
    main()
