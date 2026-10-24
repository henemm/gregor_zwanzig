---
spec_file: docs/specs/modules/feat_1969_naechstes_briefing.md
spec_sha256: 82e720178f0a9a505b88d44c06ff1c298e80dba3f57bb318f90e518a3d854f4e
spec_frozen_sha256: b242a80a93c93c911f091c47731a3fddcb247434495e22d5deeffa3bfeab873f
---

# PO-Briefing: feat-1969-naechstes-briefing

- **Spec:** docs/specs/modules/feat_1969_naechstes_briefing.md
- **Issue:** #1969
- **Erstellt:** 2026-10-23

## Was gebaut wird

Nutzer sehen pro Trip und Ortsvergleich im Versand-Reiter, wann ihr nächstes Briefing verschickt wird, oder warum keines ansteht.

## Definition of Done

Im Versand-Reiter erscheinen Wochentag, volle Stunde und Zonenkürzel des nächsten Versands, bei Pause oder Ende der Grund.

## Wie geprüft wird

Tests prüfen Zeiten, Zonen, Pause und Überspringen gegen dieselbe Regel wie der Versand, nicht aber pünktlichen Echtversand.

## Kritische Anmerkungen

- Abweichung vom Ticket: Anzeige im Versand-Reiter statt Konto-Seite; Konto zeigt weiter nur den stündlichen Prüftakt.
- Zusatzumfang: Startseite, Vergleichsliste und Mail-Fußtext werden mit umgebaut (ca. 600 Codezeilen).
- Angezeigte Zeit ist geplant; tatsächlicher Versand kann bis zu 2 Stunden später erfolgen.

## Freigabe-Frage

Soll die Anzeige im Versand-Reiter statt auf der Konto-Seite entstehen, inklusive Umbau von Startseite und Mail-Fuß?
