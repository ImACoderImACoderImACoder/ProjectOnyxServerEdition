# ProjectOnyxServerEdition

A full server client setup for controller your Volcano Hybrid written in Python

# Install Python 3.12.1 or another compatible version

https://www.python.org/downloads/

# Install Bleak before using the server

pip install bleak

# Get your mac address

go to the directory where you cloned this and run the script
py getMacAddress.py
this will give you your device mac address. use this in place of the XX:XX:XX:XX:XX:XX in the command below

# Run the server

py .\volcanoBleServer.py --BleMacAddress=XX:XX:XX:XX:XX:XX

# How to interact with the server

py volcanoClient.py [command]
py volcanoClient.py FanOn
py volcanoClient.py HeatOn
you can see how each of the bat files calls the client. If you use nssm (mentioned below) I recommend just use the bat files as passthroughs and remove the code to start the server.

# Optional Steps

get nssm and install open ssh in windows features
nssm allows you to easily install this code as a service. If you choose to use nssm the bat files can be simplified since they don't ever need to start the server

Using ssh will allow you to control with many devices such as shortcuts in ios and siri!

# Video Demo

https://www.tiktok.com/t/ZTL24gwcK/
