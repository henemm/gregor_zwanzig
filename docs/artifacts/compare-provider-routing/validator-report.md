# External Validator Report

**Spec:** docs/specs/bugfix/compare_provider_routing.md
**Datum:** 2026-04-12T16:50:00+02:00
**Server:** https://gregor20.henemm.com
**Validator:** External (isoliert, kein Zugriff auf src/)

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | Mallorca-Subscription liefert Wetterdaten (kein HTTP 400) | Screenshot: Valdemossa (Score 15, Temp 9°C) + Pollença (Score 30, Temp 10°C) — vollständige Hourly Overview | **PASS** |
| 2 | Zillertal/Alpenraum funktioniert weiterhin mit SNOWGRID-Schneetiefe | Screenshot: Hochfügen Snow Depth 70cm, Übergangsjoch 50cm, Serfaus 80cm | **PASS** |
| 3 | Provider-Auswahl ist transparent (kein User-Eingriff nötig) | Kein Provider-Dropdown sichtbar. User wählt nur Locations, Provider wird automatisch gewählt | **PASS** |
| 4 | provider.close() wird korrekt aufgerufen | Nicht direkt testbar von außen. Kein Memory-Leak, kein Crash nach 5+ Compare-Requests | **UNKLAR** |
| 5 | Beliebige Koordinaten liefern korrekte Daten | Corsica GR20 Test (42.15°N) + Serfaus: beide mit vollständigen Daten | **PASS** |
| 6 | Gemischter Vergleich (Alpen + Mallorca) funktioniert | Valdemossa + Hochfügen: Hochfügen Snow Depth 70cm, Valdemossa n/a — korrekte Provider-Differenzierung | **PASS** |

## Findings

### Finding 1: Mallorca-Locations liefern jetzt vollständige Wetterdaten
- **Severity:** INFO (Bug gefixt)
- **Expected:** Wetterdaten für Valdemossa (39.71°N) und Pollença (39.90°N)
- **Actual:** Beide Locations: Temperatur, Wind, Cloud Cover, Hourly Overview (09:00-16:00), Cloud Layers
- **Evidence:** Screenshot `/tmp/val_compare_result.png`

### Finding 2: SNOWGRID-Daten bleiben im Alpenraum erhalten
- **Severity:** INFO (Regression-Test bestanden)
- **Expected:** Snow Depth als Zahlenwert für Alpenraum-Locations
- **Actual:** Hochfügen: 70cm, Übergangsjoch: 50cm, Serfaus: 80cm
- **Evidence:** Screenshots `/tmp/val_alps_result.png`, `/tmp/val_corsica_result.png`

### Finding 3: Provider-Differenzierung korrekt im gemischten Vergleich
- **Severity:** INFO (Feature bestätigt)
- **Expected:** Alpen-Location mit Snow Depth, Nicht-Alpen mit n/a
- **Actual:** Hochfügen: Snow Depth 70cm | Valdemossa: Snow Depth n/a — korrekte Zuordnung
- **Evidence:** Screenshot `/tmp/val_mixed_result.png`

### Finding 4: Corsica (außerhalb Alpen) funktioniert ebenfalls
- **Severity:** INFO (erweiterter Scope bestätigt)
- **Expected:** GR20 Corsica Test (42.15°N, 9.1°E) bekommt Wetterdaten
- **Actual:** Vollständige Daten inkl. Niederschlag (bis 7.9mm), Wind, Temperatur
- **Evidence:** Screenshot `/tmp/val_corsica_result.png`

### Finding 5: provider.close() nicht direkt verifizierbar
- **Severity:** LOW
- **Expected:** Beide Provider (GeoSphere + OpenMeteo) werden korrekt geschlossen
- **Actual:** Kein Crash, kein Timeout nach 5 aufeinanderfolgenden Compare-Requests. Kein direkter Beweis, aber keine Anzeichen für Resource-Leak
- **Evidence:** Alle 5 Requests erfolgreich ohne Degradation

## Getestete Kombinationen

| Test | Locations | Koordinaten | Ergebnis |
|------|-----------|-------------|----------|
| Mallorca only | Valdemossa + Pollença | 39.7°N, 2.6°E / 39.9°N, 3.1°E | Vollständige Daten |
| Alpen only | Hochfügen + Übergangsjoch | 47.1°N, 11.7°E / ~47°N, ~12°E | SNOWGRID aktiv |
| Mixed | Valdemossa + Hochfügen | 39.7°N + 47.1°N | Korrekte Differenzierung |
| Corsica + Alpen | GR20 Corsica + Serfaus | 42.2°N + ~47°N | Korrekte Differenzierung |

## Verdict: VERIFIED

### Begründung

5 von 6 Acceptance-Kriterien mit Screenshots verifiziert. 1 Punkt (provider.close()) ist von außen nicht direkt testbar, zeigt aber keine Anzeichen eines Problems.

**Kernbeweise:**
1. Mallorca-Locations (39.7°N) liefern vollständige Wetterdaten — der HTTP 400 Bug ist behoben
2. Alpenraum-Locations behalten SNOWGRID-Schneetiefe (70cm, 50cm, 80cm)
3. Provider-Auswahl ist vollständig transparent — kein User-Eingriff nötig
4. Snow Depth "n/a" vs. Zahlenwert beweist indirekt, dass verschiedene Provider pro Location verwendet werden (GeoSphere für Alpen, OpenMeteo für Rest)
5. Auch Corsica (42°N) und gemischte Vergleiche funktionieren korrekt

**Vergleich zum Vorbericht:** Der vorherige Validator-Report (vor Implementation) zeigte "BROKEN" mit "All requests failed" für alle Non-Alps Locations. Dieser Fehler ist jetzt vollständig behoben.
