---
spec_file: docs/specs/bugfix/go_test_resolver_offline.md
spec_sha256: 33a25bd7541300084e54ed57fc2423538c9776a6a3cbcf7dc0a5879d77fad279
spec_frozen_sha256: 40d36b776266e4163b4419a729ba5e926afc1e639fa9ea3e5e824b7232ed81de
---

# PO-Briefing: fix-3115-go-test-offline

- **Spec:** docs/specs/bugfix/go_test_resolver_offline.md
- **Issue:** #3115
- **Erstellt:** 2026-11-19

## Was gebaut wird

Die automatischen Prüfungen für Ortslinks (Komoot, Google Maps) laufen ohne Internet und blockieren keine Änderungen mehr.

## Definition of Done

Der Prüflauf der Ortsauflösung ist ohne Internetzugriff grün, die echten Live-Prüfungen laufen separat weiter, und Ticket 3115 ist geschlossen.

## Wie geprüft wird

Lokale Testserver mit aufgezeichneten Antworten ersetzen das Netz, eine Netzsperre beweist es; Formatänderungen bei Komoot oder Google zeigen nur Live-Tests.

## Kritische Anmerkungen

- Der Komoot-Erfolgspfad der Schnittstelle hat keinen Offline-Test mehr, nur noch einen Live-Test; bewusst dokumentierte Einschränkung.
- Zusatz zum Ticket: dauerhafte Netzsperre im Test, damit Rückfälle auffallen.
- Netzsperre im Handler-Bereich nur, wenn der Probelauf sauber ist; sonst Folge-Ticket.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
