"""TDD RED — Issue #954 Bug B: SMS-Vorschau divergiert vom echten Versand.

SPEC: docs/specs/modules/fix_954_metric_gating_footer_preview.md (AC-3).

`render_sms_preview()` baut seinen Token-Text über einen eigenen, redundanten
`SMSTripFormatter().format_sms(...)`-Aufruf OHNE `disabled_specs` — im Gegensatz zum
echten Versandpfad (`trip_report.py`, #944-Fix), der `disabled_specs` aus den aktiven
Metriken ableitet. Das `report`-Objekt, das `_build_report()` bereits erzeugt, trägt
ein korrektes `report.sms_text`. `render_sms_preview()` soll dieses Feld zurückgeben.

Setup: Trip mit einer `display_config` OHNE `thunder`-Metrik. Dadurch unterdrückt der
echte Versand (report.sms_text) den `TH:`-Token, die Vorschau (ohne disabled_specs)
zeigt ihn aber — die Vorschau lügt den Nutzer an.

RED-Zustand (jetzt):
  - `render_sms_preview()` liefert einen Token-Text, der `TH:` enthält und sich von
    `report.sms_text` unterscheidet → AssertionError.
GREEN-Zustand (nach Fix):
  - `render_sms_preview()` gibt exakt `report.sms_text` zurück (kein `TH:`).

KEINE Mocks. Echter Trip via save_trip, echter FixtureProvider (demo=True),
echter Renderpfad.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.loader import save_trip
from app.trip import Stage, TimeWindow, Trip, Waypoint

_USER = "tdd-954-sms-preview"
_TRIP_ID = "tdd-954-sms-trip"
# Morgen liegt sicher im 72h-Fenster des FixtureProviders (Anker: heute 00:00 UTC).
_TARGET = date.today() + timedelta(days=1)


def _make_dc_without_thunder():
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    # Bewusst OHNE thunder — precipitation/wind haben SMS-Symbole (R/W),
    # thunder (TH:) ist damit deaktiviert.
    metric_ids = ["temperature", "precipitation", "wind"]
    metrics = [
        MetricConfig(metric_id=mid, enabled=True, bucket="primary", order=idx)
        for idx, mid in enumerate(metric_ids)
    ]
    return UnifiedWeatherDisplayConfig(
        trip_id=_TRIP_ID, metrics=metrics,
        updated_at=datetime.now(timezone.utc),
    )


def _make_and_save_trip() -> None:
    """Trip nahe Innsbruck (FixtureProvider-Standort) mit display_config ohne
    thunder-Metrik persistieren."""
    coords = [(47.2692, 11.4041), (47.2820, 11.4230), (47.2950, 11.4420)]
    waypoints = [
        Waypoint(
            id=f"G{i + 1}",
            name="Start" if i == 0 else ("Ziel" if i == len(coords) - 1 else f"Seg {i + 1}"),
            lat=lat, lon=lon, elevation_m=600,
            time_window=TimeWindow(start=time(9, 0), end=time(9, 0)),
        )
        for i, (lat, lon) in enumerate(coords)
    ]
    stage = Stage(id="T1", name="954-Etappe", date=_TARGET,
                  start_time=time(9, 0), waypoints=waypoints)
    trip = Trip(
        id=_TRIP_ID, name="TDD 954 SMS-Vorschau", stages=[stage],
        display_config=_make_dc_without_thunder(),
    )
    save_trip(trip, user_id=_USER)


def _render() -> tuple[str, str]:
    """Liefert (token_line aus render_sms_preview, report.sms_text aus _build_report)."""
    from services.preview_service import PreviewService

    _make_and_save_trip()
    ps = PreviewService()
    trip = ps._load_trip(_TRIP_ID, user_id=_USER)
    report, *_rest = ps._build_report(trip, _TARGET, "morning", demo=True)
    _subject, token_line = ps.render_sms_preview(
        _TRIP_ID, user_id=_USER, report_type="morning",
        target_date=_TARGET.isoformat(), demo=True,
    )
    return token_line, report.sms_text


def test_sms_preview_token_line_equals_report_sms_text():
    """AC-3: Der von render_sms_preview zurückgegebene Token-Text ist identisch
    mit report.sms_text (dem echten Versand-Text) — kein zweiter divergenter
    Renderpfad mehr."""
    token_line, sms_text = _render()
    assert token_line == sms_text, (
        "SMS-Vorschau divergiert vom echten Versand-Text (report.sms_text):\n"
        f"  Vorschau:  {token_line!r}\n"
        f"  Versand:   {sms_text!r}"
    )


def test_sms_preview_omits_thunder_token_when_thunder_disabled():
    """AC-3: Bei deaktivierter thunder-Metrik enthält der Vorschau-Token-Text
    keinen TH:-Token (wie der echte Versand dank #944-disabled_specs)."""
    token_line, _sms_text = _render()
    assert "TH:" not in token_line, (
        f"SMS-Vorschau zeigt TH:-Token trotz deaktivierter thunder-Metrik:\n{token_line!r}"
    )
