---
spec_file: docs/specs/modules/prod_pull_deploy.md
spec_sha256: b70c5a16ed5a4f604780ab804ddf18772a2e04e0cae661a0733bcb8b507fd06b
spec_frozen_sha256: 76caafd88c9679b9ad105b5567e59f099dde4f2df71304da8ed7fc5867c88d78
---

# PO-Briefing: feat-3289-pull-deploy

- **Spec:** docs/specs/modules/prod_pull_deploy.md
- **Issue:** #3289
- **Erstellt:** 2026-11-23

## Was gebaut wird

Der Server liefert Gregor selbst aus, sobald ein geprüfter Stand vorliegt, und meldet das Ergebnis zurück.

## Definition of Done

Ein Ticket von einem Rechner ausserhalb des Servers wird live, ohne Nachweis wird nie ausgeliefert, und ein Fehlschlag löst genau einen Alarm aus.

## Wie geprüft wird

Automatische Tests an Wegwerf-Repositories belegen Nachweis, Auslieferung, Alarm und Wartezustand; der echte Lauf vom iMac ist nicht automatisch getestet.

## Kritische Anmerkungen

- Staging-Prüfung läuft von aussen weiter per Zugang auf den Server; das Ziel "ohne Serverzugang" gilt nur für Auslieferung.
- "Feste Pfade prüfen" aus dem Ticket hat keine eigene Anforderung und keinen Test.
- Nachweis als Git-Notiz statt Commit-Status (Ticket: "z. B."); Tech-Lead-Entscheidung, technisch begründet.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
