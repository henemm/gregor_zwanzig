---
spec_file: docs/specs/modules/trip_briefing_aufbau.md
spec_sha256: 07ae65a497aea4074d522855c31c6bf92795f2cb12799dc2ecaaccc31a576081
spec_frozen_sha256: 25f4d3f896a2d40338e4aa13c9a9381120786b9032019ebb025436b328de6f9c
---

# PO-Briefing: feat-3128-trip-gemeinsamer-berichtsaufbau

- **Spec:** docs/specs/modules/trip_briefing_aufbau.md
- **Issue:** #3128
- **Erstellt:** 2026-11-18

## Was gebaut wird

Trip-Vorschau und Trip-Versand setzen ihren Bericht künftig an einer gemeinsamen Stelle zusammen, ohne dass sich Zustellungen ändern.

## Definition of Done

Zugestellte Mails, SMS und Telegram-Nachrichten sind byte-gleich wie vorher, die Vorschau unverändert, und eine echte Staging-Mail besteht die Prüfung.

## Wie geprüft wird

Vorher festgehaltene Soll-Werte aller Kanäle werden nachher verglichen; nicht nachgewiesen wird, dass die Vorschau der zugestellten SMS entspricht.

## Kritische Anmerkungen

- Das Ticket nennt Drift bei Nachtwetter und Sprache; die Spec behebt sie nicht, sondern verschiebt sie in #3144.
- Die SMS-Vorschau zeigt nach diesem Ticket weiter nicht exakt die zugestellte SMS.

## Freigabe-Frage

Ist es für dich in Ordnung, dass die Vorschau-Angleichung erst in #3144 folgt und dieses Ticket nur umbaut?

## Ampel

Ampel: rot
