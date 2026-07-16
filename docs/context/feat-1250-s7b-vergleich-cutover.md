# Context: feat-1250-s7b-vergleich-cutover

Issue **#1250** (Phase 3 von Epic #1230), **Scheibe 7b** — Persistenz-Cutover der Entität
**`vergleich`** (ComparePresets). Schwester-Scheibe zu **S7a-route** (Trips, ✅ live `22732a1a`
+ Fixups `fac27f55`/`124608dc`, Staging-VERIFIED, Prod-Deploy koordiniert ausstehend).

- **Elternkontext (verbindlich, nicht dupliziert):** `docs/context/feat-1250-s7-cutover.md`
  (F-A/F-B/F-C, Design-Prinzipien, Renderer-Dispatch, R1–R7).
- **Programm-Spec:** `docs/specs/modules/issue_1250_briefing_subscription.md` · **ADR:** `docs/adr/0023-briefing-subscription-shared-model.md`.
- **S7a-Template (direktes Vorbild):** Commit `22732a1a` (`internal/store/trip.go`, `src/app/loader.py`,
  Migration-Refresh, Kaskade ~40 Dateien, `tests/test_briefing_route_cutover.py`).

## Request Summary

`vergleich`-Presets von der **einen Array-Datei** `data/users/<uid>/compare_presets.json` auf
**per-Datei** `data/users/<uid>/briefings/<id>.json` (`kind="vergleich"`) umstellen — Lesen **und**
Schreiben, Go **und** Python, atomar im selben Deploy, mit Prod-`--execute`-Migration. Damit ist
`briefings/` für **beide** kinds die einzige Persistenz-Wahrheit.

## Kern-Differenz zu S7a (das ist der eigentliche Aufwand)

| | S7a route (Trip) | **S7b vergleich (ComparePreset)** |
|---|---|---|
| Alt-Speicherform | **per-Datei** `trips/<id>.json` | **EIN Array** `compare_presets.json` (alle Presets eines Nutzers) |
| Cutover-Lesen | Repoint Verzeichnis 1:1 | Array **zerlegen**: alle `briefings/*.json` mit `kind==vergleich` einsammeln |
| Cutover-Schreiben | `SaveTrip` = eine Datei | `SaveComparePresets([]…)` schreibt bisher das **ganze Array** → muss je Preset eine Datei schreiben **und verwaiste Dateien entfernen** |
| Löschen | `DeleteTrip` = echtes File-Remove (schon da) | `DeleteComparePresetHandler` löscht per **Array-minus-eins** (`SaveComparePresets(filtered)`) → braucht echtes Per-File-Remove (**F-A**) |

→ S7b ist **kein 1:1-Template**. Die Array→Per-Datei-Übersetzung ist neu und die Delete-Semantik
ist die gefährlichste Stelle.

## Related Files — Cutover-Ziele (Anker & Schreibpfade)

**Zwei Pfad-Anker (hier kippt die Wahrheit):**
| Datei:Zeile | Rolle |
|---|---|
| `internal/store/compare_preset.go:12` `comparePresetsFile()` | Go-Pfad-Anker → `briefingsDir()` + kind-Filter |
| `src/app/loader.py:283` `load_compare_presets()` | Python-Lese-Anker → `briefings/` (kind=vergleich) |

**Split-Brain-kritische SCHREIBER (müssen ZUSAMMEN kippen — F-B):**
| Datei:Zeile | Rolle |
|---|---|
| `internal/store/compare_preset.go:122` `SaveComparePresets` | Go-Array-Schreiber (+ verwaiste-Datei-Reconcile) |
| `internal/handler/compare_preset.go:450` `DeleteComparePresetHandler` | **DELETE-Pfad** — F-A: echtes Per-File-Remove statt Array-Rewrite |
| `internal/store/migrate_1258.go:108-141` | RMW-Migration, ComparePreset-Hälfte liest noch `compare_presets.json` |
| `src/services/scheduler_dispatch_service.py:154` `save_compare_preset_status` | Python-RMW (umgeht den Loader!) |
| `src/services/scheduler_dispatch_service.py:198` `save_compare_preset_pause` | Python-RMW (umgeht den Loader!) |

**LESER (folgen dem Anker automatisch, wenn über Store/Loader):**
- Go: `internal/handler/compare_preset.go` (List/Create/Update/Get/State), `internal/handler/briefing_subscription.go` (S6-API), `internal/store/compare_preset.go:58` `LoadComparePresets`.
- Python via `load_compare_presets`: `compare_alert.py`, `compare_official_alert.py`, `compare_radar_alert.py`, `scheduler_dispatch_service.py:47` (`run_compare_presets_daily`), `api/routers/scheduler.py`, `compare_slot_scheduler.py:58` (`presets_due_for_hour`, arbeitet auf In-Memory-Liste).

## Versteckte / „vergessene" Konsumenten (Adversary-Pflichtziele — S7a hatte hier 6)

1. **`api/routers/validator.py:56` — INVERTIERTER GUARD.** Gibt heute bewusst `None` für
   `kind=="vergleich"` in `briefings/` zurück (S7a-Zaun). Nach dem Cutover wohnt vergleich in
   `briefings/` → der External-Validator würde **jedes vergleich still überspringen/404**. **MUSS invertiert werden.**
2. **`src/services/preview_service.py:54-60` — KEIN kind-Guard.** Liest `get_briefings_dir()` und
   parst Einträge als **Trip**. Sieht vergleich heute nie; nach Cutover würde es ein vergleich als
   Trip fehl-lesen. Latent → kind-Filter nötig.
3. **`internal/store/migrate_1258.go:108-141`** — Trip-Hälfte kommt mit vergleich-in-briefings klar,
   die ComparePreset-Hälfte liest noch `compare_presets.json` (falscher/leerer Ort nach Cutover).
4. **In-place-Migrationsskripte** `migrate_1191/1244/1231/1258_official_warnings` — globben
   `*/compare_presets.json` + `write_text`. Post-Cutover No-op, aber gegen Pre-Cutover-Daten
   **re-materialisieren sie die Legacy-Datei** neben `briefings/` → Split-Brain wieder offen.
5. **`scripts/seed_validator_archive.py:120-122`** — merged in `compare_presets.json` → würde die
   Legacy-Datei nach dem Cutover neu anlegen. Auf `briefings/` umlenken.
6. **`scripts/migrate_1250_briefings.py`** — heute die **Split-Brain-Quelle**: kopiert vergleich nach
   `briefings/`, löscht `compare_presets.json` aber nie; der Live-Lesepfad zeigt noch auf Legacy.
   Cutover muss die Anker umlegen + diesen Rest neutralisieren. **Refresh = Wipe+Remigrate** (F-C).
7. **`internal/scheduler/scheduler.go` + `api/routers/scheduler.py`** — `compare_presets_daily`-Cron
   ist **indirekter** Schreiber (treibt die zwei Python-RMW), keine Datei erwähnt.

## AC-30-Zäune, die S7b INVERTIERT (S7a hat sie absichtlich gesetzt)

- `src/app/loader.py:1023-1028` `get_briefings_dir()`-Docstring kodifiziert „vergleich bleibt auf `compare_presets.json`".
- `tests/test_briefing_route_cutover.py:306` — AC-30-Guard-Test, **asserted** vergleich bleibt auf Legacy → muss invertiert werden.
- `api/routers/validator.py:56` — s. #1 oben.

## Test-Fixtures-Kaskade (Blast-Radius)

- **Go:** viele Tests seeden via `s.SaveComparePresets()`/`LoadComparePresets()` (folgen dem Store-Cutover automatisch). Die mit **hartkodiertem** `compare_presets.json`-Pfad brechen: `compare_preset_official_alerts_test.go:91/407/577` (`:577` prüft **Datei-Abwesenheit** = Delete-Semantik!), `compare_preset_prev_schedule_test.go`, `compare_preset_hourly_enabled_test.go`, `compare_preset_weekday_test.go`, `_slot_migration_test.go`, `_display_config_test.go`, `_forecast_hours_test.go`, `_nil_coercion_test.go`.
- **Python (hartkodierter Pfad, brechen):** `test_migrate_1250_briefings.py`, `test_briefing_route_cutover.py:306`, `test_compare_auto_pause_end_date.py`, `tdd/test_compare_preset_loader.py`, `tdd/test_compare_preset_send.py`, `tdd/test_compare_radar_alert.py`, `tdd/test_compare_official_alert.py`, `tdd/test_issue_461/509/511/583/649/1169/1170_*`, `tdd/test_corridor_migration.py`, `tdd/test_migrate_*`, `tdd/test_telegram_style_config_roundtrip.py`, `tdd/test_throttle_store.py` u.a.
- **conftest:** referenziert Presets NICHT direkt; S7a spiegelt committете Fixtures via `tests/integration/conftest.py` nach `briefings/` — analoges Muster für vergleich prüfen.

## Existing Patterns / Dependencies

- **Dateisystem = Integrationspunkt** (keine DB) — Go+Python teilen dieselben Dateien.
- **Migration** kopiert rohe Dicts + `kind` verlustfrei (S5); Refresh = **Wipe+Remigrate** (nicht `--force`, sonst Waisen von Post-S5-Löschungen).
- **Renderer-Dispatch vergleich:** `send_one_compare_preset` → `ComparisonEngine.run` + `render_compare_email` (`comparison.py:32`) — Template getrennt (E9), **nicht** angefasst.
- **`briefings/`-Daten NIE committen** (host-service-verwaltet, `claude-gregor`-owned; `git reset --hard` scheitert „Permission denied", brach Staging-Deploy) → gitignored, per-Host von der Migration befüllt.
- **Deploy** per-Host, `flock`-serialisiert (`deploy-gregor-prod.sh`) — atomarer Migrationsschritt: stop-writers → wipe+remigrate → start-new-code.

## Risks & Considerations (für /20-analyse)

- **F-A (CRITICAL):** Array-Delete → echtes Per-File-Remove. `SaveComparePresets` muss beim
  Schreiben verwaiste `briefings/`-Dateien der Entität abgleichen, ODER `DeleteComparePresetHandler`
  auf echtes `os.Remove` umstellen (wie S7a `DeleteTrip`). **Kernrisiko.**
- **F-B (CRITICAL):** vergessener Schreibpfad = Split-Brain. Alle 5 Schreiber oben zusammen kippen.
- **F-C (HIGH):** Migration Wipe+Remigrate, nie `--force`.
- **R-Validator/Preview:** invertierter Guard (#1) + fehlender kind-Filter (#2) — beides
  nutzer-/validator-sichtbar, S7a-Analogfehler.
- **R-Migrationsskripte:** die vier in-place-Skripte + Seed dürfen die Legacy-Datei nicht
  wiederauferstehen lassen.
- **R-Reihenfolge/Deploy:** S7a-Prod-Deploy war zuletzt an #1260 gekoppelt (inzwischen live/zu);
  S7a+S7b schreiben in **dasselbe** `briefings/`, nur andere Entität — Migration deckt beide `kind`
  ab. Als Phase-8-Deploy-Koordination behandeln, kein S7b-Vorbedingung.
- **R-Anti-Runaway:** S7a-Developer verhakte sich 2× in Vollsuiten-Polling (46+82 Min) → beim
  Developer-Agent **harter Riegel: keine Vollsuite, keine Hintergrund-Polls**, gezielte Tests only.
- **R7 — KEINE aktiven Produktiv-User** → Migration risikoarm bzgl. Nutzer-Impact, Sorgfalt bleibt.

## Analysis (Plan/Sonnet-Gegenprobe, Risiko MEDIUM-HIGH)

### Type
Feature (Scheibe eines PO-freigegebenen Programms, #1250 Phase 3).

### Technischer Ansatz — Tech-Lead-Entscheidungen

1. **F-A: per-Datei-API, NICHT reconcile-on-save.** `SaveComparePresets`(Array) wird ersetzt durch
   `LoadComparePreset(id)` / `SaveComparePreset(one)` / `DeleteComparePreset(id)` — strukturell 1:1
   `internal/store/trip.go:162-269` (`LoadTrip`/`SaveTrip`/`DeleteTrip`). **ADR-0023 Entscheidung 2
   verlangt genau das** („per-Datei, Store-Muster wie Trip-Store"). Reconcile verworfen: reale
   Datenverlust-Race — Go `SaveComparePresets([A_updated, B_stale])` würde eine gerade von Python
   per-Datei geschriebene B-Datei mit dem veralteten Load-Snapshot überschreiben (T0-Load → T1-Python-
   Write → T2-Go-Reconcile). Per-Datei-API macht Löschen nur über explizit benanntes
   `DeleteComparePreset(id)` möglich (grep-bar, nicht implizit).
2. **`LoadComparePresets` (Aggregat) globt `briefings/*.json` + Filter `kind=="vergleich"`** — **invers**
   (nur vergleich einschließen, NICHT „alles außer route": Trip beansprucht `kind==""`/`"route"`, sonst
   Doppelklassifizierung blank-kind-Dateien). Muster: `trip.go:109-160` `LoadTrips`.
3. **`SaveComparePresets` (Plural) bleibt als dünner Kompat-Wrapper** (Loop über `SaveComparePreset`,
   **ohne** Delete) für die ~40 bestehenden Go-Test-Call-Sites — minimiert Test-Churn. Der DELETE-Pfad
   geht NIE über den Wrapper, sondern über `DeleteComparePreset(id)`.
4. **Python:** `load_compare_presets` (`loader.py:261-295`) auf Glob+kind-Filter (Muster
   `load_all_trips:1235-1281`); die zwei RMW-Schreiber `save_compare_preset_status`/`_pause`
   (`scheduler_dispatch_service.py:137,178`, hardcoden den Pfad, umgehen den Loader) auf per-Datei
   `briefings/<id>.json` — durch Einzeldatei sogar **einfacher** (keine Array-Iteration).
5. **`load_compare_presets` unter Glob = partial-tolerant** (eine korrupte Einzeldatei überspringen wie
   `load_all_trips`, statt den ganzen `run_compare_presets_daily`-Lauf abzubrechen). **Verhaltensänderung
   ggü. heute** (Array-atomar → 1 Korruptes killte alle) — bewusst, PO im Spec-Approval nennen.
6. **Guard-Inversionen:** `validator.py:56` (None→vergleich laden), `preview_service.py:54-60`
   (kind-Filter ergänzen, parst sonst vergleich als Trip), `tests/test_briefing_route_cutover.py:296-315`
   (AC-30-Zaun invertieren), `seed_validator_archive.py:97-122` (per-Datei nach `briefings/` statt Merge
   in `compare_presets.json`, wie schon der Trip-Teil `:71-95`).

### CRITICAL — Migrations-Datenverlust-Fund (in keinem Vor-Doc, budgetrelevant)
`scripts/migrate_1250_briefings.py` ist **NICHT kind-scoped**: `_wipe_briefings` (:235-247) löscht per
Glob **alle** `briefings/*.json` ungeachtet `kind`; `_collect_plan` (:163-223) plant in **jedem** Lauf
**beide** Quellen (`*/trips/*.json` **und** `*/compare_presets.json`). Seit dem S7a-Prod-Cutover ist
`trips/*.json` **eingefroren** (kein Schreiber mehr). Ein S7b-`--refresh --execute` würde damit **auch
alle route-Einträge** in `briefings/` löschen und aus dem **veralteten** `trips/*.json`-Snapshot neu
schreiben → **jeder seit S7a live erstellte/geänderte/gelöschte Trip ginge verloren**. Pfad **ungetestet**
(`grep refresh tests/test_migrate_1250_briefings.py` = 0 Treffer). **Harte Vorbedingung:** Refresh muss
VOR dem S7b-Deploy kind-scoped werden (nur `kind==vergleich` wipen/remigrieren, route unberührt) + Test.

### Affected Files (Änderungstyp)
| Datei | Typ | Beschreibung |
|---|---|---|
| `internal/store/compare_preset.go` | MODIFY | Load/Save/Delete-Neubau per-Datei (~120-150 LoC) |
| `internal/handler/compare_preset.go` | MODIFY | 4 Handler auf Einzel-API (~40-60 LoC, teils Vereinfachung) |
| `internal/handler/briefing_subscription.go` | MODIFY | 2 Zweige (~20-30 LoC) |
| `internal/store/migrate_1258.go` | MODIFY | Preset-Hälfte auf per-Datei-Loop, entfernt Rohbytes-Hack `:116-127` (~20-30) |
| `src/app/loader.py` | MODIFY | `load_compare_presets` Glob+kind-Filter (~30-40) |
| `src/services/scheduler_dispatch_service.py` | MODIFY | 2 RMW-Schreiber per-Datei (~±10 je) |
| `api/routers/validator.py`, `src/services/preview_service.py` | MODIFY | Guard-Inversion/kind-Filter (~10-20 je) |
| `scripts/seed_validator_archive.py` | MODIFY | Preset-Seed per-Datei nach `briefings/` (~10-20) |
| `scripts/migrate_1250_briefings.py` | MODIFY | **kind-scoped Refresh** (`--kind=vergleich`), ~40-60, neue AC |
| `tests/…` (Go+Python, ~15-20 Dateien) | MODIFY/CREATE | Fixture-Kaskade + Repro-Tests (~150-250 test-LoC) |

### Scope Assessment
- **Prod-LoC ~260-320** (Store+Handler+Guards ~220-260 **plus** Migrations-Scoping ~40-60).
- **Über 250-LoC-Budget** → Override (500) nötig, **PO-Freigabe im Spec-Approval** (Regel: kein Override ohne Permission).
- Risk: **MEDIUM-HIGH** (Prod-Datenmigration + neuer Migrations-Datenverlust-Vektor; R7 nimmt Nutzer-Impact, Rollback via Alt-Stores).

### Dependencies / Reihenfolge
Code: Store (Go+Python) → Handler/Service-Aufrufer → Guard-Inversionen → Migrations-Scoping → Tests →
Deploy-Runbook. Deploy: **stop-writers → wipe+remigrate (kind-scoped vergleich) → start-new-code**, alle
vergleich-Schreiber in EINEM Deploy. Unabhängig von der S7a-Prod-Deploy-Koordination (disjunkte kinds).

### Open Questions (für Spec/PO-Approval)
- [ ] **PO:** LoC-Budget-Override (→500) freigeben — Slice ist größer als Standard wegen des
  Migrations-Datenverlust-Fixes (als Teil des 'go' im Spec-Approval).
- [ ] **PO (plain):** Verhaltensänderung akzeptieren — eine defekte Einzel-Vergleichsdatei wird künftig
  übersprungen statt den ganzen Tageslauf zu blockieren.
- [x] F-A-Strategie: per-Datei-API (ADR-0023-gedeckt) — entschieden.
- [x] `SaveComparePresets`-Plural als Test-Kompat-Wrapper behalten — entschieden.
- [x] Vier In-Place-Skripte (`migrate_1191/1231/1244/1258_official_warnings`): minimaler Doku-Guard
  (R7 stützt), keine Voll-Umleitung — entschieden.

## Nächster Schritt
`/30-write-spec` — vollständige Spec mit AC-N (per-Datei-API, Guard-Inversionen, kind-scoped Refresh,
atomarer Deploy), dann PO-Freigabe (ACs deutsch + Budget-Override + Verhaltensänderung).
