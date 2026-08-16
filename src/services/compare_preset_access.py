"""Geteilter Preset-/Empfaenger-Zugriff der drei Ortsvergleich-Alarmpfade
(Issue #1467 Scheibe S4a).

SPEC: docs/specs/modules/rework_1467_s4a_amtlich.md

`_load_presets()` lag bis S4a byte-identisch dreifach im Baum
(`compare_alert.py`, `compare_radar_alert.py`, `compare_official_alert.py`),
`_notification_service_for()` strukturgleich dreifach. Beide wohnen jetzt
hier; die drei Bestandsmethoden sind Ein-Zeiler-Wrapper.

`log_label` traegt den EINZIGEN echten Unterschied zwischen den drei
Aufrufern — dasselbe Parametermuster wie `context_label` in `alert_gate.py`.
Er bleibt Pflicht-Parameter mit ohne Vorbelegung: an ihm erkennt der Nutzer im
Protokoll, WELCHER seiner drei Ortsvergleich-Alarme keine Empfaengeradresse
hat (AC-14). Ein gemeinsames Label waere eine stille Verschlechterung.
"""
from __future__ import annotations

import logging

from app.config import Settings
from app.loader import compare_preset_to_dict, load_compare_presets
from services.notification_service import NotificationService

logger = logging.getLogger("compare_preset_access")


def load_compare_alert_presets(user_id: str) -> list[dict]:
    """Alle Ortsvergleich-Presets dieses Nutzers als Dicts.

    Issue #1250 Scheibe 1: zentraler Loader statt rohem `json.loads`.
    """
    return [compare_preset_to_dict(p) for p in load_compare_presets(user_id=user_id)]


def notification_service_for_preset(
    settings: Settings, user_id: str, preset: dict, *, log_label: str,
) -> NotificationService:
    """Empfaenger ausschliesslich aus den Konto-Settings des Nutzers (Muster
    `trip_alert.py:125`). Issue #1452: `preset.empfaenger` ist inert — ein
    preset-eigenes Override stellte an eine Adresse zu, die der Nutzer in
    seinem Konto nie hinterlegt hat.

    Fehlt `mail_to`, wird das laut gemeldet (statt stillem Skip); der Lauf
    laeuft fuer die uebrigen Presets weiter (Spec AC-4).
    """
    if not settings.mail_to:
        logger.warning(
            "%s Nutzer %s hat keine Empfaenger-Adresse (mail_to) in den "
            "Konto-Settings — Preset %s kann keine E-Mail zustellen.",
            log_label, user_id, preset.get("id", ""),
        )
    return NotificationService(settings, user_id)
