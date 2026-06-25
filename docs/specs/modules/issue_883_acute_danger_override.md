---
entity_id: issue_883_acute_danger_override
type: feature
created: 2026-06-25
updated: 2026-06-25
status: draft
version: "1.0"
tags: [alert, radar, nowcast, convective, safety-override, briefing-suppression, epic-813, slice-4]
---

# Issue #883 — Schmaler Sicherheits-Override für akute Gefahr (Epic #813 Slice 4)

## Approval

- [ ] Approved

## Purpose

Der Radar-Wächter (Slice 3, #818) unterdrückt heute einen Alert, wenn das letzte Briefing den Regen für die Onset-Stunde bereits angekündigt hat (`_briefing_precip >= 0.5` → kein Alert, "war nicht überraschend"). Bei **echter akuter Gefahr** — einem konvektiven Nowcast (Gewitter/Hagel, `NowcastResult.is_convective`) — ist dieses Schweigen falsch: Eine heute Morgen gelesene Briefing-Zeile und ein in ~20 Minuten unmittelbar aufziehendes Gewitter sind verschiedene Entscheidungsmomente. Dieser Slice durchbricht **ausschließlich** die Briefing-Unterdrückung bei konvektiver Gefahr. Alles andere (normaler Regen, Wind, Temperatur) bleibt rein relativ; alle Spam-Bremsen bleiben aktiv.

**PO-Entscheidung 2026-06-25 (Epic #813):** Option 2 (schmaler Override). Nur Gewitter/Hagel; Sturmböen NICHT (keine Böen-Daten im Radar-Pfad); Nachtruhe wird respektiert.

## Source

- **File:** `src/services/trip_alert.py` — `check_radar_alerts()`: Briefing-Suppression-Block (~685) um konvektive Ausnahme; Mail-Text (~734-735) fallabhängig.
- **File:** `tests/tdd/test_issue_883_acute_danger_override.py` — Neue mock-freie Tests (CREATE).

> **Schicht: Python-Backend.** Alle produktiven Änderungen in `src/services/trip_alert.py`.
> Go-API (`api/`, `internal/`), Frontend (`frontend/`), Briefing-Format, UI und der Forecast-Alert-Pfad (`check_and_send_alerts`, bleibt Δ-only) bleiben unberührt.

## Estimated Scope

- **LoC:** ~60 netto (~15 produktiv in `check_radar_alerts` + ~45 Tests)
- **Files:** 1 produktiv (MODIFY) + 1 Testdatei (CREATE)
- **Effort:** small

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/radar_service.py` — `NowcastResult.is_convective` | upstream | Flag für Gewitter/Hagel (WMO 95/96/99); Auslöser des Overrides |
| `src/services/radar_service.py` — `radar_alert_due(result, threshold_min=20)` | upstream | Onset-Gate (≤20 Min); Override reitet darauf auf, kein eigenes Zeitfenster |
| `src/services/trip_alert.py` — `_briefing_precip_for_onset` | upstream | Liefert Briefing-Stundenwert; entscheidet, ob Regen angekündigt war |
| `src/services/alert_state.py` — `AlertStateService` | upstream | Cooldown / Doppel-Alert-Guard / `radar_throttle` — bleiben unverändert aktiv |
| Issue #818 (Slice 3) | prerequisite | Muss deployed sein (✅ live) |

## Implementation Details

### Kern-Eingriff: Briefing-Suppression konditional (≈ trip_alert.py:680-689)

Heute:
```
if _briefing_precip is not None and _briefing_precip >= 0.5:
    continue   # war im Briefing angekündigt → unterdrücken
```

Neu:
```
_briefing_announced = (_briefing_precip is not None and _briefing_precip >= 0.5)
# Sicherheits-Override (Slice 4): konvektive Gefahr durchbricht die Briefing-
# Unterdrückung. Normaler (nicht-konvektiver) angekündigter Regen bleibt unterdrückt.
if _briefing_announced and not result.is_convective:
    continue
```

- Greift erst **nach** `radar_alert_due(...)` (Onset ≤20 Min) und **nach** dem QuietHours- und Throttle-Check — diese bleiben also wirksam.
- Der Doppel-Alert-Guard (≈691-709) bleibt **unverändert** aktiv: hat ein Forecast-Alert für dasselbe Segment innerhalb des Cooldowns gefeuert, wird auch der Override unterdrückt (max. eine Meldung).

### Mail-Wording fallabhängig (≈ trip_alert.py:734-735)

Heute fix:
```
onset_text += ", im Briefing nicht angekündigt"
```

Neu:
```
if _briefing_announced:
    onset_text += ", jetzt akut"          # Override: Regen WAR angekündigt, ist jetzt Gewitter
else:
    onset_text += ", im Briefing nicht angekündigt"
```

Begründung: Im Override-Fall wäre "im Briefing nicht angekündigt" eine Falschaussage. `src/outputs/radar_alert.py` (Body-/Subject-Builder) bleibt unverändert — nur der eingespeiste `onset_text` ändert sich.

### Unverändert (Invarianten)

- `radar_alert_due`-Onset-Gate (≤20 Min), `radar_throttle`-Cooldown, Doppel-Alert-Guard, "nur kommende Strecke"-Filter (Slice 2/3), QuietHours-Check.
- Forecast-Alert-Pfad (`check_and_send_alerts`) bleibt strikt Δ-only.
- Mandantentrennung über echte `user_id`.

## Acceptance Criteria

- **AC-1:** Given der Briefing-Snapshot für die Onset-Stunde des aktiven Segments enthält `precip_1h_mm >= 0.5` (Regen angekündigt) UND der injizierte `NowcastResult` ist konvektiv (`is_convective=True`) mit Onset ≤20 Min / When `check_radar_alerts()` läuft / Then wird ein Radar-Alert gesendet (Override greift: Gewitter durchbricht die Briefing-Unterdrückung), `alert_state["radar_throttle"]` wird gesetzt. Test: Snapshot mit `precip_1h_mm = 1.2` unter `data/users/tdd-883-ac1/`, konvektives `NowcastResult` via DI-Seam; nach Lauf Alert-Log-Eintrag + `radar_throttle.reported_at` nachweisbar. Kein Mock.
- **AC-2:** Given derselbe Briefing-Snapshot (`precip_1h_mm >= 0.5`, Regen angekündigt) UND der `NowcastResult` ist **nicht** konvektiv (`is_convective=False`) / When `check_radar_alerts()` läuft / Then wird **kein** Alert gesendet (Override greift NICHT, das reine Abweichungs-Modell bleibt für normalen Regen erhalten). Test: Snapshot `precip_1h_mm = 1.2`, nicht-konvektives `NowcastResult` via DI-Seam unter `data/users/tdd-883-ac2/`; nach Lauf kein Alert-Log-Eintrag, kein `radar_throttle`. Kein Mock.
- **AC-3:** Given ein Override-Alert (konvektiv + angekündigter Regen) wurde gerade gesendet und `alert_state["radar_throttle"]` ist gesetzt / When `check_radar_alerts()` mit identischen Bedingungen innerhalb des Cooldown-Fensters erneut läuft / Then wird **kein** zweiter Alert gesendet (Cooldown bleibt auch beim Override aktiv, max. 1 Meldung). Test: zwei aufeinanderfolgende Läufe unter `data/users/tdd-883-ac3/`; zweiter Lauf erzeugt keinen neuen Alert-Log-Eintrag. Kein Mock.
- **AC-4:** Given der Override greift (konvektiv + `precip_1h_mm >= 0.5` angekündigt) / When die Radar-Alert-Mail gebaut wird / Then enthält der Mail-Text **nicht** die Phrase "im Briefing nicht angekündigt" (das wäre falsch) und stattdessen den Akut-Hinweis ("jetzt akut"). Test: Mail-Body über den `_mail_sink`-Seam abgreifen; Assertion auf An-/Abwesenheit der Phrasen. Kein Mock.
- **AC-5:** Given konvektive akute Gefahr (`is_convective=True`, Onset ≤20 Min, Regen angekündigt) UND die aktuelle Uhrzeit liegt in den konfigurierten Quiet Hours des Trips / When `check_radar_alerts()` läuft / Then wird **kein** Alert gesendet (Nachtruhe wird respektiert, der Override durchbricht nur die Briefing-Unterdrückung, nicht die Quiet Hours). Test: Trip mit Quiet-Hours-Fenster, das `now` einschließt, unter `data/users/tdd-883-ac5/`; nach Lauf kein Alert. Kein Mock.
- **AC-6:** Given zwei Nutzer (`tdd-883-ac6a`, `tdd-883-ac6b`) mit je eigenem Trip, Snapshot (`precip >= 0.5`) und konvektivem Nowcast / When `check_radar_alerts()` für `tdd-883-ac6a` einen Override-Alert auslöst / Then bleibt `data/users/tdd-883-ac6b/` vollständig unberührt (kein Alert, kein `radar_throttle`). Test: zwei `TripAlertService`-Instanzen mit separaten `user_id`; nach Lauf unter `ac6a` Timestamp-/Existenz-Vergleich aller Dateien unter `ac6b`. Kein Mock.

## AC → Test Mapping

| AC | Test |
|----|------|
| AC-1 | `test_ac1_convective_override_fires_despite_briefing` |
| AC-2 | `test_ac2_nonconvective_announced_rain_stays_suppressed` |
| AC-3 | `test_ac3_override_respects_cooldown` |
| AC-4 | `test_ac4_override_mail_wording_not_unannounced` |
| AC-5 | `test_ac5_override_respects_quiet_hours` |
| AC-6 | `test_ac6_mandantentrennung_isolated` |

## Out of Scope

- **Sturmböen-Override:** `NowcastResult` trägt keine Wind/Böen-Daten; eine Böen-basierte Auslösung müsste Forecast-Daten in den Nowcast-Pfad ziehen → eigener Slice, falls überhaupt nötig.
- **Quiet-Hours-Durchbruch bei Gefahr:** bewusst nicht; Nachtruhe bleibt eine respektierte Nutzer-Einstellung.
- Forecast-Alert-Pfad, Alerts-Tab-UI, Mail-Layout.
