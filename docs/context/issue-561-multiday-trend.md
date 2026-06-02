# Context: Issue #561 — F3 Multi-Day Trend (3-Tage-Vorschau im Abendbericht)

## Request Summary

Der Abendbericht soll am Ende eine kompakte Trend-Tabelle zeigen: bis zu 3 Folge-Etappen mit Datum (Wochentag), Temperatur-Max, Niederschlags-Summe, Wind-Max und Gewitter-Level.

## Wichtigste Vorab-Erkenntnis: Feature bereits implementiert (v3.0)

Die `multi_day_trend`-Funktion existiert bereits vollständig in der Codebase:

- **Spec:** `docs/specs/modules/multi_day_trend.md` → `status: implemented`, v3.0 (2026-02-18)
- **Implementierung:** `src/services/trip_report_scheduler.py:953` → `_build_stage_trend()`
- **Rendering (HTML):** `src/formatters/trip_report.py:962-984`
- **Rendering (Plain-Text):** `src/formatters/trip_report.py:1084-1170`
- **Tests:** `tests/integration/test_multi_day_trend.py` (21 Tests, alle `@pytest.mark.live`)
- **GR221-Trip konfiguriert:** `data/users/default/trips/gr221-mallorca.json` → `report_config.multi_day_trend_reports: ['morning', 'evening']`

## Gap-Analyse: Issue AC vs. bestehende Implementierung

| AC | Issue #561 fordert | Aktuelle Implementierung | Status |
|----|-------------------|--------------------------|--------|
| AC-1 | bis zu 3 Folge-Etappen | ALLE Folge-Etappen (kein Limit) | **LÜCKE: kein max=3** |
| AC-2 | Wochentag + Temp-Max + Niederschlag + Wind-Max + Gewitter | CompactSummary-String (enthält alle Werte, aber als Fließtext) | Abweichung im Format |
| AC-3 | Kein Block wenn letzte Etappe morgen | `get_future_stages(target_date)` → leer → kein Block | ✓ erfüllt |
| AC-4 | Echte API-Calls | echte API-Calls in `_build_stage_trend` | ✓ erfüllt |

## Konkrete Gaps

### Gap 1: Kein 3-Etappen-Limit (critical)

`_build_stage_trend()` iteriiert über ALLE `get_future_stages()` ohne Begrenzung:
```python
# src/services/trip_report_scheduler.py:977-983
future_stages = trip.get_future_stages(target_date)
trend = []
for stage in future_stages:  # kein [:3]!
    ...
```

Issue verlangt: max 3, konfigurierbar. Aktuell: unbegrenzt.

### Gap 2: Format (summary string vs. Spalten)

Issue-Vorschlag zeigt Spaltenformat:
```
Tag 2 (Do) | ⛅ 16°C | 🌧 8mm | 💨 25 km/h | ⚡ NONE
```

v3.0 implementiert das 2-Zeilen-Summary-Format:
```
  Mi  Soller → Tossals Verds
      6–14°C, ⛅, trocken bis 13:00 dann 1.5mm, 25 km/h NW
```

Das Summary-Format ist informativer (Min-Max statt nur Max, Regen-Timing), aber es ist eine Formatdivergenz. Phase 3 muss klären, welches Format der PO will.

### Gap 3: Kein konfiguriertes Max in Models

`TripReportConfig` hat kein `max_trend_stages`-Feld. Issue sagt "konfigurierbar, Default 3".

## Related Files

| File | Relevanz |
|------|---------|
| `src/services/trip_report_scheduler.py:953` | `_build_stage_trend()` — Haupt-Implementierung |
| `src/services/trip_report_scheduler.py:386` | Trigger-Logik (wenn wird Trend gebaut?) |
| `src/app/trip.py:226` | `get_future_stages(from_date)` — gibt Etappen > from_date zurück |
| `src/app/models.py:679` | `TripReportConfig` — kein max_trend_stages-Feld vorhanden |
| `src/formatters/trip_report.py:962` | HTML-Rendering Trend-Abschnitt |
| `src/formatters/trip_report.py:1084` | Plain-Text-Rendering Trend-Abschnitt |
| `src/output/renderers/email/html.py:382` | Renderer HTML für multi_day_trend |
| `src/output/renderers/email/plain.py:228` | Renderer Plain-Text für multi_day_trend |
| `docs/specs/modules/multi_day_trend.md` | Bestehende Spec v3.0 |
| `tests/integration/test_multi_day_trend.py` | Tests (alle `@live`) |
| `data/users/default/trips/gr221-mallorca.json` | Trip mit Trend konfiguriert |

## Existing Patterns

- `get_future_stages(date)` → `s.date > date` (strict greater than)
- Für evening report: `target_date = today + 1` → Trend zeigt Etappen ab übermorgen
- CompactSummaryFormatter wiederverwendet für Trend (DRY, v3.0 Feature)
- `multi_day_trend_reports` auf Trip-Ebene steuert in welchen Berichten Trend erscheint

## Dependencies

- **Upstream:** `get_future_stages()` → `CompactSummaryFormatter.format_stage_summary()` → `aggregate_stage()` → OpenMeteo API
- **Downstream:** `TripReportFormatter.format_email()` → Email-Renderer HTML+Plain

## Risks & Considerations

1. **Format-Entscheidung ist Kern-Frage:** Issue will Spalten (v2.0-Stil), Spec v3.0 hat Summary-String als bewusste Verbesserung. PO muss entscheiden.
2. **Tests sind alle @live:** Kein Regressions-Schutz ohne echte API. Wenn wir das Limit hinzufügen, müssen wir offline-fähige Tests schreiben.
3. **Feature könnte schon funktionieren:** Wenn Staging-Trip korrekte Etappen-Daten hat, erscheint der Trend. Verifizierung ausstehend.
4. **API-Kosten:** Pro Folge-Etappe werden alle Wegpunkte der Etappe per API abgerufen. Limit=3 reduziert Calls.
