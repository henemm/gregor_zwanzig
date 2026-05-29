# Context: Issue #435 — Metrik-Format-Modi (Roh/Skala/Vereinfacht/Symbol)

## Request Summary

Aus Epic #428 ausgelagert: Wizard-Step 3 zeigt **pro Metrik** ein Dropdown mit vier Optionen — *Roh / Skala / Vereinfacht / Symbol*. Das Backend kennt heute nur `use_friendly_format: bool` (zwei Zustände). Backend-Modell und Renderer sollen so erweitert werden, dass jede Metrik einen Format-Modus mit 2–4 Optionen unterstützt, und das Frontend-Dropdown nur die *erlaubten* Optionen pro Metrik anzeigt.

PO-Frage zuerst: **Welche Metriken haben heute schon eine Format-Umschaltung?** Bauchgefühl: nur CAPE und Bewölkung. Ergebnis der Recherche siehe unten.

## Status quo der Format-Umschaltung (heute)

Das Modell kennt pro Metrik nur **„roh" vs. „friendly"**. Die Wirkung von `use_friendly_format=True` ist je Metrik unterschiedlich — manchmal Skala, manchmal Symbol, manchmal nichts:

| Metrik | Heute roh | Heute „friendly" | Wirkungs-Typ | Code-Quelle |
|---|---|---|---|---|
| `cloud_total`/`cloud_low`/`cloud_mid`/`cloud_high` | `50%` | `☀️🌤️⛅🌥️☁️` (5 Stufen nach %) | **Symbol** | `src/output/renderers/email/helpers.py:370–383`, `src/app/metric_catalog.py:220` |
| `cape` | `1500` (J/kg) | `🟢🟡🟠🔴` (Stufen 300/1000/2000) | **Symbol** (Ampel) | `helpers.py:409–424`, `metric_catalog.py:188` |
| `wind_direction` | `180°` | `N/NE/E/SE/S/SW/W/NW` (8-Punkt-Kompass) | **Skala** | `helpers.py:447–448`, `degrees_to_compass()` in `src/services/weather_metrics.py:175`, `metric_catalog.py:130` |
| `visibility` | `10000 m` / `10 km` | `good / fair / poor / ⚠️ fog` | **Vereinfacht** (mit Symbol bei Nebel) | `helpers.py:425–444`, `metric_catalog.py:261` |
| `sunshine` | `4.2 h` | `☀️/🌤️/⛅/🌥️/☁️/🌙` (über `get_weather_emoji`: WMO + DNI + cloud%) | **Symbol** (kontextabhängig) | `helpers.py:384–398`, `get_weather_emoji()` in `weather_metrics.py:62–88`, `metric_catalog.py:275` |
| `thunder` | (keine Zahl, nur „möglich HH–HH") | `⚡` / `⚡⚡` + Farbe | **Symbol** | `helpers.py:339–346`, `metric_catalog.py:179` |
| **alle anderen** (temperature, wind_chill, humidity, dewpoint, wind, gust, precipitation, rain_probability, confidence, snowfall_limit, precip_type, uv_index, pressure, freezing_level, snow_depth, fresh_snow) | numerisch | identisch — `friendly_label=""` und `has_friendly_format=False` | keine Umschaltung implementiert | `metric_catalog.py:57–322` |

**Stand der Wahrheit:** Sechs Metrik-Gruppen haben heute eine echte Umschaltung — `cloud_*` (4 Spalten), `cape`, `wind_direction`, `visibility`, `sunshine`, `thunder`. Der User-Verdacht „nur CAPE und Bewölkung" ist **zu eng** — Wind-Richtung, Sicht, Sonnenschein und Gewitter sind ebenfalls schon umschaltbar. *Keine* Metrik hat heute 3 oder 4 Modi parallel.

Maßgeblich für „kann umgeschaltet werden": `MetricDefinition.has_friendly_format` (`metric_catalog.py:48–50`), berechnet als `bool(friendly_label)`. Frontend liest das schon aus `/api/metrics` (`Step3Weather.svelte:92`).

## Frontend-Stand (UI bereits da, Backend-Mapping kollabiert auf 2 Zustände)

`frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte:211–221` zeigt **für jede Metrik** alle vier Optionen — auch für solche ohne `friendly_label` (z.B. Temperatur, Druck). Beim Speichern (`Step3Weather.svelte:140–146`) wird der UI-Modus über `mode !== 'raw'` auf das alte boolean platt gemappt:

```ts
type FormatMode = 'raw' | 'scale' | 'simplified' | 'symbol';
// ...
if (m) m.use_friendly_format = mode !== 'raw';  // scale==simplified==symbol == true
```

Konsequenz: „Skala", „Vereinfacht" und „Symbol" sind heute im Backend **nicht unterscheidbar** — alles wird zur selben „friendly"-Darstellung gerendert. Das Dropdown wirkt für den Nutzer falsch.

## Related Files

| File | Relevance |
|---|---|
| `src/app/metric_catalog.py` | `MetricDefinition` + Liste der 25 Metriken. Hier muss der erlaubte Modus-Satz pro Metrik definiert werden. |
| `src/app/models.py:465` | `MetricConfig.use_friendly_format: bool` — das Persistenz-Feld, das ersetzt/erweitert werden muss. |
| `src/app/loader.py` (Zeilen 347, 377, 657, 798, 1047) | Liest `use_friendly_format` aus API-Payloads in `MetricConfig`. Migrations-/Lese-Pfade. |
| `src/output/renderers/email/helpers.py:332–449` | `fmt_val()` — zentraler Renderer. Verzweigt per `key` × `use_friendly`. Hier landet die Modus-Logik. |
| `src/output/renderers/email/helpers.py:505–516` | `build_friendly_keys()` — sammelt heute Spalten-Keys mit `use_friendly=True`. Muss auf „Modus pro Spalte" umgestellt werden. |
| `src/formatters/trip_report.py:640–650` | `_build_friendly_keys()` (zweite Stelle, fast identisch) — Konsolidierungsbedarf. |
| `src/formatters/trip_report.py:503–512, 627–629` | Sonderpfade für CAPE-Highlight und Wind-Richtungs-Merge — hängen am alten Flag. |
| `src/formatters/compact_summary.py:116, 133, 154, 254, 315` | Natursprach-Briefing nutzt `friendly` ebenfalls (Wolken-Emoji, Wind-Kompass, Thunder-Emoji). |
| `src/services/weather_metrics.py:62–88, 175` | `get_weather_emoji()`, `degrees_to_compass()` — wiederverwendbare Friendly-Bausteine. |
| `frontend/src/lib/types.ts:127–138` | `WeatherConfigMetric.use_friendly_format?: boolean` — Frontend-Typ. |
| `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte:70–146, 211–221` | Wizard-Dropdown — UI ist schon da, Mapping fällt heute auf bool zusammen. |
| `frontend/src/lib/components/WeatherConfigDialog.svelte:206–212` | Locations-/Subscription-Dialog hat *zwei* Optionen (Segmented Control „Roh"/„Indikator") — muss angeglichen werden. |
| `tests/integration/test_friendly_format_email_and_alerts.py:168–195` | `TestEmailFriendlyVsRawFormatting` — abgedeckte Metriken: `cloud_total`, `cape`, `visibility`. |

## Existing Patterns

- **Katalog-getrieben:** `MetricDefinition` ist die Single Source of Truth für „was kann eine Metrik". Felder wie `summary_fields`, `display_thresholds`, `risk_thresholds`, `default_aggregations` sind schon dort. **Erlaubter Modus-Satz pro Metrik gehört dorthin** (additives Feld, z.B. `format_modes: tuple[str, ...] = ()`).
- **Property-Ableitung:** `has_friendly_format` ist eine `@property` aus `friendly_label`. Gleiche Mechanik kann für „erlaubte Modi" greifen, ohne jeden Eintrag der 25-Item-Liste manuell zu erweitern (Default-Heuristik + Override pro Metrik wo nötig).
- **Renderer-Verzweigung per Spalten-Key:** `fmt_val()` in `email/helpers.py` ist eine große `if key == "cloud" ... elif key == "cape" ...`-Kaskade. Pattern bleibt, nur dass statt `bool` jetzt `format_mode: str` verzweigt.
- **Datenschema-Pre-Snapshot:** Schreib-Pfade in `src/app/models.py` triggern `data_schema_backup.py` (siehe CLAUDE.md → „Daten-Schema-Reworks"). Migration `use_friendly_format: bool → format_mode: enum` ist persistenz-relevant.
- **Backward-Compat:** Letzte vier Epic-PRs (#429, #430/431, #432/437) haben jeweils additive Felder eingeführt + Reader-Kompatibilität für Alt-Datensätze ([[project-epic-428-done]]). Gleiches Muster hier nutzen: neues Feld neben dem alten, Lese-Pfade verstehen beide.

## Dependencies

**Upstream (was wir nutzen):**
- `MetricDefinition.friendly_label` — Quelle für „Symbol/Skala existiert überhaupt"
- `get_weather_emoji()` und `degrees_to_compass()` aus `weather_metrics.py` — bestehende Friendly-Bausteine
- `MetricConfig` (Pydantic in `models.py`) — Trip-/Location-/Subscription-DisplayConfig hängen daran

**Downstream (was uns nutzt):**
- HTML-Email-Renderer (`trip_report.py` + `email/helpers.py`)
- Compact-Summary (Briefing-Texte in `compact_summary.py`)
- Alert-Pipeline (`tests/integration/test_friendly_format_email_and_alerts.py` deckt Alerts mit)
- Wizard-Step 3, WeatherConfigDialog (Locations/Subscriptions), evtl. weitere Frontend-Ansichten

## Existing Specs

- `docs/specs/modules/epic_191_state_migration.md` — Vorbild für additive Feld-Migration mit Backward-Compat
- Es gibt **keine** dedizierte Spec für `metric_catalog.py` heute. Diese Issue ist ein guter Anlass, mindestens die Modus-Tabelle festzuschreiben.

## Risks & Considerations

1. **Definitions-Frage (Produkt):** Was bedeutet *Skala* vs. *Vereinfacht* vs. *Symbol* genau? Beispiele aus dem heutigen Code legen folgendes nahe — der PO sollte das bestätigen:
   - **Roh** = numerisch mit Einheit (`12 km/h`, `1500 J/kg`, `180°`).
   - **Skala** = standardisierte fachliche Klassen (Beaufort, Octa, Kompass-Punkte) — Text, kein Emoji.
   - **Vereinfacht** = Alltagssprache, kein Symbol (`„leicht bewölkt"`, `„starker Wind"`, `„Nebel"`).
   - **Symbol** = Emoji/Icon allein oder dominant (`☁️`, `⚡`, `🟡`).
   *Heute mischt der Code „Skala" und „Symbol" unter dem einen `friendly`-Flag.* Beispiel: Wolken-`friendly` = Emoji (Symbol), Wind-Richtungs-`friendly` = N/NE/E (Skala).
2. **Erlaubter Modus-Satz pro Metrik:** Nicht jede Metrik kennt alle vier. Vorschlag (zur PO-Bestätigung in Phase 2):
   - Temperaturen, Druck, Schneehöhe, UV, Feuchte, Taupunkt, Nullgradgrenze, Schneefallgrenze: **nur Roh** (heute friendly_label leer, kein sinnvolles Symbol)
   - Wind/Böen, Niederschlag, Regenwahrscheinlichkeit: **Roh + Vereinfacht** (Beaufort/„leicht/mäßig/stark", Regenklassen)
   - Wind-Richtung: **Roh + Skala** (Grad / Kompass-Punkte)
   - Wolken (alle 4 Layer), CAPE, Sonnenschein: **alle vier** (Roh, Skala = Octa/Stufenzahl, Vereinfacht = „heiter/bedeckt"/„schwach/stark", Symbol = Emoji)
   - Sicht: **Roh + Vereinfacht + Symbol** (m/km, „klar/Nebel", ⚠️)
   - Gewitter: **Roh + Symbol** (Zähler / ⚡)
3. **Schreibender Pfad ohne UI:** `WeatherConfigDialog.svelte` (Locations/Subscriptions) zeigt heute nur zwei Optionen. Wenn das Modell auf 4 Modi geht, brauchen beide Frontends dieselbe Auswahl-Quelle (am besten serverseitig per `/api/metrics`, das `format_modes` ausliefert).
4. **Datenmigration:** `use_friendly_format=False → 'raw'`, `True → 'scale'` (oder `'symbol'` je nach Metrik?). Default-Mapping muss pro Metrik festgelegt werden, sonst bekommen Bestands-Trips beim ersten Save einen anderen Look. Pre-Snapshot via `data_schema_backup.py` ist Pflicht.
5. **Zweite Renderer-Stelle:** `_build_friendly_keys()` existiert sowohl in `trip_report.py:640` als auch `email/helpers.py:505` (Duplikat). [[feedback-consolidate-duplicates]] gilt — vor dem Erweitern konsolidieren.
6. **Compact-Summary fällt mit-um:** `_format_clouds()`, `_format_wind()`, `_format_thunder()` hängen am `friendly`-Flag — Briefing-Texte verändern sich, falls Wolken auf „Roh" gestellt werden. Acceptance muss das mit-prüfen.
7. **LoC-Budget:** Modell + Loader + zwei Renderer + Compact-Summary + Frontend-Typ + Wizard-Mapping + Dialog + Tests — realistisch >250 LoC. `loc_limit_override` in Phase 6 vorbereiten.
8. **PO-Pre-Check (aus [[project-epic-428-done]]):** „Backend-Verkabelung folgt später"-Schätzung gegenchecken — hier ist das Gegenteil: die UI ist schon vollständig da, das Backend hängt hinterher. Implementierung ist also „Backend ans Frontend anpassen", nicht umgekehrt.

## Offene Punkte für Phase 2 (Analyse)

- Verbindliche Modus-Tabelle pro Metrik (PO-Bestätigung)
- Default-Modus pro Metrik (was sieht der Nutzer ohne explizite Wahl)
- Migrations-Mapping `bool → mode` pro Metrik
- Konsolidierung der beiden `_build_friendly_keys()`-Implementierungen vor oder mit der Erweiterung

---

## Phase 2 — Analyse-Ergebnisse (2026-05-28)

### PO-Entscheidungen

1. **Scope: Konservativ.** Nur Modi bauen, die heute schon im Code existieren — keine neuen Friendly-Mappings (Beaufort-Tabellen, Temperatur-Symbole) erfinden. Folge-Issues können später additiv weitere Modi pro Metrik addieren. Issue-Beispiel „Temperatur = Roh+Vereinfacht+Symbol" bleibt damit Vision für später, nicht Auftrag für diese Iteration.
2. **Standort-Dialog mit ziehen:** `WeatherConfigDialog` (Locations/Subscriptions) bekommt die selbe N-Optionen-Auswahl pro Metrik wie der Wizard. Die heutige 2-Wege-Segmented-Control wird zur dropdown-getriebenen Auswahl aus `metric.format_modes`.
3. **Vereinfacht-Kürzel in HTML-Tabelle:** „Vereinfacht" wirkt für `wind`/`gust`/`precipitation` auch in der HTML-Tabelle der E-Mail-Reports — als knappes Kürzel-Adjektiv (z.B. „schwach"/„mäßig"/„stark") ohne nachfolgende Zahl. Compact-Summary verwendet weiterhin die volle Phrase („schwacher Wind 12 km/h"). Die Adjektive existieren bereits in `src/formatters/compact_summary.py:271–279` (Wind) und `:187–192` (Niederschlag) — sie werden in einen kleinen Helfer extrahiert und von `fmt_val` mit-genutzt.

### Verbindliche Modus-Tabelle (alle 25 Metriken)

| Metrik-ID | `format_modes` | `default_format_mode` | Heutiger Code-Pfad |
|---|---|---|---|
| `temperature` | `("raw",)` | `raw` | — |
| `wind_chill` | `("raw",)` | `raw` | — |
| `humidity` | `("raw",)` | `raw` | — |
| `dewpoint` | `("raw",)` | `raw` | — |
| `wind` | `("raw","simplified")` | `raw` | `compact_summary.py:271–279` Adjektive → neu in Tabelle gespiegelt |
| `gust` | `("raw","simplified")` | `raw` | analog `wind` |
| `wind_direction` | `("raw","scale")` | `scale` | `degrees_to_compass()` in `weather_metrics.py:175`; `helpers.py:447–448` |
| `precipitation` | `("raw","simplified")` | `raw` | `compact_summary.py:187–192` Adjektive → neu in Tabelle gespiegelt |
| `rain_probability` | `("raw",)` | `raw` | — |
| `confidence` | `("raw",)` | `raw` | — |
| `thunder` | `("symbol",)` | `symbol` | `helpers.py:339–346` ⚡/⚡⚡ — kein numerischer Raw-Render (Enum NONE/LOW/MED/HIGH) |
| `cape` | `("raw","symbol")` | `symbol` | `helpers.py:409–424` 🟢🟡🟠🔴 |
| `snowfall_limit` | `("raw",)` | `raw` | — |
| `precip_type` | `("raw",)` | `raw` | — |
| `cloud_total` | `("raw","symbol")` | `symbol` | `helpers.py:370–383` ☀️🌤️⛅🌥️☁️ |
| `cloud_low` | `("raw","symbol")` | `symbol` | analog |
| `cloud_mid` | `("raw","symbol")` | `symbol` | analog |
| `cloud_high` | `("raw","symbol")` | `symbol` | analog |
| `visibility` | `("raw","simplified")` | `simplified` | `helpers.py:425–444` good/fair/poor/⚠️fog (Text dominiert → simplified) |
| `sunshine` | `("raw","symbol")` | `symbol` | `helpers.py:384–398` über `get_weather_emoji()` |
| `uv_index` | `("raw",)` | `raw` | — |
| `pressure` | `("raw",)` | `raw` | — |
| `freezing_level` | `("raw",)` | `raw` | — |
| `snow_depth` | `("raw",)` | `raw` | — |
| `fresh_snow` | `("raw",)` | `raw` | — |

**Wichtige Tech-Lead-Festlegung zu `visibility`:** Heutiger Output `"good"/"fair"/"poor"/"⚠️ fog"` wird als `simplified` klassifiziert (Text dominiert, ⚠️ ist Akzent). Eine separate reine `symbol`-Variante (z.B. ✅/⚠️) wird in dieser Iteration nicht angeboten — Folge-Issue, falls gewünscht.

### Migrations-Mapping (Read-Path-Adapter in `loader.py`)

```python
def _resolve_format_mode(mc_data: dict, metric_id: str) -> str:
    if (raw := mc_data.get("format_mode")) is not None:
        return raw
    if not mc_data.get("use_friendly_format", True):
        return "raw"
    return get_metric(metric_id).default_format_mode
```

Effekt für Bestandsdaten:
- `use_friendly_format: false` → immer `raw` (klar)
- `use_friendly_format: true` → der im Katalog hinterlegte Default der Metrik. Bei `cloud_*`, `cape`, `sunshine`, `thunder` → `symbol`; bei `wind_direction` → `scale`; bei `visibility` → `simplified`. Damit ist der heutige Render-Effekt bit-identisch reproduzierbar.
- Für Metriken, die im Katalog nur `("raw",)` haben (z.B. Temperatur), wird `use_friendly_format=true` auf `raw` resolved — kein Verhaltensunterschied, weil heute auch kein Friendly-Render-Pfad existiert.

Kein Daten-Migrations-Skript. Schreib-Pfade in `loader.py` schreiben künftig beide Felder (`format_mode` + `use_friendly_format`) parallel, damit ältere Frontend-Versionen weiter lesen können.

### Konsolidierung der Duplikate

`_build_friendly_keys()` in `trip_report.py:640` wird **vor** der Erweiterung durch Import aus `email/helpers.py` ersetzt (eigener Vor-Commit). Damit ist die Diff der Modus-Erweiterung in **einer** Stelle lokalisiert und Test-Triangulation klar. Der zweite, größere `fmt_val`-Quasi-Duplikat in `trip_report.py:653–770` bleibt vorerst — Konsolidierung dort ist Folge-Arbeit (Out-of-Scope für #435).

### Datei-Liste (Endgültig, ~350 LoC)

| Bereich | Dateien | LoC |
|---|---|---|
| **Datenmodell** | `src/app/models.py`, `src/app/metric_catalog.py` | ~65 |
| **API + Loader** | `src/app/loader.py`, `api/routers/config.py` | ~30 |
| **Renderer** | `src/output/renderers/email/helpers.py`, `src/formatters/trip_report.py`, `src/formatters/compact_summary.py`, `src/formatters/sms_trip.py` | ~120 |
| **Token-Builder-Adapter** | `src/output/tokens/builder.py`, `src/output/tokens/dto.py` | ~10 |
| **Frontend-Types** | `frontend/src/lib/types.ts` | ~8 |
| **Frontend-Editoren** | `Step3Weather.svelte`, `WeatherConfigDialog.svelte`, `Step4Layout.svelte`, `WeatherMetricsTab.svelte`, `metricsEditor.ts`, `SavePresetDialog.svelte` | ~70 |
| **Tests** | `tests/integration/test_friendly_format_email_and_alerts.py`, `tests/unit/test_weather_metrics_ux.py`, neue Unit-Tests für Katalog + Loader-Adapter | ~50 |

**Summe: ~350 LoC**, **15 Dateien**. Überschreitet 250-LoC-Grenze → `loc_limit_override 400` in Phase 6 setzen. Begründung: schmaler Datenmodell-Schwenk berührt jeden Read/Write-Pfad, Aufteilung in mehrere PRs würde das Frontend zwischendurch in Bug-Zustand (alle Modi außer raw → boolean-collapse) belassen.

### Implementierungs-Reihenfolge

1. **Konsolidierungs-Vorcommit:** `_build_friendly_keys` in `trip_report.py` durch Import ersetzen; bestehende Tests grün.
2. **Katalog-Erweiterung:** `MetricDefinition.format_modes` + `default_format_mode`, alle 25 Einträge füllen; `api/routers/config.py` liefert die Felder mit aus.
3. **Datenmodell + Read-Adapter:** `MetricConfig.format_mode` + `_resolve_format_mode()`; Schreib-Pfade schreiben beide Felder.
4. **Renderer-Umbau:** `fmt_val`/`build_format_modes`/`compact_summary`/`sms_trip`/`tokens` auf `mode: str`. Golden-Tests bit-identisch (heutige 6 Friendly-Metrik-Gruppen).
5. **Simplified-Kürzel-Helfer:** kleine `format_wind_strength(kmh)` und `format_precip_intensity(mm)` aus `compact_summary` extrahiert in `src/services/weather_metrics.py` (Single Source) und von `fmt_val` mit-genutzt.
6. **Frontend-Types + API-Konsum:** `format_modes`/`default_format_mode` in `MetricEntry`-Typ, keine UI-Veränderung.
7. **Wizard-Step 3:** `format_mode` persistieren, Dropdown-Options aus `m.format_modes` filtern; `use_friendly_format` parallel weiterschreiben (Backward-Compat).
8. **Andere Editoren:** `WeatherConfigDialog`, `WeatherMetricsTab`, `Step4Layout`, `SavePresetDialog`, `metricsEditor.ts` analog auf `format_mode` umstellen.
9. **Cleanup-Marker:** `use_friendly_format` `@deprecated` markieren + Folge-Issue „Remove legacy friendly bool" eröffnen (nicht in dieser Iteration).

Jeder Schritt einzeln grün-testbar; Tree bleibt zwischendurch lauffähig (parallel beide Felder).

### Signifikante Risiken

1. **Token-Builder-Semantik:** `src/output/tokens/builder.py:88,223` nutzt `use_friendly_format` als Trigger für `\x00{friendly_label}`-SMS-Tokens. Mapping: `format_mode in {"symbol","scale"} → friendly-Token`, `format_mode in {"raw","simplified"} → numerischer Token`. SMS-Goldens müssen bit-identisch zum heutigen Verhalten bleiben.
2. **Wind-Direction-Merge-Sonderfall:** `trip_report.py:616–629` und `helpers.py:48` mergen Wind-Richtung in die Wind-Spalte, wenn `wind_direction.use_friendly_format=True`. Neuer Trigger: `format_mode == "scale"`. Bei explizitem `format_mode="raw"` für Wind-Richtung verschwindet das Merge — neues, aber semantisch korrektes Verhalten. Acceptance-Test schreibt das fest.
3. **`MetricConfig.use_friendly_format` Default=True** (`models.py:465`): Bestands-Configs ohne explizites Feld haben effektiv `True`. Nach Migration werden sie auf den Katalog-Default resolved — für Nur-Roh-Metriken (z.B. Temperatur) auf `raw`. Realer Render-Impact = null, weil heute auch keine Friendly-Pfade für diese Metriken existieren.
