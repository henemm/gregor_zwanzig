"""TDD RED — Issue #1948 Scheibe S6: Die berechnete prozentuale Änderung
(`delta_pct()`) verschwindet vollständig aus dem Änderungs-Alarm. Prozent
als EINHEIT (z. B. Regenwahrscheinlichkeit) bleibt unangetastet — das ist
die Trennlinie, die AC-10 bewacht.

Spec: docs/specs/modules/fix_1948_s6_alarm_stufenwort.md (AC-8, AC-9, AC-10).
Kontext: docs/context/feat-1948-s6-telegram-paritaet.md.

PO-Begründung (wörtlich): "Das versteht niemand und stiftet keinen Nutzen."

Alles echte Renderer-Aufrufe (render_email) mit echten AlertEvent/
AlertMessage-Objekten. Kein Mock, keine Dateiinhalt-Checks.

Alle Tests hier müssen vor der Implementierung ROT sein (kein
Regressionswächter-Ausnahmefall in dieser Datei).
"""
from __future__ import annotations

import re

from output.renderers.alert.model import AlertEvent, AlertMessage
from output.renderers.alert.render import render_email

# Erfasst berechnete Prozent-Änderungen wie "+50 %", "+50%", "-60 %", "−60 %"
# -- NICHT die reine Einheit ("90 %" ohne Vorzeichen).
_COMPUTED_PERCENT_CHANGE = re.compile(r"[+\-−]\d+\s?%")


def _single_event_msg(
    metric_id: str, value_from: float, value_to: float, threshold: float,
    *, cmp: str = "über", occurred_at: str | None = "09:00",
    km_from: float = 0.0, km_to: float = 4.0,
    trip_short: str = "KHW 403", stand_at: str = "09:30",
) -> AlertMessage:
    e = AlertEvent(
        metric_id=metric_id, value_from=value_from, value_to=value_to,
        threshold=threshold, cmp=cmp, occurred_at=occurred_at,
        km_from=km_from, km_to=km_to,
    )
    return AlertMessage(trip_short=trip_short, stand_at=stand_at, events=(e,), source=None)


def _first_plain_data_line(plain: str) -> str:
    return plain.split("\n")[4]


# ===========================================================================
# AC-8: keine berechnete Prozent-Änderung mehr in H1/Badge/Datenzeile
# ===========================================================================

def test_ac8_email_enthaelt_keine_berechnete_prozentaenderung():
    """AC-8: GIVEN ein Änderungs-Alarm mit einem einzelnen Ereignis
    beliebiger Metrik (hier: Böen), WHEN E-Mail HTML und Klartext gerendert
    werden, THEN enthält weder die Überschrift noch der Badge noch die
    Datenzeile eine berechnete prozentuale Änderung -- Zeichenfolgen wie
    '+50 %', '+50%', '-60 %' kommen nicht mehr vor."""
    msg = _single_event_msg("gust", 20.0, 30.0, 5.0)
    html, plain = render_email(msg)
    for label, text in (("html", html), ("plain", plain)):
        match = _COMPUTED_PERCENT_CHANGE.search(text)
        assert match is None, (
            f"Berechnete Prozent-Änderung in {label} gefunden: {match.group() if match else None!r} "
            f"in {text!r}"
        )


# ===========================================================================
# AC-9: H1 nennt Von-/Bis-Wert statt der entfallenen Prozentzahl
# ===========================================================================

def test_ac9_h1_nennt_von_bis_wert_stufenmetrik():
    """AC-9 (Stufenmetrik): H1 lautet 'Gewitter mittel → hoch seit dem
    Briefing'."""
    from app.models import ThunderLevel
    from output.metric_format import THUNDER_LABEL_DE

    msg = _single_event_msg("thunder", 2.0, 3.0, 1.0)
    _, plain = render_email(msg)
    h1_line = plain.split("\n")[0]
    expected = (
        f"Gewitter {THUNDER_LABEL_DE[ThunderLevel.MED]} → "
        f"{THUNDER_LABEL_DE[ThunderLevel.HIGH]} seit dem Briefing"
    )
    assert h1_line == expected, f"H1 weicht ab.\n  erwartet: {expected!r}\n  bekommen: {h1_line!r}"


def test_ac9_h1_nennt_von_bis_wert_mengenmetrik():
    """AC-9 (Mengenmetrik): H1 lautet
    'Niedersch 2,0 mm → 18,0 mm seit dem Briefing'."""
    msg = _single_event_msg("precipitation", 2.0, 18.0, 10.0)
    _, plain = render_email(msg)
    h1_line = plain.split("\n")[0]
    expected = "Niedersch 2,0 mm → 18,0 mm seit dem Briefing"
    assert h1_line == expected, f"H1 weicht ab.\n  erwartet: {expected!r}\n  bekommen: {h1_line!r}"


def test_ac9_h1_bei_wertfrom_null_bleibt_nicht_inhaltsleer():
    """AC-9 (Sonderfall value_from==0): die inhaltsleere Form 'Gewitter seit
    dem Briefing' -- heute der einzige Prozent-Sonderfall -- entsteht nicht
    mehr; H1 nennt weiterhin Von-/Bis-Wert."""
    from app.models import ThunderLevel
    from output.metric_format import THUNDER_LABEL_DE

    msg = _single_event_msg("thunder", 0.0, 2.0, 1.0)
    _, plain = render_email(msg)
    h1_line = plain.split("\n")[0]
    assert h1_line != "Gewitter seit dem Briefing", (
        f"Inhaltsleere H1-Form darf nicht mehr entstehen: {h1_line!r}"
    )
    expected = (
        f"Gewitter {THUNDER_LABEL_DE[ThunderLevel.NONE]} → "
        f"{THUNDER_LABEL_DE[ThunderLevel.MED]} seit dem Briefing"
    )
    assert h1_line == expected, f"H1 weicht ab.\n  erwartet: {expected!r}\n  bekommen: {h1_line!r}"


# ===========================================================================
# AC-10: Prozent bleibt Einheit, nur die berechnete Änderung fällt weg
# ===========================================================================

def test_ac10_prozent_metrik_behaelt_einheit_verliert_aber_berechnete_aenderung():
    """AC-10: GIVEN eine Metrik mit Katalog-Einheit '%' (Regenwahrschein-
    lichkeit 60→90), WHEN die E-Mail-Datenzeile gerendert wird, THEN bleibt
    das Prozentzeichen als Einheit am Messwert erhalten ('60 % ↑ 90 %'),
    während die berechnete Änderung ('+50 %') verschwindet -- der Wegfall
    betrifft ausschließlich die Änderung, niemals die Einheit."""
    msg = _single_event_msg("rain_probability", 60.0, 90.0, 20.0)
    _, plain = render_email(msg)
    first_line = _first_plain_data_line(plain)
    assert "60 % ↑ 90 %" in first_line, (
        f"Einheit '%' am Messwert fehlt -- sie muss erhalten bleiben: {first_line!r}"
    )
    assert "+50 %" not in first_line, (
        f"Berechnete Prozent-Änderung darf nicht mehr in der Datenzeile stehen: {first_line!r}"
    )
