"""
TDD: Tests fuer das konsolidierte Metrik-Format-Modul (Issue #1214, Scheibe 1).

SPEC: docs/specs/modules/issue_1214_metric_format_slice1_2.md

Neues Modul src/output/metric_format.py buendelt format_value/severity_for/
tone_css/label als Single Source of Truth statt 6-8facher Duplikation je
Kanal-Renderer. Diese Tests pruefen Scheibe 1 (Modul + Tests, noch ohne
Consumer-Migration) gegen konkrete, gegen den echten Metrik-Katalog
verifizierte Erwartungswerte -- kein Mock, kein Dateiinhalt-Check.
"""
import pytest

from src.output.metric_format import format_value, severity_for, label
from src.output.renderers.email.design_tokens import tone_css


class TestFormatValue:
    """AC-1: format_value liefert korrekte, katalog-verifizierte Strings."""

    def test_temperature_zero_decimals(self):
        # Katalog: temperature.decimals=0 (metric_catalog.py) -- deckt sich
        # mit compare_html._fmt_deg, das ebenfalls 0 Dezimalstellen zeigt.
        assert format_value("temperature", 21.6, style="plain") == "22°C"

    def test_wind_zero_decimals(self):
        # Katalog: wind.decimals=0, unit="km/h"
        assert format_value("wind", 45.0, style="plain") == "45 km/h"

    def test_visibility_converts_m_to_km_with_one_decimal(self):
        # Katalog: visibility.unit="m", display_unit="km", decimals=1.
        # format_value muss m->km konvertieren (Faktor 1000), dann runden.
        assert format_value("visibility", 4200, style="plain") == "4.2 km"

    def test_none_value_returns_dash(self):
        assert format_value("temperature", None, style="plain") == "–"


class TestFormatValueBareStyle:
    """AC-1 (Scheibe 3): style="bare" liefert die reine Zahl OHNE
    Einheiten-Suffix -- fuer helpers.fmt_val, wo die Einheit in der
    Spalten-Ueberschrift der Trip-Briefing-Tabelle steht, nicht in der Zelle.
    style="plain" (Scheibe 1) bleibt davon unberuehrt (Koexistenz)."""

    def test_wind_bare_has_no_unit_suffix(self):
        # Katalog: wind.decimals=0. Bare-Stil: "45", nicht "45 km/h".
        assert format_value("wind", 45.0, style="bare") == "45"

    def test_gust_bare_has_no_unit_suffix(self):
        assert format_value("gust", 62.0, style="bare") == "62"

    def test_precipitation_bare_respects_one_decimal(self):
        # Katalog: precipitation.decimals=1.
        assert format_value("precipitation", 1.0, style="bare") == "1.0"

    def test_rain_probability_bare_has_no_unit_suffix(self):
        assert format_value("rain_probability", 45.0, style="bare") == "45"

    def test_cape_bare_has_no_unit_suffix(self):
        assert format_value("cape", 1200.0, style="bare") == "1200"

    def test_freezing_level_bare_has_no_unit_suffix(self):
        assert format_value("freezing_level", 2400.0, style="bare") == "2400"

    def test_bare_none_value_returns_dash(self):
        assert format_value("wind", None, style="bare") == "–"

    def test_plain_style_unaffected_by_bare_introduction(self):
        # Regressionsschutz: style="plain" bleibt exakt wie in Scheibe 1.
        assert format_value("wind", 45.0, style="plain") == "45 km/h"


class TestSeverityFor:
    """AC-3 (Vorbereitung): severity_for liefert kanonisches Ampel-Vokabular."""

    def test_wind_45_kmh_is_yellow_not_red(self):
        # Katalog: wind.display_thresholds={yellow:30, orange:50, red:70}.
        # 45 liegt zwischen yellow(30) und orange(50) -> "yellow".
        # Der alte, hartcodierte compare_html._sev_wind(45) gibt "danger"
        # (>40) zurueck -- genau diese Divergenz behebt Scheibe 2.
        assert severity_for("wind", 45.0) == "yellow"

    def test_wind_above_red_threshold(self):
        assert severity_for("wind", 75.0) == "red"

    def test_wind_below_all_thresholds_is_green(self):
        assert severity_for("wind", 10.0) == "green"

    def test_none_value_returns_none(self):
        assert severity_for("wind", None) is None

    def test_temperature_has_no_thresholds_returns_none(self):
        # F001-Fix (Adversary-Fund): Katalog definiert fuer temperature KEIN
        # display_thresholds-Dict (leer). severity_for muss dafuer None
        # liefern, NICHT das implizite "green"-Fallback -- sonst wuerde eine
        # Metrik ohne definierte Ampel-Schwellen faelschlich als "unbedenklich"
        # markiert (AC-1: mindestens 3 Metriktypen, hier temperature).
        assert severity_for("temperature", 40.0) is None

    def test_visibility_has_only_inverted_threshold_returns_none(self):
        # F001-Fix: Katalog definiert fuer visibility NUR den invertierten Key
        # "orange_lt" (niedriger Wert = kritischer), keinen Standard-Key
        # "orange"/"yellow"/"red". severity_for unterstuetzt invertierte
        # Schwellen in dieser Scheibe bewusst NICHT (Known Limitation,
        # Nachruestung: Scheibe 3+) -- liefert daher None statt "green".
        # Sicherheitsrelevant: 100m Sicht ist gefaehrlich niedrig und darf
        # NIEMALS als "green" (unbedenklich) erscheinen.
        assert severity_for("visibility", 100.0) is None


class TestToneCss:
    """AC-1/AC-5: tone_css operiert nur auf kanonischem Vokabular, getrennt
    von den 4 amtlichen Warnstufen (_ALERT_LEVEL_CELL)."""

    def test_green_returns_tuple_of_two_colors(self):
        bg, fg = tone_css("green")
        assert isinstance(bg, str) and bg.startswith("#")
        assert isinstance(fg, str) and fg.startswith("#")

    def test_four_canonical_levels_are_distinct(self):
        colors = {level: tone_css(level) for level in ("green", "yellow", "orange", "red")}
        assert len(set(colors.values())) == 4, "Alle vier Ampel-Stufen muessen unterschiedliche Farben haben"


class TestLabel:
    """AC-1: label ist reiner Katalog-Passthrough."""

    def test_label_de_matches_catalog(self):
        assert label("wind", style="label_de") == "Wind"

    def test_compact_label_matches_catalog(self):
        assert label("wind", style="compact_label") == "W"


class TestAlertLevelSeparation:
    """AC-5: Die 4 amtlichen Warnstufen (_ALERT_LEVEL_CELL) sind ein separates
    System und bleiben durch die Metrik-Konsolidierung unberuehrt. tone_css
    (Metrik-Palette) wird an keiner Stelle mit _ALERT_LEVEL_CELL vermischt."""

    def test_alert_level_cell_values_unchanged(self):
        # Amtliche Warnstufen-Palette (Issue #1056 v2.0) -- byte-identisch zu vor
        # der Metrik-Format-Migration. Aendert sich hier etwas, ist das ein
        # Regress im amtlichen Warn-Rendering.
        from output.renderers.email import compare_html as ch
        from output.renderers.email.design_tokens import (
            G_ALERT_L2, G_ALERT_L3, G_ALERT_L4, G_SUCCESS,
        )
        assert ch._ALERT_LEVEL_CELL == {
            1: ("#dbeadd", G_SUCCESS),
            2: ("#f2e4b0", G_ALERT_L2),
            3: ("#f4d3c6", G_ALERT_L3),
            4: ("#e4d7f5", G_ALERT_L4),
        }

    def test_tone_css_and_alert_level_are_separate_mappings(self):
        # Getrennte Codepfade: tone_css ist ueber das kanonische String-
        # Vokabular gekeyt, _ALERT_LEVEL_CELL ueber die amtlichen Integer-Stufen
        # 1-4. Kein gemeinsamer Lookup -> eine Metrik-Severity kann niemals in
        # eine amtliche Warnstufen-Zelle bluten (und umgekehrt).
        from output.renderers.email import compare_html as ch

        for canonical in ("green", "yellow", "orange", "red"):
            # tone_css akzeptiert nur kanonische String-Level, keine Int-Stufen.
            assert isinstance(tone_css(canonical), tuple)
        for official_level in (1, 2, 3, 4):
            assert official_level in ch._ALERT_LEVEL_CELL
            # Amtliche Integer-Stufen sind kein gueltiger tone_css-Key.
            with pytest.raises((KeyError, TypeError)):
                tone_css(official_level)  # type: ignore[arg-type]
