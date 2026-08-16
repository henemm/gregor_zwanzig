---
entity_id: fix_1887_e6a_sms_kuerzel_register
type: bugfix
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "1.1"
tags: [metric-catalog, sms, trip, register, wind-chill]
workflow: fix-1857-e6-temp-register
---

# Fix #1887 — Etappe E6 Scheibe A: Temperatur-/Gefühlt-Kürzel der Trip-SMS ins Register

## Approval

- [ ] Approved

## Purpose

Die Trip-SMS-Mehrfach-Kürzel-Tabelle (`SMS_MULTI_SYMBOLS_BY_METRIC`) trägt für
sechs Temperatur-/Gefühlt-Größen handgetippte Zeichenketten, die vom
`sms_code`-Feld des Wetter-Registers abweichen (`TD`≠`D`, `TN`≠`N`) — die
gesendeten Kürzel stehen nirgends im Register selbst, UND das Register führt
mit `TD`/`TN` zwei **tote** Werte, die kein Leser je erreicht. Diese Scheibe
macht die Tabelle zu einer reinen Ableitung aus dem Register (neues Feld je
`MetricDefinition`), entfernt die beiden toten `sms_code`-Rückstände
(`temperature_day_high`, `temperature_night` → `""`), entfernt das
redundante Wintersport-Kürzel `WC` (verdoppelt nachweislich den Wert von
`FK`, siehe „Zu messen, nicht zu raten") und versieht das irreführend
benannte Feld `wind_chill_c` mit einem erklärenden Kommentar an beiden
Provider-Zuweisungen, ohne es umzubenennen.

## Source

- **File:** `src/app/metric_catalog.py`
- **Identifier:** `class MetricDefinition` (Zeile 27), `SMS_MULTI_SYMBOLS_BY_METRIC` (Zeile 778)
- **File:** `src/output/tokens/builder.py`
- **Identifier:** `PRIORITY` (Zeile 52), `POSITIONAL` (Zeile 109), `_wintersport()` (Zeile 273)
- **File:** `src/output/tokens/render.py`
- **Identifier:** `DROP_ORDER` (Zeile 21)
- **File:** `src/output/adapters/trip_result.py`
- **Identifier:** `_wintersport_default_config()` (Zeile 211)
- **File:** `src/providers/openmeteo.py` (Zeile 394, 910), `src/providers/geosphere.py` (Zeile 552, 573)
- **Identifier:** Feldzuweisung `wind_chill_c`
- **File:** `tests/helpers/metrik_listen_scan.py`
- **Identifier:** `_BESTAND` (Zeile 292ff.), `REGISTERED_LISTS` (Zeile 359)

> **Schicht-Hinweis:** ausschließlich Python-Core. `src/app/` (Register),
> `src/output/tokens/` (app-freie Formatschicht, Literale bleiben Literale —
> Grenze durch die bestehende E3b-Ratsche gesichert, s. „Bewusste Grenzen"),
> `src/output/adapters/`, `src/providers/` (zwei Kommentare, keine
> Strukturänderung). Keine Go-Beteiligung, keine Frontend-Änderung (Legende
> ist Scheibe B, #1888).

## Estimated Scope

- **LoC Produktivcode:** ~65–75.
  `metric_catalog.py` (neues Feld `sms_multi_symbols` an 6
  `MetricDefinition`-Einträgen + Ableitung `SMS_MULTI_SYMBOLS_BY_METRIC` +
  zwei `sms_code`-Werte auf `""` + zwei bereinigte Kommentare) ~40;
  `builder.py` (4 Fundstellen `WC` entfernen: `PRIORITY`, `POSITIONAL`,
  `_wintersport()`-Paar, ggf. `_visible()`-Gate) ~10; `render.py`
  (`DROP_ORDER`-Eintrag) ~2; `trip_result.py`
  (`_wintersport_default_config()`) ~2; `openmeteo.py` + `geosphere.py`
  (Kommentare) ~15. Bleibt **unter** dem 250-Zeilen-Deckel.
- **LoC Testcode:** ~300–450, **deutlich mehr** als die ~120–180 im
  Kontext-Dokument veranschlagten. Grund: die dortige Schätzung datiert vor
  der PO-Entscheidung „WC entfällt" — das eigenständige Streichen eines
  Kürzels hat eine viel breitere Testoberfläche als die reine
  Register-Angleichung. Gemessen (grep `"WC"` über `tests/`, 2026-08-16):
  **18 Python-Testdateien + 2 Golden-Dateien + 1 Frontend-Testdatei**
  enthalten das Literal; mindestens 11 davon mit einer echten,
  WC-abhängigen Zusicherung (s. „Betroffene Tests" unten). Dazu die
  Registrierungs-Umstellung in `metrik_listen_scan.py` (~10 LoC), zwei
  umzuschreibende Pinning-Tests (`test_temp_tagesrichtung_aufloesung.py`,
  `test_metric_catalog.py`, s. „Zu messen, nicht zu raten" Punkt 1) und der
  neue getippte Wächter für AC-9 (~40–60 LoC).
- **Files:** 5 Produktivdateien geändert, 0 neu; mindestens 16 bestehende
  Testdateien angepasst (14 WC-bedingt + 2 `sms_code`-Pinning-Tests, s.
  „Betroffene Tests"), 1 Testdatei mit neuen Assertions erweitert
  (Ratsche), 1 Helfer-Datei geändert (`metrik_listen_scan.py`), 2
  Golden-Dateien angepasst, 1 Frontend-Testdatei (Kommentar).
- **Effort:** medium. Der Produktivcode-Kern ist klein; der Aufwand steckt im
  lückenlosen Mitziehen aller `WC`-Fundstellen in Tests (Risiko V7) und im
  Wirksamkeitsnachweis des E7-Wächters nach der Registrierungs-Umstellung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py::_METRICS` | MODIFY | 6 `MetricDefinition`-Einträge bekommen `sms_multi_symbols` |
| `src/app/metric_catalog.py::SMS_MULTI_SYMBOLS_BY_METRIC` | MODIFY | wird zur Comprehension über `_METRICS` + Thunder-Merge |
| `src/app/metric_catalog.py::SMS_SYMBOL_GRAMMAR["thunder"]` | READ (unverändert) | bleibt Quelle für `"TH:"`, s. „Bewusste Grenzen" |
| `src/app/metric_catalog.py::temperature_day_high.sms_code` / `temperature_night.sms_code` | **MODIFY → `""`** | tote Werte (`TD`/`TN`), von KEINEM Leser erreicht — s. „Zu messen, nicht zu raten" Punkt 1 |
| `src/app/metric_catalog.py::temperature.sms_code` / `temperature_cold.sms_code` / `wind_chill.sms_code` | **UNVERÄNDERT** | bleiben `"D"`/`"N"`/`"TF"` — lebend, s. „Zu messen, nicht zu raten" Punkt 1 |
| `src/output/tokens/builder.py::PRIORITY/POSITIONAL/_wintersport()` | MODIFY | `WC`-Fundstellen entfernen, **gemeinsam** (AC-4) |
| `src/output/tokens/render.py::DROP_ORDER` | MODIFY | `WC`-Eintrag entfernen |
| `src/output/adapters/trip_result.py::_wintersport_default_config()` | MODIFY | `MetricSpec(symbol="WC", …)` entfernen |
| `src/app/loader.py::_DERIVED_METRIC_RULES` | READ (unverändert) | trägt bereits `("wind_chill_day_low", "wind_chill", None)` / `("wind_chill_day_high", "wind_chill", None)` seit #1728 S1/S3 — deckt den Bestandsschutz für `wind_chill`-Nutzer ab (AC-5), s. „Zu messen, nicht zu raten" Punkt 3 |
| `tests/helpers/metrik_listen_scan.py::_BESTAND` / `REGISTERED_LISTS` | MODIFY | Registrierung von `SMS_MULTI_SYMBOLS_BY_METRIC` von AST-Literal auf Laufzeit-Lesung umstellen (AC-2) |
| `tests/unit/test_sms_token_symbol_register_ratchet.py::EXEMPT_FORECAST_FIELDS` | MODIFY | `wind_chill_c`-Eintrag entfällt (kein Wintersport-Token mehr für dieses Feld) |
| `tests/tdd/test_temp_tagesrichtung_aufloesung.py:309-313` | MODIFY | Pinning `sms_code == "TD"` → `== ""`, Kommentar auf diese Spec verweisen |
| `tests/unit/test_metric_catalog.py:17-29` | MODIFY | Pinning `get_sms_code("temperature_night") == "TN"` → `== ""`; Prüfziel wandert auf `SMS_MULTI_SYMBOLS_BY_METRIC["temperature_night"]` |
| `src/output/renderers/comparison.py:647` (`_RENDERER_TO_CATALOG_METRIC_ID`) | READ (unverändert) | erreicht `get_sms_code()` für **`temperature`** (`temp_max_c`/`temp_min_c`) UND **`wind_chill`** (`wind_chill_min_c`/`wind_chill_max_c`) — Beleg, warum beide unangetastet bleiben |
| `src/output/renderers/alert/render.py:93` + `alert/project.py::_resolve_metric_id()` | READ (unverändert) | erreicht `get_sms_code()` für **`temperature`** und **`temperature_cold`** — Beleg, warum beide unangetastet bleiben |
| `src/providers/openmeteo.py:394,910`, `src/providers/geosphere.py:129,552,573` | MODIFY (Kommentar) | erklärender Kommentar, keine Umbenennung |

## Implementation Details

### 1. Neues Register-Feld statt Nebentabelle

`MetricDefinition` bekommt ein neues Feld, bewusst **getrennt** von
`sms_code` (Begründung s. „Zu messen, nicht zu raten" Punkt 1):

```
sms_multi_symbols: tuple[str, ...] = ()
```

Gesetzt auf genau den sechs Größen, deren Trip-SMS-Kürzel heute nur in der
handgetippten `SMS_MULTI_SYMBOLS_BY_METRIC` steht:

| Größe | `sms_multi_symbols` | entspricht bisherigem Sendewert |
|---|---|---|
| `temperature_day_low` | `("K",)` | unverändert |
| `temperature_day_high` | `("D",)` | unverändert |
| `temperature_night` | `("N",)` | unverändert |
| `wind_chill_day_low` | `("FK",)` | unverändert |
| `wind_chill_day_high` | `("FD",)` | unverändert |
| `wind_chill_night` | `("FN",)` | unverändert |
| `wind_chill` | **kein Eintrag** (bleibt `()`) | **entfällt** (`WC`, PO-Entscheid) |

`SMS_MULTI_SYMBOLS_BY_METRIC` wird zur reinen Ableitung:

```
SMS_MULTI_SYMBOLS_BY_METRIC: dict[str, tuple[str, ...]] = {
    m.id: m.sms_multi_symbols for m in _METRICS if m.sms_multi_symbols
} | {"thunder": (SMS_SYMBOL_GRAMMAR["thunder"], "TH+:")}
```

`thunder` bleibt **bewusst außerhalb** der neuen Feld-Ableitung — `"TH:"`
kommt weiterhin aus `SMS_SYMBOL_GRAMMAR` (zentrale Quelle seit E3b),
`"TH+:"` bleibt der seit #1482 dokumentierte literale Sonderfall (Folge-Etappe,
kein `sms_code`-Pendant). Kein neues Duplikat, keine neue Ausnahme.

### 2. Die zwei toten `sms_code`-Werte entfernen

Nachgemessen (2026-08-16, s. „Zu messen, nicht zu raten" Punkt 1): `"TD"`
(`temperature_day_high`) und `"TN"` (`temperature_night`) werden von
**keinem** der beiden `get_sms_code()`-Leser (`comparison.py:647`,
`alert/render.py:93`) je erreicht — nur `temperature`, `temperature_cold`
und `wind_chill` sind lebende Katalog-IDs für diese beiden Pfade. `TD`/`TN`
sind reine DEC-8-Kompromisswerte (Kommentar `metric_catalog.py:170-174`),
die nur existierten, um der (bis dahin einzigen) globalen
`sms_code`-Eindeutigkeitsprüfung auszuweichen — seit Punkt 1 trägt
`sms_multi_symbols` das tatsächlich gesendete Kürzel, `sms_code` hat für
diese beiden Größen keine Funktion mehr:

```
temperature_day_high.sms_code = ""
temperature_night.sms_code = ""
```

`get_sms_code("temperature_day_high")` und `get_sms_code("temperature_night")`
liefern danach `""` — deckt sich mit dem dokumentierten Verhalten der
Funktion für „nicht gesetzt" (`metric_catalog.py:1198-1199`). Die drei
Uniqueness-Prüfungen filtern Leerwerte bereits heute explizit heraus (s.
„Zu messen, nicht zu raten" Punkt 1) — kein Kollisionsrisiko.

### 3. `WC` entfernen — vier Fundstellen, die GEMEINSAM ziehen müssen

Analog zum Muster aus E3b (Risiko einer unvollständigen Umbenennung):

| Datei | Fundstelle | Änderung |
|---|---|---|
| `builder.py:52` | `PRIORITY` | Eintrag `"WC": 2` entfernen |
| `builder.py:109` | `POSITIONAL` | Tupel `("WC", "wintersport")` entfernen |
| `builder.py:273` | `_wintersport()` | Paar `("WC", day.wind_chill_c)` entfernen |
| `render.py:21` | `DROP_ORDER` | `"WC"` aus der Liste entfernen |
| `trip_result.py:211` | `_wintersport_default_config()` | `MetricSpec(symbol="WC", …)` entfernen |
| `metric_catalog.py:784` | `SMS_MULTI_SYMBOLS_BY_METRIC` (alt) | Zeile `"wind_chill": ("WC",)` entfällt (durch Punkt 1 automatisch, kein `sms_multi_symbols` auf `wind_chill`) |

`wind_chill` selbst (die `MetricDefinition`, `dp_field="wind_chill_c"`,
`summary_fields={"min":…, "max":…}`, `sms_code="TF"`) bleibt **unverändert
bestehen** — sie ist weiterhin die Quelle für E-Mail-Stundentabelle und
Telegram-Zelle (`col_key="felt"`, `col_label="Feels"`) und für die
Ortsvergleichs-SMS (`comparison.py:647` liest `sms_code="TF"` für
`wind_chill_min_c`/`wind_chill_max_c`).

### 4. E7-Wächter-Registrierung umstellen

`tests/helpers/metrik_listen_scan.py::_literal()` liest `dict`-Literale per
AST — eine Dict-**Comprehension** liefert dort keine konstanten Strings
(gemessen: `_seiten()` erkennt nur `ast.Dict`/`ast.Set`/`ast.List`/
`ast.Tuple`, keine `ast.DictComp`). Ohne Anpassung würde die Registrierung
von `SMS_MULTI_SYMBOLS_BY_METRIC` (`_BESTAND`, Zeile 309) nach Punkt 1
`LookupError` werfen — das wird von `pruefe_registrierte_liste()`
**laut** gemeldet („Die Registrierung zeigt ins Leere"), nicht still grün,
aber der Wächter prüft dann nichts mehr. Notwendige Änderung:

- Zeile 309 aus `_BESTAND` entfernen.
- Neuer Eintrag nach dem Muster `METRIC_PRIORITY`/`HOURLY_EXCLUSION_REASON`
  (Zeile 369ff., Laufzeit-Lesung statt AST-Literal):

```
REGISTERED_LISTS["metric_catalog.SMS_MULTI_SYMBOLS_BY_METRIC"] = RegisteredList(
    ist=lambda: set(SMS_MULTI_SYMBOLS_BY_METRIC),
    ort="src/app/metric_catalog.py:778",
)
```

- Import von `SMS_MULTI_SYMBOLS_BY_METRIC` in `metrik_listen_scan.py`
  ergänzen.

### 5. `wind_chill_c` — Kommentar, keine Umbenennung

An beiden Provider-Zuweisungen (`openmeteo.py:394`, `geosphere.py:552,573`)
je ein Kommentar, der die tatsächlich gelieferte Größe benennt (R3 aus dem
Kontext-Dokument: **je nach Provider steht dort fachlich Verschiedenes**,
nicht nur ein irreführender Name). Kein Rename — 166 Dateien/>840
Fundstellen, persistiertes Feld (`models.py:128`) mit Go-JSON-Tag
(`forecast.go:60`) wären ein Daten-Schema-Rework, das AC-8 ausdrücklich
nicht verlangt.

## Expected Behavior

- **Input:** Ein Nutzer mit aktivierten Größen Tages-Tief/-Hoch,
  Nacht-Tiefsttemperatur (gemessen oder gefühlt) erhält ein Touren-Briefing
  (morgens oder abends) mit eingebetteter SMS-Kurzform.
- **Output:** Die SMS-Zeile trägt weiterhin `K`/`D`/`N`/`FK`/`FD`/`FN` an
  denselben Positionen — **außer** dass ein zuvor vorhandener `WC`-Token
  jetzt fehlt (er duplizierte nachweislich `FK`, s. unten). Alert-SMS
  (Hitze-/Kältealarm) und Ortsvergleichs-SMS für Tageshöchst/-tiefst bzw.
  Gefühlt zeigen weiterhin `D`/`N`/`TF`.
- **Side effects:** Keine Migration nötig — `_DERIVED_METRIC_RULES`
  (`loader.py:761-762`) leitet `wind_chill_day_low`/`wind_chill_day_high`
  bereits seit #1728 S1/S3 aus einer aktiven `wind_chill`-Auswahl ab, auf
  allen drei Konfigurationsebenen (global, `channel_layouts`,
  `channel_layouts_per_report` — `loader.py:846/889/922-924`). Ein Nutzer,
  der heute `WC` in der SMS sieht, sieht **zwingend bereits `FK`/`FD`
  daneben** (Beleg: G1-Messung im Kontext-Dokument, `"... FD-6/-1 ... WC-6"`)
  — die Ableitung existiert unabhängig von dieser Scheibe.

## Acceptance Criteria

- **AC-1:** Given eine Metrik mit SMS-Kürzeln / When Code oder Oberfläche
  danach fragt / Then liefert sie das Register; `SMS_MULTI_SYMBOLS_BY_METRIC`
  wird daraus **abgeleitet** und nicht mehr danebengepflegt (Muster wie
  `SMS_SYMBOL_BY_METRIC` seit E3b) — kein hartkodiertes Kürzel für die
  sechs betroffenen Größen mehr in der Dict-Definition selbst.
  - Test: AST-Prüfung, dass an der Zuweisung kein `ast.Dict`-Literal mit
    `ast.Constant`-String-Werten für diese sechs Schlüssel mehr steht (die
    E7-Registrierung liefert das nach Implementation Details Punkt 4 als
    Laufzeit-Set); ergänzend Wertevergleich der abgeleiteten Tabelle gegen
    die AC-9-Erwartungstabelle.

- **AC-2:** Given die Temperatur-Familie / When der Kürzel-Wächter läuft /
  Then meldet er **keine** Abweichung mehr zwischen Register und Versand —
  weder für die sechs Größen aus AC-1 (jetzt `sms_multi_symbols`) noch für
  `wind_chill` (jetzt ohne `WC`), und die Registrierung in
  `metrik_listen_scan.py` erkennt die umgestellte Tabelle weiterhin (s.
  Implementation Details Punkt 4).
  - Test: `tests/unit/test_sms_token_symbol_register_ratchet.py` komplett
    grün inkl. der drei bestehenden „gemeinsam ziehen"-Tests; Mutationsnachweis
    s. „Mutations-Gegenprobe" Punkt 4.

- **AC-3:** Given `temperature_day_high` und `temperature_night` / When ihre
  `sms_code`-Werte geprüft werden / Then sind sie **leer** (`""`) — die
  toten Werte `TD`/`TN` sind entfernt, ihr tatsächlich gesendetes Kürzel
  (`D`/`N`) trägt ausschließlich `sms_multi_symbols`. `temperature`,
  `temperature_cold` und `wind_chill` behalten unverändert `"D"`/`"N"`/
  `"TF"`, weil `comparison.py:647` und `alert/render.py:93` genau diese drei
  Katalog-IDs lesen (gemessen 2026-08-16, s. „Zu messen, nicht zu raten"
  Punkt 1) — die globale Eindeutigkeit von `sms_code` bleibt erhalten (jetzt
  ohne die beiden toten Duplikate) und ist per Test belegt.
  - Test: `tests/tdd/test_issue_917_alert_renderer.py::TestAC6CatalogSmsCodes::
    test_all_sms_codes_globally_unique` bleibt grün; die zwei umgeschriebenen
    Pinning-Tests (`test_temp_tagesrichtung_aufloesung.py:309-313`,
    `test_metric_catalog.py:17-29`) prüfen jetzt explizit `== ""` statt
    `== "TD"`/`== "TN"`; Compare-SMS-Test (`temp_max_c`/`temp_min_c` →
    `"D"`, `wind_chill_min_c`/`wind_chill_max_c` → `"TF"`) und
    Alarm-SMS-Test (`temperature`→`"D"`, `temperature_cold`→`"N"`) bleiben
    unverändert grün.

- **AC-4:** Given das SMS-Kürzel `WC` / When eine Trip-Kurznachricht erzeugt
  wird / Then erscheint es **nicht mehr** — weder bei aktivem `wind_chill`
  noch in `/api/sms-symbols` (das den Endpunkt generisch aus
  `SMS_MULTI_SYMBOLS_BY_METRIC` serialisiert, kein eigener Code-Pfad nötig).
  - Test: `tests/unit/test_sms_token_symbol_register_ratchet.py::
    test_all_symbol_tables_carry_the_same_wintersport_symbols` (bestehend,
    erkennt asymmetrisches Entfernen) plus
    `test_legacy_snow_symbols_are_absent_from_all_tables`-Muster für `"WC"`;
    API-Contract-Test gegen `/api/sms-symbols`, dass kein Eintrag mehr
    `sms_symbol="WC"` führt.

- **AC-5:** Given ein Bestands-Trip, in dem `wind_chill` für die SMS aktiv
  ist / When die Änderung ausgeliefert ist / Then zeigt seine
  Kurznachricht weiterhin die gefühlte Tages-Tiefsttemperatur — die Auswahl
  ist (bereits seit #1728 S1/S3, nicht neu durch diese Scheibe) auf
  `wind_chill_day_low` überführt. Kein Nutzer verliert stillschweigend
  einen Wert.
  - Test: Roundtrip-Fixture — ein Trip mit `wind_chill` aktiv, aber ohne
    explizite `wind_chill_day_low`/`-high`-Einträge in `channel_layouts.sms`
    — nach dem Laden (`_append_derived_metrics()`) müssen beide als
    `derived=True`/`enabled=True` erscheinen, auf allen drei
    Konfigurationsebenen. **Dieser Test existiert nach heutigem Stand nicht
    explizit für den `wind_chill`-Fall** (nur für `temperature_day_low`/
    `-high` belegt) — s. „Zu messen, nicht zu raten" Punkt 3: falls er
    fehlschlägt, ist die Migration doch aktiv zu bauen.

- **AC-6:** Given eine Trip-Kurznachricht eines Bestandsnutzers / When sie
  nach der Änderung erzeugt wird / Then ist ihr Inhalt **zeichengleich** zu
  vorher, mit der einzigen Ausnahme des entfallenen `WC`-Tokens.
  - Test: `SMSTripFormatter().format_sms()` mit Fixture, die alle sechs
    Größen aus AC-1 plus `wind_chill` aktiviert; Positionsvergleich (nicht
    nur Substring) gegen die alte Golden-Referenz minus `WC`-Token.

- **AC-7:** Given die Metrik `wind_chill` / When Mail-Stundentabelle,
  Telegram-Zelle und Kurzzusammenfassung gerendert werden / Then arbeiten
  sie unverändert weiter — sie lesen `dp_field`, nicht das SMS-Kürzel.
  - Test: bestehender E-Mail-/Telegram-Renderer-Test für `wind_chill`
    (`col_key="felt"`) läuft unverändert grün.

- **AC-8:** Given die zwei Provider Open-Meteo und Geosphere schreiben
  fachlich unterschiedliche Größen in dasselbe Feld `wind_chill_c` / When
  ein Entwickler den Code an `openmeteo.py:394` bzw. `geosphere.py:552,573`
  liest / Then erklärt ein Kommentar an BEIDEN Stellen unmissverständlich,
  welche Größe der jeweilige Provider tatsächlich liefert (Open-Meteo:
  `apparent_temperature`; Geosphere: berechneter Wind Chill,
  nordamerikanische Formel, nur T ≤ 10 °C) — keine Umbenennung, kein
  Migrations-Schritt (166 Dateien, über 840 Fundstellen, persistiertes Feld
  mit Go-JSON-Tag).
  - Test: `# doc-compliance-test`-markierter Dateiinhalt-Check auf beide
    Kommentarstellen (CLAUDE.md-Ausnahme für Doku-Nachweise; kein
    Verhaltens-Test möglich, weil sich am Laufzeitverhalten nichts ändert).

- **AC-9:** Given der Wächter aus AC-2 / When jemand eine Kürzel-Zuordnung
  im Register vertauscht / Then wird er rot. Er darf sein Soll **nicht**
  aus derselben Quelle rechnen wie der Prüfling — getippte Erwartungswerte
  sind Pflicht, sonst ist die Zusicherung eine Tautologie.
  - Test: neue oder erweiterte Testfunktion in
    `test_sms_token_symbol_register_ratchet.py` mit einer von Hand
    getippten Erwartungstabelle (`{"temperature_day_low": "K",
    "temperature_day_high": "D", "temperature_night": "N",
    "wind_chill_day_low": "FK", "wind_chill_day_high": "FD",
    "wind_chill_night": "FN"}`, Muster:
    `tests/tdd/test_issue_917_alert_renderer.py::TestAC6CatalogSmsCodes`);
    Wirksamkeit über Mutations-Gegenprobe Punkt 1.

## Zu messen, nicht zu raten

Die folgenden Punkte hat diese Spec bereits gemessen (Belege oben) — der
Entwickler muss sie **in der RED-Phase gegen den dann aktuellen Stand
erneut verifizieren**, nicht blind übernehmen:

1. **Welche Katalog-IDs erreichen die beiden `get_sms_code()`-Leser
   tatsächlich?** Gemessen (2026-08-16, zur Laufzeit ausgezählt):
   - Compare (`_RENDERER_TO_CATALOG_METRIC_ID.values()`,
     `comparison.py:546-548` gebaut aus `FRONTEND_TO_RENDERER_METRIC_ID` +
     `COMPARE_METRIC_CATALOG`): **`temperature`** (`temp_max_c`/
     `temp_min_c`) und **`wind_chill`** (`wind_chill_min_c`/
     `wind_chill_max_c`, `compare_metric_ids.py:45-46` +
     `compare_metric_catalog.py:131-136`).
   - Alarm (`alert/render.py:93` → `alert/project.py::_resolve_metric_id()`,
     gestützt auf `_METRICS`-`summary_fields` + `direction`): **`temperature`**
     und **`temperature_cold`**.
   - `temperature_day_high`/`temperature_night` erscheinen in **keiner**
     der beiden Mengen — tote Werte, deshalb Implementation Details Punkt 2.
   - **#1728 S3 (PR #1884) fasst `metric_catalog.py` an** — vor
     Implementierungsbeginn erneut prüfen, ob eine dritte Leserstelle für
     `get_sms_code()` dazugekommen ist (`grep -rn "get_sms_code("`).
2. **Ist die WC-Fundstellenliste in Tests vollständig?** Diese Spec hat per
   `grep '"WC"'`/`grep "'WC'"`/`grep "WC"` über `tests/` **18
   Python-Dateien + 2 Golden-Dateien + 1 Frontend-Testdatei** gefunden und
   für 11 davon eine echte, WC-abhängige Zusicherung bestätigt (Liste unten
   unter „Betroffene Tests"). Für die übrigen 7 (`test_temp_
   tagesrichtung_bestandsableitung.py`, `test_sms_unknown_on_missing_
   data.py`, `test_sms_snow_symbols.py`, `test_sms_temperature_range_
   token.py`, `test_sms_symbol_grammar_classes.py`, `test_renderers_
   text_report.py`, `multiSymbolMetricRowWiring.test.ts`) wurde nur ein
   Fundstellen-Ausschnitt gelesen, nicht die volle Änderungsnotwendigkeit
   bewertet — **erneut grep + einzeln entscheiden**, bevor RED geschrieben
   wird (V7: nach dem ALTEN Kürzel suchen, nicht nur nach dem Metriknamen;
   `grep -rln` über das GANZE Repo, nicht nur den naheliegenden Ordner).
3. **Ist die #1728-Ableitung (`_DERIVED_METRIC_RULES`) wirklich schon
   vollständiger Bestandsschutz für AC-5?** Diese Spec leitet aus dem Code
   (`loader.py:756-792`, drei Aufrufstellen `846/889/922-924`) her, dass
   keine neue Migration nötig ist, weil `wind_chill_day_low`/`-high` bei
   jeder aktiven `wind_chill`-Auswahl bereits mitgeladen werden — auf allen
   drei Konfigurationsebenen. **Das ist Herleitung aus Lesen, kein
   Test-Nachweis** — ein expliziter Roundtrip-Test für genau diesen Fall
   wurde nicht gefunden (bestehende Tests decken `temperature_day_low`/
   `-high` ab, nicht nachweislich `wind_chill_day_low`/`-high`). Schlägt der
   in AC-5 geforderte Test fehl, ist eine echte Migration zu bauen und diese
   Spec vor der Umsetzung nachzubessern.
4. **Bricht die Registrierungs-Umstellung (AC-2) wirklich laut, nicht
   still?** Diese Spec leitet aus `_literal()`/`_benennung()`/`_seiten()`
   (`metrik_listen_scan.py:103-148, 249-275`) her, dass eine
   Dict-Comprehension `LookupError` auslöst, den `pruefe_registrierte_
   liste()` (Zeile 422-427) als Befund meldet. **Das wurde am Code
   nachvollzogen, nicht durch tatsächliches Ausführen der Ratsche gegen
   einen probeweise umgestellten Stand bestätigt** — genau das ist Teil des
   RED-Nachweises für AC-2.
5. **Uniqueness-Prüfung mit Leerwert — Ergebnis der Nachmessung
   (2026-08-16):** drei Fundstellen filtern `sms_code` bereits heute auf
   Wahrheitswert, bevor sie auf Kollision prüfen:
   `tests/tdd/test_issue_917_alert_renderer.py:507-513`
   (`test_all_sms_codes_globally_unique`, `codes = [m.sms_code for m in
   _METRICS if m.sms_code]`), `tests/unit/test_sms_token_symbol_
   register_ratchet.py:478-493`
   (`test_register_kuerzel_bezeichnen_je_genau_eine_groesse`, sowohl der
   dict-comprehension-Filter als auch `finde_kuerzel_kollisionen()` selbst
   überspringen leere Werte) und
   `tests/tdd/test_temp_tagesrichtung_aufloesung.py:314-320` (dieselbe
   Filterform, zusätzlich mit Verweis auf Test 1 im Fehlertext). **`""`
   kollidiert mit nichts — bestätigt, kein Umgehen nötig.** Zwei weitere
   Tests **pinnen** die alten Werte direkt und brechen dadurch **absichtlich**
   (nicht durch Kollision, sondern durch die geänderte Erwartung selbst):
   `test_temp_tagesrichtung_aufloesung.py:309` (`sms_code == "TD"`) und
   `test_metric_catalog.py:25` (`get_sms_code("temperature_night") ==
   "TN"`) — beide müssen umgeschrieben werden (s. Implementation Details
   Punkt 2, Mutations-Gegenprobe Punkt 7). Ohne diese Umschreibung wächst
   der tote Wert beim nächsten Merge-Konflikt stillschweigend nach, weil
   sonst **kein** Test mehr behauptet, dass er leer sein MUSS.

## Bewusste Grenzen

- **Keine Legende in der Oberfläche.** Das ist Scheibe B (#1888) — diese
  Scheibe ändert nichts an `WeatherMetricsTab.svelte` oder verwandten
  Frontend-Komponenten (außer der einen Kommentarzeile in
  `multiSymbolMetricRowWiring.test.ts`, falls sie sich auf `WC` als
  Beispiel bezieht).
- **Literale in `src/output/tokens/` bleiben Literale.** Der Ordner
  importiert seit E3b bewusst nichts aus `src/app/`; die Übereinstimmung
  sichert weiterhin die bestehende Ratsche in der Testschicht
  (`test_sms_token_symbol_register_ratchet.py`). Diese Scheibe erweitert
  diese Grenze nicht um einen neuen, eigenständigen Test — sie nutzt die
  vorhandene Ratsche.
- **Nur `temperature`, `temperature_cold` und `wind_chill` bleiben mit
  unverändertem `sms_code` unangetastet** — NICHT `temperature_day_high`/
  `temperature_night` (die verlieren ihren toten Wert, s. AC-3). Frühere
  Fassungen dieser Spec hatten das noch undifferenziert formuliert („die
  beiden Altlasten bleiben stehen") — nach der Nachmessung der tatsächlich
  erreichten Katalog-IDs (Punkt 1 oben) ist klar: nur lebende Werte bleiben
  unangetastet, tote werden entfernt. Das neue Feld `sms_multi_symbols`
  trägt die Trip-SMS-Werte für die sechs betroffenen Größen in einem
  eigenen, kollisionsfreien Namensraum, ohne Alert-SMS/Compare-SMS zu
  berühren.
- **Die vorbestehende Compare-Kollision (`temp_max_c`/`temp_min_c`, beide
  `"D"` über `temperature.sms_code`, G4 im Kontext-Dokument) wird NICHT
  behoben** — außerhalb des Scopes dieser Scheibe, unabhängiger Befund.
- **#1848** (Vokabular-Vereinheitlichung Compare/Ausblick) bleibt
  eigenständig, hier nicht berührt.
- **Keine Umbenennung von `wind_chill_c`.** AC-8 verlangt ausdrücklich nur
  den Kommentar (R2 im Kontext-Dokument: 166 Dateien/>840 Fundstellen wären
  ein Daten-Schema-Rework).

## Mutations-Gegenprobe

Für jede neu bewachte Zusicherung mindestens eine gezielte Verfälschung,
die ein bestehender oder neuer Test fangen MUSS:

1. **AC-9/AC-1:** In einer lokalen, nicht committeten Kopie
   `temperature_day_high.sms_multi_symbols` und
   `temperature_night.sms_multi_symbols` vertauschen (`D`↔`N`) →
   der getippte AC-9-Wächter muss rot werden und beide Größen beim Namen
   nennen.
2. **AC-4:** Nur den `PRIORITY`-Eintrag `"WC"` entfernen, `POSITIONAL`/
   `DROP_ORDER`/`_wintersport_default_config()` unverändert lassen →
   `test_all_symbol_tables_carry_the_same_wintersport_symbols` muss rot
   werden (asymmetrische Entfernung, `missing_priority`-Zweig).
3. **AC-3:** `temperature.sms_code` testweise auf `"TX"` setzen → ein
   Compare-SMS- oder Alert-SMS-Test muss rot werden (verändertes Kürzel in
   einer zugestellten Nachricht, die nicht Teil dieser Scheibe sein soll).
4. **AC-2:** Die alte `_BESTAND`-Zeile für `SMS_MULTI_SYMBOLS_BY_METRIC`
   NICHT auf Laufzeit-Lesung umstellen, während die Tabelle bereits zur
   Comprehension wird → die Registrierungs-Prüfung muss `LookupError`/„Die
   Registrierung zeigt ins Leere" melden (Nachweis, dass die Umstellung
   nötig UND die Fehlermeldung sichtbar ist, nicht stumm).
5. **AC-5:** Testweise die Ableitungsregel für `wind_chill_day_low`/`-high`
   aus `_DERIVED_METRIC_RULES` entfernen → der Roundtrip-Test aus AC-5 muss
   rot werden (Nachweis, dass der Test wirklich den Bestandsschutz misst
   und nicht zufällig aus einem anderen Grund grün ist).
6. **AC-8:** Den Kommentar an `geosphere.py:552` versehentlich weglassen,
   an `openmeteo.py:394` stehen lassen → der `# doc-compliance-test`
   markierte Dateiinhalt-Check muss beide Stellen einzeln prüfen und bei
   einer fehlenden rot werden.
7. **AC-3 (Regrowth-Schutz):** `temperature_day_high.sms_code` testweise
   wieder auf `"TD"` setzen (bei unverändertem `sms_multi_symbols`) → OHNE
   die Umschreibung der beiden Pinning-Tests (Implementation Details Punkt
   2) würde **kein** Test das fangen, weil `"TD"` mit nichts kollidiert und
   keine der drei Uniqueness-Prüfungen einen toten Wert als Fehler erkennt.
   Erst der umgeschriebene Pinning-Test (`== ""`) macht diese Verfälschung
   sichtbar — das ist der eigentliche Beleg, warum die Umschreibung Pflicht
   und keine Kür ist.

## Betroffene Tests

**Mit bestätigter, WC-abhängiger Zusicherung (grep + Kontext gelesen,
2026-08-16):**

- `tests/tdd/test_sms_wintersport_tokens.py:120-138` — kompletter
  Testzweck war der Nachweis, dass `WC` erscheint (Bug #1450); wird durch
  den PO-Entscheid gegenstandslos, braucht Neufassung mit Verweis auf diese
  Spec statt stiller Löschung.
- `tests/tdd/test_felt_night_own_metric_selection.py` (~10 Stellen, Zeilen
  41, 74, 86–91, 98, 106–116, 235–258) — mehrere Erwartungsmengen
  `{"FK","FD","WC"}` → `{"FK","FD"}`.
- `tests/tdd/test_channel_metric_matrix.py:1001-1019` — AC-8-Test (E3b)
  „alle Kürzel einer Metrik toggeln gemeinsam", Erwartung
  `{"FK","FD","WC"}` → `{"FK","FD"}`.
- `tests/tdd/test_temp_tagesrichtung_aufloesung.py:120-175` — Testzweck
  „WC bleibt an der Elterngröße" (E3, #1450) wird durch den PO-Entscheid
  überholt; braucht Neufassung, nicht stille Löschung.
- `tests/tdd/test_temp_tagesrichtung_bestandsableitung.py:234-251` —
  Erwartungsmenge `{"N","K","D","FN","FK","FD","WC"}` → ohne `WC`.
- `tests/unit/test_token_builder.py:134,254,277,297` — `MetricSpec(symbol=
  "WC", …)` und `WC` in Positions-Tupeln entfernen.
- `tests/unit/test_trip_result_adapter.py:351,366` — `WC` aus erwarteter
  `MetricSpec`-Liste entfernen.
- `tests/unit/test_sms_symbol_grammar_classes.py:255` — `WC` aus
  Symbol-Liste entfernen.
- `tests/unit/test_renderers_text_report.py:40,66` — `MetricSpec(symbol=
  "WC", …)` entfernen.
- `tests/tdd/test_sms_letter_value_separator.py:173,236-241` —
  `"WC10"` als Positions-Anker in `_OUTRANKS_THE_FOURTEEN`; Ersatz-Anker
  wählen (z. B. `FK`/`FD`).
- `tests/tdd/test_sms_extended_tokens_truncation.py:66,148` — `MetricSpec`
  und Truncation-Erwartung `"WC-22"` entfernen.
- `tests/golden/sms/arlberg-winter-morning.txt:1` — `WC-22` am Zeilenende
  entfernen (Zeichenzahl/Kürzungsverhalten neu prüfen).
- `tests/golden/text_report/stubaier-skitour-evening.txt:6` — `WC-28`
  entfernen.
- `tests/unit/test_sms_token_symbol_register_ratchet.py` —
  `EXEMPT_FORECAST_FIELDS["wind_chill_c"]` entfällt (kein Wintersport-Token
  mehr für dieses Feld); neuer getippter Wächter für AC-9.
- `tests/helpers/metrik_listen_scan.py` — Registrierung umstellen (s.
  Implementation Details Punkt 4).

**`sms_code`-Pinning-Tests, MÜSSEN umgeschrieben werden (neu identifiziert
nach der Korrektur-Nachmessung, 2026-08-16):**

- `tests/tdd/test_temp_tagesrichtung_aufloesung.py:309-313` — pinnt
  `_METRICS_BY_ID[TEMP_HIGH].sms_code == "TD"` mit Begründung „DEC-8, 'D'
  ist bereits von 'temperature' belegt". Wird zu `== ""`; Kommentar auf
  diese Spec verweisen (der DEC-8-Kompromiss ist mit AC-3 aufgehoben, nicht
  nur verschoben).
- `tests/unit/test_metric_catalog.py:17-29` — pinnt
  `get_sms_code("temperature_night") == "TN"`, ursprünglich #923b-Nachweis
  gegen ein leeres Token in der SMS-Fidelity-Vorschau. **Nachgemessen: die
  Fidelity-Vorschau (`validator_render_service.py::_symbols_for_metric()`)
  liest `SMS_MULTI_SYMBOLS_BY_METRIC` VOR `SMS_SYMBOL_BY_METRIC`/`sms_code`**
  — der historische Bug kann durch das Leeren von `sms_code` nicht
  wiederkehren. Test wird zu `get_sms_code("temperature_night") == ""`;
  Prüfziel für die Fidelity-Vorschau wandert auf
  `SMS_MULTI_SYMBOLS_BY_METRIC["temperature_night"] == ("N",)`. Der
  begleitende Test `test_ac4_temperature_cold_bleibt_unveraendert_n`
  (Zeile 32ff.) bleibt unverändert grün.

**Nur Fundstelle gelesen, Änderungsnotwendigkeit NICHT abschließend
bewertet — Entwickler muss in RED erneut grep + einzeln entscheiden:**

- `tests/tdd/test_sms_unknown_on_missing_data.py:123,134`
- `tests/tdd/test_sms_snow_symbols.py:10,49,274,354-489,625,638`
  (umfangreichste Fundstelle — enthält u. a. einen Test, der explizit „WC
  verschwindet bei Abwahl von wind_chill" prüft; dessen ganze
  Existenzberechtigung entfällt, wenn `WC` nie mehr entsteht)
- `tests/tdd/test_sms_temperature_range_token.py:267-283,347`
- `frontend/.../multiSymbolMetricRowWiring.test.ts:4-82` (vermutlich nur
  Kommentar-/Beispieltext, keine funktionale Zusicherung — verifizieren)

## Known Limitations

- **Die vorbestehende Compare-Kollision bleibt bestehen.**
  `temp_max_c`/`temp_min_c` liefern in `/api/compare/metrics` beide `"D"`
  über `temperature.sms_code` (G4 im Kontext-Dokument) — unabhängig von
  dieser Scheibe, kein Teil von AC-1 bis AC-9.
- **`thunder`s Doppel-Kürzel (`TH:`/`TH+:`) bleibt der seit #1482/E3b
  dokumentierte Sonderfall** — nicht in die neue `sms_multi_symbols`-Logik
  überführt, weiterhin literal gemergt (s. Implementation Details Punkt 1).
- **Der AC-5-Roundtrip-Test für `wind_chill` existiert nach heutiger Messung
  nicht** — bestehende Roundtrip-Abdeckung wurde nur für
  `temperature_day_low`/`-high` gefunden, nicht nachweislich für
  `wind_chill_day_low`/`-high`. Diese Scheibe MUSS ihn ergänzen, nicht nur
  voraussetzen (s. „Zu messen, nicht zu raten" Punkt 3).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine.
- **Rationale:** Kein neuer Architektur-Grundsatz — die Registerherrschaft
  über Renderer-Vokabulare ist etablierte Praxis (ADR-0011, fortgeführt in
  E1a/E1b/E3a/E3b dieser Themenreihe). ADR-0050 („Kanal-Ebene darf nur
  abwählen") bleibt unverändert gültig und wird durch diese Scheibe nicht
  berührt — die für den Bestandsschutz relevante Ableitung
  (`_DERIVED_METRIC_RULES`) existiert bereits seit #1728 S1/S3 und wird
  hier nur gelesen, nicht erweitert.

## Changelog

- 2026-08-16: Initial spec created. Ist-Stand gegen den aktuellen
  Code-Stand verifiziert (nicht aus dem Kontext-Dokument übernommen):
  Neufund der aktiven Leser von `temperature.sms_code`/
  `temperature_cold.sms_code` (`comparison.py:647`, `alert/render.py:93`).
  Neufund, dass `_DERIVED_METRIC_RULES` (`loader.py`) die in V4
  befürchtete Migration bereits seit #1728 S1/S3 abdeckt. WC-Testoberfläche
  vollständig per grep erhoben (18 Python- + 2 Golden- + 1
  Frontend-Testdatei).
- 2026-08-16 (Korrektur nach Koordinator-Nachmessung): Ausgezählt, welche
  Katalog-IDs die beiden `sms_code`-Leser tatsächlich erreichen — Ergebnis:
  Compare erreicht `temperature` UND `wind_chill`, Alarm erreicht
  `temperature` UND `temperature_cold`; `temperature_day_high`
  (`"TD"`)/`temperature_night` (`"TN"`) werden von KEINEM Leser erreicht
  und sind damit tote Werte, keine legitime zweite Namensebene. AC-3
  entsprechend korrigiert (leert `TD`/`TN` statt sie unangetastet zu
  lassen), „Bewusste Grenzen" präzisiert, AC-5 aus dem Issue-Text
  aufgenommen (Bestandsschutz-Migration, durch bestehenden Mechanismus
  erfüllt, aber Test-Nachweis fehlt und muss ergänzt werden), zwei
  identifizierte Pinning-Tests (`test_temp_tagesrichtung_aufloesung.py`,
  `test_metric_catalog.py`) als Pflicht-Änderung aufgenommen, Uniqueness-
  Prüfung mit Leerwert nachgewiesen (drei Tests filtern bereits falsy),
  Mutations-Gegenprobe um Regrowth-Schutz (Punkt 7) ergänzt.
