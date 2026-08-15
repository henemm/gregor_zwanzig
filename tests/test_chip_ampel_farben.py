"""TDD RED — Bug #1801: Chip-Farben im Metriken-Überblick.

Drei Chips (Gewitter, UV, Feuchte) zeigen heute eine Farbe, die nicht zur
tatsaechlich berechneten Ampelstufe passt (Kontext-Dok Befund B). Zusaetzlich
kann die Chip-Palette heute nur 3 von 4 Ampelstufen darstellen, weil
`ampel_yellow` und `ampel_orange` beide auf denselben Ton `"warn"` abbilden
(Befund C) -- ein neuer vierter Ton `caution` behebt das.

SPEC: docs/specs/modules/fix_1801_warnstufen_abstufung.md AC-5..AC-8

Mock-frei: echte `ForecastDataPoint`-Objekte + echte Renderer-Funktionen
(`_pill_for_metric`, `pill_html`). Geprueft wird der zurueckgegebene
(text, tone)-Wert bzw. das gerenderte HTML, kein Dateiinhalt-Check.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import re

TZ = ZoneInfo("Europe/Berlin")


def _dp(hour: int, **overrides):
    from app.models import ForecastDataPoint

    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, hour, 0, tzinfo=timezone.utc), **overrides,
    )


# ===========================================================================
# AC-5 — Gewitter-Chip folgt thunder_ampel_band() (SSoT ADR-0025) statt
# fest verdrahtetem "ampel_red"
# ===========================================================================

class TestAC5ThunderChipFollowsAmpelBand:

    def test_thunder_med_pill_is_ampel_orange_not_red(self):
        """GIVEN der Gewitter-Chip zeigt heute IMMER 'ampel_red', unabhaengig
        von der tatsaechlichen Staerke / WHEN eine Stunde mit ThunderLevel.MED
        vorliegt / THEN zeigt der Chip 'ampel_orange' -- dieselbe Stufe wie
        die Stundentabelle (`thunder_ampel_band(MED) == 'orange'`)."""
        from app.models import ThunderLevel
        from output.metric_format import thunder_ampel_band
        from output.renderers.email.helpers import _pill_for_metric

        assert thunder_ampel_band(ThunderLevel.MED) == "orange"

        dps = [_dp(10, thunder_level=ThunderLevel.MED)]
        pill = _pill_for_metric("thunder", {}, dps, tz=TZ)

        assert pill is not None, "keine Gewitter-Pille fuer MED-Stunde"
        text, tone = pill
        assert tone == "ampel_orange", (
            f"Gewitter-Chip bei MED war {tone!r}, erwartet 'ampel_orange' "
            f"(SSoT thunder_ampel_band, ADR-0025) -- Text: {text!r}"
        )

    def test_thunder_high_pill_is_ampel_red(self):
        """GIVEN dieselbe SSoT-Kopplung / WHEN eine Stunde mit
        ThunderLevel.HIGH vorliegt / THEN zeigt der Chip weiterhin
        'ampel_red' (Abgrenzung zu MED -- beide duerfen sich nicht wieder
        vermischen)."""
        from app.models import ThunderLevel
        from output.metric_format import thunder_ampel_band
        from output.renderers.email.helpers import _pill_for_metric

        assert thunder_ampel_band(ThunderLevel.HIGH) == "red"

        dps = [_dp(10, thunder_level=ThunderLevel.HIGH)]
        pill = _pill_for_metric("thunder", {}, dps, tz=TZ)

        assert pill is not None, "keine Gewitter-Pille fuer HIGH-Stunde"
        _text, tone = pill
        assert tone == "ampel_red", (
            f"Gewitter-Chip bei HIGH war {tone!r}, erwartet 'ampel_red'"
        )


# ===========================================================================
# AC-6 — UV-Chip wertet die Katalog-Schwellen (3/6/8) aus statt immer
# neutral zu bleiben
# ===========================================================================

class TestAC6UvChipUsesThresholds:

    def test_uv_below_first_threshold_is_ampel_green(self):
        """GIVEN UV-Hoechstwert unter der ersten Schwelle (3) / WHEN der
        Chip gebaut wird / THEN zeigt er 'ampel_green' -- Gruen ist eine
        Ampelfarbe wie bei jeder anderen Schwellen-Metrik (Wind, Regen,
        Temperatur), kein Sonderweg auf neutral (F001-Fix, #1801)."""
        from output.renderers.email.helpers import _pill_for_metric

        dps = [_dp(14, uv_index=2.0)]
        pill = _pill_for_metric("uv_index", {}, dps, tz=TZ)

        assert pill is not None
        _text, tone = pill
        assert tone == "ampel_green", (
            f"UV 2.0 (unter Schwelle 3) sollte 'ampel_green' sein, war {tone!r}"
        )

    def test_uv_between_yellow_and_orange_threshold_is_ampel_yellow(self):
        """GIVEN UV-Hoechstwert zwischen Schwelle 3 und 6 / WHEN der Chip
        gebaut wird / THEN zeigt er 'ampel_yellow' statt der heutigen festen
        neutralen Farbe."""
        from output.renderers.email.helpers import _pill_for_metric

        dps = [_dp(14, uv_index=4.5)]
        pill = _pill_for_metric("uv_index", {}, dps, tz=TZ)

        assert pill is not None
        _text, tone = pill
        assert tone == "ampel_yellow", (
            f"UV 4.5 (zwischen Schwelle 3 und 6) war {tone!r}, erwartet "
            f"'ampel_yellow'"
        )

    def test_uv_between_orange_and_red_threshold_is_ampel_orange(self):
        """GIVEN UV-Hoechstwert zwischen Schwelle 6 und 8 / WHEN der Chip
        gebaut wird / THEN zeigt er 'ampel_orange' -- 7.7 ist exakt der Wert
        aus dem vom PO gemeldeten Screenshot (Chip 'UV max 7.7' war blau,
        muesste orange sein, #1801)."""
        from output.renderers.email.helpers import _pill_for_metric

        dps = [_dp(14, uv_index=7.7)]
        pill = _pill_for_metric("uv_index", {}, dps, tz=TZ)

        assert pill is not None
        text, tone = pill
        assert tone == "ampel_orange", (
            f"UV 7.7 (zwischen Schwelle 6 und 8) war {tone!r}, erwartet "
            f"'ampel_orange' -- Text: {text!r}"
        )

    def test_uv_above_highest_threshold_is_ampel_red(self):
        """GIVEN UV-Hoechstwert oberhalb der obersten Schwelle (8) / WHEN
        der Chip gebaut wird / THEN zeigt er 'ampel_red' statt der heutigen
        festen neutralen Farbe (Kontext-Dok Befund B)."""
        from output.renderers.email.helpers import _pill_for_metric

        dps = [_dp(14, uv_index=8.5)]
        pill = _pill_for_metric("uv_index", {}, dps, tz=TZ)

        assert pill is not None
        text, tone = pill
        assert tone == "ampel_red", (
            f"UV 8.5 (ueber Schwelle 8) war {tone!r}, erwartet 'ampel_red' "
            f"-- Text: {text!r}"
        )


# ===========================================================================
# AC-7 — Feuchte-Chip bleibt neutral, auch bei Schwellenueberschreitung
# (keine display_thresholds im Katalog fuer humidity)
# ===========================================================================

class TestAC7HumidityChipStaysNeutral:

    def test_humidity_above_default_mention_threshold_is_neutral(self):
        """GIVEN der Feuchte-Chip zeigt heute bei Ueberschreitung der
        SMS-Erwaehnungsschwelle (90%) fest 'ampel_yellow', obwohl die Metrik
        im Katalog KEINE display_thresholds fuehrt / WHEN eine hohe Feuchte
        (95%) vorliegt / THEN bleibt der Chip neutral -- analog den
        uebrigen stufenlosen Metriken (Wolken, 0°-Linie, Taupunkt, Sonne)."""
        from app.metric_catalog import get_metric
        from output.renderers.email.helpers import (
            _PILL_NEUTRAL_TONE, _pill_for_metric,
        )

        # Voraussetzung der Spec-Regel: humidity fuehrt keine Schwellen.
        assert get_metric("humidity").display_thresholds == {}

        dps = [_dp(14, humidity_pct=95)]
        pill = _pill_for_metric("humidity", {}, dps, tz=TZ)

        assert pill is not None, "keine Feuchte-Pille"
        text, tone = pill
        assert tone == _PILL_NEUTRAL_TONE, (
            f"Feuchte-Chip bei 95% war {tone!r}, erwartet neutralen Ton "
            f"{_PILL_NEUTRAL_TONE!r} (Text: {text!r})"
        )


# ===========================================================================
# AC-8 — Vierter Chip-Ton "caution": vier Ampelstufen -> vier unterscheidbare
# Hintergrundfarben (heute nur drei, weil yellow+orange auf "warn" kollidieren)
# ===========================================================================

class TestAC8FourDistinctPillTones:

    def test_pill_html_renders_four_distinct_backgrounds(self):
        """GIVEN `_PILL_TONE_MAP` bildet heute 'ampel_yellow' UND
        'ampel_orange' auf denselben Palette-Eintrag 'warn' ab (Befund C) /
        WHEN `pill_html()` fuer alle vier Ampel-Toene aufgerufen wird /
        THEN entstehen vier unterscheidbare Hintergrundfarben, nicht drei."""
        from output.renderers.email.helpers import pill_html

        bg_re = re.compile(r"background:(#[0-9a-fA-F]{6})")
        seen_bg = set()
        for tone in ("ampel_green", "ampel_yellow", "ampel_orange", "ampel_red"):
            html_out = pill_html("Test", tone)
            m = bg_re.search(html_out)
            assert m is not None, f"keine Hintergrundfarbe im Pill-HTML fuer {tone!r}"
            seen_bg.add(m.group(1))

        assert len(seen_bg) == 4, (
            f"Nur {len(seen_bg)} unterscheidbare Hintergrundfarben fuer die "
            f"vier Ampel-Toene ({seen_bg}) -- erwartet 4 (neuer Ton "
            f"'caution' schliesst die Luecke zwischen gelb und orange)"
        )

    def test_pill_tone_map_has_dedicated_caution_entry(self):
        """GIVEN der neue vierte Ton `caution` soll NUR fuer 'ampel_yellow'
        stehen (nicht mehr geteilt mit 'ampel_orange') / WHEN
        `_PILL_TONE_MAP` gelesen wird / THEN mappt 'ampel_yellow' auf
        'caution' und 'ampel_orange' bleibt bei 'warn' -- zwei
        unterschiedliche Eintraege statt einem gemeinsamen."""
        from output.renderers.email.helpers import _PILL_TONE_MAP

        assert _PILL_TONE_MAP.get("ampel_yellow") == "caution", (
            f"_PILL_TONE_MAP['ampel_yellow'] war "
            f"{_PILL_TONE_MAP.get('ampel_yellow')!r}, erwartet 'caution'"
        )
        assert _PILL_TONE_MAP.get("ampel_orange") == "warn"
        assert _PILL_TONE_MAP["ampel_yellow"] != _PILL_TONE_MAP["ampel_orange"]
