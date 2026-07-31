#!/usr/bin/env python3
"""Exercise the production Discord sender against the local test endpoint only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "anomaly_detection"))

from temi_action_viewer import DiscordDeliveryError, notify_discord_webhook  # noqa: E402


def _deliver(url: str, env_path: Path) -> str:
    env_path.write_text(f"DISCORD_WEBHOOK_URL={url}\n", encoding="utf-8")
    try:
        return str(notify_discord_webhook("[TEST] newcomer mock notification", [], str(env_path), 0)["failure_code"])
    except DiscordDeliveryError as exc:
        return exc.failure_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    env_path = args.work_dir / "discord-test.env"
    try:
        expected = {
            "204": "DISCORD_DELIVERED",
            "401": "DISCORD_UNAUTHORIZED",
            "403": "DISCORD_FORBIDDEN",
            "404": "DISCORD_WEBHOOK_NOT_FOUND",
            "429": "DISCORD_RATE_LIMITED",
            "connection": "DISCORD_CONNECTION_FAILED",
        }
        observed = {
            status: _deliver(f"{args.endpoint}?status={status}", env_path)
            for status in ("204", "401", "403", "404", "429")
        }
        host, _, port_text = args.endpoint.removeprefix("http://").partition(":")
        port = int(port_text.split("/", 1)[0])
        observed["connection"] = _deliver(f"http://{host}:{port + 1}/webhook", env_path)
        observed["timeout"] = _deliver(f"{args.endpoint}?delay=16", env_path)
        expected["timeout"] = "DISCORD_TIMEOUT"
        if observed != expected:
            raise RuntimeError(f"Discord failure matrix mismatch: {observed}")
        print(json.dumps({"status": "PASS", "codes": observed}, ensure_ascii=False))
        return 0
    finally:
        env_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
