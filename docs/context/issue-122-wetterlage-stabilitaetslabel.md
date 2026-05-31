# Context: Issue #122 — F12 Großwetterlage / Stabilitäts-Label

## Request Summary

Jeder Report soll einen Kopf-Bereich erhalten, der die übergeordnete Wetterlage
als **STABIL / WECHSELHAFT / FRAGIL** klassifiziert. Das gibt den Tages-Prognosen
Kontext: „Die Konfidenz ist 70 % — aber die Lage ist insgesamt fragil, also konservativ planen."

## Vorbedingung-Check

| Bedingung | Status |
|---|---|
| F11 (#121) geschlossen | ✅ 2026-05-15 |
| ≥ 7 Tage Prod-Stabilität | ✅ 15 Tage (Stand 2026-05-30) |
| Ensemble-Spread-Daten fließen | ✅ T2m + Precip-Spread aktiv |

**Ergebnis: Alle Vorbedingungen erfüllt. Issue kann aus `status:deferred` heraus.**

## Stand der Implementierung

**F12 ist komplett nicht gestartet.** Kein Code, keine Spec, kein Cache.

## Bereits vorhandene Bausteine (wiederverwendbar)

| Datei | Relevanter Baustein | Für F12 nutzbar als |
|---|---|---|
| `src/providers/openmeteo.py:508` | `_fetch_ensemble_spread()` | Muster für Z500-Ensemble-Fetch; holt aktuell T2m+Precip-Spread via Ensemble-API |
| `src/providers/openmeteo.py:67` | `compute_confidence_pct()` | Punktsystem-Logik-Muster (Spread → Score) |
| `src/output/renderers/email/helpers.py:282` | `build_confidence_hint()` | Muster für neuen `build_stability_section()` |
| `src/output/renderers/email/html.py:375` | Confidence-Hint-Block | Muster für neue WL-Sektion oben im HTML-Report |
| `src/output/tokens/builder.py:31` | `_confidence_symbol()` + SMS-Token | Muster für SMS WL-Token (`WL:s`/`WL:w`/`WL:f`) |
| `data/cache/model_availability.json` | Cache-Pattern | Vorlage für `data/cache/weather_pattern/<region>_<run>.json` |
| `src/services/forecast.py` | Forecast-Fetch-Aufruf | Paralleler WL-Service-Aufruf hier einzuhängen |

## Was noch fehlt (Implementierungslücken)

1. **Z500-Fetch nicht implementiert:** `_fetch_ensemble_spread()` holt `temperature_2m,precipitation`, **nicht** `geopotential_height_500hPa`. Neuer API-Call gegen OpenMeteo Ensemble API nötig.
2. **Run-zu-Run-Cache fehlt:** `data/cache/weather_pattern/` existiert nicht. Muss angelegt und in `.gitignore` eingetragen werden.
3. **`src/services/weather_pattern.py` fehlt** — der zentrale Heuristik-Service.
4. **Output-Integration fehlt** — E-Mail-Sektion und SMS-Header nicht eingebaut.
5. **Spec `docs/specs/modules/weather_pattern.md` fehlt.**

## Architektur-Entscheidungen (aus Issue)

- **Eigener Service** `src/services/weather_pattern.py` — nicht in `NormalizedTimeseries` einbauen (Großwetterlage ist synoptisch/regional, nicht punktuell)
- **Graceful Degradation:** Wenn WL-Berechnung fehlschlägt → Report läuft ohne Label
- **Score 0–6** aus 3 Komponenten à 0/1/2 Punkte: Z500-Tendenz, Ensemble-Spread Z500, Run-zu-Run-Konsistenz
- **Label-Mapping:** 5–6 = STABIL, 3–4 = WECHSELHAFT, 0–2 = FRAGIL

## Offene Fragen (aus Issue, vor Spec klären)

1. **Pro Region oder pro Trip?** Wenn eine Tour mehrere Locations hat — welche Position fürs Z500-Sample? (Empfehlung: Mittelpunkt des Trips oder erste Stage)
2. **DWD-ICON vs. ECMWF für Mittelmeer?** `/dwd-icon` OpenMeteo-Modell deckt GR221 (Mallorca) ab — verifizieren, sonst auf `/ecmwf-ifs` umsteigen.
3. **SMS-Header-Format:** `Wetterlage: STABIL ✓` vs. Kurzform `WL:s`? Hängt von Trip-Länge und SMS-Budget ab.

## Abhängigkeiten

### Upstream (was F12 braucht)
- `src/providers/openmeteo.py` — neuer Z500-Ensemble-Fetch
- `data/cache/weather_pattern/` — Run-Cache (neu anlegen)
- OpenMeteo Ensemble API: Variable `geopotential_height_500hPa`

### Downstream (was F12 verändert)
- `src/services/forecast.py` — paralleler WL-Aufruf
- `src/output/tokens/builder.py` — WL-Token/SMS-Kopfzeile
- `src/output/renderers/email/html.py` — WL-Sektion oben
- `src/output/renderers/email/plain.py` — WL-Sektion oben (Text)
- `.gitignore` — neues Cache-Verzeichnis

## Risiken

- **OpenMeteo Z500 Verfügbarkeit:** `geopotential_height_500hPa` muss in der Ensemble-API tatsächlich verfügbar sein — vor Spec verifizieren.
- **DWD-ICON Gebiet Mittelmeer:** Modell-Abdeckung für GR221 (Mallorca, ca. 39°N 3°E) unklar.
- **SMS-Zeichenbudget:** WL-Header + bestehende Tokens müssen ≤ 160 Zeichen bleiben.
- **7-Tage-Run-Cache Warmup:** Erster Run hat noch keinen Vorläufer-Cache → Run-zu-Run-Konsistenz liefert 0 Punkte (konservativ, korrekt).
- **Heuristik-Kalibrierung:** Issue verlangt Kalibrierung gegen 14 Tage echte Prod-Daten — muss nach Deployment erfolgen, nicht davor.

## Referenzen

- Issue: https://github.com/henemm/gregor_zwanzig/issues/122
- Vorbedingung F11: https://github.com/henemm/gregor_zwanzig/issues/121
- Ensemble-Fetch-Muster: `src/providers/openmeteo.py:508–590`
- E-Mail-Hint-Muster: `src/output/renderers/email/helpers.py:282–325`
- OpenMeteo Ensemble API: Docs unter open-meteo.com/en/docs/ensemble-api
