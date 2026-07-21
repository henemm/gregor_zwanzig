---
entity_id: issue_817_alerts_tab_delta
type: module
created: 2026-06-14
updated: 2026-06-15
status: approved
version: "1.2"
tags: [alert, delta, alerts-tab, sync-alert-rules, migration, frontend, epic-813, slice-2]
---

# Alert-Rework Slice 2: Alerts-Tab auf Δ-Schwellen (absolut → delta)

## Approval

- [x] Approved (PO, 2026-06-14)

## Purpose

Stellt den Alerts-Tab von absoluten Schwellenwerten auf Abweichungs-Schwellen (Δ) um:
Pro alert-fähiger Wetter-Metrik gilt künftig genau eine Δ-Schwelle ("melde ab Änderung
X gegenüber dem letzten Briefing, in beide Richtungen") statt eines absoluten Festwerts.
Die Slice-1-Auswertung (`detect_changes`, `from_alert_rules`) ist bereits Δ-fähig, nutzt
aber aufgrund von `SyncAlertRules` (Go) stets nur `kind="absolute"`-Regeln — dieser Slice
schaltet die Kette vollständig auf `kind="delta"` um und passt die Frontend-UI-Sprache an.

## Source

- **File:** `internal/model/trip.go` — `SyncAlertRules` (Z. 169-206), neuer `DefaultDeltaThreshold`-Map
- **File:** `internal/store/store.go` — `LoadTrip` (Self-Heal) und `SaveTrip` (compute-on-save) rufen `SyncAlertRules`
- **File:** `frontend/src/lib/components/alerts-tab/AlertCard.svelte` — UI-Sprache auf Δ-Framing
- **File:** `frontend/src/lib/utils/alertMetricLabels.ts` — ggf. Δ-Label-Ergänzung

> **Schicht: Go-Backend + Frontend.**
> Python-Backend (`src/`) bleibt vollständig unberührt — die Δ-Auswertung in
> `weather_change_detection.py` / `from_alert_rules` ist aus Slice 1 (#816) bereits
> korrekt implementiert. Kein Eingriff in `detect_changes`, `trip_alert.py`, `alert_state.py`.

## Estimated Scope

- **LoC:** ~80–120 (netto; Go ~60, Frontend ~40)
- **Files:** 4 (2 Go + 2 Frontend/TS)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/trip.go` — `AlertRuleKindDelta`, `AlertRuleKindAbsolute` | upstream | Bereits definierte Kind-Konstanten; Slice 2 nutzt `AlertRuleKindDelta` |
| `internal/model/trip.go` — `AlertableMetrics`, `DefaultAlertThreshold` | upstream | Menge der alert-fähigen Metriken bleibt unverändert; absoluter Default-Map bleibt für Legacy-Nutzung erhalten, wird aber nicht mehr für neue Regeln verwendet |
| `internal/store/store.go` — `SaveTrip`, `LoadTrip` | upstream | Ruft `SyncAlertRules` bereits auf (compute-on-save + self-heal); Migration läuft automatisch |
| `src/services/weather_change_detection.py` — `from_alert_rules` Z. 213-236 | upstream (Python) | Konsumiert `kind="delta"`-Regeln direkt: `rule.threshold` fließt in `_thresholds[field_name]` ein (Z. 234-235); absoluter `setdefault`-Fallback (Z. 222-223) wird durch echte Δ-Regel überschrieben |
| `src/app/metric_catalog.py` — `default_change_threshold` | upstream (Python) | Kanonische Δ-Default-Werte; `DefaultDeltaThreshold` in Go MUSS diese exakt spiegeln (Cross-Lang-Wertekontrakt analog #802 naismith) |
| `frontend/src/lib/types.ts` — `AlertRuleKind`, `AlertRule` | upstream | `AlertRuleKind='absolute'|'delta'` und `AlertRule.threshold` existieren bereits |
| `frontend/src/lib/utils/alertMetricLabels.ts` | upstream | SSoT für Metric-Labels und Units im Alerts-Tab |

## Implementation Details

### A — Schlüssel-Erkenntnis: Warum absolute Regeln nie alert-wirksam waren

In `from_alert_rules` (Z. 213-223) behandelt der Python-Code `kind="absolute"`-Regeln
wie folgt: `rule.threshold` wird NICHT direkt als Δ-Schwelle übernommen; stattdessen
setzt `setdefault` den MetricCatalog-Default ein, falls noch kein Eintrag existiert.
Nur `kind="delta"`-Regeln (Z. 224-236) überschreiben `thresholds[field_name]`
direkt mit `rule.threshold`. Da `SyncAlertRules` heute ausschließlich
`kind="absolute"`-Regeln erzeugt (und Delta-Regeln aktiv löscht, Z. 177), kommt der
nutzerkonfigurierte Threshold **nie** an der Auswertung an — es wirkt immer der
MetricCatalog-Default. Diese Migration verliert daher nichts Reales; sie macht den
Tab-Wert endlich wirkungsvoll.

### B — Go: neuer `DefaultDeltaThreshold`-Map + SyncAlertRules umstellen

**Neuer Map** `DefaultDeltaThreshold` in `internal/model/trip.go`:

```go
// DefaultDeltaThreshold spiegelt Python metric_catalog.default_change_threshold
// (Cross-Lang-Wertekontrakt — Präzedenz: #802 naismith).
// Einheit entspricht der jeweiligen AlertRule.Unit.
var DefaultDeltaThreshold = map[AlertMetric]struct {
    Threshold float64
    Unit      string
    Severity  AlertSeverity
}{
    AlertMetricWindGust:         {20, "km/h", AlertSeverityWarning},
    AlertMetricPrecipitationSum: {10, "mm",   AlertSeverityWarning},
    AlertMetricTemperatureMin:   {5,  "°C",   AlertSeverityWarning},
    AlertMetricTemperatureMax:   {5,  "°C",   AlertSeverityInfo},
    AlertMetricThunderLevel:     {1,  "",     AlertSeverityWarning},
    AlertMetricSnowLine:         {200, "m",   AlertSeverityInfo},
}
```

Cross-Lang-Mapping (Python `id` → Go `AlertMetric` → Python `summary_field` → Python `default_change_threshold`):
- `gust` (`gust_max_kmh`) → `AlertMetricWindGust` → **20 km/h**
- `precipitation` (`precip_sum_mm`) → `AlertMetricPrecipitationSum` → **10 mm**
- `temperature` (`temp_min_c` + `temp_max_c`) → `AlertMetricTemperatureMin/Max` → **5 °C**
- `thunder` (`thunder_level_max`) → `AlertMetricThunderLevel` → **1**
- `freezing_level` (`freezing_level_m`) → `AlertMetricSnowLine` → **200 m**

**Hinweis `snow_line`/`freezing_level`:** Go's `AlertMetricSnowLine` ist via
`_ALERT_METRIC_TO_SUMMARY_FIELD` auf `freezing_level_m` gemappt. Python-Katalog-Metrik
`freezing_level` hat `default_change_threshold=200`. Die Python-Metrik `snowfall_limit`
hat KEIN `default_change_threshold` und ist NICHT in `_ALERT_METRIC_TO_SUMMARY_FIELD`
eingetragen. Der Δ-Default 200 m für `AlertMetricSnowLine` ist daher korrekt und deckt
die Nullgradgrenze (nicht die Schneefallgrenze) ab.

**`SyncAlertRules` umstellen** (Z. 169-206):
- Invariante neu: genau eine `kind="delta"`-Regel pro aktiver alert-fähiger Metrik.
- Indexing: `existingByMetric` indiziert vorhandene Regeln UNABHÄNGIG vom Kind
  (sowohl bestehende Delta- als auch Absolut-Regeln werden gelesen).
- Migration: bestehende `kind="absolute"`-Regel einer Metrik → übernehmen als
  `kind="delta"` mit `Threshold = DefaultDeltaThreshold[m].Threshold`
  (der absolute Threshold war nie alert-wirksam, daher kein Verlust; enabled/severity/
  channels/pair_id werden aus der bestehenden Regel übertragen — read-modify-write,
  kein Replace).
- Bestehende `kind="delta"`-Regeln einer Metrik → 1:1 erhalten, inkl. eventuell
  nutzerkonfigurierter `Threshold` (KEIN Reset auf Default — Idempotenz-Invariante).
- Neue Metriken (kein Eintrag): `kind="delta"` mit `DefaultDeltaThreshold[m]`.
- Metriken die nicht mehr aktiv sind: Regel entfernen (wie bisher).

```
Pseudo-Code SyncAlertRules neu:
  existingByMetric = {}
  for r in existing:
      if r.Metric not in existingByMetric:  // erste Regel gewinnt, egal welches kind
          existingByMetric[r.Metric] = r

  result = []
  for id in activeMetricIDs:
      m = AlertMetric(id)
      if not alertable: skip
      if ex in existingByMetric:
          // Migration: force kind=delta, preserve threshold wenn schon delta, sonst Default
          rule = ex
          rule.Kind = AlertRuleKindDelta
          if ex.Kind == AlertRuleKindAbsolute:
              rule.Threshold = DefaultDeltaThreshold[m].Threshold
              rule.Unit      = DefaultDeltaThreshold[m].Unit
          result.append(rule)
      else:
          def = DefaultDeltaThreshold[m]
          result.append(AlertRule{Kind: AlertRuleKindDelta, Metric: m, Threshold: def.Threshold, ...})
  return result
```

**`DefaultAlertThreshold`** (absoluter Map, Z. 118-129) bleibt erhalten (Legacy,
wird von `SyncAlertRules` nicht mehr genutzt, aber kein toter Code entfernen in diesem Slice).

### C — Go: Store-Layer (keine Änderung nötig)

`store.SaveTrip` und `store.LoadTrip` rufen `SyncAlertRules` bereits auf (compute-on-save
und in-memory self-heal aus #809). Da `SyncAlertRules` jetzt idempotent Δ-Regeln
erzeugt, läuft die Migration aller Bestands-Trips automatisch beim nächsten Load/Save —
kein zusätzlicher Migrations-Schritt im Store-Layer erforderlich.

### D — Frontend: AlertCard.svelte — Δ-Sprache

**Aktuell (absolut):**
```
Schwelle:   wind_gust · 50 km/h
```

**Neu (delta):**
```
Melde ab Änderung:   Δ ≥ 20 km/h
```

Konkrete Änderungen in `AlertCard.svelte`:
- Label `"Schwelle:"` → `"Melde ab Änderung:"` (bzw. kompaktere Variante `"Δ ≥"` für
  Mono-Zeile; endgültige Formulierung in Implementierung, muss PO-verständlich sein).
- Mono-Bedingungsblock: `${metric} · ${threshold} ${unit}` → `Δ ≥ ${threshold} ${unit}`.
- Eingabefeld editiert weiterhin `rule.threshold` (bei `kind="delta"` fließt dieser
  Wert direkt via `from_alert_rules` Z. 234-235 in die Δ-Auswertung).
- `rule.kind` wird nicht im UI angezeigt (kein Toggle-UI — nach Slice 2 gibt es nur noch
  Delta-Regeln; Absolut-Regeln sind ein Relikt der Vergangenheit).
- Einheiten (km/h, °C, mm, m) bleiben unverändert.
- `alert-preview-no-metrics`-Empty-State (#809) bleibt unberührt.

### E — Delta-only-Metriken (dokumentiert, KEIN Scope)

`AlertMetricTemperatureChange`, `AlertMetricWindChange`, `AlertMetricPrecipitationChange`
(in `_ALERT_DELTA_METRIC_TO_FIELDS` gemappt) werden durch die direkt Δ-basierte
Basismetrik-Auswertung konzeptionell überflüssig. Sie werden in diesem Slice NICHT
entfernt — kein Scope, Folge-Issue anlegen.

## Expected Behavior

- **Input (Go):** `SyncAlertRules(existing []AlertRule, activeMetricIDs []string)` — wie bisher.
- **Output (Go):** Immer eine Liste von ausschließlich `kind="delta"`-Regeln, eine pro
  aktiver alertbarer Metrik, mit korrekten Δ-Defaults oder erhaltenen Nutzer-Thresholds.
- **Input (Python):** `from_alert_rules(rules)` mit `kind="delta"`-Regeln — der bisherige
  `setdefault`-Fallback für absolute Regeln greift nicht mehr; `thresholds[field_name]`
  wird auf `rule.threshold` gesetzt (Z. 234-235).
- **Output (Python):** `WeatherChangeDetectionService` mit nutzerkonfigurierter Δ-Schwelle
  statt immer dem MetricCatalog-Default.
- **Side effects:** Jeder Trip-Load/Save migriert `alert_rules` in-memory / on-disk von
  `kind="absolute"` zu `kind="delta"`. Alle anderen Trip-Felder (`stages`, `display_config`,
  `channels`, `report_config` etc.) bleiben unverändert (read-modify-write im Store).

## Acceptance Criteria

- **AC-1:** Given eine aktive alert-fähige Metrik (z.B. `wind_gust`) und kein existierender
  Alert-Rule-Eintrag für diese Metrik / When `SyncAlertRules` mit dieser Metrik in
  `activeMetricIDs` aufgerufen wird / Then enthält das Ergebnis genau eine Regel mit
  `kind="delta"` und `threshold == DefaultDeltaThreshold["wind_gust"].Threshold` (20 km/h).
  - Test: Go-Unittest, `SyncAlertRules(nil, []string{"wind_gust"})` → `len(result)==1`,
    `result[0].Kind=="delta"`, `result[0].Threshold==20.0`. Echte Funktion, kein Mock.

- **AC-2:** Given ein Bestands-Trip mit einer `kind="absolute"`-Regel für `wind_gust`
  (Threshold=50) / When `SyncAlertRules` (via `LoadTrip` oder `SaveTrip`) aufgerufen wird /
  Then wird die Regel zu `kind="delta"` migriert mit `threshold == DefaultDeltaThreshold["wind_gust"].Threshold`
  (20 km/h); `enabled`, `severity`, `channels` und `pair_id` aus der Ursprungsregel
  bleiben erhalten.
  - Test: Go-Unittest mit bestehender `AlertRule{Kind: "absolute", Metric: "wind_gust",
    Threshold: 50, Enabled: true, Severity: "warning"}` als Input → Result: `kind="delta"`,
    `Threshold==20`, `Enabled==true`, `Severity=="warning"`. Echter Aufruf, kein Mock.

- **AC-3:** Given ein Trip mit einer bereits korrekt migrierten `kind="delta"`-Regel
  (nutzerkonfigurierter Threshold 35 km/h für `wind_gust`) / When `SyncAlertRules`
  erneut aufgerufen wird (Idempotenz) / Then bleibt `threshold == 35` (kein Reset auf
  Default 20); die Regel wird nicht doppelt erzeugt.
  - Test: Go-Unittest mit `AlertRule{Kind: "delta", Metric: "wind_gust", Threshold: 35}`
    als Input → Result: genau eine Regel, `Threshold==35`. Echter Aufruf, kein Mock.

- **AC-4:** Given `DefaultDeltaThreshold` in `internal/model/trip.go` und
  `default_change_threshold` in `src/app/metric_catalog.py` / When beide Maps für alle
  gemeinsamen Metriken verglichen werden / Then stimmen die Werte exakt überein
  (gust 20 km/h, precipitation 10 mm, temperature_min/max 5 °C, thunder_level 1,
  freezing_level/snow_line 200 m).
  - Test: Python-Pytest liest Go-Quelldatei (`internal/model/trip.go`) nach dem
    `DefaultDeltaThreshold`-Block und vergleicht die Werte mit
    `metric_catalog.get_change_detection_map()` für die betroffenen Summary-Fields.
    Markierung `# doc-compliance-test` (erlaubte Ausnahme laut CLAUDE.md: Workflow-Datei
    als Artefakt prüfen — hier: Cross-Lang-Vertragscheck über Go-Quelldatei als Referenz).

- **AC-5:** Given ein Trip dessen `SyncAlertRules` migrierte Δ-Regeln erzeugt hat
  (nach LoadTrip) / When der Nutzer im Alerts-Tab die Δ-Schwelle für `wind_gust` auf 30
  ändert und speichert / Then liefert der nächste Alert-Lauf (`check_and_send_alerts`)
  eine Change-Erkennung mit Threshold 30 km/h statt dem MetricCatalog-Default 20 km/h
  (End-to-End-Wirkung des Tab-Werts via `from_alert_rules` Z. 234-235).
  - Test: Echter Python-Unittest: `from_alert_rules([AlertRule(kind="delta", metric=
    "wind_gust", threshold=30, enabled=True)])` → `service._thresholds["gust_max_kmh"] == 30`.
    Kein Mock.

- **AC-6:** Given der Alerts-Tab eines Trips mit migrierten Δ-Regeln / When die
  AlertCard für `wind_gust` in der UI angezeigt wird / Then erscheint das Label
  "Melde ab Änderung:" (oder "Δ ≥") statt "Schwelle:", der Mono-Wert zeigt
  "Δ ≥ 20 km/h" (nicht "wind_gust · 50 km/h"), die Einheit "km/h" ist korrekt,
  und kein absolutes "Schwelle:"-Framing ist sichtbar.
  - Test: Playwright E2E auf Staging (Alerts-Tab, eingeloggter Nutzer) — AlertCard
    enthält Text "Melde ab Änderung" oder "Δ ≥" und enthält NICHT "Schwelle:".
    Echter Browser-Test via staging-validator Agent.

- **AC-7:** Given zwei Nutzer (`user_a`, `user_b`) mit je einem Trip und je eigenen
  Alert-Rules / When `SyncAlertRules` für `user_a`-Trip ausgeführt und gespeichert wird /
  Then sind `user_b`-Trips und deren `alert_rules` vollständig isoliert und unverändert.
  - Test: Go-Integrationstest mit zwei separaten Store-Instanzen in `t.TempDir()`,
    je ein Trip pro User; SaveTrip user_a → LoadTrip user_b → user_b-Regeln identisch
    zum ursprünglichen Zustand. Kein Mock, echte TempDir-Stores.

- **AC-8:** Given ein Bestands-Trip mit mehreren alert_rules (`wind_gust`, `precipitation_sum`)
  und weiteren Trip-Feldern (`stages`, `display_config.channels`, `report_config`) / When
  `LoadTrip` (self-heal) die Migration von `kind="absolute"` zu `kind="delta"` durchführt /
  Then sind alle anderen Trip-Felder nach dem Load unverändert (Datenerhalt-Roundtrip).
  - Test: Go-Integrationstest: Trip-JSON mit absoluten Regeln + befüllten `stages` /
    `display_config` / `report_config` serialisieren → `store.LoadTrip` → alle
    Nicht-AlertRule-Felder byte-identisch zum Original, `alert_rules[*].kind == "delta"`.
    Kein Mock, echter TempDir-Store.

## Known Limitations

- Delta-only-Metriken (`temperature_change`, `wind_change`, `precipitation_change` als
  `AlertMetric`) werden durch die direkten Δ-Basismetriken konzeptionell überflüssig,
  aber in diesem Slice NICHT entfernt (Folge-Issue anlegen).
- Nutzer sehen nach Migration den Default-Δ-Wert (z.B. 20 km/h für Böen), nicht ihren
  vorherigen absoluten Wert (z.B. 50 km/h). Der vorherige absolute Wert war nie
  alert-wirksam — kein funktionaler Verlust, aber UI-seitig eine sichtbare Änderung.
- `briefing_mail_validator.py` und `renderer_mail_gate.py` sind NICHT betroffen
  (kein Mail-Renderer-Eingriff in diesem Slice).
- E-Mail-Gate `briefing_mail_validator.py` ist für den Alerts-Tab nicht zuständig —
  kein validator-Pflichtlauf für diesen Slice (betrifft nur Renderer-Dateien laut
  `renderer_mail_gate.py`-Scope).
- **Offene Implementierungs-Entscheidung (`snow_line` / `freezing_level`):** Der
  Python-Katalog-Eintrag `snowfall_limit` hat kein `default_change_threshold` und ist
  NICHT in `_ALERT_METRIC_TO_SUMMARY_FIELD` eingetragen. `AlertMetricSnowLine` mappt
  auf `freezing_level_m` (Nullgradgrenze, Python-Metrik `freezing_level`,
  `default_change_threshold=200`). Der Go-Default 200 m ist daher korrekt gesetzt.
  Falls zukünftig `snowfall_limit` als eigene Alert-Metrik gewünscht wird, benötigt
  sie einen separaten `AlertMetric`-Eintrag in Go und einen `default_change_threshold`-
  Eintrag im Python-Katalog — das ist Scope eines Folge-Issues.

## Test References

<!-- spec_enforcement entity lookup — maps test function names to this spec -->
- `817_ac4_cross_lang_contract_go_block_exists` — AC-4 (Teil 1: Map existiert + 6 Einträge)
- `817_ac4_cross_lang_contract_values` — AC-4 (Teil 2: Werte stimmen mit Python-Katalog überein)
- `817_ac5_delta_rule_threshold_flows_through` — AC-5 (Delta-Threshold fließt direkt durch)
- `817_ac5_contrast_absolute_rule_ignores_threshold` — AC-5 Kontrast (Absolut-Threshold ignoriert)

## Changelog

- 2026-06-14: v1.0 Initial spec created (Issue #817, Epic #813 Slice 2)
- 2026-06-14: v1.1 AC-4 auf Go-subprocess-Aufruf umgestellt (#765-Konformität); Test-Referenzen ergänzt
- 2026-06-14: v1.2 Scope-Korrektur nach Adversary-Finding F001 (KRITISCH). Annahme „Slice 1
  wertet Δ-Regeln für alle Metriken aus" war falsch: `from_alert_rules`
  (`src/services/weather_change_detection.py`) routet `kind="delta"` über
  `_ALERT_DELTA_METRIC_TO_FIELDS`, das NUR die 3 Legacy-`*_change`-Metriken kennt. Δ-Regeln
  für Basis-Metriken (wind_gust, temperature_min/max, precipitation_sum, thunder_level,
  snow_line) wurden verworfen (`_thresholds == {}`) → nach Migration hätten Alerts GAR NICHT
  mehr gefeuert (Regression). Minimal-Fix (zwingend in diesem Slice): DELTA-Zweig fällt auf
  `_ALERT_METRIC_TO_SUMMARY_FIELD` zurück (alle 6 Basis-Metriken). AC-5 testet jetzt echt mit
  `wind_gust`. Zusätzlich F003 (mittel): `SyncAlertRules` bevorzugt bei gemischten
  absolut+delta-Regeln pro Metrik die delta-Regel (Custom-Δ-Wert bleibt erhalten).
