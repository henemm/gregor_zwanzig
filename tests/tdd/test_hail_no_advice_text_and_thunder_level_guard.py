"""TDD RED — Issue #1475 Nachbesserung (Epic #1419), AC-10/AC-11
(Nummerierung nach Spec-Korrektur 2026-08-05, vormals AC-11/AC-12 -- reiner
Docstring-/Kommentar-Fix, keine Logikaenderung):
Mutationsschutz (Hagel beeinflusst `thunder_level_from_signals()` an keiner
der 6 neuen Stellen) UND keine Handlungsempfehlung (ADR-0007) an den neu
ergaenzten Ausgaben.

SPEC: docs/specs/modules/feat_1475_hagel_luecken_nachbesserung.md, AC-10/AC-11.

WICHTIGER HINWEIS zu AC-10 (explizit gemeldet, nicht verschwiegen): dieser
Test ist eine FORTSETZUNG von S5a AC-3 (`tests/tdd/test_hail_flag_wmo_signal.
py::test_ac3_...`) und prueft die bereits PRODUKTIVE, unveraenderte Funktion
`thunder_level_from_signals()`/`_fuse_thunder_levels()` direkt -- keiner der
6 neuen Aufrufer dieser Spec liegt zwischen der App und dieser Funktion.
Der direkte Teil (`test_ac10_...`) ist daher schon HEUTE gruen (Continuity-
Guard, kein neues Feature) -- er bleibt hier NICHT als Verhaltensnachweis
fuer diese Spec, sondern als Regressions-Sicherheitsnetz, das rot werden
MUESSTE, sollte eine der 6 Aenderungen versehentlich `hail_flag` in die
Stufen-Fusion einspeisen.

AC-11 ist echt rot: die Pruefung verlangt ZUGLEICH, dass der Hagel-Hinweis
in der jeweiligen Ausgabe erscheint (was heute an allen Stellen fehlschlaegt,
da die Funktionalitaet noch nicht existiert) UND dass kein Ratschlagswort
vorkommt.

Keine Mocks/patch()/MagicMock.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.metric_catalog import build_default_display_config  # noqa: E402
from app.models import (  # noqa: E402
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)

_TZ = ZoneInfo("Europe/Berlin")
_HAGEL_HINWEIS = "Hagel: ja"
_VERBOTENE_WORTLISTE = ("Schutz suchen", "Vorsicht", "meiden")


# =============================================================================
# AC-10 — Mutationsschutz (Continuity-Guard, s. Hinweis oben)
# =============================================================================

def test_ac10_thunder_level_from_signals_bleibt_unbeeinflusst_von_hail_flag():
    from providers.thunder_enrichment import _fuse_thunder_levels

    ts = datetime.now(timezone.utc)
    ohne_hagel = [ForecastDataPoint(ts=ts, thunder_level=ThunderLevel.LOW, hail_flag=None)]
    mit_hagel = [ForecastDataPoint(ts=ts, thunder_level=ThunderLevel.LOW, hail_flag=True)]

    # Issue #1592 C1: `cape_threshold_jkg` ist Pflichtparameter ohne
    # Default (kein stiller Rueckfall auf der ganzen Kette). `None` hier --
    # keine der beiden Reihen traegt CAPE, die Schwelle spielt fuer diesen
    # Hagel-Mutationsschutz keine Rolle.
    _fuse_thunder_levels(ohne_hagel, None)
    _fuse_thunder_levels(mit_hagel, None)

    assert ohne_hagel[0].thunder_level == mit_hagel[0].thunder_level, (
        f"AC-10: hail_flag darf die Gewitterstufen-Fusion nicht beeinflussen "
        f"-- bekam {mit_hagel[0].thunder_level!r} statt "
        f"{ohne_hagel[0].thunder_level!r}"
    )


# =============================================================================
# AC-11 — kein Ratschlagstext an den neu ergaenzten Ausgaben
# =============================================================================

def _segment_thunder_hail_true() -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=900.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=1500.0),
        start_time=datetime(2026, 8, 5, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 5, 14, 0, tzinfo=timezone.utc),
        duration_hours=6.0, distance_km=10.0, ascent_m=600.0, descent_m=0.0,
    )
    data = [ForecastDataPoint(
        ts=datetime(2026, 8, 5, h, 0, tzinfo=timezone.utc), t2m_c=18.0,
        thunder_level=ThunderLevel.HIGH, hail_flag=True if h == 10 else None,
    ) for h in range(8, 14)]
    ts = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
        data=data,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=14.0, temp_max_c=20.0, thunder_level_max=ThunderLevel.HIGH,
            hail_flag=True,
        ),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _pruefe_kanal(kanal_name: str, text: str) -> None:
    assert _HAGEL_HINWEIS in text, (
        f"AC-11 Vorbedingung: {kanal_name} muss ueberhaupt einen "
        f"Hagel-Hinweis ('{_HAGEL_HINWEIS}') zeigen, sonst ist die "
        f"Ratschlags-Abwesenheit ein Leerbeweis. Text: {text!r}"
    )
    for wort in _VERBOTENE_WORTLISTE:
        assert wort not in text, (
            f"AC-11: {kanal_name} enthaelt Ratschlagstext {wort!r} -- "
            f"ADR-0007 verbietet Handlungsempfehlungen (nur Fakt, kein Rat)"
        )


def test_ac11_compact_summary_kein_ratschlagstext():
    from output.renderers.compact_summary import CompactSummaryFormatter

    dc = build_default_display_config()
    for mc in dc.metrics:
        mc.enabled = mc.metric_id == "thunder"
    seg = _segment_thunder_hail_true()
    text = CompactSummaryFormatter().format_weather_summary(
        summary=seg.aggregated, hourly=seg.timeseries.data, title="Etappe1",
        dc=dc, tz=_TZ,
    )
    _pruefe_kanal("compact_summary (friendly)", text)


def _gewitter_vorschau_abschnitt(plain: str) -> str:
    """Isoliert NUR den 'Gewitter-Vorschau'-Block -- der Klartext traegt
    daneben (S5a, bereits produktiv) einen 'Metriken-Ueberblick'-Pill, der
    fuer die HEUTIGE Etappe ebenfalls 'Hagel: ja' zeigen kann. Ohne Scoping
    wuerde die Vorbedingung durch diesen UNABHAENGIGEN, bereits
    implementierten Ort scheinfaellig erfuellt -- AC-11 muss aber
    ausschliesslich die Mehrtages-Vorschau (+1-Block) pruefen."""
    lines = plain.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if "Gewitter-Vorschau" in ln), None,
    )
    assert start is not None, f"Kein 'Gewitter-Vorschau'-Block gefunden: {plain!r}"
    ende = next(
        (i for i in range(start + 1, len(lines)) if not lines[i].strip()),
        len(lines),
    )
    return "\n".join(lines[start:ende])


def test_ac11_gewitter_vorschau_klartext_kein_ratschlagstext():
    from output.renderers.email.plain import render_plain

    dc = build_default_display_config()
    thunder_forecast = {
        "+1": {
            "date": "06.08.2026", "level": ThunderLevel.HIGH,
            "text": "Starkes Gewitter erwartet ab 14:00", "hour": 14,
            "hail": True,
        },
    }
    plain = render_plain(
        segments=[_segment_thunder_hail_true()], seg_tables=[[]],
        trip_name="Vorschau-Test", report_type="evening", dc=dc, night_rows=[],
        night_weather=None, changes=None, stage_name="Etappe1", stage_stats=None,
        multi_day_trend=None, compact_summary=None, tz=_TZ, friendly_keys=set(),
        thunder_forecast=thunder_forecast,
    )
    abschnitt = _gewitter_vorschau_abschnitt(plain)
    _pruefe_kanal("Gewitter-Vorschau (Klartext, +1-Block)", abschnitt)


def test_ac11_ortsvergleich_klartext_kein_ratschlagstext():
    from app.user import ComparisonResult, LocationResult, SavedLocation
    from output.renderers.comparison import render_comparison_text

    hourly = [ForecastDataPoint(
        ts=datetime(2026, 8, 6, h, 0, tzinfo=timezone.utc), t2m_c=20.0,
        thunder_level=ThunderLevel.HIGH, hail_flag=True if h == 14 else None,
    ) for h in range(12, 16)]
    loc = LocationResult(
        location=SavedLocation(id="hagel-ort", name="Hagelort", lat=42.0, lon=9.0, elevation_m=1200),
        score=50, hourly_data=hourly,
    )
    result = ComparisonResult(
        locations=[loc], time_window=(12, 16), target_date=datetime(2026, 8, 6).date(),
        created_at=datetime(2026, 8, 5, 18, 0),
    )
    text = render_comparison_text(result, enabled_metrics=["thunder_max"])
    _pruefe_kanal("Ortsvergleich (Klartext)", text)
