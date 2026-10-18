---
spec_file: docs/specs/modules/etappen_bauliche_aenderung_speichern.md
spec_sha256: 789f359278f97abdb3ad35b8e60eaf978618d28e2dd0dfa6896d4b23f1319b30
spec_frozen_sha256: 9c3fd431b7b6a0dda81621965d53a00fe72d2d4b2aa9b64a7d82149ae7b84bac
---

# PO-Briefing: fix-2213-etappen-bauliche-aenderung-speichern

- **Spec:** docs/specs/modules/etappen_bauliche_aenderung_speichern.md
- **Issue:** #2213
- **Erstellt:** 2026-10-18

## Was gebaut wird

Etappen und Wegpunkte, die du hinzufügst, löschst oder als Pausentag einfügst, werden im Trip sofort automatisch gespeichert.

## Definition of Done

Nach Hinzufügen, Löschen, Pausentag oder Wegpunkt-Änderung zeigt das Neuladen der Seite den neuen Stand, ohne dass etwas verloren geht.

## Wie geprüft wird

Automatische Tests prüfen jeden Fall einzeln auf genau einmaliges Speichern; Browser-Tests nur Hinzufügen, Löschen und Sperre, nicht Wegpunkte oder Pausentag.

## Kritische Anmerkungen

- Mehr als das Issue: auch Wegpunkte und Höhenprofil-Klicks speichern sofort, mit mehreren Speichervorgängen bei Klick-Serien.
- Während der Datumsverschiebung (bis 15 Sekunden) sind Höhenprofil und Wegpunkte sichtbar gesperrt; Eingaben werden verweigert, nicht vorgemerkt.
- Das Issue ließ offen, ob automatisch gespeichert wird; die Spec entscheidet "sofort", ohne diese Wahl dir vorzulegen.

## Freigabe-Frage

Sollen Etappen- und Wegpunkt-Änderungen im Trip künftig sofort automatisch gespeichert werden, inklusive kurzer Sperre während der Datumsverschiebung?
