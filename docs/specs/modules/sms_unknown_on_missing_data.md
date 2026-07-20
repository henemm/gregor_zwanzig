---
entity_id: sms_unknown_on_missing_data
type: module
created: 2026-07-20
updated: 2026-07-20
status: draft
version: "1.0"
tags: [sms, day-window, teilausfall, tokens, bugfix]
---

<!-- Issue #1328 -->

# SMS: Unbekannt (`?`) statt Fehl-Entwarnung (`-`) bei Teilausfall

## Approval

- [ ] Approved

## Purpose

Bei einem teilweisen Wetterdaten-Ausfall (Fehlerquote ≤ `OUTAGE_WITHHOLD_RATIO`,
Briefing wird trotzdem versendet) überspringt die SMS-Aggregation Segmente mit
`has_error=True` bzw. fehlender Zeitreihe still und rendert für jedes Risiko,
zu dem dadurch keine Stichprobe vorliegt, das Null-Token `-` ("kein Risiko").
E-Mail und Telegram bekommen bei genau diesem Teilausfall bereits einen
expliziten Präfix-Hinweis (`partial_outage_hint`), die SMS nicht — sie ist der
einzige Kanal, der den Wanderer unterwegs erreicht, und zeigt eine falsche
Entwarnung. Diese Spec führt ein Token-Level-Unterscheidungsmerkmal ein:
`?` an der Wertstelle (z.B. `TH:?`) bedeutet "unbekannt, weil Daten fehlten",
`-` bleibt "kein Risiko bei vorhandenen Daten".

## Source

- **File:** `src/output/renderers/day_window.py` — neue Funktion, die meldet,
  ob im Aggregationsfenster mindestens ein Segment mit `has_error=True` bzw.
  fehlender/leerer Zeitreihe übersprungen wurde (dieselbe Bedingung wie
  Zeile 83, `if seg.has_error or ts is None or not ts.data: continue`)
- **File:** `src/output/renderers/sms_trip.py` — `_segments_to_normalized_forecast()`
  (ab Zeile 74) reicht das Ergebnis in die `DailyForecast` durch
- **File:** `src/output/tokens/dto.py` — `DailyForecast` (Zeile 19) bekommt ein
  neues optionales Feld
- **File:** `src/output/tokens/builder.py` — `_mk_metric()` (Zeile 85) und
  `build_token_line()` (Zeile 156) rendern `?` statt `-`, wenn keine Stichprobe
  vorliegt UND das Fenster Lücken hatte

> **Schicht-Hinweis:** reiner Python-Core-Renderer-Pfad (`src/output/...`),
> keine Go-API-, Frontend- oder DB-Berührung.

## Estimated Scope

- **LoC:** ~20 Produktionscode (4 Dateien, additive Änderungen) + ~70-100 Test
- **Files:** 4 Produktionsdateien + 1 neue Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.models.SegmentWeatherData.has_error` | Feld | Signalisiert Provider-Fehler pro Segment (Issue #1113) |
| `output.renderers.day_window.build_day_window_points` | Funktion | Liefert die 04-19-Uhr-Punktliste, aus der R/PR/W/G/TH: aggregiert werden — dieselbe Skip-Bedingung wird für die Gap-Erkennung wiederverwendet |
| `output.tokens.dto.DailyForecast` | DTO | Trägt das neue `has_data_gap`-Feld von der Aggregation zum Builder |
| `output.tokens.builder._mk_metric` | Funktion | Ort der Wert-vs-Unbekannt-Entscheidung |
| `output.tokens.metrics.render_threshold_peak_value` | Funktion | Unverändert — liefert weiterhin `-` als Null-Form, die Substitution passiert eine Ebene darüber |

## Implementation Details

### 1. Gap-Erkennung in `day_window.py` (neue Funktion, ~8 LoC)

Dieselbe Bedingung wie die bestehende Skip-Zeile 83, als eigenständige,
wiederverwendbare Prüfung (Anti-Duplikat-Prinzip dieses Moduls, siehe
Docstring "nie viermal unabhaengig nachbauen"):

```python
def segments_have_gap(segments: Sequence[SegmentWeatherData]) -> bool:
    """True, wenn mindestens ein Segment im Fenster keine Zeitreihe beitragen
    konnte (Provider-Fehler oder leere/fehlende Daten) — dieselbe Bedingung
    wie der Skip in build_day_window_points()."""
    return any(
        seg.has_error or seg.timeseries is None or not seg.timeseries.data
        for seg in segments
    )
```

### 2. Weitergabe in `sms_trip.py::_segments_to_normalized_forecast()`

Am Ende der Funktion, vor dem Bau von `today = DailyForecast(...)`:

```python
has_gap = segments_have_gap(segments)
...
today = DailyForecast(
    temp_min_c=day_min, temp_max_c=day_max,
    rain_hourly=rain_samples_d, pop_hourly=pop_samples_d,
    wind_hourly=wind_samples_d, gust_hourly=gust_samples_d,
    thunder_hourly=thunder_samples_d, confidence_pct_min=day_confidence,
    has_data_gap=has_gap,
)
```

Import ergänzt `segments_have_gap` aus `output.renderers.day_window` (dort
bereits `build_day_window_points` importiert).

### 3. DTO-Erweiterung `output/tokens/dto.py`

`DailyForecast` bekommt ein neues Feld mit sicherem Default:

```python
has_data_gap: bool = False  # Issue #1328: True -> "-" wird zu "?" (unbekannt)
```

Default `False` heißt: kein anderer Producer von `DailyForecast`
(E-Mail-Renderer, `compact_summary.py`, Tests) muss angepasst werden —
bit-identisches Verhalten, solange das Feld nicht explizit gesetzt wird.

### 4. Rendering in `output/tokens/builder.py`

`_mk_metric()` bekommt einen neuen optionalen Parameter `has_gap: bool = False`.

**Verschärfte Regel (PO-Entscheidung 2026-07-20):** ersetzt `-` durch `?`,
wenn das Fenster eine Datenlücke hatte — unabhängig davon, ob `samples` leer
war oder unterschwellige Stichproben lieferte. Die ursprüngliche Fassung
(„keine Stichprobe UND Lücke") ließ `W-`/`G-` fälschlich stehen, wenn ein
überlebendes Segment unterschwellige Werte (z.B. 5 km/h Wind) beitrug —
das ist weiterhin eine Entwarnung über einer lückenhaften Datenbasis. Die
neue Bedingung prüft das Render-**Ergebnis** statt der Eingabe:

```python
value = render_threshold_peak_value(symbol, samples, thr, is_level=is_level)
if value == "-" and has_gap:
    value = "?"
```

Sicherheitsinvariante bleibt strukturell erhalten: ein *gefundener* Wert
(`value != "-"`, z.B. `TH:H@14`, `W45@15`, `R5.0@13`) wird durch diese
Bedingung nie überschrieben — die Prüfung greift ausschließlich am
Null-Ergebnis `-`.

Aufruf im Forecast-Loop von `build_token_line()` — nur für die fünf aus dem
Tagesfenster aggregierten Symbole R/PR/W/G/TH: (NICHT für N/D [andere
Datenquelle: alle Segmente, ungefenstert] und NICHT für TH+: [andere
Datenquelle: `thunder_forecast`-Dict für Tag+1, nicht Teil dieses Fensters]):

```python
tok = _mk_metric(sym, samples, spec, report_type, is_lvl,
                  has_gap=today.has_data_gap)
```

`Token.render()` (dto.py Zeile 82) braucht **keine** Änderung: Der
Spezialfall greift nur für `value == "-"`; `"?"` fällt in den generischen
Zweig `f"{symbol}{value}"` und ergibt z.B. `TH:?`, `R?`, `W?`.

## Expected Behavior

- **Input:** SMS-Rendering-Aufruf (`SMSTripFormatter.format_sms()`) mit
  Segmenten, von denen mindestens eines `has_error=True` trägt oder keine
  Zeitreihe hat, UND für ein Symbol (R/PR/W/G/TH:) keine Stichprobe > 0 im
  04-19-Uhr-Fenster gefunden wurde
- **Output:** Das betroffene Token zeigt `?` an der Wertstelle
  (z.B. `TH:?` statt `TH:-`) statt einer stillen Entwarnung
- **Side effects:** keine — reine Rendering-Entscheidung, keine neuen
  Persistenz- oder Versand-Pfade; E-Mail/Telegram unverändert

## Acceptance Criteria

- **AC-1:** Given ein SMS-Aggregationsfenster, in dem mindestens ein Segment
  `has_error=True` trägt bzw. Stunden fehlen, und für eine Metrik kein
  Risiko/Wert ermittelt werden konnte / When die SMS gerendert wird / Then
  erscheint für diese Metrik `?` an der Wertstelle (z.B. `TH:?`) statt `-`.
  - Test: `SegmentWeatherData`-Liste mit einem `has_error=True`-Segment
    (leere `SegmentWeatherSummary()`, `timeseries=None`, wie
    `segment_weather.py:150-158` es bei Provider-Fehlern real erzeugt) und
    einem regulären Segment ohne Gewitter-Ereignis bauen, `format_sms()`
    aufrufen, `TH:?` im Ergebnis-String erwarten.

- **AC-2:** Given dasselbe Fenster mit Datenlücken, aber für eine Metrik wurde
  ein Risiko/Wert gefunden / When die SMS gerendert wird / Then wird dieser
  gefundene Wert unverändert angezeigt und nicht durch `?` ersetzt.
  - Test: dieselbe `has_error=True`-Segment-Mischung wie AC-1, aber das
    reguläre Segment enthält eine echte Gewitter-Stunde
    (`ThunderLevel.HIGH` im Datenpunkt) — Ergebnis-String muss `TH:H@<h>`
    enthalten, `TH:?` darf NICHT vorkommen (sicherheitskritisch: ein
    erkanntes Gewitter darf nie zu `?` verschluckt werden).

- **AC-3:** Given ein Fenster mit vollständigen Daten (kein `has_error`, keine
  fehlenden Stunden) / When die SMS gerendert wird / Then ist die Ausgabe
  identisch zum Verhalten vor diesem Fix — kein `?`, keine Formatänderung.
  - Test: nur fehlerfreie Segmente ohne Gewitter/Regen/Wind-Ereignis bauen,
    `format_sms()` aufrufen, `-` (nicht `?`) für R/PR/W/G/TH: erwarten —
    Regressionsschutz für das Bestandsverhalten.

- **AC-4:** Given die Längenbegrenzung (`max_length`, Default 160) / When `?`
  verwendet wird / Then bleibt die SMS innerhalb des Budgets — `?` belegt
  genau die Wertstelle, es kommt kein Zusatztext hinzu.
  - Test: `len(format_sms(...)) <= 160` für das AC-1-Szenario prüfen; da `?`
    exakt ein Zeichen wie `-` belegt, ist keine gesonderte Truncation-Logik
    nötig — der Test beweist das für den konkreten Fall statt es nur zu
    behaupten.

## Known Limitations

- **Fenster-weites, nicht pro-Metrik-genaues Signal:** `has_data_gap` ist ein
  einziges Bool für das gesamte 04-19-Uhr-Fenster, kein Fein-Tracking pro
  Stunde/Metrik. Das ist bewusst so gewählt (PO-Sicherheitsprinzip: lieber
  eine Metrik fälschlich als `?` markieren als eine echte "kein Risiko"-Aussage
  über eine tatsächlich lückenhafte Datengrundlage zu treffen). Verschärft
  2026-07-20: die Regel greift nicht mehr nur bei „keine Stichprobe", sondern
  bei jedem Render-Ergebnis `-` — auch wenn ein überlebendes Segment
  unterschwellige Stichproben (z.B. 5 km/h Wind) beitrug. Grund: eine
  Entwarnung `-` ist auf Basis einer nachweislich lückenhaften Datengrundlage
  strukturell nicht vertrauenswürdiger als eine Entwarnung ganz ohne
  Stichprobe — beide könnten eine echte, oberhalb der Schwelle liegende
  Spitze in der fehlenden Etappe verdecken.
- **N/D (Temperatur) und TH+: (Tag+1) bleiben unberührt:** Tagesmin/-max
  stammen aus allen Segmenten ungefenstert, `TH+:` aus dem separaten
  `thunder_forecast`-Dict — beide sind nicht Teil dieser Spec.
- **Vollausfall (>75 %) ist bereits korrekt gelöst** (Rückhalt +
  `send_no_data_hint` auch per SMS, Issue #1113/#1012) und nicht Teil dieser
  Spec; E-Mail/Telegram-Präfix-Hinweis (`partial_outage_hint`) bleibt
  unverändert bestehen.
- **Parallele Workflow-Kollision:** Der gleichzeitig laufende Workflow
  `feat-1318-1220-kurzform-ziel-warn` arbeitet ebenfalls an den
  Kurzform-Renderern (u.a. `day_window.py`/`sms_trip.py`-Umfeld). Diese
  Änderung ist bewusst additiv und lokal gehalten (neue Funktion +
  Default-`False`-Feld, keine Umbenennung/Umbau bestehender Signaturen), um
  ein Rebase zwischen beiden Workflows zu erleichtern.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (kein eigenes ADR-Dokument — Entscheidung ist lokal
  genug für die Spec selbst)
- **Rationale:** `?` an der Wertstelle statt Zusatztext, weil das
  160-Zeichen-SMS-Budget (`sms_format.md` §1) keinen Raum für einen
  Präfix-Satz lässt und `?` bereits als "nicht darstellbar/unbekannt"-
  Konvention im selben Dokument existiert (§1: nicht faltbare Zeichen werden
  zu `?`, nicht gelöscht). PO-Entscheidung 2026-07-20, verbindlich. Ein
  gefundener Wert wird nie durch `?` überschrieben (AC-2) — Sicherheit vor
  Vollständigkeit: eine falsche Entwarnung ist der zu vermeidende Fehler,
  ein zusätzliches `?` bei tatsächlich vorhandener echter Null-Stichprobe
  wäre der tolerierbare Fehler in die andere Richtung.
  **Nachschärfung (PO-Entscheidung 2026-07-20, selbes Datum):** die
  Bedingung wurde von „keine Stichprobe UND Lücke" auf „jede Entwarnung `-`
  UND Lücke" verschärft — unterschwellige Stichproben aus überlebenden
  Segmenten (z.B. 5 km/h Wind) durften die Entwarnung zuvor fälschlich
  legitimieren. Die Sicherheitsinvariante (gefundener Wert wird nie
  überschrieben) bleibt strukturell unverändert: sie greift an
  `value == "-"`, nicht an `samples`.

## Test Coverage

Neue Testdatei `tests/tdd/test_sms_unknown_on_missing_data.py` (Kern-Schicht,
deterministisch, netzfrei, keine Mocks — `SegmentWeatherData` mit
`has_error=True` ist eine echte Datenstruktur, kein Mock):

- `test_sms_shows_unknown_token_when_segment_has_error` (AC-1, verschärft:
  erwartet zusätzlich `R? PR? W? G?` im lückenhaften Fenster ohne Fund)
- `test_sms_keeps_found_risk_despite_other_segment_gap` (AC-2)
- `test_sms_shows_dash_when_no_gap` (AC-3, Regressionsschutz)
- `test_sms_unknown_token_stays_within_length_budget` (AC-4)
- `test_sms_shows_found_values_despite_gap_for_multiple_metrics` (Beweis der
  verschärften Regel: mehrere echte Warnwerte — Gewitter, Wind, Regen —
  bleiben trotz Lücke sichtbar, nur fundlose Metriken zeigen `?`)

## Changelog

- 2026-07-20: Initial spec erstellt — Issue #1328
- 2026-07-20: Regel verschärft nach PO-Entscheidung — jede Entwarnung bei
  Datenlücke wird `?`, nicht nur Metriken ohne Stichprobe.
