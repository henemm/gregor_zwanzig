"""
TDD RED: Tests fuer Ortsvergleich-Mail v2 (Issue #1110).

SPEC: docs/specs/modules/issue_1110_compare_mail_v2.md

Diese Tests schlagen ABSICHTLICH fehl, weil `render_compare_html()` /
`render_comparison_text()` / `email_spec_validator.py` noch den alten
Score/Winner-Vertrag implementieren. Nach der Implementierung (/5-implement)
muss jeder Test gruen sein.

Mocks sind in diesem Projekt VERBOTEN (CLAUDE.md). Alle Assertions pruefen
den gerenderten Output echter Render-Funktionen (Pure Functions) -- kein
Dateiinhalt-Check am Quellcode.

Klassen:
- TestCompareMailV2HTML       -- AC-1 bis AC-8, render_compare_html()
- TestCompareMailV2Validator  -- AC-9, email_spec_validator.py als Modul
- TestCompareMailV2Text       -- AC-10, render_comparison_text() via render_compare_email()
"""
from __future__ import annotations

import importlib.util
import re
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

from app.models import ForecastDataPoint
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult, SavedLocation
from services.official_alerts import OfficialAlert

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"


# ---------------------------------------------------------------------------
# Test-Daten: 3 Orte analog docs/design-requests/compare_mail_v2/screen-compare-email-v2.jsx
# ---------------------------------------------------------------------------

def _loc(loc_id: str, name: str, elevation_m: int = 200) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=43.1, lon=6.2, elevation_m=elevation_m)


def _dp(hour, t2m_c, wind_chill_c, wind10m_kmh, gust_kmh, precip_1h_mm, cloud_total_pct, uv_index):
    return ForecastDataPoint(
        ts=datetime(2026, 7, 8, hour, 0),
        t2m_c=t2m_c,
        wind_chill_c=wind_chill_c,
        wind10m_kmh=wind10m_kmh,
        gust_kmh=gust_kmh,
        precip_1h_mm=precip_1h_mm,
        cloud_total_pct=cloud_total_pct,
        uv_index=uv_index,
    )


def _make_v2_result() -> ComparisonResult:
    """3 Orte, Preset-Reihenfolge Collobrières -> Marseille -> Fréjus.

    - Collobrières: 2 amtliche Warnungen (Hitze + Zugang), Danger-Temp (34 Grad)
      um 12:00 Uhr, wind_chill_c=None um 09:00 Uhr.
    - Marseille: 1 amtliche Warnung (Waldbrand Stufe 4), Wind > 40 km/h um 12:00 Uhr.
    - Fréjus: keine amtlichen Warnungen (alert-frei), guenstigste Sonne-/Wolken-Werte.
    """
    collobrieres = LocationResult(
        location=_loc("collobrieres", "Collobrières"),
        score=70,
        temp_max=34.0,
        wind_max=13.0,
        sunny_hours=6.5,
        cloud_avg=70,
        official_alerts=[
            OfficialAlert(
                source="meteofrance_vigilance", hazard="extreme_heat",
                level=3, label="Extreme Hitze",
            ),
            OfficialAlert(
                source="massif_closure", hazard="access_ban",
                level=3, label="Zugang eingeschränkt — Maures",
            ),
        ],
        hourly_data=[
            _dp(9, 27.0, None, 8.0, 16.0, 0.0, 40, 2.0),
            _dp(10, 30.0, 32.0, 10.0, 20.0, 0.0, 55, 4.0),
            _dp(11, 32.0, 34.0, 12.0, 24.0, 0.0, 60, 6.0),
            _dp(12, 34.0, 36.0, 13.0, 26.0, 0.0, 70, 8.0),
            _dp(13, 33.0, 35.0, 13.0, 26.0, 0.0, 80, 6.0),
            _dp(14, 32.0, 34.0, 12.0, 24.0, 0.2, 100, 4.0),
            _dp(15, 30.0, 32.0, 10.0, 20.0, 0.0, 90, 2.0),
            _dp(16, 28.0, 30.0, 8.0, 16.0, 0.0, 100, 1.0),
        ],
    )
    marseille = LocationResult(
        location=_loc("marseille", "Marseille"),
        score=55,
        temp_max=32.0,
        wind_max=45.0,
        sunny_hours=5.0,
        cloud_avg=85,
        official_alerts=[
            OfficialAlert(
                source="meteo_forets", hazard="wildfire_risk",
                level=4, label="Waldbrand-Gefahr — Stufe 4",
            ),
        ],
        hourly_data=[
            _dp(9, 28.0, 30.0, 28.0, 50.0, 0.0, 60, 2.0),
            _dp(10, 30.0, 32.0, 32.0, 56.0, 0.0, 70, 4.0),
            _dp(11, 31.0, 33.0, 35.0, 62.0, 0.0, 80, 6.0),
            _dp(12, 32.0, 34.0, 41.0, 64.0, 0.0, 85, 7.0),
            _dp(13, 32.0, 34.0, 33.0, 60.0, 0.0, 89, 5.0),
            _dp(14, 31.0, 33.0, 30.0, 56.0, 0.1, 100, 3.0),
            _dp(15, 30.0, 32.0, 28.0, 52.0, 0.0, 95, 2.0),
            _dp(16, 29.0, 31.0, 24.0, 46.0, 0.0, 100, 1.0),
        ],
    )
    frejus = LocationResult(
        location=_loc("frejus", "Fréjus"),
        score=60,
        temp_max=29.0,
        wind_max=23.0,
        sunny_hours=7.5,
        cloud_avg=20,
        official_alerts=[],
        hourly_data=[
            _dp(9, 25.0, 26.0, 8.0, 16.0, 0.0, 20, 2.0),
            _dp(10, 26.0, 27.0, 10.0, 20.0, 0.0, 18, 4.0),
            _dp(11, 27.0, 28.0, 11.0, 22.0, 0.0, 15, 6.0),
            _dp(12, 28.0, 29.0, 12.0, 24.0, 0.0, 12, 7.0),
            _dp(13, 27.0, 28.0, 12.0, 24.0, 0.0, 10, 5.0),
            _dp(14, 26.0, 27.0, 11.0, 22.0, 0.0, 20, 3.0),
            _dp(15, 25.0, 26.0, 10.0, 20.0, 0.0, 25, 2.0),
            _dp(16, 24.0, 25.0, 8.0, 16.0, 0.0, 30, 1.0),
        ],
    )
    return ComparisonResult(
        locations=[collobrieres, marseille, frejus],
        time_window=(9, 16),
        target_date=date(2026, 7, 8),
        created_at=datetime(2026, 7, 8, 4, 1),
    )


# ---------------------------------------------------------------------------
# Generische HTML-Tabellen-Helfer (kein Mock -- reine String-/Regex-Analyse
# des ECHTEN Render-Outputs, analog email_spec_validator.py::extract_table_rows)
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


def _rows_raw(table_html: str) -> list[list[str]]:
    """Wie _rows(), aber Zellen bleiben als rohes <td ...>...</td>-HTML erhalten
    (fuer Style-/Hintergrundfarben-Pruefungen)."""
    rows = []
    for row_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL):
        rows.append(re.findall(r"<t[hd][^>]*>.*?</t[hd]>", row_match.group(1), re.DOTALL))
    return rows


def _find_overview_table(html: str) -> str:
    """Die Uebersichtstabelle ist die einzige <table>, die die Metrik-Zeile
    'Amtliche Warnungen' enthaelt (Stundentabellen kennen diese Zeile nicht)."""
    for t in _tables(html):
        if "Amtliche Warnungen" in t:
            return t
    return ""


def _zeit_positions(html: str) -> list[int]:
    return [m.start() for m in re.finditer(r">Zeit<", html)]


def _location_hour_table(html: str, loc_index: int, loc_count: int) -> str:
    """Extrahiert die vollstaendige Stundentabelle des loc_index-ten Ortes ueber
    die Position seines 'Zeit'-Spaltenkopfs (ein 'Zeit'-Header je Ort-Stundentabelle,
    in Preset-Reihenfolge)."""
    positions = _zeit_positions(html)
    assert len(positions) == loc_count, (
        f"Erwarte {loc_count} Stundentabellen (ein 'Zeit'-Header je Ort), "
        f"gefunden: {len(positions)}"
    )
    pos = positions[loc_index]
    table_start = html.rfind("<table", 0, pos)
    table_end = html.find("</table>", pos)
    assert table_start != -1 and table_end != -1, "Umschliessende <table> nicht gefunden"
    return html[table_start:table_end + len("</table>")]


def _location_section_before_hours(html: str, loc_index: int, loc_count: int, window: int = 1200) -> str:
    """Die `window` Zeichen unmittelbar VOR dem Start der Stundentabelle des
    loc_index-ten Ortes -- das ist der Bereich fuer Ort-Kopf + Warn-Streifen
    (AC-5: Langform-Warntext steht DIREKT ueber der Stundentabelle, nicht nur
    irgendwo frueher im Dokument)."""
    positions = _zeit_positions(html)
    assert len(positions) == loc_count
    own_table_start = html.rfind("<table", 0, positions[loc_index])
    assert own_table_start != -1
    start = max(0, own_table_start - window)
    return html[start:own_table_start]


# ---------------------------------------------------------------------------
# AC-1 bis AC-8 -- render_compare_html() als Pure Function
# ---------------------------------------------------------------------------

class TestCompareMailV2HTML:
    """
    Prueft render_compare_html() gegen den v2-Vertrag (kein Score/Winner,
    Uebersichtstabelle mit Warn-Zeile, Stundentabellen fuer alle Orte).

    SPEC: docs/specs/modules/issue_1110_compare_mail_v2.md
    """

    def test_ac1_kein_score_kein_winner_orte_alphabetisch_sortiert(self):
        """AC-1 (PO-Update 2026-07-08): kein 'Score'/'Empfehlung'/'Bester
        Standort'/🏆 mehr im HTML, Orte erscheinen ALPHABETISCH sortiert
        (case-insensitiv), NICHT in Preset-/Input-Reihenfolge."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        for forbidden in ("Score", "Empfehlung", "Bester Standort", "🏆"):
            assert forbidden not in html, (
                f"'{forbidden}' darf im v2-HTML nicht mehr vorkommen (Score/Winner entfernt)"
            )

        input_names = [loc.location.name for loc in result.locations]
        expected_order = sorted(input_names, key=str.casefold)
        assert input_names != expected_order, (
            "Test-Fixture muss bewusst NICHT alphabetisch sein (Collobrières, "
            "Marseille, Fréjus), sonst beweist der Test die Sortierung nicht"
        )

        positions = [html.index(name) for name in expected_order]
        assert positions == sorted(positions), (
            f"Orte muessen alphabetisch sortiert {expected_order} erscheinen, "
            f"gefundene Positionen: {positions}"
        )

    def test_ac2_uebersichtstabelle_struktur_und_warnzeile(self):
        """AC-2: Metrik-Zeilen als Zeilen, Orte als Spalten; erste Datenzeile
        'Amtliche Warnungen' mit Kuerzel-Chip pro aktiver Warnung je Ort."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        table = _find_overview_table(html)
        assert table, "Uebersichtstabelle mit Metrik-Zeile 'Amtliche Warnungen' nicht gefunden"

        rows = _rows(table)
        assert len(rows) >= 2, "Uebersichtstabelle braucht mind. Header + 1 Datenzeile"

        # Alphabetische Spaltenreihenfolge (PO-Update 2026-07-08):
        # Collobrières < Fréjus < Marseille (case-insensitiv).
        header = rows[0]
        assert header[1:] == ["Collobrières", "Fréjus", "Marseille"], (
            f"Spaltenkoepfe muessen die Ortsnamen alphabetisch sortiert zeigen, war: {header}"
        )

        warn_row = rows[1]
        assert "Amtliche Warnungen" in warn_row[0], (
            f"Erste Datenzeile muss 'Amtliche Warnungen' sein, war: {warn_row[0]!r}"
        )
        assert "Hitze" in warn_row[1] and "Zugang" in warn_row[1], (
            f"Collobrières-Warnzelle muss Kuerzel 'Hitze' und 'Zugang' zeigen, war: {warn_row[1]!r}"
        )
        assert "Brand" in warn_row[3] and "4" in warn_row[3], (
            f"Marseille-Warnzelle muss Kuerzel 'Brand · 4' zeigen, war: {warn_row[3]!r}"
        )

    def test_ac2_kein_best_value_highlight(self):
        """AC-2 (PO-Update 2026-07-08, Adversary-Finding F001): die gruene
        'guenstigster Wert'-Markierung entfaellt komplett -- weder der
        rgba-Gruenton noch der Hinweistext 'guenstigster Wert' duerfen
        irgendwo im HTML erscheinen. Zellfaerbung ist ausschliesslich
        Severity-basiert (Risk-Skala)."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        assert "rgba(61,107,58,0.14)" not in html, (
            "Der gruene Best-Wert-Marker darf im v2-HTML nicht mehr vorkommen (F001)"
        )
        assert "günstigster Wert" not in html, (
            "Der Hinweistext 'günstigster Wert' darf im v2-HTML nicht mehr vorkommen (F001)"
        )

    def test_enabled_metrics_filtert_numerische_uebersichts_zeilen(self):
        """Issue #1104-Integration: enabled_metrics={'wind_max'} filtert die
        Uebersichtstabelle auf die Warn-Zeile + Wind-Zeile; alle anderen
        numerischen Metrik-Zeilen (Temp max/Sonne/Wolken/UV max) entfallen."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        html = render_compare_html(
            result, profile=ActivityProfile.ALLGEMEIN, enabled_metrics={"wind_max"},
        )

        table = _find_overview_table(html)
        assert table, "Uebersichtstabelle nicht gefunden"
        labels = [row[0] for row in _rows(table) if row]

        assert any("Amtliche Warnungen" in lbl for lbl in labels), (
            "Warn-Zeile muss unabhaengig von enabled_metrics immer sichtbar sein"
        )
        assert any("Wind" in lbl for lbl in labels), (
            "Wind-Zeile muss sichtbar sein (in enabled_metrics enthalten)"
        )
        for hidden in ("Temp max", "Sonne", "Wolken", "UV max"):
            assert not any(hidden in lbl for lbl in labels), (
                f"'{hidden}'-Zeile darf NICHT erscheinen, da nicht in enabled_metrics, "
                f"gefundene Zeilen-Labels: {labels}"
            )

    def test_enabled_metrics_none_zeigt_alle_zeilen(self):
        """enabled_metrics=None (Default) zeigt weiterhin alle Metrik-Zeilen
        (Rueckwaertskompatibilitaet, kein Regress durch #1104)."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN, enabled_metrics=None)

        table = _find_overview_table(html)
        assert table, "Uebersichtstabelle nicht gefunden"
        labels = [row[0] for row in _rows(table) if row]

        for expected in ("Amtliche Warnungen", "Temp max", "Wind", "Sonne", "Wolken", "UV max"):
            assert any(expected in lbl for lbl in labels), (
                f"'{expected}'-Zeile muss ohne enabled_metrics-Filter sichtbar sein, "
                f"gefundene Zeilen-Labels: {labels}"
            )

    def test_top_n_details_ohne_wirkung_alle_orte_bekommen_stundentabelle(self):
        """PO 2026-07-08: top_n_details wird angenommen, hat aber KEINE
        Wirkung -- bei 3 Orten und top_n_details=2 erscheinen trotzdem 3
        Stundentabellen (die Mail zeigt immer alle Orte; #1105-#1107 definieren
        die Einstellung neu)."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN, top_n_details=2)

        assert len(_zeit_positions(html)) == len(result.locations), (
            f"top_n_details=2 darf die Anzahl der Stundentabellen bei "
            f"{len(result.locations)} Orten nicht auf 2 begrenzen"
        )

    def test_ac3_warnzelle_alertfreier_ort_zeigt_strich(self):
        """AC-3: Ort ohne official_alerts zeigt exakt '—' statt leerer Zelle/Chip."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        table = _find_overview_table(html)
        assert table, "Uebersichtstabelle nicht gefunden"
        rows = _rows(table)
        warn_row = rows[1]
        # Alphabetisch: Spalte 2 = Fréjus (Collobrières < Fréjus < Marseille).
        assert warn_row[2] == "—", (
            f"Fréjus (alert-frei) muss exakt '—' in der Warn-Zeile zeigen, war: {warn_row[2]!r}"
        )

    def test_ac4a_warn_lead_block_vorhanden_wenn_warnungen(self):
        """AC-4 (Gegenprobe): Sind Warnungen vorhanden, MUSS der Warn-Lead-Block
        (Akzent-Bar direkt unter dem Header) erscheinen."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        assert "Amtliche Warnungen · aktiv" in html, (
            "Warn-Lead-Block-Marker ('Amtliche Warnungen · aktiv') muss erscheinen, "
            "wenn mind. ein Ort eine amtliche Warnung hat"
        )

    def test_ac4b_kein_warn_lead_block_ohne_warnungen(self):
        """AC-4: Ohne jede Warnung ueber alle Orte hinweg entfaellt der
        Warn-Lead-Block komplett (kein leerer Rahmen).

        Hinweis: dieser Teilaspekt ist gegen den heutigen Renderer (noch ohne
        Lead-Block-Konzept) trivial erfuellt, da der Marker-String ueberhaupt
        noch nicht existiert -- siehe test_ac4a fuer die echte RED-Gegenprobe
        (Marker MUSS bei vorhandenen Warnungen erscheinen, was heute fehlschlaegt).
        Bleibt als Regressionsschutz fuer die Implementierung bestehen.
        """
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        for loc in result.locations:
            loc.official_alerts = []
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        assert "Amtliche Warnungen · aktiv" not in html, (
            "Lead-Block-Marker darf bei 0 Warnungen ueber alle Orte nicht erscheinen"
        )

    def test_ac5_langform_warnstreifen_direkt_vor_stundentabelle(self):
        """AC-5: Langform-Warntext (nicht nur Kuerzel) steht direkt ueber der
        Stundentabelle des betroffenen Ortes; alert-freier Ort zeigt keinen
        Streifen. Alphabetische Reihenfolge (PO-Update 2026-07-08):
        Index 0 = Collobrières, Index 1 = Fréjus (alert-frei), Index 2 = Marseille."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)
        n = len(result.locations)

        section0 = _location_section_before_hours(html, 0, n)
        assert "Zugang eingeschränkt — Maures" in section0, (
            "Langform-Warntext (Zugang) muss direkt ueber Collobrières' Stundentabelle stehen"
        )
        assert "Extreme Hitze" in section0, (
            "Langform-Warntext (Hitze) muss direkt ueber Collobrières' Stundentabelle stehen"
        )

        section1 = _location_section_before_hours(html, 1, n)
        assert "Extreme Hitze" not in section1 and "Zugang" not in section1, (
            "Fréjus (alert-frei) darf keinen Warn-Streifen ueber seiner Stundentabelle zeigen"
        )

    def test_f002_kein_ortsname_praefix_im_langform_warnstreifen(self):
        """F002 (Adversary Fix-Runde): der Langform-Warnstreifen zeigt nur
        `alert.label`, OHNE Ortsnamen-Praefix (z.B. NICHT 'Collobrières:
        Extreme Hitze') -- der Ort-Kopf direkt darueber nennt den Namen
        bereits."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)
        n = len(result.locations)

        section0 = _location_section_before_hours(html, 0, n)
        assert "Collobrières:" not in section0, (
            "Langform-Warnstreifen darf keinen Ortsnamen-Praefix zeigen (F002), "
            f"gefunden in: {section0!r}"
        )

    def test_ac6_stundentabelle_spaltenreihenfolge_alle_orte(self):
        """AC-6: Jede Stundentabelle (auch die des letzten Ortes) hat exakt die
        10 Spalten Zeit/Temp/Gef./Wind/Böen/Regen/UV/Gew./Regen-W./Sicht in
        dieser Reihenfolge (Default seit Issue #1106 -- "Wolken" wurde
        entfernt, drei neue Metriken ergaenzt, s. AC-1/AC-5 der
        1106-Spec)."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)
        n = len(result.locations)

        expected = [
            "Zeit", "Temp", "Gef.", "Wind", "Böen", "Regen", "UV", "Gew.", "Regen-W.", "Sicht",
        ]
        for idx in range(n):
            table = _location_hour_table(html, idx, n)
            header = _rows(table)[0]
            assert header == expected, (
                f"Ort-Index {idx}: Spaltenkoepfe {header} != erwartet {expected}"
            )

    def test_ac6_danger_zelle_temp_ueber_schwelle_faerbung(self):
        """AC-6: Temp >= 34 Grad wird mit Danger-Hintergrund #f6c5bf hinterlegt
        (Collobrières, 12:00 Uhr, t2m_c=34.0)."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        table = _location_hour_table(html, 0, len(result.locations))
        rows_raw = _rows_raw(table)
        hour_row = next(
            (r for r in rows_raw if r and "12:00" in re.sub(r"<[^>]+>", "", r[0])),
            None,
        )
        assert hour_row is not None, "12:00-Zeile in Collobrières' Stundentabelle nicht gefunden"
        temp_cell = hour_row[1]  # Temp ist die 2. Spalte
        assert "34" in re.sub(r"<[^>]+>", "", temp_cell), (
            f"Temp-Zelle um 12:00 Uhr muss '34' zeigen, war: {temp_cell}"
        )
        assert "#f6c5bf" in temp_cell, (
            f"Danger-Hintergrund #f6c5bf fehlt in der Temp-Zelle >= 34 Grad: {temp_cell}"
        )

    def test_ac7_wind_chill_none_zeigt_strich_in_gef_spalte(self):
        """AC-7: wind_chill_c=None -> Spalte 'Gef.' zeigt exakt '—' statt Fehler
        oder leerer Zelle (Collobrières, 09:00 Uhr)."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        table = _location_hour_table(html, 0, len(result.locations))
        rows = _rows(table)
        hour_row = next((r for r in rows if r and "09:00" in r[0]), None)
        assert hour_row is not None, "09:00-Zeile in Collobrières' Stundentabelle nicht gefunden"
        assert hour_row[2] == "—", (
            f"Gef.-Spalte muss bei wind_chill_c=None exakt '—' zeigen, war: {hour_row[2]!r}"
        )

    def test_ac8_media_query_zwei_container_kein_flex_grid(self):
        """AC-8: @media (max-width:480px)-Block + zwei unterscheidbare Markup-
        Container fuer die Header-Stats (Desktop/Mobile); kein CSS
        display:flex/display:grid im Mail-Body (Outlook-Kompatibilitaet)."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        assert re.search(r"@media\s*\(\s*max-width:\s*480px\s*\)", html), (
            "HTML muss einen @media (max-width: 480px)-Block enthalten"
        )
        assert "header-stats-desktop" in html and "header-stats-mobile" in html, (
            "Zwei unterscheidbare Markup-Container (Desktop/Mobile) fuer Header-Stats erwartet"
        )
        compact = html.replace(" ", "")
        assert "display:flex" not in compact, (
            "Kein CSS display:flex im Mail-Body -- E-Mail-Clients (Outlook) unterstuetzen es nicht"
        )
        assert "display:grid" not in compact, (
            "Kein CSS display:grid im Mail-Body -- E-Mail-Clients (Outlook) unterstuetzen es nicht"
        )


# ---------------------------------------------------------------------------
# AC-9 -- Validator-Umstellung (.claude/hooks/email_spec_validator.py)
# ---------------------------------------------------------------------------

class TestCompareMailV2Validator:
    """
    AC-9: `email_spec_validator.validate_structure()` muss den v2-Vertrag
    akzeptieren (keine Pflicht-Sektion 'Recommendation/Empfehlung' mehr,
    Struktur-Check auf Uebersichtstabelle inkl. Warn-Zeile).

    SPEC: docs/specs/modules/issue_1110_compare_mail_v2.md §8
    """

    @pytest.fixture(scope="class")
    def validator_module(self):
        if str(HOOKS_DIR) not in sys.path:
            sys.path.insert(0, str(HOOKS_DIR))
        spec = importlib.util.spec_from_file_location(
            "cv2_email_spec_validator", str(HOOKS_DIR / "email_spec_validator.py")
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_ac9_validate_structure_akzeptiert_v2_html_fehlerfrei(self, validator_module):
        """AC-9: `validate_structure()` gegen echtes v2-HTML liefert eine leere
        Fehlerliste (Exit-Code-0-Aequivalent auf Funktionsebene)."""
        from output.renderers.email.compare_html import render_compare_html

        result = _make_v2_result()
        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        errors = validator_module.validate_structure(html)
        assert not errors, (
            f"validate_structure() muss fuer v2-HTML fehlerfrei sein (Exit 0), "
            f"gefundene Fehler: {errors}"
        )


# ---------------------------------------------------------------------------
# AC-10 -- Klartext-Angleichung (render_comparison_text via render_compare_email)
# ---------------------------------------------------------------------------

class TestCompareMailV2Text:
    """
    AC-10: Klartext-Teil ohne Score-/🏆-Referenz, mit Uebersichts- sowie
    Warnungssektion je Ort.

    SPEC: docs/specs/modules/issue_1110_compare_mail_v2.md §7
    """

    def test_ac10_klartext_ohne_score_mit_uebersicht_und_warnungen_je_ort(self):
        from output.renderers.comparison import render_compare_email

        result = _make_v2_result()
        _html_body, text_body = render_compare_email(result, profile=ActivityProfile.ALLGEMEIN)

        assert "Score" not in text_body, "Klartext darf kein 'Score' mehr enthalten"
        assert "🏆" not in text_body, "Klartext darf kein 🏆-Symbol mehr enthalten"

        for name in ("Collobrières", "Marseille", "Fréjus"):
            assert name in text_body, f"Klartext muss einen Uebersichtsabschnitt fuer '{name}' zeigen"

        assert "Extreme Hitze" in text_body, (
            "Klartext muss die amtliche Warnung 'Extreme Hitze' (Collobrières) zeigen"
        )
        assert "Waldbrand-Gefahr — Stufe 4" in text_body, (
            "Klartext muss die amtliche Warnung 'Waldbrand-Gefahr — Stufe 4' (Marseille) zeigen"
        )

    def test_ac10_klartext_alphabetisch_sortiert(self):
        """PO-Update 2026-07-08: die alphabetische Sortierung gilt einheitlich
        auch fuer den Klartext-Teil (zentraler Sortier-Helfer, keine
        Doppel-Logik)."""
        from output.renderers.comparison import render_compare_email

        result = _make_v2_result()
        _html_body, text_body = render_compare_email(result, profile=ActivityProfile.ALLGEMEIN)

        expected_order = ["Collobrières", "Fréjus", "Marseille"]
        positions = [text_body.index(name) for name in expected_order]
        assert positions == sorted(positions), (
            f"Klartext muss Orte alphabetisch sortiert {expected_order} zeigen, "
            f"gefundene Positionen: {positions}"
        )


# ---------------------------------------------------------------------------
# F003 -- Abo-Footer bekommt preset_weekday ueber den Subscription-Pfad
# ---------------------------------------------------------------------------

class TestF003PresetWeekdayForwarding:
    """F003 (Adversary Fix-Runde): `CompareSubscription.weekday` muss bis zum
    Abo-Footer durchgereicht werden (compare_subscription.py -> render_compare_email
    -> render_compare_html). Echter `ComparisonEngine.run()` gegen den Offline-
    FixtureProvider (Riviera-Koordinaten ausserhalb der GeoSphere-Bounding-Box,
    tests/conftest.py autouse) -- kein Mock, kein echter Netzwerkruf."""

    def test_f003_weekday_kommt_im_abo_footer_an(self):
        from app.user import CompareSubscription, Schedule
        from services.compare_subscription import run_comparison_for_subscription

        loc = SavedLocation(id="riviera-nice-f003", name="Nizza", lat=43.7102, lon=7.2620, elevation_m=10)
        sub = CompareSubscription(
            id="f003-test", name="F003-Test", locations=["riviera-nice-f003"],
            schedule=Schedule.WEEKLY, weekday=2, forecast_hours=48,
            time_window_start=9, time_window_end=16,
        )
        _subject, html_body, _text_body, _winner = run_comparison_for_subscription(sub, [loc])

        assert "Nächster Versand" in html_body, "Abo-Footer-Sektion 'Nächster Versand' fehlt"
        idx = html_body.index("Nächster Versand")
        window = html_body[idx: idx + 400]
        assert "—</div>" not in window, (
            "Bei schedule=WEEKLY + gesetztem weekday darf der Abo-Footer NICHT auf "
            "den '—'-Platzhalter zurueckfallen (F003: weekday muss von "
            "compare_subscription.py bis render_compare_html() durchgereicht werden)"
        )
