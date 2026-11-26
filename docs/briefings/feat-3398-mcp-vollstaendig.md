---
spec_file: docs/specs/modules/mcp_wetter_vollstaendig.md
spec_sha256: b87b150cd04eacf47b39621bb8460d77c739374dab73731426d0ca178ba2d222
spec_frozen_sha256: 707d50aa7eee1a466982d1debcd75cc76c7a2ad9b8d730e32068798df36cb3b8
---

# PO-Briefing: feat-3398-mcp-vollstaendig

- **Spec:** docs/specs/modules/mcp_wetter_vollstaendig.md
- **Issue:** #3398
- **Erstellt:** 2026-11-26

## Was gebaut wird

Die Claude-App erhält über Gregor alle wählbaren Wettermetriken inklusive gefühlter Temperatur sowie einen Regen- und Gewitter-Nowcast.

## Definition of Done

Auf Staging beantwortet die Claude-App die Fragen nach gefühlter Temperatur und „Regnet es in der nächsten Stunde?“ mit Gregor-Werten.

## Wie geprüft wird

Automatische Tests mit aufgezeichneten Wetterdaten prüfen Feldmenge, Schnee, Nowcast und Sprachen; ob Werte den Briefings entsprechen, wird nicht direkt verglichen.

## Kritische Anmerkungen

- Das Issue nennt die Gewitterstufe ohne Anreicherung als Problem; die Spec hat dafür keine eigene Prüfung.
- Zusätzlich eingebaut: Parameter zur Feldauswahl, damit Antworten klein bleiben; vom Issue nicht verlangt, unkritisch.
- confidence_pct bleibt ausgeschlossen, passend zur früheren Entscheidung (#710).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
