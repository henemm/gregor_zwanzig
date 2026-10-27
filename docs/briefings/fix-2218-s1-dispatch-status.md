---
spec_file: docs/specs/modules/dispatch_orchestrator.md
spec_sha256: b140b3f05d9f77d6906b35f635dee42e90648309baa98324929ff11f84aa2e74
---

# PO-Briefing: fix-2218-s1-dispatch-status

- **Spec:** docs/specs/modules/dispatch_orchestrator.md
- **Issue:** #2218 (Scheibe A, Epic #2505)
- **Erstellt:** 2026-10-07

## Was gebaut wird

Der stündliche Trip-Versand meldet einen Fehler, wenn bei einem Trip kein Kanal erreichbar war, statt fälschlich „ok".

## Definition of Done

Bei einem Trip ohne erreichbaren Kanal zeigt der Lauf „teilweise fehlgeschlagen"; Trips ohne Kanal oder Abschnitt lösen keinen Alarm aus.

## Wie geprüft wird

Endpunkt-Tests mit zwei Nutzern und allen Ausgängen; nicht geprüft werden echte Zustellung auf Staging und die Reaktion des Heartbeats.

## Kritische Anmerkungen

- Dauerhaft unerreichbarer Trip meldet stündlich Fehler und stoppt den Heartbeat; kein Drosseln vorgesehen.
- Unbekannte Ausgänge zählen als Fehler; das hat niemand verlangt und kann zusätzliche Alarme auslösen.

## Freigabe-Frage

Ist es in Ordnung, dass ein unerreichbarer Trip jede Stunde Alarm auslöst, bis er wieder erreichbar ist?
