---
entity_id: feature_656_radar_nowcast_tests
type: tests
created: 2026-06-07
updated: 2026-06-08
status: draft
version: "1.0"
tags: [tests, feature, radar, nowcast, issue-656]
parent: radar_nowcast
phase: phase5_tdd_red
---

# Feature #656 — Radar-Nowcasting (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für Feature #656 (Radar-Nowcasting). Jeder Eintrag mappt einen
pytest-Funktionsnamen auf das in der Parent-Spec definierte Acceptance-Criterion.

Parent-Spec: `docs/specs/modules/radar_nowcast.md`.

## Source

- **Files:**
  - `tests/tdd/test_feature_656_radar_nowcast.py` (NEU — mock-frei)
- **Spec:** `docs/specs/modules/radar_nowcast.md` v1.0

## Test Inventory

Die Test-Funktionsnamen tragen die AC-Bezeichner, damit der Spec-Enforcement-Hook
sie auflösen kann.

| Test-Funktion | AC | Was geprüft wird |
|---------------|----|------------------|
| `ac1_brightsky_fetch_radar_returns_real_frames` | AC-1 | Echter BrightSky-`fetch_radar`-Call für eine DE-Koordinate liefert ≥1 RadarFrame mit monotonen Zeitstempeln und nicht-negativen Niederschlagsraten. |
| `ac2_intensity_to_text_levels` | AC-2 | `intensity_to_text` mappt reale Raten (0.0/0.3/2.5/8.0 mm/h) auf die korrekten Stufen-Strings. |
| `ac2_format_now_text_mentions_onset_and_source` | AC-2 | `format_now_text` nennt bei bevorstehendem Regen Intensität, Beginn und Quelle. |
| `ac2_format_now_text_dry` | AC-2 | `format_now_text` liefert bei Trockenheit eine klare „kein Regen"-Aussage ohne Onset. |
| `ac3_now_command_returns_nowcast_under_10s` | AC-3 | `### now` auf Trip mit heutiger Etappe liefert in <10s ein erfolgreiches CommandResult mit Nowcast-Aussage + Quelle. |
| `ac3_now_command_without_today_stage_gives_clear_message` | AC-3 | `### now` ohne heutige Etappe liefert eine klare, nicht-leere Meldung statt Absturz. |
| `ac4_radar_alert_due_pure_logic` | AC-4 | Reine Entscheidungsfunktion `radar_alert_due`: Onset ≤ Schwelle → True, sonst False. |
| `ac4_check_radar_alerts_sends_once_then_throttles` | AC-4 | `check_radar_alerts` sendet genau 1 Alert + schreibt 1 alert_log-Eintrag (HIGH); zweiter Lauf throttelt (0). |

## Changelog

- 2026-06-07: Initial test manifest (Issue #656)
- 2026-06-08: Implementation complete — all AC tests passing, mock-free verification confirmed; Gewitter-Stufe folgt in Issue #660
