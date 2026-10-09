---
spec_file: docs/specs/bugfix/interne_endpunkte_core_auth.md
spec_sha256: 1e2f3dab303ee138afa5a742d92cb1be62f318942abe0763c0bd5c9c0f039ebe
---

# PO-Briefing: fix-2159-interne-endpunkte-secret

- **Spec:** docs/specs/bugfix/interne_endpunkte_core_auth.md
- **Issue:** #2159
- **Erstellt:** 2026-10-09

## Was gebaut wird

Interne Server-Schnittstellen für Telegram-Verknüpfung und Premium-SMS-Lernen verlangen künftig ein gemeinsames Geheimnis, nicht nur Herkunft vom Server.

## Definition of Done

Aufrufe ohne oder mit falschem Geheimnis werden mit Fehler abgelehnt und ändern keine Nutzerdaten; Telegram-Verknüpfung und Premium-SMS funktionieren weiterhin.

## Wie geprüft wird

Automatische Tests gegen echten Router und lokale Testserver beweisen Ablehnung und Weiterbetrieb; Staging-Betrieb, Dokumentation und echte Telegram-Zustellung prüfen sie nicht.

## Kritische Anmerkungen

- Manueller Betriebsschritt außerhalb des Codes nötig: Staging-Einstellung ergänzen, sonst fallen dort Telegram-Verknüpfung und Premium-SMS aus.
- Kriterium 12 (Dokumentation) hat keinen automatischen Test; Prüfung nur im Review.
- Zusatz: Gesundheitsabfrage zeigt Go-Adresse an, damit ein fehlender Staging-Eintrag auffällt; nicht verlangt, aber unkritisch.

## Freigabe-Frage

Soll dieser Schutz inklusive manuellem Staging-Eintrag und Cookie-Härtung aus #2163 so umgesetzt werden?
