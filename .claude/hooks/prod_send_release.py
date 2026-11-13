#!/usr/bin/env python3
"""Issue #2125 — Prod-Versand-Freigabe (UserPromptSubmit-Hook).

Eigener Notausgang des Prod-Send-Gates (#1148): Tippt der PO allein die
Phrase `prod-versand freigeben`, wird fuer genau diese Sitzung
(`session_id`) eine einmalig gueltige Freigabe (1 h) in
`<Haupt-Repo>/.claude/prod_send_release.json` geschrieben. Nur das
Prod-Send-Gate liest diese Datei; das allgemeine `override` oeffnet es nicht.

Der Hook blockiert nie (immer Exit 0); Erfolg und Fehler erscheinen als
sichtbare `systemMessage`.

Spec: docs/specs/modules/gate_2125_prod_send_release.md
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import hook_utils

PHRASE = "prod-versand freigeben"
TTL = timedelta(hours=1)


def _is_release_prompt(prompt: object) -> bool:
    """Nur die allein stehende Phrase zaehlt; Harness-Turns (`<...>`) nie."""
    if not isinstance(prompt, str):
        return False
    text = prompt.strip()
    if text.startswith("<"):
        return False
    return text.lower() == PHRASE


def _say(message: str) -> None:
    print(json.dumps({"systemMessage": message}, ensure_ascii=False))


def _write_release(session_id: str, now: datetime) -> None:
    def _add(releases: dict):
        releases[session_id] = {"created": now.isoformat()}
        return True, None

    hook_utils.update_prod_send_releases(_add, create=True)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if not isinstance(data, dict) or not _is_release_prompt(data.get("prompt")):
        sys.exit(0)

    session_id = data.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        _say("Prod-Versand NICHT freigegeben: Sitzung unbekannt (keine session_id).")
        sys.exit(0)

    now = datetime.now(timezone.utc)
    try:
        _write_release(session_id, now)
    except Exception as exc:
        _say(f"Prod-Versand NICHT freigegeben: Freigabe konnte nicht geschrieben werden ({exc}).")
        sys.exit(0)

    until = (now + TTL).astimezone().strftime("%H:%M")
    _say(
        f"Prod-Versand freigegeben: ein einziger Versand-Aufruf in dieser "
        f"Sitzung, gueltig 1 Stunde (bis {until} Uhr)."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
