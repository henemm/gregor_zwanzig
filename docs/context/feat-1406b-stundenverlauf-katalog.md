# Kontext: Issue #1406 Scheibe B — Stundenverlauf auf den zentralen Katalog

Analyse-Auftrag, KEINE Implementierung. Arbeitsverzeichnis:
`/home/hem/gregor_zwanzig/.claude/worktrees/ws-overview-0725`. Stand: 2026-07-30,
nach #1406 Scheibe A (`86ff7f1c`, live) und #1411 (`74557cdf`, live).

## Auftrag

Bedienfläche (Grundauswahl über dem Stundenverlauf) und Auflösungspfad (Renderer)
in einer Lieferung auf den zentralen Wetterkatalog (`src/app/metric_catalog.py`,
24 wählbare Größen) umstellen. Nicht trennbar: fällt vorne die 10er-Liste ohne
Backend-Auflösung, kann der Nutzer 24 Größen anhaken, von denen nur 10 ankommen
(stiller Verlust, Invariante 2 aus Epic #1372).

## Befund 1 — es gibt KEINE technische Grenze; alle 24 Größen haben einen Stundenwert

Kernbefund, mit dem Code geprüft (nicht angenommen):

```
python3 -c "from app.metric_catalog import get_all_metrics; [print(m.id, m.dp_field) for m in get_all_metrics()]"
```

Alle 24 selektierbaren Katalog-Größen tragen ein `dp_field` — einen echten
Rohwert je Stunde in `ForecastDataPoint` (`src/app/models.py:94-150`). Das
prüft auch der **Trip**: `trip_report.py:421,499` und `email/helpers.py:112,165`
iterieren bereits generisch über `dc.metrics` und lesen jede Größe per
`getattr(dp, metric_def.dp_field, None)` — für alle 24, nicht nur für 9.

**Konsequenz:** Die 14 Größen, die der Ortsvergleichs-Stundenverlauf heute
NICHT anbietet (Luftfeuchtigkeit, Taupunkt, CAPE, Schneefallgrenze,
Niederschlagsart, Bewölkung gesamt/tief/mittel/hoch, Sonnenstunden, Luftdruck,
Nullgradgrenze, Schneehöhe, Neuschnee), fehlen **nicht**, weil der Katalog
keinen Stundenwert kennt. Sie fehlen, weil `compareHourlyMetricDefs.ts`
(Frontend) und `compare_hourly_metric_ids.py` (Backend) ein **eigenes,
bewusst disjunktes** Zehner-Vokabular pflegen (Kommentar in beiden Dateien:
„Eigenstaendiges Vokabular, kein Reuse"). Es gibt in diesem Ticket **keine**
Kategorie „technische Grenze, dem Nutzer begründet zeigen" — die einzige
Kategorie ist der Defekt selbst.

## Befund 2 — die Trip-Formatierung ist bereits generisch, Compare hat ihre eigene

`src/output/metric_format.py` (Issue #1214) stellt bereits produktweit
generische, katalog-getriebene Funktionen bereit:

- `format_value(metric_id, value)` — Rundung/Einheit aus `metric.decimals`/`unit`/`display_unit`
- `severity_for(metric_id, value)` — Ampel aus `metric.display_thresholds`
- `label(metric_id, style)` — `label_de`/`compact_label`/`col_label`

Compare (`compare_html.py:103-230`) hat für die 9 Stunden-Metriken **eigene**
Formatier-/Ampel-Funktionen (`_fmt_deg`, `_fmt_kmh`, `_sev_temp`, `_sev_wind`,
…) — separate, aber inhaltlich meist redundante Logik zur bereits
existierenden generischen. Für 2 Enum-Typen (`thunder_level`, `precip_type`)
braucht es weiterhin Spezialfälle (wie beim Trip: `max_thunder()`,
`values[-1]`) — der Rest (Temperatur, Wind, Böen, Regen, UV, Regenwahrsch.,
Sicht, plus die 14 neuen: Feuchte, Taupunkt, CAPE, …) kann generisch über
`format_value`/`severity_for` laufen. Das **col_label** aus dem Katalog
(„Feels", „Gust", „Rain", „Thdr", „Rain%", „Visib", dazu neu „Humid",
„Cond°", „CAPE", „Cloud", „CldLow", …) deckt sich bereits mit der Umbenennung,
die #1401 A2b für die Übersichtstabelle vorsieht — konsistente Fortsetzung,
kein Stilbruch.

## Befund 3 — Windrichtungs-Merge ist bereits ein geteiltes Trip-Muster, keine Compare-Besonderheit

`compareHourlyMetricDefs.ts` behandelt `wind_dir_deg` heute als
Compare-Spezialfall („Merge-Signal", `defaultOff`). Das ist **kein
Sonderfall** — Trip hat exakt dieselbe Regel bereits produktiv:
`should_merge_wind_dir(dc)` in `email/helpers.py` und
`trip_report.py::_should_merge_wind_dir` (Windrichtung wird als Kompasstext in
die Wind-Zelle gemergt, wenn beide Metriken aktiv sind). Scheibe B muss diese
Regel nicht neu erfinden, nur mit derselben Semantik auf die
Compare-Auswahlliste anwenden.

## Befund 4 — der Reihenfolge-Baustein ist für alle drei Ausgaben BEREITS geteilt

Wichtigste Korrektur der Ticket-Prämisse: `CompareHourlyLayoutControls.svelte`
(`:144-153`) und `CompareOutlookLayoutControls.svelte` (`:152-161`) verwenden
schon heute **beide** denselben `WeatherV2Reihenfolge` (`shared/
weather-metrics-tab/WeatherV2Reihenfolge.svelte`, ADR-0024) für Sortieren +
„Aus" — geliefert mit #1361 Befund 4/5 (Übersicht + Stundenverlauf) bzw.
#1406 Scheibe A (Ausblick). Der PO-Wunsch „dasselbe Kombi-Element dreimal" ist
für den **Reihenfolge-Teil bereits erfüllt**. Was fehlt, ist ausschließlich die
**Grundauswahl** oben: die Übersicht (`WeatherMetricsTab.svelte:918-948`, #1411)
und der Ausblick (`CompareOutlookLayoutControls.svelte:111-140`, Scheibe A)
gruppieren bereits nach Katalog (`groupCompareCatalog()` +
`AggregationMetricRow`); der Stundenverlauf zeigt stattdessen weiterhin die
flache 10er-Liste über `{#each ALL_HOURLY_METRICS}` +
`ChannelToggle` (`CompareHourlyLayoutControls.svelte:113-120`).

**Vereinfachung gegenüber Übersicht/Ausblick:** Der Stundenverlauf hat keine
Mehrfach-Auswertung je Größe (kein „Max vs. Min" — ein Rohwert pro Stunde hat
nur eine Darstellung). `AggregationMetricRow`/`groupCompareCatalog` würde hier
**immer** den Ein-Options-Zweig nehmen (eine Checkbox je Katalog-Größe, kein
Mehrfachkästchen wie bei Temperatur im Ausblick) — die Umstellung ist also
strukturell **einfacher** als die des Ausblicks, nicht komplizierter.

## Weg von der Auswahl bis in die Mail (Datei:Zeile)

| Schritt | Datei:Zeile | Heute |
|---|---|---|
| Speicherfeld | `frontend/src/lib/components/compare/compareEditorSave.ts:131` → `display_config.hourly_metrics` | flache String-Liste im **Compare-eigenen** Vokabular (`temp_c`, `wind_kmh`, …) |
| Go-Persistenz | `internal/handler/config_merge.go` (generischer `map[string]interface{}`-Merge) | **kein** Go-Struct-Feld nötig — analog zu `outlook_metrics` (Scheibe A), da `hourly_metrics` unter `display_config` liegt |
| Auflösung | `src/output/renderers/compare_hourly_metric_ids.py::resolve_hourly_metrics` | mappt nur die 10 bekannten Keys; alles andere wird **sichtbar** verworfen (Log-Warnung, #1361 Befund 3 — kein stiller Fall mehr, aber eben nur für 10 von 24 möglichen) |
| HTML-Renderer | `src/output/renderers/email/compare_html.py:330-340` (`HOUR_METRICS`) + `:683-723` (`_visible_hour_metrics`, `_should_merge_wind_dir`) | fixe 9-Spalten-Liste |
| Klartext-Renderer | `src/output/renderers/comparison.py:220-274` | **liest dieselbe** `HOUR_METRICS`/`_visible_hour_metrics`-Quelle wie HTML (Import aus `compare_html.py`) — **kein** zweiter blinder Fleck wie bei früheren Scheiben, weil HTML und Klartext hier schon über eine gemeinsame Liste laufen |
| Telegram/SMS | `render_compare_telegram` (`comparison.py:551`) | kennt gar keinen Stundenverlauf — `hourly_metrics` erreicht nur die E-Mail (dokumentiert in `CompareHourlyLayoutControls.svelte:128-137`) |

**Wo heute still verworfen wird:** nicht beim Rendern (das ist seit #1361
Befund 3 sichtbar/geloggt), sondern **vorher** — der Nutzer sieht in der
Grundauswahl gar nicht erst die 14 fehlenden Größen. Kein Rendering-Bug,
ein Bedienflächen-Defekt.

## Speicherformat / Migration (Frage 5)

`hourly_metrics` liegt **nicht** im Zielformat. Anders als beim Ausblick
(`outlook_metrics`, bereits `[{metric_id, aggregation}]` seit #1361 Bef.2)
ist `hourly_metrics` eine flache Liste von **Compare-eigenen** Kurzkeys
(`temp_c`, `wind_chill_c`, `wind_kmh`, `gust_kmh`, `precip_mm`, `uv_index`,
`thunder_level`, `pop_pct`, `visibility_m`, `wind_dir_deg`) — weder
Katalog-IDs noch Renderer-Feldnamen direkt (Übersetzung heute über
`FRONTEND_TO_HOURLY_METRIC_ID`).

**Kein Datenmodell-Umbau nötig, keine Batch-Migration bestehender Datensätze
nötig** (belegt, nicht angenommen): Da die Auflösung bereits eine
Übersetzungstabelle ist (`FRONTEND_TO_HOURLY_METRIC_ID`, 10 Einträge), reicht
es, diese Tabelle zu erweitern statt zu ersetzen: die 10 alten Keys bleiben
als Alias auf ihre Katalog-ID bestehen (`temp_c`→`temperature`,
`wind_kmh`→`wind`, `wind_chill_c`→`wind_chill`, `gust_kmh`→`gust`,
`precip_mm`→`precipitation`, `uv_index`→`uv_index`, `thunder_level`→`thunder`,
`pop_pct`→`rain_probability`, `visibility_m`→`visibility`,
`wind_dir_deg`→`wind_direction`), und Katalog-IDs werden zusätzlich direkt
aufgelöst. Bestehende `hourly_metrics`-Werte laden unverändert (Read-Modify-
Write mit Merge automatisch erfüllt, weil nichts geschrieben werden muss) —
Neuauswahl liefert künftig Katalog-IDs. Damit entfällt der teuerste
befürchtete Posten (Go-Feld + Batch-Migration), genau wie schon beim Ausblick
in Scheibe A.

## LoC-Schätzung je Teil (Kernnetz, ohne Tests/Doku)

| Teil | Datei | Ungefähre Größenordnung |
|---|---|---|
| Backend-Resolver | `compare_hourly_metric_ids.py` (Nachfolger) | ~+50/−30 (Alias-Tabelle + generischer Katalog-Fallback) |
| HTML/Klartext-Renderer | `compare_html.py:103-230,330-340` | ~+50/−90 (generisches `format_value`/`severity_for` ersetzt Einzel-fmt/sev; Enum-Sonderfälle Thunder/PrecipType bleiben) — **eher Netto-Reduktion** |
| Frontend Grundauswahl | `CompareHourlyLayoutControls.svelte` | ~+45/−20 (Umstellung auf `groupCompareCatalog`, analog Scheibe A des Ausblicks, aber ohne Mehrfachzweig) |
| Frontend Alt-Vokabular | `compareHourlyMetricDefs.ts` (135 Zeilen) | entfällt fast vollständig; ~15–20 Zeilen wandern nach `compareMetricOrder.ts` (analog `materializeOutlookMetricKeys`/`toggleOutlookMetricKeyFromState`, die dort schon existieren) |
| Mail-Prüfer | `.claude/hooks/email_spec_validator.py:528-533` (`_HOUR_COLUMNS_V2`) | ~+15 (Allowlist um die ~14 neuen `col_label`-Werte erweitern) — **NICHT jetzt anfassen**, Parallel-Sitzung arbeitet am Prüfer |

**Summe grob 150–220 Kern-LoC** — passt in den 250er-Rahmen, wirkt der
Ticket-Einschätzung „mehrere Tage" entgegen, weil (a) kein Go-Eingriff, (b)
keine Datenmigration, (c) Formatierung bereits generisch vorhanden, (d) der
Reihenfolge-Baustein bereits geteilt ist. Übrig bleibt im Kern nur: Alias-
Erweiterung, generische Formatierung, Grundauswahl-Umstellung, Allowlist.

**Nicht weiter aufteilbar ohne stillen Verlust zu erzeugen** (Frage 6): jede
Zwischenstufe, die die Bedienfläche vor der Auflösung auf 24 Größen bringt
(oder umgekehrt), verletzt Invariante 2. Die Lieferung ist atomar — genau wie
im Ticket beschrieben.

## Mail-Wirkung (Frage 4)

**Ja, sichtbar.** Neue Spaltenköpfe (`col_label`): u.a. „Cond°" (Taupunkt),
„Cloud"/„CldLow"/„CldMid"/„CldHi", „Humid", „hPa" (Luftdruck), „SnowL",
„SnowH", „NewSn", „0°Line" — zusätzlich zu den 9 bestehenden. Reihenfolge
bleibt nutzerbestimmt (seit #1359/#1381 keine feste Vorgabe mehr).

**Betroffene Prüfer-Stelle (nur benennen, nicht ändern):**
`.claude/hooks/email_spec_validator.py:528-533`, Konstante
`_HOUR_COLUMNS_V2` — heute eine ALLOWLIST mit 16 Strings (10 alte + 6 neue aus
#1401 A2b-Übergang). Muss um die ~14 neuen `col_label`-Werte erweitert werden,
sonst lehnt der Prüfer jede Mail mit einer neu gewählten Stundengröße als
„unbekannte Spalte" ab — das Muster, das schon #1381/#1404/#1420 blockiert
hat. **Bewusst nicht in dieser Analyse verändert**, da eine parallele Sitzung
gerade an genau dieser Datei arbeitet (Auftrag des Team Leads).

Kein zweiter blinder Fleck HTML-vs-Klartext-Labels (Befund oben,
`comparison.py` liest dieselbe Quelle wie `compare_html.py`) — anders als in
früheren Scheiben, wo das eigens nachgewiesen werden musste.

## Trip-Wirkung / Full-Stack-Urteil (Frage 3, Risiken)

- **Kein Go-Eingriff** (Befund oben).
- **Trip-Mail unberührt**, sofern Compare weiterhin `format_value`/
  `severity_for` nur AUFRUFT statt die generischen Trip-Renderer-Funktionen
  (`dp_to_row`/`extract_hourly_rows` in `email/helpers.py`) direkt zu
  importieren und umzubauen — letzteres wäre eine Trip-Regressionsgefahr,
  weil diese Funktionen ein volles `UnifiedWeatherDisplayConfig`-Objekt
  erwarten (Trip-Datenmodell), das der Ortsvergleich nicht hat. **Empfehlung:**
  Compare behält eine eigene, schlanke Orchestrierung (flache Metrik-ID-Liste
  statt `dc.metrics`), ruft aber `format_value`/`severity_for` aus dem
  bereits geteilten `metric_format.py` auf — geteilt ist die Formel, nicht
  die Aufrufsignatur. Damit bleibt der Trip-Pfad unangetastet, Paritätstests
  (analog `test_trip_outlook_parity.py` aus Scheibe A) sollten trotzdem
  ergänzt werden.
- **Frontend ist Full-Stack, nicht Frontend-only** — anders als Scheibe A
  (Ausblick), weil hier zusätzlich der Backend-Resolver und der Mail-Prüfer
  zwingend mitgehen (Invariante 2).

## Überschneidung mit #1401 Scheibe B (Frage 7)

Keine Dateiüberschneidung: #1401 B betrifft `shared/alarme-tab/
compareMetricMapping.ts` und `alerts-tab/AlertMetricLevelTable.svelte`
(Alarm-Namen/-Umfang, andere Datenquelle: Tages-Schwellen statt Stundenwerte).
Ticket #1406 selbst ordnet die Alarm-Liste **Scheibe C** zu, nicht B.
**Empfehlung: sequentiell, wie im Ticket vorgesehen (B vor C), nicht
zusammenlegen** — unterschiedliche Renderer-Pfade, unterschiedliche
Katalog-Felder (`display_thresholds`/`sms_code` statt `dp_field`), keine
Synergie durch Parallelisierung, aber Kollisionsrisiko in `WeatherMetricsTab.
svelte`, falls doch parallel gebaut.

## Risiken (Zusammenfassung)

1. **Renderer-Commit-Gate #811** greift, sobald `compare_html.py` gestaged
   wird — Reihenfolge beachten: erst Mail-Prüfer-Erweiterung (fremde
   Sitzung) muss vorliegen, dann `briefing_mail_validator.py`/
   `email_spec_validator.py` grün, dann Commit.
2. **Koordination mit der Parallel-Sitzung am Mail-Prüfer** — nicht
   gleichzeitig an `_HOUR_COLUMNS_V2` schreiben; Merge-Konflikt sonst
   vorprogrammiert (dieselbe Konstante).
3. **Trip-Paritätstest fehlt noch** — sollte mit implementiert werden, sonst
   ist die Trip-Unberührtheit nur behauptet, nicht bewiesen (Lehre aus
   Scheibe A).
4. **open-meteo-Kontingent** (#1329) bei Staging-Mail-Nachweis — ein
   Testversand reicht, danach IMAP-Verifikation (siehe Referenz-Memory).
