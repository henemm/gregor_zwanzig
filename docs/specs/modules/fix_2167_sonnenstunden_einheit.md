---
entity_id: fix_2167_sonnenstunden_einheit
type: module
created: 2026-09-07
updated: 2026-09-07
status: draft
version: "1.0"
tags: [bug, adhoc-abruf, metrik-katalog, einheiten, issue-2167]
---

# Fix #2167 — Ad-hoc-Abruf `Sun` liefert Sonnenstunden statt Strahlungswerte

## Approval

- [x] Approved — PO, 2026-09-07

## Purpose

Der Ad-hoc-Abruf der Größe `sunshine` soll Sonnenstunden ausgeben, wie es die Einheit im
Metrik-Katalog und die eigene Hilfe des Systems versprechen — heute gibt er die rohe
Direktstrahlung in W/m² aus und beschriftet sie mit „h". Der Fix trägt die Umrechnung nach,
die alle Briefing-Pfade längst anwenden, und schließt damit die letzte Stelle, an der
Katalog-Einheit und Katalog-Rohfeld auseinanderfallen.

## Source

- **File:** `src/services/trip_command_processor.py`
- **Identifier:** `_metric_formatter(metric)` (`:354-384`)

Schicht: **Python-Core / Domain-Backend** (`src/services/`). Weder Go-API noch Frontend sind
betroffen; der Metrik-Katalog (`src/app/`) wird nicht geändert.

## Estimated Scope

- **LoC:** ~55–75 (Produktivcode +12…16, Tests +40…60)
- **Files:** 2 (beide MODIFY)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/weather_metrics.py:329-347` `dni_to_sunny_fraction()` | READ | Die einzige Umrechnung W/m² → Sonnenstunden im Bestand; bekommt einen zweiten Aufrufer |
| `src/app/config.py:139-140` `sunny_dni_min_wm2` / `sunny_dni_max_wm2` | READ | Das Sonnen-Band (Defaults 60/180 W/m²) |
| `src/app/metric_catalog.py:594-613` Eintrag `sunshine` | READ | Liefert `unit="h"`, `decimals=1`, `dp_field="dni_wm2"` — **unverändert** |
| `src/output/metric_format.py:79-129` `format_value()` | READ | Rundung und Einheiten-Suffix — **unverändert** |
| `tests/helpers/adhoc_metrik_fixtures.py` | READ | Mock-freie Vorrichtung (`lege_trip_an`, `sende`, `standard_felder`) |
| `docs/specs/modules/feat_2134_adhoc_abruf_metrik_katalog.md:106-117` | READ | Die Dispatch-Tabelle „Formatierer folgt aus dem Katalogeintrag", die dieser Fix erweitert |

## Implementation Details

### Der Widerspruch, den der Fix auflöst

```
src/app/metric_catalog.py:596-597
    id="sunshine", label_de="Sonnenstunden", unit="h",
    dp_field="dni_wm2", ...
                ^^^^^^^^         ^^^
                W/m²             Stunden
```

Der Ad-hoc-Pfad liest das Rohfeld generisch (`trip_command_processor.py:993-995`,
`WeatherExtractor.drilldown(trip.id, metric.dp_field, …)`) und beschriftet es mit der
Katalog-Einheit (`:383` → `format_value(metric.id, value)`). Ergebnis: `781.5 h`.

Die Briefing-Pfade rechnen dagegen um, weil sie die Metrik **namentlich** kennen
(`src/output/renderers/email/helpers.py:811-819`, Vorberechnung `:139` je Einzelstunde).

### Die Änderung: vierte Zeile in einer bestehenden Dispatch-Tabelle

`_metric_formatter()` wählt den Formatierer bereits nach Eigenschaft des Katalogeintrags —
`is_level` (`:363`), `dp_field == "wind_direction_deg"` (`:365`), `dp_field == "precip_type"`
(`:371`), sonst `format_value()` (`:380-383`). Ergänzt wird ein vierter Zweig:

```
if metric.dp_field == "dni_wm2":
    # Band einmal je Abruf holen, NICHT je Stundenzeile (24 Aufrufe).
    <dni_min, dni_max aus Settings>
    def _sonnenstunden(value, *, with_emoji: bool = True) -> str:
        if value is None:
            return "· keine Daten"
        anteil = WeatherMetricsService.dni_to_sunny_fraction(value, dni_min, dni_max)
        return format_value(metric.id, anteil)
    return _sonnenstunden
```

Der Import von `WeatherMetricsService` erfolgt lokal in der Funktion — dasselbe Muster wie
die bestehenden lokalen Imports derselben Datei (`:905`, `:982`).

**Warum diese Stelle:** Beide Ad-hoc-Einstiege benutzen `_metric_formatter()` —
`_handle_drilldown` (Telegram-Knopf, `:907-911`) und `_handle_metric_drilldown` (getipptes
Wort, `:984-1002`). Die Ausgabezeile entsteht gemeinsam in `_format_drilldown` (`:1172`).
Ein Eingriff deckt beide Wege.

**Warum je Stunde ein Bruchwert richtig ist:** `calculate_sunny_hours([dp])` — der Weg, den
das Briefing je Einzelstunde geht (`helpers.py:139`) — reduziert sich für einen einzelnen
Datenpunkt mit DNI exakt auf `dni_to_sunny_fraction()`. Beide Wege liefern damit denselben
Stundenwert (AC-3).

### Verworfene Alternativen

| Alternative | Warum verworfen |
|---|---|
| Umrechnung in `format_value()` | Die beiden anderen Aufrufer übergeben dort bereits **fertige Stunden** — `src/output/renderers/comparison.py:118` und `src/output/renderers/email/helpers.py:1634` (beide `style="bare"` + eigenes „h"). Es würde doppelt gerechnet. |
| Neues Katalogfeld, das auf die Rechenfunktion zeigt | Dreht die Schichtung um: `metric_catalog` liegt in `app/`, `weather_metrics` in `services/`. `src/app/models.py:714-720` hält fest, dass der Katalog dort bereits in einer Import-Klemme steckt. Ein String-Schlüssel plus Registry in einem dritten Modul wäre der Ausweg — zu viel Fläche für einen Einheiten-Fix. |
| `unit` auf `W/m²` umstellen (Vorschlag 2 des Issues) | Ändert die Briefing-Anzeige, die seit #347/#1401 PO-freigegeben ist. |

### Betroffene Dateien

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_command_processor.py` | MODIFY | `_metric_formatter()` `:354-384` — vierter `dp_field`-Zweig für `dni_wm2` |
| `tests/tdd/test_adhoc_metrik_formatierung.py` | MODIFY | Neue AC-Fälle in der bestehenden Reihe (heute AC-13…AC-16) |

**Ausdrücklich NICHT anzufassen:** `src/output/metric_format.py` ·
`src/app/metric_catalog.py` · `src/output/renderers/email/helpers.py` ·
`src/output/renderers/trip_report.py` · `src/output/renderers/compare_hourly_metric_ids.py`.

## Expected Behavior

- **Input:** Ad-hoc-Abruf des Wortes `Sun` (oder des Kürzels `SU`) per Telegram oder
  E-Mail-Antwort gegen einen Trip mit stündlichen `dni_wm2`-Werten.
- **Output:** Stündlicher Verlauf, je Zeile ein Sonnenstundenwert zwischen `0.0 h` und
  `1.0 h` — dieselbe Zahl, die das Trip-Briefing für dieselbe Stunde in der Sonne-Spalte
  ausweist.
- **Side effects:** Keine. Kein Versand, keine Persistenz, kein geänderter API-Vertrag.
  Alle übrigen Abrufgrößen bleiben unverändert.

## Acceptance Criteria

- **AC-1:** Given der Katalog führt `sunshine` mit `unit="h"` und `dp_field="dni_wm2"`, und
  die Stundenwerte des Trips tragen eine Direktstrahlung deutlich oberhalb des oberen
  Bandwerts (z. B. 781,5 W/m²) / When ein Nutzer `Sun` sendet / Then trägt jede Stundenzeile
  einen Sonnenstundenwert von höchstens 1,0 h, und die rohe W/m²-Zahl erscheint nirgends in
  der Antwort.
  - Test: Trip über die bestehende Vorrichtung anlegen, `Sun` per Kanal-Eingang senden,
    jede Stundenzeile der Antwort auf den Zahlenwert prüfen; zusätzlich die Zeichenkette der
    Rohzahl im gesamten Antworttext ausschließen.

- **AC-2:** Given ein Trip, dessen Stunden teils oberhalb und teils unterhalb des unteren
  Bandwerts liegen / When `Sun` abgerufen wird / Then unterscheidet der Verlauf diese
  Stunden — die trüben Stunden weisen 0,0 h aus, die sonnigen einen Wert größer null; es
  steht nicht in allen Zeilen derselbe Wert.
  - Test: Stundenpunkte mit wechselnder Direktstrahlung (unter 60 und über 180 W/m²)
    belegen, Antwort auslesen und prüfen, dass mindestens eine Zeile 0,0 h und mindestens
    eine Zeile einen Wert über 0,0 h trägt.

- **AC-3:** Given dieselben Stundendaten / When einmal das Trip-Briefing die Sonne-Spalte
  rendert und einmal `Sun` ad hoc abgerufen wird / Then nennen beide für dieselbe Stunde
  denselben Sonnenstundenwert — die beiden Wege teilen die Umrechnung, statt sie zweimal zu
  führen.
  - Test: Für einen Stundenpunkt den Briefing-Zellwert über den Renderer-Pfad und den
    Ad-hoc-Zeilenwert über den Kanal-Eingang ermitteln und vergleichen. Der erwartete Wert
    wird **nicht** als Literal eingetippt, sondern aus beiden Pfaden gelesen.

- **AC-4:** Given die übrigen Ad-hoc-Größen mit eigenem Formatierer-Zweig / When `Visib`,
  `Thdr`, `WDir` und `PType` abgerufen werden / Then bleibt ihre Ausgabe unverändert
  gegenüber dem Stand vor dieser Änderung — die Sichtweite kommt weiterhin in km, das
  Gewitter als Stufenwort, die Windrichtung als Himmelsrichtung, die Niederschlagsart als
  deutsches Wort.
  - Test: Die vier bestehenden Testfälle AC-13 bis AC-16 in
    `tests/tdd/test_adhoc_metrik_formatierung.py` bleiben unverändert grün
    (Positivkontrolle gegen Überkorrektur).

- **AC-5:** Given die Zusicherung aus AC-1 / When die Umrechnung im Produktivcode entfernt
  wird, sodass der Rohwert wieder unverändert durch `format_value()` läuft / Then wird
  mindestens einer der neuen Tests rot.
  - Test: Mutations-Gegenprobe per String-Ersetzung mit externer Sicherungskopie; der
    mutierte Zweig muss vom Test tatsächlich erreicht werden.

## Known Limitations

- **Provider ohne Direktstrahlung.** `calculate_sunny_hours()` weicht auf die Bewölkung aus,
  wenn **kein** Datenpunkt DNI trägt (`src/services/weather_metrics.py:363-365,399-411`).
  Der Ad-hoc-Pfad liest über den Ein-Feld-Vertrag von `WeatherExtractor.drilldown()` stur
  `dni_wm2` und meldet über `_traegt_werte()` (`trip_command_processor.py:430-440`) korrekt
  „nicht verfügbar". Das ist vorbestehendes Verhalten, das dieser Fix weder verursacht noch
  verschlimmert; es zu schließen hieße, den Ein-Feld-Vertrag auf einen Mehrfeld-Abruf (DNI +
  drei Wolkenfelder + Höhenlage) zu erweitern. → Sammel-Eintrag #1199.
- **Latenter Zweitfehler im Briefing bleibt maskiert.** Weil `sunshine`
  `default_aggregations=("sum",)` trägt, summieren die generischen Zeilenbauer die rohen
  W/m² in `row["sunshine"]` (`src/output/renderers/trip_report.py:617-618`,
  `src/output/renderers/email/helpers.py:212-213`). Sichtbar wird das nur deshalb nicht,
  weil der namentliche Sonderzweig `helpers.py:811` den Zellwert verwirft. Dieser Fix
  berührt den Pfad nicht. Ein Abräumen des Sonderwissens müsste den Aggregations-Fehler
  mitlösen und würde zusätzlich das Renderer-Commit-Gate auslösen. → Sammel-Eintrag #1199.
- **Ortsvergleich bleibt ausgeschlossen.** `HOURLY_EXCLUDED_METRIC_IDS`
  (`src/output/renderers/compare_hourly_metric_ids.py:56-64`) nimmt `sunshine` vom
  Compare-Stundenverlauf aus, mit der Begründung `:70-74`, die Größe sei stündlich „nur als
  Einstrahlung (W/m²) verfuegbar, nicht als Sonnenstunden". Diese Begründung ist am
  Trip-Bestand widerlegt (`email/helpers.py:139` rechnet je Einzelstunde um; die
  trip-seitige Ausschlussmenge `email/helpers.py:104-108` führt `sunshine` **nicht**). Der
  Ausschluss bleibt dennoch stehen — Compare-Themen sind zurückgestellt. → Sammel-Eintrag
  #1199.
- **Kein Rückbau der Briefing-Anzeige.** `unit="h"` und die Beschriftung „Sonnenstunden"
  bleiben, wie seit #347/#1401 freigegeben.
- **Rundung.** `calculate_sunny_hours()` rundet über `round(x, 1)`, der Ad-hoc-Pfad über das
  `decimals=1` des Katalogs in `format_value()`. Beides ist Ein-Nachkommastellen-Rundung;
  eine Abweichung im Randfall (exakte 0,05-Schritte) ist nicht ausgeschlossen und für AC-3
  entsprechend zu behandeln.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Der Fix erfüllt ADR-0037/ADR-0055 (Katalog als Quelle statt handgepflegter
  Liste), indem er die bestehende, in
  `docs/specs/modules/feat_2134_adhoc_abruf_metrik_katalog.md:106-117` festgehaltene
  Dispatch-Tabelle „Formatierer folgt aus dem Katalogeintrag" um eine vierte Zeile ergänzt.
  Es entsteht keine neue Liste, kein neues Katalogfeld und keine zweite Umrechnung —
  `dni_to_sunny_fraction()` bleibt die einzige Quelle der W/m²→h-Wandlung im Bestand und
  bekommt lediglich einen zweiten Aufrufer.

## Changelog

- 2026-09-07: Initial spec created (Issue #2167, Nebenbefund aus der Staging-Verifikation
  von #2134)
