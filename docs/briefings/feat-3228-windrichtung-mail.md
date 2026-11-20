---
spec_file: docs/specs/modules/feat_3228_windrichtung_mail.md
spec_sha256: 14ffe3aece012cc9af94c9b8f03b3b4b1b0ea4f105b0232ad825766f01c086b2
spec_frozen_sha256: a1444acce4c14f89bb766de0c986de8c8d0d0487163e29549536e46c545dc870
---

# PO-Briefing: feat-3228-windrichtung-mail

- **Spec:** docs/specs/modules/feat_3228_windrichtung_mail.md
- **Issue:** #3228
- **Erstellt:** 2026-11-20

## Was gebaut wird

Briefing- und Vergleichs-Mail färben die Windrichtung nach Ampel, wenn Gegenwind bremst oder der Wind aus einer unerwünschten Richtung kommt.

## Definition of Done

Echt zugestellte Staging-Mails zeigen bei Gegenwind bzw. markierter Himmelsrichtung Ampelfarbe, sonst keine; Alt-Trips, Telegram und SMS bleiben unverändert, Produktion ausgeliefert.

## Wie geprüft wird

Automatische Tests für alle elf Kriterien plus zwei Validatoren gegen echte Staging-Mails; Färbung in Telegram, SMS und Alarm wird nicht geprüft.

## Kritische Anmerkungen

- Abweichung vom Ticket: Felder an Etappe und Ort sowie Ampel-Anbindung der Kurzkanäle entfallen, kommen erst in Scheibe 3.
- Zelle zeigt die höhere von Windstärke- und Gegenwind-Stufe; die Ursache der Farbe bleibt unklar.

## Freigabe-Frage

Ist es in Ordnung, dass Etappen-/Ort-Felder und Kurzkanal-Anbindung vom Ticket abweichend erst in Scheibe 3 kommen?

## Ampel

Ampel: rot
