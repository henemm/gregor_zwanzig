---
spec_file: docs/specs/modules/core_bind_guard.md
spec_sha256: c18f7db4bac2f3853eddb2f6d6f072eb3aa1697247c95542ed6bf9aea715a911
spec_frozen_sha256: 9e595134eed300c8ad8a82e2704abc072508db3433b1162b2538d91eb6501492
---

# PO-Briefing: feat-2190-core-bind-guard

- **Spec:** docs/specs/modules/core_bind_guard.md
- **Issue:** #2190
- **Erstellt:** 2026-11-02

## Was gebaut wird

Der Python-Kern weigert sich zu starten, wenn er nicht ausschliesslich auf der internen Adresse 127.0.0.1 lauschen würde.

## Definition of Done

Ein Start mit einer anderen Adresse bricht sofort mit klarer Fehlermeldung ab, der normale Start über 127.0.0.1 und die Testumgebung laufen unverändert.

## Wie geprüft wird

Echte Startversuche mit verbotenen und erlaubten Adressen beweisen Abbruch bzw. Start; Server-Einstellungen in der Infrastruktur werden nur gelesen, nicht live getestet.

## Kritische Anmerkungen

- Start mit mehreren Arbeitsprozessen oder Neustart-Modus wird nicht abgefangen; heute nutzt das kein Startweg, nur ein Textprüf-Test bewacht es.
- Schutz stützt sich auf interne Details von uvicorn (Server-Software); ein Update könnte ihn brechen, Tests würden das melden.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
