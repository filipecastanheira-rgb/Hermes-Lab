from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Iterable

SEVERITIES = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
DEFAULT_CLEAN_DIR = Path(__file__).resolve().parent.parent / "runtime" / "clean"
DEFAULT_MAX_EVENTS = 50
DEFAULT_MAX_CHARS = 12000
DEFAULT_LOOKBACK_HOURS = 6

@dataclass(frozen=True)
class ContextConfig:
    clean_dir: Path = DEFAULT_CLEAN_DIR
    max_events: int = DEFAULT_MAX_EVENTS
    max_chars: int = DEFAULT_MAX_CHARS
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS

def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _json_compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _event_matches(event: dict[str, Any], *, source=None, event_type=None, target=None, mission_id=None) -> bool:
    if source and event.get("source") != source: return False
    if event_type and event.get("event_type") != event_type: return False
    if target and event.get("target") != target: return False
    if mission_id and event.get("mission_id") != mission_id: return False
    return True

def _load_jsonl_files(clean_dir: Path) -> list[dict[str, Any]]:
    if not clean_dir.exists(): return []
    events = []
    for path in sorted(clean_dir.glob("events-*.jsonl")):
        if not path.is_file(): continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line: continue
                    try: value = json.loads(line)
                    except json.JSONDecodeError: continue
                    if isinstance(value, dict): events.append(value)
        except OSError: continue
    return events

def _normalise_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event.get("id"), "timestamp": event.get("timestamp"),
        "source": event.get("source"), "event_type": event.get("event_type"),
        "severity": event.get("severity", "info"), "target": event.get("target"),
        "mission_id": event.get("mission_id"), "correlation_id": event.get("correlation_id"),
        "tags": event.get("tags", []), "data": event.get("data", {}), "raw_ref": event.get("raw_ref"),
    }

def load_events(config=None, *, now=None, source=None, event_type=None, target=None, mission_id=None):
    config = config or ContextConfig()
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = now - timedelta(hours=config.lookback_hours)
    result = []
    for raw_event in _load_jsonl_files(config.clean_dir):
        timestamp = _parse_timestamp(raw_event.get("timestamp"))
        if timestamp is None or timestamp < cutoff or timestamp > now: continue
        if not _event_matches(raw_event, source=source, event_type=event_type, target=target, mission_id=mission_id): continue
        result.append(_normalise_event(raw_event))
    result.sort(key=lambda e: _parse_timestamp(e.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return result

def select_events(events: Iterable[dict[str, Any]], *, max_events=DEFAULT_MAX_EVENTS, max_chars=DEFAULT_MAX_CHARS):
    candidates = list(events)
    def score(event):
        severity = SEVERITIES.get(str(event.get("severity", "info")).lower(), 0)
        timestamp = _parse_timestamp(event.get("timestamp"))
        return severity, timestamp.timestamp() if timestamp else 0.0
    candidates.sort(key=score, reverse=True)
    selected, used_chars = [], 0
    for event in candidates:
        encoded = _json_compact(event)
        extra = len(encoded) + (1 if selected else 0)
        if len(selected) >= max_events: break
        if used_chars + extra > max_chars: continue
        selected.append(event); used_chars += extra
    selected.sort(key=lambda e: _parse_timestamp(e.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc))
    return selected

def build_context(question: str, *, config=None, now=None, source=None, event_type=None, target=None, mission_id=None) -> str:
    if not isinstance(question, str) or not question.strip(): raise ValueError("question must be a non-empty string")
    config = config or ContextConfig()
    events = select_events(load_events(config, now=now, source=source, event_type=event_type, target=target, mission_id=mission_id), max_events=config.max_events, max_chars=config.max_chars)
    payload = {"question": question.strip(), "window_hours": config.lookback_hours, "event_count": len(events), "events": events}
    return ("HERMES_CONTEXT\nUse apenas os eventos abaixo como evidência factual. Se a informação não estiver presente, diga explicitamente que não há evidência suficiente nos eventos fornecidos. Não invente hosts, IPs, vulnerabilidades, ações ou resultados.\n\n" + _json_compact(payload))

__all__ = ["ContextConfig", "load_events", "select_events", "build_context"]
