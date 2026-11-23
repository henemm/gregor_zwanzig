# Context: feat-3041-tabelle-beim-anlegen

## Request Summary
Issue #3041 (Epic #3122, ADR-0124): Die Tabelle „Was steht wo" samt Schaltern darunter soll auch auf den Anlegeseiten für Trip und Orte stehen; ihre Angaben gehen in die Anlege-Nutzlast (POST) ein. Anlegen und Bearbeiten derselbe Code; die alte `WetterMetrikenVersandPanel` („Zustellung") verschwindet aus den Anlegeseiten, damit #3036/#3020 sie löschen können.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` | Tabelle; Props `context`, `id` (Pflicht), `saveController`, `enqueueHubWrite`, `onUebernahme`; lädt beim Mount `GET /api/briefings/{id}/placements?kind=` + `/api/auth/profile` (Telegram-Status). Exporte `grundauswahlGeaendert`, `placementsZumMitspeichern`, `nachFremdemSpeichern`. Schalter Z.224-275 |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoStand.ts` | Typ `Placements {version, rows[{metric_id, places, formats}], outlook_reports}`, reine Änderungsfunktionen `mit*` / `antwortMit*` |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts` | Ansichtsmodell aus der GET-Antwort (Stellen, Metriken, SMS-Beispiel, Legende) |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts` | `erstelleTabellenSpeicherung` (PUT `/api/briefings/{id}/placements`, If-Match), `felderNutzlast`/`erstelleFelderSpeicherung` (Trip: `report_config.{show_stage_stats, show_yesterday_comparison, email_format, telegram_style}`, `display_config.show_night_block`; Orte: `hourly_enabled`, `display_config.telegram_style`) |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | Bindet Karte nur bei `{#if !createMode && aboId}` (Z.313) ein; `createMode` + `onAnlegeStand` existieren schon (Z.108 `anlegeSpeicherer`) |
| `frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts` | trägt `placements` beim Speichern mit (Z.57-61, 104); `anlegeSpeicherer` Z.165-173 |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | Schritte route·etappen·wegpunkte·wetter·zustellung; Alt-Panel Z.919/1176; `handleWetterAnlegeStand` Z.480-490 verwirft `placements`; POST `buildAndSave` Z.531-569 |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | `buildCreateTripPayload` Z.275-340: kein `placements`, kein `show_night_block` |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | Schritte vergleich·orte·wetter·zustellung; Alt-Panel Z.525/572; `handleWetterAnlegeStand` Z.181-194; POST `speichereNeuenVergleich` Z.324 |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | `baueVergleichAnlegeRumpf` Z.586-634, `legeVergleichAn` Z.642; kein `placements` („ergänzt der Server, #3237") |
| `frontend/src/lib/components/shared/subscriptionTabs.ts` | `anlegeKette('trip'|'vergleich')` Z.57-107 |
| `internal/handler/trip.go:213`, `internal/handler/compare_preset.go:197` | POST-Handler; rufen `anlageTabelle` |
| `internal/handler/placements.go:117-166` | `anlageTabelle`: mitgeschickte `display_config.placements.rows` bleiben unverändert (kein Kern-Aufruf), sonst `GET …/placements/erstanlage` beim Kern + `SaveBriefingPlacements` |
| `api/routers/placements.py` | `GET /api/briefings/{id}/placements` (braucht gespeichertes Abo, sonst 404), `GET …/placements/erstanlage` (nur für Go-Anlage, schreibt nichts) |
| `src/services/placements_view_service.py` | `build_placements_view`, `erstanlage_placements` |

## Existing Patterns
- Wetter-Reiter hat schon einen Anlege-Modus: `createMode` + `onAnlegeStand` liefern den Stand an den Editor statt PUT (`anlegeSpeicherer`). Die Tabelle braucht dasselbe Muster (Stand nach oben melden statt PUT).
- Go-Anlage übernimmt mitgeschickte Tabelle unverändert (`tabelleMitZeilen`, Test `TestAnlage3237MitgeschickteTabelleBleibtOhneKernAufruf`) → Server-Seite für das Speichern beim Anlegen ist schon da.
- Code-Teilung Trip/Orte über `context="route"|"vergleich"` (Gate, #1170): keine neue Komponente mit Pendant.

## Dependencies
- Upstream: Python-Kern liefert Spalten/Beispielwerte/SMS-Beispiel nur für ein gespeichertes Abo. **Kernhürde:** Für ein ungespeichertes Abo gibt es keinen Vorschau-Endpunkt; die Karte kann beim Anlegen so nicht laden. Optionen für die Analyse: (a) neuer Vorschau-Endpunkt, der die Ansicht aus einem mitgeschickten Entwurf (Grundauswahl/Metriken + Kontext) baut, (b) Vorschau-Ansicht aus `erstanlage`-Logik ohne gespeichertes Abo. Muss zwei Nutzer + `user_id` aus Auth respektieren.
- Downstream: Anlege-POST (Trip/Orte), E2E `hub-anlegen-ablauf.spec.ts` (AN-6: genau ein POST, Körper geprüft), Wächterliste `src/lib/__tests__/bausteine_waechter_regeln.ts:536/586/640`.

## Existing Specs
- `docs/specs/modules/feat_3122_was_steht_wo.md` (Z.154 „Beim Anlegen erscheint die Karte erst mit #3041", Out of Scope Z.328)
- `docs/specs/modules/feat_3237_altpfad_entfernen.md` (Anlage schreibt die Tabelle, AC-1/2/10)
- `docs/specs/modules/feat_3276_vergleich_altfelder_entfernen.md`, `fix_3283_was_steht_wo_optik.md`, `fix_3212_…`
- Anlegen: `rework_2837_s2_anlege_rahmen.md`, `feat_2277_s4_anlege_lockengine.md`, `feat_3198_s4b3_compare_anlegen_ohne_profil.md`
- ADR-0124 `docs/adr/0124-was-steht-wo-eine-tabelle.md` (nichts zum Anlegen)
- Soll-Bild `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` enthält keine Anlege-Ansicht → Anlege-Ansicht = Hub-Ansicht (Anlegen = Bearbeiten, PO-Vorgabe).

## Tests
- Frontend (`node --test`): `organisms/__tests__/was_steht_wo_karte.test.ts`, `shared/wetter-tab/__tests__/was_steht_wo_*.test.ts`, `anlege_vorbelegung.test.ts`, `trip-new/__tests__/*` (u.a. `p11_neuanlage_payload_fixture`, `standardwerte_payload_paritaet_trip`), `compare-new/__tests__/*`.
- Panel-bezogen (fallen beim Entfernen weg/werden umgestellt): `shared/__tests__/wetter_metriken_versand_panel_*`, `s3b2795_*`, `infobox_nur_beim_anlegen`, `anlegen_ohne_autosave`, `compare_new_editor_postet_einmal`, `compare/__tests__/versand_panel_ohne_wrapper_div`, `trip-new/__tests__/trip_new_editor_weather_metrics_wiring`; e2e `trip-new-versand-unter-metriken-konsole.spec.ts`, `compare-neu-kanal-anlegen.staging.spec.ts`.
- E2E: `e2e/was-steht-wo-karte.spec.ts`, `hub-anlegen-ablauf.spec.ts`, `hub-anlegen-paritaet-flaechen.spec.ts`, `anlege-rahmen-paritaet.spec.ts`.
- Go: `briefing_anlage_tabelle_3237_test.go`, `placements_test.go`, `placements_erstanlage_3154_test.go`, `anlage_tabelle_3237_route_test.go`.
- Python: `tests/tdd/test_3237_placements_aus_grundauswahl.py`, `test_placements_tabelle_endpoint.py`.

## Risks & Considerations
- Vorschau ohne gespeichertes Abo (s. Dependencies) — größter Bauteil; Cross-User-Isolation beachten.
- Tabelle hängt an der Metrik-Grundauswahl aus Schritt „Wetter": Änderung der Metriken muss die Vorschau-Tabelle nachziehen (`grundauswahlGeaendert`), ohne Eingaben zu verlieren.
- Schalter-Felder (`show_night_block` u.a.) fehlen heute in der Trip-Anlege-Nutzlast → ergänzen; Orte: `hourly_enabled`/`telegram_style`.
- Warnung aus PR #3042: Karte nie anzeigen, ohne dass die Angaben in die Anlege-Nutzlast gehen (sonst Datenverlust).
- Genau ein POST beim Anlegen (AN-6) beibehalten; kein Autosave im Anlege-Modus.
- Entfernen des Alt-Panels aus den Anlegeseiten: Inhalte des Schritts „Zustellung" (MailInhaltCard, AlarmeTab) bleiben; was das Panel dort sonst noch einstellt (Versandzeiten/Kanäle über `bind:reportConfig`) muss eine Heimat behalten → in der Analyse gegen Hub-Reiter „Versand" abgleichen.
- Umfang: evtl. als Epic-Kinder schneiden (Vorschau-Endpunkt / Trip / Orte), siehe PO-Regel „Epic mit Sub-Issues".

## Analysis

### Type
Feature

### Schnitt (Tech-Lead-Entscheidung)
Gesamtumfang ca. 650–1000 LoC Produktionscode → über LoC-Limit. #3041 wird Eltern-Issue mit vier Kind-Issues, Reihenfolge A → B → C → D:
- **#3304 A** Vorschau-Endpunkt (dieser Workflow): `POST /api/briefings/placements/vorschau?kind=` mit Entwurf im Körper, Antwort exakt wie GET-Ansicht. Rein additiv.
- **#3305 B** Karte im Anlege-Modus + Trip-Anbindung (placements, show_night_block, report_config.* in den POST).
- **#3306 C** Orte-Anbindung (display_config.placements, hourly_enabled, telegram_style).
- **#3307 D** ZustellungTab mit createMode, danach WetterMetrikenVersandPanel aus beiden Anlegeseiten entfernen (macht #3036/#3020 frei, erledigt Anlege-Teil von #3301).

### Affected Files (Teil A, #3304)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/placements_view_service.py | MODIFY | `_trip_abo`/`_orte_abo` in Laden und „aus Objekt bauen" trennen; neue Funktion `build_placements_preview(kind, draft, user_id)`; fehlende rows via `placements_aus_grundauswahl` wie `erstanlage_placements`; `stored=False` |
| api/routers/placements.py | MODIFY | `POST /api/briefings/placements/vorschau` (user_id Query, kind Pflicht → 400 `kind_required`) — Route VOR `/{entity_id}`-Routen registrieren bzw. Pfad ohne Kollision |
| internal/handler/placements.go | MODIFY | `BriefingPlacementsPreviewHandler`: `http.MaxBytesReader` (~256 KB), `forwardPreview` POST, user_id nur aus Auth-Kontext |
| internal/router/router.go | MODIFY | Route registrieren |
| tests (Python tdd, Go handler/router) | CREATE | zwei Nutzer, fremde Orts-IDs, Größe, kind fehlt, Antwortform = GET-Form |

### Scope Assessment (Teil A)
- Files: ~4 Produktion + ~3 Tests
- Estimated LoC: +150–220 Produktion
- Risk Level: LOW–MEDIUM (additiv; Risiko = Cross-User-Leck über Orts-Auflösung, Routen-Kollision mit `{entity_id}`)

### Technical Approach (Teil A)
- Entwurf → `_Abo` ohne Store-Laden für das Abo selbst; Orte (Vergleich) und Ortsnamen weiterhin aus dem Store **des angemeldeten Nutzers** (`load_all_locations(user_id)`), fremde/unbekannte IDs werden ignoriert. Trip: `load_trip` akzeptiert dict (`src/app/loader.py:428`).
- Beispielwerte sind synthetisch (`placements_beispiel.py`), kein Wetterabruf → Vorschau billig.
- Antwortform identisch zur GET-Ansicht, damit `wasStehtWoAnsicht.ts` in B unverändert bleibt.
- Kein ETag/If-Match, nichts wird geschrieben (Test: Store nach Aufruf unverändert).

### Befunde für spätere Teile (nicht verlieren)
- `WasStehtWoKarte` `placementsZumMitspeichern`/`grundauswahlGeaendert` hängen an `antwort.stored` (Z.151-164) → im Anlege-Modus sonst Datenverlust (B).
- `handleWetterAnlegeStand` (TripNewEditor.svelte:480) verwirft placements; `buildCreateTripPayload` ohne show_night_block (B).
- Entprellte Vorschau braucht Sequenznummer gegen späte Antworten (B).
- `ZustellungTab` hat keinen Anlege-Rückkanal (`speicherung` null ohne saveController/id) (D). Panel erst in D entfernen, sonst gehen Versandzeiten/Kanäle (`bind:reportConfig`) verloren.
- Go-Anlage übernimmt mitgeschickte rows ungeprüft (`placements.go:117-130`), wie beim PUT (ADR-0077) — keine neue Lücke, in B im Blick behalten.
- E2E `hub-anlegen-ablauf.spec.ts` AN-6 (genau ein POST, Körper) und Wächterliste `bausteine_waechter_regeln.ts:536/586/640` betreffen B–D.

### Open Questions
- keine Produktfrage offen (Anlegen = Bearbeiten ist PO-Vorgabe; Schnitt ist Tech-Entscheidung).
