import asyncio
import json
import logging
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from asyncua import Client

# --- Settings ---
OPCUA_URL = "opc.tcp://localhost:4840/kaizen/"
NAMESPACE = "http://kaizen-matrix.example/line1"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
BASE_TOPIC = "kaizen/plant1/bottling/line1/filler"
STATUS_TOPIC = f"{BASE_TOPIC}/bridge_status"
RETRY_SECONDS = 5

TAGS = {
    "Temperature": "degC",
    "Speed": "bottles_per_min",
    "Status": "",
}

# --- Logging: every line gets a time and a level ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("bridge")
logging.getLogger("asyncua").setLevel(logging.ERROR)  # hide the library's own chatter


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def publish_status(mqtt_client, status):
    """Pin the bridge status in the group chat (retain=True)."""
    message = {"timestamp": now_utc(), "value": status}
    mqtt_client.publish(STATUS_TOPIC, json.dumps(message), retain=True)


async def run_bridge(mqtt_client):
    """Connect to the machine and forward data until something goes wrong."""
    async with Client(url=OPCUA_URL) as opc:
        idx = await opc.get_namespace_index(NAMESPACE)

        nodes = {}
        for tag in TAGS:
            nodes[tag] = await opc.nodes.objects.get_child([f"{idx}:Filler", f"{idx}:{tag}"])

        log.info("Connected to machine at %s", OPCUA_URL)
        publish_status(mqtt_client, "online")

        while True:
            values = {}
            for tag, node in nodes.items():
                value = await node.read_value()
                values[tag] = value

                message = {"timestamp": now_utc(), "value": value, "unit": TAGS[tag]}
                mqtt_client.publish(f"{BASE_TOPIC}/{tag.lower()}", json.dumps(message))

            log.info("Forwarded: %s", values)
            await asyncio.sleep(1)


async def main():
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="opcua-bridge")
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()

    try:
        # The retry loop: if anything goes wrong, wait and try again. Forever.
        while True:
            try:
                await run_bridge(mqtt_client)
            except Exception as error:
                log.warning("Machine connection lost: %r", error)
                publish_status(mqtt_client, "offline")
                log.info("Retrying in %s seconds...", RETRY_SECONDS)
                await asyncio.sleep(RETRY_SECONDS)
    finally:
        publish_status(mqtt_client, "offline")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bridge stopped by user.")