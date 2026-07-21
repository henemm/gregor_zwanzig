---
entity_id: issue_816_alert_deviation_tests
type: tests
created: 2026-06-14
updated: 2026-06-14
status: draft
version: "1.0"
tags: [tests, alert, deviation, alert-state, change-detection, epic-813, issue-816]
parent: issue_816_alert_deviation_core
phase: phase5_tdd_red
---

# Issue #816 — Alert-Abweichungs-Kern (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für `docs/specs/modules/issue_816_alert_deviation_core.md`.
Jeder pytest-Test mappt 1:1 auf ein Acceptance Criterion der Parent-Spec.
Mock-frei (CLAUDE.md): echter Dateisystem-State unter `data/users/<user_id>/`,
echte Service-Aufrufe, echter Telegram-Socket-Sink, echtes `build_mime_message`-MIME.

Parent-Spec: `docs/specs/modules/issue_816_alert_deviation_core.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_816_alert_deviation.py` (NEU)

## Test Inventory

### Python (`tests/tdd/test_issue_816_alert_deviation.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_alert_does_not_overwrite_briefing_snapshot` | AC-1 | Zwei Alert-Läufe lassen den Briefing-Snapshot byte-gleich + mtime unverändert (Snapshot-Overwrite raus). |
| `test_ac2_repeated_same_deviation_is_suppressed` | AC-2 | Erster Lauf alertet + legt alert_state an; zweiter Lauf gleiche Δ → kein Telegram-Versand. |
| `test_ac3_escalation_triggers_new_alert_and_updates_state` | AC-3 | last_reported_value=10, frisch 20 → Δ=10 ≥ Threshold → erneuter Alert, last_reported_value=20. |
| `test_ac4_alert_state_is_tenant_isolated` | AC-4 | Alert für user_a schreibt alert_state nur unter user_a; user_b unberührt. |
| `test_ac5_briefing_send_resets_alert_state` | AC-5 | Briefing-Versand-Pfad resettet alert_state des Trips (load leer/Datei weg). |
| `test_ac6_deviation_alert_plain_content_sorted_with_km` | AC-6 | Plain-Part: Kopfzeile, Vorher→Jetzt-Zeilen mit km, nach Stärke sortiert, Fußzeile; keine Briefing-Blöcke/Stundentabelle. |
| `test_ac6_km_fallback_when_distance_zero` | AC-6 | distance_from_start_km==0.0 → Zeile ohne km, Etappe+Zeit bleiben. |
| `test_ac6b_km_shown_when_start_is_zero_but_end_positive` | AC-6b | Tag-1-Start (start_km=0.0, end_km=6.0) zeigt 'km 0–6' — F002-Fix für falsy-0.0-Bug. |
| `test_ac7_header_set_and_validator_noop` | AC-7 | Header `X-GZ-Mail-Type: deviation-alert` gesetzt; briefing_mail_validator → No-Op (ok=True). |
| `test_ac8_delta_only_detection_excludes_absolute_rules` | AC-8 | `detect_changes(include_absolute=False)` liefert keine absolute-Rule-Changes. |
| `test_ac8b_absolute_rule_trip_still_gets_delta_alert` | AC-8b | Trip mit reiner ABSOLUTE-Regel (#809-SyncAlertRules) bekommt Δ-Alert (Invariante Fix-Loop 1). |

## Implementation Details

Tests folgen dem No-Mocks-Pattern des Projekts:
- Echte `Trip`/`Stage`/`Waypoint`/`SegmentWeatherData`-Dataclasses.
- Echter lokaler Telegram-HTTP-Sink (Socket) zählt tatsächliche Versand-Aufrufe;
  Monkeypatch von `TELEGRAM_API_BASE` ist ein Konfigurations-Seam, kein Mock.
- Echte Persistenz unter `data/users/tdd-816-*/` mit Cleanup-Fixture.
- Echtes `build_mime_message`-MIME-Objekt serialisieren, Plain-Part prüfen.

RED-Zustand (Feature existiert noch nicht):
- AC-1: scheitert als AssertionError (Snapshot wird heute überschrieben).
- AC-2/3/4/5: ImportError `services.alert_state` bzw. fehlender Scheduler-Hook.
- AC-6/7: ImportError `output.renderers.email.alert_compact.render_deviation_alert`.
- AC-8: TypeError — `detect_changes` kennt kein `include_absolute`-Argument.

## Changelog

- 2026-06-14: v1.0 Test-Manifest erstellt (Issue #816, Epic #813 Slice 1)
