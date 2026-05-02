---
entity_id: activity_profile
type: module
created: 2026-05-01
updated: 2026-05-01
status: active
version: "1.0"
tags: [refactor, model, harmonization, profile]
issue: 98
---

# ActivityProfile Harmonisierung

**Status:** DRAFT
**Issue:** [#98 ActivityProfile-Konsolidierung](https://github.com/henemm/gregor_zwanzig/issues/98)

## Approval

- [ ] Approved

## §1 Zweck

`src/app/trip.py::ActivityProfile` (3 Werte) und `src/app/user.py::LocationActivityProfile`
(3 Werte) sind zwei separate Enums mit überlappender Bedeutung aber inkompatibler
Wert-Menge — einzig `WINTERSPORT` ist gemeinsam. Dieses Modul führt einen **einzigen
kanonischen Typ** `ActivityProfile` in `src/app/profile.py` ein und ersetzt beide
vorhandenen Definitionen durch Re-Export-Aliase (PR 1) und anschließende vollständige
Migration (PR 2).

**Warum jetzt?** Jede neue Sportart (Klettern, MTB, Bergsteigen) müsste bislang in zwei
Enums und zwei Dispatch-Tabellen ergänzt werden. Nach der Konsolidierung gibt es genau
eine Stelle: `profile.py`. Die Dispatch-Logik in `trip.py::AggregationConfig.for_profile`
und `compare.py::calculate_score` bleibt bewusst getrennt — das Enum ist ein
**semantisches Label**, kein Behavior-Key.

## §2 Quelle/Source

- **Neue Datei:** `src/app/profile.py` — enthält den kanonischen Enum `ActivityProfile`
- **Identifier:** `class ActivityProfile(str, Enum)`
- **Verifikations-Skript:** `scripts/verify_activity_profile_migration.py`

## §3 Scope

### In-Scope

- Neue Datei `src/app/profile.py` mit den 4 kanonischen Werten
- Re-Export-Alias in `src/app/trip.py` (PR 1)
- Backward-Compat-Alias `LocationActivityProfile` in `src/app/user.py` (PR 1)
- Vollständige Migrations-Umstellung aller Importer (PR 2)
- Sync-Comment in `internal/handler/subscription.go:82-86`
- Verifikations-Skript `scripts/verify_activity_profile_migration.py`

### Out-of-Scope

- Neue Sportarten (Klettern, MTB, Bergsteigen) — eigene Issues nach Konsolidierung
- UI-Elemente zur Profil-Auswahl
- Score-Logik-Änderungen in `compare.py` (nur Import-Pfad ändert sich)
- Aggregations-Logik-Änderungen in `AggregationConfig` (nur Import-Pfad ändert sich)
- Go-seitige Code-Generierung der Whitelist (Aufwand 10:1, Comment-Pin reicht)

## §4 Datenmodell

### §4.1 Neuer kanonischer Enum

```python
# src/app/profile.py
from enum import Enum

class ActivityProfile(str, Enum):
    """Semantisches Label für eine Aktivitäts-/Sportart.

    Dieses Enum ist ein semantisches Label — KEIN Behavior-Key.
    Die zugehörigen Dispatch-Tabellen sind unabhängig:
    - trip.py::AggregationConfig.for_profile  (Aggregations-Semantik)
    - compare.py::calculate_score              (Scoring-Semantik)

    Bei Erweiterung um neue Sportarten MUSS die Go-Whitelist in
    internal/handler/subscription.go synchronisiert werden
    (Sync-Comment dort, Checkliste §A7 unten).
    """

    WINTERSPORT     = "wintersport"      # Schnee/Lawinen
    WANDERN         = "wandern"          # Tieflagen-Wanderung (Scoring-Semantik)
    SUMMER_TREKKING = "summer_trekking"  # Alpine Mehrtagestour (Aggregations-Semantik)
    ALLGEMEIN       = "allgemein"        # Generischer Default
```

**Bewusst weggelassen:** `CUSTOM` — war in `AggregationConfig.for_profile()` ein
Fallthrough-Default ohne eigene Logik. Fälle, die heute `CUSTOM` gespeichert haben, sind
semantisch `ALLGEMEIN`.

### §4.2 Persistierte Werte (aktueller Bestand)

Vor PR 1: Verifikations-Skript läuft gegen `data/users/` (alle User-Verzeichnisse) und
dokumentiert den Bestand. Stand 2026-05-01 (Skript-Lauf nach PR 1, post-deploy):

| Pfad | Feld | Aktuelle Werte |
|------|------|----------------|
| `data/users/default/trips/gr221-mallorca.json` | `aggregation.profile` | `"wintersport"` |
| `data/users/default/trips/zillertal-mit-steffi.json` | `aggregation.profile` | `"wintersport"` |
| `data/users/default/locations/*.json` | `activity_profile` | (Feld nicht persistiert) |
| `data/users/default/compare_subscriptions.json` | `activity_profile` | (unbekannt, Skript klärt) |
| `data/users/__bug89_*` und `__test_*` (Test-Fixtures) | `activity_profile` | gemischt `"wandern"` + `"wintersport"` |

**Skript-Resultat:** 454 Dateien gescannt, 10 Profile-Werte gefunden — davon 4× `wintersport`
und 6× `wandern`. Werte `summer_trekking` und `allgemein` sind aktuell in keiner Datei
persistiert (semantisch valide, aber ungenutzt).

Alle 4 Enum-Werte (`wintersport`, `wandern`, `summer_trekking`, `allgemein`) sind weiterhin
gültig — keine Wert-Umbenennung, keine Migration der persistierten Strings nötig.

## §5 Dependencies

| Entity | Typ | Zweck |
|--------|-----|-------|
| `src/app/trip.py::ActivityProfile` | ersetzt durch Re-Export | PR 1: `from app.profile import ActivityProfile` |
| `src/app/user.py::LocationActivityProfile` | ersetzt durch Alias | PR 1: `LocationActivityProfile = ActivityProfile` |
| `src/app/loader.py` | modifiziert | Import-Pfad auf `app.profile` |
| `src/web/pages/compare.py` | modifiziert | Import-Pfad auf `app.profile` |
| `src/web/pages/gpx_upload.py` | modifiziert | Import-Pfad auf `app.profile` |
| `api/routers/compare.py` | modifiziert | Import-Pfad auf `app.profile` |
| `internal/handler/subscription.go:82-86` | Sync-Comment | Whitelist explizit an Python-Source gepinnt |
| `tests/tdd/test_generic_locations.py` | modifiziert (PR 2) | 15+ Verwendungen `LocationActivityProfile.*` |
| `tests/tdd/test_sport_aware_scoring.py` | modifiziert (PR 2) | 13+ Verwendungen |
| `tests/tdd/test_weather_templates.py` | modifiziert (PR 2) | 3 Verwendungen |
| `tests/integration/test_config_persistence.py` | modifiziert (PR 2) | 2 Verwendungen |
| `tests/test_loader.py` | modifiziert (PR 2) | Trip-Profile-Referenzen |
| `tests/test_trip.py` | modifiziert (PR 2) | Trip-Profile-Referenzen |

## §6 Implementierungsdetails

### §6.1 Phasing — Zwei PRs

**Kernprinzip:** PR 1 macht den Canonical-Enum sichtbar ohne irgendeinen bestehenden
Import zu brechen. PR 2 ist rein mechanisches Rename.

#### PR 1 — Canonical-Enum + Aliase (kein Test-Touch)

1. Neue Datei `src/app/profile.py` anlegen mit `ActivityProfile` (4 Werte, s. §4.1).
2. In `src/app/trip.py` den Enum-Body ersetzen:
   ```python
   # vorher:
   class ActivityProfile(str, Enum):
       WINTERSPORT     = "wintersport"
       SUMMER_TREKKING = "summer_trekking"
       CUSTOM          = "custom"

   # nachher (Zeilen werden zu einem Re-Export):
   from app.profile import ActivityProfile
   ```
3. In `src/app/user.py` den Enum-Body ersetzen und Alias setzen:
   ```python
   # vorher:
   class LocationActivityProfile(str, Enum):
       WINTERSPORT = "wintersport"
       WANDERN     = "wandern"
       ALLGEMEIN   = "allgemein"

   # nachher:
   from app.profile import ActivityProfile
   LocationActivityProfile = ActivityProfile  # backward-compat alias
   ```
4. Alle 40+ Tests laufen ohne Änderung grün (Aliase garantieren Kompatibilität).
5. `CUSTOM` ist nach PR 1 **nicht mehr** in `ActivityProfile`. Wenn in `for_profile()`
   ein `case ActivityProfile.CUSTOM` existiert, muss er auf `ActivityProfile.ALLGEMEIN`
   umgestellt werden.

#### PR 2 — Alias-Entfernung + Test-Migration (mechanisch)

1. `LocationActivityProfile = ActivityProfile`-Zeile aus `user.py` entfernen.
2. In folgenden Dateien alle `from app.user import LocationActivityProfile`
   durch `from app.profile import ActivityProfile` ersetzen (und Verwendungen
   `LocationActivityProfile.*` durch `ActivityProfile.*`):
   - `src/app/loader.py`
   - `src/web/pages/compare.py`
   - `src/web/pages/gpx_upload.py`
   - `api/routers/compare.py`
   - `tests/tdd/test_generic_locations.py`
   - `tests/tdd/test_sport_aware_scoring.py`
   - `tests/tdd/test_weather_templates.py`
   - `tests/integration/test_config_persistence.py`
3. In Test-Dateien mit Trip-Profilen (`tests/test_loader.py`, `tests/test_trip.py`):
   `from app.trip import ActivityProfile` → `from app.profile import ActivityProfile`.
4. Alle Tests laufen grün.
5. `grep -r "LocationActivityProfile" src tests` liefert null Treffer.

### §6.2 Go-Sync-Comment

In `internal/handler/subscription.go` an Zeile 82 (Whitelist-Block) einen Kommentar
einfügen:

```go
// sync with src/app/profile.py ActivityProfile enum
// Allowed values: wintersport, wandern, summer_trekking, allgemein
// When adding a new ActivityProfile value in Python, update this list manually.
```

Go-seitige Code-Generierung wird nicht eingeführt (Kosten-Nutzen 10:1 negativ, manueller
Sync mit Spec-Checkliste reicht).

### §6.3 Verifikations-Skript

`scripts/verify_activity_profile_migration.py` läuft **vor PR 1** und dokumentiert den
Ist-Bestand als Evidenz gemäß CLAUDE.md §Daten-Schema-Reworks:

```
Zweck: Scan von data/users/ vor der Migration.
Exit 0  → alle gefundenen Werte sind in {wintersport, wandern, summer_trekking, allgemein, None/absent}
Exit 1  → unbekannte Werte gefunden (Liste + Dateipfade)
```

**Implementierungsschritte:**

1. `pathlib.Path("data/users").rglob("*.json")` — alle JSON-Dateien rekursiv
2. Für Trip-JSONs (Heuristik: Datei enthält `"aggregation"` top-level-Key):
   `data["aggregation"]["profile"]` prüfen, falls Feld vorhanden
3. Für Location-JSONs (enthält `"activity_profile"`-Key): Wert prüfen
4. Für `compare_subscriptions.json` (Array): je Eintrag `activity_profile` prüfen
5. `VALID_VALUES = {"wintersport", "wandern", "summer_trekking", "allgemein"}`
6. Unbekannter Wert → `raise ValueError(f"Unbekannter Wert '{val}' in {path}")` (kein
   silent-continue)
7. Abschluss: Anzahl-Summary auf stdout (Dateien gescannt, Felder gefunden, alle valide)

## §7 Prozess / Workflow

### §7.1 Vor PR 1

1. `uv run python3 scripts/verify_activity_profile_migration.py` — Exit 0 ist
   Voraussetzung. Output in PR-Beschreibung dokumentieren.
2. Schema-Backup-Hook greift automatisch beim Edit von `trip.py`/`loader.py`/`user.py`
   (`.backups/data-pre-rework-<ts>.tar.gz`).
3. Pre-Snapshot-Bestand notieren: Anzahl Trips mit `wintersport`-Profil.

### §7.2 PR 1 Ablauf

1. `src/app/profile.py` anlegen.
2. `src/app/trip.py` und `src/app/user.py` auf Re-Export/Alias umstellen.
3. `uv run pytest` — alle Tests grün (kein Test-Touch erforderlich).
4. `grep -r "class ActivityProfile" src` → genau ein Treffer (in `profile.py`).
5. `grep -r "class LocationActivityProfile" src` → null Treffer.
6. PR merge.

### §7.3 PR 2 Ablauf

1. `LocationActivityProfile`-Alias aus `user.py` entfernen.
2. Alle Import-Stellen mechanisch auf `app.profile` umstellen (s. §6.1 PR 2).
3. `uv run pytest` — alle Tests grün.
4. `grep -r "LocationActivityProfile" src tests` → null Treffer.
5. PR merge.

### §7.4 Post-Migration-Verifikation

1. `uv run python3 scripts/verify_activity_profile_migration.py` nochmals — Exit 0.
2. Web-UI: Locations-Liste laden, Compare-Seite laden, GPX-Upload testen.
3. Trips im Frontend laden, Stage- und Wegpunkt-Counts gegen Pre-Snapshot vergleichen.

## §8 Fehlerbehandlung

| Bedingung | Verhalten |
|-----------|-----------|
| Unbekannter Wert in `data/users/` (z.B. `"custom"`) | Verifikations-Skript Exit 1 + ValueError mit Dateipfad — PR wird nicht gemergt |
| `for_profile(ActivityProfile.CUSTOM)` wird aufgerufen (kann nicht mehr auftreten nach PR 1) | `CUSTOM` existiert nach PR 1 nicht mehr; Code muss vorher auf `ALLGEMEIN` umgestellt werden |
| Go-API empfängt `summer_trekking` (neuer Wert) | Akzeptiert nach Go-Whitelist-Update; abgelehnt (400) bis dahin — daher Whitelist MUSS synchron mit PR 2 aktualisiert werden |
| Loader liest Trip-JSON mit fehlendem `profile`-Feld | Bestehender Default-Fallback in `loader.py::_parse_activity_profile()` gibt `None` zurück — unverändert |

## §9 Daten-Schema-Reworks (PFLICHT per CLAUDE.md)

### §9.1 Pre-Snapshot

- Schema-Backup-Hook erstellt automatisch `.backups/data-pre-rework-<ts>.tar.gz` beim
  ersten Edit einer Schema-Datei.
- Verifikations-Skript läuft manuell vor PR 1 und dokumentiert: Anzahl Trips mit
  `wintersport`-Profil, Anzahl Locations mit `activity_profile`-Feld, Anzahl
  Compare-Subscriptions.

### §9.2 Migration

Kein Alias-Layer nötig, da:
- Alle 4 Enum-Werte bleiben semantisch valide (`wintersport`, `wandern`,
  `summer_trekking`, `allgemein`)
- `CUSTOM` hat keinen persistierten Wert in Produktion (`"custom"` taucht in keiner
  bekannten JSON-Datei auf)
- Loader liest JSON-Strings, nicht Enum-Klassen — der String-Wert ändert sich nicht

### §9.3 Post-Verifikation

1. Verifikations-Skript nochmals → Exit 0
2. Alle Trips/Locations/Subscriptions im Frontend laden
3. Stage-/Waypoint-Counts gegen Pre-Snapshot vergleichen
4. Bei Datenverlust: sofortiges Rollback aus `.backups/`

### §9.4 Anti-Pattern (verboten)

```python
# VERBOTEN: Neues Enum-Objekt baut Persistenz ohne Read-Modify-Write
activity_profile = ActivityProfile("unknown_value")  # raises ValueError!
```

`ActivityProfile("unknown_value")` raised seit PR 1 direkt. Loader muss try/except
behalten (`_parse_activity_profile()` oder äquivalent) und bei unbekanntem Wert einen
sinnvollen Fallback (z.B. `ALLGEMEIN`) oder `None` zurückgeben.

## §10 Architektur-Diagramm (Soll-Zustand nach PR 2)

```
┌─────────────────────────────────────────────────────────────────┐
│                    src/app/profile.py (NEU)                     │
│                                                                 │
│   class ActivityProfile(str, Enum):                             │
│       WINTERSPORT     = "wintersport"                           │
│       WANDERN         = "wandern"                               │
│       SUMMER_TREKKING = "summer_trekking"                       │
│       ALLGEMEIN       = "allgemein"                             │
│                                                                 │
│   ← Single Source of Truth für alle Profile                     │
└───────────────────┬─────────────────────────────────────────────┘
                    │  importiert von
        ┌───────────┼───────────────────────────────┐
        │           │                               │
        ▼           ▼                               ▼
 src/app/trip.py  src/app/user.py          (weitere Importer)
 (Re-Export, PR1)  (Re-Export, PR1)         compare.py
                   alias entfernt (PR2)     gpx_upload.py
                                            loader.py
                                            api/routers/compare.py

── ENTFERNT NACH PR 2 ──────────────────────────────────────────
   class ActivityProfile in trip.py     (war 3 Werte)
   class LocationActivityProfile        (war 3 Werte)
   alias LocationActivityProfile = ...  (war Brücke in PR1)
────────────────────────────────────────────────────────────────

┌──────────────────────────────────────────────────────────────┐
│  internal/handler/subscription.go:82-86                      │
│                                                              │
│  // sync with src/app/profile.py ActivityProfile enum        │
│  allowed := []string{                                        │
│      "wintersport", "wandern", "summer_trekking", "allgemein" │
│  }                                                           │
│  ← Manuell gepflegt, bei Erweiterung Spec §A7 beachten       │
└──────────────────────────────────────────────────────────────┘
```

## §11 Akzeptanzkriterien

### §A1 — Ein einziger Enum

- `grep -rn "class ActivityProfile" src` liefert **genau einen Treffer** (in `src/app/profile.py`)
- `grep -rn "class LocationActivityProfile" src` liefert **null Treffer**

### §A2 — Alle 4 Werte vorhanden

- `ActivityProfile.WINTERSPORT.value == "wintersport"`
- `ActivityProfile.WANDERN.value == "wandern"`
- `ActivityProfile.SUMMER_TREKKING.value == "summer_trekking"`
- `ActivityProfile.ALLGEMEIN.value == "allgemein"`
- `ActivityProfile("custom")` raises `ValueError` (kein `CUSTOM`-Wert)

### §A3 — Alias entfernt (nach PR 2)

- `grep -rn "LocationActivityProfile" src tests` liefert **null Treffer**

### §A4 — Alle Tests grün (keine semantischen Regressionen)

- `uv run pytest` liefert nach PR 1 grünen Run ohne Test-Änderungen
- `uv run pytest` liefert nach PR 2 grünen Run mit mechanisch umgestellten Imports

### §A5 — Verifikations-Skript clean

- `python3 scripts/verify_activity_profile_migration.py` auf `data/users/default/`
  liefert Exit 0 — sowohl vor PR 1 als auch nach PR 2

### §A6 — Go-Validation akzeptiert alle 4 Werte

- API-Endpunkt akzeptiert `activity_profile: "summer_trekking"` nach Whitelist-Update
- API-Endpunkt lehnt `activity_profile: "custom"` mit 400 ab (war schon vorher ungültig)

### §A7 — GPX-Upload und Compare-Scoring intakt

- GPX-Upload nutzt `ActivityProfile.SUMMER_TREKKING` — funktioniert nach PR 2
- Compare-Scoring dispatcht korrekt für `wintersport`-, `wandern`- und `allgemein`-Pfade

### §A8 — Go-Whitelist-Erweiterung (Checkliste für zukünftige Sportarten)

Wenn ein neuer `ActivityProfile`-Wert in `profile.py` ergänzt wird:
- [ ] Neuen String-Wert in `internal/handler/subscription.go` Whitelist eintragen
- [ ] Sync-Comment in `subscription.go` aktualisieren
- [ ] Verifikations-Skript `VALID_VALUES` erweitern
- [ ] Diesen Spec aktualisieren (§4.1 und §5)

## §12 Risiken

### R1 — Unbekannte Werte in User-Verzeichnissen

**Risiko:** Ein User-Verzeichnis enthält Trips mit `"profile": "custom"` oder anderen
Legacy-Werten, die nicht in den 4 kanonischen Werten sind.

**Mitigation:** Verifikations-Skript scannt **rekursiv** alle `data/users/`-Unterordner
und `raises ValueError` (kein silent-continue). Exit 1 blockiert PR-Merge.

### R2 — Go-Whitelist-Drift bei späteren Erweiterungen

**Risiko:** Nach Konsolidierung werden neue Sportarten in `profile.py` ergänzt, aber
`subscription.go`-Whitelist wird vergessen → API lehnt valide Werte ab.

**Mitigation:** Sync-Comment in `subscription.go` + Checkliste §A8 in dieser Spec.
Bei Erweiterung: Spec-Review triggert Whitelist-Update.

### R3 — Versehentliches Entfernen des PR-1-Alias

**Risiko:** PR 1 und PR 2 werden als ein einziger PR zusammengeführt oder der Alias
`LocationActivityProfile = ActivityProfile` wird aus Versehen in PR 1 nicht gesetzt →
40+ Tests brechen.

**Mitigation:** PR 1 explizit trennen. Review-Checkliste: Alias-Zeile in `user.py`
muss in PR 1 vorhanden sein (`grep "LocationActivityProfile = ActivityProfile" src/app/user.py`).

## §13 Referenzen

| Quelle | Bezug |
|--------|-------|
| GitHub Issue #98 | Konsolidierungs-Auftrag |
| `docs/context/activity-profile-harmonization.md` | Phase-1+2-Analyse und Strategie |
| `docs/specs/modules/wintersport_profile_consolidation.md` | §13: listet dieses Issue explizit als Out-of-Scope der β4-Phase |
| `docs/specs/modules/sport_aware_comparison.md` | Score-Dispatcher in `compare.py` |
| `docs/specs/modules/generic_locations.md` §53-59 | Historische Begründung der Trennung (trägt nicht mehr) |
| `src/app/trip.py:129,146-160` | `AggregationConfig.for_profile()` — Dispatch-Tabelle bleibt unverändert |
| `src/web/pages/compare.py:61-67` | Score-Dispatch — nur Import-Pfad ändert sich |
| CLAUDE.md §Daten-Schema-Reworks | Pflicht-Workflow für Schema-Änderungen |

## Changelog

- 2026-05-01: Initial spec erstellt. Strategie: ein kanonischer Enum (4 Werte), Two-PR-Migration,
  Verifikations-Skript vor PR 1, Go-Whitelist-Sync-Comment, keine Go-Code-Generierung.
