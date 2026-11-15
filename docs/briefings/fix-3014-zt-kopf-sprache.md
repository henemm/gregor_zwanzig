---
spec_file: docs/specs/modules/i18n_zt_kopf_sprache_3014.md
spec_sha256: 342dc5688e18110dd6862f38bf2e2c4ba0026fefefb316015169fa4e88130051
spec_frozen_sha256: f639f81ba87b2ea6dc965bb714c6f157309251d738018eb78d9533667c0656d8
---

# PO-Briefing: fix-3014-zt-kopf-sprache

- **Spec:** docs/specs/modules/i18n_zt_kopf_sprache_3014.md
- **Issue:** #3014
- **Erstellt:** 2026-11-15

## Was gebaut wird

Englische Telegram-Briefings zeigen in der Tabelle "Hr" statt des deutschen Kürzels "Zt"; Deutsch bleibt unverändert.

## Definition of Done

Englisches Telegram-Briefing und englisches Startseiten-Bild zeigen "Hr", die deutsche Nachricht ist identisch zu vorher, und alle automatischen Prüfungen sind grün.

## Wie geprüft wird

Automatische Tests prüfen Kopf, Zeilenlänge und unveränderten deutschen Stand; das neue Startseiten-Bild wird nur per Sichtprüfung kontrolliert.

## Kritische Anmerkungen

- Englisch heisst bewusst "Hr", nicht "Time": längerer Kopf würde die Tabellenzeile umbrechen. Das Ticket nannte beide Varianten.
- Startseiten-Bild ist nur per Augenschein geprüft, nicht automatisch.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
