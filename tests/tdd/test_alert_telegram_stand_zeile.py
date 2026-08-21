"""TDD RED — Issue #1948 Scheibe S6: Der ausführliche Telegram-Alarm bekommt
dieselbe Stand-/Vergleichszeile, die die E-Mail bereits führt. Sie entsteht
ausschließlich in `render_telegram`, niemals in `render_sms` (Telegram-
Kurzstil sendet den SMS-Text unverändert weiter).

Spec: docs/specs/modules/fix_1948_s6_alarm_stufenwort.md (AC-11, AC-12).
Kontext: docs/context/feat-1948-s6-telegram-paritaet.md, Abschnitt D.

PO-Entscheid (Variante b): volle Zeile wie in der E-Mail,
'Stand: heute 10:00 · verglichen mit 18:03'.

Alles echte Renderer-Aufrufe (render_telegram/render_sms) mit echten
AlertEvent/AlertMessage-Objekten. Kein Mock, keine Dateiinhalt-Checks.

Alle Tests hier müssen vor der Implementierung ROT sein.
"""
from __future__ import annotations

from output.renderers.alert.model import AlertEvent, AlertMessage
from output.renderers.alert.render import render_sms, render_telegram


def _single_thunder_msg(
    value_from: float, value_to: float, threshold: float,
    *, reference_at: str | None, stand_at: str = "10:00",
    trip_short: str = "KHW 403", occurred_at: str | None = "15:00",
    km_from: float = 0.0, km_to: float = 4.0,
) -> AlertMessage:
    e = AlertEvent(
        metric_id="thunder", value_from=value_from, value_to=value_to,
        threshold=threshold, cmp="über", occurred_at=occurred_at,
        km_from=km_from, km_to=km_to,
    )
    return AlertMessage(
        trip_short=trip_short, stand_at=stand_at, events=(e,), source=None,
        reference_at=reference_at,
    )


# ===========================================================================
# AC-11: Telegram-Stand-Zeile — bekannter und fehlender Vergleichszeitpunkt
# ===========================================================================

def test_ac11_telegram_stand_zeile_bei_bekanntem_referenzzeitpunkt():
    """AC-11 (Fall 1, reference_at bekannt): GIVEN ein Änderungs-Alarm mit
    gesetztem reference_at, WHEN der ausführliche Telegram-Text gerendert
    wird, THEN schließt er mit derselben Stand-Zeile wie die E-Mail:
    'Stand: heute 10:00 · verglichen mit 18:03'. Beide Fälle sind real
    erreichbar: der Ortsvergleich-Einzelpunkt und der Vorschau-Pfad reichen
    reference_at nie durch (project.py:411-424, validator_render_service.py:
    144-147)."""
    msg = _single_thunder_msg(2.0, 3.0, 1.0, reference_at="18:03", stand_at="10:00")
    tg = render_telegram(msg)
    last_line = tg.splitlines()[-1]
    expected = "Stand: heute 10:00 · verglichen mit 18:03"
    assert last_line == expected, (
        f"Telegram-Stand-Zeile weicht ab.\n  erwartet: {expected!r}\n  bekommen: {last_line!r}"
    )


def test_ac11_telegram_stand_zeile_bei_fehlendem_referenzzeitpunkt():
    """AC-11 (Fall 2, reference_at fehlt): GIVEN denselben Alarm-Typ ohne
    reference_at, WHEN der ausführliche Telegram-Text gerendert wird, THEN
    schließt er mit 'Stand: heute 10:00 · verglichen mit dem letzten
    Briefing' -- derselbe Rückfalltext wie in der E-Mail."""
    msg = _single_thunder_msg(2.0, 3.0, 1.0, reference_at=None, stand_at="10:00")
    tg = render_telegram(msg)
    last_line = tg.splitlines()[-1]
    expected = "Stand: heute 10:00 · verglichen mit dem letzten Briefing"
    assert last_line == expected, (
        f"Telegram-Stand-Zeile (Rückfall) weicht ab.\n  erwartet: {expected!r}\n  "
        f"bekommen: {last_line!r}"
    )


# ===========================================================================
# AC-12: Stand-Zeile entsteht ausschließlich in render_telegram, nie in SMS
# ===========================================================================

def test_ac12_stand_zeile_entsteht_ausschliesslich_in_telegram_nie_in_sms():
    """AC-12: GIVEN einen Trip mit Telegram-Kurzstil, WHEN ein Änderungs-
    Alarm versendet wird, THEN bleibt der Kurzstil-Text byte-identisch mit
    dem SMS-Text und enthält keine Stand-Zeile -- die neue Zeile entsteht
    ausschließlich in render_telegram, niemals in render_sms. Wächter gegen
    ein Auslaufen der Zeile in die Kurznachricht (Mutations-Gegenprobe 4 der
    Spec: eine Stand-Zeile zusätzlich in render_sms muss dieses AC röten)."""
    msg = _single_thunder_msg(2.0, 3.0, 1.0, reference_at="18:03", stand_at="10:00")
    tg = render_telegram(msg)
    sms = render_sms(msg)
    assert "Stand:" in tg, (
        f"Telegram (ausführlicher Text) soll die Stand-Zeile führen (AC-11): {tg!r}"
    )
    assert "Stand:" not in sms, (
        f"Wächter AC-12: Die Stand-Zeile darf niemals in render_sms landen "
        f"(sonst liefe sie über den Kurzstil-Pfad in die SMS aus): {sms!r}"
    )
