"""TDD RED — Issue #2217: Stapellaeufe abschotten. Eine Ausnahme bei EINER
Einheit (Trip bzw. Ortsvergleich) darf die Folge-Einheiten desselben
Alarmlaufs nicht mitreissen; der Ausfall bleibt sichtbar (``failed`` in der
Antwort, ERROR-Log mit ID und Stacktrace).

SPEC: docs/specs/modules/fix_2217_stapellauf_abschotten.md (AC-1 bis AC-6,
AC-10). Go-Teil (AC-7/AC-8) und Briefing-Sammellauf (AC-11 bis AC-14) liegen
in eigenen Dateien.

Gemessen wird dort, wo die Zusicherung WIRKT: echter FastAPI-Router
(``api/routers/scheduler.py``), Folge-Einheit bekommt ihren Alarm (Mail ueber
die ``mail_sink``-DI-Naht, Sperrzeit-Buchung), Antwort traegt ``failed``.

Wie die kaputte Einheit entsteht (jeweils INNERHALB des Schleifenrumpfs,
hinter allen bestehenden engen ``except``-Bloecken — per Probe verifiziert):

* Ortsvergleich-Abweichungslauf: echte kaputte Daten, ``display_config`` ist
  ein String statt Objekt -> ``AttributeError`` in
  ``CompareAlertService._build_eval_config``.
* Ortsvergleich-Radarlauf: echte kaputte Daten, ``alert_cooldown_minutes`` ist
  ein String -> ``TypeError`` beim Versandaufbau (``_format_cooldown_display``).
* Ortsvergleich-amtlich: echte kaputte Daten, ``official_warnings`` ist ein
  String -> ``AttributeError`` in ``_check_one_preset``.
* Trip-Radarlauf: kein Feld der Trip-Datei wirft dort (Loader parst streng,
  ``tz_for_coords`` faellt auf UTC zurueck, Kanal-/Positionsfehler sind schon
  je Trip abgefangen). Testnaht: ``_ScriptedRadar``-Unterklasse liefert fuer
  den kaputten Trip ein unbrauchbares Ergebnisobjekt (Muster F009 aus
  ``test_radar_alarmlauf_fairness.py``) -> ``AttributeError`` bei
  ``result.throttled`` im Rumpf von ``_check_radar_trips``.
* Unwetterwarnungs-Lauf (``check_all_trips``): alle datengetriebenen Stellen
  sind abgefangen; ungeschuetzt bleibt der Aufruf ``_get_cached_weather`` im
  Schleifenrumpf. Testnaht: die konfigurierte Unterklasse (s. u.) laesst ihn
  fuer den kaputten Trip werfen ("Anker unlesbar"); die Schleife selbst ist
  unveraendert der echte Pruefling.

Der Router baut die Dienste ohne Settings/Sinks. Wie in
``test_compare_official_alert.py::test_ac8_scheduler_endpoint_delegates``
wird der Modul-Name des Dienstes auf eine echte Unterklasse umgebunden, die
nur deterministische Settings, ``mail_sink`` und Radar-/Wetterquelle als
Default hineinreicht (kein Mock, keine Verhaltens-Attrappe des Prueflings).

RED-Nachweis (Probe 2026-10-06): jeder heutige HTTP 500 stammt aus der
beabsichtigten Ausnahme im Schleifenrumpf (``_check_radar_trips``,
``check_all_trips`` -> ``_get_cached_weather``, ``_build_eval_config``,
``_format_cooldown_display``, ``CompareOfficialAlertService._check_one_preset``);
dieselben Aufbauten OHNE kaputte Einheit liefern je gesunder Einheit eine Mail
(Gegenprobe, Aufbau traegt).

Aufruf wie in der CI: ``--disable-socket --allow-unix-socket`` (ohne
Unix-Socket kann der TestClient keine Event-Loop oeffnen -> 500 ohne Bezug).

HINWEIS fuer GREEN:``test_radar_alarmlauf_fairness.py::
test_compare_radar_ausfall_ort1_bleibt_bei_unerwartetem_fehler_an_ort2``
erwartet heute, dass ein ``AttributeError`` den Aufrufer erreicht
(``pytest.raises``). Nach dem Fix wird er je Preset gefangen — der Test muss
in der GREEN-Phase angepasst werden (Kernaussage „Ausfall von Ort 1 bleibt im
Protokoll" bleibt bestehen).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest

# Auf Modulebene: api/main.py ruft beim ersten Import logging.basicConfig(force=True)
# auf und entfernt sonst den caplog-Handler eines laufenden Tests.
from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402

from app.loader import get_data_dir, save_location, save_trip
from app.user import SavedLocation
from services import compare_alert as compare_alert_mod
from services import compare_official_alert as compare_official_mod
from services import compare_radar_alert as compare_radar_mod
from services import trip_alert
from services.official_alerts import OfficialAlert, register_official_alert_source
from services.radar_service import RadarDeadlineExceeded
from services.throttle_store import ThrottleStore

from tests.helpers.compare_briefings import write_compare_briefings
from tests.tdd.test_alert_run_deadline import (  # noqa: F401  (autouse-Fixture per Name)
    LAT,
    LON,
    _CoveringOfficialAlertSource,
    _isolated_official_alert_sources,
    _official_trigger_trip,
    _save_cached,
    _weather_data,
)
from tests.tdd.test_compare_radar_alert import _data_root_users, _radar_preset
from tests.tdd.test_issue_1169_compare_alert_consumer import _ScriptedWeatherSource, _point
from tests.tdd.test_issue_827_radar_throttle_recording import _make_settings_with_email
from tests.tdd.test_radar_alarmlauf_fairness import (  # noqa: F401  (autouse-Fixture per Name)
    DEADLINE_S,
    LOC_LAT0,
    LOC_LON,
    LOC_STEP,
    SLEEP_S,
    _gestellte_uhr,
    _loc_idx,
    _make_trips,
    _patch_deadline,
    _premium,
    _ScriptedRadar,
    _settings_email_capable_dummy,
    _trip_idx,
    _uid,
)

# Originale beim Import festhalten: die Umbindung im Test darf nie eine
# bereits umgebundene Unterklasse erneut ableiten.
_TRIP_SERVICE = trip_alert.TripAlertService
_COMPARE_ALERT_SERVICE = compare_alert_mod.CompareAlertService
_COMPARE_RADAR_SERVICE = compare_radar_mod.CompareRadarAlertService
_COMPARE_OFFICIAL_SERVICE = compare_official_mod.CompareOfficialAlertService


# ---------------------------------------------------------------------------
# Testnaehte
# ---------------------------------------------------------------------------

class _UnbrauchbaresErgebnis(_ScriptedRadar):
    """Wie ``_ScriptedRadar`` (Schlafzeit, Zaehler, ``raise_on``), liefert aber
    fuer die Einheiten in ``kaputt_idx`` (optional nur fuer ``kaputt_user``)
    ein unbrauchbares Ergebnisobjekt. Die Auswertung wirft dann im
    Schleifenrumpf ausserhalb aller bestehenden ``try``-Bloecke."""

    def __init__(self, idx_fn, *, kaputt_idx=(0,), kaputt_user=None, **kw) -> None:
        super().__init__(idx_fn, **kw)
        self._kaputt_idx = set(kaputt_idx)
        self._kaputt_user = kaputt_user

    def get_nowcast(
        self, lat, lon, elevation_m=None, priority="user_briefing", user_id=None,
        deadline_at=None,
    ):
        normal = super().get_nowcast(
            lat, lon, elevation_m, priority, user_id, deadline_at=deadline_at,
        )
        if self._idx_fn(lat) in self._kaputt_idx and (
            self._kaputt_user is None or user_id == self._kaputt_user
        ):
            return object()
        return normal


def _bind_trip_service(monkeypatch, mails: list, *, radar=None, kaputter_anker=()):
    """Router-Aufrufer bleibt echt; die Unterklasse reicht nur Defaults hinein.
    ``kaputter_anker``: Trip-IDs, deren Wetter-Anker unlesbar ist (Testnaht fuer
    den Unwetterwarnungs-Lauf, s. Modul-Docstring)."""
    kaputt = set(kaputter_anker)

    class _Konfiguriert(_TRIP_SERVICE):
        def __init__(self, settings=None, throttle_hours=2, *, user_id,
                     radar_service=None, mail_sink=None):
            super().__init__(
                settings or _make_settings_with_email(), throttle_hours,
                user_id=user_id,
                radar_service=radar_service or radar,
                mail_sink=mail_sink or (
                    lambda subject, body: mails.append((user_id, subject, body))
                ),
            )

        def _get_cached_weather(self, trip, **kw):
            if trip.id in kaputt:
                raise RuntimeError(f"Wetter-Anker von Trip {trip.id} unlesbar")
            return super()._get_cached_weather(trip, **kw)

    monkeypatch.setattr(trip_alert, "TripAlertService", _Konfiguriert)


def _bind_compare_alert(monkeypatch, mails: list, weather_source) -> None:
    class _Konfiguriert(_COMPARE_ALERT_SERVICE):
        def __init__(self, **kw):
            uid = kw["user_id"]
            kw.setdefault("settings", _settings_email_capable_dummy())
            kw.setdefault("mail_sink", lambda subject, body: mails.append((uid, subject, body)))
            kw.setdefault("weather_source", weather_source)
            super().__init__(**kw)

    monkeypatch.setattr(compare_alert_mod, "CompareAlertService", _Konfiguriert)


def _bind_compare_radar(monkeypatch, mails: list, radar) -> None:
    class _Konfiguriert(_COMPARE_RADAR_SERVICE):
        def __init__(self, settings=None, *, user_id, radar_service=None, mail_sink=None):
            super().__init__(
                settings or _settings_email_capable_dummy(), user_id=user_id,
                radar_service=radar_service or radar,
                mail_sink=mail_sink or (
                    lambda subject, body: mails.append((user_id, subject, body))
                ),
            )

    monkeypatch.setattr(compare_radar_mod, "CompareRadarAlertService", _Konfiguriert)


def _bind_compare_official(monkeypatch, mails: list) -> None:
    class _Konfiguriert(_COMPARE_OFFICIAL_SERVICE):
        def __init__(self, **kw):
            uid = kw["user_id"]
            kw.setdefault("settings", _settings_email_capable_dummy())
            kw.setdefault("mail_sink", lambda subject, body: mails.append((uid, subject, body)))
            super().__init__(**kw)

    monkeypatch.setattr(compare_official_mod, "CompareOfficialAlertService", _Konfiguriert)


def _post(endpoint: str, uid: str):
    """Echter Router. ``raise_server_exceptions=False``: heute endet ein
    kaputter Lauf als HTTP 500 (so sieht es auch Go), nicht als Python-
    Ausnahme im Test."""
    return TestClient(app, raise_server_exceptions=False).post(
        f"/api/scheduler/{endpoint}?user_id={uid}"
    )


def _json(resp) -> dict:
    try:
        return resp.json()
    except Exception:
        return {"_raw": resp.text[:300]}


def _mails_fuer(mails: list, uid: str) -> list:
    return [m for m in mails if m[0] == uid]


# ---------------------------------------------------------------------------
# Daten-Aufbau Ortsvergleich
# ---------------------------------------------------------------------------

def _radar_presets(uid: str, specs: list[tuple[str, dict]]) -> list[str]:
    """Je Preset EIN Ort, Breite LOC_LAT0 + i*LOC_STEP (Index i = Position)."""
    _premium(uid)
    presets = []
    for i, (preset_id, extra) in enumerate(specs):
        loc_id = f"loc-{preset_id}"
        save_location(
            SavedLocation(id=loc_id, name=f"Ort {preset_id}", lat=LOC_LAT0 + i * LOC_STEP,
                          lon=LOC_LON, elevation_m=1000),
            user_id=uid,
        )
        p = _radar_preset(preset_id, [loc_id], ["gregor-test@henemm.com"])
        p.update(extra)
        presets.append(p)
    write_compare_briefings(_data_root_users() / uid, presets)
    return [pid for pid, _ in specs]


def _deviation_presets(uid: str, specs: list[tuple[str, dict]]) -> None:
    """Ortsvergleich-Abweichungslauf: Preset + Ort + Δ-Anker (2 mm) je Preset;
    die Wetterquelle liefert 18 mm (Δ=16 >= Standard-Schwelle 10)."""
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    _radar_presets(uid, specs)
    snap = CompareWeatherSnapshotService(user_id=uid)
    for i, (preset_id, _extra) in enumerate(specs):
        loc_id = f"loc-{preset_id}"
        snap.save(preset_id, loc_id, _point(
            loc_id, f"Ort {preset_id}", LOC_LAT0 + i * LOC_STEP, LOC_LON, precip_sum_mm=2.0,
        ))


def _deviation_source(preset_ids: list[str]) -> _ScriptedWeatherSource:
    return _ScriptedWeatherSource({f"loc-{pid}": 18.0 for pid in preset_ids})


# Amtliche Warnungen: je Preset ein Ort, klar getrennte Koordinaten.
OFF_LAT0, OFF_LON = 46.62, 13.68
OFF_STEP = 0.4


def _official_presets(
    uid: str, specs: list[tuple[str, dict]], *, warn_for: list[str], offset: int = 0,
) -> None:
    """Preset + Ort; fuer jedes Preset in ``warn_for`` eine echte Fake-Quelle
    (strukturell typisiert, kein Mock), die genau dessen Ort abdeckt."""
    from tests.tdd.test_compare_official_alert import _FakeOfficialAlertSource, _preset

    _premium(uid)
    now = datetime.now(timezone.utc)
    presets = []
    for i, (preset_id, extra) in enumerate(specs):
        loc_id = f"loc-{preset_id}"
        lat = OFF_LAT0 + (offset + i) * OFF_STEP
        save_location(
            SavedLocation(id=loc_id, name=f"Ort {preset_id}", lat=lat, lon=OFF_LON,
                          elevation_m=1000),
            user_id=uid,
        )
        p = _preset(preset_id, [loc_id], ["gregor-test@henemm.com"])
        p.update(extra)
        presets.append(p)
        if preset_id in warn_for:
            register_official_alert_source(_FakeOfficialAlertSource(lat, OFF_LON, [OfficialAlert(
                source="test-2217", hazard="thunderstorm", level=3,
                label=f"Gewitter {preset_id}",
                valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=20),
                region_label=f"Region {preset_id}",
            )]))
    write_compare_briefings(_data_root_users() / uid, presets)


# ---------------------------------------------------------------------------
# Daten-Aufbau Unwetterwarnungs-Lauf (check_all_trips)
# ---------------------------------------------------------------------------

def _unwetter_trips(uid: str, trip_ids: list[str]) -> None:
    """Je Trip ein eigener Ort (LAT+i, LON+i), Wetter-Anker und eine echte
    amtliche Fake-Quelle mit einer Gewitterwarnung (Muster
    ``test_alert_run_deadline::test_full_run_matches_legacy_alert_count``)."""
    _premium(uid)
    for i, trip_id in enumerate(trip_ids):
        lat, lon = LAT + i, LON + i
        trip = _official_trigger_trip(trip_id, lat=lat, lon=lon)
        save_trip(trip, user_id=uid)
        _save_cached(uid, trip.id, [_weather_data(1, lat=lat, lon=lon, precip_sum_mm=2.0)])
        register_official_alert_source(_CoveringOfficialAlertSource(lat, lon, OfficialAlert(
            source=f"test-2217-src-{trip_id}", hazard="thunderstorm", level=3,
            label=f"Warnung {trip_id}",
        )))


def _error_records_mit_id(caplog, unit_id: str) -> list:
    return [
        r for r in caplog.records
        if r.levelno >= logging.ERROR and unit_id in r.getMessage()
    ]


def _assert_error_log_mit_stacktrace(caplog, unit_id: str, exc_name: str) -> None:
    records = _error_records_mit_id(caplog, unit_id)
    mit_trace = [
        r for r in records
        if r.exc_info and r.exc_info[0] is not None and r.exc_info[0].__name__ == exc_name
    ]
    assert mit_trace, (
        f"Erwartet: ERROR-Eintrag mit der ID {unit_id!r} UND Stacktrace (exc_info, "
        f"{exc_name}). ERROR-Eintraege mit der ID: "
        f"{[(r.getMessage(), bool(r.exc_info)) for r in records]!r}; alle ERROR: "
        f"{[r.getMessage()[:120] for r in caplog.records if r.levelno >= logging.ERROR]!r}"
    )


# ===========================================================================
# AC-1 — Trip-Radarlauf: kaputter erster Trip, zweiter wird alarmiert.
# ===========================================================================

def test_trip_radar_kaputter_trip_reisst_folgetrip_nicht_mit(monkeypatch):
    """AC-1: Given zwei Trips mit aktivem Radar-Alarm, die Pruefung des ersten
    wirft (unbrauchbares Quellenergebnis) / When der Radar-Lauf ueber den
    echten Endpunkt laeuft / Then bekommt der zweite Trip seinen Alarm (Mail +
    Sperrzeit gebucht), die Antwort ist HTTP 200 mit ``failed == 1`` und
    nicht ``partial``.

    RED heute: der AttributeError bricht den Lauf ab (HTTP 500), der zweite
    Trip wird nie geprueft."""
    uid = _uid("ac1")
    ids = _make_trips(uid, ["a-kaputt", "b-heil"])
    mails: list = []
    radar = _UnbrauchbaresErgebnis(_trip_idx, wet=True, kaputt_idx=(0,))
    _bind_trip_service(monkeypatch, mails, radar=radar)

    resp = _post("radar-alert-checks", uid)
    data = _json(resp)

    assert len(_mails_fuer(mails, uid)) == 1, (
        f"Der Folge-Trip {ids[1]!r} muss im selben Lauf alarmiert werden "
        f"(Mails: {len(mails)}, Antwort {resp.status_code} {data!r})"
    )
    assert ThrottleStore(uid).last_sent("radar", ids[1]) is not None, (
        "Alarm des Folge-Trips muss auf die Sperrzeit gebucht sein"
    )
    assert resp.status_code == 200, (resp.status_code, data)
    assert data.get("failed") == 1, f"Antwort muss failed == 1 tragen: {data!r}"
    assert data.get("status") != "partial", (
        f"Ein gescheiterter Trip ist kein Teilerfolg (partial bleibt der Zeitgrenze "
        f"vorbehalten): {data!r}"
    )
    assert data.get("count") == 1, data


# ===========================================================================
# AC-2 — Unwetterwarnungs-Lauf (check_all_trips).
# ===========================================================================

def test_unwetterlauf_kaputter_trip_reisst_folgetrip_nicht_mit(monkeypatch):
    """AC-2: Given zwei Trips mit amtlicher Gewitterwarnung im Lauf
    ``check_all_trips``, beim ersten wirft der Wetter-Anker-Zugriff / When der
    Lauf ueber ``/alert-checks`` startet / Then erhaelt der zweite Trip seine
    Warnung, Antwort HTTP 200 mit ``failed == 1``, nicht ``partial``.

    RED heute: die Ausnahme bricht den Lauf ab (HTTP 500), keine Warnung."""
    uid = _uid("ac2")
    _unwetter_trips(uid, ["a-kaputt", "b-heil"])
    mails: list = []
    _bind_trip_service(monkeypatch, mails, kaputter_anker=("a-kaputt",))

    resp = _post("alert-checks", uid)
    data = _json(resp)

    assert len(_mails_fuer(mails, uid)) == 1, (
        f"Der Folge-Trip 'b-heil' muss seine Warnung bekommen (Mails: {len(mails)}, "
        f"Antwort {resp.status_code} {data!r})"
    )
    assert resp.status_code == 200, (resp.status_code, data)
    assert data.get("failed") == 1, f"Antwort muss failed == 1 tragen: {data!r}"
    assert data.get("status") != "partial", data
    assert data.get("checked") == 2, f"Gescheiterter Trip zaehlt in checked mit: {data!r}"


# ===========================================================================
# AC-3 — drei Ortsvergleich-Laeufe, je ein eigener Test.
# ===========================================================================

def test_ortsvergleich_abweichungslauf_kaputtes_preset_reisst_folgepreset_nicht_mit(monkeypatch):
    """AC-3 (Standard-Lauf, ``/compare-alert-checks``): erstes Preset hat ein
    kaputtes ``display_config`` (String) -> das zweite wird trotzdem geprueft
    und alarmiert, Antwort 200 mit ``failed == 1``.

    RED heute: AttributeError in ``_build_eval_config`` -> HTTP 500."""
    uid = _uid("ac3a")
    specs = [("p-a-kaputt", {"display_config": "kaputt"}), ("p-b-heil", {})]
    _deviation_presets(uid, specs)
    mails: list = []
    _bind_compare_alert(monkeypatch, mails, _deviation_source([s[0] for s in specs]))

    resp = _post("compare-alert-checks", uid)
    data = _json(resp)

    assert len(_mails_fuer(mails, uid)) == 1, (
        f"Folge-Preset 'p-b-heil' muss alarmiert werden (Mails: {len(mails)}, "
        f"Antwort {resp.status_code} {data!r})"
    )
    assert resp.status_code == 200, (resp.status_code, data)
    assert data.get("failed") == 1, f"Antwort muss failed == 1 tragen: {data!r}"
    assert data.get("count") == 1, data
    assert data.get("status") != "partial", data


def test_ortsvergleich_radarlauf_kaputtes_preset_reisst_folgepreset_nicht_mit(monkeypatch):
    """AC-3 (Radar-Lauf, ``/compare-radar-alert-checks``): erstes Preset hat
    ein kaputtes ``alert_cooldown_minutes`` (String), beide Orte melden Regen
    -> das zweite Preset wird alarmiert, Antwort 200 mit ``failed == 1``.

    RED heute: TypeError beim Versandaufbau des ersten Presets -> HTTP 500."""
    uid = _uid("ac3r")
    ids = _radar_presets(uid, [
        ("p-a-kaputt", {"alert_cooldown_minutes": "kaputt"}), ("p-b-heil", {}),
    ])
    mails: list = []
    _bind_compare_radar(monkeypatch, mails, _ScriptedRadar(_loc_idx, wet=True))

    resp = _post("compare-radar-alert-checks", uid)
    data = _json(resp)

    assert len(_mails_fuer(mails, uid)) == 1, (
        f"Folge-Preset {ids[1]!r} muss alarmiert werden (Mails: {len(mails)}, "
        f"Antwort {resp.status_code} {data!r})"
    )
    assert resp.status_code == 200, (resp.status_code, data)
    assert data.get("failed") == 1, f"Antwort muss failed == 1 tragen: {data!r}"
    assert data.get("checked") == 2, f"Gescheitertes Preset zaehlt in checked mit: {data!r}"
    assert data.get("status") != "partial", data


def test_ortsvergleich_amtlich_kaputtes_preset_reisst_folgepreset_nicht_mit(monkeypatch):
    """AC-3 (amtliche Warnungen, ``/compare-official-alert-checks``): erstes
    Preset hat ein kaputtes ``official_warnings`` (String) -> das zweite
    bekommt seine Warnung, Antwort 200 mit ``failed == 1``.

    RED heute: AttributeError in ``_check_one_preset`` -> HTTP 500."""
    uid = _uid("ac3o")
    _official_presets(uid, [
        ("p-a-kaputt", {"official_warnings": "kaputt"}), ("p-b-heil", {}),
    ], warn_for=["p-a-kaputt", "p-b-heil"])
    mails: list = []
    _bind_compare_official(monkeypatch, mails)

    resp = _post("compare-official-alert-checks", uid)
    data = _json(resp)

    assert len(_mails_fuer(mails, uid)) == 1, (
        f"Folge-Preset 'p-b-heil' muss seine Warnung bekommen (Mails: {len(mails)}, "
        f"Antwort {resp.status_code} {data!r})"
    )
    assert resp.status_code == 200, (resp.status_code, data)
    assert data.get("failed") == 1, f"Antwort muss failed == 1 tragen: {data!r}"
    assert data.get("count") == 1, data
    assert data.get("status") != "partial", data


# ===========================================================================
# AC-4 — Zeitgrenze bleibt partial, getrennt von failed.
# ===========================================================================

def test_trip_radar_grenzabbruch_nach_gescheitertem_trip_partial_und_failed(monkeypatch):
    """AC-4: Trip 1 scheitert, Trip 2 bricht mit ``RadarDeadlineExceeded``
    ab, Trip 3 wird nicht erreicht / Then ``status == "partial"``,
    ``reason == "deadline"``, ``failed == 1`` (nur Trip 1), Trip 2 und 3 in
    ``skipped_ids`` (der Grenzabbruch wird NICHT vom breiten Fehlerfaenger
    geschluckt — sonst waere failed 2 und Trip 3 wuerde noch geprueft).

    RED heute: Trip 1 bricht den Lauf ab (HTTP 500)."""
    uid = _uid("ac4t")
    ids = _make_trips(uid, ["a-kaputt", "b-grenze", "c-rest"])
    radar = _UnbrauchbaresErgebnis(
        _trip_idx, kaputt_idx=(0,),
        raise_on=(1, 1, RadarDeadlineExceeded("Zeitgrenze")),
    )
    _bind_trip_service(monkeypatch, [], radar=radar)

    resp = _post("radar-alert-checks", uid)
    data = _json(resp)

    assert resp.status_code == 200, (resp.status_code, data)
    assert data.get("status") == "partial" and data.get("reason") == "deadline", data
    assert data.get("failed") == 1, f"Nur der gescheiterte Trip zaehlt in failed: {data!r}"
    assert data.get("skipped_ids") == ids[1:], (
        f"Grenzabbruch bei {ids[1]!r}: er und {ids[2]!r} sind nicht erreicht: {data!r}"
    )
    assert data.get("checked") == 1, data
    assert radar.calls_per_unit.get(2, 0) == 0, (
        f"Nach dem Grenzabbruch darf kein weiterer Trip geprueft werden: "
        f"{radar.calls_per_unit!r}"
    )


def test_trip_radar_reiner_grenzabbruch_meldet_failed_null(monkeypatch):
    """AC-4: Grenzabbruch ohne gescheiterten Trip -> ``partial``/``deadline``
    und ``failed == 0`` (Feld vorhanden, Zeitgrenze ist kein Ausfall).

    RED heute: die Antwort traegt kein ``failed``."""
    uid = _uid("ac4p")
    _make_trips(uid, ["a", "b", "c", "d"])
    _patch_deadline(monkeypatch, DEADLINE_S)
    _bind_trip_service(monkeypatch, [], radar=_ScriptedRadar(_trip_idx, sleep_first_s=SLEEP_S))

    data = _json(_post("radar-alert-checks", uid))

    assert data.get("status") == "partial" and data.get("reason") == "deadline", data
    assert "failed" in data and data["failed"] == 0, (
        f"Grenzabbruch ist kein Ausfall: failed muss vorhanden und 0 sein: {data!r}"
    )


def test_ortsvergleich_radar_grenzabbruch_nach_gescheitertem_preset_partial_und_failed(monkeypatch):
    """AC-4 (Ortsvergleich-Radar): Preset 1 scheitert (kaputte Daten), Preset 2
    bricht an der Zeitgrenze ab, Preset 3 nicht erreicht -> ``partial`` und
    ``failed == 1`` getrennt gezaehlt, Preset 2/3 in ``skipped_ids``.

    RED heute: Preset 1 bricht den Lauf ab (HTTP 500)."""
    uid = _uid("ac4c")
    ids = _radar_presets(uid, [
        ("p-a-kaputt", {"alert_cooldown_minutes": "kaputt"}), ("p-b-grenze", {}), ("p-c-rest", {}),
    ])
    radar = _ScriptedRadar(_loc_idx, wet=True, raise_on=(1, 1, RadarDeadlineExceeded("Zeitgrenze")))
    _bind_compare_radar(monkeypatch, [], radar)

    resp = _post("compare-radar-alert-checks", uid)
    data = _json(resp)

    assert resp.status_code == 200, (resp.status_code, data)
    assert data.get("status") == "partial" and data.get("reason") == "deadline", data
    assert data.get("failed") == 1, data
    assert data.get("skipped_ids") == ids[1:], data
    assert radar.calls_per_unit.get(2, 0) == 0, radar.calls_per_unit


# ===========================================================================
# AC-5 — kaputter Trip rueckt in der Fairness-Reihenfolge nach hinten.
# ===========================================================================

def test_kaputter_trip_rueckt_in_der_reihenfolge_nach_hinten(monkeypatch):
    """AC-5: Given vier Trips, der (nach ID) erste scheitert bei JEDEM Lauf,
    die Zeitgrenze laesst je Lauf nur zwei Trips zu / When zwei Radar-Laeufe
    nacheinander / Then
    * Lauf 1 erreicht ``a-kaputt`` und ``b`` (``checked == 2`` — der
      gescheiterte Trip zaehlt mit, festgeschrieben), ``failed == 1``;
    * Lauf 2 beginnt mit den nicht erreichten ``c``, ``d`` — der kaputte Trip
      blockiert die Spitze nicht, weil sein Stempel VOR der Pruefung gesetzt
      wurde (Mutation „Stempel nach dem try" -> ``a-kaputt`` stuende ohne
      Stempel wieder vorn -> rot).

    RED heute: Lauf 1 bricht an ``a-kaputt`` ab (HTTP 500), ``b`` wird nie
    erreicht."""
    uid = _uid("ac5")
    ids = _make_trips(uid, ["a-kaputt", "b", "c", "d"])
    _patch_deadline(monkeypatch, DEADLINE_S)

    radar1 = _UnbrauchbaresErgebnis(_trip_idx, kaputt_idx=(0,), sleep_first_s=SLEEP_S)
    _bind_trip_service(monkeypatch, [], radar=radar1)
    resp1 = _post("radar-alert-checks", uid)
    first = _json(resp1)
    run1 = [ids[i] for i in radar1.first_seen]

    radar2 = _UnbrauchbaresErgebnis(_trip_idx, kaputt_idx=(0,), sleep_first_s=SLEEP_S)
    _bind_trip_service(monkeypatch, [], radar=radar2)
    second = _json(_post("radar-alert-checks", uid))
    run2 = [ids[i] for i in radar2.first_seen]

    assert run1 == ["a-kaputt", "b"], (
        f"Lauf 1 muss nach dem gescheiterten Trip weiterlaufen: erreicht {run1!r}, "
        f"Antwort {resp1.status_code} {first!r}"
    )
    assert resp1.status_code == 200, (resp1.status_code, first)
    assert first.get("checked") == 2 and first.get("failed") == 1, first
    assert first.get("skipped_ids") == ["c", "d"], first
    assert run2[:2] == ["c", "d"], (
        f"Lauf 2 muss mit den nicht erreichten Trips beginnen, nicht mit dem "
        f"kaputten: {run2!r} (Antwort {second!r})"
    )
    assert "a-kaputt" not in run2[:2], run2


# ===========================================================================
# AC-6 — ERROR-Log mit ID und Stacktrace (Trip- und Ortsvergleich-Laeufe).
# ===========================================================================

def test_log_trip_radar_nennt_trip_id_mit_stacktrace(monkeypatch, caplog):
    """AC-6 (Trip-Radar): ERROR-Eintrag mit der Trip-ID UND exc_info.

    RED heute: kein solcher Eintrag (der Lauf stirbt, Starlette loggt nur
    eine ID-lose ASGI-Ausnahme)."""
    uid = _uid("ac6t")
    _make_trips(uid, ["a-kaputt-log", "b-heil"])
    _bind_trip_service(monkeypatch, [], radar=_UnbrauchbaresErgebnis(_trip_idx, wet=True))
    with caplog.at_level(logging.ERROR):
        _post("radar-alert-checks", uid)
    _assert_error_log_mit_stacktrace(caplog, "a-kaputt-log", "AttributeError")


def test_log_unwetterlauf_nennt_trip_id_mit_stacktrace(monkeypatch, caplog):
    """AC-6 (check_all_trips): ERROR-Eintrag mit der Trip-ID UND exc_info."""
    uid = _uid("ac6u")
    _unwetter_trips(uid, ["a-kaputt-log", "b-heil"])
    _bind_trip_service(monkeypatch, [], kaputter_anker=("a-kaputt-log",))
    with caplog.at_level(logging.ERROR):
        _post("alert-checks", uid)
    _assert_error_log_mit_stacktrace(caplog, "a-kaputt-log", "RuntimeError")


def test_log_ortsvergleich_amtlich_nennt_preset_id_mit_stacktrace(monkeypatch, caplog):
    """AC-6 (Ortsvergleich, amtlich): ERROR-Eintrag mit der Preset-ID UND
    exc_info."""
    uid = _uid("ac6o")
    _official_presets(uid, [
        ("p-a-kaputt-log", {"official_warnings": "kaputt"}), ("p-b-heil", {}),
    ], warn_for=["p-a-kaputt-log", "p-b-heil"])
    _bind_compare_official(monkeypatch, [])
    with caplog.at_level(logging.ERROR):
        _post("compare-official-alert-checks", uid)
    _assert_error_log_mit_stacktrace(caplog, "p-a-kaputt-log", "AttributeError")


def test_log_ortsvergleich_radar_nennt_preset_id_mit_stacktrace(monkeypatch, caplog):
    """AC-6 (Ortsvergleich, Radar): ERROR-Eintrag mit der Preset-ID UND
    exc_info."""
    uid = _uid("ac6r")
    _radar_presets(uid, [
        ("p-a-kaputt-log", {"alert_cooldown_minutes": "kaputt"}), ("p-b-heil", {}),
    ])
    _bind_compare_radar(monkeypatch, [], _ScriptedRadar(_loc_idx, wet=True))
    with caplog.at_level(logging.ERROR):
        _post("compare-radar-alert-checks", uid)
    _assert_error_log_mit_stacktrace(caplog, "p-a-kaputt-log", "TypeError")


def test_log_ortsvergleich_abweichung_nennt_preset_id_mit_stacktrace(monkeypatch, caplog):
    """AC-6 (Ortsvergleich, Abweichung): ERROR-Eintrag mit der Preset-ID UND
    exc_info."""
    uid = _uid("ac6a")
    specs = [("p-a-kaputt-log", {"display_config": "kaputt"}), ("p-b-heil", {})]
    _deviation_presets(uid, specs)
    _bind_compare_alert(monkeypatch, [], _deviation_source([s[0] for s in specs]))
    with caplog.at_level(logging.ERROR):
        _post("compare-alert-checks", uid)
    _assert_error_log_mit_stacktrace(caplog, "p-a-kaputt-log", "AttributeError")


# ===========================================================================
# AC-10 — zwei echte Nutzer je Lauf-Art, Fehler nur bei A.
# ===========================================================================

_DEFAULT_FILES = (
    "alert_log.json", "alert_last_checked_radar.json", "alert_last_checked_compare_radar.json",
)


def _default_snapshot() -> dict:
    d = get_data_dir("default")
    return {f: ((d / f).read_bytes() if (d / f).exists() else None) for f in _DEFAULT_FILES}


def test_zwei_nutzer_trip_radar_fehler_nur_bei_a(monkeypatch, caplog):
    """AC-10 (Trip): Nutzer A hat einen kaputten und einen gesunden Trip,
    Nutzer B einen gesunden; derselbe Radar-Dienst, je Nutzer ein eigener
    Endpunkt-Aufruf (wie Go ihn macht) / Then werden A's gesunder Trip und
    B's Trip alarmiert, ``failed`` ist bei A 1 und bei B 0, der ERROR-Eintrag
    traegt nur A's Trip-ID, unter ``default`` aendert sich nichts.

    RED heute: A's Lauf bricht ab (HTTP 500, A's gesunder Trip ohne Alarm),
    B's Antwort traegt kein ``failed``."""
    user_a, user_b = _uid("ac10ta"), _uid("ac10tb")
    _make_trips(user_a, ["a-kaputt", "a-heil"])
    _make_trips(user_b, ["b-heil"])
    default_before = _default_snapshot()
    mails: list = []
    # Index 0 ist nur bei Nutzer A kaputt (B's einziger Trip liegt ebenfalls auf Index 0).
    radar = _UnbrauchbaresErgebnis(_trip_idx, wet=True, kaputt_idx=(0,), kaputt_user=user_a)
    _bind_trip_service(monkeypatch, mails, radar=radar)

    with caplog.at_level(logging.ERROR):
        resp_a = _post("radar-alert-checks", user_a)
        resp_b = _post("radar-alert-checks", user_b)
    data_a, data_b = _json(resp_a), _json(resp_b)

    assert len(_mails_fuer(mails, user_a)) == 1, (
        f"A's gesunder Trip muss alarmiert werden: {len(_mails_fuer(mails, user_a))} "
        f"Mails, Antwort {resp_a.status_code} {data_a!r}"
    )
    assert ThrottleStore(user_a).last_sent("radar", "a-heil") is not None
    assert len(_mails_fuer(mails, user_b)) == 1, data_b
    assert ThrottleStore(user_b).last_sent("radar", "b-heil") is not None
    assert resp_a.status_code == 200 and data_a.get("failed") == 1, (resp_a.status_code, data_a)
    assert resp_b.status_code == 200 and data_b.get("failed") == 0, (resp_b.status_code, data_b)
    assert _error_records_mit_id(caplog, "a-kaputt"), "Fehler muss A's Trip-ID tragen"
    assert not _error_records_mit_id(caplog, "b-heil"), "Fehler darf nicht B zugeordnet werden"
    assert _default_snapshot() == default_before, "Schreibzugriff unter data/users/default/"


def test_zwei_nutzer_ortsvergleich_fehler_nur_bei_a(monkeypatch, caplog):
    """AC-10 (Ortsvergleich, amtlich): Nutzer A hat ein kaputtes und ein
    gesundes Preset, Nutzer B ein gesundes / Then werden A's gesundes und B's
    Preset gewarnt, ``failed`` A=1/B=0, der ERROR-Eintrag traegt nur A's
    Preset-ID, unter ``default`` aendert sich nichts.

    RED heute: A's Lauf bricht ab (HTTP 500), B's Antwort ohne ``failed``."""
    user_a, user_b = _uid("ac10ca"), _uid("ac10cb")
    _official_presets(user_a, [
        ("p-a-kaputt", {"official_warnings": "kaputt"}), ("p-a-heil", {}),
    ], warn_for=["p-a-kaputt", "p-a-heil"])
    # Fake-Quellen sind global registriert: B's Ort bekommt eine eigene Breite.
    _official_presets(user_b, [("p-b-heil", {})], warn_for=["p-b-heil"], offset=2)
    default_before = _default_snapshot()
    mails: list = []
    _bind_compare_official(monkeypatch, mails)

    with caplog.at_level(logging.ERROR):
        resp_a = _post("compare-official-alert-checks", user_a)
        resp_b = _post("compare-official-alert-checks", user_b)
    data_a, data_b = _json(resp_a), _json(resp_b)

    assert len(_mails_fuer(mails, user_a)) == 1, (
        f"A's gesundes Preset muss gewarnt werden: Antwort {resp_a.status_code} {data_a!r}"
    )
    assert len(_mails_fuer(mails, user_b)) == 1, data_b
    assert resp_a.status_code == 200 and data_a.get("failed") == 1, (resp_a.status_code, data_a)
    assert resp_b.status_code == 200 and data_b.get("failed") == 0, (resp_b.status_code, data_b)
    assert _error_records_mit_id(caplog, "p-a-kaputt"), "Fehler muss A's Preset-ID tragen"
    assert not _error_records_mit_id(caplog, "p-b-heil"), "Fehler darf nicht B zugeordnet werden"
    assert _default_snapshot() == default_before, "Schreibzugriff unter data/users/default/"


# ===========================================================================
# Fix-Loop 1 (Adversary F001/F003/F005)
# ===========================================================================

class _DeadlineBeiQuellenbenennung(_ScriptedRadar):
    """F001-Naht: ``source_label`` wird in ``_check_radar_trips`` NACH den
    beiden Nowcast-Handlern (ausserhalb jedes inneren ``except
    RadarDeadlineExceeded``) beim Aufbau der Meldung gerufen. Die kleinste
    ehrliche Einspeisung an dieser bestehenden Naht (DI-Radar-Dienst): beim
    ersten Aufruf wirft sie die Zeitgrenzen-Ausnahme."""

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.label_calls = 0

    def source_label(self, source):
        self.label_calls += 1
        if self.label_calls == 1:
            raise RadarDeadlineExceeded("Zeitgrenze")
        return super().source_label(source)


def test_trip_radar_deadline_ausserhalb_der_nowcast_handler_ist_partial_nicht_failed(monkeypatch):
    """F001/AC-4: Die Zeitgrenze trifft den Lauf an einer Stelle ausserhalb der
    inneren Nowcast-Handler (Quellenbenennung beim Meldungsaufbau, Trip 1).
    Then: ``partial``/``deadline`` mit ``failed == 0``, Trip 1 gilt als nicht
    erreicht (``skipped_ids`` enthaelt alle drei, ``checked == 0``), Trip 2 und
    3 werden nicht mehr geprueft. Mutationen: Handler entfernen oder hinter
    ``except Exception`` setzen => die Zeitgrenze zaehlt als ``failed`` und der
    Lauf prueft weiter => rot."""
    uid = _uid("f001")
    ids = _make_trips(uid, ["a", "b", "c"])
    radar = _DeadlineBeiQuellenbenennung(_trip_idx, wet=True)
    mails: list = []
    _bind_trip_service(monkeypatch, mails, radar=radar)

    resp = _post("radar-alert-checks", uid)
    data = _json(resp)

    assert radar.label_calls >= 1, "Naht nicht erreicht (Aufbau traegt nicht)"
    assert resp.status_code == 200, (resp.status_code, data)
    assert data.get("status") == "partial" and data.get("reason") == "deadline", data
    assert data.get("failed") == 0, f"Zeitgrenze ist kein Ausfall: {data!r}"
    assert data.get("skipped_ids") == ids, data
    assert data.get("checked") == 0, data
    assert radar.label_calls == 1 and not mails, (radar.label_calls, mails)


def test_unwetterlauf_kaputter_trip_rueckt_in_der_reihenfolge_nach_hinten(monkeypatch):
    """F003 (AC-5 fuer ``check_all_trips``): vier Trips, der erste scheitert
    bei jedem Lauf, die Zeitgrenze laesst je Lauf nur zwei zu. Lauf 1 erreicht
    ``a-kaputt`` und ``b`` (``failed == 1``), Lauf 2 beginnt mit ``c`` (dann ``d``).
    Mutation: Fairness-Stempel nicht vor der Pruefung setzen (z. B. ans Ende
    des ``try`` verschieben) => ``a-kaputt`` bleibt ohne Stempel vorn => rot."""
    import time

    uid = _uid("f003")
    ids = ["a-kaputt", "b", "c", "d"]
    _unwetter_trips(uid, ids)
    monkeypatch.setattr(trip_alert, "ALERT_RUN_DEADLINE_SECONDS", 0.2)
    besucht: list[str] = []

    def _binde():
        class _Langsam(_TRIP_SERVICE):
            def __init__(self, settings=None, throttle_hours=2, *, user_id,
                         radar_service=None, mail_sink=None):
                super().__init__(
                    settings or _make_settings_with_email(), throttle_hours,
                    user_id=user_id, radar_service=radar_service,
                    mail_sink=mail_sink or (lambda subject, body: None),
                )

            def _get_cached_weather(self, trip, **kw):
                if trip.id not in besucht:
                    besucht.append(trip.id)
                if trip.id == "a-kaputt":
                    raise RuntimeError("Wetter-Anker unlesbar")
                time.sleep(0.3)
                return super()._get_cached_weather(trip, **kw)

        monkeypatch.setattr(trip_alert, "TripAlertService", _Langsam)

    _binde()
    first = _json(_post("alert-checks", uid))
    run1 = list(besucht)
    besucht.clear()
    second = _json(_post("alert-checks", uid))
    run2 = list(besucht)

    assert run1 == ["a-kaputt", "b"], (run1, first)
    assert first.get("failed") == 1 and first.get("checked") == 2, first
    assert run2[:1] == ["c"] and "a-kaputt" not in run2[:1], (
        f"Lauf 2 muss mit dem nicht erreichten Trip c beginnen, nicht mit dem "
        f"kaputten: {run2!r} ({second!r})"
    )
    assert (second.get("skipped_ids") or [None])[0] == "d", second


def _zone_scheitert_in_faelligkeit(monkeypatch, preset_id: str) -> None:
    """Nur die Zonenbestimmung INNERHALB von ``presets_due_for_hour`` scheitert
    (Naht ``compare_slot_scheduler.first_resolvable_tz``, wie im Briefing-
    Test); die Alarm-Dienste benutzen ihre eigene, ungepatchte Bindung."""
    from services import compare_slot_scheduler as css

    original = css.first_resolvable_tz

    def _zone(locations, context_label=""):
        if context_label == preset_id:
            raise RuntimeError("Zone nicht bestimmbar (Fehler-Injektion)")
        return original(locations, context_label=context_label)

    monkeypatch.setattr(css, "first_resolvable_tz", _zone)


def test_ortsvergleich_abweichung_unlesbare_faelligkeit_sperrt_alarm_und_zaehlt_failed(monkeypatch):
    """F005 (Standard-Lauf): scheitert die Faelligkeitspruefung der
    Vorlauf-Sperre fuer Preset 1, wird sein Alarm NICHT ohne Sperre gesendet;
    es zaehlt als ``failed == 1``, Preset 2 wird bedient. Mutation: Pruefung auf
    ``failed_ids`` (``due_or_raise``) entfernen => Preset 1 alarmiert => rot."""
    uid = _uid("f005a")
    specs = [("p-a-kaputt", {}), ("p-b-heil", {})]
    _deviation_presets(uid, specs)
    _zone_scheitert_in_faelligkeit(monkeypatch, "p-a-kaputt")
    mails: list = []
    _bind_compare_alert(monkeypatch, mails, _deviation_source([s[0] for s in specs]))

    resp = _post("compare-alert-checks", uid)
    data = _json(resp)

    assert resp.status_code == 200, (resp.status_code, data)
    assert data.get("failed") == 1, data
    assert len(_mails_fuer(mails, uid)) == 1, (
        f"Nur das gesunde Preset darf alarmieren: {[m[1] for m in mails]!r} {data!r}"
    )


def test_ortsvergleich_amtlich_unlesbare_faelligkeit_sperrt_alarm_und_zaehlt_failed(monkeypatch):
    """F005 (amtlicher Lauf): wie oben fuer ``/compare-official-alert-checks``."""
    uid = _uid("f005o")
    _official_presets(uid, [("p-a-kaputt", {}), ("p-b-heil", {})],
                      warn_for=["p-a-kaputt", "p-b-heil"])
    _zone_scheitert_in_faelligkeit(monkeypatch, "p-a-kaputt")
    mails: list = []
    _bind_compare_official(monkeypatch, mails)

    resp = _post("compare-official-alert-checks", uid)
    data = _json(resp)

    assert resp.status_code == 200, (resp.status_code, data)
    assert data.get("failed") == 1, data
    assert len(_mails_fuer(mails, uid)) == 1, (
        f"Nur das gesunde Preset darf warnen: {[m[1] for m in mails]!r} {data!r}"
    )
