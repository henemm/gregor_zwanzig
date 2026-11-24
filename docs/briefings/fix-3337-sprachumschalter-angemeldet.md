---
spec_file: docs/specs/modules/sprachumschalter_angemeldet_3337.md
spec_sha256: c93254217a1bd9e576e6dee1e147b11887b0fa009fe0a98488b3a9f8277b618b
spec_frozen_sha256: 25cfcfac3447586a592970e05257e740b1862ddd0a4024de8859cf43b3e2c153
---

# PO-Briefing: fix-3337-sprachumschalter-angemeldet

- **Spec:** docs/specs/modules/sprachumschalter_angemeldet_3337.md
- **Issue:** #3337
- **Erstellt:** 2026-11-24

## Was gebaut wird

Angemeldete sehen auf den Funktionsseiten statt des wirkungslosen Sprach-Umschalters einen Hinweis mit Link zur Sprachwahl im Konto.

## Definition of Done

Angemeldet zeigen die Funktionsseiten in Deutsch und Englisch den Hinweis samt funktionierendem Link, Besucher ohne Anmeldung behalten den wirksamen Umschalter, Produktion ist ausgeliefert.

## Wie geprüft wird

Automatische Tests prüfen alle vier Kombinationen (angemeldet oder nicht, Deutsch oder Englisch); Staging prüft Link und Kontrast mit dem Prüfkonto.

## Kritische Anmerkungen

- Auf der Startseite „/“ ändert sich für Angemeldete nichts, da sie diese nie sehen; das Ticket nennt sie dennoch.
- Hinweistext („Die Sprache stellst du in deinem Konto ein.“) ist neu formuliert und wird mit Freigabe festgelegt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
