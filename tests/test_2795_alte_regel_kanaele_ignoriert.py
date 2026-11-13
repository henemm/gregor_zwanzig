"""#2795 S3b Teil 1a, Nachauftrag: alte Regel-Kanaele wirken nicht mehr.

Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md §4.3 („Zielkanaele
ergeben sich nur aus ``alert_channels`` und ``alert_channel_thresholds`` der
Kanal-Tabelle, fuer alle Metriken gleich“), AC-28, AC-29.

Zwei Wege, auf denen eine Sonderregel je Metrik nach dem Wegfall von
``alert_metric_channels`` weiterlebte:

1. Im Alarmversand vereinigte ``resolve_alert_channels`` die Kanaele aktiver
   ``alert_rules[].channels`` (Schritt 3) -- diese Union stand VOR der
   Kanal-Tabelle. Ein Trip mit Kanal-Tabelle E-Mail+Telegram und einer alten
   Regel ``channels=["email"]`` bekam einen „hoch“-Alarm nur per E-Mail.
2. Beim Laden erzeugte ``app.loader`` aus den Regel-Kanaelen den Schluessel
   ``alert_metric_channels`` (Migration #1895 S2), ``save_trip`` schrieb ihn
   zurueck -- die Migration aus #2795 waere nach dem naechsten Speichern
   wieder unterlaufen.

Ortsvergleiche tragen keine ``alert_rules`` (``_compare_channel_inputs``
liefert immer eine leere Regel-Liste); geprueft wird deshalb nur der Trip.

Gemessen am echten Versandweg ``TripAlertService._send_alert`` (aufgezeichnet
an der Transport-Grenze ``send_deviation_alert``, kein Patch auf den
Aufloeser) und am echten Load->Save-Roundtrip auf Platte. Kein Mock.
"""
from __future__ import annotations

import json

from app.models import AlertMetric, AlertRule, AlertRuleKind, AlertSeverity
from tests.test_2795_alert_metric_channels_ignoriert import (
    _aenderung, _tarif, _trip, _trip_versand,
)


def _alte_regel_nur_email() -> AlertRule:
    return AlertRule(
        id="alt-gust-email", kind=AlertRuleKind.DELTA, metric=AlertMetric.WIND_GUST,
        threshold=20.0, severity=AlertSeverity.WARNING, enabled=True,
        channels=["email"],
    )


def test_trip_alarm_hoch_geht_trotz_alter_regel_kanaele_an_beide_kanaele():
    """Kanal-Tabelle E-Mail=an (gering), Telegram=an (hoch), dazu eine alte,
    aktive Regel ``channels=["email"]`` fuer Boeen. Ein Alarm „hoch“ geht an
    E-Mail UND Telegram -- die alte Regel hat keine Wirkung.

    Am HEAD-Code (vor diesem Nachauftrag) rot: die Regel-Union verengt auf
    {email}."""
    user = "u2795-alte-regel-hoch"
    _tarif(user)
    trip = _trip("trip-2795-alte-regel", altschluessel=None)
    trip.alert_rules = [_alte_regel_nur_email()]
    rek = _trip_versand(trip, user, [_aenderung("gust_max_kmh", "major")])
    assert rek.abweichung == [{"email", "telegram"}], (
        "#2795 §4.3: Alarm 'hoch' geht nach der Kanal-Tabelle an E-Mail und "
        f"Telegram, alte Regel-Kanaele ohne Wirkung: {rek.abweichung!r}"
    )


def test_trip_alarm_gering_geht_trotz_alter_regel_nur_an_email():
    """Gegenprobe: derselbe Trip, Alarm „gering“ -> nur E-Mail (Telegram steht
    auf „hoch“). Beweist, dass die Schwelle je Kanal weiter greift."""
    user = "u2795-alte-regel-gering"
    _tarif(user)
    trip = _trip("trip-2795-alte-regel-g", altschluessel=None)
    trip.alert_rules = [_alte_regel_nur_email()]
    rek = _trip_versand(trip, user, [_aenderung("gust_max_kmh", "minor")])
    assert rek.abweichung == [{"email"}], rek.abweichung


def test_load_save_roundtrip_erzeugt_kein_alert_metric_channels(tmp_path):
    """Ein Bestands-Trip mit aktiver Regel ``channels=["telegram"]`` und OHNE
    ``alert_metric_channels`` wird geladen und gespeichert: danach steht kein
    ``alert_metric_channels`` in der Datei, die Regel selbst bleibt erhalten
    (Read-Modify-Write, kein Datenverlust).

    Am HEAD-Code rot: die Lade-Migration (#1895 S2) erzeugt den Schluessel aus
    der Regel, ``save_trip`` schreibt ihn zurueck."""
    from app.loader import load_trip, save_trip

    user = "u2795-roundtrip"
    briefings = tmp_path / "users" / user / "briefings"
    briefings.mkdir(parents=True)
    roh = {
        "id": "trip-2795-rt", "name": "Roundtrip", "kind": "route",
        "stages": [{
            "id": "S1", "name": "Etappe 1", "date": "2026-08-20",
            "waypoints": [{"id": "W1", "name": "Start", "lat": 46.0, "lon": 9.0,
                           "elevation_m": 1200}],
        }],
        "alert_rules": [{
            "id": "r-gust", "kind": "delta", "metric": "wind_gust", "threshold": 5.0,
            "unit": "", "severity": "warning", "enabled": True, "channels": ["telegram"],
        }],
        "alert_channels": {"email": True, "telegram": True, "sms": False, "premium_sms": False},
    }
    pfad = briefings / "trip-2795-rt.json"
    pfad.write_text(json.dumps(roh), encoding="utf-8")

    trip = load_trip("trip-2795-rt", data_dir=tmp_path, user_id=user)
    assert trip is not None
    assert trip.alert_metric_channels is None, (
        f"#2795: Laden darf alert_metric_channels nicht aus Regeln erzeugen: {trip.alert_metric_channels!r}"
    )
    save_trip(trip, user, data_dir=tmp_path)

    gespeichert = json.loads(pfad.read_text(encoding="utf-8"))
    assert "alert_metric_channels" not in gespeichert, (
        f"#2795: Load->Save hat alert_metric_channels wiederbelebt: {gespeichert.get('alert_metric_channels')!r}"
    )
    regeln = gespeichert.get("alert_rules") or []
    assert [r.get("channels") for r in regeln] == [["telegram"]], (
        f"Read-Modify-Write: die Regel selbst muss erhalten bleiben: {regeln!r}"
    )
    assert gespeichert.get("alert_channels") == roh["alert_channels"]
