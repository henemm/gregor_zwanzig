# Context: tdd-765-backend-hygiene

## Request Summary
Backend-Pendant zum Frontend-Test-Hygiene-Sweep #754: `tests/tdd/`-Tests (und
einige `tests/refactor/`, `tests/integration/`, `tests/unit/`) lesen echten
**Produkt-Quelltext** (`.py`/`.go` unter `src/`, `api/`, `internal/`, `cmd/`) via
`read_text()` oder grep/rg-Subprozess und asserten auf Code-Strings statt auf
Verhalten — Verstoß gegen CLAUDE.md „Dateiinhalt-Checks sind VERBOTEN". Sweep:
detektieren, pro Datei urteilen (löschen / auf echtes Verhalten umstellen /
obsolet), Regress-Gate analog #754.

## Echte Offender (pfad-aufgelöster Detektor, 14 Dateien)
| Test | gelesener Produkt-Quelltext |
|------|------------------------------|
| `tests/integration/test_cli_wintersport.py` | `src/app/cli.py` |
| `tests/refactor/test_epic_129a_1_module_structure.py` | `api/routers/compare.py`, `src/services/compare_subscription.py` |
| `tests/refactor/test_epic_129a_2_module_structure.py` | `api/routers/gpx.py` |
| `tests/tdd/test_bug_198_notify_test_resend.py` | `api/routers/notify.py` |
| `tests/tdd/test_bug_400_alert_tz.py` | `src/services/trip_alert.py` |
| `tests/tdd/test_email_design_tokens.py` | `src/output/renderers/email/html.py` |
| `tests/tdd/test_email_profile_pipeline.py` | `preview_service.py`, `trip_report_scheduler.py` |
| `tests/tdd/test_issue_256_thunder_color.py` | `src/output/renderers/email/design_tokens.py` |
| `tests/tdd/test_issue_257_trip_briefing_polish.py` | `src/output/renderers/email/html.py` |
| `tests/tdd/test_issue_396_archive_stats.py` | `internal/handler/archive_stats.go`, `cockpit.go`, `store.go`, `trip_alert.py` |
| `tests/tdd/test_issue_515_remove_subscription_jobs.py` | `api/routers/scheduler.py`, `internal/config/config.go`, `internal/scheduler/scheduler.go` |
| `tests/tdd/test_issue_623_trend_channels.py` | `html.py`, `plain.py`, `narrow.py` |
| `tests/tdd/test_trip_alert_profile.py` | `src/services/trip_alert.py` |
| `tests/unit/test_issue_131_alert_klarheit.py` | `src/formatters/trip_report.py` |

5 Go-Targets (in #396 + #515), 18 Py-Targets. Die exakte, vollständige Liste
produziert das **Detektor-Gate** selbst (Pfad-Auflösung, robuster als ein
Kontextfenster-Grep — der verfehlt weit entfernte Pfad-Konstruktion).

## Existing Patterns
- Gate-Vorbild: `tests/tdd/test_754_755_test_hygiene_compliance.py` (markiert
  `# doc-compliance-test`, parametrisiert über Datei-Liste, Regex `_FORBIDDEN_READ`
  `.read_text(` + `_FORBIDDEN_GLOB` für `--include/--glob=*.svelte/*.ts`).
- #754 Triage-Logik: pro Datei (a) Verhalten schon durch echten Test gedeckt →
  Asserts löschen / Datei löschen, (b) relevant+ungedeckt → echter Verhaltenstest,
  (c) obsolet → löschen. KEINE Mocks.
- Offender-Muster: meist `SRC = Path("src/...").read_text()` + `assert "x" in SRC`;
  Go via `subprocess`-grep oder `store_path.read_text()` + `assert "Func" in content`.

## Dependencies
- Upstream (Detektor): stdlib `re`, `pathlib`, `ast` — keine neuen Deps.
- Downstream: Die geänderten Tests laufen in `uv run pytest`; das neue Gate läuft mit.

## Existing Specs
- Regel-Quelle: `CLAUDE.md` „KEINE MOCKED TESTS!" / „Dateiinhalt-Checks sind VERBOTEN".
- Schwester-Issues: #754 (Frontend-Sweep, LIVE), #755, #756, #753/#746.

## Risks & Considerations
- **Umfang/LoC:** 14 Dateien × Einzelurteil → LoC-Limit 250 wird überschritten
  (Override nötig). Gelöschte Zeilen zählen mit.
- **Go-Targets (#396, #515):** Go-Source-Greps lassen sich nicht 1:1 in
  Python-Verhaltenstests übersetzen → echter API-Call gegen laufenden Go-Service
  oder Go-Testpfad; im Zweifel löschen + Verhalten anderswo abgedeckt nachweisen.
- **Bypass-Falle (#754-Lehre):** `# doc-compliance-test`-Markierung rechtfertigt
  NUR Doku-/Tooling-Reads, niemals Produkt-Quelltext — Gate muss das durchsetzen.
- **Detektor-Robustheit:** Pfad-Auflösung statt naivem Substring, sonst False-
  Negatives bei entfernter Pfad-Konstruktion (`parents[2] / "src" / ...`).
- **Test-only Change:** kein `src/`-Produktcode berührt → kein Prod-Deploy
  (Tooling/Test-only, analog #754/#753).
