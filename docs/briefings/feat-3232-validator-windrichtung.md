---
spec_file: docs/specs/modules/feat_3232_validator_windrichtung.md
spec_sha256: 030c2fd671a744efa95cfd553cd891c746a907ac4cfb91e9840f11cd45505aa9
spec_frozen_sha256: 9f8138e5f7d56be7569d55c33c03c77130421648055d653674bf6a12847719c2
---

# PO-Briefing: feat-3232-validator-windrichtung

- **Spec:** docs/specs/modules/feat_3232_validator_windrichtung.md
- **Issue:** #3232
- **Erstellt:** 2026-11-21

## Was gebaut wird

Die Mail-Prüfprogramme kontrollieren künftig Tönung und Ampelpunkt der Windrichtung in Trip- und Vergleichs-Mails gegen ein festes Soll.

## Definition of Done

Beide Prüfprogramme bestehen eine echt zugestellte Staging-Mail mit dem Soll, melden jede bewusst verfälschte Wind-Zelle genau einmal, und alte Prüfungen bleiben grün.

## Wie geprüft wird

Echt gerenderte Mails werden gezielt verfälscht und müssen gemeldet werden; Staging-Zustellung wird live geprüft, die Aufrufzeile im Befehl nur per Textvergleich.

## Kritische Anmerkungen

- Zusätzlich zum Ticket: Fehlermeldung bei ungültiger Eingabe, Hinweis bei Kurzformat-Mails, strengere Punkt-Prüfung. Reine Absicherung, keine Produktänderung.
- Prüfung gilt nur für das Format "full" und positionsabhängig; Kurzformat-Mails liefern nur einen Hinweis.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
