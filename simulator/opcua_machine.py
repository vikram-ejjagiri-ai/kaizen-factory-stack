import asyncio
import random

from asyncua import Server


async def main():
    # --- 1. Create the OPC UA server (our fake PLC) ---
    server = Server()
    await server.init()

    # The "phone number" where other programs can call this machine.
    # 4840 is the standard OPC UA port, like 1883 is for MQTT.
    server.set_endpoint("opc.tcp://localhost:4840/kaizen/")
    server.set_server_name("Kaizen Line 1 Simulator")

    # A namespace is like a family name, so our data
    # doesn't get mixed up with other companies' data.
    idx = await server.register_namespace("http://kaizen-matrix.example/line1")

    # --- 2. Build the folder structure ---
    filler = await server.nodes.objects.add_object(idx, "Filler")
    temperature = await filler.add_variable(idx, "Temperature", 70.0)
    speed = await filler.add_variable(idx, "Speed", 120.0)
    await filler.add_variable(idx, "Status", "Running")

    print("OPC UA machine running at opc.tcp://localhost:4840/kaizen/")
    print("Press Ctrl+C to stop.")

    # --- 3. Run the machine: update the values every second ---
    async with server:
        temp = 70.0
        while True:
            temp += random.uniform(-0.3, 0.35)        # slow warming, like wear
            spd = 120 + random.uniform(-3, 3)          # speed wobbles around 120

            await temperature.write_value(round(temp, 2))
            await speed.write_value(round(spd, 1))

            print(f"Temperature: {temp:.2f} °C | Speed: {spd:.1f} bottles/min")
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Machine stopped.")