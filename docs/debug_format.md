


# Debug Format Specification

This document defines the exact format of debug output in Gregor Zwanzig.  
Debug output must be identical between **console** and **email** (plain text block at the end of the report).

---

## Principles
- **Consistency**: Console and Email debug output must be byte-identical.
- **Readability**: Plain text, monospaced, no colors or ANSI escape codes.
- **Completeness**: All inputs and decisions leading to the report must be traceable.
- **Chronological order**: Steps are logged in the order they are executed.

---

## Mandatory Keys (in order)

1. `cfg.path` → Path to config file used (or `default` if none).
2. `report` → Type of report (`morning`, `evening`, `update`).
3. `channel` → Output channel (`console`, `email`, `sms`).
4. `debug` → Debug flag status (`true`/`false`).
5. `dry_run` → Dry-run flag status (`true`/`false`).
6. `source.decision` → Explanation why a provider was accepted/rejected.
7. `source.chosen` → Chosen provider.
8. `source.confidence` → Confidence score + band (HIGH/MED/LOW).
9. `source.coords` → Latitude/Longitude of query point.
10. `source.meta` → Provider run meta (provider, run time, model).
11. `tokens` → The exact SMS token line generated.
12. `summary` → Human-readable summary (same as in email body).
13. `risks` → List of risk assessments applied (JSON-like, one per line).
14. `tables` → Optional note on table generation (etappen values included).

---

## Example Output
```
cfg.path: /etc/gregor_zwanzig/config.ini
report: evening
channel: email
debug: true
dry_run: false
source.decision: MOSMIX rejected (dist=20.0km, delta_h=220m, land_sea_match=false)
source.chosen: MET
source.confidence: MED (62)
source.coords: 54.29N, 10.90E
source.meta: provider=MET, run=2025-08-28T19:12Z, model=ECMWF
tokens: Monte: N15 D25 R- PR20%@14 W22@14(28@16) G35@14(48@17) TH:M@14 DBG[MET MED]
summary: Tomorrow max 25°C, light rain, wind 22 km/h, thunderstorm risk MED @14h.
risks: {\"type\":\"thunderstorm\",\"level\":\"MED\",\"from\":\"2025-08-28T14:00Z\"}
risks: {\"type\":\"wind\",\"level\":\"moderate\",\"gust_kmh\":48,\"from\":\"2025-08-28T16:00Z\"}
tables: 2 stages included (Monte, Pass)
```

---

## Notes
- Debug block is always appended at the very end of the report (after tables).
- For SMS reports, only the compact token line (`tokens`) and optional short DBG tag are included, not the full debug.