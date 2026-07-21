---
entity_id: issue_783_776_778_briefing_fixes_tests
type: tests
created: 2026-06-12
updated: 2026-06-12
status: draft
version: "1.0"
tags: [tests, briefing, email, scheduler, frontend, tech-debt, issue-783, issue-776, issue-778]
parent: issue_783_776_778_briefing_fixes
phase: phase5_tdd_red
---

# Briefing-Mail Bugfix-Bundle (#783 / #776 / #778) — Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest fuer `docs/specs/modules/issue_783_776_778_briefing_fixes.md`.
Jeder Test mappt auf ein Acceptance Criterion der Parent-Spec. Keine Mocks —
echte Modell-Objekte (#783), echter `format_email`-Aufruf (#778), Staging-IMAP
und Playwright in der Acceptance-Stage (#776, #783-AC-2).

## Source

- **File:** `tests/tdd/test_issue_783_startzeit.py` (NEU) — #783
- **File:** `tests/tdd/test_issue_778_dead_code.py` (NEU) — #778
- **File:** `tests/tdd/test_issue_776_metrics_toggle.py` (NEU) — #776 (Staging-IMAP, AC-4)
- **File:** `frontend/tests/e2e/issue_776_metrics_toggle.spec.ts` (NEU) — #776 Playwright (AC-3)

## Test Inventory

### #783 — Etappen-Startzeit (`tests/tdd/test_issue_783_startzeit.py`)

| Test-Funktion | AC | Was geprueft wird |
|---|---|---|
| `stage_start_time_overrides_stale_arrival_calculated_at_start` | AC-1 | `_convert_trip_to_segments`: start_time=14:00 gewinnt am Startpunkt vor stale `arrival_calculated=07:00` -> `segment.start_time.hour == 14` (RED: aktuell 7) |
| `explicit_waypoint_override_still_wins_over_stage_start` | AC-1 | Regressionsschutz: per-Waypoint `arrival_override=06:00` behaelt Vorrang vor Etappen-Startzeit |
| `briefing_mail_starts_at_configured_time_on_staging` | AC-2 | Staging-E2E (GZ_STAGING_E2E): echter Test-Versand + IMAP, erste Stundentabellen-Zeile = 14:00 |

### #778 — Toter Code (`tests/tdd/test_issue_778_dead_code.py`)

| Test-Funktion | AC | Was geprueft wird |
|---|---|---|
| `format_email_renders_after_dead_code_removal` | AC-5 | Echter `format_email`-Aufruf mit Segment-Objekten -> nicht-leerer HTML+Plain-Output, kein AttributeError/KeyError |
| `dead_formatter_methods_removed` | AC-5 | `# doc-compliance-test`: die fuenf toten Methoden-Namen kommen nicht mehr in `trip_report.py` vor (RED: aktuell vorhanden) |

### #776 — Sektionen-Toggle (`tests/tdd/test_issue_776_metrics_toggle.py` + Playwright)

| Test-Funktion | AC | Was geprueft wird |
|---|---|---|
| `metrics_summary_toggle_persists_and_hides_section` | AC-4 | Staging-E2E (GZ_STAGING_E2E): show_metrics_summary=false persistiert -> Mail ohne Metriken-Ueberblick (IMAP) |
| `issue_776_metrics_toggle.spec.ts` (Playwright) | AC-3 | Toggle im Wetter-Metriken-Tab umlegen + speichern -> `GET /api/trips/{id}` liefert `report_config.show_metrics_summary == false` |

## Test-Ausfuehrung

```bash
# RED-Phase (vor Implementation): #783 AC-1 und #778 doc-compliance sind ROT
uv run pytest tests/tdd/test_issue_783_startzeit.py tests/tdd/test_issue_778_dead_code.py -v

# Acceptance-Stage (#776 AC-3 Playwright, AC-2/AC-4 IMAP gegen Staging)
GZ_STAGING_E2E=1 uv run pytest tests/tdd/test_issue_783_startzeit.py tests/tdd/test_issue_776_metrics_toggle.py -v
```

## Changelog

- 2026-06-12: Initial test manifest fuer Issues #783, #776, #778.
