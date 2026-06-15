"""
Radar-Alert-Body und Subject-Builder -- pure functions (Issue #830).

Extrahiert aus services/trip_alert.py::check_radar_alerts() (Zeile 644-665).
Kein I/O, keine Seiteneffekte -- nur String-Aufbau.
"""
from __future__ import annotations


def build_radar_alert_subject(trip_name: str, result: object, segment_label: str) -> str:
    """Baue den Betreff fuer eine Radar-Alert-Mail.

    Konvektiv (result.is_convective == True):
        "[<trip_name>] Gewitter - <segment_label>"
    Nicht konvektiv:
        "[<trip_name>] Regen zieht auf - <segment_label>"
    """
    if getattr(result, "is_convective", False):
        return f"[{trip_name}] ⚠️ Gewitter – {segment_label}"
    return f"[{trip_name}] Regen zieht auf – {segment_label}"


def build_radar_alert_body(
    onset_text: str,
    segment_label: str,
    cooldown_display: str,
    source: str,
) -> str:
    """Baue den Body fuer eine Radar-Alert-Mail.

    Format (exakt Spec Implementation Detail D):
        <onset_text>
        auf <segment_label>.

        Quelle: <source>.
        Du erhaeltst diese Warnung hoechstens einmal in <cooldown_display>.

    Alle Parameter werden uebergeben -- keine Seiteneffekte, kein I/O.
    """
    return (
        f"{onset_text}\n"
        f"auf {segment_label}.\n\n"
        f"Quelle: {source}.\n"
        f"Du erhältst diese Warnung höchstens einmal in {cooldown_display}."
    )
