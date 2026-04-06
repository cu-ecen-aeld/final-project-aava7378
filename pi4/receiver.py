#!/usr/bin/env python3
import serial
import time
import csv
from datetime import datetime

PORT = "/dev/serial0"
BAUD = 115200
LOG_FILE = "telemetry_log.csv"

def main():
    ser = serial.Serial(PORT, BAUD, timeout=1)
    print(f"Listening on {PORT} at {BAUD} baud...")

    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)

        # Write header once
        writer.writerow([
            "host_time",
            "t_s",
            "voltage_v",
            "current_a",
            "pwm_pct",
            "pwm_freq_hz"
        ])

        while True:
            try:
                line = ser.readline().decode("utf-8", errors="replace").strip()

                if not line:
                    continue

                # Ignore comments/header from STM32
                if line.startswith("#"):
                    print(line)
                    continue

                if line.startswith("t_s"):
                    print("Header received")
                    continue

                parts = line.split(",")

                if len(parts) != 5:
                    print(f"Bad line: {line}")
                    continue

                t_s = float(parts[0])
                voltage = float(parts[1])
                current = float(parts[2])
                pwm = float(parts[3])
                freq = int(parts[4])

                host_time = datetime.now().isoformat()

                print(
                    f"[{host_time}] "
                    f"t={t_s:.2f}s | "
                    f"V={voltage:.3f}V | "
                    f"I={current:.3f}A | "
                    f"PWM={pwm:.1f}% | "
                    f"F={freq}Hz"
                )

                writer.writerow([host_time, t_s, voltage, current, pwm, freq])
                f.flush()

            except KeyboardInterrupt:
                print("\nExiting...")
                break

            except Exception as e:
                print(f"Error: {e}")
                time.sleep(0.5)

if __name__ == "__main__":
    main()
