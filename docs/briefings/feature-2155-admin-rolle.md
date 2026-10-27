---
spec_file: docs/specs/modules/admin_rolle_s1.md
spec_sha256: e7bb4ef5e9511d4f401ef0cf4edaf745809ce15ce8a9dba7645206241ca2cbdd
---

# PO-Briefing: feature-2155-admin-rolle

- **Spec:** docs/specs/modules/admin_rolle_s1.md
- **Issue:** #2155
- **Erstellt:** 2026-09-28

## Was gebaut wird

Nur Admins starten Betriebs-Auslöser; „Briefing senden" in der Trip-Liste sendet nur noch den gewählten Trip.

## Definition of Done

Normale Nutzer werden bei den drei Auslösern abgewiesen, Admins nicht, und der Knopf sendet genau einen Trip.

## Wie geprüft wird

Tests prüfen Admin, normalen Nutzer und Nichtangemeldete an den drei Auslösern sowie den Knopf; Server-Einstellung bleibt ungeprüft.

## Kritische Anmerkungen

- Anfrage verlangt auch Nutzerliste und Tier-Freigabe; diese Lieferung schützt nur die Auslöser, Ticket bleibt offen.
- Admin-Kennung unbekannt: ohne Server-Eintrag sind die Auslöser für alle gesperrt, auch den Betreiber.
- Ticket-Kommentar zum Schnitt nicht abrufbar; Abgleich nur gegen das Kontext-Dokument erfolgt.

## Freigabe-Frage

Geben Sie diese erste Lieferung frei, obwohl Nutzerliste und Tier-Freigabe erst später kommen?
