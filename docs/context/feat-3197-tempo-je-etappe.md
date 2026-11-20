# Context: feat-3197-tempo-je-etappe

## Request Summary
Issue #3197 (S4b-2, Teil von #2796 / Epic #2791, ADR-0108): Je Etappe im Reiter Etappen „Gehzeit h:mm“ plus „Tempo ändern“ (Überschreibung des Trip-Tempos nur für diese Etappe, z. B. Ruhetag/Bergetappe). Ohne Überschreibung gilt das Trip-Tempo. Nur die überschriebene Etappe ändert Gehzeit und bewertete Stunden ihrer Wegpunkte, in allen vier Kanälen gleich (ADR-0095).

## Related Files
| File | Relevance |
|------|-----------|
| src/app/trip.py:97-115 | `Stage` (frozen dataclass) – neues optionales Feld nötig; Trip.tempo :207-208 |
| src/app/loader.py:487-551, 1874-1884, 2192-2200 | Tempo-Ableitung, Stage-Parse/Serialize, Compute-on-Save (arrival_calculated) |
| src/core/naismith.py:62-83, 131-199 | `speeds_for_tempo`, `tempo_speeds(trip)` (einziger Auflösungspunkt), `dav_hours`, `compute_stage_arrivals(stage, speeds)` |
| src/services/trip_segments.py:52-61, 198-201 | Ankunftsauflösung für Kanäle; Self-Heal nur wenn alle arrival_calculated None |
| src/services/stage_weather.py:38-54 | scoped Trip je Etappe mit `tempo=trip.tempo` |
| src/services/trip_forecast.py:139 | Ankunftsauflösung |
| internal/model/trip.go:106-112, 133-136 | Go `Stage` (kein Catch-all!), Trip.Tempo |
| internal/model/naismith.go:39-41, 108, ~121 | Go `Tempo`, `ResolveTempo`, `DAVHours` |
| internal/store/trip.go:80-85, 319-324 | DeriveTempo, SaveTrip → ComputeStageArrivals |
| internal/model/trip_schema_drift_test.go, tests/test_trip_schema_drift.py | Schema-Drift-Gates je Ebene (Trip/Etappe/Wegpunkt) |
| frontend/src/lib/types.ts:37-40, 63, 397-399 | TS Tempo, Stage, Trip.tempo |
| frontend/src/lib/utils/naismith.ts | STANDARD_TEMPO, tempoSpeeds, tripTempo, computeArrivalTimes |
| frontend/src/lib/components/edit/etappenListe.ts:13,31,57-68 | `gehzeitMinuten(stage,tempo)`, `etappenZeile` → Gehzeit existiert schon; Kommentar: Button „Tempo ändern“ (i18n `trip.hub.tempo_aendern` vorhanden) fehlt noch |
| frontend/src/lib/components/edit/EditStagesPanelNew.svelte:215-232, ~1020-1040 | tempoLokal/tempoAktiv, Live-Ankünfte, Listenzeile, TempoKarte |
| frontend/src/lib/components/edit/EditStagesSection.svelte:23,26 | Wrapper, mobile Liste |
| frontend/src/lib/components/shared/TempoKarte.svelte, organisms/tempo-karte/TempoKarteInhalt.svelte | Trip-Tempo-Editor (Fortbewegung + Grundtempo) – wiederverwendbar für Override |
| frontend/.../trip-detail/__tests__/tempo_karte_3196.test.ts | prüft „überschreibbar“-Text abwesend bis #3197 (muss angepasst werden) |

## Existing Patterns
- Trip-Tempo `{fortbewegung, grundtempo_kmh}`; Raten R = R_ref·v/v_ref; DAV t = max(t_h,t_v)+min/2 (Python/Go/TS gespiegelt).
- Kanäle lesen persistierte `arrival_calculated` → Override muss beim Speichern (Python loader + Go store) wirken.
- Lazy-Migration/Ableitung statt Replace; RMW-Merge-Pflicht (CLAUDE.md).

## Dependencies
- Upstream: Trip.tempo (#3196, ausgeliefert), DAV-Rechnung.
- Downstream: Risk Engine, alle vier Kanal-Renderer über arrival_calculated; Frontend-Live-Vorschau.

## Existing Specs
- docs/specs/modules/feat_3196_trip_tempo_etappen.md (:32, :54, :114-115, :199 – #3197 nur grundtempo_kmh je Etappe)
- docs/adr/0108-vorlage-und-tempo-getrennt.md (Override je Etappe nur Grundtempo)
- docs/context/feat-3196-trip-tempo-etappen.md (:61 Ruhetag gehört zu #3197; :73, :84-87 Feld `Stage.tempo` feldweise)
- Mockup docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:693-700 (Zeile: „Gehzeit …“ + Button „Tempo ändern“, kein Dialog ausgestaltet)

## Risks & Considerations
- WIDERSPRUCH: ADR-0108/Spec #3196 sagen „nur Grundtempo je Etappe“; Issue-Text sagt „Tempo flach/Aufstieg“; Kontext-Doc #3196 nennt feldweise Override. ADR ist bindend → nur `grundtempo_kmh` je Etappe (Steigraten skalieren mit v/v_ref, also wirkt es auf flach UND Aufstieg). Fortbewegung bleibt Trip-weit.
- Go-Stage hat kein Catch-all: neues Feld in Go UND Python UND TS + Schema-Drift-Fixtures, sonst Datenverlust beim Round-Trip.
- Self-Heal in trip_segments.py heilt nur bei komplett leeren Ankünften – bestehende Trips ohne Override unberührt (gut), aber Konsistenz Go/Python-Save muss gleich rechnen.
- stage_weather.py baut scoped Trip mit trip.tempo → Override dort mitnehmen.
- Ruhetag (Pausentag) als Sonderfall prüfen (Issue nennt Ruhetage).
- Kanal-Parität: Test je Kanal, dass nur Wegpunkte der überschriebenen Etappe andere Stunden zeigen.

## Analysis

### Type
Feature

### Datenform (Tech-Lead-Entscheidung)
- `Stage.grundtempo_kmh` — optionale Zahl, absolut (km/h), Bereich 0,5–60 wie Trip-Grundtempo. Go `*float64 json:"grundtempo_kmh,omitempty"`, Python `Optional[float] = None`, TS `grundtempo_kmh?: number`.
- Verworfen: `Stage.tempo:{…}` (Verschachtelung nur sinnvoll, wenn Fortbewegung je Etappe überschreibbar — ADR-0108 schließt das aus); Faktor relativ zum Trip-Tempo (wandert still mit, schwer erklärbar).
- Auflösung je Etappe: Fortbewegung immer vom Trip, Grundtempo = `stage.grundtempo_kmh ?? trip.grundtempo_kmh`. Raten R = R_ref·v/v_ref ⇒ Override wirkt auf flach UND Aufstieg/Abstieg (löst den Issue-Wortlaut „flach/Aufstieg“ ADR-konform auf).
- Wechsel der Trip-Fortbewegung: Etappen-Overrides werden verworfen (Wechsel setzt Grundtempo schon heute auf Vorschlagswert, `TempoKarteInhalt.svelte:26-27`; ein 3-km/h-Override zu Fuß ist auf dem Rad sinnlos). Hinweis an den Nutzer, wie viele Etappen zurückgesetzt wurden. Nur Frontend (`tempoAendern`, `EditStagesPanelNew.svelte:221`); Backend prüft nur 0,5–60.
- Pausentag (Etappe ohne Wegpunkte): kein Knopf „Tempo ändern“, keine Gehzeit.
- Ungültiger gespeicherter Wert (außer Bereich/kein Zahlwert): Loader ignoriert ihn ⇒ Trip-Tempo (wie `valid_tempo`); Go-PUT antwortet 422.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/app/trip.py:97 | MODIFY | Stage-Feld `grundtempo_kmh` |
| src/app/loader.py:509-550, 1874-1890, 2197-2200 | MODIFY | Parse/Serialize (omitempty), Compute-on-Save je Etappe |
| src/core/naismith.py:75 | MODIFY | neu `stage_speeds(trip, stage)` neben `tempo_speeds` |
| src/services/trip_segments.py:198-201 | MODIFY | Self-Heal mit `stage_speeds` |
| internal/model/trip.go:106-112 | MODIFY | Go-Stage-Feld |
| internal/model/naismith.go:108 | MODIFY | neu `ResolveStageTempo(trip, stage)` |
| internal/store/trip.go:319-324 | MODIFY | SaveTrip je Etappe auflösen |
| internal/handler/trip.go (~296, ~410) | MODIFY | Validierung 0,5–60 je Stage, 422 |
| frontend/src/lib/types.ts:63 | MODIFY | TS-Stage-Feld |
| frontend/src/lib/utils/naismith.ts:83-89 | MODIFY | neu `stageTempo(stage, tripTempo)` |
| frontend/src/lib/components/edit/etappenListe.ts:31-67 | MODIFY | Gehzeit mit Etappen-Tempo, Markierung „eigenes Tempo“ |
| frontend/src/lib/components/edit/EditStagesPanelNew.svelte:219-231, 1022-1036 | MODIFY | Knopf „Tempo ändern“, Grundtempo-Feld + „Trip-Tempo verwenden“, Live-Ankünfte, Fortbewegungswechsel verwirft Overrides |
| frontend/src/lib/components/organisms/tempo-karte/TempoKarteInhalt.svelte | MODIFY | Prop `nurGrundtempo` (Fortbewegung ausblenden) — keine neue Doppel-Komponente |
| frontend/src/lib/components/mobile/StageCardM.svelte:55 | MODIFY | Etappen-Tempo |
| frontend/src/lib/i18n/messages/{de,en}/trip.json | MODIFY | Zusatz „je Etappe überschreibbar“, „Trip-Tempo verwenden“, ggf. Hinweis Reset |
| tests/fixtures/trip_schema_full.json, tests/test_trip_schema_drift.py, internal/model/trip_schema_drift_test.go | MODIFY | Drift-Gates um Stage-Feld |
| frontend/.../tempo_karte_3196.test.ts:62, molecules/__tests__/listenzeile_3007.test.ts:323 | MODIFY | sichern heute „kein überschreibbar/kein Tempo ändern“ |
| docs/reference/api_contract.md:1245-1275 | MODIFY | Stage-Feld dokumentieren |
| tests (neu) | CREATE | Parität Python/Go/TS mit Override auf 1 von 2 Etappen; PUT→GET-Roundtrip; Kanal-Parität (nur Wegpunkte der überschriebenen Etappe andere Stunden) |

Nicht betroffen: Ortsvergleich (keine Etappen), `compute_stage_arrivals`/`ComputeStageArrivals`/`computeArrivalTimes` selbst (bekommen Speeds/Tempo), `stage_weather.py` (scoped Trip trägt Stage mit Feld; rechnet nur über Self-Heal), `scripts/migrate_3196_trip_tempo.py` (Einmal-Migration, Bestand hat keine Overrides).

### Scope Assessment
- Files: ~15–18
- Estimated LoC: Python ~60, Go ~50, Frontend ~150, Tests ~250 ⇒ ~+500/-30
- Risk Level: MEDIUM (dreifach gespiegelte Rechnung; Datenverlust-Gefahr ohne Feld in allen drei Schichten; Bestand unberührt, keine Migration)

### Technical Approach
Ein Durchlauf (Backend ohne UI hat keinen Nutzen). Reihenfolge: RED (Parität, Roundtrip, Drift, Kanal) → Modellfeld + Auflösungsfunktion + Aufrufer (Py/Go/TS) → UI → Alt-Tests anpassen. Aufrufer lösen Speeds je Etappe statt einmal vor der Schleife auf.

### Dependencies
Upstream #3196 (Trip.tempo, DAV) ausgeliefert. Downstream: alle vier Kanäle lesen persistierte `arrival_calculated` ⇒ Wirkung entsteht beim Speichern (Go SaveTrip + Python _write_trip_locked).

### Open Questions
- keine Produktfrage offen; Verhalten bei Fortbewegungswechsel und Pausentag wird als AC in die Spec geschrieben (PO sieht es bei der Spec-Freigabe).
