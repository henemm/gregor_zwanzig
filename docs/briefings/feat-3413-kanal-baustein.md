---
spec_file: docs/specs/fast/feat-3413-kanal-baustein.md
spec_sha256: 1b2aab52c9933ba608061d57502750c4cab34a9830f33fcc2342f974b4920d21
spec_frozen_sha256: 17eace49e4506d3deb61510e6b932d142745a4d080ecca34749a5d68379cff64
---

# PO-Briefing: feat-3413-kanal-baustein

- **Spec:** docs/specs/fast/feat-3413-kanal-baustein.md
- **Issue:** #3413
- **Erstellt:** 2026-11-27

## Was gebaut wird

Die Kanal-Auswahl (E-Mail, Telegram, SMS, Premium-SMS) wird intern nur noch an einer Stelle ausgewertet, für Nutzer unsichtbar.

## Definition of Done

Hub-Übersicht und Zustellungs-Tab zeigen für jede Kombination der vier Kanal-Schalter exakt dieselben Kanäle wie vorher, und beide nutzen die gemeinsame Regel.

## Wie geprüft wird

Automatische Tests prüfen alle Schalter-Kombinationen gegen feste Erwartungen; das Aussehen im Browser wird nicht geprüft.

## Kritische Anmerkungen

- AC-4 (Verfälschungs-Gegenprobe) hat keinen eigenen Test, sondern wird nur vom Prüf-Agenten einmalig durchgeführt.
- Die unterschiedliche Schreibweise von Premium-SMS bleibt bewusst bestehen und wird an einer Stelle übersetzt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
