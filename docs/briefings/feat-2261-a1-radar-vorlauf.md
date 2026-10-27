---
spec_file: docs/specs/modules/feat_2261_a1_radar_vorlauf.md
spec_sha256: eca3f35f2f0dfb0c219b1968c746507053fa9970104de7c7184a1a7f741db1af
---

# PO-Briefing: feat-2261-a1-radar-vorlauf

- **Spec:** docs/specs/modules/feat_2261_a1_radar_vorlauf.md
- **Issue:** #2261
- **Erstellt:** 2026-10-03

## Was gebaut wird

Der Regen-Alarm meldet Regen bis zu drei Stunden vorher statt erst eine Stunde vorher.

## Definition of Done

Regenbeginn in 170 Minuten löst genau einen Alarm in allen vier Kanälen aus, mit Uhrzeit.

## Wie geprüft wird

Automatische Tests spielen echte Alarmläufe für Trip und Ortsvergleich durch; Premium-SMS-Empfang zeigt erst der Staging-Test.

## Kritische Anmerkungen

- Mehr, frühere Alarme: Tageslimit (Free 2, Standard 4) ist früher aufgebraucht, Premium-SMS-Kosten steigen.
- Zusatz: Mengenangabe entfällt bei Regenbeginn über 120 Minuten; Alarm nur, wenn der Regen vor dem Weitergehen liegt.
- Keine Erinnerung kurz vor Eintreffen; die 30-Minuten-Toleranz ist geschätzt, nicht gemessen.

## Freigabe-Frage

Soll der Regen-Alarm trotz mehr Alarmen so früh wie möglich melden, inklusive der Zusatzregeln?
