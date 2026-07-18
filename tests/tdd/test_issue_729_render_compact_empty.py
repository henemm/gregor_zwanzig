"""
TDD tests für Issue #729 — render_compact(segments=[]) defensiver Guard.

`render_compact` greift `segments[0]` ohne Leer-Prüfung → bei leerer Segment-Liste
`IndexError`. Defensiver Guard soll einen minimalen ASCII-Body statt Exception liefern;
der reguläre Nicht-Leer-Pfad bleibt unverändert (keine #722-Regression).

RED-Phase: AC-1/AC-2 schlagen fehl (IndexError), bis der Guard ergänzt ist.

SPEC: docs/specs/modules/issue_729_render_compact_empty_guard.md AC-1..AC-3
IMPORTANT: KEINE Mocks, KEIN patch, KEIN MagicMock. Nur echte Funktionsaufrufe mit
echten Domänen-Objekten. Kein Dateiinhalt-Check — geprüft wird der gerenderte Output.
"""
from __future__ import annotations

from zoneinfo import ZoneInfo

from app.models import UnifiedWeatherDisplayConfig
from src.output.renderers.email.compact import render_compact


_TZ = ZoneInfo("Europe/Berlin")


def _empty_kwargs(trip_name="GR20", report_type="evening"):
    """Gültige render_compact-Parameter mit leerer Segment-Liste — echte Objekte."""
    return dict(
        segments=[],
        dc=UnifiedWeatherDisplayConfig(trip_id="test", metrics=[]),
        multi_day_trend=None,
        stability_result=None,
        tz=_TZ,
        report_type=report_type,
        trip_name=trip_name,
        stage_name=None,
        stage_stats=None,
        profile=None,
    )


# ---------------------------------------------------------------------------
# AC-1: leere Segmente → keine Exception, String-Rückgabe
# ---------------------------------------------------------------------------

class TestAC1NoIndexError:
    def test_empty_segments_does_not_raise(self):
        """Given segments=[] / When render_compact aufgerufen / Then keine Exception,
        sondern ein String."""
        body = render_compact(**_empty_kwargs())
        assert isinstance(body, str), "render_compact muss bei leeren Segmenten einen String liefern"


# ---------------------------------------------------------------------------
# AC-2: leere Segmente → minimaler, nicht-leerer ASCII-Body mit Kopfzeile
# ---------------------------------------------------------------------------

class TestAC2MinimalAsciiBody:
    def test_empty_segments_body_is_ascii_and_has_header(self):
        """Given segments=[] / When gerendert / Then Body ist reines ASCII, nicht leer
        und enthält Trip-Name + Report-Typ in der Kopfzeile."""
        body = render_compact(**_empty_kwargs(trip_name="GR20", report_type="evening"))
        assert body.strip(), "Body darf nicht leer sein"
        assert body.isascii(), f"Body muss reines ASCII sein: {body!r}"
        assert "GR20" in body, "Trip-Name muss in der Kopfzeile stehen"
        assert "Evening" in body, "Report-Typ (Title-Case) muss in der Kopfzeile stehen"


# ---------------------------------------------------------------------------
# AC-3: Nicht-Leer-Pfad bleibt intakt (keine #722-Regression)
# ---------------------------------------------------------------------------

# Helfer inline uebernommen aus geloeschtem test_issue_722_email_compact.py (#1211-2b Batch 1)
def _trend_stage(weekday="Mi", name="Etappe 4", temp_lo=12, temp_hi=18,
                 precip_mm=3.0, wind_dir="W", wind_kmh=20, thunder="NONE",
                 confidence_pct=70):
    return dict(
        weekday=weekday, name=name, temp_lo=temp_lo, temp_hi=temp_hi,
        precip_mm=precip_mm, wind_dir=wind_dir, wind_kmh=wind_kmh,
        thunder=thunder, note=None,
        hourly_precip=(), hourly_wind=(), hourly_gust=(), hourly_thunder=(),
        confidence_pct=confidence_pct,
    )


def _stability(label="WECHSELHAFT", confidence_pct=70):
    from app.models import StabilityResult
    return StabilityResult(label=label, confidence_pct=confidence_pct)


def _hourly_seg_tables():
    """Echte Stunden-Zeilen, damit der Unterschied full (zeigt 08:00) vs.
    compact (zeigt 08:00 NICHT) beobachtbar wird."""
    return [[
        {"time": "08:00", "temperature": 14.0, "wind_kmh": 20.0},
        {"time": "09:00", "temperature": 16.0, "wind_kmh": 22.0},
    ]]


def _render_email(email_format, *, show_highlights=True,
                  daily_summary_metrics=None, seg_tables=None):
    """Ruft render_email mit dem email_format-Parameter auf."""
    from src.output.renderers.email import render_email
    from tests.unit.test_renderers_email import _common_kwargs, _make_token_line
    kw = _common_kwargs()
    kw["seg_tables"] = seg_tables if seg_tables is not None else _hourly_seg_tables()
    kw["multi_day_trend"] = [_trend_stage(name="Etappe 4"),
                             _trend_stage(weekday="Do", name="Etappe 5",
                                          thunder="HIGH", confidence_pct=45)]
    kw["highlights"] = ["Wind moderat erwartet"]
    return render_email(
        _make_token_line(),
        **kw,
        stability_result=_stability("WECHSELHAFT", 45),
        show_highlights=show_highlights,
        daily_summary_metrics=daily_summary_metrics,
        email_format=email_format,
    )


class TestAC3NonEmptyUnchanged:
    def test_non_empty_compact_still_renders_full_sections(self):
        """Given eine reguläre nicht-leere compact-Mail (über den #722-Pfad) / When
        gerendert / Then enthält der Body weiterhin Metriken-Überblick, Ausblick und
        Provider-Footer (der Guard greift NICHT, regulärer Pfad unverändert)."""
        _html, plain = _render_email("compact")
        assert plain.isascii(), "compact-Body muss ASCII bleiben"
        assert "Metriken" in plain, "Metriken-Überblick fehlt — regulärer Pfad beschädigt"
        assert "Naechste Etappen" in plain, "Ausblick fehlt — regulärer Pfad beschädigt"
        assert "Data:" in plain, "Provider-Footer fehlt — regulärer Pfad beschädigt"
