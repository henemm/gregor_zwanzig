---
entity_id: issue_1361_1368_ausblick_konfigurierbar
type: feature
created: 2026-07-27
updated: 2026-07-27
status: draft
version: "1.0"
workflow: fix-1361-1368-ausblick-konfigurierbar
tags: [compare, outlook, ausblick, mail, metrik-katalog, feature, epic-1372]
---

# 3-Tages-Ausblick der Vergleichs-Mail: Spaltenauswahl, Überschrift, richtiger Starttag (Issue #1361 Befund 2 + #1368, S3 Scheibe A von Epic #1372)

## Approval

- [ ] Approved

## Purpose

Der 3-Tages-Ausblick der Ortsvergleichs-Mail zeigt heute unveränderlich
dieselben sieben Größen (Temp min/max, Regen, Regen-Wahrscheinlichkeit, Wind,
Böen, Gewitter), ohne eigene Überschrift, und beginnt am selben Kalendertag,
den die Stundentabelle bereits im Detail zeigt — an einer echt zugestellten
Staging-Mail belegt (siehe Kontext-Dokument, Beleg-Tabelle). Dieses Modul
macht die Ausblick-Spalten frei wählbar aus dem vollen Metrik-Katalog (wie
bereits Übersichtstabelle und Stundenverlauf), gibt dem Block eine erkennbare
Überschrift in HTML und Klartext, und stellt sicher, dass der Ausblick immer
erst NACH dem im Detail gezeigten Tag beginnt — auch wenn das Tagesfenster
über Mitternacht reicht. Die Trip-Mail bleibt dabei byte-identisch: der
geteilte Baustein bekommt eine neue, optionale Auswahl-Fähigkeit, ändert aber
sein Standardverhalten für Aufrufer ohne Auswahl nicht.

## Source

- **File:** `src/output/renderers/email/outlook.py` — geteilter Baustein
  (Trip UND Compare). `build_outlook_row()` (Zeile 236-321) baut heute ein
  festes Dict aus sieben Größen; bekommt einen neuen optionalen `metrics`-
  Parameter (Liste `{metric_id, aggregation}`), der bei Angabe zusätzlich zu
  den bestehenden Feldern eine geordnete Zellen-Liste aus dem zentralen
  Katalog liefert. `render_outlook_table()` (Zeile 40-195) und
  `render_outlook_plain()` (Zeile 202-229) rendern heute die feste
  Sieben-Spalten-Kopfzeile bzw. den festen Klartext-Block ("Nächste
  Etappen", Zeile 211); beide bekommen die Fähigkeit, bei gesetzter Auswahl
  datengetriebene Spalten/Zeilen zu rendern, und einen parametrisierbaren
  Überschrift-Text (Default unverändert "Nächste Etappen" für Trip).
- **File:** `src/app/metric_catalog.py` — zentraler Katalog
  (`MetricDefinition`, Zeile 25-70), Quelle für `id`, `summary_fields`
  (Aggregation → `SegmentWeatherSummary`-Feldname), `col_label` und
  `selectable`. 26 Einträge, 24 davon `selectable=True` mit `summary_fields`
  — genau diese 24 sind für den Ausblick wählbar (die zwei
  `selectable=False`-Einträge `temperature_cold`/`confidence` bleiben
  ausgeschlossen, ADR-0005/#710 für `confidence`).
- **File:** `src/output/renderers/compare_metric_catalog.py` —
  `COMPARE_METRIC_CATALOG` (Zeile 51-132) deckt bereits alle 24 wählbaren
  zentralen Größen ab (kuratierte Kanonisierung, u.a. je eine typische
  Aggregation je Größe), `key_for()` (Zeile 209-218) löst ein
  `{metric_id, aggregation}`-Paar auf einen bekannten Auswahl-Schlüssel auf
  oder liefert `None` bei unbekanntem Paar — dieselbe Funktion, die
  `active_metrics` (#1373) bereits nutzt. **Kein Katalog-Eingriff nötig.**
- **File:** `src/services/comparison_engine.py` — `ComparisonEngine.run()`
  (Zeile 93-…), konkret die Ausblick-Tages-Auswahl `_outlook_days = sorted({d
  for _dp, d in _by_local_day if d >= target_date})[:3]` (Zeile 149-151).
  `>= target_date` schließt den im Detail gezeigten Tag ein — Ursache der
  V1-Verletzung; wird durch eine Grenze ersetzt, die den letzten von der
  Stundentabelle berührten Kalendertag ausschließt (s. Implementation
  Details Punkt 1).
- **File:** `src/output/renderers/email/compare_html.py` —
  `_render_location_outlook()` (Zeile 816-833) und
  `_build_location_outlook_rows()` (Zeile 794-813) rufen `build_outlook_row`
  ohne Auswahl auf; `_location_heading()` (Zeile 717-745) liefert den
  wiederholten Ortsnamen als einzige Überschrift über dem Ausblick-Block.
  `render_compare_html()` (Zeile 1088-1101, konkret `outlook_enabled`-Param
  Zeile 1100 und Aufruf Zeile 1197) bekommt einen neuen
  `outlook_metrics`-Parameter, durchgereicht bis zu
  `_render_location_outlook`.
- **File:** `src/output/renderers/comparison.py` — `render_comparison_text()`
  (Kopfzeile Zeile 172-183, Ausblick-Aufruf Zeile 236-238/271-272 über
  `render_outlook_plain(outlook_rows, show_acc=False)`) und
  `render_compare_email()` (Zeile 287-345, `outlook_enabled`-Parameter Zeile
  299/333/337) bekommen denselben neuen `outlook_metrics`-Parameter.
- **File:** `src/services/report_config_resolver.py` —
  `CompareRenderOptions` (Zeile 157-185) bekommt ein neues Feld
  `outlook_metrics: Optional[list[dict]]`; `resolve_compare_render_options()`
  (Zeile 204-267) löst `display_config.outlook_metrics` analog zu
  `hourly_metrics`/`active_metrics` auf und erzwingt — analog Zeile 250-259
  für den Stundenverlauf — `outlook_enabled=False`, wenn die Auswahl zwar
  gesetzt, aber leer ist (`[]`, keine gültige Größe übrig).
- **File (neu):** `src/output/renderers/compare_outlook_metric_ids.py` —
  Vorbild `compare_hourly_metric_ids.py`. Validiert/normalisiert die
  gespeicherte `outlook_metrics`-Liste (nur Neuformat-Paare
  `{metric_id, aggregation}`, kein Altformat) gegen `compare_metric_catalog`
  UND gegen `metric_catalog._METRICS` (muss `selectable=True` sein und
  `aggregation` muss ein Schlüssel von `summary_fields` sein), verwirft
  unbekannte/ungültige Paare mit `logger.warning` (Muster
  `compare_metric_ids.resolve_enabled_metrics`, Zeile 159-166), erhält die
  Auswahl-Reihenfolge (kein `set`).
- **File:** `src/services/scheduler_dispatch_service.py` (Zeile ~383) und
  `src/services/compare_preview_service.py` (Zeile ~185) — reichen
  `opts.outlook_enabled` bereits durch; bekommen dieselbe Zeile für
  `opts.outlook_metrics`.
- **File:** `internal/model/compare_preset.go` — `HourlyEnabled *bool`
  (Zeile 66) ist das Vorbild; `OutlookEnabled *bool` fehlt komplett und muss
  ergänzt werden (`json:"outlook_enabled,omitempty"`). `outlook_metrics`
  braucht **keinen** Go-Eingriff — es liegt in `display_config`, das
  `mergeConfigMap` generisch mergt.
- **File:** `internal/handler/compare_preset.go` — nil-Preserve-Block
  analog `HourlyEnabled` (Zeile 317-320) bzw. `DayWindowStartHour`
  (Zeile 321-329) fehlt für `OutlookEnabled` und muss ergänzt werden.
- **File:** `frontend/src/lib/components/shared/CompareHourlyLayoutControls.svelte`
  — vollständiges Vorbild (Toggle + Metrik-Liste + Reihenfolge via
  `WeatherV2Reihenfolge`) für eine neue, analoge
  `CompareOutlookLayoutControls.svelte`.
- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`
  (Einbindung analog Zeile 942) — bekommt die neue Ausblick-Sektion, aber
  **NUR** für `context="vergleich"` (E3: keine Auswahlfläche für Trip).
- **File:** `frontend/src/lib/components/compare/compareWizardState.svelte.ts`
  — `hourlyMetricKeys`/`hourlyEnabled` (Zeile 40/53) sind das Vorbild für
  neue Felder `outlookMetricKeys: string[] | null` und
  `outlookEnabled: boolean`.
- **File:** `frontend/src/lib/components/compare/compareEditorSave.ts` —
  `edits.hourlyMetricKeys`/`edits.hourlyEnabled` (Zeile 31/37,
  Verarbeitung Zeile 117-125/156) sind das Vorbild für
  `edits.outlookMetricKeys` → `displayConfig.outlook_metrics` (über
  `toStoredActiveMetrics()`, `compareMetricSelection.ts:122-133`, **dieselbe**
  bereits geladene Katalogantwort wie `active_metrics`) und
  `edits.outlookEnabled` → `outlook_enabled` (Top-Level, Round-Trip-Muster
  wie `hourlyEnabled`, Zeile 156).

> **Schicht-Hinweis:** Python-Core (`src/app/`, `src/services/`,
> `src/output/renderers/`) trägt den Rendering- und Auswahl-Kern; Go-API
> (`internal/model/`, `internal/handler/`) nur für das TOP-LEVEL Feld
> `outlook_enabled`; Frontend (`frontend/src/lib/components/shared/`,
> `frontend/src/lib/components/compare/`) für die Bedienfläche. Kein Anteil
> in `cmd/` oder anderen Go-Paketen.

## Estimated Scope

- **LoC:** ~350-450 (Backend-Rendering/Auswahl ~180-230: `outlook.py`
  ~60-90, `comparison_engine.py` ~15-25, `compare_html.py` ~30-40,
  `comparison.py` ~25-35, `report_config_resolver.py` +
  `compare_outlook_metric_ids.py` (neu) ~50-70, Dispatch/Preview-Wiring
  ~10-15; Go ~15-20; Frontend ~160-220: neue
  `CompareOutlookLayoutControls.svelte` ~100-130, `WeatherMetricsTab.svelte`-
  Einbindung ~10-15, `compareWizardState.svelte.ts` ~15-20,
  `compareEditorSave.ts` ~20-30, Typen/Wiring ~10-15)
- **Files:** ~13 Produktionsdateien geändert, 2 neu
  (`compare_outlook_metric_ids.py`, `CompareOutlookLayoutControls.svelte`);
  Tests kommen in Phase 4 (TDD RED) dazu
- **Effort:** high — vier Fundstellen-Schichten (Python-Rendering,
  Python-Auswahl/Resolver, Go-Persistenz, Frontend-Bedienfläche) müssen
  konsistent bleiben, der geteilte Baustein `outlook.py` trifft strukturell
  IMMER auch den Trip-Pfad (Byte-Identitäts-Wächter
  `test_shared_outlook_renderer.py`), Renderer-Commit-Gate #811 greift auf
  `compare_html.py`/`comparison.py`/`email/outlook.py`. Das
  Regel-Budget-LoC-Limit (250/Workflow) wird voraussichtlich überschritten
  und braucht `workflow.py set-field loc_limit_override` mit PO-Erlaubnis.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.metric_catalog.MetricDefinition` / `get_all_metrics()`-Filter | reused | Quelle der 24 wählbaren Größen samt `summary_fields`/`col_label`; keine neue Katalog-Kopie |
| `output.renderers.compare_metric_catalog.get_compare_metric_catalog()` / `key_for()` | reused | Bereits vollständige Abdeckung der 24 zentralen Größen; liefert dieselbe geladene Antwort (`GET /api/compare/metrics`), die `active_metrics` schon nutzt — **kein** Endpunkt-/Katalog-Eingriff |
| `output.renderers.compare_metric_ids.resolve_enabled_metrics` | Vorbild | Muster für Validierung + `logger.warning` bei unbekannten Paaren, reihenfolge-erhaltend |
| `output.renderers.compare_hourly_metric_ids.resolve_hourly_metrics` | Vorbild | Struktureller Zwilling für die neue `compare_outlook_metric_ids.py` |
| `output.renderers.email.compare_html.has_visible_hour_columns` | Vorbild | Muster „leere Auswahl schaltet die Sektion ab" (`resolve_compare_render_options`, Zeile 250-259) — hier auf `outlook_metrics == []` übertragen |
| `services.comparison_engine._filter_by_target_date_and_window` / `location_tz` | upstream, unverändert | Liefert bereits die Ortszeit-Auflösung (#1378); die Tagesgrenzen-Korrektur (Implementation Details Punkt 1) baut darauf auf, ändert diese Funktion selbst nicht |
| `frontend/.../compareMetricSelection.ts::toStoredActiveMetrics/compareMetricKeyFromStored` | reused | Dieselbe Lese-/Schreibübersetzung Auswahl-Schlüssel ↔ `{metric_id, aggregation}` wie `active_metrics` (#1373 S2 Scheibe B) — keine zweite Übersetzungstabelle im Frontend |
| `frontend/.../WeatherV2Reihenfolge.svelte` (ADR-0024) | reused | Geteilter Sortier-Baustein für die Ausblick-Reihenfolge, analog Stundenverlauf |
| `renderer_mail_gate.py` (#811) | Gate | Blockiert den Commit auf `outlook.py`/`compare_html.py`/`comparison.py`, bis `test_issue_811_mode_matrix.py` grün ist UND ein frischer `briefing_mail_validator.py`-Lauf vorliegt |
| `internal/handler/config_merge.go::mergeConfigMap` | upstream, unverändert | Merged `display_config.outlook_metrics` generisch — kein Go-Struct-Feld dafür nötig |

## Implementation Details

1. **Ausblick beginnt nach dem letzten von der Stundentabelle berührten
   Kalendertag (V1/E1).** In `ComparisonEngine.run()` wird der
   `_outlook_days`-Filter von `d >= target_date` auf einen expliziten
   `last_detail_day` umgestellt: bei normalem Fenster
   (`start_hour <= end_hour`) ist das weiterhin `target_date`; bei
   Mitternachts-Fenster (`start_hour > end_hour`, ADR-0035/#1361 S1b) ist es
   `target_date + 1 Tag`, weil die Stundentabelle dann auch Stunden dieses
   Folgetags zeigt (Zeile 77-82). Der Filter wird zu
   `d > last_detail_day`. `COMPARE_FORECAST_HOURS = 96` (4 Tage) muss den
   dadurch möglicherweise um einen Tag verschobenen Ausblick-Bereich
   weiterhin abdecken — bei Mitternachts-Fenster mit spätem `target_date`
   knapp, im Zweifel bei der Implementierung nachrechnen (s. Risiken).

2. **Auswahl-Format `display_config.outlook_metrics`, Neuformat, EIN
   Vokabular (E4).** Gespeichert wird ausschließlich
   `[{"metric_id": ..., "aggregation": ...}]` — kein Altformat, kein neues
   viertes Vokabular. Aufgelöst über `compare_metric_catalog.key_for()`
   (Existenz-/Gültigkeitsprüfung) und `metric_catalog._METRICS`
   (`summary_fields[aggregation]` → Feldname auf `SegmentWeatherSummary`).
   **Korrektur PO-Entscheidung 2026-07-27 (geht dieser Spec-Fassung vor):**
   Der Spaltenkopf kommt aus `compare_metric_catalog.label`, NICHT aus
   `metric_catalog.col_label`. Begründung: `col_label` liefert für
   `temperature` min/max/avg denselben Text „Temp" — zwei gewählte
   Temperatur-Auswertungen ergäben zwei identisch beschriftete Spalten;
   außerdem sind die Kürzel englisch („Rain"/„Thdr"/„PType") und erfüllen
   AC-1 („lesbare Spaltenköpfe statt der kryptischen Kürzel") damit nur
   halb. `compare_metric_catalog.label` ist deutsch und eindeutig
   („Temperatur max", „Niederschlag", „Böen") und stammt aus derselben
   Katalogantwort, die die Auswahl ohnehin auflöst. Reihenfolge = Auswahlreihenfolge, kein
   eigenes Bedienelement über `WeatherV2Reihenfolge` hinaus (Muster
   `_visible_hour_metrics`).

3. **`build_outlook_row(..., metrics=None)` bleibt byte-identisch (E3).**
   Der neue `metrics`-Parameter ist rein additiv: `None` (Trip-Aufruf,
   unverändert) liefert exakt das bisherige feste Dict. Ist `metrics`
   gesetzt (Compare mit Auswahl), liest die Funktion die Zellenwerte
   zusätzlich datengetrieben aus `summary` über `summary_fields[aggregation]`
   und liefert sie in Auswahlreihenfolge mit dem zugehörigen `col_label` als
   Kopf. `render_outlook_table`/`render_outlook_plain` rendern bei gesetzten
   `metrics` diese dynamischen Spalten statt der festen Sieben; `show_acc`
   bleibt ein davon unabhängiger Schalter (Confidence ist nicht Teil der
   wählbaren 24 Größen, ADR-0005/#710).

4. **Überschrift HTML: „3-Tages-Ausblick" statt Ortsname, Zeitzonen-Kürzel
   bleibt erhalten.** `_render_location_outlook()` schreibt über dem
   Ausblick-Block eine eigene Überschrift „3-Tages-Ausblick" mit demselben
   Zeitzonen-Kürzel-Mechanismus wie `_location_heading()` (angehängt an
   `loc.outlook_hourly_data[0].ts`, #1378) — der Ortsname selbst steht
   bereits am unmittelbar darüber liegenden Stundenblock desselben Ortes
   (Issue #1323: Ausblick folgt direkt auf den Stundenblock desselben
   Ortes), muss hier also nicht wiederholt werden.

5. **Überschrift Klartext: parametrisierbar, Compare bekommt „3-Tages-
   Ausblick".** `render_outlook_plain()` bekommt einen optionalen
   `heading`-Parameter, Default `"Nächste Etappen"` (Trip-Aufruf ruft ohne
   Parameter — byte-identisch). Compare ruft mit
   `heading="3-Tages-Ausblick"`.

6. **Leeres Namensfeld im Klartext entfällt strukturell.** Die feste
   26-Zeichen-Namensspalte (`f"{name:<26}"`, Zeile 220) gehört zum
   FESTEN Sieben-Spalten-Format (Trip-Etappenname).
   **Korrektur PO-Entscheidung 2026-07-27 (geht dieser Spec-Fassung vor):**
   Die Beschriftungsfehler werden für ALLE Ortsvergleiche behoben, auch ohne
   gesetzte Auswahl — Überschrift „3-Tages-Ausblick" und weggefallenes
   Namensfeld gelten IMMER im Compare-Pfad (`render_outlook_plain(...,
   heading=..., show_name=False)`), nur die Spaltenmenge hängt an
   `outlook_metrics`. Andernfalls bliebe der #1368-Fehler für Bestandsnutzer
   ohne Auswahl bestehen. Ist `metrics` gesetzt
   (Compare), rendert die Zeile die dynamischen Spalten OHNE Namensfeld —
   der Ortsbezug steht bereits in der umschließenden Zeile
   (`comparison.py:255-257`, `{Ortsname} ({Zeitzone})`). Kein Versuch, das
   Namensfeld nachträglich mit dem Ortsnamen zu befüllen.

7. **`outlook_enabled` bekommt eine Go-Struct-Zeile + Bedienfläche.** Neues
   `OutlookEnabled *bool` Feld (`compare_preset.go`) mit nil-Preserve-Block
   im Handler (Muster `HourlyEnabled`/`DayWindowStartHour`); Frontend
   bekommt einen Toggle in `CompareOutlookLayoutControls.svelte`.
   `outlook_metrics` selbst braucht keinen Go-Eingriff (`display_config`).

8. **Leerauswahl lässt den Ausblick-Block ganz entfallen.**
   `resolve_compare_render_options()` erzwingt `outlook_enabled=False`,
   wenn `outlook_metrics` als leere Liste `[]` gespeichert ist (analog
   `has_visible_hour_columns`-Kopplung für den Stundenverlauf, Zeile
   250-259) — eine Tagestabelle mit nur der Wochentag-Spalte hat keinen
   Nutzwert. Ein fehlendes Feld (`None`) bleibt unverändert: heutige sieben
   Spalten.

## Expected Behavior

- **Input:** Ein Compare-Preset mit `outlook_enabled` (Top-Level, Default
  `True`) und optional `display_config.outlook_metrics` (Neuformat-Liste),
  sowie ein Tagesfenster (`day_window_start_hour`/`-_end_hour`), das normal
  oder über Mitternacht reichen kann (ADR-0035).
- **Output:** Eine zugestellte Vergleichs-Mail (HTML + Klartext), deren
  3-Tages-Ausblick je Ort NUR die gewählten Größen als Spalten zeigt (in
  Auswahlreihenfolge, mit lesbaren Spaltenköpfen aus dem Katalog statt der
  bisherigen Kürzel), eine eigene, im Text erkennbare Überschrift
  „3-Tages-Ausblick" trägt (HTML mit Zeitzonen-Kürzel, Klartext ohne), NIE
  den im Detail gezeigten Tag als erste Zeile enthält, und bei einer
  bewusst geleerten Auswahl vollständig entfällt. Fehlt die Auswahl, zeigt
  die Mail unverändert die heutigen sieben Spalten. Die Trip-Mail ändert
  sich in keinem Byte.
- **Side effects:** Unbekannte/ungültige Einträge in `outlook_metrics`
  werden verworfen und über `logger.warning` protokolliert, nicht
  stillschweigend ignoriert.

## Was sich NICHT ändern darf

- **Trip-Mail bleibt byte-identisch.** `trip_report_scheduler.py`,
  `email/html.py`, `email/plain.py` rufen `build_outlook_row`/
  `render_outlook_table`/`render_outlook_plain` weiterhin ohne `metrics`-
  bzw. `heading`-Parameter auf; die vorhandenen Byte-Identitäts-Tests in
  `tests/tdd/test_shared_outlook_renderer.py` dienen als Wächter.
- **Übersichtstabelle bleibt unverändert.** `_render_overview_table`,
  `enabled_metrics`-Auflösung (#1359/#1366) werden nicht angefasst.
- **Stundenverlauf-Auswahl UND deren Reihenfolge bleiben unverändert.**
  `hourly_metrics`, `_visible_hour_metrics`, `hourly_enabled`-Kopplung
  (#1335/#1359/#1366) sind bereits frisch geliefert und nicht Teil dieses
  Slices.
- **Zeitbasis/Zeitzonen-Anschriften aus #1378 bleiben erhalten.**
  `location_tz`, `_location_heading`-Zeitzonen-Kürzel, „Erstellt"-Kopfzeile
  in Ortszeit des erstgenannten Ortes — alles unverändert; die neue
  Ausblick-Überschrift NUTZT denselben Mechanismus, ersetzt ihn nicht.
- **Orts-Reihenfolge bleibt unverändert.** `order_locations_by_ids`,
  `location_render_order` (#1359) werden nicht angefasst.
- **Vorhandenes `outlook_enabled`-Verhalten (Default `True`, sofort
  sichtbar) bleibt erhalten** — nur die fehlende Bedienfläche/Go-Persistenz
  wird ergänzt, kein Verhaltenswechsel für Bestandspresets ohne gesetztes
  Feld.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleichs-Preset mit gesetzter Auswahl
  `outlook_metrics` (z. B. nur „Temperatur max" und „Niederschlag"), When
  die Vergleichs-Mail erzeugt wird, Then zeigt der HTML-Ausblick-Block jedes
  Ortes ausschließlich diese gewählten Spalten in Auswahlreihenfolge, mit
  lesbaren Spaltenköpfen aus dem Katalog — nicht die bisherigen sieben
  festen Spalten und nicht die kryptischen Kürzel N/D/R/PR/Wind/Böen/Gew.
  - Test: Zugestellte Staging-Mail per IMAP abrufen, HTML-Ausblick-Tabelle
    auf genau die gewählten Spalten samt Werten und Köpfe prüfen — kein
    Dateiinhalt-Check.

- **AC-2:** Given dasselbe Preset und dieselbe zugestellte Mail, When der
  Klartext-Teil (nicht der HTML-Teil) betrachtet wird, Then zeigt auch der
  Klartext-Ausblick ausschließlich die gewählten Größen, identisch zur
  Auswahl im HTML-Teil derselben Mail — der Pflicht-Validator liest nur
  HTML und ist hier blind (Scheibe-B-Erfahrung, #1366).
  - Test: Eigenständige Prüfung des Klartext-Teils derselben zugestellten
    Mail, Zeile für Zeile gegen die HTML-Auswahl abgeglichen.

- **AC-3:** Given eine zugestellte Vergleichs-Mail mit aktivem 3-Tages-
  Ausblick, When der HTML-Teil betrachtet wird, Then trägt der Ausblick-
  Block jedes Ortes eine eigene, für den Empfänger erkennbare Überschrift
  „3-Tages-Ausblick" (mit demselben Zeitzonen-Kürzel wie am darüberliegenden
  Stundenblock) — nicht nur den wiederholten Ortsnamen ohne Bezeichnung des
  Blocks.
  - Test: HTML-Ausblick-Block auf das Vorkommen der Bezeichnung
    „3-Tages-Ausblick" direkt über der Tabelle geprüft (kein bloßer
    String-Sucher irgendwo im Dokument).

- **AC-4:** Given dieselbe zugestellte Mail, When der Klartext-Teil
  betrachtet wird, Then trägt der Ausblick-Block ebenfalls die Bezeichnung
  „3-Tages-Ausblick" statt der bisherigen Trip-Formulierung „Nächste
  Etappen" — im Ortsvergleich gibt es keine Etappen.
  - Test: Klartext-Ausblick-Block auf die Bezeichnung „3-Tages-Ausblick"
    geprüft.

- **AC-5:** Given dieselbe zugestellte Mail mit Klartext-Ausblick, When eine
  Ausblick-Zeile betrachtet wird, Then enthält sie kein leeres, 26 Zeichen
  breites Namensfeld (Trip-Etappenname-Reservierung) — die Zeile beginnt
  nach dem Wochentag direkt mit den gewählten Werten.
  - Test: Klartext-Ausblick-Zeile auf Abwesenheit der langen Leerraum-Lücke
    zwischen Wochentag und erstem Wert geprüft (Gegenprobe zum Staging-Fund
    im Kontext-Dokument).

- **AC-6:** Given ein Vergleichspreset mit normalem Tagesfenster (z. B.
  9-16 Uhr, `start_hour <= end_hour`) und Detailtag `target_date`, When die
  Vergleichs-Mail erzeugt wird, Then ist `target_date` in KEINER Zeile des
  3-Tages-Ausblicks als Wochentag vertreten — die erste Ausblick-Zeile
  gehört dem auf `target_date` folgenden Kalendertag.
  - Test: Wochentag-Label der ersten Ausblick-Zeile gegen den Wochentag von
    `target_date` verglichen — muss verschieden sein, für ein Preset mit
    normalem Fenster.

- **AC-7:** Given ein Vergleichspreset mit Mitternachts-Tagesfenster (z. B.
  20-04 Uhr, `start_hour > end_hour`, ADR-0035), When die Vergleichs-Mail
  erzeugt wird, Then ist WEDER `target_date` NOCH `target_date + 1 Tag` (der
  von der Stundentabelle ebenfalls berührte Folgetag) in einer Zeile des
  3-Tages-Ausblicks vertreten — die erste Ausblick-Zeile beginnt frühestens
  bei `target_date + 2 Tagen`.
  - Test: Wochentag-Labels aller Ausblick-Zeilen gegen beide von der
    Stundentabelle berührten Kalendertage geprüft — kein Treffer, für ein
    Preset mit Mitternachts-Fenster.

- **AC-8:** Given ein Ortsvergleichs-Preset mit `display_config
  .outlook_metrics = []` (bewusst leere Auswahl), When die Vergleichs-Mail
  erzeugt wird, Then entfällt der 3-Tages-Ausblick-Block für alle Orte
  vollständig (weder Überschrift noch Tabelle) — nicht nur eine leere
  Tabelle mit Wochentag-Spalte.
  - Test: Zugestellte Mail (HTML + Klartext) auf vollständige Abwesenheit
    jedes Ausblick-Bezugs geprüft.

- **AC-9:** Given ein Ortsvergleichs-Preset OHNE gesetztes
  `display_config.outlook_metrics` (Feld fehlt, Altbestand), When die
  Vergleichs-Mail erzeugt wird, Then zeigt der 3-Tages-Ausblick unverändert
  die bisherigen sieben Größen (Temp min/max, Regen, Regen-Wahrscheinlichkeit,
  Wind, Böen, Gewitter) — kein stiller Verhaltenswechsel für Bestandsnutzer.
  **Präzisierung PO-Entscheidung 2026-07-27:** AC-9 meint ausschließlich die
  SPALTENAUSWAHL. Überschrift („3-Tages-Ausblick" statt Ortsname bzw.
  „Nächste Etappen") und das entfallene leere Namensfeld gelten auch hier —
  ein Darstellungsfehler wird nicht als Bestandsverhalten konserviert.
  - Test: Preset ohne `outlook_metrics`-Feld, Ausblick-Spalten gegen die
    bisherigen sieben Größen geprüft (Regressionsschutz für Altbestand).

- **AC-10:** Given eine gespeicherte `outlook_metrics`-Auswahl mit einem
  Eintrag, der auf kein bekanntes `{metric_id, aggregation}`-Paar im
  Katalog passt, When die Vergleichs-Mail erzeugt wird, Then wird dieser
  Eintrag verworfen und über eine Log-Meldung sichtbar gemacht — die
  restliche, gültige Auswahl bleibt unverändert wirksam, kein Absturz.
  - Test: Preset mit einem unbekannten Auswahl-Eintrag, Ausblick zeigt die
    übrigen gültigen Spalten, Log-Ausgabe enthält eine Warnung zum
    unbekannten Eintrag.

- **AC-11:** Given dasselbe Feature ist ausgeliefert, When ein Trip-Briefing
  (nicht der Ortsvergleich) mit aktivem 3-Tages-Ausblick versendet wird,
  Then ist die erzeugte Trip-Mail (HTML + Klartext) byte-identisch zu einer
  vor diesem Fix erzeugten Trip-Mail mit denselben Eingabedaten — inklusive
  Sieben-Spalten-Tabelle, ACC-Spalte und Formulierung „Nächste Etappen".
  - Test: `tests/tdd/test_shared_outlook_renderer.py`-Byte-Identitäts-Tests
    für `show_acc=True`/Trip-Aufruf bleiben grün ohne Anpassung ihrer
    erwarteten Werte.

- **AC-12:** Given ein Nutzer öffnet den Ortsvergleich-Editor (Reiter
  Wetter-Metriken) und wählt eine Teilmenge von Größen für den 3-Tages-
  Ausblick aus, When die Auswahl gespeichert und der Editor neu geladen
  wird, Then zeigt die Bedienfläche exakt dieselbe Auswahl in derselben
  Reihenfolge wie vor dem Neuladen.
  - Test: Editor-Roundtrip (speichern, neu laden) auf identische
    Ausblick-Metrik-Auswahl und -Reihenfolge geprüft — reales Klickverhalten,
    kein direkter Datenbank-Check.

- **AC-13:** Given ein Nutzer schaltet den 3-Tages-Ausblick über den neuen
  Toggle aus, When die Änderung über die Go-API gespeichert und das Preset
  danach erneut geladen wird, Then bleibt der Ausblick weiterhin
  ausgeschaltet — das Feld geht beim Go-seitigen Speichern nicht verloren
  (heutiger latenter Bug: `outlook_enabled` fehlt im Go-Struct).
  - Test: Go-Handler-Test (Preset mit `outlook_enabled=false` PUTten, GET
    liefert weiterhin `false`) plus Frontend-Roundtrip über den Toggle.

## Risiken

1. **Vierter Ausblick-Tag bei Mitternachts-Fenster.** Verschiebt sich die
   Ausblick-Startgrenze durch die V1-Korrektur auf `target_date + 2`, muss
   `COMPARE_FORECAST_HOURS = 96` (4 Tage ab JETZT, nicht ab `target_date`)
   weiterhin genug Rohdaten liefern — bei einem `target_date` mehrere Tage
   in der Zukunft und Mitternachts-Fenster ist das bei der Implementierung
   explizit nachzurechnen, nicht nur anzunehmen (dasselbe Risiko wie in
   #1378 dokumentiert, hier auf den Ausblick statt die Stundenauswahl
   bezogen).
2. **`outlook.py` ist der gemeinsame Trip/Compare-Baustein — jede Änderung
   trifft strukturell auch den Trip-Pfad.** Nur additive, per Default-
   Parameter abgeschirmte Änderungen sind zulässig; Byte-Identitäts-Tests in
   `test_shared_outlook_renderer.py` sind der Wächter, nicht eine manuelle
   Prüfung.
3. **`test_shared_outlook_renderer.py::test_build_outlook_row_pure_function`
   ist vorbestehend rot** (Doppelimport `from src.output...` vs
   `output...`, #1196) — nicht mit einer durch diesen Fix verursachten
   Regression verwechseln; dieser eine Test bleibt außerhalb der
   „100% grün"-Kern-Regel, alle ANDEREN Tests in derselben Datei nicht.
4. **Klartext bleibt Prüf-blind.** `email_spec_validator.py` (Pflicht-
   Validator) liest nur den HTML-Teil. AC-2/AC-4/AC-5 verlangen deshalb
   eine eigenständige Klartext-Prüfung im Live-Nachweis, sonst wiederholt
   sich exakt die Lücke aus #1366.
5. **Renderer-Commit-Gate #811.** `outlook.py` fällt zwar nicht unter die
   im Gate explizit aufgeführten Pfade, aber `compare_html.py` und
   `comparison.py` (beide geändert) tun es — Commit ist erst möglich, wenn
   `test_issue_811_mode_matrix.py` grün ist UND ein frischer
   `briefing_mail_validator.py`-Lauf vorliegt.
6. **Formatierung heterogener Größen.** Die 24 wählbaren Größen haben sehr
   unterschiedliche Formate (Enum `precip_type`, Ordinal `thunder`, runde
   Prozent-/Meter-/hPa-Werte). Die bisherige feste Sieben-Spalten-Tabelle
   hatte für jede Spalte eine handgeschriebene Formatierung; eine
   datengetriebene Spaltenanzeige muss eine generische, aber lesbare
   Formatierung für ALLE 24 Größen liefern (Dezimalstellen/Einheit aus
   `MetricDefinition`), nicht nur für die bisherigen sieben — Adversary-
   Dialog sollte mindestens eine untypische Größe (z. B. `precip_type_dominant`,
   Enum) stichprobenartig prüfen.
7. **LoC-Budget.** Die geschätzten ~350-450 LoC überschreiten das
   Standard-Regel-Budget (250/Workflow); `loc_limit_override` braucht
   PO-Erlaubnis vor dem Setzen (kein eigenmächtiges Anheben).
8. **open-meteo-Kontingent (#1329).** Der Live-Nachweis auf Staging darf
   nur EINEN Versand auslösen, danach ausschließlich per IMAP auswerten.

## Testplan

### Kern-Schicht (deterministisch, echte aufgezeichnete Fixtures, kein Mock-Theater)

- Neuer/erweiterter Test für `build_outlook_row(..., metrics=None)`:
  liefert weiterhin exakt das bisherige feste Dict (Byte-/Struktur-
  Identität, Regressionsschutz zu `test_shared_outlook_renderer.py`).
- Neuer Test für `build_outlook_row(..., metrics=[...])`: liefert die
  Zellenwerte der gewählten Größen aus `SegmentWeatherSummary` über
  `summary_fields`, in Auswahlreihenfolge, mit `col_label` als Kopf.
- Neuer Test für `render_outlook_table`/`render_outlook_plain` mit
  gesetzten `metrics`: HTML- bzw. Klartext-Ausgabe zeigt genau die
  gewählten Spalten, keine der abgewählten sieben Alt-Spalten.
- Neuer Test für die Tagesgrenzen-Korrektur in `ComparisonEngine.run()`:
  normales Fenster → `target_date` fehlt in den Ausblick-Tagen (AC-6);
  Mitternachts-Fenster → `target_date` UND `target_date + 1` fehlen
  (AC-7). Erweiterung von `tests/tdd/test_comparison_engine_midnight_window.py`
  oder neue, nach Verhalten benannte Datei (z. B.
  `test_compare_outlook_day_boundary.py` — NICHT `test_issue_1361_*.py`,
  Gate `test_naming_gate.py`).
- Neuer Test für `compare_outlook_metric_ids.py` (Resolver): bekanntes
  Paar → aufgelöst; unbekanntes Paar → verworfen + `logger.warning`;
  leere Liste → `[]` (nicht `None`); fehlendes Feld → `None`.
- Neuer Test für `resolve_compare_render_options()`: `outlook_metrics=[]`
  erzwingt `outlook_enabled=False` im Ergebnis, unabhängig vom
  gespeicherten `outlook_enabled`-Wert.
- Neuer Test für das leere Klartext-Namensfeld (AC-5): Ausblick-Zeile mit
  gesetzten `metrics` enthält keine 26-Zeichen-Lücke.
- Alle neuen Kern-Tests (außer dem vorbestehend roten
  `test_build_outlook_row_pure_function`): 100% grün vor Commit.

### Frontend-Tests (`node:test` mit `test-lib-loader.mjs`, kein vitest, ADR-0020)

- Neuer Test für `CompareOutlookLayoutControls.svelte`-Logik (reine
  State-Funktionen, analog `compareEditorHourlyMetrics.test.ts`): Toggle
  und Metrik-Auswahl mutieren den `wiz`-State korrekt, Reihenfolge bleibt
  positionsgetreu.
- Neuer Test für `compareEditorSave.ts`: `edits.outlookMetricKeys` →
  `displayConfig.outlook_metrics` im Neuformat (`toStoredActiveMetrics`),
  `edits.outlookEnabled` → Top-Level `outlook_enabled`, beide mit
  Round-Trip-Verhalten bei `undefined` (unangetastet → `...original`).

### Go-Test

- Neuer Test in `internal/handler/compare_preset_test.go` (oder
  Äquivalent): PUT mit `outlook_enabled=false`, GET liefert weiterhin
  `false` — Regressionsschutz für den nil-Preserve-Block.

### Live-E2E (Staging, ein Versand, Marker `X-GZ-Mail-Type: compare`)

- Ein Versand eines Vergleichspresets mit expliziter `outlook_metrics`-
  Auswahl (Teilmenge, z. B. zwei Größen) über den Einzelversand-Endpoint.
- Zustellung per IMAP abrufen; **beide** Mail-Teile (HTML und Klartext)
  eigenständig auf die gewählten Spalten, die Überschrift „3-Tages-
  Ausblick" und die Abwesenheit des Detailtags geprüft (AC-1/-2/-3/-4/-6).
- Pflicht-Validator `email_spec_validator.py` muss Exit 0 liefern, bevor
  „E2E bestanden" gesagt werden darf — deckt laut
  `docs/reference/mail_validators.md` nur den HTML-Teil ab, der Klartext-
  Teil wird zusätzlich manuell/skriptgestützt geprüft.
- Zweiter, kurzer Nachweis mit `outlook_metrics=[]` (AC-8) und einem
  Preset ohne gesetztes Feld (AC-9) — nach Möglichkeit aus denselben
  bereits abgerufenen IMAP-Mails, ohne zusätzlichen Versand, falls die
  Kern-Tests diese Fälle bereits vollständig abdecken (Kontingent-Schonung,
  #1329).

## Out of Scope

- **Trip-Auswahlfläche für den Ausblick.** Der Trip bekommt keine
  Bedienfläche — das Epic betrifft ausschließlich den Ortsvergleich (E3).
- **Migration des Stundenverlauf-Altformats auf das Neuformat.**
  `display_config.hourly_metrics` bleibt im bestehenden Altformat-Vokabular
  (String-Keys); dieses Modul führt kein drittes Vokabular für den
  Ausblick ein, migriert aber auch nicht rückwirkend den Stundenverlauf.
- **Englischer Wochentag in der Klartext-Kopfzeile**
  (`comparison.py:175`, `strftime('%A')` ohne deutsche Locale) — bereits
  als Nebenbefund erfasst, gehört in Sammel-Issue #1199.
- **Spalten-Reihenfolge per eigenem Bedienelement.** Es gibt kein
  zusätzliches Sortier-UI über den geteilten `WeatherV2Reihenfolge`-
  Baustein hinaus.

## Known Limitations

- Die konkrete generische Zellenformatierung für Größen außerhalb der
  bisherigen sieben (z. B. Enum-/Ordinal-Werte) ist im Detail nicht
  vorgeschrieben — sie muss nur lesbar und dem jeweiligen `unit`/`decimals`
  der zentralen `MetricDefinition` angemessen sein (Risiko 6).
- Bei einem `target_date`, das so weit in der Zukunft liegt, dass
  `COMPARE_FORECAST_HOURS` den korrigierten Ausblick-Bereich nicht mehr
  abdeckt, bleibt der Ausblick-Block für die betroffenen Tage leer
  (fail-soft, kein Crash) — eine Erweiterung des Vorhersagehorizonts ist
  nicht Teil dieses Fixes.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** neu — Vorschlag ADR-0037 (nächste freie Nummer nach
  ADR-0036, `docs/adr/README.md` zu ergänzen).
- **Rationale:** Der 3-Tages-Ausblick wechselt von einer festen,
  handgeschriebenen Sieben-Spalten-Liste auf datengetriebene Spalten aus
  dem zentralen Metrik-Katalog (`metric_catalog.py`) — bei gleichzeitig
  garantierter Byte-Parität der Trip-Mail. Das ist dieselbe Zielrichtung
  wie die bereits für Übersichtstabelle (#1373) und Stundenverlauf
  getroffene Entscheidung „eine Größe, mehrere Auswertungen" (Epic #1372),
  jetzt auf die dritte und letzte Ausgabefläche des Ortsvergleichs
  angewendet — schwer umkehrbar, weil danach ALLE drei Compare-
  Ausgabeflächen (Übersicht, Stundenverlauf, Ausblick) auf denselben
  Katalog aufsetzen und ein Rückbau auf feste Spalten wieder drei
  divergierende Vokabulare einführen würde. Verworfene Alternative: ein
  Compare-eigener Ausblick-Renderer mit voller Auswahl (schneller zu
  bauen, aber Verstoß gegen die Trip/Compare-Teilungs-Invariante,
  Anti-Pattern-Referenz #1170) — verworfen zugunsten des additiv
  erweiterten geteilten Bausteins.

## Changelog

- 2026-07-27: Initial spec created
- 2026-07-27 (GREEN-Phase): PO-Entscheidungen eingearbeitet — Spaltenkopf aus
  `compare_metric_catalog.label` statt `col_label` (Punkt 2); Überschrift und
  Namensfeld-Wegfall gelten immer im Compare-Pfad, nicht nur bei gesetzter
  Auswahl (Punkt 6, Präzisierung AC-9).
