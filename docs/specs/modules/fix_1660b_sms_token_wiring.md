---
entity_id: fix_1660b_sms_token_wiring
type: module
created: 2026-08-10
updated: 2026-08-10
status: draft
version: "1.0"
tags: [metrics, sms, telegram, tokens, briefing]
---

<!-- Issue #1660 Scheibe B — 14 waehlbare Metriken ohne SMS-Token verdrahten
     (PO-Entscheidung, Issue-Kommentar 2026-08-09) -->

# SMS-Token-Verdrahtung: 14 fehlende Kürzel

## Approval

- [ ] Approved

## Purpose

14 der wählbaren Wetter-Metriken (humidity, dewpoint, wind_direction, cape,
precip_type, cloud_total, cloud_low, cloud_mid, cloud_high, visibility,
sunshine, uv_index, pressure, freezing_level) tragen im Register bereits ein
SMS-Kürzel (`metric_catalog.sms_code`), erscheinen aber weder in der SMS noch
in der Telegram-Kurzform (gleicher Renderer-Pfad, `TokenLine`) — der
Trip-Editor bietet sie über die Pro-Kanal-Kaskade (#429/#434/#1575 S3) an,
eine Auswahl bleibt aber wirkungslos. PO-Auftrag #1660 (Kommentar
2026-08-09): **alle 14 verdrahten**, ohne neue Bedienfläche — die
Metrik-Auswahl existiert bereits.

Diese Scheibe schließt an das Muster von Scheibe A (`fix_1660a_temp_trennung`)
an: bestehende Auswahlmechanik (Kanal-Kaskade, Abwahl, Schwellwerte) wird
über die Kürzel-Bindung erschlossen, ohne die Mechanik selbst zu ändern.

## Source

> **Schicht-Hinweis:** Alle Änderungen liegen im Python-Core
> (`src/output/tokens/`, `src/output/renderers/`). `src/output/tokens/`
> bleibt frei von `src/app/`-Importen (Schichtgrenze); Kürzel werden dort
> als Literale geführt, die Ratsche
> (`tests/unit/test_sms_token_symbol_register_ratchet.py`) prüft die
> Übereinstimmung mit dem Register automatisch.

### 1. Katalog (`src/app/metric_catalog.py`) — keine Änderung nötig

Alle 14 `sms_code`-Werte sind bereits vergeben (kollisionsfrei geprüft,
s. Kontext-Dokument): `HU DP WD CP PT CT CL CM CH VS SU UV HP NL`. Diese
Scheibe fügt **keinen** neuen Katalogeintrag hinzu und ändert keinen
bestehenden — reine Verdrahtungsarbeit unterhalb des Registers.

### 2. Register-Ableitung (`src/output/renderers/sms_trip.py`)

- `_SMS_SYMBOL_METRIC_IDS` (Zeile ~64-73) wird um die 14 metric_ids
  erweitert: `humidity, dewpoint, wind_direction, cape, precip_type,
  cloud_total, cloud_low, cloud_mid, cloud_high, visibility, sunshine,
  uv_index, pressure, freezing_level`. Alle 14 sind **1:1**-Metriken (kein
  Kürzel-Mehrfach wie bei `wind_chill`), gehören also in diese Tabelle und
  NICHT in `SMS_MULTI_SYMBOLS_BY_METRIC`.
- Damit greifen automatisch, ohne weitere Änderung:
  - `SMS_SYMBOL_BY_METRIC` (Comprehension über `_SMS_SYMBOL_METRIC_IDS`,
    Register-Ableitung #1435 E3b) — führt für alle 14 das richtige Kürzel.
  - `_disabled_sms_specs` in `trip_report.py:316-320` (Bug #944-Muster) —
    jede der 14 Metriken, die NICHT in der SMS-Kanal-Kaskade steht, bekommt
    automatisch einen `MetricSpec(enabled=False)`-Eintrag ⇒ Abwahl wirkt.
  - `_sms_thr` in `trip_report.py:294-301` (Issue #624) — ein im Trip
    konfigurierter `sms_threshold` einer der 14 Metriken landet automatisch
    im Schwellwert-Dict, das an `SMSTripFormatter().format_sms()` geht.

### 3. Werte-Beschaffung (`src/output/renderers/sms_trip.py::_segments_to_normalized_forecast`)

Die bestehende Schleife über `build_day_window_points()` (Zeilen 267-291)
sammelt bereits `rain/wind/gust/pop/thunder`-Stundenwerte und das
`hail_flag`. Sie wird um die Sammlung der neuen Felder erweitert:

- **Klasse (a), 8 Stunden-Sample-Listen** (HU, DP, CP, UV, CT, CL, CM, CH):
  je Stunde `dp.humidity_pct`, `dp.dewpoint_c`, `dp.cape_jkg`, `dp.uv_index`,
  `dp.cloud_total_pct`, `dp.cloud_low_pct`, `dp.cloud_mid_pct`,
  `dp.cloud_high_pct` — analog zur bestehenden `rain_samples`/`wind_samples`-
  Sammlung: nur `value > 0`, danach `_dedup_by_hour()` (Höchstwert je
  Ortszeit-Stunde bei Überlappung).
- **Klasse (b), 2 Stunden-Sample-Listen** (VS, NL): `dp.visibility_m`,
  `dp.freezing_level_m` — **ohne** den `> 0`-Filter (beide Größen sind auch
  bei kleinen bzw. negativen physikalisch sinnvollen Werten gültig; s. Known
  Limitations zu Klasse a); ebenfalls `_dedup_by_hour()`, aber mit dem
  Tiefstwert je Stunde statt des Höchstwerts, da die Klasse invers ist.
- **Klasse (c), 4 Tageswerte**, nach der Schleife über die gesammelten
  Punkte berechnet:
  - `WD` (Windrichtung): häufigster 8-Sektor-Kompasswert
    (N/NO/O/SO/S/SW/W/NW, Sektorbreite 45°) über `dp.wind_direction_deg`;
    bei Gleichstand entscheidet der Sektor zur Stunde des Wind-Peaks
    (`wind10m_kmh`-Maximum im Fenster). **Bewusst eine andere Aggregation**
    als die bestehende zirkuläre Mittelwertbildung
    (`WeatherMetricsService`, verwendet für die E-Mail-/Compare-Anzeige
    derselben Metrik) — s. Known Limitations.
  - `PT` (Niederschlagsart): häufigster `dp.precip_type`-Wert, bei
    Gleichstand nach Rang `FREEZING_RAIN > SNOW > MIXED > RAIN`. Fachlich
    dieselbe Regel wie `WeatherMetricsService._compute_precip_type()`
    (`src/services/weather_metrics.py:984-1004`), dort aber an
    `NormalizedTimeseries` gebunden — für die Tagesfenster-Punktliste hier
    entsteht eine eigene, kleine Ableitung (kein Import zwischen den beiden
    Schichten nötig, gleiche Rang-Tabelle als Literal).
  - `SU` (Sonnenstunden): `WeatherMetricsService.calculate_sunny_hours()`
    über dieselbe Punktliste, die auch `rain_samples` etc. speist (DNI-Pfad
    bevorzugt, Fallback proportional bewölkt — s. Docstring
    `weather_metrics.py:286-306`). Rohwert (float) wandert unverändert ins
    DTO, Rundung passiert beim Rendern.
  - `HP` (Luftdruck): arithmetisches Mittel `dp.pressure_msl_hpa` über die
    Punktliste (kein bestehender Aggregations-Helfer — analoge Ein-Zeiler-
    Berechnung wie bei `day_confidence` weiter unten in derselben Funktion).
- Alle 14 neuen Felder wandern additiv in den `DailyForecast(...)`-
  Konstruktoraufruf am Ende der Funktion (Zeile ~358-380).

### 4. DTO (`src/output/tokens/dto.py`)

`DailyForecast` bekommt 14 additive Felder mit Default (Muster #1410/#1475
— jeder Bestandsaufrufer bleibt byte-identisch, kein Feld verändert
bestehende Semantik):

| Feld | Typ | Klasse | Symbol |
|------|-----|--------|--------|
| `humidity_hourly` | `tuple[HourlyValue, ...]` | (a) | HU |
| `dewpoint_hourly` | `tuple[HourlyValue, ...]` | (a) | DP |
| `cape_hourly` | `tuple[HourlyValue, ...]` | (a) | CP |
| `uv_hourly` | `tuple[HourlyValue, ...]` | (a) | UV |
| `cloud_total_hourly` | `tuple[HourlyValue, ...]` | (a) | CT |
| `cloud_low_hourly` | `tuple[HourlyValue, ...]` | (a) | CL |
| `cloud_mid_hourly` | `tuple[HourlyValue, ...]` | (a) | CM |
| `cloud_high_hourly` | `tuple[HourlyValue, ...]` | (a) | CH |
| `visibility_hourly` | `tuple[HourlyValue, ...]` | (b) | VS |
| `freezing_level_hourly` | `tuple[HourlyValue, ...]` | (b) | NL |
| `wind_direction_sector` | `Optional[str]` | (c) | WD |
| `precip_type_dominant` | `Optional[str]` | (c) | PT |
| `sunshine_hours` | `Optional[float]` | (c) | SU |
| `pressure_avg_hpa` | `Optional[float]` | (c) | HP |

`MetricSpec` bleibt unverändert — alle 14 sind einfache 1:1-Symbole, keine
Grammatik-Sonderfälle wie `TH:`.

### 5. Token-Grammatik (`src/output/tokens/builder.py`)

- **Klasse (a):** die bestehende Threshold-Peak-Schleife (Zeilen 306-321,
  Paare `("R", today.rain_hourly, False), …`) wird um die 8 neuen Paare
  erweitert (`is_level=False` für alle), z. B.
  `("HU", today.humidity_hourly, False)`. Sie laufen durch dieselbe
  `_mk_metric()`/`render_threshold_peak_value()`-Kette wie `R`/`PR`/`W`/`G`
  — Threshold aus `spec.threshold` bzw. `DEFAULTS.get(symbol)` (kein
  neuer `DEFAULTS`-Eintrag, s. Known Limitations), Null-Form und
  Gap→`?`-Regel (`_gap_or`) automatisch mit.
- **Klasse (b):** neue, kleine Rendering-Variante für `VS`/`NL` — Tiefstwert
  im Fenster mit Stunde (`{min}@{h}`, kein `(max@h)`-Anhang), Schwelle als
  **Invers-Gate** (Token nur wenn `min <= threshold`, sonst Null-Form
  `{SYM}-`; ohne konfigurierten Threshold immer sichtbar, wenn die Metrik
  gewählt ist — Muster `SL`/#873, aber mit Stunde statt reinem Tageswert und
  mit Null-Form statt komplettem Weglassen, s. DEC-3). Gap→`?` gilt
  identisch über `_gap_or`.
- **Klasse (c):** vier Tageswert-Token ohne Peak-Klammer — `WD` (Sektor-
  String als Wert, z. B. `WDNW`), `PT` (Ein-Buchstaben-Code, z. B. `PTS`),
  `SU`/`HP` (ganzzahliger Wert via `render_int`). Alle vier folgen derselben
  „gewählt/nicht gewählt"-Zweiteilung wie die Temperatur-Token
  (`build_token_line()`-Schleife Zeilen 262-304): Metrik abgewählt ⇒
  Kürzel entfällt vollständig; gewählt, aber kein Wert ⇒ Null-Form
  `{SYM}-`; Datenlücke ⇒ `{SYM}?` über `_gap_or`.
- **`PRIORITY`-Dict** (Zeilen 46-59): alle 14 neuen Symbole = **2** (gleiche
  Stufe wie die Wintersport-Token `WC`/`AV`/`SL`/`NS24+`/`SD`). Pflicht,
  weil `PRIORITY[sym]` an mehreren Stellen ungeschützt gelesen wird
  (Risiko aus dem Kontext-Dokument: `builder.py:301` in der bestehenden
  Temperatur-Schleife) — ein fehlender Eintrag ist ein KeyError, kein
  stiller Fehler.
- **`POSITIONAL`-Liste** (Zeilen 72-87): neuer Block zwischen
  `(FORECAST_THP, "forecast")` und `(VIGI_HR, "vigilance")`, Kategorie
  jeweils `"forecast"`, Reihenfolge exakt die Katalog-Reihenfolge aus dem
  Auftrag: `HU, DP, WD, CP, PT, CT, CL, CM, CH, VS, SU, UV, HP, NL`.

### 6. Wertegrammatik (`src/output/tokens/metrics.py`)

- Neue kleine Funktion für die Invers-Min-Darstellung (Klasse b): Tiefstwert
  + Stunde, ohne Peak-Klammer, mit demselben Null-Form-Vertrag
  (`"-"` wenn keine Samples) wie `render_threshold_peak_value()`.
- `_fmt_num()` (bzw. die neue Funktion selbst) braucht einen `VS`-Sonderfall
  mit einer Nachkommastelle (Register: `decimals=1`, `display_unit="km"`,
  Faktor `0.001` gegenüber dem in Metern geführten DTO-Feld — s. Known
  Limitations zur Einheiten-Konsistenz); `NL` bleibt ganzzahlig in Metern.

### 7. Kürzung (`src/output/tokens/render.py`)

`DROP_ORDER` (Zeile 12) bekommt die 14 neuen Symbole **direkt nach `"DBG"`**
und **vor** `"WC"` — sie fallen als erste Fachtoken, noch vor den
Wintersport-Größen, dem Fire-Block, den Peak-Klammern und den
sicherheitsrelevanten Planungsgrößen `R/PR/W/G/TH:`/gefühlte/gemessene
Temperatur (bestehende Reihenfolge ab dort unverändert).

### 8. Format-Dokumentation (`docs/reference/sms_format.md`)

Als Teil des Scopes (Dokupflicht, keine separate Nacharbeit):

- §2 Token-Reihenfolge-Tabelle: neuer Block mit den 14 Kürzeln und ihrer
  Pflicht-Spalte (analog `R PR W G TH:`).
- §3.2 (bzw. neuer Unterabschnitt): je Klasse eine kurze Token-Definition
  mit Beispiel, wie bei den bestehenden Zeilen.
- §4 Null-Repräsentation: 14 neue Zeilen (`{SYM}-`, `?`-Form-Hinweis).
- §6 Kürzungsstrategie: neuer Schritt zwischen „Wintersport-Tokens" und
  „DBG" bzw. direkt danach, entsprechend der neuen `DROP_ORDER`-Position.
- §9 Datenquellen-Mapping: 14 neue Zeilen mit DTO-Feld/Aggregation.
- Neuer Versionierungs-Eintrag (v2.22) in §12.

## Estimated Scope

- **LoC:** ~150-220 produktiv (14 DTO-Felder ~16, Beschaffung inkl. vier
  Sonderableitungen ~70-90, Builder inkl. drei Grammatik-Zweige + zwei
  Register-Erweiterungen ~50, `render.py` 1, `metrics.py` ~20). Doku
  (`sms_format.md`) zählt laut CLAUDE.md-LoC-Regel nicht mit.
- **Files:** ~6 produktiv (`metric_catalog.py` unverändert, `sms_trip.py`,
  `dto.py`, `builder.py`, `render.py`, `metrics.py`) + 1 Referenz-Doku.
- **Effort:** high (14 Metriken über drei unterschiedliche
  Wertegrammatiken, keine 1:1-Blaupause wie bei Scheibe A).

> **⚠️ LoC-Limit:** Mit den Tests zu den 16 Akzeptanzkriterien (drei
> Grammatik-Klassen, Abwahl, zwei Schwellwert-Varianten, Null-Form/Gap,
> Byte-Identität, Kürzung, Ratsche, Telegram-Parität, Staging-Nachweis,
> PRIORITY-Vollständigkeit) liegt das Gesamt-Delta voraussichtlich über dem
> 250-LoC-Grundlimit. Ein `workflow.py set-field loc_limit_override` ist
> vorab beim PO einzuholen (CLAUDE.md), nicht erst bei der Blockade.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `fix_1435_e3b_sms_kuerzel` | Spec | Register-Ableitung (`_SMS_SYMBOL_METRIC_IDS` → `SMS_SYMBOL_BY_METRIC`), Ratsche |
| `fix_1660a_temp_trennung` | Spec | Vorbild-Mechanik (Kanal-Kaskade, Abwahl, DEC-Stil) |
| `sms_daywindow_aggregation` | Spec | Tagesfenster 04:00–19:00, Quelle aller Stunden-Samples |
| `fix_1613_sms_multi_symbols` | Spec | Abgrenzung 1:1- vs. 1:n-Kürzel-Tabellen |
| Kanal-Kaskade #429/#434/#1575 S3 | Feature | liefert die SMS-Metrikmenge (`get_metrics_for_channel`) |
| `sms_format` | Spec | Token-Grammatik v2.21, wird auf v2.22 fortgeschrieben |
| `metric_catalog.py` (`sms_code`) | Modul | Single Source of Truth der 14 Kürzel |

## Entscheidungen (DEC)

### DEC-1 — Register-Ableitung statt gepflegter Kürzel-Liste

Alle 14 Kürzel kommen aus `metric_catalog.sms_code` über
`_SMS_SYMBOL_METRIC_IDS` → `SMS_SYMBOL_BY_METRIC` (Register-Ableitung
#1435 E3b). Keine neuen Kürzel, keine Grammatik-Ausnahmen in
`_SMS_SYMBOL_GRAMMAR`. Dadurch wirken Abwahl (#944) und `sms_threshold`
(#624) automatisch über den bestehenden Code in
`trip_report.py:296-320`, ohne dass diese Scheibe dort etwas ändert.

### DEC-2 — Drei Wertegrammatik-Klassen

- **(a) Threshold-Peak** (wie `R/PR/W/G/TH:`): HU, DP, CP, UV, CT, CL, CM,
  CH. Stunden-Samples aus `build_day_window_points()` (Werte > 0),
  `render_threshold_peak_value()`, ganzzahlig. Ohne `sms_threshold` kein
  Filter (Peak-only). Keine neuen `DEFAULTS`-Einträge.
- **(b) Invers-Min** (Muster `SL`, #873): VS und NL — Tages-**Tiefst**wert
  über das Fenster mit Stunde (`{min}@{h}`); mit gesetztem `sms_threshold`
  erscheint der Token nur bei Unterschreitung (`val <= thr`), sonst
  Null-Form; ohne Schwelle immer sichtbar (wenn gewählt). VS in km mit
  einer Dezimale, NL in m ganzzahlig.
- **(c) Tageswert ohne Stunde:** WD = dominante 8-Sektor-Himmelsrichtung
  über das Fenster (häufigster Sektor, bei Gleichstand die Stunde des
  Wind-Peaks); PT = schwerster Typ im Fenster (Rang
  `FREEZING_RAIN > SNOW > MIXED > RAIN`, Codes `G/S/M/R`, z. B. `PTS`);
  SU = gerundete Sonnenstunden (`WeatherMetricsService.calculate_sunny_hours`
  über die Fensterpunkte); HP = ganzzahlig gerundetes Tagesmittel in hPa.

### DEC-3 — Null-Form/Gap einheitlich für alle drei Klassen

Gewählt, aber keine Daten ⇒ Null-Form `{SYM}-` (Grundregel §2/§7 der
Format-Spec); bei Datenlücke (`has_data_gap`) wird `-` zu `?`
(#1328/#1483, via `_gap_or`). Gilt für **alle** 14 Token, auch die drei
Tageswert-Größen ohne Stunde (WD/PT/SU/HP) — anders als die bestehenden
Wintersport-Token (`SD`/`NS24+`/`SL`/`AV`/`WC`), die bei fehlenden Daten
komplett weggelassen werden statt eine Null-Form zu zeigen. Diese Scheibe
folgt bewusst der jüngeren, seit #1415/#1483 geltenden Konvention
(„kein Vorhersage-Kürzel ist unbedingt"), nicht dem älteren
Wintersport-Muster.

### DEC-4 — Kürzungsrang

`DROP_ORDER` (`render.py`): die 14 neuen Symbole direkt nach `DBG` (fallen
als erste Fachtoken, noch vor WC/AV/SL/NS24+/SD). `PRIORITY` (`builder.py`):
alle 14 = 2 (unter dem gefühlten Trio 4, unter PR 5). `POSITIONAL`: eigener
Block nach `TH+:` (forecast) und vor dem Vigilance-Block, Reihenfolge =
Katalog-Reihenfolge. Schichtgrenze beachtet: `output/tokens/` importiert
nichts aus `src/app/`, Kürzel bleiben Literale; die Ratsche
(`tests/unit/test_sms_token_symbol_register_ratchet.py`) prüft die
Übereinstimmung mit dem Register automatisch.

### DEC-5 — DTO additiv

`DailyForecast` bekommt 14 additive Felder mit Default (Muster
#1410/#1475) — Bestandsaufrufer bleiben byte-identisch.

### DEC-6 — Byte-Identität

Trips, in deren SMS-Kanal-Auswahl keine der 14 Metriken vorkommt, erzeugen
eine zeichengleiche Kurzform (Goldens bleiben grün).

### DEC-7 — Morning/Evening ohne Sonderfall

Alle 14 erscheinen in **beiden** Report-Typen (kein Nacht-Sonderfall wie
bei `N`/`FN`).

## Bestandsdaten (PFLICHT-Regel aus CLAUDE.md)

Diese Scheibe ändert **kein** Persistenzschema. `MetricConfig` (inkl.
`enabled`, `sms_threshold`, `aggregations`) existiert für alle 14
Metrik-IDs bereits im Katalog und in `display_config.metrics[]`
gespeicherter Trips — es gibt keinen neuen Katalogeintrag, keine neue
Migration, keinen neuen Ableitungsblock beim Laden (`loader.py`). Betroffen
sind ausschließlich transiente Renderer-DTOs (`DailyForecast`, `TokenLine`),
die pro Report-Lauf neu aufgebaut werden. Eine Read-Modify-Write-Frage
(CLAUDE.md „Daten-Schema-Reworks") stellt sich hier nicht.

## Abgrenzungen / Known Limitations

1. **Kein Aggregat-Rückfall für die 14 bei Segmenten ohne Stunden-Zeitreihe.**
   Das bestehende Fail-soft-Muster (`sms_trip.py:296-312`) liefert für
   `R/PR/W/G` einen Etappen-Aggregat-Ersatzwert, wenn ein Segment keine
   verwertbare Zeitreihe hat (Provider-Fehler). Für die 14 neuen Metriken
   gilt dieser Rückfall **nicht** — fehlt die Stunden-Zeitreihe, bleibt die
   Sample-Liste leer und der Token zeigt die reguläre Null-Form, nicht
   einen aus Tagesaggregaten rekonstruierten Wert. Erweiterung des
   Fail-soft-Pfads ist außerhalb dieser Scheibe.
2. **Keine neuen `DEFAULTS`-Schwellen.** Klasse (a) bleibt ohne
   Editor-Konfiguration Peak-only (kein impliziter Standard-Schwellwert wie
   bei `R`/`PR`/`W`/`G`).
3. **Keine Editor-Änderungen.** Auswahl ausschließlich über die bestehende
   Pro-Kanal-Kaskade; keine neue Bedienfläche, keine Änderung an
   `WeatherMetricsTab`/`aggregationSelection.ts`.
4. **Auswertungswahl (#1357) wirkt für die 14 nicht.** Nur `temperature`
   und `wind_chill` haben das in Scheibe A eingeführte Aggregations-Gate
   (`K`/`D`/`FK`/`FD`). Die 14 neuen Token kennen kein „Nur Tiefstwert" /
   „Nur Höchstwert" — ihre Grammatik legt die Aggregation (Peak, Invers-Min,
   Tageswert) fest.
5. **`sms_threshold` ist für WD/PT semantisch leer.** Wird für diese beiden
   Metriken im Editor dennoch ein Schwellwert gesetzt, bleibt er
   wirkungslos (Fail-soft, kein Fehler) — die Grammatik dieser zwei
   Größen kennt keinen Schwellenvergleich.
6. **`WD` nutzt eine andere Aggregation als die E-Mail-/Compare-Anzeige
   derselben Metrik.** Dort gilt zirkulärer Mittelwert
   (`WeatherMetricsService`), hier häufigster 8-Sektor. Bewusste
   Entscheidung (DEC-2c) — ein Mittelwert über Kompassgrade ist für eine
   Ein-Zeichen-Kurzform weniger aussagekräftig als der dominante Sektor;
   die beiden Kanäle können für dieselbe Metrik dadurch unterschiedliche
   Werte zeigen (analog zu `D`, das ebenfalls nicht das Tagesmaximum ist,
   §3.2 der Format-Spec).
7. **`VS`-Einheitenumrechnung ist ein Sonderfall.** `visibility_m` im DTO
   ist in Metern; Anzeige und (voraussichtlich) der im Editor konfigurierte
   `sms_threshold` folgen der Register-`display_unit="km"`. Die
   Umrechnung (`_UNIT_CONVERSION[("m","km")] = 0.001`,
   `src/output/metric_format.py:58-61`) MUSS konsistent auf Wert **und**
   Schwellwert angewendet werden — ein Mismatch (Wert in km, Schwelle in m
   verglichen) wäre ein stiller Fehlschlag, kein Crash. AC-4/AC-5 prüfen
   das explizit.
8. **`> 0`-Filter für Klasse (a) inkl. `DP` (Taupunkt).** Der Filter folgt
   dem bestehenden Muster von `R`/`W`/`G` (nur positive Stundenwerte
   sammeln). Taupunkt kann unter 0 °C liegen — an kalten Tagen entstehen
   dadurch potenziell leere Sample-Listen trotz vorhandener (negativer)
   Messwerte, und `DP` zeigt dann fälschlich die Null-Form statt eines
   negativen Werts. Dieselbe Auftragsvorgabe (DEC-2a) gilt unverändert für
   alle acht Klasse-(a)-Metriken; eine feld-spezifische Ausnahme für `DP`
   ist **nicht** Teil dieser Scheibe, aber als bekannte Schwäche hier
   dokumentiert (Kandidat für eine Folge-Korrektur, falls ein echter
   Wintermesswert das belegt).

## Expected Behavior

- **Input:** Metrik-Auswahl (Reiter Wertebereiche, SMS-Kanal-Layout oder
  globale Auswahl) für die 14 Größen; optional je Metrik ein
  `sms_threshold`.
- **Output:** SMS- und Telegram-Kurzform (identische `TokenLine`) enthalten
  für jede gewählte Metrik das zugehörige Kürzel gemäß ihrer
  Wertegrammatik-Klasse (a/b/c); abgewählte Metriken erscheinen nicht,
  auch nicht als Null-Form; gewählte Metriken ohne Daten zeigen die
  Null-Form; bei Datenlücke die `?`-Form.
- **Side effects:** keine neuen Datenabrufe — alle 14 Felder werden aus
  bereits vorhandenen `ForecastDataPoint`-Feldern innerhalb des bestehenden
  Tagesfensters abgeleitet.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit gewählter Metrik „Luftfeuchtigkeit" (`humidity`), Schwellwert `sms_threshold=85` und stündlichen `humidity_pct`-Werten mit erstem Erreichen von 88 % um 14 Uhr und Tagesmaximum 92 % um 17 Uhr / When das Briefing als SMS erzeugt wird / Then enthält die SMS das Token `HU88@14(92@17)`.
  - Test: SMS-Rendering mit realistischem Forecast-Fixture (Klasse a, Threshold-Peak), Assertion auf den exakten Token-String.

- **AC-2:** Given ein Trip mit gewählter Metrik „Gewitterenergie (CAPE)" (`cape`) ohne konfigurierten `sms_threshold` und stündlichen `cape_jkg`-Werten mit Tagesmaximum um 16 Uhr / When das Briefing als SMS erzeugt wird / Then enthält die SMS `CP{max}@16` ohne Klammer-Zusatz (Peak-only, Threshold==Max-Optimierung §5).
  - Test: SMS-Rendering ohne gesetzten Schwellwert, Assertion auf die verkürzte Ein-Wert-Form.

- **AC-3:** Given ein Trip mit gewählter Metrik „Sichtweite" (`visibility`), Schwellwert `sms_threshold=1.0` (km) und stündlichen `visibility_m`-Werten mit Tagestief 600 m um 11 Uhr / When das Briefing als SMS erzeugt wird / Then enthält die SMS `VS0.6@11` (Invers-Gate ausgelöst, eine Dezimale, Einheit km).
  - Test: SMS-Rendering mit Klasse-b-Fixture, Assertion auf die km-Umrechnung UND die Stunde des Tagestiefs.

- **AC-4:** Given ein Trip mit gewählter Metrik „Sichtweite" (`visibility`), Schwellwert `sms_threshold=1.0` (km) und stündlichen `visibility_m`-Werten, deren Tagestief 3.2 km NIE unter 1 km fällt / When das Briefing als SMS erzeugt wird / Then enthält die SMS `VS-` (Null-Form, Schwelle nicht unterschritten) statt eines Zahlenwerts.
  - Test: SMS-Rendering mit demselben Fixture-Muster wie AC-3, aber Werten oberhalb der Schwelle — Gegenprobe zum Invers-Gate.

- **AC-5:** Given ein Trip mit gewählter Metrik „Nullgradgrenze" (`freezing_level`) OHNE konfigurierten `sms_threshold` und stündlichen `freezing_level_m`-Werten mit Tagestief 1800 m um 6 Uhr / When das Briefing als SMS erzeugt wird / Then enthält die SMS `NL1800@6` (ohne Schwelle immer sichtbar, wenn gewählt).
  - Test: SMS-Rendering Klasse b ohne Threshold, Assertion auf unbedingte Sichtbarkeit des Tiefstwerts.

- **AC-6:** ⚠️ **Abgelöst durch #1824** (`docs/specs/modules/feat_1824_sms_range_und_trenner.md`
  AC-12/AC-13/AC-14) — der wörtlich geforderte Wert `WDNW` gilt nicht mehr, `WD` bekommt seit #1824
  den Trenner `:` (Symbol-String `WD:`, wie `TH:`/`HR:`). Ursprünglicher Wortlaut zur Historie:
  „Given ein Trip mit gewählter Metrik „Windrichtung" (`wind_direction`) und stündlichen
  `wind_direction_deg`-Werten, deren Mehrheit im Sektor Nordwest (315°–359°) liegt / When das
  Briefing als SMS erzeugt wird / Then enthält die SMS das Token `WDNW`."
  - Test: SMS-Rendering mit Klasse-c-Fixture (Sektor-Mehrheit eindeutig), Assertion auf den Sektor-Code.

- **AC-7:** ⚠️ **Abgelöst durch #1824** (`docs/specs/modules/feat_1824_sms_range_und_trenner.md`
  AC-15) — der wörtlich geforderte Wert `PTS` gilt nicht mehr, `PT` bekommt seit #1824 den Trenner
  `:` (Symbol-String `PT:`). Ursprünglicher Wortlaut zur Historie: „Given ein Trip mit gewählter
  Metrik „Niederschlagsart" (`precip_type`) und einem Fenster, in dem `SNOW`-Stunden häufiger
  auftreten als `RAIN`- oder `MIXED`-Stunden / When das Briefing als SMS erzeugt wird / Then
  enthält die SMS das Token `PTS`."
  - Test: SMS-Rendering mit gemischtem Fixture (mehrere `PrecipType`-Werte im Fenster), Assertion auf den dominanten Code UND (separater Fall) auf die Rang-Regel bei Gleichstand (gleich viele RAIN- wie SNOW-Stunden ⇒ Rang-Regel unverändert, nur der Trenner ändert sich).

- **AC-8:** Given ein Trip mit gewählten Metriken „Sonnenstunden" (`sunshine`) und „Luftdruck" (`pressure`), DNI-abgeleiteten Sonnenstunden von 6.4 h und einem mittleren `pressure_msl_hpa` von 1013.4 hPa über das Tagesfenster / When das Briefing als SMS erzeugt wird / Then enthält die SMS die Token `SU6` und `HP1013` (kaufmännisch gerundet, ganzzahlig).
  - Test: SMS-Rendering mit beiden Metriken gewählt, Assertion auf beide gerundeten Werte.

- **AC-9:** Given ein Trip, bei dem zwei der 14 Metriken (z. B. „CAPE" und „UV-Index") im SMS-Kanal abgewählt sind, während alle anderen zuvor gewählten Metriken unverändert bleiben / When das Briefing als SMS erzeugt wird / Then fehlen `CP` und `UV` vollständig (auch keine Null-Form), und alle übrigen gewählten Token bleiben unverändert sichtbar.
  - Test: SMS-Rendering mit zwei Metrik-Konfigurationen (vorher/nachher Abwahl), Assertion auf Abwesenheit der beiden Symbole und Anwesenheit der übrigen.

- **AC-10:** Given eine gewählte Metrik ohne verwertbare Stundenwerte im Fenster und ohne erkannte Datenlücke (z. B. „Bewölkung gesamt") / When das Briefing als SMS erzeugt wird / Then zeigt sich `CT-`; besteht im selben Fall zusätzlich eine erkannte Datenlücke (`has_data_gap=True`) / Then wird daraus `CT?`.
  - Test: zwei SMS-Renderings mit identischer leerer Sample-Liste, einmal `has_data_gap=False`, einmal `True`; Assertion auf `-` bzw. `?`.

- **AC-11:** Given ein Bestands-Trip, dessen SMS-Kanal-Auswahl keine der 14 neuen Metriken enthält / When Abend- und Morgenbriefing als SMS gerendert werden / Then ist der erzeugte Text zeichengleich zum Stand vor dieser Änderung (bestehende Golden-/Fixture-Tests bleiben grün).
  - Test: bestehende SMS-Golden-Tests laufen unverändert grün; zusätzlich ein expliziter String-Vergleich gegen den vor der Änderung erzeugten Text für ein realistisches Fixture ohne die 14 Metriken.

- **AC-12:** Given ein Trip mit so vielen gewählten Metriken (mehrere der 14 zusammen mit Wintersport-Größen und den Sicherheitsgrößen `R`/`PR`/`W`/`G`/`TH:`), dass die Zeile 160 Zeichen überschreitet / When die SMS gekürzt wird / Then fallen die 14 neuen Token vollständig weg, bevor auch nur ein Wintersport-Token (`WC`/`AV`/`SL`/`NS24+`/`SD`) oder ein Sicherheitstoken entfernt wird.
  - Test: konstruiertes Überlängen-Fixture, Assertion auf die Reihenfolge des Wegfalls (welche Symbole zuerst verschwinden) statt nur auf die Endlänge.

- **AC-13:** Given die 14 neuen Kürzel sind in `PRIORITY`, `POSITIONAL` und `DROP_ORDER` verdrahtet / When `tests/unit/test_sms_token_symbol_register_ratchet.py` läuft / Then bleibt der Test grün — jedes verwendete Kürzel stimmt mit `metric_catalog.sms_code` überein, ohne eine neue manuell gepflegte Ausnahme in `_SMS_SYMBOL_GRAMMAR`.
  - Test: bestehende Ratsche läuft unverändert (kein neuer Testcode nötig, sofern die Verdrahtung korrekt registerkonform ist) — Mutationsgegenprobe s. u.

- **AC-14:** Given ein Trip mit gewählten Metriken aus allen drei Grammatik-Klassen (z. B. `humidity`, `visibility`, `wind_direction`) / When SMS-Text und Telegram-Kurzform-Zeile für dieselbe Etappe erzeugt werden / Then sind beide Token-Zeilen zeichengleich (gemeinsame `TokenLine`-Quelle, kein zweiter Rendering-Pfad).
  - Test: Rendering über beide Aufrufer (`SMSTripFormatter`/Telegram-Kurzform), String-Vergleich.

- **AC-15:** Given ein Trip mit allen 14 Metriken gewählt, real gegen Staging zugestellt (echte Test-SMS bzw. E-Mail-Kurzform-Kopfzeile über das Test-Postfach) / When die zugestellte Nachricht geprüft wird / Then enthält der tatsächlich zugestellte Text alle 14 Token mit den erwarteten Werten — nicht nur eine Zwischenstufe im Renderer-Unit-Test.
  - Test: Staging-Versand + IMAP-Abruf des zugestellten Textes (Prüfort = Wirkort, CLAUDE.md), Zahl-für-Zahl-Abgleich mit den bekannten Eingabedaten des Test-Trips.

- **AC-16:** Given eine der 14 Metriken (z. B. „UV-Index") ist gewählt / When sowohl Morgen- als auch Abendbriefing für dieselbe Etappe erzeugt werden / Then erscheint das Token in BEIDEN Report-Typen identisch — kein Nacht-Sonderfall wie bei `N`/`FN`.
  - Test: zwei Renderings (`report_type="morning"`/`"evening"`) desselben Fixtures, Assertion auf identisches Token in beiden.

## Prüfhinweis für den Adversary

Leitfrage aus CLAUDE.md: **Ist die Zusicherung dort geprüft, wo sie WIRKT —
oder nur dort, wo der Code steht?**

1. **AC-13 / PRIORITY-Vollständigkeit.** Ein Test ohne Kürzungsdruck ist
   grün, egal ob `PRIORITY` alle 14 Symbole führt — `PRIORITY.get(sym, 5)`
   an manchen Stellen fängt einen fehlenden Eintrag ab, ein direkter
   `PRIORITY[sym]`-Zugriff nicht. Nur ein Fixture, das echten
   Kürzungsdruck (>160 Zeichen) mit mindestens einem der 14 Symbole
   erzeugt, deckt einen fehlenden Eintrag auf.
2. **AC-9 (Abwahl).** Ein Test, der ausschließlich die AKTIVIERTE Auswahl
   prüft, beweist nicht, dass eine spätere Abwahl auch wirkt — es braucht
   den Vorher/Nachher-Vergleich derselben Metrik.
3. **AC-3/AC-4 (Invers-Gate, Einheitenkonsistenz).** Ein Fixture, bei dem
   die Schwelle zufällig weit über oder unter allen Messwerten liegt,
   beweist nichts über die Gate-Richtung. Ebenso deckt ein Test, der
   Schwelle und Wert in derselben Einheit (z. B. beide in Metern) vergibt,
   einen km/m-Umrechnungsfehler bei `VS` nicht auf.
4. **AC-11 (Byte-Identität).** Golden-Vergleiche müssen den **gerenderten
   Text** vergleichen, nicht die Konfiguration oder nur die Symbolmenge.

**Mutations-Gegenproben (Pflicht, per String-Ersetzung mit externer
Sicherungskopie — nie `git checkout/stash/reset`):**

- Einen `PRIORITY`-Eintrag eines der 14 Symbole entfernen und ein
  Überlängen-Fixture rendern — wirft der Code einen `KeyError`, den ein
  Test bemerkt, oder degradiert er still?
- Bei Klasse (b) den Vergleichsoperator `<=` auf `>=` drehen — welcher Test
  wird rot?
- Den `> 0`-Filter bei Klasse (a) durch `is not None` ersetzen — bleibt
  AC-1/AC-2 grün? (Belegt/widerlegt die in Known Limitations Punkt 8
  dokumentierte Schwäche.)
- `DROP_ORDER`-Reihenfolge vertauschen (die 14 neuen Symbole NACH `WC`
  statt davor) — fängt AC-12 die falsche Rangfolge?
- Eines der 14 metric_ids aus `_SMS_SYMBOL_METRIC_IDS` wieder entfernen
  (nur 13 statt 14 verdrahtet) — welcher Test bemerkt die fehlende
  Abwahl-Bindung für genau diese eine Metrik?
- Bei `PT` die Rang-Tabelle vertauschen (`RAIN` als „schwerster" statt
  `FREEZING_RAIN`) — fängt AC-7 die falsche Rangfolge bei Gleichstand?
- Die `VS`-km-Umrechnung entfernen (Wert bleibt in Metern, Vergleich mit
  der km-Schwelle) — wird AC-3/AC-4 rot, oder erscheint zufällig dasselbe
  Ergebnis, weil die Fixture-Werte die Diskrepanz nicht aufdecken?

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der Schnitt erweitert die bestehende, bereits mehrfach
  fortgeschriebene SMS-Token-Grammatik (§5/§6 `sms_format.md`, zuletzt
  #1410/#1435/#1483/#1660a) um weitere Kürzel nach denselben drei bereits
  etablierten Mustern (Threshold-Peak, Invers-Min, Tageswert) und schafft
  keine neue Entscheidungsfläche.

## Changelog

- 2026-08-10: Initial spec created (Issue #1660 Scheibe B)
