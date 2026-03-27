"""tauv-watchdog: DDS log collector + recorder."""

import os
import signal
import time

import yaml
from cyclonedds.domain import DomainParticipant

from collector import LogCollector
from recorder import Recorder

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config() -> dict:
    defaults = {
        "DDS_DOMAIN": 0,
        "LOG_TOPIC": "diagnostic/log",
        "MAX_BUFFER": 50000,
        "OUTPUT_DIR": "/data/logs",
        "STATUS_HZ": 2.0,
    }
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        for k, v in raw.items():
            defaults[k] = v
    return defaults


def main():
    cfg = load_config()
    print("=== tauv-watchdog ===")
    print(f"  domain    : {cfg['DDS_DOMAIN']}")
    print(f"  log_topic : {cfg['LOG_TOPIC']}")
    print(f"  buffer    : {cfg['MAX_BUFFER']}")
    print(f"  output    : {cfg['OUTPUT_DIR']}")

    participant = DomainParticipant(int(cfg["DDS_DOMAIN"]))

    collector = LogCollector(
        participant,
        topic_name=cfg["LOG_TOPIC"],
        max_buffer=int(cfg["MAX_BUFFER"]),
    )

    recorder = Recorder(
        participant,
        output_dir=cfg["OUTPUT_DIR"],
        status_hz=float(cfg["STATUS_HZ"]),
    )

    collector.on_log(recorder.on_log)

    shutdown = False

    def on_signal(sig, frame):
        nonlocal shutdown
        shutdown = True

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    collector.start()
    recorder.start()
    print("[OK] Listening for logs...")

    try:
        while not shutdown:
            time.sleep(1)
    finally:
        recorder.stop()
        collector.stop()
        print("[SHUTDOWN] Done.")


if __name__ == "__main__":
    main()
