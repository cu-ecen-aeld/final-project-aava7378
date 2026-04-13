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

import csv
import os
import signal
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import serial

PORT = "/dev/serial0"
BAUD = 115200
SERIAL_TIMEOUT_S = 1.0
LOG_FILE = "telemetry_log.csv"

PLOT_HISTORY = 500
LOG_QUEUE_MAX = 2000
PLOT_UPDATE_MS = 200

CSV_HEADER = [
    "host_time",
    "t_s",
    "voltage_v",
    "pot_voltage_v",
    "pot_percent",
    "pwm_pct",
    "pwm_freq_hz",
]


@dataclass
class TelemetrySample:
    host_time: str
    t_s: float
    voltage_v: float
    pot_voltage_v: float
    pot_percent: float
    pwm_pct: float
    pwm_freq_hz: int


class SharedTelemetryBuffer:
    def __init__(self, plot_history=PLOT_HISTORY, log_queue_max=LOG_QUEUE_MAX):
        self.plot_samples = deque(maxlen=plot_history)
        self.log_queue = deque(maxlen=log_queue_max)

        self.lock = threading.Lock()
        self.cond = threading.Condition(self.lock)

        self.total_received = 0
        self.total_logged = 0
        self.dropped_log_samples = 0

    def push(self, sample: TelemetrySample) -> None:
        with self.cond:
            self.plot_samples.append(sample)

            if len(self.log_queue) >= self.log_queue.maxlen:
                self.log_queue.popleft()
                self.dropped_log_samples += 1

            self.log_queue.append(sample)
            self.total_received += 1
            self.cond.notify()

    def pop_for_log(self, stop_event: threading.Event, timeout: float = 0.5):
        with self.cond:
            while not self.log_queue and not stop_event.is_set():
                self.cond.wait(timeout=timeout)

            if not self.log_queue:
                return None

            sample = self.log_queue.popleft()
            self.total_logged += 1
            return sample

    def snapshot_for_plot(self):
        with self.lock:
            return list(self.plot_samples)

    def stats(self):
        with self.lock:
            return {
                "received": self.total_received,
                "logged": self.total_logged,
                "dropped_log_samples": self.dropped_log_samples,
                "plot_buffer_len": len(self.plot_samples),
                "log_queue_len": len(self.log_queue),
            }


shared_buffer = SharedTelemetryBuffer()
stop_event = threading.Event()


def ensure_csv_header(filename):
    write_header = not os.path.exists(filename) or os.path.getsize(filename) == 0
    f = open(filename, "a", newline="")
    writer = csv.writer(f)

    if write_header:
        writer.writerow(CSV_HEADER)
        f.flush()

    return f, writer


def parse_telemetry_line(line: str) -> TelemetrySample:
    parts = line.split(",")

    if len(parts) != 6:
        raise ValueError(f"Expected 6 CSV fields, got {len(parts)}")

    t_s = float(parts[0])
    voltage_v = float(parts[1])
    pot_voltage_v = float(parts[2])
    pot_percent = float(parts[3])
    pwm_pct = float(parts[4])
    pwm_freq_hz = int(float(parts[5]))

    return TelemetrySample(
        host_time=datetime.now().isoformat(),
        t_s=t_s,
        voltage_v=voltage_v,
        pot_voltage_v=pot_voltage_v,
        pot_percent=pot_percent,
        pwm_pct=pwm_pct,
        pwm_freq_hz=pwm_freq_hz,
    )


def serial_receiver_thread():
    ser = None

    while not stop_event.is_set():
        try:
            if ser is None:
                print(f"[RX] Opening {PORT} at {BAUD} baud...")
                ser = serial.Serial(PORT, BAUD, timeout=SERIAL_TIMEOUT_S)
                time.sleep(0.2)

            raw = ser.readline()
            if not raw:
                continue

            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            if line.startswith("t_s"):
                print("[RX] Header received")
                continue

            # Ignore banner / non-CSV text from STM32 startup
            if "," not in line:
                print(f"[RX] {line}")
                continue

            try:
                sample = parse_telemetry_line(line)
                shared_buffer.push(sample)

                print(
                    f"[{sample.host_time}] "
                    f"t={sample.t_s:.2f}s | "
                    f"V={sample.voltage_v:.3f}V | "
                    f"Pot={sample.pot_voltage_v:.3f}V | "
                    f"Pot%={sample.pot_percent:.1f}% | "
                    f"PWM={sample.pwm_pct:.1f}% | "
                    f"F={sample.pwm_freq_hz}Hz"
                )
            except ValueError as e:
                print(f"[RX] Parse error: {e} | line={line}")

        except serial.SerialException as e:
            print(f"[RX] Serial error: {e}")
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
            time.sleep(1.0)

        except Exception as e:
            print(f"[RX] Unexpected error: {e}")
            time.sleep(0.5)

    if ser is not None:
        try:
            ser.close()
        except Exception:
            pass

    print("[RX] Receiver thread exited")


def logger_thread():
    f, writer = ensure_csv_header(LOG_FILE)
    print(f"[LOG] Writing to {LOG_FILE}")

    try:
        while not stop_event.is_set():
            sample = shared_buffer.pop_for_log(stop_event, timeout=0.5)
            if sample is None:
                continue

            writer.writerow([
                sample.host_time,
                sample.t_s,
                sample.voltage_v,
                sample.pot_voltage_v,
                sample.pot_percent,
                sample.pwm_pct,
                sample.pwm_freq_hz,
            ])
            f.flush()
    finally:
        f.close()
        print("[LOG] Logger thread exited")


def status_thread():
    while not stop_event.is_set():
        time.sleep(5.0)
        s = shared_buffer.stats()
        print(
            "[STAT] "
            f"received={s['received']} "
            f"logged={s['logged']} "
            f"dropped={s['dropped_log_samples']} "
            f"plot_buf={s['plot_buffer_len']} "
            f"log_q={s['log_queue_len']}"
        )

    print("[STAT] Status thread exited")


def run_live_plot():
    fig, axes = plt.subplots(3, 1, figsize=(10, 10))

    ax_voltage = axes[0]
    ax_pot = axes[1]
    ax_pwm = axes[2]

    voltage_line, = ax_voltage.plot([], [], label="System Voltage (V)")
    pot_line, = ax_pot.plot([], [], label="Pot Voltage (V)")
    pwm_line, = ax_pwm.plot([], [], label="PWM Duty (%)")

    ax_voltage.set_title("Live System Voltage vs Time")
    ax_voltage.set_xlabel("Time (s)")
    ax_voltage.set_ylabel("Voltage (V)")
    ax_voltage.grid(True)
    ax_voltage.legend()

    ax_pot.set_title("Live Potentiometer Voltage vs Time")
    ax_pot.set_xlabel("Time (s)")
    ax_pot.set_ylabel("Pot Voltage (V)")
    ax_pot.grid(True)
    ax_pot.legend()

    ax_pwm.set_title("Live PWM Duty Cycle vs Time")
    ax_pwm.set_xlabel("Time (s)")
    ax_pwm.set_ylabel("PWM Duty (%)")
    ax_pwm.grid(True)
    ax_pwm.legend()

    status_text = fig.text(0.02, 0.01, "", fontsize=9)

    def update(_frame):
        samples = shared_buffer.snapshot_for_plot()
        if not samples:
            return voltage_line, pot_line, pwm_line, status_text

        x = [s.t_s for s in samples]
        y_voltage = [s.voltage_v for s in samples]
        y_pot = [s.pot_voltage_v for s in samples]
        y_pwm = [s.pwm_pct for s in samples]

        voltage_line.set_data(x, y_voltage)
        pot_line.set_data(x, y_pot)
        pwm_line.set_data(x, y_pwm)

        ax_voltage.relim()
        ax_voltage.autoscale_view()

        ax_pot.relim()
        ax_pot.autoscale_view()

        ax_pwm.relim()
        ax_pwm.autoscale_view()

        latest = samples[-1]
        s = shared_buffer.stats()
        status_text.set_text(
            f"Latest: t={latest.t_s:.2f}s, "
            f"V={latest.voltage_v:.3f}V, "
            f"Pot={latest.pot_voltage_v:.3f}V, "
            f"PWM={latest.pwm_pct:.1f}%, "
            f"received={s['received']}, logged={s['logged']}, dropped={s['dropped_log_samples']}"
        )

        return voltage_line, pot_line, pwm_line, status_text

    def on_close(_event):
        stop_event.set()

    fig.canvas.mpl_connect("close_event", on_close)

    ani = FuncAnimation(
        fig,
        update,
        interval=PLOT_UPDATE_MS,
        blit=False,
        cache_frame_data=False
    )

    plt.tight_layout()
    plt.show()

    return ani

def handle_signal(signum, _frame):
    print(f"\n[MAIN] Signal {signum} received, shutting down...")
    stop_event.set()


def main():
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    rx_thread = threading.Thread(target=serial_receiver_thread, name="serial-rx", daemon=True)
    log_thread = threading.Thread(target=logger_thread, name="logger", daemon=True)
    stat_thread = threading.Thread(target=status_thread, name="status", daemon=True)

    rx_thread.start()
    log_thread.start()
    stat_thread.start()

    try:
        run_live_plot()
    finally:
        stop_event.set()
        rx_thread.join(timeout=2.0)
        log_thread.join(timeout=2.0)
        stat_thread.join(timeout=2.0)
        print("[MAIN] Clean exit")


if __name__ == "__main__":
    main()
