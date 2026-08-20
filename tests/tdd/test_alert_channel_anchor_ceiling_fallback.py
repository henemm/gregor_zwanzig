"""TDD RED — Issue #1987 Scheibe S1: Kandidaten-Aufloesung je Kanal.

SPEC: ``docs/specs/modules/fix_1987_kanal_anker.md`` (AC-4, AC-7, AC-8).

Gepruefte Zusicherung in einem Satz: der rollierende Tier-2-Merker EINES
Kanals entscheidet ausschliesslich ueber die Vergleichsbasis DIESES Kanals —
ist er zu alt (AC-4), gar nicht vorhanden (AC-7) oder vom falschen Tag
(AC-8), faellt die Kette fuer diesen Kanal auf den taggleichen
Tier-1-Briefing-Anker zurueck und ausdruecklich NICHT auf den (ggf.
frischeren) Merker eines ANDEREN Kanals (Kontaminationsverbot).

Angenommene API (die Spec legt den Pflicht-Parameter fest, nicht die
Aufrufform): ``WeatherSnapshotService.save_alarm_anchor(...)``/
``.load_alarm_anchor(...)``/``.alarm_anchor_target_date(...)`` bekommen
``channel`` als Pflicht-Parameter; die Kanal-Aufloesung selbst passiert
INNERHALB von ``TripAlertService._get_cached_weather()`` ueber die effektiven
Alarmkanaele des Trips. Deshalb konfigurieren die Tests hier eine Tour mit
GENAU EINEM effektiven Kanal (``alert_channels={"email": True}``) — damit ist
die AC-11-Aggregation (aeltester Kandidat) trivial und der Rueckgabewert von
``_get_cached_weather()`` ist exakt der Kandidat dieses einen Kanals. Aendert
die Umsetzung die Aufrufform, betrifft das die Aufrufstellen hier, nicht die
Zusicherungen.

Test-Politik (kein Mock-Theater): echte ``WeatherSnapshotService``-Dateien in
der pytest-isolierten ``get_data_dir()``-Basis (#1133), echter
``_get_cached_weather()``-Pfad, Vergleich ueber GELADENE Objekte
(``aggregated.gust_max_kmh``), nie ueber einen Dateiinhalt-String. Die
Rueckdatierung eines Merkers ist reine Testdaten-Manipulation der Persistenz
(Vorbild: ``test_alert_rolling_anchor.py``, F002-Test), kein Patch des
Prueflings.

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

# Unverwechselbare Boeen-Werte — sie sagen, WELCHER Stand als Vergleichsbasis
# gewaehlt wurde. Ein Zeitstempel allein koennte das nicht: alle drei Anker
# werden im selben Testlauf geschrieben.
TIER1_BOE = 11.0        # taggleicher Briefing-Anker (der erwartete Rueckfall)
EMAIL_MERKER_BOE = 22.0  # Tier-2-Merker des geprueften Kanals (ungueltig)
FREMDER_MERKER_BOE = 33.0  # Tier-2-Merker eines ANDEREN Kanals (Kontamination)


def _nutzer(prefix: str) -> str:
    return f"tdd-1987-{prefix}-{uuid.uuid4().hex[:6]}"


def _wetter(gust_kmh: float):
    return dataclasses.replace(
        weather(1, gust_max_kmh=gust_kmh), fetched_at=datetime.now(timezone.utc),
    )


def _ortstag(trip) -> date:
    """Der Tag, den der Alarm-Pfad selbst benutzt (``trip_local_today``) —
    nicht ``date.today()`` des Servers, sonst prueft der Test an der
    Tagesgrenze einen anderen Tag als der Pruefling."""
    from services.trip_day import trip_local_today

    return trip_local_today(trip, datetime.now(timezone.utc))


def _anker_pfad(user_id: str, trip_id: str, channel: str) -> Path:
    """Ablageort des kanalscharfen Tier-2-Merkers (Spec, Implementation
    Details: ``{trip_id}_alarm_anchor_{channel}.json``)."""
    from app.loader import get_snapshots_dir

    return get_snapshots_dir(user_id) / f"{trip_id}_alarm_anchor_{channel}.json"


def _zurueckdatieren(user_id: str, trip_id: str, channel: str, alter: timedelta) -> None:
    """Laesst einen bereits geschriebenen Kanal-Merker ``alter`` alt aussehen.

    ``save_alarm_anchor()`` schreibt bewusst immer die SCHREIBZEIT als
    ``snapshot_at`` (aus ihr leitet ``load_alarm_anchor()`` das ``fetched_at``
    ab) — ein alter Merker laesst sich deshalb nur so herstellen.
    """
    pfad = _anker_pfad(user_id, trip_id, channel)
    assert pfad.exists(), (
        f"Fixtur-Schutz: der kanalscharfe Merker muss unter {pfad.name!r} "
        "liegen (Spec: '{trip_id}_alarm_anchor_{channel}.json'). Fehlt er, "
        "misst dieser Test nichts."
    )
    daten = json.loads(pfad.read_text())
    daten["snapshot_at"] = (datetime.now(timezone.utc) - alter).isoformat()
    pfad.write_text(json.dumps(daten, indent=2))


def _vergleichsbasis(user_id: str, trip):
    """Die Vergleichsbasis, die der Abweichungs-Alarm tatsaechlich benutzt.

    ``_get_cached_weather(..., tagesgleicher_anker_noetig=True)`` ist genau
    der Wert, den ``check_all_trips()`` als ``cached`` an
    ``check_and_send_alerts()`` und damit an ``DeviationAlertEngine.evaluate()``
    weiterreicht — Pruefort = Wirkort.
    """
    from services.trip_alert import TripAlertService

    return TripAlertService(
        settings=settings_email_only(), user_id=user_id,
    )._get_cached_weather(trip, tagesgleicher_anker_noetig=True)


def _nur_email_trip(trip_id: str):
    """Tour mit GENAU EINEM effektiven Alarmkanal (E-Mail) — s. Modul-Docstring."""
    return gust_alert_trip(trip_id, alert_channels={"email": True})


def _tier1_briefing_anker(user_id: str, trip_id: str, tag: date) -> None:
    """Taggleicher Tier-1-Briefing-Anker, UNDATIERT abgelegt.

    Bewusst ohne ``save_dated()``: die Kette in ``_get_cached_weather()``
    steigt bei einem vorhandenen DATIERTEN Anker sofort aus
    (``load_dated`` -> return), der rollierende Zweig kaeme dann nie zum Zug
    und diese Tests waeren trivial wahr. Der undatierte Anker mit
    ``target_date = heute`` und ``briefing_backed=True`` ist ebenfalls ein
    taggleicher Briefing-Anker (AC-4 „While ein taggleicher Tier-1-\
    Briefing-Anker vorhanden ist"), erzwingt aber, dass die Kanal-Aufloesung
    tatsaechlich durchlaufen wird.
    """
    from services.weather_snapshot import WeatherSnapshotService

    WeatherSnapshotService(user_id=user_id).save(trip_id, [_wetter(TIER1_BOE)], tag)


# ═════════════════════════════════ AC-4 ══════════════════════════════════════


def test_ac4_zu_alter_kanal_merker_faellt_auf_tier1_nicht_auf_fremden_kanal():
    """AC-4.

    GIVEN der rollierende Tier-2-Merker des Kanals ``email`` ist 5 h alt (die
          Alterungs-Obergrenze ``_ALARM_ANCHOR_CEILING`` betraegt 4 h), ein
          taggleicher Tier-1-Briefing-Anker liegt vor, und der Kanal
          ``telegram`` hat einen FRISCHEN eigenen Merker.
    WHEN  die Vergleichsbasis fuer die Tour aufgeloest wird, deren einziger
          effektiver Alarmkanal ``email`` ist.
    THEN  wird gegen den Tier-1-Briefing-Anker verglichen — weder gegen den
          eigenen, zu alten Merker noch gegen den frischeren Merker des
          fremden Kanals (Kontaminationsverbot).

    HEUTE ROT: ``save_alarm_anchor()`` kennt keinen ``channel``-Parameter
    (TypeError) — es gibt gar keine kanalscharfen Merker.

    Mutations-Gegenprobe (Spec Nr. 3): greift der Ceiling-Rueckfall auf den
    Merker eines anderen Kanals zu, liefert dieser Test
    ``FREMDER_MERKER_BOE`` statt ``TIER1_BOE`` und wird rot.
    """
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = _nutzer("ac4"), "trip-1987-ac4"
    trip = _nur_email_trip(trip_id)
    heute = _ortstag(trip)
    svc = WeatherSnapshotService(user_id=user_id)

    _tier1_briefing_anker(user_id, trip_id, heute)
    svc.save_alarm_anchor(trip_id, heute, [_wetter(EMAIL_MERKER_BOE)], channel="email")
    _zurueckdatieren(user_id, trip_id, "email", timedelta(hours=5))
    svc.save_alarm_anchor(trip_id, heute, [_wetter(FREMDER_MERKER_BOE)], channel="telegram")

    basis = _vergleichsbasis(user_id, trip)

    assert basis, (
        "AC-4: ein zu alter Kanal-Merker darf die Wache nicht blind machen — "
        "es liegt ein gueltiger, taggleicher Tier-1-Briefing-Anker vor."
    )
    assert basis[0].aggregated.gust_max_kmh == pytest.approx(TIER1_BOE), (
        f"AC-4: die Vergleichsbasis des Kanals 'email' muss der "
        f"Tier-1-Briefing-Anker ({TIER1_BOE} km/h) sein. Erhalten: "
        f"{basis[0].aggregated.gust_max_kmh} km/h — "
        f"{EMAIL_MERKER_BOE} hiesse: die 4h-Ceiling wird beim LESEN nicht "
        f"geprueft; {FREMDER_MERKER_BOE} hiesse: der Rueckfall greift auf den "
        "Merker eines ANDEREN Kanals zu und kontaminiert die Vergleichsbasis "
        "mit einem Stand, den dieser Empfaenger nie erhalten hat."
    )


# ═════════════════════════════════ AC-7 ══════════════════════════════════════


def test_ac7_kanal_ohne_eigenen_merker_faellt_auf_tier1_und_bleibt_alarmfaehig():
    """AC-7.

    GIVEN der Kanal ``email`` hat noch NIE einen eigenen Tier-2-Merker
          bekommen und es existiert auch keine kanallose Altdatei; ein
          taggleicher Tier-1-Briefing-Anker liegt vor, und der Kanal
          ``telegram`` hat einen eigenen, frischen Merker.
    WHEN  die Vergleichsbasis fuer die Tour aufgeloest wird, deren einziger
          effektiver Alarmkanal ``email`` ist.
    THEN  faellt sie auf den Tier-1-Briefing-Anker zurueck (NICHT ``None``,
          die Tour bleibt alarmfaehig) und uebernimmt NICHT den Merker des
          fremden Kanals — die groebere, aber gueltige Vergleichsbasis ist die
          dokumentierte Praezisionsgrenze von S1, kein Fehler.

    HEUTE ROT: ``save_alarm_anchor()`` kennt keinen ``channel``-Parameter
    (TypeError). Der Rueckfall auf Tier 1 an sich ist Bestandsverhalten —
    NEU und ab GREEN bewacht ist, dass ein fremder Kanal-Merker ihn nicht
    verdraengt.
    """
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = _nutzer("ac7"), "trip-1987-ac7"
    trip = _nur_email_trip(trip_id)
    heute = _ortstag(trip)

    _tier1_briefing_anker(user_id, trip_id, heute)
    WeatherSnapshotService(user_id=user_id).save_alarm_anchor(
        trip_id, heute, [_wetter(FREMDER_MERKER_BOE)], channel="telegram",
    )
    assert not _anker_pfad(user_id, trip_id, "email").exists(), (
        "Fixtur-Schutz: der geprueft Kanal darf keinen eigenen Merker haben."
    )

    basis = _vergleichsbasis(user_id, trip)

    assert basis, (
        "AC-7: ein Kanal ohne eigenen Merker muss weiterhin Alarme bekommen — "
        "der Rueckfall auf den Tier-1-Briefing-Anker ist die dokumentierte "
        "Praezisionsgrenze, kein Grund fuer eine blinde Wache."
    )
    assert basis[0].aggregated.gust_max_kmh == pytest.approx(TIER1_BOE), (
        f"AC-7: erwartet wird der Tier-1-Briefing-Anker ({TIER1_BOE} km/h), "
        f"erhalten: {basis[0].aggregated.gust_max_kmh} km/h — "
        f"{FREMDER_MERKER_BOE} hiesse: ein Kanal ohne eigenen Merker erbt den "
        "Stand eines fremden Kanals (als Kontamination verworfen, s. Spec "
        "'Known Limitations')."
    )


# ═════════════════════════════════ AC-8 ══════════════════════════════════════


def test_ac8_kanal_merker_vom_falschen_tag_wird_je_kanal_verworfen():
    """AC-8.

    GIVEN der Tier-2-Merker des Kanals ``email`` traegt ``target_date =
          gestern`` (#823/#1916 AC-10), der Merker des Kanals ``telegram``
          traegt korrekt HEUTE, und ein taggleicher Tier-1-Briefing-Anker
          liegt vor.
    WHEN  die Vergleichsbasis fuer die Tour aufgeloest wird, deren einziger
          effektiver Alarmkanal ``email`` ist.
    THEN  wird der Merker vom falschen Tag verworfen und die Kette faellt fuer
          DIESEN Kanal auf den Tier-1-Briefing-Anker zurueck — die
          Tagesgrenze gilt je Kanal, und der taggleiche Merker des anderen
          Kanals springt nicht ein.

    HEUTE ROT: ``save_alarm_anchor()``/``alarm_anchor_target_date()`` kennen
    keinen ``channel``-Parameter (TypeError).
    """
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = _nutzer("ac8"), "trip-1987-ac8"
    trip = _nur_email_trip(trip_id)
    heute = _ortstag(trip)
    gestern = heute - timedelta(days=1)
    svc = WeatherSnapshotService(user_id=user_id)

    _tier1_briefing_anker(user_id, trip_id, heute)
    svc.save_alarm_anchor(trip_id, gestern, [_wetter(EMAIL_MERKER_BOE)], channel="email")
    svc.save_alarm_anchor(trip_id, heute, [_wetter(FREMDER_MERKER_BOE)], channel="telegram")

    assert svc.alarm_anchor_target_date(trip_id, channel="email") == gestern, (
        "AC-8: der Tagesbezug muss JE KANAL lesbar sein — sonst kann die "
        "Tagesgrenze nicht je Kanal greifen."
    )
    assert svc.alarm_anchor_target_date(trip_id, channel="telegram") == heute, (
        "AC-8: der Tagesbezug des anderen Kanals darf davon unberuehrt sein."
    )

    basis = _vergleichsbasis(user_id, trip)

    assert basis, (
        "AC-8: ein Merker vom falschen Tag darf die Wache nicht blind machen — "
        "es liegt ein gueltiger, taggleicher Tier-1-Briefing-Anker vor."
    )
    assert basis[0].aggregated.gust_max_kmh == pytest.approx(TIER1_BOE), (
        f"AC-8: erwartet wird der Tier-1-Briefing-Anker ({TIER1_BOE} km/h), "
        f"erhalten: {basis[0].aggregated.gust_max_kmh} km/h — "
        f"{EMAIL_MERKER_BOE} hiesse: die Tagesgrenze greift fuer den "
        f"kanalscharfen Merker gar nicht; {FREMDER_MERKER_BOE} hiesse: der "
        "taggleiche Merker eines ANDEREN Kanals springt ein."
    )
