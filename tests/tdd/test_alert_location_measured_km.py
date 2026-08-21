"""TDD RED — Issue #2036: Alarm-Kurzform nennt gemessene Kilometer statt
Segmentnummer, ABER NUR wenn die Kilometer aus echter GPX-Wegstrecke stammen.

SPEC:    docs/specs/modules/fix_2036_alarm_kilometer_ortsangabe.md (AC-1, AC-2,
         AC-4, AC-5, AC-13)
KONTEXT: docs/context/fix-2036-alarm-kilometer.md

Alle Faelle bauen echte Domaenen-Objekte (`AlertEvent`, `AlertMessage`) und
rufen die echten Renderer (`render_subject`, `render_telegram`, `render_sms`,
`segments.format_alert_location`) auf -- keine Mocks, keine Dateiinhalt-Checks.

RED-VERTRAG: `AlertEvent` (model.py) traegt heute KEIN `km_measured`-Feld und
`format_alert_location()` (segments.py) kennt heute KEINEN `km_measured`-
Parameter. Jede Konstruktion mit diesem Schluesselwort schlaegt mit
`TypeError: unexpected keyword argument 'km_measured'` fehl -- das IST der
RED-Zustand (fehlendes additives Feld/Argument aus der Spec), keine
Verwechslung mit einem Tippfehler in diesem Testcode.
"""
from __future__ import annotations

import re

import pytest


def _measured_event(
    segment_id: str | None = "3",
    km_from: float = 12.31,
    km_to: float = 20.0,
    km_measured: bool = True,
    metric_id: str = "gust",
    value_from: float = 30.0,
    value_to: float = 85.0,
    threshold: float = 20.0,
    occurred_at: str | None = "11:00",
):
    """Baut ein `AlertEvent` DIREKT (kein Umweg ueber `to_alert_message()`) --
    dieselbe Technik wie `test_alert_location_vocabulary.py::_onset_message`
    fuer das additive `segment_id`-Feld: das additive `km_measured`-Feld wird
    hier ausschliesslich am Renderer-Modell selbst gesetzt."""
    from output.renderers.alert.model import AlertEvent

    try:
        return AlertEvent(
            metric_id=metric_id, value_from=value_from, value_to=value_to,
            threshold=threshold, cmp="über", occurred_at=occurred_at,
            km_from=km_from, km_to=km_to, segment_id=segment_id,
            km_measured=km_measured,
        )
    except TypeError as exc:  # RED-Vertrag
        raise AssertionError(
            "AlertEvent traegt kein additives 'km_measured'-Feld (Spec "
            "fix_2036_alarm_kilometer_ortsangabe.md, model.py:11-32). "
            f"Urspruenglicher Fehler: {exc}"
        ) from exc


def _single_event_message(**kwargs):
    from output.renderers.alert.model import AlertMessage

    event = _measured_event(**kwargs)
    return AlertMessage(
        trip_short="KHW 403", stand_at="10:00", events=(event,), source=None,
    )


# ---------------------------------------------------------------------------
# AC-1 — Kurzform zeigt "km A-B" statt "Seg N"
# ---------------------------------------------------------------------------

def test_ac1_gemessene_spanne_zeigt_km_a_bis_b_statt_segmentnummer():
    """AC-1: Given ein Alarm-Event hat fuer sein Segment eine gemessene,
    plausible Kilometer-Spanne (km_measured=True) / When die Kurzform-
    Ortsangabe aufgeloest wird (SMS/Premium-SMS/Telegram-Kurzform) / Then
    zeigt sie 'km A-B' (Bindestrich, Leerzeichen nach 'km') statt 'Seg N',
    A/B auf ganze Kilometer gerundet (12,31 -> 12, 20,00 -> 20)."""
    from output.renderers.alert.render import render_sms

    msg = _single_event_message(segment_id="3", km_from=12.31, km_to=20.0,
                                 km_measured=True)
    sms = render_sms(msg)

    assert "km 12-20" in sms, f"Erwartete 'km 12-20' in der SMS: {sms!r}"
    assert "Seg 3" not in sms, f"SMS nennt weiterhin die Segmentnummer: {sms!r}"


def test_ac1_direkte_aufloesungsfunktion_liefert_exakte_schreibweise():
    """AC-1 (direkt): `format_alert_location()` selbst liefert bei
    `km_measured=True` 'km A-B' statt der Segment-Kennung."""
    from output.renderers.alert.segments import format_alert_location

    try:
        text = format_alert_location(
            None, ["3"], 12.31, 20.0, km_measured=True,
        )
    except TypeError as exc:
        raise AssertionError(
            "format_alert_location() kennt keinen 'km_measured'-Parameter "
            f"(Spec Implementation Details, Auflösungsreihenfolge). {exc}"
        ) from exc

    assert text == "km 12-20", f"Ortsangabe: {text!r}"


# ---------------------------------------------------------------------------
# AC-2 — Betreff und Telegram-rich zeigen dieselbe km-Angabe
# ---------------------------------------------------------------------------

def test_ac2_betreff_und_telegram_zeigen_dieselbe_km_angabe_wie_die_kurzform():
    """AC-2: Given dieselbe Aufloesungsfunktion wird auch fuer E-Mail-Betreff
    und Telegram-rich verwendet / When ein Segment eine gemessene km-Spanne
    traegt / Then zeigen Betreff- und Telegram-rich-Text dieselbe km-Angabe
    wie die Kurzform, nicht mehr die Segmentnummer."""
    from output.renderers.alert.render import render_sms, render_subject, render_telegram

    msg = _single_event_message(segment_id="4", km_from=6.0, km_to=13.6,
                                 km_measured=True)

    subject = render_subject(msg)
    telegram = render_telegram(msg)
    sms = render_sms(msg)

    assert "km 6-14" in subject, f"Betreff zeigt nicht die km-Spanne: {subject!r}"
    assert "km 6-14" in telegram, f"Telegram-rich zeigt nicht die km-Spanne: {telegram!r}"
    assert "km 6-14" in sms, f"SMS zeigt nicht die km-Spanne: {sms!r}"
    assert "Segment 4" not in subject and "Seg 4" not in telegram, (
        f"Betreff/Telegram nennen weiterhin die Segmentnummer: "
        f"{subject!r} / {telegram!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Etappenziel behaelt "Ziel", auch wenn vermessen
# ---------------------------------------------------------------------------

def test_ac4_etappenziel_zeigt_weiterhin_flagge_ziel_trotz_gemessener_spanne():
    """AC-4: Given das letzte Segment einer Etappe hat km_from == km_to
    (Etappenziel) / When die Ortsangabe fuer dieses Segment aufgeloest wird,
    auch wenn die Etappe vermessen ist / Then bleibt die Anzeige '🏁 Ziel'
    und wird NICHT durch 'km 20-20' ersetzt."""
    from output.renderers.alert.segments import format_alert_location

    text = format_alert_location(
        None, ["Ziel"], 20.0, 20.0, km_measured=True,
    )

    assert text == "🏁 Ziel", f"Ortsangabe: {text!r}"
    assert "km 20-20" not in text, f"Ortsangabe darf keine km-Spanne zeigen: {text!r}"


# ---------------------------------------------------------------------------
# AC-5 — SMS-Schreibweise: Leerzeichen nach "km", Ratschen-Regex bleibt gruen
# ---------------------------------------------------------------------------

def test_ac5_sms_schreibweise_hat_leerzeichen_nach_km_kein_kmzahl():
    """AC-5: Given eine gemessene km-Spanne wird in der SMS-Kurzform
    gerendert / When der Text erzeugt wird / Then folgt er dem Muster
    'km A-B' MIT Leerzeichen nach 'km' (nicht 'kmA-B'), und der Ratschen-
    Regex aus `test_alert_location_vocabulary.py:534`
    (`re.search(r"km\\d", sms)`) bleibt gruen."""
    from output.renderers.alert.render import render_sms

    msg = _single_event_message(segment_id="7", km_from=45.0, km_to=52.0,
                                 km_measured=True)
    sms = render_sms(msg)

    assert "km 45-52" in sms, f"SMS: {sms!r}"
    assert not re.search(r"km\d", sms), (
        f"SMS traegt eine leerzeichenlose km-Angabe (Ratschen-Verstoss): {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-13 — Ohne Messung NIE eine (Luftlinien-)Kilometerangabe
# ---------------------------------------------------------------------------

def test_ac13_unvermessenes_segment_zeigt_nie_die_luftlinien_kilometer():
    """AC-13: Given kein Wegpunkt der Etappe traegt eine gemessene
    Wegstrecke und kein Track konnte eindeutig zugeordnet werden
    (km_measured=False) / When die Ortsangabe aufgeloest wird / Then wird zu
    KEINEM Zeitpunkt ein aus Luftlinie (`haversine_km`) berechneter
    Kilometerwert als Ortsangabe angezeigt -- auch nicht als Zahl irgendwo
    im Text.

    Realistische Luftlinienwerte aus zwei echten GR221-Wegpunkten
    (Valldemossa -> Deia, Tag 1), damit der Testwert kein Phantasiewert ist."""
    from output.renderers.alert.render import render_sms, render_subject
    from output.renderers.alert.segments import format_alert_location
    from utils.geo import haversine_km

    lat1, lon1 = 39.710564, 2.62293   # G1 Start
    lat2, lon2 = 39.747657, 2.648606  # G4 Ziel
    luftlinie_km = haversine_km(lat1, lon1, lat2, lon2)
    assert luftlinie_km > 0.1, "Testkoordinaten liegen zu nah beieinander"

    text = format_alert_location(
        None, ["3"], 0.0, luftlinie_km, km_measured=False,
    )
    assert text == "Segment 3", (
        f"Unvermessenes Segment zeigt nicht 'Segment 3': {text!r}"
    )
    luft_int = int(round(luftlinie_km))
    assert f"km {luft_int}" not in text and str(luft_int) not in text, (
        f"Luftlinienwert {luft_int} taucht in der Ortsangabe auf: {text!r}"
    )

    msg = _single_event_message(
        segment_id="3", km_from=0.0, km_to=luftlinie_km, km_measured=False,
    )
    subject = render_subject(msg)
    sms = render_sms(msg)
    for rendered in (subject, sms):
        assert not re.search(r"km\s*\d", rendered), (
            f"Gerenderter Alarmtext zeigt eine km-Zahl trotz km_measured=False: "
            f"{rendered!r}"
        )
