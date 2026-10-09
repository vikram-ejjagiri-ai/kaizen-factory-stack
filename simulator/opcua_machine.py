import asyncio
import random
from pathlib import Path

import yaml
from asyncua import Server

# Find config/line1.yaml, no matter which folder we start the program from
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "line1.yaml"
CONFIG = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


async def main():
    server = Server()
    await server.init()
    server.set_endpoint(CONFIG["line"]["opcua_url"])
    server.set_server_name("Kaizen Line 1 Simulator")
    idx = await server.register_namespace(CONFIG["line"]["namespace"])

    # Build one folder per machine, with its sensors inside
    sensors = []
    for machine_name, machine_sensors in CONFIG["machines"].items():
        machine = await server.nodes.objects.add_object(idx, machine_name)
        await machine.add_variable(idx, "Status", "Running")

        for sensor_name, settings in machine_sensors.items():
            node = await machine.add_variable(idx, sensor_name, float(settings["start"]))
            sensors.append({
                "label": f"{machine_name}.{sensor_name}",
                "node": node,
                "true_value": float(settings["start"]),
                "noise": settings["noise"],
                "drift": settings["drift"],
            })

    print(f"Simulating {len(CONFIG['machines'])} machines, {len(sensors)} sensors.")
    print("Press Ctrl+C to stop.")

    async with server:
        while True:
            readings = []
            for s in sensors:
                s["true_value"] += s["drift"]                               # slow wear
                reading = s["true_value"] + random.gauss(0, s["noise"])     # + sensor noise
                await s["node"].write_value(round(reading, 3))
                readings.append(f"{s['label']}={reading:.2f}")

            print(" | ".join(readings))
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Simulator stopped.")