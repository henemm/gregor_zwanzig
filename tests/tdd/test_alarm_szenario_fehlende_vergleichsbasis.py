"""TDD RED — Issue #2050 Szenario 12: fehlende Vergleichsbasis wird
protokolliert statt lautlos zu verschwinden (Anforderungen D-2, E-1).

SPEC:    docs/specs/modules/feat_2050_sz12_fehlende_vergleichsbasis.md (AC-1..AC-16)
KONTEXT: docs/context/feat-2050-sz12-fehlende-vergleichsbasis.md

Heute endet ein laufender Trip bzw. ein aktiver Ortsvergleich ohne gueltige
Vergleichsbasis ohne jede Spur im Alarmprotokoll des Nutzers — der Grund
steht nur in ``diagnostics/alert_anchor_rejected.jsonl``. Diese Datei fordert
genau EINEN benannten Eintrag ``no_reference_basis`` je Nutzer + Entity + Tag
+ Untergrund.

Einstiege (Spec „Geplante Tests"): die ECHTEN Laeufe
``TripAlertService.check_all_trips()`` und
``CompareAlertService.check_all_compare_presets()`` — NICHT
``AlarmPruefstrecke(zweig="deviation")``, der den Fehl-Anker-Pfad gar nicht
erreicht.

Testpolitik (CLAUDE.md, „Zwei Schichten", Kern):

* Kein Mock-Theater. Persistenz ueber die pytest-isolierte
  ``get_data_dir()``-Basis (#1133), Versand ueber die ``mail_sink``-Naht,
  Wetter ueber den Offline-``FixtureProvider`` (autouse, #346) bzw. eine
  echte ``LocationWeatherSource``-Implementierung ohne Netz. Gezaehlt wird
  ueber DELEGIERENDE Beobachter (die echte Methode laeuft unveraendert).
* Die Uhr ist gestellt (``tests/helpers/wanduhr.anker_aus``): 10:00 UTC des
  heutigen Tages (12:00 Ortszeit an den Fixtur-Koordinaten) — weit weg von
  jeder Tagesgrenze, sonst teilte ein 15-Minuten-Schritt (AC-3) den Tag.
* Gelesen wird das ROHE ``not_delivered`` des Nutzers: die Leseseite
  ``read_undelivered()`` fasst Eintraege binnen ``DEDUP_WINDOW`` (2 min)
  zusammen und wuerde fehlende Entdopplung beim Zaehlen verdecken; sie traegt
  zudem ``reference_gap``/``reference_day``/``reference_at`` nicht.

Der Sperrgrund steht NICHT als eigener Schluessel im Eintrag, sondern als
``channels_not_sent[].reason`` (``append_suppressed_entry``); der Top-Level-
``reason`` ist der AUSLOESER.

Pfadregel #1409: alles ueber ``app.loader`` bzw. relativ zu dieser Datei.
"""
from __future__ import annotations

import contextlib
import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from freezegun import freeze_time

from app.loader import get_data_dir, get_snapshots_dir, save_location, save_trip
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from app.trip import Stage, Trip, Waypoint

from tests.helpers.alert_log_fixtures import (
    LAT,
    LON,
    read_log,
    settings_email_only,
)
from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip
from tests.helpers.nowcast_gate_fixtures import (
    clean_uid,
    location,
    quiet_window_elsewhere,
    radar_preset,
    write_presets,
    write_user_tier,
)
from tests.helpers.ortstag import ortstag
from tests.helpers.wanduhr import anker_aus

# Der neue Grund — bewusst als Literal: ``alert_log.REASON_NO_REFERENCE_BASIS``
# existiert vor der Implementierung noch nicht, ein Import auf Modulebene liesse
# die ganze Datei beim Sammeln scheitern.
GRUND = "no_reference_basis"

# Bewusst absurd hoch (Vorbild ``test_alert_anchor_day_guard.py``): das Delta
# gegen JEDE reale Vorhersage reisst die Boeen-Standardschwelle (20 km/h).
ANKER_BOE_KMH = 200.0


# ═══════════════════════════════ Uhr & Nutzer ════════════════════════════════

def _uhr(versatz: timedelta = timedelta(0)):
    """Gestellte Uhr: heute 10:00 UTC (+ ``versatz``), ohne Ticken."""
    return freeze_time(anker_aus("10:00") + versatz)


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


def _heute() -> date:
    """Ortstag an den Fixtur-Koordinaten, gemessen an der GESTELLTEN Uhr."""
    return ortstag(LAT, LON, now_utc=_jetzt())


def nutzer(praefix: str) -> str:
    return f"tdd-sz12-{praefix}-{uuid.uuid4().hex[:6]}"


# ═══════════════════════════════ Trip-Bausteine ══════════════════════════════
# Aufbau wie ``tests/tdd/test_alert_anchor_day_guard.py`` (#1661/#1699).

def _segment(segment_id: str) -> TripSegment:
    jetzt = _jetzt()
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500,
                           distance_from_start_km=6.0),
        start_time=jetzt - timedelta(hours=1),
        end_time=jetzt + timedelta(hours=3),
        duration_hours=4.0, distance_km=6.0, ascent_m=500, descent_m=0,
    )


def _wetter(boe_kmh: float) -> SegmentWeatherData:
    stunde = _jetzt().replace(minute=0, second=0, microsecond=0)
    punkte = [
        ForecastDataPoint(ts=stunde + timedelta(hours=h), t2m_c=12.0 + h,
                          wind10m_kmh=boe_kmh / 2, gust_kmh=boe_kmh,
                          precip_1h_mm=0.0)
        for h in range(4)
    ]
    return SegmentWeatherData(
        segment=_segment("1"),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                              grid_res_km=1.0),
            data=punkte,
        ),
        aggregated=SegmentWeatherSummary(
            gust_max_kmh=boe_kmh, wind_max_kmh=boe_kmh / 2,
            temp_max_c=15.0, temp_min_c=8.0, precip_sum_mm=0.0,
        ),
        fetched_at=_jetzt(),
        provider="openmeteo",
    )


def boeen_trip(trip_id: str, tage: list[date]) -> Trip:
    """Trip mit scharfer Boeen-Delta-Regel und frei waehlbaren Etappentagen.
    Ein Wegpunkt je Etappe (Ratsche ``test_fixture_wallclock_ratchet.py``)."""
    stages = [
        Stage(id=f"T{i}", name=f"Tag {i}", date=tag,
              waypoints=[Waypoint(id=f"G{i}", name="Start", lat=LAT, lon=LON,
                                  elevation_m=1000.0)])
        for i, tag in enumerate(tage, start=1)
    ]
    trip = Trip(
        id=trip_id, name=f"Basis-{trip_id}", stages=stages,
        official_warnings=None, corridors=[],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=[MetricConfig(metric_id="gust", enabled=True)],
            metric_alert_levels={"wind_gust": "standard"},
        ),
    )
    # #1594: Briefing-Zeiten ausserhalb des Vorlauf-Fensters — Vorbedingung.
    morgen, abend = briefing_zeiten_fuer_trip(trip)
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=True,
                                          alert_on_changes=True,
                                          morning_time=morgen, evening_time=abend)
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    return trip


def laufender_trip(trip_id: str, heute: date, *, tage_davor: int = 1,
                   tage_danach: int = 1) -> Trip:
    """``start_date <= heute <= end_date`` — die Wache laeuft (#1661 C2)."""
    tage = [heute + timedelta(days=d) for d in range(-tage_davor, tage_danach + 1)]
    trip = boeen_trip(trip_id, tage)
    assert trip.start_date <= heute <= trip.end_date, "Fixtur-Schutz: Trip laeuft"
    return trip


def zweiter_wegpunkt(trip: Trip) -> Trip:
    """Zweiter Wegpunkt je Etappe — unter zwei Wegpunkten liefert
    ``convert_trip_to_segments`` keine Segmente, die Abfrage schriebe keinen
    Snapshot (Vorbild ``abfrage_trip`` in ``test_alert_anchor_day_guard.py``)."""
    for stage in trip.stages:
        stage.waypoints.append(Waypoint(id=f"{stage.id}-Z", name="Ziel",
                                        lat=LAT + 0.1, lon=LON + 0.1,
                                        elevation_m=1500.0))
    return trip


def abfrage_glance(user_id: str, trip: Trip):
    """``### query: glance`` durch den ECHTEN Inbound-Pfad — genau dieser Weg
    schreibt den nicht briefing-gestuetzten Anker (#1699)."""
    from services.trip_command_processor import InboundMessage, TripCommandProcessor

    return TripCommandProcessor().process(InboundMessage(
        channel="telegram", trip_name=trip.name, body="### query: glance",
        sender="tdd-sz12", received_at=_jetzt(), user_id=user_id,
    ))


def briefing_anker_schreiben(user_id: str, trip_id: str, target_date: date) -> Path:
    """Der Briefing-Schreibweg (``_write_briefing_anchor`` ->
    ``WeatherSnapshotService.save``) mit echtem Zieltag — nichts von Hand."""
    from services.weather_snapshot import WeatherSnapshotService

    WeatherSnapshotService(user_id=user_id).save(
        trip_id, [_wetter(ANKER_BOE_KMH)], target_date,
    )
    return get_snapshots_dir(user_id) / f"{trip_id}.json"


def alarm_lauf(user_id: str):
    from services.trip_alert import TripAlertService

    mails: list[tuple[str, str]] = []
    ergebnis = TripAlertService(
        settings=settings_email_only(), user_id=user_id,
        mail_sink=lambda subject, body: mails.append((subject, body)),
    ).check_all_trips()
    return ergebnis, mails


def diagnose_zeilen(user_id: str) -> list[dict]:
    pfad = get_data_dir(user_id) / "diagnostics" / "alert_anchor_rejected.jsonl"
    if not pfad.exists():
        return []
    return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]


def ortstag_des_trips(trip: Trip) -> date:
    """Der Tag, den der Lauf selbst verwendet (``trip_local_today``)."""
    from services.trip_day import trip_local_today

    return trip_local_today(trip, _jetzt())


# ═══════════════════════════════ Leseseite ═══════════════════════════════════

def _sperrgruende(eintrag: dict) -> set[str]:
    return {
        item.get("reason") for item in eintrag.get("channels_not_sent") or []
        if isinstance(item, dict)
    }


def no_ref_eintraege(user_id: str, entity_id: str, entity_type: str = "trip") -> list[dict]:
    """ROHE ``not_delivered``-Eintraege dieser Kennung mit Sperrgrund
    ``no_reference_basis`` (bewusst ohne die Lese-Zusammenfassung)."""
    return [
        e for e in read_log(user_id)["not_delivered"]
        if (e.get("entity_id") or e.get("trip_id")) == entity_id
        and (e.get("entity_type") or "trip") == entity_type
        and GRUND in _sperrgruende(e)
    ]


def alle_no_ref_eintraege(user_id: str) -> list[dict]:
    return [e for e in read_log(user_id)["not_delivered"] if GRUND in _sperrgruende(e)]


def _genau_ein_eintrag(user_id: str, entity_id: str, entity_type: str = "trip") -> dict:
    eintraege = no_ref_eintraege(user_id, entity_id, entity_type)
    assert len(eintraege) == 1, (
        f"Erwartet GENAU EINEN Protokoll-Eintrag '{GRUND}' fuer "
        f"{entity_type}/{entity_id} — gefunden {len(eintraege)}. Heute endet "
        "der Lauf ohne Vergleichsbasis ohne jede Spur im Alarmprotokoll "
        f"(nur Diagnosedatei). not_delivered: {read_log(user_id)['not_delivered']!r}"
    )
    eintrag = eintraege[0]
    assert _sperrgruende(eintrag) == {GRUND}, (
        f"Der Eintrag muss GENAU den Grund '{GRUND}' tragen (kein "
        f"zusammengesetzter String), gefunden {_sperrgruende(eintrag)!r}"
    )
    return eintrag


def _als_utc(wert) -> datetime | None:
    """ISO-Zeitstempel als UTC-behafteter Zeitpunkt (``Z``/``+00:00``/naiv =
    UTC, Hausnorm #1345) — verglichen wird der WERT, nicht die Schreibweise."""
    try:
        zeitpunkt = datetime.fromisoformat(str(wert).replace("Z", "+00:00"))
    except ValueError:
        return None
    return zeitpunkt if zeitpunkt.tzinfo else zeitpunkt.replace(tzinfo=timezone.utc)


def _referenz_trifft(reference_at, anker_roh: dict) -> bool:
    """``reference_at`` ist Ankerdatum ODER Schreibzeitpunkt des verworfenen
    Ankers (Spec laesst beides zu) — gegen die Werte der Anker-Datei selbst."""
    if not isinstance(reference_at, str) or not reference_at:
        return False
    target = anker_roh.get("target_date")
    if target is not None and len(reference_at) == 10:
        return reference_at == str(target)
    geschrieben = _als_utc(anker_roh.get("snapshot_at"))
    return geschrieben is not None and _als_utc(reference_at) == geschrieben


# ═════════════════════════ Zaehlender Abruf-Beobachter ════════════════════════

class _AbrufZaehler:
    """DELEGIERENDER Beobachter auf ``SegmentWeatherService.fetch_segment_weather``
    — die Grenze, an der der Alarm-Lauf einen Wetterabruf ausloest, VOR dem
    geteilten 10-Minuten-Cache (ein Zaehler am Provider zeigte bei einem
    Cache-Treffer 0, obwohl abgerufen wurde). Die echte Methode laeuft
    unveraendert."""

    def __init__(self) -> None:
        self.aufrufe = 0

    def install(self, monkeypatch) -> None:
        from services.segment_weather import SegmentWeatherService

        original = SegmentWeatherService.fetch_segment_weather
        zaehler = self

        def _zaehlend(self, *args, **kwargs):
            zaehler.aufrufe += 1
            return original(self, *args, **kwargs)

        monkeypatch.setattr(SegmentWeatherService, "fetch_segment_weather", _zaehlend)


# ═════════════════════════════ Amtliche Quelle ═══════════════════════════════

class _FesteAmtlicheQuelle:
    """Echte Quelle (kein Mock), zustaendig fuer den Fixtur-Punkt."""

    def __init__(self, alert) -> None:
        self._alert = alert

    @property
    def name(self) -> str:
        return "tdd-sz12-amtlich"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - LAT) < 0.2 and abs(lon - LON) < 0.2

    def fetch(self, lat: float, lon: float):
        return [self._alert]


@contextlib.contextmanager
def _amtliche_warnung():
    import services.official_alerts.base as basis
    from services.official_alerts import OfficialAlert, register_official_alert_source

    sicherung = list(basis._REGISTERED_SOURCES)
    basis._REGISTERED_SOURCES.clear()
    try:
        jetzt = _jetzt()
        register_official_alert_source(_FesteAmtlicheQuelle(OfficialAlert(
            source="tdd-sz12", hazard="thunderstorm", level=3,
            label="Gewitterwarnung (Sz12)", region_label="Testregion",
            valid_from=jetzt - timedelta(hours=1),
            valid_to=jetzt + timedelta(hours=6),
        )))
        yield
    finally:
        basis._REGISTERED_SOURCES.clear()
        basis._REGISTERED_SOURCES.extend(sicherung)


# ══════════════════════════════════ AC-1 ═════════════════════════════════════

def test_trip_ohne_anker_schreibt_no_reference_basis_missing(caplog):
    """AC-1: laufender Trip, nie ein Briefing (kein Anker) / ``check_all_trips``
    / genau ein Eintrag ``no_reference_basis`` mit ``reference_gap="missing"``
    und ``reference_day`` = heute; kein Abweichungs-Alarm.

    ROT heute: ``trip_alert.py`` (leeres ``cached`` -> ``continue``) schreibt
    nichts ins Alarmprotokoll."""
    from services.alert_log import read_undelivered

    uid, trip_id = nutzer("ac1"), "trip-sz12-ac1"
    with _uhr():
        trip = laufender_trip(trip_id, _heute())
        save_trip(trip, user_id=uid)
        tag = ortstag_des_trips(trip)
        with caplog.at_level(logging.DEBUG):
            ergebnis, mails = alarm_lauf(uid)

    assert [z.get("reason") for z in diagnose_zeilen(uid)] == ["missing"], (
        "Fixtur-Schutz: der Lauf muss den fehlenden Anker erreicht haben "
        f"(Diagnosezeile 'missing'). Diagnose: {diagnose_zeilen(uid)}"
    )
    assert not mails and ergebnis.alerts_sent == 0, (
        f"AC-1: ohne Vergleichsbasis darf kein Alarm rausgehen: {mails!r}"
    )
    eintrag = _genau_ein_eintrag(uid, trip_id)
    assert eintrag.get("reference_gap") == "missing", (
        f"AC-1: reference_gap='missing' erwartet, Eintrag: {eintrag!r}"
    )
    assert eintrag.get("reference_day") == tag.isoformat(), (
        f"AC-1: reference_day muss der Tag des Laufs sein ({tag.isoformat()}), "
        f"Eintrag: {eintrag!r}"
    )
    assert "reference_at" not in eintrag, (
        f"AC-1: ohne Anker gibt es kein Ankerdatum — reference_at muss fehlen: {eintrag!r}"
    )
    vorfaelle = read_undelivered(uid, entity_id=trip_id, entity_type="trip")
    assert any(GRUND in v.reasons for v in vorfaelle), (
        f"AC-1: der Eintrag muss ueber die produktive Leseseite sichtbar sein: {vorfaelle!r}"
    )


# ══════════════════════════════════ AC-2 ═════════════════════════════════════

def _fall_nicht_briefing_gestuetzt(uid: str, trip_id: str) -> Trip:
    """Abfrage-Anker (``/glance``) eines laufenden Trips — Produktweg #1699."""
    heute = _heute()
    trip = zweiter_wegpunkt(boeen_trip(trip_id, [heute, heute + timedelta(days=1)]))
    save_trip(trip, user_id=uid)
    antwort = abfrage_glance(uid, trip)
    roh = json.loads((get_snapshots_dir(uid) / f"{trip_id}.json").read_text())
    assert roh.get("briefing_backed") is False, (
        f"Fixtur-Schutz: die Abfrage muss den Anker schreiben. {antwort!r}"
    )
    return trip


def _fall_zu_alt(uid: str, trip_id: str) -> Trip:
    """Anker ohne lesbares ``target_date``, 27 h alt.

    BEFUND (Spec-Abweichung, im Abschlussbericht benannt): ``too_old`` ist auf
    der Trip-Seite NUR ohne ``target_date`` erreichbar (``trip_alert.py``,
    Altersnetz A3) — der Produkt-Schreibweg ``save()`` schreibt das Feld aber
    immer, und ein Zeitsprung ergibt ``wrong_day``. Der Fall ist Altbestand.
    Der Schreibzeitpunkt entsteht deshalb ueber den echten ``save()`` unter
    gestellter Uhr; einzig ``target_date`` wird entfernt (wie AC-4 in
    ``test_alert_anchor_day_guard.py``)."""
    heute = _heute()
    with _uhr(timedelta(hours=-27)):
        pfad = briefing_anker_schreiben(uid, trip_id, heute)
    daten = json.loads(pfad.read_text())
    daten.pop("target_date", None)
    pfad.write_text(json.dumps(daten, indent=2))
    trip = laufender_trip(trip_id, heute)
    save_trip(trip, user_id=uid)
    return trip


def _fall_falscher_tag(uid: str, trip_id: str) -> Trip:
    """Anker eines Abend-Briefings (Zieltag morgen) — der Produktivfall
    08.08.2026 spiegelbildlich; nur der echte ``save()``."""
    heute = _heute()
    briefing_anker_schreiben(uid, trip_id, heute + timedelta(days=1))
    trip = laufender_trip(trip_id, heute)
    save_trip(trip, user_id=uid)
    return trip


@pytest.mark.parametrize("untergrund,aufbau", [
    ("not_briefing_backed", _fall_nicht_briefing_gestuetzt),
    ("too_old", _fall_zu_alt),
    ("wrong_day", _fall_falscher_tag),
], ids=["not_briefing_backed", "too_old", "wrong_day"])
def test_trip_abgelehnter_anker_je_untergrund(untergrund, aufbau):
    """AC-2: vorhandener Anker wird abgelehnt / ``check_all_trips`` / genau
    ein Eintrag mit passendem ``reference_gap`` und dem Ankerdatum in
    ``reference_at`` (D-2/E-1).

    ``reference_at`` laesst die Spec offen („Ankerdatum bzw. Schreibzeitpunkt
    des verworfenen Ankers") — akzeptiert wird deshalb genau einer der beiden
    Werte, die in der Anker-Datei selbst stehen."""
    uid, trip_id = nutzer(f"ac2-{untergrund[:8]}"), f"trip-sz12-ac2-{untergrund}"
    with _uhr():
        trip = aufbau(uid, trip_id)
        roh = json.loads((get_snapshots_dir(uid) / f"{trip_id}.json").read_text())
        tag = ortstag_des_trips(trip)
        ergebnis, mails = alarm_lauf(uid)

    assert untergrund in [z.get("reason") for z in diagnose_zeilen(uid)], (
        f"Fixtur-Schutz: der Anker muss mit Grund '{untergrund}' verworfen "
        f"worden sein. Diagnose: {diagnose_zeilen(uid)}"
    )
    assert not mails and ergebnis.alerts_sent == 0, (
        f"AC-2: ohne gueltige Vergleichsbasis kein Alarm: {mails!r}"
    )
    eintrag = _genau_ein_eintrag(uid, trip_id)
    assert eintrag.get("reference_gap") == untergrund, (
        f"AC-2: reference_gap='{untergrund}' erwartet, Eintrag: {eintrag!r}"
    )
    assert eintrag.get("reference_day") == tag.isoformat(), (
        f"AC-2: reference_day={tag.isoformat()} erwartet, Eintrag: {eintrag!r}"
    )
    assert _referenz_trifft(eintrag.get("reference_at"), roh), (
        f"AC-2: reference_at muss belegen, WELCHE Basis verworfen wurde — "
        f"Ankerdatum oder Schreibzeitpunkt aus der Anker-Datei "
        f"(target_date={roh.get('target_date')!r}, snapshot_at={roh.get('snapshot_at')!r}), "
        f"Eintrag: {eintrag!r}"
    )


# ══════════════════════════════════ AC-3 ═════════════════════════════════════

def test_trip_entdoppelt_je_tag_und_untergrund():
    """AC-3 (+ AC-15-Zaehlung): drei Laeufe im 15-Minuten-Takt -> 1 Eintrag;
    Untergrundwechsel ``missing`` -> ``wrong_day`` am selben Tag -> 2; am
    Folgetag -> ein neuer. Die Diagnosedatei schreibt dabei JEDEN Lauf.

    Der Untergrundwechsel entsteht ueber den echten Schreibweg: ein Anker mit
    Zieltag GESTERN (der auch am Folgetag ``wrong_day`` bleibt — ein
    Abend-Anker fuer morgen wuerde am Folgetag gueltig)."""
    uid, trip_id = nutzer("ac3"), "trip-sz12-ac3"
    with _uhr():
        heute = _heute()
        save_trip(laufender_trip(trip_id, heute, tage_danach=2), user_id=uid)

    for schritt in range(3):
        with _uhr(timedelta(minutes=15 * schritt)):
            alarm_lauf(uid)
    assert len(diagnose_zeilen(uid)) == 3, (
        f"AC-15: die Diagnosedatei muss JEDEN Lauf schreiben: {diagnose_zeilen(uid)}"
    )
    eintraege = no_ref_eintraege(uid, trip_id)
    assert [e.get("reference_gap") for e in eintraege] == ["missing"], (
        "AC-3: drei Laeufe am selben Tag ohne Anker ergeben GENAU EINEN Eintrag "
        f"(nicht einen je Lauf). Gefunden: {eintraege!r}"
    )

    with _uhr(timedelta(minutes=45)):
        briefing_anker_schreiben(uid, trip_id, heute - timedelta(days=1))
    for schritt in (4, 5):
        with _uhr(timedelta(minutes=15 * schritt)):
            alarm_lauf(uid)
    eintraege = no_ref_eintraege(uid, trip_id)
    assert sorted(e.get("reference_gap") for e in eintraege) == ["missing", "wrong_day"], (
        "AC-3: ein Untergrundwechsel am selben Tag ist ein NEUER Befund — genau "
        f"ein weiterer Eintrag 'wrong_day'. Gefunden: {eintraege!r}"
    )

    with _uhr(timedelta(days=1)):
        morgen = _heute()
        alarm_lauf(uid)
    eintraege = no_ref_eintraege(uid, trip_id)
    assert len(eintraege) == 3, (
        f"AC-3: am Folgetag entsteht wieder ein neuer Eintrag. Gefunden: {eintraege!r}"
    )
    assert sorted(e.get("reference_day") for e in eintraege if e.get("reference_gap") == "wrong_day") == [
        heute.isoformat(), morgen.isoformat(),
    ], f"AC-3: Bezugstage der 'wrong_day'-Eintraege: {eintraege!r}"
    assert len(diagnose_zeilen(uid)) == 6, (
        f"AC-15: sechs Laeufe, sechs Diagnosezeilen: {diagnose_zeilen(uid)}"
    )


# ══════════════════════════════════ AC-4 ═════════════════════════════════════

def test_amtlicher_zweitaufruf_schreibt_nie(caplog):
    """AC-4 (Schreibbedingung ``tagesgleicher_anker_noetig``).

    Teil 1 — der amtliche Aufruf ALLEIN (oeffentlicher Einstieg
    ``check_official_alert_triggers``, intern ``tagesgleicher_anker_noetig=
    False``) erreicht den fehlenden Anker (Diagnosezeile ``missing``), darf
    aber NIE einen Protokoll-Eintrag schreiben. Nur dieser Teil faengt die
    Mutation (a) der Spec: im kompletten Lauf verdeckte die Entdopplung einen
    Doppel-Schreiber (zweiter Aufruf, gleicher Schluessel).

    Teil 2 — der komplette Lauf: GENAU ein Eintrag, die Diagnosedatei erhaelt
    weiterhin ihre bisherigen ZWEI Zeilen je Lauf (Abweichung + amtlich).

    BEFUND: ohne jeden Anker hat auch der amtliche Zweig keine Routengeometrie
    — eine amtliche Warnung kann in genau diesem Fall nicht versandt werden.
    „Amtliche Warnung wird unveraendert versendet" prueft deshalb
    ``test_amtliche_warnung_geht_raus_trotz_verworfener_vergleichsbasis``."""
    from services.trip_alert import TripAlertService

    uid, trip_id = nutzer("ac4"), "trip-sz12-ac4"
    with _uhr(), _amtliche_warnung():
        trip = laufender_trip(trip_id, _heute())
        trip.official_alert_triggers_enabled = True
        save_trip(trip, user_id=uid)

        TripAlertService(
            settings=settings_email_only(), user_id=uid,
        ).check_official_alert_triggers(trip, now_utc=_jetzt())
        assert [z.get("reason") for z in diagnose_zeilen(uid)] == ["missing"], (
            "Fixtur-Schutz: der amtliche Aufruf muss den fehlenden Anker "
            f"erreicht haben. Diagnose: {diagnose_zeilen(uid)}"
        )
        assert no_ref_eintraege(uid, trip_id) == [], (
            "AC-4: der amtliche Aufruf (tagesgleicher_anker_noetig=False) darf "
            f"NIE einen '{GRUND}'-Eintrag schreiben: {no_ref_eintraege(uid, trip_id)!r}"
        )

        alarm_lauf(uid)

    assert [z.get("reason") for z in diagnose_zeilen(uid)] == ["missing"] * 3, (
        "AC-4/AC-15: der komplette Lauf schreibt weiterhin ZWEI Diagnosezeilen "
        f"(Abweichung + amtlich). Diagnose: {diagnose_zeilen(uid)}"
    )
    eintrag = _genau_ein_eintrag(uid, trip_id)
    assert eintrag.get("reference_gap") == "missing", eintrag


def test_amtliche_warnung_geht_raus_trotz_verworfener_vergleichsbasis():
    """AC-4 (Versandteil): Anker vom falschen Tag (Abend-Briefing fuer morgen)
    + aktive amtliche Warnung / kompletter Lauf / die amtliche Warnung geht
    unveraendert raus UND es entsteht genau ein ``no_reference_basis``-Eintrag
    (``wrong_day``) — der amtliche Zweig nutzt den Anker nur als Geometrie."""
    uid, trip_id = nutzer("ac4v"), "trip-sz12-ac4-versand"
    with _uhr(), _amtliche_warnung():
        heute = _heute()
        briefing_anker_schreiben(uid, trip_id, heute + timedelta(days=1))
        trip = laufender_trip(trip_id, heute)
        trip.official_alert_triggers_enabled = True
        save_trip(trip, user_id=uid)
        ergebnis, mails = alarm_lauf(uid)

    assert mails and ergebnis.alerts_sent == 1, (
        "AC-4: die amtliche Warnung muss trotz verworfener Vergleichsbasis "
        f"zugestellt werden. Versandt: {ergebnis.alerts_sent}, Mails: {mails!r}"
    )
    eintrag = _genau_ein_eintrag(uid, trip_id)
    assert eintrag.get("reference_gap") == "wrong_day", eintrag


# ══════════════════════════════════ AC-5 ═════════════════════════════════════

@pytest.mark.parametrize("untergrund", ["missing", "wrong_day"])
def test_nicht_gestarteter_trip_bleibt_still(caplog, untergrund):
    """AC-5 (Abgrenzung, heute GRUEN — absichtlich): derselbe Aufbau wie AC-1
    bzw. AC-2, einziger Unterschied: der Trip beginnt erst morgen. Kein Eintrag
    (Muster #1661 C2).

    * ``missing`` — kein Anker; ``_report_missing_anchor`` filtert schon heute.
    * ``wrong_day`` — der gebriefte, noch nicht gestartete Trip: sein
      undatierter Anker traegt den Starttag (Produktweg ``save()``). Bewacht
      die Laufender-Trip-Bedingung an den UEBRIGEN Ablehnungsstellen
      (Spec Implementation Details 2) — ohne diesen Fall waere Mutation (b)
      dort unsichtbar.

    Der Fixtur-Schutz belegt, dass der Lauf die Anker-Pruefung tatsaechlich
    erreicht hat."""
    uid, trip_id = nutzer(f"ac5-{untergrund[:5]}"), f"trip-sz12-ac5-{untergrund}"
    with _uhr():
        heute = _heute()
        trip = boeen_trip(trip_id, [heute + timedelta(days=1), heute + timedelta(days=2)])
        assert trip.start_date > heute, "Fixtur-Schutz: Trip noch nicht gestartet"
        if untergrund == "wrong_day":
            briefing_anker_schreiben(uid, trip_id, trip.start_date)
        save_trip(trip, user_id=uid)
        with caplog.at_level(logging.DEBUG):
            ergebnis, mails = alarm_lauf(uid)

    if untergrund == "missing":
        erreicht = [r.getMessage() for r in caplog.records
                    if r.name == "trip_alert" and trip_id in r.getMessage()
                    and "noch" in r.getMessage() and "begonnen" in r.getMessage()]
    else:
        erreicht = [z for z in diagnose_zeilen(uid) if z.get("reason") == "wrong_day"]
    assert erreicht, (
        "Fixtur-Schutz: der Lauf muss die Anker-Pruefung erreicht haben — sonst "
        "waere 'kein Eintrag' auch aus einem ganz anderen Grund wahr. "
        f"Diagnose: {diagnose_zeilen(uid)}"
    )
    assert not mails and ergebnis.alerts_sent == 0
    assert no_ref_eintraege(uid, trip_id) == [], (
        "AC-5: ein noch nicht gestarteter Trip ohne Anker ist der Normalfall vor "
        f"dem ersten Briefing — KEIN Eintrag: {no_ref_eintraege(uid, trip_id)!r}"
    )


# ══════════════════════════════ AC-6 / AC-16 ═════════════════════════════════

def test_gueltiger_anker_loest_weiter_aus_positivkontrolle(monkeypatch):
    """AC-6 (Positivkontrolle, heute GRUEN — absichtlich): gueltiger,
    tagesgleicher, briefing-gestuetzter Anker (Boeen 200 km/h) / Lauf / der
    Abweichungsalarm geht tatsaechlich raus, es wird frisch abgerufen, und es
    entsteht KEIN ``no_reference_basis``. Ohne diesen Test bewiese AC-16
    („kein Abruf, kein Versand") nichts."""
    uid, trip_id = nutzer("ac6"), "trip-sz12-ac6"
    zaehler = _AbrufZaehler()
    zaehler.install(monkeypatch)
    with _uhr():
        heute = _heute()
        briefing_anker_schreiben(uid, trip_id, heute)
        save_trip(laufender_trip(trip_id, heute), user_id=uid)
        ergebnis, mails = alarm_lauf(uid)

    assert zaehler.aufrufe >= 1, (
        "AC-6: gegen einen gueltigen Anker MUSS frisch abgerufen werden — "
        "sonst misst der Zaehler in AC-16 nichts."
    )
    assert mails and ergebnis.alerts_sent == 1, (
        f"AC-6: der Abweichungsalarm muss weiterhin ausloesen. Versandt: "
        f"{ergebnis.alerts_sent}"
    )
    assert alle_no_ref_eintraege(uid) == [], (
        f"AC-6: gueltige Basis, kein '{GRUND}': {alle_no_ref_eintraege(uid)!r}"
    )
    assert diagnose_zeilen(uid) == [], diagnose_zeilen(uid)


def test_ohne_anker_kein_frischer_abruf_kein_alarm(monkeypatch):
    """AC-16 (heute GRUEN — absichtlich, ADR-0009/0056 bitgleich): derselbe
    Aufbau wie AC-6, nur OHNE Anker. Kein frischer Abruf, kein Alarm —
    gemessen am Abruf-Zaehler und am Versand, nicht am Code."""
    uid, trip_id = nutzer("ac16"), "trip-sz12-ac16"
    zaehler = _AbrufZaehler()
    zaehler.install(monkeypatch)
    with _uhr():
        save_trip(laufender_trip(trip_id, _heute()), user_id=uid)
        ergebnis, mails = alarm_lauf(uid)

    assert "missing" in [z.get("reason") for z in diagnose_zeilen(uid)], (
        f"Fixtur-Schutz: Lauf ohne Anker. Diagnose: {diagnose_zeilen(uid)}"
    )
    assert zaehler.aufrufe == 0, (
        f"AC-16: ohne Anker darf KEIN frischer Wetterabruf gegen absolute "
        f"Schwellen starten — gezaehlt {zaehler.aufrufe}."
    )
    assert not mails and ergebnis.alerts_sent == 0, mails


# ═════════════════════════════ Ortsvergleich ═════════════════════════════════

def _punkt(point_id: str, lat: float, lon: float, precip_sum_mm: float):
    """Echtes ``PointWeatherData``-DTO; ``fetched_at`` = gestellte Uhr."""
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=point_id, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=_jetzt(), provider="tdd-sz12",
    )


class _SkriptQuelle:
    """Echte ``LocationWeatherSource`` ohne Netz, zaehlt ihre Abrufe."""

    def __init__(self, precip_sum_mm: float) -> None:
        self._wert = precip_sum_mm
        self.abrufe = 0

    def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None,
              elevation_m=None, user_id=None, target_date=None):
        self.abrufe += 1
        return _punkt(point_id, lat, lon, self._wert)


def _orte_anlegen(uid: str, ort_ids: list[str]) -> list:
    orte = []
    for i, ort_id in enumerate(ort_ids):
        ort = location(ort_id, f"Ort {i}")
        save_location(ort, user_id=uid)
        orte.append(ort)
    return orte


def _preset(uid: str, preset_id: str, ort_ids: list[str], zone) -> dict:
    quiet_from, quiet_to = quiet_window_elsewhere(zone=zone)
    return radar_preset(preset_id, ort_ids, user_id=uid, cooldown_minutes=120,
                        quiet_from=quiet_from, quiet_to=quiet_to)


def _compare_zone(orte):
    from utils.timezone import first_resolvable_tz

    return first_resolvable_tz(orte, context_label="tdd-sz12")


def _compare_anker(uid: str, preset_id: str, orte) -> None:
    """Der Report-Schreibweg des Δ-Ankers (``CompareWeatherSnapshotService.save``)."""
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    svc = CompareWeatherSnapshotService(user_id=uid)
    for ort in orte:
        svc.save(preset_id, ort.id, _punkt(ort.id, ort.lat, ort.lon, 2.0))


def _compare_lauf(uid: str, quelle: _SkriptQuelle):
    from services.compare_alert import CompareAlertService

    mails: list[tuple[str, str]] = []
    gesendet = CompareAlertService(
        settings=settings_email_only(), user_id=uid, weather_source=quelle,
        mail_sink=lambda subject, body: mails.append((subject, body)),
    ).check_all_compare_presets()
    return gesendet, mails


def test_compare_ohne_anker_schreibt_grund_je_preset():
    """AC-7: aktiver Ortsvergleich mit DREI Orten ohne Anker (Bootstrap) /
    drei Laeufe am selben Tag / genau EIN Eintrag (je Preset, nicht je Ort).

    Positivkontrolle im selben Nutzer: ein Geschwister-Preset mit frischem
    Anker versendet im ersten Lauf — die vorgelagerten Riegel (Sperrzeit,
    Tageslimit, Ruhezeit, Briefing-Vorlauf) lassen den Lauf also durch."""
    uid = nutzer("ac7")
    leer, kontrolle = "cp-sz12-ac7-ohne-anker", "cp-sz12-ac7-kontrolle"
    ort_ids = ["loc-sz12-ac7-a", "loc-sz12-ac7-b", "loc-sz12-ac7-c"]
    clean_uid(uid)
    try:
        with _uhr():
            write_user_tier(uid, "premium")
            orte = _orte_anlegen(uid, ort_ids)
            zone = _compare_zone(orte)
            write_presets(uid, [_preset(uid, leer, ort_ids, zone),
                                _preset(uid, kontrolle, ort_ids[:1], zone)])
            _compare_anker(uid, kontrolle, orte[:1])
            heute = _heute()

        laeufe = []
        for schritt in range(3):
            quelle = _SkriptQuelle(30.0)
            with _uhr(timedelta(minutes=15 * schritt)):
                laeufe.append((_compare_lauf(uid, quelle), quelle.abrufe))

        (gesendet, mails), abrufe = laeufe[0]
        assert gesendet == 1 and len(mails) == 1, (
            "Positivkontrolle: das Geschwister-Preset mit frischem Anker MUSS im "
            f"ersten Lauf versenden. gesendet={gesendet}, Mails={mails!r}"
        )
        assert abrufe >= len(ort_ids), (
            f"Fixtur-Schutz: alle Orte des anker-losen Presets muessen ausgewertet "
            f"worden sein (Abrufe: {abrufe})."
        )
        eintrag = _genau_ein_eintrag(uid, leer, "compare")
        assert eintrag.get("entity_type") == "compare" and eintrag.get("entity_id") == leer, eintrag
        assert eintrag.get("reference_gap") == "missing", eintrag
        assert eintrag.get("reference_day") == heute.isoformat(), (
            f"AC-7: reference_day={heute.isoformat()} erwartet: {eintrag!r}"
        )
        assert "reference_at" not in eintrag, eintrag
        assert no_ref_eintraege(uid, kontrolle, "compare") == [], (
            "AC-7: das Preset mit gueltigem Anker darf keinen Eintrag haben."
        )
    finally:
        clean_uid(uid)


def test_compare_anker_zu_alt(caplog):
    """AC-8: Ortsvergleich (zwei Orte), Anker 27 h alt (ueber die
    Report-Schreibstelle unter gestellter Uhr geschrieben) / zwei Laeufe /
    genau ein Eintrag ``too_old`` mit dem Ankerzeitpunkt in ``reference_at``;
    ``alert_state`` und Cooldown bleiben unberuehrt (Spec AC-7 aus #1584 C)."""
    from services.alert_state import AlertStateService
    from tests.helpers.nowcast_gate_fixtures import read_throttle_state

    uid, preset_id = nutzer("ac8"), "cp-sz12-ac8"
    ort_ids = ["loc-sz12-ac8-a", "loc-sz12-ac8-b"]
    clean_uid(uid)
    try:
        with _uhr():
            write_user_tier(uid, "premium")
            orte = _orte_anlegen(uid, ort_ids)
            write_presets(uid, [_preset(uid, preset_id, ort_ids, _compare_zone(orte))])
            heute = _heute()
        with _uhr(timedelta(hours=-27)):
            anker_zeit = _jetzt()
            _compare_anker(uid, preset_id, orte)

        state_svc = AlertStateService(user_id=uid)
        vorher_state = {o: state_svc.load(f"{preset_id}:{o}") for o in ort_ids}
        vorher_throttle = read_throttle_state(uid)

        for schritt in range(2):
            with _uhr(timedelta(minutes=15 * schritt)), caplog.at_level(logging.DEBUG):
                gesendet, mails = _compare_lauf(uid, _SkriptQuelle(30.0))
            assert gesendet == 0 and not mails, (
                f"AC-8: gegen einen zu alten Anker kein Alarm: {mails!r}"
            )

        zu_alt = [r.getMessage() for r in caplog.records
                  if r.levelno >= logging.WARNING and preset_id in r.getMessage()
                  and "alt" in r.getMessage()]
        assert zu_alt, "Fixtur-Schutz: der Anker muss als zu alt verworfen worden sein."
        eintrag = _genau_ein_eintrag(uid, preset_id, "compare")
        assert eintrag.get("reference_gap") == "too_old", eintrag
        assert eintrag.get("reference_day") == heute.isoformat(), eintrag
        assert isinstance(eintrag.get("reference_at"), str), eintrag
        assert _als_utc(eintrag["reference_at"]) == anker_zeit, (
            f"AC-8: reference_at muss der Ankerzeitpunkt ({anker_zeit.isoformat()}) "
            f"sein: {eintrag!r}"
        )
        assert {o: state_svc.load(f"{preset_id}:{o}") for o in ort_ids} == vorher_state, (
            "AC-8: der alert_state darf nicht angefasst werden."
        )
        assert read_throttle_state(uid) == vorher_throttle, (
            "AC-8: der Cooldown darf nicht fortgeschrieben werden (sonst Dauerstille)."
        )
    finally:
        clean_uid(uid)


# ══════════════════════════════════ AC-9 ═════════════════════════════════════

def test_zwei_nutzer_eintrag_nur_im_eigenen_protokoll():
    """AC-9 (Mandantentrennung, Trip UND Ortsvergleich).

    Beide Nutzer tragen DIESELBE Trip- und Preset-Kennung (nur so kann eine
    nutzeruebergreifende Entdopplung sichtbar werden) plus je eine eigene.
    Nutzer A laeuft zuerst; B bekommt trotzdem seine eigenen Eintraege, und
    keine Kennung des einen erscheint im Protokoll des anderen."""
    a, b = nutzer("ac9-a"), nutzer("ac9-b")
    geteilt_trip, geteilt_preset = "trip-sz12-ac9-geteilt", "cp-sz12-ac9-geteilt"
    eigen = {a: "trip-sz12-ac9-nur-a", b: "trip-sz12-ac9-nur-b"}
    for uid in (a, b):
        clean_uid(uid)
    try:
        with _uhr():
            heute = _heute()
            for uid in (a, b):
                write_user_tier(uid, "premium")
                save_trip(laufender_trip(geteilt_trip, heute), user_id=uid)
                save_trip(laufender_trip(eigen[uid], heute), user_id=uid)
                orte = _orte_anlegen(uid, ["loc-sz12-ac9"])
                write_presets(uid, [_preset(uid, geteilt_preset, ["loc-sz12-ac9"],
                                            _compare_zone(orte))])
            # ZWEI Durchgaenge A -> B: ein Entdopplungs-Leser auf dem falschen
            # Nutzer unterdrueckte B im ersten oder verdoppelte im zweiten.
            for durchgang in range(2):
                with _uhr(timedelta(minutes=15 * durchgang)):
                    for uid in (a, b):
                        alarm_lauf(uid)
                        _compare_lauf(uid, _SkriptQuelle(30.0))

        for uid, anderer in ((a, b), (b, a)):
            erwartet = {("trip", geteilt_trip), ("trip", eigen[uid]),
                        ("compare", geteilt_preset)}
            gefunden = [((e.get("entity_type") or "trip"), e.get("entity_id"))
                        for e in alle_no_ref_eintraege(uid)]
            assert sorted(gefunden) == sorted(erwartet), (
                f"AC-9: Nutzer {uid} muss je Kennung GENAU EINEN eigenen Eintrag "
                f"haben (Entdopplung des anderen darf nicht greifen): {gefunden!r}"
            )
            ids = {e.get("entity_id") for e in read_log(uid)["not_delivered"]}
            assert eigen[anderer] not in ids, (
                f"AC-9: die Kennung {eigen[anderer]!r} des anderen Nutzers steht im "
                f"Protokoll von {uid}: {sorted(ids)!r}"
            )
    finally:
        for uid in (a, b):
            clean_uid(uid)


# ══════════════════════════════════ AC-10 ════════════════════════════════════

_REST_HINWEIS_RE = __import__("re").compile(r"^(?:…|\.\.\.)\s*und\s+\d+\s+weitere$")


def _block_lines(text: str, heading: str) -> list[str]:
    """Inhaltszeilen EINES Hinweis-Blocks (Bauart wie
    ``test_alert_undelivered_hint.py::_block_lines``)."""
    from output.renderers.email.undelivered_hint import HEADING_FAILED, HEADING_WITHHELD

    zeilen = text.splitlines()
    try:
        start = zeilen.index(heading)
    except ValueError:
        return []
    ergebnis: list[str] = []
    for line in zeilen[start + 1:]:
        stripped = line.strip()
        if stripped == "" or stripped in {HEADING_FAILED, HEADING_WITHHELD}:
            break
        if _REST_HINWEIS_RE.match(stripped):
            continue
        ergebnis.append(stripped)
    return ergebnis


class _ReportRecorder:
    """DELEGIERENDER Beobachter auf ``TripReportFormatter.format_email`` —
    die echte Methode laeuft, festgehalten wird nur ihr Ergebnis (Muster aus
    ``test_alert_undelivered_hint.py``)."""

    def __init__(self) -> None:
        self.reports: list = []

    def install(self, monkeypatch) -> None:
        from output.renderers.trip_report import TripReportFormatter

        original = TripReportFormatter.format_email
        recorder = self

        def _recording(self, *args, **kwargs):
            report = original(self, *args, **kwargs)
            recorder.reports.append(report)
            return report

        monkeypatch.setattr(TripReportFormatter, "format_email", _recording)


def _briefing(recorder: _ReportRecorder, uid: str, trip: Trip):
    """ECHTER Briefing-Pfad ohne Transport (#1477): rendert die Mail und
    setzt den Briefing-Zeitstempel, versendet nichts."""
    from app.config import Settings
    from services.trip_report_scheduler import TripReportSchedulerService

    keine_transporte = Settings(
        smtp_host="", smtp_user="", smtp_pass="", mail_to="",
        telegram_bot_token="", telegram_chat_id="",
        telegram_test_bot_token="", telegram_test_chat_id="",
        sms_gateway_url="", seven_api_key="", sms_to="",
    )
    vorher = len(recorder.reports)
    outcome = TripReportSchedulerService(
        settings=keine_transporte, user_id=uid,
    )._send_trip_report_outcome(trip, "morning")
    assert outcome in ("sent", "no_channels"), f"Voraussetzung: Briefing lief, {outcome!r}"
    assert len(recorder.reports) > vorher, "Voraussetzung: Briefing-Mail gebaut"
    return recorder.reports[-1]


def test_briefing_hinweis_zeigt_deutsches_label_im_failed_block(monkeypatch):
    """AC-10: Briefing senden -> Eintrag ``no_reference_basis`` entsteht ->
    zweites Briefing / der Grund steht im Block FEHLGESCHLAGEN mit dem Label
    „Kein Alarm möglich: keine gültige Vergleichsbasis", nicht als roher Code
    und nicht unter ZURÜCKGEHALTEN.

    Der Eintrag wird ueber den echten Schreibweg ``append_suppressed_entry``
    mit der HEUTE gueltigen Signatur geschrieben (nur ``gate_reason``): nach
    dem ersten Briefing liegt ein gueltiger Anker vor, der Lauf faende also
    keine fehlende Basis. Gemessen wird hier die Sichtbarkeit am Renderer.
    Ein unbekannter Code landet schon heute im Block FEHLGESCHLAGEN — die
    Zusicherung ist deshalb das LABEL und das FEHLEN des Roh-Codes."""
    from output.renderers.email.undelivered_hint import HEADING_FAILED, HEADING_WITHHELD
    from services import alert_log
    from services.alert_briefing_anchor import last_briefing_at

    uid, trip_id = nutzer("ac10"), "trip-sz12-ac10"
    label = "Kein Alarm möglich: keine gültige Vergleichsbasis"
    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    with _uhr():
        trip = laufender_trip(trip_id, _heute(), tage_davor=0, tage_danach=0)
        # Feste Ankunftszeiten (#1709, Muster ``test_alert_undelivered_hint._trip``)
        # statt Naismith-Self-Heal; zwei Wegpunkte, sonst keine Segmente.
        for stage in trip.stages:
            stage.waypoints[:] = [
                Waypoint(id=f"{stage.id}-S", name="Start", lat=LAT, lon=LON,
                         elevation_m=1000.0, arrival_calculated="08:00"),
                Waypoint(id=f"{stage.id}-Z", name="Ziel", lat=LAT + 0.1, lon=LON + 0.1,
                         elevation_m=1500.0, arrival_calculated="12:00"),
            ]
        # Briefing ohne scharfen Kanal: der Pfad rendert vollstaendig
        # (Ergebnis ``no_channels``), versendet aber nichts (#1477).
        trip.report_config.send_email = False
        trip.report_config.send_telegram = False
        trip.report_config.send_sms = False
        save_trip(trip, user_id=uid)
        _briefing(recorder, uid, trip)
    assert last_briefing_at(user_id=uid, entity_id=trip_id, entity_type="trip") is not None, (
        "Voraussetzung: das erste Briefing muss den Zeitstempel gesetzt haben."
    )

    with _uhr(timedelta(minutes=5)):
        alert_log.append_suppressed_entry(
            uid, entity_id=trip_id, entity_type="trip",
            reason=alert_log.REASON_FORECAST_CHANGE, gate_reason=GRUND,
            effective_channels={"email"},
        )
    with _uhr(timedelta(minutes=10)):
        text = _briefing(recorder, uid, trip).email_plain

    failed = "\n".join(_block_lines(text, HEADING_FAILED))
    withheld = "\n".join(_block_lines(text, HEADING_WITHHELD))
    assert label in failed, (
        f"AC-10: der Grund muss im Block FEHLGESCHLAGEN als {label!r} erscheinen.\n{text}"
    )
    assert label not in withheld, f"AC-10: nicht unter ZURÜCKGEHALTEN.\n{text}"
    assert GRUND not in text, f"AC-10: der rohe Code {GRUND!r} steht in der Mail.\n{text}"


# ══════════════════════════════════ AC-11 ════════════════════════════════════

def _eintrag_schreiben(uid: str, trip_id: str, gate_reason: str, versatz: timedelta) -> None:
    """Echter Schreibweg unter gestellter Uhr — die Zeitachse entsteht vom
    Produkt, nicht von Hand. Abstaende > ``DEDUP_WINDOW`` (2 min), sonst
    fasst die Leseseite die Vorfaelle zusammen."""
    from services import alert_log

    with _uhr(versatz):
        alert_log.append_suppressed_entry(
            uid, entity_id=trip_id, entity_type="trip",
            reason=alert_log.REASON_FORECAST_CHANGE, gate_reason=gate_reason,
            effective_channels={"email"},
        )


def test_ersatzfenster_ohne_zeitstempel_nur_no_reference_basis():
    """AC-11 (ohne Briefing-Zeitstempel): gemischte Historie (``cooldown`` vor
    3 Tagen, ``delivery_failed`` vor 5 h, ``no_reference_basis`` vor 10 min) /
    ``undelivered_since_last_briefing`` / NUR der ``no_reference_basis``-
    Vorfall; aeltere Gruende bleiben draussen (AC-7 aus #1461).

    ROT heute: ohne Zeitstempel liefert die Funktion ``[]``."""
    from services.alert_briefing_anchor import last_briefing_at, undelivered_since_last_briefing

    uid, trip_id = nutzer("ac11"), "trip-sz12-ac11"
    _eintrag_schreiben(uid, trip_id, "cooldown", timedelta(days=-3))
    _eintrag_schreiben(uid, trip_id, "delivery_failed", timedelta(hours=-5))
    _eintrag_schreiben(uid, trip_id, GRUND, timedelta(minutes=-10))
    _eintrag_schreiben(uid, "trip-sz12-ac11-fremd", GRUND, timedelta(minutes=-20))
    assert last_briefing_at(user_id=uid, entity_id=trip_id, entity_type="trip") is None

    with _uhr():
        vorfaelle = undelivered_since_last_briefing(
            user_id=uid, entity_id=trip_id, entity_type="trip",
        )

    assert [set(v.reasons) for v in vorfaelle] == [{GRUND}], (
        "AC-11: ohne Briefing-Zeitstempel muss die Funktion GENAU den "
        f"'{GRUND}'-Vorfall dieser Entity liefern — weder [] noch die "
        f"Alt-Historie. Erhalten: {vorfaelle!r}"
    )


def test_fenster_mit_zeitstempel_unveraendert():
    """AC-11 (mit Briefing-Zeitstempel, heute GRUEN — absichtlich):
    Aufbau wie oben plus Zeitstempel vor 6 h / das Fenster bleibt bitgleich
    ``read_undelivered(since=last_briefing_at)`` — der aeltere Vorfall bleibt
    draussen, die juengeren erscheinen."""
    from services.alert_briefing_anchor import record_briefing_sent, undelivered_since_last_briefing
    from services.alert_log import read_undelivered

    uid, trip_id = nutzer("ac11b"), "trip-sz12-ac11b"
    _eintrag_schreiben(uid, trip_id, "cooldown", timedelta(days=-3))
    _eintrag_schreiben(uid, trip_id, "delivery_failed", timedelta(hours=-5))
    _eintrag_schreiben(uid, trip_id, GRUND, timedelta(minutes=-10))
    with _uhr():
        seit = _jetzt() - timedelta(hours=6)
        record_briefing_sent(user_id=uid, entity_id=trip_id, entity_type="trip", at=seit)
        vorfaelle = undelivered_since_last_briefing(
            user_id=uid, entity_id=trip_id, entity_type="trip",
        )
        erwartet = read_undelivered(uid, entity_id=trip_id, entity_type="trip", since=seit)

    assert vorfaelle == erwartet, (
        f"AC-11: mit Zeitstempel bleibt das Fenster bitgleich: {vorfaelle!r} != {erwartet!r}"
    )
    assert [set(v.reasons) for v in vorfaelle] == [{GRUND}, {"delivery_failed"}], (
        f"Fixtur-Schutz: zwei Vorfaelle im Fenster, der aeltere draussen: {vorfaelle!r}"
    )


# ══════════════════════════════════ AC-13 ════════════════════════════════════

def test_reference_felder_typpruefung_und_absenz(caplog):
    """AC-13: ``reference_gap``/``reference_day`` sind typgeprueft und
    additiv-defensiv wie die uebrigen E-1-Felder.

    * richtig typisiert -> beide Felder stehen im Eintrag (Positivkontrolle);
    * falsch typisiert (``int``) -> Eintrag entsteht OHNE das Feld, ohne
      Ausnahme, mit ``logger.warning``;
    * ohne die Felder -> Eintrag ohne diese Schluessel.

    ROT heute: ``append_suppressed_entry`` kennt die Parameter nicht
    (``TypeError: unexpected keyword argument``)."""
    from services import alert_log

    uid = nutzer("ac13")
    gemeinsam = dict(entity_type="trip", reason=alert_log.REASON_FORECAST_CHANGE,
                     gate_reason=GRUND, effective_channels={"email"})

    with _uhr():
        alert_log.append_suppressed_entry(
            uid, entity_id="trip-sz12-ac13-ok", reference_gap="missing",
            reference_day="2026-10-01", **gemeinsam,
        )
        with caplog.at_level(logging.WARNING):
            alert_log.append_suppressed_entry(
                uid, entity_id="trip-sz12-ac13-falsch", reference_gap=5,
                reference_day=20261001, **gemeinsam,
            )
        alert_log.append_suppressed_entry(
            uid, entity_id="trip-sz12-ac13-ohne",
            entity_type="trip", reason=alert_log.REASON_FORECAST_CHANGE,
            gate_reason=alert_log.REASON_COOLDOWN, effective_channels={"email"},
        )

    je_id = {e["entity_id"]: e for e in read_log(uid)["not_delivered"]}
    ok = je_id["trip-sz12-ac13-ok"]
    assert ok.get("reference_gap") == "missing" and ok.get("reference_day") == "2026-10-01", ok
    falsch = je_id.get("trip-sz12-ac13-falsch")
    assert falsch is not None, "AC-13: der Eintrag muss trotz falscher Typen entstehen."
    assert "reference_gap" not in falsch and "reference_day" not in falsch, falsch
    warnungen = [r.getMessage() for r in caplog.records
                 if r.levelno == logging.WARNING and "trip-sz12-ac13-falsch" in r.getMessage()]
    assert any("reference_gap" in m for m in warnungen) and any("reference_day" in m for m in warnungen), (
        f"AC-13: die Absenz muss laut protokolliert werden (logger.warning je Feld): {warnungen!r}"
    )
    ohne = je_id["trip-sz12-ac13-ohne"]
    assert "reference_gap" not in ohne and "reference_day" not in ohne, ohne


# ══════════════════════════════════ AC-14 ════════════════════════════════════

def test_protokollfehler_reisst_lauf_nicht_mit(caplog):
    """AC-14 (fail-soft, Muster ``fix_1479``).

    BEFUND (Spec-Abweichung): ``alert_log.json`` liegt je NUTZER
    (``get_data_dir(user_id)/alert_log.json``), nicht je Trip — „das
    ``alert_log.json`` des einen Trips" gibt es nicht. Naechstliegende
    Konstruktion: an der Stelle der Datei liegt ein VERZEICHNIS (echter,
    deterministischer ``OSError``, ohne Rechte-Gebastel, das root ignorierte).
    Trip A (alphabetisch zuerst) hat keinen Anker und scheitert an seinem
    Protokoll-Eintrag; Trip B (gueltiger Anker) muss trotzdem versenden. Der
    Versand liegt in ``check_and_send_alerts`` VOR dem eigenen
    ``append_entry`` — gemessen wird deshalb an ``mails``.

    ROT heute: Trip A versucht gar keinen Eintrag, es gibt also kein
    ``logger.error`` zu Trip A."""
    uid = nutzer("ac14")
    trip_a, trip_b = "trip-sz12-ac14-a-ohne-anker", "trip-sz12-ac14-b-mit-anker"
    with _uhr():
        heute = _heute()
        save_trip(laufender_trip(trip_a, heute), user_id=uid)
        briefing_anker_schreiben(uid, trip_b, heute)
        save_trip(laufender_trip(trip_b, heute), user_id=uid)
        sperre = get_data_dir(uid) / "alert_log.json"
        sperre.mkdir(parents=True, exist_ok=False)
        with caplog.at_level(logging.DEBUG):
            ergebnis, mails = alarm_lauf(uid)

    assert sperre.is_dir(), "Fixtur-Schutz: die Sperre muss ein Verzeichnis bleiben."
    assert ergebnis.checked == 2, f"AC-14: beide Trips muessen geprueft werden: {ergebnis!r}"
    assert mails, (
        "AC-14: Trip B (gueltiger Anker) muss trotz scheiterndem Protokoll von "
        "Trip A seinen Alarm versenden."
    )
    fehler_a = [r.getMessage() for r in caplog.records
                if r.levelno >= logging.ERROR and trip_a in r.getMessage()]
    assert fehler_a, (
        "AC-14: der gescheiterte Protokoll-Eintrag von Trip A muss als "
        "logger.error im Log stehen — fail-soft heisst nicht still. "
        f"ERROR-Zeilen: {[r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]}"
    )


# ══════════════════════════════════ AC-15 ════════════════════════════════════

def test_diagnosedatei_schreibt_weiter_bei_jedem_lauf():
    """AC-15 (Regression, heute GRUEN — absichtlich): drei Laeufe ohne Anker /
    drei Diagnosezeilen mit unveraendertem Format (``ts``, ``entity_id``,
    ``reason``) — die Entdopplung des PROTOKOLLS darf den Go-Health-Streak
    (liest nur ``ts``) nicht ausduennen."""
    uid, trip_id = nutzer("ac15"), "trip-sz12-ac15"
    with _uhr():
        save_trip(laufender_trip(trip_id, _heute()), user_id=uid)
    for schritt in range(3):
        with _uhr(timedelta(minutes=15 * schritt)):
            alarm_lauf(uid)

    zeilen = diagnose_zeilen(uid)
    assert len(zeilen) == 3, f"AC-15: eine Diagnosezeile je Lauf: {zeilen}"
    for zeile in zeilen:
        assert {"ts", "entity_id", "reason"} <= set(zeile), zeile
        assert zeile["entity_id"] == trip_id and zeile["reason"] == "missing", zeile
        assert datetime.fromisoformat(str(zeile["ts"])), zeile
    assert len({z["ts"] for z in zeilen}) == 3, (
        f"AC-15: drei verschiedene Laufzeitpunkte im Streak: {zeilen}"
    )
