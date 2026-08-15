# Context: feat-1720-vorschau-metriken

<!-- Issue #1720 — Bedienelement für die Metriken der 3-Tages-Vorschau der Trip-Mail -->
<!-- Gemessen 2026-08-14 gegen origin/main b26d88a9. Alle Zeilenangaben aus dieser Messung. -->

## Request Summary

Die 3-Tages-Vorschau (Mehrtages-Ausblick) eines Trips zeigt fest verdrahtete
Spalten. Der PO will auf derselben Seite wie die übrige Metrik-Steuerung
(`/trips/<id>?tab=weather`) ein Bedienelement, mit dem sich diese Spalten
auswählen lassen — nach dem Modell aus #1719/ADR-0050: Grundauswahl = Maximum,
hier darf nur abgewählt werden, „Aus" ist ein Zustand und keine Löschung.

## Der Ist-Stand, gemessen

### Vier Trip-Ausgabeorte, alle hart verdrahtet

Das Issue nennt die HTML-Mail. Gemessen sind es **vier** Ausgabeorte mit
**drei unabhängigen** Implementierungen — geteilt sind nur der Zeilenbau
(`build_outlook_row`) und die Token-Formatierung (`format_trend_tokens`), nicht
die Spaltenwahl:

| # | Ausgabeort | Renderer | Gezeigte Größen |
|---|---|---|---|
| 1 | E-Mail HTML (`full`) | `email/html.py:1357` → `email/outlook.py:174-187` | `Tag · N · D · R · PR · Wind · Böen · Gew · ACC` (9 Spalten) |
| 2 | E-Mail Klartext (`full`) | `email/plain.py:338` → `email/outlook.py:321-414` | Wochentag · Name · Temp · Regen · Wind · Gewitter [· nachts] [· Hagel] |
| 3 | E-Mail Kompakt (`compact`) | `email/compact.py:227-238` — **eigener Inline-Loop** | 6 Felder; **ohne** Böen, Regenwahrscheinlichkeit, ACC, Tag/Nacht-Split, Hagel |
| 4 | Telegram „rich" | `narrow.py:571-609` (`_outlook_lines`), Aufruf `:820` | Wochentag · Temp · Regen · Wind · Gewitter [· nachts] |

Vorschau-Endpunkte (`/api/preview/{id}/email|telegram`) rufen dieselben vier
Pfade auf und haben keinen eigenen Renderer.

**Baulich nicht erreichbar:** SMS und Premium-SMS. Beide senden
`report.sms_text or report.email_plain` (`notification_service.py:431-434`,
`:449-451`); `sms_trip.py` kennt `multi_day_trend` nicht — der Ausblick kann
dort nicht ankommen. Telegram-Kurzform nutzt dieselbe Quelle (Konfigurations-,
keine bauliche Grenze).

**Per Konfiguration abschaltbar:** `report_config.show_outlook` (Default `True`)
und `report_config.multi_day_trend_reports` (Default `["evening"]` — im
Morgenbericht wird der Ausblick gar nicht erst gebaut,
`trip_report_scheduler.py:1279-1283`).

### Der Ortsvergleich hat die vollständige Kette bereits

Seit #1361/#1368 (ADR-0037) ist der Compare-Ausblick katalog-getrieben. Die
Kette, die für den Trip nachzubauen bzw. zu teilen wäre:

| Schicht | Compare-Stelle |
|---|---|
| Oberfläche | `shared/CompareOutlookLayoutControls.svelte:102-174` — Abschnitt „3-Tages-Ausblick": An/Aus-Schalter, Metrik-Auswahl (gruppiert über `groupCompareCatalog`), Reihenfolge über den geteilten `WeatherV2Reihenfolge` |
| Reiter | eingebettet in `shared/WeatherMetricsTab.svelte:1348-1351`, gated durch `sections.includes('ausblick')` |
| Zustand | `compareWizardState.svelte.ts:57` (`outlookMetricKeys`), `:76` (`outlookEnabled`) |
| Speicherweg | `compareHubWizardBridge.ts:205-209` → `compareEditorSave.ts:170-176` → PUT |
| Persistenz | `display_config.outlook_metrics`, Neuformat `[{"metric_id":…,"aggregation":…}]` |
| Auflösung | `resolve_outlook_metrics()` (`compare_outlook_metric_ids.py:45-75`) → `CompareRenderOptions.outlook_metrics` (`report_config_resolver.py:249,291`) |
| Renderer | `render_compare_email()` → `render_outlook_table(..., metrics=…)` / `render_outlook_plain(..., metrics=…)`; Spalten aus `outlook_columns()` (`compare_outlook_metric_ids.py:78-114`), Zellen aus `build_outlook_row(..., metrics=…)` (`outlook.py:551-574`) |

**Semantik des Feldes** (`compare_outlook_metric_ids.py:45-75`):
`None`/fehlt → die bisherigen festen Spalten · `[]` → der ganze Ausblick-Block
entfällt · gefüllt → aufgelöste Paare in Auswahl-Reihenfolge, ungültige
Einträge werden verworfen und geloggt.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/email/outlook.py:66-314` | `render_outlook_table` — Legacy-Zweig (`metrics=None`, Zeilen 174-187) vs. Katalog-Zweig (`:148-172`) |
| `src/output/renderers/email/outlook.py:321-414` | `render_outlook_plain`, dieselbe Zwei-Zweig-Struktur (`:347-353`) |
| `src/output/renderers/email/outlook.py:421-576` | `build_outlook_row` — baut das Row-Dict; im `metrics`-Fall zusätzlich `row["cells"]` |
| `src/output/renderers/email/compact.py:227-238` | Dritte, unabhängige Ausblick-Implementierung |
| `src/output/renderers/narrow.py:571-609,820` | Vierte Implementierung (Telegram-Bubble) |
| `src/output/renderers/compare_outlook_metric_ids.py` | `resolve_outlook_metrics()`, `outlook_columns()`, `format_outlook_value()` — trägt `compare_` im Namen, ist aber generisch |
| `src/services/report_config_resolver.py:104-157` | `ReportRenderOptions` (Trip) — trägt `display_config` bereits **als Ganzes** durch; kein neuer Parameter durch die Kette nötig |
| `src/services/trip_report_scheduler.py:2029-2193` | `_build_stage_trend()` — Erzeuger von `multi_day_trend` |
| `src/app/models.py:774-807` | `UnifiedWeatherDisplayConfig` — **typisierte** Dataclass, hat kein `outlook_metrics` |
| `src/app/loader.py:837-921` | Liest `channel_layouts` etc. aus dem Rohdict — Vorbild für ein neues Feld |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | Geteilter Reiter, Prop `context: 'route'\|'vergleich'` (`:130-131,168`) |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:44-69` | Abschnitts-Steuerung; `'ausblick'` steht in `COMPARE_ONLY_SECTIONS` |
| `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte` | Das vorhandene Bedienelement |
| `internal/handler/config_merge.go:11-22` | `mergeConfigMap` — Top-Level-Key-Merge (RMW), `display_config` ist Go-seitig opak |

## Existing Patterns

- **Der Katalog-Zweig im Renderer existiert schon.** `render_outlook_table` /
  `render_outlook_plain` / `build_outlook_row` nehmen alle einen additiven
  `metrics`-Parameter. Für den Trip ist das keine neue Bauform, sondern das
  Setzen eines bereits vorhandenen Arguments.
- **Kanal-Ebene nach ADR-0050** ist im Trip-Reiter bereits gebaut:
  `LayoutTab.svelte` mit Kanal-Tabs E-Mail/Telegram/SMS; global abwählen
  schreibt in alle Kanal-Overrides durch (`WeatherMetricsTab.svelte:710-740`),
  kanal-eigen schreiben über `editActiveChannel` (`:751-785`).
- **`display_config` reist Go-seitig als opake Map** (`internal/model/trip.go:111`)
  — ein neues Feld braucht keinen Go-Schema-Change, aber die RMW-Pflicht beim
  Speichern gilt (Blind-Replace-Fehlerklasse #102 → #1159).

## Existing Specs & ADRs

| Dokument | Bezug |
|---|---|
| `docs/adr/0037-datengetriebener-ausblick-aus-metrik-katalog.md` | Legt Format und Semantik fest. **Punkt 2 sichert ausdrücklich zu: „Der Trip ruft weiterhin ohne `metrics` auf — die Trip-Mail ändert sich in keinem Byte."** #1720 löst diesen Punkt ab ⇒ neues ADR bzw. Fortschreibung ist Pflicht (CLAUDE.md: keine stille Rücknahme) |
| `docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md` | Grundauswahl = Maximum, Kanal darf nur abwählen, „Aus" ist ein Zustand |
| `docs/adr/0053-compare-kanal-eigene-metrikauswahl-uebersicht.md` | Punkt 1: Ausblick und Stundenverlauf des Vergleichs führen **bewusst je eine globale Liste ohne Kanal-Ebene** |
| `docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md:533-546` | Ursprungs-Spec des Compare-Ausblicks; „Out of Scope: Trip-Auswahlfläche" |
| `docs/specs/modules/feat_1406a_ausblick_geteiltes_element.md` | Hebt den Auswahl-Block auf das gruppierte Muster |
| `docs/reference/metric_output_matrix.md:89,114,204-243,575-579` | Ist-Stand-Matrix; benennt den Trip-Ausblick als „nicht katalog-getrieben" und den Trend-Pfad in Telegram/Kompakt als **unbewacht** |

## Dependencies

- **Upstream (erfüllt):** #1719 ist mit allen vier Scheiben geschlossen
  (S1–S4 live); das Verfeinerungs-Modell steht im Backend. Die im Issue
  genannte Abhängigkeit ist eingelöst.
- **Downstream:** `render_outlook_table` / `render_outlook_plain` /
  `build_outlook_row` bedienen **Trip und Ortsvergleich gemeinsam**. Jede
  Änderung am Legacy-Zweig trifft beide Mail-Familien.

## Risks & Considerations

1. **Byte-Golden schlägt planmäßig an.** `tests/tdd/test_trip_outlook_parity.py`
   vergleicht HTML und Klartext des Trip-Ausblicks byte-genau gegen Golden-Dateien
   (`tests/fixtures/outlook_trip_parity/`), `test_shared_outlook_renderer.py`
   ebenso. Sie sind ausdrücklich so gebaut, dass Golden-Dateien bei Rot **nicht**
   nachgezogen werden. Ein bewusster, begründeter Nachzug ist Teil der Lieferung —
   nicht ein „Test reparieren".
2. **Zwei Ausgabeorte haben gar keinen Wächter.** Für Kompakt-Mail
   (`compact.py:227-238`) und Telegram-Bubble (`narrow.py:571-609`) existiert
   kein Byte-Wächter; die Metrik-Matrix hält das ausdrücklich als offene Stelle
   fest (`metric_output_matrix.md:237-243`). Was dort geändert wird, fällt heute
   niemandem auf.
3. **Persistenz-Schema-Änderung auf der Trip-Seite.**
   `UnifiedWeatherDisplayConfig` ist eine typisierte Dataclass ohne
   `outlook_metrics` — anders als beim Compare, wo `display_config` durchgehend
   opak ist. Neues Feld ⇒ Loader (`loader.py`) + Roundtrip-Test + RMW-Pflicht;
   der Pre-Snapshot-Hook `data_schema_backup.py` löst bei Edits an `models.py`
   und `loader.py` automatisch aus.
4. **Zwei verschiedene Kataloge.** Der Compare-Ausblick löst über
   `get_compare_metric_catalog()` auf (25 wählbare Paare); der Trip-Reiter lädt
   `/api/metrics` (`MetricCatalog`). Welcher Katalog die Trip-Vorschau speist —
   und ob `selectable=false`-Metriken wie `confidence` weiterhin ausgeschlossen
   bleiben (PO-Entscheid #710: `confidence_pct` ist **nie** wählbar; die
   ACC-Spalte ist genau diese Größe) — ist in der Spec zu klären.
5. **Das vorhandene Bedienelement ist nicht ohne Weiteres wiederverwendbar.**
   `CompareOutlookLayoutControls.svelte` liegt zwar in `shared/`, ist aber an
   `CompareWizardState` typgebunden (`:31,43`), erwartet die Compare-Katalogform,
   hat `activeChannel="email"` hart verdrahtet (`:167`) und ist bewusst
   speicherfrei (externer Commit-Wrapper) — der Trip speichert dagegen über
   `userTouched = true; scheduleAutoSave()`. Der Teilungs-Gate-Punkt aus CLAUDE.md
   greift hier: entweder den Baustein echt parametrisieren oder die Abweichung in
   der Spec begründen. Die Pendant-Sperre (`pendant_gate.py`) blockiert eine neue
   Datei unter `trip-detail/**` ohne Begründungszeile.
6. **`activeChannel="email"` stimmt für den Trip nicht.** Die Begründung im
   Compare lautet „Ausblick existiert nur in `render_compare_email`". Beim Trip
   erscheint der Ausblick zusätzlich in der Kompakt-Mail und im Telegram-Bubble
   (s. o.) — eine 1:1-Übernahme der Annahme wäre falsch. Ob die Auswahl global
   gilt (wie beim Compare, ADR-0053 Punkt 1) oder je Kanal, ist eine
   PO-Entscheidung für die Spec.
7. **Nur 9 von ~25 Summary-Feldern erreichen heute das Row-Dict.** Der
   Legacy-Zweig von `build_outlook_row` liest gezielt neun Felder
   (`outlook.py:502-549`); der Katalog-Zweig greift dagegen generisch per
   `getattr(summary, col["field"])` zu. Der Umstieg öffnet damit automatisch den
   vollen Katalog — was gewollt ist, aber die Zellenformatierung für bislang nie
   gerenderte Größen betrifft (Risiko 6 der Ursprungs-Spec).
8. **Parallele Session im selben Bereich.** `witty-dancing-journal` arbeitet auf
   `feat-1680-s5b-vorschau-herkunft` (Gewitter-Vorschau). Das ist ein anderer
   Baustein — die separate „⚡ Gewitter-Vorschau" (`html.py:1309-1329`), die
   genau dann erscheint, wenn der volle Ausblick fehlt —, fasst aber
   möglicherweise dieselben Dateien an. Vor dem Liefern rebasen.

## Nebenbefund: die Legende ist nachweislich falsch

Die HTML-Legende sagt `N Nacht-Tief` (`email/html.py:1363`). Die Spalte zeigt
`stage["temp_lo"]` (`outlook.py:213,272`). Beleg-Kette bis zum Erzeuger:
`temp_lo = summary.temp_min_c` (`outlook.py:459`) ← `aggregate_stage()` MIN über
die Segment-Minima (`weather_metrics.py:1252-1253`) ← `_compute_temperature`
`min(temps)` über die Zeitreihe des Segments (`weather_metrics.py:509-514`) ←
Segmentfenster = **Wanderzeit** ab `stage.start_time` (Default 08:00,
`trip_segments.py:132`) bis zur letzten Wegpunkt-Ankunft.

`temp_lo` ist damit das **Tages-Minimum innerhalb des Wanderfensters**, nicht das
nächtliche Tief. Die Nachtdaten sind ein eigener, hier nicht einfließender
Datensatz (`_fetch_night_weather()`, `trip_report_scheduler.py:1880,2192`).
Die Beschriftung behauptet eine Aussage, die die Zahl nicht trägt — unabhängig
von der Konfigurierbarkeit.

## Analysis (Phase 2, 2026-08-14)

### Type

**Feature.** PO-Auftrag, neue Funktionalität — kein Fehlverhalten gegenüber einer
Zusage. (Der Nebenbefund zur Legende ist ein Bug, aber nicht der Auftrag.)

### Technischer Ansatz

Der Weg ist kürzer als erwartet, weil zwei Voraussetzungen bereits erfüllt sind:

1. **Der Katalog-Zweig im Renderer existiert.** `render_outlook_table`,
   `render_outlook_plain` und `build_outlook_row` nehmen alle bereits einen
   additiven `metrics`-Parameter (`outlook.py:66-80,321-341,421`). Für den Trip
   ist das kein Neubau, sondern das Setzen eines vorhandenen Arguments.
2. **`dc: UnifiedWeatherDisplayConfig` ist bereits Pflichtparameter aller vier
   Renderer** — `render_html()` (`html.py:956`), `render_plain()`,
   `render_compact()` (`compact.py:99`), `render_telegram_bubbles()`
   (`narrow.py:635`) — und zwar genau dort im Scope, wo der Ausblick gerendert
   wird. Es muss **keine einzige Funktionssignatur** der Aufrufkette geändert
   werden.

Daraus:

| Schritt | Stelle | Art |
|---|---|---|
| Feld anlegen | `src/app/models.py:774-807` — `outlook_metrics: Optional[list[dict]] = None` | MODIFY |
| Laden | `src/app/loader.py:912-927` — `data.get("outlook_metrics")` | MODIFY |
| Zurückschreiben | `src/app/loader.py:1524-1544` — Serialisierung | MODIFY |
| Auflösen + Zellen füllen | `trip_report_scheduler.py:2145,2161` — `resolve_outlook_metrics(...)` an `build_outlook_row(..., metrics=…)` | MODIFY |
| Wirken (HTML) | `email/html.py:1357` — `metrics=` setzen | MODIFY |
| Wirken (Klartext) | `email/plain.py:338` — `metrics=` setzen | MODIFY |
| Bedienelement | `shared/CompareOutlookLayoutControls.svelte` — von `CompareWizardState` auf flache Props umstellen | MODIFY |
| Abschnitt freischalten | `weatherMetricsTabSections.ts:56` — `'ausblick'` aus `COMPARE_ONLY_SECTIONS` lösen | MODIFY |
| Trip-Zweig verdrahten | `shared/WeatherMetricsTab.svelte` — `$state`, `initFromTrip`, `buildWeatherPayload`, `snapshot`/`isDirty`/`handleDiscard` | MODIFY |
| Go | — | **keine Änderung** (`display_config` ist `map[string]interface{}`, `mergeConfigMap` merged feldweise) |

**Katalog-Quelle:** Der Picker muss denselben Katalog laden, gegen den
`resolve_outlook_metrics()` validiert — `get_compare_metric_catalog()` /
`/api/compare/metrics`, **nicht** den Trip-eigenen `/api/metrics`. Sonst bietet
die Oberfläche Größen an, die der Resolver anschließend still verwirft
(`compare_outlook_metric_ids.py:19-31,70-74`). Das entscheidet Risiko 4 oben.

### Scope Assessment

- **LoC-Budget, nachgemessen:** 250 Produktiv **plus getrennt 500 Test**
  (`config_loader.py:264-297`, `max_test_loc_delta`, Override-Feld
  `test_loc_limit_override`). CLAUDE.md nennt nur die 250 — das getrennte
  Test-Budget existiert und ist der Grund, warum Playwright-Klickpfad und
  Wirkort-Test den Kern-Zuschnitt nicht sprengen.
- **Scheibe 1:** ~35 LoC Backend + ~110–125 LoC Frontend = **~120–160 LoC** Kern.
- **Scheibe 2:** ~40–60 LoC (Kompakt-Mail + Telegram).
- **Risiko: MEDIUM–HIGH.** Geteilter Renderer für Trip und Vergleich; die
  Bestandsschutz-Zusage betrifft 100 % der heutigen Trips.

### 🔴 Der Befund, der die Testplanung bestimmt

**Der stärkste vorhandene Wächter erreicht die Stelle nicht, an der die Änderung
wirkt.** `tests/tdd/test_trip_outlook_parity.py:96,117` ruft
`render_outlook_table(parity_rows(), show_acc=True)` bzw.
`render_outlook_plain(...)` **direkt** — mit `metrics` auf dem Default `None`.
Die neue Verdrahtung in `html.py:1357` / `plain.py:338` wird von diesem Test nie
durchlaufen.

Folge: Er bleibt grün, gleichgültig ob die neue Aufrufstelle richtig oder falsch
ist. Verwechselt sie `None` mit `[]`, wäre der Ausblick für **alle**
Bestandstrips still leer — und der Golden-Test meldete nichts. Der Byte-Golden
ist also weder Hindernis noch Schutz; er ist an dieser Frage schlicht blind.

Der Bestandsschutz braucht deshalb einen **neuen** Test, der den echten
Aufrufpfad treibt (`render_email()` bzw. `_build_stage_trend()`) und HTML plus
Klartext gegen eine vorher aufgezeichnete Referenz vergleicht. Golden-Dateien
werden **nicht** nachgezogen. Vgl. die Projektregel „Prüfort muss dem Wirkort
entsprechen".

### Mutations-Gegenproben, die ein Test fangen muss

1. `resolve_outlook_metrics(dc.outlook_metrics)` wird zu `... or []` verkürzt
   (`None` als leer behandelt) ⇒ Bestandsschutz-Test muss rot werden.
2. `metrics=` wird nur an `render_outlook_table` (HTML), nicht an
   `render_outlook_plain` (Klartext) übergeben ⇒ ein Test, der **beide**
   zugestellten Formate auf dieselbe Auswahl prüft, fängt das.
3. Der Picker lädt den ungefilterten Registry-Katalog statt
   `get_compare_metric_catalog()`, wodurch `confidence` (`selectable=false`,
   PO-Entscheid #710 — die ACC-Spalte **ist** diese Größe) wählbar wird ⇒ Test
   auf Abwesenheit im Picker **und** serverseitige Ablehnung eines manipulierten
   PUT-Payloads.
4. Die Auswahl-Reihenfolge wird über ein `Set` statt eine geordnete Liste geführt
   ⇒ Test wählt drei Größen bewusst unsortiert und prüft die exakte Spaltenfolge.
5. Das Speichern schreibt `display_config` als Vollersatz statt feldweise ⇒
   Roundtrip-Test: erst Grundauswahl + Kanal-Layout setzen, dann nur die
   Ausblick-Auswahl speichern; die früheren Felder müssen unverändert bleiben.

### 🔴 Korrektur an der strategischen Bewertung — zum zweiten Mal dieselbe Fehlerklasse

Die Bewertung begründete „keine Kanal-Ebene" mit einem wörtlichen ADR-0053-Zitat:
„Ausblick bleibt bewusst global (…), kein Widerspruch zur Kaskaden-Zusage aus
ADR-0050, weil diese sich auf Kanäle bezieht, nicht auf Ausgabeflächen."

Nachgemessen lautet der Satz (`docs/adr/0053-…:50-54`):

> Ausblick (`outlook_metrics`) und Stundenverlauf (`hourly_metrics`) bleiben
> **in dieser Scheibe** bewusst global — eigene, getrennt gespeicherte
> Auswahllisten ohne Kanal-Ebene (**Scheiben-Schnitt**, kein Widerspruch zur
> Kaskaden-Zusage aus ADR-0050, weil diese sich auf Kanäle bezieht, nicht auf
> Ausgabeflächen).

Weggefallen sind „in dieser Scheibe" und „Scheiben-Schnitt". Der Klammerzusatz
rechtfertigt **den Schnitt**, nicht eine grundsätzliche Eigenschaft des
Ausblicks. Damit trägt die Begründung nicht — die Empfehlung selbst kann trotzdem
richtig sein, braucht aber eine eigene.

Das ist **dieselbe Fehlerklasse wie beim Code-Kommentar in Phase 1**, zum zweiten
Mal in diesem Workflow: eine Zuschnittgrenze wird beim Weiterreichen zur
Festlegung. Vgl. #1680 S5a, wo eine Blockade-Begründung vier Scheiben lang
weitergereicht wurde, ohne je gemessen worden zu sein.

**Tragfähige Begründung für „global":** SMS und Premium-SMS erreichen den
Ausblick baulich nicht; wirksam wären genau zwei Kanäle (E-Mail in drei Formen,
Telegram). Eine Kanal-Ebene für zwei Kanäle verdoppelt Speicherweg, Resolver und
Bedienfläche für einen Nutzen, den niemand angefragt hat. Das ist ein
Aufwand-Nutzen-Argument — und damit eine PO-Entscheidung, keine aus einem ADR
ableitbare.

### Empfohlener Zuschnitt

**Scheibe 1 (~120–160 LoC):** Globale, kanal-freie Ausblick-Spaltenauswahl für
den Trip als eigener Abschnitt „3-Tages-Vorschau" in
`/trips/<id>?tab=weather` — dasselbe Bauteil wie beim Ortsvergleich,
parametrisiert statt kopiert. Wirkt in HTML- und Klartext-Trip-Mail.
Nutzersichtbar: abwählen, speichern, die nächste zugestellte Mail zeigt genau
diese Auswahl in dieser Reihenfolge.

**Scheibe 2 (~40–60 LoC):** Kompakt-Mail und Telegram ziehen nach. Weil dort
**kein** Wächter existiert, legt Scheibe 2 zuerst einen Charakterisierungstest
des heutigen Ist-Zustands an, bevor etwas geändert wird.

Bis Scheibe 2 live ist, trägt der Abschnitt denselben Hinweistext wie beim
Ortsvergleich („Erscheint nur in der E-Mail",
`CompareOutlookLayoutControls.svelte:159-161`) — kein neuer Bruch, sondern ein
bereits akzeptiertes Muster.

## PO-Entscheidungen (2026-08-14, entschieden)

1. **Umfang: alle vier Ausgabeorte, in zwei Scheiben.** Scheibe 1 liefert HTML-
   und Klartext-Mail; Scheibe 2 zieht Kompakt-Mail und Telegram unmittelbar
   danach nach — nicht auf unbestimmte Zeit vertagt. Scheibe 2 legt **zuerst**
   einen Charakterisierungstest des heutigen Ist-Zustands an, weil dort kein
   Wächter existiert. Bis Scheibe 2 live ist, trägt der Abschnitt denselben
   Hinweistext wie beim Ortsvergleich („Erscheint nur in der E-Mail").
2. **Keine Kanal-Ebene — eine Auswahl für alle.** Ein Abschnitt
   „3-Tages-Vorschau", eine Liste, wie beim Ortsvergleich. Damit ist auch die im
   Issue offen gelassene Gestaltungsfrage beantwortet: weder eigener
   Kanal-Eintrag noch Unterabschnitt des E-Mail-Kanals, sondern ein eigener
   Abschnitt im selben Reiter — an derselben Stelle, an der er beim
   Ortsvergleich bereits sitzt.
   **Begründung (tragfähig, nicht aus ADR-0053 abgeleitet):** SMS und
   Premium-SMS erreichen den Ausblick baulich nicht; wirksam wären genau zwei
   Kanäle. Eine Kanal-Ebene für zwei Kanäle verdoppelt Bedienfläche,
   Speicherweg und Auflösung ohne angefragten Nutzen.
3. **Die falsche Legende wird in dieser Lieferung mitkorrigiert.** `N` heißt
   künftig nicht mehr „Nacht-Tief". Begründung des PO-Entscheids: eine falsche
   Beschriftung in einem Briefing-Werkzeug ist eine Fehlinformation bei einer
   Tourenentscheidung, und die Stelle wird ohnehin angefasst.

## Zur Notiz im Code, die dagegen zu sprechen scheint

`weatherMetricsTabSections.ts:54-55` trägt: „Ebenfalls NUR im Vergleich: der Trip
bekommt bewusst keine Ausblick-Auswahlfläche (Spec § Out of Scope)." Am Ursprung
nachgemessen lautet der Satz dort:

> **Trip-Auswahlfläche für den Ausblick.** Der Trip bekommt keine Bedienfläche —
> das Epic betrifft ausschließlich den Ortsvergleich (E3).
> (`docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md:535-536`)

Das ist die **Zuschnittgrenze jener Lieferung**, keine Produktentscheidung gegen
ein Trip-Bedienelement. Der Code-Kommentar verkürzt sie zu „bewusst keine" und
liest sich dadurch wie eine dauerhafte Festlegung. Wer ihn so liest, hält #1720
für einen Widerspruch zu einer getroffenen Entscheidung — er ist keiner.
Vgl. die gleichartige Fehlerklasse in #1680 S5a, wo eine Blockade-Begründung vier
Scheiben lang weitergereicht wurde, ohne je gemessen worden zu sein.

**Was dagegen wirklich abzulösen ist:** ADR-0037 Punkt 2 (Trip-Mail bleibt
byte-identisch). Das ist eine akzeptierte Entscheidung und braucht ein neues ADR
mit Status-Fortschreibung.
