---
spec_file: docs/specs/modules/feat_3096_mail_resolver.md
spec_sha256: 04712b63b29206c4d9694de3e6fe54f10760eecdf8cd1663530346905e913379
spec_frozen_sha256: 0572ae7a9c755c0cc285c732e278e1f3924f45f1004a16d6e0d94c35c1f806a6
---

# PO-Briefing: feat-3096-mail-resolver

- **Spec:** docs/specs/modules/feat_3096_mail_resolver.md
- **Issue:** #3096
- **Erstellt:** 2026-11-17

## Was gebaut wird

Trip- und Orte-Mails holen Spalten und Reihenfolge aus einer gemeinsamen Quelle; alte Parallelwege werden gelöscht, Mails bleiben unverändert.

## Definition of Done

Zugestellte Trip- und Orte-Mails auf Staging sind Zeichen für Zeichen gleich wie vorher, die alten Rechenwege sind entfernt, alle Prüfungen grün.

## Wie geprüft wird

Referenz-Mails und Prüfkatalog vergleichen Zeichen für Zeichen, ein Zwei-Nutzer-Test sichert Trennung; Telegram und SMS bleiben unberührt, Darstellung nicht vereinheitlicht.

## Kritische Anmerkungen

- Darstellung (Roh oder Katalog) kommt beim Trip weiter aus der alten Quelle, nicht aus der neuen; Vereinheitlichung bewusst ausgeklammert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
