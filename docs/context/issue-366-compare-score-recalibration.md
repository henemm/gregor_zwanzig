# Context: issue-366-compare-score-recalibration

## Request Summary
Nach dem Sonnenstunden-Fix #347 (deployed `0b4c90a`) liefert `calculate_sunny_hours()`
erstmals realistische, gebrochene Werte statt de-facto konstant `0`. Die hartcodierten
Sonnenstunden-Schwellen im Compare-Scoring (`src/services/comparison_scoring.py`) wurden
gegen den kaputten `0`-Wert kalibriert und müssen gegen reale Verteilungen neu justiert werden.

## Kritische Architektur-Erkenntnis: ZWEI Compare-Engines

Es gibt zwei getrennte, nutzerseitige Compare-Pfade — nur **einer** ist von #366 betroffen:

| Pfad | Engine | Sonnen-Metrik | Von #347/#366 betroffen? |
|------|--------|---------------|--------------------------|
| **Frontend-Compare-Screen** (interaktiv, `/compare`) | **Go** `/api/compare/run` (`internal/compare/scoring.go`, `engine.go`) | `DniAvgWm2` (W/m², relative Normalisierung best=100/worst=0) | **NEIN** — nutzt kein `sunny_hours`, keine absoluten Schwellen |
| **Compare-E-Mail-Abos** (Scheduler, Feature #253) | **Python** `comparison_scoring.calculate_score()` | `sunny_hours` (absolute h-Schwellen) | **JA** — genau hier wirkt #347 und greift #366 |

→ **#366 betrifft ausschließlich die Python-Engine der Compare-E-Mail-Abos.** Der interaktive
Frontend-Vergleich bleibt unberührt (eigene Go-Logik, relative DNI-Normalisierung).

## Konsumkette der Python-Engine (NICHT tot!)
```
comparison_scoring.calculate_score()   ← Schwellen sitzen hier
  ↑ importiert von
comparison_engine.py  (Zeile 19, Aufruf Zeile 176 + 445)
  ↑ importiert von
compare_subscription.py  +  api/routers/compare.py (Legacy GET /api/compare)
  ↑ run_comparison_for_subscription() aufgerufen von
api/routers/scheduler.py  → versendet reale Compare-Abo-Mails an Nutzer
```

## Related Files
| Datei | Relevanz |
|------|-----------|
| `src/services/comparison_scoring.py` | **Kern von #366** — alle sunny_hours-Schwellen pro Profil |
| `src/services/comparison_engine.py` | Baut `metrics`-Dict, ruft `calculate_sunny_hours` (Z. 144) + `calculate_score` (Z. 176) |
| `src/services/weather_metrics.py` | `calculate_sunny_hours()` (Z. 266) + `dni_to_sunny_fraction()` (Z. 246) nach #347 |
| `src/services/compare_subscription.py` | Setzt `time_window`/`target_date`/`forecast_hours`, ruft Engine |
| `api/routers/scheduler.py` | Versendet Compare-Abo-Mails (Konsument der Scores) |
| `api/routers/compare.py` | Legacy GET `/api/compare` (vom Frontend NICHT genutzt) |
| `internal/compare/scoring.go` | Go-Engine — **außerhalb #366-Scope**, nur zur Abgrenzung |
| `docs/specs/modules/issue_347_sunshine_hours.md` | Spec des Sonnenstunden-Fixes |
| `docs/specs/modules/sport_aware_comparison.md` | Spec der Scoring-Logik v1.0 |

## Aktuelle Schwellen (IST-Zustand, gegen kaputte `0` kalibriert)
| Profil | sunny_hours-Stufen → Bonus | Zeilen |
|--------|-----------------------------|--------|
| **WINTERSPORT** | ≥6h: +15 / ≥4h: +10 / ≥2h: +5 | 60–66 |
| **WANDERN** | ≥7h: +20 / ≥5h: +12 / ≥3h: +5 | 164–171 |
| **ALLGEMEIN** | ≥6h: +15 / ≥4h: +8 / ≥2h: +4 | 228–235 |

Basis-Score: Wintersport 50, Wandern 50, Allgemein 55. Ergebnis geclamped auf 0–100.

## calculate_sunny_hours nach #347 (Wertebereich)
- **Haupt-Pfad (DNI vorhanden, Open-Meteo):** je Stunde lineare Interpolation über DNI-Band
  (`min=60`, `max=180` W/m², env-konfigurierbar via `GZ_SUNNY_DNI_*`): `dni>=180`→+1.0h,
  `60<dni<180`→anteilig, `dni<=60`→0. Summe über alle Datenpunkte, gerundet auf 1 Dezimale.
- **Fallback (kein DNI, Geosphere):** `(100 - effective_cloud)/100` pro Stunde (proportional, kein Binär-Cutoff).
- **Aggregiert über `filtered_data`** = ein `target_date` + Zeitfenster `start_hour..end_hour`.
- **Max-Wert = Fensterlänge.** Zeitfenster ist **pro Abo konfigurierbar** (`sub.time_window_start/end`),
  also nicht fix → absolute Stundenschwellen sind fensterabhängig.

## Kern-Problem für die Kalibrierung (für Phase 2)
Mit altem `sunny_hours≈0` feuerte **kein** Sonnen-Bonus. Mit realen Werten feuert an jedem
klaren Tag fast immer die **oberste** Stufe (z. B. 7h bei einem 12–14h-Fenster trivial erreicht)
→ die Abstufung (7 vs 5 vs 3) **kollabiert**, kein Differenzierungs-Wert mehr zwischen "gut" und
"sehr sonnig". Schwellen müssen gegen plausible Tageswerte (klarer Tag saison-/breitenabhängig
~8–14h) und gegen das konfigurierbare Zeitfenster neu gestaffelt werden.

## Existing Patterns
- Pure-Function-Scorer pro Profil (`_score_wintersport/_wandern/_allgemein`), additive Boni/Mali,
  finaler Clamp 0–100. Schwellen als Magic Numbers inline — keine zentrale Konstanten-Tabelle.
- Settings env-overridable (`GZ_SUNNY_DNI_MIN/MAX_WM2`) — Präzedenz für konfigurierbare Bänder.

## Dependencies
- **Upstream:** `calculate_sunny_hours` (weather_metrics) liefert den Wert; DNI aus Open-Meteo,
  Cloud-Fallback aus Geosphere. Zeitfenster aus der Abo-Konfiguration.
- **Downstream:** Compare-Abo-Mail-Versand (`scheduler.py`), Legacy `GET /api/compare`.

## Risks & Considerations
- **Keine Mocks:** Kalibrierung gegen reale API-Werte / reale Forecast-Verteilungen, nicht gegen erfundene Zahlen (Projektregel).
- **Fenster-Abhängigkeit:** Absolute h-Schwellen sind nur sinnvoll relativ zur (variablen) Fensterlänge. Option für Phase 2: anteilige Schwellen (z. B. % der Fensterstunden mit Sonne) statt fixer Stunden — Trade-off klären.
- **Daten-Quellen-Asymmetrie:** DNI-Pfad (Open-Meteo) vs. Cloud-Fallback (Geosphere) liefern unterschiedlich skalierte Werte → Schwellen müssen für beide plausibel sein.
- **Engine-Inkonsistenz (out of scope, aber notieren):** Frontend-Compare (Go, relative DNI-Norm) und E-Mail-Compare (Python, absolute Schwellen) bewerten Sonne unterschiedlich. #366 konsolidiert das NICHT — verwandt mit #362 (ScoreToggle). Konsolidierung ggf. als eigenes Folge-Issue.
- **Snapshot-Pflicht:** Kein Persistenz-Schema betroffen (reine Scoring-Konstanten) → kein Daten-Migrations-Risiko.

---

## Analysis (Phase 2)

### Reale Datengrundlage (Open-Meteo, echte DNI, 25.–29. Mai 2026, 4 Alpenorte)
Algorithmus 1:1 aus `dni_to_sunny_fraction` (Band 60/180) gegen echte stündliche DNI gerechnet:

| Ort | Fenster 09–16 (8 h) | Fenster 08–18 (11 h) | Fenster 06–20 (15 h) |
|-----|---------------------|----------------------|----------------------|
| Innsbruck 574 m | 8,0 h (alle Tage) | 11,0 h | 12–14,3 h |
| Stubai 2300 m | 8,0 h | 11,0 h | 14,0–14,5 h |
| Zugspitze 2960 m | 8,0 h | 11,0 h | 13,2–14,2 h |
| Korsika/GR20 1500 m | 8,0 h | 11,0 h | 14,0 h |

**Befund:** An jedem nicht-bedeckten Tag liegt die DNI jeder Mittags-Stunde weit über 180 W/m² (Peak 470–966).
→ `sunny_hours` ≈ **Fensterlänge** (Mittagsfenster komplett gesättigt). Die oberste Bonus-Stufe (Wandern ≥7 h, Wintersport/Allgemein ≥6 h) feuert an **jedem** klaren Tag mit Maximum → **Differenzierung null**.

### Strukturkern
„≥7 h absolut" = 87 % Sonne bei 8-h-Fenster, aber nur 50 % bei 15-h-Fenster. Da das Fenster **pro Abo frei wählbar** ist, sind feste Stundenschwellen prinzipiell fensterabhängig und damit inkonsistent.

### Entscheidung: Ansatz B (anteilige Schwellen) — Tech-Lead-Empfehlung
Sonnen-Bonus über **Sonnen-Anteil am Fenster** (`sunny_hours / window_hours` ∈ [0,1]) statt fixer Stunden.
- **Robust** gegen jede Fensterlänge; Semantik („sehr sonnig") bleibt stabil.
- Geosphere-Fallback ist symmetrisch (gleiche Einheit, gleiche Fensterlänge) → identisch korrekt normiert.
- Verworfen: Ansatz A (feste Stunden hochsetzen) löst nur ein Fenster-Segment; bei kurzem Fenster kollabiert er erneut.

### Kandidaten-Schwellen (Anteil des Fensters) — final in Spec zu fixieren
| Profil | Stufe 1 | Stufe 2 | Stufe 3 | Bonus |
|--------|---------|---------|---------|-------|
| WINTERSPORT | ≥0,70 | ≥0,50 | ≥0,25 | +15/+10/+5 |
| WANDERN | ≥0,70 | ≥0,50 | ≥0,30 | +20/+12/+5 |
| ALLGEMEIN | ≥0,65 | ≥0,45 | ≥0,25 | +15/+8/+4 |

### Signatur-Konsequenz
`calculate_score(metrics, profile, window_hours=None)` — optionaler Parameter, abwärtskompatibel.
- `comparison_engine.py:80` → `window_hours = end_hour - start_hour + 1` (time_window liegt vor), Übergabe bei Aufruf Z. 176.
- `comparison_engine.py:445` (Legacy, ohne Zeitfenster) und `api/routers/compare.py` → `window_hours=None` → alter Absolut-Pfad bleibt unverändert (kein Bruch).

### Scope
| Datei | Änderung | LoC |
|-------|----------|-----|
| `src/services/comparison_scoring.py` | Signatur + 3 Sonnen-Blöcke auf Anteil | ~25 |
| `src/services/comparison_engine.py` | `window_hours` berechnen + übergeben | ~5 |
| `tests/tdd/test_sport_aware_scoring.py` | Tests anpassen + Fenster-Robustheit | ~40–60 |

**3 Dateien, ~70–90 LoC** — unter 250-Grenze. Keine Persistenz-/API-Breaking-Änderung.

### Hinweis Wirkungsbereich (Transparenz, nicht blockierend)
Greift nur in den **Compare-E-Mail-Abos** (Scheduler). Der interaktive Frontend-Vergleich (Go) bleibt unberührt. Fix ist korrekt + günstig → lohnt als Korrektheits-Hygiene, auch wenn aktuell wenige Abos existieren sollten.
