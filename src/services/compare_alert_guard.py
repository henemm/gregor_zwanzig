"""Die EINE Stilllegungs-Regel fuer Ortsvergleiche (Issue #1467 Scheibe S2,
Arbeitsgang AG6).

PO-Vorgabe woertlich: "Pausierte und archivierte Ortsvergleiche duerfen
grundsaetzlich nichts senden. Sie sollen sich so verhalten, als wuerde es sie
im System nicht geben."

Ein Preset ist stillgelegt, wenn EINES dieser vier Merkmale zutrifft
(ODER-verknuepft, jedes fuer sich genuegend):

1. ``paused_at`` ist gesetzt (ausdrueckliches Pausieren per Knopf),
2. ``schedule == "manual"`` (Alt-Semantik "kein Zeitplan" = pausiert),
3. ``archived_at`` ist gesetzt (Bestands-Riegel aus #1233),
4. ``end_date`` liegt vor heute (Europe/Vienna; heute oder Zukunft = aktiv,
   fehlend/leer/ungueltig = nicht abgelaufen; Issue #2422 S5, AC-21).

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

from datetime import date, datetime
from zoneinfo import ZoneInfo

# Alt-Semantik: genau dieser eine Zeitplan-Wert bedeutet "pausiert". Jeder
# andere Wert ("daily", "weekly", ...) ist ein aktiver Zeitplan.
_PAUSED_SCHEDULE = "manual"

# ``end_date`` ist ein Kalendertag ohne Ortsbezug (Ortsvergleich = mehrere Orte,
# freigegebene AC #2422 S5): er wird gegen den Wiener Kalendertag geprueft.
_END_DATE_REFERENCE_ZONE = "Europe/Vienna"


def is_silenced(preset: dict, *, ohne_end_date: bool = False) -> bool:
    """True, wenn der Ortsvergleich pausiert, archiviert oder abgelaufen ist.

    Rein und ohne Seiteneffekte. Gelesen wird ausschliesslich per ``.get()``,
    ein fehlender Schluessel gilt nie als stillgelegt. Leere Werte
    (``None``, ``""``) zaehlen ebenfalls nicht als gesetzt — ein leeres Feld
    aus einem Formular-Roundtrip darf keinen aktiven Ortsvergleich dauerhaft
    stummschalten.

    ``ohne_end_date=True`` blendet Merkmal 4 aus: der Slot-Scheduler wertet
    ``end_date`` selbst gegen den Ortstag (injizierte Uhr, Orts-Zeitzone) aus.
    """
    if preset.get("paused_at"):
        return True
    if preset.get("schedule") == _PAUSED_SCHEDULE:
        return True
    if preset.get("archived_at"):
        return True
    return not ohne_end_date and _end_date_passed(preset.get("end_date"))


def _end_date_passed(end_date) -> bool:
    """Merkmal 4: True nur bei gueltigem ``end_date`` < heute (Wien)."""
    if not end_date:
        return False
    try:
        return date.fromisoformat(end_date) < datetime.now(ZoneInfo(_END_DATE_REFERENCE_ZONE)).date()
    except (ValueError, TypeError):
        return False
