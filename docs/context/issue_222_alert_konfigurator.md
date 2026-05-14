---
issue: 222
title: "Alert-Konfigurator: Wizard + AlertsPreviewCard + Service-Umstellung auf alert_rules"
created: 2026-05-14
phase: phase1_context
---

# Context: Issue #222 — Alert-Konfigurator

## Request Summary

Issue #205 hat `trip.alert_rules` als Datenmodell + Migration eingeführt und live geschaltet. Dieses Issue schließt die User-sichtbare Lücke: Wizard-Step-4 schreibt strukturierte Rules, `AlertsPreviewCard` rendert sie, und `TripAlertService` liest sie statt der Legacy-`report_config`-Felder.

## Scope (drei Subscopes)

1. **Wizard Step 4 — Save-Pipeline:** `briefings.thresholds` (gust_kmh, precip_mm, thunder_level, snow_line_m) → `trip.alert_rules` (kind=absolute, severity=warning, enabled=true).
2. **AlertsPreviewCard rendern:** Pro `enabled=true`-Rule eine Zeile mit Metric-Label, Schwellwert+Unit, Severity-Pill, Edit-Link. Empty-State wenn keine enabled Rules.
3. **TripAlertService Umstellung:** Neue Factory `WeatherChangeDetectionService.from_alert_rules(rules)`. Wenn `trip.alert_rules` nicht leer → neue Factory; sonst Fallback auf bisherigen Pfad.

## Related Files

### Frontend (Svelte/TypeScript)

| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/types.ts:41-79` | AlertRule-Typdefinitionen (AlertRuleKind, AlertMetric, AlertSeverity, AlertRule, Trip.alert_rules). Read-only. |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts:312-373` | `toTripPayload()` — derzeit nur `report_config`-Mapping. Erweitern: `mapBriefingsToAlertRules(b.thresholds)` ergänzen. |
| `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` | Bestehendes UI bleibt unverändert. Schreibt in `wizard.briefings.thresholds`. |
| `frontend/src/lib/components/trip-wizard/steps/ThresholdRow.svelte` | Bestehende Input-Komponente, unverändert. |
| `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` | **Skeleton-Datei.** Neu implementieren: Rules iterieren, Metric-Label aus lokaler Map, Severity-Pill-Styles. |
| **NEU:** `frontend/src/lib/components/trip-detail/AlertRow.svelte` | Neue Zeile pro Rule (Issue nennt sie explizit). |
| **NEU:** `frontend/src/lib/types/alertMetrics.ts` (oder `lib/utils/`) | Frontend Metric→Label-Map (heute nicht vorhanden). Quelle: Python `metric_catalog.py`. |

### Backend Go

| Datei | Relevanz |
|------|-----------|
| `internal/model/trip.go:45-100` | AlertRule-Struct, AlertMetric, AlertSeverity, Trip.AlertRules — read-only, schon vollständig. |
| `internal/handler/trip.go:77-199` | API-Handler — akzeptiert `alert_rules` schon im POST/PUT-Body. Keine Änderung nötig. |
| `internal/store/store.go:140-174` | Persistence — `nil → []`-Coercion vorhanden. Keine Änderung nötig. |

### Backend Python

| Datei | Relevanz |
|------|-----------|
| `src/app/models.py:620-663` | AlertRule-Dataclass + Enums. Read-only. |
| `src/app/trip.py:183` | `Trip.alert_rules: List[AlertRule]`. Read-only. |
| `src/app/loader.py:32-83` | Legacy-Migration (Load-Time). Read-only — neue Rules werden 1:1 geparst. |
| `src/app/metric_catalog.py` | MetricCatalog mit `label_de`, `unit`. Quelle für Frontend-Mapping (nur Referenz). |
| `src/services/weather_change_detection.py:24-123` | **Neue Factory `from_alert_rules(rules)`** ergänzen. Bestehende `from_trip_config`, `from_display_config` bleiben (Fallback). |
| `src/services/trip_alert.py:29-100` | **Priorität ändern**: wenn `trip.alert_rules` nicht leer → `from_alert_rules`; sonst bisheriger Fallback. |

### Specs

| Datei | Relevanz |
|------|-----------|
| `docs/specs/modules/epic_136_step4_briefings.md` | Vorhanden. **Erweitern** um Mapping `briefings.thresholds → trip.alert_rules`. |
| `docs/specs/modules/issue_205_alert_rules.md` | Read-only Referenz (Datenmodell + Migration). |
| `docs/specs/modules/trip_alert.md` | **Erweitern** um Factory `from_alert_rules` + Priorität. |
| `docs/specs/modules/epic_135_step5_right_column.md` (oder verwandt) | AlertsPreviewCard-Skeleton-Spec. Hier oder in neuer Spec ergänzen. |

## Existing Patterns

### 1. AlertRule JSON (kanonisch, aus Issue #205)
```json
{
  "id": "r1",
  "kind": "absolute",
  "metric": "wind_gust",
  "threshold": 50.0,
  "unit": "km/h",
  "severity": "critical",
  "enabled": true
}
```

### 2. Heutiger Detector-Bau (`trip_alert.py:88-99`)
```python
if trip.display_config and trip.display_config.get_enabled_metrics():
    detector = WeatherChangeDetectionService.from_display_config(trip.display_config)
elif trip.report_config:
    detector = WeatherChangeDetectionService.from_trip_config(trip.report_config)
else:
    detector = WeatherChangeDetectionService()
```

### 3. ThresholdRow Null-Coercion (Wizard)
- `type="number"`: `oninput → value === '' ? null : Number(value)`
- `type="thunder"`: `onchange → value === '' ? null : (value as ThunderLevel)`

### 4. Metric→Label/Unit (Python-Katalog, nur Backend)
- `wind_gust` → "Böen", km/h
- `precipitation_sum` → "Niederschlag", mm
- `thunder_level` → "Gewitter", "" (MED=1, HIGH=2)
- `snow_line` → "Schneefallgrenze", m

### 5. ID-Generierung
- Frontend: `crypto.randomUUID()` (laut Issue)
- Backend: bestehende Rules behalten ihre ID

## Dependencies

**Upstream (worauf wir aufbauen):**
- Issue #205 — AlertRule-Datenmodell, Migration, Persistence — komplett
- Issue #131 — Alert-Mail-Format
- Epic #135 Step 5 — AlertsPreviewCard-Skeleton

**Downstream (was Tests treffen werden):**
- Bestehende Trip-Tests: müssen weiter grün bleiben (Roundtrip aus Issue #205)
- TripAlertService-Tests: Verhaltens-Parität für Δ-Migration-Rules (AC-6)
- E2E: Wizard → Save → Detail-View

## Risks & Considerations

1. **Verhaltens-Parität (AC-6):** Migrierte Δ-Rules müssen weiterhin korrekt feuern. Risiko: neue Factory ignoriert disabled Rules, oder ändert Severity-Berechnung. → In Spec: `kind=delta` exakt wie heutige `_thresholds`-Logik.

2. **Replacement vs. Fallback (Wizard):** Issue lässt offen, ob neue Rules `report_config` ersetzen oder beides geschrieben wird. → Klärung im Spec. Empfehlung: Beides schreiben für Übergangszeit, `alert_rules` ist Quelle der Wahrheit.

3. **Metric-Label im Frontend:** Keine zentrale Map vorhanden — manuell duplizieren (klein, vier Metrics) statt einen API-Endpoint zu bauen.

4. **Thunder-Mapping:** Wizard speichert "MED"/"HIGH" (Enum-String), AlertRule erwartet `threshold` als Float. Mapping: MED → 1, HIGH → 2. Im Spec dokumentieren.

5. **Severity-Klassifizierung:** Issue sagt "Severity aus Rule überschreibt heutige ratio-basierte Klassifizierung". Neuer Pfad muss in Mail-Renderer durchgereicht werden — kann größerer Touch werden.

6. **LoC-Limit 250:** Drei Subscopes (Frontend Mapping + Card + Backend Factory + Service-Switch) — wird tendenziell knapp. In Phase 2 prüfen, ob in 2 Workflows splittbar.

## Phase 2 — Analyse-Ergebnisse

### Severity-Datenfluss heute

- **Klassifizierung:** `WeatherChangeDetectionService._classify_severity(delta, threshold)` (`weather_change_detection.py:191-214`) — ratio-basiert: <1.5 = MINOR, 1.5-2.0 = MODERATE, ≥2.0 = MAJOR.
- **DTO:** `WeatherChange.severity: ChangeSeverity` (`src/app/models.py:393`) — fließt vom Detector über `TripAlertService._send_alert` (`trip_alert.py:372-429`) ins `format_email()`.
- **Mail-Renderer:** `src/output/renderers/email/html.py:227-237` — nutzt Severity **nicht** für UI-Anzeige, nur für Filter (MINOR wird in `_filter_significant_changes` rausgefiltert).
- **Konsequenz:** Severity-Override aus AlertRule muss **bei `WeatherChange`-Erzeugung** im Detector greifen (nicht im Renderer).

### Test-Patterns

- **Frontend Unit:** `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` (Node-Test) — `assert.equal(trip.activity, …)` auf `toTripPayload()`-Output.
- **Frontend E2E:** Playwright in `frontend/e2e/trip-wizard-step4.spec.ts`, `trip-detail-overview-right.spec.ts` — TestIDs `right-card-alerts*`.
- **Backend Unit:** `tests/unit/test_change_detection.py:382-504` — Trip-Fixture + synthetische `SegmentWeatherData` (old/new), Assertions auf `service._thresholds["wind_chill_min_c"]` etc.
- **Backend Integration:** `tests/integration/test_trip_alert.py:30-72` — `_create_test_trip()`, `_create_change()` Factories; Assertions auf `severity in [MODERATE, MAJOR]`.
- **Mocks:** verboten — alle Tests nutzen synthetische Daten oder echtes Gmail-SMTP/IMAP.

### Architektur-Entscheidungen (Plan-Agent)

**A — Replacement vs. Fallback im Wizard:** Wizard schreibt **BEIDES** — `alert_rules` (neue Source-of-Truth) + `report_config.alert_thresholds` (für Scheduler/Channels bleibt). Backend-Priorität: `alert_rules` > `display_config` > `report_config`.

**B — Severity-Override:** Direkt in `from_alert_rules()` bei `WeatherChange`-Erzeugung (nicht im Versand). Severity ist Eigenschaft der Detection, nicht des Channels.

**C — Splittung:** **ZWEI Workflows, sequenziell**:
- **Workflow 1 (Backend, ~150-200 LoC):** Subscope 3 — `from_alert_rules()` + Service-Priorität.
- **Workflow 2 (Frontend, ~160-220 LoC):** Subscope 1 + 2 — Wizard-Save + AlertsPreviewCard (gemeinsame Metric-Label-Map).

**D — AC-Splittung (siehe unten in den jeweiligen Workflow-Specs).**

### Empfehlung

**Start mit Workflow 1 (Backend).** Datenmodell ist live, Service-Switch ist kritischer Pfad (Mail-Versand). Frontend kann später gegen echtes Backend-Verhalten E2E-testen.

### Verbleibende offene Frage

Reihenfolge des Workflow-Starts: **Backend zuerst** — bestätigt durch Plan-Agent.

## Next

Phase 3 (Spec) für **Workflow 1: Backend Service-Switch (`from_alert_rules` + Priorität)**. Nach Approval & Implementation startet Workflow 2 für Frontend (eigene Spec).
