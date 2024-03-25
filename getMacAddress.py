import asyncio
from bleak import BleakScanner

async def run():
    devices = await BleakScanner.discover()
    for device in devices:
        # Check if device.name is not None before looking for "VOLCANO" in it
        if device.name and "VOLCANO" in device.name.upper():
            print(f"Found VOLCANO device: {device.name}, MAC Address: {device.address}")
            # If you wish to connect, additional code using BleakClient would go here.
            break
    else:
        print("No VOLCANO device found.")

# Use asyncio.run() which is the recommended way to run asyncio programs from Python 3.7+
if __name__ == "__main__":
    asyncio.run(run())
