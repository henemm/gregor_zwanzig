---
spec_file: docs/specs/fast/fix-3200-rueckfrage-153.md
spec_sha256: 8cfc41b8ba33dc4dd25736cc463075dc1508e3533a85c2c81f5243e64dce63fa
spec_frozen_sha256: bad61858cb1a2bec0e1ed0eb8bad92a92c21d728ccfd7fe093c4a859a51db984
---

# PO-Briefing: fix-3200-rueckfrage-153

- **Spec:** docs/specs/fast/fix-3200-rueckfrage-153.md
- **Issue:** #3200
- **Erstellt:** 2026-11-20

## Was gebaut wird

Die Rückfrage bei mehrdeutigen Premium-SMS-Befehlen passt künftig in 153 Zeichen und kommt mit allen Kandidaten samt Antwort-Hinweis an.

## Definition of Done

Eine mehrdeutige Premium-SMS-Anfrage liefert eine Rückfrage von höchstens 153 Zeichen ohne abgeschnittenes Ende; Telegram-Rückfragen behalten ihre vollen Namen.

## Wie geprüft wird

Automatische Tests prüfen Länge, Vollständigkeit, Telegram-Unverändertheit und Eindeutigkeit der Kürzung; nicht geprüft werden Fälle, in denen Namen erst sehr spät eindeutig werden.

## Kritische Anmerkungen

- Seiten- oder Nummernantwort aus dem Issue-Zusatz bewusst weggelassen: Bei spät eindeutigen Namen bleiben Kandidaten unerreichbar (bekannte Einschränkung).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
