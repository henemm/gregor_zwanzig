"""Geteilte Ableitung der Kanal-Schwelle (Issue #1461 Scheibe S3b-2a).

Eine reine Funktion, kein Zustand: teilt ein rohes Kanal-Opt-in in die
Kanaele, die eine Meldung dieser Dringlichkeit erreichen darf, und die, die
sie nicht erreicht. Ohne gesetzten Wert gilt die Vorbelegung je Kanal
(#2801, ADR-0131): E-Mail und Telegram "LOW", SMS "MODERATE",
Premium-SMS "HIGH". Ein gesetzter Wert (auch "LOW") bleibt unveraendert.
Unterdrueckte Kanaele bleiben im Protokoll sichtbar (rote Linie #638).

SPEC: docs/specs/modules/feat_1461_s3b2a_kanal_schwelle.md
SPEC: docs/specs/modules/feat_2801_alarm_schwelle_vorbelegung_je_kanal.md

Der Rangvergleich selbst lebt in `alert_urgency.meets_or_exceeds()` -- dieses
Modul dupliziert ihn nicht (Wiederholungs-Klasse #1481).
"""
from __future__ import annotations

import services.alert_urgency as alert_urgency

# Issue #2801: EINE Quelle der Vorbelegung je Kanal (Python-Seite). Das
# Frontend-Gegenstueck lebt in alertChannelState.ts; beide werden gegen
# tests/fixtures/alarm_schwelle_vorbelegung_2801.json auf Gleichheit geprueft.
DEFAULT_CHANNEL_THRESHOLDS: dict[str, str] = {
    "email": "LOW",
    "telegram": "LOW",
    "sms": "MODERATE",
    "premium_sms": "HIGH",
}

_KNOWN_THRESHOLDS = frozenset({"LOW", "MODERATE", "HIGH"})


def default_threshold(channel: str) -> str:
    """Vorbelegung der Alarm-Schwelle fuer einen Kanal ohne gesetzten Wert.
    Unbekannter Kanal -> "LOW" (keine Unterdrueckung ohne Grund)."""
    return DEFAULT_CHANNEL_THRESHOLDS.get(channel, "LOW")


def resolve_threshold(channel: str, thresholds: "dict[str, str] | None") -> str:
    """Wirksame Schwelle eines Kanals: gesetzter Wert, sonst Vorbelegung.
    Leere oder unbekannte Werte gelten als nicht gesetzt."""
    value = (thresholds or {}).get(channel)
    return value if value in _KNOWN_THRESHOLDS else default_threshold(channel)


def split_by_threshold(
    channels: set[str],
    urgency: str,
    thresholds: "dict[str, str] | None",
) -> "tuple[set[str], set[str]]":
    """(erlaubt, unterdrueckt). Kein gesetzter Wert -> Vorbelegung je Kanal."""
    allowed: set[str] = set()
    suppressed: set[str] = set()
    for channel in channels:
        threshold = resolve_threshold(channel, thresholds)
        if alert_urgency.meets_or_exceeds(urgency, threshold):
            allowed.add(channel)
        else:
            suppressed.add(channel)
    return allowed, suppressed
