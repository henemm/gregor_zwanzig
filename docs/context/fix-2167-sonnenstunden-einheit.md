# Context: fix-2167-sonnenstunden-einheit

**Issue:** #2167 — Ad-hoc-Abruf: `Sun` liefert Strahlungswerte mit Stunden-Etikett (781.5 h)
**Herkunft:** Nebenbefund aus der Staging-Verifikation von #2134 (Scheibe S1 von Epic #2133)
**Erstellt:** 2026-09-07 · **Track:** Bug
**Basis:** `origin/main` @ `2234d037`

## Analysis

### Type

**Bug.**

### Request Summary

Fragt der Wanderer per Telegram oder E-Mail-Antwort nach `Sun`, antwortet das System mit
Zeilen wie `15:00  781.5 h`. Der Zahlenwert ist die Direktstrahlung in W/m², das Etikett
kommt aus dem Katalog und sagt „h". Eine Stunde kann höchstens **1,0** Sonnenstunde
enthalten — die Angabe ist um rund den Faktor 800 daneben und dabei nicht als falsch
erkennbar. Das ist schlimmer als eine Fehlermeldung.

### Ursache — der Katalog beschreibt die Größe zweigeteilt, und die Teilung steht nirgends

| Glied | Beleg |
|---|---|
| Katalogeintrag sagt Einheit `h`, zeigt aber auf das Rohfeld `dni_wm2` (W/m²) | `src/app/metric_catalog.py:596-597` |
| Rohfeld im Datenmodell | `src/app/models.py:143` (`dni_wm2: Optional[float]  # Direct Normal Irradiance (W/m²)`) |
| Umrechnung liegt abseits vom Katalog | `src/services/weather_metrics.py:329-347` `dni_to_sunny_fraction()` — `<=min` → 0,0 · `>=max` → 1,0 · dazwischen linear |
| Band konfigurierbar, Defaults 60/180 W/m² | `src/app/config.py:139-140` |
| Ad-hoc-Pfad liest generisch das Rohfeld | `src/services/trip_command_processor.py:993-995` |
| … und beschriftet es mit der Katalog-Einheit | `:379-383` → `format_value(metric.id, value)`; Einheit angehängt in `src/output/metric_format.py:112,126-128` |

### Warum es bis #2134 nicht auffiel

Jeder bisherige Anzeigepfad ging über einen Renderer, der die Metrik **namentlich** kennt
und den Katalogwert verwirft:

```
src/output/renderers/email/helpers.py:811-819
    if key == "sunshine":
        hours = row.get("_sunny_hours")      # vorberechnet in :139 (je Stunde) / :235 (je Block)
        return f"{hours:.1f} h"              # dieselbe Einheit — aus einer ANDEREN Zahl
```

#2134 macht den Katalog erstmals zur direkten Quelle einer Anzeige und legt den
Widerspruch damit offen. **Nicht durch #2134 verursacht, aber durch #2134 sichtbar.**

### Die Bestandsaufnahme aus dem Issue — sie fällt beruhigend aus

Alle 30 Katalogeinträge gegeneinander gehalten (`unit` gegen die physikalische Größe des
`dp_field`). Die Rohfeldnamen tragen ihre Einheit im Namen und stimmen durchweg:
`t2m_c`↔°C · `wind10m_kmh`↔km/h · `pop_pct`↔% · `cape_jkg`↔J/kg · `pressure_msl_hpa`↔hPa ·
`snow_depth_cm`↔cm · `snowfall_limit_m`↔m · `freezing_level_m`↔m.

- **`sunshine` ist der einzige Eintrag mit echtem Einheitenbruch.**
- Der einzige weitere Abweichungsfall — `visibility`, `unit="m"` + `display_unit="km"`
  (`metric_catalog.py:571-578`) — ist bereits sauber modelliert und wird über die
  Faktortabelle `src/output/metric_format.py:71-73` aufgelöst (angewandt `:116-121`).

Die im Issue befürchtete Streuung („wo steht das sonst noch?") existiert nicht. Das
Problem ist ein Einzelfall — aber ein struktureller, weil der katalog-getriebene Ansatz
Zielbild ist (#1372, #1514).

### Alle vier Briefing-Pfade rechnen korrekt — falsch ist ausschließlich der Ad-hoc-Abruf

| Pfad | Beleg |
|---|---|
| E-Mail (Zelle je Stunde / je Block) | `src/output/renderers/email/helpers.py:139`, `:235` |
| Trip-Report | `src/output/renderers/trip_report.py:641`, `:686` |
| SMS / Premium-SMS | `src/output/renderers/sms_trip.py:419-422` |
| Ortsvergleich | `src/services/comparison_engine.py:261,560` |

Alle rufen dieselbe Funktion `WeatherMetricsService.calculate_sunny_hours()`. Es gibt
**keine** zweite, abweichende W/m²→h-Umrechnung im Bestand. Der Fix muss also nichts
geradeziehen, sondern nur die eine fehlende Umrechnung nachtragen.

### Entschieden: der Ad-hoc-Abruf RECHNET, er verweigert nicht

Der Ortsvergleich löst denselben Widerspruch durch **Ausschluss** —
`HOURLY_EXCLUDED_METRIC_IDS` (`src/output/renderers/compare_hourly_metric_ids.py:56-64`,
PO-Entscheid 2026-08-01) enthält `sunshine` mit der Begründung `:70-74`:

> „Stuendlich nur als Einstrahlung (W/m²) verfuegbar, nicht als Sonnenstunden …"

**Diese Begründung ist am Trip-Bestand widerlegt.** `email/helpers.py:139` ruft
`calculate_sunny_hours([dp])` für einen **einzelnen** Datenpunkt — der Stundenwert in
Stunden existiert und wird täglich ausgeliefert (Beleg #2104: „Stunden 08..14 je 1,0 h").
Entsprechend enthält die **trip-seitige** Ausschlussmenge `NO_HOURLY_COLUMN_METRIC_IDS`
(`email/helpers.py:104-108`) `sunshine` **nicht** — nur die sechs Fenster-Kennzahlen.

Der Ausschluss im Ortsvergleich hält damit eine Umsetzungslücke fest, keine Eigenschaft
der Größe. Für den Ad-hoc-Abruf gilt die trip-seitige Regel: die Größe hat einen
Stundenwert, also wird er gerechnet. Zusätzlich stützt das die eigene Hilfe des Systems,
die `Sun / SU – Sonnenstunden (h)` ausgibt (`trip_command_processor.py:1663-1677`) — heute
widerspricht die Antwort der eigenen Hilfe.

**Der Ortsvergleich bleibt unangetastet** (Compare-Themen sind zurückgestellt).

### Technical Approach

**Vierter `dp_field`-Zweig in `_metric_formatter()`** (`src/services/trip_command_processor.py:354-384`).

Die Funktion dispatcht dort bereits nach Eigenschaft des Katalogeintrags — `is_level`
(`:363`), `dp_field == "wind_direction_deg"` (`:365`), `dp_field == "precip_type"` (`:371`).
Die Spec zu #2134 führt diese Tabelle ausdrücklich
(`docs/specs/modules/feat_2134_adhoc_abruf_metrik_katalog.md:106-117`); der Fix ergänzt
eine vierte Zeile, statt ein neues Muster zu erfinden.

Erreicht **beide** Ad-hoc-Einstiege, weil beide `_metric_formatter()` benutzen:
`_handle_drilldown` (Button-Token, `:907-911`) und `_handle_metric_drilldown`
(getipptes Wort, `:984-1002`); die Ausgabezeile entsteht gemeinsam in `_format_drilldown`
(`:1172`).

**Verworfene Alternativen:**

1. **Umrechnung in `format_value()`** — bricht die beiden anderen Aufrufer. Nachgemessen:
   `src/output/renderers/comparison.py:118` und `src/output/renderers/email/helpers.py:1634`
   übergeben dort bereits **fertige Stunden** (`style="bare"` + eigenes „h"). Eine
   Umrechnung in `format_value` würde dort doppelt rechnen.
2. **Neues Katalogfeld, das auf die Rechenfunktion zeigt** — würde die Schichtung umdrehen.
   `metric_catalog` liegt in `app/`, `weather_metrics` in `services/`; `app/models.py:714-720`
   hält ausdrücklich fest, dass der Katalog dort bereits in einer Import-Klemme steckt
   (`models` importiert den Katalog nur lokal). Ein String-Key plus Registry in einem
   dritten Modul wäre der Ausweg — deutlich mehr Fläche für einen Einheiten-Bugfix.
   *(Korrektur zur Zwischenbewertung: einen harten Importzyklus gäbe es NICHT —
   `weather_metrics.py` importiert `metric_catalog` auf Modulebene gar nicht, der einzige
   Treffer `:577` ist ein Kommentar. Der Grund ist die Schichtung, nicht ein Zyklus.)*
3. **`unit` auf `W/m²` umstellen** (Vorschlag 2 des Issues) — ändert die Briefing-Anzeige,
   die seit #347/#1401 PO-freigegeben ist.

**Umsetzungshinweis:** Die `Settings()`-Instanz für das DNI-Band gehört **außerhalb** der
Formatierer-Closure geholt — sonst wird sie je Stundenzeile neu gebaut (24×).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_command_processor.py` | MODIFY | `_metric_formatter()` `:354-384` — vierter Zweig `dp_field == "dni_wm2"`: Rohwert über `dni_to_sunny_fraction()` in Stunden, dann unverändert durch `format_value()` |
| `tests/tdd/test_adhoc_metrik_formatierung.py` | MODIFY | neuer AC-Fall in der bestehenden Reihe (AC-13…AC-16); Vorrichtung `tests/helpers/adhoc_metrik_fixtures.py` existiert bereits |

**Ausdrücklich NICHT anzufassen:**
`src/output/metric_format.py` (`format_value` bleibt unberührt) ·
`src/app/metric_catalog.py` (kein neues Feld) ·
`src/output/renderers/email/helpers.py` und `trip_report.py` (Briefing-Sonderwissen bleibt —
s. „Bewusst nicht in diesem Zuschnitt") ·
`src/output/renderers/compare_hourly_metric_ids.py` (Ortsvergleich zurückgestellt).

### Scope Assessment

- Files: **2** (beide MODIFY)
- Estimated LoC: Produktivcode **+12…16**, Tests **+40…60** → deutlich unter dem Limit 250
- Risk Level: **LOW**

### Risiko — die sechs Bestandstests einzeln geprüft

Keiner läuft durch die geänderte Zeile:

| Test | Warum unberührt |
|---|---|
| `tests/unit/test_issue_347_sunshine_hours.py` | prüft `calculate_sunny_hours()` direkt, kein Import von `trip_command_processor` |
| `tests/tdd/test_renderer_katalog_schwellen.py:314` | Pill-Kette `helpers.py:1628`, andere Aufrufkette |
| `tests/tdd/test_issue_808_sonne_pill.py` | dieselbe Pill-Kette |
| `tests/unit/test_compare_hourly_catalog_columns.py:327-336` | Compare-Ausschluss, wird nicht angefasst |
| `tests/tdd/test_channel_metric_matrix.py:3931-3935` | laut eigenem Kommentar bereits als tautologisch markiert |
| `tests/tdd/test_adhoc_metrik_formatierung.py` | enthält heute **keinen** Sonne-Fall — hier entsteht der neue Test |

Restrisiko ist Vollständigkeit, nicht Bruch: der Verlauf zeigt künftig je Stunde einen
Bruchwert 0,0–1,0 h. Das deckt sich mit dem Briefing und mit dem Muster der übrigen
Drilldowns (Gewitter/Wind/Regen zeigen ebenfalls Stundenwerte, keine Tagessummen).

### Dependencies

- `src/services/weather_metrics.py:329-347` — `dni_to_sunny_fraction()`, heute nur von
  `calculate_sunny_hours()` (`:350`) gerufen; wird zum zweiten Aufrufer erweitert
- `src/app/config.py:139-140` — DNI-Band
- `src/output/metric_format.py:79-129` — `format_value()`, unverändert
- `tests/helpers/adhoc_metrik_fixtures.py` — Mock-freie Vorrichtung (`lege_trip_an`,
  `sende`, `standard_felder`, `katalog_eintrag_ersetzt`)

### Vorgeschlagene Acceptance Criteria (Freigabe in `/30-write-spec`)

- **AC-1:** Given `sunshine` trägt im Katalog `unit="h"` und `dp_field="dni_wm2"`, und die
  Stundenwerte führen eine Direktstrahlung oberhalb des Sonnen-Bands / When ein Nutzer
  `Sun` sendet / Then trägt jede Stundenzeile einen Wert von höchstens 1,0 h, und die rohe
  W/m²-Zahl steht nirgends in der Antwort.
- **AC-2:** Given eine Stunde mit einer Direktstrahlung unterhalb des unteren Bandwerts /
  When `Sun` abgerufen wird / Then weist diese Stunde 0,0 h aus — der Verlauf
  unterscheidet sonnige von trüben Stunden, statt überall denselben Wert zu zeigen.
- **AC-3:** Given dieselben Stundendaten / When einmal das Trip-Briefing gerendert und
  einmal `Sun` abgerufen wird / Then nennen beide für dieselbe Stunde denselben
  Sonnenstundenwert — die beiden Wege teilen die Umrechnung, statt sie zweimal zu führen.
- **AC-4:** Given die übrigen Ad-hoc-Größen / When `Visib`, `Thdr`, `WDir` und `PType`
  abgerufen werden / Then bleibt ihre Ausgabe unverändert (Positivkontrolle gegen
  Überkorrektur).
- **AC-5:** Given die Zusicherung aus AC-1 / When die Umrechnung im Produktivcode wieder
  entfernt wird, sodass der Rohwert durchgereicht wird / Then wird mindestens ein Test rot
  (Mutations-Gegenprobe).

### Open Questions

- [x] Rechnen oder verweigern? → **Rechnen.** Die trip-seitige Regel
  (`NO_HOURLY_COLUMN_METRIC_IDS`) führt `sunshine` nicht als stundenwertlos, das Briefing
  liefert den Stundenwert täglich aus, und die eigene Hilfe verspricht „(h)".
- [x] Vorschlag 1 oder 2 des Issues? → **1**, aber an der Datenpunkt-Naht statt in
  `format_value` (s. Technical Approach).
- [x] Briefing-Sonderwissen im selben Zug abräumen? → **Nein**, s. unten.
- [x] Ist der Ad-hoc-Abruf von Fenster-Kennzahlen (`Night`, `DayMin` …) ein zweiter Bug?
  → **Nein.** Die Spec zu #2134 hat das ausdrücklich entschieden
  (`feat_2134_adhoc_abruf_metrik_katalog.md:243-249`: „Das ist hinzunehmen und zu
  dokumentieren, nicht wegzukürzen"). Sie zeigen auf echte Stundenfelder (`t2m_c`,
  `wind_chill_c`) und liefern einen echten Verlauf, keinen 24-fach wiederholten Skalar.

### Bewusst NICHT in diesem Zuschnitt

- **Briefing-Sonderwissen abräumen** (`email/helpers.py:811-819`, `trip_report.py`).
  Zwei Gründe, beide am Risiko: (a) Der Sonderzweig maskiert einen **latenten
  Zweitfehler** — weil `sunshine` `default_aggregations=("sum",)` trägt, summieren die
  generischen Zeilenbauer die rohen W/m² in `row["sunshine"]`
  (`trip_report.py:617-618`, `helpers.py:212-213`); wer den Zweig entfernt, muss das
  mitlösen. (b) Beide Dateien sind Mail-Inhalts-Dateien und lösen das
  **Renderer-Commit-Gate** aus, `trip_command_processor.py` nicht.
  → Sammel-Eintrag **#1199**, kein eigenes Ticket (kein nutzersichtbares Fehlverhalten,
  der Wert wird nie ausgeliefert).
- **Provider ohne DNI.** `calculate_sunny_hours()` weicht auf die Bewölkung aus, wenn
  **kein** Datenpunkt DNI trägt (`weather_metrics.py:363-365,399-411`). Der Ad-hoc-Pfad
  liest über den Ein-Feld-Vertrag von `WeatherExtractor.drilldown()` stur `dni_wm2` und
  meldet über `_traegt_werte()` (`trip_command_processor.py:430-440`) korrekt „nicht
  verfügbar". Das ist vorbestehendes Verhalten, das dieser Fix weder verursacht noch
  verschlimmert; es zu schließen hieße, den Ein-Feld-Vertrag auf einen Mehrfeld-Abruf
  (DNI + drei Wolkenfelder + Höhenlage) zu erweitern. → Sammel-Eintrag **#1199**.
- **Ortsvergleich.** Der Ausschluss von `sunshine` aus dem Compare-Stundenverlauf bleibt
  bestehen, obwohl seine Begründung überholt ist — Compare-Themen sind zurückgestellt.
  → Sammel-Eintrag **#1199**.
