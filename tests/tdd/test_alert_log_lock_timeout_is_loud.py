"""AC-11 (Epic #1539, S1a): ein Sperr-Timeout im Alarm-Log ist laut, nie stumm.

Given ein Sperrhalter, der die Sperre `alert_log.json.lock` ueber die
      Wartefrist von `alert_log` hinaus haelt (Frist im Test verkuerzt)
When  ein Eintrag geschrieben werden soll
Then  wird er NICHT still verworfen: `logger.error` traegt den vollstaendigen
      Eintrag als JSON (aus dem Journal wiederherstellbar), der Prozess-Zaehler
      `alert_log_lost_entries` steigt um 1, `alert_log.json` bleibt byte-genau
      unveraendert (nie ungesperrt schreiben), und der Aufrufer bekommt keine
      Ausnahme (ein Protokollproblem darf keinen Alarmversand abbrechen).

Echter Sperrhalter: ein zweiter Dateideskriptor mit `fcntl.flock(LOCK_EX)` in
einem eigenen Thread (flock gilt je offener Dateibeschreibung, blockiert also
auch im selben Prozess). Kein Mock.

Vom Test angenommene Namen (Spec legt sie nicht woertlich fest, Developer
richtet sich danach oder meldet Abweichung):
  * `services.alert_log.ALERT_LOG_LOCK_TIMEOUT_SECONDS` -- Wartefrist (Spec: 30 s)
  * `services.alert_log.alert_log_lost_entries`          -- int-Prozess-Zaehler

RED heute: `_append` kennt keine Sperre und schreibt einfach durch -- die Datei
aendert sich, nichts wird protokolliert, der Zaehler existiert nicht.
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import sys
import threading
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.loader import get_data_dir  # noqa: E402
from services import alert_log  # noqa: E402


@pytest.mark.timeout(20)
def test_lock_timeout_protokolliert_eintrag_laut_und_zaehlt(monkeypatch, caplog):
    """AC-11: toter Sperrhalter -> ERROR mit vollem Eintrag, Zaehler +1, Datei
    unveraendert, keine Ausnahme beim Aufrufer."""
    monkeypatch.setattr(alert_log, "ALERT_LOG_LOCK_TIMEOUT_SECONDS", 0.3, raising=False)
    nutzer = "ac11-alice"
    pfad = get_data_dir(nutzer) / "alert_log.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"entries": [{"entity_id": "alt"}], "not_delivered": []}, indent=2))
    vorher = pfad.read_bytes()
    zaehler_vorher = getattr(alert_log, "alert_log_lost_entries", 0)

    halten, freigeben = threading.Event(), threading.Event()

    def sperrhalter() -> None:
        fd = os.open(str(pfad) + ".lock", os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            halten.set()
            freigeben.wait(timeout=15)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    halter = threading.Thread(target=sperrhalter, daemon=True)
    halter.start()
    assert halten.wait(timeout=5), "Testaufbau: Sperre nicht gehalten"
    try:
        with caplog.at_level(logging.ERROR, logger="services.alert_log"):
            try:
                alert_log.append_entry(
                    nutzer, entity_id="ac11-verloren", entity_type="trip",
                    changes_count=2, severity="high", reason="forecast_change",
                    effective_channels=["email"], sent_channels=["email"],
                )
            except BaseException as e:  # Aufrufer darf keine Ausnahme sehen
                pytest.fail(f"Aufrufer bekam Ausnahme: {e!r}")
    finally:
        freigeben.set()
        halter.join(timeout=5)

    assert pfad.read_bytes() == vorher, "alert_log.json wurde trotz fremder Sperre veraendert"

    fehler = [r for r in caplog.records
              if r.levelno >= logging.ERROR and "ac11-verloren" in r.getMessage()]
    assert fehler, "kein ERROR-Log mit dem verlorenen Eintrag -- stilles Verwerfen"
    text = fehler[0].getMessage()
    try:
        eintrag, _ = json.JSONDecoder().raw_decode(text[text.index("{"):])
    except ValueError as e:
        raise AssertionError(f"ERROR-Log enthaelt den Eintrag nicht als JSON: {text!r} ({e})")
    for feld in ("entity_id", "entity_type", "sent_at", "severity", "channels_sent"):
        assert feld in eintrag, f"Eintrag im Log unvollstaendig, Feld {feld!r} fehlt"
    assert eintrag["entity_id"] == "ac11-verloren"

    assert getattr(alert_log, "alert_log_lost_entries", 0) == zaehler_vorher + 1, (
        "Zaehler alert_log_lost_entries ist nicht um genau 1 gestiegen"
    )
