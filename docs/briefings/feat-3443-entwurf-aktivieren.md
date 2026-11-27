---
spec_file: docs/specs/modules/feat_3443_entwurf_aktivieren.md
spec_sha256: 2e9b354a5ed67f0e43c280348e9236b32e7a1d7b7550b548a50c55156d52e615
spec_frozen_sha256: 0fc9761600a084628128e0e2c6adb9b62d19767bc477b3ca839939e6ed18e144
---

# PO-Briefing: feat-3443-entwurf-aktivieren

- **Spec:** docs/specs/modules/feat_3443_entwurf_aktivieren.md
- **Issue:** #3443
- **Erstellt:** 2026-11-27

## Was gebaut wird

Bei Entwürfen zeigt der Kopf einen Knopf „Aktivieren“, der nennt, was fehlt, und dorthin führt.

## Definition of Done

Im Entwurf nennt „Aktivieren“ (Knopf und erster Menüpunkt) das Fehlende und öffnet die Stelle; nach Ergänzen erscheint „Aktiviert“ mit Termin, ausgeliefert.

## Wie geprüft wird

Automatische Tests und Staging-Läufe mit selbst angelegten Entwürfen prüfen Trip und Orts-Vergleich, DE und EN; ein Vergleich ohne Namen nur im Kerntest.

## Kritische Anmerkungen

- Abweichung vom Mockup: Klick schaltet nicht ein, sondern nennt Fehlendes; entspricht deiner Entscheidung (Variante B vom 27.11.).
- Termin steht als „Do 29.10. 07:00 (CEST)“, nicht „morgen um 07:00“.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
