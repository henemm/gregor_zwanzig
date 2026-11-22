---
spec_file: docs/specs/modules/feat_3154_karte_abgleich.md
spec_sha256: f498dc9d950ec0146f17970651af7fffcf557d50362761ae66720a34ef1a1ff6
spec_frozen_sha256: 48467eed05bcdce7018be7cd012f7a6ca8d6e94ce25dc1f0087070e99880e5dd
---

# PO-Briefing: karte-3154-abgleich

- **Spec:** docs/specs/modules/feat_3154_karte_abgleich.md
- **Issue:** #3154
- **Erstellt:** 2026-11-22

## Was gebaut wird

Die Abnahme der Karte „Was steht wo“ wird abgeschlossen: Prüfkonto, Soll-Bild und Abgleich-Werkzeug stimmen mit der fertigen Karte überein.

## Definition of Done

Der Abgleich für „Was steht wo“ läuft auf Deutsch und Englisch ohne Abweichung, und der Bildvergleich für Trip und Orte hat keinen offenen Befund.

## Wie geprüft wird

Automatische Tests prüfen Testdaten und Abgleich-Werkzeug; Staging-Lauf und Bildvergleich weisen die Karte nach, Beispielzahlen nur der Form nach.

## Kritische Anmerkungen

- Geändert wird das Soll-Bild (gesperrte Zellen, Gewitter-Knopf, Orte-SMS), nicht die Karte; Grundlage sind bereits freigegebene Entscheidungen.
- Beispielzahlen werden nur der Form nach geprüft; ihre inhaltliche Richtigkeit sichern andere Tests.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
