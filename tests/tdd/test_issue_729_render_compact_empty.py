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

class TestAC3NonEmptyUnchanged:
    def test_non_empty_compact_still_renders_full_sections(self):
        """Given eine reguläre nicht-leere compact-Mail (über den #722-Pfad) / When
        gerendert / Then enthält der Body weiterhin Metriken-Überblick, Ausblick und
        Provider-Footer (der Guard greift NICHT, regulärer Pfad unverändert)."""
        from tests.tdd.test_issue_722_email_compact import _render_email
        _html, plain = _render_email("compact")
        assert plain.isascii(), "compact-Body muss ASCII bleiben"
        assert "Metriken" in plain, "Metriken-Überblick fehlt — regulärer Pfad beschädigt"
        assert "Naechste Etappen" in plain, "Ausblick fehlt — regulärer Pfad beschädigt"
        assert "Data:" in plain, "Provider-Footer fehlt — regulärer Pfad beschädigt"
