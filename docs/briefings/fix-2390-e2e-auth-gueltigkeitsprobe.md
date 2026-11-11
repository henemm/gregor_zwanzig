---
spec_file: docs/specs/modules/fix_2390_e2e_auth_gueltigkeitsprobe.md
spec_sha256: bcb2cee4c8c0bf569b326d762fa3ffb691509e708117d9a71009811a2eacdf9d
spec_frozen_sha256: 0c7cf35913d99cd48bf0cb18e7b1f2d7fc1e44b3e5d9858916dc6757961a52b6
---

# PO-Briefing: fix-2390-e2e-auth-gueltigkeitsprobe

- **Spec:** docs/specs/modules/fix_2390_e2e_auth_gueltigkeitsprobe.md
- **Issue:** #2390
- **Erstellt:** 2026-11-11

## Was gebaut wird

Lokale Browser-Tests melden sich neu an, wenn der Server die gespeicherte Anmeldung ablehnt, statt still falsch-rot zu werden.

## Definition of Done

Zwei Testläufe mit Neustart dazwischen und absichtlich stehengelassener Anmeldedatei liefern beide dieselben grünen Zahlen; das Ergebnis steht im Ticket.

## Wie geprüft wird

Ein automatischer Test deckt die Entscheidung bei Antwort 200, 401 und Fehler ab; die Zwei-Läufe-Abnahme erfolgt manuell.

## Kritische Anmerkungen

- Keine — Spec deckt die Anfrage ab, jede Anforderung hat einen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
