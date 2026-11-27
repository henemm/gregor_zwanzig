"""TDD RED — Issue #2063: Kanalparitaet der exakten Radar-Uhrzeiten.

SPEC: docs/specs/modules/fix_2063_onset_minute_exakt.md — AC-8.

Derselbe Radar-Lauf (Sekundenlage :42, Beginn-Frame 18:00, Ende 19:45,
Reichweite 20:00) muss in SMS, Premium-SMS, Telegram und E-Mail DIESELBEN
Uhrzeiten zeigen (ADR-0095) — und zwar die Frame-Zeiten. Geprueft fuer beide
Alarm-Flaechen: Trip (Baustein `onset_event_from_nowcast`, wie
`trip_alert.check_radar_alerts`) und Ortsvergleich (geteilter Nachrichtenbau
`build_onset_message` -> `render_channel_texts`).

SMS und Premium-SMS teilen fuer den Alarm denselben Kurztext (`render_sms`,
Limit 140; `notification_service` sendet `sms_body` an beide Kanaele). Der
Kurztext traegt Beginn und Ende (`@HH:MM@HH:MM`), keine Reichweite — die
Reichweite wird deshalb nur in den Langform-Kanaelen verglichen.

Mock-frei: echte Frames, echter `_derive_result`, echte Renderer.
"""
from __future__ import annotations

import re

import pytest

from tests.tdd.test_onset_zeit_exakt_frame import (
    ableiten, frames_beginn_ende, lokal, trip_texte, vergleich_texte,
)

_KURZ_RE = re.compile(r"@(\d{1,2}:\d{2})@(\d{1,2}:\d{2})")
_BEGINN_LANG_RE = re.compile(r"(?:ab |>)?(\d{2}:\d{2}) · letzter Regen gegen (\d{2}:\d{2})")
_REICHWEITE_RE = re.compile(r"Radar reicht bis (\d{2}:\d{2})")


def _zeiten(kanal: str, text: str) -> dict:
    """Beginn/Ende/Reichweite aus dem gerenderten Kanaltext."""
    if kanal in ("SMS", "Premium-SMS"):
        treffer = _KURZ_RE.search(text)
        assert treffer, f"Vorbedingung {kanal}: kein @Beginn@Ende-Token: {text!r}"
        return {"Beginn": treffer.group(1), "Ende": treffer.group(2)}
    treffer = _BEGINN_LANG_RE.search(text)
    assert treffer, f"Vorbedingung {kanal}: keine Beginn/Ende-Angabe: {text!r}"
    reichweite = _REICHWEITE_RE.search(text)
    assert reichweite, f"Vorbedingung {kanal}: keine Reichweite: {text!r}"
    return {"Beginn": treffer.group(1), "Ende": treffer.group(2),
            "Reichweite": reichweite.group(1)}


@pytest.mark.parametrize(
    "flaeche, texte_fn",
    [("Trip", trip_texte), ("Ortsvergleich", vergleich_texte)],
    ids=["trip", "ortsvergleich"],
)
def test_ac8_alle_vier_kanaele_zeigen_dieselben_frame_zeiten(flaeche, texte_fn):
    """AC-8 GIVEN derselbe Radar-Lauf um 17:37:42 (Beginn-Frame 18:00, Ende
    19:45, Reichweite 20:00)
    WHEN SMS, Premium-SMS, Telegram und E-Mail den Alarm ({flaeche})
    darstellen
    THEN zeigen alle vier Kanaele dieselbe Uhrzeit fuer Beginn (18:00) und
    Ende (19:45), und Telegram und E-Mail dieselbe Reichweite (20:00).

    RED heute: alle Kanaele zeigen gleichermassen die zurueckgerechnete
    Zeit 17:59 / 19:44 / 19:59 — paritaetisch, aber falsch."""
    jetzt = lokal(17, 37, 42)
    nc = ableiten(frames_beginn_ende(), jetzt)

    texte = texte_fn(nc, jetzt)
    assert set(texte) == {"SMS", "Premium-SMS", "Telegram", "E-Mail"}

    erwartet = {"Beginn": "18:00", "Ende": "19:45", "Reichweite": "20:00"}
    for kanal, text in texte.items():
        gefunden = _zeiten(kanal, text)
        soll = {k: erwartet[k] for k in gefunden}
        assert gefunden == soll, (
            f"AC-8 ({flaeche}): {kanal} zeigt {gefunden!r} statt {soll!r}:\n{text}"
        )
