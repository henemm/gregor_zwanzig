"""
TDD RED: Schneehoehe/Neuschnee als reguläre Metrik im Ortsvergleich (Issue #1105).

Der hardcodierte Metrik-Katalog ``CV2_METRICS`` in
``src/output/renderers/email/compare_html.py`` kennt bislang nur warn,
temp_max, wind_max, sunny_hours, cloud_avg, uv_max -- Schnee (``snow_depth_cm``
"Schneehöhe" und ``snow_new_cm`` "Neuschnee") fehlt komplett, obwohl
``LocationResult`` diese Felder bereits fuehrt (src/app/user.py:157-158).

Diese Tests schlagen ABSICHTLICH fehl (RED), solange die Schnee-Zeilen nicht
existieren. Sie beweisen echtes Renderer-Verhalten -- ``render_compare_html()``
und ``render_comparison_text()`` sind Pure Functions, hier direkt mit echten
``ComparisonResult``/``LocationResult``-Objekten aufgerufen. KEINE Mocks
(CLAUDE.md).

AC-Zuordnung:
- AC-1: enabled_metrics=None -> Uebersichtstabelle zeigt 'Schneehöhe' UND
  'Neuschnee' als Zeilen.
- AC-2 (Guard, bleibt gruen): enabled_metrics ohne Schnee-Keys -> keine
  Schnee-Zeile, aber die gewaehlten Zeilen (+ Warn-Zeile) bleiben sichtbar.
- AC-3: enabled_metrics={'snow_depth_cm'} -> 'Schneehöhe'-Zeile mit dem
  cm-Wert des Schnee-Orts erscheint.
- AC-4: render_comparison_text() enthaelt eine Schnee-Zeile mit demselben
  Wert wie die HTML-Uebersichtstabelle (HTML/Text-Konsistenz).
"""
from __future__ import annotations

import re
from datetime import date, datetime

from app.models import ForecastDataPoint
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult, SavedLocation

# ---------------------------------------------------------------------------
# Test-Fixture: 2 Orte, einer mit Schneedaten, einer ohne (Kontrast fuer '—').
# ---------------------------------------------------------------------------


def _loc(loc_id: str, name: str, elevation_m: int = 200) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=45.9, lon=6.9, elevation_m=elevation_m)


def _dp(hour: int, t2m_c: float) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 8, hour, 0),
        t2m_c=t2m_c,
        wind_chill_c=t2m_c - 2,
        wind10m_kmh=10.0,
        gust_kmh=18.0,
        precip_1h_mm=0.0,
        cloud_total_pct=40,
        uv_index=3.0,
    )


def _make_snow_result() -> ComparisonResult:
    """Chamonix (Schneedaten vorhanden) + Nizza (kein Schnee, Kueste)."""
    chamonix = LocationResult(
        location=_loc("chamonix", "Chamonix", elevation_m=1035),
        score=60,
        snow_depth_cm=45.0,
        snow_new_cm=8.0,
        temp_max=12.0,
        wind_max=18.0,
        sunny_hours=5.0,
        cloud_avg=50,
        official_alerts=[],
        hourly_data=[_dp(9, 8.0), _dp(12, 12.0), _dp(15, 10.0)],
    )
    nizza = LocationResult(
        location=_loc("nizza", "Nizza", elevation_m=10),
        score=55,
        snow_depth_cm=None,
        snow_new_cm=None,
        temp_max=29.0,
        wind_max=15.0,
        sunny_hours=8.0,
        cloud_avg=10,
        official_alerts=[],
        hourly_data=[_dp(9, 24.0), _dp(12, 29.0), _dp(15, 27.0)],
    )
    return ComparisonResult(
        locations=[chamonix, nizza],
        time_window=(9, 16),
        target_date=date(2026, 7, 8),
        created_at=datetime(2026, 7, 8, 4, 1),
    )


# ---------------------------------------------------------------------------
# HTML-Tabellen-Helfer (identisch zu tests/tdd/test_issue_1110_compare_mail_v2.py,
# reine String-/Regex-Analyse des ECHTEN Render-Outputs -- kein Mock)
# ---------------------------------------------------------------------------

_TABLE_RE = re.compile(r"<table[^>]*>.*?</table>", re.DOTALL)


def _tables(html: str) -> list[str]:
    return _TABLE_RE.findall(html)


def _rows(table_html: str) -> list[list[str]]:
    rows = []
    for row_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL):
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_match.group(1), re.DOTALL)
        clean = []
        for c in cells:
            text = re.sub(r"<[^>]+>", " ", c)
            text = re.sub(r"\s+", " ", text).strip()
            clean.append(text)
        rows.append(clean)
    return rows


def _find_overview_table(html: str) -> str:
    """Die Uebersichtstabelle ist die einzige <table>, die die Metrik-Zeile
    'Amtliche Warnungen' enthaelt (Stundentabellen kennen diese Zeile nicht)."""
    for t in _tables(html):
        if "Amtliche Warnungen" in t:
            return t
    return ""


def _overview_labels(html: str) -> list[str]:
    table = _find_overview_table(html)
    assert table, "Uebersichtstabelle nicht gefunden"
    return [row[0] for row in _rows(table) if row]


# ---------------------------------------------------------------------------
# AC-1 -- Schnee-Zeilen erscheinen ohne Filter
# ---------------------------------------------------------------------------


class TestAC1SchneeZeilenOhneFilter:
    def test_ac1_schneehoehe_und_neuschnee_als_uebersichtszeilen(self):
        from output.renderers.email.compare_html import render_compare_html

        result = _make_snow_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN, enabled_metrics=None)

        labels = _overview_labels(html)
        assert any("Schneehöhe" in lbl for lbl in labels), (
            f"'Schneehöhe'-Zeile muss in der Uebersichtstabelle erscheinen (enabled_metrics=None), "
            f"gefundene Zeilen-Labels: {labels}"
        )
        assert any("Neuschnee" in lbl for lbl in labels), (
            f"'Neuschnee'-Zeile muss in der Uebersichtstabelle erscheinen (enabled_metrics=None), "
            f"gefundene Zeilen-Labels: {labels}"
        )


# ---------------------------------------------------------------------------
# AC-2 -- Guard: enabled_metrics ohne Schnee-Keys blendet Schnee weiterhin aus
# ---------------------------------------------------------------------------


class TestAC2GuardEnabledMetricsOhneSchnee:
    def test_ac2_enabled_metrics_ohne_schnee_zeigt_keine_schneezeile(self):
        from output.renderers.email.compare_html import render_compare_html

        result = _make_snow_result()
        html = render_compare_html(
            result, profile=ActivityProfile.ALLGEMEIN, enabled_metrics={"temp_max", "wind_max"},
        )

        labels = _overview_labels(html)
        assert not any("Schneehöhe" in lbl for lbl in labels), (
            f"'Schneehöhe'-Zeile darf NICHT erscheinen, da nicht in enabled_metrics, "
            f"gefundene Zeilen-Labels: {labels}"
        )
        assert not any("Neuschnee" in lbl for lbl in labels), (
            f"'Neuschnee'-Zeile darf NICHT erscheinen, da nicht in enabled_metrics, "
            f"gefundene Zeilen-Labels: {labels}"
        )
        assert any("Amtliche Warnungen" in lbl for lbl in labels), (
            "Warn-Zeile muss unabhaengig von enabled_metrics immer sichtbar sein"
        )
        assert any("Temp max" in lbl for lbl in labels), (
            f"'Temp max'-Zeile muss sichtbar sein (in enabled_metrics enthalten), Labels: {labels}"
        )
        assert any("Wind" in lbl for lbl in labels), (
            f"'Wind'-Zeile muss sichtbar sein (in enabled_metrics enthalten), Labels: {labels}"
        )


# ---------------------------------------------------------------------------
# AC-3 -- gezielte Auswahl von snow_depth_cm zeigt Wert des Schnee-Orts
# ---------------------------------------------------------------------------


class TestAC3SchneehoeheGezieltAusgewaehlt:
    def test_ac3_snow_depth_cm_zeile_zeigt_cm_wert_des_schnee_orts(self):
        from output.renderers.email.compare_html import render_compare_html

        result = _make_snow_result()
        html = render_compare_html(
            result, profile=ActivityProfile.ALLGEMEIN, enabled_metrics={"snow_depth_cm"},
        )

        table = _find_overview_table(html)
        assert table, "Uebersichtstabelle nicht gefunden"
        rows = _rows(table)

        schnee_row = next((r for r in rows if r and "Schneehöhe" in r[0]), None)
        assert schnee_row is not None, (
            f"'Schneehöhe'-Zeile muss erscheinen, wenn enabled_metrics={{'snow_depth_cm'}}, "
            f"gefundene Zeilen: {rows}"
        )

        # Spaltenreihenfolge folgt alphabetischer Ort-Sortierung: Chamonix < Nizza.
        header = rows[0]
        assert header[1:] == ["Chamonix", "Nizza"], (
            f"Spaltenkoepfe muessen alphabetisch sortiert sein, war: {header}"
        )
        assert "45" in schnee_row[1], (
            f"Chamonix-Zelle muss den Schneehoehe-Wert '45' (cm) zeigen, war: {schnee_row[1]!r}"
        )
        assert schnee_row[2] == "—", (
            f"Nizza (kein Schnee) muss exakt '—' in der Schneehoehe-Zeile zeigen, war: {schnee_row[2]!r}"
        )


# ---------------------------------------------------------------------------
# AC-4 -- Klartext-Konsistenz (render_comparison_text)
# ---------------------------------------------------------------------------


class TestAC4KlartextSchneeKonsistenz:
    def test_ac4_klartext_enthaelt_schneehoehe_zeile_mit_wert(self):
        from output.renderers.comparison import render_comparison_text

        result = _make_snow_result()
        text_body = render_comparison_text(result, profile=ActivityProfile.ALLGEMEIN)

        assert "Schneehöhe" in text_body, (
            "Klartext muss eine 'Schneehöhe'-Zeile fuer Chamonix zeigen, "
            f"Text war:\n{text_body}"
        )

        chamonix_idx = text_body.index("Chamonix")
        nizza_idx = text_body.index("Nizza")
        chamonix_section = text_body[chamonix_idx:nizza_idx]
        assert "Schneehöhe" in chamonix_section, (
            f"Die 'Schneehöhe'-Zeile muss im Chamonix-Abschnitt stehen, gefunden: {chamonix_section!r}"
        )
        assert "45" in chamonix_section, (
            f"Chamonix-Abschnitt muss den Schneehoehe-Wert '45' (cm) enthalten, war: {chamonix_section!r}"
        )

    def test_ac4_html_und_klartext_zeigen_denselben_schneehoehe_wert(self):
        """HTML-/Text-Konsistenz: derselbe Zahlenwert (45 cm) fuer Chamonix
        muss in beiden Rendering-Pfaden erscheinen."""
        from output.renderers.comparison import render_comparison_text
        from output.renderers.email.compare_html import render_compare_html

        result = _make_snow_result()
        html = render_compare_html(
            result, profile=ActivityProfile.ALLGEMEIN, enabled_metrics={"snow_depth_cm"},
        )
        text_body = render_comparison_text(result, profile=ActivityProfile.ALLGEMEIN)

        table = _find_overview_table(html)
        assert table, "Uebersichtstabelle nicht gefunden"
        rows = _rows(table)
        schnee_row = next((r for r in rows if r and "Schneehöhe" in r[0]), None)
        assert schnee_row is not None, "'Schneehöhe'-Zeile im HTML nicht gefunden"
        html_value_match = re.search(r"(\d+)", schnee_row[1])
        assert html_value_match, f"Kein numerischer Wert in der HTML-Schneezelle: {schnee_row[1]!r}"

        chamonix_idx = text_body.index("Chamonix")
        nizza_idx = text_body.index("Nizza")
        chamonix_section = text_body[chamonix_idx:nizza_idx]
        text_value_match = re.search(r"Schneehöhe[^\d]*(\d+)", chamonix_section)
        assert text_value_match, (
            f"Kein numerischer Schneehoehe-Wert im Klartext-Abschnitt gefunden: {chamonix_section!r}"
        )

        assert html_value_match.group(1) == text_value_match.group(1) == "45", (
            f"HTML-Wert ({html_value_match.group(1)}) und Text-Wert "
            f"({text_value_match.group(1)}) muessen beide '45' (cm) sein"
        )
