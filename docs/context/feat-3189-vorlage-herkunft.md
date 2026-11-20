# Context: feat-3189-vorlage-herkunft

## Request Summary
Issue #3189 (PO-Entscheid 20.11.): Beim Speichern einer eigenen Wetter-Vorlage (Reiter Wetter, „Als eigene Vorlage speichern“, Trip und Orts-Vergleich, geteilter Code) merkt sich die App die Herkunft. Unterzeile im Vorlagen-Menü: ohne Beschreibung „eigene · aus <Name> gespeichert“, mit Beschreibung „eigene · <Beschreibung>“. DE+EN über den Katalog (ADR-0104). Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` Z.357/Z.490 (`EIGENE=[['Mallorca Frühling','eigene · aus GR221 gespeichert']]`).

## Related Files
| Datei | Zeilen | Relevanz |
|---|---|---|
| internal/model/metric_preset.go | 45-65 | `MetricPreset` (id,name,description omitempty,kind,is_default,metrics,created_at,ampel omitempty); hier Feld ergänzen |
| internal/handler/metric_preset.go | 28-50 (createPresetRequest), 236-300 (Create), 341-420 (Patch), 223 (List) | Create baut `MetricPreset` aus Request (~Z.281-290); Patch hat keinen Herkunfts-Pfad; List gibt Struct zurück |
| internal/store/metric_preset.go | 26-55 (Load), 56-142 (`migrateMetricPreset`), 144 (Save) | Load läuft über map-basierte Migration: unbekannte Felder werden NICHT durchgereicht, jedes neue Feld muss hier explizit gelesen werden (sonst Datenverlust beim nächsten Save, vgl. `ampel` ~Z.134) |
| frontend/src/lib/types.ts | 366-377 | `MetricPreset` TS-Typ |
| frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts | 223-243 | `EigeneVorlageEingabe` + `eigeneVorlagePayload` (schreibt description nur wenn nicht leer) |
| frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte | Props 17-27, submit 60-80 | ruft `eigeneVorlagePayload({name,beschreibung,alsStandard,kind,ampel})`; kennt Trip-/Vergleichsnamen nicht |
| frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts | 23 (`EigeneVorlage`), 84-95 (`eigeneVorlageAus`, `eigeneVorlagen`) | Abbildung `MetricPreset` -> `EigeneVorlage` (Beschreibung wird hier mitgenommen) |
| frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte | 60-63 (`eigeneUnterzeile`), 122-131 (Menüzeile), 147 (`<SavePresetDialog>`) | Unterzeile heute „eigene“ + ` · ` + Beschreibung |
| frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte | 36-49 (Props `trip`, `preset`, `createMode`), 77 (`aboId`), 197-206 (`vorlageGespeichert`), 261-270 (VorlageKarte) | Namensquelle: `trip?.name` bzw. `preset.name`; frisch gespeicherte Vorlage ohne Neuladen via `eigeneVorlageAus(POST-Antwort)` |
| frontend/src/lib/i18n/messages/{de,en}/wetter.json | Z.22 `wetter.vorlage.eigene_unterzeile`, Z.132 `wetter.dialog.gespeichert` | neuer Schlüssel für „aus {name} gespeichert“ |
| scripts/staging_pruefkonto_mockupdaten.py | ~346 | Prüfkonto-Vorlage trägt die Mockup-Zeile als `description` „aus GR221 gespeichert“ (#3192/#3151) |
| frontend/e2e/s3a2794-teil3-vorlage.spec.ts | 157-190 | #3192 AC-8: speichert MIT Beschreibung, erwartet `eigene · <Beschreibung>` ohne Neuladen |
| frontend/e2e/elementliste_abgleich_logik.ts | 518-520 | `EIGENE_VORLAGE_BESCHREIBUNG = 'aus GR221 gespeichert'` |

Python: `MetricPreset` wird in `src/`/`api/` NICHT gespiegelt (grep ohne Treffer); ein Python-DTO entfällt entgegen Issue-Text. `docs/reference/api_contract.md` listet nur die Routen `/api/metric-presets` (Z.276-277), keine Feldtabelle: Eintrag ergänzen.

## Existing Patterns
- Optionales Feld mit `omitempty` + explizites Lesen in `migrateMetricPreset` (Muster `description`, `ampel`, `kind`).
- Frontend-Payload: optionale Felder nur bei Inhalt (`...(beschreibung ? {description} : {})`).
- Unterzeile als Join mit ` · ` aus Katalogtexten (`$t`); Nutzernamen werden nie übersetzt.
- Geteilter Code Trip/Vergleich: `WetterTabInhalt` mit `context` (route|vergleich), keine Kontext-Zweige nötig.
- Menü-Update ohne Neuladen: `vorlageGespeichert` -> `eigeneVorlageAus(POST-Antwort)`; Create antwortet mit voller Struct, Herkunft kommt also zurück.

## Dependencies
- Create/Patch/List-Handler und Store (`migrateMetricPreset`), Datenexport (generisch, prüfen), Frontend-Typen, i18n-Parität (Tests `deutsch_unveraendert.test.ts`, `wetter_tab_i18n.test.ts` führen Schlüssellisten).
- Mehrnutzer: Datei je Nutzer `data/users/<id>/metric_presets.json`, Handler mit `s.WithUser(UserIDFromContext)`; Herkunft enthält nur eigene IDs/Namen des Nutzers.

## Existing Specs/ADRs
- docs/specs/modules/feat_3111_wetter_dialoge_mockup.md (AC-5 Unterzeile „eigene“ + Beschreibung), fix_3192_wetter_dialog_abgleich.md (AC-3/AC-8), feat_2794_s3a_teil3_wetter.md §5 (Dialog).
- ADR-0104 (i18n/Katalog), ADR-0083 (Schreibsperre Metrik-Vorlagen, `LockMetricPresets`), ADR-0106 (Profil-Ampel an Vorlage), ADR-0108 (Vorlage/Tempo getrennt). Kein ADR zu Herkunft; additives optionales Feld ändert keine Entscheidung, kein neues ADR nötig.

## Risks
- `migrateMetricPreset` vergisst das Feld -> stiller Verlust beim nächsten Save (Round-Trip-Test Load/Save). Bestand ohne Feld bleibt gültig (nil).
- PATCH ohne Herkunft muss das Feld unverändert lassen (Struct-Merge); Herkunft wird nur beim Create gesetzt.
- Anlege-Kette (`createMode`): Trip/Vergleich existiert noch nicht, kein Name/ID -> keine Herkunft; Unterzeile fällt auf „eigene“ zurück (wie Bestand).
- Trip/Vergleich später umbenannt oder gelöscht: eingefrorener Name bleibt stehen (bewusst, siehe Approach 2).
- Bestehender E2E #3192 AC-8 und Prüfdatensatz (Beschreibung) bleiben grün, da Beschreibung Vorrang hat; neuer AC für den Fall ohne Beschreibung nötig.
- Herkunftsname kommt vom Client: trimmen, Länge begrenzen (200), nur als Text anzeigen (Svelte escaped).

## Analysis

### Type
Feature (kleine, additive Datenmodell-Erweiterung, Go + Frontend, Trip und Vergleich gemeinsam).

### Affected Files (with changes)
| Datei | Änderung |
|---|---|
| internal/model/metric_preset.go | neues `Herkunft *PresetHerkunft` mit `json:"herkunft,omitempty"`; Typ `{ID string "id", Name string "name"}`; die Art ist bereits `Kind` der Vorlage (route\|vergleich) und wird nicht doppelt gespeichert |
| internal/handler/metric_preset.go | `createPresetRequest.Herkunft`; Name trimmen, auf 200 Zeichen kappen, leerer Name = Feld verwerfen; in Create übernehmen; Patch unverändert (Feld bleibt erhalten) |
| internal/store/metric_preset.go | `migrateMetricPreset`: `herkunft` (map id/name) lesen |
| frontend/src/lib/types.ts | `herkunft?: { id: string; name: string }` an `MetricPreset` |
| ampelSchreiben.ts | `EigeneVorlageEingabe.herkunft?`; Payload schreibt `herkunft` nur mit nicht leerem Namen |
| SavePresetDialog.svelte | neue optionale Prop `herkunft`, an Payload durchreichen |
| VorlageKarte.svelte | Prop `herkunft` an Dialog; `eigeneUnterzeile`: Beschreibung > Herkunft > nur „eigene“ |
| WetterTabInhalt.svelte | `herkunft` ableiten `{id: aboId, name: (trip ?? preset).name}` (nicht bei `createMode`, nur mit Name) |
| wetterTabLaden.ts | `EigeneVorlage.herkunftName?`; `eigeneVorlageAus` füllt es aus `p.herkunft?.name` |
| i18n de/en wetter.json | neu `wetter.vorlage.eigene_aus_herkunft`: DE „aus {name} gespeichert“, EN „saved from {name}“; Schlüssellisten in beiden i18n-Tests ergänzen |
| docs/reference/api_contract.md | `herkunft` bei POST `/api/metric-presets` |
| scripts/staging_pruefkonto_mockupdaten.py, e2e-Logik | optional: Prüf-Vorlage mit `herkunft` statt Beschreibung, damit die Mockup-Zeile die neue Logik zeigt (in Spec entscheiden) |
| Tests | Go: Create speichert Herkunft, List liefert sie, Patch lässt sie unberührt, Altbestand ohne Feld lädt/speichert unverändert, ZWEI Nutzer getrennt; node --test: Payload, `eigeneVorlageAus`, Unterzeilen-Priorität DE+EN; e2e: neuer Fall ohne Beschreibung „eigene · aus <Name> gespeichert“ für route und vergleich (neben AC-8) |

### Scope Assessment
Etwa 9 Quelldateien plus Tests/Doku, rund 120-160 LoC Produktivcode; keine Python-Änderung, kein neues ADR. Ein Workflow genügt.

### Technical Approach
1. Feld `herkunft {id, name}` (Pointer-Struct, `omitempty`) am Go-`MetricPreset`; Art = vorhandenes `kind`. Minimal, keine Doppelung. `id` wird mitgespeichert (später Verlinkung/Löschprüfung ohne Migration). Alternative nur `source_name` ist ärmer bei fast gleichem Aufwand. Bestand ohne Feld bleibt gültig (nil).
2. Name zum Speicherzeitpunkt EINFRIEREN, nicht live auflösen: „aus GR221 gespeichert“ ist ein Ereignis der Vergangenheit; Umbenennen oder Löschen des Trips soll die Aussage nicht verfälschen oder leer machen. Live-Auflösung bräuchte zusätzliches Laden aller Trips/Vergleiche im Wetter-Reiter plus Löschfall-Sonderlogik.
3. Store/Handler: `migrateMetricPreset` liest `herkunft`; Create übernimmt validiert; Patch bleibt ohne Herkunftsfeld (Read-Modify-Write, Feld bleibt).
4. Frontend: `WetterTabInhalt` leitet die Herkunft aus `trip`/`preset` ab und reicht sie über `VorlageKarte` an `SavePresetDialog`; `eigeneVorlagePayload` schreibt sie; `eigeneVorlageAus` nimmt den Namen mit.
5. Unterzeile: Beschreibung vorhanden -> „eigene · <Beschreibung>“; sonst Herkunft -> „eigene · aus <Name> gespeichert“ (neuer Katalogschlüssel DE/EN, Name unübersetzt); sonst „eigene“.
6. Frisch gespeichert ohne Neuladen läuft über die POST-Antwort (enthält Herkunft).
7. Tests wie oben (zwei Nutzer, Altbestand, DE+EN), Prüfkonto-Seed und api_contract nachziehen.

### Befunde gegen den Plan
- Issue-Text nennt „Python-DTO“: existiert nicht, `MetricPreset` lebt nur in Go und Frontend.
- „Besitzer-Einträge“ (#2913): laut PO-Kommentar keine mehr an #3189, nichts zu übernehmen.
- Falle: `migrateMetricPreset` ist map-basiert; ohne Eintrag dort geht das Feld beim ersten Save verloren, auch bei korrektem Create.
- Mockup-Zeile existiert schon als Prüfdatensatz-Beschreibung (#3192); Beschreibung hat Vorrang, AC-8 und Seed bleiben grün.
- Anlege-Kette (`createMode`): keine Herkunft möglich, Unterzeile nur „eigene“.

### Open Questions
Keine echte Produktfrage offen. Technisch entschieden: Name eingefroren; Beschreibung hat Vorrang vor Herkunft (PO-Text).
