# Context/Analyse: feat-1250-s5-kind-migration

## Request Summary
Scheibe 5 von Epic #1250 (die Migrations-Scheibe): `kind`-Feld additiv, gemeinsames
`BriefingSubscription`-Modell/Store, Migrationsskript `scripts/migrate_1250_briefings.py`
(Dry-Run-Default, Backup, idempotent, pro Nutzer) das Trips + ComparePresets verlustfrei nach
`data/users/<uid>/briefings/<id>.json` migriert. ACs: AC-16/AC-17/AC-18/AC-19. **Verhaltensneutral** —
die App liest in S5 weiter aus den alten Stores; `briefings/` wird erst in S6/S7 gelesen.

## Zentrale Befunde (2 parallele Recherchen)
1. **Migrations-Vorbilder:** `scripts/migrate_1231_corridors.py` (zweiphasig collect→apply, argparse
   `--execute`/Dry-Run-Default `:233-276`, `_make_backup` tar.gz nach `.backups/` VOR Schreiben `:206-212`,
   Idempotenz `_needs_migration` `:67-70`, RMW `_apply` nur additiv `:215-230`, `MigrationAbort` = kein
   Teil-Commit) + Go `internal/store/migrate_1258.go:21` (per-User-Iteration, **Idempotenz über rohe Bytes**
   `:58-67` — typisiert `{}` vs. bewusster Wert nicht unterscheidbar).
2. **Datenlayout:** Trips per-Datei `trips/<id>.json`; ComparePresets EINE Array-Datei `compare_presets.json`.
   Nutzer-Enumeration: Glob `<root>/*/…` (ein Segment = ein User → AC-19-Isolation automatisch). Ziel
   `briefings/<id>.json` = per-Datei → **Trip-Store ist das nähere Store-Vorbild** (`internal/store/trip.go`).
3. **Union (Trip vs. ComparePreset nach S2/S4):** ~16 gemeinsame Felder (id/name/display_config/corridors/
   alert_*/paused_at/archived_at/official_*/morning-evening_time+enabled/send_sms+telegram/end_date).
   Trip-only: stages/avalanche_regions/aggregation/weather_config/report_config/alert_rules/shortcode/
   activity/region/**send_email**. Compare-only: user_id/location_ids/schedule(deprecated)/previous_schedule/
   profil/hour_from-to/forecast_hours/weekday/empfaenger/letzter_versand/top_ort_letzter_versand/created_at/
   radar_alert_enabled/hourly_enabled. Divergenz `activity`(ActivityType) ↔ `profil`(ActivityProfile) = echte Konvertierung.
4. **`kind` existiert nicht** (nur `AlertRule.Kind`, unabhängig). `BriefingSubscription` existiert nicht.

## Design-Entscheidung (Analyse) — Migration-Kern + verlustfreies Gerüst, volle Union → S6
1. **Migrationsskript `scripts/migrate_1250_briefings.py`** (Herzstück, AC-16-19) nach `migrate_1231`-Muster:
   - Pro User: `<root>/*/trips/*.json` (je 1 Trip) + `<root>/*/compare_presets.json` (Array) als **ROHE Dicts**
     lesen (`json.loads`, NICHT geparste Objekte → kein Feldverlust, BUG-DATALOSS-GR221).
   - `kind` additiv setzen: Trip → `"route"`, Preset → `"vergleich"`. Alle übrigen Felder 1:1 übernehmen.
   - Verlustfrei nach `<root>/<uid>/briefings/<id>.json` schreiben (id = Trip-Dateiname bzw. `preset["id"]`).
   - **Dry-Run-Default** (ohne `--execute`: nur Feld-Diff-Report, nichts geschrieben — AC-17).
   - **Backup** (`_make_backup` tar.gz `.backups/migrate-1250-<ts>.tar.gz`) VOR `--execute`; Fehler → Abbruch.
   - **Idempotenz** (AC-18): Ziel `briefings/<id>.json` existiert UND trägt `kind` → SKIP-Report-Zeile,
     kein Re-Write. Prüfung über **rohe Bytes/Existenz**, nicht typisiert.
   - **Pro-Nutzer** (AC-19): Ziel strikt unter demselben `<uid>/briefings/`, nie cross-user.
   - Zweiphasig (erst planen/validieren, dann schreiben) → kein Teil-Commit.
2. **`kind`-Feld additiv** an den bestehenden Modellen (verhaltensneutral, damit die App den Diskriminator kennt):
   Go `model.Trip` (`kind` default via Store-Normalize „route"), `model.ComparePreset` („vergleich");
   Python `ComparePreset`-Dataclass (`models.py`) + Trip-Dataclass (`trip.py`). Wird von der App noch nicht konsumiert.
3. **`BriefingSubscription`-Go-Modell/Store — VERLUSTFREIES GERÜST, nicht volle Union:**
   - Modell: typisierte Diskriminator-/Kern-Felder (`ID`, `Kind`, `Name`, ggf. `Corridors`, `EndDate`, `PausedAt`)
     PLUS ein **Raw-Auffang** (`map[string]json.RawMessage` oder eingebettetes Roh-Dict) — löst die Go-„kein
     Catch-all"-Falle: jedes nicht typisierte Feld überlebt Load→Save verlustfrei (spiegelt Python `raw`/`extra`).
   - Store: per-Datei `briefings/<id>.json` nach Trip-Store-Muster (`Load`/`Save`, `New`/`WithUser`).
   - **NICHT in S5:** volle typisierte Union (alle ~40 Felder explizit), `points`-Sum-Type mit Custom-Unmarshal,
     `activity`↔`profil`-Konvertierung — das gehört zu **S6** (dort wird das Modell tatsächlich gelesen/geschrieben).
     Begründung: kein AC testet das volle Modell; es jetzt zu bauen bläht S5 und ist ohne Konsumenten riskant.
   - Unit-Test: migrierte `briefings/<id>.json` durch den Store laden → Save → **bytegleich** (verlustfreier Roundtrip).

## Risiken & Gegenmaßnahmen
- **(i) Verlustfreie Union (Go kein Catch-all):** Gerüst-Modell mit Raw-Auffang → nichts geht verloren. Migration
  schreibt ohnehin rohe Dicts. Deprecated-Felder (`schedule`/`previous_schedule`/…) tragen bis S5 lebende
  Semantik (KL-3) — die Migration übernimmt sie 1:1, materialisiert `paused_at` NICHT doppelt (Go leitet es aus `schedule` ab).
- **(ii) `points`/`end_date`-Semantik:** in S5 NICHT typisiert erzwungen (rohes Dict trägt stages/location_ids wie
  vorhanden). `end_date` route=abgeleitet vs. vergleich=persistiert bleibt in den Rohdaten je Herkunft erhalten. S6 typisiert.
- **(iii) Koexistenz/Doppel-Wahrheit:** App liest weiter alt; `briefings/` daneben. Idempotenz + Dry-Run-Default
  verhindern versehentliche Mehrfach-/Überschreibung. **Kein Löschen der Altdaten** (RMW, kein Replace).
- **Deploy:** Migration ist ein **per-Host-Schritt NACH dem Code-Deploy** (erst Dry-Run-Report prüfen, dann
  `--execute` mit Backup), als `claude-gregor`, idempotent — analog `reference_data_migration_per_host_deploy`.
- **ADR nötig:** neues gemeinsames Datenmodell = Architektur-Entscheidung → ADR (BriefingSubscription, kind, briefings/-Layout, Scope-Grenze S5↔S6).

## Related Files
| File | Rolle |
|------|------|
| `scripts/migrate_1231_corridors.py` | Vorbild Migrationsskript (Dry-Run/Backup/Idempotenz/RMW) |
| `internal/store/migrate_1258.go:21-67` | Vorbild per-User-Iteration + **Byte-basierte Idempotenz** |
| `internal/store/trip.go` | Store-Vorbild für per-Datei `briefings/<id>.json` (Load/Save/New/WithUser) |
| `src/app/loader.py:258-303` (compare) / `:347-394,1201-1238` (trip) | Roh-Dict-Zugriff / Enumeration |
| `internal/model/trip.go:101-153`, `internal/model/compare_preset.go:14-102` | Union-Inventar + `kind`-Platzierung |
| `src/app/models.py:848-903`, `src/app/trip.py:168-220` | Python `kind`-Feld (ComparePreset + Trip) |

## Tests (Andockpunkte)
- AC-16: Fixture-Bestand (2 User, je Trip + Preset) → `--execute` → `briefings/<id>.json` enthält ALLE Quellfelder + `kind`, Report listet jede Entität.
- AC-17: Dry-Run → Dateisystem-Zustand (mtime/Existenz) unverändert, Report nicht leer.
- AC-18: zweiter `--execute` → Ziel-mtime unverändert + SKIP-Zeile.
- AC-19: zwei User → Dateien strikt unter eigenem `<uid>/briefings/`, kein Cross-Pfad.
- Go: BriefingSubscription-Store Roundtrip bytegleich (verlustfrei).
- Vorbild-Tests: `tests/` migrate_1231/1258-Tests.

## Existing Specs
- `docs/specs/modules/issue_1250_briefing_subscription.md` — S5 = AC-16-19, Zielmodell `:72-90`, Slice `:156-164`.
- Epic #1230 (gh) — BriefingSubscription-Interface, Constraints C1-C6/E8/E9.

## Umfang
Migrationsskript (~150-200) + kind-Feld (~30) + Gerüst-Modell/Store + Tests → **LoC-Override nötig** (Skript zählt
mit); PO-Permission bei ACs-Freigabe. Volle Union bewusst NICHT in S5 (→ S6) hält es beherrschbar.
