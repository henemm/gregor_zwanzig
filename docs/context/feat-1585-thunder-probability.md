# Context: feat-1585-thunder-probability (#1585 Scheibe B)

## Request Summary

`thunder_probability` soll als zweite und letzte nutzersichtbare Gewitter-Metrik in den
Katalog aufgenommen und aus der Ensemble-Mehrheit befüllt werden (Anteil der Modellläufe mit
Gewittercode). Vorgeschaltet war die Klärung, ob der Open-Meteo-Ensemble-Endpunkt die dafür
nötigen Daten überhaupt liefert und was der Abruf im Kontingent kostet.

## 🔴 Ergebnis der vorgeschalteten Abruf-Klärung (gemessen 2026-08-07, echte Live-Abrufe)

### Was trägt

| Frage | Messergebnis |
|---|---|
| Liefert der Ensemble-Endpunkt `weather_code` je Member? | **Ja** — `hourly=weather_code` wird akzeptiert, HTTP 200 |
| Wie viele Läufe kommen zusammen? | **71 Reihen** bei den drei heute genutzten Modellen: `icon_seamless_eps` **40**, `ncep_gefs_seamless` **31**, `ecmwf_ifs04` **1** |
| Braucht es einen zweiten HTTP-Call? | **Nein** — `hourly=temperature_2m,precipitation,weather_code` liefert alle drei Größen in einem Call (63 kB statt 7 kB) |

⚠️ **`ecmwf_ifs04` steuert nur den Kontrolllauf bei, keine Member.** Die im Issue genannten
„40 Läufe" sind faktisch das ICON-EPS; ein einfacher Anteil über alle Reihen wäre ein
ICON/GFS-Mischwert, in dem ECMWF mit 1/71 praktisch bedeutungslos ist.

### 🔴 Was NICHT trägt — der Ensemble-Wettercode ist gewitterblind

Gemessen über 8 Orte × 7 Tage × 40 Member = **53.760 Werte**: nur **22 Gewittercodes (0,04 %)**,
ausnahmslos Code 95. **96 und 99 kamen kein einziges Mal vor.**

Gegenprobe gegen den deterministischen Forecast (gleiche Orte, gleicher Zeitraum) — es liegt
nicht nur an der ruhigen Wetterlage:

**Wallis, alle 9 Stunden mit Gewitter im Hauptlauf:**

| Zeit | Hauptlauf | EPS-Member mit Gewitter | EPS-Codes stattdessen |
|---|---|---|---|
| 2026-08-12T13:00–15:00 | 95 | **0 / 40** | 51 (Niesel) ×19, 2 ×10–14 |
| 2026-08-13T10:00–15:00 | 95 | **0 / 40** | 2 ×15–22, 3 ×8–16, 51 ×4–14 |

Der Befund ist über Modelle und Regionen robust:

| Messung | Gewittertreffer |
|---|---|
| Wallis, `icon_seamless` (6720 Werte) | 0 |
| Wallis, `gfs_seamless` (5208 Werte) | 0 |
| Balkan / Ungarn, `icon_seamless` (je 6720) | 0 / 0 |
| Rumänien, `icon_seamless` (6720) | 8 — Spitze **2/40 = 5 %** |
| GR20 Korsika / Pyrenäen (Spitzenwerte) | 8 % / 10 % |

**Konsequenz:** Die im Issue geplante Definition („Anteil der Läufe mit WMO 95/96/99") ergäbe
eine Metrik, die fast immer 0 % anzeigt und ihren Höchstwert bei ~10 % hat — **während die
Stufe aus demselben System „Gewitter" meldet.** Zwei sich widersprechende Gewitter-Metriken,
genau in der Lage, für die das Produkt gebaut ist. Der im Issue notierte Beispielwert
„19 von 40 = 47 %" ist mit dieser Definition an keinem der acht Orte reproduzierbar.

### Alternative Größen je Member (gemessen)

| Variable | Verfügbar je Member? |
|---|---|
| `cape` | ✅ 40 Reihen mit echten Werten (570, 200, 620, 270 …) |
| `precipitation` | ✅ 40 Reihen (wird heute schon geholt) |
| `showers` | ✅ 40 Reihen |
| `convective_inhibition` | 🟡 akzeptiert, Reihen aber **leer** |
| `lifted_index` | 🟡 akzeptiert, Reihen aber **leer** |

⚠️ Eine Ableitung aus CAPE-Schwellen wäre **Eigenkalibrierung** — PO-seitig verboten
(Grund für die Schließung von #1456). Das ist in der Analyse zu klären, nicht zu setzen.

## 🔴 Kontingent-Befund

Der `ForecastBudgetGate` zählt **einmal pro `fetch_forecast()`**, nicht pro HTTP-Aufruf
(`src/services/segment_weather.py:194`). Der heutige Ensemble-Call wird durch denselben
`record_call()` mitkassiert und erscheint **nicht separat**. Solange der Wettercode in den
bestehenden Call wandert, entsteht **kein zusätzlicher Verbrauch im Zähler** — ein
eigenständiger zweiter Ensemble-Abruf wäre dagegen im Kontingent **unsichtbar**, bis er ein
eigenes `record_call()` bekommt.

Das Diagnose-Log `data/diagnostics/openmeteo_calls.jsonl` protokolliert dagegen jeden
physischen Call inklusive Ensemble (`src/providers/call_log.py:37`, Quellzuordnung
`("_fetch_ensemble_spread", "ensemble")`).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/app/models.py:168` | `thunder_probability_pct: Optional[int] = None` — leeres, dokumentiertes Zielfeld |
| `src/app/metric_catalog.py:28-88` | `MetricDefinition` inkl. `selectable` (Zeile 67) |
| `src/app/metric_catalog.py:328-352` | `cape`-Eintrag — heute ohne `selectable`, also wählbar (Scheibe C) |
| `src/app/metric_catalog.py:307` | `confidence` mit `selectable=False` — Präzedenz |
| `src/app/metric_catalog.py:670` | `get_all_metrics()` filtert `if m.selectable` |
| `api/routers/config.py:58-63` | `/api/metrics` ruft `get_all_metrics()` |
| `src/providers/openmeteo.py:684-770` | `_fetch_ensemble_spread()` — Abrufstelle, `hourly` in Zeile 703 |
| `src/providers/openmeteo.py:1104-1129` | Zuweisung der Ensemble-Werte an die Datenpunkte; hier entsteht `confidence_pct` |
| `src/providers/call_log.py:37` | Quellzuordnung des Ensemble-Calls im Diagnose-Log |
| `src/services/segment_weather.py:194` | einziger `record_call()` des Budget-Gates |
| `tests/tdd/test_thunder_probability_field_prepared_empty.py` | Wächter, der die Leere des Feldes festhält — wird durch B rot |

## Ausgabeorte einer Gewitter-Metrik (belegt, gegen die 9-Punkte-Regel geprüft)

| # | Ort | Fundstelle |
|---|---|---|
| 1 | E-Mail-Pill | `email/helpers.py:1670` (`_pill_for_metric`) |
| 2 | Trip-Stundentabelle | `email/helpers.py:185` (`dp_to_row`) |
| 3 | Nachtblock | `email/helpers.py:154-236` (`aggregate_night_block`, dupliziert) |
| 4 | Kurzzusammenfassung | `compact_summary.py:571` |
| 5 | SMS-Token | `sms_trip.py:280` |
| 6 | Telegram-Fußzeile | `narrow.py:210` |
| 7 | GEWITTER-Kommando + Drilldown | `trip_command_processor.py:228, 114, 126, 980` |
| 8 | Ortsvergleich | `compare_html.py:158-159, 331-332, 600` |
| 9 | Mehrtages-Vorschau | `outlook.py:200-202, 371-372`; `trip_report_scheduler.py:1820` |

Nicht betroffen: `tokens/builder.py` und `comparison.py` enthalten keine Gewitter-Referenzen —
`comparison.py` arbeitet generisch über `metric_id`, eine Katalogmetrik erscheint dort von selbst.

## Risks & Considerations

1. **🔴 Die Datenquelle trägt die geplante Metrik nicht.** Der Ensemble-Wettercode vergibt
   Gewitter fast nie. Vor jeder Implementierung muss die Spec beantworten, woraus die
   Wahrscheinlichkeit stattdessen entsteht — sonst entsteht eine Metrik, die konstant 0 %
   anzeigt und der Stufe widerspricht.
2. **Schwellen sind Produktentscheidung, nicht Forschung.** `display_thresholds` /
   `risk_thresholds` der Prozentskala sind im Issue ausdrücklich offen. Eine Ableitung aus
   CAPE-Membern wäre dagegen Eigenkalibrierung und damit verboten.
3. **Rückgabevertrag.** `_fetch_ensemble_spread()` gibt heute
   `Dict[datetime, Tuple[Optional[float], Optional[float]]]` zurück
   (`openmeteo.py:684-694`). Ein dritter Wert erweitert diese Signatur — bestehende Aufrufer
   und Tests hängen daran.
4. **Neun Ausgabeorte.** PO-Grundsatz: eine Wettermetrik hat diverse Ausgabeorte, alle müssen
   berücksichtigt werden (bei Hagel wurden 5 von 9 vergessen).
5. **Reihenfolge B vor C.** CAPE ist beim PO in drei Trips und einem Vergleichs-Preset aktiv.
   Fällt C vor B, verschwindet eine Spalte ersatzlos.
6. **Bestandsdaten.** Gespeicherte Trips mit aktiviertem `cape` müssen still weiterladen —
   Muster ADR-0005/#710, keine Migration.

## Existing Patterns

### 🔴 Die Aggregation ist NICHT generisch — jedes Feld ist einzeln verdrahtet

`summary_fields={"max": "cape_max_jkg"}` im Katalog ist **nur ein Lookup-Register**
(`summary_field_for()`, `metric_catalog.py:577-588`). Es gibt **keinen** Aggregator, der daraus
automatisch rechnet. Für eine neue aggregierte Größe braucht es sechs Stellen:

| # | Stelle | Beleg (am Beispiel `cape`) |
|---|---|---|
| 1 | Feld in `ForecastDataPoint` | `app/models.py` — für uns vorhanden (`:168`) |
| 2 | Feld in `SegmentWeatherSummary` | `app/models.py:425` (`cape_max_jkg`) |
| 3 | eigene `_compute_X()`-Methode | `weather_metrics.py:938-941` (`_compute_cape`) |
| 4 | Aufruf + Zuweisung **Trip-Pfad** | `weather_metrics.py:756`, `:797` |
| 5 | Zuweisung **Compare-Pfad** (zweite, separate Stelle!) | `weather_metrics.py:1083` (`summarize_points()`) |
| 6 | Eintrag in `aggregation_config` | `weather_metrics.py:821` |

Punkt 5 ist die klassische Vergessensfalle: Trip- und Compare-Aggregation sind getrennt
verdrahtet. Wer nur Punkt 4 macht, bekommt eine Metrik, die im Trip funktioniert und im
Ortsvergleich leer bleibt.

### Präzedenz für den Ensemble-Abruf

`docs/specs/modules/forecast_confidence.md` ist die Master-Spec für genau diesen Weg
(Abschnitt 3 „OpenMeteo Ensemble-Call", Abschnitt 4 „Aggregation in `SegmentWeatherSummary`").
Sie ist die formale Vorlage für Scheibe B.

### Präzedenz für Scheibe C (`cape` unsichtbar)

Die Render-Pfade prüfen **bereits generisch** auf `selectable`:
`email/helpers.py:117-118`, `:172-175`, `:282-286`, `email/html.py:1024`, `alert_preset.py:254`
— jeweils `if not metric_def.selectable: continue`. Scheibe C ist damit im Kern **ein
Katalog-Kwarg**, kein neuer Code. Bestandsdaten laden still weiter (ADR-0005, Zeile 27-29).

### Frontend

Der Compare-Metrik-Katalog wird **live** aus dem Backend gezogen
(`shared/corridor-editor/compareMetricCatalogLoader.ts:3` über `GET /api/compare/metrics`) —
eine neue Katalogmetrik erscheint dort **ohne Frontend-Änderung**. Hartkodierte Listen
existieren, betreffen aber die Stärke-Metrik, nicht die Wahrscheinlichkeit:
`types.ts:72-88` (`AlertMetric`-Union, nur bei alarmfähiger Metrik nötig),
`WeatherMetricsTab.svelte:206` (`SMS_THRESHOLD_METRIC_IDS`).

## Existing Specs

| Datei | Inhalt |
|---|---|
| `docs/specs/modules/forecast_confidence.md` | **Präzedenz**: Ensemble-Call + Aggregation für `confidence_pct` |
| `docs/specs/modules/feat_1474_gewitter_befund_stufen.md` §5 (Z. 282-299) | legt `thunder_probability_pct` als leeres Feld an, ausdrücklich ohne Quelle/Renderer |
| `docs/reference/api_contract.md:274` | dokumentiert bereits: Befüllung „braucht den Wettercode je Lauf im Ensemble-Abruf, der heute nur Temperatur und Niederschlag anfordert" |
| `docs/reference/decision_matrix.md:109` | „Zweite Achse, vorbereitet: `thunder_probability_pct`" |
| `docs/adr/0005-confidence-not-selectable-metric.md` | bindende Vorlage für Scheibe C inkl. Bestandsdaten-Regel |
| `docs/adr/0025`, `0043`, `0047` | Nachbar-ADRs zur Gewitter-Stufenskala und Quellenwahl |
| `docs/specs/modules/openmeteo_additional_metrics.md:11-15` | Referenz für vollständige Pipeline-Integration einer neuen Metrik |
| `docs/context/feat-1480-thunder-scale-guard.md` | Wächter gegen Kopien der **Stärke**-Skala; berührt die Prozent-Achse nicht, solange sie keine eigene Stufung bekommt |

## Dependencies

- **Upstream:** Open-Meteo Ensemble-API (`ensemble-api.open-meteo.com/v1/ensemble`),
  `_fetch_ensemble_spread()`, `ForecastBudgetGate`
- **Downstream:** `SegmentWeatherSummary` → alle neun Ausgabeorte oben; `/api/metrics` und
  `/api/compare/metrics` → Trip-Editor und Compare-Editor

---

# Analysis

## Type

Feature (Epic-Scheibe). **Ergebnis: die Datengrundlage trägt die Scheibe in der geplanten Form
nicht** — siehe Quellenbewertung.

## Kernfrage

Woraus entsteht eine Gewitter-Wahrscheinlichkeit 0–100 %, **ohne Eigenkalibrierung von
Schwellen** (PO-Verbot, Grund für die Schließung von #1456)?

## Quellenbewertung — alle Kandidaten live gemessen 2026-08-07

| # | Quelle | Ergebnis | Urteil |
|---|---|---|---|
| 1 | **Open-Meteo Ensemble, Anteil Läufe mit WMO 95/96/99** *(der im Issue geplante Weg)* | 22 Gewittertreffer in 53.760 Werten (0,04 %); Codes 96/99 **nie**; bei 9 Hauptlauf-Gewitterstunden **0 von 40** Membern; Spitzenwerte 5–10 % | ❌ **untauglich** — Metrik stünde konstant nahe 0 % und widerspräche der Stufe |
| 2 | **Open-Meteo `thunderstorm_probability`** | Parametername wird akzeptiert (HTTP 200), Einheit `undefined`, Reihen **bei allen 11 geprüften Modellen leer** (icon_d2, icon_eu, arome_france_hd, gfs, ecmwf_ifs025, knmi, dmi, ukmo …) | ❌ **Scheinparameter** — klassischer stiller Parameter-Rückfall |
| 3 | **DWD MOSMIX `wwT`** (Gewitterwahrscheinlichkeit, echte %) | Werte real und plausibel (Bukarest bis 23 %, Genf 13 %). **Aber:** an 8 von 13 geprüften Stationen **vollständig leer** (0/247), ohne erkennbares Muster — Berlin ✅ / München ❌, Genf ✅ / Zürich ❌, ferner Stuttgart, Hohenpeißenberg, Zugspitze, Wien, Innsbruck ❌. `ww` und `wwP` sind an denselben Stationen vollständig | 🟡 **nur bedingt** — siehe Ortsbindung |
| 4 | **CAPE je Ensemble-Member** | ✅ verfügbar, 40 Reihen mit echten Werten | ❌ **verboten** — Ableitung einer Prozentskala daraus wäre Eigenkalibrierung |

### Ortsbindung von MOSMIX — für dieses Produkt der entscheidende Haken

MOSMIX ist **stationsbasiert**, nicht flächig (4209 Stationen im Katalog). Gemessene Abstände
zur nächsten Station:

| Zielgebiet | nächste Station | Höhe | Entfernung |
|---|---|---|---|
| **GR20 Mitte (Korsika)** | BASTIA | **10 m** | **31 km** |
| Wallis/Alpen | ZERMATT | 1638 m | 18 km |
| Tirol | HOERNLE | 1538 m | 4 km |

Der GR20 verläuft auf ~1500–2000 m. Eine Gewitterwahrscheinlichkeit von einer Küstenstation
auf Meereshöhe, 31 km entfernt, ist für den Bergkamm fachlich nicht tragfähig — und Korsika ist
das Kernzielgebiet des Produkts. **Bitter dabei:** Genau dort, wo die Stationen dicht und hoch
liegen (Alpen), ist `wwT` leer; wo `wwT` gefüllt ist (Korsika), liegen die Stationen falsch.

### 🔴 MOSMIX `wwT` ist vom DWD selbst abgekündigt (Primärquelle)

Die gemessene Lückenhaftigkeit ist kein Zufall und kein Abrufproblem. DWD-Newsletter
25.06.2025 (`dwd.de/DE/fachnutzer/.../2025_0604_mosmix_aenderung.pdf`), Abschnitt
„Wegfall der Gewittervorhersagen an vielen Stationen seit der Version vom 07. Mai 2025":

> „Da es derzeit nur noch ca. **25 Stationen in Deutschland mit manuellen
> Gewitterbeobachtungen** gibt, ergeben sich leider automatisch große Regionen in
> Deutschland, in denen keine Gewittervorhersage mehr möglich ist."

> „**Wir empfehlen ganz generell allen Nutzern von MOSMIX-Gewittervorhersagen auf andere
> Produkte wie z.B. die Wetterinterpretation (ww) aus dem DMO umzusteigen**, auch wenn es
> derzeit für Ihre Station noch MOSMIX-Gewittervorhersagen gibt. Dies kann sich leider
> jederzeit ändern."

Ursache: `wwT` ist ein **MOS-Parameter**, statistisch aus historischen *Beobachtungen*
trainiert — nicht aus Modellphysik abgeleitet. Mit dem Wegfall manueller SYNOP-Gewitter-
beobachtungen bricht die Grundlage strukturell weg. Das erklärt das gemessene Muster exakt
(Berlin ✅ / München ❌ — nicht geografisch, sondern nach verbliebener Beobachtungsstation).

Elementdefinition zur Vollständigkeit (`opendata.dwd.de/weather/lib/MetElementDefinition.xml`):
`wwT` = „Probability: Occurrence of thunderstorms within the last hour", Einheit `% (0..100)`;
nur in MOSMIX_L, nicht in MOSMIX_S.

⇒ **Ausschlusskriterium, nicht bloße Einschränkung.** Eine Metrik auf einen Parameter zu
bauen, von dessen Nutzung der Betreiber ausdrücklich abrät, wäre fahrlässig.

### Weitere geprüfte Anbieter

| Anbieter | Ergebnis |
|---|---|
| **Open-Meteo** | Kein Gewitterwahrscheinlichkeits-Parameter in der Doku. `precipitation_probability` existiert, ein Gewitter-Pendant nicht. MOSMIX wird nicht eingebunden, `wwT` kommt also auch nicht indirekt |
| **Météo-France** | PEARP/PEAROME liefern nur allgemeine „champs statistiques"; kein benannter Gewitter-Parameter auffindbar — **nicht belegbar**, offen bliebe ein `GetCapabilities`-Abruf |
| **ECMWF Open Data** | `type=ep` (Ensemble-Probability) frei zugänglich, aber kein Gewitter-spezifisches Feld belegbar; ECMWF behandelt Gewitter über Indizes (CAPE, EFI) |
| **GeoSphere AT, MeteoSwiss, AEMET, KNMI** | kein belegbarer direkter Parameter gefunden |
| **NCEP NBM `TSTM`** | ✅ echte Gewitterwahrscheinlichkeit in % — aber **nur CONUS/Alaska/Hawaii**, für Europa irrelevant |

## Fazit der Analyse

Es gibt **derzeit keine belegte, flächige Quelle** für eine Gewitter-Wahrscheinlichkeit in
Prozent, die die Zielgebiete des Produkts abdeckt. Jeder gangbare Weg verletzt eine bindende
Vorgabe oder liefert eine Metrik, die entweder konstant 0 % zeigt oder für den Zielort nicht
gilt.

## Open Questions (PO-Entscheidung nötig)

- [ ] Scheibe B zurückstellen, bis eine tragfähige Quelle existiert — und stattdessen die
      Scheiben mit belegter Grundlage vorziehen (A3 Radar-Anhebung, A4 `sdi_2`)?
- [ ] Oder MOSMIX `wwT` bewusst als teilverfügbare Quelle akzeptieren (mit „unbekannt", wo sie
      fehlt — Muster #1492: „leer" ≠ „unbekannt")?
