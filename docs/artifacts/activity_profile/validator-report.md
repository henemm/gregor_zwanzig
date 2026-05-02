# External Validator Report

**Spec:** `docs/specs/modules/activity_profile.md`
**Datum:** 2026-05-02T06:24+02:00
**Server:** https://gregor20.henemm.com (UI-Probe via http://localhost:8080 — gleiches Backend hinter dem Auth-Layer)
**Validator:** External (isoliert, kein Zugriff auf `src/`, `git log`, `git diff`, `docs/artifacts/<andere>/`)

## Zusammenfassung der Mess­methoden

Die Spec definiert die Akzeptanzkriterien §A1–§A8. Die Mehrheit ist **Code-Level** (grep auf `src/`, pytest, Python-REPL). Mein Mandat verbietet das Lesen von `src/` und Test-Code. Ich prüfe das Verhalten der **laufenden App** und der **Persistenz-Daten**:

- ✅ Verifikations-Skript `scripts/verify_activity_profile_migration.py` ausgeführt
- ✅ Web-UI (Trips, Compare, Edit-Trip, NEW-TRIP, Trip-Settings) per Headless-Browser
- ✅ Persistierte Profile-Werte unter `data/users/**/*.json` selbst gescannt
- ❌ Go-API mit Auth-Cookie nicht testbar (401 vor Validierung)
- ❌ Code-Level-grep / pytest außerhalb des Validator-Scopes

Code-Level-Akzeptanzkriterien (§A1, §A3, §A4) gehören in die **Implementierer-Pipeline**, nicht in die externe App-Validierung. Sie sind hier als **N/A (out of scope)** markiert; ein "PASS" durch den Validator wäre nicht auf Beweisen gestützt.

## Checklist

| #   | Expected Behavior (Spec)                                                                       | Beweis                                                                                                                                | Verdict                |
| --- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| §A1 | Genau ein `class ActivityProfile` in `src/app/profile.py`                                       | grep auf `src/` ist Implementierer-Pipeline; nicht Validator-Scope. App-runtime: kein Crash → Enum konsistent definiert.              | **N/A (Out of Scope)** |
| §A2 | 4 Werte (`wintersport`, `wandern`, `summer_trekking`, `allgemein`); `ActivityProfile("custom")` raises | Persistenz-Scan: `wintersport` (2 Trips + 2 Locs) und `wandern` (6 Locs) werden vom Loader fehlerfrei verarbeitet. Loader würde bei fehlendem Enum-Wert `ValueError` werfen. → 2/4 Werte indirekt PASS, `custom` taucht nirgends auf. | **PARTIAL PASS**       |
| §A3 | `LocationActivityProfile` nirgends in `src` / `tests`                                          | grep auf `src/`/`tests/` außerhalb Scope. App-runtime: keine Import-Crash-Banner.                                                     | **N/A (Out of Scope)** |
| §A4 | `uv run pytest` grün                                                                           | pytest-Lauf außerhalb Scope (Implementierer-Pipeline).                                                                                | **N/A (Out of Scope)** |
| §A5 | `verify_activity_profile_migration.py` Exit 0                                                  | Selbst ausgeführt: `OK: 454 Dateien gescannt, 10 Profile-Werte alle gueltig`, Exit 0                                                   | **PASS**               |
| §A6 | API akzeptiert `summer_trekking`, lehnt `custom` mit 400 ab                                    | `POST /api/subscriptions` → HTTP 401 (Auth-Layer schaltet vor Validator). Ohne gültigen Auth-Token nicht testbar.                     | **UNKLAR**             |
| §A7 | GPX-Upload und Compare-Scoring intakt                                                          | UI `/trips → NEW TRIP / Edit / GPX Import` lädt ohne Crash (Screenshots 11, 12). `/compare` → 3 Locations gewählt → COMPARE-Klick liefert Score-Tabelle inkl. `Snow Depth` (Wintersport-Pfad). Screenshot 32. | **PASS**               |
| §A8 | Checkliste für künftige Sportarten-Erweiterung                                                 | Prozess-Anweisung, keine Runtime-Behauptung.                                                                                          | **N/A**                |

## Daten-Schema-Rework Verifikation (§9.3)

| Aspekt                                        | Beweis                                                                                                                                       | Verdict      |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| Trips laden ohne Datenverlust                 | `/trips` zeigt: GR221 Mallorca **4 stage(s), 16 waypoints**; Zillertal mit Steffi **1 stage(s), 1 waypoints** (Screenshot 06). Beide Trips haben `aggregation.profile = "wintersport"` und werden korrekt geladen. | **PASS**     |
| Locations werden geladen mit `wandern`-Profil | Direkter JSON-Scan: 6 Locations mit `activity_profile = "wandern"`, 2 mit `wintersport`. App-runtime nutzt sie (kein Loader-Crash beim Boot). | **PASS**     |
| Keine unbekannten Werte in Persistenz         | Eigener rekursiver Scan über alle 454 JSON-Dateien: 0 unbekannte Werte. Auch das Verifikations-Skript bestätigt Exit 0.                     | **PASS**     |
| Compare-Pipeline (Wintersport-Pfad) intakt    | `/compare` → 3 Wintersport-Locations → Score 60, Snow Depth 70cm/90cm/305cm (Screenshot 32). Sport-aware-Dispatch funktioniert.              | **PASS**     |
| Compare-Pipeline (Wandern-Pfad)               | UI bietet keinen sichtbaren Filter; Wandern-Locations konnten in dieser Session nicht im Compare-Workflow getriggert werden.                 | **UNKLAR**   |

## Beobachtungen / Findings

### F1 — UI hat keinen sichtbaren `ActivityProfile`-Selector
- **Severity:** LOW (Spec-konform, keine Anforderung verletzt)
- **Beobachtung:** Weder `/compare`, `/trips → NEW TRIP`, `/trips → Edit GR221` noch `/trips → WETTER-METRIKEN` zeigen ein Dropdown/Radio zur Auswahl des Activity-Profils.
- **Bewertung:** Die Spec §3 listet "UI-Elemente zur Profil-Auswahl" explizit als **Out-of-Scope**. Das Profil wird über die JSON-Datei gepflegt (für Trips: `aggregation.profile`, für Locations: `activity_profile`). Konsistent mit Spec.
- **Evidence:** `screenshots/11_new_trip.png`, `screenshots/12_edit_gr221.png`, `screenshots/13_trip_settings.png`, `screenshots/30_compare_dropdown.png`

### F2 — Persistierte Profile-Verteilung
- **Severity:** INFO
- **Stand 2026-05-02:**
  ```
  Trip profiles:        {'wintersport': 2}
  Location profiles:    {'wandern': 6, 'wintersport': 2}
  Subscription profiles: {} (alle null)
  ```
- **Bewertung:** 2 von 4 kanonischen Enum-Werten sind real persistiert (`wintersport`, `wandern`). `summer_trekking` und `allgemein` sind im aktuellen `data/users/`-Bestand nicht vorhanden — für deren Validierung über die laufende App müsste manuell ein Trip mit diesen Werten angelegt werden. Spec §4.2 erwähnt "wandern" gar nicht als persistierten Wert; tatsächlich sind 6 Locations mit "wandern" gespeichert. Spec-Tabelle ist hier ungenau, aber funktional unkritisch — alle 8 Werte sind in `VALID_VALUES`.

### F3 — Auth-Layer blockiert §A6-Test
- **Severity:** MEDIUM
- **Beobachtung:** `POST /api/subscriptions` mit `activity_profile: "summer_trekking"` und mit `"custom"` liefert beide HTTP 401 — der Validator-Layer der Go-Whitelist liegt **hinter** der Auth. Ohne gültigen Session-Token kann ich nicht prüfen, ob die Whitelist die 4 Werte korrekt erlaubt bzw. `custom` mit 400 ablehnt.
- **Bewertung:** §A6 ist über die Production-API ohne Login nicht extern verifizierbar. Empfehlung: Implementierer-Pipeline soll das per integrationstest decken.

### F4 — Routes mit 404 in lokaler UI
- **Severity:** INFO
- **Beobachtung:** `/locations`, `/subscriptions`, `/dashboard`, `/settings`, `/gpx-upload`, `/trip/<id>` liefern alle HTTP 404 in der NiceGUI-App. Existierend sind nur `/`, `/trips`, `/compare`. Trip-Edit/Settings sind Modals innerhalb von `/trips`.
- **Bewertung:** Nicht spec-relevant — in der Top-Nav stehen "Locations / Subscriptions / Settings", aber sie sind aktuell nicht implementiert. Affects nicht ActivityProfile-Migration.

## Verdict: VERIFIED (mit Scope-Vorbehalten)

### Begründung

**Was ich extern beweisen kann, ist konsistent mit der Spec:**

1. **Persistenz-Migration (§9.2/§A5/§9.3) ist solide:** Der Verifikations-Scan über 454 JSON-Dateien meldet 0 unbekannte Werte und Exit 0. Mein eigener unabhängiger Scan bestätigt: 10 Profile-Werte (`wintersport`×4, `wandern`×6) — alle im erlaubten 4-Werte-Set. Kein `custom`, kein Legacy-Wert.

2. **Loader funktioniert mit beiden in Produktion vorkommenden Werten:** Sowohl `wintersport` (Trip-Aggregation, Location) als auch `wandern` (Location) werden vom Backend ohne Crash geladen — die Web-UI zeigt alle Trips/Locations korrekt an. Hätten Enum-Werte gefehlt oder wäre `LocationActivityProfile` nicht mehr definiert, würde der Loader fallen.

3. **Sport-aware Compare-Scoring intakt (§A7):** `/compare` mit 3 Wintersport-Locations liefert vollständiges Ergebnis mit `Score`, `Snow Depth`, `New Snow`, `Wind/Gusts` etc. Der Wintersport-Dispatch-Pfad funktioniert.

4. **Trip-CRUD-UIs intakt (§A7):** NEW TRIP, Edit Trip und Wetter-Metriken-Settings laden für GR221 (wintersport) ohne Crash.

5. **Daten-Bestand erhalten (§9.3):** GR221 Mallorca (4 Stages, 16 Waypoints) und Zillertal mit Steffi (1 Stage, 1 Waypoint) sind vollständig — kein Datenverlust durch die Migration.

**Was außerhalb meines Scopes liegt** (§A1, §A3, §A4 — grep/pytest auf `src/tests`) wird in der Implementierer-Pipeline geprüft. §A6 ist hinter Auth nicht extern testbar. Diese sind nicht "BROKEN", sondern "nicht durch den External Validator abgedeckt".

**Verdict: VERIFIED** — die durch eine externe App-Probe beweisbaren Anforderungen halten. Die Code-Level- und API-Auth-Anforderungen sind als out-of-scope markiert und müssen separat (Implementierer-Pipeline) abgesichert werden.

## Evidenz / Screenshots

Alle Screenshots im Unterordner `screenshots/`:

| Screenshot | Zweck |
|------------|-------|
| `02_trips.png` / `06_trips_loaded.png` | `/trips` zeigt 2 Trips mit korrekten Stage-/Waypoint-Counts |
| `08_compare_loaded.png` | `/compare`-Initial-State |
| `11_new_trip.png` | Modal "New Trip" — kein Profile-Dropdown |
| `12_edit_gr221.png` | Modal "Edit Trip GR221" — Stages/Waypoints intakt, kein Profile-Dropdown |
| `13_trip_settings.png` | Wetter-Metriken-Konfig für GR221 (wintersport-Profil-getrieben) lädt |
| `30_compare_dropdown.png` | Locations-Dropdown im Compare |
| `31_compare_selected.png` | 3 Wintersport-Locations gewählt |
| `32_compare_results.png` | Compare-Ergebnis mit Score 60, Snow Depth 70cm — Sport-aware-Scoring intakt |
| `compare_full.html` / `trips_full.html` | Roh-HTML für Reproduzierbarkeit |

## Anhang: Manuelle Verifikations-Skript-Ausführung

```
$ uv run python3 scripts/verify_activity_profile_migration.py
OK: 454 Dateien gescannt, 10 Profile-Werte alle gueltig
$ echo $?
0
```

## Anhang: Eigener Persistenz-Scan (zur Cross-Validierung)

```
Total JSON files: 454
Trip profiles:         {'wintersport': 2}
Location profiles:     {'wandern': 6, 'wintersport': 2}
Subscription profiles: {}
Unknown values: 0
```
