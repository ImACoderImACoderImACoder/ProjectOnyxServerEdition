import socket
import asyncio
import argparse
import struct
import sys
from bleak import BleakClient

class AsyncServer:
    def __init__(self, turnFanOnWhenConnected, fanOnTime, host='127.0.0.1', port=65432, bt_device_address="XX:XX:XX:XX:XX:XX", initialTemp=None):
        self.host = host
        self.port = port
        self.bt_device_address = bt_device_address
        self.initialTemp = initialTemp
        self.fanOn = None
        self.bt_client = None
        self.server_task = None
        self.fan_off_timer_task = None
        self.turnFanOnWhenConnected = turnFanOnWhenConnected
        self.fanOnTime = fanOnTime

    async def connect_bluetooth_device(self):
        self.bt_client = BleakClient(self.bt_device_address)
        try:
            await self.bt_client.connect()
            if self.turnFanOnWhenConnected == True:
                if self.fanOnTime > 0:
                    await self.onFanOffTimer(self.fanOnTime)
                else:
                    await self.bt_client.write_gatt_char("10110013-5354-4f52-5a26-4249434b454c", bytes([0]))
            if not self.initialTemp:
                return
            print("Writing initial temp")
            buffer = struct.pack('<I', self.initialTemp * 10)
            await self.bt_client.write_gatt_char("10110003-5354-4f52-5a26-4249434b454c", buffer)

            print(f"Connected to Bluetooth device at {self.bt_device_address}")
        except Exception as e:
            print(f"Failed to connect to the Bluetooth device: {e}")
            sys.exit("Failed to connect to the Bluetooth device")

    async def shutdown(self, delay):
        await asyncio.sleep(delay)  # Wait for specified delay (in seconds)
        if self.server_task is not None:
            self.server_task.cancel()
            print("Server has been shut down after the delay.")

    async def write_gatt_char_with_delay(self, delay, char_uuid, data):
        await asyncio.sleep(delay)
        await self.bt_client.write_gatt_char(char_uuid, data)

    async def onFanOffTimer(self, timeOn):
        await self.bt_client.write_gatt_char("10110013-5354-4f52-5a26-4249434b454c", bytes([0]))
        # Cancel the existing task if it's still running
        if self.fan_off_timer_task and not self.fan_off_timer_task.done():
            self.fan_off_timer_task.cancel()
            print("Cancelled the existing timer task.")
        
        # Schedule the new task
        self.fan_off_timer_task = asyncio.create_task(
            self.write_gatt_char_with_delay(timeOn, "10110014-5354-4f52-5a26-4249434b454c", bytes([0]))
        )
    async def handle_client(self, reader, writer):
        address = writer.get_extra_info('peername')
        print(f"Connected by {address}")
        while True:
            data = await reader.read(1024)
            if not data:
                break
            message = data.decode()
            print(f"Received {message} from {address}")
            if message == "HeatOn":
                await self.bt_client.write_gatt_char("1011000f-5354-4f52-5a26-4249434b454c", bytes([0]))
            elif message == "HeatOff":
                await self.bt_client.write_gatt_char("10110010-5354-4f52-5a26-4249434b454c", bytes([0]))
            elif message == "FanOn":
                await self.bt_client.write_gatt_char("10110013-5354-4f52-5a26-4249434b454c", bytes([0]))
            elif message == "FanOff":
                await self.bt_client.write_gatt_char("10110014-5354-4f52-5a26-4249434b454c", bytes([0]))
            elif message.startswith("FanOffTimer"):
                parts = message.split("=")
                timeOn = float(parts[1])  # Convert the right part to integer
                await self.onFanOffTimer(timeOn)

            elif message == "FanToggle":
                fanChar = "10110013-5354-4f52-5a26-4249434b454c"
                print(f"self fan on: {self.fanOn}")
                if self.fanOn == None:
                    self.fanOn = True
                    value = await self.bt_client.read_gatt_char("1010000c-5354-4f52-5a26-4249434b454c")
                    decodedValue = value[0] + (value[1] * 256)
                    unmaskedValue = decodedValue & 0x2000
                    if unmaskedValue != 0:
                        self.fanOn = False
                        fanChar = "10110014-5354-4f52-5a26-4249434b454c"
                else:
                    if self.fanOn:
                       fanChar = "10110013-5354-4f52-5a26-4249434b454c"
                    else:
                       fanChar = "10110014-5354-4f52-5a26-4249434b454c"
                await self.bt_client.write_gatt_char(fanChar, bytes([0]))
                self.fanOn = not self.fanOn
            elif message.startswith("Temp="):
                parts = message.split("=")
                temp_value = int(parts[1])  # Convert the right part to integer
                buffer = struct.pack('<I', temp_value * 10)
                await self.bt_client.write_gatt_char("10110003-5354-4f52-5a26-4249434b454c", buffer)
                await self.bt_client.write_gatt_char("1011000f-5354-4f52-5a26-4249434b454c", bytes([0]))
            elif message.startswith("Disconnect"):
                await self.bt_client.write_gatt_char("10110010-5354-4f52-5a26-4249434b454c", bytes([0]))
                await self.bt_client.write_gatt_char("10110014-5354-4f52-5a26-4249434b454c", bytes([0]))
                if self.server_task is not None:
                    self.server_task.cancel()

                sys.exit("Disconnect command recieved, closing server")
            writer.write(data)
            await writer.drain()
        print("Closing connection")
        writer.close()

    async def run_server(self):
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        addr = server.sockets[0].getsockname()
        print(f"Serving on {addr}")

        async with server:
            await server.serve_forever()

    async def run(self):
        await self.connect_bluetooth_device()
        self.server_task = asyncio.create_task(self.run_server())
        await self.shutdown(18000) #5 hours

# To run the server and connect to the Bluetooth device
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Send a message to a TCP server.')
    parser.add_argument('--initTemp', type=int, help='Message to send', default=None)
    parser.add_argument('--FanOn', type=bool, help='Turn fan on', default=False)
    parser.add_argument('--FanOnTime', type=float, help='Optional time to keep fan on', default=0)
    args = parser.parse_args()
    server = AsyncServer(args.FanOn, args.FanOnTime, bt_device_address="XX:XX:XX:XX:XX:XX", initialTemp=args.initTemp)  # Replace with your device's address
    asyncio.run(server.run())
