---
entity_id: weather_pattern
type: module
created: 2026-05-30
updated: 2026-05-30
status: draft
version: "1.0"
tags: [forecast, ensemble, openmeteo, stability, sms, email, z500, risk]
---

<!-- Issue #122 — F12: Großwetterlage / Stabilitäts-Label -->

# F12: Großwetterlage / Stabilitäts-Label (Master-Spec)

## Approval

- [x] Approved

## Purpose

Ergänzt jeden Trip-Wetter-Report um ein Stabilitäts-Label (STABIL / WECHSELHAFT / FRAGIL), das auf einen Blick zeigt, wie verlässlich die Wetterprognose für die nächsten Etappen ist. Das Label basiert auf zwei Z500-Ensemble-Komponenten — Tendenz der 500-hPa-Geopotentialhöhe über 48 h und Ensemble-Spread über 72 h — und erscheint ganz oben im E-Mail-Report sowie als `WL`-Token in der SMS-Kompaktzeile.

Die Großwetterlage-Einschätzung beantwortet für einen Mehrtagswanderer (z.B. GR20, Etappe 3 von 15) die Frage: "Kann ich den Prognosen für die nächsten Tage vertrauen, oder sollte ich konservativ planen?" Da diese Frage unabhängig von einzelnen Wetterwerten (Regen, Wind) beantwortet wird, ist F12 ein eigenständiger Service — `WeatherPatternService` — der parallel zur bestehenden Forecast-Pipeline läuft und sein Ergebnis als `StabilityResult`-Dataclass zurückliefert.

## Source

### Neues Modul

- **Datei:** `src/services/weather_pattern.py`
- **Identifier:** `WeatherPatternService`
- **Methode:** `compute_for_trip(trip, target_date) -> StabilityResult | None`

### Geänderte Dateien

- **Änderung:** `src/app/models.py` — neues Dataclass `StabilityResult` (frozen, 3 Felder)
- **Änderung:** `src/providers/openmeteo.py` — neue Methode `_fetch_ensemble_with_z500(lat, lon) -> dict`
- **Änderung:** `src/services/trip_report_scheduler.py` — `WeatherPatternService` aufrufen, Ergebnis an Formatter durchreichen
- **Änderung:** `src/formatters/trip_report.py` — Parameter `stability_result: StabilityResult | None` aufnehmen, weiterreichen
- **Änderung:** `src/output/renderers/email/__init__.py` — Parameter `stability_result` aufnehmen, weiterreichen
- **Änderung:** `src/output/renderers/email/html.py` — farbige WL-Box ganz oben rendern (vor Confidence-Hinweis)
- **Änderung:** `src/output/renderers/email/plain.py` — WL-Textzeile ganz oben rendern
- **Änderung:** `src/output/tokens/builder.py` — `WL`-Token in `POSITIONAL` einfügen (nach `C`, vor `HR`)
- **Änderung:** `docs/reference/sms_format.md` — v2.1 → v2.2, WL-Token definieren

## Estimated Scope

- **LoC:** ~303 Python + ~10 Markdown
- **Files:** 9 Produktionsdateien + 1 Doku
- **Effort:** medium
- **LoC-Override:** 350

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| OpenMeteo Ensemble API (`ensemble-api.open-meteo.com/v1/ensemble`) | extern | Liefert Z500-Ensemble-Member-Zeitreihen |
| `StabilityResult` | neues Dataclass (models.py) | Trägt Label, Gesamt-Score und Komponenten-Scores |
| `Trip.get_future_stages(from_date)` | Methode (trip.py) | Liefert die verbleibenden zukünftigen Etappen ab `target_date` |
| `OpenMeteoProvider._fetch_ensemble_with_z500()` | neue Methode (openmeteo.py) | Ensemble-HTTP-Call für Z500 |
| `trip_report_scheduler.py` | Service | Orchestriert den Report-Bau; ruft `WeatherPatternService` auf |
| `trip_report.py` (Formatter) | Service | Nimmt `stability_result` entgegen und reicht es an Renderer weiter |
| `email/html.py` | Renderer | Rendert die farbige WL-Box |
| `email/plain.py` | Renderer | Rendert die WL-Textzeile |
| `tokens/builder.py` | Token-Builder | Emittiert den `WL`-Token in der POSITIONAL-Reihenfolge |
| `sms_format.md` | Referenz-Dokument | Single Source of Truth für Token-Reihenfolge und Symbole |
| `httpx` | externe Bibliothek | HTTP-Client für den Ensemble-API-Call (bereits im Provider vorhanden) |
| `statistics.stdev` | stdlib | Berechnung des Ensemble-Spreads (σ) pro Stunde |

## Implementation Details

### 1) Neues Dataclass `StabilityResult` in `src/app/models.py`

```python
from typing import Literal

@dataclass(frozen=True)
class StabilityResult:
    label: Literal["STABIL", "WECHSELHAFT", "FRAGIL"]
    score: int                       # Gesamt-Score 0–4
    component_scores: tuple[int, int]  # (tendency_score, spread_score)
```

Das Dataclass ist `frozen=True` (immutable). Es wird nicht persistiert — es wird bei jedem Report-Lauf frisch berechnet. Kein Schema-Impact auf bestehende Snapshots.

### 2) Neue Methode `_fetch_ensemble_with_z500()` in `src/providers/openmeteo.py`

**Endpoint:** `https://ensemble-api.open-meteo.com/v1/ensemble`

**Parameter:**
```
latitude=<lat>
longitude=<lon>
hourly=geopotential_height_500hPa
models=ecmwf_ifs04,icon_seamless,gfs_seamless
forecast_days=4
timezone=UTC
```

**Response-Struktur:** Die API liefert unter `hourly` für jedes Modell Spalten mit Suffix `_member01`, `_member02`, … (z.B. `geopotential_height_500hPa_member01`). Alle Member-Spalten für Z500 werden gesammelt.

**Rückgabe:** `dict` mit `time: list[str]` (ISO-8601 UTC) und `z500_members: list[list[float]]` — äußere Liste: Zeitpunkte, innere Liste: Member-Werte pro Zeitpunkt.

**Fehlerbehandlung:** Bei HTTP-Fehler (4xx/5xx) oder Timeout gibt die Methode `None` zurück — kein Exception-Raise nach außen. `WeatherPatternService` behandelt `None` als „Daten nicht verfügbar" und gibt selbst `None` zurück.

### 3) `WeatherPatternService.compute_for_trip()` in `src/services/weather_pattern.py`

```python
class WeatherPatternService:
    def __init__(self, provider: OpenMeteoProvider): ...

    def compute_for_trip(
        self,
        trip,
        target_date: date,
    ) -> StabilityResult | None:
        ...
```

**Schritt 1 — Zukünftige Etappen ermitteln:**
```python
future_stages = trip.get_future_stages(from_date=target_date)
# Begrenze auf max 5 Tage ab target_date
future_stages = [s for s in future_stages
                 if s.start_date <= target_date + timedelta(days=5)]
if not future_stages:
    return None  # letzter Tag oder keine weiteren Etappen
```

**Schritt 2 — Zentroid der zukünftigen Etappen:**
```python
# Erster Wegpunkt jeder Etappe
waypoints = [s.waypoints[0] for s in future_stages if s.waypoints]
lat = sum(w.lat for w in waypoints) / len(waypoints)
lon = sum(w.lon for w in waypoints) / len(waypoints)
```

**Schritt 3 — Ensemble-Daten holen:**
```python
data = self._provider._fetch_ensemble_with_z500(lat, lon)
if data is None:
    return None  # graceful degradation
```

**Schritt 4 — Komponente 1: Z500-Tendenz über 48 h (0/1/2 Punkte):**
```python
# T+0 = erster Datenpunkt (Index 0), T+48h = Index 48
z500_mean_t0 = mean(data["z500_members"][0])   # mean über Member
z500_mean_t48 = mean(data["z500_members"][48])
delta = abs(z500_mean_t48 - z500_mean_t0)      # in geopotential metres (gpm)

if delta < 15:
    tendency_score = 2
elif delta < 40:
    tendency_score = 1
else:
    tendency_score = 0
```

**Schritt 5 — Komponente 2: Ensemble-Spread Z500 über T+0 bis T+72 h (0/1/2 Punkte):**
```python
# Berechne σ (stdev) der Member pro Stunde, dann Mittelwert über 73 Datenpunkte
spread_per_hour = []
for hour_members in data["z500_members"][:73]:
    valid = [v for v in hour_members if v is not None]
    if len(valid) >= 5:
        spread_per_hour.append(stdev(valid))
mean_spread = mean(spread_per_hour) if spread_per_hour else 9999

if mean_spread < 40:
    spread_score = 2
elif mean_spread < 80:
    spread_score = 1
else:
    spread_score = 0
```

**Schritt 6 — Label-Mapping:**
```python
total = tendency_score + spread_score
if total >= 3:
    label = "STABIL"
elif total == 2:
    label = "WECHSELHAFT"
else:
    label = "FRAGIL"

return StabilityResult(
    label=label,
    score=total,
    component_scores=(tendency_score, spread_score),
)
```

**Gesamte Exception-Behandlung:** Der gesamte Body von `compute_for_trip()` ist in `try/except Exception` gewrappt. Bei einem unerwarteten Fehler wird `None` zurückgegeben und der Fehler geloggt. Der Report läuft ohne Label weiter.

### 4) Integration in `trip_report_scheduler.py`

```python
# Nach dem bestehenden Forecast-Call, vor dem Formatter-Aufruf:
weather_pattern_svc = WeatherPatternService(provider=openmeteo_provider)
stability_result = weather_pattern_svc.compute_for_trip(trip, target_date)

# stability_result kann None sein — der Formatter behandelt beide Fälle
report = formatter.format(
    ...,
    stability_result=stability_result,
)
```

### 5) E-Mail-Rendering in `html.py` und `plain.py`

Das WL-Label wird als erster Block im E-Mail-Body gerendert, noch vor dem bestehenden Konfidenz-Hinweis (F11).

**HTML — farbige Box:**

| Label | CSS-Hintergrundfarbe | Textfarbe |
|-------|---------------------|-----------|
| `STABIL` | `#d4edda` (Bootstrap success-tint) | `#155724` |
| `WECHSELHAFT` | `#fff3cd` (Bootstrap warning-tint) | `#856404` |
| `FRAGIL` | `#f8d7da` (Bootstrap danger-tint) | `#721c24` |

Wortlaut (fix, nicht konfigurierbar):

- STABIL: `"Wetterlage: STABIL — Die Großwetterlage ist stabil. Prognosen für die nächsten Etappen sind verlässlich."`
- WECHSELHAFT: `"Wetterlage: WECHSELHAFT — Die Lage ist im Übergang. Prognosen ab Tag 3 mit Vorsicht behandeln."`
- FRAGIL: `"Wetterlage: FRAGIL — Schnelle Frontverlagerung möglich. Prognosen ab Tag 2 konservativ planen."`

**Plain:** Gleicher Wortlaut, eingerahmt durch Trennlinie (`---`), ohne HTML-Markup.

**Wenn `stability_result is None`:** Kein Block wird gerendert. Der restliche Report ist unverändert.

### 6) SMS-Token `WL` in `tokens/builder.py`

**Symbol-Mapping:**
| Label | Token |
|-------|-------|
| `STABIL` | `WL+` |
| `WECHSELHAFT` | `WL~` |
| `FRAGIL` | `WL-` |
| `None` (nicht berechnet) | Token weggelassen |

**Position in `POSITIONAL`:** Unmittelbar nach `C` (Konfidenz-Token, F11), vor `HR` (Vigilance). Damit lautet die vollständige Reihenfolge in der SMS-Zeile:

```
{Name}: N D R PR W G TH: TH+: C WL HR:TH: Z: M: [SN SN24+ SFL AV WC] DBG
```

**Builder-Code:**
```python
if stability_result is not None:
    symbol = {"STABIL": "+", "WECHSELHAFT": "~", "FRAGIL": "-"}[stability_result.label]
    tokens.append(Token(symbol="WL", value=symbol))
```

**Truncation:** `WL`-Token hat niedrigere Priorität als Gewitter- und Wind-Tokens. Bei Platzmangel wird er nach `C`, aber vor `PR` gestrichen. Die bestehende Truncation-Strategie aus §6 der `sms_format.md` gilt.

### 7) `sms_format.md` Update (v2.1 → v2.2)

- Versionszeile `version: "2.2"` in YAML-Header
- Token-Übersicht §2 ergänzen: `WL` nach `C` einfügen
- Neuer Unterabschnitt §3.4c: WL-Token, Symbole, Mapping, Omit-Bedingung
- Beispiel §8 ergänzen (Beispiel mit FRAGIL + `WL-`)
- Versionstabelle §12 ergänzen: `2.2 | 2026-05-30 | WL-Token (Issue #122)`

## Acceptance Criteria

- **AC-1:** Given `StabilityResult` importiert aus `src.app.models` / When eine Instanz mit `label="STABIL", score=4, component_scores=(2,2)` erstellt wird / Then ist das Objekt frozen (Mutation löst `FrozenInstanceError` aus) und alle drei Felder haben genau die übergebenen Werte
  - Test: (populated after /tdd-red)

- **AC-2:** Given Ensemble-Z500-Daten mit `z500_mean_t0=5500 gpm` und `z500_mean_t48=5530 gpm` (delta=30 gpm) / When `tendency_score` berechnet wird / Then ist der Wert genau `1` (delta < 40, aber >= 15)
  - Test: (populated after /tdd-red)

- **AC-3:** Given Ensemble-Z500-Daten mit `z500_mean_t0=5500 gpm` und `z500_mean_t48=5560 gpm` (delta=60 gpm) / When `tendency_score` berechnet wird / Then ist der Wert genau `0` (delta >= 40)
  - Test: (populated after /tdd-red)

- **AC-4:** Given stündliche Ensemble-Member-Daten über T+0 bis T+72h mit `mean_spread=35 gpm` / When `spread_score` berechnet wird / Then ist der Wert genau `2` (mean_spread < 40)
  - Test: (populated after /tdd-red)

- **AC-5:** Given `tendency_score=2, spread_score=2` (total=4) / When `label` gemappt wird / Then ist `label == "STABIL"`. Given `tendency_score=1, spread_score=1` (total=2) / Then `label == "WECHSELHAFT"`. Given `tendency_score=0, spread_score=1` (total=1) / Then `label == "FRAGIL"`
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein Trip, bei dem `trip.get_future_stages(from_date=target_date)` eine leere Liste zurückgibt (letzte Etappe) / When `WeatherPatternService.compute_for_trip()` aufgerufen wird / Then ist der Rückgabewert `None` — kein Ensemble-API-Call wird gemacht
  - Test: (populated after /tdd-red)

- **AC-7:** Given die OpenMeteo Ensemble-API antwortet mit HTTP 503 / When `WeatherPatternService.compute_for_trip()` aufgerufen wird / Then gibt die Methode `None` zurück, kein Exception propagiert nach außen, der Report-Build läuft fehlerfrei ohne WL-Label weiter
  - Test: (populated after /tdd-red)

- **AC-8:** Given ein Report-Build mit `stability_result=StabilityResult(label="FRAGIL", score=1, component_scores=(0,1))` / When `html.py` rendert / Then enthält der HTML-Body den Block `"Wetterlage: FRAGIL"` als ersten inhaltlichen Element vor dem Konfidenz-Hinweis (F11), mit rotem/orangen Hintergrund (`#f8d7da`)
  - Test: (populated after /tdd-red)

- **AC-9:** Given ein Report-Build mit `stability_result=None` / When `html.py` und `plain.py` rendern / Then fehlt jeder WL-bezogene Block im Output — kein leerer Platzhalter, kein leeres `<div>`
  - Test: (populated after /tdd-red)

- **AC-10:** Given ein Report-Build mit `stability_result=StabilityResult(label="STABIL", ...)` / When `tokens/builder.py` die POSITIONAL-Liste aufbaut / Then enthält die Token-Liste einen Token mit `symbol="WL"` und `value="+"`, positioniert nach dem `C`-Token und vor dem `HR`-Token
  - Test: (populated after /tdd-red)

- **AC-11:** Given eine vollständige SMS-Zeile mit allen optionalen Tokens (C, WL, HR, TH Vigilance, Z, M) für einen GR20-Etappe / When die finale SMS-Zeichenkette gebildet wird / Then bleibt die Länge ≤ 160 Zeichen (GSM-7), und `WL+`/`WL~`/`WL-` erscheint genau einmal in korrekter Position
  - Test: (populated after /tdd-red)

- **AC-12:** Given ein Trip, der an `target_date` seine letzte Etappe hat (`get_future_stages` = []) / When der vollständige Report (E-Mail + SMS) gebaut wird / Then enthält weder der E-Mail-Body noch die SMS-Zeile irgendeine WL-Referenz
  - Test: (populated after /tdd-red)

## Expected Behavior

- **Input:** Ein `Trip`-Objekt und ein `target_date` (Datum des aktuellen Reports). Der Service fragt intern die OpenMeteo Ensemble API für den Zentroid der nächsten 1–5 Etappen ab.
- **Output:**
  - `StabilityResult(label, score, component_scores)` bei erfolgreicher Berechnung (1+ zukünftige Etappen, API-Call erfolgreich)
  - `None` bei letzter Etappe (0 zukünftige Etappen) oder API-Fehler
  - E-Mail: farbige WL-Box ganz oben im Body (nur wenn `StabilityResult` vorhanden)
  - SMS: `WL+`/`WL~/`WL-`-Token nach `C` in der POSITIONAL-Reihenfolge (nur wenn `StabilityResult` vorhanden)
- **Side effects:** Ein zusätzlicher HTTP-Call an `ensemble-api.open-meteo.com` pro Report-Lauf. Bei API-Fehler: kein Crash, kein Retry, `None` wird zurückgegeben. Der Fehler wird auf DEBUG-Level geloggt.

## Known Limitations

- **Run-to-run-Konsistenz nicht implementiert:** Vergleich aufeinanderfolgender API-Läufe (ob sich das Label von Lauf zu Lauf ändert) ist im MVP bewusst weggelassen — zu komplex für den marginalen Gewinn. Follow-up als separates Issue falls nötig.
- **Zentroid als Näherung:** Der Zentroid der ersten Wegpunkte der nächsten Etappen ist eine grobe geografische Näherung. Für Hochgebirgsrouten mit starker Orographie (z.B. GR20 zwischen 500 m und 2500 m) könnte ein präziserer Punkt (z.B. Etappenmitte oder höchster Punkt) treffender sein — für MVP ausreichend, da Z500 ein großräumiger Index ist.
- **Ensemble-Coverage je nach Region:** Nicht alle drei Modelle (ECMWF IFS04, ICON, GFS) liefern für jede Region gleich viele Member. Bei < 5 validen Member-Werten pro Stunde wird die Stunde aus dem Spread-Mittel ausgeschlossen (keine Fehler-Propagation). Wenn über den gesamten 72-h-Zeitraum keine auswertbaren Member vorhanden sind, gibt `compute_for_trip()` `None` zurück.
- **Statische Score-Schwellen:** Die Grenzwerte 15/40 gpm (Tendenz) und 40/80 gpm (Spread) sind aus der meteorologischen Literatur zur synoptischen Skala abgeleitet. Sie sind nicht dynamisch kalibriert und könnten für extreme Klimazonen (tropische Regionen, Hocharktis) zu eng oder zu weit sein.
- **Kein direkter Risk-Engine-Trigger:** Im Gegensatz zu F11 (`LOW_CONFIDENCE`) feuert `FRAGIL` kein neues `RiskType`-Event in der bestehenden Risk-Engine. Das Label ist eine eigenständige Großwetterlagen-Aussage, keine Ergänzung zu einem spezifischen Wetter-Risiko. Ein möglicher `FRAGIL → Risk`-Trigger wäre ein separates Follow-up.

## Changelog

- 2026-05-30: Initial spec erstellt für Issue #122 (F12: Großwetterlage / Stabilitäts-Label)
