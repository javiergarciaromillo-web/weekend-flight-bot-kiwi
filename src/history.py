from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


HISTORY_PATH = Path("data/price_history.json")


def _load() -> Dict[str, Dict[str, float]]:
    if not HISTORY_PATH.exists():
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_PATH.write_text("{}", encoding="utf-8")
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: Dict[str, Dict[str, float]]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def make_key(provider: str, origin: str, destination: str, date_iso: str, flight_code: str) -> str:
    return f"{provider}:{origin}:{destination}:{date_iso}:{flight_code}"


def get_prev_price(key: str) -> Optional[float]:
    d = _load()
    # store by key -> {"last": float}
    v = d.get(key, {}).get("last")
    return float(v) if v is not None else None


def set_last_price(key: str, price: Optional[float]) -> None:
    d = _load()
    d.setdefault(key, {})
    if price is None:
        # keep previous last if we got no price today
        _save(d)
        return
    d[key]["last"] = float(price)
    _save(d)
