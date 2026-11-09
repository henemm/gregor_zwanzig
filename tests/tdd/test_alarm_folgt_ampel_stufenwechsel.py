"""TDD RED -- Abweichungs-Alarme folgen der Profil-Ampel (Issue #2793 S2b).

SPEC: docs/specs/modules/feat_2793_s2_alarm_stufenwechsel.md (v1.1, §1-§3)
ACs: AC-1..AC-7, AC-10, AC-11, AC-13, AC-14, AC-20.

Gemessen an der Wirkstelle: ueber die echten Einstiege
``TripAlertService.check_and_send_alerts`` (Trip) und
``CompareAlertService.check_all_compare_presets`` (Orts-Vergleich) mit
Fixture-Wetter. Beobachtet wird, OB eine Mail rausgeht, was sie sagt und was
das Alarm-Protokoll (``alert_log.json``) vermerkt -- nicht ein Zwischenwert.

Kein ``Mock()``/``patch()``/``MagicMock``; Transport ueber die bestehende
``mail_sink``-/``weather_source``-DI-Naht, Persistenz unter der
pytest-isolierten Datenwurzel (#1133). Jede Kennung ist ein frischer Nutzer.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest

from app.loader import get_data_dir, save_location
from app.models import (
    MetricConfig,
    SegmentWeatherSummary,
    ThunderLevel,
    TripReportConfig,
    UnifiedWeatherDisplayConfig,
)
from app.trip import Stage, Trip, Waypoint
from app.user import SavedLocation

from tests.helpers.alert_log_fixtures import (
    LAT,
    LON,
    clean_compare_user,
    compare_data_root,
    read_log,
    settings_email_only,
    weather,
)
from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip
from tests.helpers.compare_briefings import write_compare_briefings
from tests.helpers.ortstag import ortstag


def _uid(tag: str) -> str:
    return f"tdd-2793-{tag}-{uuid.uuid4().hex[:6]}"


def _ampel(template: str, alarm_ab: dict[str, str]) -> dict:
    return {
        "template": template,
        "metrics": {mid: {"alarm_ab": ab} for mid, ab in alarm_ab.items()},
    }


# ───────────────────────────── Trip-Einstieg ─────────────────────────────────

def _trip(trip_id: str, *, template: str = "allgemein", alarm_ab: dict[str, str],
          metrics: tuple[str, ...], levels: dict[str, str] | None = None) -> Trip:
    stage = Stage(
        id="T1", name="Tag 1", date=ortstag(LAT, LON),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(
        id=trip_id, name="Ampel-Trip", stages=[stage],
        official_warnings=None, corridors=[],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=[MetricConfig(metric_id=cid, enabled=True) for cid in metrics],
            metric_alert_levels=levels,
            ampel=_ampel(template, alarm_ab),
        ),
    )
    morgen, abend = briefing_zeiten_fuer_trip(trip)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, alert_on_changes=True,
        morning_time=morgen, evening_time=abend,
    )
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    return trip


def _trip_lauf(uid: str, trip: Trip, alt: dict, neu: dict) -> list[tuple[str, str]]:
    """Ein Alarm-Lauf; liefert die zugestellten Mails ``(Betreff, Text)``.

    Tarif premium: ohne ihn greift beim zweiten Alarm des Tages das
    Tageslimit -- gemessen wird hier die Ausloesung, nicht der Tarif."""
    from services.trip_alert import TripAlertService

    profil = get_data_dir(uid) / "user.json"
    if not profil.exists():
        profil.parent.mkdir(parents=True, exist_ok=True)
        profil.write_text(json.dumps({"tier": "premium"}))
    mails: list[tuple[str, str]] = []
    TripAlertService(
        settings=settings_email_only(), user_id=uid, throttle_hours=0,
        mail_sink=lambda subject, body, **_kw: mails.append((subject, body)),
    ).check_and_send_alerts(trip, [weather(1, **alt)], fresh_weather=[weather(1, **neu)])
    return mails


def _alarm_eintraege(uid: str) -> list[dict]:
    log = read_log(uid)
    return [e for e in log["entries"] + log["not_delivered"] if (e.get("changes_count") or 0) > 0]


# ──────────────────────────── Vergleichs-Einstieg ───────────────────────────

_PRESET = "cp-2793"


class _Quelle:
    """Deterministische ``LocationWeatherSource`` (DI-Naht, kein Mock)."""

    def __init__(self, **summary) -> None:
        self._summary = summary

    def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None,
              elevation_m=None, user_id=None, target_date=None):
        from services.point_weather import PointWeatherData

        return PointWeatherData(
            id=point_id, name="Vergleichsort", lat=lat, lon=lon, timeseries=None,
            aggregated=SegmentWeatherSummary(**self._summary),
            fetched_at=datetime.now(timezone.utc), provider="tdd-2793",
        )


def _vergleich_lauf(uid: str, *, template: str, alarm_ab: dict[str, str],
                    active: list[str], alt: dict, neu: dict) -> list[tuple[str, str]]:
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    clean_compare_user(uid)
    save_location(
        SavedLocation(id="loc-a", name="Vergleichsort", lat=LAT, lon=LON, elevation_m=1000),
        user_id=uid,
    )
    write_compare_briefings(compare_data_root() / uid, [{
        "id": _PRESET, "name": "Vergleich 2793", "user_id": uid,
        "location_ids": ["loc-a"], "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["dummy@example.com"], "created_at": "2026-08-01T00:00:00Z",
        "alert_cooldown_minutes": 0,
        "display_config": {"active_metrics": active, "ampel": _ampel(template, alarm_ab)},
    }])
    user_dir = get_data_dir(uid)
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "user.json").write_text(json.dumps({"tier": "premium"}))
    CompareWeatherSnapshotService(user_id=uid).save(
        _PRESET, "loc-a", _Quelle(**alt).fetch("loc-a", LAT, LON),
    )
    mails: list[tuple[str, str]] = []
    CompareAlertService(
        settings=settings_email_only(), user_id=uid, weather_source=_Quelle(**neu),
        mail_sink=lambda subject, body, **_kw: mails.append((subject, body)),
    ).check_all_compare_presets()
    return mails


# ═════════════ AC-1 — Verschaerfung auf/ueber „Alarm ab" alarmiert ═══════════

def test_ac1_boeen_gelb_auf_orange_alarmiert_bei_alarm_ab_orange_mit_mittel():
    """AC-1 GIVEN Trip Vorlage „Allgemein" (Boeen gelb 30, orange 45, rot 60),
    Boeen „Alarm ab Orange", Anker 40 (gelb) / WHEN Prognose 55 (orange) /
    THEN geht ein Alarm mit Dringlichkeit „mittel" (MODERATE) hinaus.

    RED heute: Δ 15 < Standard-Schwelle 20 -> kein Alarm."""
    uid = _uid("ac1")
    trip = _trip("trip-ac1", alarm_ab={"gust": "orange"}, metrics=("gust",))
    mails = _trip_lauf(uid, trip, {"gust_max_kmh": 40.0}, {"gust_max_kmh": 55.0})
    assert mails, "AC-1: gelb -> orange bei Alarm ab Orange muss alarmieren."
    eintraege = _alarm_eintraege(uid)
    assert eintraege and eintraege[-1]["severity"] == "MODERATE", eintraege


def test_ac1_dieselben_werte_bei_alarm_ab_rot_alarmieren_nicht():
    """AC-1 Gegenstueck: mit „Alarm ab Rot" bleibt derselbe Wechsel stumm."""
    uid = _uid("ac1-rot")
    trip = _trip("trip-ac1r", alarm_ab={"gust": "red"}, metrics=("gust",))
    assert _trip_lauf(uid, trip, {"gust_max_kmh": 40.0}, {"gust_max_kmh": 55.0}) == []
    assert _alarm_eintraege(uid) == []


# ═════════════════ AC-2 — grosser Sprung innerhalb der Farbe ═════════════════

def test_ac2_weiter_rot_grosser_sprung_alarmiert_ab_sprung_schwelle():
    """AC-2 GIVEN Boeen „Alarm ab Orange", Anker 65 (rot) / WHEN 95 (Sprung 30
    >= 20) / THEN Alarm „weiter rot, großer Sprung"."""
    uid = _uid("ac2")
    trip = _trip("trip-ac2", alarm_ab={"gust": "orange"}, metrics=("gust",))
    mails = _trip_lauf(uid, trip, {"gust_max_kmh": 65.0}, {"gust_max_kmh": 95.0})
    assert mails, "AC-2: Sprung 30 km/h innerhalb Rot muss alarmieren."
    assert "weiter rot, großer Sprung" in mails[-1][1], mails[-1][1]


def test_ac2_kleiner_sprung_innerhalb_rot_alarmiert_nicht():
    """AC-2 Gegenstueck: 65 -> 80 (Sprung 15 < 20) bleibt stumm.

    RED heute: Δ 15 < 20 bleibt zwar auch heute stumm -- dieser Test ist die
    Gegenprobe zu AC-2 und zugleich gruen vor und nach S2b."""
    uid = _uid("ac2-klein")
    trip = _trip("trip-ac2k", alarm_ab={"gust": "orange"}, metrics=("gust",))
    assert _trip_lauf(uid, trip, {"gust_max_kmh": 65.0}, {"gust_max_kmh": 80.0}) == []


# ═════════════════════ AC-3 — Entwarnung unter „Alarm ab" ════════════════════

def test_ac3_entwarnung_orange_auf_gelb_mit_text_und_mittel():
    """AC-3 GIVEN Boeen „Alarm ab Orange", Anker 50 (orange) / WHEN 35 (gelb) /
    THEN Entwarnung „von orange auf gelb zurückgegangen", Dringlichkeit mittel.

    RED heute: Δ 15 < 20 -> keine Meldung."""
    uid = _uid("ac3")
    trip = _trip("trip-ac3", alarm_ab={"gust": "orange"}, metrics=("gust",))
    mails = _trip_lauf(uid, trip, {"gust_max_kmh": 50.0}, {"gust_max_kmh": 35.0})
    assert mails, "AC-3: orange -> gelb muss eine Entwarnung senden."
    assert "von orange auf gelb zurückgegangen" in mails[-1][1], mails[-1][1]
    assert _alarm_eintraege(uid)[-1]["severity"] == "MODERATE"


# ═════════════════ AC-4 — Rueckgang im Alarmbereich bleibt stumm ═════════════

@pytest.mark.parametrize("alt,neu", [(70.0, 50.0), (95.0, 65.0)])
def test_ac4_rueckgang_innerhalb_des_alarmbereichs_bleibt_stumm(alt, neu):
    """AC-4 (D2) GIVEN Boeen „Alarm ab Orange" / WHEN 70 -> 50 (rot -> orange)
    bzw. 95 -> 65 (beides rot) / THEN weder Alarm noch Entwarnung.

    RED heute: Δ 20 bzw. 30 >= 20 -> heute ein Alarm."""
    uid = _uid("ac4")
    trip = _trip("trip-ac4", alarm_ab={"gust": "orange"}, metrics=("gust",))
    assert _trip_lauf(uid, trip, {"gust_max_kmh": alt}, {"gust_max_kmh": neu}) == []
    assert _alarm_eintraege(uid) == []


# ═════════════════ AC-5 — Anstieg unterhalb „Alarm ab" bleibt stumm ══════════

@pytest.mark.parametrize("alt,neu", [(20.0, 40.0), (40.0, 40.0)])
def test_ac5_anstieg_unterhalb_alarm_ab_oder_unveraendert_bleibt_stumm(alt, neu):
    """AC-5 GIVEN Boeen „Alarm ab Orange" / WHEN 20 -> 40 (gruen -> gelb) oder
    unveraendert / THEN kein Alarm.

    RED heute: 20 -> 40 ist Δ 20 >= 20 -> heute ein Alarm."""
    uid = _uid("ac5")
    trip = _trip("trip-ac5", alarm_ab={"gust": "orange"}, metrics=("gust",))
    assert _trip_lauf(uid, trip, {"gust_max_kmh": alt}, {"gust_max_kmh": neu}) == []


# ═══════════════════ AC-6 — Vorboten alarmieren nie (ADR-0010) ═══════════════

_VORBOTEN_ALT = {"wind_chill_min_c": 5.0, "pop_max_pct": 10}
_VORBOTEN_NEU = {"wind_chill_min_c": -20.0, "pop_max_pct": 95}


def test_ac6_vorboten_mit_alarm_ab_orange_alarmieren_im_trip_nie():
    uid = _uid("ac6-trip")
    trip = _trip(
        "trip-ac6", alarm_ab={"wind_chill": "orange", "rain_probability": "orange"},
        metrics=("wind_chill", "rain_probability"),
    )
    assert _trip_lauf(uid, trip, _VORBOTEN_ALT, _VORBOTEN_NEU) == []


def test_ac6_vorboten_mit_alarm_ab_orange_alarmieren_im_vergleich_nie():
    uid = _uid("ac6-cmp")
    try:
        mails = _vergleich_lauf(
            uid, template="allgemein",
            alarm_ab={"wind_chill": "orange", "rain_probability": "orange"},
            active=["wind_chill_min_c", "pop_max_pct"],
            alt=_VORBOTEN_ALT, neu=_VORBOTEN_NEU,
        )
        assert mails == []
    finally:
        clean_compare_user(uid)


# ═════════════════════ AC-7 — Gewitter nach Vorlage und Stufe ════════════════

@pytest.mark.parametrize("template,alarm_ab,neu,erwartet", [
    ("allgemein", "orange", ThunderLevel.MED, True),     # mittel = orange
    ("allgemein", "red", ThunderLevel.MED, False),
    ("wassersport", "red", ThunderLevel.MED, True),      # mittel = rot
    ("allgemein", "orange", ThunderLevel.LOW, False),    # leicht = gelb, nie
])
def test_ac7_gewitter_alarmiert_nach_farbe_der_vorlage(template, alarm_ab, neu, erwartet):
    """AC-7 GIVEN Gewitter „Alarm ab {alarm_ab}" in Vorlage {template} / WHEN
    die Stufe von „keins" auf {neu} steigt / THEN Alarm genau dann, wenn die
    Farbe der Stufe „Alarm ab" erreicht.

    RED heute: Vorlage und „Alarm ab" gehen nicht ein (standard: erst HOCH)."""
    uid = _uid("ac7")
    trip = _trip("trip-ac7", template=template, alarm_ab={"thunder": alarm_ab},
                 metrics=("thunder",))
    mails = _trip_lauf(
        uid, trip, {"thunder_level_max": ThunderLevel.NONE}, {"thunder_level_max": neu},
    )
    assert bool(mails) is erwartet, (template, alarm_ab, neu, mails)


# ═════════ AC-10 — zwei Abos, zwei Vorlagen, dieselben Werte (Trip/Vergleich) ═

_TEMP_ALT, _TEMP_NEU = {"temp_max_c": 2.0}, {"temp_max_c": 10.0}


@pytest.mark.parametrize("reihenfolge", [("skitouren", "allgemein"), ("allgemein", "skitouren")])
def test_ac10_trip_nur_das_skitouren_abo_alarmiert(reihenfolge):
    """AC-10 GIVEN zwei Trips (zwei Nutzer) mit identischem Wetter, Vorlage
    Skitouren (oben gelb 3, orange 8) bzw. Allgemein (oben gelb 28), beide
    Temperatur „Alarm ab Orange" / WHEN Tageshoechst 2 -> 10 / THEN alarmiert
    nur das Skitouren-Abo -- in beiden Reihenfolgen.

    RED heute: beide alarmieren (Δ 8 > 6)."""
    ergebnis = {}
    for template in reihenfolge:
        uid = _uid(f"ac10-{template}")
        trip = _trip(f"trip-{template}", template=template,
                     alarm_ab={"temperature": "orange"}, metrics=("temperature",))
        ergebnis[template] = bool(_trip_lauf(uid, trip, _TEMP_ALT, _TEMP_NEU))
    assert ergebnis == {"skitouren": True, "allgemein": False}, ergebnis


@pytest.mark.parametrize("reihenfolge", [("skitouren", "allgemein"), ("allgemein", "skitouren")])
def test_ac10_vergleich_nur_das_skitouren_abo_alarmiert(reihenfolge):
    """AC-10 fuer den Orts-Vergleich: derselbe geteilte Kern (ADR-0021)."""
    ergebnis = {}
    for template in reihenfolge:
        uid = _uid(f"ac10c-{template}")
        try:
            ergebnis[template] = bool(_vergleich_lauf(
                uid, template=template, alarm_ab={"temperature": "orange"},
                active=["temp_max_c"], alt=_TEMP_ALT, neu=_TEMP_NEU,
            ))
        finally:
            clean_compare_user(uid)
    assert ergebnis == {"skitouren": True, "allgemein": False}, ergebnis


# ═══════════════════ AC-11 — Kaelteseite nennt das Tagestief ═════════════════

def test_ac11_tagestief_gruen_auf_orange_nennt_tagestief_und_farbpaar():
    """AC-11 GIVEN Temperatur „Alarm ab Orange", Vorlage Allgemein (unten gelb
    < 0, orange < -5) / WHEN Tagestief 1 -> -7 / THEN Alarm, dessen Text das
    Tagestief nennt und „von grün auf orange" sagt."""
    uid = _uid("ac11")
    trip = _trip("trip-ac11", alarm_ab={"temperature": "orange"}, metrics=("temperature",))
    mails = _trip_lauf(uid, trip, {"temp_min_c": 1.0}, {"temp_min_c": -7.0})
    assert mails, "AC-11: gruen -> orange auf der Kaelteseite muss alarmieren."
    text = mails[-1][1]
    assert "Tagestief" in text and "von grün auf orange" in text, text


# ═══════════════════════ AC-13 — CAPE allein alarmiert nie ═══════════════════

def test_ac13_cape_sprung_ohne_gewitterstufe_alarmiert_nicht():
    """AC-13 (ADR-0106 P1) GIVEN CAPE 300 -> 1500 J/kg, Gewitterstufe gleich /
    WHEN der Lauf prueft / THEN kein Alarm.

    Invariante, heute schon gruen: CAPE ist seit #1585 nicht mehr waehlbar
    und damit nie aktiv; S2b darf das nicht ueber die Ampel zurueckholen."""
    uid = _uid("ac13")
    trip = _trip("trip-ac13", alarm_ab={"thunder": "orange"}, metrics=("thunder", "cape"),
                 levels={"cape": "sensibel"})
    alt = {"cape_max_jkg": 300.0, "cape_model_id": "icon_d2",
           "thunder_level_max": ThunderLevel.NONE}
    neu = {"cape_max_jkg": 1500.0, "cape_model_id": "icon_d2",
           "thunder_level_max": ThunderLevel.NONE}
    assert _trip_lauf(uid, trip, alt, neu) == []


# ═══════════════ AC-14 — alle „Nie" und keine D4-Metrik: kein Alarm ═══════════

def test_ac14_alle_alarm_ab_nie_ohne_d4_metrik_alarmiert_nicht():
    """AC-14 GIVEN alle aktiven alarmfaehigen Metriken „Nie" / WHEN Werte von
    gruen auf rot springen / THEN kein Alarm.

    RED heute: die Δ-Logik ignoriert „Alarm ab" -> Alarm."""
    uid = _uid("ac14")
    trip = _trip(
        "trip-ac14",
        alarm_ab={"gust": "never", "precipitation": "never", "temperature": "never"},
        metrics=("gust", "precipitation", "temperature"),
    )
    alt = {"gust_max_kmh": 10.0, "precip_sum_mm": 0.0, "temp_max_c": 20.0}
    neu = {"gust_max_kmh": 90.0, "precip_sum_mm": 30.0, "temp_max_c": 36.0}
    assert _trip_lauf(uid, trip, alt, neu) == []


# ═════════════════ AC-20 — derselbe Stufenwechsel meldet nie zweimal ═════════

def test_ac20_drei_laeufe_wiederholung_unterdrueckt_neue_stufe_meldet():
    """AC-20 GIVEN ein zugestellter Boeen-Alarm gelb -> orange (40 -> 55) /
    WHEN der naechste Lauf dieselben Werte bzw. 57 liefert / THEN keine
    Wiederholung; mit 78 (rot) ein neuer Alarm „von orange auf rot gestiegen".

    RED heute: 40 -> 55 alarmiert gar nicht (Δ 15 < 20)."""
    uid = _uid("ac20")
    trip = _trip("trip-ac20", alarm_ab={"gust": "orange"}, metrics=("gust",))
    anker = {"gust_max_kmh": 40.0}
    erst = _trip_lauf(uid, trip, anker, {"gust_max_kmh": 55.0})
    assert erst, "AC-20 Voraussetzung: der erste Wechsel gelb -> orange meldet."
    assert _trip_lauf(uid, trip, anker, {"gust_max_kmh": 55.0}) == []
    assert _trip_lauf(uid, trip, anker, {"gust_max_kmh": 57.0}) == []
    dritt = _trip_lauf(uid, trip, anker, {"gust_max_kmh": 78.0})
    assert dritt, "AC-20: orange -> rot ist ein neuer Stufenwechsel."
    assert "von orange auf rot gestiegen" in dritt[-1][1], dritt[-1][1]
