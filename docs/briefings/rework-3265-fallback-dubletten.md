---
spec_file: docs/specs/modules/rework_3265_fallback_dubletten.md
spec_sha256: fdde7edd92305db4d1fc268f071c6ec3d237937de4d71d65ca177f8a33124a75
spec_frozen_sha256: 3069cdef4310f61d81548d9b394a5e46ea19ce66bfe917e6dfb0c7e1594410db
---

# PO-Briefing: rework-3265-fallback-dubletten

- **Spec:** docs/specs/modules/rework_3265_fallback_dubletten.md
- **Issue:** #3265
- **Erstellt:** 2026-11-23

## Was gebaut wird

Eine einzige doppelte Prüfung in den Ausweich-Tests für Wetterdienste wird entfernt; für Nutzer ändert sich nichts.

## Definition of Done

Die vier Testdateien laufen vollständig grün, der doppelte Fall ist weg, und ein Protokoll belegt, dass kein Schutz verloren ging.

## Wie geprüft wird

Gezielt eingebaute Fehler werden vor und nach der Löschung von den Tests bemerkt; geprüft wird nur die Testsammlung, nicht das Produktverhalten.

## Kritische Anmerkungen

- Ausbeute winzig: nur ein Fall von vier Dateien ist wirklich doppelt, alles andere bleibt bewusst unverändert.
- Begründungen, warum ähnliche Paare bleiben, werden nur im Review gelesen, nicht automatisch geprüft.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
