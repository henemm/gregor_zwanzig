---
spec_file: docs/specs/modules/fix_3192_wetter_dialog_abgleich.md
spec_sha256: d9d0c3e61c6ad90d1cb12dd0266e13cfb94553f30f9eb225f3a74ba2f511f622
spec_frozen_sha256: bc1772d34a175f22edb3bdf9286ade5d182235b06713fb82d5c27ae41a290890
---

# PO-Briefing: fix-3192-wetter-dialog-abgleich

- **Spec:** docs/specs/modules/fix_3192_wetter_dialog_abgleich.md
- **Issue:** #3192
- **Erstellt:** 2026-11-20

## Was gebaut wird

Der Abgleich prüft die Wetter-Dialoge auf Testdaten in Mockup-Lage, und eine frisch gespeicherte eigene Vorlage erscheint sofort.

## Definition of Done

Der Abgleich findet in Deutsch und Englisch alle Wetter-Dialog-Einträge, keiner bleibt offen, und das Speichern einer eigenen Vorlage ist im Browser belegt.

## Wie geprüft wird

Kleine Tests prüfen die Auswahlregeln; der Abgleich auf Staging und ein Browser-Test belegen den Rest. Produktcode bleibt unverändert.

## Kritische Anmerkungen

- Statt einer Mockup-Lage nutzt die Spec zwei Testdatensätze je Bereich, weil das Mockup in sich widersprüchlich ist.
- Restabweichungen werden begründet an #3151, #3189 oder #3190 umgehängt; #3151 nennt das Ticket nicht.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
