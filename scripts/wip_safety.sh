#!/usr/bin/env bash
# WIP-Sicherung vor einem harten Reset (gregor_zwanzig#2047, Scheibe 1).
#
# Sichert uncommittete getrackte Arbeit in <repo_dir> als Stash-Objekt + Tag,
# BEVOR der Aufrufer `git reset --hard origin/main` ausfuehrt. Vorbild:
# henemm-infra/scripts/deploy-gregor-prod.sh (Sicherheitsnetz vor dem Reset).
#
# Bewusst `git stash create` statt `git stash push`: der Arbeitsbaum bleibt
# unveraendert, weil der Checkout mit anderen Sessions geteilt wird. Untrackte
# Dateien werden nicht erfasst — der nachfolgende Reset fasst sie ebenfalls nicht an.
#
# Usage: bash scripts/wip_safety.sh <repo_dir>
# Exit 0: nichts zu sichern ODER erfolgreich gesichert.
# Exit != 0: Sicherung fehlgeschlagen — der Aufrufer darf NICHT hart resetten.
set -u

REPO_DIR="${1:-}"
if [ -z "$REPO_DIR" ]; then
    echo "FEHLER: Repo-Verzeichnis fehlt. Usage: wip_safety.sh <repo_dir>" >&2
    exit 2
fi
if ! git -C "$REPO_DIR" rev-parse --git-dir >/dev/null 2>&1; then
    echo "FEHLER: '$REPO_DIR' ist kein Git-Repository — Abbruch vor dem harten Reset" >&2
    exit 2
fi

# Sauberer Arbeitsbaum: keine Aktion, keine Ausgabe.
if git -C "$REPO_DIR" diff --quiet 2>/dev/null && git -C "$REPO_DIR" diff --cached --quiet 2>/dev/null; then
    exit 0
fi

SAFETY=$(git -C "$REPO_DIR" stash create "ci-wip-safety $(date -u +%FT%TZ)" 2>/dev/null || true)
SAFETY=$(echo "$SAFETY" | tr -d '[:space:]')

if [ -z "$SAFETY" ]; then
    echo "FEHLER: Uncommittete Arbeit in '$REPO_DIR' konnte NICHT gesichert werden" >&2
    echo "       (git stash create lieferte kein Stash-Objekt) — Abbruch, damit kein" >&2
    echo "       harter Reset die ungesicherte Aenderung verwirft." >&2
    exit 1
fi

# Tag-Name traegt zusaetzlich zur UTC-Sekunde die Kurzform des Stash-Objekts: zwei
# Merges in derselben Sekunde (kein `concurrency:`-Gate im deploy-Job) wuerden sonst
# im Namen kollidieren und den Lauf abbrechen, obwohl die Sicherung gelungen ist.
TAG="deploy-safety/ci-$(date -u +%Y%m%d-%H%M%S)-${SAFETY:0:12}"
if ! git -C "$REPO_DIR" tag "$TAG" "$SAFETY" 2>/dev/null; then
    # Unveraenderte WIP-Arbeit ergibt in derselben UTC-Sekunde dasselbe Stash-Objekt und
    # damit denselben Tag-Namen. Zeigt der vorhandene Tag auf genau dieses Objekt, ist die
    # Arbeit bereits gesichert — Erfolg, kein Fehler (sonst blockiert jeder zweite Merge).
    EXISTING=$(git -C "$REPO_DIR" rev-parse --verify --quiet "refs/tags/$TAG^{}" 2>/dev/null || true)
    if [ -n "$EXISTING" ] && [ "$EXISTING" = "$SAFETY" ]; then
        echo "Uncommittete Aenderungen sind bereits gesichert: $SAFETY (Tag $TAG)"
        echo "  Der vorhandene Tag zeigt auf genau diesen Stand — die Arbeit ist sicher."
        echo "  Wiederherstellen mit: git -C $REPO_DIR stash apply $TAG"
        exit 0
    fi
    echo "FEHLER: Uncommittete Arbeit in '$REPO_DIR' ist NICHT gesichert." >&2
    echo "       Das Stash-Objekt $SAFETY wurde zwar erzeugt, aber der Tag '$TAG' liess" >&2
    echo "       sich nicht setzen (Namensraum belegt oder Tag zeigt auf einen anderen" >&2
    echo "       Stand) — ohne Tag sammelt die GC das Objekt ein und die Aenderung ist" >&2
    echo "       verloren. Abbruch vor dem harten Reset." >&2
    exit 1
fi

echo "Uncommittete Aenderungen gesichert: $SAFETY (Tag $TAG)"
echo "  Wiederherstellen mit: git -C $REPO_DIR stash apply $TAG"
exit 0
