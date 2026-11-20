---
spec_file: docs/specs/modules/fix_3133_premium_antwort_laenge.md
spec_sha256: a39da9b0c4ea0334b17dab520a9cfc71662347b7783a59e06a80bc6ed09723ad
spec_frozen_sha256: 6589851545819956506f2252e0fa80976e460e36be2a8b2afe77931fcbacf3bb
---

# PO-Briefing: fix-3133-premium-antwort-laenge

- **Spec:** docs/specs/modules/fix_3133_premium_antwort_laenge.md
- **Issue:** #3133
- **Erstellt:** 2026-11-20

## Was gebaut wird

Jede Premium-SMS-Antwort passt in eine Nachricht; lange Hilfe und Kürzelliste lassen sich seitenweise abfragen.

## Definition of Done

Auf der zweiten Nummer kommen HILFE, HILFE 2 und KUERZEL je als eine Nachricht bis 153 Zeichen an, mit Verweis „more:“.

## Wie geprüft wird

Tests senden Befehle durch den echten Premium-Eingang (Deutsch, Englisch, zwei Nutzer) und prüfen Länge, Vollständigkeit und Kontingent; Live-Empfang bleibt manuell.

## Kritische Anmerkungen

- Andere lange Antworten (Status, Strecke) werden nur abgeschnitten, nicht geseitet; Inhalt geht verloren, Folge-Ticket nur bei Bedarf.
- Verweis, Seitenfehler und Unbekannt-Hinweis sind für alle Konten englisch, wie von dir nachentschieden.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
