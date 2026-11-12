---
spec_file: docs/specs/modules/gate_2125_prod_send_release.md
spec_sha256: acd1fe7b8148263e36fd7b47e0dcddcbcddc197599bc9ac70d479fa3d78fde0f
spec_frozen_sha256: ede8d06a2e5971ab7002a1232b20d16d34f7131c08394edaee324dfa47403622
---

# PO-Briefing: fix-2125-override-prod-send

- **Spec:** docs/specs/modules/gate_2125_prod_send_release.md
- **Issue:** #2125
- **Erstellt:** 2026-11-12

## Was gebaut wird

Der Notausgang für Prod-Versand funktioniert wieder, mit neuem Stichwort statt „override“, gültig für einen Versand der eigenen Sitzung.

## Definition of Done

Der PO tippt „prod-versand freigeben“, sieht eine Bestätigung, und genau ein Prod-Versand der Sitzung geht durch, danach wieder gesperrt.

## Wie geprüft wird

Automatische Tests spielen Freigabe, Einmaligkeit, Ablauf, fremde Sitzung und Missbrauch nach; echter Versand wird nie ausgelöst, Live-Test erst nach Auslieferung.

## Kritische Anmerkungen

- Neues Stichwort „prod-versand freigeben“ ersetzt „override“; Ticket verlangte nur Reparatur, Wortlaut ist noch nicht vom PO festgelegt.
- „override“ öffnet Prod-Versand danach nicht mehr; Freigabe gilt nur einmalig, eine Stunde, nur in der tippenden Sitzung.

## Freigabe-Frage

Ist „prod-versand freigeben“ als Freigabe-Stichwort für den Prod-Versand für dich so in Ordnung?

## Ampel

Ampel: rot
