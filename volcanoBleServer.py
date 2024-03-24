import socket
import asyncio
import argparse
import struct
import time
import sys
from bleak import BleakClient

class AsyncServer:
    def __init__(self, turnFanOnWhenConnected, host='127.0.0.1', port=65432, bt_device_address="XX:XX:XX:XX:XX:XX", initialTemp=None):
        self.host = host
        self.port = port
        self.bt_device_address = bt_device_address
        self.initialTemp = initialTemp
        self.fanOn = None
        self.heatOn = None
        self.bt_client = None
        self.server_task = None
        self.fan_off_timer_task = None
        self.heatOnUuid = "1011000f-5354-4f52-5a26-4249434b454c"
        self.heatOffUuid = "10110010-5354-4f52-5a26-4249434b454c"
        self.fanOnUuid = "10110013-5354-4f52-5a26-4249434b454c"
        self.fanOffUuid = "10110014-5354-4f52-5a26-4249434b454c"
        self.screenBrightnessUuid = "10110005-5354-4f52-5a26-4249434b454c"
        self.targetTempUuid = "10110003-5354-4f52-5a26-4249434b454c"
        self.registerOneUuid = "1010000c-5354-4f52-5a26-4249434b454c"
        self.turnFanOnWhenConnected = turnFanOnWhenConnected
        self.fanOnTime = None

    async def connect_bluetooth_device(self):
        def notification_handler(sender, data):
            """Callback for when a notification is received from the BLE device."""
            print(f"Notification from {sender}: {data}")
            decodedValue = data[0] + (data[1] * 256)
            unmaskedFanOnValue = decodedValue & 0x2000
            unmaskedHeatOnValue = decodedValue & 0x0020
            self.heatOn = unmaskedHeatOnValue != 0
            self.fanOn = unmaskedFanOnValue != 0

        self.bt_client = BleakClient(self.bt_device_address)
        try:
            await self.bt_client.connect()
            value = await self.bt_client.read_gatt_char(self.registerOneUuid)
            decodedValue = value[0] + (value[1] * 256)
            unmaskedFanOnValue = decodedValue & 0x2000
            unmaskedHeatOnValue = decodedValue & 0x0020
            self.heatOn = unmaskedHeatOnValue != 0
            self.fanOn = unmaskedFanOnValue != 0
            
            await self.bt_client.start_notify(self.registerOneUuid, notification_handler)
            if self.turnFanOnWhenConnected == True:
                await self.bt_client.write_gatt_char(self.fanOnUuid, bytes([0]))

            if self.initialTemp:
                print("Writing initial temp")
                buffer = struct.pack('<I', self.initialTemp * 10)
                await self.bt_client.write_gatt_char(self.targetTempUuid, buffer)

            print(f"Connected to Bluetooth device at {self.bt_device_address}")
        except Exception as e:
            print(f"Failed to connect to the Bluetooth device: {e}")
            sys.exit("Failed to connect to the Bluetooth device")

    async def shutdown(self, delay):
        await asyncio.sleep(delay)  # Wait for specified delay (in seconds)
        if self.server_task is not None:
            await self.bt_client.stop_notify(self.registerOneUuid)
            self.server_task.cancel()
            print("Server has been shut down after the delay.")

    async def write_gatt_char_with_delay(self, delay, char_uuid, data, turnHeatOff, turnOffScreen):
        await asyncio.sleep(delay)
        await self.bt_client.write_gatt_char(char_uuid, data)
        if turnHeatOff:
             await self.bt_client.write_gatt_char(self.heatOffUuid, bytes([0]))
        if turnOffScreen:
             await self.bt_client.write_gatt_char(self.screenBrightnessUuid,  struct.pack('<H', 0))

    async def onFanOffTimer(self, timeOn, turnOffHeat, turnOffScreen):
        await self.bt_client.write_gatt_char(self.fanOnUuid, bytes([0]))
        # Cancel the existing task if it's still running
        if self.fan_off_timer_task and not self.fan_off_timer_task.done():
            self.fan_off_timer_task.cancel()
            print("Cancelled the existing timer task.")
        
        # Schedule the new task
        self.fan_off_timer_task = asyncio.create_task(
            self.write_gatt_char_with_delay(timeOn, self.fanOffUuid, bytes([0]), turnOffHeat, turnOffScreen)
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
                await self.bt_client.write_gatt_char(self.heatOnUuid, bytes([0]))
            elif message == "HeatOff":
                await self.bt_client.write_gatt_char(self.heatOffUuid, bytes([0]))
            elif message == "FanOn":
                await self.bt_client.write_gatt_char(self.fanOnUuid, bytes([0]))
            elif message.startswith("SetBrightness"):
                parts = message.split("=")
                brightness = int(parts[1])  # Convert the right part to integer
                await self.bt_client.write_gatt_char(self.screenBrightnessUuid,  struct.pack('<H', brightness))
            elif message == "NextSesh":
                value = await self.bt_client.read_gatt_char(self.targetTempUuid)
                decodedValue = value[0] + (value[1] * 256)
                normalizedValue = round(decodedValue / 10)
                print(normalizedValue)
                if normalizedValue == 185:
                    await self.bt_client.write_gatt_char(self.targetTempUuid, struct.pack('<I', 1900))
                elif normalizedValue == 190:
                    await self.bt_client.write_gatt_char(self.targetTempUuid, struct.pack('<I', 1950))
                elif normalizedValue == 195:
                    await self.bt_client.write_gatt_char(self.targetTempUuid, struct.pack('<I', 2000))
                elif normalizedValue == 200:
                    await self.bt_client.write_gatt_char(self.targetTempUuid, struct.pack('<I', 1850))
                else:
                    await self.bt_client.write_gatt_char(self.targetTempUuid, struct.pack('<I', 1850))

                await self.bt_client.write_gatt_char(self.heatOnUuid, bytes([0]))
            elif message == "FanOff":
                await self.bt_client.write_gatt_char(self.fanOffUuid, bytes([0]))
            elif message.startswith("FanOffTimer"):
                parts = message.split("=")
                timeOn = float(parts[1])  # Convert the right part to integer
                turnOffHeat = "HeatOff" in parts[0]
                turnOffScreen = "ScreenOff" in parts[0]
                await self.onFanOffTimer(timeOn, turnOffHeat, turnOffScreen)

            elif message == "HeatToggle": 
                print(self.heatOn)
                heatChar = self.heatOnUuid
                print(f"self heat on: {self.heatOn}")
                if self.heatOn:
                    heatChar = self.heatOffUuid
                
                await self.bt_client.write_gatt_char(heatChar, bytes([0]))
                self.heatOn = not self.heatOn
                data = f"Heat on: {self.heatOn}".encode('utf-8')
            elif message == "FanToggle":
                fanChar = self.fanOnUuid
                print(f"self fan on: {self.fanOn}")
                if self.fanOn:
                    fanChar = self.fanOffUuid

                await self.bt_client.write_gatt_char(fanChar, bytes([0]))
                self.fanOn = not self.fanOn
            elif message.startswith("Temp="):
                parts = message.split("=")
                temp_value = int(parts[1])  # Convert the right part to integer
                buffer = struct.pack('<I', temp_value * 10)
                await self.bt_client.write_gatt_char(self.targetTempUuid, buffer)
                await self.bt_client.write_gatt_char(self.heatOnUuid, bytes([0]))
            elif message.startswith("Disconnect"):
                await self.bt_client.write_gatt_char(self.heatOffUuid, bytes([0]))
                await self.bt_client.write_gatt_char(self.fanOffUuid, bytes([0]))
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
        await self.server_task
        
        """ x = 1
        increment = True
        while True:
            if increment:
                x += 1
            else:
                x -= 1

            if x == 15:
                increment = False
            elif x == 0:
                increment = True

            brightness = x
            print(brightness)
            await self.bt_client.write_gatt_char(self.screenBrightnessUuid,  struct.pack('<H', brightness))
            if 0 <= x <=15:
                time.sleep(0.3)
            if 16 <=x <= 70 :
                time.sleep(0.05)
            if 71 <= x <=100:
                time.sleep(0.05) """

        #await self.shutdown(18000) #5 hours

# To run the server and connect to the Bluetooth device
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Send a message to a TCP server.')
    parser.add_argument('--initTemp', type=int, help='Message to send', default=None)
    parser.add_argument('--FanOn', type=bool, help='Turn fan on', default=False)
    parser.add_argument('--BleMacAddress', type=str, help='Mac address of your Volcano', default="XX:XX:XX:XX:XX:XX")
    args = parser.parse_args()
    server = AsyncServer(args.FanOn, bt_device_address=args.BleMacAddress, initialTemp=args.initTemp)  # Replace with your device's address
    asyncio.run(server.run())