# Feature: Model-Metric-Fallback + Verfuegbarkeits-Probe

**Status:** backlog
**Priority:** MEDIUM
**Category:** Providers
**Created:** 2026-02-13
**Story:** Wetter-Engine - Provider-Qualitaet

## What

Zwei zusammenhaengende Teilfeatures:

### A) Metrik-Verfuegbarkeits-Probe (Voraussetzung)

Periodischer Test-API-Call pro Modell, der prueft welche Metriken tatsaechlich
Daten liefern vs. `null`. Ergebnis wird gecacht und dient als Entscheidungs-
grundlage fuer Fallback.

### B) Model-Metric-Fallback

Wenn das primaere Modell (z.B. AROME fuer Mallorca) fuer bestimmte Metriken
`null` liefert, automatisch auf ein breiteres Modell (z.B. ICON-EU oder ECMWF IFS)
zurueckfallen — aber NUR fuer die fehlenden Metriken.

## Why

**Problem heute:**
- Wir fragen immer 18 Parameter an, aber nicht jedes Modell liefert alle
- Fehlende Werte werden als "–" angezeigt — der User weiss nicht ob
  "kein Wert" = "nicht verfuegbar" oder "Wert ist 0/null"
- Wir wissen selbst nicht zuverlaessig, welches Modell was liefert
  (OpenMeteo-Doku ist unvollstaendig)
- Kein Fallback: wenn AROME kein `cape` liefert, bleibt es leer —
  obwohl ECMWF IFS es haette

**Nutzen:**
- Vollstaendigere Wetterdaten fuer den User
- Transparenz: Konfig-UI kann anzeigen welche Metriken verfuegbar sind
- Grundlage fuer spaetere Provider-Info in der UI

## For Whom

- **Primary User:** Weitwanderer — sieht weniger "–" in E-Mail-Tabellen
- **Secondary:** Entwickler — weiss welche Metriken pro Region funktionieren

## Design

### A) Verfuegbarkeits-Probe

```
Ablauf:
1. Fuer jedes Modell in REGIONAL_MODELS:
   - API-Call mit Referenz-Koordinate (Mitte der Bounding-Box)
   - Alle 18 hourly-Parameter anfragen
   - Pruefen welche Arrays Daten vs. nur null enthalten
2. Ergebnis als JSON cachen:
   {
     "probe_date": "2026-02-13",
     "models": {
       "meteofrance_arome": {
         "available": ["temperature_2m", "wind_speed_10m", "cape", ...],
         "unavailable": ["snow_depth", "precipitation_probability"]
       },
       "icon_d2": { ... },
       ...
     }
   }
3. Cache-TTL: 7 Tage (konfigurierbar)
4. Bei Startup pruefen ob Cache abgelaufen → neu proben
```

**Cache-Datei:** `data/cache/model_availability.json`

**Trigger:**
- Automatisch bei Server-Start wenn Cache aelter als TTL
- Manuell via CLI: `python -m src.app.cli --probe-models`
- NICHT bei jedem Request (zu teuer: 5 API-Calls)

### B) Fallback-Logik

```
Ablauf pro Forecast-Request:
1. Primaeres Modell waehlen (wie bisher: select_model by coords)
2. Availability-Cache laden
3. Fehlende Metriken identifizieren:
   requested_metrics - available_metrics[primary_model] = missing
4. Wenn missing nicht leer:
   a. Naechstes Modell in Prioritaetsliste finden das missing-Metriken hat
   b. Zweiten API-Call NUR mit fehlenden Parametern
   c. Ergebnisse mergen (primary hat Vorrang, fallback fuellt Luecken)
5. Meta-Info erweitern: welche Metriken aus welchem Modell
```

**Wichtig:**
- Maximal 1 Fallback-Call (nicht kaskadieren)
- Fallback-Modell muss die Koordinaten abdecken
- Zeitliche Aufloesung kann abweichen → auf Stunden-Raster interpolieren
- Im ForecastMeta dokumentieren welches Modell welche Daten liefert

### Transparenz in E-Mail

Footer erweitern:
```
Data: AROME France 1.3km | Fallback CAPE, POP: ICON-EU 7km
```

## Affected Systems

| Datei | Aenderung |
|-------|-----------|
| `src/providers/openmeteo.py` | Probe-Logik, Fallback-Fetch, Merge |
| `src/app/models.py` | ForecastMeta erweitern (multi-model info) |
| `data/cache/model_availability.json` | Neuer Cache-File |
| `src/app/cli.py` | `--probe-models` Command |
| `src/formatters/trip_report.py` | Footer mit Fallback-Info |

## Scoping

- **Probe allein:** ~80 LOC + Cache-IO
- **Fallback:** ~120 LOC (zweiter Call + Merge)
- **Gesamt:** ~200-250 LOC netto
- **Risiko:** Niedrig (additiv, kein Breaking Change)

## Open Questions

1. Soll die Probe auch bei Geosphere-Provider laufen?
2. Soll die UI anzeigen welche Metriken "via Fallback" kommen (Indikator)?
3. Cache-TTL: 7 Tage sinnvoll oder reicht 30 Tage (Modell-Verfuegbarkeit
   aendert sich selten)?
4. Soll der Fallback konfigurierbar sein (pro Trip an/aus)?

## Acceptance Criteria

- [ ] Probe laeuft bei Server-Start (wenn Cache abgelaufen)
- [ ] Cache-JSON zeigt pro Modell welche Metriken verfuegbar sind
- [ ] Fallback-Call fuer fehlende Metriken an breiteres Modell
- [ ] E-Mail-Footer zeigt Fallback-Info wenn verwendet
- [ ] Maximal 2 API-Calls pro Location (primary + 1 fallback)
- [ ] Bestehende Tests bleiben gruen (kein Breaking Change)
