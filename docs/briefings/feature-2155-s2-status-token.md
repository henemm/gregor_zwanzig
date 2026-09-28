---
spec_file: docs/specs/modules/admin_rolle_s2_status_token.md
spec_sha256: 8874852203ab3b55df74104a7a8e9d058589e21299099891ad3d447c1dead077
---

# PO-Briefing: feature-2155-s2-status-token

- **Spec:** docs/specs/modules/admin_rolle_s2_status_token.md
- **Issue:** #2155
- **Erstellt:** 2026-09-28

## Was gebaut wird

Der technische Betriebsstatus wird durch ein Geheim-Passwort geschützt; jeder Nutzer sieht nur noch seinen eigenen Versandstatus im Konto.

## Definition of Done

Der externe Prüf-Dienst kommt nur mit Passwort an den Status, die Konto-Seite zeigt weiter den eigenen Versandstatus.

## Wie geprüft wird

Automatisierte Tests prüfen Zugriffsschutz und eigene Statusanzeige; die korrekte Umstellung des externen Prüf-Skripts wird nur manuell beim Ausliefern kontrolliert.

## Kritische Anmerkungen

- Ursprünglich verlangt war Schutz per Admin-Rolle; die Spec nutzt stattdessen ein separates Passwort, weil der Prüf-Dienst keine Anmeldung hat.
- Funktioniert nur, wenn das Passwort vor dem Ausliefern in der richtigen Reihenfolge in zwei getrennten Systemen eingetragen wird.
- Vier Prüfpunkte hängen an manueller Kontrolle nach dem Ausliefern statt an automatisierten Tests.

## Freigabe-Frage

Ist ein separates Passwort statt einer Admin-Anmeldung für den Prüf-Dienst akzeptabel, trotz mehrstufiger manueller Ausliefer-Schritte?
