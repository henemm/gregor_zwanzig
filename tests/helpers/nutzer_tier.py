"""Testnutzer mit Tarif anlegen (Issue #2412 S4a, SMS-Tageslimit).

Seit dem SMS-Tageslimit-Gate (`src/services/sms_daily_limit.py`) gilt ein
Nutzer ohne `user.json` als Tarif "free" (SMS-/Premium-SMS-Cap 0) und wird
gesperrt. Tests, die den echten SMS-/Premium-SMS-Draht pruefen, legen ihren
Nutzer deshalb mit Tarif an -- IMMER ueber `get_data_dir()`, also in der
isolierten Test-Datenwurzel (`tests/conftest.py::_isolate_data_root`), nie im
echten `data/users`-Baum. `standard` = SMS, `premium` = SMS + Premium-SMS.
Muster: `tests/tdd/test_sms_tageslimit.py::_nutzer_anlegen`.
"""
from __future__ import annotations

import json

from app.loader import get_data_dir


def nutzer_mit_tier(uid: str, tier: str = "standard") -> str:
    """Schreibt `user.json` mit `tier` und gibt `uid` zurueck (inline nutzbar)."""
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"id": uid, "tier": tier}))
    return uid
