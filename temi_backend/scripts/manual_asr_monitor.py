"""Manual MQTT ASR monitor for validating the Android Temi client."""

from __future__ import annotations

import argparse
import time
from typing import Any

from temi_backend.mqtt_bridge import MqttBridge


def parse_args() -> argparse.Namespace:
    """Parse command line options for the ASR monitor."""
    parser = argparse.ArgumentParser(description="Print ASR events received from Temi over MQTT.")
    parser.add_argument("--broker", default="127.0.0.1", help="MQTT broker hostname or IP address.")
    parser.add_argument("--port", default=1883, type=int, help="MQTT broker port.")
    return parser.parse_args()


def print_asr_event(payload: dict[str, Any]) -> None:
    """Print one ASR event payload in a human-readable format."""
    print("\n--- ASR event received ---")
    print(f"Text      : {payload.get('text', '')}")
    print(f"Language  : {payload.get('language', 'UNKNOWN')}")
    print(f"Timestamp : {payload.get('timestamp_ms', 0)} ms")
    print("--------------------------\n")


def main() -> None:
    """Run the blocking ASR monitor until interrupted."""
    args = parse_args()
    bridge = MqttBridge(args.broker, args.port, client_id="pc-manual-asr-monitor")
    bridge.set_asr_callback(print_asr_event)

    print(f"Connecting to MQTT broker at {args.broker}:{args.port}...")
    try:
        bridge.start()
        print("Waiting for Temi ASR events. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping ASR monitor.")
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
