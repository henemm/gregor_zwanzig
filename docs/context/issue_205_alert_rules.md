# Context: Issue #205 — Trip-Datenmodell `alert_rules`-Feld einführen

## Request Summary

Neues Feld `Trip.alert_rules: AlertRule[]` einführen — strukturierte Alert-
Liste pro Trip, gespeist aus Wizard Step 4, gerendert in der Alert-Card
der Trip-Detail-Übersicht (rechte Spalte, Epic #135 Step 5).
Bestehende `report_config.change_threshold_*` Felder müssen verlustfrei
in die neue Struktur migriert werden — bestehende Daten dürfen nicht
verloren gehen (Memory-Regel "Daten-Schema-Reworks", BUG-DATALOSS-GR221).

## Related Files

| File | Relevance |
|------|-----------|
| `internal/model/trip.go` Z. 22-35 | Trip-Struct in Go — `ReportConfig` ist heute `map[string]interface{}`, kein typisiertes Feld. Hier muss `AlertRules []AlertRule` ergänzt werden. |
| `internal/handler/trip.go` Z. 115-195 | UpdateTripHandler macht bereits Read-Modify-Write mit Pointer-DTO → Pattern für `AlertRules`-Merge ist da. |
| `internal/store/store.go` Z. 85-165 | Persistiert Trip als JSON in `data/users/<user>/trips/<id>.json`. |
| `src/app/models.py` Z. 573-620 | `TripReportConfig` Dataclass mit `alert_on_changes`, `change_threshold_temp_c/wind_kmh/precip_mm`. Quelle der Migrations-Defaults. |
| `src/app/loader.py` Z. 106-145 | Python-Loader nutzt `.setdefault()` — Migrations-Pfad für fehlende Felder. |
| `frontend/src/lib/types.ts` Z. 41-54 | Trip-Interface — `report_config: Record<string, unknown>` (auch untypisiert). Hier neue Typen `AlertRule`/`AlertRuleType`/`Severity` ergänzen. |
| `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` | Skeleton-Empty-State, blockiert auf Issue #205. Muss `trip.alert_rules` lesen und `AlertRow`-Komponente pro Eintrag rendern. |
| `frontend/src/lib/components/trip-detail/TripOverview.svelte` Z. 52-57 | Rechte Spalte rendert `<AlertsPreviewCard {trip} />` als 3. von 4 Cards. |
| `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` | Wizard Step 4 (Epic #136) — schreibt aktuell in `wizard.briefings.thresholds` mit Feldern `gust_kmh`, `precip_mm`, `thunder_level`, `snow_line_m`. Save-Pipeline muss diese in `alert_rules` umsetzen. |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | `BriefingConfig.thresholds`-Schema — Input für die Save-Pipeline. |
| `frontend/src/lib/components/wizard/WizardStep4ReportConfig.svelte` | **Legacy-Wizard** mit `change_threshold_temp_c/wind_kmh/precip_mm` — schreibt in `report_config` direkt. Existiert parallel zum neuen Wizard. |
| `docs/specs/modules/epic_135_step5_right_column.md` §4 + §Known Limitations Z. 489-490 | Spec markiert Alert-Card als blockiert auf #205. |
| `docs/specs/modules/trip_alert.md` | Alert-Service liest heute aus `report_config` — muss nach Datenmodell-Wechsel `alert_rules` lesen. |
| `src/services/trip_alert.py` Z. 102, 173 | `trip.report_config.alert_on_changes` und Schwellwerte werden im Alert-Service gelesen. |
| `src/services/weather_change_detection.py` | `from_trip_config()` (3-Slider-Pfad) und `from_display_config()` (per-Metrik) — beide werden aufgerufen. Nach Migration auf `alert_rules` braucht es einen `from_alert_rules()`-Factory. |
| `data/users/default/trips/gr221-mallorca.json` | Echter Trip — Beispiel für aktuelles `report_config`-Persistenz-Layout (siehe unten). |
| `.claude/hooks/data_schema_backup.py` | Auto-Trigger bei Edits auf `internal/model/`, `src/app/models.py`, `src/app/loader.py`, `internal/store/store.go` → tar.gz in `.backups/`. |
| `tests/integration/test_config_persistence.py` | Bestehende Roundtrip-Tests — Pattern für Migrations-Tests. |

## Echtes Trip-JSON-Layout (Stand vor Migration)

```json
{
  "report_config": {
    "alert_on_changes": false,
    "change_threshold_precip_mm": 10,
    "change_threshold_temp_c": 5,
    "change_threshold_wind_kmh": 20,
    "enabled": true,
    "evening_time": "18:00:00",
    "morning_time": "06:00:00",
    "send_email": true,
    "send_telegram": true
  },
  "aggregation": { "profile": "wintersport" },
  "display_config": { "metrics": [...] }
}
```

Es gibt 9 produktive Trips (`data/users/admin/` 2x, `data/users/default/` 7x).

## Existing Patterns

- **Read-Modify-Write im Backend** (`internal/handler/trip.go`): Pointer-DTO,
  null-Felder ignoriert, optionale Configs bleiben erhalten. Verhindert
  Datenverlust analog GR221.
- **`.setdefault()` im Python-Loader** (`src/app/loader.py`): Migrations
  via Default-Werte beim Laden — nicht-destruktiv, fail-soft.
- **Auto-Backup vor Schema-Edits** (`.claude/hooks/data_schema_backup.py`):
  greift auf `internal/model/trip.go` und `src/app/models.py` → Backups
  laufen automatisch.
- **Roundtrip-Tests** (`tests/integration/test_config_persistence.py`):
  Pattern für Load-Save-Load-Assertion auf Felder.
- **Parallele Wizards**: Legacy `WizardStep4ReportConfig` (3 globale Slider)
  + neuer `Step4Briefings` (granulare Felder). Beide schreiben in
  unterschiedliche Container — Migrations-Pfad muss beide kennen.
- **Severity-Klassen** in `WeatherChangeDetectionService._classify_severity`:
  MINOR/MODERATE/MAJOR — vs. Issue-205-Vorschlag info/warning/critical.
  Mapping-Frage offen.

## Dependencies

- **Upstream (Was wir lesen):**
  - `Step4Briefings.thresholds.{gust_kmh, precip_mm, thunder_level, snow_line_m}`
    (neu, Epic #136 Wizard)
  - `TripReportConfig.{alert_on_changes, change_threshold_temp_c/wind_kmh/precip_mm}`
    (legacy, alle bestehenden Trips)
  - `aggregation.activity_profile` (für Default-Rule-Sets pro Aktivität)
- **Downstream (Wer uns liest):**
  - `AlertsPreviewCard.svelte` (Trip-Detail rechte Spalte)
  - `TripAlertService` + `WeatherChangeDetectionService` (Alert-Auslösung)
  - Frontend-Save-Pipeline (`toTripPayload` in Wizard)

## Existing Specs

- `docs/specs/modules/epic_135_step5_right_column.md` — Alert-Card-Skeleton
- `docs/specs/modules/trip_alert.md` v2.0 — Alert-Service (muss aktualisiert werden)
- `docs/specs/modules/weather_change_detection.md` v2.0 — Detector (muss erweitert werden)
- `docs/specs/modules/epic_136_step4_briefings.md` — Wizard Step 4 (neues Schema)
- `docs/specs/modules/issue_131_alert_email_klarheit.md` — direkter Vorgänger,
  hat Detector + Formatter angefasst.

## Risks & Considerations

1. **Datenverlust durch unsichere Migration (BUG-DATALOSS-GR221, Issue #102).**
   Pflicht: Read-Modify-Write, Roundtrip-Test, automatischer Pre-Snapshot
   im `.backups/`-Ordner. Migration darf alte Felder NICHT löschen, sondern
   nur ergänzen (Fallback bleibt erhalten).

2. **Drei Sprachen, ein Schema:** Go-Struct + Python-Dataclass + TS-Interface
   müssen synchron sein. Heute schon Drift bei `report_config` (Go
   `map[string]any`, Python typisiert, TS `Record<string, unknown>`).
   Empfehlung: Go `AlertRules []AlertRule` als typisiertes Feld einführen,
   Python `TripAlertRules` Dataclass, TS `AlertRule` Interface — alle drei
   mit identischen Field-Namen (snake_case in JSON).

3. **Severity-Mapping:** Issue-Text schlägt `info/warning/critical` vor —
   bestehende `ChangeSeverity` ist `MINOR/MODERATE/MAJOR`. Entweder
   Issue-Severity neu definieren (orthogonal zu Detection-Severity) oder
   Mapping festlegen.

4. **Threshold-Semantik unklar:** Aus dem neuen `Step4Briefings`-Wizard
   kommt `gust_kmh: 50` (absoluter Schwellwert = "warne wenn Wind > 50").
   Aus dem alten `change_threshold_wind_kmh: 20` kommt ein Δ-Wert
   (warne wenn ΔWind > 20). **Zwei verschiedene Konzepte — eine
   Datenstruktur muss beide abbilden** (oder die Migration entscheidet
   sich). Klärungsbedarf.

5. **Aktivitäts-Defaults:** Issue #135 Step 5 Spec referenziert
   `aggregation.activity_profile`. Falls Trip ohne `alert_rules` und ohne
   Legacy-`change_threshold_*` existiert, sollte er ein Profile-Default
   bekommen (Wintersport ≠ Wandern). Logik gehört konzentriert in
   eine `default_alert_rules_for(profile)`-Funktion.

6. **Zwei Wizards parallel:** Solange Legacy- und neuer Wizard beide
   existieren, müssen beide auf `alert_rules` schreiben — oder genau
   einer von beiden. Tech-Lead-Vorschlag: neuen Wizard als Single Source
   of Truth, Legacy-Wizard auf Read-Only oder Deprecation-Warnung.

7. **Alert-Service-Umstellung:** `TripAlertService` muss
   neue `from_alert_rules()`-Logik bekommen. Bisherige Pfade
   `from_display_config()` (per-Metrik) und `from_trip_config()`
   (3-Slider) bleiben als Fallback bis Migration aller Trips durch ist.

8. **LoC-Limit 250:** Issue ist groß. Realistisch:
   - Datenmodell (Go + Python + TS): ~80 LoC
   - Migration: ~50 LoC
   - Wizard Step 4 Save-Pipeline: ~40 LoC
   - AlertsPreviewCard + AlertRow Komponente: ~80 LoC
   - Tests: ~100 LoC
   - **Wahrscheinlich Override nötig auf 400-500 LoC** oder Aufspaltung
     in Sub-Issues (Datenmodell-only vs. UI-only).

## Offene Produkt-Fragen für Phase 2

- Severity-Schema: `info/warning/critical` (UI-orientiert) oder
  `MINOR/MODERATE/MAJOR` (Detection-Severity wiederverwenden)?
- Threshold-Semantik: absolut (`> 50 km/h`) oder Delta (`Δ > 20 km/h`)
  oder beides als zwei separate Rule-Types?
- Migration: Legacy `change_threshold_*` löschen oder als Read-Fallback
  behalten?
- Aktivitäts-Defaults für Trips ohne explizite Rules: aktiv generieren
  oder leer lassen?
- Issue jetzt im Scope von #205 komplett ODER Sub-Issue für UI/Wizard?
