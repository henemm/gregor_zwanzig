"""Bugfix #1947: SMS-Kanal-Reihenfolge "Gefühlte Temperatur" (wind_chill) an
Position 0 wirkt nicht -- das/die gerenderten Symbole (FL/FD/FN) landeten
strukturell am Ende der SMS statt an der vom Nutzer gezogenen Position.

ECHTER Root Cause (nach Korrektur des ersten, wirkungslosen Anlaufs --
Mutations-Gegenprobe des ersten Testentwurfs blieb GRUEN bei deaktiviertem
Fix, weil die Kind-IDs dort LITERAL in der Kanal-Layout-Liste standen und
dadurch unabhaengig vom Fix schon eine eigene Position bekamen):

``src/app/loader.py::_append_derived_metrics()`` haengt fuer Kind-Groessen
(``wind_chill_day_low/_day_high/_night``, ``temperature_day_low/_day_high/
_night`` -- ``_DERIVED_METRIC_RULES``) automatisch ein ``MetricConfig`` an,
sobald die Elterngroesse in einer Liste existiert -- AUCH in
``per_channel_layouts["sms"]``. Der neue Eintrag bekam hartcodiert
``bucket="secondary"`` ohne eigene ``order``.
``src/app/models.py::_sorted_by_layout()`` sortiert zuerst nach Bucket-Rang
(primary=0 vor secondary=1) -- ein secondary-Kind landete deshalb
STRUKTURELL IMMER hinter allen primary-Metriken, egal wo die Elterngroesse
selbst positioniert war.

Fix: das angehaengte ``MetricConfig`` uebernimmt ``bucket``/``order`` der
Elterngroesse statt hartcodiert secondary/0 -- gilt einheitlich fuer ALLE
sechs ``_DERIVED_METRIC_RULES``-Paare (wind_chill- UND temperature-Familie).

Wirkort-Prinzip: der Fehler entsteht im LADEPFAD (``loader.py``), nicht im
Renderer -- jeder Test hier geht deshalb durch ``load_trip()`` gegen eine
echte JSON-Datei (Muster ``tests/tdd/test_temp_tagesrichtung_bestandsableitung
.py``), NIE durch eine von Hand vorbelegte ``UnifiedWeatherDisplayConfig``
(die wuerde ``_append_derived_metrics()`` komplett umgehen und waere blind
fuer den Fix, exakt der Fehler des ersten Testentwurfs). Die Kanal-Layout-
Liste fuehrt NUR die Elterngroesse, NIE die Kind-IDs literal -- so wie es der
SMS-Kanal-Reihenfolge-Editor im Frontend tatsaechlich tut.

Keine Mocks, kein Netz -- reine Datenmodell-Objekte + echter Ladepfad +
Renderer-Aufruf (CLAUDE.md Test-Politik, Schicht "Kern").
"""
from __future__ import annotations

import json
from pathlib import Path

from app.loader import load_trip
from app.models import TripReportConfig
from output.renderers.trip_report import TripReportFormatter

from tests.tdd import _min_temp_felt_fixtures as F
from tests.tdd.test_sms_user_metric_order import _token_index

# ---------------------------------------------------------------------------
# Helfer -- realer Ladepfad (Muster test_temp_tagesrichtung_bestandsableitung.py)
# ---------------------------------------------------------------------------


def _write_trip(root: Path, trip_id: str, metrics: list[dict],
                 channel_layouts: dict | None = None) -> None:
    """Gespeicherter Trip im echten Dateiformat (briefings/<id>.json)."""
    display_config: dict = {"trip_id": trip_id, "metrics": metrics,
                             "show_night_block": True, "night_interval_hours": 2}
    if channel_layouts is not None:
        display_config["channel_layouts"] = channel_layouts
    path = root / "users" / "default" / "briefings" / f"{trip_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "id": trip_id, "name": trip_id, "kind": "route", "stages": [],
        "display_config": display_config,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


def _render_sms(root: Path, trip_id: str) -> tuple[str, str]:
    """Laedt den Trip real und rendert das Abend-Briefing.

    Returns (cascade_source, sms_text) -- die Kaskaden-Quelle ist die
    Vorbedingung jedes Tests (muss "per_channel" sein, sonst wird die zu
    pruefende Kaskade gar nicht durchlaufen, Spec-Pruefhinweis analog AC-13
    in test_temp_tagesrichtung_bestandsableitung.py)."""
    trip = load_trip(trip_id, data_dir=root, user_id="default")
    assert trip is not None, f"Trip {trip_id!r} nicht geladen"
    dc = trip.display_config
    source = dc.cascade_source_for_channel("sms", "evening")
    report = TripReportFormatter().format_email(
        [F.segment()], trip_name="I1947", report_type="evening",
        night_weather=F.night_weather(), display_config=dc,
        stage_name=F.STAGE_NAME, tz=F.TZ, report_config=TripReportConfig(),
    )
    return source, report.sms_text


# ---------------------------------------------------------------------------
# Familie 1: wind_chill (Symbole FL/FD/FN)
# ---------------------------------------------------------------------------


def test_wind_chill_family_inherits_parent_position_from_sms_channel_layout(tmp_path):
    """SMS-Kanal-Reihenfolge fuehrt NUR "wind_chill" (Position 0) -- genau
    wie im echten Editor, der die drei Kind-IDs nicht einzeln anbietet. Die
    real ueber loader.py::_append_derived_metrics() angehaengten Kind-Symbole
    (FL/FD/FN) muessen trotzdem VOR W/R stehen, nicht mehr strukturell am
    Ende (Belegtext aus der Meldung: '... TH+:- SU10 FD11/18', FD als
    letztes Token)."""
    metrics = [
        {"metric_id": "wind_chill", "enabled": True, "bucket": "primary", "order": 0},
        {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 1},
        {"metric_id": "precipitation", "enabled": True, "bucket": "primary", "order": 2},
    ]
    _write_trip(tmp_path, "wc-anchor", metrics, channel_layouts={"sms": metrics})

    source, sms = _render_sms(tmp_path, "wc-anchor")
    assert source == "per_channel", (
        f"Vorbedingung: Kanal-Layout-Ebene muss antworten, sonst wird die "
        f"Kaskade gar nicht geprueft (source={source!r})"
    )
    i_w, i_r = _token_index(sms, "W"), _token_index(sms, "R")
    felt_syms = [s for s in ("FL", "FD", "FN") if _has(sms, s)]
    assert felt_syms, f"Vorbedingung: mind. ein gefuehltes Symbol muss stehen: {sms!r}"
    for sym in felt_syms:
        i_felt = _token_index(sms, sym)
        assert i_felt < i_w and i_felt < i_r, (
            f"{sym} (Kind von wind_chill, geerbte Position 0) muss vor W "
            f"und R stehen: {sms!r}"
        )


def _has(sms: str, symbol: str) -> bool:
    try:
        _token_index(sms, symbol)
        return True
    except AssertionError:
        return False


# ---------------------------------------------------------------------------
# Familie 2: temperature (Symbole L/D/N) -- selber Mechanismus, PO-Entscheid:
# beide Familien in einer Scheibe (identischer Codeort).
# ---------------------------------------------------------------------------


def test_temperature_family_inherits_parent_position_from_sms_channel_layout(tmp_path):
    """Gleicher Mechanismus wie oben, jetzt fuer die GEMESSENE Temperatur
    (Symbole N/L/D) -- "temperature" an Position 0 vor wind/precipitation."""
    metrics = [
        {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
        {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 1},
        {"metric_id": "precipitation", "enabled": True, "bucket": "primary", "order": 2},
    ]
    _write_trip(tmp_path, "temp-anchor", metrics, channel_layouts={"sms": metrics})

    source, sms = _render_sms(tmp_path, "temp-anchor")
    assert source == "per_channel", f"Vorbedingung verletzt (source={source!r})"
    i_w, i_r = _token_index(sms, "W"), _token_index(sms, "R")
    temp_syms = [s for s in ("N", "L", "D") if _has(sms, s)]
    assert temp_syms, f"Vorbedingung: mind. ein Temperatur-Symbol muss stehen: {sms!r}"
    for sym in temp_syms:
        i_temp = _token_index(sms, sym)
        assert i_temp < i_w and i_temp < i_r, (
            f"{sym} (Kind von temperature, geerbte Position 0) muss vor W "
            f"und R stehen: {sms!r}"
        )


# ---------------------------------------------------------------------------
# Regressions-Charakterisierung: unbeteiligte Konfiguration bleibt unveraendert
# ---------------------------------------------------------------------------


def test_unrelated_trip_without_derived_families_stays_byte_identical(tmp_path):
    """Ein Trip OHNE wind_chill/temperature (keine abgeleiteten Groessen
    beteiligt) und OHNE SMS-Kanal-Reihenfolge (globaler Fallback) darf durch
    den Fix in keiner Weise veraendert werden -- Referenzstring identisch zum
    eingefrorenen AC-2-String aus test_sms_user_metric_order.py (derselbe
    Fixture-Baustein F.segment(), zeigt: der Fix ist auf die beiden
    betroffenen Familien beschraenkt)."""
    metrics = [
        {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 0},
        {"metric_id": "gust", "enabled": True, "bucket": "primary", "order": 1},
        {"metric_id": "precipitation", "enabled": True, "bucket": "primary", "order": 2},
    ]
    _write_trip(tmp_path, "unrelated", metrics)

    source, sms = _render_sms(tmp_path, "unrelated")
    assert source == "global", f"Vorbedingung verletzt (source={source!r})"
    assert sms == "E7: R0.5@5(8.4@11) W12@4(45@10) G22@4(70@10)", (
        f"Unbeteiligte Konfiguration muss byte-identisch zum eingefrorenen "
        f"Referenzstring bleiben: {sms!r}"
    )
