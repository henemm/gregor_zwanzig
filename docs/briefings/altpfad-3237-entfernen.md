---
spec_file: docs/specs/modules/feat_3237_altpfad_entfernen.md
spec_sha256: a0beaea52872a6f023258f17ae47e7ae1e0370168c39f6f661b2fefe16727b30
spec_frozen_sha256: ccec5e84929d8df9a23b95a36f61790f4c2b85ce149ced9137af727f0b0953d7
---

# PO-Briefing: altpfad-3237-entfernen

- **Spec:** docs/specs/modules/feat_3237_altpfad_entfernen.md
- **Issue:** #3237 (mit #3275)
- **Erstellt:** 2026-11-22

## Was gebaut wird

Neue Trips und Orts-Vergleiche bekommen sofort die volle Tabelle „Was steht wo“, und die alte Auswahllogik im Hintergrund verschwindet.

## Definition of Done

Alle vier Kanäle liefern für bestehende Abos zeichengleich dieselben Berichte wie vorher, neue Abos haben sofort volle Tabelle, Produktion läuft fehlerfrei.

## Wie geprüft wird

Automatische Tests vergleichen Berichte vorher und nachher je Kanal und prüfen Anlage mit zwei Nutzern; Bedienung der alten Editoren bleibt ungeprüft.

## Kritische Anmerkungen

- Bis zum Folgeticket schreiben die alten Editoren weiter wirkungslose Einstellungen; Nutzer sehen zwei Bedienwege, die Tabelle gewinnt.
- Neue Abos erhalten Metriken aus der Grundauswahl statt aus dem Assistenten-Ausblick; in Produktion sind null Abos betroffen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
