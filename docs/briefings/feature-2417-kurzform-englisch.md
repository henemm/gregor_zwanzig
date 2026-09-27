---
spec_file: docs/specs/modules/feat_2417_kurzform_englisch.md
spec_sha256: 71d686ff2edfd9a493006813ebb49e78d1b3b02ce99eb37759573af1c1673f13
---

# PO-Briefing: feature-2417-kurzform-englisch

- **Spec:** docs/specs/modules/feat_2417_kurzform_englisch.md
- **Issue:** #2417
- **Erstellt:** 2026-09-27

## Was gebaut wird

Premium-SMS und Telegram-Kurzform antworten jetzt vollständig Englisch, englische Befehlswörter wirken überall, plus neuer Kürzel-Erklärungsbefehl CODES.

## Definition of Done

PO erkennt Erfolg daran, dass Premium-SMS/Garmin und Telegram-Kurzform durchgehend Englisch antworten, englische und deutsche Befehle überall gleich wirken.

## Wie geprüft wird

Automatisierte Tests prüfen Wortlaut, Sprache und Kürzel-Eindeutigkeit exakt; Premium-SMS läuft im Test über den echten Eingang, der Handy-Check folgt erst nach Auslieferung.

## Kritische Anmerkungen

- Kälte-Alarm-SMS zeigt künftig T statt N, eine automatische Nachricht ändert sich sichtbar für Nutzer.
- Ortsvergleich bleibt bei D und L statt wie ursprünglich freigegeben auf T umzustellen, weniger Änderung als zuerst geplant.
- STATUS-Antwort in Kurzform nutzt künftig einen einfachen Bindestrich statt Gedankenstrich, CODES erklärt neu auch MAX.

## Freigabe-Frage

Stimmen Sie diesen Nachträgen zu: Kälte-Alarm zeigt T statt N, Ortsvergleich bleibt bei D/L, STATUS nutzt einfachen Bindestrich?
