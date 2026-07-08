---
entity_id: fix_991_trip_roundtrip_fields
type: module
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
tags: [bug, data-loss, python, persistence, read-modify-write, roundtrip]
---

# Fix: Trip-Roundtrip erhält unmodellierte Top-Level-Felder (#991)

## Approval

- [ ] Approved

## Purpose

Der reine Modell-Roundtrip `_trip_to_dict(load_trip(...))` verliert unmodellierte
Top-Level-Felder (`accuracy_pct`, `headline`, `briefings_count`, `alerts_count`).
Root-Cause-Fix: das Trip-Modell erhält generisch alle unbekannten Top-Level-Keys,
statt pro Go-Feld ein weiteres Einzelattribut anzubauen. Beendet die wiederkehrende
Datenverlust-Klasse #805/#995/#1087.

## Source

- **File:** `src/app/trip.py` (`class Trip`)
- **File:** `src/app/loader.py` (`_parse_trip`, `_trip_to_dict`)
- **Identifier:** `Trip.extra`, `_parse_trip`, `_trip_to_dict`

Schicht: **Python-Core** (`src/app/`).

## Estimated Scope

- **LoC:** ~25
- **Files:** 2 (`src/app/trip.py`, `src/app/loader.py`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `save_trip` / `_deep_merge_preserve_unknown` (`loader.py`) | persistence | #805-Merge bleibt, wird durch generische Erhaltung ergänzt (kein Konflikt) |
| `tests/tdd/test_alert_rules_model.py::test_ac9` | test | Roundtrip-Vertrag (rot vor Fix) |

## Implementation Details

### 1. `Trip`-Dataclass: generisches `extra`
```python
extra: Dict[str, Any] = field(default_factory=dict)  # #991: unmodellierte Top-Level-Keys, roundtrip-erhalten
```

### 2. `_parse_trip`: unbekannte Top-Level-Keys auffangen
Nach dem Parsen aller bekannten Felder:
```python
KNOWN_TOP_LEVEL = {
    "id","name","stages","avalanche_regions","aggregation","shortcode","activity",
    "region","archived_at","paused_at","official_alerts_enabled","weather_config",
    "display_config","report_config","alert_rules","alert_cooldown_minutes",
    "alert_quiet_from","alert_quiet_to","trip",
}
extra = {k: v for k, v in data.items() if k not in KNOWN_TOP_LEVEL}
# ... Trip(..., extra=extra)
```

### 3. `_trip_to_dict`: `extra` re-emittieren (modellierte Keys gewinnen)
Vor `return data`:
```python
for k, v in trip.extra.items():
    data.setdefault(k, v)   # nur Lücken füllen — nie ein modelliertes Feld überschreiben
```

## Expected Behavior

- **Input:** Trip-JSON mit unmodellierten Top-Level-Keys (z.B. `accuracy_pct`, `headline`).
- **Output:** `_trip_to_dict(load_trip(json))` enthält diese Keys unverändert.
- **Invariante:** Modellierte Felder haben Vorrang; `extra` überschreibt nie ein
  vom Modell gesetztes Feld. Nested-Strukturen bleiben außen vor (nur Top-Level).
- **Side effects:** keine.

## Acceptance Criteria

- **AC-1:** Given eine Prod-Trip-JSON mit `accuracy_pct`/`headline`/`briefings_count`/`alerts_count` /
  When `_trip_to_dict(load_trip(json))` ausgeführt wird /
  Then enthält das Ergebnis alle vier Keys mit **unverändertem** Wert.
  - Test: Roundtrip einer echten Prod-JSON, Vergleich der vier Werte vor/nach.

- **AC-2:** Given der bestehende Vertragstest über alle `data/users/*/trips/*.json` /
  When `test_ac9_all_production_trips_load_with_additive_migration` läuft /
  Then ist er **grün** (kein Top-Level-Key-Verlust außer den tolerierten).
  - Test: `uv run pytest tests/tdd/test_alert_rules_model.py::test_ac9...` grün (rot vor Fix).

- **AC-3:** Given ein Trip-JSON mit einem **synthetischen, nie modellierten** Key (z.B. `future_field_xyz`) /
  When Roundtrip ausgeführt wird /
  Then überlebt auch dieser Key — die Erhaltung ist generisch, nicht auf die vier Felder beschränkt.
  - Test: Roundtrip mit künstlichem Unbekannt-Key, Key + Wert bleiben erhalten.

- **AC-4:** Given ein Trip-JSON, in dem ein **modelliertes** Feld gesetzt ist (z.B. `region="GR20"`) /
  When Roundtrip ausgeführt wird /
  Then stammt der Wert aus dem Modell (nicht aus `extra`), und es entsteht **kein** doppelter/kollidierender Eintrag — modellierte Felder haben Vorrang.
  - Test: Roundtrip eines Trips mit gesetztem `region`; genau ein `region`-Eintrag mit korrektem Wert.

- **AC-5:** Given ein Trip mit Stage-`start_time` /
  When Roundtrip `_trip_to_dict(load_trip(...))` ausgeführt wird /
  Then emittiert Python das systemweit kanonische `"HH:MM"` (Go `naismith.go:24 defaultStartTime="08:00"`, Frontend `DEFAULT_START_TIME`), nicht `.isoformat()` mit Sekunden. `"08:00"` bleibt `"08:00"`.
  - Test: Roundtrip mit `start_time="08:00"` → exakt `"08:00"`.
  - **Wichtig (Adversary-Befund):** Da persistierte Trips gemischt `"HH:MM"`/`"HH:MM:SS"` sind (Go reicht `start_time` als opaquen String durch), macht die Serialisierungsänderung ALLEIN `test_ac9` NICHT grün — die auf Platte als `"HH:MM:SS"` liegenden Dateien driften dann andersherum. Deshalb zwingend zusammen mit AC-6.

- **AC-6:** Given persistierte Trip-JSONs mit gemischtem `start_time`-Format auf Platte /
  When die einmalige Migration `scripts/migrate_start_time_canonical.py` läuft /
  Then sind ALLE `start_time`-Werte in `data/users/*/trips/*.json` auf `"HH:MM"` normalisiert, **ausschließlich** die start_time-Strings geändert (kein anderes Feld/Byte), die Migration ist **idempotent** (zweiter Lauf = keine Änderung) und legt vorher ein **Backup** an. Danach ist `test_ac9` auf dem vollen Datensatz grün.
  - Test: Fixture-Trip mit `start_time="14:00:00"` + Zusatzfelder → Migration → `start_time=="14:00"`, alle anderen Felder byte-identisch; zweiter Lauf idempotent; `test_ac9` grün nach Migration.

## Was NICHT Teil dieses Workflows ist

- **Nested-Feldverlust** (innerhalb `display_config`/`report_config`/`aggregation` etc.) —
  der Test toleriert diese bewusst (`drift_tolerant_keys`). Nur Top-Level + der oben
  behandelte `start_time`-Format-Drift sind Scope.
- Der `save_trip`-File-Merge (#805) bleibt unverändert; die generische Modell-Erhaltung
  ergänzt ihn (Roundtrip verliert nichts mehr, unabhängig vom Zielpfad).
- **Staging-Testdaten-Verschmutzung** (`data/users/tdd-692-*` u.a. pytest-Residuen) —
  separates Aufräum-Thema, eigenes Issue.

## Test-Plan

Echte Roundtrip-Tests gegen Prod-JSONs (keine Mocks), plus synthetischer Unbekannt-Key.
Bug-Reproduktion: test_ac9 rot → grün.
