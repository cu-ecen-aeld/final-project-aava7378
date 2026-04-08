# Raspberry Pi 4 Telemetry Receiver

This script receives UART telemetry from the STM32:

- Parses CSV data
- Prints formatted output
- Logs data to a CSV file

## Run

python3 receiver.py

## UART Settings

- Device: /dev/serial0
- Baud: 115200
