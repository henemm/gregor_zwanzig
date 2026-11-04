---
spec_file: docs/specs/bugfix/e2e_verify_en_mailweg_2813.md
spec_sha256: 43180c64b21b11a36a0a4e9e86ac9d9766fab67a8a100458e17d112f611c8b63
spec_frozen_sha256: 4065b538a87600b00d0762fe98cfe4013487620aa4b3c5d7ad7a99156ecab7ba
---

# PO-Briefing: fix-2813-e2e-en-mailweg

- **Spec:** docs/specs/bugfix/e2e_verify_en_mailweg_2813.md
- **Issue:** #2813
- **Erstellt:** 2026-11-04

## Was gebaut wird

Die Freigabe-Prüfwerkzeuge werden verlässlicher: lauter Abbruch statt falschem Erfolg, Auswahl der frischen Alarm-Mail, saubere Telegram-Tests.

## Definition of Done

Englischer Versand aus dem Arbeitsverzeichnis bricht laut ab, Alarm-Prüfer wählen die Mail mit Lauf-Kennung, Telegram-Tests enden ohne Wächter-Fehler.

## Wie geprüft wird

Automatische Tests belegen Abbruch, Mailauswahl und Aufräumen; die Anleitung wird nur per Textprüfung kontrolliert, echte Telegram-Läufe bleiben manuell.

## Kritische Anmerkungen

- Teil 1 des Tickets (englischer Mailweg über den Staging-Kern) fehlt bewusst, Folge-Ticket wegen Blocker 2774; Englisch bleibt dort unbelegt.
- Lauf-Kennung im Betreff ist nur für Gate-Mails gesichert, nicht für echte Alarm-Mails.

## Freigabe-Frage

Darfst du Teil 1 (englischer Mailweg über Staging) als Folge-Ticket abspalten, obwohl Issue 2813 ihn mit verlangt?

## Ampel

Ampel: rot
