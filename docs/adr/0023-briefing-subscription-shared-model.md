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
   `briefings/`-Dateien entstehen daneben (verhaltensneutral). S6 schaltet die Lesepfade um.

## Konsequenzen

- **Positiv:** Verlustfreiheit ist durch den Raw-Auffang strukturell garantiert; die Migration
  ist reversibel (Altdaten bleiben, Backup vorhanden) und idempotent. S6 kann Felder inkrementell
  vom Raw-Auffang in typisierte Felder heben, ohne erneute Daten-Migration.
- **Negativ / Schuld:** Für die Dauer von S5 existieren zwei Wahrheiten (alt + `briefings/`) —
  entschärft durch Idempotenz + Dry-Run-Default + „App liest noch alt". Das volle Modell + die
  `points`-Diskriminierung sind offene S6-Arbeit (dort ADR-Fortschreibung).
- **Deploy:** Die Migration ist ein **per-Host-Schritt nach dem Code-Deploy** (erst Dry-Run-Report
  prüfen, dann `--execute` mit Backup), idempotent — siehe `reference_data_migration_per_host_deploy`.
