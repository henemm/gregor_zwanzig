"""
RED-Tests fuer Issue #952 — Deviation-Alert-Renderer weicht von #914-ACs (C3/C6)
und der Claude-Design-Vorlage ab.

Spec: docs/specs/modules/fix_952_alert_mail_design_fidelity.md (AC-1 bis AC-5).
AC-6 (Bestandsschutz Onset/Nowcast + Legacy-Shim) ist reiner Regressionsnachweis
auf bestehende Tests, kein neuer Test hier.

Alles echte Aufrufe der kanonischen Renderer/Katalog-Funktionen, keine Mocks.
"""
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "src")

from app.metric_catalog import format_metric_value
from output.renderers.alert.model import AlertEvent, AlertMessage
from output.renderers.alert.render import (
    _val, render_email, render_subject, render_telegram,
)


def _cape_msg(value_from=1230.0, value_to=620.0, threshold=800.0):
    event = AlertEvent(
        metric_id="cape", value_from=value_from, value_to=value_to,
        threshold=threshold, cmp="über", occurred_at="09:00",
        km_from=0.0, km_to=1.8,
    )
    return AlertMessage(trip_short="KHW 403", stand_at="09:30", events=(event,), source=None)


class TestAC1KuerzelStattLangform:
    def test_subject_shows_short_label_not_langform(self):
        subj = render_subject(_cape_msg())
        assert "CAPE" in subj, f"Kürzel 'CAPE' fehlt im Betreff: {subj!r}"
        assert "Gewitterenergie" not in subj, f"Langform noch im Betreff: {subj!r}"

    def test_email_shows_short_label_not_langform(self):
        html, plain = render_email(_cape_msg())
        assert "Gewitterenergie" not in html, f"Langform noch im E-Mail-HTML: {html!r}"
        assert "Gewitterenergie" not in plain, f"Langform noch im Plain-Text: {plain!r}"
        assert "CAPE" in plain, f"Kürzel 'CAPE' fehlt im Plain-Text: {plain!r}"

    def test_telegram_shows_short_label_not_langform(self):
        tg = render_telegram(_cape_msg())
        assert "CAPE" in tg, f"Kürzel 'CAPE' fehlt in Telegram: {tg!r}"
        assert "Gewitterenergie" not in tg, f"Langform noch in Telegram: {tg!r}"


class TestAC2RundungOhneKommaRauschen:
    def test_format_metric_value_cape_no_trailing_zero(self):
        # CAPE (J/kg) wird NICHT von format_metric_value() selbst mit Einheit
        # formatiert (geteilte Katalog-Funktion bleibt fuer andere Aufrufer wie
        # format_change_line unveraendert, Issue #952 Finding F001) — der
        # Alert-Renderer haengt die Einheit lokal in _val() an.
        event = AlertEvent(
            metric_id="cape", value_from=1230.0, value_to=620.0,
            threshold=800.0, cmp="ueber", occurred_at="09:00",
            km_from=0.0, km_to=1.8,
        )
        assert _val(event, 1230.0) == "1230 J/kg"
        assert _val(event, 620.0) == "620 J/kg"

    def test_subject_values_have_no_trailing_zero(self):
        subj = render_subject(_cape_msg())
        assert "1230.0" not in subj, f"Unrunde Zahl im Betreff: {subj!r}"
        assert "620.0" not in subj, f"Unrunde Zahl im Betreff: {subj!r}"
        assert "1230" in subj and "620" in subj, f"Werte fehlen im Betreff: {subj!r}"

    def test_format_metric_value_existing_units_unchanged(self):
        """Regressionsschutz: bereits gehandhabte Einheiten bleiben exakt gleich."""
        assert format_metric_value("km/h", 52.0) == "52 km/h"
        assert format_metric_value("%", 55.0) == "55 %"
        assert format_metric_value("mm", 14.0) == "14,0 mm"
        assert format_metric_value("°C", 12.3) == "12,3 °C"
        assert format_metric_value("m", 1200.0) == "1.200 m"
        assert format_metric_value("hPa", 1013.0) == "1.013 hPa"


class TestAC3KeinDoppeltesKm:
    def test_subject_km_range_single_unit(self):
        subj = render_subject(_cape_msg())
        assert "km 0–1.8" in subj or "km 0–2" in subj, f"km-Bereich fehlt/falsch: {subj!r}"
        assert subj.count("km") == 1, f"'km' erscheint nicht genau einmal: {subj!r}"

    def test_email_km_range_single_unit(self):
        html, plain = render_email(_cape_msg())
        assert plain.count("km") == 1, f"'km' erscheint nicht genau einmal im Plain-Text: {plain!r}"


class TestAC4DesignTokensImHtml:
    def test_email_html_uses_design_tokens_not_hardcoded_hex(self):
        from output.renderers.email.design_tokens import G_DANGER, G_SUCCESS

        html, _ = render_email(_cape_msg())  # 620 < 800 Schwelle, cmp="über" -> unter Schwelle -> G_SUCCESS erwartet
        assert "#c0392b" not in html, "Alter hartcodierter Danger-Hex-Wert noch vorhanden"
        assert "#2e7d32" not in html, "Alter hartcodierter Success-Hex-Wert noch vorhanden"
        assert G_SUCCESS in html or G_DANGER in html, (
            f"Kein Design-Token-Hex-Wert im HTML gefunden: {html!r}"
        )

    def test_email_html_no_generic_sans_serif(self):
        html, _ = render_email(_cape_msg())
        assert "font-family:sans-serif" not in html, "Generische Schrift statt Marken-Font"


class TestAC5PlainTextBleibtTextbasiert:
    def test_plain_text_has_no_html_tags(self):
        _, plain = render_email(_cape_msg())
        assert "<" not in plain and ">" not in plain, f"HTML-Tags im Plain-Text: {plain!r}"

    def test_plain_text_has_short_label_and_rounded_value(self):
        _, plain = render_email(_cape_msg())
        assert "CAPE" in plain
        assert "1230.0" not in plain and "620.0" not in plain
