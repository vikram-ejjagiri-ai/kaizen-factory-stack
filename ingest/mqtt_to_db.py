import json
import logging
import os
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt
import psycopg
import yaml
from dotenv import load_dotenv

# --- Load settings ---
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")   # reads the secret settings from .env
CONFIG = yaml.safe_load((ROOT / "config" / "line1.yaml").read_text(encoding="utf-8"))
SUBSCRIBE_TOPIC = CONFIG["line"]["base_topic"] + "/#"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("ingest")

# --- Connect to the database (open the diary) ---
db = psycopg.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    autocommit=True,   # save each line immediately
)
log.info("Connected to database '%s'", os.getenv("DB_NAME"))

saved = {"count": 0}


def on_connect(client, userdata, flags, reason_code, properties):
    """Doorbell 1: runs every time we (re)connect to the broker."""
    log.info("Connected to MQTT broker, subscribing to %s", SUBSCRIBE_TOPIC)
    # Subscribing here means: if the broker restarts, we subscribe again automatically
    client.subscribe(SUBSCRIBE_TOPIC)


def on_message(client, userdata, msg):
    """Doorbell 2: runs for every single message."""
    # Topic example: kaizen/plant1/bottling/line1/pump/vibration
    parts = msg.topic.split("/")
    machine, sensor = parts[-2], parts[-1]

    if sensor == "bridge_status":   # not machine data, skip it
        return

    try:
        data = json.loads(msg.payload)
        timestamp = datetime.fromisoformat(data["timestamp"])

        if sensor == "status":
            db.execute(
                "INSERT INTO machine_status (time, machine, status) VALUES (%s, %s, %s)",
                (timestamp, machine, data["value"]),
            )
        else:
            db.execute(
                "INSERT INTO sensor_readings (time, machine, sensor, value, unit) "
                "VALUES (%s, %s, %s, %s, %s)",
                (timestamp, machine, sensor, float(data["value"]), data.get("unit")),
            )

        saved["count"] += 1
        if saved["count"] % 100 == 0:   # report every 100 rows, not every row
            log.info("Saved %d rows so far", saved["count"])

    except Exception as error:
        # One bad message must never stop the whole service
        log.warning("Skipped bad message on %s: %r", msg.topic, error)


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="db-ingest")
    client.on_connect = on_connect     # install doorbell 1
    client.on_message = on_message     # install doorbell 2
    client.connect("localhost", 1883)

    try:
        client.loop_forever()          # wait for doorbells, forever
    except KeyboardInterrupt:
        log.info("Ingest stopped by user.")
    finally:
        db.close()


if __name__ == "__main__":
    main()