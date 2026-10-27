# Context: feature-2277-s2c-compare-from-vorlage

## Request Summary
Issue #2277 (Epic #2345, Etappe P2), Scheibe **S2c**: `/compare/new?from=<id>` belegt die Anlege-Seite mit den Werten eines bestehenden Ortsvergleichs vor (AC-4 des Issues). S1, S2a, S2b sind live; AC-3 (Reiter-Reihenfolge, Lesart offen) und AC-5 (Rückbau) sind bewusst NICHT Teil von S2c.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/routes/compare/new/+page.server.ts` (26 Z.) | lädt nur `/api/locations` + Profil; kein `url`/`from`-Handling, muss `?from=` lesen und das Preset laden |
| `frontend/src/routes/compare/new/+page.svelte` (24 Z.) | instanziiert `CompareWizardState`, `setContext('compare-wizard-state')`; hier müsste die Vorbelegung des Zustands passieren |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` (578 Z.) | liest den Zustand über `getContext`, `bind:value={wiz.name}` etc.; Reiter-Freigabe (Lock-Engine) hängt an `name`/`pickedIds` |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | Zustandsklasse mit allen Feldern (Name, Region, Profil, pickedIds, Korridore, Metriken, Versand, Alarme, Zeitplan) |
| `frontend/src/lib/components/compare/compareHubHydration.ts` | `hydrateAlarmFieldsFromPreset`, `hydrateHubFieldsFromPreset` (Preset → Zustand, Hub-Weg); wiederverwendbar; Versand-/Metrik-Gegenstücke prüfen (`hydrateVersandFieldsFromPreset`, `hydrateWeatherMetricsFromPreset`) |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | `buildNewComparePresetPayload` (Create-POST) — muss vorbelegte Felder unverändert mitschicken |
| `frontend/src/routes/compare/[id]/+page.server.ts` | Vorbild für Preset-Laden inkl. 404-Behandlung (`/api/compare/presets/{id}`) |
| `frontend/src/routes/trips/new/+page.server.ts` `:22-32` | „Trip-Vorbild": lädt `templateTrip` per `?from=` |
| `frontend/src/routes/trips/new/+page.svelte` | **konsumiert `templateTrip` nirgends** (`<TripNewEditor />` ohne Props) |

## Existing Patterns
- Server-Load holt Ressource mit Session-Cookie über die Go-API; die Go-API trennt nach Nutzer (`WithUser`) — eine fremde ID liefert dort 404, kein Leck (im Test mit zwei Nutzern zu belegen).
- Anlege-Editor kapselt Zustand in `CompareWizardState` (Factory im `+page.svelte`, Safari-Reaktivität). Vorbelegung gehört dorthin, nicht in den Editor.
- Hydration Preset → Zustand existiert bereits stückweise für den Hub (Alarme, Korridore, Metriken, Versand).
- `end_date` beim Ortsvergleich: schreiben `""`, lesen FEHLT (Memory `reference_compare_end_date_sentinel_schreiben_vs_lesen`).

## Kernbefunde
1. **Das „Trip-Verhalten" aus AC-4 existiert nicht.** `templateTrip` wird serverseitig geladen, aber im Client nie verwendet; kein UI-Link führt auf `/trips/new?from=` (0 Treffer). Die Vorlagen-Funktion ist im Trip-Pfad tot. AC-4 kann also nicht „wie beim Trip" gebaut werden, sondern ist für Compare neu zu bauen.
2. **Es gibt keinen Einstieg für Nutzer.** Weder für Trip noch für Compare existiert ein Button „Als Vorlage verwenden". Ohne Einstieg ist `?from=` nur per Hand-URL erreichbar. Einstiege gehören laut Epic zu #2278 (Aktionsmodell Liste/Detail/Mobil, P3). Für S2c ist zu entscheiden, ob ein Minimal-Einstieg mitkommt oder ob `?from=` bis #2278 nur per URL nutzbar bleibt.
3. **Geltungsbereich:** Das Issue-Zielbild sagt „`?from=` gilt für beide kinds". Der Trip-Anteil ist der tote Pfad aus Befund 1 und würde einen Trip-Editor-Umbau (Vorbelegung von `TripNewEditor`, 1.170 Z.) bedeuten. Vorschlag: S2c nur Compare; Trip-Anteil als eigene Scheibe/Sammel-Eintrag (#1199), nicht stillschweigend fallenlassen.
4. **Vorlage darf keine Identität mitkopieren:** `id`, ETag, `letzter_versand`, Lauf-/Historien-Felder, Status (aktiv/pausiert) dürfen nicht in den neuen Vergleich übergehen; Name braucht ein Abgrenzungsmerkmal (z. B. Suffix) oder bleibt leer zum Neueintippen — Spec-Entscheidung.
5. **Orte der Vorlage können gelöscht sein** (`location_ids` zeigt ins Leere). Vorbelegung muss auf vorhandene Orte filtern; bei weniger als 2 Orten bleibt der Orte-Reiter gesperrt (Lock-Engine `compareNewLogic`).
6. **Mobil:** `/compare/new` mobil wurde nie im Browser gemessen (Memory #2276 S6g); Staging-Nachweis mit Desktop UND 390 px.

## Dependencies
- Upstream: `GET /api/compare/presets/{id}` (Go-API, ETag), `GET /api/locations`, Hydration-Module des Hubs.
- Downstream: `CompareNewEditor`, `buildNewComparePresetPayload`, POST `/api/compare/presets`. Kein Schema-Eingriff, kein Go-/Python-Code erwartet.

## Existing Specs
- `docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md` (Anlege-Editor Compare)
- `docs/specs/modules/fix_2277_s2a_wertebereiche_trip_anlegen.md`, `fix_2277_s2b_mobile_rahmen_angleichung.md`, `fix_2277_s1_alarme_tab_route.md`
- Vorarbeit: `docs/context/feature-2277-s2-anlege-editor.md` (Schnitt S2a/b/c, Risiko 2 = kaputte Trip-Vorlage)

## Risks & Considerations
- **Cross-User-Leck:** fremde Preset-ID als `from` muss 404/leer ergeben, nie Fremddaten. Test mit zwei Nutzern ist Pflicht.
- **Falsche Übernahme von Zuständen:** Hydration-Funktionen setzen `isEditMode: true` (Hub) — im Anlege-Weg muss `isEditMode` `false` bleiben, sonst kippt der Editor in den Bearbeiten-Modus (`createMode`-Zweige der geteilten Organismen).
- **Teil-Hydration:** Hub-Funktionen decken Korridore, Metriken, Alarme, Versand einzeln ab; Lücken (Region, Zeitplan, Tagesfenster, Ausblick/Stundenverlauf, Kurzform) würden still auf Defaults fallen → Vollständigkeit gegen `CompareWizardState`-Felder prüfen (Mutations-Gegenprobe: je Feld eine Verfälschung).
- **Sentinelwerte:** `null` = „nie eingestellt" vs. `[]` = bewusste Leerauswahl beim Kopieren erhalten (#1191/#1366).
- **LoC:** Schätzung unter 250 (Load + Vorbelegungsfunktion + Tests), ohne Einstiegs-UI.
- **Offene PO-Fragen für die Spec (fachlich, keine Technik):** (a) Einstiegs-Button jetzt oder erst mit #2278? (b) Name der Kopie: leer oder „… (Kopie)"? (c) Trip-`?from=` in eigene Scheibe?

## Analysis

### Type
Feature (Scheibe S2c von #2277, Epic #2345)

### Bestätigte Befunde aus der Code-Prüfung (Phase 2)
- `compare/new/+page.server.ts` liest weder `url` noch `from`; `+page.svelte` erzeugt `CompareWizardState` leer.
- Der Hub (`CompareTabs.svelte:344ff`) besitzt bereits ALLE Preset→Zustand-Hydrierer: `hydrateHubFieldsFromPreset`, `hydrateAlarmFieldsFromPreset`, `hydrateVersandFieldsFromPreset`, `hydrateWeatherMetricsFromPreset`, `hydrateChannelActiveMetricsFromPreset`, `hydrateDayWindowFromPreset`, `hydrateLayoutFieldsFromPreset`. Es muss keine neue Mapping-Logik erfunden werden — nur eine **Komposition** dieser Funktionen für den Anlege-Weg.
- `hydrateHubFieldsFromPreset` liefert `isEditMode: true`; `CompareWizardState.isEditMode` steht im Anlege-Weg auf `false` und darf nicht überschrieben werden (Ergebnisfeld beim Übertragen auslassen).
- `name`, `region`, `pickedIds` (aus `location_ids`), `hourlyMetricKeys`, `outlookMetricKeys/-Formats`, `hourlyEnabled/outlookEnabled`, `schedule/weekday`, `endDate` haben KEINEN gemeinsamen Hydrierer — hier Lücken-Gefahr (still Default).
- `saveNewPreset()` baut den Payload aus dem Zustand; `id`/ETag/`letzter_versand` sind dort nicht enthalten → Identität wird strukturell nicht mitkopiert.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/routes/compare/new/+page.server.ts` | MODIFY | `?from=` lesen, Preset per Session laden (404/fremd → `null`, kein Fehler) |
| `frontend/src/routes/compare/new/+page.svelte` | MODIFY | Zustand einmalig aus `data.vorlage` vorbelegen |
| `frontend/src/lib/components/compare-new/compareNewVorlage.ts` | CREATE | reine Funktion `vorlageInZustand(preset, locations, state)`: komponiert die Hub-Hydrierer, filtert gelöschte Orte, setzt Name, lässt `isEditMode` false |
| `frontend/src/lib/components/compare-new/__tests__/compareNewVorlage.test.ts` | CREATE | Node-Test je Feld (Mutations-Gegenprobe), Sentinel `null` vs. `[]` |
| `frontend/e2e/…` (Staging-Spec) | CREATE | Zwei-Nutzer-Test (fremde ID ⇒ leer), Desktop + 390 px |

### Scope Assessment
- Files: 5 (3 produktiv, 2 Test)
- Estimated LoC: +150 / -5 (produktiv ~80)
- Risk Level: MEDIUM — kein Schema-/Backend-Eingriff, aber Cross-User-Leck-Risiko und stille Default-Lücken bei Teil-Hydration

### Technical Approach
1. Server-Load: `from` aus `url.searchParams`; `GET /api/compare/presets/{id}` mit Session-Cookie; bei nicht-OK → `vorlage: null` (Seite fällt still auf leere Anlage, kein 500). Nutzertrennung übernimmt die Go-API (`WithUser`).
2. Neue reine Funktion in `compare-new/` komponiert die vorhandenen Hydrierer; Zustandsübertragung einmalig beim Seitenaufbau (nicht reaktiv, damit spätere Nutzereingaben nicht überschrieben werden).
3. Nicht kopieren: `id`, ETag, Lauf-/Versand-Historie, Aktiv-Status. Orte filtern auf existierende `locations`; <2 Orte ⇒ Orte-Reiter bleibt durch Lock-Engine gesperrt.
4. Sentinel-Semantik erhalten: `null` (nie eingestellt) bleibt `null`, `[]` bleibt `[]`; `end_date` fehlt ⇒ `null`.
5. Trip-Anteil (`/trips/new?from=` ist toter Pfad, `templateTrip` wird nirgends konsumiert) NICHT in S2c — Erfassung als Eintrag in #1199 bzw. Folge-Scheibe.

### Dependencies
Upstream: `GET /api/compare/presets/{id}`, `/api/locations`, Hub-Hydrierer. Downstream: `CompareNewEditor` (liest Zustand über Context), `saveNewPreset`. Kein Go-/Python-Code.

### Open Questions (Entscheidung fällt in der Spec, ohne PO-Technikfragen)
- [ ] Einstiegs-Button „Als Vorlage verwenden": Empfehlung — NICHT in S2c, gehört zu #2278 (Aktionsmodell); `?from=` bleibt bis dahin per URL erreichbar. (Fachliche Rückfrage an Henning in der Spec-Freigabe.)
- [ ] Name der Kopie: Empfehlung „<Name> (Kopie)" — verhindert versehentliche Namensdoppelung.
- [ ] Trip-`?from=` als eigene Scheibe/Sammel-Eintrag.
