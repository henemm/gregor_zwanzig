"""
RED/GREEN-Tests fuer Issue #957 — render_email() uebernimmt die echte HTML-Struktur
der Design-Vorlage (docs/design-requests/alert-mail-vorschlaege/..., Zeilen 156-247),
nicht nur Farben/Schrift (#952 hat das nur oberflaechlich nachgebaut).

Spec: docs/specs/fast/fix-957-alert-mail-design-literal.md

Alles echte Aufrufe der kanonischen Renderer/Katalog-Funktionen, keine Mocks.
KEINE Beispielwerte aus der Mockup-Datei (1230/620/800/KHW 403 etc.) werden hier
als erwartete Literale geprueft -- nur die STRUKTUR (Anzahl Zeilen, Marker-Strings,
Werte die aus den Fixture-Feldern berechnet werden).
"""
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "src")

from output.renderers.alert.model import AlertEvent, AlertMessage
from output.renderers.alert.render import render_email


def _single_event_msg(value_from=1230.0, value_to=620.0, threshold=800.0):
    event = AlertEvent(
        metric_id="cape", value_from=value_from, value_to=value_to,
        threshold=threshold, cmp="über", occurred_at="09:00",
        km_from=0.0, km_to=1.8,
    )
    return AlertMessage(trip_short="TEST", stand_at="09:30", events=(event,), source=None)


def _multi_event_msg():
    # Issue #958-Umstellung: `threshold` ist die Δ-Auslöseschwelle. Fixture Δ-realistisch
    # kalibriert — e1/e2 über Schwelle (|Δ| >= threshold), e3 unter Schwelle (|Δ| < threshold).
    e1 = AlertEvent(metric_id="gust", value_from=30.0, value_to=80.0, threshold=40.0,
                     cmp="über", occurred_at="11:00", km_from=0.0, km_to=4.0)
    e2 = AlertEvent(metric_id="thunder", value_from=30.0, value_to=90.0, threshold=40.0,
                     cmp="über", occurred_at="11:30", km_from=1.0, km_to=4.0)
    e3 = AlertEvent(metric_id="rain_probability", value_from=70.0, value_to=90.0,
                     threshold=95.0, cmp="über", occurred_at=None, km_from=0.0, km_to=3.0)
    return AlertMessage(trip_short="TEST", stand_at="14:30", events=(e1, e2, e3), source=None)


class TestSingleEventVerdictAndDatablock:
    def test_verdict_contains_percent_and_schwelle(self):
        html, _ = render_email(_single_event_msg())
        assert "%" in html, f"Kein Δ%-Zeichen im Verdikt: {html!r}"
        assert "Schwelle" in html, f"'Schwelle'-Bezug fehlt im Verdikt: {html!r}"

    def test_verdict_delta_matches_computed_value(self):
        """Δ% im Verdikt muss aus delta_pct() berechnet sein, kein Literal."""
        from output.renderers.alert.model import delta_pct
        msg = _single_event_msg(value_from=1000.0, value_to=400.0, threshold=500.0)
        e = msg.events[0]
        expected = delta_pct(e)
        html, plain = render_email(msg)
        assert f"{expected:+d} %" in html, (
            f"Berechnetes Δ% ({expected:+d} %) fehlt im HTML: {html!r}"
        )
        assert f"{expected:+d} %" in plain

    def test_datablock_has_three_rows(self):
        """3 separate Datenzeilen: Wert-Vergleich, Schwellwert-Status, Wo & wann."""
        html, plain = render_email(_single_event_msg())
        # 3 <div ...>...</div>-Zeilen im Datenblock-Container (rows-Markup).
        mono_count = html.count("font-family:'JetBrains Mono'")
        assert mono_count == 3, (
            f"Erwartet 3 Datenzeilen (Mono-Font), gefunden: {mono_count}: {html!r}"
        )
        assert "Wo &amp; wann" in html, f"'Wo & wann' (escaped) fehlt im HTML: {html!r}"
        assert "Wo & wann" in plain

    def test_wo_und_wann_row_contains_km_and_time(self):
        msg = _single_event_msg()
        html, plain = render_email(msg)
        assert "km 0" in html, f"km-Angabe fehlt in Wo & wann: {html!r}"
        assert "09:00" in html, f"occurred_at fehlt in Wo & wann: {html!r}"
        assert "km 0" in plain and "09:00" in plain

    def test_threshold_row_has_check_or_cross_mark(self):
        """Schwellwert-Zeile zeigt ✓ (unter Schwelle) oder ✗ (über Schwelle)."""
        under = render_email(_single_event_msg(value_from=1230.0, value_to=620.0, threshold=800.0))[0]
        assert "✓" in under, f"✓-Marker fehlt bei unter-Schwelle-Event: {under!r}"

        # Issue #958: über Schwelle = |Δ| >= threshold. |950-100|=850 >= 800 → ✗.
        over = render_email(_single_event_msg(value_from=100.0, value_to=950.0, threshold=800.0))[0]
        assert "✗" in over, f"✗-Marker fehlt bei über-Schwelle-Event: {over!r}"

    def test_footer_has_no_km_single_event(self):
        """1-Event-Footer OHNE km (steht schon in Wo & wann-Zeile) -- kein Doppel-km."""
        _, plain = render_email(_single_event_msg())
        assert plain.count("km") == 1, f"'km' soll genau 1x vorkommen: {plain!r}"


class TestMultiEventVerdictAndDatablock:
    def test_verdict_says_n_ueber_schwelle(self):
        # Issue #981: Zähler filtert auf über-Schwelle-Events. Fixture hat 2 über
        # (e1/e2) + 1 unter (e3) → "2 über Schwelle" (nicht 3).
        html, plain = render_email(_multi_event_msg())
        assert "2 über Schwelle" in html
        assert "2 über Schwelle" in plain

    def test_one_row_per_event(self):
        msg = _multi_event_msg()
        html, _ = render_email(msg)
        assert html.count("font-family:'JetBrains Mono'") == len(msg.events)

    def test_dampened_row_for_under_threshold_event(self):
        """Event unter Schwelle bekommt gedämpfte Farbe (G_INK_MUTED), nicht G_DANGER."""
        from output.renderers.email.design_tokens import G_INK_MUTED
        html, _ = render_email(_multi_event_msg())
        assert G_INK_MUTED in html

    def test_footer_contains_km_multi_event(self):
        _, plain = render_email(_multi_event_msg())
        assert "km 0" in plain, f"km-Spanne fehlt im Footer (Multi-Event): {plain!r}"


class TestNoRegressionOfOldFixes:
    """Regressionsschutz gegen die alten #952-Fehler (keine hartcodierten Werte etc.)."""

    def test_no_hardcoded_hex_colors(self):
        html, _ = render_email(_single_event_msg())
        for old_hex in ("#c0392b", "#2e7d32", "#555"):
            assert old_hex not in html, f"Alter hartcodierter Hex-Wert {old_hex} noch vorhanden"

    def test_no_trailing_zero_noise(self):
        _, plain = render_email(_single_event_msg())
        assert "1230.0" not in plain and "620.0" not in plain

    def test_no_double_km(self):
        _, plain = render_email(_multi_event_msg())
        assert "km km" not in plain

    def test_no_langform_only_kuerzel(self):
        html, _ = render_email(_single_event_msg())
        assert "Gewitterenergie" not in html

    def test_no_interpretation_words_in_h1(self):
        html, plain = render_email(_single_event_msg())
        for word in ("halbiert", "verdoppelt"):
            assert word not in html.lower()
            assert word not in plain.lower()

    def test_no_example_literals_from_mockup_hardcoded_in_source(self):
        """Werte muessen aus den Fixture-Feldern berechnet sein, nicht als Literal
        im Renderer stehen -- Nachweis: andere Eingabewerte -> andere Ausgabewerte."""
        html_a, _ = render_email(_single_event_msg(value_from=1230.0, value_to=620.0, threshold=800.0))
        html_b, _ = render_email(_single_event_msg(value_from=500.0, value_to=100.0, threshold=200.0))
        assert html_a != html_b
        assert "500 J/kg" in html_b
        assert "1230 J/kg" not in html_b
