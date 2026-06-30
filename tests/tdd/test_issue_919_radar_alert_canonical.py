"""
TDD-RED: Issue #919 — Radar-Alert auf kanonischen Renderer migrieren.

Slice zu #917. Migriert den Radar-/Nowcast-Onset-Alert auf die vier kanonischen
Renderer (render_subject · render_email · render_telegram · render_sms). Ein neuer
`OnsetEvent` (eigenständig neben `AlertEvent`, ADR-0011) trägt die Onset-Daten;
`AlertMessage.source != None` schaltet den Renderer auf den Onset-Zweig.

Diese Tests schlagen HEUTE fehl (RED), weil:
- AC-1..AC-5: `OnsetEvent` existiert noch nicht in
  `src/output/renderers/alert/model.py` (ImportError), und die vier Renderer haben
  keinen Onset-Zweig (AttributeError/AssertionError).
- AC-3: `AlertMessage.cooldown_display` existiert noch nicht.
- AC-6/AC-7: `src/outputs/radar_alert.py` existiert noch und wird noch genutzt.
- AC-8 (Regression Deviation) DARF GRÜN sein — der Deviation-Pfad existiert bereits
  und bleibt unverändert (source=None).

KEINE Mocks. Direkte Konstruktion der Dataclasses + echte Renderer-Aufrufe.

SPEC: docs/specs/modules/issue_919_radar_alert_canonical.md
"""
from __future__ import annotations

import os

import pytest


# GSM-7 Grundzeichensatz (3GPP TS 23.038) — für AC-5 Charset-Prüfung.
GSM7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ ÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)


def _make_onset_msg(*, is_convective: bool, onset_minutes: int,
                    onset_time: str = "14:35", km_from: float = 5.0,
                    km_to: float = 18.0, intensity_label: str = "leichter Regen",
                    source_label: str = "Radar (DWD)",
                    cooldown_display: str | None = "2 Stunden"):
    """Konstruiert ein Onset-`AlertMessage` direkt (ohne Service-Pfad)."""
    from src.output.renderers.alert.model import AlertMessage, OnsetEvent

    onset = OnsetEvent(
        onset_minutes=onset_minutes,
        onset_time=onset_time,
        km_from=km_from,
        km_to=km_to,
        is_convective=is_convective,
        intensity_label=intensity_label,
        source_label=source_label,
    )
    return AlertMessage(
        trip_short="GR20",
        stand_at="14:23",
        events=(onset,),
        source=source_label,
        cooldown_display=cooldown_display,
    )


# ---------------------------------------------------------------------------
# AC-1: Betreff Regen (nicht-konvektiv)
# ---------------------------------------------------------------------------

class TestAC1SubjectRegen:
    """AC-1: render_subject Onset Regen — 'Regen in <m> Min' + km-Spanne."""

    def test_ac1_render_subject_onset_regen(self):
        from src.output.renderers.alert.render import render_subject

        msg = _make_onset_msg(is_convective=False, onset_minutes=12,
                              km_from=5.0, km_to=18.0)
        subj = render_subject(msg)

        assert "km 5" in subj, f"km-Spanne fehlt: {subj!r}"
        assert "Regen in 12 Min" in subj, f"Onset-Text fehlt: {subj!r}"
        assert "%" not in subj, f"Δ-Prozent darf nicht vorkommen: {subj!r}"
        assert "→" not in subj, f"Wert-Pfeil darf nicht vorkommen: {subj!r}"


# ---------------------------------------------------------------------------
# AC-2: Betreff Gewitter (konvektiv)
# ---------------------------------------------------------------------------

class TestAC2SubjectGewitter:
    """AC-2: render_subject Onset Gewitter — 'Gewitter in <m> Min', kein 'Regen'."""

    def test_ac2_render_subject_onset_gewitter(self):
        from src.output.renderers.alert.render import render_subject

        msg = _make_onset_msg(is_convective=True, onset_minutes=8)
        subj = render_subject(msg)

        assert "Gewitter in 8 Min" in subj, f"Gewitter-Onset fehlt: {subj!r}"
        assert "Regen" not in subj, f"'Regen' darf bei Gewitter nicht vorkommen: {subj!r}"


# ---------------------------------------------------------------------------
# AC-3: Email-Body mit Quelle + Cooldown
# ---------------------------------------------------------------------------

class TestAC3EmailQuelleCooldown:
    """AC-3: render_email — HTML enthält Quelle, Plain enthält Cooldown-Text."""

    def test_ac3_render_email_onset_quelle_cooldown(self):
        from src.output.renderers.alert.render import render_email

        msg = _make_onset_msg(is_convective=False, onset_minutes=12,
                              source_label="Radar (DWD)", cooldown_display="2 Stunden")
        html, plain = render_email(msg)

        assert "Radar (DWD)" in html, f"Quelle fehlt im HTML-Part: {html!r}"
        assert "höchstens einmal in" in plain, f"Cooldown-Text fehlt im Plain-Part: {plain!r}"
        assert "2 Stunden" in plain, f"cooldown_display fehlt im Plain-Part: {plain!r}"


# ---------------------------------------------------------------------------
# AC-4: Telegram mit Onset-Zeit + Quelle
# ---------------------------------------------------------------------------

class TestAC4Telegram:
    """AC-4: render_telegram — enthält HH:MM-Onset-Zeit und source_label."""

    def test_ac4_render_telegram_onset(self):
        from src.output.renderers.alert.render import render_telegram

        msg = _make_onset_msg(is_convective=False, onset_minutes=12,
                              onset_time="14:35", source_label="Radar (DWD)")
        text = render_telegram(msg)

        assert "14:35" in text, f"Onset-Uhrzeit fehlt: {text!r}"
        assert "Radar (DWD)" in text, f"Quelle fehlt: {text!r}"


# ---------------------------------------------------------------------------
# AC-5: SMS Onset-Token
# ---------------------------------------------------------------------------

class TestAC5SMS:
    """AC-5: render_sms — '!'-Onset-Token, ≤140 Zeichen, GSM-7-only."""

    def test_ac5_render_sms_onset_regen_token(self):
        from src.output.renderers.alert.render import render_sms

        msg = _make_onset_msg(is_convective=False, onset_minutes=12)
        sms = render_sms(msg)

        assert "R!12" in sms, f"Regen-Onset-Token 'R!12' fehlt: {sms!r}"
        assert len(sms) <= 140, f"SMS zu lang ({len(sms)}): {sms!r}"
        assert set(sms) <= GSM7_BASIC, (
            f"Nicht-GSM-7-Zeichen: {set(sms) - GSM7_BASIC!r} in {sms!r}"
        )

    def test_ac5_render_sms_onset_gewitter_token(self):
        from src.output.renderers.alert.render import render_sms

        msg = _make_onset_msg(is_convective=True, onset_minutes=8)
        sms = render_sms(msg)

        assert "TH!8" in sms, f"Gewitter-Onset-Token 'TH!8' fehlt: {sms!r}"
        assert len(sms) <= 140, f"SMS zu lang ({len(sms)}): {sms!r}"
        assert set(sms) <= GSM7_BASIC, (
            f"Nicht-GSM-7-Zeichen: {set(sms) - GSM7_BASIC!r} in {sms!r}"
        )


# ---------------------------------------------------------------------------
# AC-6 / AC-7: radar_alert.py gelöscht / nicht mehr genutzt
# ---------------------------------------------------------------------------

class TestAC6And7RadarAlertDeleted:
    """AC-6/AC-7: src/outputs/radar_alert.py existiert nach Migration nicht mehr."""

    def test_ac7_radar_alert_py_not_tracked(self):
        """git ls-files src/outputs/radar_alert.py liefert keinen Treffer."""
        import subprocess

        result = subprocess.run(
            ["git", "ls-files", "src/outputs/radar_alert.py"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        )
        assert result.stdout.strip() == "", (
            "src/outputs/radar_alert.py ist noch git-getrackt — muss nach "
            f"Migration gelöscht sein. git ls-files: {result.stdout!r}"
        )

    def test_ac6_build_radar_alert_helpers_gone(self):
        """Die alten build_radar_alert_*-Builder existieren nicht mehr (Modul weg)."""
        with pytest.raises(ImportError):
            from src.outputs.radar_alert import build_radar_alert_subject  # noqa: F401


# ---------------------------------------------------------------------------
# AC-8: Regression — Deviation-Format unverändert (DARF GRÜN sein)
# ---------------------------------------------------------------------------

class TestAC8DeviationRegression:
    """AC-8: Deviation-Pfad (source=None) bleibt unverändert."""

    def _make_deviation_msg(self):
        from src.output.renderers.alert.model import AlertEvent, AlertMessage

        event = AlertEvent(
            metric_id="gust",
            value_from=50.0,
            value_to=80.0,
            threshold=60.0,
            cmp="über",
            occurred_at="12:00",
            km_from=5.0,
            km_to=18.0,
        )
        return AlertMessage(
            trip_short="GR20",
            stand_at="10:00",
            events=(event,),
            source=None,
        )

    def test_ac8_deviation_subject_unveraendert(self):
        """Deviation-Betreff trägt km-Spanne und Wert-Pfeil (altes Format)."""
        from src.output.renderers.alert.render import render_subject

        msg = self._make_deviation_msg()
        subj = render_subject(msg)

        assert "[GR20]" in subj, f"Trip-Klammer fehlt: {subj!r}"
        assert "km 5" in subj, f"km-Spanne fehlt: {subj!r}"
        assert "→" in subj, f"Deviation-Wert-Pfeil fehlt: {subj!r}"
        assert "Regen in" not in subj, f"Onset-Text darf bei Deviation nicht vorkommen: {subj!r}"

    def test_ac8_deviation_all_four_renderers_run(self):
        """Alle vier Renderer liefern für Deviation weiterhin Ausgaben."""
        from src.output.renderers.alert.render import (
            render_email, render_sms, render_subject, render_telegram,
        )

        msg = self._make_deviation_msg()

        assert render_subject(msg)
        html, plain = render_email(msg)
        assert html and plain
        assert render_telegram(msg)
        sms = render_sms(msg)
        assert sms and len(sms) <= 140
