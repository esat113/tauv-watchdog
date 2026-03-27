"""Recording controller -- listens for start/stop commands, writes JSONL files."""

import json
import os
import threading
import time
from datetime import datetime

from cyclonedds.domain import DomainParticipant
from cyclonedds.sub import DataReader
from cyclonedds.pub import DataWriter
from cyclonedds.topic import Topic
from cyclonedds.qos import Qos, Policy
from cyclonedds.util import duration

from dds.types import DiagnosticCommand, DiagnosticStatus

CMD_QOS = Qos(
    Policy.Reliability.Reliable(max_blocking_time=duration(seconds=1)),
    Policy.History.KeepAll,
)
STATUS_QOS = Qos(Policy.Reliability.BestEffort, Policy.History.KeepLast(depth=1))


class Recorder:
    def __init__(self, participant: DomainParticipant, output_dir: str = "/data/logs",
                 status_hz: float = 2.0):
        self._output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        cmd_topic = Topic(participant, "diagnostic/command", DiagnosticCommand, qos=CMD_QOS)
        self._cmd_reader = DataReader(participant, cmd_topic, qos=CMD_QOS)

        status_topic = Topic(participant, "diagnostic/status", DiagnosticStatus, qos=STATUS_QOS)
        self._status_writer = DataWriter(participant, status_topic, qos=STATUS_QOS)

        self._recording = False
        self._record_buffer: list[dict] = []
        self._lock = threading.Lock()
        self._last_file = ""
        self._start_time = time.monotonic()
        self._status_interval = 1.0 / status_hz
        self._stop = threading.Event()
        self._log_count = 0

    @property
    def recording(self) -> bool:
        return self._recording

    def on_log(self, entry: dict):
        with self._lock:
            self._log_count += 1
            if self._recording:
                self._record_buffer.append(entry)

    def start(self):
        self._stop.clear()
        threading.Thread(target=self._cmd_loop, daemon=True, name="recorder-cmd").start()
        threading.Thread(target=self._status_loop, daemon=True, name="recorder-status").start()

    def stop(self):
        self._stop.set()

    def _cmd_loop(self):
        while not self._stop.is_set():
            try:
                samples = self._cmd_reader.take(16)
                for sample in samples:
                    cmd = sample.command.strip().lower()
                    if cmd == "start_recording":
                        self._start_recording()
                    elif cmd == "stop_recording":
                        self._stop_recording()
            except Exception:
                pass
            time.sleep(0.05)

    def _start_recording(self):
        with self._lock:
            self._recording = True
            self._record_buffer.clear()
        print(f"[RECORDER] Recording started")

    def _stop_recording(self):
        with self._lock:
            self._recording = False
            buf = list(self._record_buffer)
            self._record_buffer.clear()

        if not buf:
            print("[RECORDER] Recording stopped (empty)")
            return

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(self._output_dir, f"logs_{ts}.jsonl")
        try:
            with open(path, "w", encoding="utf-8") as f:
                for entry in buf:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._last_file = path
            print(f"[RECORDER] Saved {len(buf)} logs -> {path}")
        except Exception as e:
            print(f"[RECORDER] Save failed: {e}")

    def _status_loop(self):
        while not self._stop.is_set():
            try:
                self._status_writer.write(DiagnosticStatus(
                    recording=self._recording,
                    log_count=self._log_count,
                    file_path=self._last_file,
                    uptime_sec=time.monotonic() - self._start_time,
                    timestamp=int(time.time() * 1000),
                ))
            except Exception:
                pass
            time.sleep(self._status_interval)
