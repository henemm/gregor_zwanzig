# Context: Weather Metrics UX

## Request Summary
Wetter-Metriken benutzerfreundlicher gestalten: 1) Neue, konsistente englische col_labels im MetricCatalog, 2) Level-basierte Formatierung für Cloud/CAPE/Visibility statt roher Zahlenwerte, 3) Config-UI zeigt col_label neben dem deutschen Label.

## Related Files
| File | Relevance |
|------|-----------|
| `src/app/metric_catalog.py` | **PRIMARY** — col_label Werte ändern (19 Metriken) |
| `src/formatters/trip_report.py` | **PRIMARY** — `_fmt_val()` erweitern (Cloud→Emoji, CAPE→Level, Visibility→Level) |
| `src/web/pages/weather_config.py` | **PRIMARY** — Checkbox-Label um col_label ergänzen |
| `docs/specs/modules/weather_config.md` | Spec aktualisieren |
| `tests/unit/test_trip_report_formatter_v2.py` | Tests für neue Formatierung |

## Existing Patterns
- `_fmt_val()` hat bereits bedingte HTML-Formatierung (Farben für Gust, Precip, Pop, CAPE)
- Thunder nutzt bereits Emoji-Darstellung (⚡⚡ / ⚡ mögl.)
- Visibility hat bereits Smart-Formatting (k-Suffixe)
- Weather Config UI gruppiert Metriken nach Kategorien mit `label_de`

## Dependencies
- **Upstream:** MetricCatalog → col_label wird von `get_col_defs()` gelesen
- **Downstream:** `trip_report.py` liest col_defs für Tabellenheader; Tests referenzieren KEINE col_labels direkt

## Existing Specs
- `docs/specs/modules/weather_config.md` — MetricDefinition Datenstruktur
- `docs/specs/modules/openmeteo_additional_metrics.md` — Pop/CAPE Pipeline

## Risks & Considerations
- **Keine Test-Brüche erwartet:** Tests referenzieren col_label nicht direkt
- **SMS-Formatter:** Nutzt `compact_label`, nicht `col_label` → nicht betroffen
- **Fixture:** `fixtures/renderer/expected_email.html` referenziert col_labels im HTML-Header → muss aktualisiert werden
- **Scope:** 3 Dateien + Spec + ggf. Fixture = passt in Scoping-Limits

## Agreed Label Changes
| Metrik-ID | Alt | Neu |
|-----------|-----|-----|
| wind_chill | Felt | Feels |
| thunder | Thund | Thunder |
| snowfall_limit | Snow | SnowL |
| cloud_total | Clouds | Cloud |
| cloud_low | CLow | CldLow |
| cloud_mid | CMid | CldMid |
| cloud_high | CHi | CldHi |
| dewpoint | Dew | Cond° |
| visibility | Vis | Visib |
| rain_probability | Pop | Rain% |
| cape | CAPE | Thndr% |
| freezing_level | 0Gr | 0°Line |
| snow_depth | SnDp | SnowH |

## Agreed Formatting Changes
- **Cloud (all):** Prozent → Emoji (☀️/🌤️/⛅/🌥️/☁️)
- **CAPE:** J/kg → Level-Emoji (🟢/🟡/🟠/🔴)
- **Visibility:** Meter → Level-Text (good/fair/poor/⚠️ fog)
