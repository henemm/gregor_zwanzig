"""TDD RED — Issue #1935/#1779: Alarm-SMS spricht dieselbe Ortssprache wie
E-Mail/Betreff (statt einer km-Spanne), fuehrt keinen Trip-Namen mehr auf dem
Trip-Δ-Pfad, und traegt den Von-Wert im Token.

SPEC: docs/specs/modules/fix_1935_1779_alarm_nachricht_klarheit.md
      (AC-5 bis AC-8, AC-12)
KONTEXT: docs/context/fix-1935-1779-alarm-nachricht-klarheit.md

Nimmt AC-5 der abgeloesten Spec `fix_1744_alarm_format_angleichen.md`
("Kurznachricht nennt weiterhin keinen Ortsbezug") ausdruecklich zurueck --
PO-Entscheid 2026-08-17.

Betrifft AUSSCHLIESSLICH den Trip-Δ-Pfad von `render_sms()` (kein
`location_positions`, kein `multi_location`, kein `msg.location_label`) sowie
den Trip-Zweig von `_render_sms_onset` (`OnsetEvent.location_label is None`).
Der Ortsvergleich-Pfad bleibt unangetastet (AC-9/AC-10, Regressionsschutz --
bereits durch `tests/tdd/test_alert_sms_location_positions.py` bewacht, hier
NICHT dupliziert).

Kein Mock, keine Dateiinhalt-Checks -- echte `AlertEvent`/`AlertMessage`/
`OnsetEvent` (Vorbild `_onset_message()` in `test_alert_location_vocabulary.py
:116-146`) durch die echten Renderer.
"""
from __future__ import annotations

import re
import unicodedata

from output.renderers.alert.model import AlertEvent, AlertMessage, OnsetEvent
from output.renderers.alert.render import render_sms, render_subject

_SUBJECT_RE = re.compile(r"^\[[^\]]*\]\s+(?P<where>.+?)\s+·\s+.+$")

# Token-Muster (Issue #1948 S3): 1-2 Buchstaben-Kuerzel + Von-Wert + '->' +
# Bis-Wert, optional '@HH'-Suffix. KEIN Vorzeichen-Praefix mehr (loeste die
# alte '>'-Notation ab).
_TOKEN_RE = re.compile(r"[A-Z]{1,2}\d+->\d+(?:@\d{2})?")


def _location_slot(subject: str) -> str:
    match = _SUBJECT_RE.match(subject)
    assert match, f"Betreff hat nicht die Bauform '[Trip] <Ort> · <Kern>': {subject!r}"
    return match.group("where")


def _strip_leading_pictograph(text: str) -> str:
    """Entfernt ein fuehrendes Piktogramm (z.B. 🏁) samt folgendem Leerzeichen.

    Unabhaengige Testerwartung -- KEINE Wiederverwendung von Produktivcode
    (der Prueflings-eigene Emoji-Entfernungsschritt ist genau das, was AC-7
    zusichert; ihn hier nachzubauen wuerde die Zusicherung entwerten)."""
    if not text:
        return text
    if unicodedata.category(text[0]) == "So":
        return text[1:].lstrip()
    return text


def _delta_event(*, segment_id: str, value_from: float, value_to: float,
                  threshold: float = 1000.0, occurred_at: str | None = None) -> AlertEvent:
    return AlertEvent(
        metric_id="visibility", value_from=value_from, value_to=value_to,
        threshold=threshold, cmp="unter", occurred_at=occurred_at,
        km_from=8.0, km_to=8.0, segment_id=segment_id,
    )


def _delta_msg(*events: AlertEvent, trip_short: str = "KHW 403") -> AlertMessage:
    return AlertMessage(trip_short=trip_short, stand_at="10:00", events=events)


# ---------------------------------------------------------------------------
# AC-5 — Kopf nennt denselben Ortstext wie der Betreff, kein Trip-Name
# ---------------------------------------------------------------------------


def test_ac5_sms_kopf_nennt_denselben_ortstext_wie_der_betreff():
    """AC-5: Given ein Trip-Δ-Alarm fuer das Ziel-Segment / When Betreff UND
    SMS gerendert werden / Then kehrt der (emoji-freie) Ortsteil aus dem
    Betreff als Kopf-Praefix in der SMS wieder -- kein km-Spanne, kein
    Trip-Name."""
    msg = _delta_msg(_delta_event(segment_id="Ziel", value_from=1400.0, value_to=280.0))

    subject_location = _location_slot(render_subject(msg))
    expected_head_text = _strip_leading_pictograph(subject_location)
    sms = render_sms(msg)

    assert sms.startswith(f"{expected_head_text}: "), (
        f"SMS-Kopf {sms!r} beginnt nicht mit dem Betreff-Ortstext {expected_head_text!r}"
    )
    assert msg.trip_short not in sms, f"SMS traegt weiterhin den Trip-Namen: {sms!r}"
    assert not re.search(r"km\d", sms), f"SMS nennt weiterhin eine km-Spanne: {sms!r}"


# ---------------------------------------------------------------------------
# AC-6 — Token traegt Von- UND Bis-Wert
# ---------------------------------------------------------------------------


def test_ac6_sms_token_traegt_von_und_bis_wert():
    """AC-6: Given denselben Fall wie AC-5 / When das Token gerendert wird /
    Then lautet es exakt 'VS1400->280' -- Von- UND Bis-Wert, nicht mehr nur
    der Bis-Wert von heute ('-VS280').

    Issue #1948 S3: die urspruengliche Vorzeichen+'>'-Notation ('-VS1400>280')
    ist durch die vorzeichenfreie '->'-Notation abgeloest."""
    msg = _delta_msg(_delta_event(segment_id="Ziel", value_from=1400.0, value_to=280.0))
    sms = render_sms(msg)

    match = _TOKEN_RE.search(sms)
    assert match, f"Kein Von->Bis-Token im Muster [A-Z]{{1,2}}\\d+->\\d+ gefunden: {sms!r}"
    assert match.group() == "VS1400->280", f"Token: {match.group()!r} (SMS: {sms!r})"
    assert "-VS1400>280" not in sms, f"Alte Vorzeichen+'>'-Notation noch vorhanden: {sms!r}"
    assert "-VS280" not in sms, f"Alter Nur-Bis-Wert-Token noch vorhanden: {sms!r}"


# ---------------------------------------------------------------------------
# AC-7 — Emoji wird entfernt, nicht transliteriert
# ---------------------------------------------------------------------------


def test_ac7_sms_kopf_entfernt_emoji_statt_es_zu_transliterieren():
    """AC-7: Given ein Trip-Δ-Alarm fuer das Ziel-Segment (Ortstext enthaelt
    🏁) / When der SMS-Kopf gerendert wird / Then steht dort 'Ziel: ' -- ohne
    Emoji UND ohne dessen Transliteration (':checkered_flag:' darf NICHT
    vorkommen). Kopf ist dadurch nicht laenger als der reine Textname."""
    msg = _delta_msg(_delta_event(segment_id="Ziel", value_from=1400.0, value_to=280.0))
    sms = render_sms(msg)

    assert ":checkered_flag:" not in sms, (
        f"Emoji wurde transliteriert statt entfernt: {sms!r}"
    )
    assert sms.startswith("Ziel: "), f"SMS-Kopf: {sms!r}"
    assert len("Ziel: ") == 6, "Sanity: Referenzlaenge des reinen Textkopfs"


# ---------------------------------------------------------------------------
# AC-8 — Segment-Buendel-Kopf, jedes Token mit eigenem Von/Bis-Wert
# ---------------------------------------------------------------------------


def test_ac8_sms_buendelkopf_traegt_zusammengefasste_segmentsprache():
    """AC-8: Given einen Trip-Δ-Alarm ueber die Segmente 2, 3 und Ziel (je ein
    Ereignis, drei verschiedene Metriken) / When render_sms() rendert / Then
    traegt der Kopf 'Segment 2-3, Ziel: ' (ASCII-gefaltet, Bindestrich statt
    Gedankenstrich, Ziel-Emoji entfernt) und jedes Ereignis sein eigenes
    Von/Bis-Token nach AC-6.

    Anmerkung (Spec-Ungenauigkeit, s. Bericht): das Golden-Beispiel der Spec
    nennt fuer diesen Fall nur zwei Token-Beispiele ('beide Token'), obwohl
    fuer drei Segmente mit je einem Ereignis eigentlich drei Token entstehen.
    Dieser Test verlangt deshalb bewusst DREI verschiedene Metriken (Boeen,
    Sicht, Niederschlag) statt der engeren Nacherzaehlung -- so ist jedes
    Token unabhaengig und eindeutig pruefbar, unabhaengig davon, ob die
    GREEN-Phase zwei oder drei Segmente mit je eigenem Token abbildet.
    """
    e_gust = AlertEvent(
        metric_id="gust", value_from=30.0, value_to=80.0, threshold=20.0,
        cmp="über", occurred_at="15:12", km_from=2.0, km_to=4.0, segment_id="2",
    )
    e_visibility = AlertEvent(
        metric_id="visibility", value_from=1400.0, value_to=280.0, threshold=1000.0,
        cmp="unter", occurred_at="14:30", km_from=4.0, km_to=6.0, segment_id="3",
    )
    e_precip = AlertEvent(
        metric_id="precipitation", value_from=2.0, value_to=30.0, threshold=10.0,
        cmp="über", occurred_at="16:00", km_from=8.0, km_to=8.0, segment_id="Ziel",
    )
    msg = _delta_msg(e_gust, e_visibility, e_precip)
    sms = render_sms(msg)

    assert sms.startswith("Segment 2-3, Ziel: "), f"SMS-Kopf: {sms!r}"
    assert ":checkered_flag:" not in sms, f"Ziel-Emoji transliteriert: {sms!r}"

    tokens = _TOKEN_RE.findall(sms)
    assert "G30->80@15" in tokens, f"Boeen-Token fehlt/falsch: {sms!r} ({tokens!r})"
    assert "VS1400->280@14" in tokens, f"Sicht-Token fehlt/falsch: {sms!r} ({tokens!r})"
    assert "R2->30@16" in tokens, f"Niederschlags-Token fehlt/falsch: {sms!r} ({tokens!r})"


# ---------------------------------------------------------------------------
# AC-12 — Trip/Compare-Weiche in `_render_sms_onset` (Vergleich, nicht isoliert)
# ---------------------------------------------------------------------------


def _onset_event(*, location_label: str | None) -> OnsetEvent:
    return OnsetEvent(
        onset_minutes=12, onset_time="14:08", km_from=5.0, km_to=18.0,
        is_convective=False, intensity_label="kraeftiger Regen",
        source_label="Radar (GeoSphere INCA)", location_label=location_label,
    )


def test_ac12_trip_radar_sms_verliert_den_namen_compare_radar_sms_behaelt_ihn():
    """AC-12: Given zwei AlertMessages ueber `_render_sms_onset` -- eine mit
    `OnsetEvent.location_label=None` (echter Trip-Radar/Onset-Alarm) und eine
    mit gesetztem `location_label` (Ortsvergleich-Buendel-Onset), ansonsten
    identisch (gleiche `onset_minutes`/`km_from`/`km_to`) / When `render_sms()`
    beide rendert / Then enthaelt NUR die zweite den Trip-Kurznamen im Kopf;
    die erste beginnt direkt mit der km-Spanne.

    Die Zusicherung ist der VERGLEICH beider Ergebnisse -- nicht die isolierte
    Pruefung des Trip-Falls (der isoliert schon durch #1744-Bestandstests lief).
    """
    trip_msg = AlertMessage(
        trip_short="KHW 403", stand_at="10:00",
        events=(_onset_event(location_label=None),),
        source="radar", cooldown_display="60 Min",
    )
    compare_msg = AlertMessage(
        trip_short="Vergleich", stand_at="10:00",
        events=(_onset_event(location_label="Vergleich"),),
        source="radar", cooldown_display="60 Min",
    )

    sms_trip = render_sms(trip_msg)
    sms_compare = render_sms(compare_msg)

    # FORTGESCHRIEBEN (Issue #1948 S4 AC-9): das Format wechselte auf
    # `format_alert_location`-Schreibweise + Zeitpunkt-Token; die
    # DIFFERENZLOGIK zwischen beiden Ergebnissen bleibt die Zusicherung.
    assert sms_trip.startswith("km 5-18: "), (
        f"Trip-Radar-SMS traegt weiterhin einen Namens-Kopf: {sms_trip!r}"
    )
    assert "KHW 403" not in sms_trip, f"Trip-Name noch in der SMS: {sms_trip!r}"

    assert sms_compare.startswith("Vergleich: "), (
        f"Compare-Radar-SMS hat ihren Ortsnamen verloren: {sms_compare!r}"
    )
    assert sms_trip != sms_compare, (
        f"Trip- und Compare-Kopf duerfen nicht zusammenfallen: "
        f"{sms_trip!r} / {sms_compare!r}"
    )
