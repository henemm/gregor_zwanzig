# Context: feat-2475-verbrauch-je-nutzer

## Request Summary
S4 von #2150 (Issue #2475): Der Open-Meteo-Verbrauch je Nutzer soll sichtbar werden — Grundlage für #1702 (Kostenstelle) und Nachweis, wer das Kontingent verbraucht.

## Messbefund (origin/main 63d611a5)
- Pro-Nutzer-Zähler liegt seit #2387 unter `data/users/<uid>/diagnostics/forecast_budget.json`, Form `{"date","calls":{"openmeteo":N}}` (`src/services/forecast_budget.py:152-156, 313-328`). Cache-Hits/-Misses stehen NUR in der globalen Datei, nicht je Nutzer.
- Go liest nur die globale Datei (`internal/scheduler/forecast_budget_health.go:125`). `/api/scheduler/status` → Block `forecast_budget` zeigt nur Aggregate.
- Fairer Anteil = `DAILY_BUDGET / max(N,1)`, N = Länge `active_users` der globalen Datei (`forecast_budget.py:230-268`). Go hat keine Kopie dieser Rechnung (nur Display-Spiegel der Schwellen).

## Konflikt mit ADR-0075 Punkt 5
ADR-0075 (Pt. 5) + Schutztest `internal/scheduler/forecast_budget_user_privacy_test.go` verbieten Nutzerkennungen im Status-Endpunkt, Begründung „ohne Anmeldung erreichbar". Diese Prämisse ist seit #2155 S2 überholt (Status nur mit `X-GZ-Status-Token`, `internal/router/router.go:269-272`) — der Endpunkt bleibt aber ein Maschinen-/Monitoring-Endpunkt (check-gregor20.sh, BetterStack), das Token liegt in Skripten.
Ticket-Wortlaut verlangt „im Scheduler-Status sichtbar".

## Lösungsraum
| Option | Wirkung | Bewertung |
|---|---|---|
| A) Kennungen in `/api/scheduler/status` | Ticket-Wortlaut, aber bricht ADR-0075 Pt.5 + Schutztest; Kennungen im Monitoring-Pfad | verworfen |
| B) Anonyme Kennzahlen im Status (Anzahl aktiver Töpfe, fairer Anteil, größter Nutzeranteil, Anzahl über fairem Anteil) | ADR-konform („Anzahl statt Liste" in Spec #2387 ausdrücklich als Folge-Scheibe vorgesehen), kein Leck | Teil der Lösung |
| C) Verbrauch je Nutzer im Admin-API `GET /api/admin/users` (`requireAdmin`, `internal/handler/admin_users.go`: `AdminUser`-DTO, hat bereits `LastTripReportRun` je Nutzer, Vertrag „alle Felder immer da") | Kennungen nur für Admin, Admin-UI (`frontend/src/routes/admin/+page.svelte`, #2155 S4) kann es anzeigen; Grundlage #1702 | Teil der Lösung |

Empfehlung: **B + C**. ADR-0075 Pt. 5 wird präzisiert (nicht abgelöst): Nutzerkennungen weiter nie im Status-Endpunkt; Verbrauch je Nutzer nur hinter Admin-Auth. Der Schutztest bleibt unverändert grün.

## Related Files
| File | Relevanz |
|---|---|
| `internal/scheduler/forecast_budget_health.go` | Snapshot global; neue anonyme Kennzahlen + Nutzer-Lesefunktion |
| `internal/scheduler/forecast_budget_user_privacy_test.go` | Schutztest, darf NICHT brechen |
| `internal/scheduler/scheduler.go:1227` | Status-Block `forecast_budget` |
| `internal/handler/admin_users.go` | `AdminUser`-DTO + Liste; Muster `LastTripReportRun` |
| `internal/scheduler/briefing_health.go:253` | Muster `Glob users/*/diagnostics/…` |
| `frontend/src/routes/admin/+page.svelte` | Admin-UI (#2155 S4), Anzeige-Spalte |
| `src/services/forecast_budget.py` | Schreibformat (nicht ändern) |
| `docs/adr/0075-forecast-budget-fairness-je-nutzer.md`, `docs/specs/modules/forecast_budget_je_nutzer.md` | ADR/Spec S1 |
| `docs/specs/modules/admin_rolle_s3_admin_api.md`, `admin_ui_s4.md` | Verträge Admin-API/UI |

## Existing Patterns
- Go liest Python-Zählerdateien direkt, fail-soft („unavailable"), Stale-Date → 0 (`forecastBudgetSnapshot`).
- `s.store.DataDir` + `users/<uid>/diagnostics/`; Nutzer-ID nur über `store.ValidUserID` auflösen (Path-Traversal).

## Dependencies / Dependents
- Upstream: Python schreibt die Dateien; `TestForecastBudgetConstantsMatchPython` hält Konstanten synchron.
- Downstream: `/api/admin/users`-Konsumenten (Admin-UI + Test `admin_seite_render_und_dialogfluss.test.ts`), check-gregor20.sh liest den Status-Block (nur additive Felder erlaubt).

## Risks & Considerations
- Additive Felder im Status/Admin-DTO: Vertrag „alle Felder immer da" einhalten, `docs/reference/api_contract.md` nachziehen.
- Kein Schreibzugriff auf Persistenz, Schema-Backup-Hook nicht betroffen.
- Test mit zwei Nutzern: je Nutzer die richtige Zahl, keine Vermischung, Stale-Date, kaputte Datei fail-soft.
- Cache-Hit/Miss je Nutzer existiert nicht (nur global) — nicht erfinden.
- Fair-Share-Rechnung nicht in Go neu entscheiden (Python bleibt einzige Entscheidungsstelle); Go zeigt nur Rohwerte und `daily_budget/N` als Anzeige.

## Analysis

### Type
Feature (S4 von #2150)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| internal/scheduler/forecast_budget_health.go | MODIFY | anonyme Kennzahlen (Töpfe, fairer Anteil, größter Anteil, Anzahl über Anteil) + `UserForecastCalls(uid)` fail-soft, Stale-Date → 0 |
| internal/scheduler/scheduler.go (~1227) | MODIFY | Status-Block `forecast_budget` additiv erweitern |
| internal/handler/admin_users.go | MODIFY | `AdminUser`-DTO: Feld Verbrauch je Nutzer (immer vorhanden) |
| frontend/src/routes/admin/+page.svelte | MODIFY | Anzeige-Spalte Verbrauch |
| docs/adr/0075-...md | MODIFY | Pt. 5 präzisieren (nicht ablösen) |
| docs/reference/api_contract.md | MODIFY | neue Felder |
| docs/specs/modules/forecast_budget_verbrauch_je_nutzer.md | CREATE | Spec mit ACs |
| Tests (Go Scheduler, Go Handler, Frontend admin) | CREATE/MODIFY | Zwei-Nutzer-Test, Stale, kaputte Datei |

### Scope Assessment
- Files: ~8 produktiv/Test + Doku
- Estimated LoC: +150/-5
- Risk Level: LOW–MEDIUM (nur lesend, additive Felder; Datenschutz-Grenze ADR-0075 Pt.5 beachten)

### Technical Approach
Option B + C (siehe oben): Status-Endpunkt nur anonyme Kennzahlen, Nutzerkennungen nur hinter `requireAdmin`. Schutztest bleibt unverändert grün. Python bleibt einzige Entscheidungsstelle; Go zeigt Rohwerte. Nutzer-ID nur via `store.ValidUserID`.

### Dependencies
Python schreibt Zähler (unverändert); check-gregor20.sh liest Status-Block (nur additiv); Admin-UI-Test `admin_seite_render_und_dialogfluss.test.ts`.

### Open Questions
- [ ] Ticket-Wortlaut „im Scheduler-Status sichtbar" wird durch anonyme Kennzahlen + Admin-Ansicht erfüllt — PO-Abnahme in der Spec-Freigabe (Abweichung klar benennen).
