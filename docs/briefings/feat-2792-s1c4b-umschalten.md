---
spec_file: docs/specs/modules/feat_2792_s1_profil_ampel.md
spec_sha256: d4f9cecac35f9e8d5e46e6ace1d0da76004beadc6d76ff16052366d78d147aee
spec_frozen_sha256: 796593fe6de40df5c46be2554eae25df8b2ef711b7683f17dc3b469c8c536cd8
---

# PO-Briefing: feat-2792-s1c4b-umschalten

- **Spec:** docs/specs/modules/feat_2792_s1_profil_ampel.md
- **Issue:** #2792
- **Erstellt:** 2026-11-06

## Was gebaut wird

E-Mail, Telegram, SMS und Premium-SMS bewerten Wetter gleichzeitig nach der Ampel des jeweiligen Abos statt nach festen Standardwerten.

## Definition of Done

Ein Skitouren-Abo und ein Allgemein-Abo zeigen denselben Messwert in allen vier Kanälen unterschiedlich bewertet, in beiden Reihenfolgen, und Mail-Prüfungen bestehen.

## Wie geprüft wird

Je Einstieg ein Test Skitouren gegen Allgemein; echte Staging-Mails werden validiert, aber die Optik der Farben beurteilt kein Test.

## Kritische Anmerkungen

- Trip ohne gespeicherte Vorlage wird nach "allgemein" bewertet; Zusage der früheren Fassung wurde korrigiert.
- Auch bei "allgemein" ändern sich Erwähnungsschwellen (etwa Wind erst ab 30 km/h) und die Kopfzelle "Profil".
- Staging-Mailweg war zeitweise defekt; Nachweise der Mail-Prüfung könnten dadurch eingeschränkt sein.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
