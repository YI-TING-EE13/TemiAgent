import argparse
import json
import paho.mqtt.client as mqtt

def main():
    parser = argparse.ArgumentParser(description="Temi Speak Action")
    parser.add_argument("--text", required=True, help="Text for Temi to speak")
    parser.add_argument("--language", default="ZH_TW", help="Language code (default: ZH_TW)")
    parser.add_argument("--listen", action="store_true", help="Keep microphone open after speaking")
    parser.add_argument("--broker", default="127.0.0.1", help="MQTT Broker IP")
    args = parser.parse_args()

    # Use paho-mqtt to publish the command
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "hermes-skill-speak")
    try:
        client.connect(args.broker, 1883, 60)
        payload = {
            "text": args.text,
            "language": args.language,
            "continue_listening": args.listen
        }
        client.publish("temi/action/speak", json.dumps(payload), qos=1)
        client.disconnect()
        print(f"Success: Temi is speaking '{args.text}'")
    except Exception as e:
        print(f"Error connecting to MQTT Broker at {args.broker}: {e}")

if __name__ == "__main__":
    main()
