---
entity_id: issue_638_alerts_redesign_tests
type: tests
created: 2026-06-08
updated: 2026-06-08
status: approved
version: "1.0"
tags: [alerts, channels, severity, routing, multi-user]
---

# TDD-RED-Tests: Issue #638 Alerts-Tab Redesign

## Approval

- [x] Approved

## Purpose

Mock-freie Verhaltenstests für den Alerts-Redesign: Severity-Falle beseitigen,
Kanal pro Alert (Routing + Persistenz), Mandantentrennung. Beobachtung über
echte Socket-Sinks (Telegram-HTTP, SMTP-Greeter) und echte Trip-Persistenz.

## Source

- **File:** `tests/tdd/test_issue_638_alerts_redesign.py`
- **Implementation under test:** `src/services/trip_alert.py`
  (`TripAlertService.check_and_send_alerts`, `_filter_significant_changes`, `_send_alert`),
  `src/app/models.py` (`AlertRule.channels`), `src/app/loader.py` (parse/serialize alert_rules)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| TripAlertService | module | Alert-Detektion + kanalbewusster Versand |
| AlertRule | model | Neues `channels`-Feld |
| EmailOutput / TelegramOutput | module | Echte Kanal-Outputs gegen lokale Sinks |
| loader save_trip/load_trip | module | Persistenz-Roundtrip |

## Test Cases

| # | Test | Erwartetes Verhalten |
|---|------|---------------------|
| 1 | `test_ac1_info_severity_alert_is_no_longer_silently_swallowed` | Aktiver Alert (alt severity=info), Schwelle überschritten → wird über Telegram zugestellt (kein stilles Verschlucken durch MODERATE-Filter) |
| 2 | `test_ac2_per_alert_channel_override_beats_briefing_channel` | `rule.channels=[telegram]` gewinnt über `report_config` (email an, telegram aus) → nur Telegram zugestellt, kein E-Mail-Versuch |
| 3 | `test_ac3_empty_channels_inherit_briefing_channels` | Leere `rule.channels` → erbt aktive Briefing-Kanäle (Telegram) → Telegram zugestellt |
| 4 | `test_ac4_channels_survive_save_load_roundtrip` | `alert_rules[].channels` überleben save_trip → load_trip unverändert |
| 5 | `test_ac4_legacy_rule_without_channels_defaults_to_empty` | Bestands-Alert ohne `channels`-Feld lädt fehlerfrei mit `channels=[]` (kein Datenverlust) |
| 6 | `test_ac5_per_user_alert_channels_are_isolated` | Zwei Nutzer mit je eigenem Trip + eigenen Alert-Kanälen → mandantengetrennte Persistenz, keine Vermischung |
| 7 | `test_mixed_rules_union_both_channels` | Mixed-Rule-Fall: Regel-A=[telegram] + Regel-B=[]/briefing-email → Union-Semantik → BEIDE Kanäle bedient (kein stilles Verschlucken des geerbten E-Mail-Kanals) |
| 8 | `test_telegram_only_user_without_smtp_still_gets_alert` | Telegram-only-Nutzer (can_send_email==False, kein smtp_host) mit rule.channels=["telegram"] → Alert zugestellt, True zurück (F001: früher SMTP-Guard blockierte) |
| 9 | `test_legacy_path_no_alert_rules_still_sends_via_report_config` | Trip ohne aktive alert_rules + report_config (send_telegram=True) → Legacy-Detektor erkennt Change → Telegram-Alert zugestellt (leeres active_rules-Set darf Briefing-Kanäle aus report_config nicht verschlucken) |
| 10 | `test_f001_all_channels_off_sends_nothing` | report_config existiert mit send_email=False + send_telegram=False, keine aktiven alert_rules, Schwelle gerissen → kein Versand (kein SMTP-Attempt, kein Telegram); E-Mail-Default nur bei report_config=None |

## Expected Behavior

- **Input:** Synthetische Trips mit AlertRules (Schwelle überschritten), echte Settings,
  echte lokale Socket-Sinks für Telegram/SMTP.
- **Output:** RED vor Implementierung (Severity-Falle, fehlendes `channels`-Feld),
  GREEN nach Implementierung.
- **Side effects:** Schreibt Throttle/Snapshot in tmp- bzw. Test-User-Verzeichnisse; keine echten Mails/Telegram-Nachrichten.

## Known Limitations

- E-Mail-Kanal wird nur auf „nicht versucht"/„versucht" geprüft (Fast-Fail-Greeter ohne STARTTLS),
  nicht auf Inhalt — die inhaltliche E-Mail-Verifikation bleibt der Staging-Acceptance (`email_spec_validator`) vorbehalten.
- Frontend-ACs (Karten-Modell, Chip-Persistenz, Pixel-Fidelity) werden post-Deploy per
  Playwright/`staging-validator` gegen Staging verifiziert, nicht in dieser Datei.
