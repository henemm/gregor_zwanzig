---
entity_id: issue_1135_heat_warning_plausibility
type: module
created: 2026-07-15
updated: 2026-07-15
status: draft
version: "1.0"
tags: [official-alerts, vigilance, briefing, bugfix]
---

# #1135 — Hitze-Warnung: Plausibilität & Bündelung

## Approval

- [x] Approved (PO-go 2026-07-15)

## Purpose

Behebt zwei Fehler bei amtlichen Vigilance-Hitzewarnungen im Trip-Briefing:
1. **Symptom 2** — dieselbe Hitzewarnung erscheint mehrfach (3×), weil der Trip mehrere Départements kreuzt.
2. **Symptom 1** — eine Hitzewarnung wird gezeigt, obwohl an der Etappe gar keine Hitze modelliert ist (gefühlt <20 °C in Höhenlage).

## Source

- **File:** `src/output/renderers/email/html.py` (Briefing-Warn-Block, ~1428-1452)
- **File:** `src/output/renderers/alert/official_alerts.py` (`_bundle_by_hazard_level` — bestehende Stufe-2-Bündelung, wird im Briefing-Pfad angewendet)
- **File:** `src/services/weather_metrics.py` (`_compute_wind_chill` — neues MAX-Pendant)
- **File:** `src/app/models.py` (`SegmentWeatherSummary` — neues Feld `wind_chill_max_c`)
- **Identifier:** Briefing-Render-Pfad + Segment-Aggregation

## Estimated Scope

- **LoC:** ~120-180
- **Files:** 3-4 (Model, Aggregation, Render-Pfad, Tests)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `dedupe_official_alerts` | bestehend | Stufe-1-Identitäts-Dedup (unverändert) |
| `_bundle_by_hazard_level` | bestehend | Stufe-2-Bündelung (bisher nur Alarm/Compare, nun auch Briefing) |
| `wind_chill_c` (`app/models.py:121`) | bestehend | Rohquelle gefühlte Temperatur je Datenpunkt |
| #1254 | ausgeliefert | Point-in-Polygon-Zuordnung (verschärfte Symptom 2 real) |

## Implementation Details

### Teil A — Symptom 2 (Mehrfach-Anzeige)
Im Briefing-HTML-Pfad (`html.py`, nach `dedupe_official_alerts`) zusätzlich `_bundle_by_hazard_level` anwenden — analog Alarm-/Compare-Pfad. Ergebnis: gleiche Gefahr + gleiche Stufe + gleiches Gültigkeitsfenster über mehrere Départements → **eine** Karte, deren Quellen-/Regions-Zeile alle betroffenen Regionen nennt (via `OfficialAlertNotice.regions`, dritter Rückgabewert von `_bundle_by_hazard_level`).

### Teil B — Symptom 1 (Plausibilitäts-Gate)
1. **Neues Segment-Datum:** `SegmentWeatherSummary.wind_chill_max_c` (Optional[float]). Aggregation in `weather_metrics.py` analog `_compute_wind_chill`, aber `max()` statt `min()` über `dp.wind_chill_c`.
2. **Gate im Briefing-Pfad, VOR Dedup/Bündelung:** Für jede Etappe die eigenen `official_alerts` filtern — ein Alert mit `hazard == "extreme_heat"` wird für diese Etappe entfernt, wenn `wind_chill_max_c` vorhanden UND `< HEAT_PLAUSIBILITY_MIN_C` (= 25.0 °C).
3. **Fail-safe:** Ist `wind_chill_max_c` None (keine Daten), wird NICHT unterdrückt — amtliche Warnung bleibt sichtbar.
4. **Nur Hitze:** Andere Gefahren (`wind_gust`, `thunderstorm`) bleiben vom Gate unberührt.

```
HEAT_PLAUSIBILITY_MIN_C = 25.0   # gefühlt-max-Schwelle; darunter = klarer Widerspruch
```

## Expected Behavior

- **Input:** Trip-Segmente mit `official_alerts` (Vigilance) + Segment-Wetter (`wind_chill_c`-Zeitreihe).
- **Output:** Briefing-HTML mit (a) höchstens einer Karte je Gefahr/Stufe/Gültigkeit über alle Regionen, (b) keiner Hitzewarnung an Etappen mit gefühlt-max < 25 °C.
- **Side effects:** Neues Feld `wind_chill_max_c` in Segment-Persistenz (additiv, keine Migration nötig — Optional, Default None).

## Acceptance Criteria

- **AC-1:** Given ein Trip kreuzt drei Départements, die alle unter derselben `extreme_heat`-Vigilance gleicher Stufe und gleichem Gültigkeitsfenster stehen (jede Etappe mit gefühlt-max ≥ 25 °C) / When das Trip-Briefing-HTML gerendert wird / Then erscheint **genau eine** Hitze-Warnkarte, die (a) den **Streckenbezug** aller betroffenen Etappen nennt UND (b) die **Namen aller drei betroffenen Départements** nennt (nicht die Codes, nicht nur des Bündel-Repräsentanten) — nicht drei separate Karten.
  - Test: Briefing-HTML für einen 3-Département-Trip (echte Codes, z.B. "83"/"13"/"06") rendern, Anzahl der Hitze-Warn-Einträge == 1 prüfen, dass alle drei Etappen im Streckenbezug UND alle drei Département-**Namen** ("Var"/"Bouches-du-Rhône"/"Alpes-Maritimes") im Kartentext vorkommen.

- **AC-2:** Given zwei Hitzewarnungen **unterschiedlicher Stufe** (Département A orange/Level 3, Département B gelb/Level 2) / When das Briefing gerendert wird / Then bleiben beide als **getrennte** Warnungen sichtbar (verschiedene Stufe = verschiedene Warnung).
  - Test: Briefing mit zwei Hitzewarnungen unterschiedlicher Stufe rendern, zwei getrennte Einträge nachweisen.

- **AC-3:** Given eine Etappe trägt eine `extreme_heat`-Vigilance-Warnung, aber die dort modellierte gefühlte Höchsttemperatur (`wind_chill_max_c`) liegt bei 18 °C (< 25 °C) / When das Briefing gerendert wird / Then wird für diese Etappe **keine** Hitzewarnung angezeigt.
  - Test: Segment mit extreme_heat-Alert + wind_chill_max_c=18 rendern, kein Hitze-Eintrag im Output.

- **AC-4:** Given eine Etappe trägt eine `extreme_heat`-Warnung und `wind_chill_max_c` liegt bei 31 °C (≥ 25 °C) / When das Briefing gerendert wird / Then wird die Hitzewarnung **angezeigt**.
  - Test: Segment mit extreme_heat-Alert + wind_chill_max_c=31 rendern, Hitze-Eintrag vorhanden.

- **AC-5:** Given eine Etappe trägt eine `extreme_heat`-Warnung, aber es liegt **keine** gefühlte Temperatur vor (`wind_chill_max_c` ist None) / When das Briefing gerendert wird / Then wird die Warnung **angezeigt** (Fail-safe: bei fehlenden Daten nie unterdrücken).
  - Test: Segment mit extreme_heat-Alert + wind_chill_max_c=None rendern, Hitze-Eintrag vorhanden.

- **AC-6:** Given eine Etappe mit gefühlt-max 15 °C trägt eine `wind_gust`- oder `thunderstorm`-Warnung / When das Briefing gerendert wird / Then bleibt diese Nicht-Hitze-Warnung **unverändert sichtbar** (Gate greift ausschließlich auf `extreme_heat`).
  - Test: Segment mit thunderstorm-Alert + niedrigem wind_chill_max_c rendern, Warnung vorhanden.

- **AC-7:** Given eine Segment-Zeitreihe mit `wind_chill_c`-Werten [10, 22, 31, 27] / When die Segment-Zusammenfassung berechnet wird / Then ist `wind_chill_max_c == 31` (neues Feld, analog `wind_chill_min_c`).
  - Test: `SegmentSummarizer` auf Timeseries anwenden, `wind_chill_max_c` == max der Eingabewerte.

## Known Limitations

- **Schwelle 25 °C ist ein fester Wert** (keine Konfigurierbarkeit in diesem Fix). Konservativ gewählt: echte Canicule-Spitzen liegen bei ~33-36 °C; der Bereich 25-30 °C bleibt bewusst sichtbar, um berechtigte Warnungen nicht zu unterdrücken.
- **Gate greift im Trip-Briefing-Pfad.** Der Standalone-Alarm- und der Compare-Pfad sind nicht Teil dieses Fixes (dort ist das Segment-Feels-Max nicht überall im selben Kontext verfügbar; separater Bedarf ggf. als Folgebefund).
- **Vigilance bleibt département-granular** — dieser Fix ersetzt keine punktgenaue Warnung, sondern unterdrückt nur den *klaren* Widerspruch gegen die eigene Prognose.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues architektonisches Muster — Teil A nutzt die bestehende Stufe-2-Bündelung, Teil B ergänzt eine Metrik-Aggregation (analog vorhandenem MIN) plus einen lokalen Filter. Beides folgt etablierten Pfaden.

## Changelog

- 2026-07-15: Initial spec created (PO-Entscheidung: „Ausblenden bei klarem Widerspruch", Schwelle 25 °C)
- 2026-07-15: AC-1 präzisiert nach Adversary-Finding F001 (BROKEN) + PO-Entscheidung „Etappen + Départements": gebündelte Karte nennt zusätzlich die Département-**Namen** (nicht nur Codes). Erfordert eine Département-Code→Name-Referenztabelle (das System speichert nur Codes) und Konsum von `OfficialAlertNotice.regions` im Embedded-Renderer.
