"""Radar-Logik haengt nicht an der angezeigten Sprache (Issue #2667, AC-5).

SPEC: docs/specs/modules/i18n_p5_abweichungs_radar_alarme_2667.md AC-5.

Die Intensitaets-Konstanten bleiben der deutsche Vergleichsschluessel
(``alert_urgency``, ``rain_extent``); nur die Anzeige uebersetzt
``intensity_text``. Eine englisch gebaute Alarm-Nachricht traegt deshalb
denselben Schluessel und dieselbe Dringlichkeit wie die deutsche. Die
Kurzform ``format_now_text(..., englisch=True)`` (#2417) bleibt byte-gleich.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from i18n import t
from services import radar_service as rs
from services.alert_urgency import urgency_from_radar
from services.radar_alert_service import build_onset_alert_message

STUFEN = [rs.INTENSITY_CONVECTIVE, rs.INTENSITY_CONVECTIVE_NO_HAIL, rs.INTENSITY_HEAVY,
          rs.INTENSITY_MODERATE, rs.INTENSITY_LIGHT]


def _nachricht(label: str, lang: str):
    trip = SimpleNamespace(name="GR20", alert_cooldown_minutes=120)
    active = SimpleNamespace(start_point=SimpleNamespace(lat=42.2, lon=9.0), distance_km=8.0)
    return build_onset_alert_message(trip, active, 25, "06:25", label, "Radar (DWD)",
                                     is_convective=label in STUFEN[:2], lang=lang)


@pytest.mark.parametrize("label", STUFEN)
def test_ac5_dringlichkeit_gleich_in_beiden_sprachen(label):
    ergebnisse = set()
    for lang in ("de", "en"):
        e = _nachricht(label, lang).events[0]
        assert e.intensity_label == label
        ergebnisse.add(urgency_from_radar(is_convective=e.is_convective,
                                          intensity_label=e.intensity_label))
    assert len(ergebnisse) == 1


@pytest.mark.parametrize("label", STUFEN + [rs.INTENSITY_DRY])
def test_ac5_anzeige_uebersetzt_nur_den_text(label):
    assert rs.intensity_text(label, "de") == label
    assert rs.intensity_text(label, "en") != label
    assert rs.intensity_text(label, "en") == t(rs._INTENSITY_KEYS[label], "en")


def test_ac5_unbekannte_intensitaet_bleibt():
    assert rs.intensity_text("Nieselregen", "en") == "Nieselregen"


def test_ac5_englische_nachricht_traegt_englischen_cooldown():
    assert _nachricht(rs.INTENSITY_HEAVY, "en").cooldown_display == "2 hours"
    assert _nachricht(rs.INTENSITY_HEAVY, "de").cooldown_display == "2 Stunden"


@pytest.mark.parametrize("label, unavailable, soll", [
    (rs.INTENSITY_DRY, False, "No precipitation.\nNo rain expected in the next 3 hours.\nSource: dwd."),
    (rs.INTENSITY_HEAVY, False, "Heavy rain.\nNo rain expected in the next 3 hours.\nSource: dwd."),
    (rs.INTENSITY_DRY, True, "Short-term rain check not possible right now.\n"
                             "Please watch the sky yourself.\nSource: dwd."),
])
def test_ac5_kurzform_englisch_byte_gleich(label, unavailable, soll):
    """Aufgezeichnet mit dem Code vor #2667 (Kurzform #2417 bleibt)."""
    svc = rs.RadarNowcastService.__new__(rs.RadarNowcastService)
    r = rs.NowcastResult(onset_minutes=None, intensity_label=label, source="dwd",
                         data_unavailable=unavailable)
    assert svc.format_now_text(r, englisch=True) == soll
