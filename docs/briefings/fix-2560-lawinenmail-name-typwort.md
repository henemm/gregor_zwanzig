---
spec_file: docs/specs/fast/fix-2560-lawinenmail-name-typwort.md
spec_sha256: f61bff524af366f80990cfa338354540f4c7f863995675c55366ef99c7138725
spec_frozen_sha256: e4edcf1dc195c6805134d870f32eab0f56e0d0816bcfd279c16a4f3fbc54d468
---

# PO-Briefing: fix-2560-lawinenmail-name-typwort

- **Spec:** docs/specs/fast/fix-2560-lawinenmail-name-typwort.md
- **Issue:** #2560
- **Erstellt:** 2026-11-01

## Was gebaut wird

Eine reine Lawinenwarnung-Mail wird vom Prüfwerkzeug auch dann als korrekt erkannt, wenn der Trip „Sturmtrip" oder „Hitzeck" heißt.

## Definition of Done

Die Prüfung besteht für echt gerenderte Lawinenmails mit Trip-Namen „PROBE Sturmtrip" und „Hitzeck", während eine Gewittermail mit angehängtem Lawinentext weiter durchfällt.

## Wie geprüft wird

Drei automatische Tests mit echt gerenderten Mails decken alle Kriterien ab; die Wirkung auf den Versand wird nicht geprüft, da dieser nie betroffen ist.

## Kritische Anmerkungen

- Gelöst wird per Ausschneiden des Namens statt über das Typ-Element der Warnkarte; vom Ticket als Alternative ausdrücklich vorgesehen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
