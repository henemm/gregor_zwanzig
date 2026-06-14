# Renderer Specification – E-Mail Reports

This document defines how E-Mail reports are generated in Gregor Zwanzig.

**Acceptance Validators (seit Issue #733):**
- **Trip-Briefing-Mail** (beide Formate: `full` HTML / `compact` Nur-Text): `.claude/hooks/briefing_mail_validator.py` (dispatcht auf `X-GZ-Mail-Type` + `X-GZ-Format` Header)
- **Orts-Vergleich-Mail**: `.claude/hooks/email_spec_validator.py` (fest auf Vergleichstabelle/Winner-Box verdrahtet)

Siehe CLAUDE.md für Scope-Details und Pflicht-Gate-Dokumentation.

---

## Principles
- E-Mail reports are **long-form**, human-friendly, but must remain concise and structured.
- They always include the **compact token line** (identical to the SMS).
- They may add **human-readable summaries** and **tables per stage/etappen points**.
- Debug information is appended at the end in plain text, identical to console output.
- Outgoing mails carry marker headers (`X-GZ-Mail-Type`, `X-GZ-Format`) for deterministic routing to acceptance validators.

---

## Layout

### 1) Header
- Subject format: `{Etappe} – {ReportType} – {MainRisk} – {KeyValues}`
- `{ReportType}`: `morning`, `evening`, or `update`.
- `{MainRisk}`: the highest risk detected (e.g., Thunderstorm, Wind). If none, omit.
- `{KeyValues}`: selected compact tokens (e.g. `D25`, `W22`, `G35`, `R-`, `TH:M@14`), to give immediate overview.
- Example: `Monte – evening – Thunderstorm – D25 W22 G35 TH:M@14`

Note: "Gregor Zwanzig" appears as the sender name and does not need to be repeated in the subject.

### 2) Token Line
- First block of the body.
- Exact 1:1 copy of the SMS token line.
- **Format-Definition:** siehe [`docs/reference/sms_format.md`](sms_format.md) (v2.0) — Single Source of Truth.
- Beispiel (mit Vigilance-Block und Fire-Block für Korsika):
  ```
  Paliri: N8 D24 R0.2@6(1.4@16) PR20%@11(100%@17) W10@11(15@17) G20@11(30@17) TH:M@16(H@18) TH+:M@14(H@17) HR:M@17TH:H@17 Z:HIGH208 M:24
  ```
- Beispiel (ohne Vigilance/Fire, internationaler Trip):
  ```
  Monte: N15 D25 R- PR20%@14 W22@14(28@16) G35@14(48@17) TH:M@14 TH+:- DBG[MET MED]
  ```

### 3) Human-Friendly Summary
- Short list (dl) of the same values in words, e.g.:
  - Temperatur: Nacht-Min 15°C · Tages-Max 25°C
  - Regen: Menge –, Wahrscheinlichkeit 20% @14 Uhr
  - Wind: 22 km/h @14 Uhr, Böen 35 km/h @14 Uhr (Peak 48 km/h @19 Uhr)
  - Gewitter: Level M @14 Uhr

### 4) Stage Tables
- Each stage/etappen point (from ROUTE file) is listed with time-aligned forecasts.
- Table columns:
  - Time (with **leading zeros**, e.g. `05:00`, `14:00`, `19:00`)
  - Point (name or ID)
  - T (°C), W (km/h), G (km/h), R (mm), PR (%), TH (L/M/H), Symbol
  - **(ENTFERNT ab Issue #715)** Sicherheit (Spalte nicht mehr wählbar) — Vorhersage-Verlässlichkeit ist keine pro-Etappe wählbare Metrik mehr. Die Verlässlichkeit wird nur noch als Klartext-Hinweis (Abs. 4a) und SMS-Symbol (C+/C~/C?) dargestellt.
- Example (nach Issue #715 ohne Sicherheit-Spalte):

  | Time  | Point | T | W | G | R | PR | TH | Symbol     |
  |-------|-------|---|---|---|---|----|----|------------|
  | 14:00 | Monte |25 |22 |35 | 0 | 20 | M  | lightrain  |
  | 16:00 | Pass  |24 |28 |48 | 0 | 20 | M  | cloudy     |

#### 4a) Klartext-Hinweis bei niedriger Konfidenz (Issue #121, ab Issue #715 einziger Confidence-Output in Tabelle)

Im E-Mail-Body wird ein Klartext-Hinweis ausgegeben, wenn an mindestens einer Stunde in T+0..72h `confidence_pct < 60` liegt. Dies ist der **einzige visuelle Confidence-Hinweis in der E-Mail-Tabelle** (Spalte wurde mit Issue #715 entfernt; Verlässlichkeit erscheint nur noch als Textblock und SMS-Token). Andernfalls erscheint **kein** Hinweis (Visual-Noise-Vermeidung).

- Format: `"Ab {Wochentag} nimmt die Unsicherheit zu (Temperatur-Spreizung {N} °C)."`
- Wochentag: erster betroffener Tag in T+0..72h (Deutsch: Montag–Sonntag).
- Spread: `max(spread_t2m_k)` über alle unsicheren Stunden dieses Tages, gerundet auf ganze Kelvin/°C.
- HTML: `<p class="confidence-hint">…</p>` in einem gelb hinterlegten Block, positioniert zwischen `summary` und `changes`.
- Plain: eigene Zeile mit Leerzeile davor/dahinter, gleicher Position.

### 5) Debug Block
- Always appended at the end, in `<pre>` formatted text.
- Content identical to console output.
- Must include:
  - `cfg.path`
  - `report` (morning/evening/update)
  - `channel` (console/email/sms)
  - `debug` flag
  - `dry_run` flag
  - `source.decision`
  - `source.chosen`
  - `source.confidence`
  - `source.coords`
  - `source.meta` (provider, run, model)
  - token line used
- Example:
  ```
  DBG[MET MED]
  source.decision: MOSMIX rejected (dist=20.0km, delta_h=220m, land_sea_match=false)
  source.chosen: MET
  source.confidence: MED (62)
  source.coords: 54.29N,10.90E
  source.meta: run=2025-08-28T19:12Z, model=ECMWF
  tokens: Monte: N15 D25 R- PR20%@14 W22@14(28@16) G35@14(48@17) TH:M@14 DBG[MET MED]
  ```

---

## Rules
- **Token line** is the single source of truth → all other representations must derive from it.
- **Debug block** must be identical between console and email.
- **Tables** may extend beyond 160 chars (no SMS limit).
- **Times** in tables use **leading zeros** for clarity.
- All numbers are integers unless explicitly defined as float (e.g. rainfall `R`).

---

## Marker Headers and Validation Routing (seit Issue #733)

`build_mime_message()` in `src/outputs/email.py` setzt optionale Marker-Header zur deterministischen Klassifikation:

### Header-Format

```
X-GZ-Mail-Type: trip-briefing | compare
X-GZ-Format:    full | compact
```

### Routing

| Mail-Typ | Format | Quelle | Validator |
|----------|--------|--------|-----------|
| `trip-briefing` | `full` | `trip_report_scheduler.py` (Briefing-Versand) | `.claude/hooks/briefing_mail_validator.py` (AC-1/4) |
| `trip-briefing` | `compact` | `trip_report_scheduler.py` (compact-Renderer seit #722) | `.claude/hooks/briefing_mail_validator.py` (AC-2/6) |
| `compare` | `full` | `src/app/cli.py` (Compare-Wizard Versand) | `.claude/hooks/email_spec_validator.py` (AC-3) |

### Validierungslogik

- **`briefing_mail_validator.py`** prüft Trip-Briefing-Mails format-spezifisch:
  - `trip-briefing/full`: multipart/alternative, HTML + Plain Parts, ≥1 sequenzielle Stundentabelle, Werte selbst-konsistent
  - `trip-briefing/compact`: single text/plain, 7bit, isascii, < 2 KB, Kopf + Metriken + Ausblick + Footer (keine Stundentabelle)
  - `compare`-getaggte Mails: sauberes No-Op (Exit 0, falscher Validator)

- **`email_spec_validator.py`** prüft Orts-Vergleich-Mails (Vergleichstabelle, Winner-Box, min-locations). Für andere Mail-Typen nicht zuständig.

**Acceptance Gating:** Nur Exit 0 der entsprechenden Validator erlaubt „E2E Test bestanden".

---

## Metric Display Contract (seit Issue #814)

### Einfach (use_friendly_format=True) vs. Roh (use_friendly_format=False)

Der vollständige Vertrag aller Wetter-Metriken in der Briefing-Mail wird hier **einmalig** festgelegt.
Die **alleinige Quelle** der Anzeige-Entscheidung ist `use_friendly_format` in `MetricConfig`.

**Single Source of Truth: Metrik-spezifische Anzeige-Regeln**

| Kategorie | Metriken | Einfach (HTML) | Einfach (Plain) | Roh (HTML) | Roh (Plain) | Notiz |
|---|---|---|---|---|---|---|
| **Severity-Ampel** 🟢🟡🟠🔴 | wind, gust, precip, pop, cape | Ampelpunkt nach `display_thresholds` | Zahl + Einheit | Zahl + Einheit, **keine Markierung** | Zahl + Einheit | Nur HTML hat Ampel; Plain & Roh immer numerisch |
| **Wetterbild-Piktogramm** | cloud_total, cloud_low, cloud_mid, cloud_high, sunshine | Emoji (☀️🌤️⛅🌥️☁️) | Emoji (gleich) | Zahl | Zahl | Emoji in Einfach (HTML+Plain), Zahl in Roh — unverändert seit #435 |
| **Gewitter-Symbol** | thunder | ⚡ (MED=„⚡ mögl.", HIGH=„⚡⚡", NONE=„–") | ⚡ (gleiche Symbole) | deutsches Wort (kein / mögl. / hoch) | deutsches Wort (kein / mögl. / hoch) | ⚡-Symbol in Einfach (HTML+Plain); Roh immer deutsches Wort |
| **Zahl (kein Modus-Unterschied)** | visibility, temperature, wind_chill, dewpoint, humidity, pressure, uv_index, freezing_level, snowfall_limit, snow_depth, fresh_snow, precip_type | Zahl + Einheit | Zahl + Einheit | Zahl + Einheit | Zahl + Einheit | Unverändert in beiden Modi |

### Best-Practice-Schwellen (Ampelpunkte für Severity-Metriken)

| Metrik | 🟡 (Gelb) | 🟠 (Orange) | 🔴 (Rot) | Basis |
|---|---|---|---|---|
| wind (km/h) | 30 | 50 | 70 | Beaufort 5/7/8–9 |
| gust (km/h) | 50 | 65 | 80 | Böenklassifikation |
| precip (mm/h) | 1 | 5 | 10 | Regenintensität leicht/mäßig/stark |
| pop (%) | 30 | 60 | 80 | Niederschlagswahrscheinlichkeit |
| cape (J/kg) | 1000 | 2500 | 3500 | Standard-Konvektionsskala (ersetzt seit #814 fest verdrahtete Leiter 300/1000/2000) |

### Visibility wird bewusst NICHT ampeliert

Echte Wetterdaten zeigen: Median 16–54 km, ≥10 km in 90–100 % aller Stunden, <1 km (Nebel) ~0 %.
Eine Ampel wäre dauergrün und wertlos. Die nackte km-Zahl trägt mehr Information.
Ein echter Nebel-/Diesigkeits-Wächter gehört in die Alarm-Ebene (Folge-Issue nach #814).

### Implementierungs-Hinweis: „Roh ist Roh"

Im Roh-Modus gibt es **bei keiner Metrik** inline-Farb- oder Hintergrund-Markierungen
(insbesondere nicht Gelb-Highlight bei CAPE oder Orange-Highlight bei Sicht).
Alle Roh-Ausgaben sind numerisch/textlich ohne Styling.