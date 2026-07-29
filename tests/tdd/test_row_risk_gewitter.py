"""TDD RED — Issue #1418 Fehler 1 (Epic #1419 S1): der Warnpunkt am
Zeilenende der Stundentabelle bleibt bei Gewitter stumm.

`_row_risk` (`src/output/renderers/email/html.py`) vergleicht `r["thunder"]`
mit `_safe_float(...) > 20`. In beiden Produktionspfaden, die die Stundentabelle
mit Daten fuellen (`trip_report.py: _dp_to_row` fuer Einzelstunden UND
`_aggregate_night_block` fuer Nachtbloecke), steht in `row["thunder"]` aber ein
`ThunderLevel`-Stufenwert (`app/models.py` — `class ThunderLevel(str, Enum)`,
Werte NONE/MED/HIGH), keine Zahl. `_safe_float` faengt den `ValueError`/
`TypeError` beim Zahl-Cast ab und liefert 0.0 — die Schwelle `> 20` ist damit
IMMER falsch, der Risiko-Punkt springt bei Gewitter nie auf Rot.

Da `ThunderLevel` von `str` erbt, kann derselbe Wert je nach Aufrufpfad als
Enum-Instanz ODER als reiner String ("HIGH"/"MED") in der Zeile stehen — beide
Formen muessen denselben Warnpunkt ergeben (s. `outlook.py:186`,
`helpers.py:831`: `(stage.get("thunder", "NONE") or "NONE").upper()` erzeugt
dort den String-Pfad).

Kern-Schicht, deterministisch: keine Mocks/patch()/MagicMock, kein Netz. Echter
Renderer-Aufruf (`_row_risk`) mit echten Zeilen-Dicts. Kein Dateiinhalt-Check.

SPEC: Issue #1418 Fehler 1 / Epic #1419 Schritt S1.
"""
from __future__ import annotations

from app.models import ThunderLevel
from src.output.renderers.email.html import _row_risk

_HARMLESS = {"wind": 5, "gust": 10, "precip": 0.0, "pop": 5, "vis": 20000.0}


def test_thunder_high_enum_becomes_risk():
    """Given eine Zeile mit `ThunderLevel.HIGH` und sonst harmlosen Werten /
    When `_row_risk` berechnet wird / Then ist das Ergebnis 'risk' — heute
    liefert es 'ok', weil `_safe_float(ThunderLevel.HIGH)` beim `> 20`-Vergleich
    still auf 0.0 faellt."""
    row = {**_HARMLESS, "thunder": ThunderLevel.HIGH}
    result = _row_risk(row)
    assert result == "risk", (
        f"_row_risk mit ThunderLevel.HIGH liefert {result!r}, erwartet 'risk' "
        f"— der Warnpunkt bleibt bei Gewitter stumm (Issue #1418 Fehler 1)."
    )


def test_thunder_high_string_becomes_risk():
    """Given dieselbe Zeile, aber Gewitter als reiner String 'HIGH' (Pfad
    `outlook.py`/`helpers.py`: `.upper()` auf `stage.get('thunder', 'NONE')`) /
    When `_row_risk` berechnet wird / Then ist das Ergebnis ebenfalls 'risk'."""
    row = {**_HARMLESS, "thunder": "HIGH"}
    result = _row_risk(row)
    assert result == "risk", (
        f"_row_risk mit String 'HIGH' liefert {result!r}, erwartet 'risk'."
    )


def test_thunder_med_enum_becomes_at_least_watch():
    """Given eine Zeile mit `ThunderLevel.MED` und sonst harmlosen Werten /
    When `_row_risk` berechnet wird / Then ist das Ergebnis mindestens
    'watch' — heute liefert es 'ok'."""
    row = {**_HARMLESS, "thunder": ThunderLevel.MED}
    result = _row_risk(row)
    assert result in ("watch", "risk"), (
        f"_row_risk mit ThunderLevel.MED liefert {result!r}, erwartet "
        f"mindestens 'watch'."
    )


def test_thunder_med_string_becomes_at_least_watch():
    """Dieselbe Erwartung fuer die String-Form 'MED'."""
    row = {**_HARMLESS, "thunder": "MED"}
    result = _row_risk(row)
    assert result in ("watch", "risk"), (
        f"_row_risk mit String 'MED' liefert {result!r}, erwartet mindestens "
        f"'watch'."
    )


def test_thunder_none_enum_stays_ok():
    """Regressionsschutz: Given `ThunderLevel.NONE` und sonst harmlose Werte /
    When `_row_risk` berechnet wird / Then bleibt es 'ok' (kein
    Falsch-Alarm-Regress durch den Fix)."""
    row = {**_HARMLESS, "thunder": ThunderLevel.NONE}
    assert _row_risk(row) == "ok"


def test_thunder_missing_stays_ok():
    """Regressionsschutz: fehlender Gewitter-Wert darf nie abstuerzen und
    bleibt 'ok'."""
    row = dict(_HARMLESS)
    assert _row_risk(row) == "ok"


def test_thunder_unknown_string_no_crash_stays_ok():
    """Regressionsschutz: ein unbekannter String darf nicht abstuerzen und
    traegt nichts zum Risiko bei."""
    row = {**_HARMLESS, "thunder": "UNBEKANNT"}
    assert _row_risk(row) == "ok"


def test_other_catalog_metrics_still_decide_risk_unchanged():
    """Regressionsschutz (#1377 Scheibe B): Wind/Boeen/Regen/Regenwahrsch./
    Sicht entscheiden weiterhin ueber `severity_for` — unveraendert vom
    Gewitter-Fix. Boeen 65 km/h liegt ueber der roten Katalog-Schwelle (60)."""
    row = {"wind": 5, "gust": 65, "precip": 0.0, "pop": 5, "vis": 20000.0,
           "thunder": ThunderLevel.NONE}
    assert _row_risk(row) == "risk"
