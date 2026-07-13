---
entity_id: issue_1250_briefing_subscription
type: feature
created: 2026-07-13
updated: 2026-07-13
status: draft
version: "1.0"
tags: [briefing-subscription, compare, trip, migration, epic-1230, convergence]
workflow: feat-1250-briefing-subscription
---

<!-- Issue #1250 — Phase 3 von Epic #1230 (Konvergenz-Programm E8/E9, C1-C6).
     Vorgänger-Phasen #1231 (Korridore), #1229 (Monitor-Hub), #1232 (geteilte
     Organismen + flache Briefing-Slot-Felder) sind live. Programm-Spec über
     8 Scheiben (Scheibe 0 = #1131), Muster #1231 (eine Spec, Scheiben-Workflows). -->

# Issue 1250 — BriefingSubscription: Trip + Vergleich konvergieren

## Approval

- [ ] Approved — wartet auf PO-Freigabe (getipptes „go")

## Purpose

Trip und ComparePreset — heute zwei divergente Datenmodelle mit einem
zusätzlichen aktiven Legacy-Drittstack (`CompareSubscription`) — werden Feld
für Feld auf ein gemeinsames Schema `BriefingSubscription{kind:"route"|"vergleich"}`
konvergiert: ein Store, eine API-Familie, ein Scheduler-Einstieg. Kein
Big-Bang — jede der 8 Scheiben ist unabhängig auslieferbar und verhaltensneutral,
bis Scheibe 5 die gemeinsame Persistenz (`briefings/<id>.json`) einführt.

## Source

> Schicht-Hinweis (Template-Pflicht): Diese Spec deckt **alle drei Schichten**
> ab — Frontend (`frontend/src/lib/...`), Go-API (`internal/model/`,
> `internal/store/`, `internal/handler/`, `cmd/server/router.go`) und
> Python-Core (`src/app/`, `src/services/`, `src/output/renderers/`).
> Aufteilung nach Schicht + Scheibe steht in der Scheiben-Tabelle unten.

- **File (Ist-Vermessung, verbindlich):** `docs/context/feat-1250-briefing-subscription.md`
  (alle Datei:Zeile-Belege dieser Spec stammen von dort)
- **Identifier:** `Trip` (`internal/model/trip.go:101-131`), `ComparePreset`
  (`internal/model/compare_preset.go:14-92`), `CompareSubscription`
  (`internal/store/subscription.go:15-17`) — Ziel: `BriefingSubscription`

## Estimated Scope

- **LoC:** ~1500 gesamt (netto, Scheibe 0 stark negativ), verteilt auf 8
  Scheiben (je ≤250 LoC bzw. mit angekündigtem Override, Muster #1231)
- **Files:** ~30 (Neuanlagen + Änderungen über Go/Python/Svelte/Migrationsskript)
- **Effort:** high (cross-layer, Datei-Migration, Renderer- und Mail-Gates,
  zwei aktive Legacy-Vollpfade)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/issue_1231_korridor_editor.md` | Spec | Corridor-Modell + Migrationsmuster (Dry-Run/Backup/Idempotenz) als Vorbild für die BriefingSubscription-Migration |
| `docs/specs/modules/issue_1229_monitor_hub.md` | Spec | Hub-Statusanzeige, konsumiert `paused_at`/Auto-Pause-Hinweis aus Scheibe 3 |
| `docs/reference/api_contract.md` | Referenz | SSoT DTOs — MUSS mit `/api/briefings*` (Scheibe 6) nachgezogen werden |
| Issue #1131 | Issue | Legacy `CompareSubscription`-Stack, wird in Scheibe 0 stillgelegt |
| Issue #1244 | Issue | `corridors:null` bricht Python-Loader — MUSS vor Scheibe 4/5 als eigener Bugfix-Workflow gelöst sein (Migration liest jeden Trip durch den Loader) |
| Issue #1221 | Issue | Compare-Editor `handleSave` verliert Felder — MUSS vor Scheibe 4/5 als eigener Bugfix-Workflow gelöst sein (verfälscht sonst Vorher/Nachher-Verifikation) |
| Issue #1203 | Issue | Config-Resolver — Scheibe 1 ist natürlicher Unterbau, NICHT Teil dieser Spec |
| Issue #1159 | Issue | Merge-Helfer für Config-PUTs — bleibt eigenständig, Scheibe 6 implementiert Merge einmalig korrekt, baut den generischen Helfer nicht |
| Issue #1207 | Issue | Konvergenz Versand-Orchestrator — Renderer-Zusammenführung geht als Folge-Issue dorthin (KL-1) |

## Implementation Details

### Zielmodell

`BriefingSubscription{kind:"route"|"vergleich", ...gemeinsame Felder}` ersetzt
mittelfristig `Trip` und `ComparePreset` als ein Schema, eine Persistenz
(`data/users/<uid>/briefings/<id>.json`, 1 Datei/Entität nach Trip-Muster),
eine API-Familie (`/api/briefings*`) und einen Scheduler-Einstieg. `kind` ist
additiv und diskriminiert nur die kind-spezifischen Felder (`Stages`,
`AlertRules`, `Aggregation`, `AvalancheRegions`, `Shortcode` bei `route`;
`LocationIDs`, `HourlyEnabled`, `RadarAlertEnabled` bei `vergleich`); die
Renderer-Templates selbst bleiben getrennt (E9, KL-1).

### Richtungs-Tabelle (Feld-für-Feld-Konvergenz, kein Big-Bang)

| Feld/Bereich | Zielrichtung | Rationale |
|---|---|---|
| Pause | `paused_at *time` (Trip-Modell gewinnt) | Preset dual-write über `schedule=="manual"` bis FE umgestellt ist (Scheibe 2); Trip-Semantik ist bereits das Zielformat für `deriveStatusFromPreset` |
| Briefing-Slots + Kanäle | Flache Felder (Preset-Modell gewinnt) | Trip dual-read aus `report_config`-Map (Scheibe 4); Preset hat bereits die flachen Felder aus #1232 |
| Profil | `activity_profile`-Namensraum (Neubau, einzige echte Wertkonvertierung) | Trip `Activity` (ActivityType) und Preset `Profil` (ActivityProfile) sind verschiedene Namensräume — Mapping-Tabelle nötig, kein reines Rename |
| endDate | Persistiert + nullable auf beiden Seiten | `route`: Server materialisiert aus `max(stage.date)` (bisher reine FE-Berechnung `computeTripEnd`); `vergleich`: bereits persistiert (`EndDate *string`) |
| Deprecated-Felder (`Schedule`, `PreviousSchedule`, `Weekday`, `HourFrom/HourTo`, `ForecastHours`) | Dokumentierter Pass-Through bis zur Migrations-Scheibe (5) | Tragen bis dahin lebende Semantik (`schedule=="manual"` = Pause!), dürfen nicht vorzeitig entfernt werden (KL-3) |
| `kind`-Diskriminator | Additiv, existiert vorher nirgends | Voraussetzung für gemeinsamen Store (Scheibe 5) und Scheduler-Dispatch (Scheibe 7) |

### Scheiben-Definition (0–7)

**Scheibe 0 — Legacy-Drittstack stilllegen (#1131)**
- Inhalt: `CompareSubscription`-Stack (Handler, Store, 9 Routen, Python-CLI-Pfad,
  FE-Totcode) entfernen; Account-Zähler auf `/api/compare/presets` umstellen.
- Dateien: `internal/store/subscription.go` (DELETE), `internal/handler/subscription.go`
  (DELETE, 305 LoC), `cmd/server/router.go:145-152` (Routen entfernen),
  `src/app/user.py:117`, `src/app/loader.py:1375-1467` (DELETE), FE
  `types.ts:298-320` (`Subscription`-Typ, DELETE), `compareWizardState.svelte.ts:85,161`
  (`wiz.save()`/`toggleEnabled()`-Totcode, DELETE), `+page.server.ts:27`
  (Account-Zähler-Fix).
- ~LoC: ~40 netto add, stark negativ in Summe (Löschungen überwiegen).
- Abhängigkeiten: keine — erste Scheibe.

**Scheibe 1 — Python-Preset-Kontrakt**
- Inhalt: `ComparePreset`-Dataclass + EIN zentraler Loader ersetzt 4 rohe
  Dict-Loads.
- Dateien: `src/app/models.py` (CREATE Dataclass, analog `Trip` :168-266),
  `src/app/loader.py` (CREATE Loader-Funktion), `src/services/compare_alert.py:292`,
  `src/services/compare_radar_alert.py:180`, `src/services/compare_official_alert.py:185`,
  `src/services/scheduler_dispatch_service.py:38` (alle auf Loader umstellen).
- ~LoC: ~200.
- Abhängigkeiten: nach Scheibe 0.

**Scheibe 2 — Pause-Konvergenz**
- Inhalt: `paused_at` additiv am Preset (Go+Python+FE), Dual-Write mit
  `schedule=="manual"`, `deriveStatusFromPreset` liest `paused_at` zuerst.
- Dateien: `internal/model/compare_preset.go` (MODIFY, additives Feld),
  `internal/store/compare_preset.go` (MODIFY), `src/app/models.py` (MODIFY,
  aus Scheibe 1), `frontend/.../subscriptionHelpers.ts:100`
  (`deriveStatusFromPreset` MODIFY).
- ~LoC: ~200.
- Abhängigkeiten: nach Scheibe 1.

**Scheibe 3 — Auto-Pause bei endDate (Neubau, C3/E8)**
- Inhalt: Slot-Scheduler erkennt überschrittenes `endDate`, setzt `paused_at`,
  Hub bekommt Hinweis; idempotent, kein Auto-Archiv/-Löschen.
- Dateien: `src/services/compare_slot_scheduler.py:81-84` (MODIFY, Auto-Pause-Logik
  statt reiner Versand-Skip), Hub-Anbindung analog `issue_1229_monitor_hub.md`.
- ~LoC: ~150.
- Abhängigkeiten: nach Scheibe 2 (paused_at muss existieren); parallel zu Scheibe 4 möglich.

**Scheibe 4 — Trip-Konvergenz**
- Inhalt: Flache Slot-/Kanal-Felder additiv am Trip (Dual-Read aus
  `report_config`), `end_date` wird serverseitig materialisiert
  (`max(stage.date)`, bisher nur `trip.py:212-214` + FE `computeTripEnd`).
- Dateien: `internal/model/trip.go:101-131` (MODIFY, additive flache Felder),
  `src/app/trip.py:212-214` (MODIFY, Materialisierung), FE `types.ts:275-296`
  (`Trip`-Typ MODIFY).
- ~LoC: ~250 (Override-Kandidat, Ankündigung nötig).
- Abhängigkeiten: parallel zu Scheibe 2/3 möglich; braucht #1244-Fix vorher (KL-2).

**Scheibe 5 — `kind` + gemeinsames Modell/Store + Datei-Migration**
- Inhalt: `kind`-Feld additiv, gemeinsames `BriefingSubscription`-Modell/Store,
  Migrationsskript `data/users/<uid>/briefings/<id>.json` (Dry-Run/Backup/idempotent).
- Dateien: `internal/model/briefing_subscription.go` (CREATE),
  `internal/store/briefing_subscription.go` (CREATE),
  `scripts/migrate_1250_briefings.py` (CREATE, Vorbild
  `migrate_1231_corridors.py`), `src/app/models.py` (MODIFY, `kind`-Feld).
- ~LoC: ~250 + Migrationsskript separat.
- Abhängigkeiten: braucht Scheibe 1–4 vollständig; braucht #1244/#1221-Fixes (KL-2).

**Scheibe 6 — API-Konsolidierung**
- Inhalt: `/api/briefings*` + dünne Kompat-Delegates für `/api/trips*` und
  `/api/compare/presets*` (C6: bestehende Testids/FE bleiben stabil); PUT
  implementiert Merge statt Replace (kein Blind-Replace, KL-5).
- Dateien: `internal/handler/briefing_subscription.go` (CREATE),
  `cmd/server/router.go` (MODIFY, neue Routen + Delegates), bestehende
  `internal/handler/trip.go` / `compare_preset.go` (MODIFY, Delegate-Wrapper).
- ~LoC: ~250.
- Abhängigkeiten: braucht Scheibe 5.

**Scheibe 7 — Scheduler-Vereinheitlichung**
- Inhalt: EIN Scheduler-Einstieg liest `briefings/`, dispatcht per `kind` auf
  bestehende Render-Pfade; `last_run`-Observability je Job bleibt erhalten.
- Dateien: `cmd/server/scheduler.go` (MODIFY, ein Cron-Einstieg statt zwei),
  `src/services/trip_report_scheduler.py` / `scheduler_dispatch_service.py`
  (MODIFY, Dispatch-Wrapper, Render-Logik selbst unverändert — KL-1).
- ~LoC: ~200.
- Abhängigkeiten: braucht Scheibe 5/6.

## Expected Behavior

- **Input:** Bestehende Trips und ComparePresets, Legacy-CompareSubscription-
  Bestandsdateien, laufender Scheduler-Betrieb.
- **Output:** Nach Scheibe 7 existiert genau ein Schema, ein Store, eine
  API-Familie (`/api/briefings*`), ein Scheduler-Einstieg; Versandverhalten
  ist zu jedem Zeitpunkt zwischen den Scheiben identisch zum Vorzustand
  (Golden-Vergleich je Scheibe).
- **Side effects:** `data_schema_backup.py` Pre-Snapshot-Hook feuert bei Edits
  an `trip.go`/`compare_preset.go`/`models.py`/`loader.py`. Migrationsskript
  (Scheibe 5) schreibt `tar.gz`-Backup vor jedem `--execute`-Lauf.

## Test Plan

Zwei Schichten gemäß Test-Politik (CLAUDE.md, PO-go 2026-07-09).

**Kern-Schicht (deterministisch, kein Netz — Commit-Gate je Scheibe):**
- Scheibe 0: Go-/Python-Test prüft 404 auf entfernten Routen, Account-Zähler-
  Test gegen neue Quelle (AC-1–AC-4).
- Scheibe 1: Golden-Vergleich — Verhalten der 4 umgestellten Call-Sites vor/nach
  Umstellung auf Dataclass/Loader identisch (AC-5, AC-6).
- Scheibe 2: Parametrisierter Test Dual-Write (`paused_at` ↔ `schedule`),
  Status-Ableitung mit/ohne `paused_at` (AC-7–AC-9).
- Scheibe 3: Fixture-Test Auto-Pause-Trigger, Idempotenz (zweiter Lauf setzt
  nichts erneut), kein Archiv-/Lösch-Seiteneffekt (AC-10–AC-12).
- Scheibe 4: Roundtrip-Test Trip laden/speichern, `end_date`-Materialisierung
  gegen `max(stage.date)`-Fixtures, Golden-Vergleich Versand-Payload
  (AC-13–AC-15).
- Scheibe 5: Migrations-Dry-Run-Golden-Test auf Fixture-Bestand (Report-Diff),
  Idempotenz-Test (zweiter Lauf: 0 Änderungen), Zwei-User-Isolation-Test
  (AC-16–AC-19).
- Scheibe 6: Kontrakt-Test `/api/briefings*` + Delegate-Routen, Merge- statt
  Replace-Test (Fremdfeld bleibt erhalten) (AC-20–AC-22).
- Scheibe 7: Test Einzel-Scheduler-Dispatch nach `kind`, `last_run`-Feld pro
  Job weiterhin befüllt (AC-23, AC-24).

**Live-E2E-Schicht (nur `/e2e-verify` gegen Staging):**
- Bestehende Playwright-Specs für Trip- und Compare-Editor bleiben grün nach
  Scheibe 6 (C6, Testid-Stabilität).
- Echte Test-Mail-Verifikation (`briefing_mail_validator.py`/
  `email_spec_validator.py` je Pfad) nach Scheibe 3 (Auto-Pause-Hinweis im
  Hub) und Scheibe 7 (Versand über neuen Einstieg unverändert).
- Migrations-Dry-Run zusätzlich einmal gegen anonymisierte Staging-Kopie vor
  `--execute` auf Produktionsdaten (Deploy-Schritt, kein Commit-Gate).

## Acceptance Criteria

<!-- Scheibe 0 — Legacy CompareSubscription stilllegen (#1131) -->

- **AC-1:** Given die 9 bisherigen `/api/subscriptions*`-Routen / When ein
  Request nach Scheibe 0 gegen eine dieser Routen läuft / Then antwortet der
  Server mit 404, die Routen existieren nicht mehr im Router.
  - Test: HTTP-Test gegen jede der 9 alten Routen, prüft Status 404.

- **AC-2:** Given den Account-Zähler auf der Startseite / When er nach
  Scheibe 0 berechnet wird / Then zählt er die Anzahl der `ComparePreset`-
  Einträge (`/api/compare/presets`), nicht mehr den alten
  `CompareSubscription`-Store.
  - Test: Fixture mit N Presets und M Legacy-Subscriptions anlegen, Zähler
    liefert N, nicht N+M oder M.

- **AC-3:** Given den FE-Totcode `wiz.save()`/`toggleEnabled()`
  (`compareWizardState.svelte.ts:85,161`) / When das Repository nach
  Scheibe 0 durchsucht wird / Then existiert dieser Code-Pfad nicht mehr.
  - Test: Statischer Grep-Test auf die entfernten Funktionsnamen im
    Compare-Wizard-State, 0 Treffer.

- **AC-4:** Given die Bestandsdatei `compare_subscriptions.json` / When
  Scheibe 0 ausgeliefert wird / Then bleibt die Datei auf der Platte
  unverändert liegen (keine Datenlöschung, nur Code-Stilllegung, KL-4).
  - Test: Dateiinhalt/-Prüfsumme vor/nach Deploy von Scheibe 0 identisch.

<!-- Scheibe 1 — Python-Preset-Kontrakt -->

- **AC-5:** Given die 4 Call-Sites, die bisher rohe Dicts lasen
  (`compare_alert.py`, `compare_radar_alert.py`, `compare_official_alert.py`,
  `scheduler_dispatch_service.py`) / When sie nach Scheibe 1 auf die
  `ComparePreset`-Dataclass + den zentralen Loader umgestellt sind / Then
  liefern alle vier für denselben Bestandsdatensatz identisches Verhalten wie
  vor der Umstellung (Golden-Vergleich).
  - Test: Golden-Vergleich — gleicher Fixture-Preset durch alte und neue
    Implementierung, Ausgabe (Alert-Entscheidung, Radar-Ergebnis)
    bytegleich.

- **AC-6:** Given ein Preset mit unbekanntem/zusätzlichem Feld im JSON / When
  es durch den neuen zentralen Loader (Scheibe 1) geladen und wieder
  gespeichert wird / Then geht das unbekannte Feld nicht verloren
  (Read-Modify-Write, kein Replace).
  - Test: Fixture mit künstlichem Zusatzfeld laden/speichern, Feld nach
    Roundtrip noch vorhanden.

<!-- Scheibe 2 — Pause-Konvergenz -->

- **AC-7:** Given ein Preset mit `schedule=="manual"` (Alt-Pause-Semantik) /
  When es nach Scheibe 2 geladen wird / Then wird `paused_at` additiv
  gesetzt (Dual-Write), `schedule` bleibt unverändert erhalten.
  - Test: Fixture mit `schedule=="manual"` laden, prüft `paused_at` != null
    UND `schedule=="manual"` weiterhin vorhanden.

- **AC-8:** Given ein Preset ohne `paused_at`-Feld (Alt-Bestand vor
  Scheibe 2) / When `deriveStatusFromPreset` den Status ableitet / Then
  funktioniert die Ableitung ohne Absturz und liefert denselben Status wie
  vor der Umstellung (Fallback auf `schedule`).
  - Test: Fixture ohne `paused_at`, Status-Ableitung liefert identisches
    Ergebnis zur Alt-Implementierung.

- **AC-9:** Given ein Preset mit gesetztem `paused_at` UND abweichendem
  `schedule`-Wert / When `deriveStatusFromPreset` läuft / Then hat
  `paused_at` Vorrang (Zielrichtung: Trip-Semantik gewinnt).
  - Test: Fixture mit Konflikt zwischen `paused_at` (gesetzt) und
    `schedule!="manual"`, Status zeigt „pausiert".

<!-- Scheibe 3 — Auto-Pause bei endDate (C3/E8, Neubau) -->

- **AC-10:** Given ein Compare-Preset mit `endDate` in der Vergangenheit /
  When der Slot-Scheduler nach Scheibe 3 läuft / Then wird `paused_at`
  gesetzt und kein Versand für diese Subscription ausgelöst.
  - Test: Fixture-Preset mit `endDate` gestern, Scheduler-Lauf, prüft
    `paused_at` gesetzt + kein Versand-Aufruf.

- **AC-11:** Given ein bereits per Auto-Pause pausiertes Preset / When der
  Slot-Scheduler ein zweites Mal für denselben Tag läuft / Then bleibt
  `paused_at` unverändert (kein erneutes Setzen, kein doppelter
  Hub-Hinweis) — idempotent.
  - Test: Scheduler zweimal hintereinander mit derselben Fixture laufen
    lassen, `paused_at`-Wert und Hub-Hinweis-Anzahl unverändert nach dem
    zweiten Lauf.

- **AC-12:** Given ein Preset, dessen `endDate` durch Auto-Pause erreicht
  wurde / When der Zustand nach Auto-Pause geprüft wird / Then wird das
  Preset NICHT automatisch archiviert oder gelöscht (nur `paused_at`
  gesetzt), der Hub zeigt einen Hinweis auf die überschrittene Laufzeit.
  - Test: Fixture nach Auto-Pause-Lauf prüfen — Preset weiterhin über die
    normale Preset-Liste abrufbar, `archived_at` unverändert null, Hub-API
    liefert Hinweis-Feld.

<!-- Scheibe 4 — Trip-Konvergenz -->

- **AC-13:** Given einen Trip mit bestehender `ReportConfig`-Map (Slot-/
  Kanal-Felder) / When der Trip nach Scheibe 4 geladen wird / Then werden
  die flachen Felder additiv aus `report_config` befüllt (Dual-Read), die
  Map selbst bleibt unverändert im JSON erhalten.
  - Test: Fixture-Trip mit `report_config` laden, prüft flache Felder
    korrekt abgeleitet UND `report_config` bytegleich zum Original.

- **AC-14:** Given einen Trip mit Stages / When `end_date` nach Scheibe 4
  serverseitig materialisiert wird / Then entspricht der Wert
  `max(stage.date)` und ist identisch zu dem, was die bisherige FE-Funktion
  `computeTripEnd` berechnet hätte.
  - Test: Fixture-Trip mit mehreren Stages, Server-Wert gegen
    `computeTripEnd`-Referenzimplementierung auf denselben Daten verglichen,
    identisch.

- **AC-15:** Given einen bestehenden Trip / When er vor und nach Scheibe 4
  über den Versandpfad läuft / Then ist die erzeugte Briefing-Mail
  (Inhalt/Empfänger/Zeitpunkt) identisch (Golden-Vergleich, keine
  Verhaltensänderung durch die additiven Felder).
  - Test: Golden-Vergleich Versand-Payload vor/nach Scheibe 4 für denselben
    Fixture-Trip, bytegleich bis auf Zeitstempel-Metadaten.

<!-- Scheibe 5 — kind + gemeinsames Modell/Store + Datei-Migration -->

- **AC-16:** Given einen Trip und ein ComparePreset ohne `kind`-Feld / When
  `migrate_1250_briefings.py --execute` läuft / Then bekommen beide ein
  `kind`-Feld (`"route"` bzw. `"vergleich"`) und werden nach
  `data/users/<uid>/briefings/<id>.json` migriert, alle bestehenden Felder
  bleiben erhalten (Read-Modify-Write, kein Replace).
  - Test: Migration auf Fixture-Bestand laufen lassen, Ziel-Datei enthält
    alle Quellfelder + `kind`, Report listet jede migrierte Entität.

- **AC-17:** Given `migrate_1250_briefings.py` ohne `--execute` / When das
  Skript läuft / Then werden keine Dateien angelegt oder verändert, aber ein
  vollständiger Feld-Diff-Report ausgegeben (Dry-Run-Default, C4).
  - Test: Dateisystem-Zustand (Existenz/Zeitstempel) vor/nach Dry-Run-Lauf
    identisch, Report nicht leer.

- **AC-18:** Given eine bereits migrierte Entität (Ziel existiert + `kind`
  gesetzt) / When die Migration ein zweites Mal mit `--execute` läuft / Then
  wird diese Entität übersprungen (Skip-Report-Zeile), keine erneute
  Schreiboperation — idempotent.
  - Test: Migration zweimal mit `--execute` laufen lassen, zweiter Lauf
    Dateizeitstempel der Zielsätze unverändert + Skip-Zeile im Report.

- **AC-19:** Given zwei verschiedene User mit eigenen Trips/Presets / When
  die Migration für beide läuft / Then landen die migrierten Dateien
  ausschließlich unter dem jeweils eigenen `data/users/<uid>/briefings/`,
  kein Cross-User-Datenzugriff.
  - Test: Migration mit zwei User-IDs ausführen, prüft Datei-Präfixe strikt
    getrennt, User-A-Daten nicht unter User-B-Pfad und umgekehrt.

<!-- Scheibe 6 — API-Konsolidierung -->

- **AC-20:** Given die neuen `/api/briefings*`-Routen / When ein Request
  gegen `/api/trips/<id>` oder `/api/compare/presets/<id>` läuft / Then
  liefert der dünne Kompat-Delegate dieselbe Response-Struktur wie vor
  Scheibe 6 (bestehende FE-Aufrufe brechen nicht).
  - Test: Kontrakt-Test — Response-Schema von `/api/trips/<id>` vor/nach
    Scheibe 6 strukturell identisch.

- **AC-21:** Given bestehende `data-testid`-Attribute und FE-Aufrufpfade
  (Trip-Editor, Compare-Editor) / When Scheibe 6 ausgeliefert ist / Then
  bleiben alle bestehenden Testids und FE-Requests unverändert funktionsfähig
  (C6, kein Playwright-Bruch).
  - Test: Bestehende Playwright-Specs für Trip- und Compare-Editor laufen
    unverändert grün gegen die neue API-Schicht.

- **AC-22:** Given ein `PUT`-Request gegen `/api/briefings/<id>` mit nur
  einem Teilfeld im Body / When der Handler nach Scheibe 6 verarbeitet /
  Then bleiben alle nicht im Body enthaltenen Bestandsfelder erhalten
  (Merge, kein Blind-Replace — KL-5, siebte Wiederholung des Datenverlust-
  Musters wird explizit vermieden).
  - Test: Bestandssatz mit N Feldern anlegen, `PUT` mit 1 geändertem Feld
    senden, GET danach zeigt alle N Felder, nur das eine geändert.

<!-- Scheibe 7 — Scheduler-Vereinheitlichung -->

- **AC-23:** Given `briefings/`-Einträge mit `kind="route"` und
  `kind="vergleich"` / When der vereinheitlichte Scheduler-Einstieg nach
  Scheibe 7 läuft / Then dispatcht er jeden Eintrag korrekt auf den
  bestehenden Render-Pfad seines `kind` (Trip-Report bzw.
  Compare-Renderer), keine Vermischung.
  - Test: Fixture-Lauf mit gemischten `kind`-Einträgen, prüft je Eintrag den
    aufgerufenen Render-Pfad (Mock-freier Spy auf tatsächlichen
    Funktionsaufruf, nicht auf Rückgabewert).

- **AC-24:** Given den `/api/scheduler/status`-Endpoint / When der
  vereinheitlichte Scheduler-Einstieg läuft / Then zeigt der Endpoint
  weiterhin `last_run`/Status pro ursprünglichem Job (Trip-Reports,
  Compare-Presets-Daily) — Observability geht durch die Vereinheitlichung
  nicht verloren.
  - Test: Scheduler-Lauf auslösen, `/api/scheduler/status` abfragen, prüft
    beide Job-Einträge mit aktualisiertem `last_run`.

## Known Limitations

- **KL-1:** Tiefe Renderer-Zusammenführung (`comparison.py` vs.
  `trip_report.py`/`NotificationService`) ist NICHT Teil von #1250 — Folge-
  Issue, mit #1207 zu verschmelzen; `kind`-Dispatch existiert nach Scheibe 7
  nur am Scheduler-Einstieg. Templates bleiben per E9 getrennt.
- **KL-2:** #1244 und #1221 werden als eigene Bugfix-Workflows VOR Scheibe 4/5
  erledigt (nicht Teil dieser Spec).
- **KL-3:** Deprecated-Felder (`schedule`-Rhythmus, `weekday`, `hour_from/to`,
  `forecast_hours`) bleiben bis Scheibe 5 als Pass-Through erhalten;
  endgültige Auflösung im Migrationslauf.
- **KL-4:** `compare_subscriptions.json`-Bestandsdateien werden NICHT
  gelöscht (nur Code-Stilllegung).
- **KL-5:** #1203 (Config-Resolver) und #1159 (Merge-Helfer) bleiben
  eigenständig; Scheibe 1 ist Unterbau von #1203, Scheibe 6 implementiert
  Merge statt Replace einmalig korrekt.

## Edge Cases

| Fall | Erwartetes Verhalten |
|---|---|
| Alt-Preset ohne Slot-Felder (vor #1232) | Dual-Read/Migration liefert sinnvolle Defaults, kein Absturz |
| `endDate` liegt in der Vergangenheit beim Speichern (Epic-Ebene) | Validierungsfehler beim Save, kein stiller Erfolg |
| `endDate` wird während einer laufenden manuellen Pause erreicht | Auto-Pause-Logik (Scheibe 3) greift trotzdem, kein Konflikt mit vorhandener manueller Pause (`paused_at` bleibt gesetzt, keine doppelte Aktion) |
| Trip ohne Stages | `end_date` wird `null`, kein Crash der Materialisierung (Nachbarschaft #1178) |
| Migration bei teilmigriertem Bestand (Scheibe 5 nach Abbruch erneut gestartet) | Bereits migrierte Entitäten werden übersprungen (idempotent, AC-18), nur fehlende werden migriert |
| Zwei User führen parallel Aktionen auf ihren jeweiligen Subscriptions aus | Strikte Datei-Isolation je `user_id`, kein Cross-User-Zugriff (AC-19) |
| Legacy-`CompareSubscription`-Datei liegt nach Scheibe 0 weiter vor, wird aber nie mehr geschrieben | Datei bleibt unverändert liegen, kein Leser greift mehr zu (KL-4) |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine für Scheiben 0–4 [no-adr]-fähig; neuer ADR
  „BriefingSubscription-Konvergenz" wird in Scheibe 5 angelegt.
- **Rationale:** Scheiben 0–4 sind additive Feld-für-Feld-Konvergenz ohne
  neues Architekturmuster (Legacy-Stilllegung, Dataclass-Extraktion,
  Dual-Write/Dual-Read) — analog zu #1231, das ebenfalls ohne ADR auskam.
  Scheibe 5 führt jedoch erstmals ein **gemeinsames Datenmodell mit
  Diskriminator-Feld und neuer Ziel-Persistenz** ein
  (`data/users/<uid>/briefings/<id>.json` ersetzt zwei bisherige
  Persistenzmuster: 1-Datei-pro-Trip vs. Sammel-Array) — das ist ein
  Architektur-Grundsatzentscheid (Store-Konsolidierung, Migrationsstrategie,
  Kompatibilitäts-Fenster) und braucht daher einen eigenen ADR, angelegt im
  Scheibe-5-Workflow.

## Changelog

- 2026-07-13: Initial spec erstellt — Issue #1250, Phase 3 von Epic #1230,
  Programm-Spec über 8 Scheiben nach Muster #1231, basierend auf
  `docs/context/feat-1250-briefing-subscription.md` (Ist-Vermessung +
  Analyse 2026-07-13).
