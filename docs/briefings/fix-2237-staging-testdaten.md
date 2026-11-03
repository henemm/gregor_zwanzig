---
spec_file: docs/specs/bugfix/fix_2237_staging_testdaten.md
spec_sha256: 189c8ba7c1defad0a70329cbf3c4532493d502e35a9188e93eba370862c241e5
spec_frozen_sha256: 6c3ebf870c43744d6fd657a67ed5f9c42e83b5e02ba1f55d5f4405293896ac1f
---

# PO-Briefing: fix-2237-staging-testdaten

- **Spec:** docs/specs/bugfix/fix_2237_staging_testdaten.md
- **Issue:** #2237
- **Erstellt:** 2026-11-03

## Was gebaut wird

Der nächtliche Staging-Aufräumlauf bereinigt den richtigen Datenordner, und Löschen von Trips und Vergleichen hinterlässt keine Reste.

## Definition of Done

Alte Testdaten sind aus Staging verschwunden, Schutz-Konten bestehen weiter, kein Konto teilt Kontaktdaten, und Löschen hinterlässt keine Dateireste.

## Wie geprüft wird

Tests mit echten Dateien belegen Aufräumlauf und Löschen samt Nutzertrennung; die Konten- und Datenbereinigung wird nur manuell gemessen.

## Kritische Anmerkungen

- Ticketpunkte zum Konto gregor_zwanzig_staging (Kontaktdaten, Test-Presets) entfallen, weil es im Staging nicht existiert.
- Bereinigung löschte bereits sechs Test-Konten, obwohl die Spec noch Entwurf ist.
- Konten-Bereinigung hat keinen automatischen Test.

## Freigabe-Frage

Dürfen die Ticketpunkte zum nicht vorhandenen Konto gregor_zwanzig_staging ersatzlos entfallen?

## Ampel

Ampel: rot
