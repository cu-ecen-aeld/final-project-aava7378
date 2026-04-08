#!/usr/bin/env python3

# ============================================================
# Raspberry Pi UART Telemetry Logger
#
# This script listens to telemetry sent from the STM32 over UART,
# parses the CSV data, prints live values to the terminal, and
# logs everything to a CSV file for later analysis.
#
# Telemetry format expected from STM32:
# t_s,voltage_v,pot_voltage_v,pot_percent,pwm_pct,pwm_freq_hz
#
# Example:
# 1.234,2.500,1.650,50.0,50.0,1000
# ============================================================

import serial
import time
import csv
from datetime import datetime
import os

# ============================================================
# Serial port configuration
# ============================================================
PORT = "/dev/serial0"     # UART port connected to STM32
BAUD = 115200             # Must match STM32 UART baud rate

# CSV file used to log telemetry data
LOG_FILE = "telemetry_log.csv"

# CSV header written once when file is created
CSV_HEADER = [
    "host_time",       # Raspberry Pi timestamp
    "t_s",             # STM32 uptime (seconds)
    "voltage_v",       # Measured system voltage
    "pot_voltage_v",   # Potentiometer voltage
    "pot_percent",     # Potentiometer percentage (0–100%)
    "pwm_pct",         # PWM duty cycle (%)
    "pwm_freq_hz"      # PWM frequency (Hz)
]


# ============================================================
# Creates CSV file header if file does not already exist
# ============================================================
def ensure_csv_header(filename):
    """
    Create the CSV header only if the file does not already exist
    or is empty.

    This prevents duplicate headers if the script is restarted.
    """

    # Check if file is missing or empty
    write_header = not os.path.exists(filename) or os.path.getsize(filename) == 0

    # Open file in append mode
    f = open(filename, "a", newline="")
    writer = csv.writer(f)

    # Write header only once
    if write_header:
        writer.writerow(CSV_HEADER)
        f.flush()

    return f, writer


def main():
    """
    Main program loop:
    - Opens serial connection to STM32
    - Reads incoming telemetry lines
    - Ignores startup banner / headers
    - Parses numeric values
    - Prints live status to terminal
    - Logs data to CSV
    """

    # Open UART serial port
    ser = serial.Serial(PORT, BAUD, timeout=1)

    print(f"Listening on {PORT} at {BAUD} baud...")

    # Open CSV log file
    f, writer = ensure_csv_header(LOG_FILE)

    try:
        while True:
            try:
                # Read one line from UART
                line = ser.readline().decode("utf-8", errors="replace").strip()

                # Ignore empty lines
                if not line:
                    continue

                # Ignore STM32 banne
                if line.startswith("#"):
                    print(line)
                    continue

                # Ignore CSV header sent by STM32
                if line.startswith("t_s"):
                    print("Header received")
                    continue

                # Split CSV values into list
                parts = line.split(",")

                # Expected STM32 telemetry format:
                # t_s,voltage_v,pot_voltage_v,pot_percent,pwm_pct,pwm_freq_hz
                if len(parts) != 6:
                    print(f"Bad line: {line}")
                    continue

                # Parse incoming values
                t_s = float(parts[0])               # STM32 elapsed time
                voltage_v = float(parts[1])         # Fan Driver voltage
                pot_voltage_v = float(parts[2])     # Potentiometer voltage
                pot_percent = float(parts[3])       # Potentiometer %
                pwm_pct = float(parts[4])           # PWM duty %
                pwm_freq_hz = int(parts[5])         # PWM frequency

                # Raspberry Pi host timestamp
                host_time = datetime.now().isoformat()

                # Print live telemetry to terminal
                print(
                    f"[{host_time}] "
                    f"t={t_s:.2f}s | "
                    f"V={voltage_v:.3f}V | "
                    f"Pot={pot_voltage_v:.3f}V | "
                    f"Pot%={pot_percent:.1f}% | "
                    f"PWM={pwm_pct:.1f}% | "
                    f"F={pwm_freq_hz}Hz"
                )

                # Save telemetry row to CSV file
                writer.writerow([
                    host_time,
                    t_s,
                    voltage_v,
                    pot_voltage_v,
                    pot_percent,
                    pwm_pct,
                    pwm_freq_hz
                ])

                # Flush to disk immediately so data is not lost
                f.flush()

            except KeyboardInterrupt:
                print("\nExiting...")
                break

            except ValueError:
                # Handles parsing errors 
                print(f"Parse error: {line}")
                time.sleep(0.1)

            except Exception as e:
                # Handles UART disconnects / unexpected runtime issues
                print(f"Error: {e}")
                time.sleep(0.5)

    finally:
        # close resources cleanly on exit
        f.close()
        ser.close()

if __name__ == "__main__":
    main()
