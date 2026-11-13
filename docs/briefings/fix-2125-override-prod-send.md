# PO-Briefing: fix-2125-override-prod-send

- **Spec:** docs/specs/modules/gate_2125_prod_send_release.md
- **Issue:** #2125
- **Erstellt:** 2026-11-12

## Was gebaut wird

Mit „prod-versand freigeben“ geht genau ein Prod-Versand der eigenen Sitzung durch; „override“ öffnet ihn nicht mehr.

## Definition of Done

Bestätigung erscheint, genau ein Prod-Versand der Sitzung geht durch, der nächste bleibt gesperrt.

## Wie geprüft wird

Automatische Tests prüfen Freigabe, Einmaligkeit, Ablauf, fremde Sitzung und Missbrauch ohne echten Versand; Live-Test erst nach Auslieferung.

## Kritische Anmerkungen

- Ticket wollte „override“ reparieren; die Spec führt stattdessen ein neues Stichwort ein, ohne dass der PO es entschieden hat.
- Freigabe gilt nur einmalig, eine Stunde, in der tippenden Sitzung; Ticket sagte „aus jeder Sitzung wirksam“.

## Freigabe-Frage

Neues Stichwort „prod-versand freigeben“ statt „override“, nur in der tippenden Sitzung gültig: einverstanden?

## Ampel

Ampel: rot
