---
entity_id: issue_666_e2e_verified_retention
type: module
created: 2026-06-08
updated: 2026-06-08
status: draft
version: "1.0"
tags: [tooling, e2e-gate, retention]
---

# E2E-Verified Retention

## Approval

- [ ] Approved

## Purpose

Begrenzt das monoton wachsende Verzeichnis `.claude/e2e_verified/<sha>.json`
(eingeführt mit #662) auf die jüngsten N Attestationen — analog zum bewährten
`.backups/`-Retention-Pattern — ohne Gate- oder Deploy-Verhalten zu verändern.

## Source

- **File:** `.claude/hooks/staging_gate.py`
- **Identifier:** `write_verdict()` (+ neuer Helper `prune_old_attestations()`)

## Estimated Scope

- **LoC:** ~25
- **Files:** 1 (Implementierung) + 1 (Test)
- **Effort:** low

## Dependencies

- `.claude/hooks/_e2e_paths.py::commit_e2e_path()` — liefert das Attestation-Verzeichnis
- Vorbild: `.claude/hooks/data_schema_backup.py::prune_old_backups()`

## Behaviour

`write_verdict()` schreibt zuerst wie bisher die neue `<sha>.json`. **Danach**
ruft es `prune_old_attestations()` auf: das Verzeichnis `.claude/e2e_verified/`
wird gelistet, die `*.json`-Dateien nach Änderungszeit (mtime) absteigend
sortiert, und alle jenseits der jüngsten `RETENTION` (= 20) werden gelöscht.
Fehler beim Löschen werden geschluckt (`OSError`-Guard) — das Verdict-Schreiben
bleibt davon unberührt. Die gerade geschriebene Datei ist immer die jüngste und
wird daher nie geprunt.

## Acceptance Criteria

**AC-1:** Given das Attestation-Verzeichnis enthält bereits 20 ältere `<sha>.json`-Dateien, When `write_verdict()` mit einem VERIFIED-Verdict für einen neuen Commit aufgerufen wird, Then existiert die neue `<sha>.json`-Datei und das Verzeichnis enthält danach genau 20 Dateien (die älteste wurde gelöscht).

**AC-2:** Given das Attestation-Verzeichnis enthält weniger als 20 Dateien, When `write_verdict()` ein neues Verdict schreibt, Then wird keine bestehende Datei gelöscht und alle vorherigen Dateien bleiben unverändert erhalten.

**AC-3:** Given ein VERIFIED-Verdict wird für den aktuellen HEAD geschrieben während das Verzeichnis bereits voll (≥20) ist, When anschließend der Gate-Check / die Default-Pfad-Auflösung für denselben HEAD läuft, Then wird die HEAD-passende Datei gefunden und das Verdict gelesen (die HEAD-Datei wurde nicht weggeprunt) → Exit 0.

**AC-4:** Given das Löschen einer alten Datei schlägt fehl (z.B. fehlende Berechtigung, simuliert über eine nicht löschbare Alt-Datei), When `write_verdict()` das Pruning durchläuft, Then bleibt der Rückgabewert von `write_verdict()` 0 (Verdict erfolgreich) und die neue Attestation existiert.

## Out of Scope

- Retention nach Alter (Tage) statt Anzahl — bewusst Anzahl-basiert wie `.backups/`.
- Aufräumen des Singleton-Fallbacks `.claude/e2e_verified.json` (Migrations-Artefakt, bleibt unberührt).
- Änderungen am Gate-Check, an `prod_selftest.py` oder am Deploy-Script.
