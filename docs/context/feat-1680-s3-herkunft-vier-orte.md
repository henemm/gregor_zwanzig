<!-- Issue #1680, Scheibe 3 (vier weitere Ausgabeorte). Vorgaenger: S1 (Ortsvergleich,
     live 2026-08-12) und S2 (Trip-Kurzzusammenfassung + GEWITTER-Kommando, live 2026-08-12,
     Merge bacc6f29). Bezug: Epic #1419 Rang 4, Entscheidung E1. -->

# Kontext: Herkunft der Gewitterstufe an vier weiteren Ausgabeorten (#1680 Scheibe 3)

## Zusammenfassung der Anforderung

Die fusionierte Gewitterstufe soll ihre tragenden Signale an vier weiteren Stellen
nennen. PO-Entscheid zum Umfang (2026-08-13): **Pille im Metriken-Überblick**,
**Kommando-Timeline je Wegpunkt**, **GLANCE-Tageszeile** und
**Ortsvergleich-Stundentabelle**.

Auswahlgrund: bei allen vieren liegt die Zutat bereits vor. Keiner braucht ein neues
Feld, einen strukturellen Umbau oder den Aggregationsweg, der seit Scheibe 2
bewusst unangeschlossen bleibt.

Fortbestehende PO-Entscheidungen (2026-08-11), unverändert gültig:

| Frage | Entscheidung |
|---|---|
| Auslegung | **(ii) alle tragenden Signale** — jede Zutat, die die gezeigte Stufe erreicht. Kein Gewinner wird gekürt |
| Kanäle | **E-Mail und Telegram ja · SMS und Premium-SMS ausdrücklich OHNE Herkunft** — aktiv abzuwählen, nicht stillschweigend auszulassen |

## Was aus S1 und S2 bereitsteht

| Baustein | Ort | Rolle |
|---|---|---|
| `union_of_max_carriers()` | `src/output/metric_format.py` | **die eine** Stelle, an der die Vereinigungsregel gerechnet wird; garantiert seit S2-Finding F001 selbst, dass Stufe `NONE` auf `None` führt |
| `thunder_signal_carriers()` | `src/output/metric_format.py` | ermittelt je Zeitpunkt die tragenden Signale |
| `THUNDER_SIGNAL_LABEL_DE` / `thunder_signal_label()` | `src/output/metric_format.py:374-390` | deutscher Wortkatalog, vier feste Schlüssel |
| `ForecastDataPoint.thunder_level_signals` | `src/app/models.py:204` | `list[str]`, providerseitig befüllt (`providers/thunder_enrichment.py:151`) |
| `SegmentWeatherSummary.thunder_level_max_signals` | `src/app/models.py:430` | `list[str]`, befüllt in `compute_basis_metrics()` |

Renderweg überall gleich (Hagel-Muster aus #1475): `f"{text} · {note}"`.

## Die vier Ausgabeorte im Einzelnen

### 1. Pille im Metriken-Überblick
`src/output/renderers/email/helpers.py:1713-1757` (`_pill_for_metric`, thunder-Zweig),
gespeist von `build_metrics_summary_pills()` (`:1815-1881`).

- **Datenquelle:** `all_dps` aus `build_day_window_points(...)` (`:1861-1864`) — rohe
  `ForecastDataPoint`-Liste, kein Aggregat. `dp.thunder_level_signals` ist direkt
  erreichbar, wird heute nicht gelesen.
- **Nicht mit Compare geteilt:** Aufrufer von `build_metrics_summary_pills()` sind
  ausschließlich Trip-Renderer (`compact.py:176`, `plain.py:205`, `html.py:1432`);
  `compare_html.py` ruft sie nicht auf. Die *Datei* `helpers.py` ist geteilt, die
  *Funktion* nicht.
- **Platz:** freier Fließtext, kein Zeichenlimit im Code. Das Hagel-Suffix hängt dort
  bereits (`format_hail_note`).

### 2. Kommando-Timeline je Wegpunkt
`src/services/trip_command_processor.py:908-939` (`_fmt_timeline`), Gewitterzeile
`:933-937`.

- **Datenquelle:** `m = p.metrics` (`:928`) — eine `SegmentWeatherSummary` je Wegpunkt,
  aus `WeatherExtractor.timeline()` (`weather_extractor.py:98`, `metrics=seg.aggregated`).
  Das ist ein **Einzelsegment**-Aggregat aus `compute_basis_metrics()`, also mit korrekt
  gerechneter Trägerliste — **nicht** vom `aggregate_stage()`-Rückfall betroffen.
- **Platz:** freier Zeilentext mit Emoji, kein Limit.

### 3. GLANCE-Tageszeile
`src/services/trip_command_processor.py:844-854` (`_fmt_day_agg`), Gewitter-Label `:849`.

- **Die Zutat liegt bereits im Aggregat:** `_aggregate_day()` (`:804-842`) rechnet
  `thunder_signals` seit Scheibe 2 über `union_of_max_carriers()` (`:834-839`). Nur
  `_fmt_gewitter()` liest den Schlüssel; `_fmt_day_agg()` nicht.
- 🔴 **Diese Scheibe dreht eine Entscheidung um.** Der Kommentar an `:832-833` hält
  ausdrücklich fest: „Nur `_fmt_gewitter()` liest den Schluessel; `_fmt_day_agg()` /GLANCE
  bleibt bewusst zeichengleich (Spec D3, Known Limitation 4)." Das war der S2-Entscheid;
  der PO hat ihn am 2026-08-13 bewusst abgelöst. Kommentar und Spec-Verweis sind
  entsprechend nachzuziehen — eine stehengebliebene Notiz, die das Gegenteil behauptet,
  ist genau die Fehlerklasse, die in S2 zum Streichen eines ganzen Arbeitspunkts führte.

### 4. Ortsvergleich-Stundentabelle
`src/output/renderers/email/compare_html.py:962-998` (`_render_hour_row`, HTML) und
`src/output/renderers/comparison.py:329-333` (Klartext).

- **Der Parameter existiert bereits.** `_fmt_thunder(v, hail=None, signals=None)`
  (`compare_html.py:204-233`) hat den dritten Parameter seit S1. Der Docstring
  (`:215-220`) hält fest, dass er dort bewusst nicht übergeben wurde — die
  Stundentabelle blieb in S1 unverändert (AC-11 dort).
- **Aufrufstellen:** `_render_hour_row` ruft `m["fmt"](value, getattr(dp, "hail_flag", None))`
  (`:982-983`) — ohne dritten Parameter, obwohl `dp` die Signale trägt. Klartext ebenso
  (`comparison.py:329-333`).
- **Anzeige ist Text, nicht Farbe:** Kommentar `compare_html.py:977-981` — „Gewitter als
  TEXT (kein Ampel-Kreis)". Ein Suffix ist dort also sichtbar.

## Warum drei Kandidaten NICHT in dieser Scheibe sind

| Kandidat | Grund |
|---|---|
| **Mehrtages-Ausblick** (`email/outlook.py`) | Die Träger gehen **strukturell** verloren: `HourlyValue` (`src/output/tokens/dto.py:15-18`) ist ein frozen Dataclass mit nur `hour` und `value`. Dazu getrennte Tag-/Nachtanteile (#1653), die zwei eigene Trägerrechnungen bräuchten, und er ist der **einzige** Kandidat, der `aggregate_stage()` als Verbraucher aktivieren würde (`trip_report_scheduler.py:2026`). Eigene Scheibe. |
| **Trip-Stundentabelle** | Braucht erst einen Seitenkanal analog `row["_hail_flag"]` (`trip_report.py:687`) in `_dp_to_row()` plus Auswertung in `fmt_val()` (`helpers.py:732-757`). Zusätzlich rechnet `_aggregate_night_block()` (`trip_report.py:596-601`) mit `max_thunder()` ohne Trägerlogik — eine zweite, unabhängige Stelle. |
| **Gewitter-Vorschau** | Primärpfad liest `row["hourly_thunder"]`, also dieselben trägerlosen `HourlyValue` wie der Ausblick (`trip_report_scheduler.py:2266`). Nur der Fallback-Pfad (`:2494-2504`) hätte rohe Datenpunkte. Halb baubar — gehört zum Ausblick. |
| **Go-DTO** | `internal/model/segment.go:15` hat kein Signalfeld — aber `model.SegmentWeatherSummary` wird laut vollständigem grep über `internal/` **nirgends konstruiert oder gelesen**. Ein Feld dort hätte keinen Verbraucher. |
| **Frontend** | Keine Komponente rendert eine live abgerufene Gewitterstufe. `CompareMetrics` (`frontend/src/lib/types.ts:426-440`) wird außerhalb von `types.ts` nicht referenziert; alle übrigen `thunder_level_max`-Treffer sind Konfigurations-Oberflächen (Korridor-/Alarm-Editor, Metrik-Auswahl) mit Katalog-Schlüsseln, keine Live-Werte. `TablePreview.svelte:36-39` zeigt statische Demodaten. |

Go und Frontend fallen damit **ersatzlos**, nicht aufgeschoben: es gibt dort keinen Ort,
an dem die Herkunft erscheinen könnte. Dieselbe Begründung, aus der in S2 der
`aggregate_stage()`-Zweig draußen blieb — Code ohne Wirkort, den kein Test bewachen kann.

## Der Aggregationsweg bleibt unberührt

`aggregate_stage()` (`src/services/weather_metrics.py:1168-1271`) kennt die Regel
`union_of_max_carriers` weiterhin nicht und fällt in den generischen `else`-Zweig
(`:1265-1266`) auf `values[0]` zurück. Gemessen (vollständige Konsumentenanalyse):

- `stage_weather.py:112` liest die Trägerliste **nicht** (nur Temperatur, Wind,
  Niederschlag, Wettercode).
- `compact_summary.py:268` (`_aggregate()`) ebenfalls nicht — der Gewittertext dort
  rechnet bewusst daneben, direkt über die Stundenwerte (`:572-629`, eigener
  `union_of_max_carriers()`-Aufruf `:628`).
- `trip_report_scheduler.py:2026` (Mehrtages-Ausblick) **wäre** der erste Verbraucher —
  liest heute aber nur `agg.thunder_level_max`.

⇒ Keiner der vier Ausgabeorte dieser Scheibe aktiviert den Rückfall. Known Limitation 7
aus Scheibe 1 bleibt bestehen und gehört in die Ausblick-Scheibe.

## Risiken und Fallstricke

1. 🔴 **Die Voraussetzung des Musters je Ort einzeln prüfen** (Lehre aus AC-12 in S1 und
   aus dem gestrichenen Arbeitspunkt in S2). Für jeden der vier Orte ist zu belegen, dass
   **gezeigte Stufe und Trägerliste aus derselben Rechnung** stammen. Bei der Pille und
   der Stundentabelle ist das je ein Datenpunkt, bei der Timeline ein Segment-Aggregat,
   bei GLANCE das Tages-Aggregat — vier verschiedene Ebenen.
2. 🔴 **Kein Leck in SMS und Premium-SMS.** `comparison.py` speist auch die Compare-SMS
   (`:629`, `_sms_metric_cell`) — in S1 war die Annahme „Compare-SMS zeigt Gewitter gar
   nicht" gemessen **falsch**. Der Klartext-Zweig der Stundentabelle ist hier besonders
   zu prüfen. Ebenso der Trip-Rückfall `report.sms_text or report.email_plain`
   (`notification_service.py:417,433`).
3. **Geteilte Funktion:** `_fmt_thunder` speist sowohl die S1-Übersichtszeile (mit
   Herkunft) als auch die Stundentabelle (bisher ohne). Eine Änderung im Rumpf statt an
   der Aufrufstelle würde die Übersichtszeile mit verändern.
4. **Zeichengleichheit** überall dort, wo keine Herkunft vorliegt — inklusive
   Alt-Schnappschüssen ohne das Feld.
5. **Commit-Gates:** `renderer_mail_gate.py` greift für `email/`-Dateien und
   `compare_html.py` — Commit blockiert ohne frischen `briefing_mail_validator.py`-Lauf
   und grüne `tests/tdd/test_issue_811_mode_matrix.py`. Für den Ortsvergleich ist
   zusätzlich `email_spec_validator.py` der zuständige Validator (zwei Mailpfade, zwei
   Gates).
6. **Doku-Drift aktiv nachziehen:** der Kommentar `trip_command_processor.py:832-833`
   behauptet nach dieser Scheibe das Gegenteil des Codes, ebenso der Docstring-Hinweis in
   `compare_html.py:215-220`. Beide gehören in den Änderungssatz.
