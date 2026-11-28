---
spec_file: docs/specs/modules/fix_3503_compare_mail_gate_imac.md
spec_sha256: d8644e4c34f299568c4df45aad57adec13e180b0258b01b8e877945055eaeb26
spec_frozen_sha256: ad987dbb9ecad96cb7289143ce8f99a04b844f83b1e3a52ad2a6cfeac12371bb
---

# PO-Briefing: fix-3503-mail-gate-imac

- **Spec:** docs/specs/modules/fix_3503_compare_mail_gate_imac.md
- **Issue:** #3503
- **Erstellt:** 2026-11-28

## Was gebaut wird

Änderungen an der Vergleichs-Mail werden nur mit echtem Nachweis zugelassen; auf dem iMac genügt ein lokaler Render-Nachweis.

## Definition of Done

Testläufe mit Beispiel-Mails erfüllen die Sperre nicht mehr, und ein Commit am iMac geht nach lokalem Nachweis durch.

## Wie geprüft wird

Automatische Tests mit echten Wegwerf-Repositories belegen alle neun Kriterien; Versand und Live-Daten prüft erst die Abnahme nach dem Deploy.

## Kritische Anmerkungen

- Abweichung: Testläufe schreiben weiter ins Log, werden aber ignoriert; verlangt war, dass sie nicht schreiben.
- Der neue iMac-Nachweis rendert nur Beispieldaten, prüft keine zugestellte Mail und ist von Hand fälschbar.

## Freigabe-Frage

Darf der iMac Vergleichs-Mail-Commits mit lokalem Render-Nachweis statt zugestellter Mail durchlassen, mit echter Mailprüfung erst nach dem Deploy?

## Ampel

Ampel: rot
