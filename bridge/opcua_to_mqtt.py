import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
import yaml
from asyncua import Client

# --- Settings from the config file ---
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "line1.yaml"
CONFIG = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

OPCUA_URL = CONFIG["line"]["opcua_url"]
NAMESPACE = CONFIG["line"]["namespace"]
BASE_TOPIC = CONFIG["line"]["base_topic"]
STATUS_TOPIC = f"{BASE_TOPIC}/bridge_status"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
RETRY_SECONDS = 5

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bridge")
logging.getLogger("asyncua").setLevel(logging.ERROR)


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def publish_status(mqtt_client, status):
    message = {"timestamp": now_utc(), "value": status}
    mqtt_client.publish(STATUS_TOPIC, json.dumps(message), retain=True)


async def run_bridge(mqtt_client):
    async with Client(url=OPCUA_URL) as opc:
        idx = await opc.get_namespace_index(NAMESPACE)

        # Build the list of all signals: (MQTT topic, OPC UA node, unit)
        signals = []
        for machine, sensors in CONFIG["machines"].items():
            tags = {"Status": ""}
            for sensor_name, settings in sensors.items():
                tags[sensor_name] = settings["unit"]

            for tag, unit in tags.items():
                node = await opc.nodes.objects.get_child([f"{idx}:{machine}", f"{idx}:{tag}"])
                topic = f"{BASE_TOPIC}/{machine.lower()}/{tag.lower()}"
                signals.append((topic, node, unit))

        log.info("Connected to machine. Forwarding %d signals.", len(signals))
        publish_status(mqtt_client, "online")

        while True:
            for topic, node, unit in signals:
                value = await node.read_value()
                message = {"timestamp": now_utc(), "value": value, "unit": unit}
                mqtt_client.publish(topic, json.dumps(message))

            log.info("Forwarded %d signals", len(signals))
            await asyncio.sleep(1)


async def main():
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="opcua-bridge")
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()

    try:
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