@echo off
python C:\full\path\to\volcanoClient.py FanOffTimer=36

if %ERRORLEVEL% equ 0 (
    echo Script executed successfully.
) else (
    python C:\full\path\to\volcanoBleServer.py --FanOn=True --FanOnTime=36
)