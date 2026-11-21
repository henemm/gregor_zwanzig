# Inventar Metrik-Wissen ausserhalb des Python-Kerns (Go / Frontend / Hooks)

Stand: Repo-Checkout 2026-11-21, nur gelesen. Referenz-ID-Menge: `src/app/metric_catalog.py` (32 IDs: temperature, temperature_cold/_night/_day_low/_day_high, wind_chill(+_night/_day_low/_day_high), humidity, dewpoint, wind, gust, wind_direction, precipitation, rain_probability, confidence, thunder, cape, snowfall_limit, precip_type, cloud_total/low/mid/high, visibility, sunshine, uv_index, pressure, freezing_level, snow_depth, fresh_snow).

Spalte **Ziel**:
- **Katalog über API** = Wissen gehört in den Python-Katalog und soll vom Client über einen Endpunkt gelesen werden (Liste/Schwelle/Fähigkeit/Wort/Einheit nicht im Client führen).
- **Verarbeitungsmodul** = bleibt Code im jeweiligen Dienst (Schema/DTO, Validierung, Migration, Provider-Adapter), ggf. aber aus Katalog/generiertem Artefakt speisen.
- **erlaubte Test-Erwartung** = handgeschriebene Erwartung in einem Validator (zulässig, soll NICHT aus dem Produkt importiert werden).
- **tot/entfernen** = kein Produktaufrufer gefunden.
- **Demo** = Vorschau-/Designseite, kein Produktpfad.

Art-Kürzel: ID-Liste · Schwelle · Wortskala · Einheit · Fähigkeit · Default-Auswahl · Reihenfolge/Rang · Mapping · Vergleich(fester Wert) · Farbe/Icon · Label.

---

## 1. Go (`internal/`, `cmd/`, ohne `_test.go`)

| Datei:Zeile | Art | Inhalt kurz | Ziel |
|---|---|---|---|
| internal/model/trip.go:39-51 | ID-Liste (Alarm-Vokabular) | `AlertMetric`-Konstanten wind_gust, precipitation_sum, temperature_min/max, thunder_level, snow_line, temperature_change, wind_change, precipitation_change | Verarbeitungsmodul (Schema), Werte aus Katalog generieren |
| internal/model/trip.go:250-261 | Fähigkeit (alarmfähig) | `AlertableMetrics` = 6 Alarm-Metriken (wind_gust, precipitation_sum, temp_min/max, snow_line, thunder_level) | Katalog über API (bzw. generiertes Artefakt wie alert_metric_mapping) |
| internal/model/trip.go:263-277 | Schwelle + Einheit + Severity | `DefaultDeltaThreshold` 20 km/h, 10 mm, 5 °C, 5 °C, 1, 200 m; Kommentar „spiegelt Python default_change_threshold" (Handkopie) | Katalog über API / generiertes Artefakt |
| internal/model/trip.go:279-290 | Schwelle + Einheit (tot) | `DefaultAlertThreshold` 50 km/h, 20 mm, -5 °C, 35 °C, 1500 m; **kein Aufrufer** im Nicht-Test-Code | tot/entfernen |
| internal/model/trip.go:292-305 | Mapping (generiert) | `//go:embed alert_metric_mapping.generated.json` → `catalogIDToAlertMetrics` (Katalog-ID → AlertMetric) | Verarbeitungsmodul (bereits aus Python generiert, Paritäts-Ratsche) |
| internal/model/alert_metric_mapping.generated.json:1-23 | Mapping (generiert) | freezing_level/snowfall_limit→snow_line, gust→wind_gust, precipitation→precipitation_sum, temperature→min/max, temperature_cold→min, thunder→thunder_level | Verarbeitungsmodul (generiertes Artefakt, ok) |
| internal/model/trip.go:340-378 | Fähigkeit (Filter) | `ActiveAlertableMetricIDs` filtert enabled-Katalog-IDs über Mapping ∩ `AlertableMetrics` | Verarbeitungsmodul (Logik), Menge aus Katalog |
| internal/model/trip.go:390-428 | Schwelle (Erzeugung) | `SyncAlertRules`: erzeugt/migriert delta-Regeln je aktiver Metrik mit `DefaultDeltaThreshold` (Threshold/Unit/Severity) | Verarbeitungsmodul; Default-Werte aus Katalog |
| internal/store/trip.go:376-389 | Mapping (Alt-Vokabular) | `legacyAlertLevelKeys` temp_max_c→temperature_max, gust_max_kmh→wind_gust, …, snow_line→freezing_level, wind_chill_min_c→"" („deckungsgleich mit Python `_ALT_ALERT_LEVEL_KEYS`") | Verarbeitungsmodul (Migration), Handkopie mit Python-Pendant |
| internal/store/trip.go:311-317 | Migration | `migrateMetricAlertLevels` (snow_line→freezing_level im Go-Schreibpfad) | Verarbeitungsmodul |
| internal/handler/vergleich_grundauswahl.go:11-18 | ID-Liste + Mapping (Aggregation) | `vergleichAggregation` 23 Katalog-IDs → max/min/sum/avg (Drift-Wächter gegen Python) | Katalog über API (`/api/compare/metrics` liefert `metric_id`+`aggregation` bereits) |
| internal/handler/vergleich_grundauswahl.go:26-48 | Default-Auswahl | baut `active_metrics` aus Vorlage nur für IDs in `vergleichAggregation` | Verarbeitungsmodul (Logik), Tabelle aus Katalog |
| internal/handler/ampel.go:13-16 | Farb-Stufen | `ampelUnten`/`ampelOben`/`ampelRang`/`ampelAlarmAb` (generische Ampel, nicht metrikspezifisch) | Verarbeitungsmodul (Validierung, Spiegel `app.ampel.validate_ampel`) |
| internal/handler/ampel.go:18-20 | Fähigkeit (metrikspez.) | `ampelAlarmAbGewitter` = never/orange/red (Gewitter nie gelb) | Verarbeitungsmodul; Regel könnte aus Katalog (`allowed_alarm_ab` je Metrik) kommen |
| internal/handler/ampel.go:22-26 | Wortskala/Token | `ampelWindModi` aus/gegenwind/sektoren, `ampelWindSektoren` N…NW | Verarbeitungsmodul (Protokoll-Token), Pendant Python `services.windrichtung` |
| internal/handler/ampel.go:37 | Vergleich (ID) | `if mid != "wind_direction"` → modus/sektoren nur für Windrichtung | Verarbeitungsmodul; Fähigkeit „hat Sektoren" aus Katalog |
| internal/handler/ampel.go:106 | Vergleich (ID) | `mid == "thunder"` → Gewitter-alarm_ab-Menge | Verarbeitungsmodul; aus Katalog-Fähigkeit |
| internal/handler/ampel.go:135-146,174 | Wortskala (Gewitter) | `ampelGewitterGueltig`: Schlüssel `mittel`/`hoch`, hoch ≥ orange, hoch ≥ mittel | Verarbeitungsmodul (Spiegel Python) |
| internal/model/forecast.go:8-15 | Wortskala (Gewitter) | `ThunderLevel` NONE/MED/HIGH | Verarbeitungsmodul (DTO) |
| internal/provider/openmeteo/models.go:50-58 | Schwelle (WMO) | `ThunderCodes` {95,96,99} → ThunderHigh, sonst None (keine MED-Stufe) | Verarbeitungsmodul (Provider-Adapter); Abweichung zur Python-Gewitterlogik prüfen |
| internal/provider/openmeteo/models.go:60-80 | ID-Liste (Provider) | `HourlyParams` OpenMeteo-Parameternamen (temperature_2m … freezing_level_height) | Verarbeitungsmodul (Provider) |
| internal/provider/openmeteo/provider.go:110-116 | Einheit | `setUnits`: kmh, celsius, mm | Verarbeitungsmodul (Provider) |
| internal/model/segment.go:5-26 | Einheit (DTO-Felder) | Segment-Summary-Felder mit Einheit im Namen (gust_max_kmh, visibility_min_m, cape_max_jkg, uv_index_max …) | Verarbeitungsmodul (DTO) |
| internal/model/metric_preset.go:24-29 | Schema | `DisplayMetric{MetricID, Enabled, UseFriendlyFormat}` (keine Liste) | Verarbeitungsmodul |
| internal/handler/metric_preset.go:99-128 | Default-Reihenfolge | `displayConfigAusVorlage` setzt order/bucket "primary" je aktiver Vorlagen-Metrik (kein Metrikwissen) | Verarbeitungsmodul |
| internal/router/router.go:280-285,323-328 | Endpunkt-Proxy | `/api/metrics`, `/api/alert-metric-channel-keys`, `/api/templates`, `/api/sms-symbols`, `/api/compare/metrics`, `/api/_validator/*` → Python | Katalog über API (bestehend) |

Go-Zeilen: **25**

---

## 2. Frontend (`frontend/src/`, ohne `*.test.ts`/`*.spec.ts`/`__tests__`/`e2e/`)

| Datei:Zeile | Art | Inhalt kurz | Ziel |
|---|---|---|---|
| lib/components/trip-detail/metricsEditor.ts:24-39 | Wortskala + Fähigkeit | `INDICATOR_MAP` 12 IDs mit deutschen Wortskalen (wind 'ruhig / mäßig / stark / sturm', gust 'harmlos/…/orkan', thunder, cape, cloud_*, sunshine, rain_probability, precipitation, wind_direction); widerspricht laut Kommentar `has_friendly_format` des Backends | Katalog über API (`has_friendly_format`/`format_modes`/Wortskala je Sprache) |
| lib/components/trip-detail/metricsEditor.ts:62-64 | Fähigkeit | `indicatorCapable(id)` = `id in INDICATOR_MAP`; benutzt von WeatherMetricsTab:1774, OutputLayoutEditor:24/216/234, WeatherV2Reihenfolge:84 (Default `modeCapable`), TablePreview:73/109, BucketSection:91, WeatherConfigDialog:193 | Katalog über API |
| lib/components/trip-detail/metricsEditor.ts:42-56 | Reihenfolge + Label | `CATEGORY_ORDER` + `CATEGORY_LABELS` (deutsche Literale, nicht i18n) | Katalog über API (Kategorie-Rang + Label je Sprache) |
| lib/components/trip-detail/metricsEditor.ts:208-215 | Rang | `METRIC_PRIORITY` 24 IDs (95…10), „konsistent mit Backend channel_layout.METRIC_PRIORITY" (Handkopie) | Katalog über API |
| lib/components/trip-detail/metricsEditor.ts:218 | Konstante | `PRIMARY_SLOTS = 5` (Spiegel `_PRIMARY_SLOTS`) | Katalog über API / Verarbeitungsmodul (Server) |
| lib/components/trip-detail/metricsEditor.ts:316-323 | Mapping (Ableitung) | `DERIVED_METRIC_RULES` temperature_night/day_low/day_high→temperature, wind_chill_*→wind_chill (Spiegel `loader._DERIVED_METRIC_RULES`) | Katalog über API |
| lib/components/shared/weather-metrics-tab/outlookFriendlyCapability.ts:16-34 | Fähigkeit | `OUTLOOK_FRIENDLY_CAPABLE` 10 IDs (Frontend-Hälfte von Python `OUTLOOK_FRIENDLY_CAPABLE`, Drift-Test liest Live-Backend) | Katalog über API |
| lib/components/compare/hourlyFriendlyMap.ts:17-19,26-35 | Fähigkeit (delegiert) | `hourlyFriendlyCapable` = `outlookFriendlyCapable` (keine eigene Liste, aber erbt Handkopie) | Katalog über API (via Quelle oben) |
| lib/utils/alertMetricCatalogIds.ts:11-29 | Mapping | `ALERT_METRIC_TO_CATALOG_ID` AlertMetric→Katalog-ID; **nur von Tests importiert** | tot/entfernen (oder Katalog über API) |
| lib/utils/alertMetricCatalogIds.ts:41-45 | ID-Liste | `NON_CATALOG_ALERT_METRICS` temperature_change/wind_change/precipitation_change; nur Tests | tot/entfernen |
| lib/utils/stageRisk.ts:20-25 | Farbe (kein Metrikwissen) | `riskToPill` red/yellow/green → bad/warn/good; Risiko kommt fertig von `/api/trips/{id}/stages/weather` | Verarbeitungsmodul (Anzeige, ok) |
| lib/utils/cockpitHelpers568.ts:54-120 | — | geprüft: nur `display_config.metrics.length`/`active_metrics` als Setup-Signal, kein Metrikwissen | Verarbeitungsmodul (ok) |
| lib/components/shared/WeatherMetricsTab.svelte:308 | ID-Liste + Fähigkeit | `SMS_THRESHOLD_METRIC_IDS` precipitation, rain_probability, wind, gust, thunder, snow_depth, snowfall_limit | Katalog über API |
| lib/components/shared/WeatherMetricsTab.svelte:1792-1866 | Schwelle (Stufen) | feste SMS-Schwellen-Zeilen: wind `stufen(15,20,30)`, gust `(30,40,50)`, precipitation `(0.3,0.8,1.5)`, rain_probability `(25,40,60)`, snow_depth `(5,10,20)`, snowfall_limit `(2000,1500,1000)`; thunder aus Katalog | Katalog über API |
| lib/components/shared/WeatherMetricsTab.svelte:1870-1926 | ID-Liste | feste Symbolzeilen temperature, temperature_night, wind_chill, temperature_day_low/high, wind_chill_day_low/high, wind_chill_night | Katalog über API |
| lib/components/shared/WeatherMetricsTab.svelte:462-463 | Reihenfolge | Kategorien nach `CATEGORY_ORDER` | Katalog über API |
| lib/components/shared/wetter-tab/ampelModell.ts:22-39,79-102 | Fähigkeit (aus API) | `MetrikEigenschaften` aus `/api/metrics` (group, alertable, is_precursor, allowed_sides, display_only, unit, threshold_unit, labels, trip_default_rank, rang) — Vorbild | Katalog über API (bestehend, gut) |
| lib/components/shared/wetter-tab/ampelModell.ts:49,53 | Fähigkeit (ID-spez.) | `GEWITTER='thunder'`, `ALARM_AB_GEWITTER` never/orange/red | Katalog über API (zulässige alarm_ab je Metrik) |
| lib/components/shared/wetter-tab/ampelModell.ts:50-52,54 | Farb-Stufen | `UNTEN/OBEN/ALARM_AB/RANG` (generische Ampel) | Verarbeitungsmodul (Spiegel validate_ampel, ok) |
| lib/components/shared/wetter-tab/ampelModell.ts:56-57,242 | Wortskala/Token + Vergleich(ID) | `WIND_MODI`, `WIND_SEKTOREN`; `mid !== 'wind_direction'` | Verarbeitungsmodul; Fähigkeit aus Katalog |
| lib/components/shared/wetter-tab/ampelModell.ts:59 | Reihenfolge | `GRUPPEN_FOLGE` temperature, wind, precip_thunder, sky_visibility, snow_height | Katalog über API (Gruppen-Rang) |
| lib/components/shared/wetter-tab/ampelModell.ts:264-266 | Farbe (Gewitter) | `gewitterFarben`: mittel gelb/orange/rot, hoch orange/rot | Katalog über API |
| lib/components/shared/wetter-tab/ampelModell.ts:269-272 | Fähigkeit | `alarmAbOptionen`: thunder ohne gelb | Katalog über API |
| lib/components/shared/wetter-tab/ampelModell.ts:306-319 | ID-Liste | `HINWEIS_IDS` 12 IDs mit eigenem Untertitel (`wetter.hinweis.<id>`) | Katalog über API (Hinweis je Metrik/Sprache) |
| lib/components/shared/wetter-tab/ampelModell.ts:583 | Vergleich (ID) | thunder + alarm_ab yellow → orange | Katalog über API |
| lib/components/shared/wetter-tab/ampelLeiste.ts:61-66 | Farbe (Default) | Gewitter-Leiste: kein=grün, mittel Default gelb, hoch Default orange | Katalog über API |
| lib/components/organisms/wetter-tab/GrenzenEditor.svelte:28 | Farb-Stufen | `FOLGE` lower/upper Farbfolge (generisch) | Verarbeitungsmodul (ok) |
| lib/components/organisms/wetter-tab/AlarmAbKopf.svelte:17 | Farb-Stufen | `STUFEN` never/yellow/orange/red (generisch) | Verarbeitungsmodul (ok) |
| lib/components/alerts-tab/alarmAbAnzeige.ts:15 | ID-Liste | `AMPEL_ZEILEN` gust, precipitation, temperature, thunder | Katalog über API |
| lib/components/alerts-tab/alarmAbAnzeige.ts:30-41 | Mapping | `AMPEL_KATALOG_ID` generiert + Handergänzung (precipitation_change→precipitation, temperature_change→temperature, wind_change→wind, visibility, fresh_snow) | Katalog über API |
| lib/components/alerts-tab/alarmAbAnzeige.ts:44-54 | Fähigkeit | `D4_METRIKEN` (freezing_level, snow_line, thunder_onset, precipitation_heavy_onset), `VORBOTEN` {humidity}, `KEIN_AUSLOESER` {cape} | Katalog über API (`is_precursor`/`alertable` liegen schon in `/api/metrics`) |
| lib/components/alerts-tab/alarmAbAnzeige.ts:57 | Mapping | `PROFIL_ZU_VORLAGE` summer_trekking→alpen-trekking (Spiegel `app.ampel._PROFIL_ZU_VORLAGE`) | Katalog über API |
| lib/utils/alertMetricLabels.ts:32-61 | Einheit + Vergleich | `ALERT_METRIC_LABELS` je AlertMetric Einheit (km/h, mm, °C, cm, J/kg, m, %, h) und Vergleichszeichen (> ≥ <) | Katalog über API (`unit`, `cmp` liefert `/api/metrics` bereits) |
| lib/components/alerts-tab/alertMetricTable.ts:23-43 | Schwelle | `METRIC_DEFAULTS` wind_gust 50, precipitation_sum 10, thunder_level 1, snow_line 2000, temp_min -5, temp_max 35, temperature_change 10, wind_change 20, precipitation_change 5, fresh_snow 8, cape 600, visibility 1000, humidity 15, freezing_level 200, onset 1 | Katalog über API |
| lib/components/alerts-tab/alertMetricTable.ts:21,61-82,113-117 | Schwelle (generiert) | Preset-Schwellen entspannt/standard/sensibel + `THRESHOLD_CROSSING_METRICS` aus `generated/alertPresetThresholds.generated.json` | Katalog über API (heute generierte Kopie) |
| lib/components/alerts-tab/alertMetricTable.ts:91-108 | ID-Liste + Reihenfolge | `ALERTABLE_METRICS` 15 AlertMetrics; genutzt von alarme-tab/tripAlertMetricsFromCatalog.ts:72, activeAlertMetricsFromCatalog.ts:31 | Katalog über API |
| lib/components/alerts-tab/alertMetricTable.ts:119-137 | Einheit | `_METRIC_UNITS` je AlertMetric (zweite Einheitentabelle neben alertMetricLabels.ts) | Katalog über API |
| lib/components/alerts-tab/alertPreviewHelpers.ts:11-32 | Mapping + Richtung | `METRIC_MAP` AlertMetric → Summary-Key (gust_max_kmh …) + direction above/below/increase | Katalog über API |
| lib/components/alerts-tab/alertPreviewHelpers.ts:120-133 | Schwelle | `vergleichAlarmRegeln` setzt `threshold: METRIC_DEFAULTS[m]` | Katalog über API |
| lib/components/molecules/AlertRow.svelte:53-56 | Farbe | `TONE_MAP` thunder/thunder_level → bad, Rest warn | Katalog über API (oder Server liefert Ton) |
| lib/components/molecules/AlertRow.svelte:60-77 | Icon | `KIND_MAP` Alarmart → WIcon (wind/rain/snow/sun/thunder) | Katalog über API (Icon-Kind je Metrik) |
| lib/types.ts:87-106 | ID-Liste (Typ) | `AlertMetric`-Union 17 Werte | Verarbeitungsmodul (Typ), aus Katalog generieren |
| lib/components/shared/weather-metrics-tab/compareMetricOrder.ts:38-44 | Default-Auswahl | `DEFAULT_OUTLOOK_METRIC_KEYS` temperature, precipitation, rain_probability, wind, gust, thunder (Spiegel email/outlook.py) | Katalog über API |
| lib/components/shared/mailInhaltKonstanten.ts:7-12 | Default-Auswahl | `DEFAULT_DAILY_SUMMARY_METRICS` precipitation, wind, visibility, thunder | Katalog über API |
| lib/components/compare/CompareHourlyLayoutControls.svelte:114-117 | Reihenfolge | `HOURLY_DEFAULT_FOLGE` 9 IDs (Spiegel `HOURLY_DEFAULT_METRIC_IDS`); Mitgliedschaft aus Katalog `hourlyDefault` | Katalog über API (Rang mitliefern) |
| lib/utils/weatherUtils.ts:28-55 | Vergleich (fest) | `wmoToWIconKind`: WMO-Bereiche, `cloudPct > 50`, `dni > 500` → Icon (genutzt von StageDetailRow.svelte:126) | Verarbeitungsmodul (Anzeige) oder Server liefert Icon |
| lib/utils/weatherEmoji.ts:1-46 | Vergleich (fest) | WMO→Emoji, cloud <20/<50/<80, dni >500/>200/>50 — **kein Importeur** | tot/entfernen |
| lib/components/shared/wetter-tab/corridorEditorState.ts:46-52 | Label | `ROUTE_ZEILEN_TEXT` wind_gust, precipitation_sum, temp_min/max, snow_line → i18n-Schlüssel | Katalog über API |
| lib/components/shared/wetter-tab/corridorEditorState.ts:75-87 | Einheit + Skala + Schwelle | `ROUTE_METRIC_DEFS` wind_gust km/h [0,120] max 70; precipitation_sum mm/h [0,20] max 5; temp_min -5; temp_max 28; snow_line m [500,3000] min 1500 | Katalog über API |
| lib/components/shared/wetter-tab/corridorEditorState.ts:145-150 | Mapping (generiert+Filter) | `FRONTEND_EXCLUDED_CATALOG_IDS` {temperature_cold, thunder}, `ROUTE_CORRIDOR_CATALOG_IDS` aus generated mapping | Verarbeitungsmodul (generiert), Ausnahme-Filter in Katalog |
| lib/components/shared/wetter-tab/corridorEditorState.ts:165-170 | Schwelle | `percentBoundToOrdinal` ≤33 NONE, ≤66 MED, sonst HIGH (Gewitter-Migration) | Verarbeitungsmodul (Migration) |
| lib/components/shared/wetter-tab/corridorEditorState.ts:324-333 | Fähigkeit | `TRIP_SUM_METRICS_WITHOUT_MARK` precipitation_sum, snow_new_sum_cm, sunny_hours_h → `supportsMark` | Katalog über API |
| lib/components/shared/wetter-tab/corridorEditorState.ts:445-451 | Wortskala | `ORDINAL_ENUM` NONE/LOW/MED/HIGH | Katalog über API (`ordinalLabels`) |
| lib/components/shared/wetter-tab/corridorEditorState.ts:463-496 | Schwelle (Default) | `_COMPARE_DEFAULTS` 25 Summary-Keys mit defaultMin/Max (temp_max_c 15-35, gust_max_kmh 70, visibility_min_m 2000-10000, uv_index_max 8 …) | Katalog über API |
| lib/components/shared/wetter-tab/corridorEditorState.ts:512-522 | ID-Liste + Reihenfolge | `COMPARE_METRIC_KEYS` 25 Summary-Keys in CV2-Folge (Spiegel compare_html `CV2_METRICS`) | Katalog über API |
| lib/components/shared/wetter-tab/corridorEditorState.ts:537-556 | Default-Auswahl + Label | `PROFIL_METRIK_TEXT`, `PROFILE_METRICS_WITH_SCALES` je Profil (WINTERSPORT, ALPINE_TOURING, SUMMER_TREKKING, ALLGEMEIN) | Katalog über API |
| lib/components/shared/wetter-tab/corridorEditorState.ts:558-579 | Schwelle (Default) | `IDEAL_DEFAULTS` je Profil (wind_max_kmh 0-40/50/35, precip_sum_mm 0-3/5, thunder max NONE, uv 0-8 …) | Katalog über API |
| lib/components/shared/wetter-tab/compareMetricCatalogLoader.ts:42 | Fähigkeit | `_COMPARE_RANGE_UNSUPPORTED` precip_type_dominant, wind_direction_deg (kein Von/Bis) | Katalog über API |
| lib/components/shared/wetter-tab/compareMetricCatalogLoader.ts:224-234,312-318 | Wortskala (aus API) | Gewitter-Schwellenstufen aus `ordinalLabels` des Katalogeintrags `thunder_level_max` (Schlüssel fest verdrahtet) | Katalog über API (bestehend; Key-Literal ok) |
| lib/components/shared/layout-tab/ltIdealRange.ts:22-33 | Vergleich | `isIdealGood(value, range, fallbackGood)` — **kein Aufrufer** | tot/entfernen |
| lib/components/trip-detail/StageDetailRow.svelte:126-134 | Einheit + Vergleich | feste Anzeige `°C`, Wind (i18n mit km/h), `precip_mm > 0`; WMO-Icon | Verarbeitungsmodul (Anzeige); Einheit aus Katalog wünschenswert |
| routes/_home/cockpitHelpers.ts:111-115 | Einheit + Vergleich | Etappen-Kurztext `°C`, `Wind … km/h` (nicht i18n), `precip_mm > 0`, `toFixed(1)` | Katalog über API (Einheit/Dezimalen) |
| routes/account/+page.server.ts:7-15 | Default-Auswahl | `FALLBACK_TEMPLATES` 7 Vorlagen mit Metrik-ID-Listen (wenn `/api/templates` fehlt) | Katalog über API (Fallback entfernen) |
| lib/generated/alertMetricMapping.generated.json | Mapping (generiert) | Kopie des Go-Artefakts (Katalog-ID → AlertMetric) | Verarbeitungsmodul (generiert, Paritäts-Ratsche) |
| lib/generated/alertPresetThresholds.generated.json | Schwelle (generiert) | Preset-Schwellen je AlertMetric aus `services/alert_preset.py` | Katalog über API (statt eingecheckter Kopie) |
| lib/i18n/messages/de/wetter.json:48-52,57-68 (+en) | Label/Hinweis | `wetter.gruppe.*` (5 Gruppen), `wetter.hinweis.<id>` (12 Metriken, z. B. „Mittelwind", „m über höchster Stelle") | Katalog über API (Metrik-Texte je Sprache) oder i18n bleibt, Schlüssel aus Katalog |
| lib/i18n/messages/de/wertebereiche.json:27-31,53-59,65-68,83-89 (+en) | Label + Einheit + Wortskala | Kategorien, SMS-Schwellen-Labels mit Einheit „Wind (km/h)", Gewitterstufen kein/leicht/mittel/hoch, Symbolzeilen-Namen Temperaturfamilie | Katalog über API |
| lib/i18n/messages/de/alarme.json (`alarme.metrik.*`, 11 Schlüssel) | Label | Namen der Alarm-Metriken | Katalog über API (`alert_label`/`alert_label_en` liefert `/api/metrics` bereits) |
| lib/i18n/messages/de/layout.json (`layout.korridor_zeile/hinweis`, `layout.profil_metrik`) | Label | Korridor-/Profil-Metriknamen | Katalog über API |
| routes/_design-system/einstelltabelle/beispieldaten.ts:1-… | Demo | Beispielzeilen mit Metriken/Formen je Stelle (Mockup) | Demo |
| routes/_design/+page.svelte:143-221, routes/_design-system/+page.svelte:105,126,691 | Demo | Dot/WIcon-Töne thunder/wind, Beispiel-AlertRow | Demo |

Frontend-Zeilen: **68**

---

## 3. Hooks / Validatoren (`.claude/hooks/`)

| Datei:Zeile | Art | Inhalt kurz | Ziel |
|---|---|---|---|
| _soll_aus_konfiguration.py:73,242 | **Produkt-Import** (Mapping) | `from app.loader import _DERIVED_METRIC_RULES` → `_ELTERN` | Finding: durch handgeschriebene Erwartung ersetzen |
| _soll_aus_konfiguration.py:74-76,90,98,106-110 | **Produkt-Import** (Register) | `_METRICS`, `_REG` (col_label, label, selectable, trip_default_rank, format_modes, default_format_mode) → `_TRIP_STANDARD`, `ALLE_KUERZEL`, `_ASCII_KUERZEL` | Finding (Register-Lesen ist im Docstring als „statisch" deklariert; Fähigkeitsfelder sind Produktwissen) |
| _soll_aus_konfiguration.py:75,358-377,738 | **Produkt-Import** (Fähigkeit) | `AMPEL_METRIC_IDS` entscheidet erwartete Zellform (Ampelpunkt vs. Wort/Zahl) | Finding → handgeschriebene Liste (wind, gust, precipitation, rain_probability) |
| _soll_aus_konfiguration.py:75,382-390 | **Produkt-Import** (Fähigkeit) | `OUTLOOK_FRIENDLY_CAPABLE` entscheidet, ob Ausblick Einfach-Form erwarten darf | Finding → handgeschriebene Erwartung |
| _soll_aus_konfiguration.py:75-76,255-262 | **Produkt-Import** (Fähigkeit/Default) | `zwei_formen_stellen(mid)`, `standard_form(mid)` → Soll-Form je Stelle | Finding (Spiegel-Test: prüft Produkt gegen sich selbst) |
| _soll_aus_konfiguration.py:75,398,630 | Produkt-Import (Label) | `aggregation_label` | erlaubt-nah (Text aus Katalog, kein Verhalten) – beobachten |
| _soll_aus_konfiguration.py:79-82,698,714-722 | **Produkt-Import** (ID-Listen) | `FRONTEND_TO_HOURLY_METRIC_ID`, `HOURLY_DEFAULT_METRIC_IDS`, `HOURLY_EXCLUDED_METRIC_IDS`, `HOURLY_MERGE_ONLY_METRIC_IDS` → Soll-Stundenspalten Orte | Finding |
| _soll_aus_konfiguration.py:83,412-422 | **Produkt-Import** (Rang) | `METRIC_PRIORITY`, `_PRIMARY_SLOTS` → erwartete Bucket-Zuordnung | Finding |
| _soll_aus_konfiguration.py:84,213,609-644 | **Produkt-Import** (Katalog-Tabelle) | `COMPARE_METRIC_CATALOG` → wählbare Orte-Zeilen, Labels, Grundauswahl | Finding |
| _soll_aus_konfiguration.py:85-86,326,366,594,872 | **Produkt-Import** (ID-Listen) | `_PILL_CATALOG_ORDER`, `NO_HOURLY_COLUMN_METRIC_IDS` | Finding |
| _soll_aus_konfiguration.py:88,802-804 | **Produkt-Import** (Schwellen) | `AMPEL_TEMPLATES`, `DEFAULT_TEMPLATE` → `ampel_grenzen()` Soll-Grenzen je Metrik | Finding (Schwellen-Soll aus Produkt) |
| _soll_aus_konfiguration.py:486-497,510-526,540 | Produkt-Import (Resolver, bewusst) | `services.channel_list_resolver.grundauswahl`, `services.placements.*`, `load_trip_from_dict`, `trip_enabled_reports`, `resolve_preset_slots` (Docstring: Spec-Ausnahme für Ausblick-Regel) | Finding (als Ausnahme dokumentiert; prüfen ob noch nötig) |
| _soll_aus_konfiguration.py:891-893 | **Produkt-Import** (Reihenfolge) | `compare_html.CV2_ZEILEN` → Standardfolge Vergleichstabelle | Finding |
| _soll_aus_konfiguration.py:1050-1058 | Produkt-Import (Farben) | `design_tokens._TONE_CSS`, `helpers._AMPEL_DOT_COLORS` → Farbe→Stufe beim Parsen | Finding-nah (Decoder; besser hand-codierte Hex-Tabelle) |
| _soll_aus_konfiguration.py:94 | Hand-Erwartung (Default-Auswahl) | `_FEST` 6 feste Ausblick-Spalten | erlaubte Test-Erwartung |
| _soll_aus_konfiguration.py:100,740 | Hand-Erwartung (Fähigkeit) | `_ROH_WORT` {thunder, precip_type} | erlaubte Test-Erwartung |
| _soll_aus_konfiguration.py:317-318,326,366,372 | Hand-Erwartung (Vergleich ID) | Sonderfälle wind/wind_direction (Merge), precip_type, thunder | erlaubte Test-Erwartung |
| _soll_aus_konfiguration.py:791-793 | Hand-Erwartung | `_PROFIL_VORLAGE` summer_trekking→alpen-trekking, `_STUFEN` green…red | erlaubte Test-Erwartung |
| _soll_aus_konfiguration.py:808-830 | Hand-Erwartung (Schwellen-Logik) | `ampel_stufe` oben `>=`, unten `<`, schärfere Seite gewinnt; `ampel_erlaubt` Rundungstoleranz | erlaubte Test-Erwartung (Grenzwerte selbst aber aus Produkt, s. o.) |
| _soll_aus_konfiguration.py:838-845,860-867 | Hand-Erwartung (Wort/Label) | `_KACHEL_SCHLUESSEL` Kacheltexte je Metrik; Kachel-Erkennung wind/gust/uv_index/wind_chill/cloud_total/temperature | erlaubte Test-Erwartung (liest i18n-Katalog `t()`) |
| _soll_aus_konfiguration.py:907 | Hand-Erwartung (Fähigkeit) | `_ORTE_AMPEL` temperature, wind, gust, precipitation, rain_probability, uv_index | erlaubte Test-Erwartung |
| email_spec_validator.py:582-583,612,753-755,790-791 | Produkt-Import (Register) | `get_metric(...).col_label/label(lang)`, `aggregation_label` → Spalten-Allowlist, Zeilen-Labels, Ausnahmemenge | Finding-nah (Label-Ableitung, im Kommentar begründet) |
| email_spec_validator.py:586-588,611-615 | **Produkt-Import** (ID-Listen) | `HOURLY_MERGE_ONLY_METRIC_IDS`, `hourly_selectable_metric_ids()` → `_HOUR_VALUE_COLUMN_LABELS` | Finding |
| email_spec_validator.py:1171-1173 (+1135,1178,1311-1336,1405,1453,1635-1636,1697,1761,1796,1942-1959) | Produkt-Import (transitiv) | `_soll_aus_konfiguration` (lazy) inkl. `ALLE_KUERZEL`, `_REG` | Finding (erbt alle Imports oben) |
| email_spec_validator.py:705-746 | Hand-Erwartung (Format/Einheit/Plausibilität) | `_OVERVIEW_METRIC_SPEC` Regex + Wertebereich je Metrik (°C −40..55, km/h 0..250/300, % 0..100, hPa 500..1085 …) | erlaubte Test-Erwartung |
| briefing_mail_validator.py:49,382-396 | Hand-Erwartung (Toleranz) | `_WIND_TOL = 3` km/h, Wind-Max-Regex | erlaubte Test-Erwartung |
| briefing_mail_validator.py:700-703 (+709,800,850,875,909,984,1158,1182) | Produkt-Import (transitiv) | `_soll_aus_konfiguration` (lazy) inkl. `_REG`, `_ASCII_KUERZEL` | Finding (erbt Imports) |
| briefing_mail_validator.py:1137,1182 | Hand-Erwartung (Fähigkeit) | `_AMPEL_SPALTEN` wind, gust, precipitation, rain_probability | erlaubte Test-Erwartung |
| radar_alert_mail_validator.py:40-48 | Hand-Erwartung (Wortskala) | `_INTENSITY_LABELS` Leichter/Mäßiger/Starker Regen, Starker Hagel, Gewitter | erlaubte Test-Erwartung |
| official_alert_mail_validator.py:110-113 | Hand-Erwartung (ID-Liste Gefahren) | `_OTHER_HAZARD_KEYS` (keine Wettermetriken, Gefahrenarten) | erlaubte Test-Erwartung |

Hooks-Zeilen: **30** (davon 15 Produkt-Import-Findings bzw. finding-nah, 13 erlaubte Hand-Erwartungen, 2 transitive Import-Ketten)

---

## 4. Katalog-Endpunkt heute

Es gibt bereits mehrere read-only Katalog-Endpunkte; alle laufen über den Go-Proxy (`internal/router/router.go`) zum Python-Kern, ohne `user_id`-Bezug:

| Endpunkt (Go → Python) | Python-Quelle | Liefert heute | Frontend-Leser |
|---|---|---|---|
| `GET /api/metrics` → `/metrics` (router.go:280) | api/routers/config.py:110-178 `get_metrics()` | je Kategorie: id, label/label_de/label_en, alert_label(_en), unit (Anzeige), threshold_unit, category, default_enabled, trip_default_enabled, trip_default_rank, **has_friendly_format**, **sms_format_capable**, format_modes, default_format_mode, col_label, **sms_code**, **decimals**, **cmp**, change_alert_metric, aggregations[{id,label,label_en,alert_metric}], plus `reiter_wetter_eigenschaften`: group, **alertable**, is_precursor, allowed_sides, display_only, rang | WeatherMetricsTab.svelte:549/654, wetterTabLaden.ts:122 (→ ampelModell `eigenschaftenAusKatalog`), compareMetricCatalogLoader.ts:273, TripNewEditor.svelte:158, WeatherConfigDialog.svelte:94, routes/trips/[id]/+page.server.ts:29 |
| `GET /api/compare/metrics?lang=` (router.go:323) | api/routers/compare.py:11 → `output/renderers/compare_metric_catalog.get_compare_metric_catalog` | Orte-Zeilen: key, metric_id, aggregation, kind/ordinalLabels/rangeMin/Max, label, col_label, sms_code, kuerzel_metric_id, aggregation_label, alertMetric, **alarmCapable**, **hourlySelectable**(+Reason), **hourlyDefault**, **hourlyMergeOnly**, hourly_legacy_keys | compareMetricCatalogLoader.ts:102 |
| `GET /api/templates` (router.go:283) | config.py:25 `get_all_templates()` + `AMPEL_TEMPLATES` | Vorlagen inkl. `ampel` (Grenzen je Metrik, Gewitter, alarm_ab) | wetterTabLaden.ts:123, WeatherMetricsTab.svelte:550, HubUebersicht.svelte:73, HubOverview.svelte:59, alarmAbAnzeige.ts:92, WeatherConfigDialog.svelte:95, account/+page.server.ts:27 (mit Hand-Fallback) |
| `GET /api/sms-symbols` (router.go:285) | config.py:61 | metric_id → sms_symbols, Gefahren-Kürzel | WeatherMetricsTab.svelte:542, OutlookLayoutControls, CompareHourlyLayoutControls, kuerzelMarken.ts |
| `GET /api/alert-metric-channel-keys` (router.go:282) | config.py:100 `alert_metric_channel_keys()` | Alarm-Zeile → Speicherschlüssel | alarme-tab/alertMetricChannels.ts:27 |
| `GET/PUT /api/briefings/{id}/placements` (router.go:361-362) | api/routers/placements.py:30 → `services.placements` (nutzt `zwei_formen_stellen`, `AMPEL_METRIC_IDS`, `standard_form`, `stellen_sperre`) | je Briefing „Was steht wo": Zeilen × Stellen mit state (on/off/locked/not_in_email), reason, format, ampel, mark, example | wetter-tab/wasStehtWo*.ts |
| `GET /api/_validator/format-metric`, `/detector-thresholds`, `/metrics-for-channel` (router.go:326-328) | api/routers/validator.py:176/190/574 | Formatierung je Einheit, Detektor-Schwellen je Trip, Kanal-Kaskade | Validatoren/Tests |

**Lücken (heute NICHT über API, aber im Client hart verdrahtet):** Wortskalen je Metrik/Sprache (INDICATOR_MAP), `OUTLOOK_FRIENDLY_CAPABLE`, `AMPEL_METRIC_IDS`/`zwei_formen_stellen` je Stelle (nur indirekt über placements), `METRIC_PRIORITY`/`_PRIMARY_SLOTS`, `_DERIVED_METRIC_RULES`, SMS-Schwellen-Stufen (15/20/30 …) und die Liste der SMS-schwellenfähigen Metriken, Alarm-Default-Schwellen (`METRIC_DEFAULTS`, Go `DefaultDeltaThreshold`), Preset-Schwellen (nur als generierte JSON-Kopie), Kategorie-/Gruppen-Rang und -Labels, Gewitter-Sonderregeln (alarm_ab ohne gelb, Farbwahl je Stufe), Default-Auswahlen (Ausblick, Tages-Summe, Stundenverlauf-Folge), Alarm-Einheiten/Vergleichszeichen je AlertMetric (nur je Katalog-ID als `unit`/`cmp` vorhanden), Icon/Ton je Metrik.

**Bereits doppelt vorhanden (API liefert es, Client führt trotzdem eigene Kopie):** `has_friendly_format` vs. INDICATOR_MAP; `alertable`/`is_precursor` vs. alarmAbAnzeige `VORBOTEN`/`KEIN_AUSLOESER`; `unit`/`cmp` vs. alertMetricLabels/alertMetricTable `_METRIC_UNITS`; `alert_label(_en)` vs. i18n `alarme.metrik.*`; `hourlyDefault` (Mitgliedschaft) vs. `HOURLY_DEFAULT_FOLGE` (nur Rang fehlt); `/api/templates` vs. account `FALLBACK_TEMPLATES`; `/api/compare/metrics` (metric_id+aggregation) vs. Go `vergleichAggregation`.
