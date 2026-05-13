import argparse
import json
import paho.mqtt.client as mqtt

def main():
    parser = argparse.ArgumentParser(description="Temi Navigate Action")
    parser.add_argument("--target", required=True, help="Target location (e.g. kitchen, living_room)")
    parser.add_argument("--broker", default="127.0.0.1", help="MQTT Broker IP")
    args = parser.parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "hermes-skill-navigate")
    try:
        client.connect(args.broker, 1883, 60)
        payload = {
            "target_location": args.target
        }
        client.publish("temi/action/navigate", json.dumps(payload), qos=1)
        client.disconnect()
        print(f"Success: Temi is navigating to '{args.target}'")
    except Exception as e:
        print(f"Error connecting to MQTT Broker at {args.broker}: {e}")

if __name__ == "__main__":
    main()
