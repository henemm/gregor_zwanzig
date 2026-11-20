---
spec_file: docs/specs/modules/fix_3133_premium_antwort_laenge.md
spec_sha256: 7732787778159682de5007e8657e77d6354ef1955a4aa7e053a1399e632c6253
spec_frozen_sha256: c77fdac12506d7d716968d1cebd6a24f7cfcbf26c7215ce85531142036b87cb7
---

# PO-Briefing: fix-3133-premium-antwort-laenge

- **Spec:** docs/specs/modules/fix_3133_premium_antwort_laenge.md
- **Issue:** #3133
- **Erstellt:** 2026-11-20

## Was gebaut wird

Jede Premium-SMS-Antwort passt in eine Nachricht; lange Hilfe und Kürzelliste lassen sich seitenweise abfragen.

## Definition of Done

Auf der zweiten Nummer kommen HILFE, HILFE 2 und KUERZEL je als eine Nachricht bis 153 Zeichen an, mit Verweis „mehr:“.

## Wie geprüft wird

Tests senden Befehle durch den echten Premium-Eingang (Deutsch, Englisch, zwei Nutzer) und prüfen Länge, Vollständigkeit und Kontingent; Live-Empfang bleibt manuell.

## Kritische Anmerkungen

- Andere lange Antworten (Status, Strecke) werden nur abgeschnitten, nicht geseitet; Inhalt geht verloren, Folge-Ticket nur bei Bedarf.
- Zusätzlich eingebaut: gekürzter Text bei unbekanntem Befehl und Grenze 153 statt 160 bei Etappenwetter-Kurzform.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
