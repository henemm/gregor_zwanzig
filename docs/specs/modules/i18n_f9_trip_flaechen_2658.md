---
entity_id: i18n_f9_trip_flaechen_2658
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2658, frontend, model-haiku]
---

# i18n F9: Katalog-Migration Trip-Flächen (trip-detail, trip-new, edit, email-preview) und gemeinsamer Namensraum `aktionen.*`

**Issue:** #2658 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 2, 3 (Frontend), 8

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Der Trip-Hub (Kopf, Übersicht, Etappen, Wegpunkte, Historie, Vorschau-Rahmen) und das Anlegen eines Trips sind für englischsprachige Nutzer vollständig englisch; Etappen-Daten erscheinen als `Thu 30 Oct`. Dieses Paket legt außerdem den Namensraum `aktionen.*` für alle Texte an, die auf Trip- und Ortsvergleich-Flächen wortgleich stehen (Pausieren, Archivieren, Löschen, Bearbeiten, Reiternamen); F10 verwendet sie wieder. Deutsch bleibt wörtlich wie heute.

## Source

- **File:** `frontend/src/lib/components/trip-detail/**`, `frontend/src/lib/components/trip-new/**`, `frontend/src/lib/components/edit/**`, `frontend/src/lib/components/email-preview/**`, `frontend/src/routes/trips/[id]/+page.svelte`, `frontend/src/routes/trips/[id]/edit/+page.svelte`, `frontend/src/routes/trips/new/+page.svelte`, `frontend/src/lib/components/shared/{subscriptionActions,subscriptionTabs}.ts`, `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte`, `frontend/src/lib/components/shared/BriefingHistory.svelte`
- **Identifier:** Tabelle `A` und Hilfsfunktion `ids()` samt `subscriptionActions()` in `subscriptionActions.ts` (Aktions-IDs `pause`, `resume`, `send`, `alarms`, `weather`, `edit`, `archive`, `unarchive`, `delete`, `continue-setup`), Reiter-Tabelle in `subscriptionTabs.ts`, `TripStatusBadge`, `TripHeader`, `TripNewEditor`, `StageDateField` (`WD`), Katalog-Namensräume `trip.*` und `aktionen.*`

> **Schicht-Hinweis:** Reines SvelteKit-Frontend. Kein Python-/Go-Code. Die Briefing-Mail selbst (Python) ist P2/P3.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `frontend/src/lib/i18n/messages/de/aktionen.json` | MODIFY | gemeinsame Texte Trip/Ortsvergleich (Aktionen, Reiternamen, Kopf-Bedienung) |
| `frontend/src/lib/i18n/messages/en/aktionen.json` | MODIFY | gleiche Schlüssel, englisch |
| `frontend/src/lib/i18n/messages/de/trip.json` | MODIFY | Trip-eigene Texte (wörtlich) |
| `frontend/src/lib/i18n/messages/en/trip.json` | MODIFY | gleiche Schlüssel, englisch |
| `frontend/src/lib/components/shared/subscriptionActions.ts` | MODIFY | Labels der Aktionen über `tr('aktionen.<id>')`; `id`, `danger` unverändert |
| `frontend/src/lib/components/shared/subscriptionTabs.ts` | MODIFY | Reiter-Labels und `lockHint` über `tr()`; IDs und Reihenfolge unverändert |
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | MODIFY | „Abbrechen", `aria-label` „Name bearbeiten", „Region bearbeiten" |
| `frontend/src/lib/components/shared/BriefingHistory.svelte` | MODIFY | „Versand-Historie", Leerzustand, `SLOT_LABELS` (Morgen/Abend) |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | MODIFY | `Tag {n}`, Stat-Labels ETAPPE/BRIEFING, Zahlenformat (`de-DE`/`en-GB`) |
| `frontend/src/lib/components/trip-detail/TripStatusBadge.svelte` | MODIFY | Status-Namen (Entwurf … Archiviert) |
| `frontend/src/lib/components/trip-detail/HubOverview.svelte` | MODIFY | Eyebrows, Sprungknöpfe, Plural „Größe(n) unbekannt" |
| `frontend/src/lib/components/trip-detail/{TripTabs,StageList,StageDetailRow,TripStageRow,FullProfile,AlertsPreviewCard,AlarmeScheduleTab,BriefingScheduleTab,ChannelLimitMarkers,TablePreview,AboutOutputLayout,BucketSection,BucketSectionOff,MetricGroup,ActiveMetricRow,PresetRow,DetailCard,ReportLine,WeatherV2Kanaele,WaypointsPanel}.svelte` | MODIFY | sichtbare Texte, `title`, `aria-label`; Metrik-Namen über `metricLabel` (F5) |
| `frontend/src/lib/components/trip-detail/{metricsEditor,weatherSaveGate}.ts` | MODIFY | nur Nutzertexte (Meldungen); IDs, Kataloge, Logik unverändert |
| `frontend/src/lib/components/trip-detail/waypoints/{EtappenStrip,StageCard,WaypointCard,WaypointPin,ProfileEditor,MapCanvas,PauseStageView}.svelte` | MODIFY | Wegpunkt-Editor-Texte |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Anlege-Editor (Reiter, Hinweise, Schaltflächen, Speichern) |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | MODIFY | Meldungen über `tr()` |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | MODIFY | größte Einzeldatei: Etappen-Editor (Texte, Platzhalter, Fehler, Hinweise) |
| `frontend/src/lib/components/edit/{AccordionSection,EditStagesSection,EditRouteSection,EditWeatherSection,WeatherSummaryCard,StageDateField,StageTimeField}.svelte` | MODIFY | Texte; `StageDateField.WD` über `fmtWeekday` |
| `frontend/src/lib/components/edit/{cascade,weatherSummary}.ts` | MODIFY | Meldungen und Zusammenfassungs-Texte über `tr()` |
| `frontend/src/lib/components/email-preview/{EmailPreviewHeader.svelte,headerStats.ts}` | MODIFY | Texte des Vorschau-Rahmens |
| `frontend/src/routes/trips/[id]/+page.svelte` | MODIFY | Breadcrumb „Trips", „Weitere Aktionen", „Briefing gesendet!", Lösch-Dialog |
| `frontend/src/routes/trips/[id]/edit/+page.svelte`, `frontend/src/routes/trips/new/+page.svelte` | MODIFY | sichtbare Texte, falls vorhanden |
| `frontend/src/lib/i18n/hardcode_allowlist.json` | MODIFY | Einträge `components/trip-detail`, `components/trip-new`, `components/edit`, `components/email-preview`, `routes/trips/[id]`, `routes/trips/new`, `shared/subscription*`, `shared/BriefingHistory` entfernen |
| `frontend/src/lib/components/trip-detail/__tests__/trip_hub_sprache.test.ts` | CREATE | Trip-Hub de/en, Aktionen, Datum, zwei Nutzer, Golden |
| `frontend/src/lib/components/trip-new/__tests__/trip_anlegen_sprache.test.ts` | CREATE | Anlege-Editor und Etappen-Editor de/en |
| `tests/golden/f9_trip_flaechen/*.de.html` | CREATE | Golden der deutschen Ausgabe |

> **Querschnitts-Prüfpunkte**
> - **Trip/Ortsvergleich-Teilung:** Texte, die auf Trip- und Ortsvergleich-Flächen wortgleich stehen (Aktionsliste aus `subscriptionActions.ts`, Reiternamen aus `subscriptionTabs.ts`, `SubscriptionHeader`, `BriefingHistory`), liegen **einmal** in `aktionen.*`; F10 nutzt sie wieder. Trip-eigene Texte (Etappen, Wegpunkte, GPX, Trip-Status) liegen in `trip.*`. Es entsteht keine neue Komponente.
> - **Mandantentrennung:** Der Trip-Hub liest und speichert nur Trips des angemeldeten Nutzers (`user_id` aus Auth-Kontext, unverändert). Anzeige-Texte dürfen nie in die gespeicherte Nutzlast. Test mit zwei Nutzern (AC-5).
> - **Kanäle:** Der Hub zeigt Kanal-Markierungen (E-Mail, Telegram, SMS, Premium-SMS); Kanalnamen bleiben Eigennamen, Begrenzungs-Hinweise (Telegram-Spalten, SMS-Zeichen) haben gleichen Inhalt in beiden Sprachen.

## Estimated Scope

- **LoC:** ca. 480 Code-Zeilen (ohne Katalog und Tests): `EditStagesPanelNew` ca. 130, `TripNewEditor` ca. 60, `trip-detail` ca. 150, `edit` übrige ca. 40, Wegpunkt-Editor ca. 25, `shared` ca. 40, Routen ca. 20, Rest ca. 15. Das überschreitet das Limit von 250 deutlich: `workflow.py set-field loc_limit_override 500` einplanen; zeigt die Messung mehr als 500, ist das ein Befund an den Orchestrator (Aufteilung F9a `trip-detail`+Routen+`shared`, F9b `trip-new`+`edit`), nicht ein Grund, Dateien auszulassen.
- **Files:** ca. 60 Code-/Katalogdateien plus 2 Tests plus Golden
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2647 (S2) | Paket | `t`, `tn`, `tr`, `locale`, `fmtDate`, `fmtWeekday` |
| #2649 (S4) | Paket | Ratsche und Allowlist |
| #2654 (F5), #2655 (F6), #2656 (F7), #2657 (F8) | Pakete (vorher) | Tab-Organismen und `metricLabel`; sind sie fertig, bleiben die Allowlist-Reste für die Organismen weg |
| #2652 (F3) | Paket (vorher) | `tripHero.ts` (Tagesangaben, Zeitraum) wird in `TripHeader` schon sprachfähig benutzt |
| #2659 (F10) | Paket (danach) | nutzt `aktionen.*` |
| `docs/reference/i18n_glossar.md` | Doku | Trip, stage, Pausieren = pause, Archivieren = archive, Löschen = delete, Vorschau = preview |
| ADR-0104 | adr | Formate (`Thu 30 Oct`, 24 h), Wortwahl |

## Implementation Details

**1. Katalog.** Nur `messages/{de,en}/aktionen.json` und `messages/{de,en}/trip.json` bearbeiten. `aktionen.*` enthält ausschließlich Texte, die in Trip **und** Ortsvergleich wortgleich vorkommen; ein Text steht nie unter zwei Schlüsseln (Reiter „Alarme" und Aktion „Alarme" sind derselbe Text und nutzen `aktionen.alarms`). Platzhalter in beiden Sprachen gleich (`{tag}`, `{count}`), Plural als `.one`/`.other`. Aktions-IDs mit Bindestrich (`continue-setup`) werden im Schlüssel zu Unterstrich (`aktionen.continue_setup`), weil Schlüssel nur `[a-z0-9_.]` enthalten.

**2. Beispiel-Schlüssel (de / en).**

| Schlüssel | de | en |
|---|---|---|
| `aktionen.pause` | Pausieren | Pause |
| `aktionen.resume` | Fortsetzen | Resume |
| `aktionen.send` | Senden | Send |
| `aktionen.alarms` | Alarme | Alerts |
| `aktionen.weather` | Wetter-Metriken | Weather metrics |
| `aktionen.edit` | Bearbeiten | Edit |
| `aktionen.archive` | Archivieren | Archive |
| `aktionen.unarchive` | Reaktivieren | Reactivate |
| `aktionen.delete` | Löschen | Delete |
| `aktionen.continue_setup` | Setup fortsetzen | Continue setup |
| `aktionen.cancel` | Abbrechen | Cancel |
| `aktionen.weitere` | Weitere Aktionen | More actions |
| `aktionen.reiter.uebersicht` | Übersicht | Overview |
| `aktionen.reiter.etappen_wegpunkte` | Etappen & Wegpunkte | Stages & waypoints |
| `aktionen.reiter.orte` | Orte | Locations |
| `aktionen.reiter.wertebereiche` | Wertebereiche | Target ranges |
| `aktionen.historie.titel` | Versand-Historie | Delivery history |
| `trip.status.draft` | Entwurf | Draft |
| `trip.status.planned` | Geplant | Planned |
| `trip.status.finished` | Fertig | Finished |
| `trip.hub.keine_etappen` | Keine Etappen geplant | No stages planned |
| `trip.hub.briefing_gesendet` | Briefing gesendet! | Briefing sent |
| `trip.hub.loeschen_titel` | Trip endgültig löschen? | Delete trip permanently? |
| `trip.kopf.tag` | Tag {tag} | Day {tag} |
| `trip.uebersicht.unbekannt.one` / `.other` | {count} Größe unbekannt / {count} Größen unbekannt | {count} metric unknown / {count} metrics unknown |
| `trip.etappe.aufstieg` | Aufstieg | Ascent |

Der englische Text darf kein Ausrufezeichen tragen (Stilregel); das deutsche „Briefing gesendet!" bleibt wörtlich.

**3. Beispiel-Umstellung vorher → nachher.**

- `frontend/src/lib/components/shared/subscriptionActions.ts:31-44` — vorher trägt die Tabelle `A` die Labels (`pause: { id: 'pause', label: 'Pausieren' }`) und `ids()` kopiert `{ ...A[id] }`. Nachher hat `A` den Typ `Record<SubscriptionActionId, Omit<SubscriptionAction, 'label'>>` (nur `id`, `danger`), und `ids()` setzt `label: tr('aktionen.' + id.replace('-', '_'))` mit Kommentar `// i18n-dynamic: aktionen.`. Die Aktionsliste der Trip-Liste (F3) und des Ortsvergleichs (F10) wird damit zweisprachig, ohne dass dort ein Schlüssel nötig ist.
- `frontend/src/lib/components/shared/subscriptionTabs.ts:35,41,43` — vorher `label: 'Übersicht'`, `'Wetter-Metriken'`, `'Alarme'`; nachher `tr('aktionen.reiter.uebersicht')`, `tr('aktionen.weather')`, `tr('aktionen.alarms')`.
- `frontend/src/lib/components/trip-detail/TripStatusBadge.svelte:25-30` — vorher `draft: 'Entwurf', planned: 'Geplant', …`, nachher `draft: $t('trip.status.draft')` usw. als `$derived`-Map.
- `frontend/src/lib/components/trip-detail/HubOverview.svelte:131` — vorher `{metricsState?.unknownCount === 1 ? 'Größe unbekannt' : 'Größen unbekannt'}`, nachher `{$tn('trip.uebersicht.unbekannt', metricsState?.unknownCount ?? 0)}`.
- `frontend/src/lib/components/trip-detail/TripHeader.svelte:98` — vorher `` `Tag ${idx + 1}` ``, nachher `$t('trip.kopf.tag', { tag: idx + 1 })`.
- `frontend/src/lib/components/edit/StageDateField.svelte:26-27` — vorher `const WD = ['So', 'Mo', …]` und `WD[new Date(value + 'T00:00:00').getDay()]`, nachher `fmtWeekday(new Date(value + 'T00:00:00'), $locale, true)`; Deutsch bleibt `So`, `Mo` … (byte-gleich), Englisch `Sun`, `Mon` ….
- `frontend/src/lib/components/trip-detail/StageDetailRow.svelte:58-68` — vorher eigener Helfer `formatDate` mit „DD.MM."; nachher: bei `de` unverändert „DD.MM." (byte-gleich), bei `en` `fmtDate(date, 'en', 'kurz')` (z. B. `Thu 30 Oct`). `TripStageRow.svelte:62` zeigt `stage.date` roh; dort bleibt der ISO-Wert (Daten, kein Fließtext), die Anzeige `Thu 30 Oct` entsteht in `StageDetailRow`.
- `frontend/src/lib/components/trip-detail/TripHeader.svelte:139` — `toLocaleString('de-DE')` bleibt bei `de`; bei `en` `en-GB` (Tausendertrennzeichen Komma).

**4. Metrik-Namen.** Alle Stellen, die `entry.label` anzeigen (`ActiveMetricRow`, `BucketSection`, `MetricGroup`, `HubOverview`-Namensliste, `TablePreview`), gehen über `metricLabel(entry, $locale)` aus F5. `col_label` (Spaltenköpfe der Tabellenvorschau) und Kürzel bleiben.

**5. Nicht übersetzen.** Trip-, Etappen-, Wegpunkt- und Regionsnamen, Kanalnamen, Metrik-IDs, `col_label`, Kürzel, `data-testid`, ISO-Daten in Eingabefeldern. Die Platzhalter-Texte in `TripTabs.svelte:81-82` („Inhalt folgt mit Issue …") sind Entwicklungs-Texte, werden aber wie alles andere migriert, damit die Ratsche grün wird.

**6. Allowlist.** Aus `frontend/src/lib/i18n/hardcode_allowlist.json` die Einträge entfernen, die auf Dateien dieser Tabelle zeigen (laut Issue `components/trip-detail`, `components/trip-new`, `components/edit`, `components/email-preview`, `routes/trips/[id]`, `routes/trips/new`; dazu die `shared/`-Dateien dieser Tabelle).

**7. Golden-Fixture.** Vor der Umstellung für Nutzer `golden-de` mit einem laufenden Trip (3 Etappen, 2 Wegpunkte je Etappe, Kanäle E-Mail und Telegram), einem pausierten Trip und einem Entwurf den Trip-Hub (alle Reiter), das Anlegen (`/trips/new`) und den Etappen-Editor per SSR nach `tests/golden/f9_trip_flaechen/<fall>.de.html` schreiben; danach byte-gleich vergleichen. `*.en.html` zur Review einchecken.

## Expected Behavior

- **Input:** Aufruf von `/trips/<id>`, `/trips/<id>/edit`, `/trips/new` mit Nutzer `language=en` oder `de`.
- **Output:** Alle sichtbaren Texte in der Nutzersprache; Trip-/Etappen-Namen, Zahlen, Einheiten, Kanal- und Metrik-IDs unverändert; Etappen-Daten englisch als `Thu 30 Oct`, deutsch unverändert.
- **Side effects:** Keine. Gespeicherte Trips sind in beiden Sprachen identisch.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Sprache Englisch und ein Trip mit drei Etappen / When der Trip-Hub lädt / Then sind alle Reiter und Aktionen englisch („Overview", „Alerts", „Target ranges", „Pause", „Archive", „Delete"), Etappen-Daten erscheinen als `Thu 30 Oct`, und Trip- und Etappen-Namen stehen unverändert.
  - Test: `frontend/src/lib/components/trip-detail/__tests__/trip_hub_sprache.test.ts` — Render mit `locale.set('en')`, Prüfung über `tr()`-Werte und `fmtDate`; Trip-Name byte-gleich zur Eingabe.

- **AC-2:** Given die Aktionsliste `subscriptionActions('trip', …)` und `subscriptionActions('vergleich', …)` / When sie in Englisch ausgewertet wird / Then tragen gleichnamige Aktionen in beiden Arten denselben Text aus demselben Schlüssel `aktionen.*`, und die Aktions-IDs sowie `danger` sind unverändert.
  - Test: `frontend/src/lib/components/trip-detail/__tests__/trip_hub_sprache.test.ts` — Textgleichheit Trip/Vergleich je Aktion; Schlüsselherkunft `aktionen.*`; die vorhandenen Tests `subscriptionActions.test.ts` bleiben grün.

- **AC-3:** Given das Anlegen eines Trips (`/trips/new`) und der Etappen-Editor in Englisch / When der Nutzer einen Trip-Namen, ein Startdatum und eine Etappe eingibt / Then stehen Reiter, Hinweise, Schaltflächen und Fehlermeldungen auf Englisch, das Datumsfeld zeigt den Wochentag als `Mon`/`Tue`, und die eingegebenen Namen werden unverändert gespeichert.
  - Test: `frontend/src/lib/components/trip-new/__tests__/trip_anlegen_sprache.test.ts` — Render und Eingabe in `en` und `de`, Wochentag über `fmtWeekday`, Nutzlast unverändert.

- **AC-4:** Given Metrik-Einträge mit und ohne `label_en` / When Trip-Hub (Übersicht, Metrik-Gruppen, Tabellenvorschau) in Englisch angezeigt wird / Then steht die volle Form englisch bzw. bei fehlendem `label_en` deutsch, und die Spaltenköpfe `col_label` stehen unverändert.
  - Test: `frontend/src/lib/components/trip-detail/__tests__/trip_hub_sprache.test.ts` — `metricLabel`-Verdrahtung in `ActiveMetricRow`/`TablePreview`, `col_label` byte-gleich.

- **AC-5:** Given Nutzer A (Englisch) mit Trip X und Nutzer B (Deutsch) mit Trip Y / When beide ihren Trip-Hub öffnen, einen Namen ändern und speichern / Then sieht A nur Trip X englisch und B nur Trip Y deutsch, die gespeicherte Nutzlast ist je Nutzer sprachunabhängig identisch aufgebaut, und keiner kann den Trip des anderen laden.
  - Test: `frontend/src/lib/components/trip-detail/__tests__/trip_hub_sprache.test.ts` — zwei Nutzer in einem Lauf (`locals.userId` und `locals.lang` je Nutzer), Lade- und Speicherpfad.

- **AC-6:** Given die deutsche Oberfläche / When Trip-Hub, Anlegen und Etappen-Editor mit der Fixture `golden-de` gerendert werden / Then ist die Ausgabe Byte für Byte gleich zu `tests/golden/f9_trip_flaechen/*.de.html`.
  - Test: `frontend/src/lib/components/trip-detail/__tests__/trip_hub_sprache.test.ts` — Golden-Vergleich (deutsche Ausgabe unverändert).

- **AC-7:** Given der Trip-Status Entwurf, geplant, aktiv, pausiert, fertig, archiviert / When `TripStatusBadge` in Englisch gerendert wird / Then lauten die Texte „Draft", „Planned", „Active", „Paused", „Finished", „Archived", deutsch weiterhin „Entwurf", „Geplant", „Aktiv", „Pausiert", „Fertig", „Archiviert".
  - Test: `frontend/src/lib/components/trip-detail/__tests__/trip_hub_sprache.test.ts` — Tabelle Status → Text in beiden Sprachen; der vorhandene Test `TripStatusBadge.atomic.test.ts` bleibt grün.

- **AC-8:** Given die Allowlist der Ratsche / When `keine_hartkodierten_nutzertexte.test.ts` und der Paritätstest laufen / Then gibt es keine Treffer mehr in den Dateien dieses Pakets, die Allowlist enthält keinen Eintrag mehr für `components/trip-detail`, `components/trip-new`, `components/edit`, `components/email-preview`, `routes/trips/[id]`, `routes/trips/new`, und `aktionen` sowie `trip` haben in de und en identische Schlüssel- und Platzhaltermengen.
  - Test: `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` und `paritaet_de_en.test.ts` — Ratschen-/Paritätstest (`# doc-compliance-test`).

## Known Limitations

- **A1 (Annahme):** `subscriptionActions.ts`, `subscriptionTabs.ts`, `SubscriptionHeader.svelte` und `BriefingHistory.svelte` liegen unter `shared/` außerhalb aller genannten Ordner; sie stehen in diesem Paket, weil F9 den Namensraum `aktionen.*` anlegt und der Trip-Hub ihr erster Verwender ist.
- **A2 (Annahme):** Wortgleiche Basistexte, die frühere Pakete (F3 bis F8) unter ihren eigenen Bereichen angelegt haben (z. B. „Wiederholen", „Abbrechen"), werden hier **nicht** umbenannt oder verschoben (Schlüssel werden nie umbenannt); die Zusammenführung nach `aktionen.*` ist ein Nebenbefund nach F10.
- **A3 (Annahme):** `TripStageRow` zeigt `stage.date` roh (ISO). Das bleibt so; die lesbare Datumsangabe entsteht in `StageDetailRow` über `fmtDate`.
- Liefert `fmtWeekday` für Deutsch eine Abkürzung mit Punkt (`So.` statt `So`), ist das ein Fehler in S2 und wird dort behoben; F9 passt die deutsche Ausgabe nicht an.
- Dateien ohne Ratschen-Treffer (z. B. `index.ts`) bleiben unberührt; der Entwickler prüft jede Datei der Tabelle mit der Ratsche.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Wortgleiche Texte von Trip und Ortsvergleich stehen einmal in `aktionen.*`; die Sprache gehört dem Nutzer, Deutsch bleibt byte-gleich.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
