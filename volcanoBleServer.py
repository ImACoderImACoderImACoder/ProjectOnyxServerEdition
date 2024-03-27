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
        self.screenAnimationTask = None
        self.heatOnUuid = "1011000f-5354-4f52-5a26-4249434b454c"
        self.heatOffUuid = "10110010-5354-4f52-5a26-4249434b454c"
        self.fanOnUuid = "10110013-5354-4f52-5a26-4249434b454c"
        self.fanOffUuid = "10110014-5354-4f52-5a26-4249434b454c"
        self.screenBrightnessUuid = "10110005-5354-4f52-5a26-4249434b454c"
        self.targetTempUuid = "10110003-5354-4f52-5a26-4249434b454c"
        self.registerOneUuid = "1010000c-5354-4f52-5a26-4249434b454c"
        self.turnFanOnWhenConnected = turnFanOnWhenConnected
        self.fanOnTime = None
        self.isAnimating = False

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
            notification_handler("connect_bluetooth_device", value)
            
            await self.bt_client.start_notify(self.registerOneUuid, notification_handler)
            if self.turnFanOnWhenConnected == True:
                await self.turnFanOn()

            if self.initialTemp:
                await self.writeTargetTemperature(self.initialTemp)

            print(f"Connected to Bluetooth device at {self.bt_device_address}")
        except Exception as e:
            print(f"Failed to connect to the Bluetooth device: {e}")
            sys.exit("Failed to connect to the Bluetooth device")

    async def turnHeatOn(self):
        await self.bt_client.write_gatt_char(self.heatOnUuid, bytes([0]))
        self.heatOn = True

    async def turnHeatOff(self):
        await self.bt_client.write_gatt_char(self.heatOffUuid, bytes([0]))
        self.heatOn = False

    async def turnFanOn(self):
        await self.bt_client.write_gatt_char(self.fanOnUuid, bytes([0]))
        self.fanOn = True

    async def turnFanOff(self):
        await self.bt_client.write_gatt_char(self.fanOffUuid, bytes([0]))
        self.fanOn = False

    async def setBrightness(self, brightness):
        await self.bt_client.write_gatt_char(self.screenBrightnessUuid,  struct.pack('<H', brightness))

    async def writeTargetTemperature(self, targetTemperatureInC):
        await self.bt_client.write_gatt_char(self.targetTempUuid, struct.pack('<I', targetTemperatureInC * 10))

    async def readTargetTemperature(self):
        value = await self.bt_client.read_gatt_char(self.targetTempUuid)
        decodedValue = value[0] + (value[1] * 256)
        return round(decodedValue / 10)
    
    async def shutdown(self, delay):
        await asyncio.sleep(delay)  # Wait for specified delay (in seconds)
        if self.server_task is not None:
            await self.bt_client.stop_notify(self.registerOneUuid)
            if self.fan_off_timer_task is not None and not self.fan_off_timer_task.done():
                self.fan_off_timer_task.cancel()
            if self.screenAnimationTask is not None and not self.screenAnimationTask.done():
                self.isAnimating = False
                while not self.screenAnimationTask.done():
                    await asyncio.sleep(0.1)

            self.server_task.cancel()
            print("Server has been shut down after the delay.")

    async def write_gatt_char_with_delay(self, message):
        parts = message.split("=")
        timeOn = float(parts[1])
        turnOffHeat = "HeatOff" in parts[0]
        turnOffScreen = "ScreenOff" in parts[0]
        await asyncio.sleep(timeOn)
        await self.turnFanOff()
        if turnOffHeat:
             await self.turnHeatOff()
        if turnOffScreen:
             await self.setBrightness(0)
        if "Animate" in message:
            await self.screenAnimationTaskScheduler(message)

    async def AnimateVolcano(self, animationMessage):
        self.isAnimating = True
        MIN_BRIGHTNESS, MAX_BRIGHTNESS, interval = 0, 100, 8
        brightness = MIN_BRIGHTNESS
        increment = True

        while self.isAnimating:
            if "Blinking" in animationMessage:
                brightness = 0 if brightness == 100 else 100
                await asyncio.sleep(0.5)
            elif "Breathing" in animationMessage:
                brightness += interval if increment else -interval
                increment = not increment if brightness in [min(MIN_BRIGHTNESS,brightness), max(MAX_BRIGHTNESS, brightness)] else increment
                brightness = min(max(brightness, MIN_BRIGHTNESS), MAX_BRIGHTNESS)
                await asyncio.sleep(0.1)
            elif "Ascending" in animationMessage:
                if brightness >= MAX_BRIGHTNESS:
                    brightness = -interval
                brightness = min(interval+brightness,MAX_BRIGHTNESS)
                await asyncio.sleep(0.1)
            elif "Descending" in animationMessage:
                if brightness <= MIN_BRIGHTNESS:
                    brightness = MAX_BRIGHTNESS+interval
                brightness = max(brightness-interval, MIN_BRIGHTNESS)
                await asyncio.sleep(0.1)
            else:
                break

            await self.setBrightness(brightness)

        await self.setBrightness(70)  # Reset brightness to 70 when animation stops

    async def screenAnimationTaskScheduler(self, animationMessage):
        if self.screenAnimationTask and not self.screenAnimationTask.done():
            self.isAnimating = False
            #waiting to let the ble commands finish.
            #This effectively cancels the task since I know the implementation and that it can exit very quickly.  
            #This is a friendly way to 'cancel' the task and prevents us from experiencing errors from the windows ble api
            while not self.screenAnimationTask.done():
                await asyncio.sleep(0.01)
            print("Cancelled the existing animation task.")

        # Schedule the new task
        if "True" in animationMessage:
            self.screenAnimationTask = asyncio.create_task(
                self.AnimateVolcano(animationMessage)
            )
    async def onFanOffTimer(self, message):
        await self.turnFanOn()
        # Cancel the existing task if it's still running
        if self.fan_off_timer_task and not self.fan_off_timer_task.done():
            self.fan_off_timer_task.cancel()
            print("Cancelled the existing timer task.")
        
        # Schedule the new task
        self.fan_off_timer_task = asyncio.create_task(
            self.write_gatt_char_with_delay(message)
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
                await self.turnHeatOn()
            elif message == "HeatOff":
                await self.turnHeatOff()
            elif message == "FanOn":
                await self.turnFanOn()
            elif message.startswith("SetBrightness"):
                parts = message.split("=")
                brightness = int(parts[1])
                await self.setBrightness(brightness)
            elif message == "NextSesh":
                nextTemp = await self.readTargetTemperature() + 5
                if nextTemp not in (185,190,195,200):
                    nextTemp = 185

                await self.writeTargetTemperature(nextTemp)
                await self.turnHeatOn()
            elif message == "FanOff":
                await self.turnFanOff()
            elif message.startswith("Animate"):
                await self.screenAnimationTaskScheduler(message)
            elif message.startswith("FanOffTimer"):
                await self.onFanOffTimer(message)
            elif message == "HeatToggle": 
                await self.turnHeatOff() if self.heatOn else await self.turnHeatOn()
                data = f"Heat on: {self.heatOn}".encode('utf-8')
            elif message == "FanToggle":
                await self.turnFanOff() if self.fanOn else await self.turnFanOn()
                data = f"Fan on: {self.fanOn}".encode('utf-8')
            elif message.startswith("Temp="):
                parts = message.split("=")
                nextTemp = int(parts[1])
                await self.writeTargetTemperature(nextTemp)
                await self.turnHeatOn()
            elif message.startswith("Disconnect"):
                await self.turnHeatOff()
                await self.turnFanOff()
                if self.server_task is not None:
                    self.server_task.cancel()
                sys.exit("Disconnect command received, closing server")

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
        #await self.shutdown(18000) #5 hours

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Send a message to a TCP server.')
    parser.add_argument('--initTemp', type=int, help='Message to send', default=None)
    parser.add_argument('--FanOn', type=bool, help='Turn fan on', default=False)
    parser.add_argument('--BleMacAddress', type=str, help='Mac address of your Volcano', default="XX:XX:XX:XX:XX:XX")
    args = parser.parse_args()
    server = AsyncServer(args.FanOn, bt_device_address=args.BleMacAddress, initialTemp=args.initTemp)
    asyncio.run(server.run())