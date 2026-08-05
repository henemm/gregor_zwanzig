"""Geteilte Ableitung der Kanal-Schwelle (Issue #1461 Scheibe S3b-2a).

Eine reine Funktion, kein Zustand: teilt ein rohes Kanal-Opt-in in die
Kanaele, die eine Meldung dieser Dringlichkeit erreichen darf, und die, die
sie nicht erreicht. Startwert je Kanal ist "LOW" -- eine Schwelle wird nur
wirksam, wenn der Nutzer sie selbst hochsetzt (rote Linie #638).

SPEC: docs/specs/modules/feat_1461_s3b2a_kanal_schwelle.md

Der Rangvergleich selbst lebt in `alert_urgency.meets_or_exceeds()` -- dieses
Modul dupliziert ihn nicht (Wiederholungs-Klasse #1481).
"""
from __future__ import annotations

import services.alert_urgency as alert_urgency

DEFAULT_CHANNEL_THRESHOLD = "LOW"


def split_by_threshold(
    channels: set[str],
    urgency: str,
    thresholds: "dict[str, str] | None",
) -> "tuple[set[str], set[str]]":
    """(erlaubt, unterdrueckt). Kein gesetzter Wert je Kanal -> "LOW"."""
    thresholds = thresholds or {}
    allowed: set[str] = set()
    suppressed: set[str] = set()
    for channel in channels:
        threshold = thresholds.get(channel) or DEFAULT_CHANNEL_THRESHOLD
        if alert_urgency.meets_or_exceeds(urgency, threshold):
            allowed.add(channel)
        else:
            suppressed.add(channel)
    return allowed, suppressed
