---
spec_file: docs/specs/modules/startseite_en_bilder_2777.md
spec_sha256: ce074c62215c17627d9d005a9e77a899b0e6dab38a79afcbd860796932efc428
spec_frozen_sha256: cf1bf8a4e2d3ca15da7018ae4a28c2fd9dcff7312c4e6cdb921d04c3685da00a
---

# PO-Briefing: fix-2777-startseite-en-bilder

- **Spec:** docs/specs/modules/startseite_en_bilder_2777.md
- **Issue:** #2777
- **Erstellt:** 2026-11-14

## Was gebaut wird

Englischsprachige Besucher der Startseite sehen englische statt deutscher Beispielbilder für Mail, Telegram und Alarm.

## Definition of Done

Mit Sprache Englisch zeigt die ausgeloggte Startseite auf Produktion drei englische Beispielbilder ohne deutschen Text und ohne Personendaten; Deutsch bleibt unverändert.

## Wie geprüft wird

Automatische Tests prüfen Bildpfade, Dateiexistenz und Größe; der Bildinhalt (kein Deutsch, keine Personendaten) wird nur per Sichtprüfung kontrolliert.

## Kritische Anmerkungen

- Abweichung vom Ticket: Alarm- und Telegram-Bild stammen aus Testdaten-Renderern, nicht aus echt zugestellten englischen Mails.
- Bildinhalt hat keinen automatischen Test, nur manuelle Sichtprüfung.

## Freigabe-Frage

Akzeptieren Sie, dass Alarm- und Telegram-Bild aus Testdaten statt aus echt zugestellten englischen Mails erzeugt werden?

## Ampel

Ampel: rot
