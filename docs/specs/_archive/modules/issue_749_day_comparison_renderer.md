---
entity_id: issue_749_day_comparison_renderer
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [renderer, email, html, plain-text, vortag-vergleich, day-comparison]
---

# DayComparison-Renderer — Vortag-Vergleich-Sektion (HTML + Plain-Text)

## Approval

- [ ] Approved

## Purpose

Zwei neue Pure Functions `render_day_comparison_html` und `render_day_comparison_plain` wandeln ein `DayComparison`-DTO in eine kompakte Delta-Sektion um, die in bestehende E-Mail-Renderer (HTML und Plain-Text) eingebettet wird. Sie erzeugen eine konsistente "Vortag-Vergleich"-Sektion mit farblicher Richtungscodierung (BETTER/WORSE/EQUAL), lassen MISSING-Metriken vollständig weg und geben einen leeren String zurück wenn kein Vergleich vorliegt.

## Source

- **File:** `src/output/renderers/email/html.py` (MODIFY — neue Funktion `render_day_comparison_html`)
- **File:** `src/output/renderers/email/plain.py` (MODIFY — neue Funktion `render_day_comparison_plain`)
- **Identifier:** `render_day_comparison_html`, `render_day_comparison_plain`

## Estimated Scope

- **LoC:** ~100
- **Files:** 3 (html.py, plain.py, test)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/day_comparison.py` | Internal module | Liefert `DayComparison`, `DayComparisonEntry`, `MetricDelta`, `ComparisonDirection` (Issue #748) |
| `src/output/renderers/email/design_tokens.py` | Internal module | Farb-Tokens `G_SUCCESS`, `G_DANGER`, `G_INK_MUTED` für Richtungscodierung |

## Implementation Details

### Funktions-Signaturen

```python
from typing import Optional
from src.services.day_comparison import DayComparison

def render_day_comparison_html(comparison: Optional[DayComparison]) -> str:
    """Gibt '' zurück wenn comparison is None."""
    ...

def render_day_comparison_plain(comparison: Optional[DayComparison]) -> str:
    """Gibt '' zurück wenn comparison is None."""
    ...
```

### None-Guard

Beide Funktionen prüfen als erstes `if comparison is None: return ""`. Kein leerer
Block, kein Platzhalter wird ausgegeben.

### Metrik-Mapping

6 anzuzeigende Metriken je `DayComparisonEntry` (in dieser Reihenfolge):

| Feld | Label | Einheit | Richtungs-Pfeil |
|------|-------|---------|-----------------|
| `temp_min` + `temp_max` kombiniert | "Temperatur" | °C | Kein Pfeil (immer EQUAL) — zeigt nur `+2°/+4°C` |
| `precip_sum` | "Niederschlag" | mm | Pfeil |
| `wind_max` | "Wind" | km/h | Pfeil |
| `gust_max` | "Böen" | km/h | Pfeil |
| `thunder` | "Gewitter" | Stufen | Ordinal-Text |

**MISSING-Zeilen:** Wenn `direction == MISSING` für eine Metrik → Zeile komplett
weglassen. Kein "–"-Platzhalter.

### Richtungscodierung

| Direction | HTML-Farbe | HTML-Zeichen | Plain-Text |
|-----------|-----------|--------------|------------|
| BETTER | `G_SUCCESS = '#3a7d44'` | `▲` (grün) | `▲` |
| WORSE | `G_DANGER = '#b33a2a'` | `▼` (rot) | `▼` |
| EQUAL | `G_INK_MUTED = '#5c5a52'` | kein Pfeil | kein Pfeil |
| MISSING | — | Zeile weglassen | Zeile weglassen |

**Temperatur-Sonderfall:** `direction` ist immer EQUAL (laut Service-Spec), daher
kein Pfeil. Format: `+{temp_min.delta}°/{+temp_max.delta}°C` mit Vorzeichen.

**Gewitter-Sonderfall:** `delta` ist Ordinal-Integer (−2 bis +2).
- `delta == 0` → `"unverändert"`
- `delta < 0` → `"−N Stufen"` (BETTER, grün)
- `delta > 0` → `"+N Stufen"` (WORSE, rot)

### HTML-Struktur

Kompakte Tabelle im `daily_summary_html`-Stil:
- Section-Eyebrow: `"Vortag-Vergleich"` (gleiche CSS-Klasse wie bestehende Sektionen)
- Farbiger Wert-Text per Inline-Style `color: {farbe}`
- Kein separater Pfeil-Spalte — Pfeil steht vor dem Wert-String

### Plain-Text-Struktur

```
━━ Vortag-Vergleich ━━
  Niederschlag: ▲ −3.0 mm
  Wind:         ▼ +8 km/h
  Temperatur:   +2°/+4°C
```

Einrückung 2 Leerzeichen. Labels linksbündig, Werte durch Leerzeichen getrennt.

### Multi-Segment-Verhalten

- 1 Eintrag → kein Segment-Header
- Mehr als 1 Eintrag → vor jeder Gruppe `"Segment {n}:"` (HTML: `<b>`, Plain: eigene Zeile)

## Expected Behavior

- **Input:** `Optional[DayComparison]` mit 0 bis N Segmenten
- **Output:** Fertig gerenderte HTML- oder Plain-Text-Zeichenkette; `""` wenn `comparison is None`
- **Side effects:** Keine — beide Funktionen sind pure (kein State, kein I/O)

## Acceptance Criteria

**AC-1:** Given ein `DayComparison`-Objekt mit einem `DayComparisonEntry` (precip_sum delta=−3.0, BETTER) / When `render_day_comparison_html(comparison)` aufgerufen / Then enthält die Ausgabe den Wert "−3.0" sowie die Farbe `#3a7d44` (G_SUCCESS).

**AC-2:** Given `render_day_comparison_html(None)` / When aufgerufen / Then ist der Rückgabewert exakt `""` (leerer String, kein Whitespace, kein HTML-Block).

**AC-3:** Given ein `DayComparisonEntry` bei dem `precip_sum.direction == MISSING` / When `render_day_comparison_html(comparison)` aufgerufen / Then enthält die Ausgabe keine "Niederschlag"-Zeile und keinen "–"-Platzhalter.

**AC-4:** Given ein `DayComparisonEntry` mit `wind_max.direction == WORSE` (delta=+8) / When `render_day_comparison_html(comparison)` aufgerufen / Then enthält die Ausgabe die Farbe `#b33a2a` (G_DANGER) und das Zeichen `▼`.

**AC-5:** Given ein `DayComparison`-Objekt mit einem Eintrag / When `render_day_comparison_plain(comparison)` aufgerufen / Then enthält die Ausgabe dieselben Delta-Werte wie die HTML-Variante, jedoch kein HTML-Tag.

**AC-6:** Given BETTER/WORSE-Metriken im Renderer / When die verwendeten Farb-Tokens geprüft / Then sind `G_SUCCESS = '#3a7d44'` und `G_DANGER = '#b33a2a'` aus `design_tokens.py` die einzigen Quellen (keine helleren Varianten, WCAG-AA-Konform).

**AC-7:** Given ein echter `DayComparison`-Instanz (kein Mock) / When der Test `render_day_comparison_html` und `render_day_comparison_plain` aufruft / Then laufen beide Tests grün ohne `Mock()`, `patch()` oder `MagicMock`.

## Known Limitations

- Absolutwerte (Heute-Werte) sind nicht zugänglich — Funktionen erhalten nur `DayComparison` mit Deltas.
- Formatierung von `delta` als Integer vs. Float folgt dem Typ in `MetricDelta.delta`; kein explizites Runden.
- Temperatur-Kombinationsdarstellung (`+2°/+4°C`) setzt voraus, dass `temp_min` und `temp_max` beide nicht MISSING sind; ist eines MISSING, wird die Temperaturzeile weggelassen.

## Changelog

- v1.0 (2026-06-11): Initial spec, Issue #749
