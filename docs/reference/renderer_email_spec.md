# Renderer Specification – E-Mail Reports

This document defines how E-Mail reports are generated in Gregor Zwanzig.

---

## Principles
- E-Mail reports are **long-form**, human-friendly, but must remain concise and structured.
- They always include the **compact token line** (identical to the SMS).
- They may add **human-readable summaries** and **tables per stage/etappen points**.
- Debug information is appended at the end in plain text, identical to console output.

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
- Example:  
  ```
  Monte: N15 D25 R- PR20%@14 W22@14(28@16) G35@14(48@17) TH:M@14 DBG[MET MED]
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
- Example:

  | Time  | Point | T | W | G | R | PR | TH | Symbol     |
  |-------|-------|---|---|---|---|----|----|------------|
  | 14:00 | Monte |25 |22 |35 | 0 | 20 | M  | lightrain |
  | 16:00 | Pass  |24 |28 |48 | 0 | 20 | M  | cloudy    |

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