import json
import time
import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883
TOPIC_SPEAK = "temi/action/speak"

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT Broker!")
        
        # Test TTS payload
        payload = {
            "text": "你好，我是你的具身智能助理，很高興為你服務。",
            "language": "ZH_TW",
            "continue_listening": False
        }
        
        print(f"Publishing to {TOPIC_SPEAK}: {payload}")
        client.publish(TOPIC_SPEAK, json.dumps(payload), qos=1)
        print("Message sent! You should hear Temi speaking.")
    else:
        print(f"Failed to connect, return code {reason_code}")

if __name__ == "__main__":
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "pc-tester-tts")
    client.on_connect = on_connect
    
    try:
        print(f"Connecting to {BROKER}:{PORT}...")
        client.connect(BROKER, PORT, 60)
        client.loop_start()
        time.sleep(3) # Wait for message to be sent
        client.loop_stop()
        client.disconnect()
    except ConnectionRefusedError:
        print("ERROR: Connection Refused. Is Mosquitto Broker running on 127.0.0.1:1883?")
