"""Die Aenderungs-Token der SMS tragen das SMS-Kuerzel, nicht das Telegram-Kuerzel.

Issue #1719 Scheibe S4, AC-4 — Spec
docs/specs/modules/fix_1719_s4_kuerzel_vereinheitlichung.md.

Gemessener Ist-Stand (Kontext-Dokument, Abschnitt "Die Systeme sind schon
heute in derselben Nachricht gemischt"): ``SMSTripFormatter.format_alert_sms``
baut seine Token ueber ``metric_catalog.get_compact_label_for_field()`` — also
aus ``compact_label``, dem TELEGRAM-Kuerzel. Eine SMS traegt damit heute Token
aus beiden Systemen nebeneinander: der Stundenwert der Luftfeuchtigkeit
erscheint als ``HU``, ihre Aenderung als ``H``.

Fuer den Nutzer heisst das: zwei Kuerzel fuer dieselbe Groesse in DERSELBEN
Nachricht — und eines davon steht in keiner Legende.

Erwartung aus Nutzersicht: das Aenderungs-Token traegt dasselbe Kuerzel wie
derselbe Wert an anderer Stelle. Gerechnet aus ``SMS_SYMBOL_BY_METRIC`` /
``SMS_MULTI_SYMBOLS_BY_METRIC``, nicht abgetippt.

KEINE Mocks: echte ``WeatherChange``-Objekte, echter Renderaufruf.

Ausfuehren:
  uv run pytest tests/unit/test_sms_aenderungs_token_kuerzel.py
"""
from __future__ import annotations

import pytest


def _sms_kuerzel(metric_id: str) -> str:
    """Das Kuerzel, das die Trip-SMS fuer diese Groesse sendet (MULTI hat
    Vorrang, ``rstrip(":")`` entfernt die Grammatik-Trennung) — dieselbe
    Aufloesung wie ``/api/sms-symbols::_symbols_for``."""
    from output.renderers.sms_trip import (
        SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC,
    )
    if metric_id in SMS_MULTI_SYMBOLS_BY_METRIC:
        return SMS_MULTI_SYMBOLS_BY_METRIC[metric_id][0].rstrip(":")
    return SMS_SYMBOL_BY_METRIC[metric_id].rstrip(":")


def _aenderungs_sms(metric_id: str, summary_field: str, delta: float) -> str:
    """Rendert eine echte Aenderungs-SMS ueber den Produktionspfad."""
    from app.models import ChangeSeverity, WeatherChange
    from output.renderers.sms_trip import SMSTripFormatter

    change = WeatherChange(
        metric=summary_field,
        old_value=40.0, new_value=40.0 + delta, delta=delta,
        threshold=10.0, severity=ChangeSeverity.MODERATE,
        direction="increase" if delta > 0 else "decrease",
    )
    return SMSTripFormatter().format_alert_sms([change], "KHW", max_length=160)


# Groessen, deren Aenderung die SMS ueberhaupt melden kann (sie brauchen ein
# `summary_fields`-Feld) UND die genau EIN rein alphabetisches SMS-Kuerzel
# tragen. Damit bleiben die beiden benannten Ausnahmen (Temperatur, Gefuehlte
# Temperatur — dort fuehrt die SMS Tagesauswertungen `K`/`D` bzw. `FK`/`FD`)
# und die Grammatikform `NS24+` (Neuschnee, 24-Stunden-Fenster) aussen vor:
# beide sind keine reine Umbenennung und gehoeren nicht in diese Frage.
_EINDEUTIGE = [
    ("humidity", "humidity_avg_pct"),
    ("cloud_total", "cloud_avg_pct"),
    ("visibility", "visibility_min_m"),
    ("pressure", "pressure_avg_hpa"),
    ("freezing_level", "freezing_level_m"),
    ("rain_probability", "pop_max_pct"),
    ("snowfall_limit", "snowfall_limit_m"),
]


@pytest.mark.parametrize("metric_id,summary_field", _EINDEUTIGE)
def test_aenderungs_token_traegt_das_sms_kuerzel(metric_id, summary_field):
    """AC-4: Given ein Trip, dessen SMS ein Aenderungs-Token enthaelt (z.B.
    Luftfeuchtigkeit steigt) / When die SMS gerendert wird / Then traegt das
    Token dasselbe Kuerzel, das die SMS fuer diese Groesse auch sonst sendet —
    kein Token aus dem alten Telegram-System."""
    erwartet = _sms_kuerzel(metric_id)
    text = _aenderungs_sms(metric_id, summary_field, delta=+15.0)

    token = [t for t in text.split() if t.startswith("+") is False and "+" in t]
    assert token, f"Kein Aenderungs-Token in der SMS gefunden: {text!r}"
    gerendert = token[-1]
    assert gerendert.startswith(erwartet), (
        f"AC-4 FAIL ({metric_id}): das Aenderungs-Token der SMS lautet "
        f"{gerendert!r}, die SMS sendet diese Groesse sonst als {erwartet!r}. "
        f"Zwei Kuerzel fuer dieselbe Groesse in derselben Nachricht.\n"
        f"Gerenderte SMS: {text!r}"
    )


def test_umkehrsuche_liefert_fuer_jede_eindeutige_groesse_das_sms_kuerzel():
    """AC-4, Wirkort statt Aufrufstelle: die Umkehrsuche
    ``get_compact_label_for_field()`` ist die EINE Quelle der Aenderungs-Token
    (sms_trip.py, `format_alert_sms`). Sie muss fuer jede eindeutig
    bekuerzelte Groesse das SMS-Kuerzel liefern — sonst faellt derselbe Fehler
    beim naechsten Aufrufer wieder an."""
    from app.metric_catalog import get_compact_label_for_field

    abweichungen = []
    for metric_id, summary_field in _EINDEUTIGE:
        treffer = get_compact_label_for_field(summary_field)
        assert treffer is not None, (
            f"Testaufbau: '{summary_field}' ist im Katalog keiner Groesse "
            "zugeordnet — Feldname pruefen."
        )
        if treffer[0] != _sms_kuerzel(metric_id):
            abweichungen.append(
                f"{metric_id}: Umkehrsuche liefert {treffer[0]!r}, "
                f"die SMS sendet {_sms_kuerzel(metric_id)!r}"
            )
    assert not abweichungen, (
        "AC-4 FAIL — die Umkehrsuche der Aenderungs-Token spricht das alte "
        "Telegram-Vokabular:\n  " + "\n  ".join(abweichungen)
    )
