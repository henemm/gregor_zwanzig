---
spec_file: docs/specs/modules/rework_2988_ampel_ableitung.md
spec_sha256: d2030711beba960328ebeb679bd398403267707bb721247ba07fd5aedbab0a1e
spec_frozen_sha256: a269b0a774c1f0c8f19d5e5950b9da388ff3aa0133ac29f39372d16d0b2b7c66
---

# PO-Briefing: rework-2988-ampel-ableitung

- **Spec:** docs/specs/modules/rework_2988_ampel_ableitung.md
- **Issue:** #2988
- **Erstellt:** 2026-11-25

## Was gebaut wird

Die Wetter-Ampel wird nur noch vom Server berechnet; die Oberfläche fragt das Ergebnis ab und zeigt es an.

## Definition of Done

Reiter Wetter, Zähler und Übersichten zeigen und speichern dasselbe wie vorher, und die doppelte Rechnung samt Paritätstest ist aus der Oberfläche entfernt.

## Wie geprüft wird

Automatische Tests vergleichen alle Werte mit Referenzen vor dem Umbau, inklusive zwei Nutzern und Fehlerfällen; echtes Tippverhalten prüft ein Live-Test gegen Staging.

## Kritische Anmerkungen

- Ticket verlangt eine einzige Ableitung; die Spec lässt Zähler, Metrik-Auswahl und weitere Teilrechnungen bewusst im Frontend. Ob das genügt, ist nicht entschieden.
- Nutzer sehen eine kleine Änderung: Windrichtungs-Einstellungen bleiben beim Speichern eigener Vorlagen erhalten; ungültige Altdaten-Ampeln werden anders aufgelöst.
- Beim Öffnen von Reiter und Trip-Übersicht braucht es einen zusätzlichen Serveraufruf; offline erscheint „Erneut laden".

## Freigabe-Frage

Genügt dir, dass Zähler und Metrik-Auswahl in der Oberfläche berechnet bleiben, obwohl das Ticket eine einzige Ableitung nennt?

## Ampel

Ampel: rot
