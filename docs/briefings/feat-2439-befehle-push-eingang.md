---
spec_file: docs/specs/modules/feat_2439_befehle_push_eingang.md
spec_sha256: 20ef54f91bb39e8746ae65f70356cbbb9153d379980b2e8001ded2db346f6fbf
---

# PO-Briefing: feat-2439-befehle-push-eingang

- **Spec:** docs/specs/modules/feat_2439_befehle_push_eingang.md
- **Issue:** #2439
- **Erstellt:** 2026-10-13

## Was gebaut wird

Befehle per Premium-SMS und E-Mail werden sofort beantwortet statt erst beim nächsten Fünf-Minuten-Abruf.

## Definition of Done

Ein Befehl wie CODES wird per SMS und E-Mail innerhalb von 30 Sekunden beantwortet; der Fünf-Minuten-Abruf bleibt Reserve.

## Wie geprüft wird

Automatische Tests prüfen Absicherung, Weckruf und Nutzertrennung; die 30 Sekunden werden nur manuell auf Staging gemessen.

## Kritische Anmerkungen

- Zusatz ungefragt: Alarm an den PO, wenn der Sofort-Weg ausfällt.
- SMS-Signaturprüfung ist ungeklärt; ein echter Mitschnitt muss erst zeigen, dass der SMS-Sofort-Weg funktioniert.

## Freigabe-Frage

Soll der Sofort-Weg für SMS und E-Mail inklusive Ausfall-Alarm gebaut werden?
