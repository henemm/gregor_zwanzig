---
spec_file: docs/specs/modules/feat_3096_mail_resolver.md
spec_sha256: 45f61bfe4389937d421d89226ca6cc857f7d9203ebde68f2a9b5634bf995e9e8
spec_frozen_sha256: b51bf2478519601d0f22b1a96e916978c2b41c86231307385ec57cb7e8ca61b8
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

Referenz-Mails und Prüfkatalog vergleichen Zeichen für Zeichen, ein Zwei-Nutzer-Test sichert Trennung; Telegram und SMS bleiben unberührt.

## Kritische Anmerkungen

- Update-/Alarm-Mails folgen künftig der E-Mail-Auswahl (von dir entschieden); im Livebetrieb noch nicht sichtbar, da Alarme eigenen Renderer nutzen.
- Darstellung (Roh oder Katalog) bleibt bewusst uneinheitlich; Vereinheitlichung wäre eigenes Ticket.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
