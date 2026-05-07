import json
import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883
TOPIC_NAVIGATE = "temi/action/navigate"

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT Broker!")
        
        # Test Payload
        payload = {
            "target_location": "home base"
        }
        
        print(f"Publishing to {TOPIC_NAVIGATE}: {payload}")
        client.publish(TOPIC_NAVIGATE, json.dumps(payload), qos=1)
        print("Message sent! Temi should start navigating to 'home base' or say that it doesn't exist.")
    else:
        print(f"Failed to connect, return code {reason_code}")

if __name__ == "__main__":
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "pc-tester-nav")
    client.on_connect = on_connect
    
    try:
        print(f"Connecting to {BROKER}:{PORT}...")
        client.connect(BROKER, PORT, 60)
        client.loop_start()
        
        # Keep alive for a bit to ensure message is sent
        import time
        time.sleep(2)
        client.loop_stop()
        client.disconnect()
        
    except ConnectionRefusedError:
        print("ERROR: Connection Refused. Is Mosquitto Broker running on 127.0.0.1:1883?")
