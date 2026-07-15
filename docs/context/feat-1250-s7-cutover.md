# Context: feat-1250-s7-cutover

Issue #1250 (Phase 3 von Epic #1230), **Scheibe 7** — die letzte Scheibe.
Programm-Spec: `docs/specs/modules/issue_1250_briefing_subscription.md` (S7 = §176-183,
AC-23/24; KL-6 lud den atomaren Cutover + volles Modell + Prod-Migration in S7).
ADR: `docs/adr/0023-briefing-subscription-shared-model.md`. Vorstufen S0–S6 live (HEAD `4f4bedc1`).

## Request Summary

`briefings/<id>.json` zur **einzigen Persistenz-Wahrheit** machen (Lesen+Schreiben, Go **und**
Python, atomar) + Prod-Migration am Deploy; plus Scheduler-Vereinheitlichung (ein Cron-Einstieg
statt zwei, Dispatch per `kind`). Die S6-Fortschreibung (KL-6) verwies den atomaren Cutover
hierher.

## Kernbefund 1 — Cutover ⊥ Scheduler-Merge (→ Aufteilung gerechtfertigt)

Der **Go-Scheduler liest KEINEN Store** (`internal/scheduler/scheduler.go`): er enumeriert nur
User (`ListUserIDs()` :131) und macht **HTTP-POST** an die Python-Endpoints
(`triggerEndpointForUser` :286, `PythonCoreURL` default localhost:8000). Die echten Store-Loads
passieren in **Python** (`run_compare_presets_daily` → `compare_presets.json`; Trip-Reports →
`load_all_trips`). **Folge:** Der Persistenz-Cutover (Python/Go lesen `briefings/`) ist von der
Scheduler-Vereinheitlichung **entkoppelt** — die zwei Cron-Einstiege können bleiben, nur die
Lese-/Schreibpfade ziehen um. **Empfehlung: S7 aufteilen** — **S7a = Cutover**, **S7b = Scheduler-Merge** (AC-23/24), orthogonal danach.

## Kernbefund 2 — die Spec-Komplexität von S7 basiert auf falschen Prämissen

- **`activity`↔`profil`-Konvertierung existiert NICHT und wird NICHT gebraucht.** Trip-`activity`
  ist ein Naismith-**Tempo**-Key (`fahrrad_15/20/25` + Freeform, `internal/model/naismith.go:39`),
  Preset-`profil` ist ein Scoring-**Profil** (`wintersport`/`wandern`/`allgemein`/`summer_trekking`,
  `src/app/profile.py:23`). **Disjunkte Namensräume, kein Mapping** (Grep bestätigt). Die Spec
  (§87 „einzige echte Wertkonvertierung") ist falsch — sie verwechselte zwei unabhängige Felder.
  Die EINZIGE reale Konvertierung ist **profil-intern** (FE-lowercase→Engine-uppercase,
  `normalizeProfile` `internal/handler/compare_preset.go:86-103`, Python `_parse_activity_profile`
  `loader.py:1563`) — die bleibt unverändert erhalten.
- **`points`-Diskriminator existiert nicht** (reines Zielkonzept). Heute: route → `stages[].waypoints[]`,
  vergleich → `location_ids`. Kein Umbau nötig.
- **`kind` ist schon additiv** auf beiden Modellen (`trip.go:163`, `compare_preset.go:107`, S5).

**Folge:** Der Cutover braucht **KEIN volles typisiertes Union-Modell**. `briefings/<id>.json`
trägt einen kind-getaggten Trip- bzw. Preset-Dict (Migration kopierte rohe Dicts). Man lädt/speichert
per `kind` in die **bestehenden** `Trip`/`ComparePreset`-Strukturen — dasselbe Dispatcher-Muster wie
S6. Die Feld-Konvergenz zu EINER Struktur ist NICHT nötig für den Cutover (Folge-Arbeit, falls je gewollt).

## Related Files (Cutover-Ziele)

| Datei:Zeile | Rolle im Cutover |
|---|---|
| `src/app/loader.py:283` `load_compare_presets` | Python-Lesepfad Presets → auf `briefings/` (kind=vergleich) umlenken |
| `src/app/loader.py:1225` `load_all_trips` (`get_trips_dir`) | Python-Lesepfad Trips → auf `briefings/` (kind=route) |
| `src/app/loader.py:1476` `save_trip` | Python-Schreibpfad Trip → `briefings/<id>.json` |
| `src/services/scheduler_dispatch_service.py:124-201` `save_compare_preset_status`/`_pause` | Python-Schreibpfad Preset-Status → `briefings/<id>.json` |
| `internal/handler/briefing_subscription.go` (S6) | Go-API dispatcht per kind über Alt-Stores → auf `briefings/` umstellen |
| `internal/store/trip.go`, `compare_preset.go` | Go Load/Save → `briefings/` (oder `LoadBriefing`/`SaveBriefing` scaffold verdrahten) |
| `internal/store/briefing_subscription.go:20,42` `LoadBriefing`/`SaveBriefing` | S5-Gerüst, **null Prod-Aufrufer** — hier zu verdrahten |
| `scripts/migrate_1250_briefings.py` | Prod-Migration am Deploy; **Staleness: Skip-wenn-kind frischt NICHT auf** → Refresh-Modus nötig |
| `internal/scheduler/scheduler.go:91,100` (S7b) | zwei Cron-Einstiege `tripReports`/`comparePresetsDaily` → einer |
| `internal/handler/scheduler_status.go` + `scheduler.go:387` (S7b) | `/api/scheduler/status` `last_run` (in-memory, ephemer) — AC-24 |

## Existing Patterns / Dependencies

- **Dateisystem = Integrationspunkt** (kein DB). Go+Python teilen die Dateien.
- **Migration** kopiert rohe Dicts + `kind` verlustfrei (S5). Idempotenz = Skip-wenn-`kind` (Byte/Existenz).
- **Renderer-Dispatch:** route → `NotificationService.send_trip_report` (`notification_service.py:211`,
  `trip_report.py`); vergleich → `send_one_compare_preset` → `ComparisonEngine.run` + `render_compare_email`
  (`comparison.py:32`). Templates getrennt (E9/KL-1).
- **Deploy** ist per-Host, `flock`-serialisiert (`deploy-gregor-prod.sh`) — natürlicher Ort für einen
  atomaren Migration-Schritt (stop → migrate → start-new-code).

## Risks & Considerations (für /20-analyse)

- **R1 — Atomarer Umschalt / Split-Brain:** Go+Python müssen im selben Deploy auf `briefings/` kippen,
  Migration dazwischen, keine Traffic-Fenster. Design: Migration-Schritt in `deploy-gregor-prod.sh`
  zwischen Build und Service-Restart? Oder Dual-Read-Fallback (liest `briefings/`, sonst Alt-Store)?
- **R2 — Migrations-Staleness (S5-Handoff):** die idempotente Migration (Skip-wenn-`kind`) frischt eine
  seit S5 geänderte Quelle NICHT auf. Der Cutover-Lauf MUSS `briefings/` aus dem AKTUELLEN Alt-Store
  frisch schreiben (Refresh/Force-Modus **oder** `briefings/` vor dem Lauf leeren) — sonst Cutover auf
  veraltete Daten = Datenverlust. **Kernrisiko.**
- **R3 — Datenverlust bei der Migration (GR221):** verlustfrei = rohe Dicts; Backup vor `--execute`;
  Rollback = Alt-Stores bleiben liegen. Zwei-Nutzer-Isolation.
- **R4 — Rückweg:** Alt-Stores werden im Cutover NICHT gelöscht (Rollback-Fähigkeit); erst später aufräumen.
- **R5 — AC-24 Observability:** `last_run` ist in-memory/ephemer; bei S7b-Merge nicht zusätzlich verlieren
  (Heartbeat-Asymmetrie: nur `comparePresetsDaily` pingt).
- **R6 — ADR-0023 Entscheidung 4 falsch:** „volles typisiertes Union-Modell + points + activity↔profil"
  beruht auf falscher Prämisse → in S7 zu korrigieren (Dispatch per kind über bestehende Modelle).
- **R7 — KEINE aktiven Produktiv-User** (Projekt-Memory) → Migration ist risikoarm bzgl. Nutzer-Impact,
  aber Sorgfalt bleibt (Bestandsdaten der Test-/Eigen-Accounts).

## Analysis (Plan-Gegenprobe bestätigt, Risiko MITTEL)

### Type
Feature (Scheibe eines PO-freigegebenen Programms).

### Zuschnitt-Empfehlung (die der PO an die Analyse delegiert hat)
- **S7b (Scheduler-Merge) = OPTIONAL, separate spätere Scheibe.** Der Go-Scheduler liest keinen Store;
  nach dem Cutover triggern die zwei bestehenden Cron-Einträge dasselbe Python, das `briefings/` liest —
  verhaltensneutral. Wert von S7b: nur Entdopplung + Observability-Symmetrie (AC-24). Niedrige Priorität.
- **Der Cutover selbst nach ENTITÄT teilen (empfohlen):** **S7a-route** (Trips `trips/*.json` → `briefings/`)
  zuerst, auf Prod validiert, **dann S7a-vergleich** (Presets `compare_presets.json` → `briefings/`).
  Begründung: (1) je Cutover <250 LoC (kein Override); (2) kleinerer Blast-Radius je Prod-Datenmigration;
  (3) disjunkte Namensräume → jede Entität read+write-konsistent umstellbar; Go `ListBriefingsHandler`
  liest dann route aus `briefings/`, vergleich noch aus Alt-Store — konsistent per kind.
  **NICHT** nach read-then-write teilen (ein Read-only-Vorlauf läse stale `briefings/`, das kein Writer
  aktualisiert → divergiert beim ersten Alt-Store-Write). Read+Write EINER Entität kippen zusammen.

### Design (Lean-Cutover, drei Nicht-Verhandelbare)
1. **Repoint** der Lese-/Schreibpfade EINER Entität auf `briefings/<id>.json`, geladen per `kind` in die
   BESTEHENDEN `Trip`/`ComparePreset`-Strukturen (kein Union-Modell, keine activity↔profil-Konvertierung —
   disjunkt; ADR-0023 Entscheidung 4 korrigieren). Go: `LoadTrip`/`SaveTrip` (bzw. `LoadComparePresets`/
   `SaveComparePresets`) auf `briefingsDir()` + kind-Filter umbiegen. `BriefingSubscription`-Gerüst +
   `LoadBriefing`/`SaveBriefing` bleiben ungenutzt → **explizit als tot markieren**.
2. **Refresh = WIPE + Remigrate** (nicht `--force`): `briefings/` der Entität leeren, dann frisch aus dem
   AKTUELLEN Alt-Store remigrieren (Backup vorher). Sicher, weil `briefings/` reine Projektion ist (kein
   nativer Schreiber). Verhindert Waisen (F-C).
3. **Atomar im Deploy:** ALLE Schreibpfade der Entität in EINEM Deploy kippen; Reihenfolge
   **stop-writers → wipe+remigrate → start-new-code**. Alt-Stores bleiben liegen (Rollback).

### Gefährlichste Fallen (Adversary-Pflichtziele)
- **F-A (CRITICAL, vergleich):** `SaveComparePresets` (`store/compare_preset.go:122-141`, `:449`) schreibt das
  ganze Array — Per-File-`briefings/` braucht bei DELETE ein echtes Datei-Remove (Delete-Diff), sonst
  kehrt ein gelöschtes Preset zurück.
- **F-B (CRITICAL):** ein vergessener Schreibpfad = Split-Brain (Python-Versandstatus Alt-Store vs. Go-Read
  `briefings/`). Für route: Go `SaveTrip` + Python `save_trip`. Für vergleich: Go `SaveComparePresets` +
  Python `save_compare_preset_status/_pause`.
- **F-C (HIGH):** Force statt Wipe → Waisen-`briefings/`.

### Scope (S7a-route)
- Files: ~5-6 (Go store trip.go + Python loader.py `load_all_trips`/`save_trip` + Migration Wipe-Refresh +
  Deploy-Doku + Tests). LoC ~150-200 (unter Budget).
- Risk: **MEDIUM** (Prod-Datenmigration, aber R7 nimmt Nutzer-Impact; Rollback via Alt-Stores).

### Open Questions / Spec
- [ ] Bestätigung Zuschnitt: erst S7a-route, dann S7a-vergleich, S7b optional (PO-Nicken).
- [ ] Dual-Read-Fallback (briefings→sonst Alt) als Netz JA/NEIN — Empfehlung: nein (Wipe+Remigrate macht
  briefings/ vollständig; Fallback reintroduziert Split-Brain-Vektor). Fixture-Roundtrip-Test statt Fallback.
- [ ] Prod-Migration-Schritt: manuell als `claude-gregor` im Deploy (wie S5) vs. in `deploy-gregor-prod.sh`
  (henemm-infra-Änderung). Empfehlung: manueller dokumentierter Schritt (kein infra-Repo-Change nötig).
