"""TDD RED — Issue #1948 Scheibe S3: Δ-Alarm-SMS (Zweig a) verliert den
redundanten Vergleichszeitpunkt-Präfix `@HH:MM` im Kopf (löst #1939
strukturell mit), wechselt die Von-Bis-Notation von `>` auf `->` ohne
Vorzeichen-Präfix, und rendert Gewitter-Stufen als Buchstaben statt Rohzahlen.

SPEC: docs/specs/modules/fix_1948_s3_sms_sofortfix.md — AC-1 bis AC-4.
KONTEXT: docs/context/fix-1948-s3-sms-sofortfix.md

Kein Mock, keine Dateiinhalt-Checks -- echte `AlertEvent`/`AlertMessage`
durch den echten Renderer (Vorbild: `test_alert_sms_segment_head.py`).
"""
from __future__ import annotations

from output.renderers.alert.model import AlertEvent, AlertMessage
from output.renderers.alert.render import render_sms


def _visibility_event(*, occurred_at: str | None = "14:00") -> AlertEvent:
    return AlertEvent(
        metric_id="visibility", value_from=1400.0, value_to=280.0, threshold=1000.0,
        cmp="unter", occurred_at=occurred_at, km_from=8.0, km_to=8.0, segment_id="Ziel",
    )


def _thunder_event() -> AlertEvent:
    return AlertEvent(
        metric_id="thunder", value_from=2.0, value_to=3.0, threshold=1.0,
        cmp="über", occurred_at="16:00", km_from=8.0, km_to=8.0, segment_id="Ziel",
    )


# ---------------------------------------------------------------------------
# AC-1 — Kein @HH:MM-Kopf-Präfix mehr im Trip-Δ-Pfad
# ---------------------------------------------------------------------------


def test_ac1_kein_at_praefix_im_trip_delta_kopf():
    """AC-1: Given ein Trip-Δ-Alarm mit `reference_at='18:03'` und einem
    Sicht-Ereignis / When gerendert / Then enthaelt der Text an keiner
    Stelle `@18:03` -- der Kopf endet direkt mit 'Ziel: '.

    HEUTE ROT: `render_sms()` (Z.793-794) haengt `@{msg.reference_at} ` immer
    an den Kopf an, sobald `reference_at` gesetzt ist.
    """
    msg = AlertMessage(
        trip_short="KHW 403", stand_at="10:00", events=(_visibility_event(),),
        reference_at="18:03",
    )
    sms = render_sms(msg)

    assert "@18:03" not in sms, (
        f"AC-1: kein @HH:MM-Kopf-Praefix mehr erwartet: {sms!r}"
    )
    assert sms.startswith("Ziel: "), (
        f"AC-1: der Kopf muss direkt mit 'Ziel: ' beginnen: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — Numerisches Δ-Token: `->`-Notation ohne Vorzeichen
# ---------------------------------------------------------------------------


def test_ac2_numerisches_delta_token_ohne_vorzeichen_pfeil_notation():
    """AC-2: Given denselben Fall wie AC-1 (ohne `reference_at`) / When
    gerendert / Then lautet das Ereignis-Token exakt 'VS1400->280@14' -- kein
    fuehrendes '+'/'-', ASCII '->' statt '>'.

    HEUTE ROT: `_sms_token()` (Z.707-711) liefert '-VS1400>280@14'.
    """
    msg = AlertMessage(
        trip_short="KHW 403", stand_at="10:00", events=(_visibility_event(),),
    )
    sms = render_sms(msg)

    assert sms == "Ziel: VS1400->280@14", (
        f"AC-2: exaktes Zielbild erwartet, gemessen: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 — Gewitter-Δ-Token: Stufenbuchstaben statt Rohzahlen
# ---------------------------------------------------------------------------


def test_ac3_gewitter_delta_token_stufenbuchstaben():
    """AC-3: Given ein Gewitter-Ereignis (`thunder`, 2.0 -> 3.0, `@16`) /
    When gerendert / Then lautet das Token exakt 'TH:M->H@16' -- Doppelpunkt
    nach 'TH', Stufenbuchstaben 'M'/'H' statt der Rohzahlen '2'/'3'.

    HEUTE ROT: `_sms_token()` kennt keine Level-Erkennung -> 'TH2>3@16'.
    """
    msg = AlertMessage(
        trip_short="KHW 403", stand_at="10:00", events=(_thunder_event(),),
    )
    sms = render_sms(msg)

    assert sms == "Ziel: TH:M->H@16", (
        f"AC-3: exaktes Zielbild erwartet, gemessen: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Compare-Änderungspfad: Token byte-identisch, Kopf-Präfix entfällt
# ---------------------------------------------------------------------------


def test_ac4_compare_pfad_token_bleibt_byte_identisch_ohne_at_praefix():
    """AC-4: Given ein Ortsvergleich-Änderungspfad-Ereignis mit gesetztem
    `location_positions` (Regen 2->45mm, Position 2) UND gesetztem
    `reference_at` / When gerendert / Then lautet das Token weiterhin
    '2:+R45' -- Vorzeichen-Präfix UND '>'-freie Bis-Wert-Notation bleiben wie
    vor S3 (Invariante #1467 AC-9); NUR der `@HH:MM`-Kopf-Präfix entfaellt
    (struktureller #1939-Fix).

    HEUTE ROT: der `reference_at`-Block (Z.793-794) haengt sich VOR den Kopf-
    Wegfall des Compare-Pfads -- Ergebnis heute '@18:03 2:+R45' statt
    '2:+R45'. Das ist der #1939-Auslöser.
    """
    e = AlertEvent(
        metric_id="precipitation", value_from=2.0, value_to=45.0, threshold=5.0,
        cmp="über", occurred_at=None, km_from=0.0, km_to=0.0,
        location_label="Ort",
    )
    msg = AlertMessage(
        trip_short="Vergleich", stand_at="10:00", events=(e,), reference_at="18:03",
    )
    sms = render_sms(msg, location_positions={"Ort": 2})

    assert "@18:03" not in sms, (
        f"AC-4: kein @HH:MM-Kopf-Praefix im Compare-Pfad erwartet: {sms!r}"
    )
    assert sms == "2:+R45", (
        f"AC-4: Compare-Token bleibt byte-identisch (Vorzeichen+'>'-Notation "
        f"invariant), gemessen: {sms!r}"
    )
