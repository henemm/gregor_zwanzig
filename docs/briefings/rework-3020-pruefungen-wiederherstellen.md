---
spec_file: docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md
spec_sha256: 2c7eb453a93773122e957bf4b7530cf511006266babda6c5441b88b6db11f332
spec_frozen_sha256: 181cfb2968e5ff00baedc201fa6ffcafcb87b6145f4c4eb7913c443a82911b2c
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

- Die Kennzeichnung "Nur ein Bericht" entfällt bewusst: Übergangshilfe bis #3065, auf Prod betrifft sie null Metriken.
- Beim Trip-Anlegen zeigt die Karte den Nachtblock-Schalter, weil #3305 die alte Regel "kein Schalter" abgelöst hat.
- 44 der 60 Dateien gelten als "prüfte nur gelöschten Code" oder Altfelder; Einschätzung des Tech Leads.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
