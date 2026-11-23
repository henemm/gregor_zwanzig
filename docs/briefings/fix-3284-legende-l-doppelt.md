---
spec_file: docs/specs/modules/fix_3284_legende_bereich_ohne_l.md
spec_sha256: 5c89491eb301681b4ba45cdaf1a4d2aaaf3af27ab0a75e98aebcf375dcf117b9
spec_frozen_sha256: 0c32e37061b872099cb1ddc989583e59663257c06daabeda423fe256c3026a60
---

# PO-Briefing: fix-3284-legende-l-doppelt

- **Spec:** docs/specs/modules/fix_3284_legende_bereich_ohne_l.md
- **Issue:** #3284
- **Erstellt:** 2026-11-23

## Was gebaut wird

Die Kürzel-Erklärung bei „Was steht wo“ nennt bei Tiefst- und Höchsttemperatur nur das wirklich gesendete Bereichs-Kürzel, ohne zusätzliches L.

## Definition of Done

Bei Trip und Orten, Deutsch und Englisch, fehlt „L = Tagestiefstwert“, sobald Tiefst- und Höchstwert gewählt sind; das Bereichs-Kürzel erklärt beide.

## Wie geprüft wird

Automatische Tests rufen die echte Tabelle ab und prüfen die Legende je Trip/Orte und Sprache; das Aussehen im Browser prüfen sie nicht.

## Kritische Anmerkungen

- Bei nur gewähltem Tiefstwert bleibt L doppelt (Tiefstwert, Stufe gelb); das hast du am 23.11. so entschieden.
- Die Bedeutung des Bereichs-Kürzels wird aus vorhandenen Texten zusammengesetzt („Tagestiefstwert/Tageshöchstwert“); nicht ausdrücklich verlangt, aber Folge der Korrektur.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
