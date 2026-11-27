---
spec_file: docs/specs/modules/feat_3444_gemeinsamer_katalog.md
spec_sha256: 712beec238cdd22f15580392a701c6c5e95ecf21e5e89e6a66bdbdf4a225f1bf
spec_frozen_sha256: ba1c66d74f10c4f044b7550aea4f0f6d81681defcd2e2676cdf740b479ba00b9
---

# PO-Briefing: feat-3444-gemeinsamer-katalog

- **Spec:** docs/specs/modules/feat_3444_gemeinsamer_katalog.md
- **Issue:** #3444
- **Erstellt:** 2026-11-27

## Was gebaut wird

Die Fehlermeldung bei fehlender Briefing-Art kommt in beiden Systemen aus einer gemeinsamen Textdatei, Deutsch unverändert.

## Definition of Done

Fehlende Briefing-Art liefert auf Staging und Produktion in Deutsch und Englisch den bisherigen Text, aus einer einzigen Quelle, alle Prüfungen grün.

## Wie geprüft wird

Tests ändern den gemeinsamen Text und prüfen, dass beide Systeme ihn ausgeben; Radar- und MCP-Texte der Folgeschritte werden nicht geprüft.

## Kritische Anmerkungen

- Nur ein Text zieht um; Radar-Intensität und MCP-Fehler bleiben vorerst doppelt, eigene Folge-Tickets werden erst zum Abschluss angelegt.
- Der Frontend-Text für denselben Fehler bleibt bewusst separat.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
