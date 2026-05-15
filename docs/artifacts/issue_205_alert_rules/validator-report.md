# External Validator Report — Issue #205 Trip.alert_rules Datenmodell + Migration

**Spec:** `docs/specs/modules/issue_205_alert_rules.md`
**Datum:** 2026-05-14
**Server:** https://staging.gregor20.henemm.com (Go API) + Python-Loader (gregor-python-staging, localhost:8001)
**Validator:** external-validator (unabhaengig, ohne src/-Zugriff)

## Test-Setup

- Go API auf `https://staging.gregor20.henemm.com/api/*` — Auth via `validator-issue110` Session-Cookie
- Python Loader-Endpoint `/api/_internal/trip/{tid}/loaded?user_id={user}` (localhost:8001) — testet Python-Migration ohne Code-Zugriff
- Staging-Trip-JSONs: `/home/hem/gregor_zwanzig_staging/data/users/default/trips/` (5 Bestandstrips, davon 3 mit Legacy-Schwellwerten)

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| AC-1 | `AlertRule(...)` mit 7 Feldern, str-Enums | Migration-Output zeigt `{id, kind:"delta", metric:"temperature_change", threshold:5.0, unit:"°C", severity:"warning", enabled:True}` — alle 7 Felder vorhanden (siehe AC-3) | PASS |
| AC-2 | `Trip(...)` ohne alert_rules → leere Liste | Trip `3f48b6fc` (kein Legacy, kein alert_rules-JSON) → Loader liefert `alert_rules: []` (count=0, kein None, kein Crash) | PASS |
| AC-3 | Legacy `alert_on_changes:True` + 3 Thresholds → 3 delta-Rules, enabled=True, UUIDs | Trip `5f534011` (KHW 403): 3 Rules `{temperature_change,wind_change,precipitation_change}` mit `enabled=True`, UUIDs Länge 36, Units `°C`/`km/h`/`mm`, `severity:warning` | PASS |
| AC-4 | Legacy `alert_on_changes:False` → 3 Rules enabled=False, Schwellwerte erhalten | Trip `gr221-mallorca` (alert_on_changes=False): alle 3 Rules `enabled=False`; Legacy `change_threshold_*` unverändert | PASS |
| AC-5 | Existierendes alert_rules-Array → No-Op | Trip `validator-issue205-roundtrip` (POST mit 3 expliziten Rules, davon 1 enabled=False): zwei aufeinanderfolgende Loads liefern identische IDs (`rule-temp-1`/`rule-wind-2`/`rule-precip-3`) + identische enabled-Flags | PASS |
| AC-6 | Trip mit 3 Rules → serialize → load → 3 Rules identisch + Legacy-Felder erhalten | POST `/api/trips` mit 3 alert_rules, GET liefert identisches Resultat. JSON auf Disk (`validator-issue205-roundtrip.json`) byte-identisch zum gesendeten Body | PASS |
| AC-7 | Go-Struct ohne `omitempty` → Empty serialisiert als `"alert_rules":[]` | API-GET `/api/trips` über alle 9 validator-issue110-Trips: alle haben `"alert_rules":[]` (leeres Array, nicht null, nicht fehlend) | PASS |
| AC-8 | TS-Interface exportiert AlertRule, AlertRuleKind, AlertSeverity, AlertMetric; Trip-Interface hat `alert_rules?: AlertRule[]` | Deployed staging frontend `types.ts` Z. 42-77: alle 4 Typen via `export type`/`export interface` exportiert; Trip-Interface Z. 76 hat `alert_rules?: AlertRule[]` optional | PASS |
| AC-9 | 9 Produktiv-Trips load + serialize: alle Felder ausser `alert_rules` byte-identisch zum Original | 5 staging-Trips (default-User): Legacy `report_config.alert_on_changes`/`change_threshold_*` byte-identisch erhalten. `alert_rules` korrekt hinzugefügt. **Caveat**: Loader füllt zusätzlich Default-Felder auf (`updated_at`, `trip_id`, `send_sms`, Metric-Defaults) und normalisiert Time-Format `18:00`→`18:00:00`. Bestandsdaten werden nicht überschrieben. Siehe Finding #1. | PASS-mit-Caveat |

## Findings

### Finding #1 — Loader füllt Default-Felder über AC-9 hinaus auf

- **Severity:** LOW (kein Datenverlust, kein Regress aus Issue #205)
- **Expected (AC-9):** „alle Felder ausser dem neuen `alert_rules` byte-identisch zum Original"
- **Actual:** Beim Load+Serialize fügt der Loader Default-Felder hinzu, die nicht im Original-JSON stehen (z.B. `send_sms=false`, `multi_day_trend_reports=false`, `updated_at`, `trip_id`, Metric-Defaults `aggregations=['min','max']`, `morning_enabled=null`, `evening_enabled=null`, `use_friendly_format=true`, `alert_enabled=false`, `alert_threshold=null`) und normalisiert Zeit-Strings (`evening_time:"18:00"` → `"18:00:00"`). Beobachtet bei `5f534011.json`, `gr221-mallorca.json`, `zillertal-mit-steffi.json`.
- **Evidence:** `evidence-trips-list.txt` (5 staging-Trips, Drift-Diff je Feld)
- **Einordnung:** Loader-Schema-Hardening aus Vor-Issues (Default-Auffüllung älterer JSONs). Für Issue #205 wesentlich:
  - **Keine User-konfigurierten Bestandsdaten überschrieben** — Legacy `alert_on_changes` + `change_threshold_*` exakt erhalten
  - **Metric-Bestandsfelder** (`enabled`/`metric_id`) erhalten, nur neue Sub-Felder mit Defaults gefüllt
  - Spec-Intent „Migration ist additiv" (Z. 322) gehalten — der Default-Fill ist Bestandsverhalten, nicht durch dieses Issue eingeführt

### Finding #2 — Empty-Array-Garantie nur Go-seitig direkt belegbar

- **Severity:** LOW
- **Expected (AC-7):** Go marshalt `[]AlertRule{}` als `"alert_rules":[]`
- **Actual:** Verifiziert für alle 9 validator-issue110-Trips, Go-Side `"alert_rules":[]`. Python-Pendant `_trip_to_dict()` konnte ohne Legacy-Felder isoliert nicht beobachtet werden, weil der Python `/loaded`-Endpoint immer ein vorhandenes Feld liefert. JSON-Persistierung nach POST (`validator-issue205-roundtrip.json`) zeigt aber `alert_rules` als Array (kein null/missing) — Roundtrip-Korrektheit indirekt belegt.
- **Evidence:** `evidence-empty-array.txt`

## Verdict: **VERIFIED**

### Begründung

Alle 9 Acceptance Criteria sind durch direkte Beobachtung am laufenden staging-System bewiesen:

- **Datenmodell** (AC-1, AC-2, AC-8): Drei-Sprachen-Typen (Python-Dataclass, Go-Struct, TS-Interface) korrekt implementiert und im Deploy nachweisbar.
- **Migration** (AC-3, AC-4, AC-5): Python-Loader übersetzt Legacy-Felder von 3 staging-Trips (`5f534011`, `gr221-mallorca`, `zillertal-mit-steffi`) korrekt in delta-Rules; `enabled`-Flag folgt `alert_on_changes`; bei vorhandenem `alert_rules` läuft No-Op-Pfad sauber.
- **Roundtrip + Persistenz** (AC-6, AC-7): Go-API akzeptiert `alert_rules` im POST und serialisiert es 1:1 im GET; JSON auf Disk byte-identisch. Leere AlertRules-Liste als `[]` garantiert.
- **Bestandsdaten** (AC-9): Legacy-Felder aller untersuchten Trips bleiben unverändert; die einzige Drift ist Loader-Default-Auffüllung (Finding #1, LOW), kein Datenverlust und kein Regress.

Spec-Intent „Datenmodell + Migration only, Wizard/UI in Folge-Issue" konsistent mit Known-Limitations Z. 326–339 eingehalten. Keine CRITICAL- oder HIGH-Findings.
