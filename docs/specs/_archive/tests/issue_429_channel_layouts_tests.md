---
entity_id: issue_429_channel_layouts_tests
type: tests
created: 2026-05-28
updated: 2026-05-28
status: draft
version: "1.0"
tags: [tests, backend, data-model, channel-layouts, issue-429, epic-428]
parent: issue_429_channel_layouts
phase: phase5_tdd_red
---

# Issue #429 — Datenmodell „Layout pro Kanal" (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für `docs/specs/modules/issue_429_channel_layouts.md`. Jeder pytest-Test mappt 1:1 auf ein Acceptance Criterion der Parent-Spec (AC-1..AC-7). AC-8 (TypeScript-Typen) wird durch ein separates Frontend-Test-Artefakt abgedeckt — sobald die Frontend-Edits in PR 1 erfolgen.

Parent-Spec: `docs/specs/modules/issue_429_channel_layouts.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_429_channel_layouts.py` (NEU — RED-Phase-Tests für `UnifiedWeatherDisplayConfig.per_channel_layouts`, `get_metrics_for_channel(channel, report_type)`, den erweiterten `_parse_display_config()`-Pfad und die Backward-Compat-Garantie in `render_for_channel`).

## Test Inventory

### Python (`tests/tdd/test_issue_429_channel_layouts.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_loader_reads_channel_layouts` | AC-1 | Trip-JSON mit `channel_layouts` → `dc.per_channel_layouts` ist nicht None, enthält pro Kanal eine korrekt typisierte `MetricConfig`-Liste mit Reihenfolge und Bucket erhalten. |
| `test_ac1_all_empty_channel_layouts_treated_as_none` | AC-1 (Invariante) | `channel_layouts` mit ausschließlich leeren Kanal-Listen → `dc.per_channel_layouts` ist None (effektiv „nicht gesetzt"). |
| `test_ac2_legacy_trip_has_no_per_channel_layouts` | AC-2 | Alter Trip ohne `channel_layouts` → `dc.per_channel_layouts is None` und `get_metrics_for_channel("email", "evening")` liefert dasselbe wie `get_metrics_for_report_type("evening")`. |
| `test_ac3_per_channel_layout_wins_over_global` | AC-3 | Email-Layout gespeichert → `get_metrics_for_channel("email", "evening")` liefert genau die Email-Liste (eigene Reihenfolge), nicht die globale Liste. |
| `test_ac4_missing_channel_falls_back_to_global` | AC-4 | Signal nicht in `channel_layouts` (nur Email/Telegram gesetzt) → `get_metrics_for_channel("signal", "morning")` fällt auf globale `get_metrics_for_report_type("morning")` zurück. |
| `test_ac5_channel_limits_still_applied_with_per_channel_layouts` | AC-5 | Telegram-Layout mit 10 primary-Metriken → `render_for_channel("telegram", dc, "evening")` respektiert `CHANNEL_LIMITS["telegram"]=8` (max 7 in `table_columns`, Rest in `detail_metrics`, `demoted_count==3`). |
| `test_ac6_legacy_trip_render_bit_identical` | AC-6 | Alter Trip ohne `channel_layouts` durch komplette Render-Pipeline → `table_columns`, `detail_metrics`, `demoted_count` für Email/Telegram/SMS bit-identisch zum heutigen Verhalten (Regression-Sentinel). |
| `test_ac7_empty_channel_layout_no_fallback` | AC-7 | `per_channel_layouts["sms"] == []` (User hat alles deaktiviert) → `get_metrics_for_channel("sms", "evening")` liefert leere Liste, kein Fallback auf globale Liste. |

### TypeScript (AC-8) — kein Python-Test

AC-8 ist eine TypeScript-Typ-Anforderung (`ChannelLayouts`-Interface kompilierbar). Wird mit `tsc --noEmit` gegen `frontend/src/lib/types.ts` verifiziert, sobald die Frontend-Typen in PR 1 ergänzt sind. Kein eigener pytest-Eintrag.

## Implementation Details

Tests folgen dem No-Mocks-Pattern des Projekts (CLAUDE.md: KEINE MOCKED TESTS):

- Reine Datenstrukturen (`UnifiedWeatherDisplayConfig` / `MetricConfig`) + echte Aufrufe der (noch zu bauenden) Methoden.
- Test-Fixtures als JSON-Dicts in Helper-Funktionen (`_legacy_trip_data`, `_per_channel_trip_data`, `_empty_sms_layout_trip_data`).
- Echter Aufruf von `_parse_display_config()` aus `src/app/loader.py` — kein `Mock()`, kein `patch()`, kein `MagicMock`.
- `render_for_channel`-Tests laufen gegen die echte Funktion aus `src/output/renderers/channel_layout.py`.

## RED-Phase-Erwartung

- AC-1, AC-3, AC-4, AC-7, AC-5 + Invariante: **AttributeError** beim Zugriff auf `dc.per_channel_layouts` oder `dc.get_metrics_for_channel(...)` — Feld/Methode existiert noch nicht.
- AC-2: scheitert mit AttributeError beim Aufruf von `get_metrics_for_channel`.
- AC-6: läuft heute schon grün (Regression-Sentinel) — er testet das BESTEHENDE Verhalten und stellt sicher, dass der Refactor es nicht bricht. Der Test bleibt nach Implement grün.

## Expected Behavior

- **Input:** verschiedene `display_config`-Dicts mit/ohne `channel_layouts`.
- **Output:** `UnifiedWeatherDisplayConfig`-Instanzen mit erwarteten `per_channel_layouts`-Werten, `ChannelLayout`-Ergebnisse aus `render_for_channel`.
- **Side effects:** Keine I/O, keine DB-Writes.

## Acceptance Criteria

**AC-T1:** Given der Test-Lauf `pytest tests/tdd/test_issue_429_channel_layouts.py -v` /
When alle 8 Test-Funktionen ausgeführt werden /
Then schlagen 7 von 8 Tests in der RED-Phase mit AttributeError fehl (Feld/Methode existiert nicht) und 1 Test (AC-6 Regression-Sentinel) läuft bereits grün als Schutznetz.

**AC-T2:** Given die GREEN-Phase ist abgeschlossen (Implementation von `per_channel_layouts` + `get_metrics_for_channel`) /
When derselbe pytest-Lauf wiederholt wird /
Then sind alle 8 Tests grün und das `pytest`-Exit-Code ist 0 — kein Test wurde stillgelegt, kein `@pytest.mark.skip` eingefügt.

## Known Limitations

- AC-8 (TypeScript-Typen) wird nicht durch pytest abgedeckt — separater `tsc --noEmit`-Lauf in PR 1.
- Die Tests prüfen keine vollständige End-to-End-Render-Pipeline (Briefing-HTML); das ist Sache der `test_html_email.py`-Suite, die in PR 3 erweitert wird.

## Changelog

- 2026-05-28: Initial test manifest für Issue #429 (PR 1/4 von Epic #428).
