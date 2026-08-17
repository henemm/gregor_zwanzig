"""Amtliche Warnung: reine Fenster-Revision loest keinen redundanten Alarm aus.

SPEC: docs/specs/modules/fix_1685_warnfenster_revision.md (AC-1..AC-12)
KONTEXT: docs/context/fix-1685-warnfenster-revision.md

RED: `official_alert_revision_verdict()` existiert noch nicht -> ImportError
im parametrisierten Test 1-6/AC-1..AC-6 und in Test 8/9. Der echte Einstieg
`TripAlertService.check_official_alert_triggers()` meldet heute jede
Fenster-Revision erneut (Test 1/AC-1, Test 10/AC-10 rot);
`CompareOfficialAlertService._detect()` identisch (Test 7/AC-7). Der
"melden"-Zweig von AC-3/AC-7/AC-11/AC-12 ist bereits unter dem heutigen
Verhalten gruen (Non-Regression, analog test_official_alert_dedup_timespan.py).

Mock-frei: echte OfficialAlert-DTOs, echte Quellen (Protocol-Subtyping),
echte alert_state-Persistenz unter data/users/<frischer-user>/.
"""
from __future__ import annotations

import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models import (
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from app.user import SavedLocation
from output.renderers.alert.official_alerts import dedupe_official_alerts, official_alert_state_key
from services.official_alerts.models import OfficialAlert

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"
LAT, LON = 47.0, 11.0


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _fresh_user(prefix: str) -> str:
    return f"tdd-1685-{prefix}-{uuid.uuid4().hex[:6]}"


def _registered_sources_backup():
    import services.official_alerts.base as oa_base

    return oa_base, list(oa_base._REGISTERED_SOURCES)


def _minimal_trip(trip_id: str) -> Trip:
    stage = Stage(
        id="T1", name="Tag 1", date=date(2026, 7, 8),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(id=trip_id, name="Revision-Trip", stages=[stage], official_warnings=None)
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=True)
    return trip


def _save_cached(user_id: str, trip_id: str) -> None:
    # Segment jetzt-2h..jetzt+48h -- deckt alle Revisions-Fenster dieser Datei ab.
    from services.weather_snapshot import WeatherSnapshotService

    now = datetime.now(timezone.utc)
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500, distance_from_start_km=8.0),
        start_time=now - timedelta(hours=2), end_time=now + timedelta(hours=48),
        duration_hours=4.0, distance_km=8.0, ascent_m=500, descent_m=0,
    )
    data = SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0), data=[],
        ),
        aggregated=SegmentWeatherSummary(precip_sum_mm=2.0),
        fetched_at=now, provider="openmeteo",
    )
    WeatherSnapshotService(user_id=user_id).save_dated(trip_id, date.today(), [data])


def _mk_alert(vf: datetime, vt: datetime, level: int, *, hazard: str = "thunderstorm",
              region: str = "Kartitsch-1685") -> OfficialAlert:
    return OfficialAlert(source="test-1685", hazard=hazard, level=level,
                          label="Gewitter (#1685)", region_label=region, valid_from=vf, valid_to=vt)


class _RevisableOfficialAlertSource:
    """Echte Quelle (kein Mock), austauschbares `.alert` -- Behoerde revidiert Fenster/Level."""

    def __init__(self, lat: float, lon: float, alert: OfficialAlert) -> None:
        self._lat, self._lon, self.alert = lat, lon, alert

    @property
    def name(self) -> str:
        return "test-1685-revision"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        return [self.alert]


def _freeze_compare_now(monkeypatch, frozen: datetime) -> None:
    # Muster test_compare_official_alert.py -- sonst variiert das lokale
    # ADR-0035-Tagesfenster mit der Testzeit.
    import services.compare_official_alert as coa_mod

    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen.astimezone(tz) if tz else frozen.replace(tzinfo=None)

    monkeypatch.setattr(coa_mod, "datetime", _Frozen)


def _run_trip_chain(uid_prefix: str, shifts: list[tuple[float, float, int]]) -> list[list]:
    # Echter check_official_alert_triggers()-Lauf je (start_h, end_h, level);
    # nach jeder nicht-leeren Runde wird -- wie am echten Sende-Erfolgspfad -- fortgeschrieben.
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService

    user_id = _fresh_user(uid_prefix)
    _clean_user(user_id)
    oa_base, backup = _registered_sources_backup()
    oa_base._REGISTERED_SOURCES.clear()
    try:
        trip = _minimal_trip(f"trip-1685-{uid_prefix}")
        _save_cached(user_id, trip.id)
        base_from = datetime.now(timezone.utc) - timedelta(hours=1)
        base_to = base_from + timedelta(hours=8)
        source = _RevisableOfficialAlertSource(LAT, LON, _mk_alert(base_from, base_to, shifts[0][2]))
        register_official_alert_source(source)
        svc = TripAlertService(user_id=user_id)
        rounds = []
        for start_h, end_h, level in shifts:
            source.alert = _mk_alert(base_from + timedelta(hours=start_h), base_to + timedelta(hours=end_h), level)
            result = svc.check_official_alert_triggers(trip)
            rounds.append(result)
            if result:
                svc._record_official_alert_state(trip.id, result)
        return rounds
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


def _run_compare_chain(monkeypatch, uid_prefix: str, shifts: list[tuple[float, float, int]]) -> list[list]:
    # Wie _run_trip_chain, ueber den Ortsvergleichs-Einstieg _detect() (AC-7).
    from app.config import Settings
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    user_id = _fresh_user(uid_prefix)
    _clean_user(user_id)
    oa_base, backup = _registered_sources_backup()
    oa_base._REGISTERED_SOURCES.clear()
    try:
        frozen = datetime(2026, 8, 11, 6, 0, tzinfo=timezone.utc)
        _freeze_compare_now(monkeypatch, frozen)
        base_from = frozen - timedelta(hours=1)
        base_to = base_from + timedelta(hours=8)
        loc = SavedLocation(id="loc-1685", name="Kartitsch-1685", lat=LAT, lon=LON, elevation_m=1000)
        source = _RevisableOfficialAlertSource(LAT, LON, _mk_alert(base_from, base_to, shifts[0][2]))
        register_official_alert_source(source)
        settings = Settings(smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
                             mail_to="dummy@example.com")
        svc = CompareOfficialAlertService(settings=settings, user_id=user_id, mail_sink=lambda *a: None)
        preset_id = "preset-1685"
        rounds = []
        for start_h, end_h, level in shifts:
            source.alert = _mk_alert(base_from + timedelta(hours=start_h), base_to + timedelta(hours=end_h), level)
            new_or_escalated, per_loc = svc._detect(preset_id, [loc])
            rounds.append(new_or_escalated)
            if new_or_escalated:
                svc._record_state(preset_id, per_loc)
        return rounds
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


# ---- Test 1-6 / AC-1..AC-6 -- parametrisierte Melde-Entscheidung ----
# (Verschiebung Beginn h, Verschiebung Ende h, Stufen-Delta, erwartetes Melden)
REVISION_CASES = [
    pytest.param(4, 5, 0, False, id="ac1-spaeter-ueberlappend-still"),
    pytest.param(0, 4, 0, False, id="ac2-nur-verlaengert-still"),
    pytest.param(-2, -2, 0, True, id="ac3-exakt-2h-frueher-meldet"),
    pytest.param(-4, -4, 0, True, id="ac4-4h-frueher-meldet"),
    pytest.param(4, 5, 1, True, id="ac5-stufe-gestiegen-meldet"),
    # Issue #1657 "Zu revidierende Zusicherung": der frueher pauschale Fall
    # `ac6-kein-zeit-ueberlapp-meldet` zerfaellt in zwei Teilfaelle. Die echte
    # Luecke bleibt eine eigenstaendige Warnung (#1657 AC-2), die exakte
    # Beruehrung gilt kuenftig als dieselbe Warnung (#1657 AC-1).
    pytest.param(24, 24, 0, True, id="ac6-echte-luecke-meldet"),
    pytest.param(8, 8, 0, False, id="ac6b-beruehrung-still"),
]


@pytest.mark.parametrize("start_shift_h,end_shift_h,level_delta,expect_report", REVISION_CASES)
def test_revision_verdict_matches_po_regel(start_shift_h, end_shift_h, level_delta, expect_report):
    # Test 1-6/AC-1..AC-6 (RED): official_alert_revision_verdict fehlt noch.
    # Zeitgrenzen aus der PO-Tabelle (Kontext-Doc Abschnitt 6).
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    base_from = datetime.now(timezone.utc) - timedelta(hours=1)
    base_to = base_from + timedelta(hours=8)
    prev_alert = _mk_alert(base_from, base_to, 2)
    prev_key = official_alert_state_key(prev_alert)
    state = {prev_key: {
        "last_reported_value": 2.0, "reported_at": "2026-08-10T05:01:19+00:00",
        "valid_from": base_from.isoformat(), "valid_to": base_to.isoformat(),
    }}
    new_alert = _mk_alert(
        base_from + timedelta(hours=start_shift_h), base_to + timedelta(hours=end_shift_h), 2 + level_delta,
    )

    should_report, stale_key, merged_entry = official_alert_revision_verdict(new_alert, state)

    assert should_report is expect_report, (
        f"shift={start_shift_h}/{end_shift_h} delta={level_delta}: erwartet {expect_report}, erhalten {should_report}"
    )
    if expect_report:
        assert merged_entry is None, f"Melden darf keinen merged_entry liefern: {merged_entry!r}"
    else:
        assert stale_key == prev_key, f"Stille Revision muss den alten Schluessel markieren: {stale_key!r}"
        assert merged_entry["last_reported_value"] == max(2, 2 + level_delta), merged_entry
        assert merged_entry["valid_from"] == new_alert.valid_from.isoformat()
        assert merged_entry["valid_to"] == new_alert.valid_to.isoformat()
        assert merged_entry["reported_at"] == "2026-08-10T05:01:19+00:00", (
            "Fortschreibung darf den urspruenglichen reported_at NICHT veraendern"
        )


# ---- AC-8/AC-9/AC-12 -- Fail-soft (keine Interval-Logik) & Anzeige unveraendert

def test_ac8_ac9_fail_soft_ohne_interval_logik():
    """Test 8/AC-8 (RED, zeitlose Warnung entscheidet nur ueber den exakten
    Schluesseltreffer) + Test 9/AC-9 (RED, ein Alt-Eintrag ohne valid_from/
    valid_to wird bei der Kandidatensuche ignoriert -- kein Absturz)."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    timeless = OfficialAlert(source="test-1685", hazard="wildfire", level=2,
                              label="Waldbrand-Gefahr Stufe 2 (#1685 AC-8)", region_label="Var-1685")
    state = {official_alert_state_key(timeless): {
        "last_reported_value": 2.0, "reported_at": "2026-08-10T05:01:19+00:00",
    }}
    should_report, stale_key, merged_entry = official_alert_revision_verdict(timeless, state)
    assert should_report is False, "Unveraenderte zeitlose Warnung darf nicht erneut melden"
    assert stale_key is None and merged_entry is None, f"stale_key={stale_key!r} merged_entry={merged_entry!r}"

    old_from = datetime.now(timezone.utc) - timedelta(hours=1)
    old_to = old_from + timedelta(hours=8)
    legacy_key = official_alert_state_key(_mk_alert(old_from, old_to, 2))
    legacy_state = {legacy_key: {"last_reported_value": 2.0, "reported_at": "2026-08-09T07:00:00+00:00"}}
    revised = _mk_alert(old_from + timedelta(hours=4), old_to + timedelta(hours=5), 2)
    should_report2, stale_key2, merged_entry2 = official_alert_revision_verdict(revised, legacy_state)
    assert should_report2 is True, f"Alt-Eintrag darf die Interval-Logik nicht ausloesen: {should_report2!r}"
    assert stale_key2 is None and merged_entry2 is None


def test_f001_naiver_alert_gegen_tz_bewussten_bestandseintrag_und_umgekehrt():
    """Adversary F001 (#1685 Fix-Loop, CRITICAL): manche Quellen (vigilance,
    meteoalarm) liefern naive Zeitstempel. Ein Vergleich naiv-vs-aware wirft
    ohne Normalisierung `TypeError` -- und der echte Einstieg
    `TripAlertService.check_official_alert_triggers` faengt das NICHT ab,
    der Trip verliert damit fuer den Lauf ALLE amtlichen Warnungen. Beide
    Richtungen ueber den echten Einstieg, nicht nur an der Hilfsfunktion."""
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService

    # Richtung 1: Bestandseintrag tz-bewusst, neue Warnung liefert naiven Zeitstempel.
    user_naive = _fresh_user("f001-naive")
    _clean_user(user_naive)
    oa_base, backup = _registered_sources_backup()
    oa_base._REGISTERED_SOURCES.clear()
    try:
        trip = _minimal_trip("trip-1685-f001-naive")
        _save_cached(user_naive, trip.id)
        base_from_aware = datetime.now(timezone.utc) - timedelta(hours=1)
        base_to_aware = base_from_aware + timedelta(hours=8)
        source = _RevisableOfficialAlertSource(
            LAT, LON, _mk_alert(base_from_aware, base_to_aware, 2, region="Kartitsch-f001"),
        )
        register_official_alert_source(source)
        svc = TripAlertService(user_id=user_naive)
        first = svc.check_official_alert_triggers(trip)
        assert len(first) == 1, f"Vorbedingung: Erstmeldung muss neu sein: {first!r}"
        svc._record_official_alert_state(trip.id, first)

        # Revision liefert NAIVE (tz-lose) Zeitstempel -- reale Quellenlage.
        naive_from = (base_from_aware + timedelta(hours=4)).replace(tzinfo=None)
        naive_to = (base_to_aware + timedelta(hours=5)).replace(tzinfo=None)
        source.alert = _mk_alert(naive_from, naive_to, 2, region="Kartitsch-f001")
        second = svc.check_official_alert_triggers(trip)  # darf NICHT werfen
        assert second == [], f"Ueberlappende Revision (naiv) muss still bleiben: {second!r}"
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_naive)

    # Richtung 2: Bestandseintrag naiv (Alt-Fassung), neue Warnung tz-bewusst.
    user_aware = _fresh_user("f001-aware")
    _clean_user(user_aware)
    oa_base, backup = _registered_sources_backup()
    oa_base._REGISTERED_SOURCES.clear()
    try:
        trip = _minimal_trip("trip-1685-f001-aware")
        _save_cached(user_aware, trip.id)
        base_from_aware = datetime.now(timezone.utc) - timedelta(hours=1)
        base_to_aware = base_from_aware + timedelta(hours=8)
        naive_from = base_from_aware.replace(tzinfo=None)
        naive_to = base_to_aware.replace(tzinfo=None)
        source = _RevisableOfficialAlertSource(
            LAT, LON, _mk_alert(naive_from, naive_to, 2, region="Kartitsch-f001b"),
        )
        register_official_alert_source(source)
        svc = TripAlertService(user_id=user_aware)
        first = svc.check_official_alert_triggers(trip)
        assert len(first) == 1, f"Vorbedingung: Erstmeldung muss neu sein: {first!r}"
        svc._record_official_alert_state(trip.id, first)

        # Revision liefert TZ-BEWUSSTE Zeitstempel gegen einen naiv gespeicherten Bestand.
        source.alert = _mk_alert(
            base_from_aware + timedelta(hours=4), base_to_aware + timedelta(hours=5), 2,
            region="Kartitsch-f001b",
        )
        second = svc.check_official_alert_triggers(trip)  # darf NICHT werfen
        assert second == [], f"Ueberlappende Revision (aware) muss still bleiben: {second!r}"
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_aware)


def test_f002_tie_break_und_merge_ueberleben_reported_at_null():
    """Adversary F002 (#1685 Fix-Loop, HIGH): `.get("reported_at", "")` griff
    nur bei fehlendem Schluessel, nicht bei explizit gespeichertem `None`.
    Zwei echt ueberlappende, gleichrangige Kandidaten -- einer mit
    `reported_at: null`, der andere mit echtem String -- duerfen beim
    Tie-Break nicht werfen (sonst `None < str`, TypeError). Gleicher Rang UND
    unterschiedlicher `reported_at`-Typ ist die Bedingung, unter der der Bug
    tatsaechlich greift (zwei identische `None` vergleichen sich klaglos)."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    base_from = datetime.now(timezone.utc) - timedelta(hours=2)
    base_to = base_from + timedelta(hours=10)
    cand_a = _mk_alert(base_from, base_from + timedelta(hours=8), 2)
    cand_b = _mk_alert(base_from + timedelta(hours=1), base_from + timedelta(hours=9), 2)
    key_a, key_b = official_alert_state_key(cand_a), official_alert_state_key(cand_b)
    state = {
        key_a: {
            "last_reported_value": 2.0, "reported_at": None,
            "valid_from": cand_a.valid_from.isoformat(), "valid_to": cand_a.valid_to.isoformat(),
        },
        key_b: {
            "last_reported_value": 2.0, "reported_at": "2026-08-10T05:01:19+00:00",
            "valid_from": cand_b.valid_from.isoformat(), "valid_to": cand_b.valid_to.isoformat(),
        },
    }
    new_alert = _mk_alert(base_from + timedelta(hours=2), base_from + timedelta(hours=10), 2)

    should_report, stale_key, merged_entry = official_alert_revision_verdict(new_alert, state)  # darf NICHT werfen

    assert should_report is False, f"Ueberlappung ohne Eskalation muss still bleiben: {should_report!r}"
    assert merged_entry["reported_at"] is not None, (
        f"Melde-Gedaechtnis darf kein None mehr speichern: {merged_entry!r}"
    )
    assert isinstance(merged_entry["reported_at"], str) and merged_entry["reported_at"] != ""

    # Zweiter Teil (Zeile 502): der GEWINNENDE Kandidat selbst traegt
    # `reported_at: null` (eindeutig hoehere Stufe, kein Tie-Break noetig) --
    # deckt die Fortschreibungs-Zeile isoliert ab, unabhaengig vom Tie-Break.
    # Adversary F007 (#1685 Fix-Loop Runde 2, MEDIUM): der Ersatzwert ist seit
    # der Korrektur der leere String, NICHT mehr `datetime.now()` (das
    # verzerrte kuenftige Tie-Breaks, s. test_f007_... unten) -- die
    # Assertion prueft deshalb den EXAKTEN Wert, nicht nur "nicht None".
    winner_key = official_alert_state_key(cand_a)
    winner_state = {winner_key: {
        "last_reported_value": 3.0, "reported_at": None,
        "valid_from": cand_a.valid_from.isoformat(), "valid_to": cand_a.valid_to.isoformat(),
    }}
    lower_level_alert = _mk_alert(base_from + timedelta(hours=2), base_from + timedelta(hours=10), 2)
    _, _, merged_entry2 = official_alert_revision_verdict(lower_level_alert, winner_state)
    assert merged_entry2["reported_at"] == "", (
        f"Fortschreibung darf ein None-reported_at des Gewinner-Kandidaten nur durch den "
        f"leeren String ersetzen (F007), nicht durch ein erfundenes 'jetzt': {merged_entry2!r}"
    )


def test_f007_erfundener_jetzt_wert_verzerrt_kuenftigen_tie_break():
    """Adversary F007 (#1685 Fix-Loop Runde 2, MEDIUM): `official_alerts.py:534`
    schrieb bei fehlendem `reported_at` bisher `datetime.now(...)` statt des
    leeren Strings. `reported_at` ist genau das Tie-Break-Kriterium (Zeile
    519) -- ein erfundenes "jetzt" ist chronologisch IMMER groesser als jeder
    echte, aeltere Zeitstempel und wuerde einen Kandidaten OHNE eigenen
    reported_at in einer SPAETEREN Runde systematisch gegen einen echten,
    datierten Kandidaten gleicher Stufe gewinnen lassen. Zwei Runden: Runde 1
    erzeugt den Ersatzwert ueber die echte Verdict-Funktion (wie er auch
    tatsaechlich persistiert wuerde), Runde 2 stellt ihn gegen einen echten,
    datierten Kandidaten gleicher Stufe -- der echte MUSS gewinnen."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    t0 = datetime.now(timezone.utc)
    region = "Kartitsch-f007"

    # Runde 1: Kandidat OHNE eigenen reported_at (Alt-Zustand) -> stille
    # Revision, die F007-Zeile erzeugt den Ersatzwert.
    cand_none = _mk_alert(t0, t0 + timedelta(hours=8), 2, region=region)
    key_none = official_alert_state_key(cand_none)
    state_r1 = {key_none: {
        "last_reported_value": 2.0, "reported_at": None,
        "valid_from": cand_none.valid_from.isoformat(), "valid_to": cand_none.valid_to.isoformat(),
    }}
    revised_r1 = _mk_alert(t0 + timedelta(hours=4), t0 + timedelta(hours=13), 2, region=region)
    _, _, merged_r1 = official_alert_revision_verdict(revised_r1, state_r1)
    assert merged_r1["reported_at"] == "", f"F007: Ersatzwert muss '' sein, nicht 'jetzt': {merged_r1!r}"

    # Runde 2: der aus Runde 1 fortgeschriebene Eintrag (reported_at exakt wie
    # tatsaechlich geschrieben) tritt gegen einen ECHTEN, datierten,
    # gleichrangigen Kandidaten an.
    key_r1 = official_alert_state_key(revised_r1)
    cand_real = _mk_alert(t0 + timedelta(hours=3), t0 + timedelta(hours=11), 2, region=region)
    key_real = official_alert_state_key(cand_real)
    state_r2 = {
        key_r1: merged_r1,
        key_real: {
            "last_reported_value": 2.0, "reported_at": "2020-01-01T00:00:00+00:00",
            "valid_from": cand_real.valid_from.isoformat(), "valid_to": cand_real.valid_to.isoformat(),
        },
    }
    revised_r2 = _mk_alert(t0 + timedelta(hours=6), t0 + timedelta(hours=9), 2, region=region)
    should_report_r2, stale_key_r2, merged_r2 = official_alert_revision_verdict(revised_r2, state_r2)

    assert should_report_r2 is False
    assert stale_key_r2 == key_real, (
        f"Echter, datierter Kandidat muss den Tie-Break gewinnen, nicht der Runde-1-Ersatzwert "
        f"(sonst haette ein erfundenes 'jetzt' den Vorrang): stale_key={stale_key_r2!r}"
    )
    assert merged_r2["reported_at"] == "2020-01-01T00:00:00+00:00"


def test_f004_sinkende_stufe_im_still_zweig_senkt_last_reported_value_nicht():
    """Adversary F004 (#1685 Fix-Loop, MEDIUM): REVISION_CASES deckte nie ein
    sinkendes Level im Still-Zweig ab -- die Mutation `max(kandidat_level,
    float(alert.level))` -> `float(alert.level)` blieb dadurch ungefangen
    (alle 65 Tests grün). Ueberlappend, nicht vorverlegt, Stufe faellt:
    `last_reported_value` darf NICHT sinken."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    base_from = datetime.now(timezone.utc) - timedelta(hours=1)
    base_to = base_from + timedelta(hours=8)
    prev_alert = _mk_alert(base_from, base_to, 3)  # ORANGE bereits gemeldet
    prev_key = official_alert_state_key(prev_alert)
    state = {prev_key: {
        "last_reported_value": 3.0, "reported_at": "2026-08-10T05:01:19+00:00",
        "valid_from": base_from.isoformat(), "valid_to": base_to.isoformat(),
    }}
    # Stufe faellt auf GELB(2), Fenster ueberlappt (spaeter, nicht vorverlegt).
    new_alert = _mk_alert(base_from + timedelta(hours=4), base_to + timedelta(hours=5), 2)

    should_report, stale_key, merged_entry = official_alert_revision_verdict(new_alert, state)

    assert should_report is False, "Sinkende Stufe bei echter Ueberlappung darf nicht erneut melden"
    assert merged_entry["last_reported_value"] == 3.0, (
        f"last_reported_value darf bei sinkender Stufe NICHT absinken: {merged_entry!r}"
    )


def test_f005_unparsebarer_bestandswert_faellt_auf_exakten_treffer_zurueck():
    """Adversary F005 (#1685 Fix-Loop, MEDIUM): AC-9 deckte nur KOMPLETT
    fehlende valid_from/valid_to ab (Guard vor dem try, Zeile 480) -- nie
    einen VORHANDENEN, aber unparsebaren Wert, der den try/except tatsaechlich
    erreicht. Ohne try/except wirft `datetime.fromisoformat('not-a-date')`
    `ValueError` -> Absturz statt Fallback auf den exakten Schluesseltreffer."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    base_from = datetime.now(timezone.utc) - timedelta(hours=1)
    base_to = base_from + timedelta(hours=8)
    key = official_alert_state_key(_mk_alert(base_from, base_to, 2))
    state = {key: {
        "last_reported_value": 2.0, "reported_at": "2026-08-10T05:01:19+00:00",
        "valid_from": "not-a-date", "valid_to": base_to.isoformat(),
    }}
    revised = _mk_alert(base_from + timedelta(hours=4), base_to + timedelta(hours=5), 2)

    should_report, stale_key, merged_entry = official_alert_revision_verdict(revised, state)  # darf NICHT werfen

    assert should_report is True, (
        f"Unparsebarer Bestandswert muss auf den exakten Schluesseltreffer zurueckfallen "
        f"(neuer Schluessel != alter -> melden), nicht abstuerzen: {should_report!r}"
    )
    assert stale_key is None and merged_entry is None


def test_ac12_anzeige_bleibt_getrennt_trotz_ueberlappung():
    """Test 12/AC-12 (Non-Regression, MUSS GRUEN bleiben): ueberlappende
    Perioden bleiben in `dedupe_official_alerts` zwei Eintraege."""
    base_from = datetime.now(timezone.utc) - timedelta(hours=1)
    base_to = base_from + timedelta(hours=8)
    alert_a = _mk_alert(base_from, base_to, 2)
    alert_b = _mk_alert(base_from + timedelta(hours=4), base_to + timedelta(hours=5), 2)

    result = dedupe_official_alerts([(alert_a, []), (alert_b, [])])

    assert len(result) == 2, f"Anzeige muss beide Perioden getrennt zeigen: {result!r}"


# ---- AC-1/AC-3/AC-10/AC-11 -- echter Einstieg (Trip) ----

def test_ac1_ac3_ac10_ac11_trip_checker_real_entry():
    # Test 1/AC-1 (RED, still) + Test 3/AC-3 (Non-Regression, melden 2h frueher)
    # + Test 10/AC-10 (RED, Kette 14-22->18-03->22-06, nur Glied 1 meldet)
    # + Test 11/AC-11 (Non-Regression, angrenzend meldet neu, #1245 AC-4) --
    # alle vier ueber den echten Einstieg check_official_alert_triggers().
    still = _run_trip_chain("ac1", [(0, 0, 2), (4, 5, 2)])
    assert len(still[0]) == 1, f"Vorbedingung: Erstmeldung muss neu sein: {still[0]!r}"
    assert still[1] == [], f"AC-1: spaeter/ueberlappend darf nicht erneut melden: {still[1]!r}"

    reports = _run_trip_chain("ac3", [(0, 0, 2), (-2, -2, 2)])
    assert len(reports[0]) == 1
    assert len(reports[1]) == 1, f"AC-3: 2h frueherer Beginn muss erneut gemeldet werden: {reports[1]!r}"

    chain = _run_trip_chain("ac10", [(0, 0, 2), (4, 5, 2), (8, 8, 2)])
    assert len(chain[0]) == 1, f"Erstmeldung muss neu sein: {chain[0]!r}"
    assert chain[1] == [], f"Zweites Glied muss still bleiben: {chain[1]!r}"
    assert chain[2] == [], f"Drittes Glied muss (Fortschreibung) still bleiben: {chain[2]!r}"

    # Issue #1657 AC-1 REVIDIERT diese Zusicherung am echten Einstieg: das
    # zweite Fenster beginnt exakt dort, wo das erste endet (`base_to` ==
    # `base_from + 8h`). #1685 AC-11 verlangte hier eine erneute Meldung,
    # #1657 AC-1 verlangt Stille ("Beruehrung zaehlt als Ueberlappung").
    # Beide Zusicherungen koennen nicht gleichzeitig gelten -- die freigegebene
    # Spec fix_1657_warnfenster_identitaet.md gewinnt.
    adjacent = _run_trip_chain("ac11", [(0, 0, 2), (8, 8, 2)])
    assert len(adjacent[0]) == 1
    assert adjacent[1] == [], (
        f"#1657 AC-1: exakt angrenzendes Fenster darf am echten Einstieg NICHT "
        f"erneut gemeldet werden: {adjacent[1]!r}"
    )


def test_ac13_mandantentrennung_fortschreibung_beruehrt_nur_den_eigenen_nutzer():
    # Test 13 (Mandantentrennung, CLAUDE.md-Pflicht): Nutzer B's Melde-Gedaechtnis
    # bleibt unberuehrt von Nutzer A's stiller Fortschreibung.
    from services.alert_state import AlertStateService
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService

    user_a, user_b = _fresh_user("t13a"), _fresh_user("t13b")
    _clean_user(user_a)
    _clean_user(user_b)
    oa_base, backup = _registered_sources_backup()
    oa_base._REGISTERED_SOURCES.clear()
    try:
        trip_a, trip_b = _minimal_trip("trip-1685-t13a"), _minimal_trip("trip-1685-t13b")
        _save_cached(user_a, trip_a.id)
        _save_cached(user_b, trip_b.id)
        base_from = datetime.now(timezone.utc) - timedelta(hours=1)
        base_to = base_from + timedelta(hours=8)
        source = _RevisableOfficialAlertSource(LAT, LON, _mk_alert(base_from, base_to, 2))
        register_official_alert_source(source)

        svc_a, svc_b = TripAlertService(user_id=user_a), TripAlertService(user_id=user_b)
        svc_a._record_official_alert_state(trip_a.id, svc_a.check_official_alert_triggers(trip_a))
        svc_b._record_official_alert_state(trip_b.id, svc_b.check_official_alert_triggers(trip_b))
        state_b_before = AlertStateService(user_id=user_b).load(trip_b.id)

        source.alert = _mk_alert(base_from + timedelta(hours=4), base_to + timedelta(hours=5), 2)
        second_a = svc_a.check_official_alert_triggers(trip_a)
        assert second_a == [], f"Vorbedingung AC-1: Nutzer A muss still bleiben: {second_a!r}"

        state_b_after = AlertStateService(user_id=user_b).load(trip_b.id)
        assert state_b_after == state_b_before, (
            f"Fortschreibung von Nutzer A darf Nutzer B nicht beruehren:\n"
            f"vorher={state_b_before!r}\nnachher={state_b_after!r}"
        )
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_a)
        _clean_user(user_b)


# ---- AC-7/Test 14 -- echter Einstieg (Ortsvergleich) ----

def test_ac7_compare_detect_real_entry(monkeypatch):
    # Test 7/AC-7 (RED still-Fall + Non-Regression melden-Fall): echter Einstieg
    # CompareOfficialAlertService._detect verhaelt sich wie der Trip-Pfad.
    still = _run_compare_chain(monkeypatch, "ac7a", [(0, 0, 2), (4, 5, 2)])
    assert len(still[0]) == 1, f"Vorbedingung: Erstmeldung muss neu sein: {still[0]!r}"
    assert still[1] == [], f"AC-7 (still): Compare-Pfad muss wie Trip-Pfad still bleiben: {still[1]!r}"

    reports = _run_compare_chain(monkeypatch, "ac7b", [(0, 0, 2), (-2, -2, 2)])
    assert len(reports[0]) == 1
    assert len(reports[1]) == 1, f"AC-7 (melden): erwartet erneute Meldung: {reports[1]!r}"


def test_f006_compare_detect_self_persistence_of_silent_revision(monkeypatch):
    """Adversary F006 (#1685 Fix-Loop Runde 2, MEDIUM): der Compare-Lesepfad
    (`CompareOfficialAlertService._detect`, Zeile 245-246) schreibt die
    stille Fensterrevision sofort selbst fort -- analog zum Trip-Zwilling
    (`trip_alert.py:1399-1400`, bewacht durch Test 10/AC-10 oben). Entfernt
    man die `save()`-Zeile im Compare-Pfad, blieben ohne diesen Test alle 69
    Tests gruen (Testluecke): ein drittes Kettenglied vergliche sonst gegen
    das veraltete, ERSTE Fenster und meldete faelschlich erneut. Kette wie
    Test 10, ueber den Compare-Einstieg `_detect()`."""
    chain = _run_compare_chain(monkeypatch, "f006", [(0, 0, 2), (4, 5, 2), (8, 8, 2)])
    assert len(chain[0]) == 1, f"Erstmeldung muss neu sein: {chain[0]!r}"
    assert chain[1] == [], f"Zweites Glied muss still bleiben: {chain[1]!r}"
    assert chain[2] == [], f"Drittes Glied muss (Fortschreibung) still bleiben: {chain[2]!r}"


def test_ac14_compare_orts_isolation_keine_fortschreibung_ueber_die_location_id_hinweg(monkeypatch):
    # Test 14 (Compare-Orts-Isolation, F005/F006): Ort A traegt Warnung X bereits
    # im Melde-Gedaechtnis, Ort B sieht dieselbe Identitaet mit unveraendertem
    # Fenster zum ersten Mal -- kein Cross-Talk ueber die location-id-Trennung.
    from app.config import Settings
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    user_id = _fresh_user("t14")
    _clean_user(user_id)
    oa_base, backup = _registered_sources_backup()
    oa_base._REGISTERED_SOURCES.clear()
    try:
        frozen = datetime(2026, 8, 11, 6, 0, tzinfo=timezone.utc)
        _freeze_compare_now(monkeypatch, frozen)
        base_from = frozen - timedelta(hours=1)
        base_to = base_from + timedelta(hours=8)
        loc_a = SavedLocation(id="loc-a-1685", name="Ort A", lat=LAT, lon=LON, elevation_m=1000)
        loc_b = SavedLocation(id="loc-b-1685", name="Ort B", lat=LAT + 2.0, lon=LON + 2.0, elevation_m=1000)
        register_official_alert_source(_RevisableOfficialAlertSource(LAT, LON, _mk_alert(base_from, base_to, 2)))
        register_official_alert_source(
            _RevisableOfficialAlertSource(LAT + 2.0, LON + 2.0, _mk_alert(base_from, base_to, 2))
        )
        settings = Settings(smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
                             mail_to="dummy@example.com")
        svc = CompareOfficialAlertService(settings=settings, user_id=user_id, mail_sink=lambda *a: None)
        preset_id = "preset-1685-iso"

        first, per_loc_first = svc._detect(preset_id, [loc_a])
        assert len(first) == 1, f"Vorbedingung: Ort A meldet neu: {first!r}"
        svc._record_state(preset_id, per_loc_first)

        _, per_loc_second = svc._detect(preset_id, [loc_a, loc_b])
        assert "loc-b-1685" in per_loc_second, f"Ort B muss trotz identischem Fenster neu gelten: {per_loc_second!r}"
        assert "loc-a-1685" not in per_loc_second, f"Ort A darf nicht erneut als neu gelten: {per_loc_second!r}"
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


# =====================================================================
# Issue #1657 -- Beruehrende und umschliessende Warnfenster sind dieselbe
# amtliche Warnung. SPEC: docs/specs/modules/fix_1657_warnfenster_identitaet.md
# KONTEXT: docs/context/fix-1657-warnung-identitaet.md
#
# Zeit wird INJIZIERT, nie gemessen: jeder Test, der den 6h-Frische-Guard
# beruehrt, reicht `now` explizit herein und setzt `reported_at` als festen
# Wert relativ dazu (Spec-Abschnitt "Test-Schicht"). Der Guard ist die
# einzige Sicherung dagegen, dass eine echte neue Warnung verschluckt wird --
# ein an der Grenze sporadisch roter Test wuerde als "flaky" abgetan und die
# Sicherung fiele still aus.
# =====================================================================

R1657 = "Kartitsch-1657"


def _entry_1657(alert: OfficialAlert, reported_at: datetime) -> dict:
    """Melde-Gedaechtnis-Eintrag wie ihn `official_alert_state_entry` schreibt
    -- hier mit explizit gesetztem `reported_at`, damit der 6h-Guard exakt
    und nicht gegen die Laufzeituhr geprueft wird."""
    return {
        "last_reported_value": float(alert.level),
        "reported_at": reported_at.isoformat(),
        "valid_from": alert.valid_from.isoformat(),
        "valid_to": alert.valid_to.isoformat(),
    }


def _verdict_round(state: dict, alert: OfficialAlert, reported_at: datetime, now: datetime) -> bool:
    """Ein Prueflauf inklusive der Fortschreibung, die die BEIDEN echten
    Aufrufstellen (`trip_alert.py:1499-1508`, `compare_official_alert.py:
    268-279`) identisch ausfuehren: melden -> neuer Eintrag; stille Revision
    -> `stale_key` raus, `merged_entry` unter dem neuen Schluessel rein."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    should_report, stale_key, merged_entry = official_alert_revision_verdict(alert, state, now=now)
    if should_report:
        state[official_alert_state_key(alert)] = _entry_1657(alert, reported_at)
    elif merged_entry is not None:
        del state[stale_key]
        state[official_alert_state_key(alert)] = merged_entry
    return should_report


def _utc(day: int, hour: int, minute: int = 0, second: int = 0, *, month: int = 8) -> datetime:
    return datetime(2026, month, day, hour, minute, second, tzinfo=timezone.utc)


def _containment_state(now: datetime, kandidat_alter: timedelta) -> tuple[dict, datetime, datetime]:
    """Zwei frische Schmaleintraege derselben Identitaet+Gefahr (`08:00-09:00Z`
    und `09:00-10:00Z`). Der spaeter gemeldete gewinnt den Tie-Break; sein
    Beginn liegt 4h nach dem des breiten Fensters `05:00-13:00Z`, damit die
    #1685-Vorverlegungs-Ausnahme (>=2h) ohne die #1657-Containment-Regel
    zwingend greifen wuerde."""
    schmal_a = _mk_alert(_utc(16, 8), _utc(16, 9), 2, region=R1657)
    schmal_b = _mk_alert(_utc(16, 9), _utc(16, 10), 2, region=R1657)
    state = {
        official_alert_state_key(schmal_a): _entry_1657(schmal_a, now - kandidat_alter - timedelta(minutes=30)),
        official_alert_state_key(schmal_b): _entry_1657(schmal_b, now - kandidat_alter),
    }
    return state, _utc(16, 5), _utc(16, 13)


def test_beruehrendes_folgefenster_meldet_nicht_erneut():
    """Test 1/AC-1 (RED): `14:00-15:00Z` beginnt exakt dort, wo `13:00-14:00Z`
    endet -- dieselbe durchgehende Gefahr in stundenfeiner Ausgabe. Heute
    faellt der Fall durch `alert_vf < cand_vt` (strikt) aus der
    Kandidatensuche und wird als voellig neue Warnung gemeldet."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    bestand = _mk_alert(_utc(16, 13), _utc(16, 14), 2, region=R1657)
    bestand_key = official_alert_state_key(bestand)
    state = {bestand_key: _entry_1657(bestand, _utc(16, 13, 15, 14))}
    folge = _mk_alert(_utc(16, 14), _utc(16, 15), 2, region=R1657)

    should_report, stale_key, merged_entry = official_alert_revision_verdict(folge, state)

    assert should_report is False, (
        "AC-1: exakt anschliessendes Fenster ist dieselbe amtliche Warnung und darf "
        f"nicht erneut melden: {should_report!r}"
    )
    assert stale_key == bestand_key, f"Stille Revision muss den alten Schluessel markieren: {stale_key!r}"
    assert merged_entry["valid_from"] == folge.valid_from.isoformat()
    assert merged_entry["valid_to"] == folge.valid_to.isoformat()
    assert merged_entry["reported_at"] == _utc(16, 13, 15, 14).isoformat(), (
        f"Fortschreibung darf den urspruenglichen reported_at nicht veraendern: {merged_entry!r}"
    )


def test_eine_sekunde_luecke_bleibt_eine_eigenstaendige_warnung():
    """Test 2/AC-2 (Non-Regression, gruen): die ausdrueckliche Grenze der
    Revision. Eine Luecke von einer einzigen Sekunde macht die Warnung wieder
    zu einer eigenstaendigen Warnung -- sonst waere `<=` ein Freibrief."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    bestand = _mk_alert(_utc(16, 13), _utc(16, 14), 2, region=R1657)
    state = {official_alert_state_key(bestand): _entry_1657(bestand, _utc(16, 13, 15, 14))}
    nach_luecke = _mk_alert(_utc(16, 14, 0, 1), _utc(16, 15), 2, region=R1657)

    should_report, stale_key, merged_entry = official_alert_revision_verdict(nach_luecke, state)

    assert should_report is True, (
        f"AC-2: eine Sekunde echte Luecke bleibt eine eigenstaendige Warnung: {should_report!r}"
    )
    assert stale_key is None and merged_entry is None


def test_umschliessendes_breitfenster_mit_frischem_kandidaten_bleibt_still():
    """Test 3/AC-3 (RED): das breite Fenster `05:00-13:00Z` umschliesst beide
    Schmaleintraege vollstaendig -- reiner Granularitaetswechsel derselben
    Gefahr. Heute wertet die Funktion den 4h frueheren Beginn als
    "Vorverlegung >=2h" (#1685) und meldet erneut."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    now = _utc(16, 16, 30, 2)
    state, breit_vf, breit_vt = _containment_state(now, timedelta(minutes=10))
    breit = _mk_alert(breit_vf, breit_vt, 2, region=R1657)

    should_report, stale_key, merged_entry = official_alert_revision_verdict(breit, state, now=now)

    assert should_report is False, (
        "AC-3: umschliessendes Breitfenster mit frischem Kandidaten ist eine stille "
        f"Granularitaets-Revision, keine Vorverlegung: {should_report!r}"
    )
    assert merged_entry is not None and stale_key in state, f"stale_key={stale_key!r}"


def test_umschliessendes_breitfenster_mit_veraltetem_kandidaten_meldet():
    """Test 4/AC-4 (RED): der 6h-Zeitnaehe-Guard. `AlertStateService.reset()`
    behaelt `official_alert:`-Eintraege ueber den Briefing-Reset hinweg
    (#1614) -- ohne Guard wuerde ein Wochen alter Eintrag eine voellig neue,
    unabhaengige Warnung derselben Region+Gefahr verschlucken."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    now = _utc(16, 16, 30, 2)
    state, breit_vf, breit_vt = _containment_state(now, timedelta(hours=7))
    breit = _mk_alert(breit_vf, breit_vt, 2, region=R1657)

    should_report, stale_key, merged_entry = official_alert_revision_verdict(breit, state, now=now)

    assert should_report is True, (
        "AC-4: Containment darf einen >6h alten Bestandskandidaten NICHT still "
        f"fortschreiben -- sonst verschluckt ein Alt-Eintrag eine echte neue Warnung: {should_report!r}"
    )
    assert stale_key is None and merged_entry is None


def test_containment_guard_grenze_liegt_bei_sechs_stunden_nicht_darunter():
    """Test 5 (RED): Grenzfall des Guards -- 5h59min ist noch frisch. Die
    Grenze liegt bei ">6h", nicht bei ">=6h" und nicht bei "5h"."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    now = _utc(16, 16, 30, 2)
    state, breit_vf, breit_vt = _containment_state(now, timedelta(hours=5, minutes=59))
    breit = _mk_alert(breit_vf, breit_vt, 2, region=R1657)

    should_report, _stale_key, _merged = official_alert_revision_verdict(breit, state, now=now)

    assert should_report is False, (
        f"Guard-Grenze: 5h59min alter Kandidat ist noch frisch, Containment greift: {should_report!r}"
    )


def test_stufenerhoehung_meldet_trotz_containment():
    """Test 6/AC-5 (Non-Regression, gruen): die Eskalations-Zusicherung aus
    #1685 bleibt unter Containment wirksam.

    Der Vorverlegungs-Abstand ist hier bewusst auf 1h30 gesetzt (Kandidat
    `06:30-07:30Z` gegen Breitfenster `05:00-13:00Z`) -- damit traegt die
    Meldung ALLEIN die gestiegene Stufe. Waere der Abstand >=2h, bliebe der
    Test auch dann gruen, wenn die Eskalations-Bedingung ersatzlos entfiele,
    und wuerde gar nichts bewachen. Kein `now`: der Eskalations-Zweig liegt
    vor dem 6h-Guard und erreicht ihn nie."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    schmal_a = _mk_alert(_utc(16, 5, 30), _utc(16, 6, 30), 2, region=R1657)
    schmal_b = _mk_alert(_utc(16, 6, 30), _utc(16, 7, 30), 2, region=R1657)
    state = {
        official_alert_state_key(schmal_a): _entry_1657(schmal_a, _utc(16, 5, 35)),
        official_alert_state_key(schmal_b): _entry_1657(schmal_b, _utc(16, 6, 35)),
    }
    breit_orange = _mk_alert(_utc(16, 5), _utc(16, 13), 3, region=R1657)

    should_report, stale_key, merged_entry = official_alert_revision_verdict(breit_orange, state)

    assert should_report is True, (
        f"AC-5: Stufenerhoehung ueberlebt Containment und meldet als Alarm: {should_report!r}"
    )
    assert stale_key is None and merged_entry is None


def test_echte_vorverlegung_ohne_containment_meldet_weiterhin():
    """Test 7/AC-6 (Non-Regression, gruen): `12:00-20:00Z` gegen Bestand
    `14:00-22:00Z` -- 2h frueherer Beginn, aber KEIN Containment (das Ende
    liegt frueher). Die #1685-Vorverlegungs-Ausnahme bleibt unangetastet."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    now = _utc(16, 12, 30)
    bestand = _mk_alert(_utc(16, 14), _utc(16, 22), 2, region=R1657)
    state = {official_alert_state_key(bestand): _entry_1657(bestand, now - timedelta(minutes=10))}
    vorverlegt = _mk_alert(_utc(16, 12), _utc(16, 20), 2, region=R1657)

    # Kein `now`: ohne Containment erreicht der Fall den 6h-Guard nie -- der
    # Test muss schon vor der Implementierung gruen sein (Non-Regression).
    should_report, stale_key, merged_entry = official_alert_revision_verdict(vorverlegt, state)

    assert should_report is True, (
        f"AC-6: echte Vorverlegung >=2h ohne Containment meldet wie vor dieser Spec: {should_report!r}"
    )
    assert stale_key is None and merged_entry is None


def test_kirchbach_drei_fenster_melden_genau_einmal():
    """Test 8/AC-7 (RED): die drei realen Kirchbach-Fenster vom 2026-08-16,
    alle Stufe 2.0, in der realen Reihenfolge mit den realen Ausgabezeiten.
    Der PO erhielt drei Meldungen fuer eine durchgehende Gewitterwarnung."""
    state: dict = {}
    fenster = [
        (_utc(16, 13), _utc(16, 14), _utc(16, 13, 15, 14)),
        (_utc(16, 14), _utc(16, 15), _utc(16, 13, 45, 2)),
        (_utc(16, 11), _utc(16, 20), _utc(16, 16, 30, 2)),
    ]
    meldungen = [
        _verdict_round(state, _mk_alert(vf, vt, 2, region=R1657), reported_at, reported_at)
        for vf, vt, reported_at in fenster
    ]

    assert meldungen == [True, False, False], (
        f"AC-7: Kirchbach muss GENAU EINMAL melden (erstes Fenster), danach still "
        f"fortgeschrieben werden: {meldungen!r}"
    )


def test_obertilliach_drei_fenster_melden_genau_zweimal():
    """Test 9/AC-8 (RED): Obertilliach 2026-08-11. Zwischen Fenster 1
    (`15:00-16:00Z`) und Fenster 2 (`17:00-18:00Z`) liegt eine ECHTE
    einstuendige Luecke -- Fenster 2 bleibt deshalb eine eigenstaendige
    Warnung. Erst das dritte, umschliessende Fenster ist eine stille
    Revision. Zwei Meldungen, nicht eine: das Ergebnis ist nachgerechnet,
    nicht auf "genau einmal" geschoent."""
    state: dict = {}
    fenster = [
        (_utc(11, 15), _utc(11, 16), _utc(11, 14, 30, 14)),
        (_utc(11, 17), _utc(11, 18), _utc(11, 15, 45, 22)),
        (_utc(11, 13), _utc(11, 19), _utc(11, 17, 45, 9)),
    ]
    meldungen = [
        _verdict_round(state, _mk_alert(vf, vt, 2, region=R1657), reported_at, reported_at)
        for vf, vt, reported_at in fenster
    ]

    assert meldungen == [True, True, False], (
        f"AC-8: Obertilliach muss GENAU ZWEIMAL melden (echte Luecke zwischen Fenster 1 "
        f"und 2), nur das dritte, umschliessende Fenster bleibt still: {meldungen!r}"
    )


def test_stufenerhoehung_bei_reiner_ueberlappung_meldet_weiterhin():
    """Test 11 (Non-Regression #1685 AC-5, gruen): ueberlappendes, NICHT
    umschliessendes Fenster mit gestiegener Stufe meldet wie bisher."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    now = _utc(16, 12)
    bestand = _mk_alert(_utc(16, 10), _utc(16, 14), 2, region=R1657)
    state = {official_alert_state_key(bestand): _entry_1657(bestand, now - timedelta(minutes=5))}
    eskaliert = _mk_alert(_utc(16, 12), _utc(16, 16), 3, region=R1657)

    should_report, stale_key, merged_entry = official_alert_revision_verdict(eskaliert, state)

    assert should_report is True, f"Stufenerhoehung bei reiner Ueberlappung meldet: {should_report!r}"
    assert stale_key is None and merged_entry is None


def test_zeitlose_warnung_umgeht_beruehrungs_und_containment_pruefung():
    """Test 12/AC-10 (Non-Regression, gruen): fehlen `valid_from`/`valid_to`,
    entscheidet ausschliesslich der exakte Schluesseltreffer -- weder die neue
    Beruehrungs- noch die neue Containment-Pruefung darf dort greifen."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    zeitlos = OfficialAlert(source="test-1657", hazard="wildfire", level=2,
                            label="Waldbrand-Gefahr (#1657 AC-10)", region_label="Var-1657")
    state = {official_alert_state_key(zeitlos): {
        "last_reported_value": 2.0, "reported_at": "2026-08-16T05:01:19+00:00",
    }}

    should_report, stale_key, merged_entry = official_alert_revision_verdict(zeitlos, state)

    assert should_report is False, f"Unveraenderte zeitlose Warnung darf nicht erneut melden: {should_report!r}"
    assert stale_key is None and merged_entry is None


# ---------------------------------------------------------------------
# Adversary-Fix-Loop #1657 -- Mutations-Gegenprobe hatte drei unbewachte
# Zweige gefunden (Protokoll: docs/artifacts/fix-1657-warnung-identitaet/
# adversary-dialog.md, Runde 2). Die folgenden Tests schliessen sie. Jeder
# traegt eine POSITIVKONTROLLE im selben Test: dieselbe Konstellation mit
# genau einem umgestellten Merkmal muss das ANDERE Ergebnis liefern -- sonst
# waere nicht belegt, dass die gepruefte Grenze das Ergebnis ueberhaupt traegt.
# ---------------------------------------------------------------------

F003_UNBRAUCHBARER_REPORTED_AT = [
    pytest.param("__schluessel-fehlt__", id="reported_at-fehlt-ganz"),
    pytest.param(None, id="reported_at-none"),
    pytest.param("", id="reported_at-leerer-string"),
    pytest.param("kein-zeitstempel", id="reported_at-unparsebar"),
]


@pytest.mark.parametrize("kaputter_wert", F003_UNBRAUCHBARER_REPORTED_AT)
def test_f003_containment_mit_unbrauchbarem_reported_at_meldet_statt_zu_verschlucken(kaputter_wert):
    """Adversary F003 (#1657 Fix-Loop, CRITICAL): der `except`-Zweig des
    6h-Frische-Guards (`official_alerts.py:533-534`) war von KEINEM der 102
    Tests bewacht -- die Mutation `kandidat_frisch = True` (Containment greift
    ⇒ echte neue Warnung wird VERSCHLUCKT) blieb komplett gruen. Genau die
    gefaehrliche Richtung an der Stelle, die die Spec "die einzige Sicherung
    dagegen, dass eine echte neue Warnung verschluckt wird" nennt.

    `test_f002_tie_break_und_merge_ueberleben_reported_at_null` erreicht den
    Zweig nicht: dort ist `is_containment` in BEIDEN Teilfaellen `False`, der
    Guard wird nie betreten.

    Vier Ausfallarten eines migrierten/korrupten State-Eintrags (#1614 haelt
    `official_alert:`-Eintraege ueber den Briefing-Reset hinweg): Schluessel
    fehlt ganz, `None`, leerer String, unparsebarer Text. Erwartung jedes Mal:
    NICHT frisch ⇒ Containment greift nicht ⇒ die #1685-Vorverlegungs-Ausnahme
    bleibt wirksam ⇒ es wird gemeldet. Im Zweifel melden, nicht schlucken."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    now = _utc(16, 16, 30, 2)
    schmal = _mk_alert(_utc(16, 8), _utc(16, 9), 2, region=R1657)
    schmal_key = official_alert_state_key(schmal)
    breit = _mk_alert(_utc(16, 5), _utc(16, 13), 2, region=R1657)

    def _state(reported_at_wert) -> dict:
        entry = {
            "last_reported_value": 2.0,
            "valid_from": schmal.valid_from.isoformat(),
            "valid_to": schmal.valid_to.isoformat(),
        }
        if reported_at_wert != "__schluessel-fehlt__":
            entry["reported_at"] = reported_at_wert
        return {schmal_key: entry}

    # POSITIVKONTROLLE: identische Fenster, nur mit BRAUCHBAREM, frischem
    # `reported_at`. Sie beweist, dass `is_containment` hier tatsaechlich True
    # ist und der Guard-Zweig ueberhaupt erreicht wird -- ohne sie koennte der
    # Haupt-Assert auch aus einem ganz anderen Grund gruen sein.
    kontroll_state = {schmal_key: _entry_1657(schmal, now - timedelta(minutes=10))}
    kontrolle, _k_stale, _k_merged = official_alert_revision_verdict(breit, kontroll_state, now=now)
    assert kontrolle is False, (
        "Vorbedingung: mit frischem reported_at MUSS dieselbe Konstellation still bleiben "
        f"(sonst prueft der Test unten gar nicht den Guard-Zweig): {kontrolle!r}"
    )

    should_report, stale_key, merged_entry = official_alert_revision_verdict(
        breit, _state(kaputter_wert), now=now,
    )

    assert should_report is True, (
        f"F003: Kandidat mit unbrauchbarem reported_at ({kaputter_wert!r}) darf NICHT als "
        f"frisch gelten -- sonst verschluckt ein korrupter Alt-Eintrag eine echte neue "
        f"Gewitterwarnung: {should_report!r}"
    )
    assert stale_key is None and merged_entry is None, (
        f"Melden liefert kein stale_key/merged_entry: {stale_key!r} / {merged_entry!r}"
    )


def test_f001_beruehrung_aus_der_gegenrichtung_zaehlt_ebenfalls_als_ueberlappung():
    """Adversary F001 (#1657 Fix-Loop, MEDIUM): die Ueberlappungsbedingung
    `alert_vf <= cand_vt and cand_vf <= alert_vt` (`official_alerts.py:503`)
    besteht aus zwei unabhaengigen Grenzen. Die erste war bewacht (Mutation
    von 4 Tests gefangen), die ZWEITE nicht -- alle bisherigen
    Beruehrungs-Tests legen das neue Fenster HINTER den Bestand.

    Hier der umgekehrte Fall: das neue Fenster `13:00-14:00Z` endet exakt
    dort, wo der Bestandskandidat `14:00-15:00Z` beginnt (die Behoerde
    ergaenzt eine Stunde nach VORN). Auch das ist AC-1 -- dieselbe
    durchgehende Gefahr, keine neue Warnung."""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    bestand = _mk_alert(_utc(16, 14), _utc(16, 15), 2, region=R1657)
    bestand_key = official_alert_state_key(bestand)
    state = {bestand_key: _entry_1657(bestand, _utc(16, 13, 50))}
    davor = _mk_alert(_utc(16, 13), _utc(16, 14), 2, region=R1657)

    should_report, stale_key, merged_entry = official_alert_revision_verdict(davor, state)

    assert should_report is False, (
        "AC-1 (Gegenrichtung): ein Fenster, das exakt dort ENDET, wo der Bestand beginnt, "
        f"ist dieselbe amtliche Warnung und darf nicht erneut melden: {should_report!r}"
    )
    assert stale_key == bestand_key, f"Stille Revision muss den alten Schluessel markieren: {stale_key!r}"

    # POSITIVKONTROLLE: eine Sekunde echte Luecke davor -- Spiegelbild von
    # test_eine_sekunde_luecke_bleibt_eine_eigenstaendige_warnung. Ohne sie
    # waere nicht belegt, dass oben die BERUEHRUNG traegt und nicht etwa jedes
    # beliebige frueher liegende Fenster still bliebe.
    mit_luecke = _mk_alert(_utc(16, 12), _utc(16, 13, 59, 59), 2, region=R1657)
    luecke_report, luecke_stale, luecke_merged = official_alert_revision_verdict(
        mit_luecke, {bestand_key: _entry_1657(bestand, _utc(16, 13, 50))},
    )
    assert luecke_report is True, (
        f"AC-2 (Gegenrichtung): eine Sekunde echte Luecke bleibt eigenstaendig: {luecke_report!r}"
    )
    assert luecke_stale is None and luecke_merged is None


def test_f002_containment_greift_auch_bei_exakt_gleichem_fensterende():
    """Adversary F002 (#1657 Fix-Loop, MEDIUM): die Gleichheitsgrenze
    `alert_vt >= kandidat_vt` in `is_containment` (`official_alerts.py:525`)
    war ungetestet -- die Verschaerfung auf `>` blieb gruen.

    Konstellation, in der die Grenze das Ergebnis TATSAECHLICH kippt: der
    Kandidat `08:00-13:00Z` endet exakt mit dem neuen Fenster `05:00-13:00Z`,
    der Beginn liegt 3h frueher. Ohne Containment griffe die
    #1685-Vorverlegungs-Ausnahme (>=2h) und meldete erneut; mit Containment
    und frischem Kandidaten ist es ein reiner Granularitaetswechsel.

    (Die Schwester-Grenze `alert_vf <= kandidat_vf` ist NICHT auf diese Weise
    pruefbar -- s. Bericht: dort ist `<=` vs. `<` ein aequivalenter Mutant,
    weil bei `alert_vf == kandidat_vf` die Vorverlegung ohnehin 0h betraegt
    und Containment am Ergebnis nichts mehr aendern kann.)"""
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    now = _utc(16, 16, 30, 2)
    kandidat = _mk_alert(_utc(16, 8), _utc(16, 13), 2, region=R1657)
    kandidat_key = official_alert_state_key(kandidat)
    state = {kandidat_key: _entry_1657(kandidat, now - timedelta(minutes=10))}
    breit_gleiches_ende = _mk_alert(_utc(16, 5), _utc(16, 13), 2, region=R1657)

    should_report, stale_key, merged_entry = official_alert_revision_verdict(
        breit_gleiches_ende, state, now=now,
    )

    assert should_report is False, (
        "AC-3: gleiches Fensterende zaehlt als vollstaendiges Umschliessen -- der 3h "
        f"fruehere Beginn ist dann Granularitaet, keine Vorverlegung: {should_report!r}"
    )
    assert stale_key == kandidat_key and merged_entry is not None, (
        f"Stille Revision erwartet: stale_key={stale_key!r} merged_entry={merged_entry!r}"
    )

    # POSITIVKONTROLLE: EINE SEKUNDE vor dem Kandidatenende -- damit ist das
    # Umschliessen nicht mehr vollstaendig, die Vorverlegungs-Ausnahme lebt
    # wieder auf. Beweist, dass oben die Gleichheitsgrenze das Ergebnis traegt.
    knapp_kuerzer = _mk_alert(_utc(16, 5), _utc(16, 12, 59, 59), 2, region=R1657)
    kontroll_report, kontroll_stale, kontroll_merged = official_alert_revision_verdict(
        knapp_kuerzer, {kandidat_key: _entry_1657(kandidat, now - timedelta(minutes=10))}, now=now,
    )
    assert kontroll_report is True, (
        "Eine Sekunde vor dem Kandidatenende ist KEIN Containment mehr -- die "
        f"Vorverlegung >=2h muss dann wieder melden: {kontroll_report!r}"
    )
    assert kontroll_stale is None and kontroll_merged is None


def test_compare_pfad_behandelt_containment_wie_der_trip_pfad(monkeypatch):
    """Test 10/AC-9 (RED): Ortsvergleich-Paritaet ueber den echten Einstieg
    `CompareOfficialAlertService._detect`. Beide Lesepfade teilen sich
    dieselbe Funktion -- dieser Test beweist, dass der Compare-Pfad die
    Containment-Regel tatsaechlich erbt und nicht nur der Trip-Pfad sie hat.

    `reported_at` der vorbelegten Schmaleintraege steht auf der ECHTEN
    Wanduhr minus 10 Minuten (nicht auf der eingefrorenen Compare-Zeit): der
    Compare-Aufrufer reicht kein `now` herein, dort gilt der Default
    `datetime.now(timezone.utc)`. So ist der Guard hier deterministisch
    frisch, unabhaengig vom Kalendertag des Testlaufs."""
    from app.config import Settings
    from services.alert_state import AlertStateService
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    user_id = _fresh_user("t1657-compare")
    _clean_user(user_id)
    oa_base, backup = _registered_sources_backup()
    oa_base._REGISTERED_SOURCES.clear()
    try:
        frozen = datetime(2026, 8, 11, 6, 0, tzinfo=timezone.utc)
        _freeze_compare_now(monkeypatch, frozen)
        wall_now = datetime.now(timezone.utc)
        breit = _mk_alert(frozen - timedelta(hours=1), frozen + timedelta(hours=7), 2, region=R1657)
        schmal_a = _mk_alert(frozen + timedelta(hours=2), frozen + timedelta(hours=3), 2, region=R1657)
        schmal_b = _mk_alert(frozen + timedelta(hours=3), frozen + timedelta(hours=4), 2, region=R1657)

        loc = SavedLocation(id="loc-1657", name="Kartitsch-1657", lat=LAT, lon=LON, elevation_m=1000)
        register_official_alert_source(_RevisableOfficialAlertSource(LAT, LON, breit))
        preset_id = "preset-1657"
        state_svc = AlertStateService(user_id=user_id)
        state_svc.save(f"{preset_id}:{loc.id}", {
            official_alert_state_key(schmal_a): _entry_1657(schmal_a, wall_now - timedelta(minutes=40)),
            official_alert_state_key(schmal_b): _entry_1657(schmal_b, wall_now - timedelta(minutes=10)),
        })

        settings = Settings(smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
                            mail_to="dummy@example.com")
        svc = CompareOfficialAlertService(settings=settings, user_id=user_id, mail_sink=lambda *a: None)

        new_or_escalated, per_loc = svc._detect(preset_id, [loc])

        assert new_or_escalated == [], (
            f"AC-9: der Ortsvergleichs-Pfad muss das umschliessende Breitfenster genauso "
            f"still fortschreiben wie der Trip-Pfad: {new_or_escalated!r}"
        )
        assert per_loc == {}, f"Kein Ort darf als neu gelten: {per_loc!r}"
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)
