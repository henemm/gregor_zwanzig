"""TDD RED — Issue #2009: Datumsbezug am Onset-Zeitpunkt (AC-4, AC-5).

SPEC: docs/specs/modules/fix_2009_nowcast_vorlauf.md

Mit der auf 55 Min angehobenen Onset-Schwelle (#2009) kann der berechnete
Onset-Zeitpunkt ueber Mitternacht rutschen (23:30 + 53 Min = 00:23
Folgetag). `render.py` formatiert `onset_time` heute als reines `%H:%M`
(`utils/timezone.py::local_fmt`) -- ohne Tagesbezug ist "00:23" mehrdeutig
(heute Nacht oder in ueber 23 Stunden?).

`OnsetEvent` (`output/renderers/alert/model.py`) hat noch KEIN
`onset_day_offset`-Feld -- die Konstruktion mit diesem Keyword-Argument
schlaegt heute mit `TypeError: unexpected keyword argument` fehl.

Kein Mock: echte `OnsetEvent`/`AlertMessage`-Objekte durch die echten
Renderer (`render_email`/`render_telegram`/`render_sms`), FESTE
`onset_time`-Werte (keine Wanduhr noetig -- die Renderer lesen `onset_time`
nur aus dem uebergebenen Objekt, s. `test_alert_sms_onset_zeitpunkt.py`
fuer dasselbe Muster).
"""
from __future__ import annotations

import re

from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import render_email, render_sms, render_telegram


def _onset_event(**kw) -> OnsetEvent:
    """Ein Trip-Radar-Onset-Ereignis mit festen Feldern (keine Wanduhr)."""
    fields = dict(
        onset_minutes=53, onset_time="00:23", km_from=8.0, km_to=8.0,
        is_convective=True, intensity_label="Starker Regen",
        source_label="INCA",
    )
    fields.update(kw)
    return OnsetEvent(**fields)


def _onset_msg(event: OnsetEvent, *, trip_short: str = "KHW 403", source: str = "radar") -> AlertMessage:
    """`source is not None` routet die Renderer in den Onset-Zweig."""
    return AlertMessage(trip_short=trip_short, stand_at="23:30", events=(event,), source=source)


# ═══════════════════════════════ AC-4 ═════════════════════════════════════


def test_ac4_email_and_telegram_show_day_on_rollover():
    """AC-4: Given ein Onset-Zeitpunkt, der ueber Mitternacht rutscht
    (now=23:30 lokal, onset_minutes=53 -> 00:23 Folgetag) / When E-Mail-
    oder Telegram-Text gerendert wird / Then enthaelt der Text einen
    eindeutigen Tagesbezug ("ab morgen 00:23") statt der nackten,
    mehrdeutigen Uhrzeit; Kontrollfall im selben Test: ein Onset ohne
    Tageswechsel bleibt exakt wie bisher (kein "morgen"-Zusatz)."""
    rollover_event = _onset_event(onset_time="00:23", onset_day_offset=1)
    rollover_msg = _onset_msg(rollover_event)

    _, plain = render_email(rollover_msg)
    telegram = render_telegram(rollover_msg)

    assert "ab morgen 00:23" in plain, (
        f"E-Mail-Text traegt keinen eindeutigen Tagesbezug fuer den "
        f"Mitternachts-Ueberlauf (erwartet 'ab morgen 00:23'): {plain!r}"
    )
    assert "ab 00:23" not in plain, (
        f"Die nackte, mehrdeutige Uhrzeit '00:23' ohne Tagesbezug darf nach "
        f"dem Ueberlauf nicht mehr vorkommen: {plain!r}"
    )
    assert "morgen 00:23" in telegram, (
        f"Telegram-Text traegt keinen eindeutigen Tagesbezug fuer den "
        f"Mitternachts-Ueberlauf: {telegram!r}"
    )

    # Kontrollfall: kein Tageswechsel -> Text bleibt EXAKT wie bisher
    # (byte-identisch, kein "morgen"-Zusatz, Regressionsschutz).
    control_event = _onset_event(onset_time="14:05", onset_day_offset=0)
    control_msg = _onset_msg(control_event)
    _, control_plain = render_email(control_msg)
    control_telegram = render_telegram(control_msg)

    assert "ab 14:05" in control_plain, (
        f"Ohne Tageswechsel muss die Uhrzeit unveraendert erscheinen: "
        f"{control_plain!r}"
    )
    assert "morgen" not in control_plain, (
        f"Ohne Tageswechsel darf kein 'morgen'-Zusatz erscheinen (byte-"
        f"identisch zum Bestandsverhalten): {control_plain!r}"
    )
    assert "14:05" in control_telegram and "morgen" not in control_telegram, (
        f"Telegram-Kontrollfall (kein Tageswechsel) muss unveraendert "
        f"bleiben: {control_telegram!r}"
    )


# ═══════════════════════════════ AC-5 ═════════════════════════════════════


def test_ac5_sms_token_carries_day_suffix():
    """AC-5: Given denselben Mitternachts-Ueberlauf-Fall / When die
    Kurznachricht (SMS und Premium-SMS teilen `_render_sms_onset`) gerendert
    wird / Then traegt der Token ein zeichensparendes Tages-Suffix
    ("TH@0:23+1"), bleibt GSM-7-vertraeglich und unter der 160-Zeichen-
    Grenze; ohne Tageswechsel bleibt der Token exakt wie bisher."""
    rollover_event = _onset_event(onset_time="00:23", onset_day_offset=1)
    sms = render_sms(_onset_msg(rollover_event))

    assert "TH@0:23+1" in sms, (
        f"Erwartetes Tages-Suffix-Token 'TH@0:23+1' fehlt in der SMS: {sms!r}"
    )
    assert len(sms) <= 160, f"SMS ueberschreitet die 160-Zeichen-Grenze: {len(sms)} — {sms!r}"

    token_match = re.search(r"(TH|R)@\d{1,2}:\d{2}(?:\+\d+)?", sms)
    assert token_match, f"Kein Onset-Zeitpunkt-Token in der SMS gefunden: {sms!r}"
    token = token_match.group(0)
    assert re.fullmatch(r"[A-Za-z0-9@:+\-]+", token), (
        f"Token enthaelt Zeichen ausserhalb des GSM-7-vertraeglichen Satzes "
        f"(Ziffern/@/:/+/-): {token!r}"
    )

    # Kontrollfall: kein Tageswechsel -> Token bleibt EXAKT wie bisher.
    control_event = _onset_event(onset_time="15:40", onset_day_offset=0)
    control_sms = render_sms(_onset_msg(control_event))
    assert "TH@15:40" in control_sms, (
        f"Ohne Tageswechsel muss der Token unveraendert erscheinen: {control_sms!r}"
    )
    assert "+1" not in control_sms, (
        f"Ohne Tageswechsel darf kein Tages-Suffix erscheinen: {control_sms!r}"
    )


# ══════════════════════ Zusatzfall: Sommerzeit-Umstellung ═════════════════


def test_day_offset_survives_dst_transition():
    """Zusatz (Team-Lead-Wunsch zu AC-4/AC-5): `utils.timezone.day_offset()`
    vergleicht KALENDERTAGE in der Ortszone, nicht eine feste 24h-Distanz --
    bleibt deshalb auch ueber die Sommerzeit-Umstellung hinweg korrekt (ein
    "Tag" mit 23 Stunden aendert die Kalenderdatums-Differenz nicht).

    Fall: Sommerzeit-Beginn Europe/Berlin 2026-03-29, 02:00 CET -> 03:00 CEST
    (Umstellung bei 01:00 UTC). `now`=00:50 UTC (01:50 CET, VOR dem Sprung),
    Onset +53 Min = 01:43 UTC (03:43 CEST, NACH dem Sprung) -- beide liegen
    auf demselben Kalendertag (29.), day_offset muss 0 liefern, nicht
    faelschlich 1 wegen des uebersprungenen 02:00-03:00-Fensters."""
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    from utils.timezone import day_offset

    tz = ZoneInfo("Europe/Berlin")
    now_utc = datetime(2026, 3, 29, 0, 50, tzinfo=timezone.utc)
    onset_utc = now_utc + timedelta(minutes=53)

    assert day_offset(now_utc, onset_utc, tz) == 0, (
        "Sommerzeit-Sprung (23h-Tag) darf einen Onset am selben Kalendertag "
        "nicht faelschlich als Tageswechsel zaehlen"
    )
