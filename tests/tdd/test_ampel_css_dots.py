"""#1222: Gestylte CSS-Dots statt Kreis-Emojis 🟢🟡🟠🔴 in E-Mails.

Kern-Schicht (deterministisch, kein Netz/Mail): prueft die Renderer-SSoT direkt
und ueber einen echten render_email-Durchlauf. Die Kreis-Emojis duerfen weder im
HTML (dort CSS-Dot mit Ring) noch im Plain-Text (dort ersatzlos entfernt)
erscheinen. Wetter-Symbole (z.B. Blitz) bleiben erhalten.

RED-Erwartung vor dem Fix: ampel_dot()/fmt_val() liefern heute Emoji, die
official-Notice und Plain-Pills tragen heute Emoji → alle Assertions unten
schlagen fehl.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

CIRCLE_EMOJIS = ("🟢", "🟡", "🟠", "🔴")

# Echte End-to-End-Render-Harness aus dem #759-Test wiederverwenden (kein Mock).
from tests.tdd.test_issue_759_email_ampel import (  # noqa: E402
    _data_cells_759,
    _render_wind_via_render_email,
)


# ---------------------------------------------------------------------------
# AC-1: HTML-Ampelzelle = CSS-Dot mit Ring, kein Kreis-Emoji
# ---------------------------------------------------------------------------

class TestHtmlAmpelCellIsCssDot:
    def test_ampel_dot_returns_css_span_no_emoji(self):
        """ampel_dot() liefert einen CSS-Dot (border-radius:50%), kein Emoji."""
        from src.output.renderers.email.helpers import ampel_dot
        from app.metric_catalog import get_metric

        thr = get_metric("wind").display_thresholds
        out = ampel_dot(75, thr)  # roter Bereich
        assert "border-radius:50%" in out, f"Kein CSS-Dot: {out!r}"
        assert not any(e in out for e in CIRCLE_EMOJIS), f"Emoji verblieben: {out!r}"

    def test_fmt_val_html_ampel_cell_is_css_dot(self):
        """fmt_val(..., html=True) fuer Ampel-Metriken → CSS-Dot statt Emoji."""
        from src.output.renderers.email.helpers import fmt_val

        for key, val in [("wind", 75), ("gust", 85), ("precip", 12), ("pop", 85)]:
            out = fmt_val(key, val, html=True)
            assert "border-radius:50%" in out, f"{key}: kein CSS-Dot: {out!r}"
            assert not any(e in out for e in CIRCLE_EMOJIS), (
                f"{key}: Kreis-Emoji verblieben: {out!r}"
            )

    def test_rendered_html_briefing_has_no_circle_emoji(self):
        """End-to-End: Einfach-Briefing-HTML enthaelt CSS-Dot, kein Kreis-Emoji."""
        html, _plain = _render_wind_via_render_email(use_friendly=True)
        cells = _data_cells_759(html)
        assert cells, "HTML muss Wind-Zellen haben"
        emoji_cells = [c for c in cells if any(e in c for e in CIRCLE_EMOJIS)]
        assert not emoji_cells, f"Kreis-Emoji in Zellen: {emoji_cells!r}"
        assert "border-radius:50%" in html, "Kein CSS-Dot im HTML"


# ---------------------------------------------------------------------------
# AC-2: Dot-Farbe je Band konsistent mit Pill-/Toenungs-Level
# ---------------------------------------------------------------------------

class TestDotLevelConsistency:
    def test_ampel_stage_index_matches_band(self):
        """ampel_stage_index bleibt 0..3 korrekt (Entkopplung vom Emoji-Lookup)."""
        from src.output.renderers.email.helpers import ampel_stage_index
        from app.metric_catalog import get_metric

        thr = get_metric("wind").display_thresholds
        assert ampel_stage_index(20, thr) == 0
        assert ampel_stage_index(40, thr) == 1
        assert ampel_stage_index(60, thr) == 2
        assert ampel_stage_index(75, thr) == 3

    def test_dot_color_matches_stage_tone(self):
        """Der CSS-Dot je Band traegt die Farbe, die auch der Pill-tone vorgibt."""
        from src.output.renderers.email.helpers import (
            ampel_dot,
            ampel_stage_tone,
            _AMPEL_STAGE_COLORS,
        )
        from app.metric_catalog import get_metric

        thr = get_metric("wind").display_thresholds
        # Rotes Band: Dot und Pill-tone muessen denselben Schweregrad tragen.
        tone = ampel_stage_tone(75, thr)
        assert tone == "ampel_red"
        dot = ampel_dot(75, thr)
        # Dot ist rot: enthaelt keine gruene/gelbe/orange Stage-Farbe.
        assert _AMPEL_STAGE_COLORS["ampel_green"][0] not in dot


# ---------------------------------------------------------------------------
# AC-3: Plain-Text-Alert-Notice ohne Kreis-Emoji, Wort bleibt
# ---------------------------------------------------------------------------

class TestOfficialNoticePlainNoEmoji:
    def test_notice_plain_has_word_no_emoji(self):
        from src.output.renderers.alert.official_alerts import (
            render_official_alert_notice_plain,
        )
        from services.official_alerts.models import OfficialAlert

        alert = OfficialAlert(
            source="meteofrance", hazard="thunderstorm", level=4,
            label="Gewitterwarnung", region_label="Etappe 3",
            valid_from=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
            valid_to=datetime(2026, 7, 11, 18, 0, tzinfo=timezone.utc),
        )
        lines = render_official_alert_notice_plain(
            [(alert, [])], tz=ZoneInfo("Europe/Berlin")
        )
        blob = "\n".join(lines)
        assert "ROT" in blob, f"Schwere-Wort fehlt: {blob!r}"
        assert not any(e in blob for e in CIRCLE_EMOJIS), f"Kreis-Emoji verblieben: {blob!r}"


# ---------------------------------------------------------------------------
# AC-4: Plain-Text-Metriken-Pills ohne Kreis-Emoji
# ---------------------------------------------------------------------------

class TestPlainPillsNoEmoji:
    def test_tone_symbol_has_no_circle_emoji(self):
        from src.output.renderers.email.helpers import tone_symbol

        for tone in ("ampel_green", "ampel_yellow", "ampel_orange", "ampel_red"):
            sym = tone_symbol(tone)
            assert not any(e in sym for e in CIRCLE_EMOJIS), (
                f"tone_symbol({tone!r}) traegt Kreis-Emoji: {sym!r}"
            )


# ---------------------------------------------------------------------------
# AC-5: Gesamter Mail-Korpus emoji-frei, Wetter-Symbole bleiben
# ---------------------------------------------------------------------------

class TestNoCircleEmojiAnywhere:
    def test_full_html_and_plain_have_no_circle_emoji(self):
        html, plain = _render_wind_via_render_email(use_friendly=True)
        for label, blob in [("HTML", html), ("Plain", plain)]:
            found = [e for e in CIRCLE_EMOJIS if e in blob]
            assert not found, f"{label} enthaelt Kreis-Emoji {found!r}"

    def test_weather_symbols_are_not_stripped(self):
        """Regressionsschutz: Blitz-Symbol darf weiter erscheinen (nicht Teil des Fix)."""
        from src.output.renderers.email.helpers import fmt_val
        from app.models import ThunderLevel

        out = fmt_val("thunder", ThunderLevel.HIGH, html=True)
        assert "⚡" in out, f"Wetter-Symbol faelschlich entfernt: {out!r}"
