"""Issue #1895 S3b1 AC-60 (Python-Haelfte, Wirkung am Leser).

Dieselbe Testdatei wie `kanal_wahl_je_wettergroesse_regeln.test.ts` (Frontend erzeugt genau diese
Nutzlast) läuft hier durch den echten Loader und `effective_alert_channels` -> `resolve_alert_channels`,
Trip UND Ortsvergleich. GRÜN seit S3a — bewusst: die Rot-Hälfte der Brücke ist die Frontend-Seite.
"""
from __future__ import annotations

import json
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "alert_metric_channels_nutzlast_beispiel.json"
NUTZER = "tdd-1895-s3b1-bruecke"


def _beispiel() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_ac60_trip_alarm_ueber_thunder_geht_nur_ueber_telegram():
    from app.loader import load_trip_from_dict
    from services.alert_channels import effective_alert_channels

    fx = _beispiel()
    trip = load_trip_from_dict({
        "id": "trip-ac60", "name": "AC-60", "stages": [],
        "report_config": {"send_email": True, "send_telegram": False, "send_sms": False},
        **fx["nutzlast"],
    })
    assert trip.alert_metric_channels == fx["nutzlast"]["alert_metric_channels"]
    abo = effective_alert_channels(trip, None, NUTZER)
    gewaehlt = effective_alert_channels(trip, None, NUTZER, metrics=[fx["summary_key"]])
    assert abo == {"email"}, f"Abo-Satz der Probe muss nur E-Mail sein: {abo!r}"
    assert gewaehlt == {"telegram"}, f"thunder-Alarm muss über Telegram statt Abo gehen: {gewaehlt!r}"


def test_ac60_vergleich_alarm_ueber_thunder_geht_nur_ueber_telegram():
    from app.loader import compare_preset_from_dict, compare_preset_to_dict
    from services.alert_channels import effective_alert_channels

    fx = _beispiel()
    preset = compare_preset_to_dict(compare_preset_from_dict({
        "id": "cmp-ac60", "name": "AC-60", "location_ids": ["a", "b", "c"], **fx["nutzlast"],
    }))
    assert effective_alert_channels(preset, None, NUTZER) == {"email"}
    assert effective_alert_channels(preset, None, NUTZER, metrics=[fx["summary_key"]]) == {"telegram"}
