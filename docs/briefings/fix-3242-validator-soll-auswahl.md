---
spec_file: docs/specs/modules/fix_3242_validator_soll_auswahl.md
spec_sha256: fbad0f913ea40935b7a1750128668b6bd554bc6248f66f3f9ef7cbee6cd43838
spec_frozen_sha256: 450f15404893afcad075dc90a70fec7926690cdef81ba743632396f8fb4323ea
---

# PO-Briefing: fix-3242-validator-soll-auswahl

- **Spec:** docs/specs/modules/fix_3242_validator_soll_auswahl.md
- **Issue:** #3242
- **Erstellt:** 2026-11-21

## Was gebaut wird

Die Mail-Prüfung erwartet Spaltenauswahl und Reihenfolge so, wie sie im Editor „Was steht wo“ eingestellt sind.

## Definition of Done

Wer im Editor Haken oder Reihenfolge ändert, bekommt bei korrekter Mail keinen Fehlalarm mehr; Altbestände ohne Tabelle prüfen unverändert.

## Wie geprüft wird

Automatische Tests mit von Hand notierten Erwartungen decken alle Kriterien ab; der Fehlalarm-Fall wird zusätzlich auf Staging manuell abgenommen.

## Kritische Anmerkungen

- Das Ticket ließ offen, ob das Soll das Produkt aufruft oder nachbildet; die Spec wählt die Nachbildung, begründet.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
