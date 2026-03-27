from dataclasses import dataclass
from cyclonedds.idl import IdlStruct


@dataclass
class DetailLog(IdlStruct):
    timestamp: float
    source: str
    component: str
    level: str
    message: str


@dataclass
class DiagnosticCommand(IdlStruct):
    command: str
    client_id: str
    timestamp: int


@dataclass
class DiagnosticStatus(IdlStruct):
    recording: bool
    log_count: int
    file_path: str
    uptime_sec: float
    timestamp: int
