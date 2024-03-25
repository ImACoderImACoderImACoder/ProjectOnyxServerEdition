@echo off
python C:\full\path\to\volcanoClient.py Temp=200

if %ERRORLEVEL% equ 0 (
    echo Script executed successfully.
) else (
    python C:\full\path\to\volcanoBleServer.py --initTemp=200
)