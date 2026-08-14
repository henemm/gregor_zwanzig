---
entity_id: feat_1720_s1_trip_ausblick_metriken
type: feature
created: 2026-08-14
updated: 2026-08-14
status: approved
version: "1.0"
workflow: feat-1720-vorschau-metriken
tags: [trip, outlook, ausblick, mail, metrik-katalog, feature, epic-1372, issue-1720]
---

# 3-Tages-Vorschau des Trip-Briefings: wählbare Spalten für HTML- und Klartext-Mail (Issue #1720, Scheibe 1)

## Approval

- [x] Approved — PO Henning, 2026-08-14 (Freigabe auf die 16 ACs auf Deutsch,
      nach vier Vorab-Entscheidungen: alle vier Ausgabeorte in zwei Scheiben ·
      keine Kanal-Ebene · Legenden-Korrektur in dieser Lieferung ·
      Vorschau-Auswahl an die Grundauswahl gebunden)

## Purpose

Die 3-Tages-Vorschau der Trip-Mail zeigt heute unveränderlich dieselben sieben
festen Größen (Temp min/max, Regen, Regen-Wahrscheinlichkeit, Wind, Böen,
Gewitter) plus die ACC-Spalte — ohne Auswahlmöglichkeit, obwohl der
Ortsvergleich seit ADR-0037 genau dieselbe Auswahl längst besitzt. Dieses
Modul überträgt die vorhandene, geteilte Rendering-Infrastruktur auf den Trip:
ein neuer Abschnitt „3-Tages-Vorschau" auf `/trips/<id>?tab=weather` lässt den
Nutzer die Spalten aus dem zentralen Metrik-Katalog frei wählen — dieselbe
Bedienfläche wie beim Ortsvergleich, parametrisiert statt kopiert. Die Auswahl
ist **global** (keine Kanal-Ebene) und wirkt in dieser Scheibe in der
**HTML-** und **Klartext-Trip-Mail**; Kompakt-Mail und Telegram folgen in
Scheibe 2. Zusätzlich wird die HTML-Legende `N Nacht-Tief` richtiggestellt —
sie beschreibt bislang eine Größe, die die Spalte gar nicht liefert (siehe
Implementation Details Punkt 5).

## Source

- **File:** `src/app/models.py:774-807` — `UnifiedWeatherDisplayConfig`.
  Neues Feld `outlook_metrics: Optional[list[dict]] = None`, eingefügt nach
  `metric_alert_levels` (Zeile 806), vor `updated_at` (Zeile 807). Neuformat
  `[{"metric_id": ..., "aggregation": ...}]` — dasselbe Vokabular wie
  `display_config.active_metrics` seit #1373, kein viertes.
- **File:** `src/app/loader.py:912-927` — Lesepfad. Ergänzt um
  `outlook_metrics=data.get("outlook_metrics"),` im Konstruktor-Aufruf von
  `UnifiedWeatherDisplayConfig(...)`. Ohne diese Zeile bleibt das Feld für
  Python unsichtbar, egal was gespeichert ist.
- **File:** `src/app/loader.py:1524-1544` — Schreibpfad
  (`data["display_config"] = {...}`). Ergänzt um einen bedingten Eintrag nach
  dem Muster `alert_preset`/`metric_alert_levels` (Zeile 1538-1543):
  `**({"outlook_metrics": dc.outlook_metrics} if dc.outlook_metrics is not None else {})`.
  Bedingt, nicht unbedingt — sonst ginge die Drei-Werte-Semantik
  (fehlt/`[]`/gefüllt) beim Speichern verloren und jeder Trip bekäme nach dem
  ersten Speichern ein explizites `outlook_metrics` im JSON, auch ohne dass
  der Nutzer die neue Fläche je berührt hat.
- **File:** `src/output/renderers/compare_outlook_metric_ids.py` (bestehend,
  **keine Änderung**) — `resolve_outlook_metrics()` (Zeile 45-75),
  `outlook_columns()` (Zeile 78-114), `format_outlook_value()`
  (Zeile 117-149). Bereits generisch trotz `compare_` im Modulnamen; die
  Auflösung läuft über `compare_metric_catalog.key_for()` und
  `metric_catalog.summary_field_for()`, keine Compare-spezifische Logik.
- **File:** `src/services/trip_report_scheduler.py:2145,2161` —
  `_build_stage_trend()`. `dc = getattr(trip, "display_config", None)` liegt
  bereits vor (Zeile 2145); neu: `resolve_outlook_metrics(dc.outlook_metrics)`
  auflösen und als `metrics=` an `build_outlook_row(...)` (Zeile 2161)
  durchreichen. Füllt `row["cells"]` (Zeilenwerte der gewählten Größen,
  `outlook.py:551-574`).
- **File:** `src/output/renderers/email/html.py:1349-1400` — der
  `if multi_day_trend:`-Block, der `outlook_table`, `outlook_legend` und
  `trend_html` baut. Neu: `metrics=` an `render_outlook_table(...)`
  (Zeile 1357) übergeben; die Bedingung, unter der der Block überhaupt gebaut
  wird, erweitert sich um „Auswahl ist nicht bewusst leer" (Implementation
  Details Punkt 2); die Legende (Zeile 1360-1366) wird an dieselbe Bedingung
  gekoppelt (Implementation Details Punkt 4).
- **File:** `src/output/renderers/email/plain.py:309,334-338` —
  `outlook_active = show_outlook and bool(multi_day_trend)` (Zeile 309) und
  der `if outlook_active:`-Block (Zeile 334). Neu: dieselbe Erweiterung der
  Bedingung, `metrics=` an `render_outlook_plain(...)` (Zeile 338).
- **File:** `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte`
  — von `CompareWizardState`-Bindung (Zeile 31,43,49,57,62,92,105) auf flache
  Props umgestellt (`metricKeys: string[] | null`, `catalog`, `onToggleMetric`,
  `onReorder`, `onCommit?`, optional `enabled`/`onEnabledChange` — nur die
  Compare-Einbindung übergibt Letztere, s. Implementation Details Punkt 6).
  `SectionH title="..."` wird parametrisierbar (Compare weiterhin
  „3-Tages-Ausblick", Trip „3-Tages-Vorschau").
- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:56`
  — `'ausblick'` verlässt `COMPARE_ONLY_SECTIONS` (die dann nur noch
  `['stundenverlauf']` enthält) und wird für **beide** Kontexte angehängt
  (Implementation Details Punkt 7).
- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` —
  neue `$state`-Variable `outlookMetricKeys: string[] | null`
  (Vorbild: `channelBuckets`, Zeile 254-256); Aufnahme in `initFromTrip()`
  (ab Zeile 371), `snapshot()`/`isDirty` (Zeile 343-363),
  `handleDiscard()` (Zeile 787-813), `buildWeatherPayload()`
  (Zeile 835-858); Erweiterung des Ladepfad-Guards für `compareCatalog`
  (Zeile 519,532) um `context === 'route'`; neuer Markup-Zweig neben
  Zeile 1348-1351 für `context === 'route'` (kein `wiz`, da Trip-Kontext).
- **Wiederverwendet, unverändert:** `materializeOutlookMetricKeys()`,
  `toggleOutlookMetricKeyFromState()`, `DEFAULT_OUTLOOK_METRIC_KEYS`
  (`weather-metrics-tab/compareMetricOrder.ts:31-54`) sowie
  `toStoredActiveMetrics()`/`normalizeStoredActiveMetrics()`/
  `compareMetricKeyFromStored()` (`weather-metrics-tab/compareMetricSelection.ts:113-169`)
  — beide Modulgruppen sind bereits reine, kontextfreie Funktionen und
  bedienen den Trip ohne Änderung.
- **Go:** **keine Änderung.** `display_config` ist
  `map[string]interface{}` (`internal/model/trip.go:111`),
  `mergeConfigMap` (`internal/handler/config_merge.go:11-22`) merged
  `outlook_metrics` feldweise wie jedes andere unbekannte Feld.

> **Schicht-Hinweis:** Python-Core (`src/app/`, `src/services/`,
> `src/output/renderers/`) trägt Persistenz und Rendering; Frontend
> (`frontend/src/lib/components/shared/`) die Bedienfläche. Kein Anteil in
> `cmd/`, `internal/` oder anderen Go-Paketen.

## Estimated Scope

- **LoC:** ~135-180 Produktiv (Backend ~50: `models.py` ~2, `loader.py`
  ~4, Schnitt gegen die Grundauswahl ~15 (AC-14/15/16, Nachbildung von
  `_clip_to_global_maximum()` für das `{metric_id, aggregation}`-Vokabular),
  `trip_report_scheduler.py` ~6, `html.py` ~10, `plain.py` ~10, Legende ~3;
  Frontend ~110-125: `CompareOutlookLayoutControls.svelte`-Umbau auf
  flache Props ~30-40, `weatherMetricsTabSections.ts` ~5,
  `WeatherMetricsTab.svelte`-Verdrahtung ~70-80). Getrennt davon Test-LoC
  (eigenes Budget, s. u.). Bleibt unter dem 250er-Limit; kein Override
  beantragt.
- **Files:** ~8 Produktionsdateien geändert, 0 neu (Backend-Resolver und
  Frontend-Auswahl-/Übersetzungs-Helfer werden vollständig wiederverwendet,
  keine zweite Kopie).
- **Effort:** medium-high — geteilter Renderer (`outlook.py`) trifft
  strukturell Trip UND Compare; der stärkste vorhandene Wächter
  (`test_trip_outlook_parity.py`) erreicht die neue Aufrufstelle nicht
  (s. u.), der Bestandsschutz braucht deshalb einen neuen Test am echten
  Aufrufpfad.
- **LoC-Limit Test-Budget:** 500 (getrennt vom 250-Produktiv-Limit,
  `config_loader.py:264-297`). Playwright-Klickpfad und Wirkort-Mail-Test
  sprengen damit den Kern-Zuschnitt nicht.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `output.renderers.compare_outlook_metric_ids.resolve_outlook_metrics/outlook_columns/format_outlook_value` | reused, unverändert | Auflösung/Formatierung der Auswahl — dieselbe Funktion, die der Ortsvergleich seit ADR-0037 nutzt |
| `output.renderers.compare_metric_catalog.get_compare_metric_catalog()` / `/api/compare/metrics` | reused | **Die** Katalog-Quelle, gegen die der Resolver validiert — der Picker MUSS denselben Katalog laden, sonst bietet er Größen an, die der Resolver anschließend verwirft (Risiko 4 des Kontextdokuments) |
| `output.renderers.email.outlook.render_outlook_table/render_outlook_plain/build_outlook_row` | reused, additiv | Katalog-Zweig (`metrics is not None`) existiert bereits (`outlook.py:66-80,321-341,421-428`) — kein Neubau |
| `frontend/.../compareMetricOrder.ts::materializeOutlookMetricKeys/toggleOutlookMetricKeyFromState/DEFAULT_OUTLOOK_METRIC_KEYS` | reused, unverändert | Pure Functions, kontextfrei — bedienen Trip ohne Änderung |
| `frontend/.../compareMetricSelection.ts::toStoredActiveMetrics/normalizeStoredActiveMetrics/compareMetricKeyFromStored` | reused, unverändert | Lese-/Schreibübersetzung Auswahl-Schlüssel ↔ `{metric_id, aggregation}`, nimmt den Katalog als Parameter — kein zweiter Übersetzungscode |
| `frontend/.../WeatherV2Reihenfolge.svelte` (ADR-0024) | reused | Geteilter Sortier-Baustein für die Reihenfolge |
| `renderer_mail_gate.py` (#811) | Gate | Blockiert den Commit auf `html.py`/`plain.py`, bis `test_issue_811_mode_matrix.py` grün ist UND ein frischer `briefing_mail_validator.py`-Lauf vorliegt |
| `internal/handler/config_merge.go::mergeConfigMap` | upstream, unverändert | Merged `display_config.outlook_metrics` generisch — kein Go-Struct-Feld nötig |
| `pendant_gate.py` (#1481 B) | Gate | Die Änderung an `CompareOutlookLayoutControls.svelte` bleibt eine Änderung an einer bestehenden Datei unter `shared/` — keine Neuanlage, Gate greift nicht |

## Implementation Details

1. **Persistenz-Semantik, identisch zu Compare (ADR-0037).**
   `outlook_metrics` fehlt/`None` → die bisherigen sieben Spalten (inkl.
   ACC). `[]` (bewusst geleert) → der gesamte Ausblick-Block entfällt.
   Gefüllt → gewählte Spalten in Auswahlreihenfolge; ungültige Einträge
   werden von `resolve_outlook_metrics()` verworfen und geloggt
   (`compare_outlook_metric_ids.py:70-74`).

2. **`[]` muss den ganzen Block entfallen lassen, nicht nur die Spalten.**
   `render_outlook_table(rows, metrics=[])` würde ohne weitere Änderung eine
   Tabelle mit **nur der Tag-Spalte** liefern (`outlook.py:148-172`: die
   `if metrics is not None:`-Verzweigung baut Kopf/Zeilen ausschließlich aus
   `outlook_columns(metrics)`, bei leerer Liste bleibt nur `<th>Tag</th>`
   übrig) — das ist NICHT die Compare-Semantik „Block entfällt vollständig".
   Beim Ortsvergleich verhindert das `resolve_compare_render_options()`
   *vor* dem Renderer-Aufruf (`outlook_enabled=False` bei `[]`); der Trip hat
   keinen äquivalenten Render-Options-Schritt. Deshalb wird die Bedingung, ob
   der Block überhaupt gebaut wird, direkt an der Aufrufstelle erweitert:
   - `html.py`: `if multi_day_trend and _outlook_metrics != []:` statt
     `if multi_day_trend:`.
   - `plain.py`: `outlook_active = show_outlook and bool(multi_day_trend) and _outlook_metrics != []`,
     dieselbe `_outlook_metrics`.
   - Für `_outlook_metrics is None` (Altbestand) bleibt das Verhalten
     unverändert — nur der explizite `[]`-Fall schaltet ab.
   - Woher `_outlook_metrics` in beiden Renderern kommt, steht in Punkt 10 —
     sie berechnen es **nicht** selbst.

3. **`metrics=` wird an BEIDE Renderer übergeben, nicht nur an HTML.**
   Der stärkste vorhandene Wächter prüft das nicht (s. „Der Befund, der die
   Testplanung bestimmt" unten) — eine Aufrufstelle zu vergessen fiele ohne
   den neuen Wirkort-Test nicht auf. `render_outlook_table()` (HTML) UND
   `render_outlook_plain()` (Klartext) bekommen dieselbe `_outlook_metrics`.

4. **Legende wird an dieselbe Bedingung gekoppelt wie die Spaltenauswahl.**
   Die Abkürzungs-Legende (`html.py:1360-1366`,
   „N Nacht-Tief · D Tag-Hoch °C · R Regen mm · PR Regen-W. % · Wind/Böen
   km/h · Gew Gewitter-Stufe @h · ACC Prognose-Genauigkeit") beschreibt
   AUSSCHLIESSLICH die sieben festen Spalten. Ist eine Auswahl aktiv
   (`_outlook_metrics is not None`, unabhängig vom Inhalt — der `[]`-Fall
   baut den Block ohnehin nicht), sind die Tabellenköpfe bereits die
   ausgeschriebenen deutschen Katalog-Labels (`outlook_columns()`,
   `outlook.py:101-107`) — selbsterklärend, keine Abkürzung, keine Legende
   nötig. Die Legende wird deshalb nur gebaut, wenn
   `_outlook_metrics is None`. Andernfalls entstünde die Inkohärenz, dass
   die Legende z. B. „R Regen mm" erklärt, obwohl „Regen" in der aktiven
   Auswahl gar nicht gewählt wurde, und umgekehrt gewählte Größen (z. B.
   „Schneehöhe") in keiner Legende auftauchen.

5. **Legenden-Korrektur `N Nacht-Tief` → `N Tagestief`.** Gemessen
   (Kontextdokument, Beleg-Kette bis `weather_metrics.py:509-514`):
   `temp_lo` ist `summary.temp_min_c`, das Tages-Minimum **innerhalb des
   Wanderfensters** (Default 08:00 bis letzte Wegpunkt-Ankunft,
   `trip_segments.py:132`), NICHT das nächtliche Tief — die Nachtdaten
   fließen hier gar nicht ein (`_fetch_night_weather()` ist ein separater
   Datensatz). Die Legendenzeile wird zu
   `f'N Tagestief °C · D Tag-Hoch °C · R Regen mm · PR Regen-W. % · '`
   `f'Wind/Böen km/h · Gew Gewitter-Stufe @h · ACC Prognose-Genauigkeit'`
   — konsistent zur bestehenden Formulierung „D Tag-Hoch", kein neuer
   Begriff „Nacht" mehr an dieser Stelle. Diese Korrektur gilt UNABHÄNGIG
   von einer gesetzten Auswahl (nur im `None`-Zweig sichtbar, s. Punkt 4,
   also greift sie für 100 % der heutigen Trips ohne gesetzte Auswahl).

6. **Kein zweiter Ein/Aus-Schalter.** Der Trip hat mit
   `report_config.show_outlook` (`EditReportConfigSection.svelte:95,482-487`,
   Default `true`) bereits eine Bedienfläche, die den gesamten
   Ausblick-Block an-/abschaltet — sichtbar in der bestehenden
   Inhalt-/Versand-Karte, nicht im Wetter-Metriken-Reiter. Der neue
   Abschnitt „3-Tages-Vorschau" dupliziert das NICHT: er zeigt
   ausschließlich die Spaltenauswahl, keinen zweiten Toggle. Deshalb wird
   `CompareOutlookLayoutControls.svelte` so parametrisiert, dass
   `enabled`/`onEnabledChange` **optional** sind — nur die
   Compare-Einbindung übergibt sie (dort bleibt `outlook_enabled` unverändert
   bestehen), die neue Trip-Einbindung lässt sie weg, wodurch der
   `ChannelToggle` „3-Tages-Ausblick" im Trip-Zweig gar nicht gerendert wird.

7. **Abschnitt für beide Kontexte, `'stundenverlauf'` bleibt compare-exklusiv.**
   `weatherMetricsTabSections.ts:56`:
   ```
   const COMPARE_ONLY_SECTIONS = ['stundenverlauf'] as const;
   ```
   und in `weatherMetricsTabSections()` (Zeile 63-69) wird `sections.push('ausblick')`
   unbedingt (nach dem kontextabhängigen Block, vor `official_alerts`)
   ergänzt — Position im Trip-Reiter: direkt nach den route-eigenen
   Abschnitten (`sms_schwellen`/`auswertungen`/`report_config`), vor
   `official_alerts`; im Vergleich unverändert direkt nach
   `stundenverlauf`. `'stundenverlauf'` bleibt bewusst compare-exklusiv —
   der Trip hat heute keine Stundenverlauf-Steuerung, das nachzurüsten ist
   nicht Teil dieser Scheibe.

8. **Katalog-Ladepfad für den Trip erweitern.** `compareCatalog` wird heute
   nur geladen, wenn `context === 'vergleich'`
   (`WeatherMetricsTab.svelte:532`). Der Guard erweitert sich um
   `context === 'route'`, sonst bleibt der neue Abschnitt beim Trip ohne
   Katalog-Daten leer bzw. zeigt einen Dauer-Ladezustand.

9. **State/Dirty/Discard/Payload — vollständige Anbindung.** Eine neue
   `$state`-Variable `outlookMetricKeys: string[] | null` wird:
   - in `initFromTrip()` aus
     `normalizeStoredActiveMetrics(trip!.display_config?.outlook_metrics, compareCatalog)`
     initialisiert (Roundtrip-Übersetzung Neuformat → Auswahl-Schlüssel,
     analog Compare);
   - in `snapshot()`/`isDirty` aufgenommen (Muster `channelBuckets`,
     Zeile 352-363) — **ohne das bleibt der Reiter nach einer reinen
     Ausblick-Änderung fälschlich „sauber"**, der Speichern-Button feuert
     nie (der konkrete Fehler, den die Aufgabenstellung explizit als
     Fallstrick benennt);
   - in `handleDiscard()` aus dem geparsten `savedSnapshot` zurückgesetzt;
   - in `buildWeatherPayload()` als
     `outlook_metrics: outlookMetricKeys === null ? trip!.display_config?.outlook_metrics : toStoredActiveMetrics(outlookMetricKeys, compareCatalog)`
     in den Payload geschrieben — der Spread `...(trip!.display_config ?? {})`
     (Zeile 852) liefert bereits den Altwert; der explizite Zweig stellt
     sicher, dass eine bewusste Leerauswahl (`outlookMetricKeys = []`)
     tatsächlich als `[]` gesendet wird und nicht durch den Spread verdeckt
     bleibt (RMW-Pflicht, Fehlerklasse #102 → #1159).

10. **EINE Auflösungsregel, explizit durchgereicht (Nachbesserung nach
    Adversary-Finding F001, PO-Entscheid 2026-08-14).** Die Auswahl wurde
    zunächst an drei Stellen unabhängig aufgelöst (Zeitplaner, `html.py`,
    `plain.py`). Der Zeitplaner arbeitete auf dem ungekollabierten
    `trip.display_config`, die Renderer auf dem kanal-kollabierten `dc`
    (`trip_report.py`, `dataclasses.replace(dc, metrics=active_metrics)`) —
    ein Ausdruck, der auf beiden Seiten dasselbe liefert, musste deshalb
    `get_metrics_for_channel("email", …)` sein und schnitt damit
    kanal-gebunden. Die neue Bauform beseitigt die Ursache statt eine Seite
    zu opfern:
    - **Regel:** `resolve_trip_outlook_metrics(dc, report_type)`
      (`compare_outlook_metric_ids.py`) schneidet gegen
      `dc.get_metrics_for_report_type(report_type)` — kanal-neutral,
      spec-wörtlich, D2/D3/D4 unverändert. Der Ortsvergleich ruft weiterhin
      `resolve_outlook_metrics()` und bleibt unberührt.
    - **Spalten:** `trip_report.py` löst EINMAL aus `_dc_uncollapsed` auf
      (dem Stand, den #1575 Scheibe 3 für die SMS eingeführt hat) und reicht
      das Ergebnis als `render_email(outlook_metrics=…)` →
      `render_html(outlook_metrics=…)` / `render_plain(outlook_metrics=…)`
      durch. Beide Renderer lösen nicht mehr selbst auf; ihre Importe von
      `resolve_trip_outlook_metrics` entfallen.
    - **Zeilen:** der Zeitplaner löst gar nicht mehr auf, sondern reicht die
      ungekollabierte Konfiguration durch:
      `build_outlook_row(…, trip_display_config=dc, report_type=report_type)`.
      Die Auflösung passiert dort, in derselben Schicht wie der Spaltenbau.
      Nebeneffekt, der sie erzwingt: der Zeitplaner darf laut
      `test_notification_service::test_scheduler_has_no_output_imports`
      **nichts** aus `output/` importieren außer `build_outlook_row` — die
      erste Fassung verletzte diese Wache.
    - **Warum `build_outlook_row()` weiterhin selbst auflöst** (die eine
      verbleibende zweite Aufrufstelle, bewusst benannt): die Zellen entstehen
      zur Aggregationszeit aus `SegmentWeatherSummary`. Dieses Objekt reist
      nicht im Zeilen-Dict zum Renderer; es dorthin zu heben würde den
      geteilten Ausblick-Baustein und damit den Ortsvergleich ändern. Beide
      Aufrufstellen lesen jetzt aber dieselbe Funktion **und** denselben
      ungekollabierten Stand — die frühere Ursache des Auseinanderlaufens ist
      damit weg, nicht nur überdeckt. Ein ausdrücklich übergebenes `metrics=`
      hat Vorrang, deshalb ist der Compare-Pfad unverändert.
    - **Vorschau:** `preview_service` baut die Zeilen über einen EIGENEN
      `_build_stage_trend()`-Aufruf — dieser bekommt jetzt `report_type`
      durchgereicht (s. „Known Limitations").

## Was sich NICHT ändern darf

- **Trip-Mail ohne gesetztes `outlook_metrics` bleibt byte-identisch.**
  `trip_report_scheduler.py`, `html.py`, `plain.py` rufen weiterhin mit
  `metrics=None`, wenn `dc.outlook_metrics` `None` ist —
  `test_trip_outlook_parity.py` bleibt grün OHNE Anpassung seiner Golden-
  Dateien, weil er den geteilten Renderer direkt aufruft, nie die neue
  Aufrufstelle (s. „Der Befund, der die Testplanung bestimmt").
- **Compare-Verhalten unverändert.** `resolve_outlook_metrics()`,
  `outlook_columns()`, `format_outlook_value()`, die Compare-Renderpfade
  (`comparison.py`, `compare_html.py`) werden nicht angefasst.
- **Kompakt-Mail und Telegram unverändert.** `compact.py:227-238`,
  `narrow.py:571-609,820` bleiben unangetastet — sie kennen `outlook_metrics`
  in dieser Scheibe nicht (Scheibe 2).
- **`report_config.show_outlook`-Semantik unverändert.** Der bestehende
  Ein/Aus-Toggle bleibt die einzige Stelle, an der der Ausblick-Block ganz
  abgeschaltet wird; diese Scheibe fügt keinen zweiten hinzu.

## 🔴 Der Befund, der die Testplanung bestimmt

`tests/tdd/test_trip_outlook_parity.py:96,117` ruft
`render_outlook_table(parity_rows(), show_acc=True)` bzw.
`render_outlook_plain(...)` **direkt**, mit `metrics` auf dem Default `None`.
Die neue Verdrahtung in `html.py:1357`/`plain.py:338` durchläuft dieser Test
NIE. Er bleibt grün, egal ob die neue Aufrufstelle richtig oder falsch ist —
verwechselte sie `None` mit `[]`, wäre der Ausblick für alle Bestandstrips
still leer, und dieser Test meldete nichts.

**Golden-Dateien werden NICHT nachgezogen.** Der Bestandsschutz braucht einen
NEUEN Test am echten Aufrufpfad (`render_email()`,
`src/output/renderers/email/__init__.py:34`, bereits als voller
Kern-Test-Einstiegspunkt etabliert in
`tests/tdd/test_trip_renderer_characterization.py:221`), der HTML und
Klartext gegen eine vorher aufgezeichnete Referenz vergleicht — Prüfort muss
dem Wirkort entsprechen.

## Acceptance Criteria

- **AC-1:** Given ein Trip, dessen `display_config.outlook_metrics` NICHT
  gesetzt ist (Altbestand, heutiger Normalfall), When die Trip-Mail über den
  echten Versandpfad erzeugt wird (nicht der isolierte Renderer-Aufruf),
  Then sind HTML- und Klartext-Ausblick byte-identisch zu einer vor dieser
  Lieferung aufgezeichneten Referenz — inklusive Sieben-Spalten-Tabelle,
  ACC-Spalte und der (korrigierten) Legende.
  - Test: `render_email()` mit unverändertem `display_config` (kein
    `outlook_metrics`) gegen eine aufgezeichnete Referenz-Datei, NICHT gegen
    einen zweiten Aufruf desselben Codes im selben Lauf.

- **AC-2:** Gegeben ein Nutzer wählt im neuen Abschnitt „3-Tages-Vorschau"
  eine Teilmenge der Größen (z. B. nur „Niederschlag" und „Böen") und
  speichert, wenn die nächste Trip-Mail versendet wird, dann zeigt der
  HTML-Ausblick-Block ausschließlich diese gewählten Spalten in
  Auswahlreihenfolge, mit lesbaren deutschen Spaltenköpfen aus dem
  Katalog — nicht die bisherigen sieben festen Spalten.
  - Test: echter Trip-Versandpfad (`_send_trip_report_outcome()`,
    `trip_report_scheduler.py:1023`) getrieben, `EmailOutput(settings).send(...)`
    über eine Recording-Subklasse abgefangen (kein Mock-Framework, Muster
    `tests/tdd/test_compare_dispatch_mail_marker.py`), der von
    `build_mime_message()` (`output/channels/email.py:311`) gebaute
    HTML-Teil auf genau die gewählten Spalten geprüft.

- **AC-3:** Given dieselbe zugestellte/gerenderte Mail wie in AC-2, When der
  Klartext-Teil betrachtet wird, Then zeigt auch der Klartext-Ausblick
  ausschließlich dieselben gewählten Größen in derselben Reihenfolge wie der
  HTML-Teil.
  - Test: Klartext-Teil derselben abgefangenen Nachricht eigenständig auf
    die gewählte Spaltenmenge geprüft, gegen den HTML-Teil abgeglichen.

- **AC-4:** Given ein Trip mit `display_config.outlook_metrics = []`
  (bewusst geleerte Auswahl), When die Trip-Mail erzeugt wird, Then entfällt
  der gesamte 3-Tages-Vorschau-Block (weder Überschrift „Ausblick · nächste
  3 Tage" noch Tabelle) in HTML UND Klartext — nicht nur eine leere Tabelle
  mit Wochentag-Spalte.
  - Test: gerenderte Mail auf vollständige Abwesenheit jedes
    Ausblick-Bezugs geprüft, für HTML und Klartext getrennt.

- **AC-5:** Given eine gespeicherte Auswahl aus drei Größen, bewusst in
  unsortierter Reihenfolge gewählt (z. B. erst „Gewitter", dann
  „Temperatur", dann „Regen"), When die Mail erzeugt wird, Then erscheinen
  die drei Spalten exakt in dieser Auswahlreihenfolge — nicht alphabetisch,
  nicht in Katalog-Reihenfolge.
  - Test: Auswahl mit bewusst nicht-sortierter Reihenfolge, gerenderte
    Kopfzeile Spalte für Spalte gegen die Auswahlreihenfolge geprüft.

- **AC-6:** Gegeben ein Nutzer öffnet `/trips/<id>?tab=weather` im echten
  Browser, wenn er im Abschnitt „3-Tages-Vorschau" eine Größe abwählt und
  speichert, dann bleibt diese Abwahl nach einem Neuladen der Seite
  erhalten — und die Browser-Konsole bleibt währenddessen fehlerfrei.
  - Test: Playwright-Klickpfad unter `frontend/e2e/`, angemeldete Ansicht
    gegen Staging, Konsolenfehler und `pageerror` eingesammelt,
    Auswahl-Zustand vor/nach Reload verglichen.

- **AC-7:** Gegeben Kompakt-Mail und Telegram unterstützen die Auswahl noch
  nicht (Scheibe 2 folgt), wenn der Abschnitt „3-Tages-Vorschau" angezeigt
  wird, dann trägt er denselben Hinweistext wie beim Ortsvergleich
  („Erscheint nur in der E-Mail", Muster
  `CompareOutlookLayoutControls.svelte:159-161`) — kein neuer, unbegründeter
  Bruch, sondern ein bereits akzeptiertes Muster.
  - Test: Abschnitt im DOM auf das Vorhandensein des Hinweistexts geprüft,
    sobald mindestens eine Größe gewählt ist.

- **AC-8:** Given ein Trip OHNE gesetztes `outlook_metrics` (Legacy-Zustand,
  feste sieben Spalten), When der HTML-Teil der Mail betrachtet wird, Then
  bezeichnet die Legende die Spalte „N" nicht mehr als „Nacht-Tief", sondern
  korrekt als Tageswert innerhalb des Wanderfensters (z. B. „Tagestief") —
  die Zahl in der Spalte ist nachweislich das Tagesminimum im Wanderfenster,
  nicht das nächtliche Tief (Beleg-Kette Kontextdokument).
  - Test: HTML-Legendentext auf Abwesenheit von „Nacht" im Zusammenhang mit
    Spalte „N" geprüft, Ersatzformulierung vorhanden.

- **AC-9:** Given ein Trip MIT aktiver Spaltenauswahl (unabhängig vom
  Inhalt), When der HTML-Teil der Mail betrachtet wird, Then erscheint die
  alte Abkürzungs-Legende (N/D/R/PR/Wind/Böen/Gew/ACC) NICHT mehr — die
  Spaltenköpfe der Tabelle sind bereits ausgeschriebene deutsche
  Bezeichnungen und tragen für sich selbst, keine Legende nennt eine
  Bezeichnung, die zur aktuell gezeigten Spaltenmenge nicht passt.
  - Test: Mail mit aktiver Auswahl gerendert; die Legendenzeile aus dem
    Legacy-Pfad ist im HTML nicht vorhanden.

- **AC-10:** Given der Nutzer öffnet den Auswahl-Dialog für die
  3-Tages-Vorschau, When die wählbaren Größen angezeigt werden, Then ist
  „Vorhersage-Genauigkeit" (`confidence_pct`, ACC-Spalte) NICHT unter den
  Optionen — sie bleibt laut PO-Entscheid #710 dauerhaft keine pro-Spalte
  wählbare Größe. Given zusätzlich ein technisch manipulierter Speicher-
  Aufruf trägt trotzdem einen Eintrag mit `metric_id: "confidence"`, When
  die Mail anschließend gerendert wird, Then erscheint dafür keine Spalte —
  der Eintrag wird beim Rendern serverseitig verworfen (protokolliert),
  unabhängig davon, was im Editor angezeigt wurde.
  - Test: (a) geladene Katalogantwort des Pickers enthält keinen
    `confidence`-Eintrag; (b) `dc.outlook_metrics` künstlich mit einem
    `confidence`-Paar belegt, Renderausgabe enthält keine ACC/Confidence-
    Spalte, Log-Ausgabe zeigt die Verwerfung.

- **AC-11:** Given der Auswahl-Dialog lädt seine Größen aus derselben
  Katalog-Quelle wie der Resolver (`get_compare_metric_catalog()` /
  `GET /api/compare/metrics`), When eine beliebige im Dialog angebotene
  Größe gewählt und gespeichert wird, Then erscheint sie in der Mail
  garantiert als Spalte — der Picker bietet nie eine Größe an, die der
  Resolver anschließend verwirft.
  - Test: Menge der im Picker angebotenen Größen gegen die Menge der vom
    Resolver akzeptierten Größen abgeglichen — beide Mengen sind identisch,
    keine Differenz in beide Richtungen.

- **AC-12:** Gegeben ein Nutzer hat bereits eine Grundauswahl der
  Tages-Metriken und ein kanal-eigenes Layout eingestellt, wenn er
  anschließend NUR die 3-Tages-Vorschau-Auswahl ändert und speichert, dann
  bleiben Grundauswahl und Kanal-Layout unverändert erhalten — kein
  Datenverlust durch einen Vollersatz-Schreibvorgang (Fehlerklasse #102 →
  #1159).
  - Test: Grundauswahl + Kanal-Layout setzen und speichern, danach
    ausschließlich die Ausblick-Auswahl ändern und speichern, anschließend
    Trip neu laden und Grundauswahl/Kanal-Layout auf Unverändertheit prüfen.

- **AC-13:** Given der bestehende Ein/Aus-Schalter für den 3-Tages-Ausblick
  liegt bereits im Versand-/Inhalt-Bereich (`report_config.show_outlook`),
  When der neue Abschnitt „3-Tages-Vorschau" im Wetter-Metriken-Reiter
  angezeigt wird, Then enthält er KEINEN zweiten Ein/Aus-Schalter — nur die
  Spaltenauswahl.
  - Test: DOM des neuen Abschnitts auf Abwesenheit eines zusätzlichen
    Toggle-Elements für „Ausblick an/aus" geprüft.

- **AC-14:** Gegeben eine Wettergröße ist in der Grundauswahl des Trips
  NICHT aktiv, wenn sie über einen technisch manipulierten Speicher-Aufruf
  trotzdem in der Vorschau-Auswahl landet, dann erscheint sie in der
  zugestellten Mail NICHT als Spalte — die Vorschau darf nur abwählen, nie
  hinzufügen (PO-Entscheid 2026-08-14, ADR-0050 Regel 1/2 auf die
  Ausgabefläche „Vorschau" ausgeweitet).
  - Test: Der Schnitt wird am **Wirkort** geprüft, nicht in der Oberfläche —
    `display_config.outlook_metrics` künstlich mit einer Größe belegt, die in
    `display_config.metrics` fehlt; die gerenderte Mail (HTML und Klartext)
    enthält keine Spalte dafür. Eine Prüfung, die nur den Editor betrachtet,
    genügt NICHT: sie wäre eine Attrappe, die ein direkter PUT umgeht
    (Bedingung aus ADR-0053, „die ganze Kette, nicht nur die Oberfläche").

- **AC-15:** Gegeben eine Wettergröße erscheint heute in der Vorschau, wenn
  der Nutzer sie anschließend in der Grundauswahl abwählt, dann verschwindet
  sie ohne weiteres Zutun auch aus der Vorschau der nächsten Mail — eine
  globale Abwahl überlebt keine Ausgabefläche (ADR-0050 Regel 3).
  - Test: Zwei aufeinanderfolgende Renderläufe desselben Trips, dazwischen
    nur die Grundauswahl geändert; die Spalte ist im zweiten Lauf weg, die
    übrigen gewählten Spalten stehen unverändert.

- **AC-16:** Gegeben ein Trip hat überhaupt keine Grundauswahl gespeichert
  (Altbestand, `display_config.metrics` leer), wenn eine Vorschau-Auswahl
  gesetzt ist, dann wird sie vollständig gezeigt und NICHT gegen eine leere
  Menge geschnitten — eine fehlende Grundauswahl bedeutet „kein Maximum
  definiert", nicht „nichts erlaubt".
  - Test: `display_config.metrics = []` mit gesetzter Vorschau-Auswahl; alle
    gewählten Spalten erscheinen. Diese Regel ist der bestehenden
    `_clip_to_global_maximum()`-Regel D4 (`src/app/models.py:913-914`)
    wortgleich nachgebildet — der Ausblick-Schnitt darf sich hier nicht
    anders verhalten als der Kanal-Schnitt aus #1719 Scheibe 2.

- **AC-17:** Gegeben ein Trip führt ein E-Mail-eigenes Kanal-Layout
  (`display_config.per_channel_layouts["email"]`, Bestandsfeature seit #429),
  das eine Wettergröße NICHT enthält, während dieselbe Größe in der
  Grundauswahl aktiv UND für die Vorschau gewählt ist, wenn die Mail über den
  echten Versandpfad zugestellt wird, dann erscheint sie als Spalte im
  Ausblick, und jede Spalte trägt den Wert ihrer eigenen Größe (kein
  Spaltenversatz zwischen Überschrift und Zahl). Der Ausblick hat bewusst
  keine Kanal-Ebene (s. „Out of Scope") — ein enges Kanal-Layout darf ihn
  nicht leiser machen als die Grundauswahl erlaubt.
  - Herkunft: Adversary-Finding F001 (HIGH, spec_violation) aus dem Lauf vom
    2026-08-14 — der erste Schnitt lief gegen
    `get_metrics_for_channel("email", report_type)` und schnitt damit für
    diese reale, im Editor bedienbare Konfiguration strenger als AC-14/15/16
    verlangen. Keiner der ersten 27 Tests setzte `per_channel_layouts`.
  - Test: drei Prüfungen am Wirkort (zugestellte MIME-Nachricht bzw. echte
    Vorschau-Pipeline), `tests/tdd/test_trip_outlook_dispatch_mail.py`:
    (a) Kanal-Layout ohne die **zweite** gewählte Größe ⇒ sie steht trotzdem
    in Kopfzeile und Klartext; (b) Kanal-Layout ohne die **erste** gewählte
    Größe ⇒ ein Versatz verschöbe die Zuordnung um eine Position statt nur
    abzuschneiden, deshalb werden zusätzlich die Zellwerte je Spalte geprüft;
    (c) Vorschau (`PreviewService._build_report()`) zeigt dieselbe Kopfzeile
    UND dieselben Zellen wie die zugestellte Mail.

## Mutations-Gegenproben

Zehn Verfälschungen: fünf aus dem Kontextdokument (1-5), zwei S1-eigene
(6-7, während der Spec-Erstellung ergänzt — leere Auswahl und
Legenden-Kohärenz sind neue Verzweigungen dieser Scheibe), sowie drei zum
Schnitt gegen die Grundauswahl (8-10, nach dem PO-Entscheid vom 2026-08-14
ergänzt):

1. `resolve_outlook_metrics(dc.outlook_metrics)` wird zu `... or []`
   verkürzt (`None` als leer behandelt) ⇒ **AC-1** (Bestandsschutz) muss rot
   werden — der Ausblick würde für alle Bestandstrips leer.
2. `metrics=` wird nur an `render_outlook_table` (HTML) übergeben, nicht an
   `render_outlook_plain` (Klartext) ⇒ **AC-3** (Klartext-Parität) muss rot
   werden.
3. Der Picker lädt den ungefilterten zentralen Registry-Katalog statt
   `get_compare_metric_catalog()`, wodurch `confidence` wählbar wird ⇒
   **AC-10** und **AC-11** müssen rot werden.
4. Die Auswahl-Reihenfolge wird über ein `Set` statt eine geordnete Liste
   geführt ⇒ **AC-5** muss rot werden.
5. Das Speichern schreibt `display_config` als Vollersatz statt feldweise
   (RMW) ⇒ **AC-12** muss rot werden.
6. Die Bedingung `_outlook_metrics != []` in `html.py`/`plain.py` wird auf
   `_outlook_metrics` (Wahrheitswert statt expliziter Vergleich) verkürzt —
   `[]` ist in Python falsy, das sieht im Diff harmlos aus, verändert aber
   nichts am Ergebnis für DIESEN Fall. Die eigentliche Gegenprobe: die
   Bedingung wird ganz weggelassen (`if multi_day_trend:` unverändert) ⇒
   **AC-4** muss rot werden (leere Tabelle mit Wochentag-Spalte statt
   vollständigem Wegfall).
7. Die Legende in `html.py` wird unabhängig von `_outlook_metrics` immer
   gebaut (Bedingung aus Punkt 4 der Implementation Details entfernt) ⇒
   **AC-9** muss rot werden (Legende nennt Abkürzungen von Spalten, die gar
   nicht gezeigt werden).
8. Der Schnitt gegen die Grundauswahl wird **nur im Frontend** umgesetzt (der
   Picker zeigt die abgewählten Größen nicht mehr an), am Renderer aber nicht
   ⇒ **AC-14** muss rot werden. Diese Mutation ist die wichtigste der Liste:
   sie ist die einzige, bei der die Oberfläche dem Nutzer das richtige
   Verhalten *zeigt*, während die zugestellte Mail es nicht *einhält* — genau
   die Attrappen-Fehlerklasse, gegen die ADR-0053 die Ganze-Kette-Bedingung
   gesetzt hat.
9. Der Schnitt verwendet rohe `enabled`-Flags statt
   `get_metrics_for_report_type(report_type)` ⇒ ein Test muss rot werden, der
   eine per Morgen-/Abend-Override abgeschaltete Größe prüft. Die bestehende
   Kanal-Schnitt-Regel begründet diese Quelle ausdrücklich
   (`src/app/models.py:903-907`, D2) — u. a. weil damit auch das
   `selectable`-Gate (#1585) im Schnitt wirkt.
10. Der Schnitt läuft auch bei leerer Grundauswahl (`self.metrics == []`) und
    liefert dadurch eine leere Spaltenmenge ⇒ **AC-16** muss rot werden. Das
    ist die Regel D4 aus `_clip_to_global_maximum()`; sie hier zu vergessen
    ist der naheliegendste Fehler beim Nachbilden.

## Prüfhinweis für den Adversary

- Leitfrage (Projektregel „Prüfort muss dem Wirkort entsprechen"): Ist die
  Zusicherung an der Stelle geprüft, an der sie **wirkt** — an der
  versendeten/gerenderten Mail über den echten Aufrufpfad — oder nur dort,
  wo der Code steht (isolierter `render_outlook_table()`-Aufruf, den
  `test_trip_outlook_parity.py` bereits abdeckt)?
- Zweite Pflichtprobe: `dc.outlook_metrics` NICHT auflösen und stattdessen
  roh als `metrics=dc.outlook_metrics` durchreichen (ohne
  `resolve_outlook_metrics()`) — ein Eintrag mit unbekanntem `metric_id`
  müsste dann einen Absturz statt eines stillen Verwerfens auslösen. AC-10/
  AC-11 sollten das über die Fehlerfreiheit des Renderpfads indirekt fangen;
  wird kein Test rot, ist das ein Finding.
- Dritte: `initFromTrip()` liest `outlook_metrics` nicht über
  `normalizeStoredActiveMetrics()`, sondern castet die gespeicherten
  Objekte direkt auf `string[]` — die Anzeige nach einem Neuladen zeigt dann
  keine angehakten Größen, obwohl gespeichert wurde. AC-6 (Playwright-
  Klickpfad) muss das über den Reload-Vergleich fangen.

## Out of Scope

**Zuschnitt dieser Lieferung (Scheibe 1), keine dauerhafte Festlegung** — im
Unterschied zur früheren Formulierung in
`docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md:535-536`
(„Der Trip bekommt keine Bedienfläche — das Epic betrifft ausschließlich den
Ortsvergleich"), die eine Zuschnittgrenze jener Lieferung war und fälschlich
als Produktentscheidung gelesen wurde (s. Kontextdokument, Abschnitt „Zur
Notiz im Code, die dagegen zu sprechen scheint"). Diese Spec löst jene
Formulierung ausdrücklich ab.

- **Kompakt-Mail (`compact.py:227-238`) und Telegram-Bubble
  (`narrow.py:571-609`) bleiben unverändert.** Beide haben eigene,
  unabhängige Ausblick-Implementierungen ohne Katalog-Anbindung und ohne
  Byte-Wächter. Sie folgen **unmittelbar** in Scheibe 2 — nicht auf
  unbestimmte Zeit vertagt. Scheibe 2 legt vor jeder Änderung zuerst einen
  Charakterisierungstest des heutigen Ist-Zustands an, weil dort kein
  Wächter existiert (PO-Entscheidung, Kontextdokument).
- **Keine Kanal-Ebene.** Eine globale Auswahl für alle Ausgabeorte, kein
  eigener Kanal-Eintrag und kein Unterabschnitt je Kanal. Begründung (PO,
  2026-08-14, NICHT aus ADR-0053 abgeleitet — jenes Zitat rechtfertigt nur
  einen Scheiben-Schnitt, keine grundsätzliche Eigenschaft): SMS und
  Premium-SMS erreichen den Ausblick baulich nicht (`sms_trip.py` kennt
  `multi_day_trend` nicht); wirksam wären genau zwei Kanäle (E-Mail in drei
  Formen, Telegram). Eine Kanal-Ebene für zwei Kanäle verdoppelt Speicherweg,
  Resolver und Bedienfläche für einen Nutzen, den niemand angefragt hat.
- **Kein zusätzliches Sortier-Bedienelement.** Reihenfolge ausschließlich
  über den geteilten `WeatherV2Reihenfolge`-Baustein (ADR-0024), wie beim
  Ortsvergleich.
- **Kein CI-Ampel-Eintrag für den neuen Playwright-Test in dieser
  Lieferung.** Die Positivliste `.github/ci_e2e_specs.txt` wächst nur nach
  dem in ADR-0054 beschriebenen Vermessungsprozess (3× grün im
  `workflow_dispatch`-Lauf) — das ist ein eigener, unabhängiger Vorgang und
  nicht Teil dieser Spec.
- **Keine Migration bestehender Compare-Presets oder -Formate.**

## Known Limitations

- Die generische Zellenformatierung für Größen außerhalb der bisherigen
  sieben (z. B. Enum-/Ordinal-Werte) ist bereits durch `format_outlook_value()`
  abgedeckt (identisch zum Compare-Verhalten) — keine neue Formatierungsarbeit
  in dieser Scheibe, aber auch keine trip-spezifische Sonderprüfung über die
  vom Compare bereits gehärteten Fälle hinaus.
- `WeatherV2Reihenfolge` erhält `activeChannel="email"` fest verdrahtet
  (identisch zur Compare-Einbindung) — das steuert dort nur eine
  darstellerische Eigenschaft, keine Kanal-Filterung; die PO-Entscheidung
  „keine Kanal-Ebene" macht diesen Wert für den Trip ohnehin bedeutungslos.
- Ein manipulierter Payload mit `confidence` wird beim Rendern verworfen,
  aber NICHT mit einem HTTP-Fehler beim PUT abgelehnt — `display_config` ist
  serverseitig (Go) opak, Validierung findet ausschließlich am Resolver zur
  Renderzeit statt (identisch zum bestehenden Compare-Verhalten, kein neues
  Sicherheitsrisiko, aber auch keine strengere Eingabevalidierung als heute).
- 🔴 **Trip und Ortsvergleich verhalten sich nach dieser Lieferung
  unterschiedlich.** Der Trip-Ausblick wird gegen die Grundauswahl
  geschnitten (AC-14/15/16, PO-Entscheid 2026-08-14); der Compare-Ausblick
  führt weiterhin eine unabhängige Liste ohne jeden Schnitt
  (`resolve_outlook_metrics()` kennt kein globales Maximum). Das ist eine
  bewusst in Kauf genommene Divergenz, keine Auslassung: der PO-Entscheid zur
  Kaskade (#1719, ADR-0050) erging für den Trip, und der Auftragstext zu
  #1720 verlangt ihn ausdrücklich auch hier.
  **Wer den Compare später nachzieht, sollte das an dieser Stelle
  wiederfinden** — die Trip/Compare-Teilungsvorgabe ist damit für die
  *Semantik* offen, während der *Code* (Resolver, Renderer, Bedienelement)
  geteilt bleibt. Der Schnitt sitzt bewusst außerhalb von
  `resolve_outlook_metrics()`, damit der Compare-Pfad unberührt bleibt;
  eine spätere Vereinheitlichung muss ihn hineinziehen, nicht danebenlegen.
- 🔴 **Der Vorschau-Pfad baute die Ausblick-Zellen nach dem falschen
  Report-Typ** (gefunden bei der F001-Nachbesserung, 2026-08-14, behoben):
  `preview_service` rief `scheduler._build_stage_trend(trip, target, …)` ohne
  `report_type` — der Parameter hat den Default `"evening"`. Solange dort
  nichts aufgelöst wurde, war das folgenlos; mit dieser Scheibe steuert
  `report_type` die Zellen. Bei einem Morgen-/Abend-Override
  (`morning_enabled`/`evening_enabled`) hätte die Vorschau die Zellen nach dem
  Abend-Default und die Überschriften nach dem echten Typ gebaut — sichtbar
  als „–" unter einer korrekt beschrifteten Spalte, ausschließlich in der
  Vorschau, nicht in der zugestellten Mail. Jetzt durchgereicht und von
  AC-17 (c) bewacht; die Mutations-Gegenprobe (Parameter entfernt) macht
  diesen Test rot.
- Die Vorschau-Parität ist damit für die **Spaltenwahl** bewacht, nicht für
  jede andere Abweichung zwischen Vorschau und Versand — dafür bleiben
  `test_preview_parity_without_outlook.py` und `test_sms_preview_matches_sent.py`
  zuständig.

## Definition of Done

- [ ] AC-1 bis AC-17 grün (AC-17 kam nach dem Adversary-Lauf vom 2026-08-14
      hinzu, Finding F001 — die 16 vom PO freigegebenen ACs bleiben inhaltlich
      unverändert)
- [ ] Adversary-Verdict VERIFIED, alle zehn Pflicht-Mutationen gefangen
      sowie die fünf Gegenproben der F001-Nachbesserung (Spaltenauflösung aus
      dem kollabierten `dc`; Durchreichung an `render_html` bzw.
      `render_plain` weggelassen; `report_type` im Vorschau-Zeilenbau
      weggelassen; `trip_display_config` im Zeilenbau weggelassen)
- [ ] `test_trip_outlook_parity.py` bleibt grün OHNE Anpassung der
      Golden-Dateien
- [ ] Playwright-Beleg zu AC-6 im Änderungssatz (Screenshot + Konsolenprotokoll)
- [ ] Neues ADR (nächste freie Nummer, Stand dieser Spec: 0055) schreibt
      ADR-0037 Punkt 2 fort — Status von ADR-0037 wird auf „Abgelöst durch
      ADR-0055" (bezogen auf Punkt 2) bzw. entsprechend präzisiert gesetzt
- [ ] Issue #1720 Scheiben-Checkbox für Scheibe 1 gesetzt, Scheibe 2
      angekündigt

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** neu — Vorschlag ADR-0055 (nächste freie Nummer nach
  ADR-0054, Stand `docs/adr/README.md` zum Zeitpunkt dieser Spec;
  bei paralleler Sitzungsbelegung vor dem Schreiben erneut prüfen).
- **Rationale:** ADR-0037 Punkt 2 sichert wörtlich zu: „Der Trip ruft
  weiterhin ohne `metrics` auf — die Trip-Mail ändert sich in keinem Byte."
  Diese Lieferung löst genau diese Zusicherung ab: der Trip bekommt jetzt
  eine echte, wählbare Auswahl für HTML- und Klartext-Ausblick. Das ist eine
  bewusste, freigegebene Rücknahme einer dokumentierten Entscheidung (PO,
  2026-08-14) und braucht laut CLAUDE.md ein neues ADR mit
  Status-Fortschreibung an ADR-0037 — keine stille Änderung. Das neue ADR
  hält zusätzlich fest: (a) die Auswahl bleibt bewusst global (keine
  Kanal-Ebene) mit der Aufwand-Nutzen-Begründung aus „Out of Scope", (b) der
  Umbau erfolgt in zwei Scheiben, mit Charakterisierungstest vor Scheibe 2,
  weil dort kein Wächter existiert. Verworfene Alternative: ein
  Trip-eigener Ausblick-Renderer — verworfen aus demselben Grund wie bei
  ADR-0037 selbst (Trip/Compare-Teilungs-Invariante, Anti-Pattern-Referenz
  #1170); der geteilte Baustein bleibt geteilt, diese Scheibe nutzt nur
  seinen bereits vorhandenen additiven `metrics`-Parameter.

## Changelog

- 2026-08-14: Initial spec created
- 2026-08-14: Nachbesserung nach Adversary-Finding F001 (HIGH) — AC-17
  ergänzt, Implementation Details Punkt 10 (eine Auflösungsregel,
  kanal-neutral, explizit durchgereicht) ergänzt, Punkte 2/3 darauf
  verwiesen, Known Limitations um den Vorschau-Befund erweitert, DoD-Zählungen
  nachgezogen. Die 16 freigegebenen ACs bleiben inhaltlich unangetastet.
