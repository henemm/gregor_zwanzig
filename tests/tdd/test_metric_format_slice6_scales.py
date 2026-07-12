"""TDD — Issue #1214 Scheibe 6: Wolken-Skala + Thunder-Ordinal vereinheitlichen.

SPEC: docs/specs/modules/issue_1214_metric_format_slice6.md
PO-Entscheidung 2026-07-12: Mail-Skala (≤10/30/70/90) wird produktweite Wahrheit.

RED vor Implementierung:
- AC-1: metric_format.cloud_emoji existiert nicht (ImportError).
- AC-3: compact_summary friendly-Wolken nutzt noch die alte <20/40/60/80-Skala.
- AC-4: metric_format.thunder_ordinal/max_thunder existieren nicht.
- AC-5: narrow._cloud_emoji (tote Kopie) existiert noch.
- AC-6: Katalog sunshine.decimals ist None (nicht 1).
GRÜN vor+nach (Anker):
- AC-2: Mail-Skala via helpers.fmt_val (Boundary-Tests in
  test_weather_metrics_ux.py laufen unverändert — hier nicht dupliziert).
- AC-7: _night_emoji/_dni_emoji-Verhalten festgenagelt (eigene Konzepte).
"""
from __future__ import annotations

import pytest


# ===========================================================================
# AC-1: kanonische cloud_emoji mit Mail-Skala (RED: Funktion fehlt)
# ===========================================================================

class TestAC1CanonicalCloudEmoji:
    def test_cloud_emoji_boundaries(self):
        """AC-1: GIVEN die kanonische Skala ≤10/30/70/90 / WHEN cloud_emoji an
        allen Grenzwerten aufgerufen wird / THEN liefert sie exakt die
        PO-entschiedenen Mail-Emojis; None -> '–'."""
        from src.output.metric_format import cloud_emoji

        assert cloud_emoji(0) == "☀️"
        assert cloud_emoji(10) == "☀️"
        assert cloud_emoji(11) == "🌤️"
        assert cloud_emoji(30) == "🌤️"
        assert cloud_emoji(31) == "⛅"
        assert cloud_emoji(70) == "⛅"
        assert cloud_emoji(71) == "🌥️"
        assert cloud_emoji(90) == "🌥️"
        assert cloud_emoji(91) == "☁️"
        assert cloud_emoji(100) == "☁️"
        assert cloud_emoji(None) == "–"


# ===========================================================================
# AC-3: Kompakt-Zusammenfassung zeigt neue Skala (RED: alte <20/40/60/80)
# ===========================================================================

class TestAC3CompactSummaryNewScale:
    @pytest.mark.parametrize("pct,expected", [
        (15, "🌤️"),  # alt: ☀️ (<20) — PO-gewollte Änderung
        (35, "⛅"),   # alt: 🌤️ (<40)
        (85, "🌥️"),  # alt: ☁️ (>=80)
    ])
    def test_format_clouds_delta_zones(self, pct, expected):
        """AC-3: GIVEN die PO-entschiedene kanonische Skala / WHEN die
        Kompakt-Zusammenfassung Wolken im friendly-Modus formatiert / THEN
        zeigt sie in den Delta-Zonen das NEUE Emoji (15%/35%/85%)."""
        from app.models import SegmentWeatherSummary
        from output.renderers.compact_summary import CompactSummaryFormatter

        summary = SegmentWeatherSummary(cloud_avg_pct=pct)
        out = CompactSummaryFormatter._format_clouds(summary, friendly=True)
        assert out == expected, f"{pct}%: erwartet {expected}, bekam {out}"


# ===========================================================================
# AC-4: kanonische Thunder-Ordnung (RED: Funktionen fehlen)
# ===========================================================================

class TestAC4CanonicalThunderOrder:
    def test_thunder_ordinal_and_max(self):
        """AC-4: GIVEN ThunderLevel als str-Enum ohne eigene Ordnung / WHEN
        thunder_ordinal/max_thunder genutzt werden / THEN gilt kanonisch
        NONE<MED<HIGH und max_thunder liefert das jeweils höchste Level."""
        from app.models import ThunderLevel
        from src.output.metric_format import max_thunder, thunder_ordinal

        assert thunder_ordinal(ThunderLevel.NONE) == 0
        assert thunder_ordinal(ThunderLevel.MED) == 1
        assert thunder_ordinal(ThunderLevel.HIGH) == 2
        assert max_thunder([ThunderLevel.NONE, ThunderLevel.HIGH,
                            ThunderLevel.MED]) == ThunderLevel.HIGH
        assert max_thunder([ThunderLevel.MED, ThunderLevel.NONE]) == ThunderLevel.MED
        # Regressions-Falle aus der Analyse: nacktes max() wäre alphabetisch
        # (NONE > MED > HIGH) — genau falsch herum.
        assert max_thunder([ThunderLevel.NONE, ThunderLevel.MED]) != ThunderLevel.NONE


# ===========================================================================
# AC-5: tote narrow._cloud_emoji gelöscht (RED: existiert noch)
# ===========================================================================

class TestAC5DeadNarrowCloudEmojiRemoved:
    def test_narrow_cloud_emoji_gone(self):
        """AC-5: GIVEN narrow.py nach der Scheibe / WHEN das Modul importiert
        wird / THEN existiert kein `_cloud_emoji`-Attribut mehr (kein
        Aufrufer, verifiziert in der Analyse). Modul-Introspektion statt
        Quelltext-Read (#765-Hygiene-Gate: kein read_text() auf Produkt-.py)."""
        from output.renderers import narrow
        assert not hasattr(narrow, "_cloud_emoji"), (
            "narrow.py: tote _cloud_emoji-Kopie muss ersatzlos entfernt werden"
        )


# ===========================================================================
# AC-6: sunshine decimals=1 + Sonne-Zeile migriert (RED: None bzw. 4 Aufrufe)
# ===========================================================================

class TestAC6SunshineCatalogAndMigration:
    def test_sunshine_decimals_is_one(self):
        """AC-6: GIVEN der Katalog-Eintrag sunshine / WHEN decimals gelesen
        wird / THEN ist es 1 (deckt das faktische Anzeige-Verhalten aller
        Kanäle: calculate_sunny_hours rundet immer auf 1 Dezimale)."""
        from app.metric_catalog import get_metric
        assert get_metric("sunshine").decimals == 1

    def test_format_value_sunshine_bare_matches_str(self):
        """AC-6: GIVEN decimals=1 / WHEN format_value('sunshine', v, 'bare')
        für 1-Dezimal-Floats läuft / THEN identisch zu str(v) — Beweis, dass
        die Sonne-Zeile verhaltensneutral migrierbar ist."""
        from src.output.metric_format import format_value
        for v in (4.7, 7.0, 0.0, 12.5):
            assert format_value("sunshine", v, style="bare") == str(v)

    def test_comparison_sun_line_uses_format_value(self):
        """AC-6: GIVEN render_comparison_text nach der Migration / WHEN der
        Quelltext untersucht wird / THEN existieren genau 5 format_value-
        Aufrufe (Scheibe-5-Stand 4 + migrierte Sonne-Zeile)."""
        import inspect
        import re
        from output.renderers.comparison import render_comparison_text
        calls = re.findall(r"format_value\(", inspect.getsource(render_comparison_text))
        assert len(calls) == 5, (
            f"Erwartet 5 format_value-Aufrufe (inkl. Sonne-Zeile), gefunden {len(calls)}"
        )


# ===========================================================================
# AC-7: Nacht-/DNI-Emoji bleiben unverändert (GRÜN vor+nach — Anker)
# ===========================================================================

class TestAC7NightAndDniUntouched:
    def test_night_emoji_scale_unchanged(self):
        """AC-7-Anker: GIVEN das eigenständige Nacht-Konzept / WHEN
        _night_emoji läuft / THEN gilt weiter <40 Mond, <80 Mond+Wolke,
        sonst Wolke — von der Tages-Skala unberührt."""
        from services.weather_metrics import _night_emoji
        assert _night_emoji(0) == "🌙"
        assert _night_emoji(39) == "🌙"
        assert _night_emoji(40) == "🌙☁️"
        assert _night_emoji(79) == "🌙☁️"
        assert _night_emoji(80) == "☁️"

    def test_dni_emoji_unchanged(self):
        """AC-7-Anker: GIVEN das DNI-Konzept (Sonnenstrahlung) / WHEN
        _dni_emoji an den Bandgrenzen läuft / THEN unverändert."""
        from services.weather_metrics import _dni_emoji
        assert _dni_emoji(0) == "☁️"
        assert _dni_emoji(1) == "🌥️"
