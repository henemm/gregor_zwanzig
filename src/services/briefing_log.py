"""Geteilter Schreib-Helfer fuer den Briefing-Log (`briefing_log.json`).

Issue #2281, Epic #2345 P4.
SPEC: docs/specs/modules/feat_2281_vergleich_versand_historie.md

Jeder Eintrag traegt eine Kennung (`entity_id`) und eine Art (`entity_type`,
`"trip"` | `"compare"`, wie im Alarm-Log #1467). Trip-Eintraege schreiben
zusaetzlich weiter `trip_id` (gelesen von `briefing_slots` und Go-Altbestand);
Compare-Eintraege nie. Go leitet bei Alt-Eintraegen ohne die neuen Felder
`entity_id := trip_id` und `entity_type := "trip"` ab (Lese-Regel, keine
Datei-Migration).

Vorlage ist `alert_log._append`: Sperre holen, danach FRISCH lesen, anhaengen,
atomar schreiben. Eine kaputte Datei wird nach #2231 beiseitegelegt. Bei
Sperr-Timeout wird laut protokolliert und nie ungesperrt geschrieben. Kein
Fehler dieses Helfers erreicht den Aufrufer -- ein Log-Schreibfehler darf den
bereits erfolgten Versand nie scheitern lassen (AC-7).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Iterable, Optional

from app.loader import get_data_dir
from services.briefing_slots import lege_beschaedigte_datei_beiseite, lesefehler
from services.file_lock import LockTimeout, atomic_write_json, exclusive_lock

logger = logging.getLogger(__name__)

BRIEFING_LOG_FILENAME = "briefing_log.json"
BRIEFING_LOG_LOCK_TIMEOUT_SECONDS = 30.0


def append_briefing_log(
    user_id: Optional[str],
    entity_type: str,
    entity_id: str,
    kind: str,
    channels: Iterable[str],
    on_demand: bool,
    mail_to: Optional[str],
) -> None:
    """Haengt GENAU EINEN Versand-Eintrag an den Log des Nutzers an.

    Ohne `user_id` wird nichts geschrieben (kein Rueckfall auf `default`,
    AC-11). Wirft nie.
    """
    if not user_id:
        logger.error(
            "briefing_log: keine user_id -- Eintrag NICHT geschrieben (%s:%s)",
            entity_type, entity_id,
        )
        return
    eintrag: dict = {}
    if entity_type == "trip":
        eintrag["trip_id"] = entity_id
    eintrag.update({
        "entity_id": entity_id,
        "entity_type": entity_type,
        "kind": kind,
        "sent_at": datetime.now(tz=timezone.utc).isoformat(),
        "channels": list(channels),
        "on_demand": bool(on_demand),
    })
    if mail_to:
        eintrag["mail_to"] = mail_to
    try:
        _append(user_id, eintrag)
    except Exception:  # noqa: BLE001 -- Versand ist schon erfolgt (AC-7)
        logger.exception(
            "briefing_log: Eintrag NICHT geschrieben (user=%s): %s",
            user_id, json.dumps(eintrag, ensure_ascii=False, default=str),
        )


def _append(user_id: str, eintrag: dict) -> None:
    path = get_data_dir(user_id) / BRIEFING_LOG_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with exclusive_lock(path, timeout_s=BRIEFING_LOG_LOCK_TIMEOUT_SECONDS):
            data: dict = {"entries": []}
            if path.exists():
                grund = lesefehler(path)
                if grund is None:
                    data = json.loads(path.read_text(encoding="utf-8"))
                elif lege_beschaedigte_datei_beiseite(
                    path, grund, datetime.now(tz=timezone.utc), logger,
                ) is None:
                    return  # Original bleibt; ERROR ist geloggt (#2231)
            if not isinstance(data.get("entries"), list):
                data["entries"] = []
            data["entries"].append(eintrag)
            atomic_write_json(path, data)
    except LockTimeout:
        logger.error(
            "briefing_log: Sperre nicht erhalten -- Eintrag NICHT geschrieben "
            "(user=%s): %s",
            user_id, json.dumps(eintrag, ensure_ascii=False, default=str),
        )
