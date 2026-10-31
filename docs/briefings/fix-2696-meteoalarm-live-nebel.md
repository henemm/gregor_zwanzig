---
spec_file: docs/specs/fast/fix-2696-meteoalarm-live-nebel.md
spec_sha256: 09f5b6eb8ef5b90af02703274d348963a7d4bcee8568fa7b7965552806031abf
spec_frozen_sha256: 6640deb2c0fb35f4010b7f4bf0aa4e9572375c2e1e3d027cafc16c5895e5c735
---

# PO-Briefing: fix-2696-meteoalarm-live-nebel

- **Spec:** docs/specs/fast/fix-2696-meteoalarm-live-nebel.md
- **Issue:** #2696
- **Erstellt:** 2026-10-31

## Was gebaut wird

Die drei Live-Tests für amtliche Wetterwarnungen wählen keine Prüfzonen mehr aus, deren einzige Warnung Nebel ist.

## Definition of Done

Die drei Live-Tests melden bei Nebel-Warnungen keinen falschen Fehler mehr, sondern überspringen die Zone; die Nebel-Regel der App bleibt unverändert.

## Wie geprüft wird

Netzfreie Tests mit Beispiel-Warnungen belegen die Zonenauswahl für alle bekannten und verworfenen Warntypen; echte Live-Läufe bleiben manuell.

## Kritische Anmerkungen

- Die im Ticket als optional genannte Suche über alle Zonen fehlt bewusst; die Auswahl bleibt bei wenigen Prüfpunkten, häufiger SKIP möglich.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
