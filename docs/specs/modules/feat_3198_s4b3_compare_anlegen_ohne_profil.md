---
entity_id: feat_3198_s4b3_compare_anlegen_ohne_profil
type: module
created: 2026-11-21
updated: 2026-11-21
status: draft
version: "1.0"
workflow: feature-3198-compare-anlegen-ohne-profil
tags: [compare, anlegen, vorlage, profil, i18n, epic-2791]
---

# Einstellungen neu S4b-3: Orts-Vergleich anlegen ohne Aktivitätsprofil-Kacheln, die Vorlage ist maßgeblich (#3198)

## Approval

- [ ] Approved

## Purpose

Beim Anlegen eines Orts-Vergleichs stehen noch die Aktivitätsprofil-Kacheln „Allgemein · Wintersport · Wandern · Sommer-Trekking“ (am Handy als Knopf). Seit S4a (#2796) gibt es sie im Bearbeiten nicht mehr; maßgeblich ist die Vorlage im Reiter Wetter (ADR-0108). Anlegen und Bearbeiten sind derselbe Code (ADR-0097), also entfallen die Kacheln auch beim Anlegen. Zugleich wird ein Widerspruch behoben: Wer ohne Besuch des Reiters Wetter speichert, sieht „Allgemein“, bekommt aber heute serverseitig „Wandern“.

Grundlagen: Issue #3198, Teil von #2796, Epic #2791; ADR-0108 (Vorlage und Tempo getrennt), ADR-0097 (geteilter Code), ADR-0101 (Bestandsdaten bleiben); Vorgänger-Spec `docs/specs/modules/feat_2796_s4a_orte_vorlage_statt_profil.md` (hat die Anlege-Kette ausdrücklich für dieses Folge-Issue ausgespart); Kontext `docs/context/feature-3198-compare-anlegen-ohne-profil.md`.

## Source

- **File:** `frontend/src/lib/components/compare-new/CompareNewEditor.svelte`
- **Identifier:** Anlege-Editor des Orts-Vergleichs (Kacheln, `selectProfile`, `profileMetricsLabel`, `wetterAbo`, Speicher-Nutzlast)

> Schicht: nur Frontend (SvelteKit). Go-API und Python-Core bleiben unverändert (siehe Out of Scope).

## Scope

Scheibe S4b-3 von #2796 (Einstellungen neu S4): Anlege-Editor des Orts-Vergleichs ohne Aktivitätsprofil-Kacheln (Desktop und Mobil); Speichern legt immer die angezeigte Vorlage fest; `?from=<id>` übernimmt die Vorlage der Quelle; verwaiste Katalogtexte DE/EN entfallen. Nur Frontend. Kanäle: Keine Änderung an Inhalt oder Format von E-Mail, Telegram, SMS und Premium-SMS; alle vier Kanäle lesen die Vorlage wie bisher über den Server, die Kanal-Parität (ADR-0095) ist nicht berührt.

## Estimated Scope

- **LoC:** Produktivcode ca. +40/−70, dazu Tests und Goldens
- **Files:** ca. 6 Produktivdateien, ca. 8 Unit-Testdateien, 4 E2E-Specs, Goldens; Scope für den Deploy: frontend-only
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WetterTab` (shared, Vorlagen-Auswahl) | Komponente | Vorlage wird dort gewählt, meldet Stand per `onAnlegeStand` zurück |
| `compareEditorSave.ts` (`buildNewComparePresetPayload`, `compareFeldsatzStandard`) | Modul | Nutzlast der Neuanlage, Feldsatz-Standard |
| `compareNewVorlage.ts` (`feldsatzAusVorlage`) | Modul | Vorbelegung bei `?from=<id>` |
| `wetter-tab/ampelModell.ts` (`STANDARD_VORLAGE = 'allgemein'`) | Modul | angezeigte Standardvorlage |
| `wetter-tab/wetterZustand.ts` (`standAusAbo`), `alerts-tab/alarmAbAnzeige.ts` (`vorlageIdFuer`) | Module | Rückfallkette Vorlage: template → preset_name → profil → allgemein |
| `wetter-tab/anlegeVorbelegung.ts` (`vergleichVorbelegung`) | Modul | Wertebereiche-Vorbelegung, Signatur unverändert |
| `src/app/ampel.py` (`template_id_for`, `profile_for_template`) | Python (nur lesend betroffen) | Server löst Vorlage und Bewertungsprofil auf |
| Go `POST /api/compare/presets` (`validateComparePreset`) | API | verlangt gültiges `profil`, kein Default |
| `frontend/messages/{de,en}/vergleich.json`, `frontend/src/lib/components/compare/__tests__/f10KatalogAnker.ts` | Katalog | verwaiste Schlüssel entfernen |

## Implementation Details

Technische Entscheidungen (Tech Lead, nicht neu zu verhandeln):

1. **Neuanlage schickt konstant `profil: 'allgemein'`** statt `fields.activityProfile ?? 'wandern'` (`compareEditorSave.ts`). Grund: Go verlangt ein gültiges `profil` (kein Default, sonst HTTP 400); „allgemein“ ist neutral. `profil` wird beim Anlegen nicht mehr aus einer Nutzerwahl abgeleitet.
2. **Neuanlage schickt immer `display_config.ampel` mit `template`.** Nach Besuch des Reiters Wetter die volle Ampel aus `onAnlegeStand` (unverändert). Ohne Besuch `{ template: <angezeigte Vorlage> }`; der Server füllt die Metriken aus der Vorlage. Damit gilt serverseitig immer die angezeigte Vorlage (Nebenbefund-Fix).
3. **Neues Feldsatz-Feld für die Vorlage der Neuanlage** (Standard `STANDARD_VORLAGE`), Quelle für `wetterAbo` statt `wiz.activityProfile`.
4. **`?from=<id>`:** `feldsatzAusVorlage` übernimmt `ampel.template` der Quelle; ohne dieses Feld gilt die Rückfallkette (`vorlageIdFuer`: preset_name → profil → allgemein). Quelle mit `profil=wintersport` ohne `ampel.template` ergibt die Vorlage „Wintersport“.
5. **`activityProfile` bleibt im Typ `CompareFeldsatz`:** Der Bearbeiten-Pfad reicht `original.profil` unverändert durch (ADR-0101). Aus der Anlege-Kette entfernt werden Kacheln (Desktop und Mobil), `selectProfile`, `profileMetricsLabel`, `stateOverride.activityProfile`, `wetterAbo.profil = wiz.activityProfile` und die Importe.
6. **Wertebereiche-Vorbelegung bleibt „Allgemein“** (`vergleichVorbelegung` ohne Profil, Signatur unverändert). Sichtbare Folge: Beim Anlegen sind die Wertebereiche immer mit den Allgemein-Werten belegt, auch wenn der Nutzer im Reiter Wetter eine andere Vorlage wählt; die Bewertung kommt aus der Ampel der Vorlage (ADR-0108). Das entspricht dem bisherigen Verhalten ohne Kachelwahl. Eine Kopplung an die später änderbare Vorlage würde ein zweites Mapping einführen.

### Fundstellen `ACTIVITY_PROFILE_OPTIONS` / Profil-Auswahl

| Stelle | Entscheidung | Grund |
|---|---|---|
| `CompareNewEditor.svelte` Kacheln Desktop und Mobil, `selectProfile`, `profileMetricsLabel`, Importe | **entfällt** | Ziel des Issues; Vorlage im Reiter Wetter maßgeblich |
| `CreateGroupDialog.svelte` (Standard-Profil der Ortsgruppe) | bleibt | Ortsebene, nicht Vergleich |
| `LocationNewModal.svelte`, `LocationForm.svelte` (`activity_profile` des Orts) | bleibt | Bewertung je Ort, wenn die Vorlage keine Vorgabe macht (S4a F1, `comparison_engine`) |
| `locationHelpers.ts` (Orts-Filter, Issue #132), `routes/locations/+page.svelte` (Badge) | bleibt | gehören zum Orts-Profil |
| `types.ts` (`ACTIVITY_PROFILE_OPTIONS` + Compiler-Abdeckungsprüfung) | bleibt | von den Orts-Stellen gebraucht |

## Expected Behavior

- **Input:** Nutzer legt einen Orts-Vergleich an (leer oder per `?from=<id>`), mit oder ohne Besuch des Reiters Wetter.
- **Output:** Keine Profil-Auswahl; gespeichert wird die angezeigte Vorlage (`ampel.template`), `profil` ist konstant „allgemein“.
- **Side effects:** Keine Änderung an Bestandsdaten; Bearbeiten bestehender Vergleiche unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet „Orts-Vergleich anlegen“ am Computer (1280 px) / When er den Anlege-Editor betrachtet / Then gibt es keine Aktivitätsprofil-Kacheln („Allgemein · Wintersport · Wandern · Sommer-Trekking“) und keinen Hinweistext dazu; Name, Orte, Wetter und Zustellung sind unverändert bedienbar.
  - Test: E2E 1280×900 (DE und EN) — keine Profil-Kacheln im Editor, Anlege-Ablauf bis zum Speichern möglich; Unit am Editor ohne Kacheln.
- **AC-2:** Given derselbe Anlege-Editor am Handy (390 px) / When er betrachtet wird / Then gibt es keinen Profil-Knopf und keine Profil-Auswahl mehr.
  - Test: E2E 390×844 — kein Profil-Knopf, keine Profil-Auswahl, Speichern funktioniert.
- **AC-3:** Given ein Nutzer legt einen Orts-Vergleich an, ohne den Reiter Wetter zu öffnen / When er speichert / Then wird die angezeigte Vorlage „Allgemein“ gespeichert (Nutzlast mit `display_config.ampel.template='allgemein'` und `profil='allgemein'`), der Hub zeigt „Allgemein“, und Versand und Bewertung nutzen „Allgemein“ und nicht mehr „Wandern“.
  - Test: Unit auf die echte Nutzlast der Neuanlage; E2E Anlegen ohne Wetter-Besuch → Hub-Übersicht zeigt „Allgemein“; Server-Auflösung `template_id_for` auf die gespeicherte Nutzlast ergibt „allgemein“.
- **AC-4:** Given ein Nutzer wählt beim Anlegen im Reiter Wetter die Vorlage „Wintersport“ / When er speichert und den neuen Vergleich im Hub bzw. im Bearbeiten öffnet / Then steht dort die Vorlage „Wintersport“ (Name in der Sprache des Nutzers), und das Speichern geschieht genau einmal.
  - Test: E2E Vorlage wählen → anlegen → Hub und Bearbeiten zeigen „Wintersport“ (DE/EN); Unit `compare_new_editor_postet_einmal`.
- **AC-5:** Given ein bestehender Vergleich mit `profil=wintersport` und ohne `ampel.template` / When der Nutzer „Anlegen aus Vorlage“ (`/compare/new?from=<id>`) öffnet und speichert / Then ist die Vorlage „Wintersport“ vorausgewählt und wird gespeichert; hat die Quelle ein `ampel.template`, wird dieses übernommen.
  - Test: Unit `compareNewVorlage` mit beiden Quellen (Regression Pflicht); E2E Anlegen per `?from=` → Hub zeigt die erwartete Vorlage.
- **AC-6:** Given Ort anlegen, Ort bearbeiten, Ortsgruppe anlegen, Orts-Filter und Orts-Liste / When der Nutzer sie nutzt / Then ist das Orts-Profil dort unverändert wählbar, filterbar und als Badge sichtbar (es steuert die Bewertung je Ort, wenn die Vorlage keine Vorgabe macht).
  - Test: bestehende Unit-/E2E-Tests von `LocationNewModal`, `LocationForm`, `CreateGroupDialog`, `locationHelpers` und der Ortsliste bleiben unverändert grün.
- **AC-7:** Given ein bestehender Orts-Vergleich mit gespeichertem `profil` (beliebiger Wert) / When der Nutzer ihn im Hub bearbeitet und speichert / Then bleibt das gespeicherte `profil` unverändert und es werden keine Bestandsdaten verändert oder gelöscht (ADR-0101).
  - Test: Unit Bearbeiten-Pfad (`profil` aus `original.profil` durchgereicht, Vorher/Nachher-Vergleich des Vergleichs-Objekts).
- **AC-8:** Given ein Nutzer legt einen Vergleich an und öffnet danach den Reiter Wertebereiche / When die Werte betrachtet werden / Then sind sie mit den Werten „Allgemein“ vorbelegt, unabhängig von der im Reiter Wetter gewählten Vorlage.
  - Test: Unit `anlege_vorbelegung` (Vorbelegung ohne Profil = Allgemein); E2E Wintersport wählen → Wertebereiche zeigen Allgemein-Werte.
- **AC-9:** Given die Kataloge DE und EN / When sie geprüft werden / Then sind `vergleich.neu.aktivitaetsprofil` und `vergleich.neu.profil_hinweis` in beiden Sprachen entfernt (samt Anker in `f10KatalogAnker.ts`), es sind keine neuen Nutzertexte hinzugekommen, und die Katalog-Ratschen (Parität, Schlüssel haben Verwender) sind grün.
  - Test: bestehende Katalog-Ratschen `katalog_schluessel_haben_verwender.test.ts` und Paritätstests; die Golden-Dateien (DE/EN) zeigen den Anlege-Editor ohne Profil-Block.
- **AC-10:** Given zwei verschiedene Nutzer legen je einen Orts-Vergleich an / When beide speichern / Then liegt jeder Vergleich nur unter dem eigenen Nutzer, mit der jeweils gewählten Vorlage, und keiner sieht den des anderen.
  - Test: Staging-E2E mit zwei Nutzern (unterschiedliche Vorlage); Änderung berührt Mandantentrennung nicht, wird aber wegen des Speicherwegs abgesichert.

## Definition of Done

- AC-1 bis AC-10 durch benannte Tests grün (Unit `node --test` und Playwright gegen Staging); Adversary mit Mutations-Gegenprobe ohne offenen Befund.
- Im Anlege-Editor ist am Computer und am Handy keine Profil-Auswahl mehr sichtbar; ein ohne Besuch des Reiters Wetter angelegter Vergleich zeigt im Hub die Vorlage „Allgemein“.
- Goldens neu erzeugt (Diff nur Kachel-Wegfall), Katalog-Ratschen grün.
- Alle sechs CI-Checks grün, Staging-Verifikation, Prod-Deploy, Prod-Selftest Exit 0.

## Test Plan

### Automated Tests (TDD RED, ohne Mock-Theater)

- **RED zuerst:** Nutzlast ohne Wetter-Besuch enthält `display_config.ampel.template='allgemein'` und `profil='allgemein'`; `?from=` mit Wintersport-Quelle ohne template ergibt Vorlage „Wintersport“; keine Kacheln im gerenderten Editor.
- **Unit (anpassen und ergänzen):** `compare_new_preset_payload.test.ts`, `compare_feldsatz_standard_startwerte.test.ts`, `compareNewVorlage.test.ts`, `standardwerte_payload_paritaet_compare.test.ts`, `compare_new_editor_postet_einmal.test.ts`, `compareNeuEditorPruefstand.ts`, `anlege_vorbelegung.test.ts`; Katalog-Ratsche `katalog_schluessel_haben_verwender.test.ts`.
- **E2E (Playwright, gegen Staging):** `compare-editor-slice3.spec.ts`, `layout-tab-vergleich.spec.ts`, `compare-editor-fidelity-s8d.spec.ts`, `hub-anlegen-ablauf.spec.ts`: Kachel-Schritte streichen bzw. auf Vorlagenwahl im Reiter Wetter umstellen; neuer Ablauf „anlegen ohne Wetter-Besuch → Hub zeigt Allgemein“ und „Vorlage Wintersport wählen → Hub zeigt Wintersport“.
- **Goldens neu erzeugen:** `tests/golden/f10_vergleich_flaechen/anlegen_vergleich.{de,en}.html`, `anlegen_toast.*`.
- Nicht betroffen: `issue-344-wetter-profile.spec.ts`, `issue-609-sms-profil.spec.ts` (anderes „Profil“).
- **Mutations-Gegenprobe (Adversary):** Neuanlage schickt wieder `profil: 'wandern'` bzw. lässt `ampel.template` ohne Wetter-Besuch weg; `?from=` ignoriert `profil` der Quelle; Kacheln wieder eingeblendet. Jede Verfälschung muss ein Test fangen.

## Known Limitations

- Der Trip-Pendant (`TripNewEditor`) ist nicht Teil dieses Issues; er behält seine Aktivitätsauswahl bis zu seiner eigenen S4b-Scheibe.
- `profil` bleibt im Datenmodell gespeichert (Go verlangt es); neue Vergleiche tragen konstant „allgemein“, ältere ihren bisherigen Wert als Rückfall-Quelle.
- Die Vorbelegung der Wertebereiche folgt der Vorlage nicht (AC-8); Bewertung kommt aus der Ampel.
- AC-9 und AC-6 stehen beim Schlüssel `vergleich.neu.aktivitaetsprofil` im Widerspruch: „Ort bearbeiten“ (`LocationForm.svelte`) nutzt ihn als Beschriftung des Orts-Profils, das nach AC-6 unverändert bleiben muss. AC-6 hat Vorrang: Der Schlüssel bleibt in DE und EN, entfernt wird nur `vergleich.neu.profil_hinweis` (samt Anker). Im Anlege-Editor des Vergleichs wird keiner der beiden Schlüssel mehr verwendet. Prüfung von AC-9 daher: `profil_hinweis` weg, `aktivitaetsprofil` nur noch in `LocationForm.svelte` verwendet, Katalog-Ratschen grün.

## Out of Scope

Trip-Anlegen (`TripNewEditor`), Go-API (Create bleibt unverändert), Python-Core, Mail-Inhalt (Renderer-Gate nicht berührt).

## Risiken

- Speicherweg der Neuanlage geändert (Risiko MEDIUM): Regression bei `?from=` und 400 bei ungültigem `profil` werden durch konstantes „allgemein“ und den Regressionstest abgefangen.
- Mandantentrennung nicht berührt (`user_id` weiterhin aus dem Auth-Kontext); AC-10 sichert sie ab.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (Umsetzung von ADR-0108 Punkt 3 für das Anlegen, ADR-0097 und ADR-0101)
- **Rationale:** Die Entscheidung „Vorlage statt Profil“ ist in ADR-0108 getroffen; diese Scheibe führt sie in der Anlege-Kette zu Ende, ohne neue Architektur.

## Changelog

- 2026-11-21: Initial spec created (S4b-3, #3198)
- 2026-11-21: Abschnitte Scope, Definition of Done, Test Plan für das CI-Spec-Gate ergänzt
- 2026-11-21: Phase 6, Tech-Lead-Auflösung des Widerspruchs AC-9/AC-6 unter Known Limitations dokumentiert (`vergleich.neu.aktivitaetsprofil` bleibt wegen `LocationForm.svelte`); Feldsatz-Feld heißt `vorlageId`; RED-Tests `frontend/src/lib/components/compare-new/__tests__/anlegen_ohne_profil_3198.test.ts`.
