---
spec_file: docs/specs/modules/feat_2439_push_eingang_prod_scharf.md
spec_sha256: 7eff41536ef445dc51d35185b3b1c05f22348954852d0b6874eef09cc79d3eaf
spec_frozen_sha256: 8240c7c1e9930757a0b6707917ca505ff13b6213bc8a6af6aacc61820e740d32
---

# PO-Briefing: feat-2439-push-eingang-prod-scharf

- **Spec:** docs/specs/modules/feat_2439_push_eingang_prod_scharf.md
- **Issue:** #2439
- **Erstellt:** 2026-10-20

## Was gebaut wird

Befehle per SMS und E-Mail werden in Produktion sofort beantwortet statt erst nach bis zu fünf Minuten.

## Definition of Done

Beide Anmeldungen sind in Produktion eingetragen; ein Test-Befehl per E-Mail und ein echter SMS-Befehl werden in Sekunden beantwortet.

## Wie geprüft wird

Automatische Tests prüfen Werkzeuge und Auswertung; die Wirkung in Produktion belegen nur Messungen, keine Tests.

## Kritische Anmerkungen

- SMS- und Telegram-Nachweis hängen am nächsten echten Befehl; Issue bleibt bis dahin offen.
- Mail-Dienst filtert womöglich nicht nach Empfänger; fremde Mails könnten echte Ausfälle verdecken.
- Bis zur Registrierung lösen Prod-Befehle Fehlalarm-Mails aus.

## Freigabe-Frage

Freigeben, den Sofort-Weg in Produktion einzuschalten, obwohl der SMS-Nachweis erst mit dem nächsten echten Befehl kommt?
