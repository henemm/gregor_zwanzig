"""Woher die Vorschau ihre frischen Reihen holt (Issue #1737, AC-11/AC-14).

Der Frisch-Abruf der Vorschau muss mit denselben Argumenten laufen wie der Versand
(``compare_alert._evaluate_one_location``): mit der ECHTEN ``user_id`` (Abruf-Budget und
Mandantentrennung, nie ``"default"``) und mit dem Kalendertag des Ankers (``target_date``,
#1661 B2) -- sonst misst die Vorschau einen anderen Tag als der Versand.

Beobachtet wird an der Wirkstelle: eine aufzeichnende Abruf-Funktion mit der echten Signatur,
die an den echten ``CompareLocationWeatherSource().fetch`` weiterreicht (Fixture-Naht) und
dessen Daten liefert.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

from tests.integration.test_briefing_preview_bundle import env  # noqa: F401  (Fixture)
from tests.tdd.test_alert_hour_rows import CMP_STURM, _cmp_orte, _cmp_welt, _plant, _trip_welt


def _aufzeichnender_abruf(protokoll: list):
    from services.compare_location_weather_source import CompareLocationWeatherSource

    def fetch(point_id, lat, lon, start_hour=None, end_hour=None, **kwargs):
        protokoll.append(dict(kwargs))
        return CompareLocationWeatherSource().fetch(
            point_id, lat, lon, start_hour, end_hour, **kwargs)
    return fetch


def test_ortsvergleich_vorschau_ruft_mit_der_echten_user_id_ab(env, monkeypatch, tmp_path):  # noqa: F811
    from services.alert_preview_hours import compare_preview_point
    from tests.tdd.test_alert_preview_compare_paritaet import PRESET_ID

    preset = _cmp_welt(monkeypatch, tmp_path, env, anker_boeen={})
    _plant(tmp_path, monkeypatch, "csturm", CMP_STURM)
    protokoll: list = []
    frisch, anker = compare_preview_point(
        preset, PRESET_ID, _cmp_orte()[0], user_id=env, fetch=_aufzeichnender_abruf(protokoll))
    assert frisch is not None and anker is not None, "Vorbedingung: Abruf lieferte Daten"
    assert [p["user_id"] for p in protokoll] == [env]


def test_ortsvergleich_vorschau_ruft_den_kalendertag_des_ankers_ab(env, monkeypatch, tmp_path):  # noqa: F811
    """Anker beschreibt MORGEN (Abend-Slot) -> der Frisch-Abruf der Vorschau holt morgen,
    nicht heute; die frische Reihe traegt denselben Tag wie der Anker."""
    from services.alert_preview_hours import compare_preview_point
    from services.compare_location_weather_source import CompareLocationWeatherSource
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from tests.tdd.test_alert_preview_compare_paritaet import PRESET_ID

    preset = _cmp_welt(monkeypatch, tmp_path, env, anker_boeen=None)
    ort = _cmp_orte()[0]
    _plant(tmp_path, monkeypatch, "canker", {})
    morgen = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    punkt = CompareLocationWeatherSource().fetch(
        ort.id, ort.lat, ort.lon, 9, 16, elevation_m=ort.elevation_m, user_id=env)
    CompareWeatherSnapshotService(user_id=env).save(
        PRESET_ID, ort.id, dataclasses.replace(punkt, target_date=morgen))
    assert CompareWeatherSnapshotService(user_id=env).load(PRESET_ID, ort.id)[0].target_date == morgen

    protokoll: list = []
    frisch, _anker = compare_preview_point(
        preset, PRESET_ID, ort, user_id=env, fetch=_aufzeichnender_abruf(protokoll))
    assert [p.get("target_date") for p in protokoll] == [morgen]
    assert frisch.target_date == morgen


def test_trip_vorschau_ohne_verwertbare_frische_reihe_zeigt_keine_stundenzeilen(
    env, monkeypatch, tmp_path,  # noqa: F811
):
    """Frisch-Abruf liefert Segmente ohne Stundenreihe (echte ``SegmentWeatherData``) ->
    ``(None, None)`` statt einer leeren Reihe, die die Platzhalter-Segmente verdraengt."""
    from services.alert_preview_hours import trip_preview_series

    trip = _trip_welt(monkeypatch, tmp_path, env, anker_boeen={})
    aufrufe: list = []

    def ohne_reihe(anker):
        aufrufe.append(anker)
        return [dataclasses.replace(a, timeseries=None) for a in anker]

    out = trip_preview_series(
        trip, user_id=env, now_utc=datetime.now(timezone.utc), fetch=ohne_reihe)
    assert aufrufe and aufrufe[0], "Vorbedingung: Anker lag vor, Abruf lief"
    assert out == (None, None)


def test_ortsvergleich_vorschau_ohne_verwertbare_frische_reihe_zeigt_keine_stundenzeilen(
    env, monkeypatch, tmp_path,  # noqa: F811
):
    from services.alert_preview_hours import compare_preview_point
    from tests.tdd.test_alert_preview_compare_paritaet import PRESET_ID

    preset = _cmp_welt(monkeypatch, tmp_path, env, anker_boeen={})
    _plant(tmp_path, monkeypatch, "csturm", CMP_STURM)
    echt = _aufzeichnender_abruf([])

    def ohne_reihe(*args, **kwargs):
        return dataclasses.replace(echt(*args, **kwargs), timeseries=None)

    assert compare_preview_point(
        preset, PRESET_ID, _cmp_orte()[0], user_id=env, fetch=ohne_reihe) == (None, None)


def _ortsvergleich_anker_mit_alter(env, monkeypatch, tmp_path, stunden: float):  # noqa: F811
    """Preset des Nutzers + Anker fuer den ersten Ort mit ``fetched_at`` = jetzt - ``stunden``;
    danach liefert der Frisch-Abruf die Sturm-Reihe."""
    from services.compare_location_weather_source import CompareLocationWeatherSource
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from tests.tdd.test_alert_preview_compare_paritaet import PRESET_ID

    preset = _cmp_welt(monkeypatch, tmp_path, env, anker_boeen=None)
    ort = _cmp_orte()[0]
    _plant(tmp_path, monkeypatch, f"canker-{int(stunden)}h", {})
    punkt = CompareLocationWeatherSource().fetch(
        ort.id, ort.lat, ort.lon, 9, 16, elevation_m=ort.elevation_m, user_id=env)
    CompareWeatherSnapshotService(user_id=env).save(PRESET_ID, ort.id, dataclasses.replace(
        punkt, fetched_at=datetime.now(timezone.utc) - timedelta(hours=stunden)))
    _plant(tmp_path, monkeypatch, f"csturm-{int(stunden)}h", CMP_STURM)
    return preset, ort


def _dateistand(uid: str) -> dict:
    from app.loader import get_data_dir

    d = get_data_dir(uid)
    return {str(p.relative_to(d)): p.stat().st_mtime_ns for p in d.rglob("*") if p.is_file()}


def test_ortsvergleich_vorschau_mit_gerade_noch_frischem_anker_zeigt_stundenzeilen(
    env, monkeypatch, tmp_path,  # noqa: F811
):
    """Gegenprobe zur 26-h-Grenze: 25 h alter Anker -> Vorschau liefert (frisch, Anker)."""
    from services.alert_preview_hours import compare_preview_point
    from tests.tdd.test_alert_preview_compare_paritaet import PRESET_ID

    preset, ort = _ortsvergleich_anker_mit_alter(env, monkeypatch, tmp_path, 25)
    frisch, anker = compare_preview_point(preset, PRESET_ID, ort, user_id=env)
    assert frisch is not None and anker is not None


def test_ortsvergleich_vorschau_mit_zu_altem_anker_zeigt_keine_stundenzeilen(
    env, monkeypatch, tmp_path,  # noqa: F811
):
    """Anker aelter als 26 h: der Versand (``_evaluate_one_location``) verwirft ihn und meldet
    fuer diesen Ort nichts -- die Vorschau baut dann ebenfalls keine Stundenzeilen aus ihm
    (AC-11, Vorschau == Versand) und schreibt dabei nichts in den Nutzerordner (der Versand
    protokolliert hier eine fehlende Basis; die Vorschau nicht)."""
    from services.alert_preview_hours import compare_preview_point
    from tests.tdd.test_alert_preview_compare_paritaet import PRESET_ID

    preset, ort = _ortsvergleich_anker_mit_alter(env, monkeypatch, tmp_path, 27)
    vorher = _dateistand(env)
    out = compare_preview_point(preset, PRESET_ID, ort, user_id=env)
    assert out == (None, None), "zu alter Anker: Vorschau baut Stundenzeilen, der Versand nicht"
    assert _dateistand(env) == vorher, "Vorschau hat in den Nutzerordner geschrieben"
