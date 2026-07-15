# ADR-0023: Gemeinsames `BriefingSubscription`-Modell (`kind`-Diskriminator) + `briefings/`-Persistenz

- **Status:** Akzeptiert (PO-„freigabe" 2026-07-15)
- **Datum:** 2026-07-15
- **Bezug:** GitHub-Issue #1250 (Scheibe 5, Phase 3 von Epic #1230
  „Briefing-Abo-Chassis"), Spec `docs/specs/modules/issue_1250_briefing_subscription.md`
  (AC-16–AC-19, Zielmodell §72-90), Analyse `docs/context/feat-1250-s5-kind-migration.md`;
  verwandt [ADR-0021](0021-shared-deviation-alert-engine.md) (geteilte Alert-Engine),
  [ADR-0003](0003-multi-tenant-isolation.md) (per-User-Isolation). Vorstufen live:
  S1 (Preset-Kontrakt), S2 (Pause-Konvergenz), S3 (Auto-Pause), S4 (Trip-Konvergenz).

## Kontext

Trip und ComparePreset sind fachlich stark konvergiert (nach S2/S4 teilen sie ~16
Felder: Korridore, Pause, flache Slot-/Kanal-Felder, `end_date`, offizielle Warnungen).
Das Epic-Ziel ist **ein** Datenmodell `BriefingSubscription{kind:"route"|"vergleich"}`,
das Trip und Vergleich ersetzt (Persistenz `data/users/<uid>/briefings/<id>.json`,
1 Datei/Entität). Die Umstellung erfolgt in Scheiben: S5 = Modell-Gerüst + `kind` +
verlustfreie Daten-Migration; S6 = API-Konsolidierung (liest das Modell); S7 =
Scheduler-Vereinheitlichung.

Zwei Randbedingungen prägen die Entscheidung: (1) Go besitzt **keinen** Auffang-Bucket
für unmodellierte Felder (anders als Python `raw`/`extra`) — ein typisiertes Union-Struct,
das nicht jedes Feld trägt, verliert Daten beim Roundtrip. (2) Datenverlust ist das
Kernrisiko des Projekts (BUG-DATALOSS-GR221).

## Entscheidung

1. **`BriefingSubscription` wird als `kind`-diskriminiertes gemeinsames Modell eingeführt.**
   `kind` (`"route"`/`"vergleich"`) ist additiv und unterscheidet nur die kind-spezifischen
   Felder (`route`: stages/aggregation/…; `vergleich`: location_ids/…). Die Renderer-Templates
   bleiben getrennt (E9).
2. **Persistenz `data/users/<uid>/briefings/<id>.json`** (per-Datei, Store-Muster wie Trip-Store).
3. **Migration verlustfrei über rohe Dicts** (`scripts/migrate_1250_briefings.py`, Vorbild
   `migrate_1231_corridors.py`): Dry-Run-Default, tar.gz-Backup vor `--execute`, idempotent
   (Byte-/Existenz-basiert), strikt pro Nutzer, kein Löschen der Altdaten (RMW, kein Replace).
4. **Scope-Grenze S5 ↔ S6 (bewusst):** S5 liefert die Migration + `kind` + ein **verlustfreies
   Gerüst-Modell** (typisierte Diskriminator-/Kern-Felder + Raw-Auffang `map[string]json.RawMessage`,
   das jedes weitere Feld erhält). Das **volle typisierte Union-Modell** (alle ~40 Felder explizit,
   `points`-Sum-Type mit Custom-Unmarshal, `activity`↔`profil`-Konvertierung) entsteht in **S6**,
   wo es tatsächlich gelesen/geschrieben wird. Begründung: kein S5-AC testet das volle Modell; es
   ohne Konsumenten zu bauen, bläht die Scheibe und schafft Risiko.
5. **Koexistenz:** In S5 lesen App/Scheduler weiter aus `trips/`+`compare_presets.json`; die
   `briefings/`-Dateien entstehen daneben (verhaltensneutral).

   **Fortschreibung 2026-07-15 (S6-Analyse, `docs/context/feat-1250-s6-api-konsolidierung.md`):**
   Die ursprüngliche Formulierung „S6 schaltet die Lesepfade um" wird korrigiert. **S6 schaltet
   die Persistenz NICHT um.** Go-API und Python-Core teilen dieselben Alt-Dateien (Dateisystem =
   einziger Integrationspunkt), und Python **schreibt** die Alt-Stores auch — Versand-Status
   (`save_compare_preset_status`/`_pause`, `scheduler_dispatch_service.py:124-201`) und
   Inbound-Command-Trip-Edits (`save_trip`, `loader.py:1476`) — und zieht erst in S7 um. Ein
   Go-only-Umschalt auf `briefings/` erzeugt **bidirektionalen Split-Brain** (FE-Edit für
   Python-Versand unsichtbar UND Python-Statusschreibungen für Go/FE unsichtbar) → verletzt die
   Programm-Invariante „jede Scheibe verhaltensneutral". Verworfene Alternativen: Go-Dual-Write
   (Python schreibt weiter nur alt → `briefings/` driftet); S6+S7 zusammen (sprengt
   Scheiben-Granularität, hoher GR221-Risk). **Korrigierte Grenze:** S6 liefert nur die
   `kind`-diskriminierte **API-Oberfläche** (`/api/briefings*`) als Dispatcher über die
   **bestehenden** Stores (`LoadTrip`/`SaveTrip`, `LoadComparePresets`/`SaveComparePresets`);
   Alt-Endpoints werden dünne Delegates. Der **atomare Cutover** Lese+Schreibpfade (Go **und**
   Python) auf `briefings/<id>.json` inkl. Prod-`--execute` ist **S7**. `LoadBriefing`
   (`internal/store/briefing_subscription.go`) bleibt in S6 unverdrahtet. **Bedingung aus der
   Analyse:** `kind` wird auf `/api/briefings*` **explizit** getragen (POST-Body bzw.
   Query-Param), nie per Store-Probing geraten — Trip-ID == Preset-ID ist real möglich (s.
   Migrations-F001, `scripts/migrate_1250_briefings.py`). Das volle typisierte Union-Modell
   (~40 Felder, `points`-Sum-Type) bleibt damit S7-Arbeit; S6 nutzt die schon typisierten
   `model.Trip`/`model.ComparePreset`.

   **2. Fortschreibung 2026-07-15 (S7-Analyse, `docs/context/feat-1250-s7-cutover.md`, Plan-Gegenprobe):**
   Entscheidung 4 wird **teilweise revidiert**. Das **volle typisierte Union-Modell** (~40 Felder,
   `points`-Sum-Type, `activity`↔`profil`-Konvertierung) wird **NICHT gebaut** — es ist obsolet:
   (a) kein Konsument braucht eine Einzelstruktur (`ListBriefingsHandler` baut schon `[]interface{}`
   gemischt); (b) `activity` (Naismith-Tempo) und `profil` (Scoring) sind **disjunkte** Namensräume
   ohne Konvertierung (Grep bestätigt) — die Prämisse „einzige echte Wertkonvertierung" war falsch;
   (c) `points` existiert nirgends (route→`stages[].waypoints`, vergleich→`location_ids`). Der
   **S7-Cutover** lädt `briefings/<id>.json` per `kind` in die bestehenden `Trip`/`ComparePreset`-
   Strukturen (Go via Repoint von `LoadTrip`/`LoadComparePresets` auf `briefingsDir()`+kind-Filter,
   NICHT via `LoadBriefing`). Das S5-Gerüst `BriefingSubscription` + `LoadBriefing`/`SaveBriefing`
   bleiben **ungenutzt** und werden als tot markiert. **S7 wird nach Entität geteilt** (S7a route,
   S7b vergleich, S7c Scheduler optional), da der Go-Scheduler keinen Store liest → Cutover ⊥
   Scheduler-Merge. **Cutover-Refresh = `briefings/` wipen + frisch remigrieren** (nicht `--force`;
   `briefings/` ist bis zum Cutover reine Projektion der Alt-Stores, kein nativer Schreiber → Wipe
   verliert nichts, verhindert Waisen von post-S5-Löschungen). Alle Schreibpfade einer Entität kippen
   in EINEM Deploy (stop-writers → refresh → start-new-code); Alt-Stores bleiben für Rollback liegen.

## Konsequenzen

- **Positiv:** Verlustfreiheit ist durch den Raw-Auffang strukturell garantiert; die Migration
  ist reversibel (Altdaten bleiben, Backup vorhanden) und idempotent. S6 kann Felder inkrementell
  vom Raw-Auffang in typisierte Felder heben, ohne erneute Daten-Migration.
- **Negativ / Schuld:** Für die Dauer von S5 existieren zwei Wahrheiten (alt + `briefings/`) —
  entschärft durch Idempotenz + Dry-Run-Default + „App liest noch alt". Das volle Modell + die
  `points`-Diskriminierung sind offene S6-Arbeit (dort ADR-Fortschreibung).
- **Deploy:** Die Migration ist ein **per-Host-Schritt nach dem Code-Deploy** (erst Dry-Run-Report
  prüfen, dann `--execute` mit Backup), idempotent — siehe `reference_data_migration_per_host_deploy`.
