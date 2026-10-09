import asyncio
import json
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from asyncua import Client

# --- Settings ---
OPCUA_URL = "opc.tcp://localhost:4840/kaizen/"          # the machine's "phone number"
NAMESPACE = "http://kaizen-matrix.example/line1"        # the machine's "family name"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
BASE_TOPIC = "kaizen/plant1/bottling/line1/filler"      # the Unified Namespace address

# Which values to read, and their units
TAGS = {
    "Temperature": "degC",
    "Speed": "bottles_per_min",
    "Status": "",
}


async def main():
    # --- 1. Join the MQTT group chat ---
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="opcua-bridge")
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()

    try:
        # --- 2. Phone the machine ---
        async with Client(url=OPCUA_URL) as opc:
            idx = await opc.get_namespace_index(NAMESPACE)

            # Find each value in the machine's folder structure: Filler → Temperature, etc.
            nodes = {}
            for tag in TAGS:
                nodes[tag] = await opc.nodes.objects.get_child([f"{idx}:Filler", f"{idx}:{tag}"])

            print("Bridge connected: OPC UA → MQTT. Press Ctrl+C to stop.")

            # --- 3. Every second: read from the machine, post to MQTT ---
            while True:
                for tag, node in nodes.items():
                    value = await node.read_value()

                    message = {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "value": value,
                        "unit": TAGS[tag],
                    }
                    topic = f"{BASE_TOPIC}/{tag.lower()}"
                    mqtt_client.publish(topic, json.dumps(message))
                    print(f"{topic} → {value}")

                await asyncio.sleep(1)

    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bridge stopped.")