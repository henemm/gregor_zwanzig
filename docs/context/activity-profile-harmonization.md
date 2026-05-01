---
workflow: activity-profile-harmonization
issue: https://github.com/henemm/gregor_zwanzig/issues/98
created: 2026-05-01
phase: 1-context
---

# Context: ActivityProfile-Harmonisierung

## Request Summary

Issue #98: Es existieren zwei separate Enums mit gleicher Bedeutung aber unterschiedlichen Werten — `ActivityProfile` (Trips) und `LocationActivityProfile` (Locations/Compare). Konsolidierung zu einem gemeinsamen Typ, damit zukünftige Sportarten (Klettern, MTB, Bergsteigen) nur an einer Stelle ergänzt werden müssen.

## Ist-Zustand

### Python — zwei Enums

| Enum | Datei | Werte |
|------|-------|-------|
| `ActivityProfile` | `src/app/trip.py:29-33` | `WINTERSPORT="wintersport"`, `SUMMER_TREKKING="summer_trekking"`, `CUSTOM="custom"` |
| `LocationActivityProfile` | `src/app/user.py:20-24` | `WINTERSPORT="wintersport"`, `WANDERN="wandern"`, `ALLGEMEIN="allgemein"` |

**Werte-Überlapp:** Nur `WINTERSPORT` ist in beiden gleich. `SUMMER_TREKKING` (trip) ≠ `WANDERN` (location), `CUSTOM` ≠ `ALLGEMEIN`.

### Go — String-Validation

| Stelle | Datei | Wert |
|--------|-------|------|
| `Location.ActivityProfile *string` | `internal/model/location.go:11` | optionaler String |
| `CompareSubscription.ActivityProfile *string` | `internal/model/subscription.go:19` | optionaler String |
| Validation | `internal/handler/subscription.go:82-86` | nur `wintersport` / `wandern` / `allgemein` erlaubt |

Go kennt keine Trip-Profile (Trips werden Python-seitig verwaltet).

## Verwendung

### Code (Python)

| Datei | Zeile | Zweck |
|-------|-------|-------|
| `src/app/trip.py:129,146-160` | AggregationConfig.profile + `for_profile()` Branching für Wintersport/SummerTrekking |
| `src/app/loader.py:110` | `ActivityProfile(agg_data["profile"])` beim Laden eines Trips |
| `src/app/loader.py:430,675-683` | `LocationActivityProfile(...)` für Locations & Compare-Subs |
| `src/app/user.py:64,139` | `SavedLocation.activity_profile`, `CompareSubscription.activity_profile` |
| `src/web/pages/compare.py:61-67` | Score-Dispatch (wintersport / wandern / allgemein) |
| `src/web/pages/gpx_upload.py:163` | `AggregationConfig.for_profile(ActivityProfile.SUMMER_TREKKING)` |
| `api/routers/compare.py:49` | API-Parsing String → `LocationActivityProfile` |

### Tests (umfangreich)

- `tests/tdd/test_generic_locations.py` — 15+ Verwendungen `LocationActivityProfile.*`
- `tests/tdd/test_sport_aware_scoring.py` — 13+ Verwendungen
- `tests/tdd/test_weather_templates.py` — 3 Verwendungen
- `tests/integration/test_config_persistence.py` — 2 Verwendungen
- `tests/test_loader.py`, `tests/test_trip.py` — Trip-Profile

## Persistenz (kritisch — siehe CLAUDE.md "Daten-Schema-Reworks")

### Aktuell gespeicherte Werte

```
data/users/default/trips/gr221-mallorca.json     → "profile": "wintersport"
data/users/default/trips/zillertal-mit-steffi.json → "profile": "wintersport"
data/users/default/locations/*.json              → kein activity_profile gesetzt
```

In Produktion sind aktuell nur `wintersport`-Werte persistiert. Migrations-Risiko für Trips ist gering, aber:

- **Theoretisch möglich:** Alte Trip-JSONs mit `"profile": "summer_trekking"` oder `"custom"` (Code unterstützt es)
- **Locations:** Default-Wert `"allgemein"` (LocationActivityProfile.ALLGEMEIN) — beim Laden gesetzt, falls Feld fehlt

## Existierende Specs

| Spec | Bezug |
|------|-------|
| `docs/specs/modules/wintersport_profile_consolidation.md` | Listet das Issue als Out-of-Scope §13. Pipeline nutzt seit β1 ein `Profile`-Literal, das künftig erweitert werden soll. |
| `docs/specs/modules/sport_aware_comparison.md` | Score-Dispatcher in `compare.py` |
| `docs/specs/modules/generic_locations.md:53-59` | Begründet die Trennung historisch ("vermeidet Verwechslung") — diese Begründung trägt nicht mehr |

## Existierende Patterns

- **str-Mixin Enum:** beide nutzen `(str, Enum)` für direkte JSON-Serialisierung
- **Loader mit Default-Fallback:** `_parse_activity_profile()` in `loader.py:675` returns None bei unbekanntem Wert
- **Migration-Pattern:** Bisher noch keine echte Enum-Migration im Repo. CLAUDE.md verweist auf BUG-DATALOSS-GR221 (#102) — Schema-Backup-Hook (`data_schema_backup.py`) greift automatisch bei Edit von `models.py`/`trip.py`/`loader.py`.

## Dependencies

- **Upstream:** keine — beide Enums sind Blattknoten
- **Downstream:**
  - Persistenz-Loader (Python + Go)
  - AggregationConfig (Trip-spezifische Default-Aggregationsregeln)
  - Score-Dispatcher (compare.py)
  - Web-UI Forms / API-Endpoints
  - Token-Builder (β1 Pipeline, Profile-Flag)

## Risks & Considerations

### R1 — Persistenz-Migration
Trip-Werte `summer_trekking`/`custom` müssen entweder erhalten bleiben oder explizit migriert werden (auf `wandern`/`allgemein`?). Zentrale Frage: Soll die Konsolidierung **alle bisherigen Werte als Aliase** behalten oder **kanonisieren**?

### R2 — Semantischer Unterschied "Trip vs Location"
- Trip-Profile dient zur **Aggregations-Logik** (wie über mehrere Wegpunkte/Stunden zusammenfassen)
- Location-Profile dient zur **Score-Logik** (was ist gutes Wetter für diese Sportart)

Ein gemeinsamer Typ ist semantisch sauber, aber die Sub-Logik bleibt getrennt (AggregationConfig vs. Scorer). Risiko: Konsolidierung könnte fälschlich zu "ein Profil → ein Verhalten" verleiten.

### R3 — Go-Validation
Go kennt nur die 3 Location-Werte. Wenn das Enum auf 4+ Werte wächst, muss die Go-seitige Whitelist (`subscription.go:82`) mitwachsen — sonst kommen valide Subscriptions nicht mehr durch.

### R4 — Test-Volumen
40+ Test-Verwendungen → Refactoring-Aufwand ist real. Plan sollte stufenweise migrieren statt Big-Bang.

### R5 — Naming-Konflikt
Das gemeinsame Enum heißt "ActivityProfile" — es gibt aber bereits `ActivityProfile` in `trip.py`. Das alte Enum muss umbenannt oder das neue in einem separaten Modul liegen (`src/app/profile.py`?).

## Phase-2-Strategie (Plan-Agent, 2026-05-01)

### Ein Enum, vier Werte
Neues `src/app/profile.py` mit `ActivityProfile`:
- `WINTERSPORT` — bestehend
- `WANDERN` — Tieflagen-Wandern (Scoring-Semantik aus Location)
- `SUMMER_TREKKING` — Alpine Mehrtagestour (Aggregations-Semantik aus Trip)
- `ALLGEMEIN` — generischer Default

Bewusst **nicht 3, sondern 4** Werte: `WANDERN` und `SUMMER_TREKKING` haben unterschiedliche Wetter-Bewertung (Tiefland-Hike vs. Alpentour mit Höhen-Bändern und Restschnee). `CUSTOM` entfällt (war in `for_profile()` Branching identisch zum Default).

### Migration: Hard-Rename + One-Shot-Verifikations-Skript
Real persistierte Werte enthalten ausschließlich `"wintersport"` (in 2 Trip-JSONs). Locations haben kein `activity_profile`-Feld gespeichert. Daher: Kein Alias-Layer nötig, Migration ist semantisch ein No-Op. Verifikations-Skript scannt rekursiv `data/users/`, prüft jede Persistenz-Datei, raised bei unbekanntem Wert. Schema-Backup-Hook greift automatisch beim Edit von `loader.py`/`trip.py`.

### Phasing: Zwei PRs
- **PR 1:** Neues `profile.py`, beide alten Klassen werden zu Re-Export-Aliasen → keine Test-Änderungen, alle 40+ Tests grün
- **PR 2:** Aliase entfernen, Test-Imports umstellen (mechanisch)

### Go-Whitelist: Manuell mit Comment-Pin
Go hat 3 Zeilen Validation in `subscription.go:82`. Code-Generation lohnt sich nicht (Aufwand 10:1). Stattdessen: Sync-Comment + Checklisten-Eintrag in der Spec.

### Misuse-Mitigation
Das gemeinsame Enum fließt in zwei unabhängige Dispatch-Tabellen (`AggregationConfig.for_profile` für Trips, `calculate_score` für Compare). Dispatch-Funktionen behalten ihre eigenen Namen, kein gemeinsamer Wrapper. Docstring in `profile.py` macht explizit, dass das Enum ein semantisches Label ist und die Logik-Tabellen unabhängig sind.

### Scope
- **13 Dateien** total (7 Production + 6 Tests) — überschreitet die 5er-Schwelle (acknowledged, da meiste Änderungen reine Import-Pfade sind)
- **~50 LoC** netto in Production, ~90 mechanische Substitutionen in Tests
- **Migration-Skript:** +40 LoC in `scripts/`

### Top-3-Risiken
1. Unbekannte Trip-JSON in einem User-Verzeichnis mit Legacy-Wert → Migration-Skript scannt rekursiv, raised statt silent-continue
2. Go-Whitelist driftet nach späterer Klettern/MTB-Erweiterung → Sync-Comment + Spec-Checkliste
3. Versehentliches Entfernen des Alias in PR 1 → Review-Aufmerksamkeit auf Alias-Zeile
