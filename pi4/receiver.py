#!/usr/bin/env python3
import serial
import time
import csv
from datetime import datetime
import os

PORT = "/dev/serial0"
BAUD = 115200
LOG_FILE = "telemetry_log.csv"

CSV_HEADER = [
    "host_time",
    "t_s",
    "voltage_v",
    "pot_voltage_v",
    "pot_percent",
    "pwm_pct",
    "pwm_freq_hz"
]

def ensure_csv_header(filename):
    """
    Create the CSV header only if the file does not already exist
    or is empty.
    """
    write_header = not os.path.exists(filename) or os.path.getsize(filename) == 0

    f = open(filename, "a", newline="")
    writer = csv.writer(f)

    if write_header:
        writer.writerow(CSV_HEADER)
        f.flush()

    return f, writer

def main():
    ser = serial.Serial(PORT, BAUD, timeout=1)
    print(f"Listening on {PORT} at {BAUD} baud...")

    f, writer = ensure_csv_header(LOG_FILE)

    try:
        while True:
            try:
                line = ser.readline().decode("utf-8", errors="replace").strip()

                if not line:
                    continue

                # Ignore STM32 comment/banner lines
                if line.startswith("#"):
                    print(line)
                    continue

                # Ignore STM32 CSV header line
                if line.startswith("t_s"):
                    print("Header received")
                    continue

                parts = line.split(",")

                # New STM32 format:
                # t_s,voltage_v,pot_voltage_v,pot_percent,pwm_pct,pwm_freq_hz
                if len(parts) != 6:
                    print(f"Bad line: {line}")
                    continue

                t_s = float(parts[0])
                voltage_v = float(parts[1])
                pot_voltage_v = float(parts[2])
                pot_percent = float(parts[3])
                pwm_pct = float(parts[4])
                pwm_freq_hz = int(parts[5])

                host_time = datetime.now().isoformat()

                print(
                    f"[{host_time}] "
                    f"t={t_s:.2f}s | "
                    f"V={voltage_v:.3f}V | "
                    f"Pot={pot_voltage_v:.3f}V | "
                    f"Pot%={pot_percent:.1f}% | "
                    f"PWM={pwm_pct:.1f}% | "
                    f"F={pwm_freq_hz}Hz"
                )

                writer.writerow([
                    host_time,
                    t_s,
                    voltage_v,
                    pot_voltage_v,
                    pot_percent,
                    pwm_pct,
                    pwm_freq_hz
                ])
                f.flush()

            except KeyboardInterrupt:
                print("\nExiting...")
                break

            except ValueError:
                print(f"Parse error: {line}")
                time.sleep(0.1)

            except Exception as e:
                print(f"Error: {e}")
                time.sleep(0.5)

    finally:
        f.close()
        ser.close()

if __name__ == "__main__":
    main()
