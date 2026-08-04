"""Die EINE Stilllegungs-Regel fuer Ortsvergleiche (Issue #1467 Scheibe S2,
Arbeitsgang AG6).

PO-Vorgabe woertlich: "Pausierte und archivierte Ortsvergleiche duerfen
grundsaetzlich nichts senden. Sie sollen sich so verhalten, als wuerde es sie
im System nicht geben."

Ein Preset ist stillgelegt, wenn EINES dieser drei Merkmale zutrifft
(ODER-verknuepft, jedes fuer sich genuegend):

1. ``paused_at`` ist gesetzt (ausdrueckliches Pausieren per Knopf),
2. ``schedule == "manual"`` (Alt-Semantik "kein Zeitplan" = pausiert),
3. ``archived_at`` ist gesetzt (Bestands-Riegel aus #1233).

Verbindliche Vorlage ist die Oberflaechen-Logik
``frontend/src/lib/components/compare/subscriptionHelpers.ts:83-88``
(``deriveStatusFromPreset``): dort ergibt ``paused_at`` gesetzt ODER
``schedule === 'manual'`` die Beschriftung "pausiert". Der Riegel folgt
dieser Vorlage, damit Anzeige und Verhalten nicht auseinanderlaufen
(PO-Entscheidung 2026-08-04). ``archived_at`` kommt aus #1233 hinzu.

Diese Regel darf es nur EINMAL geben (AC-28): ``compare_alert.py``,
``compare_radar_alert.py`` und ``compare_official_alert.py`` rufen diese
Funktion auf, statt die Bedingung erneut auszuschreiben.

Bewusst NICHT hier angebunden: ``scheduler_dispatch_service.py:66-68``. Dort
bedeutet dieselbe Bedingung "schon stillgelegt, nicht erneut schreiben", nicht
"nicht senden" — gleiche Frage, andere Aussage.

SPEC: docs/specs/modules/rework_1467_s2_aenderungsalarm.md, Abschnitt "AG6".
"""
from __future__ import annotations

# Alt-Semantik: genau dieser eine Zeitplan-Wert bedeutet "pausiert". Jeder
# andere Wert ("daily", "weekly", ...) ist ein aktiver Zeitplan.
_PAUSED_SCHEDULE = "manual"


def is_silenced(preset: dict) -> bool:
    """True, wenn der Ortsvergleich pausiert oder archiviert ist.

    Rein und ohne Seiteneffekte. Gelesen wird ausschliesslich per ``.get()``,
    ein fehlender Schluessel gilt nie als stillgelegt. Leere Werte
    (``None``, ``""``) zaehlen ebenfalls nicht als gesetzt — ein leeres Feld
    aus einem Formular-Roundtrip darf keinen aktiven Ortsvergleich dauerhaft
    stummschalten.
    """
    if preset.get("paused_at"):
        return True
    if preset.get("schedule") == _PAUSED_SCHEDULE:
        return True
    if preset.get("archived_at"):
        return True
    return False
