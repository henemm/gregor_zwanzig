---
spec_file: docs/specs/modules/fix_2218_alarm_ausfaelle.md
spec_sha256: 241b9d31bd5d85ba75d5ae93e9ac4c1fafb429d1ffef3271ed630d149f1a9480
---

# PO-Briefing: fix-2218-alarm-stumme-ausfaelle

- **Spec:** docs/specs/modules/fix_2218_alarm_ausfaelle.md
- **Issue:** #2218
- **Erstellt:** 2026-10-08

## Was gebaut wird

Scheiternde Wetterabrufe bei Trip- und Ortsvergleich-Alarmen werden für den Betreiber sichtbar, ohne dass sich Alarmierung ändert.

## Definition of Done

Ein dauerhaft scheiternder Trip oder Ort erscheint in der Betreiber-Statusabfrage als Ausfall und verschwindet nach dem nächsten erfolgreichen Abruf wieder.

## Wie geprüft wird

Automatische Tests prüfen Journal, Statusliste, Nutzertrennung und unveränderte Alarmentscheidung; die automatische Warnung bei Dauerausfall wird nicht geprüft.

## Kritische Anmerkungen

- Niemand wird aktiv benachrichtigt: Die Auswertung im Monitoring ist ausgeklammert, ein Ganztagsausfall bleibt bis zu diesem Folgeschritt weiter unbemerkt.
- Nutzer sehen keinerlei Änderung; Sichtbarkeit gibt es nur für den Betreiber über den token-geschützten Status.
- Teilausfall (ein Segment scheitert, eines liefert) zählt als Ausfall und kann dadurch häufiger Ausfälle melden.

## Freigabe-Frage

Genügt dir diese reine Betreiber-Sichtbarkeit ohne aktive Warnung, wenn die Monitoring-Auswertung als separater Folgeschritt kommt?
