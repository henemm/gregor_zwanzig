---
entity_id: i18n_f8_layout_korridor_2657
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2657, frontend, model-haiku]
---

# i18n F8: Katalog-Migration Layout-Tab, Korridor-/Wertebereiche-Editor, Ausgabe-Layout und GPX-Upload

**Issue:** #2657 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 2, 3 (Frontend), 8

## Approval

- [ ] Approved

## Purpose

Der Layout-Tab (Kanal-Auswahl und Kappung, Reihenfolge, Spalten und Detail-Werte, Mail-Inhalt), der Korridor-Editor für die Wertebereiche (Idealbereiche je Metrik) und die GPX-Upload-Seite sind für englischsprachige Nutzer vollständig englisch. Spaltenköpfe (`col_label`, englische Kurzform nach ADR-0042), Einheiten, Skalen und Zahlen bleiben unverändert. Deutsch bleibt wörtlich wie heute.

## Source

- **File:** `frontend/src/lib/components/shared/layout-tab/**`, `frontend/src/lib/components/shared/corridor-editor/{CorridorEditor,CorridorEditorMobile}.svelte`, `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts`, `frontend/src/lib/components/shared/{OutputLayoutEditor,OutlookLayoutControls,MailInhaltCard}.svelte`, `frontend/src/lib/components/shared/mailInhaltKonstanten.ts`, `frontend/src/routes/gpx-upload/+page.svelte`
- **Identifier:** `ROUTE_METRIC_DEFS`, `PROFILE_METRICS_WITH_SCALES` (corridorEditorState.ts), `CHANNEL_LABELS`, `ltCapNoteText`, `ltKanalAbwahlHinweisText` (ltChannels.ts), Konstantenliste in `mailInhaltKonstanten.ts`, Katalog-Namensraum `layout.*`

> **Schicht-Hinweis:** Reines SvelteKit-Frontend. Hinweis zur Benennung: Das Issue nennt „Korridor-Editor" und meint den vorhandenen `CorridorEditor` in `shared/corridor-editor/` (Wertebereiche/Idealbereiche), nicht den Layout-Tab-Ordner. Kein Python-/Go-Code.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `frontend/src/lib/i18n/messages/de/layout.json` | MODIFY | Texte von Layout-Tab, Korridor-Editor, Ausgabe-Layout, Mail-Inhalt, GPX-Upload (wörtlich) |
| `frontend/src/lib/i18n/messages/en/layout.json` | MODIFY | gleiche Schlüssel, englisch |
| `frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte` | MODIFY | Eyebrow „Kanal · Auswahl & Kappung" und weitere Texte |
| `frontend/src/lib/components/shared/layout-tab/{LTCapNote,LTChannelPicker,LTCutLine}.svelte` | MODIFY | sichtbare Texte und `aria-label` |
| `frontend/src/lib/components/shared/layout-tab/ltChannels.ts` | MODIFY | `ltCapNoteText`, `ltKanalAbwahlHinweisText` über `tr()`; `CHANNEL_LABELS` (Kanalnamen) bleiben |
| `frontend/src/lib/components/shared/layout-tab/{ltIdealRange,channelLayoutsDirty}.ts` | MODIFY | nur Nutzertexte, falls vorhanden |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | MODIFY | Eyebrows, Überschriften, Legende, Titel „Grenze öffnen", Wiederholen, Lade-Texte |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte` | MODIFY | gleiche Texte der mobilen Fassung (gleiche Schlüssel) |
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts` | MODIFY | `ROUTE_METRIC_DEFS` (`label`, `note`) und `PROFILE_METRICS_WITH_SCALES` (`label`) über Katalog; Skalen, Einheiten, Defaults unverändert |
| `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` | MODIFY | „Reihenfolge", „Zeichen", „Preset-Auswahl", „Spalten", „Detail-Werte" (Annahme A1) |
| `frontend/src/lib/components/shared/OutlookLayoutControls.svelte` | MODIFY | sichtbare Texte (Annahme A1) |
| `frontend/src/lib/components/shared/MailInhaltCard.svelte` | MODIFY | „Format" und weitere Texte (Annahme A1) |
| `frontend/src/lib/components/shared/mailInhaltKonstanten.ts` | MODIFY | Bezeichnungen und Beschreibungen der Mail-Inhalts-Bausteine über `tr()` |
| `frontend/src/routes/gpx-upload/+page.svelte` | MODIFY | Formularbeschriftungen, Vorschau-Tabelle, Speichern |
| `frontend/src/lib/i18n/hardcode_allowlist.json` | MODIFY | Einträge `shared/layout-tab`, `shared/CorridorEditor*`, `shared/corridor*`, `routes/gpx-upload`, `shared/OutputLayoutEditor`, `shared/OutlookLayoutControls`, `shared/MailInhalt*` entfernen |
| `frontend/src/lib/components/shared/layout-tab/__tests__/layout_korridor_sprache.test.ts` | CREATE | Layout-Tab, Korridor-Editor, Hinweise de/en, zwei Nutzer, Golden |
| `frontend/src/routes/gpx-upload/__tests__/gpx_upload_sprache.test.ts` | CREATE | GPX-Seite de/en |
| `tests/golden/f8_layout_korridor/*.de.html` | CREATE | Golden der deutschen Ausgabe |

> **Querschnitts-Prüfpunkte**
> - **Trip/Ortsvergleich-Teilung:** Layout-Tab und Korridor-Editor sind geteilte Bausteine (`context="route"|"vergleich"`, mobile und Desktop-Fassung teilen die Schlüssel); es entsteht kein Nachbau. Kontextbedingte Sätze (`titel_route`/`titel_vergleich`) haben zwei Schlüssel.
> - **Mandantentrennung:** Layout, Wertebereiche und hochgeladene Trips gehören dem angemeldeten Nutzer (`user_id` aus Auth-Kontext, unverändert). Anzeige-Texte dürfen nie in die gespeicherte Nutzlast. Test mit zwei Nutzern (AC-4).
> - **Kanäle:** Layout-Tab beschreibt E-Mail, Telegram, SMS (und Premium-SMS über die Kappung); Kanalnamen sind Eigennamen, die Kappungs-Sätze stehen in beiden Sprachen mit gleichem Inhalt.

## Estimated Scope

- **LoC:** ca. 190 Code-Zeilen (ohne Katalog und Tests): Korridor-Editor ca. 60, `corridorEditorState.ts` ca. 45, Layout-Tab ca. 25, Ausgabe-Layout und Mail-Inhalt ca. 35, GPX-Upload ca. 25.
- **Files:** 17 Code-/Katalogdateien plus 2 Tests plus Golden
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2647 (S2), #2649 (S4) | Pakete | Katalogkern, Ratsche, Allowlist |
| #2654 (F5, danach) | Paket | stellt die Metrik-Namen des Katalogs (`compareMetricCatalogLoader.ts`) über `metricLabel` um |
| `docs/reference/i18n_glossar.md` | Doku | Layout, Korridor = corridor, Wertebereiche = target ranges, Kurzform = compact style |
| ADR-0104, ADR-0042 | adr | Spaltenköpfe `col_label` und Kürzel sind Klasse 1 und bleiben |

## Implementation Details

**1. Katalog.** Nur `messages/{de,en}/layout.json` bearbeiten. Als Kommentar an die erste Zeile jeder Gruppe schreibt der Entwickler nichts in die JSON-Datei (JSON kennt keine Kommentare); der Glossar-Hinweis „Spaltenköpfe (`col_label`) bleiben englische Kurzform (ADR-0042)" steht stattdessen im Commit-Text.

**2. Beispiel-Schlüssel (de / en).**

| Schlüssel | de | en |
|---|---|---|
| `layout.tab.eyebrow` | Kanal · Auswahl & Kappung | Channel · selection & cutoff |
| `layout.kappung.zeigt_alles` | {kanal} zeigt alles · keine Begrenzung | {kanal} shows everything · no limit |
| `layout.hinweis.kanal_abwahl` | Ein Kanal zeigt höchstens, was in der Grundauswahl gewählt ist. Was dort fehlt, erscheint in keinem Kanal. | A channel shows at most what is selected in the base selection. Anything missing there appears in no channel. |
| `layout.korridor.eyebrow_idealbereiche` | Wertebereiche · Idealbereiche | Target ranges · ideal ranges |
| `layout.korridor.lade` | Lade Metriken… | Loading metrics… |
| `layout.korridor.titel_route` | Sag mir, welche Werte für dich passen | Tell me which values suit you |
| `layout.korridor.titel_vergleich` | Sag mir, welche Werte dir ideal sind | Tell me which values are ideal for you |
| `layout.korridor.grenze_oeffnen` | Grenze öffnen | Open limit |
| `layout.korridor.metrik_hinzufuegen` | Metrik hinzufügen | Add metric |
| `layout.korridor_zeile.wind_gust` | Böen | Wind gusts |
| `layout.korridor_hinweis.wind_gust` | Grat-kritisch | Critical on ridges |
| `layout.korridor_hinweis.temperature_min` | Frost-Grenze | Frost limit |
| `layout.profil_metrik.wind_max_kmh` | Windspitzen | Peak wind |
| `layout.ausgabe.reihenfolge` | Reihenfolge | Order |
| `layout.ausgabe.spalten` | Spalten | Columns |
| `layout.mail_inhalt.etappen_kennzahlen` | Etappen-Kennzahlen | Stage figures |
| `layout.gpx.hochladen` | Hochladen | Upload |
| `layout.gpx.als_trip_speichern` | Als Trip speichern | Save as trip |

**3. Beispiel-Umstellung vorher → nachher.**

- `frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte:72` — vorher `<div class="lt-eyebrow mono">Kanal · Auswahl &amp; Kappung</div>`, nachher `<div class="lt-eyebrow mono">{$t('layout.tab.eyebrow')}</div>` (Svelte maskiert `&` beim Rendern zu `&amp;`, die Ausgabe bleibt byte-gleich).
- `frontend/src/lib/components/shared/layout-tab/ltChannels.ts:141` — vorher `` `${label} zeigt alles · keine Begrenzung` ``, nachher `tr('layout.kappung.zeigt_alles', { kanal: label })`.
- `frontend/src/lib/components/shared/layout-tab/ltChannels.ts:155` — vorher der deutsche Satz als Rückgabewert, nachher `return tr('layout.hinweis.kanal_abwahl');`.
- `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte:382` — vorher `<Eyebrow>Wertebereiche · Idealbereiche</Eyebrow>`, nachher `<Eyebrow>{$t('layout.korridor.eyebrow_idealbereiche')}</Eyebrow>`; dieselbe Zeile steht in `CorridorEditorMobile.svelte:349` und nutzt denselben Schlüssel.
- `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts:42` — vorher `{ metric: 'wind_gust', label: 'Böen', …, note: 'Grat-kritisch', … }`, nachher `label: tr('layout.korridor_zeile.wind_gust')`, `note: tr('layout.korridor_hinweis.wind_gust')`. Damit die Liste auf Sprachwechsel reagiert, wird `ROUTE_METRIC_DEFS` zur Funktion `routeMetricDefs()` oder wird beim Rendern mit `tr` aufgelöst; `metric`, `unit`, `scale`, `step`, `defaultMin/Max` bleiben exakt (Annahme A2).
- `frontend/src/routes/gpx-upload/+page.svelte:177` — vorher `{loading ? 'Wird hochgeladen...' : 'Hochladen'}`, nachher `{loading ? $t('layout.gpx.wird_hochgeladen') : $t('layout.gpx.hochladen')}`.

**4. Nicht übersetzen.** Spaltenköpfe `col_label`, Kürzel, `CHANNEL_LABELS` (Email, Telegram, SMS), Einheiten und Skalen, `ORDINAL_ENUM` (`NONE`, `LOW`, `MED`, `HIGH`), Datumsplatzhalter `YYYY-MM-DD`, Profil-IDs (`WINTERSPORT` …), `data-testid`. Metrik-Namen, die aus `GET /api/compare/metrics` geladen werden, stellt F5 um (nicht dieses Paket).

**5. Allowlist.** Aus `frontend/src/lib/i18n/hardcode_allowlist.json` die Einträge entfernen, die auf Dateien dieser Tabelle zeigen (laut Issue `shared/layout-tab`, `shared/CorridorEditor*`, `shared/corridor*`, dazu `routes/gpx-upload`).

**6. Golden-Fixture.** Vor der Umstellung für Nutzer `golden-de` den Layout-Tab (Trip und Vergleich), den Korridor-Editor (Trip und Vergleich, Desktop und mobil) und die GPX-Seite per SSR nach `tests/golden/f8_layout_korridor/<fall>.de.html` schreiben; danach byte-gleich vergleichen, ebenso die Funktionswerte von `ltCapNoteText` und `ltKanalAbwahlHinweisText`. `*.en.html` zur Review einchecken.

## Expected Behavior

- **Input:** Layout-Reiter und Wertebereiche-Reiter im Trip- und Ortsvergleich-Hub und beim Anlegen, die GPX-Upload-Seite; Nutzer mit `language=en` oder `de`.
- **Output:** Alle Beschriftungen in der Nutzersprache; Spaltenköpfe, Einheiten, Skalen, Kürzel und Zahlen identisch.
- **Side effects:** Keine. Gespeichertes Layout, Wertebereiche und hochgeladene Trips sind in beiden Sprachen identisch.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Sprache Englisch / When der Layout-Tab im Trip-Hub und im Ortsvergleich-Hub lädt / Then sind die Beschriftungen englisch („Channel · selection & cutoff", „Order", „Columns"), und die Spaltenköpfe (`col_label`) und Kanalnamen stehen unverändert.
  - Test: `frontend/src/lib/components/shared/layout-tab/__tests__/layout_korridor_sprache.test.ts` — Render beider Kontexte mit `locale.set('en')`, Prüfung über `tr()`-Werte; `col_label` byte-gleich zur Eingabe.

- **AC-2:** Given der Korridor-Editor im Trip-Kontext und im Vergleichs-Kontext, Desktop und mobil / When er in Englisch angezeigt wird / Then lauten Überschrift („Tell me which values suit you" bzw. „… are ideal for you"), Zeilen („Wind gusts" mit Hinweis „Critical on ridges"), „Open limit" und „Add metric" englisch, und Einheiten, Skalen und Standardgrenzen sind identisch zur deutschen Ausgabe.
  - Test: `frontend/src/lib/components/shared/layout-tab/__tests__/layout_korridor_sprache.test.ts` — beide Kontexte und beide Fassungen; Gleichheit von `unit`/`scale`/`defaultMin/Max` zwischen den Sprachen.

- **AC-3:** Given die Kappungs- und Abwahl-Hinweise / When `ltCapNoteText` und `ltKanalAbwahlHinweisText` in beiden Sprachen aufgerufen werden / Then enthalten sie dieselben Zahlen und Kanäle, englisch ohne wertende Wörter („only", „unfortunately", „bad"), deutsch byte-gleich zu den bisherigen Werten; die vorhandenen Tests `channelHintTextNoJudgement` und `ltChannels.test.ts` bleiben grün.
  - Test: `frontend/src/lib/components/shared/layout-tab/__tests__/layout_korridor_sprache.test.ts` — Eingabe/Ausgabe-Tabelle in beiden Sprachen, Wortliste für Englisch.

- **AC-4:** Given Nutzer A (Englisch) und Nutzer B (Deutsch) mit demselben Layout und denselben Wertebereichen / When beide den Layout- und den Wertebereiche-Reiter öffnen, eine Grenze ändern und speichern / Then ist die gespeicherte Nutzlast bei beiden identisch (keine Anzeige-Texte darin), und jeder sieht nur seine Werte in seiner Sprache.
  - Test: `frontend/src/lib/components/shared/layout-tab/__tests__/layout_korridor_sprache.test.ts` — zwei Nutzer in einem Lauf, Vergleich der Speicher-Nutzlast.

- **AC-5:** Given die GPX-Upload-Seite in Englisch / When sie lädt, eine Datei hochgeladen und als Trip gespeichert wird / Then stehen Formular, Vorschau-Tabelle und Schaltflächen auf Englisch („Upload", „Stage preview", „Save as trip"), und der gespeicherte Trip trägt den vom Nutzer eingegebenen Namen unverändert.
  - Test: `frontend/src/routes/gpx-upload/__tests__/gpx_upload_sprache.test.ts` — Render und Speichern in `en` und `de`, Trip-Name unverändert.

- **AC-6:** Given die deutsche Oberfläche / When Layout-Tab, Korridor-Editor und GPX-Seite mit der Fixture `golden-de` gerendert werden / Then ist die Ausgabe Byte für Byte gleich zu `tests/golden/f8_layout_korridor/*.de.html`.
  - Test: `frontend/src/lib/components/shared/layout-tab/__tests__/layout_korridor_sprache.test.ts` — Golden-Vergleich (deutsche Ausgabe unverändert).

- **AC-7:** Given die Allowlist der Ratsche / When `keine_hartkodierten_nutzertexte.test.ts` und der Paritätstest laufen / Then gibt es keine Treffer mehr in den Dateien dieses Pakets, die Allowlist enthält keinen Eintrag mehr für `shared/layout-tab`, `shared/CorridorEditor*`, `routes/gpx-upload`, und `layout` hat in de und en identische Schlüssel- und Platzhaltermengen.
  - Test: `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` und `paritaet_de_en.test.ts` — Ratschen-/Paritätstest (`# doc-compliance-test`).

## Known Limitations

- **A1 (Annahme):** `OutputLayoutEditor`, `OutlookLayoutControls`, `MailInhaltCard` und `mailInhaltKonstanten.ts` liegen unter `shared/` außerhalb aller genannten Ordner und gehören thematisch zum Layout (Ausgabe-Layout, Mail-Inhalt); sie werden hier migriert, sonst bliebe kein Paket zuständig.
- **A2 (Annahme):** `ROUTE_METRIC_DEFS` ist heute eine Konstante. Sie bleibt als Konstante mit Schlüsselnamen (`labelKey`, `noteKey`) erhalten und wird beim Rendern aufgelöst, wenn das die vorhandenen Tests am wenigsten berührt; der Entwickler wählt die Variante mit der kleineren Änderung, die Werte `metric/unit/scale/step/defaultMin/defaultMax` bleiben in jedem Fall unverändert.
- Metrik-Namen aus dem Vergleichs-Katalog (`GET /api/compare/metrics`) bleiben in diesem Paket deutsch; F5 stellt sie über `metricLabel` um.
- Wiederholen/Abbrechen in diesem Bereich liegen als `layout.*`; eine Zusammenführung mit `aktionen.*` ist ein Nebenbefund nach F10.
- Der Glossar-Hinweis zu `col_label` steht im Commit-Text, nicht im Katalog, weil JSON keine Kommentare kennt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (zusätzlich ADR-0042)
- **Rationale:** Spaltenköpfe und Kürzel sind Platzform und bleiben, nur Beschriftungen und Hinweise folgen der Nutzersprache.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
