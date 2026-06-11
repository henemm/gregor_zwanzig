---
entity_id: issue_765_backend_test_hygiene
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [tests, hygiene, backend, cleanup, gate]
---

<!-- Issue #765 — Backend-Test-Hygiene-Sweep (Nebenbefund aus #754) -->

# Backend-Test-Hygiene-Sweep #765

## Approval

- [x] Approved

## Purpose

Das in #754 (Frontend) behobene Anti-Pattern existiert genauso im Backend:
Backend-Tests lesen echten **Produkt-Quelltext** (`.py`/`.go` unter `src/`, `api/`,
`internal/`, `cmd/`) via `read_text()` oder grep/rg-Subprozess und asserten auf
Code-Strings (`assert "tz_for_coords" in src`) statt auf tatsächliches Verhalten.

Das verstößt gegen CLAUDE.md **„Dateiinhalt-Checks sind VERBOTEN"** und erzeugt
dieselben Risiken: falsch-rote Tests bei harmlosen Refactorings, maskierte echte
Regressionen, Scheinsicherheit. Ein Detektor-Gate (analog #754) räumt die
bestehende Schuld ab **und** verhindert Regress.

**Scope: test-/tooling-only.** Keine Produkt-Code-Änderung in `src/`, `api/`,
`internal/`, `cmd/`, `frontend/src/`. Kein Prod-Deploy. Verifikation lokal über
`uv run pytest`.

## Source

### Detektor-Gate (neu)

`tests/tdd/test_765_backend_hygiene_compliance.py` (markiert `# doc-compliance-test`).
Scannt **alle** `tests/**.py` und flaggt jeden Test, der via `read_text()`,
`subprocess`-`grep`/`rg` (`--include`/`--glob=*.py`/`*.go`) den **Inhalt einer
existierenden Produkt-Quelltext-Datei** unter `src/`/`api/`/`internal/`/`cmd/` mit
Endung `.py`/`.go` liest. **Pfad-Auflösung statt naivem Substring** (robuster gegen
entfernte Pfad-Konstruktion wie `parents[2] / "src" / ...`). Selbst-Markierung
`# doc-compliance-test` ist **kein** Freibrief für Produkt-Quelltext (Bypass-Schutz,
Lehre aus #754).

### Offender-Dateien (14, pfad-aufgelöst)

| Datei | gelesener Produkt-Quelltext | Disposition |
|-------|------------------------------|-------------|
| `tests/integration/test_cli_wintersport.py` | `src/app/cli.py` | Source-Asserts raus, echten CLI-Run behalten |
| `tests/refactor/test_epic_129a_1_module_structure.py` | `api/routers/compare.py`, `src/services/compare_subscription.py` | Refactor abgeschlossen → Source-Struktur-Asserts löschen (Import/Verhalten deckt ab) |
| `tests/refactor/test_epic_129a_2_module_structure.py` | `api/routers/gpx.py` | dito |
| `tests/tdd/test_bug_198_notify_test_resend.py` | `api/routers/notify.py` | Source-Check raus, echten Settings-Roundtrip behalten |
| `tests/tdd/test_bug_400_alert_tz.py` | `src/services/trip_alert.py` | reine Source-Inspektion → auf echten Render-Verhaltenstest umstellen oder löschen wenn gedeckt |
| `tests/tdd/test_email_design_tokens.py` | `src/output/renderers/email/html.py` | gemischt: gerenderte-`html`-Asserts behalten, `HTML_PY.read_text()`-Block raus |
| `tests/tdd/test_email_profile_pipeline.py` | `preview_service.py`, `trip_report_scheduler.py` | gemischt: Render-Asserts behalten, Source-Asserts raus |
| `tests/tdd/test_issue_256_thunder_color.py` | `src/output/renderers/email/design_tokens.py` | `design_tokens.py`-Read raus (app.css/design_system.md sind kein Produkt-`.py`/`.go`) |
| `tests/tdd/test_issue_257_trip_briefing_polish.py` | `src/output/renderers/email/html.py` | gemischt: Render-Asserts behalten, `html.py`-Read raus |
| `tests/tdd/test_issue_396_archive_stats.py` | `internal/handler/archive_stats.go`, `cockpit.go`, `store.go`, `trip_alert.py` | Go-Greps → echter API-Call gegen Go-Service oder löschen; py-Source-Asserts raus |
| `tests/tdd/test_issue_515_remove_subscription_jobs.py` | `api/routers/scheduler.py`, `internal/config/config.go`, `internal/scheduler/scheduler.go` | „Code entfernt"-Checks → echter HTTP-404/Verhaltensnachweis oder löschen |
| `tests/tdd/test_issue_623_trend_channels.py` | `html.py`, `plain.py`, `narrow.py` | gemischt: Render-Asserts behalten, `read_text`-Block (Z.45) raus |
| `tests/tdd/test_trip_alert_profile.py` | `src/services/trip_alert.py` | reine Source-Inspektion → auf echten Alert-Render-Test umstellen oder löschen wenn gedeckt |
| `tests/unit/test_issue_131_alert_klarheit.py` | `src/formatters/trip_report.py` | gemischt: behaviorale Asserts behalten, Source-Read raus |

Die **maßgebliche** Liste produziert das Gate selbst (Pfad-Auflösung); diese
Tabelle ist die Triage-Vorgabe. Falls das Gate weitere Treffer findet, gilt
dieselbe Disposition-Regel.

### Triage-Regel (pro Datei)

1. **Gemischt** (behaviorale Asserts auf gerenderte Ausgabe/realen Zustand
   vorhanden) → nur die Source-Inspection-Asserts entfernen, behaviorale behalten.
2. **Verhalten bereits anderswo gedeckt** → Datei/Asserts löschen.
3. **Relevant + ungedeckt** → auf echten Verhaltenstest umstellen (echter
   Funktionsaufruf / echter HTTP-Call / echter DB-/Render-Zustand). **KEINE Mocks.**
4. **Go-Source-Greps** → echter API-Call gegen laufenden Go-Service oder Go-Testpfad;
   im Zweifel löschen + Abdeckung anderswo nachweisen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/tdd/test_754_755_test_hygiene_compliance.py` | Gate (read-only) | Struktur-Vorbild (Regex `_FORBIDDEN_READ`, parametrisierte Datei-Liste) |
| `src/`, `api/`, `internal/`, `cmd/` Produktquelltext | Prod (read-only) | Referenz für Pfad-Auflösung — wird NICHT geändert |
| `uv run pytest` | Tooling | Verifikation grün vs. rot |
| bestehende Integration/E2E-Suite | Coverage | Ersatz für gelöschte Source-Struktur-Asserts |

## Acceptance Criteria

**AC-1:** Given das neue Detektor-Gate `tests/tdd/test_765_backend_hygiene_compliance.py`;
When es über alle `tests/**.py` läuft;
Then schlägt es VOR dem Sweep rot fehl (es listet die ≥14 Offender mit dem jeweils
gelesenen Produkt-Quelltext-Pfad) und ist NACH dem Sweep grün — die Erkennung nutzt
echte Pfad-Auflösung (`.py`/`.go` unter `src/`/`api/`/`internal/`/`cmd/`), nicht bloß
einen Datei-Namen-Substring.

**AC-2:** Given jede der gelisteten Offender-Dateien;
When der Sweep abgeschlossen ist;
Then enthält keine dieser Dateien mehr einen `read_text()`- oder grep/rg-basierten
Assert auf den **Inhalt** einer Produkt-`.py`/`.go`-Quelldatei — gemischte Dateien
behalten dabei ihre behavioralen Asserts (auf gerenderte Ausgabe / realen Zustand)
unverändert lauffähig.

**AC-3:** Given die rein source-inspizierenden Dateien ohne behaviorale Abdeckung
(`test_bug_400_alert_tz.py`, `test_trip_alert_profile.py`, `test_issue_515_*`,
`test_issue_396_*`);
When der Sweep abgeschlossen ist;
Then ist jede entweder (a) gelöscht UND ihr Verhalten ist nachweislich durch einen
anderen echten Test gedeckt, ODER (b) auf einen echten Verhaltenstest umgestellt
(echter Funktionsaufruf / HTTP-Call / Render-Zustand) — **ohne neue Mocks/`patch`/
`MagicMock`** im Diff.

**AC-4:** Given eine Test-Datei mit der Markierung `# doc-compliance-test`, die
trotzdem Produkt-`.py`/`.go`-Quelltext via `read_text()`/grep liest;
When das Gate läuft;
Then flaggt das Gate sie dennoch als Verstoß (die Markierung rechtfertigt nur
Doku-/Tooling-/Workflow-Artefakt-Reads, niemals Produkt-Quelltext — Bypass-Schutz).

**AC-5:** Given den vollständigen Diff dieses Workflows;
When er gegen `origin/main` verglichen wird;
Then berührt er ausschließlich `tests/`, `docs/`, `.claude/` (test/tooling/docs) —
kein Produktcode in `src/`, `api/`, `internal/`, `cmd/`, `frontend/src/` — und führt
keinen neuen Mock/`patch`/`MagicMock` ein.

## Non-Goals

- Keine Bereinigung von Tests, die **Runtime-Daten** (`data/users/*.json`,
  Workflow-State, `e2e_verified.json`) oder **Tooling/Doku** (`.claude/hooks/*.py`,
  `CLAUDE.md`, `docs/`, `README`) lesen — das ist legitime Zustands-/Compliance-Prüfung.
- Keine Frontend-`.svelte`/`.ts`-Reads (#754-Scope, bereits erledigt).
- Keine Produkt-Code-Änderung, kein Prod-Deploy.
