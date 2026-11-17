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
