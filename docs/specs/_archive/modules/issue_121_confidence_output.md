---
entity_id: issue_121_confidence_output
type: module
created: 2026-05-15
updated: 2026-05-15
status: draft
version: "1.0"
tags: [forecast, confidence, sms, email, output, token-builder, metric-catalog]
parent: forecast_confidence
---

<!-- Issue #121 — Workflow 2 (Output) Sub-Spec -->

# F11: Konfidenz-Output (Sub-Spec für Workflow 2)

## Approval

- [ ] Approved

## Purpose

Output-Schicht für die in Workflow 1 implementierten Konfidenz-Daten: SMS-Symbol pro Tag (`+`/`~`/`?`), neue E-Mail-Spalte „Sicherheit" (automatisch via MetricCatalog), Klartext-Hinweis im E-Mail-Body bei unsicherer Prognose in T+0-72h.

**Verhältnis zur Master-Spec:** Diese Sub-Spec referenziert `docs/specs/modules/forecast_confidence.md` v1.0 und füllt die ACs **AC-9 bis AC-14** mit konkreten Implementierungsdetails. Backend-ACs (AC-1 bis AC-8) sind in Workflow 1 erfüllt und auf Production deployed (Commit `35c9190`).

## Source

- **Änderung:** `src/output/tokens/dto.py` — `DailyForecast` (Z. 20+): neues Optional-Feld `confidence_pct_min`
- **Änderung:** `src/formatters/sms_trip.py` (Z. 79+) — `confidence_pct_min` aus `SegmentWeatherSummary` aggregieren und an `DailyForecast` übergeben
- **Änderung:** `src/output/tokens/builder.py` (Z. 31–47, 127+) — `PRIORITY["C"]`, `POSITIONAL`-Eintrag, neue Token-Loop für C
- **Änderung:** `src/app/metric_catalog.py` (nach Z. 157, neben `pop_pct`) — neue `MetricDefinition(id="confidence", ...)`
- **Änderung:** `src/output/renderers/email/html.py` (nach Z. 221, vor `changes_html`-Block) — Klartext-Hinweis-Block
- **Änderung:** `src/output/renderers/email/plain.py` (analog ~Z. 170–180) — Klartext-Hinweis Plain-Variante
- **Änderung:** `docs/reference/sms_format.md` v2.0 → v2.1 — Token-Position, Symbol-Reservierung
- **Änderung:** `docs/reference/renderer_email_spec.md` — Spalte „Sicherheit" + Hinweis-Regel dokumentieren

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ForecastDataPoint.confidence_pct` | DTO-Feld (Workflow 1) | Quelle für E-Mail-Spalte (per-Stunde) |
| `SegmentWeatherSummary.confidence_pct_min` | DTO-Feld (Workflow 1) | Quelle für SMS-Token (per-Tag) |
| `MetricCatalog` | Registry | Zentrale Spalten-Definition |
| `dp_to_row()` | Function | Konsumiert `dp.confidence_pct` automatisch via MetricCatalog |
| `visible_cols()` | Function | Zieht Header automatisch aus MetricDefinition |
| `Token` + `TokenLine` | DTO | Output für SMS |
| `TestRealGmailE2E` Pattern | Test-Helper | E2E-Roundtrip via Gmail SMTP/IMAP |

## Implementation Details

### 1) `DailyForecast` DTO erweitern

In `src/output/tokens/dto.py` (`DailyForecast` Z. 20+):

```python
@dataclass(frozen=True)
class DailyForecast:
    # ... bestehende Felder ...
    confidence_pct_min: Optional[int] = None  # Issue #121: worst-case confidence
```

### 2) SMS-Adapter erweitern (`src/formatters/sms_trip.py`)

In der `segments_to_normalized_forecast()`-Funktion (Z. 79+): vor der `DailyForecast`-Konstruktion `confidence_pct_min` aus den Segmenten aggregieren:

```python
confidences = [s.aggregated.confidence_pct_min for s in segments
               if s.aggregated.confidence_pct_min is not None]
day_confidence = min(confidences) if confidences else None

today = DailyForecast(
    # ... bestehende Felder ...
    confidence_pct_min=day_confidence,
)
```

Worst-case-Aggregation analog zum Backend-Pattern.

### 3) Token-Builder Symbol-Logik

Symbol-Berechnung als reine Funktion in `src/output/tokens/builder.py`:

```python
def _confidence_symbol(pct: Optional[int]) -> Optional[str]:
    if pct is None:
        return None
    if pct >= 75:
        return "+"
    if pct >= 50:
        return "~"
    return "?"
```

**PRIORITY-Erweiterung** (Z. 31–35):

```python
PRIORITY = {
    "DBG": 1, "WC": 2, ...,
    "C": 4,  # confidence — niedriger als TH/HR/Vigilance, höher als PR/D/N
    ...
}
```

**POSITIONAL-Erweiterung** (Z. 38–47): neuer Eintrag nach `TH+:`:

```python
POSITIONAL = [
    ...,
    ("TH+:", "forecast"),
    ("C", "forecast"),  # NEU
    ("HR:", "vigilance"),
    ...,
]
```

**Builder-Loop** (in `build_token_line()`, nach Z. 179): neuer Block nach dem TH+:-Token-Aufbau:

```python
symbol = _confidence_symbol(today.confidence_pct_min)
if symbol is not None:
    spec = by_sym.get("C")
    if _visible(spec, report_type):
        tokens.append(Token(
            symbol="C",
            value=symbol,
            category="forecast",
            priority=PRIORITY.get("C", 4),
        ))
```

### 4) MetricCatalog-Eintrag (`src/app/metric_catalog.py`)

Nach Z. 157 (neben `pop_pct`-Definition) neue Definition:

```python
MetricDefinition(
    id="confidence",
    label_de="Sicherheit",
    unit="%",
    dp_field="confidence_pct",
    category="atmosphere",
    default_aggregations=("min",),
    compact_label="Conf",
    col_key="confidence",
    col_label="Sicherheit",
    providers={"openmeteo": True, "geosphere": False, "met_norway": False},
    summary_fields={"min": "confidence_pct_min"},
    default_enabled=True,
),
```

→ `dp_to_row()` befüllt automatisch `row["confidence"] = dp.confidence_pct` für jede Stunde. `visible_cols()` zieht Header automatisch.

### 5) Klartext-Hinweis E-Mail-Body

Neue Helper-Funktion in `src/output/renderers/email/helpers.py`:

```python
def build_confidence_hint(
    segments: list["SegmentWeatherData"],
    *, now: datetime, tz: ZoneInfo,
) -> Optional[str]:
    """
    Returns a plain-text hint string if confidence_pct < 60 for any hour
    in T+0-72h, else None.
    
    Example: "Bis morgen ist die Prognose verlässlich. Ab Mittwoch nimmt
              die Unsicherheit zu (Temperatur-Spreizung 8 °C)."
    """
    cutoff = now + timedelta(hours=72)
    uncertain_days: dict[date, tuple[int, float]] = {}  # day → (min_conf, max_spread)
    for seg in segments:
        if seg.timeseries is None:
            continue
        for dp in seg.timeseries.data:
            if dp.ts > cutoff or dp.confidence_pct is None:
                continue
            if dp.confidence_pct >= 60:
                continue
            day = dp.ts.astimezone(tz).date()
            existing = uncertain_days.get(day)
            spread = dp.spread_t2m_k or 0.0
            if existing is None or dp.confidence_pct < existing[0]:
                uncertain_days[day] = (dp.confidence_pct, max(spread, existing[1] if existing else 0.0))
    if not uncertain_days:
        return None
    first_day = min(uncertain_days.keys())
    _, max_spread = uncertain_days[first_day]
    weekday = _format_weekday_de(first_day)  # "Mittwoch"
    return (
        f"Ab {weekday} nimmt die Unsicherheit zu "
        f"(Temperatur-Spreizung {max_spread:.0f} °C)."
    )
```

**HTML-Integration** (`html.py`, nach Z. 221, vor `changes_html`):

```python
confidence_hint = build_confidence_hint(segment_weather, now=now, tz=tz)
if confidence_hint:
    confidence_hint_html = f'<p class="confidence-hint">{html.escape(confidence_hint)}</p>'
else:
    confidence_hint_html = ""
```

Einbinden im HTML-Template zwischen `summary_html` und `changes_html`.

**Plain-Integration** (`plain.py`, analoge Position): direkter Text-Append mit Leerzeile davor/dahinter.

### 6) sms_format.md v2.0 → v2.1

Neuer Abschnitt zwischen Vigilance- und Wintersport-Tokens:

```markdown
### Confidence-Symbol (C)

Position: Nach `TH+:`, vor `HR:`/Vigilance-Tokens.

Symbol-Mapping (1 Zeichen):
- `+` — confidence_pct_min ≥ 75 (sicher)
- `~` — 50 ≤ confidence_pct_min < 75 (mittel)
- `?` — confidence_pct_min < 50 (unsicher)

Wird nur ausgegeben wenn confidence_pct_min ≠ None. 
GSM-7-konform (alle drei Zeichen sind Standard-GSM-7).

Beispiel: `Mo: 18-22° 0mm +`
```

Version-Bump im Frontmatter auf 2.1.

### 7) renderer_email_spec.md

Spalte „Sicherheit" in der Tabellen-Spalten-Reihenfolge dokumentieren (am Ende, nach Wind/Niederschlag, vor Symbol-Spalten). Hinweis-Regel: „Klartext-Hinweis im Body wenn `confidence_pct < 60` für eine Stunde in T+0-72h, andernfalls kein Hinweis (Visual-Noise-Vermeidung)."

## Acceptance Criteria

Die folgenden ACs sind aus der Master-Spec übernommen und für diesen Workflow detailliert.

- **AC-9:** Given ein `DailyForecast` mit `confidence_pct_min=80` / When der Token-Builder läuft / Then enthält die SMS-Token-Liste einen Token `(symbol="C", value="+")`. Bei `confidence_pct_min=60` → `"~"`. Bei `confidence_pct_min=35` → `"?"`. Bei `confidence_pct_min=None` → kein C-Token in der Liste
  - Test: (populated after /tdd-red)

- **AC-10:** Given ein 7-Tage-Trip mit C-Tokens für jeden Tag / When `render()` mit `max_length=160` ausgeführt wird / Then bleibt die finale SMS-Länge ≤ 160 Zeichen, Tokens werden bei Bedarf nach `PRIORITY` getrunkt (C bleibt erhalten solange Platz ist)
  - Test: (populated after /tdd-red)

- **AC-11:** Given ein E-Mail-Report mit `dc.metrics`-Eintrag für `confidence` / When `dp_to_row()` über stündliche Datenpunkte mit `dp.confidence_pct=85` läuft / Then enthält jede Row `row["confidence"] == 85`, und `visible_cols()` liefert einen Eintrag `("confidence", "Sicherheit")`
  - Test: (populated after /tdd-red)

- **AC-12:** Given ein 5-Tage-Trip mit `confidence_pct=45` an einer Stunde in T+48h (Mittwoch) und `confidence_pct ≥ 80` für alle anderen Stunden in T+0-72h / When `build_confidence_hint()` läuft / Then liefert sie einen String der den Wochentag „Mittwoch" und eine Spread-Angabe mit `°C` enthält
  - Test: (populated after /tdd-red)

- **AC-13:** Given ein Trip mit `confidence_pct ≥ 60` für **alle** Stunden in T+0-72h / When `build_confidence_hint()` läuft / Then liefert sie `None` (Visual-Noise-Vermeidung, kein Hinweis im E-Mail-Body)
  - Test: (populated after /tdd-red)

- **AC-14:** Given ein echtes Gmail-E2E-Setup (`TestRealGmailE2E`) und ein Trip mit gemischten Konfidenz-Werten / When `format_email()` ausgeführt und die Mail via SMTP gesendet wird / Then bestätigt der IMAP-Roundtrip den Empfang, das HTML enthält den Spalten-Header `Sicherheit` und (bei niedriger Konfidenz) den Klartext-Hinweis-Text. Der Test darf NICHT mocken (echtes Gmail + IMAP)
  - Test: (populated after /tdd-red)

## Expected Behavior

- **Input:**
  - `list[SegmentWeatherData]` mit befüllten `aggregated.confidence_pct_min` und `timeseries.data[*].confidence_pct` (aus Workflow 1)
- **Output:**
  - SMS: `Stage: N16 D22 R0.0 W12 G18 +` (für sicheren Tag) oder `Stage: N16 D22 R0.5 W12 G18 ?` (für unsicheren Tag)
  - HTML-E-Mail: Tabelle mit zusätzlicher Spalte „Sicherheit", Werte in `%`
  - Plain-E-Mail: gleiche Spalte, gleicher Hinweis im Body bei niedriger Konfidenz
  - Body-Hinweis (nur bei `confidence_pct < 60` in T+0-72h): „Ab Mittwoch nimmt die Unsicherheit zu (Temperatur-Spreizung 8 °C)."
- **Side effects:** Keine. Reine Output-Schicht.

## Known Limitations

- **CLI-Pfad (`trip_result.py`)** bleibt ohne Konfidenz-Anzeige (führt über `AggregatedSummary`, das `confidence` nicht trägt). CLI ist nicht produktiv für E-Mail/SMS — separater Workflow falls CLI-Anzeige gewünscht.
- **Tagesweise Aggregation für SMS** nutzt `min` über alle Segmente. Ein Trip mit nur einer unsicheren Stunde am Morgen wird für den ganzen Tag als `?` gemeldet.
- **Wochentags-Hinweis nur auf Deutsch** — `_format_weekday_de()` produziert „Montag", „Dienstag", ... Internationalisierung (z.B. „Wednesday") nicht in diesem Workflow.
- **Klartext-Hinweis-Schwelle 60 %** ist fix — keine konfigurierbare Schwelle pro Trip. Begründung: gleiche Schwelle für alle Reports vereinfacht UX und User-Erwartung.
- **`email_spec_validator.py` Spalten-Check** prüft aktuell nicht auf Spalten-Anzahl. Falls in Zukunft ein „Sicherheit"-Pflicht-Check gewünscht: separates Issue.

## Changelog

- 2026-05-15: Initial Sub-Spec für Workflow 2 (Output) erstellt, parent `forecast_confidence` (Master-Spec)
