---
spec_file: docs/specs/modules/feat_3260_s1c_zusammenfassung_telegram.md
spec_sha256: 4ae6cd2b965e21c89851e496dad409ee078d10cfd5a25802f37fd526b6215804
spec_frozen_sha256: d683f669e3a0269805960e8e9272c675a8934be9eda7f2f80139baddfc034210
---

# PO-Briefing: feat-3260-s1c-zusammenfassung

- **Spec:** docs/specs/modules/feat_3260_s1c_zusammenfassung_telegram.md
- **Issue:** #3260
- **Erstellt:** 2026-11-27

## Was gebaut wird

Kurz-Zusammenfassung nennt Gewitter mit Stufenwort und Windrichtung unabhängig vom Umschalter; Orte-Telegram zeigt keine Stunden-Marke an der Windrichtung.

## Definition of Done

Echte Staging-Mail zeigt „Gewitter mittel“ mit Zeitfenster in beiden Umschalter-Stellungen, und das Orte-Telegram trägt an der Windrichtung keine Stunden-Marke.

## Wie geprüft wird

Tests rendern echte Mails und Telegram für Deutsch, Englisch, beide Umschalter und zwei Nutzer; SMS wird nicht geprüft, da unberührt.

## Kritische Anmerkungen

- Sichtbare Textänderung: „Gewitter möglich“ wird zu „Gewitter mittel/hoch“; viele Referenz-Mails werden dafür neu erzeugt.
- Wind-Wortskala der Zusammenfassung (inkl. „Sturm“) weicht bis Schritt 3 weiter von der Tabelle ab; bewusst verschoben.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
