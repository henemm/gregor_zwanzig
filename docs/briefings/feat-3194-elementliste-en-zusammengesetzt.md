---
spec_file: docs/specs/modules/feat_3194_elementliste_en_zusammengesetzt.md
spec_sha256: 51ba282bcf5a78bcb7b88cd9c78b7ad5bc624d5e4d9d6f6e673d5e510e30c75c
spec_frozen_sha256: 63b4e8b44e2e2075b92ebfe95ce70060135509c98d46f366c28fe34da82d6ac2
---

# PO-Briefing: feat-3194-elementliste-en-zusammengesetzt

- **Spec:** docs/specs/modules/feat_3194_elementliste_en_zusammengesetzt.md
- **Issue:** #3194
- **Erstellt:** 2026-11-20

## Was gebaut wird

Das Prüfwerkzeug erkennt zusammengesetzte Wetter-Dialogtexte künftig auch auf Englisch, nur aus vorhandenen Katalogtexten, ohne erfundene Übersetzungen.

## Definition of Done

100 bisherige englische Lücken sind gelöst, nur echte Restfälle bleiben offen, und der Englisch-Abgleich auf Staging zeigt keine neue Abweichung.

## Wie geprüft wird

Tests gegen den echten Katalog prüfen Treffer, Fehlfälle und Wiederholbarkeit; die Staging-Prüfung zeigt keine neuen Abweichungen, Live-Varianten ohne Mockup-Bild bleiben ungeprüft.

## Kritische Anmerkungen

- Live-Texte „genau ein Ort“ und „Verlust“-Zeile fehlen im Mockup und bleiben unzugeordnet (dokumentierte Einschränkung).
- Etwa 8 Restfälle (Eigenname, Metriknamen, Zusatztexte) bleiben bewusst offen; für sie braucht es ein eigenes Issue.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
