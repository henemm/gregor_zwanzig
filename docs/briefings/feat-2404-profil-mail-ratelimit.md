---
spec_file: docs/specs/bugfix/profile_mail_ratelimit.md
spec_sha256: 2d02523ffd69451bdd2e393df2ef099d3e72dbb89a9e66fd4c352e96b7996ef0
---

# PO-Briefing: feat-2404-profil-mail-ratelimit

- **Spec:** docs/specs/bugfix/profile_mail_ratelimit.md
- **Issue:** #2404 (S2 von #2153, Epic #2138)
- **Erstellt:** 2026-09-22

## Was gebaut wird

Bestätigungsmails bei Adressänderung im Profil werden je Nutzer und je Zieladresse auf 10 pro Stunde begrenzt.

## Definition of Done

Der elfte Adresswechsel je Nutzer oder Zieladresse innerhalb einer Stunde wird abgelehnt, ohne Speicherung oder Mailversand.

## Wie geprüft wird

Automatisierte Go-Tests simulieren elf Adresswechsel, geteilte Zieladressen zweier Nutzer und Nachversand; echtes Betriebsverhalten wird nicht beobachtet.

## Kritische Anmerkungen

- Nachversand meldet bei erreichtem Limit weiter "erfolgreich" — der Nutzer erfährt nicht, dass keine Mail ankam.
- Bei Limit-Überschreitung gehen auch unbeteiligte Änderungen wie der Anzeigename im selben Antrag verloren.
- Ob die Fehlermeldung im Web-Formular verständlich erscheint, ist nicht gesichert Teil dieser Lieferung.

## Freigabe-Frage

Ist akzeptabel, dass Nutzer beim Nachversand-Limit keine Fehlermeldung sehen und harmlose Profiländerungen mitverworfen werden?
