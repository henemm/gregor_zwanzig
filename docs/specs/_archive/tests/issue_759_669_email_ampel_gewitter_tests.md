---
entity_id: issue_759_669_email_ampel_gewitter_tests
type: tests
created: 2026-06-12
updated: 2026-06-12
status: draft
version: "1.0"
tags: [tests, email, renderer, ampel, gewitter, issue-759, issue-669]
parent: issue_759_669_email_ampel_gewitter
phase: phase5_tdd_red
---

# #759 (Ampel-Metriken) + #669 (Gewitter-Badge): Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_759_669_email_ampel_gewitter.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.
Keine Mocks — reale Render-Aufrufe der E-Mail-Renderer mit konstruierten
Wetterdaten; AC-11 ist die Staging-IMAP-Acceptance-Stage.

Parent-Spec: `docs/specs/modules/issue_759_669_email_ampel_gewitter.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_759_email_ampel.py` (NEU)
- **File:** `tests/tdd/test_issue_669_outlook_thunder_badge.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_issue759_wind_ampel_dot_four_levels` | AC-1 | Wind-Zellen (20/40/60/75) → 🟢/🟡/🟠/🔴 im HTML, keine km/h-Zahl |
| `test_issue759_gust_ampel_red_boundary_80` | AC-2 | Böen 79→🟠, 80→🔴 (rote Stufe ab ≥80, Eckwert bewahrt) |
| `test_issue759_precip_ampel_dot_four_levels` | AC-3 | Regen-Zellen (0/2/6/12) → 🟢/🟡/🟠/🔴 (Schwellen 1/5/10) |
| `test_issue759_pop_ampel_dot_four_levels` | AC-4 | pop-Zellen (10/40/65/85) → 🟢/🟡/🟠/🔴 (Schwellen 30/60/80) |
| `test_issue759_plain_text_stays_numeric_ascii` | AC-5 | Plain-Text-Render: numerisch, kein Ampel-Emoji, `isascii()` |
| `test_issue759_ampel_legend_present` | AC-6 | HTML-Mail enthält Ampel-Legende mit allen vier Emojis + Labels |
| `test_issue669_thunder_badge_time_window` | AC-7 | Folge-Etappe MED@15(HIGH@16) → „⚡ Gewitter möglich 15:00–16:00", rot |
| `test_issue669_thunder_badge_single_hour` | AC-8 | Single-Hour-Thunder → „⚡ Gewitter möglich 14:00" (kein Bereich) |
| `test_issue669_no_badge_without_thunder` | AC-9 | Keine Gewitter-Etappe → kein „Gewitter möglich"-Badge, kein leerer Platzhalter |
| `test_issue669_other_outlook_columns_unchanged` | AC-10 | TEMP/REGEN/WIND-Zellen des Ausblicks unverändert vorhanden |
| `test_issue669_badge_not_duplicated_with_forecast` | AC-7-Härtung | Badge genau einmal in &lt;td&gt; (Tabelle); thunder_forecast-Vorschau-Block bleibt intakt (F001 Regression) |

## Test-Ausführung

```bash
uv run pytest tests/tdd/test_issue_759_email_ampel.py tests/tdd/test_issue_669_outlook_thunder_badge.py -v
```

RED-Erwartung: Alle Tests schlagen vor der Implementierung fehl (Ampelpunkte
fehlen / Badge fehlt). GREEN nach Implementierung in `metric_catalog.py`,
`helpers.py`, `html.py`.
