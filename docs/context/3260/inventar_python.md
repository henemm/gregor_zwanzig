# Inventar: Metrik-Wissen und Metrik-Verarbeitung im Python-Produktcode ausserhalb von Katalog und Formatmodul

Stand: 2026-11-21, Arbeitsbaum `/home/user/gregor_zwanzig`. Umfang: `src/`, `api/` (ohne `tests/`).
Ausgenommen: `src/app/metric_catalog.py` (Katalog) und `src/output/metric_format.py` (Formatmodul).

Methode: (1) Lauf von `tests/helpers/metrik_listen_scan.scanne_register_listen(["src","api"])` – 57 Register-Listen-Funde (davon 39 ausserhalb der beiden Zielmodule; alle in die Tabelle uebernommen, Kennzeichen „[Scan]“). (2) Darueber hinaus grep/Lesen nach Metrik-Kennungen als Literal, `if key == "…"`/`metric_id in (…)`-Ketten (vom Scan bewusst nicht erfasst), festen Zahlenvergleichen, Wortskalen, Kürzeln, Farb-/Formwahl und Wert-Formatierung.

Spalte „Gehört in“: **Katalog** = Wissen (Kennungen, Schwellen, Wortskalen, Kürzel, Fähigkeiten, Einheit/Nachkommastellen) gehört als Daten an die Metrik-Definition; **Verarbeitung** = Logik (Wert→Wort/Farbe/Stufe, Formwahl, Text-Formatierung) gehört ins zentrale Verarbeitungsmodul (`metric_format.py` bzw. Nachfolger), das die Katalogdaten liest.

Arten: Liste-IDs · Schwelle · Wortskala · Kürzel · Fähigkeit · Formatierung · Formwahl · Farbwahl

## src/app/ampel_templates.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| ampel_templates.py:24 | Schwelle / Liste-IDs | `_ZEILEN`: 7 Vorlagen × ~20 Metriken mit unten (rot/orange/gelb) / oben (gelb/orange/rot) Grenzen und „Alarm ab“ (z.B. wind 30/45/60, gust 35/50/70, precipitation 1/5/15) | Katalog |
| ampel_templates.py:25 | Schwelle | Vorlage „alpen-trekking“ (Zahlen je Metrik) | Katalog |
| ampel_templates.py:47 | Schwelle | Vorlage „wandern“ | Katalog |
| ampel_templates.py:69 | Schwelle | Vorlage „skitouren“ (u.a. fresh_snow, snow_depth) | Katalog |
| ampel_templates.py:91 | Schwelle | Vorlage „wintersport“ | Katalog |
| ampel_templates.py:113 | Schwelle | Vorlage „radtour“ | Katalog |
| ampel_templates.py:135 | Schwelle | Vorlage „wassersport“ | Katalog |
| ampel_templates.py:157 | Schwelle | Vorlage „allgemein“ (deckungsgleich mit Katalog-`display_thresholds`, Paritaets-Ratsche) | Katalog |
| ampel_templates.py:184 | Fähigkeit | `_WIND_MODUS` {"radtour": "gegenwind"} – Windrichtungs-Modus je Vorlage | Katalog |
| ampel_templates.py:187 | Farbwahl / Fähigkeit | `_GEWITTER` thunder mittel→orange, hoch→red; 188: wassersport red/red | Katalog |

## src/app/ampel.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| ampel.py:28 | Farbwahl | `_LOWER`/`_UPPER` Stufenfolgen rot<orange<gelb bzw. gelb<orange<rot | Verarbeitung |
| ampel.py:32 | Fähigkeit | `ALARM_AB_GEWITTER` – thunder darf nur never/orange/red | Katalog |
| ampel.py:34 | Farbwahl | `_THUNDER_HOCH` {"orange","red"} | Verarbeitung |
| ampel.py:71 | Fähigkeit | `_windrichtung_grund`: nur `wind_direction` hat modus/sektoren; gegenwind nur Trip | Katalog |
| ampel.py:100 | Fähigkeit | `mid == "thunder"` Sonderpruefung alarm_ab | Katalog |
| ampel.py:113 | Schwelle | `_pruefe_gewitter`: Gewitter-Ampel mittel/hoch statt Zahlengrenzen | Katalog |
| ampel.py:227 | Schwelle | `_schwellen`: upper/lower → yellow/orange/red bzw. *_lt-Schluessel | Verarbeitung |
| ampel.py:247 | Liste-IDs / Fähigkeit | `AMPEL_LESER` 9 IDs (temperature, wind_chill, wind, gust, precipitation, rain_probability, visibility, uv_index, fresh_snow) [Scan] | Katalog |
| ampel.py:256 | Fähigkeit | `AMPEL_ABGELEITET` {"wind_direction"} | Katalog |
| ampel.py:329 | Farbwahl | `thunder_color`: keins grün, leicht fest gelb, mittel/hoch aus Vorlage | Verarbeitung |
| ampel.py:349 | Farbwahl | `_GELB_ODER_SCHLECHTER`, `ampel_stufe`, `gelb_oder_schlechter` | Verarbeitung |
| ampel.py:374 | Farbwahl | `ampel_seite`/`ampel_schaerfe`: oben/unten-Abstand zur mildesten Grenze | Verarbeitung |
| ampel.py:410 | Schwelle | `gewitter_gelb_oder_schlechter`: ab ThunderLevel.LOW | Katalog |

## src/output/renderers/email/helpers.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| helpers.py:66 | Formwahl | `should_merge_wind_dir`: wind + wind_direction(scale) → Kompass in Windzelle | Verarbeitung |
| helpers.py:98 | Liste-IDs / Fähigkeit | `NO_HOURLY_COLUMN_METRIC_IDS` 6 Fenster-IDs [Scan] | Katalog |
| helpers.py:191 | Formatierung | `aggregate_night_block`: Sonderfaelle `dp_field == "thunder_level"`/`"precip_type"`, min/max/sum/avg-Wahl | Verarbeitung |
| helpers.py:585 | Liste-IDs | `OUTLOOK_FIXED_METRIC_IDS` (temperature, precipitation, rain_probability, wind, gust, thunder) [Scan] | Katalog |
| helpers.py:668 | Farbwahl | `_AMPEL_DOT_COLORS` green/yellow/orange/red Hex + Ring | Verarbeitung |
| helpers.py:680 | Farbwahl | `_HAIL_RING_COLOR` Hagel-Doppelring | Verarbeitung |
| helpers.py:702 | Farbwahl | `ampel_dot` / `_ampel_dot_severity` / `ampel_level` Wert→Ampelpunkt | Verarbeitung |
| helpers.py:765 | Farbwahl | `mit_windrichtung`: hoehere Stufe aus Wind und Richtungs-Ampel | Verarbeitung |
| helpers.py:778 | Liste-IDs | `_AMPEL_KEY_TO_METRIC_ID` col_key→ID (wind, gust, precip, pop) [Scan] | Katalog |
| helpers.py:790 | Formatierung / Formwahl | `fmt_val` – zentrale Zellformatierung je col_key, Modus raw/simplified/Ampel | Verarbeitung |
| helpers.py:836 | Formatierung | fmt_val: precip_type → Wort | Verarbeitung |
| helpers.py:842 | Formwahl / Formatierung | fmt_val: thunder Wort+Zutaten+Hagel (raw/Text) vs. Ampelkreis (HTML) | Verarbeitung |
| helpers.py:875 | Formatierung | fmt_val: temp/felt/dewpoint `:.1f` | Katalog (Nachkommastellen) |
| helpers.py:877 | Formwahl | fmt_val: wind/gust simplified→Adjektiv (`format_wind_strength`), HTML→Ampel, sonst Zahl; Kompass-Anhang | Verarbeitung |
| helpers.py:902 | Formwahl | fmt_val: precip simplified→`format_precip_intensity`, HTML→Ampel | Verarbeitung |
| helpers.py:910 | Formatierung | fmt_val: snow_limit/snow_depth roh, 0→„–“ | Verarbeitung |
| helpers.py:912 | Formwahl | fmt_val: Wolken `:.0f` vs. `cloud_emoji` | Verarbeitung |
| helpers.py:918 | Formwahl / Formatierung | fmt_val: sunshine Stunden `:.1f h` vs. Wetter-Emoji aus DNI/WMO | Verarbeitung |
| helpers.py:933 | Formatierung | fmt_val: humidity roh, pressure `:.1f` | Katalog (Nachkommastellen) |
| helpers.py:937 | Formwahl | fmt_val: pop simplified→Wortstufe 25/50/75, HTML→Ampel | Verarbeitung |
| helpers.py:947 | Fähigkeit | fmt_val: cape nie Ampel (keine eigene Farbe) | Katalog |
| helpers.py:952 | Schwelle / Formatierung | fmt_val: visibility `>= 10000` → km ohne Nachkomma, sonst `:.1f` | Katalog + Verarbeitung |
| helpers.py:958 | Formwahl | fmt_val: wind_dir raw→Grad, sonst Kompass | Verarbeitung |
| helpers.py:986 | Wortskala / Kürzel | `_THUNDER_MAP` NONE/LOW/MED/HIGH → Wort + „⚡“-Plain-Token | Katalog |
| helpers.py:1008 | Wortskala | `_thunder_map(lang)` EN-Variante | Katalog |
| helpers.py:1071 | Formatierung | `format_trend_tokens`: Temperatur „tl/th°C“, Niederschlag `:g mm` | Verarbeitung |
| helpers.py:1082 | Schwelle | `precip_highlight = pm > 1` (fest 1 mm) | Katalog |
| helpers.py:1088 | Schwelle | `wind_highlight = wk > 30`, `wind_risk = wk >= 50` (fest km/h) | Katalog |
| helpers.py:1112 | Kürzel | Trend-Tokens "R"/"W"/"G" je Metrik, 1131 "TH" | Katalog |
| helpers.py:1123 | Wortskala | `_TREND_THUNDER_LABELS` 1/2/3 → leicht/mittel/hoch | Katalog |
| helpers.py:1129 | Schwelle | `thunder_thr = 1.0` (ab LOW meldenswert) | Katalog |
| helpers.py:1235 | Formatierung | `format_change_line`: alt→neu `:.1f` (Δ) | Verarbeitung |
| helpers.py:1294 | Formwahl | `build_friendly_keys` (has_friendly_format) | Verarbeitung |
| helpers.py:1410 | Formwahl | `build_format_modes` col_key→Modus | Verarbeitung |
| helpers.py:1430 | Fähigkeit | `_AMPEL_CAPABLE_METRIC_IDS` Alias auf Katalog; 1433 `build_html_indicator_keys` | Verarbeitung |
| helpers.py:1460 | Farbwahl | `_AMPEL_STAGE_ORDER`/`_TONES`/`_COLORS` WCAG-Vollfarben je Stufe | Verarbeitung |
| helpers.py:1476 | Farbwahl | `_PILL_NEUTRAL_COLORS` | Verarbeitung |
| helpers.py:1479 | Farbwahl | `ampel_stage_index`/`ampel_stage_tone` Wert→Stufenindex | Verarbeitung |
| helpers.py:1520 | Farbwahl | `_PILL_TAG_PALETTE` ok/caution/warn/risk/info; 1528 `_PILL_TONE_MAP` | Verarbeitung |
| helpers.py:1558 | Liste-IDs | `_PILL_CATALOG_ORDER` Pillen-Reihenfolge [Scan] | Katalog |
| helpers.py:1567 | Fähigkeit | `_PILL_CLASS1` (Schweregrad-Pillen: wind, gust, precipitation, rain_probability, thunder, visibility, humidity) [Scan] | Katalog |
| helpers.py:1571 | Fähigkeit | `_PILL_CLASS2` (neutrale Bereichs-Pillen) [Scan] | Katalog |
| helpers.py:1577 | Farbwahl | `_thunder_band` Gewitterstufe→Ampelfarbe | Verarbeitung |
| helpers.py:1593 | Schwelle | Import `LUFTFEUCHTE_ERWAEHNUNG_AB_PCT` (90 %) für Pillen | Katalog |
| helpers.py:1598 | Schwelle | `_mention_threshold`/`_erwaehnt`: Erwähnungsschwelle = mildeste Ampelgrenze | Verarbeitung |
| helpers.py:1664 | Formatierung | `_fmt_thousands`, 1669 `_range_pill` | Verarbeitung |
| helpers.py:1685 | Liste-IDs / Formatierung | `_AGGREGATION_PILL_METRICS` temperature/wind_chill → (Feld, Präfix „gef.“, Nachkommastellen) [Scan] | Katalog |
| helpers.py:1699 | Formatierung | `format_temp_span` min–max mit decimals | Verarbeitung |
| helpers.py:1760 | Farbwahl | `_extreme_ampel_tone` | Verarbeitung |
| helpers.py:1777 | Formatierung / Farbwahl | `_pill_for_metric`: if-Kette je Metrik (Text+Ton) | Verarbeitung |
| helpers.py:1834 | Formatierung | Pille cloud_total min–max % + Zeit, neutral | Verarbeitung |
| helpers.py:1848 | Formatierung | Pille cloud_low Bereich | Verarbeitung |
| helpers.py:1856 | Formatierung | Pille freezing_level Tausender-Format | Verarbeitung |
| helpers.py:1871 | Formatierung | Pille dewpoint `:.1f` | Verarbeitung |
| helpers.py:1882 | Formatierung / Farbwahl | Pille uv_index „UV max x.x“ + Ampelton | Verarbeitung |
| helpers.py:1901 | Formatierung | Pille sunshine (Sonnenstunden) | Verarbeitung |
| helpers.py:1912 | Formatierung / Farbwahl | Pille wind/gust (Feldwahl wind10m_kmh/gust_kmh, Spitze, Ton) | Verarbeitung |
| helpers.py:1943 | Formatierung | Pille precipitation Summe `:.1f` (rstrip) | Verarbeitung |
| helpers.py:1966 | Formatierung / Farbwahl | Pille rain_probability | Verarbeitung |
| helpers.py:1991 | Formatierung / Farbwahl | Pille thunder (Tag/Nacht, Herkunft, Datenluecke) | Verarbeitung |
| helpers.py:2080 | Formatierung | Pille visibility km `:.0f`/`:.1f` | Verarbeitung |
| helpers.py:2106 | Formatierung / Schwelle | Pille humidity (Erwähnung ab 90 %) | Verarbeitung |
| helpers.py:2141 | Liste-IDs | `_DAY_WINDOW_PILL_IDS` (wind, gust, precipitation, rain_probability, thunder) [Scan] | Katalog |

## src/output/renderers/email/compare_html.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| compare_html.py:77 | Farbwahl | `_LEVEL_TO_COMPARE` green/yellow/orange/red → ok/caution/warn/danger | Verarbeitung |
| compare_html.py:97 | Farbwahl | `_RISK_CELL` Zellfarben je Stufe; 102 `_INFO_CELL` | Verarbeitung |
| compare_html.py:107 | Farbwahl | `_ALERT_LEVEL_CELL` Warnstufe 1–4 → Farben | Verarbeitung |
| compare_html.py:118 | Farbwahl | `_sev_temp` (severity_for "temperature") | Verarbeitung |
| compare_html.py:126 | Farbwahl | `_sev_wind` | Verarbeitung |
| compare_html.py:134 | Farbwahl | `_sev_gust` | Verarbeitung |
| compare_html.py:141 | Farbwahl | `_sev_rain`; 267 `_sev_rain_safe` (None→0) | Verarbeitung |
| compare_html.py:145 | Farbwahl | `_sev_uv` | Verarbeitung |
| compare_html.py:149 | Farbwahl | `_sev_pop` | Verarbeitung |
| compare_html.py:153 | Farbwahl | `_sev_visibility` (Docstring <2000/<1000/<500 m) | Verarbeitung |
| compare_html.py:159 | Farbwahl | `_sev_windrichtung` / 168 `_sev_mit_richtung` | Verarbeitung |
| compare_html.py:188 | Formatierung | `_fmt_deg` `:.0f°` | Verarbeitung |
| compare_html.py:192 | Formatierung | `_fmt_kmh` `:.0f` | Verarbeitung |
| compare_html.py:196 | Formatierung | `_fmt_rain` `:.1f`, 0→„·“ | Verarbeitung |
| compare_html.py:200 | Formatierung | `_fmt_uv` `:.0f` | Verarbeitung |
| compare_html.py:204 | Formatierung | `_fmt_pop` `:.0f%` | Verarbeitung |
| compare_html.py:208 | Formatierung | `_fmt_visibility` m→km `:.1f` | Verarbeitung |
| compare_html.py:214 | Formatierung | `_fmt_thunder` Wort + Hagel/Zutaten | Verarbeitung |
| compare_html.py:259 | Farbwahl | `_sev_thunder` über thunder_color | Verarbeitung |
| compare_html.py:274 | Formatierung | `_fmt_precip_type`; 281 `fmt_word_cell` | Verarbeitung |
| compare_html.py:291 | Formatierung | `_fmt_visibility_overview` + „ km“ | Verarbeitung |
| compare_html.py:338 | Liste-IDs / Formatierung | `CV2_ZEILEN` Übersichtszeilen key→metric_id + Aggregation (temp_max, wind_max, precip_sum, pop_max, thunder_max, sunny_hours, cloud_avg, uv_max, visibility_min, snow…, gust_max, freezing_level, wind_chill_min/max, cloud_*, humidity, dewpoint, pressure, precip_type, snowfall_limit) | Katalog |
| compare_html.py:417 | Formatierung | `_HOUR_FMT_OVERRIDES` 10 IDs → Formatierer [Scan] | Verarbeitung |
| compare_html.py:433 | Farbwahl | `_HOUR_SEV_OVERRIDES` wind_chill=None, precipitation, thunder [Scan] | Verarbeitung |
| compare_html.py:479 | Fähigkeit | `_hour_zeilen`: Ampel nur bei `hat_ampel` | Verarbeitung |
| compare_html.py:669 | Liste-IDs | `_DAILY_AGGREGATE_FIELD` Zeilenschlüssel → Summary-Feld (precip_sum_mm, pop_max_pct, cape_max_jkg …) | Katalog |
| compare_html.py:765 | Formatierung | `_fmt_metric`: Einheit ohne Leerzeichen bei °C/% | Verarbeitung |
| compare_html.py:777 | Fähigkeit | `_FRIENDLY_AMPEL_METRIC_IDS` Alias AMPEL_METRIC_IDS | Verarbeitung |
| compare_html.py:780 | Formwahl | `_friendly_overview_html`: Ampel-IDs→Punkt, thunder→Symbol, sonst `_friendly_outlook_text` | Verarbeitung |
| compare_html.py:1132 | Formwahl | `_should_merge_wind_dir` (wind10m_kmh + wind_direction_deg) | Verarbeitung |
| compare_html.py:1143 | Formwahl | `_hour_einfach_text`: wind/gust → Ampelpunkt, sonst `_friendly_hour_text` (Z.1160) | Verarbeitung |
| compare_html.py:1685 | Farbwahl | Legende gruen/gelb/orange/rot Hex | Verarbeitung |

## src/output/renderers/email/html.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| html.py:81 | Schwelle | `HEAT_PLAUSIBILITY_MIN_C = 25.0` (Hitzewarnung nur bei gefühlter Max ≥ 25 °C, Z.1464) | Katalog |
| html.py:162 | Farbwahl | `_AMPEL_BAND_RISK` green→ok … red→risk | Verarbeitung |
| html.py:165 | Farbwahl | `_thunder_risk_level` Gewitter → Risikostufe | Verarbeitung |
| html.py:206 | Farbwahl | `_row_risk`: Zeilenrisiko aus gust/wind/precip/pop/visibility/temp/fresh_snow-Severities | Verarbeitung |
| html.py:249 | Liste-IDs | `severities`-Dict 8 IDs für Paar-Eskalation [Scan] | Katalog |
| html.py:276 | Farbwahl | `_RISK_LEVEL_TO_AMPEL`; 283 `_RISK_DOT_COLORS`; 288 `_ampel_cell_bg` | Verarbeitung |
| html.py:451 | Liste-IDs | `TRIP_CORRIDOR_METRIC_TO_COL_KEY` wind_gust/temperature_min/max/snow_line → col_key | Katalog |
| html.py:570 | Liste-IDs | `_COL_KEY_TO_METRIC_ID` (wind, gust, precip, pop, cape) [Scan] | Katalog |
| html.py:581 | Liste-IDs | `_FALLBACK_COL_KEY_TO_METRIC_ID` (+vis, visibility, temp) [Scan] | Katalog |
| html.py:655 | Farbwahl | Zellhintergrund je col_key über severity_for | Verarbeitung |
| html.py:659 | Farbwahl | wind_dir-Zelle über mit_windrichtung | Verarbeitung |
| html.py:661 | Farbwahl | thunder-Zelle: Wort→Band, Zahl→risk/watch | Verarbeitung |
| html.py:693 | Farbwahl | wind + Richtungs-Ampel | Verarbeitung |
| html.py:1166 | Liste-IDs | Nacht-Hinweis nur bei temperature/freezing_level | Katalog |
| html.py:1220 | Schwelle / Farbwahl | `_confidence_dot_color`: ≥80 grün, ≥60 orange, sonst rot | Katalog + Verarbeitung |
| html.py:1364 | Farbwahl | Trend-Glyph/-Farbe aus „besser/schlechter“ | Verarbeitung |
| html.py:1527 | Farbwahl | Risiko-Legende Hex | Verarbeitung |

## src/services/day_comparison.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| day_comparison.py:21 | Fähigkeit | `_LOWER_IS_BETTER` (wind_max_kmh, gust_max_kmh, precip_sum_mm, thunder) – Polarität je Metrik | Katalog |
| day_comparison.py:24 | Fähigkeit | `_NEUTRAL` temp_min_c/temp_max_c ohne Richtung | Katalog |
| day_comparison.py:30 | Liste-IDs | `_METRIC_ID_TO_ENTRY_ATTR` 15 IDs → Vortags-Feld [Scan] | Katalog |
| day_comparison.py:50 | Liste-IDs | `_DIRECTION_METRICS` 15 IDs mit Richtungswort [Scan] | Katalog |
| day_comparison.py:57 | Wortskala | `_direction_word` höher/tiefer je metric_id über Textkatalog | Verarbeitung |
| day_comparison.py:111 | Schwelle | `_scalar_delta`: ±0.5 als Richtungsgrenze | Katalog |
| day_comparison.py:210 | Schwelle | Legacy: Temperatur-Δ > 1.5 °C erwähnenswert | Katalog |
| day_comparison.py:216 | Schwelle | Legacy: Niederschlags-Δ > 1.0 mm erwähnenswert | Katalog |
| day_comparison.py:225 | Schwelle | `_SALIENCE_FACTOR = 0.6` × default_change_threshold | Katalog |
| day_comparison.py:232 | Schwelle | `_DISPLAY_SALIENCE_OVERRIDES` humidity 12, rain_probability 12, cloud_total 18, pressure 6, wind_chill 3, dewpoint 3 [Scan] | Katalog |
| day_comparison.py:242 | Schwelle | `_get_threshold` Fallback 3.0 | Katalog |
| day_comparison.py:287 | Formwahl | thunder-Sonderzweig (Ordinal-Delta) | Verarbeitung |
| day_comparison.py:298 | Formwahl | wind_chill verdrängt temperature in der Vortags-Zeile | Katalog |
| day_comparison.py:329 | Formatierung | `_thunder_delta` Ordinal-Differenz | Verarbeitung |

## src/services/weather_change_detection.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| weather_change_detection.py:38 | Liste-IDs | `_ALERT_METRIC_TO_SUMMARY_FIELD` AlertMetric → Summary-Feld (gust_max_kmh, precip_sum_mm, temp_min_c …) | Katalog |
| weather_change_detection.py:66 | Liste-IDs | `_ONSET_SUMMARY_FIELDS` thunder/precip-heavy onset | Katalog |
| weather_change_detection.py:72 | Liste-IDs | `_ALERT_DELTA_METRIC_TO_FIELDS` Delta-Alarm → Felder | Katalog |
| weather_change_detection.py:96 | Liste-IDs | `_ALERT_METRIC_TO_CATALOG_ID` AlertMetric → Katalog-IDs (inkl. temperature_cold, snowfall_limit/freezing_level OR) [Scan] | Katalog |
| weather_change_detection.py:123 | Fähigkeit | `_COMPARISON_EXCLUDED_METRICS` {VISIBILITY} | Katalog |
| weather_change_detection.py:130 | Fähigkeit | `_ALERTABLE_METRIC_VALUES` (wind_gust, precipitation_sum, temperature_min/max, snow_line, thunder_level) | Katalog |
| weather_change_detection.py:171 | Fähigkeit | `_LEGACY_ONLY_CHANNEL_KEYS` {"snowfall_limit"} | Katalog |
| weather_change_detection.py:296 | Farbwahl | `_RULE_SEVERITY_TO_CHANGE_SEVERITY` INFO/WARNING/CRITICAL → MINOR/MODERATE/MAJOR | Verarbeitung |
| weather_change_detection.py:338 | Schwelle | `_PRECIP_MEASURABLE_MM = 0.1` (messbarer Niederschlag) | Katalog |

## src/app/models.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| models.py:38 | Wortskala | `ThunderLevel` NONE/LOW/MED/HIGH | Katalog |
| models.py:50 | Wortskala | `PrecipType` RAIN/SNOW/MIXED/FREEZING_RAIN | Katalog |
| models.py:317 | Liste-IDs | `RiskType` (thunderstorm, rain, wind, wind_chill, poor_visibility …) – eigene Metrik-Kennungen der Risk-Engine | Katalog |
| models.py:585 | Schwelle | `ChangeSeverity` minor/moderate/major = 1,1×/1,5×/2,0× Überschreitung | Katalog |
| models.py:1170 | Schwelle | `change_threshold_temp_c=5.0`, `_wind_kmh=20.0`, `_precip_mm=10.0` (auch 1145) | Katalog |
| models.py:1195 | Liste-IDs | `daily_summary_metrics` Default (precipitation, wind, visibility, thunder) [Scan] | Katalog |
| models.py:1250 | Liste-IDs | `AlertMetric`-Enum (wind_gust, precipitation_sum, temperature_min/max, thunder_level, snow_line, fresh_snow, cape, visibility, freezing_level, humidity, *_onset) | Katalog |

## src/output/renderers/compare_hourly_metric_ids.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| compare_hourly_metric_ids.py:32 | Liste-IDs | `FRONTEND_TO_HOURLY_METRIC_ID` Stundenfeld (temp_c, wind_kmh, gust_kmh, precip_mm, pop_pct, visibility_m, thunder_level, wind_dir_deg …) → ID [Scan] | Katalog |
| compare_hourly_metric_ids.py:60 | Fähigkeit | `HOURLY_EXCLUDED_METRIC_IDS` (sunshine + 6 Fenster-IDs) – „keine Stundenspalte“ [Scan] | Katalog |
| compare_hourly_metric_ids.py:74 | Fähigkeit | `HOURLY_EXCLUSION_REASON` Begründung je ausgeschlossener ID [Scan] | Katalog |
| compare_hourly_metric_ids.py:84 | Fähigkeit | Tagesrichtungs-Begründungen (temperature_day_*, wind_chill_day_*) | Katalog |
| compare_hourly_metric_ids.py:104 | Fähigkeit | `HOURLY_MERGE_ONLY_METRIC_IDS` {"wind_direction"} | Katalog |
| compare_hourly_metric_ids.py:114 | Liste-IDs | `HOURLY_DEFAULT_METRIC_IDS` 9 IDs Vorgabe-Stundenspalten [Scan] | Katalog |

## src/app/loader.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| loader.py:56 | Liste-IDs / Formatierung | `_LEGACY_DELTA_MAPPING` change_threshold_* → AlertMetric + Einheit °C/km/h/mm | Katalog |
| loader.py:63 | Formwahl | `_resolve_format_mode` explizit / use_friendly_format / Katalog-Default | Verarbeitung |
| loader.py:488 | Schwelle | Grundtempo nur 0,5..60 km/h gültig | (kein Wetterwert; Randfall) |
| loader.py:676 | Liste-IDs | `daily_summary_metrics`-Fallback (precipitation, wind, visibility, thunder) [Scan] | Katalog |
| loader.py:809 | Formwahl | `_LEGACY_FORMAT_MODES` {"scale","symbol"} | Katalog |
| loader.py:821 | Liste-IDs | `_ALT_ALERT_LEVEL_KEYS` Summary-Feld → Alarmname (spiegelt Go `legacyAlertLevelKeys`) | Katalog |
| loader.py:970 | Liste-IDs / Fähigkeit | `_DERIVED_METRIC_RULES` Fenster-ID → Eltern-ID (temperature_night←temperature …) [Scan, 6 Funde Z.971–976] | Katalog |
| loader.py:1235 | Liste-IDs | `_OLD_METRIC_MAP` alter Feldname → (metric_id, Aggregation) | Katalog |

## src/output/renderers/narrow.py (Telegram)

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| narrow.py:193 | Wortskala | `_thunder_severity` Ordinal-Wrapper; 204 `_SEV_TO_THUNDER_LEVEL` Inverse | Verarbeitung |
| narrow.py:209 | Formatierung | `_day_window_thunder_severity` / 237 `_day_window_hail_note` | Verarbeitung |
| narrow.py:315 | Formwahl / Wortskala | `_tg_day_footer`: Gewitterwort kein/leicht/mittel/hoch, „?“ bei Lücke, LOW → „Luftmasse“ (Z.340–352) | Verarbeitung |
| narrow.py:367 | Schwelle / Wortskala | Sicht `>= 10000` gut, `>= 4000` mäßig, sonst schlecht | Katalog |
| narrow.py:377 | Formatierung | Nullgradgrenze-Footer | Verarbeitung |
| narrow.py:413 | Liste-IDs / Formatierung | `_tg_vortag_line` Felder precip_sum/wind_max/gust_max/temp_max/temp_min/thunder mit Einheit mm/km/h/°C | Katalog |
| narrow.py:510 | Schwelle | `_gelb` Erwähnung ab Ampel-gelb | Verarbeitung |
| narrow.py:587 | Formwahl | `_overview_line`: temperature/wind_chill Spannen-Sonderzweig | Verarbeitung |
| narrow.py:617 | Formatierung | Abend: Nacht-Minimum `:.1f` für temperature/wind_chill | Verarbeitung |
| narrow.py:623 | Formwahl | Ampel-Metriken: @Uhrzeit-Tag nur bei gelb | Verarbeitung |
| narrow.py:639 | Formwahl | thunder-Sonderzweig (schlimmste Stunde, Hagel) | Verarbeitung |
| narrow.py:908 | Formwahl / Formatierung | temperature_night / wind_chill_night als Prosazeile `:.1f` (Z.920–936) | Verarbeitung |
| narrow.py:918 | Formwahl | wind_direction nur gemergt | Verarbeitung |

## src/output/renderers/compact_summary.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| compact_summary.py:46 | Schwelle | `_RAIN_DETECT = 0.1` mm Regen vs. trocken | Katalog |
| compact_summary.py:186 | Liste-IDs / Formwahl | `format_weather_summary`: feste Reihenfolge/Auswahl temperature, wind_chill, cloud_total, precipitation/rain_probability, wind/gust, wind_direction, thunder (Z.186–256) | Katalog (Reihenfolge) + Verarbeitung |
| compact_summary.py:311 | Formatierung | `_format_temperature` Spanne Nacht/Gehzeit, ganzzahlig | Verarbeitung |
| compact_summary.py:349 | Formatierung | `_format_felt_temperature` „gef. min–max°C“ | Verarbeitung |
| compact_summary.py:389 | Formwahl | `_format_clouds` friendly → cloud_emoji, sonst „Wolken x %“ | Verarbeitung |
| compact_summary.py:405 | Formwahl / Wortskala | `_format_precipitation` trocken / Muster (peak, starts_later, ends_early, window) | Verarbeitung |
| compact_summary.py:447 | Schwelle / Wortskala | `_precip_adjective` > 10 stark, > 2 mäßig, sonst leicht | Katalog |
| compact_summary.py:454 | Schwelle | `_find_rain_pattern`: Peak ≥ 2× Mittel, ≥ 2 trockene Stunden (Z.486–494) | Verarbeitung |
| compact_summary.py:524 | Schwelle / Wortskala | `_format_wind` > 60 Sturm, > 35 stark, > 15 mäßig, sonst schwach (Z.544–551) | Katalog |
| compact_summary.py:559 | Formatierung | Wind „ N km/h“ ganzzahlig + Kompass | Verarbeitung |
| compact_summary.py:570 | Schwelle | `_find_wind_peak` | Verarbeitung |
| compact_summary.py:588 | Wortskala / Formwahl | `_format_thunder` LOW-Sonderfall, Stunden mit Gewitter | Verarbeitung |

## src/output/tokens/builder.py (SMS-Token)

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| builder.py:20 | Kürzel | `FORECAST_TH = "TH:"`, `FORECAST_THP = "TH+:"`, 30 `"+HL"` Hagel-Suffix | Katalog |
| builder.py:54 | Kürzel / Fähigkeit | `PRIORITY` Kürzel → Kürzungspriorität (SL, NS24+, SD, PR, FD/FL/FN, TF, D/N/L, R, W, G, HU, DP, WD:, CP, PT:, CT, CL, CM, CH, VS, SU, UV, HP, FZ) | Katalog |
| builder.py:102 | Kürzel | `POSITIONAL` Positionsreihenfolge der Kürzel | Katalog |
| builder.py:141 | Kürzel | `_BAUSTEIN_SCHLUESSEL` / `BAUSTEIN_BEDEUTUNG_DE/EN` Kürzel-Bedeutung | Katalog |
| builder.py:173 | Kürzel / Liste-IDs | `AMPEL_METRIK_JE_KUERZEL` R/PR/W/G/UV → ID [Scan] | Katalog |
| builder.py:178 | Schwelle | `_GEWITTER_AB_LEICHT = 1.0` | Katalog |
| builder.py:181 | Schwelle | `LUFTFEUCHTE_ERWAEHNUNG_AB_PCT = 90.0` | Katalog |
| builder.py:220 | Formwahl | `_mk_metric` Schwellen-/Ampel-Token, friendly-Token | Verarbeitung |
| builder.py:266 | Kürzel / Fähigkeit | `INVERS_MIN_AMPEL_METRIK` VS→visibility, TF→wind_chill (Minimum ist kritisch) [Scan] | Katalog |
| builder.py:357 | Kürzel / Schwelle | `_wintersport` SD/NS24+/SL; SL `val > threshold`, sonst `<` (Z.378–382) | Katalog |
| builder.py:421 | Kürzel / Liste-IDs | Temperatur-Token N/L/D/FL/FD mit Eltern-ID temperature/wind_chill | Katalog |
| builder.py:478 | Kürzel | Paare kalt/warm ("L","D"), ("FL","FD") | Katalog |
| builder.py:488 | Kürzel | R/PR/W/G aus Stundenreihen | Katalog |
| builder.py:516 | Kürzel | CP/UV/CT/CL/CM/CH aus Stundenreihen | Katalog |
| builder.py:533 | Kürzel / Formatierung | VS (Faktor 0.001, 1 Nachkommastelle), FZ, TF (0) | Katalog |
| builder.py:554 | Kürzel | WD:/PT: Textcode, 568 SU/HP ganzzahlig | Katalog |

## src/services/weather_metrics.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| weather_metrics.py:29 | Schwelle | `_DNI_FULL_SUN=600`, `_MOSTLY_SUNNY=300`, `_PARTLY_SUNNY=120` W/m² | Katalog |
| weather_metrics.py:34 | Wortskala | `_WMO_PRECIP_EMOJI` WMO-Code → Emoji | Katalog |
| weather_metrics.py:47 | Schwelle | `_WMO_SEVERITY` WMO-Rangfolge | Katalog |
| weather_metrics.py:58 | Formwahl | `get_weather_emoji` WMO > Nacht > DNI > Wolken | Verarbeitung |
| weather_metrics.py:87 | Schwelle / Wortskala | `_night_emoji` Wolken < 40 / < 80 | Katalog |
| weather_metrics.py:96 | Schwelle / Wortskala | `_dni_emoji` DNI-Stufen → ☀️/🌤️/⛅/🌥️/☁️ | Katalog |
| weather_metrics.py:124 | Schwelle / Wortskala | `format_wind_strength` < 10 schwach, < 25 mäßig, < 40 stark, sonst sehr stark | Katalog |
| weather_metrics.py:145 | Schwelle / Wortskala | `format_precip_intensity` 0 trocken, ≤ 2 leicht, ≤ 10 mäßig, > 10 stark | Katalog |
| weather_metrics.py:163 | Schwelle / Wortskala | `format_precip_daily_sum` ≤ 5 / ≤ 20 / > 20 mm (Tagessumme) | Katalog |
| weather_metrics.py:184 | Schwelle / Wortskala | `format_rain_probability_scale` < 25 unwahrscheinlich, < 50 möglich, < 75 wahrscheinlich, sonst sehr wahrscheinlich | Katalog |
| weather_metrics.py:206 | Schwelle / Wortskala | `format_sunshine_scale` < 2 trübe, < 5 wechselhaft, < 8 freundlich, sonst sonnig | Katalog |
| weather_metrics.py:252 | Schwelle | Wolkenlage: GLACIER_LEVEL_M 3000, ALPINE_LEVEL_M 2000, ABOVE_CLOUDS_* 20/30, IN_CLOUDS_* 50/50/60 % | Katalog |
| weather_metrics.py:273 | Formatierung | `degrees_to_compass` Grad → 8 Himmelsrichtungen | Verarbeitung |
| weather_metrics.py:294 | Schwelle | `SUNNY_HOUR_CLOUD_THRESHOLD_PCT = 30` | Katalog |
| weather_metrics.py:297 | Schwelle | `dni_to_sunny_fraction` (DNI-Band aus Settings) | Verarbeitung |
| weather_metrics.py:371 | Schwelle / Wortskala | `get_weather_symbol` Niederschlag > 0.5 mm (Schnee < 0 °C), Wolken < 20/50/80 → ☀️/⛅/🌥️/☁️ | Katalog |
| weather_metrics.py:503 | Liste-IDs | `aggregation_config` Summary-Feld → min/max/avg/sum/onset … | Katalog |
| weather_metrics.py:645 | Schwelle | `_PRECIP_HEAVY_MMPH = 4.0` Starkregen-Beginn | Katalog |
| weather_metrics.py:720 | Wortskala | `_compute_thunder_level` Max-Stufe | Verarbeitung |
| weather_metrics.py:807 | Schwelle | `_validate_plausibility` Plausi-Grenzen temp −50..50, wind/gust 0..300, precip 0..500, cloud/humidity 0..100, visibility 0..100000 | Katalog |
| weather_metrics.py:1134 | Schwelle | `_compute_precip_type` Rang FREEZING_RAIN > SNOW > MIXED > RAIN | Katalog |
| weather_metrics.py:1156 | Schwelle | `_validate_extended_plausibility` dewpoint −50..40, pressure 800..1100, wind_chill −60..30, snow 0..1000, freezing 0..6000, pop 0..100, cape 0..5000, uv 0..15 | Katalog |
| weather_metrics.py:1398 | Schwelle | `_ENUM_ORDER` PrecipType RAIN 0/SNOW 1/MIXED 2 (abweichend von Z.1134 und sms_trip.py:183) | Katalog |

## src/services/comparison_scoring.py (Orts-Ranking)

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| comparison_scoring.py:48 | Schwelle | `_score_wintersport`: Schneehöhe ≥ 100/50/30 cm | Katalog |
| comparison_scoring.py:67 | Schwelle | Wintersport Sonne: Anteil im Fenster bzw. ≥ 6/4/2 h | Katalog |
| comparison_scoring.py:87 | Schwelle | Wintersport Wind > 60/40/25 km/h | Katalog |
| comparison_scoring.py:96 | Schwelle | Wintersport Böen > 80/60 km/h | Katalog |
| comparison_scoring.py:103 | Schwelle | Wintersport Wolken > 80/60 % | Katalog |
| comparison_scoring.py:110 | Schwelle | Wintersport Temperatur < −20, > 5, −10..−3 °C; Regen bei T > 0 (Z.118) | Katalog |
| comparison_scoring.py:123 | Schwelle | Wintersport Sicht < 500 / < 1000 / ≥ 10000 m | Katalog |
| comparison_scoring.py:148 | Schwelle | `_score_wandern` Niederschlag > 5 / > 1 mm | Katalog |
| comparison_scoring.py:156 | Schwelle | Wandern Regenwahrsch. > 80 % | Katalog |
| comparison_scoring.py:162 | Schwelle | Wandern Sicht < 200 / < 1000 / ≥ 5000 m | Katalog |
| comparison_scoring.py:172 | Schwelle | Wandern Wind > 60 / > 40 km/h | Katalog |
| comparison_scoring.py:179 | Schwelle | Wandern Wolken > 90 % | Katalog |
| comparison_scoring.py:183 | Schwelle | Wandern Sonne ≥ 7/5/3 h | Katalog |
| comparison_scoring.py:204 | Schwelle | Wandern Temperatur 10..20 / 5..10 / < 0 °C | Katalog |
| comparison_scoring.py:222 | Schwelle | `_score_allgemein` Niederschlag > 5 / > 1 mm | Katalog |
| comparison_scoring.py:237 | Schwelle | Allgemein Wind > 50 / > 30 km/h | Katalog |
| comparison_scoring.py:244 | Schwelle | Allgemein Wolken > 80 % | Katalog |
| comparison_scoring.py:250 | Schwelle | Allgemein Temperatur < −10 / > 30 / 5..25 °C | Katalog |
| comparison_scoring.py:258 | Schwelle | Allgemein Sonne ≥ 6/4/2 h | Katalog |

## src/services/compare_alert.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| compare_alert.py:58 | Fähigkeit | `_STANDARD_METRIC_LEVELS` alle Preset-Metriken → "standard" | Katalog |
| compare_alert.py:71 | Liste-IDs / Fähigkeit | `_SUMMARY_KEY_TO_CATALOG_ID` 10 alarmfähige Summary-Keys → ID (temp_min_c→temperature_cold …) [Scan] | Katalog |

## src/services/alert_preset.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| alert_preset.py:56 | Schwelle | `_PRESET_TABLE` Alarm-Schwellen je AlertMetric × entspannt/standard/sensibel (gust 35/20/12, precip 20/10/5, freezing 600/400/200, cape 1200/600/200, visibility 500/1000/3000 …) | Katalog |
| alert_preset.py:83 | Schwelle | `_COL` Empfindlichkeit → Spalte | Katalog |
| alert_preset.py:117 | Schwelle | `ORDINAL_LEVEL_BOUNDS` Gewitter-Niveau je Empfindlichkeit | Katalog |
| alert_preset.py:124 | Fähigkeit | `ORDINAL_LEVEL_METRICS` (thunder_level) | Katalog |
| alert_preset.py:139 | Schwelle | `ONSET_SHIFT_BOUNDS` Beginn-Verschiebung h je Stufe | Katalog |
| alert_preset.py:146 | Fähigkeit | `ONSET_METRICS` | Katalog |
| alert_preset.py:218 | Liste-IDs | snow_line → freezing_level Migration | Katalog |
| alert_preset.py:271 | Fähigkeit | temperature_cold → Feld temp_min_c / Umbrella "temperature" | Katalog |

## src/services/risk_engine.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| risk_engine.py:28 | Farbwahl | `_LEVEL_ORDER` LOW/MODERATE/HIGH | Verarbeitung |
| risk_engine.py:69 | Liste-IDs | geprüfte Metriken wind, gust, precipitation, rain_probability, wind_chill, visibility → RiskType + Summary-Feld (Z.69–98) | Katalog |
| risk_engine.py:126 | Schwelle / Farbwahl | `_check_thunder` HIGH→HIGH, MED→MODERATE, LOW→LOW | Katalog |
| risk_engine.py:142 | Schwelle | `_check_catalog_metric` high_lt / high / medium aus risk_thresholds | Verarbeitung |
| risk_engine.py:180 | Schwelle | `_check_confidence` confidence_pct_min < 40 | Katalog |
| risk_engine.py:201 | Liste-IDs / Schwelle | `_check_wind_exposition` wind/gust gegen exposition_thresholds | Verarbeitung |

## src/output/renderers/alert/hours.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| hours.py:23 | Fähigkeit | `_LEVEL_METRICS` = Ampel-IDs ∪ {"thunder"} | Katalog |
| hours.py:25 | Formatierung | `_CELL_KEY_ALIAS` temp_cold/night/day_low/day_high → "temp" | Katalog |
| hours.py:31 | Formatierung | `_numeric`: thunder → Ordinal 0..3 | Verarbeitung |
| hours.py:40 | Farbwahl | `_stage`: thunder Ordinal, sonst Ampelband-Index | Verarbeitung |
| hours.py:152 | Formwahl / Formatierung | `format_cell` thunder Ordinal→Stufe, dann fmt_val | Verarbeitung |

## src/services/notification_service.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| notification_service.py:706 | Formwahl / Fähigkeit | Alarm-Indikator-Keys: Ampel-fähige IDs mit use_friendly_format → col_key je Kanal | Verarbeitung |
| notification_service.py:830 | Formatierung | Starkregen-Nowcast → `format_starkregen_hint` | Verarbeitung |

## src/services/trip_alert.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| trip_alert.py:116 | Schwelle | `_BRIEFING_OVERTAKE_FACTOR = 2.0` (Radar überholt Briefing-Niederschlag) | Katalog |
| trip_alert.py:127 | Schwelle | `_OVERTAKE_MIN_ABSOLUTE_MM = 2.0` | Katalog |
| trip_alert.py:2610 | Schwelle | Briefing gilt als „angekündigt“ ab ≥ 0.5 mm | Katalog |

## src/services/alert_gate.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| alert_gate.py:436 | Schwelle | `_COOLDOWN_OVERTAKE_FACTOR = 2.0`, `_COOLDOWN_OVERTAKE_MIN_ABSOLUTE_MM = 2.0` (Duplikat zu trip_alert) | Katalog |

## src/services/radar_service.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| radar_service.py:89 | Schwelle | `HEAVY_RAIN_THRESHOLD_MM_H = 4.0` (Duplikat zu weather_metrics `_PRECIP_HEAVY_MMPH`) | Katalog |
| radar_service.py:137 | Schwelle | `_DRY_THRESHOLD_MM_H = 0.1` | Katalog |
| radar_service.py:169 | Wortskala | `INTENSITY_*` Starker Hagel/Gewitter, Gewitter, Starker/Mäßiger/Leichter Regen, Kein Niederschlag (deutsche Literale) | Katalog |
| radar_service.py:179 | Wortskala | `_INTENSITY_KEYS` → Textkatalog; 205 `_INTENSITY_EN` | Katalog |
| radar_service.py:627 | Schwelle / Wortskala | `intensity_to_text` < 0.1 trocken, < 1.0 leicht, < 4.0 mäßig, sonst stark | Katalog |
| radar_service.py:649 | Schwelle | WMO 95/96/99 konvektiv, 96/99 Hagel | Katalog |

## src/output/renderers/compare_outlook_metric_ids.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| compare_outlook_metric_ids.py:316 | Formatierung | `outlook_columns`: Spalte aus Katalog (unit, decimals, kind, aggregation_label, friendly) | Verarbeitung |
| compare_outlook_metric_ids.py:398 | Formwahl | `_merge_min_max_pairs` Tief/Hoch → Spannenspalte | Verarbeitung |
| compare_outlook_metric_ids.py:452 | Liste-IDs | `_FRIENDLY_CLOUD_IDS` 4 Wolken-IDs [Scan] | Katalog |
| compare_outlook_metric_ids.py:455 | Formwahl / Wortskala | `_friendly_outlook_text`: if-Kette wind_direction→Kompass, Wolken→Emoji, wind/gust→Windwort, precipitation→Tagessummen-Skala, rain_probability→Wahrsch.-Skala, sunshine→Sonnen-Skala (Z.481–493) | Katalog (Zuordnung ID→Skala) + Verarbeitung |
| compare_outlook_metric_ids.py:496 | Fähigkeit | `resolve_hourly_metric_formats` nur IDs mit Stelle "hourly" | Verarbeitung |
| compare_outlook_metric_ids.py:512 | Formwahl | `_friendly_hour_text`: precipitation → Stunden-Skala, sonst wie Ausblick (Z.521) | Verarbeitung |
| compare_outlook_metric_ids.py:528 | Formatierung / Formwahl | `format_outlook_value`: ordinal→_fmt_thunder, enum→_fmt_precip_type, friendly→Wort, sonst Zahl mit decimals+unit | Verarbeitung |
| compare_outlook_metric_ids.py:585 | Formatierung | `format_outlook_range_cell` „min/max“, „13/-“ | Verarbeitung |

## src/output/renderers/email/outlook.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| outlook.py:53 | Schwelle / Wortskala / Farbwahl | `_ACC_STUFEN` Konfidenz ≥ 80 hoch / ≥ 60 mittel / ≥ 40 niedrig / sonst sehr niedrig + Farben | Katalog |
| outlook.py:63 | Farbwahl | `_acc_stufe` / 75 `_acc_wort` | Verarbeitung |
| outlook.py:207 | Liste-IDs | feste Ausblick-Spalten temperature, precipitation, rain_probability, wind, gust, thunder (Z.207–215) | Katalog |
| outlook.py:246 | Formatierung | Fester Ausblick: Temp `:.0f°`, Regen `:.1f`, Wind `:.0f` (Z.249–253) | Katalog (Nachkommastellen) + Verarbeitung |
| outlook.py:259 | Farbwahl | Zellhintergrund je fester Spalte (temperature/precipitation/rain_probability/wind/gust, Z.259–267) | Verarbeitung |
| outlook.py:270 | Farbwahl | Gewitter-Band, grün ohne Hintergrund | Verarbeitung |
| outlook.py:311 | Formatierung | `_gust_text` `:.0f`; 316 `_pr_text` `int %` | Verarbeitung |
| outlook.py:420 | Formatierung | Klartext-Ausblick Spaltenbreiten je Metrik (Z.420–425) | Verarbeitung |
| outlook.py:440 | Farbwahl / Fähigkeit | `_metric_column_bg` enum/AMPEL_ABGELEITET ohne Farbe, ordinal→Gewitterband, sonst severity_for | Verarbeitung |
| outlook.py:477 | Liste-IDs | `_HIKING_FIELD_MAP` temp_min/max, wind_chill_min/max → (Feld, Index) | Katalog |

## src/output/renderers/sms_trip.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| sms_trip.py:66 | Liste-IDs | `build_extended_metric_specs` 14 erweiterte Metriken → MetricSpec | Katalog |
| sms_trip.py:96 | Formwahl | `sms_format_fields` symbol/scale → friendly | Verarbeitung |
| sms_trip.py:128 | Wortskala | `_SMS_RISK_LABELS` (RiskType, Level) → „Gewitter“, „Luftmasse leicht“, „Sturm“, „Wind“, „Regen“, „Kaelte“, „Nebel“, „GratSturm“, „GratWind“ | Katalog |
| sms_trip.py:181 | Kürzel | `_COMPASS_SECTORS` N/NO/O/SO/S/SW/W/NW (Duplikat Kompass) | Katalog |
| sms_trip.py:183 | Schwelle | `_PRECIP_TYPE_SEVERITY` RAIN 0/MIXED 1/SNOW 2/FREEZING_RAIN 3 | Katalog |
| sms_trip.py:189 | Kürzel | `_PRECIP_TYPE_CODE` R/M/S/G | Katalog |
| sms_trip.py:197 | Formatierung | `_sector_for_degrees`, 202 `_dominant_wind_sector`, 219 `_dominant_precip_type_code` | Verarbeitung |
| sms_trip.py:361 | Liste-IDs | Stundenreihen je Metrik (precip, wind, gust, pop, thunder, humidity, dewpoint, cape, uv, cloud_*, visibility, freezing, wind_chill, wind_direction, precip_type, pressure; Z.361–410) | Katalog |
| sms_trip.py:422 | Liste-IDs | Aggregat-Fallback precip/wind/gust/pop | Katalog |
| sms_trip.py:686 | Wortskala | GratSturm/GratWind-Sonderbehandlung | Katalog |

## src/services/trip_command_processor.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| trip_command_processor.py:471 | Kürzel | `_CODES_WETTER` Kürzel-Hilfe (T, D, N, L, TF, FD/FL/FN, R, PR, TH, TH+, W, G, WD, HU, DP, CP, PT, SL, NS24+, CT/CL/CM/CH, VS, SU, UV, HP, FZ) | Katalog |
| trip_command_processor.py:478 | Kürzel | `_CODES_WEITERE` SD, C, Z:/MAX/M: | Katalog |
| trip_command_processor.py:579 | Farbwahl | `_BAND_EMOJI` green/yellow/orange/red → 🟢🟡🟠🔴 | Verarbeitung |
| trip_command_processor.py:582 | Wortskala | `_thunder_words` Stufe → Wort | Verarbeitung |
| trip_command_processor.py:589 | Farbwahl | `_thunder_symbols` Stufe → Kreis-Emoji | Verarbeitung |
| trip_command_processor.py:612 | Liste-IDs | `_TAGESWERTE` temp_min_c, temp_max_c, wind_max_kmh, precip_sum_mm, thunder_level_max, pop_max_pct | Katalog |
| trip_command_processor.py:667 | Formatierung | `_thunder_fmt` | Verarbeitung |
| trip_command_processor.py:722 | Liste-IDs | `_DRILLDOWN_TOKEN_METRIC` thunder/wind/precip → ID [Scan] | Katalog |
| trip_command_processor.py:727 | Kürzel | `_DRILLDOWN_TOKEN_EMOJI` ⛈️/💨/🌧 | Katalog |
| trip_command_processor.py:732 | Formwahl / Formatierung | `_metric_formatter`: is_level / wind_direction_deg→Kompass / precip_type→Wort / dni_wm2→Sonnenstunden / sonst Katalog | Verarbeitung |
| trip_command_processor.py:2104 | Formatierung | Abruf-Stundentabelle: Temp `:.0f°C`, Wind `:.0f km/h`, Regen `:.1f mm`, Gewitter-Symbol (Z.2104–2119) | Verarbeitung |
| trip_command_processor.py:2445 | Formatierung | `_aggregate_day` Tageswerte, Gewitter-Max | Verarbeitung |
| trip_command_processor.py:2474 | Formatierung | `_fmt_day_agg` „T min/max C, wind … km/h, rain … mm, storms …“ (EN) bzw. Emoji-Zeile (Z.2481–2517) | Verarbeitung |
| trip_command_processor.py:2520 | Wortskala | `_stufe_en` Gewitter EN | Verarbeitung |
| trip_command_processor.py:2634 | Formatierung | Mehrtages-Zeile T/Wind/Regen (Z.2634–2672) | Verarbeitung |
| trip_command_processor.py:2690 | Schwelle | Drilldown-Knöpfe: Gewitter ≥ MED, Wind ≥ 40 km/h, Regenwahrsch. ≥ 30 % oder Niederschlag ≥ 1.0 mm | Katalog |

## src/output/renderers/comparison.py (Orts-Vergleich Text/Telegram/SMS)

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| comparison.py:86 | Formatierung / Liste-IDs | `_DAILY_PLAIN_ROWS` je Zeile Formatierer: precip_sum `:.1f mm`, pop_max `:.0f%`, uv_max `:.0f`, freezing_level `:.0f m`, humidity `:.0f%`, pressure `:.0f hPa`, snowfall_limit `:.0f m` … | Katalog (Einheit/Nachkommastellen) |
| comparison.py:120 | Formatierung / Liste-IDs | `_PLAIN_ROWS_UNSORTED` temp_max/min, wind_max, gust_max, sunny_hours „h“, cloud_avg, snow_depth, snow_new `:.0f cm` | Katalog |
| comparison.py:656 | Liste-IDs | `_NIE_EINGESTELLT_IDS` Vorgabezeilen | Katalog |
| comparison.py:664 | Formwahl | `_friendly_overview_text`: SMS nur Wolken-Stufe (SMS_FORMAT_MODE_METRIC_IDS), sonst `_friendly_outlook_text` | Verarbeitung |
| comparison.py:691 | Formwahl / Formatierung | `_fmt_overview_cell` Einfach/Gewitter/Wort | Verarbeitung |
| comparison.py:734 | Liste-IDs | `_METRIC_ID_BY_FRONTEND_KEY` / 737 `_RENDERER_TO_CATALOG_METRIC_ID` | Katalog |
| comparison.py:742 | Formwahl | `_ampel_stunde` @h-Marke über ampel_seite | Verarbeitung |
| comparison.py:770 | Formatierung | `_plain_metric_cell` „Label Wert“ | Verarbeitung |

## src/output/renderers/compare_metric_catalog.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| compare_metric_catalog.py:85 | Wortskala | `_THUNDER_ORDINAL_LABELS` | Katalog |
| compare_metric_catalog.py:106 | Liste-IDs / Formatierung | `COMPARE_METRIC_CATALOG` 26 Einträge key, unit, decimals, metric_id, aggregation, kuerzel_metric_id (zweiter Katalog neben dem zentralen) | Katalog |
| compare_metric_catalog.py:348 | Liste-IDs | `_KEY_BY_METRIC_AGGREGATION` | Katalog |

## src/output/renderers/compare_metric_ids.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| compare_metric_ids.py:15 | Liste-IDs | `FRONTEND_TO_RENDERER_METRIC_ID` Compare-Key → Renderer-ID (sunny_hours_h, freezing_level_m, precip_type_dominant, snowfall_limit_m …) | Katalog |
| compare_metric_ids.py:67 | Liste-IDs | `RENDERER_TO_TRIP_METRIC_ID` temp_max/cloud_avg/precip_sum/pop_max/wind_max/thunder_max → ID [Scan] | Katalog |
| compare_metric_ids.py:93 | Liste-IDs | `CORRIDOR_METRIC_TO_HOUR_KEY` temp_max_c/wind_max_kmh/gust_max_kmh/thunder_level_max → Stundenfeld | Katalog |
| compare_metric_ids.py:368 | Formwahl | `_friendly_effective` Einfach je Kanal | Verarbeitung |

## src/output/renderers/channel_layout.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| channel_layout.py:63 | Liste-IDs | `METRIC_PRIORITY` 29 IDs → Priorität (temperature 95, wind 90 … confidence 8) [Scan] | Katalog |
| channel_layout.py:78 | Fähigkeit | `VISIBILITY_GATE_IDS` 6 Fenster-IDs [Scan] | Katalog |
| channel_layout.py:147 | Formwahl | wind_direction entfällt bei Merge | Verarbeitung |

## src/output/renderers/trip_report.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| trip_report.py:431 | Fähigkeit | `metric_id != "thunder"` Sonderfall | Katalog |
| trip_report.py:638 | Formwahl | wind_direction Merge in Windzeile (auch 691, 736, 751) | Verarbeitung |
| trip_report.py:669 | Formatierung | `_aggregate_night_block` precip_type-Sonderfall (Duplikat zu helpers.aggregate_night_block) | Verarbeitung |
| trip_report.py:709 | Formatierung | `_sunny_hours` je Zeile | Verarbeitung |
| trip_report.py:777 | Formatierung | `_build_units_legend` Einheiten-Gruppen | Verarbeitung |
| trip_report.py:864 | Wortskala | `_RISK_LABELS` RiskType×Level → „⚠️ Thunder“, „Luftmasse leicht“, „Storm“, „Heavy Rain“, „Extreme Cold“, „Low Visibility“, „Exposed Ridge“ | Katalog |
| trip_report.py:903 | Formwahl | `_should_merge_wind_dir` (Duplikat) | Verarbeitung |

## src/app/thunder_scale.py (Gewitter-Skala, faktisch ein zweites Formatmodul für eine Metrik)

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| thunder_scale.py:46 | Formatierung | `format_hail_note` Hagel-Zusatz | Verarbeitung |
| thunder_scale.py:72 | Wortskala | `_THUNDER_ORDER` NONE 0 … HIGH 3 + `thunder_ordinal` | Katalog |
| thunder_scale.py:95 | Wortskala | `_THUNDER_LABEL_VALUE` (identisch zu `_THUNDER_ORDER`) | Katalog |
| thunder_scale.py:129 | Wortskala | `THUNDER_SIGNAL_LABEL_DE/EN` Zutaten (Wettercode, Blitzdichte, CAPE, Blitzpotenzial, Modellläufe) | Katalog |
| thunder_scale.py:230 | Schwelle | `MODELLLAUF_ANHEBUNG_MIN_PCT = 60`, `MODELLLAUF_DAEMPFUNG_MAX_PCT = 10` | Katalog |
| thunder_scale.py:237 | Wortskala | `dampen_…by_one_step` / `elevate_…by_modelllauf` | Verarbeitung |
| thunder_scale.py:283 | Wortskala | LOW-Kern „instabile Luftmasse“ / „schwaches Signal“ (+EN) | Katalog |
| thunder_scale.py:301 | Wortskala | `THUNDER_LABEL_DE` keins/leicht/mittel/hoch; 311 `THUNDER_LABEL_EN` | Katalog |
| thunder_scale.py:319 | Formatierung | `thunder_label` | Verarbeitung |
| thunder_scale.py:340 | Formatierung | `thunder_low_statement` inkl. „CAPE … J/kg“ (Z.373) | Verarbeitung |
| thunder_scale.py:397 | Wortskala | `THUNDER_NIGHT_ADJECTIVE_DE/EN` (z.B. „starkes“) | Katalog |
| thunder_scale.py:408 | Wortskala | `thunder_headline_sentence` „Gewitter möglich“ / „Starkes Gewitter erwartet“ | Katalog |

## src/output/renderers/alert/render.py (Alarm-Mail/SMS)

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| render.py:49 | Formatierung | `_HANDLED_UNITS` m, km, hPa, %, km/h, °C, mm | Katalog |
| render.py:52 | Wortskala | `_thunder_word` Ordinal → Wort; 64 `_stufe_unit` | Verarbeitung |
| render.py:71 | Formatierung | `_val_raw` / `_val` / `_val_delta` Rundung nach Katalog-decimals, Stufenwort bei Level-Metrik | Verarbeitung |
| render.py:114 | Formatierung | `_num_raw` DE/EN-Zahlform, Tausenderpunkt | Verarbeitung |
| render.py:156 | Formatierung | `_unit_suffix`: % ohne Leerzeichen | Katalog |
| render.py:187 | Fähigkeit | `_is_level_metric` | Katalog |
| render.py:225 | Farbwahl | `_FARBWORT` Ampelfarbe → Textschlüssel | Verarbeitung |
| render.py:229 | Kürzel / Farbwahl | `_FARBBUCHSTABE` green/yellow/orange/red → G/Y/O/R | Katalog |
| render.py:230 | Liste-IDs | `_AMPEL_SEITEN_LABEL` temperature/temperature_cold → Label [Scan] | Katalog |
| render.py:385 | Formatierung | `_mm` Niederschlag ganzzahlig | Verarbeitung |
| render.py:866 | Formatierung | `_verschaerfung_text` `:.1f` DE-Komma; 881 SMS „UP x>y“ | Verarbeitung |
| render.py:1081 | Schwelle | `_SMS_ONSET_MENGE_MIN_MM = 0.1` | Katalog |
| render.py:1092 | Kürzel | Onset-Menge über `_fmt_num("R", …)` | Katalog |
| render.py:1305 | Kürzel | Onset-SMS-Kopf "TH" (konvektiv) / "R" | Katalog |
| render.py:2078 | Formatierung | Änderungszeile alt/neu `format_metric_value` bzw. `:.1f` | Verarbeitung |

## src/services/ampel_alarm.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| ampel_alarm.py:27 | Farbwahl | `RANG` green 0 … red 3; 28 `_ALARM_AB_RANG` | Verarbeitung |
| ampel_alarm.py:29 | Farbwahl | `_FARBE_ZU_SCHWERE` yellow/orange/red → MINOR/MODERATE/MAJOR | Verarbeitung |
| ampel_alarm.py:34 | Farbwahl | `_SEITEN_SCHLUESSEL` oben/unten → Stufenschlüssel | Verarbeitung |
| ampel_alarm.py:40 | Schwelle | `_sprung` Mindest-Sprung je AlertMetric | Katalog |
| ampel_alarm.py:59 | Liste-IDs / Fähigkeit | `AMPEL_FELDER` alarmfähige Felder: temperature (temp_max_c oben, temp_min_c unten), wind, gust, precipitation, fresh_snow, visibility (unten), uv_index, thunder (stufe) + AlertMetric | Katalog |
| ampel_alarm.py:108 | Formatierung | `_ordinal` Gewitter → Zahl | Verarbeitung |
| ampel_alarm.py:114 | Farbwahl | `_farbe` Wert → Ampelfarbe | Verarbeitung |

## src/output/tokens/metrics.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| tokens/metrics.py:14 | Kürzel / Wortskala | `LEVELS` 0 „-“, 1 L, 2 M, 3 H (Gewitter-SMS) | Katalog |
| tokens/metrics.py:20 | Kürzel / Schwelle | `_CLOUD_STUFEN` CLR/FEW/SCT/BKN/OVC mit Bandmitten 5/20/50/80/95 | Katalog |
| tokens/metrics.py:23 | Wortskala | `cloud_stufe` | Verarbeitung |
| tokens/metrics.py:32 | Kürzel / Fähigkeit | `STUFEN_FN` CT/CL/CM/CH → cloud_stufe | Katalog |
| tokens/metrics.py:37 | Formatierung / Kürzel | `_fmt_num` R `:.1f`, PR `int %`, sonst ganzzahlig | Katalog (Nachkommastellen) + Verarbeitung |
| tokens/metrics.py:49 | Farbwahl | `_STUFEN_RANG`, 52 `_peak_per_ampel_stufe` | Verarbeitung |
| tokens/metrics.py:80 | Formatierung | `render_threshold_peak_value` Erst-/Spitzen-Token | Verarbeitung |
| tokens/metrics.py:143 | Formatierung | `render_temperature` ganzzahlig; 150 `render_inverse_min_value` | Verarbeitung |

## src/output/tokens/hazard_symbols.py (Abgrenzung)

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| hazard_symbols.py:20 | Kürzel | `HAZARD_SMS_SYMBOLS` amtliche Warnarten (TS, RA, WG, SN …) – überlappen mit Metrik-Kürzeln, sind aber keine Metriken | (eigener Warnungs-Katalog) |
| hazard_symbols.py:56 | Kürzel | `LEVEL_LETTERS` 2/3/4 → L/M/H (doppelt zu tokens/metrics.LEVELS) | (eigener Warnungs-Katalog) |

## src/output/renderers/email/thunder_branch.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| thunder_branch.py:30 | Formatierung | `_THUNDER_TOKEN_RE` / `_thunder_token_parts` Token „leicht@5(hoch@15)“ parsen | Verarbeitung |
| thunder_branch.py:54 | Wortskala | `_token_is_pure_low` nur „leicht“ | Verarbeitung |
| thunder_branch.py:74 | Formwahl | `resolve_thunder_day_branch` Tag/Nacht-Zweig | Verarbeitung |
| thunder_branch.py:206 | Formatierung | `thunder_cell_html` / `_plain` / `_compact` / `_telegram` | Verarbeitung |
| thunder_branch.py:263 | Fähigkeit | `thunder_column_index` (metric_id == "thunder", Z.274) | Verarbeitung |

## src/output/renderers/email/plain.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| plain.py:344 | Liste-IDs | Nacht-Hinweis nur bei temperature/freezing_level (Duplikat html.py:1166) | Katalog |

## src/output/renderers/email/compact.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| compact.py:58 | Kürzel | `_ASCII_MAP` „⚡“ → „T“ (Gewitter-Symbol) | Katalog |
| compact.py:292 | Formatierung | Ausblickzeile Spaltenbreiten temp/precip/wind/thunder | Verarbeitung |

## src/output/adapters/trip_result.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| trip_result.py:106 | Formatierung | Stundenzeile Temp `:.1f°C` (gefühlt), Wind `:.0f km/h` (Böen) | Verarbeitung |
| trip_result.py:118 | Formatierung / Wortskala | Niederschlag `:.1f mm`, Neuschnee `:.0f cm Schnee`, sonst „trocken“ (Z.118–125) | Verarbeitung |
| trip_result.py:149 | Formatierung | Zusammenfassung Temp/gefühlt/Wind/Böen/Niederschlag/Neuschnee/Schneehöhe/Schneefallgrenze/Sicht km/Bewölkung % (Z.149–196, deutsche Labels) | Katalog (Labels/Einheit) + Verarbeitung |
| trip_result.py:207 | Kürzel / Schwelle | Default-MetricSpecs N, D, W threshold 10, G threshold 20 | Katalog |

## src/services/weather_pattern.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| weather_pattern.py:48 | Schwelle / Wortskala | `compute_stability` confidence ≥ 75 STABIL, ≥ 50 WECHSELHAFT, sonst FRAGIL | Katalog |

## src/output/renderers/orte_sms.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| orte_sms.py:47 | Kürzel / Fähigkeit | `_IMMER_AUS` N, FN, TH+:, TF im Ortsvergleich nie | Katalog |
| orte_sms.py:52 | Kürzel / Liste-IDs | Kürzel → Summary-Feld (L, D, FL, FD, SU, HP, SD, NS24+, SL) | Katalog |
| orte_sms.py:59 | Kürzel / Liste-IDs | Stunden-Kürzel → (Feld, Reihe) R, PR, W, G, CP, UV, CT, CL, CM, CH | Katalog |
| orte_sms.py:79 | Kürzel | `_BEREICH` D↔L, FD↔FL | Katalog |
| orte_sms.py:132 | Schwelle | `nur_positiv` Werte ≤ 0 entfallen | Verarbeitung |

## src/output/renderers/fallback_notice.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| fallback_notice.py:63 | Liste-IDs | `_METRIK_KENNUNGEN` Provider-Feldnamen (temperature_2m, wind_gusts_10m, precipitation_probability …) | Katalog (Provider-Abbildung) |

## src/services/windrichtung.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| windrichtung.py:22 | Fähigkeit | `MODI` aus/gegenwind/sektoren | Katalog |
| windrichtung.py:24 | Kürzel | `SEKTOREN` N … NW (Duplikat zu sms_trip/geo) | Katalog |
| windrichtung.py:26 | Schwelle | `MIN_LUFTLINIE_KM = 0.3` | Verarbeitung |
| windrichtung.py:66 | Formwahl | `zeilen_wert_kmh` Wind-Ampelwert aus Richtungs-Ampel | Verarbeitung |

## src/utils/geo.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| geo.py:14 | Kürzel | Kompass-Sektoren EN/DE | Katalog |

## Nachtrag src/services/weather_change_detection.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| weather_change_detection.py:1135 | Schwelle / Farbwahl | `_classify_severity` Verhältnis Δ/Schwelle ≥ 2.0 MAJOR, ≥ 1.5 MODERATE, sonst MINOR | Katalog (Faktoren) + Verarbeitung |

## src/services/trip_report_scheduler.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| trip_report_scheduler.py:396 | Wortskala | Trend-Notiz Gewitter LOW → Luftmassen-Satz, sonst „Gewitter“ | Verarbeitung |
| trip_report_scheduler.py:404 | Schwelle | Trend-Notiz Regen > 5 mm, Wind > 40 km/h (fest) | Katalog |
| trip_report_scheduler.py:3333 | Formwahl | Gewitter-Stunde im Tagesfenster (ThunderLevel != NONE) | Verarbeitung |

## src/services/segment_weather.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| segment_weather.py:571 | Liste-IDs | Nacht-Abruf nötig bei temperature_night / wind_chill_night / thunder | Katalog |

## src/services/validator_render_service.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| validator_render_service.py:620 | Kürzel / Formwahl | SMS-Vorschau-Specs aus SMS_SYMBOL_BY_METRIC, Format-IDs | Verarbeitung |
| validator_render_service.py:635 | Kürzel / Fähigkeit | Sonderfall wind_chill → 'TF' braucht aktive Spec | Katalog |

## src/services/deviation_alert_engine.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| deviation_alert_engine.py:33 | Liste-IDs / Fähigkeit | `D4_ALERT_METRICS` freezing_level, snow_line, thunder_onset, precipitation_heavy_onset (Δ-Logik) | Katalog |

## src/services/alert_urgency.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| alert_urgency.py:20 | Kürzel | `_LETTER_TO_URGENCY` L/M/H → LOW/MODERATE/HIGH | Katalog |
| alert_urgency.py:57 | Wortskala | Radar-Intensität stark→HIGH, mäßig→MODERATE, sonst LOW; konvektiv HIGH | Katalog |

## src/services/alert_log.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| alert_log.py:213 | Liste-IDs | Onset-Flag → ("thunder","max") / ("precipitation","sum") | Katalog |

## src/services/placements_view_service.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| placements_view_service.py:460 | Fähigkeit | wind_direction von Platzierung ausgenommen | Katalog |

## src/app/cloud_cover.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| cloud_cover.py:21 | Schwelle | `HOHE_WOLKEN_GEWICHT = 0.5`, `HOCHLAGE_SCHWELLE_M = 2500` (wirksame Bewölkung) | Katalog |

## src/app/model_registry.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| model_registry.py:75 | Fähigkeit | "cape" in fallback_metrics | Katalog |
| model_registry.py:225 | Schwelle | `CAPE_REFERENZ_NIVEAU_JKG = 1000.0` | Katalog |
| model_registry.py:260 | Schwelle | `CAPE_LEITER_MED_ABSOLUT_JKG = 1000.0`, `_HIGH_ = 2500.0` | Katalog |

## src/providers/* (Provider-Abbildung, Randfälle)

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| openmeteo.py:270 | Liste-IDs | Abgefragte Open-Meteo-Parameter (wind_gusts_10m, precipitation_probability, cape, uv_index …) | (Provider-Abbildung) |
| openmeteo.py:286 | Schwelle | `THUNDER_CODES = {95, 96, 99}` (Duplikat radar_service) | Katalog |
| openmeteo.py:294 | Schwelle | `ENSEMBLE_THUNDER_MIN_MEMBERS = 20` | Katalog |
| openmeteo.py:466 | Liste-IDs | Provider-Feld → dp-Feld (precipitation→precip_1h_mm, visibility→visibility_m, cape→cape_jkg …) | (Provider-Abbildung) |
| openmeteo.py:731 | Wortskala | `_parse_thunder_level` Gewittercode → HIGH, sonst NONE | Katalog |
| openmeteo.py:866 | Schwelle | Ensemble-Spread erst ab ≥ 5 Mitgliedern | Verarbeitung |
| geosphere.py:188 | Schwelle | `_calculate_wind_chill` nur T ≤ 10 °C und Wind ≥ 4.8 km/h | Katalog |
| geosphere.py:803 | Formatierung | Niederschlag auf 1 Nachkommastelle gerundet | Katalog |
| thunder_enrichment.py:53 | Liste-IDs | "cape" → cape_geosphere_jkg | (Provider-Abbildung) |
| thunder_enrichment.py:208 | Schwelle | `_RADAR_OVERRIDE_FENSTER_MIN = 90`, `_RADAR_OVERRIDE_BLITZDICHTE_MIN = 0.005` | Katalog |
| thunder_enrichment.py:263 | Schwelle | Radar-Override hebt Gewitter mindestens auf MED | Katalog |

## src/analysis/thunder_ablation.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| thunder_ablation.py:163 | Formatierung | `stufe_gegen_niederschlag` (Analyse-Werkzeug, cape/precipitation) | (Analyse, kein Produktpfad) |

## api/routers/config.py

| Datei:Zeile | Art | Inhalt kurz | Gehört in |
|---|---|---|---|
| config.py:39 | Kürzel | `sms_symbols_for` Mehrfach-/Einzel-Symbole, `rstrip(":")` Grammatik-Doppelpunkt | Verarbeitung |


## Zusammenfassung

Zeilen gesamt: **461** in **58** Datei-Abschnitten. Davon 39 Funde des bestehenden Metrik-Listen-Scans (gekennzeichnet „[Scan]“, teils zu einer Zeile zusammengefasst); der Rest stammt aus der erweiterten Suche (if-Ketten, Schwellen, Wortskalen, Kürzel, Farb-/Formwahl, Formatierung), die der Scan per Konstruktion nicht sieht.

### Top 10 Dateien nach Treffern

| Rang | Datei | Treffer |
|---|---|---|
| 1 | src/output/renderers/email/helpers.py | 63 |
| 2 | src/output/renderers/email/compare_html.py | 32 |
| 3 | src/services/weather_metrics.py | 23 |
| 4 | src/services/comparison_scoring.py | 19 |
| 5 | src/output/renderers/email/html.py | 17 |
| 6 | src/services/trip_command_processor.py | 16 |
| 7 | src/output/tokens/builder.py | 16 |
| 8 | src/output/renderers/alert/render.py | 15 |
| 9 | src/services/day_comparison.py | 14 |
| 10 | src/output/renderers/narrow.py | 13 |

### Auffällige Duplikate (Hinweis für die Konsolidierung)

- Starkregen-Schwelle 4,0 mm/h doppelt: weather_metrics.py:645 und radar_service.py:89.
- Gewitter-Wettercodes 95/96/99 doppelt: openmeteo.py:286 und radar_service.py:649.
- Überhol-Faktor/-Mindestmenge 2,0 doppelt: trip_alert.py:116/127 und alert_gate.py:436.
- Kompass-Sektoren dreifach: sms_trip.py:181, windrichtung.py:24, geo.py:14.
- Niederschlagsart-Rangfolge widersprüchlich: weather_metrics.py:1134 und sms_trip.py:183 (RAIN 0 / MIXED 1 / SNOW 2 / FREEZING_RAIN 3) vs. weather_metrics.py:1398 (RAIN 0 / SNOW 1 / MIXED 2, ohne FREEZING_RAIN).
- Wind-Wortskala zweimal mit verschiedenen Grenzen: weather_metrics.py:124 (10/25/40) vs. compact_summary.py:524 (15/35/60); Niederschlags-Adjektiv compact_summary.py:447 (2/10) parallel zu weather_metrics.py:145.
- Feste Trend-Schwellen (Regen > 1 mm / > 5 mm, Wind > 30/40/50 km/h) in helpers.py:1082/1088, trip_report_scheduler.py:404, trip_command_processor.py:2690 ignorieren die Abo-Ampel.
- Zweiter Compare-Katalog mit Einheit/Nachkommastellen: compare_metric_catalog.py:106 neben metric_catalog.py; dazu Formatierer in compare_html.py:188–211 und comparison.py:86–137.
- Risiko-Wortlisten doppelt: sms_trip.py:128 und trip_report.py:864.
- Night-/Merge-Logik doppelt: helpers.aggregate_night_block vs. trip_report._aggregate_night_block; should_merge_wind_dir in helpers.py:66, trip_report.py:903, compare_html.py:1132.
