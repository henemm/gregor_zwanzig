# Context: feature-3198-compare-anlegen-ohne-profil

Issue #3198 (S4b-3) · Teil von #2796 (Einstellungen neu S4) · Epic #2791 · ADR-0108 · Vorgänger S4a (PR #3126, Spec `docs/specs/modules/feat_2796_s4a_orte_vorlage_statt_profil.md` v1.1)

## Request Summary
Beim Anlegen eines Orts-Vergleichs entfallen die Aktivitätsprofil-Kacheln; maßgeblich ist allein die Vorlage im Reiter Wetter, wie seit S4a im Bearbeiten (ADR-0097: Anlegen und Bearbeiten sind derselbe Code). Für jede übrige Fundstelle von `ACTIVITY_PROFILE_OPTIONS` festhalten, ob sie entfällt oder einen anderen Zweck hat.

S4a-Spec Z. 99/135 hat die Anlege-Kette ausdrücklich für dieses Folge-Issue ausgespart.

## Related Files (Stand `origin/main` c3f5e01fc)
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | Kacheln Desktop (Z. 562-579) und Mobil (Z. 649-668), `selectProfile`/`profileMetricsLabel` (Z. 331-338), `stateOverride.activityProfile` (Z. 111, 135), `wetterAbo.profil = wiz.activityProfile` (Z. 175), Payload `activityProfile` (Z. 347), Ampel nur in `display_config`, wenn der Reiter Wetter einen Stand gemeldet hat (Z. 388-393) |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | `buildNewComparePresetPayload`: `profil: fields.activityProfile ?? 'wandern'` (Z. 467); `compareFeldsatzStandard().activityProfile = null` (Z. 646); Bearbeiten-Pfad `profil: edits.activityProfile ?? original.profil` (Z. 235) |
| `frontend/src/lib/components/shared/wetter-tab/anlegeVorbelegung.ts` | `vergleichVorbelegung` belegt Wertebereiche (corridors) beim Anlegen aus dem Profil vor (ohne Profil: ALLGEMEIN), Z. 120-133 |
| `frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts` | `standAusAbo`: Vorlagen-ID = template → preset_name → profil → `allgemein` (Z. 89-112) |
| `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts:48` | `STANDARD_VORLAGE = 'allgemein'` |
| `src/app/ampel.py:185-202` | Python `template_id_for` (gleiche Rückfallkette) und `profile_for_template` (allgemein ⇒ keine Bewertungsvorgabe ⇒ Ortsprofil wirkt) |
| `frontend/src/lib/components/compare/CreateGroupDialog.svelte:86-98` | Ortsgruppe anlegen: „Standard-Profil“ der Gruppe (Ortsebene, nicht Vergleich) |
| `frontend/src/lib/components/compare/LocationNewModal.svelte:73, 224` | Ort anlegen: Profil-Kacheln setzen `activity_profile` des **Orts** |
| `frontend/src/lib/components/LocationForm.svelte:53-139` | Ort bearbeiten: Profil-Auswahl des **Orts** |
| `frontend/src/lib/components/compare/locationHelpers.ts:56-77` | Orts-Filter nach `activity_profile` (Issue #132) |
| `frontend/src/routes/locations/+page.svelte:162` | Ortsliste zeigt Orts-Profil als Badge |
| `frontend/src/lib/types.ts:141-153` | `ACTIVITY_PROFILE_OPTIONS` + Compiler-Abdeckungsprüfung |
| Hub-Sicht-Lesepfade (`compareHubHydration.ts:64`, `versandVergleichSpeicherung.ts:157`, `wertebereicheVergleichSpeicherung.ts:68`, `weatherMetricsCompareSave.ts`, `alarmeVergleichSpeicherung.ts:153`) | lesen `preset.profil` nur als Rückfall in den Feldsatz; S4a hat das Schreiben von `profil` im Hub beendet |

## Existing Patterns
- S4a im Hub: Kopf ohne Profil, Vorlagenname aus `ampel.template` mit Rückfallkette über `profil`; `profil` bleibt gespeichert (ADR-0101), wird aber nicht mehr geschrieben.
- `/compare/new?from=<id>` (Issue #2277 S2c): Vorbelegung einmalig aus einem bestehenden Vergleich (`feldsatzAusVorlage`).
- Anlege-Kette Vergleich · Orte · Wetter · Zustellung (#2794 S3a); der Reiter Wetter meldet Ampel + Auswahl per `onAnlegeStand` zurück.

## Dependencies
- Upstream: WetterTab (Vorlagen-Picker), Vorlagen-Katalog, `vergleichVorbelegung`, Go-Create (`POST /api/compare/presets`, Feld `profil` optional).
- Downstream: Versand/Bewertung (`profile_for_template(template_id_for(preset))`), Mail-Kopf (Vorlagenname), Hub-Hydration.

## Existing Specs
- `docs/specs/modules/feat_2796_s4a_orte_vorlage_statt_profil.md` (v1.1)
- `docs/specs/modules/feat_2277_s2c_compare_from_vorlage.md`
- `docs/adr/0108-vorlage-und-tempo-getrennt.md`, ADR-0097 (Code-Teilung), ADR-0101 (Daten nie löschen)

## Risks & Considerations
1. **Widerspruch im Ist-Zustand (fachlich relevant):** Ohne gewähltes Profil zeigt der Reiter Wetter die Vorlage „Allgemein“, die Neuanlage schickt aber `profil: 'wandern'`. Aktiviert jemand, ohne dass der Reiter Wetter einen Stand gemeldet hat (keine `ampel` in der Nutzlast), löst der Server über `profil` zur Vorlage „Wandern“ auf — anders als angezeigt. Nach Wegfall der Kacheln wäre das der Normalfall; die Analyse muss festlegen, dass die Neuanlage immer die angezeigte Vorlage speichert (z. B. `ampel.template` immer mitschicken, `profil` nicht mehr aus dem Anlegen ableiten).
2. **Wertebereiche-Vorbelegung** (`vergleichVorbelegung`) hängt am Profil; ohne Profil immer ALLGEMEIN. Prüfen, ob sie der gewählten Vorlage folgen soll oder ob die Wertebereiche durch die Ampel der Vorlage abgelöst sind.
3. `?from=<id>`: Vorlage mit gespeichertem `profil` aber ohne `ampel.template` muss weiterhin dieselbe Vorlage ergeben (Rückfallkette).
4. Orts-Profil (LocationNewModal, LocationForm, CreateGroupDialog, Filter, Badge) hat einen anderen Zweck: Bewertung je Ort, wenn die Vorlage keine Vorgabe macht (S4a F1). Voraussichtlich bleibt es; in der Spec je Fundstelle begründen.
5. Tests/E2E, die die Kacheln anklicken (`compare-editor-profile-*`), müssen angepasst werden (u. a. `frontend/e2e/compare-new-vorlage.spec.ts`, `issue-344-wetter-profile.spec.ts`, `issue-609-sms-profil.spec.ts`, Unit-Tests mit `stateOverride.activityProfile`).
6. i18n: Katalogschlüssel `vergleich.neu.aktivitaetsprofil` / `profil_hinweis` werden ggf. verwaist (Ratschen-Test für ungenutzte Schlüssel prüfen).
7. Kein Python-/Mail-Inhalt geplant ⇒ Renderer-Gate voraussichtlich nicht betroffen; Go-Create unverändert.

## Analysis

### Type
Feature (mit Nebenbefund-Fix: angezeigte vs. gespeicherte Vorlage bei Neuanlage)

### Kernbefunde
1. **Go-Create verlangt ein gültiges `profil`** (`internal/handler/compare_preset.go:126`, `validateComparePreset` → `IsValidProfile(normalizeProfile(...))`, kein Default). Leeres/fehlendes `profil` ⇒ HTTP 400. „profil nicht mehr schreiben" geht ohne Go-Eingriff nicht.
2. **Widerspruch Ist-Zustand bestätigt:** „Mit Standardwerten speichern" (`CompareNewEditor.svelte` ~Z.460) speichert ohne Wetter-Besuch ⇒ keine `display_config.ampel` ⇒ Python `template_id_for` (`src/app/ampel.py`) fällt über `profil='wandern'` auf Vorlage „Wandern" zurück, Oberfläche zeigt „Allgemein".
3. **Einziger fachlicher Python-Leser von Compare-`profil`** ist die Rückfallkette in `ampel.py` (`_aufloesen` → `template_for_profil`). Mail-Kopf zeigt `vorlage_label`; SMS/Telegram/profile_signature lesen kein Compare-`profil`. Hub-Lesepfade reichen `profil` nur durch.
4. Trip-Pendant (TripNewEditor) nicht Teil dieses Issues.

### Technical Approach (Entscheidung Tech Lead)
- Neuanlage schickt **konstant `profil: 'allgemein'`** (gültig für Go, neutral) statt `fields.activityProfile ?? 'wandern'` (`compareEditorSave.ts:467`). `profil` wird damit beim Anlegen nicht mehr aus einer Nutzerwahl abgeleitet.
- Neuanlage schickt **immer `display_config.ampel` mit `template`**: nach Wetter-Besuch die volle Ampel aus `onAnlegeStand` (unverändert, trägt `template`); ohne Besuch `{ template: <angezeigte Vorlage> }` — `validate_ampel` verlangt keine `metrics`, `_verschmelzen` füllt aus der Vorlage. Damit gilt serverseitig immer die angezeigte Vorlage.
- Neues Feldsatz-Feld für die Vorlage der Neuanlage (Standard `STANDARD_VORLAGE='allgemein'`), Quelle für `wetterAbo` statt `wiz.activityProfile` (Z.175).
- `?from=<id>` (`compareNewVorlage.ts` `feldsatzAusVorlage`): Vorlage ausdrücklich ableiten — `dc.ampel` der Quelle übernehmen, sonst `vorlageIdFuer(dc.ampel, dc.preset_name, preset.profil, …)` (`alerts-tab/alarmAbAnzeige.ts:66`) bzw. reine Rückfallkette wie `standAusAbo`. Quelle mit `profil=WINTERSPORT` ohne `ampel.template` ⇒ Neuanlage mit Vorlage „Wintersport" (Regressionstest Pflicht).
- `activityProfile` bleibt im `CompareFeldsatz`-Typ (Bearbeiten-Pfad `compareEditorSave.ts:235` reicht `original.profil` durch, ADR-0101), wird aber aus der Anlege-Kette (Kacheln, `selectProfile`, `profileMetricsLabel`, `stateOverride.activityProfile`, `wetterAbo`, Payload) entfernt.
- **Wertebereiche-Vorbelegung** (`vergleichVorbelegung`): bleibt bei ALLGEMEIN (ohne Profil — wie heute, wenn keine Kachel gewählt wird). Begründung: Bewertung läuft über die Ampel der Vorlage (ADR-0108); die Vorbelegung an eine später änderbare Vorlagenwahl zu koppeln, würde ein zweites Mapping einführen. Signatur unverändert. Sichtbare Folge in der Spec benennen.

### Fundstellen `ACTIVITY_PROFILE_OPTIONS` / Profil-Auswahl
| Stelle | Entscheidung | Grund |
|---|---|---|
| `CompareNewEditor.svelte` Kacheln Desktop (Z.562-579) + Mobil (Z.649-668), `selectProfile`/`profileMetricsLabel` (Z.331-338), Importe | entfällt | Issue-Ziel; Vorlage im Reiter Wetter maßgeblich |
| `CreateGroupDialog.svelte:86-98` | bleibt | Standard-Profil der Ortsgruppe (Orts-Ebene) |
| `LocationNewModal.svelte:73,224`, `LocationForm.svelte:53-139` | bleibt | `activity_profile` des Orts; Engine nutzt es, wenn die Vorlage keine Vorgabe macht (`comparison_engine.py:406`, S4a F1) |
| `locationHelpers.ts:56-77` (Filter #132), `routes/locations/+page.svelte:162` (Badge) | bleibt | gehören zum Orts-Profil |
| `types.ts:141-153` | bleibt | von den Orts-Stellen gebraucht |

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Kacheln/Handler raus, Vorlagen-Feld als Quelle für `wetterAbo`, Ampel immer in `display_config` |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `profil: 'allgemein'` fest in `buildNewComparePresetPayload`; Vorlagen-Feld im Feldsatz-Standard |
| `frontend/src/lib/components/compare-new/compareNewVorlage.ts` | MODIFY | Vorlage aus `?from=`-Quelle ableiten |
| `frontend/messages/{de,en}/vergleich.json` | MODIFY | `vergleich.neu.aktivitaetsprofil`, `vergleich.neu.profil_hinweis` entfernen (Ratsche `katalog_schluessel_haben_verwender.test.ts`) |
| `frontend/src/lib/.../f10KatalogAnker.ts:164-165` | MODIFY | Anker der entfernten Schlüssel raus |
| Unit-Tests: `compare_new_preset_payload.test.ts`, `compare_feldsatz_standard_startwerte.test.ts`, `compareNewVorlage.test.ts`, `standardwerte_payload_paritaet_compare.test.ts`, `compare_new_editor_postet_einmal.test.ts`, `compareNeuEditorPruefstand.ts`, `anlege_vorbelegung.test.ts` | MODIFY | Erwartungen anpassen + neue Fälle (Ampel ohne Besuch, `from=`) |
| E2E: `compare-editor-slice3.spec.ts:40`, `layout-tab-vergleich.spec.ts:38`, `compare-editor-fidelity-s8d.spec.ts:183-189`, `hub-anlegen-ablauf.spec.ts:119-122` | MODIFY | Kachel-Schritte streichen bzw. auf Vorlagenwahl umstellen |
| `tests/golden/f10_vergleich_flaechen/anlegen_vergleich.{de,en}.html`, `anlegen_toast.*` | MODIFY | neu erzeugen |

Nicht betroffen: Go, Python, Mail-Inhalt (Renderer-Gate nicht berührt). `issue-344-wetter-profile.spec.ts`, `issue-609-sms-profil.spec.ts` meinen ein anderes „Profil".

### Scope Assessment
- Produktivcode: ~6 Dateien, ca. +40/−70 LoC; Tests ~8 Unit, ~4 E2E, Goldens
- Risk Level: MEDIUM (Speicherweg der Neuanlage; Regression `?from=`; 400 bei falschem `profil` vermieden durch `'allgemein'`)

### Reihenfolge
1) RED: Payload ohne Wetter-Besuch enthält `ampel.template='allgemein'` und `profil='allgemein'`; `from=` Wintersport-Quelle ohne template ⇒ Vorlage Wintersport; keine Kacheln im DOM. 2) `compareEditorSave.ts`. 3) Vorlagen-Feld + `compareNewVorlage.ts`. 4) Editor. 5) i18n/Anker. 6) E2E + Goldens.

### Open Questions
- keine PO-Frage offen (Vorbelegung der Wertebereiche bleibt „Allgemein" wie bisher ohne Kachelwahl; in der Spec als sichtbares Verhalten benennen)
