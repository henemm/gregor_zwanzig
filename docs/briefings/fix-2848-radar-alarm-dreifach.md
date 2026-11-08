---
spec_file: docs/specs/modules/fix_2848_radar_verschaerfung_kennzeichnen.md
spec_sha256: 2b8822c95d9fc7905bcbc3065960ef26edbba20799289d8ea7e1317fb5cf745a
spec_frozen_sha256: 2a10c2eb4523dccc093c2656a4ebd77ea42894d7f0b71bf84ff73203964b9855
---

# PO-Briefing: fix-2848-radar-alarm-dreifach

- **Spec:** docs/specs/modules/fix_2848_radar_verschaerfung_kennzeichnen.md
- **Issue:** #2848
- **Erstellt:** 2026-11-08

## Was gebaut wird

Radar-Folgealarme, die dasselbe Ereignis stärker melden, sagen das ausdrücklich, mit alter und neuer Regenmenge, in allen vier Kanälen.

## Definition of Done

Bei 1,0 → 3,1 → 7,3 mm tragen Alarm zwei und drei den Hinweis „Dasselbe Ereignis, jetzt stärker“ in E-Mail, Telegram, SMS, Premium-SMS.

## Wie geprüft wird

Nachbau des 24.08. gegen echten Code prüft alle vier Kanäle, beide Sprachen, zwei Nutzer; Staging-Mail ist wegen Mailweg-Störung evtl. nur lokal belegt.

## Kritische Anmerkungen

- Kein Deckel: weiterhin bis zu drei Alarme je Ereignis möglich, nur als Verschärfung erkennbar (von dir so entschieden, Option B).
- Hinweis-Zahlen können von der Regenmenge im SMS-Kürzel abweichen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
