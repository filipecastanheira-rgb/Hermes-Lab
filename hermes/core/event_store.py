"""
event_store.py
Shared write layer for the raw/ + clean/ event pipeline (Fase 0 spec,
agreed 2026-08-14 with ChatGPT).

Every tool keeps its existing internal processing untouched — this
module is purely additive: it lets any reader/tool persist its raw
output for audit, and emit a normalized Hermes event into clean/ for
the future brain/chat layer to consume.

Conventions (per the agreed spec):
- raw/<tool>/   : original tool output, one file per capture/run,
                  kept for 48h by default.
- clean/events-YYYY-MM-DD.jsonl : one JSON object per line, UTC
                  timestamps, kept for 6h after being written (an
                  approximation of "6h after Hermes has seen it",
                  since events are written to clean/ at the same time
                  they become visible to the correlator/brain).

Required clean event fields (Fase 0 schema):
    id, timestamp, source, event_type, severity, target, data
Optional fields: mission_id, correlation_id, tags, raw_ref
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone

RUNTIME_DIR = os.path.join("hermes", "runtime")
RAW_DIR = os.path.join(RUNTIME_DIR, "raw")
CLEAN_DIR = os.path.join(RUNTIME_DIR, "clean")

RAW_RETENTION_SECONDS = 48 * 3600
CLEAN_RETENTION_SECONDS = 6 * 3600

VALID_SEVERITIES = {"info", "low", "medium", "high", "critical"}


def _ensure_dirs(tool_name=None):
    os.makedirs(CLEAN_DIR, exist_ok=True)
    if tool_name:
        os.makedirs(os.path.join(RAW_DIR, tool_name), exist_ok=True)


def now_utc_iso():
    """Current time, UTC, ISO-8601 with offset (e.g. 2026-08-14T10:30:15+00:00)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_event_id():
    return str(uuid.uuid4())


def write_raw(tool_name: str, content: str, extension: str = "log") -> str:
    """
    Persists raw tool output for audit/forensics. Returns the relative
    path written (suitable for the clean event's raw_ref field).
    Never on the hot path for on-demand tools' response time — call
    this AFTER you already have what you need in memory.
    """
    _ensure_dirs(tool_name)
    fname = f"{int(time.time())}_{uuid.uuid4().hex[:8]}.{extension}"
    rel_path = os.path.join(RAW_DIR, tool_name, fname)
    with open(rel_path, "w") as f:
        f.write(content)
    return rel_path


def write_clean(
    source: str,
    event_type: str,
    severity: str,
    target: str,
    data: dict,
    mission_id: str = None,
    correlation_id: str = None,
    tags: list = None,
    raw_ref: str = None,
) -> dict:
    """
    Builds and appends one normalized Hermes event to today's clean/
    JSONL file. Returns the event dict that was written.
    """
    if severity not in VALID_SEVERITIES:
        raise ValueError(
            f"severity '{severity}' invalid — must be one of {VALID_SEVERITIES}. "
            f"Each tool's parse_evento must map its own scale to this one."
        )

    _ensure_dirs()

    event = {
        "id": new_event_id(),
        "timestamp": now_utc_iso(),
        "source": source,
        "event_type": event_type,
        "severity": severity,
        "target": target,
        "data": data or {},
    }
    if mission_id:
        event["mission_id"] = mission_id
    if correlation_id:
        event["correlation_id"] = correlation_id
    if tags:
        event["tags"] = tags
    if raw_ref:
        event["raw_ref"] = raw_ref

    day_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    clean_path = os.path.join(CLEAN_DIR, f"events-{day_str}.jsonl")
    with open(clean_path, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    return event


def apply_retention():
    """
    Deletes raw/ files older than 48h and clean/ daily files whose
    every line is older than 6h (i.e. the whole day-file is stale —
    kept simple: per-file granularity, not per-line, since files
    rotate daily anyway). Call periodically (e.g. from a watchdog
    tick), not on every write.
    """
    now = time.time()
    removed = {"raw": 0, "clean": 0}

    if os.path.isdir(RAW_DIR):
        for tool_dir in os.listdir(RAW_DIR):
            full_dir = os.path.join(RAW_DIR, tool_dir)
            if not os.path.isdir(full_dir):
                continue
            for fname in os.listdir(full_dir):
                fpath = os.path.join(full_dir, fname)
                if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > RAW_RETENTION_SECONDS:
                    os.remove(fpath)
                    removed["raw"] += 1

    if os.path.isdir(CLEAN_DIR):
        for fname in os.listdir(CLEAN_DIR):
            fpath = os.path.join(CLEAN_DIR, fname)
            if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > CLEAN_RETENTION_SECONDS:
                os.remove(fpath)
                removed["clean"] += 1

    return removed
