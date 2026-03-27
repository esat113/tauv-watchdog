"""DDS log subscriber + circular buffer."""

import threading
import time
from collections import deque

from cyclonedds.domain import DomainParticipant
from cyclonedds.sub import DataReader
from cyclonedds.topic import Topic
from cyclonedds.qos import Qos, Policy

from dds.types import DetailLog

LOG_QOS = Qos(Policy.Reliability.BestEffort, Policy.History.KeepLast(depth=512))


class LogCollector:
    def __init__(self, participant: DomainParticipant, topic_name: str = "diagnostic/log",
                 max_buffer: int = 50000):
        self._topic = Topic(participant, topic_name, DetailLog, qos=LOG_QOS)
        self._reader = DataReader(participant, self._topic, qos=LOG_QOS)
        self._buffer = deque(maxlen=max_buffer)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._on_log_callbacks = []

    def on_log(self, callback):
        self._on_log_callbacks.append(callback)

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._recv_loop, daemon=True, name="log-collector")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3.0)

    def get_buffer_snapshot(self) -> list[dict]:
        with self._lock:
            return list(self._buffer)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._buffer)

    def _recv_loop(self):
        while not self._stop.is_set():
            try:
                samples = self._reader.take(64)
                for sample in samples:
                    entry = self._to_dict(sample)
                    with self._lock:
                        self._buffer.append(entry)
                    for cb in self._on_log_callbacks:
                        try:
                            cb(entry)
                        except Exception:
                            pass
            except Exception:
                pass
            if not samples:
                time.sleep(0.01)

    @staticmethod
    def _to_dict(log_entry) -> dict:
        return {
            "timestamp": log_entry.timestamp,
            "source": log_entry.source,
            "component": log_entry.component,
            "level": log_entry.level,
            "message": log_entry.message,
        }
