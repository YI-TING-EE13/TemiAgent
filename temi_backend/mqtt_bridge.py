"""
MQTT Bridge Module for TemiAgent.

This module encapsulates the Paho MQTT client to manage the low-latency
event-driven telemetry between the PC Backend and the Android robot client.
It abstracts the publish and subscribe logic for Speech and Navigation events.
"""

import json
import paho.mqtt.client as mqtt
import logging
from typing import Callable, Optional

class MqttBridge:
    """
    Manages MQTT connections and event dispatching for the Embodied AI framework.
    """

    def __init__(self, broker: str = "127.0.0.1", port: int = 1883):
        """
        Initialize the MQTT Bridge.

        Args:
            broker (str): The IP address of the Mosquitto MQTT Broker.
            port (int): The port of the MQTT Broker.
        """
        self.broker = broker
        self.port = port
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "temi-backend-brain")
        self.on_asr_callback: Optional[Callable[[dict], None]] = None
        
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def set_asr_callback(self, callback: Callable[[dict], None]) -> None:
        """
        Register a callback function to handle incoming ASR events.

        Args:
            callback (Callable[[dict], None]): The function to execute upon receiving an ASR payload.
        """
        self.on_asr_callback = callback

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        """Internal callback for when the client connects to the broker."""
        if reason_code == 0:
            logging.info("MqttBridge: Connected to Broker!")
            self.client.subscribe("temi/event/asr")
        else:
            logging.error(f"MqttBridge: Failed to connect, code {reason_code}")

    def _on_message(self, client, userdata, msg) -> None:
        """Internal callback for when a PUBLISH message is received from the server."""
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            if topic == "temi/event/asr" and self.on_asr_callback:
                self.on_asr_callback(payload)
        except Exception as e:
            logging.error(f"MqttBridge: Parse error on {topic}: {e}")

    def publish_speak(self, text: str, language: str = "ZH_TW", continue_listening: bool = False) -> None:
        """
        Dispatch a Text-to-Speech command to the robot.

        Args:
            text (str): The semantic content to be spoken.
            language (str): The language code (e.g., 'ZH_TW', 'EN_US').
            continue_listening (bool): If True, triggers the robot to enter ASR mode immediately after speaking.
        """
        payload = {
            "text": text,
            "language": language,
            "continue_listening": continue_listening
        }
        self.client.publish("temi/action/speak", json.dumps(payload), qos=1)
        logging.info(f"MqttBridge: Published speak -> {text}")

    def publish_navigate(self, target_location: str) -> None:
        """
        Dispatch a topological navigation command to the robot.

        Args:
            target_location (str): The predefined map location string (e.g., 'kitchen').
        """
        payload = {"target_location": target_location}
        self.client.publish("temi/action/navigate", json.dumps(payload), qos=1)
        logging.info(f"MqttBridge: Published navigate -> {target_location}")

    def start(self) -> None:
        """Connect to the MQTT broker and start the network loop in a background thread."""
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()

    def stop(self) -> None:
        """Stop the network loop and cleanly disconnect from the broker."""
        self.client.loop_stop()
        self.client.disconnect()
