---
spec_file: docs/specs/modules/feat_3258_sms_kuerzel_legende.md
spec_sha256: 858ebcd17baa5799a734a2a843a224cc48a156b83f48b93a6b69d202e6416904
spec_frozen_sha256: 3b96222ed52123112d2a85c7c02b0d0a4b82044e026e76d3dd2185e2371a01d1
---

# PO-Briefing: feat-3258-sms-kuerzel-legende

- **Spec:** docs/specs/modules/feat_3258_sms_kuerzel_legende.md
- **Issue:** #3258
- **Erstellt:** 2026-11-22

## Was gebaut wird

Der Entwurf des Reiters Wetter erhält den Block „Kürzel erklärt“, damit er mit der unveränderten App übereinstimmt.

## Definition of Done

Im Abgleich Entwurf gegen App stehen Legende und SMS-Beispielwerte nicht mehr als „zusätzlich ohne Besitzer“, und die App verhält sich unverändert.

## Wie geprüft wird

Automatische Tests prüfen Legendentexte in Deutsch und Englisch sowie das Zahlenmuster; der Abgleich auf Staging läuft vorher und nachher.

## Kritische Anmerkungen

- Das Zahlenmuster prüft nur „Zahl“, nicht den konkreten Wert; abweichende SMS-Beispielwerte (FN7 statt FN12) fallen dadurch nicht auf.
- Bedeutungstexte der Metriken liegen im Entwurf fest; ändert der Server sie, muss der Entwurf nachgezogen werden.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
