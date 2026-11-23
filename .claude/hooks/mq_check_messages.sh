#!/bin/bash
# SessionStart-Hook: offene Claude-MQ-Alarme anzeigen, auf jedem Rechner.
# Issue #3294 (Spec docs/specs/modules/imac_portabilitaet.md, AC-4 bis AC-6),
# henemm-infra#487, henemm-security#219 (kein Secret auf dem iMac: die Abfrage
# laeuft immer auf dem Server).
#
# - Liegt das Server-Skript vor (GZ_MQ_CHECK_SCRIPT, Standard
#   /home/hem/claude-mq/check-messages.sh), wird es direkt im aktuellen
#   Verzeichnis aufgerufen (es leitet die Instanz aus $PWD ab).
# - Sonst per SSH auf dem Server (GZ_MQ_SSH_HOST, Standard "henemm").
# - Jeder Fehler: keine Ausgabe, Exit 0. Der Sitzungsstart blockiert nie.
# Bewusst ohne `set -e` und ohne bash-4-Features (macOS-bash 3.2).

SCRIPT="${GZ_MQ_CHECK_SCRIPT:-/home/hem/claude-mq/check-messages.sh}"

if [ -f "$SCRIPT" ]; then
    bash "$SCRIPT"
    exit 0
fi

AUSGABE=$(ssh -o ConnectTimeout=3 -o BatchMode=yes -o ServerAliveInterval=2 \
    -o ServerAliveCountMax=2 "${GZ_MQ_SSH_HOST:-henemm}" \
    'cd ~/gregor_zwanzig && bash ~/claude-mq/check-messages.sh' 2>/dev/null)
if [ $? -eq 0 ] && [ -n "$AUSGABE" ]; then
    printf '%s\n' "$AUSGABE"
fi
exit 0
