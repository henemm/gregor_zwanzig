---
entity_id: i18n_f10_vergleich_flaechen_2659
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2659, frontend, model-haiku]
---

# i18n F10: Katalog-Migration Ortsvergleich-Flächen (compare, compare-new, Orte-Tab, transponierte Übersicht)

**Issue:** #2659 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 2, 3 (Frontend), 8

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Der Ortsvergleich-Hub (Status, Versand-Rhythmus, Orte-Tab, transponierte Übersicht) und das Anlegen eines Ortsvergleichs sind für englischsprachige Nutzer vollständig englisch. Nur Texte, die es im Trip-Hub nicht gibt, bekommen Schlüssel in `vergleich.*`; alles Wortgleiche (Aktionen, Reiternamen, Bearbeiten, Abbrechen) nutzt `aktionen.*` aus F9, damit Trip und Ortsvergleich denselben Text aus demselben Schlüssel zeigen. Deutsch bleibt wörtlich wie heute.

## Source

- **File:** `frontend/src/lib/components/compare/**`, `frontend/src/lib/components/compare-new/**`, `frontend/src/routes/compare/[id]/+page.svelte`, `frontend/src/routes/compare/[id]/edit/+page.svelte`, `frontend/src/routes/compare/new/+page.svelte`
- **Identifier:** `STATUS_MAP`, `presetScheduleLabel`, `presetTileScheduleLabel`, `presetLocationsLabel`, `relativeLastSent`, `formatNextSend`, `formatLastSent`, `PROFILE_LABELS`, `WEEKDAYS` (subscriptionHelpers.ts), `CompareTabs`, `CompareNewEditor`, `LocationNewModal`, Katalog-Namensraum `vergleich.*`

> **Schicht-Hinweis:** Reines SvelteKit-Frontend. Kein Python-/Go-Code. Die Compare-Mail (Python) ist P4. Die Listenseite `routes/compare/+page.svelte` gehört zu F3.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `frontend/src/lib/i18n/messages/de/vergleich.json` | MODIFY | compare-eigene Texte (wörtlich) |
| `frontend/src/lib/i18n/messages/en/vergleich.json` | MODIFY | gleiche Schlüssel, englisch |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Hub: Status, Kennzahlen, Orte-Abschnitt, Zusammenfassung; Aktionen und Reiternamen aus `aktionen.*` |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | MODIFY | `STATUS_MAP`, Zeitplan-Labels, `WEEKDAYS`, `PROFILE_LABELS`, Orte-Anzahl, `relativeLastSent`, `formatNextSend` („manuell"), `formatLastSent` |
| `frontend/src/lib/components/compare/steps/Step2Orte.svelte` | MODIFY | Orte-Auswahl beim Anlegen (Gruppen, Bibliothek, Hinweise) |
| `frontend/src/lib/components/compare/LocationNewModal.svelte` | MODIFY | „Neuer Ort", Vorschau-Felder, Platzhalter |
| `frontend/src/lib/components/compare/{AddReportCard,CompareStatusPill,CompareDetail,CreateGroupDialog,CompareHourlyLayoutControls,LocationPreviewMap}.svelte` | MODIFY | sichtbare Texte, `aria-label`, `title` |
| `frontend/src/lib/components/compare/{compareEditorSave,compareEditorLoad,compareHubPersistenz,compareHubHydration,compareWizardState.svelte,locationHelpers,layoutPreviewRows,compareHourlyMetricDefs}.ts` | MODIFY | Meldungen und Anzeige-Texte über `tr()`; Logik und Nutzlast unverändert |
| `frontend/src/lib/components/compare/{versandPropsAus,alarmePropsAus,wetterMetrikenPropsAus,corridorPropsAus}.ts` | MODIFY | nur Nutzertexte, falls vorhanden (viele Treffer sind Kommentare) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Anlege-Editor (Reiter, Hinweise, Schaltflächen) |
| `frontend/src/lib/components/compare-new/compareNewVorlage.ts` | MODIFY | Vorlagen-Texte |
| `frontend/src/routes/compare/[id]/+page.svelte`, `frontend/src/routes/compare/[id]/edit/+page.svelte`, `frontend/src/routes/compare/new/+page.svelte` | MODIFY | sichtbare Texte (Breadcrumb, Dialoge) |
| `frontend/src/lib/i18n/hardcode_allowlist.json` | MODIFY | Einträge `components/compare`, `components/compare-new`, `routes/compare/[id]`, `routes/compare/new` entfernen |
| `frontend/src/lib/components/compare/__tests__/vergleich_hub_sprache.test.ts` | CREATE | Hub de/en, Helfer, Orte, zwei Nutzer, Golden |
| `frontend/src/lib/components/compare/__tests__/vergleich_nutzt_gemeinsame_aktionen.test.ts` | CREATE | Struktur: Aktionen kommen aus `aktionen.*` |
| `tests/golden/f10_vergleich_flaechen/*.de.html` | CREATE | Golden der deutschen Ausgabe |

> **Querschnitts-Prüfpunkte**
> - **Trip/Ortsvergleich-Teilung:** Geteilte Texte stehen nur in `aktionen.*` (F9) und `home.*`/`listen.*` (F3, z. B. „Nächster Versand", „Kanäle", „heute"); in `vergleich.*` liegt **nur** Compare-Eigenes (Orte-Tab, transponierte Übersicht, Compare-Mail-Template-Bezug, Versand-Rhythmus-Kürzel). `git grep "vergleich.aktion"` darf keinen Treffer liefern, `git grep "aktionen\." frontend/src/lib/components/compare` muss Treffer liefern. Es entsteht keine neue Komponente.
> - **Mandantentrennung:** Hub und Anlegen lesen und speichern nur Ortsvergleiche und Orte des angemeldeten Nutzers (`user_id` aus Auth-Kontext, unverändert). Anzeige-Texte dürfen nie in die gespeicherte Nutzlast. Test mit zwei Nutzern (AC-4).
> - **Kanäle:** Der Hub zeigt Versand-Kanäle (E-Mail, Telegram, SMS, Premium-SMS) über die zentrale Ableitung `presetChannels`; Kanalnamen bleiben Eigennamen, Inhalt in beiden Sprachen gleich.

## Estimated Scope

- **LoC:** ca. 320 Code-Zeilen (ohne Katalog und Tests): `CompareTabs` ca. 70, `subscriptionHelpers` ca. 35, `Step2Orte` ca. 30, `CompareNewEditor` ca. 40, `LocationNewModal` ca. 25, übrige Komponenten ca. 40, Hilfsdateien ca. 50, Routen ca. 30. Das überschreitet das Limit von 250: `workflow.py set-field loc_limit_override 500` einplanen.
- **Files:** ca. 35 Code-/Katalogdateien plus 2 Tests plus Golden (das Issue nennt 9 Dateien; der Ordner `compare/` enthält 22 Quelldateien)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2658 (F9) | Paket (vorher) | Namensraum `aktionen.*`, `subscriptionActions`, `subscriptionTabs`, `SubscriptionHeader`, `BriefingHistory` |
| #2652 (F3) | Paket (vorher) | `home.*`/`listen.*`-Schlüssel („Nächster Versand", „Kanäle", „heute", Orte-Anzahl) |
| #2654 (F5) | Paket (vorher) | `metricLabel`, `wertebereiche.auswertung.*` |
| #2647 (S2), #2649 (S4) | Pakete | Katalogkern, Ratsche, Allowlist |
| `docs/reference/i18n_glossar.md` | Doku | Ortsvergleich = location comparison (Reiter kurz: comparison), Orte = locations, Aktivitätsprofil = activity profile |
| ADR-0104 | adr | Formate (24 h), Wortwahl |

## Implementation Details

**1. Katalog.** Nur `messages/{de,en}/vergleich.json` bearbeiten. Vor dem Anlegen eines Schlüssels prüfen, ob der Text schon unter `aktionen.*`, `home.*` oder `listen.*` steht; dann **dort** verwenden (nie zwei Schlüssel für denselben Text). Platzhalter in beiden Sprachen gleich, Plural als `.one`/`.other`.

**2. Beispiel-Schlüssel (de / en).**

| Schlüssel | de | en |
|---|---|---|
| `vergleich.status.active` | aktiv | active |
| `vergleich.status.paused` | pausiert | paused |
| `vergleich.hub.laeuft_automatisch` | Läuft automatisch | Runs automatically |
| `vergleich.hub.entwurf` | Entwurf · nicht aktiv | Draft · not active |
| `vergleich.hub.zuletzt_raus` | Zuletzt raus | Last sent |
| `vergleich.hub.verglichene_orte` | Verglichene Orte | Compared locations |
| `vergleich.hub.reihenfolge_hinweis` | Reihenfolge = Spalten im Briefing · ziehen zum Sortieren | Order = columns in the briefing · drag to sort |
| `vergleich.hub.keine_orte` | Noch keine Orte ausgewählt. | No locations selected yet. |
| `vergleich.hub.ort_hinzufuegen` | Ort hinzufügen | Add location |
| `vergleich.zeitplan.taeglich` | Täglich {von}–{bis} Uhr | Daily {von}–{bis} |
| `vergleich.zeitplan.woechentlich` | Wöchentlich | Weekly |
| `vergleich.zeitplan.kachel_taeglich` | tägl. {stunde} | daily {stunde} |
| `vergleich.relativ.gestern` | gestern | yesterday |
| `vergleich.relativ.wochen.one` / `.other` | vor {count} Woche / vor {count} Wochen | {count} week ago / {count} weeks ago |
| `vergleich.wochentag_lang.0` | Montag | Monday |
| `vergleich.profil.wintersport` | Wintersport | Winter sports |
| `vergleich.ort.neuer_ort` | Neuer Ort | New location |
| `vergleich.ort.erkannt_vorschau` | Erkannt · Vorschau | Detected · preview |
| `vergleich.neu.auto_report` | Neuer Auto-Report | New auto report |

Wiederverwendet, nicht neu angelegt: `aktionen.edit` („Bearbeiten"), `aktionen.cancel`, `aktionen.reiter.wertebereiche`, `home.hero.naechster_versand`, `home.hero.kanaele`, `home.tage.heute`, `listen.anzahl.orte` (Orte-Anzahl mit Plural, aus F3).

**3. Beispiel-Umstellung vorher → nachher.**

- `frontend/src/lib/components/compare/CompareTabs.svelte:841` — vorher `…>Bearbeiten →</button>`, nachher `…>{$t('aktionen.edit')} →</button>` (der Pfeil bleibt im Markup, die Ausgabe ist byte-gleich).
- `frontend/src/lib/components/compare/CompareTabs.svelte:768` — vorher `…>Nächster Versand</div>`, nachher `…>{$t('home.hero.naechster_versand')}</div>`; `:773` `>Briefings<` bekommt `vergleich.hub.briefings`.
- `frontend/src/lib/components/compare/CompareTabs.svelte:758` — vorher `Läuft automatisch`, nachher `{$t('vergleich.hub.laeuft_automatisch')}`; die mobile Kurzfassung „Läuft autom." (Zeile 723) bekommt `vergleich.hub.laeuft_autom`.
- `frontend/src/lib/components/compare/subscriptionHelpers.ts:32` — vorher `` `Täglich ${preset.hour_from}–${preset.hour_to} Uhr` ``, nachher `tr('vergleich.zeitplan.taeglich', { von: preset.hour_from, bis: preset.hour_to })`.
- `frontend/src/lib/components/compare/subscriptionHelpers.ts:246` — vorher `` `vor ${weeks} ${weeks === 1 ? 'Woche' : 'Wochen'}` ``, nachher `get(tn)('vergleich.relativ.wochen', weeks)` (`get` aus `svelte/store`, Annahme A1 wie in F3).
- `frontend/src/lib/components/compare/subscriptionHelpers.ts:14` — `WEEKDAYS` entfällt als Konstante; `weekdayLong(i)` liefert `tr('vergleich.wochentag_lang.' + i)` mit Kommentar `// i18n-dynamic: vergleich.wochentag_lang.`.
- `frontend/src/lib/components/compare/subscriptionHelpers.ts:65` — `formatLastSent`: bei `de` unverändert `toLocaleDateString('de-DE', …)`, bei `en` `en-GB`; „Noch kein Versand" → `vergleich.relativ.noch_kein_versand`.

**4. Nicht übersetzen.** Orts-, Gruppen- und Vergleichsnamen, Region, Kanalnamen, Metrik-IDs, `col_label`, Kürzel, Profil-IDs (`allgemein`, `wintersport` …), `data-testid`. Aktivitätsprofil-Anzeigenamen sind Katalog (Allgemein/General, Wintersport/Winter sports, Wandern/Hiking, Sommer-Trekking/Summer trekking). Metrik-Namen gehen über `metricLabel` (F5).

**5. Allowlist.** Aus `frontend/src/lib/i18n/hardcode_allowlist.json` die Einträge entfernen, die auf Dateien dieser Tabelle zeigen (laut Issue `components/compare`, `components/compare-new`, `routes/compare/[id]`, `routes/compare/new`).

**6. Golden-Fixture.** Vor der Umstellung für Nutzer `golden-de` mit einem aktiven, einem pausierten und einem Entwurf-Ortsvergleich (je 3 Orte, Kanäle E-Mail und Telegram) den Hub (alle Reiter), die transponierte Übersicht und `/compare/new` per SSR nach `tests/golden/f10_vergleich_flaechen/<fall>.de.html` schreiben; danach byte-gleich vergleichen, ebenso die Funktionswerte der Helfer in `subscriptionHelpers.ts` (Tabelle `Eingabe → Ausgabe`). `*.en.html` zur Review einchecken.

## Expected Behavior

- **Input:** Aufruf von `/compare/<id>`, `/compare/<id>/edit`, `/compare/new` mit Nutzer `language=en` oder `de`.
- **Output:** Alle sichtbaren Texte in der Nutzersprache; Aktionen und Reiternamen wortgleich zum Trip-Hub (gleicher Schlüssel); Orts-, Gruppen- und Vergleichsnamen sowie Zahlen unverändert.
- **Side effects:** Keine. Gespeicherte Ortsvergleiche sind in beiden Sprachen identisch.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Sprache Englisch und ein aktiver Ortsvergleich mit drei Orten / When der Ortsvergleich-Hub lädt / Then ist er vollständig englisch („Runs automatically", „Compared locations", „Add location", „Next delivery"), Ortsnamen und Vergleichsname stehen unverändert, und „Edit", „Delete", „Pause" tragen denselben Text wie im Trip-Hub.
  - Test: `frontend/src/lib/components/compare/__tests__/vergleich_hub_sprache.test.ts` — Render mit `locale.set('en')`, Prüfung über `tr()`-Werte; Textgleichheit der Aktionen zwischen `subscriptionActions('trip', …)` und `subscriptionActions('vergleich', …)`.

- **AC-2:** Given die Compare-Helfer `presetScheduleLabel`, `presetTileScheduleLabel`, `presetLocationsLabel`, `relativeLastSent` / When sie in Englisch und in Deutsch mit festen Eingaben aufgerufen werden / Then liefert Deutsch weiterhin wörtlich z. B. `Täglich 7–9 Uhr`, `tägl. 07`, `3 Orte`, `vor 2 Wochen`, `Montag`, Englisch `Daily 7–9`, `daily 07`, `3 locations`, `2 weeks ago`, `Monday`, und `1 Ort`/`1 location` im Singular.
  - Test: `frontend/src/lib/components/compare/__tests__/vergleich_hub_sprache.test.ts` — Eingabe/Ausgabe-Tabelle in beiden Sprachen; die vorhandenen Tests `issue_582_list_helpers.test.ts` und `compare_tile_schedule_label_slots.test.ts` bleiben grün.

- **AC-3:** Given der Orte-Abschnitt des Hubs und der Orte-Schritt beim Anlegen in Englisch / When ein Ort hinzugefügt, ein neuer Ort über „New location" angelegt und ein Ort entfernt wird / Then stehen Hinweise, Platzhalter und Schaltflächen auf Englisch, die Reihenfolge der Orte und die Koordinaten sind unverändert, und die gespeicherte Nutzlast enthält nur Ort-IDs.
  - Test: `frontend/src/lib/components/compare/__tests__/vergleich_hub_sprache.test.ts` — Render von `CompareTabs` (Orte), `Step2Orte`, `LocationNewModal` in `en` und `de`, Nutzlast-Vergleich.

- **AC-4:** Given Nutzer A (Englisch) mit Ortsvergleich X und Nutzer B (Deutsch) mit Ortsvergleich Y / When beide ihren Hub öffnen, den Namen ändern und speichern / Then sieht A nur X englisch und B nur Y deutsch, die gespeicherte Nutzlast ist sprachunabhängig identisch aufgebaut, und keiner kann den Ortsvergleich des anderen laden.
  - Test: `frontend/src/lib/components/compare/__tests__/vergleich_hub_sprache.test.ts` — zwei Nutzer in einem Lauf (`locals.userId` und `locals.lang` je Nutzer), Lade- und Speicherpfad.

- **AC-5:** Given die Compare-Flächen / When die Quelltexte von `components/compare` auf Aktionstexte geprüft werden / Then kommen Aktionen und Reiternamen aus `aktionen.*` und es gibt keinen Schlüssel `vergleich.aktion*` und keinen zweiten Schlüssel für einen bereits vorhandenen Text.
  - Test: `frontend/src/lib/components/compare/__tests__/vergleich_nutzt_gemeinsame_aktionen.test.ts` — Strukturtest (`# doc-compliance-test`): Treffer für `aktionen.` in `components/compare`, kein Treffer für `vergleich.aktion` in den Katalogen; Doppeltext-Prüfung über beide Kataloge.

- **AC-6:** Given die deutsche Oberfläche / When Hub, transponierte Übersicht und Anlegen mit der Fixture `golden-de` gerendert werden / Then ist die Ausgabe Byte für Byte gleich zu `tests/golden/f10_vergleich_flaechen/*.de.html`.
  - Test: `frontend/src/lib/components/compare/__tests__/vergleich_hub_sprache.test.ts` — Golden-Vergleich (deutsche Ausgabe unverändert).

- **AC-7:** Given Metrik-Einträge mit und ohne `label_en` / When Hub und Anlegen (Metrik-Auswahl, Stundenverlauf) in Englisch angezeigt werden / Then steht die volle Form englisch bzw. bei fehlendem `label_en` deutsch, und `col_label` sowie Kürzel stehen unverändert.
  - Test: `frontend/src/lib/components/compare/__tests__/vergleich_hub_sprache.test.ts` — `metricLabel`-Verdrahtung in der Metrik-Auswahl, `col_label` byte-gleich.

- **AC-8:** Given die Allowlist der Ratsche / When `keine_hartkodierten_nutzertexte.test.ts` und der Paritätstest laufen / Then gibt es keine Treffer mehr in den Dateien dieses Pakets, die Allowlist enthält keinen Eintrag mehr für `components/compare`, `components/compare-new`, `routes/compare/[id]`, `routes/compare/new`, und `vergleich` hat in de und en identische Schlüssel- und Platzhaltermengen.
  - Test: `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` und `paritaet_de_en.test.ts` — Ratschen-/Paritätstest (`# doc-compliance-test`).

## Known Limitations

- **A1 (Annahme):** Für Plurale in `.ts`-Modulen wird `get(tn)(...)` aus `svelte/store` verwendet (die Konventionen kennen dort nur `tr`); ändert S2 die Signatur, folgt F10 ihr.
- **A2 (Annahme):** Das Issue nennt 9 Dateien in `compare/`; der Ordner enthält 22 Quelldateien (ohne Tests). Alle mit Nutzertexten gehören zum Paket; Dateien ohne Treffer der Ratsche bleiben unberührt.
- **A3 (Annahme):** Der englische Zeitplan lautet „Daily {von}–{bis}" ohne „h"/„o'clock" (24-h-Angaben sind sprachneutral, ADR-0104).
- Wortgleiche Basistexte früherer Pakete unter anderen Bereichen (z. B. „Wiederholen") bleiben dort; die Zusammenführung ist ein Nebenbefund nach F10.
- `routes/compare/+page.svelte` (Liste) ist F3; die Listen-Zeitplanspalte nutzt `presetTileScheduleLabel` aus diesem Paket und bleibt bis F10 deutsch.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Trip und Ortsvergleich teilen Texte über `aktionen.*`, nur Compare-Eigenes liegt in `vergleich.*`; Deutsch bleibt byte-gleich.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
