"""TDD RED — Issue #1987 Scheibe S1, AC-11: EIN gemeinsamer Auswertungslauf,
verglichen gegen den AELTESTEN gueltigen Kandidaten.

SPEC: ``docs/specs/modules/fix_1987_kanal_anker.md`` (AC-11).

Die Auslöse-Entscheidung bleibt EIN gemeinsamer
``DeviationAlertEngine.evaluate()``-Lauf (E2, ADR-0021 unangetastet) und
braucht deshalb GENAU EINEN ``cached``-Stand. Gewaehlt wird der AELTESTE
gueltige Kandidat unter den effektiven Kanaelen: nur so geht keinem Kanal
eine Aenderung verloren, die er noch nicht kennt. Gegen Wiederholungs-Alarme
fuer bereits aktuellere Kanaele schuetzt weiterhin das Melde-Gedaechtnis
(``alert_state``, ADR-0056 AC-12).

Test-Politik (kein Mock-Theater): echte ``WeatherSnapshotService``-Dateien in
der pytest-isolierten ``get_data_dir()``-Basis (#1133). Der zweite Test misst
die WIRKUNG ueber den echten Produktivpfad ``check_all_trips()`` — ersetzt
wird ausschliesslich der Provider-Abruf durch eine echte, netzfreie
Implementierung der vorhandenen Abruf-Naht (Haus-Muster
``_FixedSegmentWeatherService`` aus ``test_briefing_anchor_survives_dispatch\
_failure.py``), nicht der Prüfling. Statt auf den an ``evaluate()``
uebergebenen Wert zu spionieren, sind die drei moeglichen Vergleichsbasen so
gewaehlt, dass NUR die richtige (der aelteste Kandidat) einen Alarm ergibt —
der Alarm selbst ist damit der Nachweis.

Pfadregel #1409: alle Prueflinge werden ueber ``app.loader`` bzw. relativ zur
Testdatei aufgeloest, nie ueber einen festen Hauptrepo-Pfad.
"""
from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.helpers.alert_log_fixtures import gust_alert_trip, settings_email_only, weather

# Die drei moeglichen Vergleichsbasen — bewusst so gelegt, dass gegen den
# frischen Stand von 50 km/h NUR der AELTESTE Kandidat ein meldepflichtiges
# Delta (>= 20 km/h) ergibt:
#   SMS  (aeltester, 3 h)  10 -> 50 = Δ40  -> Alarm      (richtig)
#   MAIL (juengster, neu)  45 -> 50 = Δ5   -> kein Alarm (Mutation "juengster")
#   TIER1 (Rueckfall)      48 -> 50 = Δ2   -> kein Alarm (Mutation "Tier 1")
SMS_MERKER_BOE = 10.0
EMAIL_MERKER_BOE = 45.0
TIER1_BOE = 48.0
FRISCH_BOE = 50.0

SMS_MERKER_ALTER = timedelta(hours=3)  # innerhalb der 4h-Ceiling: gueltig


def _nutzer(prefix: str) -> str:
    return f"tdd-1987-{prefix}-{uuid.uuid4().hex[:6]}"


def _wetter(gust_kmh: float, segment=None):
    daten = dataclasses.replace(
        weather(1, gust_max_kmh=gust_kmh), fetched_at=datetime.now(timezone.utc),
    )
    return dataclasses.replace(daten, segment=segment) if segment is not None else daten


def _ortstag(trip) -> date:
    from services.trip_day import trip_local_today

    return trip_local_today(trip, datetime.now(timezone.utc))


def _anker_pfad(user_id: str, trip_id: str, channel: str) -> Path:
    from app.loader import get_snapshots_dir

    return get_snapshots_dir(user_id) / f"{trip_id}_alarm_anchor_{channel}.json"


def _zurueckdatieren(user_id: str, trip_id: str, channel: str, alter: timedelta) -> None:
    """Laesst einen Kanal-Merker ``alter`` alt aussehen — ``save_alarm_anchor()``
    schreibt immer die Schreibzeit als ``snapshot_at``."""
    pfad = _anker_pfad(user_id, trip_id, channel)
    assert pfad.exists(), (
        f"Fixtur-Schutz: der kanalscharfe Merker muss unter {pfad.name!r} "
        "liegen (Spec: '{trip_id}_alarm_anchor_{channel}.json')."
    )
    daten = json.loads(pfad.read_text())
    daten["snapshot_at"] = (datetime.now(timezone.utc) - alter).isoformat()
    pfad.write_text(json.dumps(daten, indent=2))


def _sms_kanal_freischalten(user_id: str) -> None:
    """SMS haengt am Nutzerlevel (``services/user_tier.py``) — ohne
    ``tier >= standard`` faellt der Kanal aus ``_effective_alert_channels()``
    heraus und der Test haette nur EINEN Kandidaten."""
    from app.loader import get_data_dir

    verzeichnis = get_data_dir(user_id)
    verzeichnis.mkdir(parents=True, exist_ok=True)
    (verzeichnis / "user.json").write_text(
        json.dumps({"id": user_id, "tier": "premium"}), encoding="utf-8",
    )


def _zwei_kandidaten_anlegen(user_id: str, trip, heute: date) -> None:
    """Ausgangslage beider Tests: SMS-Merker von "06:00", E-Mail-Merker von
    "09:00", dazu ein taggleicher Tier-1-Briefing-Anker als Rueckfall.

    Der Tier-1-Anker wird bewusst UNDATIERT abgelegt: bei einem vorhandenen
    DATIERTEN Anker steigt ``_get_cached_weather()`` sofort aus und die
    Kanal-Aufloesung kaeme nie zum Zug (der Test waere trivial wahr).
    """
    from services.weather_snapshot import WeatherSnapshotService

    svc = WeatherSnapshotService(user_id=user_id)
    svc.save(trip.id, [_wetter(TIER1_BOE)], heute)
    svc.save_alarm_anchor(trip.id, heute, [_wetter(SMS_MERKER_BOE)], channel="sms")
    _zurueckdatieren(user_id, trip.id, "sms", SMS_MERKER_ALTER)
    svc.save_alarm_anchor(trip.id, heute, [_wetter(EMAIL_MERKER_BOE)], channel="email")


def _zwei_kanal_trip(trip_id: str):
    return gust_alert_trip(trip_id, alert_channels={"email": True, "sms": True})


# ═════════════════════════════════ AC-11 ═════════════════════════════════════


def test_ac11_gemeinsame_vergleichsbasis_ist_der_aelteste_gueltige_kandidat():
    """AC-11 (Auswahl).

    GIVEN zwei Alarmkanaele mit unterschiedlich alten, beide gueltigen
          Kandidaten-Merkern (E-Mail von "09:00", SMS von "06:00") und einem
          taggleichen Tier-1-Briefing-Anker.
    WHEN  der EINE gemeinsame Auswertungslauf seine Vergleichsbasis aufloest.
    THEN  ist es der SMS-Merker von "06:00" — der AELTERE der beiden
          Kandidaten —, damit auch die Aenderung zwischen "06:00" und "09:00"
          gemeldet wird, die der SMS-Kanal noch nicht kennt.

    HEUTE ROT: ``save_alarm_anchor()`` kennt keinen ``channel``-Parameter
    (TypeError) — es gibt nur einen kanallosen Merker, also gar keine Auswahl.

    Mutations-Gegenprobe (Spec Nr. 4): waehlt die Aufloesung den JUENGSTEN
    statt den AELTESTEN Kandidaten, liefert sie ``EMAIL_MERKER_BOE`` und
    dieser Test wird rot.
    """
    user_id, trip_id = _nutzer("ac11"), "trip-1987-ac11"
    _sms_kanal_freischalten(user_id)
    trip = _zwei_kanal_trip(trip_id)
    _zwei_kandidaten_anlegen(user_id, trip, _ortstag(trip))

    from services.trip_alert import TripAlertService

    svc = TripAlertService(settings=settings_email_only(), user_id=user_id)
    assert svc._effective_alert_channels(trip) == {"email", "sms"}, (
        "Fixtur-Schutz: es muessen ZWEI effektive Alarmkanaele vorliegen, "
        f"erhalten: {svc._effective_alert_channels(trip)!r} — mit nur einem "
        "Kanal gaebe es nichts auszuwaehlen."
    )

    basis = svc._get_cached_weather(trip, tagesgleicher_anker_noetig=True)

    assert basis, "AC-11: beide Kandidaten sind gueltig, es MUSS eine Basis geben."
    assert basis[0].aggregated.gust_max_kmh == pytest.approx(SMS_MERKER_BOE), (
        f"AC-11: verglichen werden muss gegen den AELTESTEN gueltigen "
        f"Kandidaten ({SMS_MERKER_BOE} km/h, SMS-Merker von '06:00'). "
        f"Erhalten: {basis[0].aggregated.gust_max_kmh} km/h — "
        f"{EMAIL_MERKER_BOE} hiesse: der JUENGSTE Kandidat gewinnt und dem "
        f"schlechter versorgten Kanal wird eine Aenderung unterschlagen; "
        f"{TIER1_BOE} hiesse: die Kanal-Kandidaten werden gar nicht erst "
        "herangezogen."
    )


def test_ac11_wirkung_aenderung_die_nur_der_aeltere_kanal_kennt_wird_gemeldet(monkeypatch):
    """AC-11 (Wirkung am Produktivpfad).

    GIVEN dieselbe Ausgangslage wie oben, und die frische Vorhersage liegt bei
          50 km/h.
    WHEN  der regulaere Alarm-Lauf ``check_all_trips()`` fuer diese Tour
          durchlaeuft.
    THEN  geht ein Alarm raus — denn gegen den SMS-Merker von "06:00"
          (10 km/h) betraegt das Delta 40 km/h. Gegen den E-Mail-Merker
          (45 km/h, Δ5) oder den Tier-1-Anker (48 km/h, Δ2) bliebe es still.
          Der Alarm ist damit selbst der Nachweis, WELCHE Basis in den EINEN
          gemeinsamen Auswertungslauf gegangen ist.

    HEUTE ROT: ``save_alarm_anchor()`` kennt keinen ``channel``-Parameter
    (TypeError).

    Mutations-Gegenprobe (Spec Nr. 4): waehlt die Aufloesung den JUENGSTEN
    Kandidaten, bleibt der Lauf still (``alerts_sent == 0``, keine Mail) und
    dieser Test wird rot — genau der stille Ausfall, den die Scheibe fuer
    schlechter versorgte Kanaele verhindern soll.
    """
    import services.segment_weather as sw_mod
    from app.loader import save_trip
    from services.trip_alert import TripAlertService

    user_id, trip_id = _nutzer("ac11w"), "trip-1987-ac11w"
    _sms_kanal_freischalten(user_id)
    trip = _zwei_kanal_trip(trip_id)
    save_trip(trip, user_id=user_id)
    _zwei_kandidaten_anlegen(user_id, trip, _ortstag(trip))

    class _FesteWetterquelle:
        """Echte, netzfreie Implementierung der Abruf-Naht von
        ``_fetch_fresh_weather()`` — der Zeitfilter dort laeuft unveraendert."""

        def __init__(self, provider=None) -> None:
            self._provider = provider

        def fetch_segment_weather(self, segment, **kwargs):
            return _wetter(FRISCH_BOE, segment=segment)

    monkeypatch.setattr(sw_mod, "SegmentWeatherService", _FesteWetterquelle)

    mails: list = []
    ergebnis = TripAlertService(
        settings=settings_email_only(), user_id=user_id,
        mail_sink=lambda subject, body: mails.append(subject),
    ).check_all_trips()

    assert ergebnis.alerts_sent == 1, (
        "AC-11 (Wirkung): der Lauf muss die Aenderung melden, die nur der "
        f"aeltere SMS-Kandidat noch nicht kennt ({SMS_MERKER_BOE} -> "
        f"{FRISCH_BOE} km/h). Erhalten: alerts_sent="
        f"{ergebnis.alerts_sent} — still bleibt der Lauf genau dann, wenn "
        f"gegen den juengeren E-Mail-Merker ({EMAIL_MERKER_BOE}) oder den "
        f"Tier-1-Anker ({TIER1_BOE}) verglichen wurde."
    )
    assert mails, (
        "AC-11 (Wirkung): es muss tatsaechlich eine Meldung rausgehen — sonst "
        "ist die Auswertung nur formal gelaufen."
    )
