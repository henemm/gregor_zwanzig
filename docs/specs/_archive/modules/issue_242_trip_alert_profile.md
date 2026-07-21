---
entity_id: issue_242_trip_alert_profile
type: module
created: 2026-05-17
updated: 2026-05-17
status: draft
version: 1.0.0
tags: [email, activity-profile, trip-alert, issue-242, epic-236]
parent: epic_236_email_design_system
phase: phase3_spec
---

<!-- Issue #242 — Trip-Alert-Mail: ActivityProfile durchreichen (Epic #236 Sub-Issue 4) -->

# Issue #242 — Trip-Alert-Mail: ActivityProfile durchreichen

## Approval

- [ ] Approved

## Zweck

`src/services/trip_alert.py` ruft `format_email` heute ohne `profile`-kwarg auf — jeder Trip-Alert fällt damit auf die ALLGEMEIN-Signatur zurück, obwohl die Pipeline seit #241 das Profil sofort visualisieren könnte. Ein einziger zusätzlicher kwarg (`profile=trip.aggregation.profile`) reicht aus, damit Trip-Alerts denselben Profil-Marker wie Trip-Briefings tragen (Akzentfarbe + Eyebrow + Icon im Header, Prefix-Zeile im Plain-Text).

Sub-Issue 4 von Epic #236.

## Kontext

Setzt voraus:
- **#241** (`issue_241_email_profile_pipeline`) — Pipeline-Durchreichung von `ActivityProfile`, profil-spezifischer Header + Eyebrow

Die gesamte Render-Infrastruktur (Helper `profile_signature.py`, Header-Markup, Plain-Prefix) existiert bereits. Diese Spec ergänzt nur die fehlende Aufrufstelle.

## Quelle / Source

**Geänderte Dateien:**
- `src/services/trip_alert.py` — `format_email`-Call ergänzt `profile=trip.aggregation.profile`

**Tests:**
- `tests/tdd/test_trip_alert_profile.py` (NEU) — Source-Inspection + In-Process-Render

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/profile.py::ActivityProfile` | Enum | Profil-Wert |
| `src/app/trip.py::AggregationConfig.profile` | Datenfeld | Quelle für den Wert |
| `src/formatters/trip_report.py::format_email()` | Funktion | Empfänger des `profile`-kwargs (seit #241) |
| `src/output/renderers/email/profile_signature.py` | Modul (#241) | Helper, bereits live |

## Implementation Details

### Einzige Code-Änderung

**`src/services/trip_alert.py:~405`** — bestehender Call:

```python
report = self._formatter.format_email(
    segments=weather,
    trip_name=trip.name,
    report_type="alert",
    display_config=trip.display_config,
    changes=changes,
)
```

wird zu:

```python
report = self._formatter.format_email(
    segments=weather,
    trip_name=trip.name,
    report_type="alert",
    display_config=trip.display_config,
    changes=changes,
    profile=trip.aggregation.profile,
)
```

### LoC-Budget

| Datei | Δ LoC |
|-------|--------|
| `src/services/trip_alert.py` | +1 |
| `tests/tdd/test_trip_alert_profile.py` (neu) | +~25 |
| `docs/specs/modules/issue_242_trip_alert_profile.md` (neu, Doku) | 0 |
| **Gesamt Code** | **~26 LoC** |

Weit unter 250er-Limit.

## Expected Behavior

- **Input:** Trip-Alert wird ausgelöst (Wetteränderung erkannt) für einen Trip mit beliebigem `aggregation.profile`
- **Output:** Versendete Alert-Mail enthält im Header den profilspezifischen Akzent (`#4a7fb5` / `#3a7d44` / `#c45a2a` / `#6b675c`) und Eyebrow-Block (`❄ Wintersport` / `🥾 Wandern` / `🏔 Sommer-Trekking` / `◯ Allgemein`); Plain-Text-Variante mit Prefix-Zeile
- **Side effects:** Keine — pure Durchreichung eines bereits existierenden Wertes

## Acceptance Criteria

- **AC-1:** Given `src/services/trip_alert.py` / When der Quelltext nach `profile=trip.aggregation.profile` gegrept wird / Then findet sich genau dieser Substring im Aufruf von `format_email` (Source-Inspection, ohne Mocks)
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Trip mit `aggregation.profile = WINTERSPORT` / When ein Alert-Report über `TripReportFormatter.format_email(report_type="alert", profile=WINTERSPORT, ...)` gerendert wird / Then enthält `report.email_html` den Hex `#4a7fb5` und das Label `Wintersport`
  - Test: (populated after /tdd-red)

- **AC-3:** Given `tests/tdd/test_email_profile_pipeline.py`, `tests/tdd/test_email_design_tokens.py`, `tests/unit/test_renderers_email.py` / When diese Suiten ohne Änderungen ausgeführt werden / Then bleiben alle 52 Tests grün (keine Regression)
  - Test: (populated after /tdd-red)

## Known Limitations

- **Real-Gmail-Test deferred** — Gmail→Stalwart-Relay-Infra-Störung aus #240 weiterhin aktiv (MQ 20834). In-Process-Render-Verifikation als Ersatz.
- **Default WINTERSPORT** in `AggregationConfig.profile` — bestehende Trips ohne explizites Profil bekommen Wintersport-Akzent für Alerts. Konsistent mit Briefing-Verhalten seit #241.

## Out of Scope

- **Inhalt** der Alert-Mail (welche Daten, welcher Wortlaut, Block-Reihenfolge)
- **Refactor** von `trip_alert.py`
- **Service-Error-Mail** (Sub-Issue 5 von Epic #236)
- **Inbound-Reply-Mail** (Sub-Issue 6)
- **Password-Reset-Mail** (Sub-Issue 7)
- **Welcome / Subscription-Confirmation-Mail** (Sub-Issue 8)

## Risiken

1. **`format_email`-Signatur könnte sich noch ändern** — sehr unwahrscheinlich, da seit #241 live + getestet.
2. **`trip.aggregation` ist None-safe** — `AggregationConfig` hat einen Default (`field()`), `profile` defaultet auf WINTERSPORT — kein AttributeError zu erwarten.

## Tests / Verifikation

- **Source-Inspection** (analog #241 AC-5): Substring-Check `"profile=trip.aggregation.profile"` im Quelltext.
- **In-Process-Render**: TripReportFormatter mit `report_type="alert"` + `profile=ActivityProfile.WINTERSPORT` → HTML enthält Hex + Eyebrow.
- **Bestehende Suiten** bleiben grün (Backward-Kompat-Check).

## Changelog

- 2026-05-17: Initial spec (Epic #236 / Sub-Issue 4). Setzt #241 voraus.
