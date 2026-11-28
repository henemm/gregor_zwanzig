---
spec_file: docs/specs/modules/fix_2221_dpc_gueltigkeit.md
spec_sha256: 8b195f40f1e97d997111c241c80df33be603aa5d2e395d3481df81643454b98d
spec_frozen_sha256: a01090f6788a6ac32a4c54ea0dfa552ac38816cfb98d7e9f56467b9aefc8d277
---

# PO-Briefing: fix-2221-dpc-gueltigkeit

- **Spec:** docs/specs/modules/fix_2221_dpc_gueltigkeit.md
- **Issue:** #2221
- **Erstellt:** 2026-11-28

## Was gebaut wird

Italienische Zivilschutz-Warnungen bekommen ein Gültigkeitsfenster, nämlich den ganzen Tag, für den die Behörde warnt.

## Definition of Done

Mail und Telegram zeigen bei italienischen Warnungen "Datum · ganztägig", und zwei Warnungen verschiedener Tage werden getrennt gemeldet.

## Wie geprüft wird

Automatische Tests mit echten Behörden-Bulletins prüfen Fenster, Mitternachtsgrenze, Anzeige und Meldegedächtnis; das echte Verhalten auf Staging wird anschließend verifiziert.

## Kritische Anmerkungen

- Das Ticket nennt fehlendes SMS-Zeit-Token; die Spec liefert bewusst keine Uhrzeit in der SMS, da ganztägig.
- Einmalig am Deploy-Tag kann eine bereits gemeldete italienische Warnung doppelt kommen.
- Zusätzlich wird der Bezugstag auf italienische Ortszeit umgestellt, was das Ticket nicht verlangte.

## Freigabe-Frage

Ist es für dich in Ordnung, dass italienische Warnungen in der SMS ganztägig ohne Uhrzeit erscheinen?

## Ampel

Ampel: rot
