"""Manual navigation command publisher for validating robot movement."""

from __future__ import annotations

import argparse
import time

from temi_backend.mqtt_bridge import MqttBridge


def parse_args() -> argparse.Namespace:
    """Parse command line options for the navigation publisher."""
    parser = argparse.ArgumentParser(description="Send one navigation command to Temi over MQTT.")
    parser.add_argument("--broker", default="127.0.0.1", help="MQTT broker hostname or IP address.")
    parser.add_argument("--port", default=1883, type=int, help="MQTT broker port.")
    parser.add_argument("--target", required=True, help="Predefined Temi map location name.")
    return parser.parse_args()


def main() -> None:
    """Connect to MQTT and publish one robot navigation command."""
    args = parse_args()
    bridge = MqttBridge(args.broker, args.port, client_id="pc-manual-navigate")

    print(f"Connecting to MQTT broker at {args.broker}:{args.port}...")
    bridge.start()
    try:
        bridge.publish_navigate(args.target)
        print(f"Navigation command published for target: {args.target}")
        time.sleep(1)
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
