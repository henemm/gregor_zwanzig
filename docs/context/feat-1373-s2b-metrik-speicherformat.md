# Context: feat-1373-s2b-metrik-speicherformat

Issue #1373 (Etappe S2 von Epic #1372, Kind von Dach-Epic #1374) — **Scheibe B**.
Scheibe A ist geliefert und live (`373d3970`): jeder der 26 Einträge des
Vergleichs-Metrik-Katalogs trägt `metric_id` + `aggregation`, drei Drift-Wächter
gegen `metric_catalog.py` stehen.

## Request Summary

Das Speicherformat der Metrik-Auswahl eines Orts-Vergleichs
(`display_config.active_metrics`) wechselt von einer Liste von Zeichenketten
(`["temp_max_c", "temp_min_c"]`) auf eine Liste aus Größe + Auswertung
(`[{"metric_id": "temperature", "aggregation": "max"}, …]`). Altformat wird
weiterhin gelesen, aber nie mehr geschrieben. Bestandsdaten werden per
Migrationsskript umgestellt (verlustfrei, idempotent, mit Sicherung, je Host).
An der Bedienoberfläche ändert sich nichts.

## Related Files

### Backend — Lesen/Auflösen

| File | Relevance |
|------|-----------|
| `src/output/renderers/compare_metric_ids.py:101-132` | `resolve_enabled_metrics(active_metrics: list[str]\|None) -> list[str]\|None` — **der zentrale Auflöser**. Muss künftig beide Formate lesen. Verwirft nicht-mappbare Einträge mit `logger.warning` (Z.123-126), dedupliziert reihenfolge-erhaltend (Z.127-131), gibt bei leer/`None`/falschem Typ `None` zurück (= kein Filter, alle Metriken sichtbar) |
| `src/output/renderers/compare_metric_ids.py:15-57` | `FRONTEND_TO_RENDERER_METRIC_ID` (26 Einträge) — Compare-Key → Renderer-ID |
| `src/services/report_config_resolver.py:216,238` | Einziger Aufrufer von `resolve_enabled_metrics()`: `resolve_compare_render_options(preset)` → `enabled_metrics=…(display_config.get("active_metrics"))`. Der Render-/Versandpfad aller Kanäle hängt hier |
| **`src/services/compare_alert.py:233-271`** | **NEU GEFUNDEN — zweiter, unabhängiger Leser.** `_display_config_from_active_metrics()` liest `preset["display_config"]["active_metrics"]` (Z.252) und übersetzt über eine **eigene** Tabelle `_SUMMARY_KEY_TO_CATALOG_ID` in Katalog-IDs. In der Scheibe-B-Skizze der Spec **nicht erwähnt** — wird das Neuformat hier nicht gelesen, verliert der Δ-Alarm-Pfad (#1191) seine Metriken |
| `src/output/renderers/compare_metric_catalog.py` | Scheibe-A-Ergebnis: 26 Einträge mit `key`/`metric_id`/`aggregation` **inline** an jedem Dict. **Es gibt noch keine Hilfsfunktion** `key ↔ (metric_id, aggregation)` — Scheibe B braucht eine (und darf keine fünfte Übersetzungstabelle daneben stellen) |
| `src/output/renderers/compare_metric_catalog.py:139-146` | Import-Zeit-`assert`: `_catalog_keys == _resolver_keys` (gegen `FRONTEND_TO_RENDERER_METRIC_ID.keys()`). Jeder Rückbau einer der beiden Tabellen bricht den Modul-Import, wenn nicht synchron |

### Backend — Schreiben/Persistenz (Go)

| File | Relevance |
|------|-----------|
| `internal/model/compare_preset.go:48` | `DisplayConfig map[string]interface{}` — **untypisiert**. `active_metrics` kommt in Go-Produktionscode namentlich **nicht** vor |
| `internal/handler/compare_preset.go:262,300` | `PUT /api/compare/presets/{id}` → `updated.DisplayConfig = mergeConfigMap(original.DisplayConfig, updated.DisplayConfig)` |
| `internal/handler/config_merge.go:11-22` | Key-für-Key-Merge — ein PUT mit nur `active_metrics` lässt `region`, `ideal_ranges`, `metric_alert_levels` … stehen (#1159, Klasse #102) |
| `internal/store/compare_preset.go:89,139,199` | Laden/Speichern je Preset als `briefings/<id>.json`, `DisplayConfig` 1:1 durchgereicht |

→ **Folgerung: Der Formatwechsel erzwingt keine Go-Änderung.** Go reicht den
JSON-Blob blind durch. Das ist der wichtigste umfangsbegrenzende Fund.

### Frontend — die Speicher-/Ladepfade

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare/compareEditorLoad.ts:24-33` | `rehydrateActiveMetrics()` — **Lesetor**. Heute `Array.isArray(saved)` → durchreichen, sonst `null`. Muss künftig Alt- **und** Neuformat auf `string[]` zurückführen |
| `frontend/src/lib/components/compare/compareEditorSave.ts:97-103` | `buildComparePresetSavePayload()` — Z.102 `displayConfig.active_metrics = edits.activeMetricKeys`. **Schreibstelle 1** (Edit). Leeres `[]` wird bewusst persistiert (#1191/F001: „alles abgewählt" ≠ „nie konfiguriert") |
| `frontend/src/lib/components/compare/compareEditorSave.ts:277` | `buildNewComparePresetPayload()` — **Schreibstelle 2** (Neuanlage). **Asymmetrie:** bei leerem Array wird der Key *weggelassen* |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts:104-149` | `buildHubPutPayload()` Z.115: `edit.activeMetricKeys ?? displayConfig.active_metrics` als Bestandsrückfall — liest also Altbestand und gibt ihn an Schreibstelle 1 weiter. **Hier muss das Neuformat mitgelesen werden**, sonst kippt der Bestandsrückfall |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts:43-54,430-451` | `hydrateWizardStateFromPreset()` und `hydrateAlarmFieldsFromPreset()` (Z.445, Deep-Link Alarme-Tab, #1320) — zwei weitere Lesestellen |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts:40-44,54-62,85-91` | `hydrateWeatherMetricsFromPreset()`, `WeatherMetricsSnapshot`, `norm()`. Dirty-Check per `JSON.stringify(norm(…))`; `norm()` sortiert **bewusst nicht** (#1359 S1: Reihenfolge = Metrik-Reihenfolge seit #1335) |
| `frontend/src/lib/components/compare/CompareTabs.svelte:636-643,645-661,663-678` | `currentWetterMetrikenSnapshot()` (Z.638), Hydration (Z.647), Rollback (Z.678) |
| **`frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts:517-578`** | **NEU GEFUNDEN — dritte Schreibstelle.** `buildCompareCorridorSavePayload()` Z.575 baut `activeMetricKeys: [...activeSet]` für den Idealwerte-Tab und speist denselben Hub-PUT. In der Scheibe-B-Skizze **nicht in den „vier Ergänzungsstellen" enthalten** |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareMetricOrder.ts:23-26` | `toggleCompareMetricKey()` — der **primäre UI-Schreibpunkt** (Checkbox/Drag). Arbeitet auf `string[]`; bleibt unangetastet, wenn die Snapshot-Ebene bei `string[]` bleibt |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts:26` | `activeMetricKeys = $state<string[]>([])` — geteilter State zwischen Wetter-Metriken-, Idealwerte- und Alarme-Tab |
| `frontend/src/lib/utils/cockpitHelpers568.ts:105-106` | Cockpit-Fortschritt: `Array.isArray(activeMetrics) && length > 0`. Mit dem Neuformat weiterhin ein Array → bleibt korrekt, muss aber verifiziert werden |
| `frontend/src/lib/types.ts:540` | `display_config?: Record<string, unknown>` — kein Typ für das Feld, überall `as string[]`-Casts |

### Migration

| File | Relevance |
|------|-----------|
| `scripts/migrate_1361_drop_compare_hour_from_to.py` | **Jüngstes und bestes Vorbild** (nicht 1191/1360 wie in der Spec-Skizze genannt): `--root` (Pflicht), `--backup-dir`, `--execute`; Dry-Run ist Default; tar.gz-Sicherung vor jedem Schreiblauf; Plan→Apply; Idempotenz über `_needs_migration()`; Read-Modify-Write; Filter `kind != "vergleich"` → überspringen; saubere Fehlerpfade für Backup-Fehlschlag (Z.115-120) und Schreibfehler je Datei (Z.115-136) |
| `tests/test_compare_hour_from_to_migration.py` (287 Z.) | **Testvorbild.** Echter Subprozess (`uv run python3 <script> --root <tmp_path>`), kein Mock; Skriptpfad aus `__file__` abgeleitet (Z.32-38, worktree-sicher); sechs Fälle: RMW inkl. unbekanntem Zukunftsfeld · Idempotenz · Sicherung enthält Vorzustand · Dry-Run schreibt nichts · `kind=route` unberührt · mehrere Nutzerverzeichnisse |
| `src/app/loader.py:1038-1057` | `get_data_root()`: `_DATA_ROOT` > ENV **`GZ_DATA_DIR`** > `Path("data")`. (Nicht `GZ_DATA_ROOT` — häufige Verwechslung) |
| `docs/reference/operations_playbook.md:195-251` | Migration ist ein **manueller Ops-Schritt je Host** als `claude-gregor`: erst Dry-Run lesen, dann `--execute`. Nicht Teil von `deploy-gregor-prod.sh` |

## Existing Patterns

- **Datenlayout (#1250/#1265):** Vergleiche liegen als `<root>/<uid>/briefings/<id>.json` mit `"kind": "vergleich"`; Trips als `"kind": "route"` in denselben Verzeichnissen.
- **Read-Modify-Write mit Merge** auf allen Ebenen: Go `mergeConfigMap` (Key-für-Key), Migrationsskripte (ganze Datei laden, nur Zielfeld ändern). Nie Replace — Klasse #102/BUG-DATALOSS-GR221.
- **Toleranter Leser, strenger Schreiber** (Strangler): Altformat lesen, nur Neuformat schreiben. Vorbild: `migrate_1262_flat_metrics.py` (Legacy-Flach-String → dict) und `rehydrateActiveMetrics()`s `null`-vs-`[]`-Unterscheidung.
- **Drift-Wächter mit Wirkungsnachweis:** ein Wächter wird künstlich sabotiert und muss dann anschlagen (`test_compare_metric_catalog_consistency.py`, in Scheibe A auf Adversary-Befund F002 gehärtet: keine Kopie prüfen, sondern die echte Funktion erneut aufrufen).
- **Frontend-Tests:** `node --import ./test-lib-loader.mjs --experimental-strip-types --test` (`frontend/package.json:13`).

## Dependencies

- **Upstream:** `src/app/metric_catalog.py` (24 wählbare Größen mit `summary_fields`) → `compare_metric_catalog.py` (26 Einträge mit `metric_id`/`aggregation`, Scheibe A) → hier.
- **Downstream:** `report_config_resolver.resolve_compare_render_options()` → alle Kanal-Renderer (E-Mail HTML/Klartext, Telegram, SMS); `compare_alert._display_config_from_active_metrics()` → Δ-Alarm-Pfad; Frontend-Editor + Hub + Cockpit-Fortschrittsanzeige.

## Existing Specs

- `docs/specs/modules/feat_1373_s2_ein_katalog.md` — Scheibe A (geliefert), Abschnitt „Scheibe B" (Z.184-221) als Vorarbeit. **Drei Stellen dort ergänzungsbedürftig** (s. Risiken).
- `docs/adr/` — vor Persistenz-Entscheidungen prüfen (Datenmodell ist Entscheidungsfläche).

## Risks & Considerations

1. **Die Spec-Skizze ist an drei Stellen unvollständig** (alle drei erst durch diese Recherche belegt):
   - `src/services/compare_alert.py:233-271` liest `active_metrics` unabhängig mit eigener Tabelle — fehlt in der Skizze. Ohne Anpassung verliert der Δ-Alarm nach der Migration seine Metriken.
   - `corridorEditorState.ts::buildCompareCorridorSavePayload()` ist eine **dritte** Schreibstelle über den Idealwerte-Tab — die Skizze nennt „vier Ergänzungsstellen", trifft aber diese nicht.
   - Vorbild sollte `migrate_1361_*` sein (jüngstes, gleiches `briefings/`-Layout, saubere Fehlerpfade), nicht `migrate_1191_*` (Alt-Layout `compare_presets.json`).
2. **Datenverlust-Risiko** ist das dominierende Risiko (#102). Verifikationsanker gemessen: 3 Produktions-Vergleiche mit `temp_max_c` **und** `temp_min_c`, 1 mit `wind_chill_min_c`. Die Migration darf keinen davon zusammenfallen lassen — genau das ist die Falle, weil beide auf `metric_id: temperature` abbilden und nur die `aggregation` sie unterscheidet.
3. **Reihenfolge ist bedeutungstragend** (#1335/#1359): die Liste ist keine Menge. Migration und Auflöser müssen die Reihenfolge exakt erhalten; ein `set()` an falscher Stelle ist ein stiller Datenverlust.
4. **`[]` vs. `null` ist bedeutungstragend** (#1191): „alles abgewählt" ≠ „nie konfiguriert". Migration darf `[]` nicht zu `null` machen und nicht auffüllen.
5. **Die Asymmetrie Edit-/Neuanlage-Pfad** (`[]` schreiben vs. Key weglassen) muss erhalten bleiben, sonst kippt #1191 zurück.
6. **Import-Zeit-`assert`** in `compare_metric_catalog.py:139-146`: jeder Rückbau von `FRONTEND_TO_RENDERER_METRIC_ID` bricht den Modul-Import der ganzen Anwendung, wenn nicht synchron mit dem Katalog. Rückbau daher nur soweit, wie der Assert es trägt.
7. **Kein Nutzen an der Oberfläche.** Scheibe B ist reine Grundlagenarbeit für S4 (wählbare Auswertung, #1357) und trägt Datenverlust-Risiko ohne sichtbaren Gewinn. Der Nachweis muss deshalb Nicht-Veränderung beweisen: dieselbe Auswahl ⇒ dieselbe Mail, Zahl für Zahl, vor und nach Migration (echte Staging-Mail, `email_spec_validator.py` Exit 0).
8. **Parallele Sitzungen** arbeiten an #1374 S1 (`ws-1374-s1`) und #1384 (`issue-1384`). Keine Überschneidung mit diesen Dateien erwartet — vor dem Commit erneut prüfen.
9. **LoC-Deckel 250** wird voraussichtlich überschritten (Migrationsskript ~150 + Testdatei ~280 + Auflöser + drei Frontend-Stellen). Override braucht PO-Erlaubnis.

---

## Analysis

### Type
Feature (Grundlagenarbeit — Persistenzformat, keine Oberflächenänderung)

### Vier Korrekturen an der Scheibe-B-Skizze (belegt am Code)

1. **`compare_alert.py` braucht KEINEN Rückbau, nur tolerantes Lesen.**
   `_SUMMARY_KEY_TO_CATALOG_ID` (`src/services/compare_alert.py:46-57`) übersetzt in
   einen **anderen Namensraum** als der zentrale Katalog: `"temp_min_c" → "temperature_cold"`
   (Z.48), nicht `"temperature"`. Das ist die Alarm-Engine-ID
   (`weather_change_detection._ALERT_METRIC_TO_CATALOG_ID:84`), semantisch verschieden
   von Größe+Auswertung. Die neue Zuordnung kann sie nicht ersetzen. Richtiger Zug:
   in `_display_config_from_active_metrics()` (Z.256-260) jedes Element **vor**
   `_SUMMARY_KEY_TO_CATALOG_ID.get(...)` auf die alte Zeichenkette normalisieren;
   Tabelle bleibt stehen. Rückbau wäre S3/S4-Scope.
2. **`corridorEditorState.ts` muss NICHT geändert werden.**
   `buildCompareCorridorSavePayload()` (Z.575) baut `string[]` und speist über
   `CorridorEditor.svelte:137-148` → `ws.activeMetricKeys` → `buildHubPutPayload()`
   → `buildComparePresetSavePayload()`. Es ist **Aufrufer** des einen
   Übersetzungspunkts, keine eigene Übersetzungsstelle. Damit schrumpft die
   Änderungsfläche gegenüber der Skizze.
3. **Zwingend zu ändernde Frontend-Funktionen sind nur drei**, nicht vier:
   `buildComparePresetSavePayload()` (Edit, `compareEditorSave.ts:102`),
   `buildNewComparePresetPayload()` (Neuanlage, `:277`, Asymmetrie erhalten),
   `rehydrateActiveMetrics()` (Lesen, `compareEditorLoad.ts:24-33`).
   Snapshot-/Diff-Ebene bleibt `activeMetricKeys: string[]` — `norm()` und
   `currentWetterMetrikenSnapshot()` bleiben unangetastet (verifiziert).
4. **Migrations-Vorbild ist `migrate_1361_drop_compare_hour_from_to.py`**, nicht 1191
   (Alt-Layout `compare_presets.json`) — gleiches `briefings/`-Layout, saubere
   Fehlerpfade für Sicherungs- und Schreibfehler.

### Zwei neu gefundene Risiken (in keinem Dokument vorher)

**R1 — Mischlisten sind real erreichbar, nicht theoretisch.** Nicht durch Teil-PUTs
(jeder Speicherpfad schreibt `active_metrics` immer als ganze Liste), sondern durch
eine **stehengebliebene Browser-Sitzung**: nach Deploy+Migration liefert der Server
Neuformat; der alte, im Browser noch geladene Code prüft nur `Array.isArray(...)`
(`compareEditorLoad.ts:29-31` alte Fassung) → `true` auch bei Objekten → die Objekte
gehen unverändert als `activeMetricKeys` durch → jede UI-Prüfung `.includes("temp_max_c")`
schlägt fehl → **die gespeicherte Auswahl zeigt sich als „nichts ausgewählt"**.
Klickt der Nutzer dann eine Metrik an, hängt `toggleCompareMetricKey()`
(`compareMetricOrder.ts:25`) eine Zeichenkette an eine Liste aus Objekten —
Mischliste, gespeichert. Folge: die Auflösung muss **pro Element** entscheiden,
nicht pro Liste. Heilt sich beim nächsten Laden mit neuem Code selbst; nicht
verhinderbar, nur abfederbar. Als bekanntes Restrisiko dokumentieren, kein Blocker.

**R2 — Rollback nach Migrationsstart stürzt ab.** Die heutige
`resolve_enabled_metrics()` prüft `m not in FRONTEND_TO_RENDERER_METRIC_ID` (Z.118) —
Mitgliedschaft in einem Dict. Kommt `m` als Objekt herein (Neuformat) und wurde der
Commit zurückgerollt, wirft Python `TypeError: unhashable type: 'dict'` → **der
komplette Vergleichs-Mailversand für dieses Preset bricht ab**, nicht nur eine Metrik
fällt weg. Betriebswissen: nach Migrationsstart ist ein Rückrollen des Codes nicht
mehr gefahrlos. Muss in der Lieferung vermerkt werden.

### Technischer Ansatz (Empfehlung)

- **EIN Ort für die Zuordnung:** Umkehr-Index auf Modulebene über
  `COMPARE_METRIC_CATALOG` in `src/output/renderers/compare_metric_catalog.py`:
  `{(e["metric_id"], e["aggregation"]): e["key"]}` plus Funktion
  `key_for(metric_id, aggregation) -> str | None`. Das ist **keine fünfte
  Übersetzungstabelle**, sondern ein reiner Index über schon vorhandene kuratierte
  Daten (wie `_catalog_keys`/`_resolver_keys` Z.139-140). Die 26 Paare sind heute
  paarweise eindeutig (nachgemessen) — **neuer Assert nötig**:
  `len(pairs) == len(set(pairs))`, denn Scheibe As Wächter prüft die
  Paar-Eindeutigkeit nicht; ein künftiges Duplikat würde still kollidieren.
- **Auflösung pro Element:** `_to_key(item)` → Zeichenkette bleibt Zeichenkette;
  Objekt → `key_for(...)`; alles andere → `None`. Danach unverändert die bestehende
  Verarbeitung; der Dedup-Schlüssel bleibt die Renderer-Kennung (`dict.fromkeys`,
  Z.127-131), ändert sich also **nicht** — Reihenfolge (#1335/#1359) bleibt erhalten,
  solange die Normalisierung **vor** dem Dedup läuft und niemand nach Format gruppiert.
- **Frontend braucht keine neue Tabelle:** `toCompareSelectionEntries()`
  (`compareMetricSelection.ts:25-37`) reicht `metric_id`/`aggregation` je Eintrag aus
  `GET /api/compare/metrics` bereits durch (Scheibe A) — dieselbe geladene
  Katalogantwort ist die Quelle für beide Richtungen im Browser.
- **Deploy-Sequenz:** ein Deploy genügt. `deploy-gregor-prod.sh` bringt Go, Python
  und Frontend im selben Lauf auf denselben Commit — es gibt keinen Zustand
  „schreibt neu, liest alt". Zu sequenzieren ist nur die **Migration**: frühestens
  nach erfolgreichem Deploy, je Host, Trockenlauf zuerst. Tolerantes Lesen bleibt
  **dauerhaft** im Code (nicht „bis migriert"), weil Alt-Sitzungen jederzeit wieder
  Altformat schreiben können.

### Affected Files

| File | Change | Beschreibung |
|------|--------|--------------|
| `src/output/renderers/compare_metric_catalog.py` | MODIFY | Umkehr-Index + `key_for()` + Paar-Eindeutigkeits-Assert (~10-15) |
| `src/output/renderers/compare_metric_ids.py` | MODIFY | `_to_key()`, `resolve_enabled_metrics()` liest beide Formate pro Element (~15-20) |
| `src/services/compare_alert.py` | MODIFY | Normalisierung vor `_SUMMARY_KEY_TO_CATALOG_ID` (~5-10) |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | zwei Schreibstellen ins Neuformat, Asymmetrie `[]`/weglassen erhalten (~20-30) |
| `frontend/src/lib/components/compare/compareEditorLoad.ts` | MODIFY | `rehydrateActiveMetrics()` liest beide Formate → `string[]` (~15-20) |
| `frontend/.../weather-metrics-tab/compareMetricSelection.ts` (o. neues Modul) | MODIFY/CREATE | Übersetzung Eintrag ↔ `{metric_id, aggregation}` aus der Katalogantwort (~15-25) |
| `scripts/migrate_1373_compare_active_metrics_format.py` | CREATE | Vorbild `migrate_1361_*` (~140-160) |
| `tests/unit/test_compare_active_metrics_dual_format.py` | CREATE | beide Formate, Mischliste, Reihenfolge, `[]` vs. `null` (~60-90) |
| `tests/test_compare_active_metrics_format_migration.py` | CREATE | Vorbild `test_compare_hour_from_to_migration.py` (~250-290) |
| `frontend/.../__tests__/compareEditorSave.test.ts`, `compareEditorLoad.test.ts` | MODIFY | Schreib-/Lese-Übersetzung (~40-60) |

**Ausdrücklich NICHT geändert:** `corridorEditorState.ts`, `compareMetricOrder.ts`,
`CompareTabs.svelte`, `weatherMetricsCompareSave.ts`, `compareWizardState.svelte.ts`,
`cockpitHelpers568.ts` (bleibt korrekt: Neuformat ist weiterhin eine Liste),
Go-Code (`display_config` ist dort untypisiert), `api/routers/compare.py`.

### Scope Assessment

- Dateien mit Codeänderung: 6 MODIFY + 3 CREATE
- Produktivcode: **~80-120 Zeilen** (unter dem Deckel)
- Migrationsskript: ~140-160 Zeilen
- Tests: ~350-440 Zeilen
- Gesamt: **~600-700 Zeilen** → **Deckel 250 hält nicht**, Override nötig
- Risiko: **HIGH** (Bestandsdaten, Datenverlust-Klasse #102)

### Härteste Prüffälle

1. Vergleich mit `["temp_max_c", "temp_min_c", "wind_chill_min_c"]` → nach Migration
   exakt **drei** Einträge mit drei verschiedenen `(metric_id, aggregation)`-Paaren.
   Die Falle: `temp_max_c` und `temp_min_c` haben dieselbe `metric_id` — jede
   Gruppierung/Deduplikation nach `metric_id` allein lässt sie zu einem verschmelzen.
2. Reihenfolge positionsgetreu — kein `set()`, keine Gruppierung nach Format.
3. `[]` bleibt `[]` (nicht `null`, nicht aufgefüllt); fehlender Eintrag bleibt fehlend.
4. Mischliste (Zeichenkette + Objekt) wird ohne Absturz aufgelöst.
5. Zweiter Migrationslauf: leerer Plan, Exit 0, nichts geschrieben.
6. `kind=route` (Touren) bleiben unberührt; mehrere Nutzerverzeichnisse werden erfasst.
7. Dieselbe Auswahl ⇒ **dieselbe Vergleichsmail**, Zahl für Zahl, vor und nach
   Migration (echte Staging-Mail, `email_spec_validator.py` Exit 0).

### Open Questions
- [ ] Erlaubnis für den Zeilen-Override (Deckel 250 → 900, wie in Scheibe A)
