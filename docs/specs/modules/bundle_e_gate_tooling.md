---
entity_id: bundle_e_gate_tooling
type: module
created: 2026-06-14
updated: 2026-06-14
status: draft
version: "1.0"
tags: [tooling, gate, prod_selftest, briefing_mail_validator, deploy]
---

# Bundle E — Gate-Tooling-Verlässlichkeit (#788, #786, #780)

## Approval

- [x] Approved

## Purpose

Drei Deploy-/Mail-Gates liefern reproduzierbar Fehlurteile und blockieren
fälschlich Issue-Closes (bzw. winken Defekte durch). Dieses Bundle macht die
Gates deterministisch: Sentinel-URLs zählen nicht als fehlgeschlagene Probe
(#788), docs-only/tooling-Deploys werden über eigene Scope-Erkennung sauber
übersprungen statt an stale Singleton-Attestation zu scheitern (#786), und der
Briefing-Mail-Validator wählt im geteilten Test-Postfach gezielt die eigene
Mail per Marker/Subject (#780).

## Source

- **File:** `.claude/hooks/prod_selftest.py` (#788, #786)
- **File:** `.claude/hooks/briefing_mail_validator.py` (#780)
- **Identifier:** `_probe_ac`, `run_selftest`, `_detect_committed_scope` (neu),
  `fetch_latest_message`, `_message_matches` (neu)

> Schicht-Hinweis: Reines Tooling unter `.claude/hooks/` — kein Frontend-,
> Go- oder Python-Produktivcode. Tooling-only-Deploy (kein Staging-Walk nötig).

## Estimated Scope

- **LoC:** ~70
- **Files:** 2 Quell- + Tests
- **Effort:** low–medium

## Dependencies

- `_e2e_paths.py` (vorhandene Pfad-Helfer; `worktree_repo_dir`)
- Vorbild Scope-Erkennung: `staging_gate._detect_committed_scope`

## Acceptance Criteria

**AC-1:** Given ein Finding mit Staging-Status `PASS` und `url` gleich einem
Sentinel-Wert (`"n/a"`, `"na"`, `"-"`, `"none"`, `"—"`, `"interaktiv"`,
case-insensitive, getrimmt). When `_probe_ac(finding)` aufgerufen wird. Then es
wird **kein** HTTP-GET ausgeführt und das Ergebnis hat
`prod_status == "SKIPPED_NO_URL"` (nicht `"FAIL"`).

**AC-2:** Given eine Findings-Liste, in der alle PASS-Findings Sentinel-URLs
tragen. When `_derive_verdict(probes)` über die geprobten Findings läuft. Then
das Verdict ist **nicht** `"PARTIAL"` (kein False-Block), sondern `"PASS"` oder
`"SKIPPED_ALL"`.

**AC-3:** Given ein Deploy mit committetem Scope `docs-only` (HEAD~1..HEAD
berührt nur `docs/`, `.claude/`, `*.md`, `tests/`, `.gitignore`) und eine
vorhandene **stale** Attestation, deren `verified_commit` von HEAD abweicht.
When `run_selftest(...)` mit diesem Scope läuft. Then es liefert **Exit/Return 0**
(SKIP) und führt **keine** Commit-Mismatch-Prüfung durch (kein False-FAIL).

**AC-4:** Given ein Deploy mit committetem Scope `backend` oder `full-stack` und
eine zu HEAD passende, gültige Attestation. When `run_selftest(...)` läuft. Then
der bisherige Pfad (Commit-Attestation, Health, AC-Probe) wird **unverändert**
durchlaufen (keine Regression des Erfolgsfalls).

**AC-5:** Given `_detect_committed_scope(repo_dir)` gegen ein echtes Git-Repo,
dessen letzter Commit ausschließlich `.claude/`- bzw. `docs/`-Dateien ändert.
When die Funktion läuft. Then sie liefert `"docs-only"`; ändert der letzte
Commit eine Datei unter `src/`/`api/`/`internal/`/`cmd/`, liefert sie
`"backend"`.

**AC-6:** Given mehrere E-Mails als geparste `email.message.Message`-Objekte —
eine mit `X-GZ-Mail-Type: trip-briefing` und einem Subject, das den Marker-Token
enthält, weitere fremde ohne Marker bzw. mit anderem Subject. When die
Auswahl-Prädikate (`_message_matches(headers, mail_type=..., subject_contains=...)`)
angewandt werden. Then nur die eigene markierte Mail matcht; fremde Mails ohne
passenden `X-GZ-Mail-Type` bzw. ohne Subject-Marker matchen nicht.

**AC-7:** Given ein RFC-2047-kodiertes Subject (z.B. mit Em-Dash/Umlaut). When
`_message_matches` mit einem `subject_contains`-Marker prüft. Then das Subject
wird vor dem Substring-Vergleich dekodiert (Marker wird im dekodierten Subject
gefunden) — Python-seitiges Substring-Matching, nicht IMAP-`SEARCH SUBJECT`.

**AC-8:** Given keine expliziten Filter (`mail_type=None`, `subject_contains=None`).
When `fetch_latest_message()` ohne Argumente aufgerufen wird. Then das bisherige
Verhalten bleibt erhalten (neueste Mail wird zurückgegeben) — die Änderung ist
rückwärtskompatibel/additiv.

## Out of Scope

- Abkündigung des Singleton-Fallbacks in `_e2e_paths.default_e2e_path` (separat;
  Scope-SKIP entschärft das Problem bereits).
- Der in #786 genannte Nebenbefund zu `test_staging_gate.py::TestGateCheckModeB`
  (umgebungsabhängige Hauptrepo-HEAD-Kopplung) — eigenes Issue/Folgearbeit.
- Änderungen am `staging_gate.py`-Scope-Klassifizierer (wird gespiegelt, nicht
  refaktoriert, um das laufende Gate nicht zu riskieren).
