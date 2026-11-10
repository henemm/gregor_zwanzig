"""Konsistenzprobe AC-20: Alarm-Lesart der amtlichen Warnungen vs. ODER-Regel.

SPEC: docs/specs/modules/feat_2794_s3a_teil3_wetter.md (AC-20, Implementation
Details §1 ``amtlicheWarnungen.ts``). Der Reiter Wetter zeigt EINEN Schalter
„Amtliche Warnungen". Lese-Regel (Frontend): ist ``official_warnings``
vorhanden, gilt ``official_warnings.enabled || official_alerts_enabled``;
sonst ``official_alert_triggers_enabled`` (Default an). Schreib-Regel: beide
Felder ``official_alerts_enabled`` und ``official_warnings.enabled`` auf
denselben Wert. Renderer und Alarm-Engine bleiben UNVERAENDERT.

Diese Datei aendert nichts am Produktivcode. Sie spielt die bestehende
Alarm-Lesart durch und haelt fest, wo sie mit der ODER-Regel uebereinstimmt:

- Trip: ``TripAlertService._official_trigger_possible`` — die geteilte
  Vorrangregel beider Trip-Pfade (Vorab-Filter in ``check_all_trips`` und
  ``check_official_alert_triggers``).
- Orts-Vergleich: ``CompareOfficialAlertService`` aus Nutzersicht — eine
  echte, netzfreie amtliche Quelle meldet eine Warnung, beobachtet wird, ob
  die Alarm-Mail rausgeht.

Befund-Dokumentation (kein Verbiegen):
- Die Alarm-Engine liest ``official_alerts_enabled`` NICHT; ``official_warnings``
  gilt nur als „vorhanden", wenn der Schluessel ``enabled`` darin steht (ein
  leeres ``{}`` faellt auf ``official_alert_triggers_enabled`` zurueck).
- Einzige gewollte Abweichung: „Bericht an, Alarm aus" (``official_warnings
  .enabled=false``, ``official_alerts_enabled=true``) — die ODER-Regel zeigt
  den Schalter „an", der Alarm bleibt bis zum Speichern aus. Nach dem
  Speichern (Schreib-Regel, beide Felder gleich) stimmen Anzeige und Alarm
  in jeder Kombination ueberein.

Kein Mock()/patch(); Quelle ueber die Registrierungs-Naht, Versand ueber
``mail_sink``, Persistenz unter der pytest-isolierten Datenwurzel (#1133).
"""
from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.loader import get_data_root, save_location
from app.trip import Stage, Trip, Waypoint
from app.user import SavedLocation
from services.official_alerts.models import OfficialAlert

from tests.helpers.alert_log_fixtures import settings_email_only
from tests.helpers.compare_briefings import write_compare_briefings

FEHLT = object()  # Schluessel ``official_warnings`` gar nicht im Abo
LAT, LON = 46.62, 13.68


def oder_regel(official_warnings, official_alerts_enabled, triggers) -> bool:
    """Referenz der Spec-Lese-Regel (AC-20). „Vorhanden" heisst hier, wie in
    der Engine: Dict MIT Schluessel ``enabled``."""
    if isinstance(official_warnings, dict) and "enabled" in official_warnings:
        return bool(official_warnings["enabled"]) or official_alerts_enabled is True
    return triggers is not False


# (Name, official_warnings, official_alerts_enabled, official_alert_triggers_enabled,
#  erwarteter Alarm laut heutiger Engine, stimmt mit ODER-Regel ueberein?)
KOMBINATIONEN = [
    ("ohne_schluessel_default", FEHLT, None, None, True, True),
    ("ohne_schluessel_trigger_aus", FEHLT, None, False, False, True),
    ("ohne_schluessel_bericht_aus_trigger_an", FEHLT, False, True, True, True),
    ("ohne_schluessel_bericht_an_trigger_aus", FEHLT, True, False, False, True),
    ("gespeichert_an", {"enabled": True}, True, False, True, True),
    ("gespeichert_aus", {"enabled": False}, False, True, False, True),
    ("gespeichert_aus_trigger_default", {"enabled": False}, False, None, False, True),
    # Altfelder laufen auseinander:
    ("bericht_aus_alarm_an", {"enabled": True}, False, False, True, True),
    ("bericht_an_alarm_aus", {"enabled": False}, True, None, False, False),
    # Leeres Dict = nicht migriert -> Rueckfall auf den Trigger-Schalter.
    ("leeres_dict_trigger_aus", {}, True, False, False, True),
    ("leeres_dict_default", {}, None, None, True, True),
]
IDS = [k[0] for k in KOMBINATIONEN]


def _trip(ow, oae, trig) -> Trip:
    trip = Trip(
        id="trip-ac20", name="AC-20",
        stages=[Stage(id="T1", name="Tag 1", date=datetime.now(timezone.utc).date(),
                      waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON,
                                          elevation_m=1000.0)])],
    )
    trip.official_warnings = None if ow is FEHLT else dict(ow)
    trip.official_alerts_enabled = oae
    trip.official_alert_triggers_enabled = trig
    return trip


@pytest.mark.parametrize("name, ow, oae, trig, alarm, gleich", KOMBINATIONEN, ids=IDS)
def test_trip_alarm_lesart(name, ow, oae, trig, alarm, gleich):
    from services.trip_alert import TripAlertService

    assert TripAlertService._official_trigger_possible(_trip(ow, oae, trig)) is alarm, name


@pytest.mark.parametrize("name, ow, oae, trig, alarm, gleich", KOMBINATIONEN, ids=IDS)
def test_oder_regel_gegen_alarm_lesart(name, ow, oae, trig, alarm, gleich):
    """Dokumentiert, wo Anzeige (ODER-Regel) und Alarm uebereinstimmen. Die
    einzige Abweichung ist „Bericht an, Alarm aus" vor dem Speichern."""
    assert (oder_regel(ow, oae, trig) == alarm) is gleich, name


@pytest.mark.parametrize("wert", [True, False])
@pytest.mark.parametrize("trig", [None, True, False])
def test_nach_speichern_stimmen_anzeige_und_alarm_immer_ueberein(wert, trig):
    """Schreib-Regel: beide Felder gleich -> Alarm == ODER-Regel == Schalter,
    unabhaengig vom Alt-Schalter ``official_alert_triggers_enabled``."""
    from services.trip_alert import TripAlertService

    ow = {"enabled": wert}
    assert oder_regel(ow, wert, trig) is wert
    assert TripAlertService._official_trigger_possible(_trip(ow, wert, trig)) is wert


# ───────────────────────── Orts-Vergleich aus Nutzersicht ────────────────────

class _Quelle:
    """Echte amtliche Quelle (kein Mock), zustaendig fuer den Testort."""

    name = "tdd-2794-ac20"

    def covers(self, lat, lon) -> bool:
        return abs(lat - LAT) < 0.05 and abs(lon - LON) < 0.05

    def fetch(self, lat, lon):
        jetzt = datetime.now(timezone.utc)
        return [OfficialAlert(
            source="tdd-2794-ac20", hazard="extreme_heat", level=2, label="Hitze",
            valid_from=jetzt - timedelta(hours=1), valid_to=jetzt + timedelta(hours=20),
            region_label="Testregion",
        )]


def _vergleich_lauf(ow, oae, trig) -> list:
    import services.official_alerts.base as basis
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = f"tdd-2794-ac20-{uuid.uuid4().hex[:6]}"
    sicherung = list(basis._REGISTERED_SOURCES)
    basis._REGISTERED_SOURCES.clear()
    try:
        save_location(SavedLocation(id="loc-a", name="Ort A", lat=LAT, lon=LON,
                                    elevation_m=1000), user_id=uid)
        preset = {
            "id": "p-ac20", "name": "AC-20", "user_id": uid,
            "location_ids": ["loc-a"], "schedule": "daily", "weekday": 4,
            "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
            "empfaenger": ["dummy@example.com"], "created_at": "2026-08-01T00:00:00Z",
        }
        if ow is not FEHLT:
            preset["official_warnings"] = dict(ow)
        if oae is not None:
            preset["official_alerts_enabled"] = oae
        if trig is not None:
            preset["official_alert_triggers_enabled"] = trig
        write_compare_briefings(get_data_root() / "users" / uid, [preset])
        register_official_alert_source(_Quelle())
        mails: list = []
        CompareOfficialAlertService(
            settings=settings_email_only(), user_id=uid,
            mail_sink=lambda subject, body: mails.append(subject),
        ).check_all_compare_presets()
        return mails
    finally:
        basis._REGISTERED_SOURCES.clear()
        basis._REGISTERED_SOURCES.extend(sicherung)
        shutil.rmtree(get_data_root() / "users" / uid, ignore_errors=True)


@pytest.mark.parametrize("name, ow, oae, trig, alarm, gleich", KOMBINATIONEN, ids=IDS)
def test_vergleich_alarm_lesart_aus_nutzersicht(name, ow, oae, trig, alarm, gleich):
    mails = _vergleich_lauf(ow, oae, trig)
    assert bool(mails) is alarm, (
        f"{name}: erwartet Alarm={alarm}, Mails={mails!r} — Trip- und "
        "Vergleichs-Lesart muessen gleich sein."
    )
