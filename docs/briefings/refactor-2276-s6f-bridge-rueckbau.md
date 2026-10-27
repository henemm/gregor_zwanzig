---
spec_file: docs/specs/modules/rework_2276_s6f_bridge_umzug.md
spec_sha256: 1003665d8c5fdfeb98785dece8312b423f63f5890a057526110420a844733425
---

# PO-Briefing: refactor-2276-s6f-bridge-rueckbau

- **Spec:** docs/specs/modules/rework_2276_s6f_bridge_umzug.md
- **Issue:** #2276 (Epic #2345)
- **Erstellt:** 2026-09-22

## Was gebaut wird

Der Ortsvergleich wird intern aufgeräumt: eine alte Verbindungs-Datei wird durch zwei sauber getrennte Bausteine ersetzt, Verhalten bleibt gleich.

## Definition of Done

Die alte Klebeschicht existiert nicht mehr, alle bestehenden Wetter-Vergleichs-Funktionen (Orte, Alarme, Versand, Aktivieren/Pausieren) verhalten sich unverändert.

## Wie geprüft wird

Automatisierte Tests und ein neuer Kern-Test weisen nach, dass die alte Datei komplett verschwunden ist und sich sonst nichts ändert.

## Kritische Anmerkungen

- Issue #2276 bleibt nach dieser Scheibe offen — ein Teil der Anforderung folgt erst in Scheibe S6g.
- Reiner technischer Umbau ohne sichtbare Änderung — Bedienung, Aussehen und Ablauf bleiben für Nutzer:innen exakt gleich.

## Freigabe-Frage

Ist es in Ordnung, dass Issue #2276 nach dieser Scheibe weiterhin offen bleibt, weil ein Teil erst in einer Folge-Scheibe (S6g) kommt?
