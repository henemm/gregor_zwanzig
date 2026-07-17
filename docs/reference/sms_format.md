---
entity_id: sms_format
type: reference
version: "2.7"
status: active
created: 2025-12-27
updated: 2026-07-13
tags: [sms, compact, tokens, single-source-of-truth]
---

## Approval

- [x] Approved (v2.0 am 2026-04-25)
- [x] Implementiert in SMS-Adapter via `src/output/renderers/sms/` (β3, 2026-04-28)

# SMS / Kompakt-Format Specification (v2.7)

**Single Source of Truth** für die kompakte Token-Zeile, die in allen Channels (SMS, Satellit, E-Mail-Header, Push) identisch verwendet wird. Alle anderen Repräsentationen (E-Mail-Body, Tabellen, Push-Titel) leiten sich aus dieser Token-Zeile ab.

Diese Spec ersetzt v1.0 und integriert das Format aus dem Vorgänger-Projekt (`weather_email_autobot/requests/morning-evening-refactor.md`).

---

## 1. Prinzipien

- **Maximale Länge:** ≤160 Zeichen (GSM-7 normalisiert).
- **Zeichensatz:** ASCII / GSM-7. Umlaute werden ersetzt (ä→ae, ö→oe, ü→ue, ß→ss);
  darüber hinaus wird **jede** andere Schrift (Griechisch, Kyrillisch, Arabisch, …)
  auf ASCII transliteriert. Umsetzung einzig über `fold_ascii()` in
  `src/utils/ascii_fold.py` (ADR-0022) — Umlaut-Digraph-Map zuerst, danach
  `anyascii` zeichenweise. Buchstaben, die auch `anyascii` nicht falten kann,
  erscheinen als sichtbarer Platzhalter `?` statt lautlos zu verschwinden.
- **Zeitformat:** Lokale Zeit (CEST), nur Stunde (0–23, **ohne** führende Null). Beispiel: `@7`, nicht `@07`.
- **Tokens:** Kurze, möglichst englische/internationale Identifier.
- **Trennzeichen:** Einzelnes Leerzeichen zwischen Tokens. Ausnahmen siehe Risks-Block (3.3).
- **Werte-Rundung:** Temperaturen ganzzahlig gerundet; Niederschlag mit einer Nachkommastelle; Wind/Böen ganzzahlig.
- **Threshold = Max:** Wenn Threshold-Wert UND Threshold-Stunde exakt dem Tagesmaximum entsprechen, wird der Peak-Block `(max@h)` weggelassen (Details §5).
- **Priorität bei Truncation:** Thunderstorm > Wind/Gusts > Rain > Temperatur (siehe §6).

---

## 2. Token-Reihenfolge (fix)

```
{Name}: N D R PR W G TH: TH+: C HR:TH: Z: M: [SN SN24+ SFL AV WC] DBG
```

| Block | Tokens | Pflicht? |
|-------|--------|---------|
| Header | `{Name}:` | immer |
| Forecast | `N D R PR W G TH: TH+:` | immer (bei `-` als Null-Wert) |
| Confidence | `C` | nur wenn Provider Konfidenz liefert (Issue #121, v2.1) |
| Risks (Vigilance) | `HR:TH:` (zusammenhängend, kein Leerzeichen zwischen den beiden) | nur bei FR-Provider |
| Fire-Zonen | `Z: M:` | nur Korsika, weglassen wenn leer |
| Wintersport | `SN SN24+ SFL AV WC` | optional |
| Debug | `DBG[...]` | nur Dry-Run / Debug-Modus |

**Hinweis zu `HR:TH:`** — Das sind zwei separate Tokens, die ohne Leerzeichen aneinandergeschrieben werden (z.B. `HR:M@17TH:H@17` oder `HR:-TH:-`). Siehe §3.3 und §3.4.

---

## 3. Token-Definitionen

### 3.1 Header

| Token | Bedeutung | Beispiel |
|-------|-----------|----------|
| `{Name}:` | Etappen-/Location-Name (max 10 Zeichen, ASCII) oder mit km-Bereich | `Ballone:` oder `GR221 km0-11:` |

**Name-Truncation & km-Bereichs-Bewahrung (Issue #936):**
1. Falten **zuerst** — Umlaute ersetzen (ä→ae, ö→oe, ü→ue, ß→ss) und alle sonstigen
   Nicht-ASCII-Buchstaben transliterieren, siehe §1 und ADR-0022
   (`docs/adr/0022-ascii-faltung-via-anyascii.md`). Nicht faltbare Buchstaben werden
   zu `?`, nicht gelöscht. Erst danach kürzen (Issue #1253: „erst falten, dann
   kürzen" gilt durchgängig für alle Kanäle, nicht nur den Header).
2. Auf "km" prüfen im Namen. Wenn gefunden:
   - Prefix vor "km" auf **max. 10 Zeichen** kürzen.
   - **Kompletten km-Bereich** (z.B. `km0-11`) bewahren und anhängen.
   - Beispiel: `GR221 Mallorca km0-11` → `GR221 km0-11:` (Name gekürzt, km-Teil vollständig).
3. Wenn kein "km": Standard-Truncation auf 10 Zeichen.
4. Trailingde Leerzeichen und `:` entfernen.

**Implementierung:** `_sanitize_stage_name()` in `src/output/tokens/builder.py`.

### 3.2 Forecast-Tokens

| Token | Bedeutung | Quelle (DTO-Feld) | Beispiel |
|-------|-----------|-------------------|----------|
| `N{temp}` / `N-` | Nacht-Min °C, ganzzahlig — Wert AM letzten GEO-Punkt der Etappe (kein Min über mehrere Punkte) | `temp_min_c` aus DAILY_FORECAST des letzten Etappenpunkts | `N9` |
| `D{temp}` / `D-` | Tag-Max °C, ganzzahlig | Alle GEO-Punkte der Etappe, MAX über `temp_max_c` | `D24` |
| `R{mm}@{h}({max}@{h})` / `R-` | Regen Threshold@Stunde + Peak | Hourly `precip_1h_mm`, Threshold aus `config.rain_amount_threshold` | `R0.2@6(1.4@16)` |
| `PR{p}%@{h}({max}%@{h})` / `PR-` | Regenwahrscheinlichkeit Threshold + Peak (Issue #887: auch SMS via `pop_hourly` aus `agg.pop_max_pct` synthetisiert) | Hourly `pop_pct`, Threshold aus `config.rain_probability_threshold` | `PR20%@11(100%@17)` |
| `W{v}@{h}({max}@{h})` / `W-` | Wind km/h Threshold + Peak | Hourly `wind10m_kmh`, Threshold aus `config.wind_speed_threshold` | `W10@11(15@17)` |
| `G{v}@{h}({max}@{h})` / `G-` | Böen km/h Threshold + Peak | Hourly `gust_kmh`, Threshold aus `config.wind_gust_threshold` | `G20@11(30@17)` |
| `TH:{level}@{h}({max}@{h})` / `TH:-` | Gewitter der **berichteten** Etappe (M/H) | Hourly `dp.thunder_level` aus `seg.timeseries`, auf die Wanderzeit gefenstert | `TH:M@16(H@18)` |
| `TH+:{level}@{h}({max}@{h})` / `TH+:-` | Gewitter der Etappe **danach** | Folge-Etappe via `thunder_forecast["+1"]` (Level **und** Stunde) | `TH+:M@14(H@17)` |

**Report-relativ, nicht kalender-relativ (Issue #1275):** `TH:` und `TH+:` beziehen sich auf die
Etappe, über die der Report spricht — nicht auf „heute"/„morgen" im Kalendersinn. Im
**Morgen-Report** ist das heute (`TH:`) und morgen (`TH+:`), im **Abend-Report** morgen (`TH:`)
und übermorgen (`TH+:`). Die frühere absolute Lesart war falsch.

Levels für `TH`/`TH+`:
- `M` = med (Averses orageuses)
- `H` = high (Orages)
- `-` = none

> `LEVELS` (`src/output/tokens/metrics.py:14`) kennt zusätzlich `L`. Dieser Wert ist
> **unerreichbar**: `ThunderLevel` (`src/app/models.py:33-37`) hat kein LOW, und
> `openmeteo.py:524-538` liefert ausschließlich HIGH oder NONE (WMO 95/96/99). `L` bleibt nur
> aus Golden-Snapshot-Kompatibilität im Code stehen und ist kein Teil des Format-Vertrags.

**Threshold-Logik:** `R`, `PR`, `W`, `G`, `TH`, `TH+` zeigen den **ersten Zeitpunkt** im Tagesfenster, an dem der konfigurierte Threshold erreicht/überschritten wird, gefolgt vom **Tagesmaximum** in Klammern. Wenn kein Wert ≥ Threshold: Token ist `R-` / `W-` / etc.

**Threshold-Konfiguration (Issue #624):** Die Schwellwerte für `R`, `PR`, `W`, `G` sind pro Trip und Metrik im Trip-Editor (Wetter-Metriken-Tab) optional konfigurierbar über `MetricConfig.sms_threshold`. Leeres Feld → bisheriges fest eingebautes Standardverhalten (Fallback auf `DEFAULTS` in builder.py). E-Mail-Tabelle nutzt weiterhin das separate `display_thresholds`-Farbkonzept (nicht vereinheitlicht).

### 3.3 Risk-Tokens (Vigilance-Warnungen, nur Frankreich)

Die zwei Tokens bilden einen **zusammenhängenden Block** ohne Leerzeichen dazwischen:

| Token | Bedeutung | Quelle | Beispiel |
|-------|-----------|--------|----------|
| `HR:{level}@{h}` / `HR:-` | Heavy Rain Vigilance (Pluie-inondation) | Météo France `get_warning_full()` | `HR:M@17` |
| `TH:{level}@{h}` / `TH:-` | Thunderstorm Vigilance (Orages) | Météo France `get_warning_full()` | `TH:H@17` |

Levels:
- `L` = 1 (Gelb)
- `M` = 2 (Orange)
- `H` = 3 (Rot)
- `R` = 4 (Violett)
- `-` = keine Warnung

**Beispiel zusammen:** `HR:M@17TH:H@17` (kein Trennzeichen zwischen `HR:` und `TH:`) bzw. `HR:-TH:-` wenn keine Warnungen.

**Geographische Geltung:** Météo France Vigilance API funktioniert nur für Frankreich. Außerhalb FR werden beide Tokens **komplett weggelassen** (nicht als `-` ausgegeben).

### 3.4 Disambiguierung der zwei `TH:`-Tokens

Es gibt zwei `TH:`-Tokens mit unterschiedlicher Bedeutung. Disambiguierung erfolgt durch **Position** in der Token-Reihenfolge:

| Position | Bedeutung | Quelle |
|----------|-----------|--------|
| Zwischen `G` und `TH+:` | Forecast-Gewitter heute (Wettervorhersage) | Hourly Wetterdaten |
| Direkt nach `HR:` (kein Space) | Vigilance-Gewitterwarnung (offizielle Warnung) | Météo France Vigilance API |

Parser erkennen den Unterschied durch:
- Forecast-`TH:` ist von Leerzeichen umgeben
- Vigilance-`TH:` folgt **direkt** auf `HR:` ohne Leerzeichen

### 3.4b Confidence-Symbol `C` (v2.1, Issue #121)

Einzelnes Zeichen, das die tagesweise Worst-Case-Konfidenz der Wettervorhersage signalisiert. Position: **nach `TH+:`, vor `HR:`/Vigilance-Tokens**.

| Wert | Symbol | Bedeutung |
|------|--------|-----------|
| `confidence_pct_min >= 75` | `C+` | Sichere Vorhersage |
| `50 <= confidence_pct_min < 75` | `C~` | Mittlere Sicherheit |
| `confidence_pct_min < 50` | `C?` | Unsichere Vorhersage |
| `confidence_pct_min is None` | _(Token weggelassen)_ | Kein Provider-Support |

**GSM-7-konform** — `+`, `~`, `?` sind alle Standard-GSM-7-Zeichen.

Aggregation: `min()` der stündlichen `confidence_pct` über alle Segmente des Tages.

Beispiel mit niedriger Konfidenz: `Etappe: N12 D22 R0.5 W15 G25 C?`

### 3.5 Fire-Risk-Tokens (Korsika-spezifisch)

Optional, nur für Trips in Korsika ausgegeben. Quelle: `risque-prevention-incendie.fr` (täglicher JSON-Feed).

| Token | Bedeutung | Beispiel |
|-------|-----------|----------|
| `Z:HIGH{ids}` | Fire-Zone Risk Level 2 (HIGH) | `Z:HIGH208,217` |
| `MAX{ids}` | Fire-Zone Risk Level 3 (MAX) | `MAX209` |
| `M:{ids}` | Restricted Massifs (Zugangsbeschränkungen) | `M:3,5,9` |

Der vollständige Block wird als zusammenhängender Abschnitt nach den Vigilance-Tokens platziert:

```
Z:HIGH208,217 MAX209 M:3,5,9
```

Wenn keine relevanten Zonen/Massifs aktiv sind: **Block komplett weglassen** (kein `Z:-`).

**Geographische Geltung:** Nur ausgeben wenn `trip.country == "FR"` und mindestens eine GR20-Zone betroffen ist.

### 3.6 Wintersport-Tokens (optional)

| Token | Bedeutung | Quelle |
|-------|-----------|--------|
| `SN{cm}` | Schneehöhe gesamt | `snow_depth_cm` |
| `SN24+{cm}` | Neuschnee 24h | `snow_new_24h_cm` |
| `SFL{m}` | Schneefallgrenze | `snowfall_limit_m` |
| `AV{1-5}` | Lawinenstufe | `AvalancheReport.danger.level` |
| `WC{temp}` | Wind Chill | `wind_chill_c` |

Nur ausgeben wenn der Trip als Wintersport markiert ist (`trip.profile == "wintersport"`). Details siehe `docs/specs/wintersport_extension.md`.

### 3.7 Debug-Token

| Token | Bedeutung | Beispiel |
|-------|-----------|----------|
| `DBG[{provider} {confidence}]` | Provider-Auswahl + Konfidenz | `DBG[MET MED]` |

Nur in Dry-Run / Debug-Modus angehängt, ansonsten weggelassen.

---

## 4. Null-Repräsentation

| Token | Null-Form | Anmerkung |
|-------|-----------|-----------|
| `N` / `D` | `N-` / `D-` | Bei fehlenden Temperaturen |
| `R` / `PR` | `R-` / `PR-` | Bei fehlendem oder Sub-Threshold-Niederschlag |
| `W` / `G` | `W-` / `G-` | Bei fehlendem oder Sub-Threshold-Wind |
| `TH` / `TH+` | `TH:-` / `TH+:-` | Bei fehlendem oder Sub-Threshold-Gewitter |
| `HR` / `TH` (Vigilance) | `HR:-TH:-` | Bei keiner Vigilance-Warnung; immer paarweise |
| `Z` / `M` (Fire) | komplett weglassen | Kein `Z:-`, einfach Block entfernen |
| `SN`/`SN24`/`SFL`/`AV`/`WC` | komplett weglassen | Wintersport-Tokens nicht zwingend |
| `DBG` | komplett weglassen | Nur Debug-Modus |

---

## 5. Werte-Formate

### Temperaturen
- Ganzzahlig gerundet (z.B. 9.1 → `9`, 9.7 → `10`).
- Negative Vorzeichen erlaubt: `N-12`, `D-5`, `WC-22`.

### Niederschlag (mm)
- **Eine Nachkommastelle**, auch wenn die zweite `0` ist (z.B. `0.2`, `1.4`).
- Bei `0` Niederschlag: Token ist `R-` (nicht `R0.0`).

### Wind / Böen (km/h)
- Ganzzahlig.

### Wahrscheinlichkeit (%)
- Ganzzahlig (kein Dezimalzeichen).

### Stunden
- 0–23, ohne führende Null.

### Threshold == Max-Optimierung
- Wenn der Threshold-Wert exakt dem Tagesmaximum entspricht und beide am gleichen Zeitpunkt liegen, wird **nur der Threshold ausgegeben**, der `(max@h)`-Block entfällt. Beispiel: `W15@14` statt `W15@14(15@14)`.

---

## 6. Truncation-Strategie

Wenn die zusammengesetzte Token-Zeile >160 Zeichen ist, werden Tokens in dieser **Reihenfolge** entfernt:

1. `DBG[...]`
2. Wintersport-Tokens (`WC`, `AV`, `SFL`, `SN24+`, `SN`)
3. Fire-Block komplett (`Z:HIGH...`, `MAX...`, `M:...`)
4. Peak-Werte `(max@h)` (Threshold-Werte bleiben erhalten)
5. `PR` (Regenwahrscheinlichkeit)
6. `D`, `N` (Temperaturen)

`{Name}:` plus mindestens **ein** Risk- oder Wert-Token ist Pflicht. Wenn nach allen Truncation-Schritten immer noch >160 Zeichen: ValueError.

---

## 7. Pflicht-Tokens

- `{Name}:` ist immer im Output.
- Mindestens **ein** Wert-/Risk-Token ist Pflicht (z.B. `TH:M@14`, `W22@14`, `R0.2@6` oder `HR:M@17`).
- Reine Null-Zeilen (`Ballone: N- D- R- PR- W- G- TH:- TH+:-`) sind erlaubt und zeigen "alles ruhig".

---

## 8. Beispiele

Alle Beispiele sind ≤160 Zeichen.

### 8.1 Morning Report (Forecast, kein Risiko)
```
Ballone: N9 D16 R- PR10%@14(20%@17) W- G- TH:- TH+:-
```
**Länge:** 51 Zeichen.

### 8.2 Morning Report (mit Schwellenwerten)
```
Paliri: N8 D24 R0.2@6(1.4@16) PR20%@11(100%@17) W10@11(15@17) G20@11(30@17) TH:M@16(H@18) TH+:M@14(H@17)
```
**Länge:** 105 Zeichen.

### 8.3 Evening Report mit Vigilance + Fire-Block (Korsika)
```
Paliri: N8 D24 R0.2@6(1.4@16) PR20%@11(100%@17) W10@11(15@17) G20@11(30@17) TH:M@16(H@18) TH+:M@14(H@17) HR:M@17TH:H@17 Z:HIGH208 M:24
```
**Länge:** 134 Zeichen.

### 8.4 Update Report (nur kritische Werte)
```
Paliri: D24 G35@14(58@17) TH:H@15 HR:-TH:H@15
```
**Länge:** 46 Zeichen.

### 8.5 Wintersport
```
Arlberg: N-12 D-5 SN180 SN24+25 SFL1800 AV3 W45@12 G78@14(85@16) WC-22
```
**Länge:** 70 Zeichen.

### 8.6 Mit Debug
```
Monte: N15 D25 R- PR20%@14 W22@14(28@16) G35@14(48@17) TH:M@14 TH+:- DBG[MET MED]
```
**Länge:** 81 Zeichen.

### 8.7 Alles ruhig (alle Null)
```
Ballone: N9 D16 R- PR- W- G- TH:- TH+:-
```
**Länge:** 38 Zeichen.

---

## 9. Datenquellen-Mapping

| Token | Quelle | Aggregation | Status (gregor_zwanzig) |
|-------|--------|-------------|--------------------------|
| `N` | `SegmentWeatherSummary.temp_min_c` (Nacht-Segment) | Wert am letzten GEO-Punkt der Etappe (kein MIN über mehrere Punkte) | ✅ vorhanden |
| `D` | `SegmentWeatherSummary.temp_max_c` (Tag-Segment) | MAX über alle Geo-Punkte | ✅ vorhanden |
| `R` | `precip_1h_mm` hourly | Threshold + MAX | ✅ vorhanden |
| `PR` | `pop_pct` hourly | Threshold + MAX | ✅ vorhanden |
| `W` | `wind10m_kmh` hourly | Threshold + MAX | ✅ vorhanden |
| `G` | `gust_kmh` hourly | Threshold + MAX | ✅ vorhanden |
| `TH` | `thunder_level` hourly | Threshold + MAX (NONE<MED<HIGH) | ✅ vorhanden |
| `TH+` | Folgetag `thunder_level` | wie TH, aber +1 Tag | ✅ vorhanden |
| `HR` (Vigilance) | Météo France `get_warning_full()` | offizielle Warnung | ⚠️ Provider TODO |
| `TH` (Vigilance) | Météo France `get_warning_full()` | offizielle Warnung | ⚠️ Provider TODO |
| `Z`/`M` | `risque-prevention-incendie.fr` | tagesaktueller JSON | ⚠️ Provider TODO |
| `SN`/`SN24`/`SFL` | GeoSphere/SLF | siehe Wintersport-Spec | ⚠️ teilweise vorhanden |
| `AV` | `AvalancheReport.danger.level` | aus Lawinenbericht | ⚠️ Provider TODO |
| `WC` | `wind_chill_c` | berechnet | ⚠️ teilweise vorhanden |
| `DBG` | `source.chosen`, `source.confidence` | aus DebugBuffer | ✅ vorhanden |

Markierte TODOs sind separate Issues, nicht Teil dieser Spec.

---

## 10. Geographische Einschränkungen

| Token-Block | Geltung | Verhalten außerhalb |
|-------------|---------|--------------------|
| Forecast (N…TH+) | global | immer ausgeben |
| Vigilance (`HR`/`TH`) | nur Frankreich | komplett weglassen (kein `-`) |
| Fire (`Z`/`M`) | nur Korsika (FR) | komplett weglassen |
| Wintersport (SN…WC) | AT/CH/Tirol/Südtirol/Trentino | komplett weglassen, wenn Provider fehlt |

---

## 11. Single Source of Truth

Diese Token-Zeile ist die **einzige verbindliche Repräsentation** der Wetterzusammenfassung. Alle anderen Formate leiten sich daraus ab:

| Channel | Verwendung |
|---------|-----------|
| SMS / Satellit | 1:1 die Token-Zeile (≤160 Zeichen) |
| E-Mail Subject | Auszug: `{Etappe} – {ReportType} – {MainRisk} – D{val} W{val} G{val} TH:{level}` |
| E-Mail Body | Token-Zeile als erstes, danach human-readable Summary + Tabellen |
| Push-Notification | Auszug der Token-Zeile (Titel) + Long-Form (Body) |
| Debug-Log | Token-Zeile + DebugBuffer-Inhalt |

Implementationen, die SMS-Text und E-Mail-Subject getrennt erzeugen, sind als **Bug** zu betrachten.

---

## 12. Versionierung & Quellen

| Version | Datum | Änderung |
|---------|-------|----------|
| 1.0 | 2025-12-27 | Initiale Spec mit N, D, R, PR, W, G, TH, TH+, DBG |
| 2.0 | 2026-04-25 | Vigilance-Block (HR/TH), Fire-Block (Z/M), Wintersport-Sektion, Disambiguierungs-Regel, vollständiges Datenquellen-Mapping |
| 2.1 | 2026-05-15 | Confidence-Symbol `C` (Issue #121) — GSM-7-konformes `+`/`~`/`?` nach `TH+:` |
| 2.2 | 2026-05-31 | WL-Token für Großwetterlage (Issue #122) — `+`/`~`/`-` nach `C`, vor `HR:`; Truncation NACH `C` aber VOR `PR` |
| 2.3 | 2026-05-31 | WL-Token aus SMS entfernt (Issue #479) — `C+/C~/C?` deckt den Stabilitäts-Use-Case ab; WL-Block bleibt nur in der E-Mail erhalten, jetzt aus `min(confidence_pct_min)` der Folge-Etappen abgeleitet statt aus Z500-Ensemble-API |
| 2.4 | 2026-06-06 | Konfigurierbare Threshold pro Metrik (Issue #624) — `MetricConfig.sms_threshold` optional per Metrik in `display_config` (Trip-Editor), Fallback auf `DEFAULTS`; E-Mail-Tabelle bleibt separate Logik |
| 2.5 | 2026-06-26 | SMS PR-Token-Befüllung (Issue #887) — `_segments_to_normalized_forecast()` in `sms_trip.py` erzeugt synthetisches `pop_hourly` aus `agg.pop_max_pct`, damit SMS-Token `PR{p}%` nicht mehr leer bleibt |
| 2.6 | 2026-07-01 | km-Bereichs-Bewahrung in Header (Issue #936) — `_sanitize_stage_name()` erkennt `km`-Marker und bewahrt vollständigen km-Bereich (z.B. `km0-11`) statt ihn nach 10 Zeichen abzuschneiden; Prefix gekürzt, km-Teil vollständig |
| 2.7 | 2026-07-13 | Faltungs-Konvention auf alle Schriften erweitert (Issue #1253) — bisher nur Umlaute; einzige Quelle jetzt `fold_ascii()` in `src/utils/ascii_fold.py` (ADR-0022: `anyascii` + deutsche Digraph-Map + zeichenweiser `?`-Guard gegen stille Buchstaben-Löschung), gilt jetzt durchgängig „erst falten, dann kürzen" auch im SMS-Titelzeilen-Pfad (`_sms_stage_prefix`) |
| 2.8 | 2026-07-16 | `TH+`-Datenquelle korrigiert (Issue #1275) — aggregiert jetzt über ALLE Segmente der tatsächlichen Folge-Etappe (statt nur das letzte Segment der heutigen Etappe zu prüfen) und nutzt dieselbe Fetch-/Aggregations-Kette wie die E-Mail-Outlook-Tabelle (`_build_stage_trend()`); stimmt dadurch garantiert mit deren Wert überein |

**Quellen für v2.0:**
- Vorgänger-Repo `henemm/weather_email_autobot`:
  - `requests/morning-evening-refactor.md` (HR + Vigilance-TH)
  - `src/utils/risk_block_formatter.py` (Z + M)
  - `src/fire/risk_block_formatter.py` (HIGH/MAX-Logik)
- Bestehende gregor-Specs:
  - `docs/specs/wintersport_extension.md` §5 (Wintersport-Tokens)
  - `docs/reference/renderer_email_spec.md` §2 (Token line is single source of truth)
