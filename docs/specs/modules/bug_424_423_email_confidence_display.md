---
entity_id: bug_424_423_email_confidence_display
type: bugfix
created: 2026-05-29
updated: 2026-05-29
status: draft
version: "1.0"
tags: [email, metric_catalog, confidence, bugfix, ux]
---

# Bug #424 + #423 — E-Mail: Spalte „Sicherheit" entfernen und Hinweis-Text vereinfachen

## Approval

- [ ] Approved

## Purpose

Zwei zusammengehörige Darstellungsfehler im E-Mail-Report, die aus Feature #121 (Prognose-Konfidenz, deployed 2026-05-15) stammen: Die Spalte „Sicherheit" erscheint ungefragt in allen E-Mail-Tabellen, weil `"confidence"` in allen 7 WeatherTemplates eingetragen ist — der Wanderer sieht eine Prozentzahl ohne Kontext und kann damit nichts anfangen. Der Unsicherheits-Hinweis-Text enthält zusätzlich eine technische Klammer „(Temperatur-Spreizung X °C)", die auf Ensemble-Standardabweichung verweist und für Laien nicht handelbar ist. Beide Fixes machen den Confidence-Block für Wanderer wieder lesbar, ohne die zugrundeliegende Konfidenz-Logik zu verändern.

## Source

- **Datei 1:** `src/app/metric_catalog.py` (Zeilen 397–456, `WEATHER_TEMPLATES`-Dict)
- **Datei 2:** `src/output/renderers/email/helpers.py` (Zeilen 301–304, `build_confidence_hint()`)
- **Datei 3:** `tests/tdd/test_forecast_confidence_output.py` (Zeile 245, AC-12-Assertion)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WEATHER_TEMPLATES` dict in `src/app/metric_catalog.py` | Daten | Steuert welche Metriken pro Aktivitätstyp in die E-Mail-Tabelle aufgenommen werden |
| `MetricDefinition(id="confidence")` in `src/app/metric_catalog.py` | Daten | Bleibt erhalten (default_enabled=False); nur die Template-Einträge werden entfernt |
| `dp_to_row()` in `src/output/renderers/email/helpers.py` | Funktion | Liest `mc.enabled=True`-Metriken aus der WeatherDisplayConfig; liefert Tabellenzeilen |
| `visible_cols()` in `src/output/renderers/email/helpers.py:194` | Funktion | Aggregiert sichtbare Spalten aus allen Zeilen; bestimmt den Tabellen-Header |
| `build_confidence_hint()` in `src/output/renderers/email/helpers.py:253` | Funktion | Erzeugt deutschen Hinweis-Text wenn confidence_pct < 60 in T+0–72h |
| `test_forecast_confidence_output.py::TestConfidenceHint` | Test | AC-12 prüft derzeit auf `"°C"` im Hinweis-Text — muss angepasst werden |

## Implementation Details

### Fix 1 — `"confidence"` aus allen 7 WeatherTemplates entfernen

In `src/app/metric_catalog.py` im Dict `WEATHER_TEMPLATES` das Listenelement `"confidence"` aus jedem der 7 Templates entfernen:

| Template-Key | Zeile (aktuell) | Aktion |
|---|---|---|
| `"alpen-trekking"` | 404 | `"confidence"` aus `metrics`-Liste entfernen |
| `"wandern"` | 411 | `"confidence"` aus `metrics`-Liste entfernen |
| `"skitouren"` | 421 | `"confidence"` aus `metrics`-Liste entfernen |
| `"wintersport"` | 429 | `"confidence"` aus `metrics`-Liste entfernen |
| `"radtour"` | 437 | `"confidence"` aus `metrics`-Liste entfernen |
| `"wassersport"` | 445 | `"confidence"` aus `metrics`-Liste entfernen |
| `"allgemein"` | 453 | `"confidence"` aus `metrics`-Liste entfernen |

Die `MetricDefinition`-Zeile mit `id="confidence"` im oberen Teil der Datei bleibt vollständig erhalten (nur die Template-Verweise werden entfernt).

### Fix 2 — Hinweis-Text in `build_confidence_hint()` vereinfachen

In `src/output/renderers/email/helpers.py` das `return`-Statement am Ende von `build_confidence_hint()` (aktuell Zeilen 301–303) wie folgt ersetzen:

```python
# ALT:
return (
    f"Ab {weekday} nimmt die Unsicherheit zu "
    f"(Temperatur-Spreizung {round(max_spread)} °C)."
)

# NEU:
return f"Ab {weekday} ist die Vorhersage weniger verlässlich."
```

Die Variable `max_spread` und die Berechnungslogik darüber können aus der Funktion entfernt werden, da sie nur für den Klammer-Text benötigt wurde. Die Felder `spread_t2m_k` auf den Datenpunkten bleiben unverändert im Datenmodell.

### Fix 3 — AC-12-Test-Assertion anpassen

In `tests/tdd/test_forecast_confidence_output.py` Zeile 245 die Assertion auf `"°C"` entfernen und durch eine Assertion auf den neuen Text ersetzen:

```python
# ALT (Zeile 244–245):
assert "Mittwoch" in hint, f"Hint must mention 'Mittwoch': {hint}"
assert "°C" in hint, f"Hint must mention spread in °C: {hint}"

# NEU:
assert "Mittwoch" in hint, f"Hint must mention 'Mittwoch': {hint}"
assert "weniger verlässlich" in hint, f"Hint must say 'weniger verlässlich': {hint}"
```

## Expected Behavior

- **Input (Fix 1):** E-Mail-Rendering für beliebigen Trip mit beliebigem WeatherTemplate
- **Output (Fix 1):** Die generierte HTML-Tabelle enthält keine Spalte mit Header „Sicherheit" oder Prozentwerten aus der Confidence-Metrik
- **Input (Fix 2):** `build_confidence_hint(segments, now=..., tz=...)` mit mindestens einem Datenpunkt mit `confidence_pct < 60` in T+0–72h
- **Output (Fix 2):** String der Form `"Ab {Wochentag} ist die Vorhersage weniger verlässlich."` — ohne Klammer, ohne Zahlenwert
- **Side effects:** SMS-Token C (`+`/`~`/`?`) bleibt unverändert. Der Trigger-Schwellenwert (confidence_pct < 60) bleibt unverändert. `MetricDefinition(id="confidence")` bleibt im Katalog erhalten.

## Acceptance Criteria

**AC-1:** Given eine E-Mail für eine Tour mit WeatherTemplate „wandern" / When der HTML-Report gerendert wird / Then erscheint keine Spalte „Sicherheit" in der Tabelle
- Test: `tests/tdd/test_bug_424_423_confidence_display.py::TestNoConfidenceInWandernTemplate`

**AC-2:** Given eine E-Mail für eine Tour mit WeatherTemplate „alpen-trekking" / When der HTML-Report gerendert wird / Then erscheint keine Spalte „Sicherheit" in der Tabelle
- Test: `tests/tdd/test_bug_424_423_confidence_display.py::TestNoConfidenceInAlpenTrekkingTemplate`

**AC-3:** Given `build_confidence_hint()` mit einem Datenpunkt mit `confidence_pct=45` an T+48h (Mittwoch) / When der Hint-Text generiert wird / Then enthält er „Mittwoch" und „weniger verlässlich", aber keine Klammer mit °C
- Test: `tests/tdd/test_forecast_confidence_output.py::TestConfidenceHint::test_low_confidence_day_in_window` (angepasste Assertion)

**AC-4:** Given `build_confidence_hint()` mit allen `confidence_pct >= 60` in T+0–72h / When der Hint-Text generiert wird / Then gibt die Funktion `None` zurück (kein visuelles Rauschen)
- Test: `tests/tdd/test_forecast_confidence_output.py::TestConfidenceHint::test_high_confidence_in_72h_window_no_hint` (bleibt unverändert)

## Known Limitations

- Die `spread_t2m_k`-Berechnungslogik in `build_confidence_hint()` kann nach Fix 2 entfernt werden. Falls zukünftig ein anderer Kanal (z.B. ein Debug-Endpoint) den Spread-Wert benötigt, muss er aus dem Datenmodell (`ForecastDataPoint.spread_t2m_k`) direkt lesen.
- Für alle 7 Templates wird `"confidence"` entfernt. Sollte künftig ein neues Template hinzukommen, darf `"confidence"` dort ebenfalls nicht eingetragen werden, solange kein wanderergerechter Darstellungskontext definiert ist.

## Changelog

- 2026-05-29: Initial spec created (Bug #424 + #423, entstammen Feature #121 deployed 2026-05-15)
