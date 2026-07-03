"""TDD RED — Issue #978: lesbare Multi-Metrik-Zeile im Deviation-Alert.

Die Multi-Metrik-Zeile (E-Mail-Datenblock, Betreff-Top-3, Telegram-Zweitzeile)
wiederholt heute die Einheit bis zu 3x pro Zeile und zeigt ",0"-Rauschen bei
glatten Werten. Diese Suite bringt render_subject()/render_email()/
render_telegram() im Multi-Metrik-Zweig auf das SOLL-Format der Design-Vorlage
(docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail
Vorschläge.html:200-290): Einheit genau einmal, Schwelle ohne Einheit
(ausser bei %), glatte Werte ganzzahlig, Tausender-Punkt erhalten.

Spec: docs/specs/modules/issue_978_deviation_line_readability.md

Alles echte Renderer-Aufrufe (render_subject/render_email/render_telegram),
AlertEvent/AlertMessage direkt konstruiert wie in test_957_alert_mail_literal_
structure.py::_multi_event_msg() und test_952_onset_alert_fidelity.py. Keine
Mocks, keine Datei-Inhalts-Checks ausserhalb der Renderer-Rückgabewerte.

AC-5 (Regressionsschutz: Einzel-Metrik-Betreff/-Datenblock/-Verdikt, Onset-
Zweig, format_metric_value() für alle anderen Aufrufer bleiben unverändert)
wird NICHT hier dupliziert, sondern von den bestehenden Suiten abgedeckt:
tests/tdd/test_952_alert_mail_design_fidelity.py,
tests/tdd/test_952_onset_alert_fidelity.py::TestAC8RendererParity,
tests/tdd/test_957_alert_mail_literal_structure.py::TestSingleEventVerdictAndDatablock.

Bekannte Katalog-Randbedingung (nicht Teil dieser RED-Tests, aber
GREEN-relevant): `metric_catalog.get_metric("thunder").unit == ""` (nicht
"%"), obwohl die Design-Vorlage Gewitter-Werte mit "%" zeigt
(Zeilen 208/220-233/281). AC-3/AC-4 unten prüfen daher exakt die von der
Spec vorgegebenen Literale inkl. "Gewitter 55%" — die GREEN-Phase muss diesen
Katalog/Vorlage-Widerspruch auflösen (z.B. Sonderfall für metric_id=="thunder"
im neuen `_num()`-Helper), da ein reiner `unit=="%"`-Check laut aktuellem
Katalogstand nicht greift.
"""
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "src")

from output.renderers.alert.model import AlertEvent, AlertMessage
from output.renderers.alert.render import render_email, render_subject, render_telegram


def _multi_msg() -> AlertMessage:
    """3-Event-Fixture nach Design-Vorlage (Gregor 20 - Alert Mail
    Vorschläge.html:220-233 Datenblock, :208 Betreff, :281 Telegram), alle
    ÜBER Schwelle. Issue #958: `threshold` ist die Δ-Auslöseschwelle — Werte
    Δ-realistisch kalibriert (|Δ| >= threshold), severity-Ordnung unverändert
    (Niedersch > Gewitter > Böen): Böen 20→80 (Schwelle 40, Δ=60),
    Gewitter 20→90 (Schwelle 40, Δ=70), Niedersch 2→30 (Schwelle 10, Δ=28)."""
    e_gust = AlertEvent(
        metric_id="gust", value_from=20.0, value_to=80.0, threshold=40.0,
        cmp="über", occurred_at="11:00", km_from=0.0, km_to=4.0,
    )
    e_thunder = AlertEvent(
        metric_id="thunder", value_from=20.0, value_to=90.0, threshold=40.0,
        cmp="über", occurred_at="11:30", km_from=1.0, km_to=4.0,
    )
    e_precip = AlertEvent(
        metric_id="precipitation", value_from=2.0, value_to=30.0, threshold=10.0,
        cmp="über", occurred_at="12:00", km_from=0.0, km_to=3.0,
    )
    return AlertMessage(
        trip_short="KHW 403", stand_at="14:30",
        events=(e_gust, e_thunder, e_precip), source=None,
    )


def _decimal_precip_msg() -> AlertMessage:
    """precipitation mit echtem Dezimalwert (0,4 mm) + zweitem Event, damit
    der Multi-Zweig (>=2 Events) greift statt des Einzel-Metrik-Zweigs."""
    e_decimal = AlertEvent(
        metric_id="precipitation", value_from=0.1, value_to=0.4, threshold=0.2,
        cmp="über", occurred_at="10:00", km_from=0.0, km_to=2.0,
    )
    e_gust = AlertEvent(
        metric_id="gust", value_from=35.0, value_to=52.0, threshold=50.0,
        cmp="über", occurred_at="11:00", km_from=0.0, km_to=4.0,
    )
    return AlertMessage(
        trip_short="TEST", stand_at="14:30", events=(e_decimal, e_gust), source=None,
    )


def _thousand_visibility_decimal_msg() -> AlertMessage:
    """visibility-artiges Fixture (decimals=1) mit echtem Dezimal-Rest
    >=1000, damit F002 (Tausender-Punkt im Dezimal-Zweig von _num()) greift."""
    e_visibility = AlertEvent(
        metric_id="visibility", value_from=800.0, value_to=1234.5, threshold=1000.0,
        cmp="unter", occurred_at="09:00", km_from=0.0, km_to=1.8,
    )
    e_gust = AlertEvent(
        metric_id="gust", value_from=35.0, value_to=52.0, threshold=50.0,
        cmp="über", occurred_at="11:00", km_from=0.0, km_to=4.0,
    )
    return AlertMessage(
        trip_short="TEST", stand_at="14:30", events=(e_visibility, e_gust), source=None,
    )


def _thousand_visibility_glatt_msg() -> AlertMessage:
    """visibility-artiges Fixture (decimals=1), das nach Rundung glatt bei
    genau 1000 landet (999.96 -> 1000.0), Gegenprobe zu F002."""
    e_visibility = AlertEvent(
        metric_id="visibility", value_from=800.0, value_to=999.96, threshold=900.0,
        cmp="unter", occurred_at="09:00", km_from=0.0, km_to=1.8,
    )
    e_gust = AlertEvent(
        metric_id="gust", value_from=35.0, value_to=52.0, threshold=50.0,
        cmp="über", occurred_at="11:00", km_from=0.0, km_to=4.0,
    )
    return AlertMessage(
        trip_short="TEST", stand_at="14:30", events=(e_visibility, e_gust), source=None,
    )


def _thousand_cape_msg() -> AlertMessage:
    """CAPE-artiges Tausender-Fixture (glatt, 1230 J/kg, nicht von
    format_metric_value() gehandhabte Einheit) + zweites Event für den
    Multi-Zweig."""
    e_cape = AlertEvent(
        metric_id="cape", value_from=800.0, value_to=1230.0, threshold=1000.0,
        cmp="über", occurred_at="09:00", km_from=0.0, km_to=1.8,
    )
    e_gust = AlertEvent(
        metric_id="gust", value_from=35.0, value_to=52.0, threshold=50.0,
        cmp="über", occurred_at="11:00", km_from=0.0, km_to=4.0,
    )
    return AlertMessage(
        trip_short="TEST", stand_at="14:30", events=(e_cape, e_gust), source=None,
    )


# ===========================================================================
# AC-1: E-Mail-Datenblock-Zeile — Einheit genau einmal, Schwelle ohne Einheit
# ===========================================================================


class TestAC1EmailMultiLineUnitOnce:
    def test_email_datablock_line_unit_once_and_threshold_without_unit(self):
        html, plain = render_email(_multi_msg())
        assert "Böen · Schwelle 40" in html, (
            f"Schwelle ohne Einheit fehlt (SOLL laut Design-Vorlage "
            f"Zeile 220): {html!r}"
        )
        assert "Böen · Schwelle 40" in plain
        assert "20 ↑ 80 km/h" in html, (
            f"Wertespanne mit Einheit genau einmal fehlt (SOLL laut Design-"
            f"Vorlage Zeile 221): {html!r}"
        )
        assert "20 ↑ 80 km/h" in plain
        assert "über" in html and "über" in plain
        assert html.count("km/h") == 1, (
            f"Einheit 'km/h' soll in der Böen-Zeile genau 1x vorkommen "
            f"(nicht 3x wie im Ist-Format): {html!r}"
        )
        assert plain.count("km/h") == 1, (
            f"Einheit 'km/h' soll in der Böen-Zeile genau 1x vorkommen: {plain!r}"
        )


# ===========================================================================
# AC-2: Rundung — glatte Werte ganzzahlig, echte Dezimalwerte mit Komma,
# Tausender-Punkt bleibt erhalten
# ===========================================================================


class TestAC2RoundingNoiseAndThousandSeparator:
    def test_glatt_value_has_no_trailing_zero_noise(self):
        html, plain = render_email(_multi_msg())
        assert "10,0" not in html, (
            f"',0'-Rauschen bei glattem Schwellwert (Niedersch-Schwelle 10 mm "
            f"ohne Rest): {html!r}"
        )
        assert "10,0" not in plain

    def test_real_decimal_value_keeps_one_decimal_with_comma(self):
        html, plain = render_email(_decimal_precip_msg())
        assert "0,4" in html, f"Echter Dezimalwert (0,4 mm) fehlt: {html!r}"
        assert "0,4" in plain

    def test_thousand_separator_preserved_for_large_glatt_value(self):
        html, plain = render_email(_thousand_cape_msg())
        assert "1.230" in html, (
            f"Tausender-Punkt-Trenner fehlt für glatten Grosswert "
            f"(1230 J/kg → '1.230'): {html!r}"
        )
        assert "1.230" in plain

    def test_thousand_separator_preserved_in_decimal_branch(self):
        """Issue #978 Finding F002: auch mit verbleibender Nachkommastelle
        muss der Ganzzahl-Teil den Tausender-Punkt bekommen."""
        html, plain = render_email(_thousand_visibility_decimal_msg())
        assert "1.234,5" in html, (
            f"Tausender-Punkt fehlt im Dezimal-Zweig (1234.5 → '1.234,5'): "
            f"{html!r}"
        )
        assert "1.234,5" in plain

    def test_thousand_separator_glatt_after_rounding(self):
        """Gegenprobe: 999.96 rundet mit decimals=1 glatt auf 1000.0 ->
        Integer-Zweig, weiterhin Tausender-Punkt ('1.000')."""
        html, plain = render_email(_thousand_visibility_glatt_msg())
        assert "1.000" in html, (
            f"Tausender-Punkt fehlt nach Rundung auf glatten Grosswert "
            f"(999.96 → '1.000'): {html!r}"
        )
        assert "1.000" in plain


# ===========================================================================
# AC-3: Betreff-Top-3 — nur Zahl, % klebt am Wert
# ===========================================================================


class TestAC3SubjectTop3JustNumbers:
    def test_subject_top3_exact_literal(self):
        subject = render_subject(_multi_msg())
        assert "Niedersch 30, Gewitter 90%, Böen 80" in subject, (
            f"Betreff-Top3 nicht im SOLL-Format (PO-Nachtrag 2026-07-02: "
            f"kritischster zuerst, severity-absteigend): {subject!r}"
        )


# ===========================================================================
# AC-4: Telegram-Multi-Zeile — kein Einheiten-Text ausser %, kein 'Schwelle'
# ===========================================================================


class TestAC4TelegramMultiLineNoUnitsExceptPercent:
    def test_telegram_multiline_exact_literal(self):
        tg = render_telegram(_multi_msg())
        assert "Niedersch 2→30 · Gewitter 20→90% · Böen 20→80" in tg, (
            f"Telegram-Multi-Zeile nicht im SOLL-Format (PO-Nachtrag "
            f"2026-07-02: kritischster zuerst, severity-absteigend): {tg!r}"
        )

    def test_metric_line_has_no_schwelle_word(self):
        """Der Schwellen-Bezug steht in der fetten Kopfzeile ('N über
        Schwelle'), nicht in der Metrik-Zeile darunter."""
        tg = render_telegram(_multi_msg())
        lines = tg.split("\n")
        metric_line = next((l for l in lines if l.startswith("Niedersch")), None)
        assert metric_line is not None, f"Metrik-Zeile fehlt: {tg!r}"
        assert "Schwelle" not in metric_line, (
            f"'Schwelle'-Text darf nicht in der Metrik-Zeile stehen "
            f"(nur in der fetten Kopfzeile): {metric_line!r}"
        )


# ===========================================================================
# Kanal-Konsistenz: Betreff-Top3, E-Mail-Datenblock und Telegram-Zeile
# nutzen dieselbe (severity-absteigende) Kürzel-Reihenfolge
# ===========================================================================


class TestChannelOrderConsistency:
    def test_subject_email_telegram_share_same_severity_order(self):
        import re

        msg = _multi_msg()
        expected_order = ["Niedersch", "Gewitter", "Böen"]

        subject = render_subject(msg)
        subject_order = re.findall(r"(Niedersch|Gewitter|Böen) \d", subject)
        assert subject_order == expected_order, (
            f"Betreff-Reihenfolge nicht severity-absteigend: {subject_order!r} "
            f"(erwartet {expected_order!r}) — {subject!r}"
        )

        html, plain = render_email(msg)
        email_order = re.findall(r"(Niedersch|Gewitter|Böen) · Schwelle", plain)
        assert email_order == expected_order, (
            f"E-Mail-Datenblock-Reihenfolge nicht severity-absteigend: "
            f"{email_order!r} (erwartet {expected_order!r}) — {plain!r}"
        )
        html_order = re.findall(r"(Niedersch|Gewitter|Böen) · Schwelle", html)
        assert html_order == expected_order

        tg = render_telegram(msg)
        tg_order = re.findall(r"(Niedersch|Gewitter|Böen) \d", tg)
        assert tg_order == expected_order, (
            f"Telegram-Reihenfolge nicht severity-absteigend: {tg_order!r} "
            f"(erwartet {expected_order!r}) — {tg!r}"
        )


# ===========================================================================
# Adversary-Finding F001: unter-Schwelle-Events bleiben gedämpft zuletzt, auch
# bei höchster severity (Spec-Nachtrag, PO 2026-07-02)
# ===========================================================================


def _mixed_over_under_msg() -> AlertMessage:
    """3 über-Schwelle-Events (unterschiedliche severity) + 1 unter-Schwelle-
    Event mit hoher abs(severity) — das unter-Schwelle-Event muss trotzdem
    gedämpft zuletzt erscheinen (Adversary-Finding F001). Issue #958: Werte
    Δ-realistisch — Böen 30→80/Δ=50, Gewitter 10→55/Δ=45, Regen% 10→55/Δ=45
    (alle über Schwelle 40); Niedersch 20→2/Δ=18 < Schwelle 25 (unter,
    abs(severity)=0.92)."""
    e_gust = AlertEvent(
        metric_id="gust", value_from=30.0, value_to=80.0, threshold=40.0,
        cmp="über", occurred_at="11:00", km_from=0.0, km_to=4.0,
    )
    e_thunder = AlertEvent(
        metric_id="thunder", value_from=10.0, value_to=55.0, threshold=40.0,
        cmp="über", occurred_at="11:30", km_from=1.0, km_to=4.0,
    )
    e_rain = AlertEvent(
        metric_id="rain_probability", value_from=10.0, value_to=55.0, threshold=40.0,
        cmp="über", occurred_at="12:00", km_from=0.0, km_to=3.0,
    )
    e_precip = AlertEvent(
        metric_id="precipitation", value_from=20.0, value_to=2.0, threshold=25.0,
        cmp="über", occurred_at="12:30", km_from=0.0, km_to=3.0,
    )
    return AlertMessage(
        trip_short="KHW 403", stand_at="14:30",
        events=(e_gust, e_thunder, e_rain, e_precip), source=None,
    )


class TestMixedOverUnderOrdering:
    """unter-Schwelle bleibt gedämpft zuletzt, auch wenn seine relative
    Abweichung (severity) am höchsten ist."""

    def test_email_plain_order_under_threshold_last(self):
        import re

        _, plain = render_email(_mixed_over_under_msg())
        # Issue #980: unter-Schwelle-Zeilen tragen das Label "· unter Schwelle"
        # (ohne Schwellen-Zahl), über-Schwelle "· Schwelle N" — beide erfassen.
        order = re.findall(r"(Niedersch|Gewitter|Regen%|Böen) · (?:unter )?Schwelle", plain)
        assert order == ["Böen", "Gewitter", "Regen%", "Niedersch"], (
            f"unter-Schwelle-Event (Niedersch) muss trotz hoher abs(severity) "
            f"gedämpft zuletzt stehen: {order!r} — {plain!r}"
        )

    def test_telegram_order_under_threshold_last(self):
        import re

        tg = render_telegram(_mixed_over_under_msg())
        order = re.findall(r"(Niedersch|Gewitter|Regen%|Böen) \d", tg)
        assert order == ["Böen", "Gewitter", "Regen%", "Niedersch"], (
            f"Telegram-Reihenfolge muss unter-Schwelle-Event zuletzt zeigen: "
            f"{order!r} — {tg!r}"
        )

    def test_subject_top3_excludes_under_threshold_event(self):
        subject = render_subject(_mixed_over_under_msg())
        assert "Böen 80, Gewitter 55%, Regen% 55%" in subject, (
            f"Top-3 muss die drei über-Schwelle-Events severity-absteigend "
            f"zeigen: {subject!r}"
        )
        assert "Niedersch 2" not in subject, (
            f"unter-Schwelle-Event (höchste severity) darf NICHT im Top-3 "
            f"landen, da es durch die neue Sortierregel ans Ende faellt "
            f"(Zaehler-Inkonsistenz '4 ueber Schwelle' bleibt unkorrigiert, "
            f"das ist Issue #981, hier nicht zu fixen): {subject!r}"
        )


# ===========================================================================
# AC-6: HTML/Plain-Strukturgleichheit
# ===========================================================================


class TestAC6HtmlPlainStructuralParity:
    def test_html_and_plain_share_same_kuerzel_schwelle_content(self):
        html, plain = render_email(_multi_msg())
        for literal in ("Böen · Schwelle 40", "20 ↑ 80 km/h"):
            assert literal in html, f"{literal!r} fehlt im HTML: {html!r}"
            assert literal in plain, f"{literal!r} fehlt im Plain-Text: {plain!r}"

    def test_plain_text_has_no_html_tags(self):
        _, plain = render_email(_multi_msg())
        assert "<" not in plain and ">" not in plain, (
            f"HTML-Tags im Plain-Text gefunden: {plain!r}"
        )
