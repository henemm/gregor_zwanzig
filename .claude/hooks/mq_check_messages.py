#!/usr/bin/env python3
"""SessionStart-Hook: offene Claude-MQ-Alarme anzeigen, auf jedem Rechner.

Issue #3294 (Spec docs/specs/modules/imac_portabilitaet.md, AC-4 bis AC-6),
henemm-infra#487, henemm-security#219 (kein Secret auf dem iMac: die Abfrage
laeuft immer auf dem Server).

- Liegt das Server-Skript vor (GZ_MQ_CHECK_SCRIPT, Standard
  /home/hem/claude-mq/check-messages.sh), wird es direkt im aktuellen
  Verzeichnis aufgerufen (es leitet die Instanz aus $PWD ab).
- Sonst per SSH auf dem Server (GZ_MQ_SSH_HOST, Standard "henemm").
- Jeder Fehler: keine Ausgabe, Exit 0. Der Sitzungsstart blockiert nie.

Python statt Bash, damit der Eintrag in settings.json die Fail-open-Form
`if [ -f ... ]; then python3 ...; fi` hat (tests/tdd/test_issue_384_hook_fail_open.py).
Nur Standardbibliothek, Python-3.9-kompatibel (macOS), kein Projekt-Import.
"""

import os
import subprocess
import sys

DEFAULT_SCRIPT = "/home/hem/claude-mq/check-messages.sh"
REMOTE_COMMAND = "cd ~/gregor_zwanzig && bash ~/claude-mq/check-messages.sh"


def main():
    script = os.environ.get("GZ_MQ_CHECK_SCRIPT") or DEFAULT_SCRIPT
    if os.path.isfile(script):
        try:
            subprocess.run(["bash", script])
        except Exception:
            pass
        return

    host = os.environ.get("GZ_MQ_SSH_HOST") or "henemm"
    try:
        res = subprocess.run(
            [
                "ssh",
                "-o", "ConnectTimeout=3",
                "-o", "BatchMode=yes",
                "-o", "ServerAliveInterval=2",
                "-o", "ServerAliveCountMax=2",
                host,
                REMOTE_COMMAND,
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception:
        return
    ausgabe = (res.stdout or "").rstrip("\n")
    if res.returncode == 0 and ausgabe:
        sys.stdout.write(ausgabe + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
