# Context: feat-3196-trip-tempo-etappen

## Request Summary
Issue #3196 (Teil von #2796, Epic #2791, ADR-0108 Nr. 2/3/5): Die Aktivitäts-Chips im Trip-Kopf entfallen. Der Reiter Etappen bekommt oben eine Karte „Fortbewegung (zu Fuß · Rad · MTB · Ski) · Tempo flach · Aufstieg“. Bestandstrips werden so migriert, dass alle Gehzeiten unverändert bleiben. Tempo je Etappe überschreiben ist #3197, Anlege-Kette Orts-Vergleich ist #3198.

## Wichtigste Befunde
- `EtappenConfig` (`src/app/models.py:418-424`, 4.0/300/500) wird **nicht gespeichert**, nur als Default für GPX-Segmentierung erzeugt (`src/services/gpx_processing.py:294`, `core/segment_builder.py`, `core/hybrid_segmentation.py`). Pro Trip existiert nur `activity` (flacher JSON-Schlüssel), pro Etappe kein Tempo.
- Heutige Abbildung activity → Tempo (Go `internal/model/naismith.go:15-50`, Python `src/core/naismith.py:22-33`):
  | activity | flach km/h | Aufstieg Hm/h | Abstieg Hm/h |
  |---|---|---|---|
  | fahrrad_15/20/25 | 15/20/25 | 600 | 1000 |
  | alles andere (trekking, skitour, hochtour, klettersteig, mtb, leer, Altwert „wandern“) | 4 | 300 | 500 |
- **Drift Frontend ↔ Backend:** `frontend/src/lib/utils/naismith.ts:17-36` kennt nur das Flachtempo und rechnet bei fahrrad_* mit 300/500 statt 600/1000 → Live-Anzeige weicht vor dem Speichern von gespeicherten Zeiten ab. Wird mit einem gespeicherten Tempo-Objekt von selbst behoben (eine Quelle für alle drei Rechner).
- Gespeichert (inkl. `arrival_calculated`) wird zentral in Go `internal/store/trip.go:313-316` (`SaveTrip`); Python rechnet in `src/app/loader.py:2178` und `src/services/trip_segments.py:200-201` (Selbstheilung) nach.
- Fixtures enthalten `"activity": "wandern"` (`tests/fixtures/trip_schema_full.json:75`, `tests/fixtures/migrate_2454/...:492`) – kein gültiger ActivityType.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/model/trip.go:106-132` | Go `Trip.Activity`, `Stage` – neues Tempo-Feld (Trip) ergänzen, sonst verwirft Go es |
| `internal/model/naismith.go` | `ActivitySpeed`, `ComputeStageArrivals` – auf Tempo-Feld umstellen |
| `internal/store/trip.go:313,402` | SaveTrip-Neuberechnung, Lazy-Migrationen-Muster |
| `internal/handler/trip.go:310,466` | `Optional[string] Activity` + Merge – Muster für neues Feld |
| `src/app/trip.py:205`, `src/app/loader.py:743,1882,2178` | Python-Modell, Laden/Schreiben |
| `src/core/naismith.py`, `src/services/trip_segments.py:200`, `src/services/stage_weather.py:50` | Python-Rechner und Weitergabe |
| `frontend/src/lib/types.ts:28-30,145-154,401` | ActivityType, Optionen, Trip.activity |
| `frontend/src/lib/utils/naismith.ts` | Frontend-Rechner (nur Flachtempo) |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte:16-30,64,88,117` | Aktivitäts-Chips (entfallen) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte:57,212-224` | reicht `activityType` an Etappen-Reiter |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte:135-151,215,1006` | Etappen-Reiter, speichert nur `{stages}` per PUT |
| `frontend/src/lib/components/edit/etappenListe.ts:13-35`, `mobile/StageCardM.svelte:55` | Gehzeit je Etappe |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:662-684` | `ACTIVITY_TO_TEMPLATE` – Vorlagen-Vorbelegung nur im Anlegen |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte`, `tripNewLogic.ts:142,249` | Aktivitäts-Dropdown beim Anlegen |
| `frontend/src/lib/i18n/messages/{de,en}/trip.json` | `trip.aktivitaet.*`, `trip.hub.kopf.etappen_*`, `trip.hub.etappe_gehzeit`, `trip.hub.tempo_aendern` (vorhanden) |
| `docs/reference/i18n_glossar.md` | Tempo/Fortbewegung fehlen (Vorschlag `einstellungen_neu.md:585`: Mode of travel · Pace on flat · Ascent rate) |

## Existing Patterns
- PUT-Merge mit `Optional[T]` je Feld im Go-Handler (Read-Modify-Write, ADR-0101).
- Migration: `scripts/migrate_2794_preset_horizons.py` (planen → sichern → `schreiben` aus `migrate_2792_profil_ampel.py:325-337`, `--execute`), Go-Variante `internal/store/migrate_1258.go` + `cmd/migrate1258`; Lazy-Migration beim Lesen `store/trip.go:402`.
- Schema-Drift-Wächter: `internal/model/trip_schema_drift_test.go`, `tests/test_trip_schema_drift.py`.
- Hook `data_schema_backup.py` greift bei `models.py`, `trip.py`, `loader.py`, `internal/model/*.go`.

## Dependencies
- Upstream: GPX-Distanz/Höhen je Etappe, Naismith-Formel (drei Kopien).
- Downstream: `arrival_calculated` je Wegpunkt → bewertete Stunden in Risk Engine, alle vier Kanäle, Trip-Briefing-Mail. Renderer/Scheduler lesen `activity` **nicht** (dort ist `ActivityProfile` = Orts-Profil gemeint).

## Existing Specs / ADR
- `docs/adr/0108-vorlage-und-tempo-getrennt.md` (Status Vorgeschlagen, geht mit S4b auf Angenommen)
- `docs/specs/modules/feat_2796_s4a_orte_vorlage_statt_profil.md` (S4a, verweist auf S4b)
- `feat_2284_s2_trip_kopf.md`, `feat_2913_c2_seitenkopf.md`, `rework_2837_s1b_status_profil.md`, `feat_3007_etappen_orte_listen.md`, `fix_1667_s2_naismith_wrap.md`, `fix_2082_gehzeit_plausibilitaet.md`, `fix_2042_gehzeit_wegstrecke.md`; Archiv `issue_674_aktivitaetstyp_fahrrad.md`, `issue_802_fahrrad_segment_zeit.md`, `issue_932_activity_type_first_screen.md`
- Soll-Bild: `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` `viewEtappen()` (:691-701) – Fassung 3 ist ersetzt. PO-Notiz `docs/context/einstellungen_neu/daten/entscheidungen/aktivitaet.json`.

## Risks & Considerations
- Gehzeiten-Parität nach Migration: fahrrad_* braucht Aufstieg 600 / Abstieg 1000; „Rad“-Default muss das abbilden, sonst ändern sich Ankunftszeiten und bewertete Stunden.
- MTB war bisher 4 km/h (zu Fuß-Tempo) – Migration muss das erhalten, auch wenn „MTB“ als Fortbewegung neu einen anderen Vorschlagswert bekäme.
- Drei Rechner (Go, Python, Frontend) müssen dasselbe Tempo-Objekt lesen; Frontend-Drift bei fahrrad_* wird dabei behoben.
- Altwert „wandern“ und leere activity → zu Fuß 4/300/500.
- Anlegen (TripNewEditor) nutzt activity für die Vorlagen-Vorbelegung → im Anlegen Fortbewegung statt Aktivität (Anlegen = Bearbeiten, gleicher Code).
- Viele Tests hängen an activity/Chips (Frontend-Unit, E2E, Python, Go – Liste siehe Recherche), Kopf-Parität Trip/Orte (`hub_kopf_seiten_paritaet`).
- Mandantentrennung: Tempo-Feld läuft über bestehenden PUT mit user_id; Zwei-Nutzer-Test Pflicht.
- Pausentag: Tempo-Wirkung auf Ruhetage (gehört zu #3197).

## Analysis

### Type
Feature (Teil von #2796, ADR-0108 Nr. 2/3/5). Tempo je Etappe = #3197 (nicht hier).

### Prod-Bestand (ausgezählt 2026-11-20, /var/lib/gregor/users/*/briefings, kind=route)
~16 Trips: 1× `fahrrad_15`, 1× `fahrrad_20`, 1× `hochtour`, Rest ohne `activity`. Kein `mtb`/`skitour`/`klettersteig` im Bestand.

### Datenmodell (Tech-Lead-Entscheidung)
- Neues Trip-Feld `tempo` = `{fortbewegung: "fuss"|"rad"|"mtb"|"ski", flach_kmh, aufstieg_hmh, abstieg_hmh}`. `EtappenConfig` wird NICHT wiederverwendet (wird nicht gespeichert, bleibt GPX-Segmentierungs-Default). Issue-Text „Abstieg bleibt im Modell (EtappenConfig.speed_descent_mh)" ist irreführend: `abstieg_hmh` wird neu im Trip gespeichert.
- Form ist auf #3197 vorbereitet: dort `Stage.tempo` als optionaler Override mit feldweiser Auflösung `stage.tempo.x ?? trip.tempo.x`. In #3196 nur `ResolveTempo(trip)` (Go) / `tempo_speeds(trip)` (Python) / `tripTempo(trip)` (TS) als einzige Quelle; kein Stage-Feld.
- `activity` bleibt als Altfeld auf der Platte (nicht löschen: ADR-0101, Rollback, Mischbetrieb Python-Whitelist `loader.py:700`). Wird von UI nicht mehr geschrieben, für Rechnung nur noch als Fallback-Quelle der Ableitung gelesen.
- Go `Trip` hat keine Extra-Map ⇒ Feld MUSS in `internal/model/trip.go`, Handler-Merge `Optional[Tempo]` in `internal/handler/trip.go:310/466`; Schema-Drift-Tests (Go + Python) anpassen.

### Migration
- Lazy-Ableitung beim Lesen (Go `normalizeTrip`, Python Loader), wenn `tempo` fehlt — exakt heutige Tabelle:
  - `fahrrad_15/20/25` → `rad`, 15/20/25, 600, 1000
  - alles andere (leer, `wandern`, `hiking`, `trekking`, `hochtour`, `klettersteig`, `skitour`, `mtb`) → `fuss`, 4, 300, 500 (Gehzeit-Parität geht vor Etikett; Migration setzt nie `mtb`/`ski`).
- Eager-Skript nach Muster `scripts/migrate_2794_preset_horizons.py` (planen → sichern → `--execute`, Read-Modify-Write mit Merge, `activity` bleibt stehen), nach Prod-Deploy ausführen. Gate: Gehzeiten/`arrival_calculated` vorher = nachher für alle Prod-Trips (Prüfung gegen Kopie).

### Rechner auf eine Quelle
- Go: `ActivitySpeed` → `ResolveTempo`; `ComputeStageArrivals(stage, tempo)`; SaveTrip (`internal/store/trip.go:313`) rechnet mit Tempo.
- Python: `src/core/naismith.py` `activity_speeds` → `tempo_speeds(trip)`; Aufrufer `loader.py:2178/743/1882/700`, `trip_segments.py:200`, `stage_weather.py:50` (Scoped-Trip muss `tempo` mitgeben), Modell `src/app/trip.py:205`.
- Frontend: `naismith.ts` liest Tempo-Objekt (flach/auf/ab) statt `activityToSpeed` (behebt Drift fahrrad 300/500 vs. 600/1000). Konsumenten: `EditStagesPanelNew.svelte:215,1004-1012`, `EditStagesSection.svelte`, `etappenListe.ts`, `StageCardM.svelte:53-55`, `TripTabs.svelte:57`.
- Paritätstest: gemeinsame JSON-Falltabelle (Tempo + Distanz/Hm → Minuten) für Go, Python, TS.

### UI
- Neue Komponente Fortbewegungs-Karte oben im Reiter Etappen (Kopf „Etappen & Wegpunkte" + Erklärsatz, Soll-Bild `mockup-hub-fassung4.html` `viewEtappen()`), Speichern über bestehenden Etappen-PUT (heute nur `{stages}` ⇒ `tempo` mitgeben, Autosave/ETag-Pfad).
- Aktivitäts-Chips/Profil-Zusatz in `TripHeader.svelte` (Desktop + mobil) entfallen; `profile={trip.activity}` an `SubscriptionHeader` entfällt (Kopf-Parität Trip/Orte prüfen: Orte-Profil-Chips sind schon über S4a weg).
- Anlegen = Bearbeiten: Aktivitäts-Dropdown in `TripNewEditor.svelte` (~712, ~1049) und `tripNewLogic.ts:142,249` → Fortbewegungs-Karte, neuer Trip Default `fuss` 4/300/500. Vorlagen-Vorbelegung `ACTIVITY_TO_TEMPLATE` (`WeatherMetricsTab.svelte:662-684`) und `wizardHelpers.ts:107 mapActivityToProfile` hängen künftig an `fortbewegung`.
- i18n DE/EN über Katalog; Glossar ergänzen (Fortbewegung = Mode of travel, Tempo flach = Pace on flat, Aufstieg = Ascent rate, Abstieg = Descent rate).

### Affected Files (with changes)
| File | Change | Beschreibung |
|---|---|---|
| internal/model/trip.go | MODIFY | Feld `Tempo` |
| internal/model/naismith.go | MODIFY | ResolveTempo, Ableitung, Vorschlagswerte |
| internal/store/trip.go | MODIFY | Lazy-Ableitung, SaveTrip-Rechnung |
| internal/handler/trip.go | MODIFY | Optional-Merge `tempo` |
| src/app/trip.py, src/app/loader.py | MODIFY | Modell, Laden/Schreiben, Whitelist |
| src/core/naismith.py, src/services/trip_segments.py, src/services/stage_weather.py | MODIFY | Rechner auf Tempo |
| scripts/migrate_3196_trip_tempo.py | CREATE | Eager-Migration |
| frontend/src/lib/types.ts, utils/naismith.ts | MODIFY | Typ Tempo, Rechner |
| frontend/.../edit/TempoKarte.svelte (Name in Spec) | CREATE | Fortbewegungs-Karte |
| EditStagesPanelNew.svelte, EditStagesSection.svelte, etappenListe.ts, StageCardM.svelte, TripTabs.svelte | MODIFY | Tempo statt activityType |
| TripHeader.svelte, SubscriptionHeader-Aufruf | MODIFY | Chips weg |
| TripNewEditor.svelte, tripNewLogic.ts, WeatherMetricsTab.svelte, wizardHelpers.ts | MODIFY | Anlegen, Vorlagen-Vorbelegung |
| i18n de/en trip.json, docs/reference/i18n_glossar.md | MODIFY | Texte |
| docs/adr/0108 | MODIFY | Status Angenommen |
| Tests (Liste unten) | MODIFY/DELETE | s. u. |

Betroffene Tests: Go `naismith_674_test.go`, `naismith_802_test.go`, `naismith_test.go`, `naismith_gemessene_strecke_test.go`, `trip_optional_clear_test.go`, Schema-Drift; Python `test_674_aktivitaetstyp_fahrrad.py`, `test_issue_802_fahrrad_segment_zeit.py`, Fixtures mit `activity` (bleiben gültig dank Ableitung); Frontend `naismith_674.test.ts`, `issue_943_activity_edit.test.ts`, `trip_kopf_aktivitaet_melden_konflikt.test.ts`, `trip_header_status_profil.test.ts`, Reiter-Roundtrip/Prüfstände (`f9KatalogAnker.ts`, `f9Pruefstand.ts`, `tripMehrreiterPruefstand.ts`), `hub_kopf_seiten_paritaet.test.ts`, `subscription_header_*`; E2E `issue-943-activity-edit.spec.ts`, `issue-932-activity-type-route-tab.spec.ts`, `trip-hub-kopf-region-aktivitaet.spec.ts`, `hub-kopf-*.spec.ts`, `design-system-trip-vergleich.spec.ts`.

### Scope Assessment
- Dateien: ~25 produktiv + ~25 Tests
- Geschätzt: produktiv +450..550 / −150 LoC (Go ~120, Python ~100, Frontend ~250, Skript ~80)
- Risiko: MITTEL-HOCH — `arrival_calculated` bestimmt bewertete Stunden und Alarme in allen vier Kanälen.
- LoC-Gate zählt nur ungecommittete Zeilen ⇒ EIN Issue/Workflow, Implementierung in zwei Commits (1: Backend + Migration + Paritätstabelle; 2: Frontend), EIN Deploy (vermeidet Mischstand „Frontend schreibt tempo, Go verwirft es"). Kein Issue-Split nötig.

### Technical Approach
Go ist die Quelle der Wahrheit für gespeicherte Ankunftszeiten; Python und Frontend rechnen mit demselben Tempo-Objekt und derselben Ableitung; Paritäts-Falltabelle bewacht alle drei. Migration lazy (sofort wirksam, idempotent) + eager-Skript (Festschreiben mit Sicherung). Zwei-Nutzer-Test für den PUT.

### Risiken
- Mischbetrieb Python schreibt Trip ohne `tempo` zurück → Lazy-Ableitung fängt ab, solange `activity` bleibt.
- Fortbewegungs-Wechsel ändert Gehzeiten → bewertete Stunden/Alarme; Neuberechnung beim Save ist gegeben.
- Altwerte `wandern`/`hiking` in Fixtures → Default `fuss`.

### PO-Entscheidungen 2026-11-20 (per Rückfrage, ersetzen die offenen Fragen)
1. **Gehzeit-Modell = DAV (DIN 33466)** statt heutiger Summenformel: `t = max(t_h, t_v) + min(t_h, t_v)/2`, `t_h = km / v`, `t_v = Hm_auf/R_auf + Hm_ab/R_ab`. PO hat bewusst akzeptiert, dass sich die Gehzeiten **aller** Bestandstrips einmalig ändern (Beispiel 8 km/↑600/↓600: 5:12 → 4:12) und damit die bewerteten Stunden je Wegpunkt. ⇒ Issue-AC-Skizze „Gehzeiten unverändert" ist überholt; Migration erhält Fortbewegung + Grundtempo, nicht die Zeiten. PO-Zitat: „Ich würde das gar nicht so kompliziert machen, sondern einfach das Modell vom DAV oder das Schweizer Modell verwenden und der User kann beim Wandern die Grundgeschwindigkeit eingeben. Aber Wandern ist ja auch nur eine Fortbewegungsform."
2. **Eingabe nur Grundtempo** (eine Zahl je Trip) für alle vier Fortbewegungen. Aufstieg/Abstieg sind NICHT sichtbar, sie folgen Fortbewegung und Grundtempo im selben Verhältnis (`R = R_ref · v / v_ref`).
3. **Wechsel der Fortbewegung setzt das Grundtempo auf den Vorschlagswert.** Vorschläge (Grundtempo · Referenz auf/ab Hm/h bei diesem Tempo): zu Fuß 4 · 300/500 (DAV), Rad 20 · 600/1000, MTB 12 · 500/1000, Ski 3 · 300/1500.

### Folgen für Spec (Tech Lead)
- ADR-0108 Nr. 2 („Tempo flach und Aufstieg") wird durch die PO-Entscheidung geändert ⇒ ADR-0108 vor Annahme anpassen (Status war noch Vorgeschlagen) oder Nachtrags-ADR „Gehzeit nach DAV, nur Grundtempo".
- Datenmodell vereinfacht: `tempo = {fortbewegung, grundtempo_kmh}`; Referenzverhältnisse je Fortbewegung als Konstante (Go-Quelle, Python/TS gespiegelt, Paritätstabelle). Für #3197 Override je Etappe = nur `grundtempo_kmh`.
- Migration: `fahrrad_15/20/25` → `rad` 15/20/25; alles andere → `fuss` 4.
- Mockup zeigt noch „Tempo flach" + „Aufstieg": Karte wird „Fortbewegung" + „Grundtempo"; Kopftext bleibt.
- Alle drei Rechner wechseln auf DAV-Kombination; bestehende Naismith-Tests (Summe) werden ersetzt. Downstream-Wirkung (bewertete Stunden, Alarme) in Staging-E2E prüfen.
- Ruhetag/Pausentag: unverändert (#3197).

## RED-Vertrag (Phase 5, 2026-11-20)

Die RED-Tests legen diese Schnittstellen fest (Developer: genau so bauen):

- Go `internal/model`: `type Tempo struct{Fortbewegung string "fortbewegung"; GrundtempoKmh float64 "grundtempo_kmh"}`, `Trip.Tempo *Tempo` (`json:"tempo,omitempty"`), `DeriveTempo(activity string) Tempo`, `ResolveTempo(*Trip) ActivitySpeeds` (Tempo vor Activity), `DAVHours(distKm, ascM, descM float64, sp ActivitySpeeds) float64`; `ComputeStageArrivals` rechnet DAV je Wegpunkt-Paar. Store: `normalizeTrip` leitet `Tempo` ab, `SaveTrip` nutzt `ResolveTempo`. Handler: `PUT /api/trips/{id}` mit `Optional` `tempo`, ungültig (unbekannte/leere Fortbewegung, ≤0, >60 km/h) → 422.
- Python `core.naismith`: `derive_tempo(activity) -> dict`, `tempo_speeds(trip) -> (flat, auf, ab)`, `dav_hours(km, auf, ab, sp)`; `Trip.tempo: Optional[dict]`, Loader leitet beim Lesen ab und schreibt `tempo`.
- Migration `scripts/migrate_3196_trip_tempo.py`: `main(argv)` mit `--root <data/users> [--backup-dir] [--execute]`, Dateien `<uid>/briefings/*.json`, nur `kind != vergleich`, bestehendes `tempo` bleibt.
- TS `naismith.ts`: `davHours`, `tripTempo(trip)` (liefert `fortbewegung, grundtempo_kmh, flatKmh, ascentMh, descentMh`), `deriveTempo`, `wechsleFortbewegung(tempo, neu)`, `computeArrivalTimes(stage, start, tempo: Tempo)`; Typ `Tempo` in `types.ts`.
- `shared/TempoKarte.svelte`: props `{tempo, onchange?}`, Testids `tempo-karte`, `tempo-fortbewegung-<wert>` (aria-pressed), `tempo-grundtempo` (number). Katalog `trip.tempo.*` (≥7 Schlüssel, DE=EN-Menge).
- Gemeinsame Falltabelle: `tests/fixtures/naismith_dav_paritaet.json`; `trip_schema_full.json` trägt jetzt `tempo`.
- Alt-Tests (Summenformel, Chips) laut Spec-Liste in GREEN ersetzen oder löschen.
