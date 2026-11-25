---
spec_file: docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md
spec_sha256: 9bd778c846292311b254024232660d1ddfa15139a3aed9abe8f715529314adb4
spec_frozen_sha256: 3717a997240fad3b42b38a715e85734b75781d235d306a3fd6b4b9cb58fc4e87
---

# PO-Briefing: rework-3020-pruefungen-und-waisen

- **Spec:** docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md
- **Issue:** #3020
- **Erstellt:** 2026-11-25

## Was gebaut wird

Die Prüfung der Fallliste wird ehrlich, und Prüfungen für heute noch lebendes Verhalten werden wiederhergestellt.

## Definition of Done

Erfundene Testverweise in der Fallliste werden rot gemeldet, und jedes noch lebende Verhalten der 20 zugeordneten Dateien hat eine grüne Prüfung.

## Wie geprüft wird

Automatische Tests mit zwei Nutzern und Gegenproben belegen Wächter und Verhalten; Browser-Abläufe und die Zuordnungsliste bleiben ungeprüft.

## Kritische Anmerkungen

- Die Kennzeichnung "Nur ein Bericht" im Editor entfällt bewusst: Übergangshilfe bis #3065, auf Prod betrifft sie null Metriken. Mit Freigabe bestätigt.
- 44 der 60 Dateien gelten als "prüfte nur gelöschten Code" oder Altfelder; das ist Einschätzung des Tech Leads, nicht nachgeprüft.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
