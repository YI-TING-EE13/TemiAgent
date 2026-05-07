import json
import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883
TOPIC_ASR = "temi/event/asr"

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT Broker!")
        print(f"Subscribing to {TOPIC_ASR}...")
        client.subscribe(TOPIC_ASR)
        print("Waiting for Temi ASR results. Please say 'Hey Temi' followed by a command...")
    else:
        print(f"Failed to connect, return code {reason_code}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8')
        data = json.loads(payload)
        
        text = data.get("text", "")
        language = data.get("language", "UNKNOWN")
        timestamp = data.get("timestamp_ms", 0)
        
        print("\n--- [ASR Result Received] ---")
        print(f"Text      : {text}")
        print(f"Language  : {language}")
        print(f"Timestamp : {timestamp} ms")
        print("-----------------------------\n")
        
    except Exception as e:
        print(f"Error parsing message: {e}")
        print(f"Raw Payload: {msg.payload}")

if __name__ == "__main__":
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "pc-tester-asr")
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        print(f"Connecting to {BROKER}:{PORT}...")
        client.connect(BROKER, PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nDisconnecting...")
        client.disconnect()
    except ConnectionRefusedError:
        print("ERROR: Connection Refused. Is Mosquitto Broker running on 127.0.0.1:1883?")
