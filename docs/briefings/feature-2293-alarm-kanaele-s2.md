---
spec_file: docs/specs/modules/feat_2293_s2_compare_alarm_kanaele.md
spec_sha256: 23a29500bf910ddb3bc14531af5582f75f9252aed03739ba3f427cfa0717aa33
---

# PO-Briefing: feature-2293-alarm-kanaele-s2

- **Spec:** docs/specs/modules/feat_2293_s2_compare_alarm_kanaele.md
- **Issue:** #2293 (mitgezogen: #2448)
- **Erstellt:** 2026-09-28

## Was gebaut wird

Ortsvergleiche bekommen eigene Alarm-Kanal-Schalter (auch E-Mail), getrennt vom Versand, plus einen Premium-SMS-Schalter für Briefings.

## Definition of Done

Ein Testalarm mit E-Mail aus und Telegram an kommt nur per Telegram an, die Mailbox bleibt leer.

## Wie geprüft wird

Automatisierte Tests prüfen jede Regel einzeln, plus ein echter Testalarm auf Staging; Bedienung im Browser wird nicht geprüft.

## Kritische Anmerkungen

- Schaltet der Nutzer alle vier Alarm-Kanäle aus, wird ein ausgelöster Alarm an niemanden zugestellt — ohne Warnung oder Fehler.
- Fälschlich aktivierte, kostenpflichtige Premium-SMS-Briefings werden automatisch abgeschaltet — ohne Ankündigung, ohne Liste Betroffener.
- Der E-Mail-Schalter im Versand-Reiter bleibt sichtbar, wirkt aber weiterhin nicht — Issue #2212 bleibt trotz Ankündigung offen.

## Freigabe-Frage

Ist es akzeptabel, dass ein Alarm bei vier abgeschalteten Kanälen ohne jede Warnung ins Leere läuft?
