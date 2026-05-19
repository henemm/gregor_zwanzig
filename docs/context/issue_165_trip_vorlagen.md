# Context: Issue #165 — Trip-Vorlagen

## Request Summary

Rechte Spalte in Step 2 des Trip-Wizards: 3 Schnellauswahl-Vorlagen (GR20, Karnischer Höhenweg, Stubaier Höhenweg). Klick auf Vorlage befüllt `wizard.stages` mit vorbereiteten GPS-Wegpunkten und setzt sinnvolle Defaults für `activity` und `name`.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | Hier wird die rechte Spalte eingebaut — Layout von Single-Column auf Two-Column umstellen |
| `frontend/src/lib/components/trip-wizard/templates/` | Zielverzeichnis für `TemplatePicker.svelte` + statische Template-Daten (`.gitkeep` vorhanden) |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | `WizardState.addStage()` bereits mit Kommentar zu #165 vorbereitet (Z.164); stages/activity/name/shortcode direkt mutierbar |
| `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` | `newId()`, `addDays()`, `formatStageNumber()`, `isPauseStage()` — werden von TemplatePicker gebraucht |
| `frontend/src/lib/types.ts` | `Stage`, `Waypoint`, `ActivityType` — Typen für Template-Daten |
| `docs/specs/modules/epic_136_step5_templates.md` | Sub-Spec-Stub (status: stub) — **MUSS in Phase 3 ausgefüllt werden** |
| `docs/specs/modules/epic_136_trip_wizard.md` | Master-Spec — nennt `TemplatePicker.svelte` explizit als Ziel-Komponente |
| `data/users/default/gpx/KHW_*.gpx` | 13 reale GPX-Dateien für den Karnischen Höhenweg — GPS-Koordinaten bereits extrahiert |
| `examples/stubai_skitour.json` | Nur Skitour-Daten (kein Höhenweg) — nicht direkt nutzbar für Summer-Trekking-Vorlage |

## Existing Patterns

- **Zwei-Spalten-Layout**: Derzeit kein Beispiel im Wizard — aber im Trip-Detail-View gibt es Side-by-Side-Patterns. Frontend ist Desktop-First (CLAUDE.md).
- **Stage-Erstellung**: `wizard.addStage(stage)` setzt automatisch `suggested: true` auf alle Waypoints (Z.163–171). Template-Stages müssen `waypoints.map()` also mit confirmed Waypoints befüllen — kein `suggested`-Flag setzen.
- **Statische Daten im Frontend**: KHW-Vorlage kann aus extrahierten GPX-Koordinaten hard-coded werden. GR20 + Stubai müssen als statische TypeScript-Objekte angelegt werden.
- **WizardState-Mutation**: Vorlagen überschreiben `wizard.stages = [...]` direkt (analog zu DnD-Finalize in Step2Stages.svelte Z.136). Dann `wizard.recomputeStageDates()` aufrufen.

## KHW-Koordinaten (aus existierenden GPX-Dateien extrahiert)

Alle 13 Etappen inkl. Start/End-Koordinaten:

| Etappe | Start (lat, lon, m) | Ziel (lat, lon, m) |
|--------|--------------------|--------------------|
| KHW_00a Troblach → Helmhotel | 46.72475, 12.22542, 1212 | 46.73042, 12.32164, 1144 |
| KHW_00b Helmhotel → Sillianer Hütte | 46.73042, 12.32164, 1142 | 46.70606, 12.40627, 2377 |
| KHW_01 Sillianer Hütte → Obstansersee | 46.70607, 12.40627, 2441 | 46.68427, 12.49369, 2312 |
| KHW_02 Obstansersee → Porzehütte | 46.68427, 12.49369, 2297 | 46.65972, 12.58220, 1930 |
| KHW_03 Porzehütte → Hochweißsteinhaus | 46.65972, 12.58220, 1950 | 46.64301, 12.74033, 1815 |
| KHW_04 Hochweißsteinhaus → Wolayersee | 46.64301, 12.74033, 1867 | 46.61229, 12.86717, 1953 |
| KHW_05 Wolayersee → Valentinalm | 46.61241, 12.86704, 1949 | 46.62285, 12.93057, 1200 |
| KHW_06 Valentinalm → Zollnersee Hütte | 46.62285, 12.93057, 1190 | 46.60538, 13.07065, 1751 |
| KHW_07 Zollnersee → Straniger Alm | 46.60539, 13.07064, 1729 | 46.59567, 13.13447, 1504 |
| KHW_08 Straniger Alm → Nassfeld | 46.59571, 13.13440, 1515 | 46.55762, 13.27852, 1522 |
| KHW_09 Nassfeld → Egger Alm | 46.55762, 13.27852, 1532 | 46.58570, 13.38018, 1396 |
| KHW_10 Egger Alm → Dolinza Alm | 46.58570, 13.38018, 1408 | 46.56405, 13.47916, 1483 |
| KHW_11 Dolinza → Nötsch im Gailtal | 46.56405, 13.47916, 1468 | 46.59079, 13.62275, 560 |

## GR20-Koordinaten (hard-coded, bekannte Hütten)

15 Etappen (klassische Nordroute, Calenzana → Conca):

| Etappe | Start | Hütte/Ziel (lat, lon, m) |
|--------|-------|--------------------------|
| 1 Calenzana → Ortu di u Piobbu | 42.509, 8.848, 275 | 42.478, 8.903, 1520 |
| 2 Ortu → Carrozzu | 42.478, 8.903, 1520 | 42.452, 8.907, 1270 |
| 3 Carrozzu → Ascu Stagnu | 42.452, 8.907, 1270 | 42.448, 8.916, 1422 |
| 4 Ascu → Tighjettu | 42.448, 8.916, 1422 | 42.423, 8.950, 1683 |
| 5 Tighjettu → Ciottulu di i Mori | 42.423, 8.950, 1683 | 42.392, 9.008, 1991 |
| 6 Ciottulu → Manganu | 42.392, 9.008, 1991 | 42.298, 9.009, 1601 |
| 7 Manganu → Petra Piana | 42.298, 9.009, 1601 | 42.268, 9.041, 1842 |
| 8 Petra Piana → L'Onda | 42.268, 9.041, 1842 | 42.245, 9.077, 1430 |
| 9 L'Onda → Vizzavona | 42.245, 9.077, 1430 | 42.128, 9.135, 1163 |
| 10 Vizzavona → E'Capannelle | 42.128, 9.135, 1163 | 41.959, 9.233, 1586 |
| 11 E'Capannelle → Usciolu | 41.959, 9.233, 1586 | 41.935, 9.147, 1750 |
| 12 Usciolu → Asinau | 41.935, 9.147, 1750 | 41.895, 9.125, 1536 |
| 13 Asinau → Paliri | 41.895, 9.125, 1536 | 41.758, 9.197, 1055 |
| 14 Paliri → Conca | 41.758, 9.197, 1055 | 41.666, 9.330, 252 |

## Stubaier Höhenweg-Koordinaten (hard-coded, klassische 7-Tage-Route)

| Etappe | Start | Ziel (lat, lon, m) |
|--------|-------|---------------------|
| 1 Fulpmes → Franz-Senn-Hütte | 47.157, 11.329, 937 | 47.131, 11.206, 2147 |
| 2 Franz-Senn → Neue Regensburger | 47.131, 11.206, 2147 | 47.062, 11.048, 2286 |
| 3 Neue Regensburger → Sulzenauhütte | 47.062, 11.048, 2286 | 46.993, 11.068, 2191 |
| 4 Sulzenauhütte → Nürnberger Hütte | 46.993, 11.068, 2191 | 46.986, 11.119, 2280 |
| 5 Nürnberger → Dresdner Hütte | 46.986, 11.119, 2280 | 47.075, 11.110, 2302 |
| 6 Dresdner → Starkenburger Hütte | 47.075, 11.110, 2302 | 47.152, 11.280, 2237 |
| 7 Starkenburger → Neustift | 47.152, 11.280, 2237 | 47.099, 11.314, 1000 |

## Dependencies

- **Upstream (was TemplatePicker braucht):** `WizardState` (stages, activity, name, shortcode, recomputeStageDates), `newId()` aus wizardHelpers, `ActivityType` + `Stage` + `Waypoint` aus types
- **Downstream (was TemplatePicker beeinflusst):** Step2Stages.svelte erhält rechte Spalte; canAdvanceStep2 wird `true` nach Template-Auswahl

## Existing Specs

- `docs/specs/modules/epic_136_trip_wizard.md` — Master-Spec (approved), definiert TemplatePicker.svelte als Zielkomponente
- `docs/specs/modules/epic_136_step5_templates.md` — Sub-Spec-Stub (status: stub, muss ausgefüllt werden)
- `docs/specs/modules/epic_136_step2_stages.md` — Step 2 Sub-Spec (approved, implementiert)

## Risks & Considerations

1. **GR20/Stubai-Koordinaten hard-coded**: Nicht aus echten GPX-Tracks — ausreichend genau für Wetterprognosen (~1–2 km), aber leichte Abweichungen von tatsächlicher Route möglich
2. **Stages-Überschreiben**: Template-Auswahl ersetzt alle bestehenden Stages — User muss gewarnt werden wenn bereits Stages vorhanden sind (optional: Bestätigungs-Dialog)
3. **Step2-Layout-Änderung**: Zwei-Spalten-Layout darf die bestehende Drop-Zone nicht kaputt machen; das Layout muss auf kleinen Bildschirmen stabil bleiben (Desktop-First, aber nicht Desktop-Only)
4. **Kein Backend nötig**: Feature ist rein Frontend — keine API-Änderungen, keine GPX-Uploads, keine neuen Endpunkte
5. **Etappen-Anzahl**: KHW hat 13 Etappen (inkl. 00a/00b) — das ist viel für Step 2. Vorlage könnte die klassischen 11 (KHW_01–KHW_11) nehmen.
