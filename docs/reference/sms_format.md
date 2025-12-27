


# SMS Format Specification (Gregor Zwanzig MVP)

This document defines the compact SMS output format for weather risk reports.  
Goal: **≤160 characters**, GSM-7 only, unambiguous, and consistent across all report types.

---

## Principles
- **Max length:** 160 characters (GSM-7 normalized).
- **Character set:** ASCII/GSM-7 only (Umlauts replaced: ä→ae, ö→oe, ü→ue, ß→ss).
- **Time format:** Local time, hour only (0–23, no leading zeros).
- **Tokens:** Short, uppercase English identifiers.
- **Separators:** Single space between tokens.
- **Priority:** Thunderstorm > Wind/Gusts > Rain > Temperature.

---

## Token Formats (MVP)

- `N{temp}` → Night minimum temperature (°C, integer).
- `D{temp}` → Day maximum temperature (°C, integer).
- `R{mm}` → Rain amount in mm, or `R-` if none.
- `PR{p}%@{h}` → Rain probability in % at hour `h`.
- `W{value}@{h}({max}@{h})` → Wind speed [km/h], with peak at hour `h`.
- `G{value}@{h}({max}@{h})` → Gusts [km/h], with peak at hour `h`.
- `TH:{level}@{h}` → Thunderstorm level (L/M/H) at hour `h`.
- `TH+:{level}@{h}` → Thunderstorm forecast tomorrow.
- `DBG[{provider} {confidence}]` → Optional debug tag, only if space allows.

**Null values:**  
- Rain: `R-` or `PR-`.  
- Thunderstorm: `TH:-`.  

---

## Formatting Rules
- All tokens separated by a single space.  
- Etappe/Location name (max 10 chars) at the start, followed by a colon.  
- Always include time with W/G tokens, even for the first value.  
- No units (°C, km/h, mm) in text – implied by token.  
- Example: `W20@5(22@5)` means 20 km/h wind at 05:00, peak 22 km/h at 05:00.

---

## Examples

### Evening Report
```
Monte: N15 D18 R- PR30%@5 W20@5(22@5) G43@17(58@19) TH:M@0 TH+:H@1 DBG[MET MED]
```

### Morning Report
```
StageX: D27 R2@14 PR60%@15 W12@12(24@16) G30@14(45@17) TH:H@15
```

### Update Report
```
Pass: Update TH:H@16 R5@16 PR70%@16 G40@16 DBG[MOSMIX HIGH]
```

---

## Budget Strategy
1. Generate tokens in priority order (TH, W/G, R/PR, D/N).  
2. Append until 160 chars reached.  
3. If space remains, append `DBG[...]`.  
4. If still over budget, drop lowest-priority tokens (N, D, PR).  