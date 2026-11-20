---
spec_file: docs/specs/fast/fix-3200-rueckfrage-153.md
spec_sha256: fd0928cc6e9bb5284e61e96e8e155004c47e7eff33db02e1670e6e0b1d8728d5
spec_frozen_sha256: 05ec77107b4958d6996954c909053a75271f898a8055a355a8ecbbb9b3ed6f19
---

# PO-Briefing: fix-3200-rueckfrage-153

- **Spec:** docs/specs/fast/fix-3200-rueckfrage-153.md
- **Issue:** #3200
- **Erstellt:** 2026-11-20

## Was gebaut wird

Die Premium-SMS-Rückfrage bei mehrdeutigem Befehl wird auf 153 Zeichen zugeschnitten, sodass Kandidaten und Antwort-Hinweis vollständig ankommen.

## Definition of Done

Eine mehrdeutige Premium-SMS-Anfrage liefert eine Rückfrage mit höchstens 153 Zeichen, ohne abgeschnittenes Ende, mit allen Kandidaten und vollständigem Hinweis; Telegram bleibt unverändert.

## Wie geprüft wird

Automatische Tests prüfen Länge, Vollständigkeit, Telegram-Unverändertheit und Eindeutigkeit der Kürzung; nicht geprüft wird die Lage bei spät eindeutigen Namen.

## Kritische Anmerkungen

- Spät eindeutige Namen passen weiterhin nie in 153 Zeichen; Kandidaten fallen weg. Seiten-/Nummernantwort bewusst ausgeklammert, bleibt bekannte Einschränkung.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
