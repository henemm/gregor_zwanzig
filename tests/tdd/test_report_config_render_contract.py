"""Issue #1208 (Scheibe A von #1203) — Vertragstest: report_config → gerenderter Output.

Spec: docs/specs/modules/report_config_resolver.md

Beweist auf Ebene der ECHTEN Zuleitung (TripReportFormatter.format_email, nicht
Renderer direkt), dass JEDES Feld von TripReportConfig entweder
  (a) den gerenderten Output veraendert (render-wirksam), oder
  (b) explizit und begruendet in RENDER_NEUTRAL deklariert ist.
Ein wirkungsloses, nicht deklariertes Feld — auch jedes kuenftig NEUE Feld —
laesst den Test mit dem Feldnamen fehlschlagen (AC-2).

AC-4: Der Resolver-Fallback in format_email (render_options=None) liefert
identisches Rendering wie der explizite render_options-Pfad.

KEINE Mocks/patch/MagicMock — echte format_email-Aufrufe mit Segment-Fabrik
nach Vorbild tests/tdd/test_issue_811_mode_matrix.py.

RED-Phase: src/services/report_config_resolver.py existiert noch nicht →
Klassifikations-/Effekt-Tests schlagen mit ModuleNotFoundError fehl;
test_email_format_compact_reaches_render schlaegt als echter #1102-Repro fehl.
"""
from __future__ import annotations

import dataclasses
import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

_TZ = ZoneInfo("Europe/Berlin")
_REPORT_TYPE = "evening"

# Felder, deren Aenderung den Output aendern MUSS (Quelle: Spec v1.1, 7 Felder).
# PO-Entscheidung 2026-07-10 (GREEN-Review): show_daylight entfernt —
# Tageslicht-Block seit #790 aus render_html/render_plain entfernt, Toggle
# strukturell wirkungslos, jetzt RENDER_NEUTRAL (siehe Spec v1.1).
_RENDER_EFFECTIVE_EXPECTED = {
    "email_format",
    "show_outlook",
    "show_stage_stats",
    "show_stability",
    "show_compact_summary",
    "multi_day_trend_reports",
    "show_yesterday_comparison",
}


# ---------------------------------------------------------------------------
# Fabriken — echte Domaenen-Objekte (Vorbild test_issue_811_mode_matrix.py)
# ---------------------------------------------------------------------------

def _make_dp():
    from app.models import ForecastDataPoint, ThunderLevel
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=22.0, wind10m_kmh=55.0, gust_kmh=85.0, precip_1h_mm=8.0,
        pop_pct=80, cloud_total_pct=85, thunder_level=ThunderLevel.MED,
        wind_chill_c=20.0, cape_jkg=1500.0, visibility_m=15000.0,
    )


def _make_dc():
    from app.metric_catalog import build_default_display_config
    return build_default_display_config()


def _make_seg_data():
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
    dp = _make_dp()
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[dp])
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=24.0, temp_avg_c=19.0,
        wind_max_kmh=55.0, gust_max_kmh=85.0, precip_sum_mm=8.0,
        cloud_avg_pct=85, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.MED, wind_chill_min_c=20.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime(2026, 7, 11, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _stability():
    from app.models import StabilityResult
    return StabilityResult(label="WECHSELHAFT", confidence_pct=60)


def _trend():
    """Trend-Stage-dict wie vom Scheduler gebaut (Vorbild test_issue_721)."""
    return [dict(
        weekday="Sa", name="Folge-Etappe",
        temp_lo=12, temp_hi=18,
        precip_mm=2.5, wind_dir="W", wind_kmh=25, thunder="NONE", note=None,
        hourly_precip=(), hourly_wind=(), hourly_gust=(), hourly_thunder=(),
    )]


def _day_comparison():
    from services.day_comparison import DayComparison
    return DayComparison(
        wind_delta_kmh=15.0, gust_delta_kmh=20.0, precip_delta_mm=5.0,
        summary="Deutlich windiger als gestern",
    )


_STATS = {"distance_km": 9.3, "ascent_m": 1600.0, "descent_m": 0.0,
          "max_elevation_m": 1200}


# ---------------------------------------------------------------------------
# Render-Harness: ECHTER format_email-Aufruf ueber die Zuleitung
# ---------------------------------------------------------------------------

def _resolve(cfg, dc):
    """Resolver aufrufen — existiert in der RED-Phase noch nicht."""
    from src.services.report_config_resolver import resolve_report_render_options
    return resolve_report_render_options(cfg, dc, _REPORT_TYPE)


def _scheduler_gated_kwargs(options) -> dict:
    """Bildet die Scheduler-Gates nach, die VOR format_email liegen.

    show_multi_day_trend gatet heute im Scheduler, ob der Input ueberhaupt
    berechnet wird — der Test speist ihn exakt so ein, wie es der Scheduler
    anhand der Options tut. Issue #1224: das ehemalige show_daylight-Gate
    entfaellt (Feld aus ReportRenderOptions entfernt).
    """
    return dict(
        multi_day_trend=_trend() if options.show_multi_day_trend else None,
    )


def _format_email(cfg, *, render_options=None, gated_kwargs=None):
    """Ruft TripReportFormatter.format_email ueber die echte Zuleitung auf."""
    from src.output.renderers.trip_report import TripReportFormatter
    dc = _make_dc()
    kwargs = dict(
        segments=[_make_seg_data()],
        trip_name="Contract-Test",
        report_type=_REPORT_TYPE,
        display_config=dc,
        stage_name="Etappe 1",
        stage_stats=_STATS,
        stability_result=_stability(),
        day_comparison=_day_comparison(),
        tz=_TZ,
        report_config=cfg,
        stage_total=3,
    )
    if gated_kwargs is None:
        gated_kwargs = dict(multi_day_trend=_trend())
    kwargs.update(gated_kwargs)
    if render_options is not None:
        kwargs["render_options"] = render_options
    return TripReportFormatter().format_email(**kwargs)


_HHMM = re.compile(r"\b\d{1,2}:\d{2}\b")
_DATE = re.compile(r"\b\d{1,2}\.\d{1,2}\.(\d{4})?\b")


def _normalize(text: str) -> str:
    """Neutralisiert wall-clock-abhaengige Teile (sent_at-Label u. ae.).

    Struktur-Unterschiede durch Toggles bleiben sichtbar (Sektionen,
    Labels, Tabellen) — nur Uhrzeit-/Datums-LITERALE werden maskiert.
    """
    return _DATE.sub("D.D.", _HHMM.sub("HH:MM", text))


def _render_normalized(cfg, *, use_resolver_gates: bool) -> tuple[str, str]:
    if use_resolver_gates:
        options = _resolve(cfg, _make_dc())
        gated = _scheduler_gated_kwargs(options)
    else:
        gated = None
    report = _format_email(cfg, gated_kwargs=gated)
    return _normalize(report.email_html), _normalize(report.email_plain)


# ---------------------------------------------------------------------------
# Feld-Mutationen: pro Feld ein vom Default abweichender, typrichtiger Wert
# ---------------------------------------------------------------------------

def _mutate(field: dataclasses.Field, default_value):
    """Erzeugt einen garantiert abweichenden, typrichtigen Wert."""
    if field.name == "email_format":
        return "compact" if default_value != "compact" else "full"
    if field.name == "multi_day_trend_reports":
        return [] if default_value else [_REPORT_TYPE]
    if isinstance(default_value, bool):
        return not default_value
    if isinstance(default_value, float):
        return default_value + 1.0
    if isinstance(default_value, int):
        return default_value + 1
    if isinstance(default_value, str):
        return default_value + "-x"
    if isinstance(default_value, list):
        return [] if default_value else ["probe"]
    if isinstance(default_value, time):
        return time((default_value.hour + 1) % 24, default_value.minute)
    if isinstance(default_value, datetime):
        return default_value + timedelta(days=1)
    if default_value is None:
        # Optional[...] — konkreten Wert je Feldname setzen
        if field.name == "paused_until":
            return datetime(2027, 1, 1, tzinfo=timezone.utc)
        return 1234.0
    raise AssertionError(
        f"AC-2: Kein Mutations-Rezept fuer Feld {field.name!r} "
        f"(Typ {type(default_value).__name__}) — neues Feld MUSS hier und im "
        f"Resolver klassifiziert werden."
    )


def _all_fields():
    from app.models import TripReportConfig
    return list(dataclasses.fields(TripReportConfig))


def _default_cfg():
    from app.models import TripReportConfig
    return TripReportConfig(trip_id="contract-test")


# ---------------------------------------------------------------------------
# AC-2a: Klassifikations-Vollstaendigkeit — jedes Feld genau einmal deklariert
# ---------------------------------------------------------------------------

class TestFieldClassification:

    def test_every_field_is_classified(self):
        """Jedes TripReportConfig-Feld ist ENTWEDER render-wirksam ODER
        namentlich in RENDER_NEUTRAL — sonst rot mit Feldname (AC-2)."""
        from src.services.report_config_resolver import (
            RENDER_EFFECTIVE_FIELDS, RENDER_NEUTRAL,
        )
        all_names = {f.name for f in _all_fields()}
        effective = set(RENDER_EFFECTIVE_FIELDS)
        neutral = set(RENDER_NEUTRAL)
        unclassified = all_names - effective - neutral
        assert not unclassified, (
            f"AC-2: Nicht klassifizierte report_config-Felder (weder "
            f"render-wirksam noch RENDER_NEUTRAL): {sorted(unclassified)!r}"
        )
        double = effective & neutral
        assert not double, f"Doppelt klassifiziert: {sorted(double)!r}"
        stale = (effective | neutral) - all_names
        assert not stale, (
            f"Deklarierte Felder existieren nicht (mehr) in TripReportConfig: "
            f"{sorted(stale)!r}"
        )

    def test_expected_effective_set(self):
        """Die 8 render-wirksamen Felder entsprechen der freigegebenen Spec."""
        from src.services.report_config_resolver import RENDER_EFFECTIVE_FIELDS
        assert set(RENDER_EFFECTIVE_FIELDS) == _RENDER_EFFECTIVE_EXPECTED

    def test_render_neutral_has_reasons(self):
        """RENDER_NEUTRAL ist ein Mapping Feldname → nicht-leere Begruendung."""
        from src.services.report_config_resolver import RENDER_NEUTRAL
        for name, reason in RENDER_NEUTRAL.items():
            assert isinstance(reason, str) and len(reason.strip()) >= 10, (
                f"RENDER_NEUTRAL[{name!r}] braucht eine echte Begruendung, "
                f"war: {reason!r}"
            )


# ---------------------------------------------------------------------------
# AC-2b: Effekt-Nachweis — render-wirksame Felder aendern den Output
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field_name", sorted(_RENDER_EFFECTIVE_EXPECTED))
def test_effective_field_changes_output(field_name):
    """Given Default-Config / When genau EIN render-wirksames Feld abweicht /
    Then unterscheidet sich der normalisierte format_email-Output (AC-2)."""
    fields_by_name = {f.name: f for f in _all_fields()}
    cfg_base = _default_cfg()
    fld = fields_by_name[field_name]
    mutated_value = _mutate(fld, getattr(cfg_base, field_name))
    cfg_mut = dataclasses.replace(cfg_base, **{field_name: mutated_value})

    out_base = _render_normalized(cfg_base, use_resolver_gates=True)
    out_mut = _render_normalized(cfg_mut, use_resolver_gates=True)
    assert out_base != out_mut, (
        f"AC-2: Feld {field_name!r} ({getattr(cfg_base, field_name)!r} → "
        f"{mutated_value!r}) hat den gerenderten Output NICHT veraendert — "
        f"Einstellung gespeichert, aber wirkungslos (#1102-Klasse)."
    )


# ---------------------------------------------------------------------------
# #1102-Repro (Kern-Proxy zu AC-1): email_format=compact kommt in der
# Zuleitung an — kein HTML-Body, Plain-Compact-Text
# ---------------------------------------------------------------------------

def test_email_format_compact_reaches_render():
    """Given report_config.email_format='compact' / When format_email ueber die
    echte Zuleitung rendert / Then entsteht KEIN HTML-Body (compact = ("",
    text)) — heute rot, weil format_email email_format nie durchreicht (#1102).
    """
    cfg = dataclasses.replace(_default_cfg(), email_format="compact")
    report = _format_email(cfg)
    assert report.email_html == "", (
        "#1102: email_format='compact' wurde von format_email ignoriert — "
        f"HTML-Body ist {len(report.email_html)} Zeichen statt leer. "
        "Der Versand wuerde X-GZ-Format: full statt compact tragen."
    )
    assert report.email_plain.strip(), "compact muss Plain-Text liefern"


# ---------------------------------------------------------------------------
# AC-4: Resolver-Fallback in format_email == expliziter render_options-Pfad
# ---------------------------------------------------------------------------

def test_fallback_equals_explicit_options_default_cfg():
    """Given Default-Trip / When einmal ohne und einmal mit explizit
    aufgeloesten render_options gerendert wird / Then sind beide Ergebnisse
    identisch (AC-4 — kein Regressions-Nebeneffekt durch den Umbau)."""
    cfg = _default_cfg()
    options = _resolve(cfg, _make_dc())
    report_fallback = _format_email(cfg)
    report_explicit = _format_email(cfg, render_options=options)
    assert _normalize(report_fallback.email_html) == _normalize(report_explicit.email_html)
    assert _normalize(report_fallback.email_plain) == _normalize(report_explicit.email_plain)
    assert report_fallback.email_subject == report_explicit.email_subject


def test_resolver_is_pure_and_frozen():
    """ReportRenderOptions ist frozen (immutable) — kein Patch-Hack mehr
    moeglich; Resolver mutiert die Eingaben nicht."""
    cfg = _default_cfg()
    dc = _make_dc()
    dc_before = dataclasses.asdict(dc) if dataclasses.is_dataclass(dc) else None
    options = _resolve(cfg, dc)
    with pytest.raises(dataclasses.FrozenInstanceError):
        options.email_format = "compact"  # type: ignore[misc]
    if dc_before is not None:
        assert dataclasses.asdict(dc) == dc_before, (
            "Resolver darf display_config nicht mutieren (Ersatz des "
            "Patch-Hacks aus trip_report_scheduler.py:779)"
        )
