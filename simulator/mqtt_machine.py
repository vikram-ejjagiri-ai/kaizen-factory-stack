import json
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

# --- Settings ---
BROKER = "localhost"   # the broker runs on this laptop
PORT = 1883            # the broker's "apartment number"
TOPIC = "kaizen/plant1/bottling/line1/filler/temperature"

# --- Connect to the broker (join the group chat) ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="filler-01")
client.connect(BROKER, PORT)
client.loop_start()    # handle network work in the background

temperature = 70.0     # the machine starts at 70 °C
print("Filling machine started. Press Ctrl+C to stop.")

try:
    while True:   # repeat forever, like a real machine
        # Real sensors are never perfectly steady: small random changes.
        # The machine also warms up slowly over time (a sign of wear).
        temperature += random.uniform(-0.3, 0.35)

        # Pack the reading as JSON: a labelled message
        message = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "value": round(temperature, 2),
            "unit": "degC",
        }

        client.publish(TOPIC, json.dumps(message))
        print(f"Sent: {message}")

        time.sleep(1)  # wait 1 second

except KeyboardInterrupt:   # this runs when you press Ctrl+C
    print("Machine stopped.")

finally:                    # always clean up before exiting
    client.loop_stop()
    client.disconnect()
    