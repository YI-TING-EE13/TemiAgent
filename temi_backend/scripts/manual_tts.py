"""Manual TTS command publisher for validating robot speech output."""

from __future__ import annotations

import argparse
import time

from temi_backend.mqtt_bridge import MqttBridge


def parse_args() -> argparse.Namespace:
    """Parse command line options for the TTS publisher."""
    parser = argparse.ArgumentParser(description="Send one TTS command to Temi over MQTT.")
    parser.add_argument("--broker", default="127.0.0.1", help="MQTT broker hostname or IP address.")
    parser.add_argument("--port", default=1883, type=int, help="MQTT broker port.")
    parser.add_argument("--text", default="Hello, I am Temi.", help="Text for Temi to speak.")
    parser.add_argument("--language", default="EN_US", help="Temi language code, such as EN_US or ZH_TW.")
    parser.add_argument("--listen", action="store_true", help="Ask Temi to resume listening after speaking.")
    return parser.parse_args()


def main() -> None:
    """Connect to MQTT and publish one robot speech command."""
    args = parse_args()
    bridge = MqttBridge(args.broker, args.port, client_id="pc-manual-tts")

    print(f"Connecting to MQTT broker at {args.broker}:{args.port}...")
    bridge.start()
    try:
        bridge.publish_speak(args.text, language=args.language, continue_listening=args.listen)
        print("TTS command published.")
        time.sleep(1)
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
