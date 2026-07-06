# Context: fix-1032-ruff-cleanup

## Request Summary

Issue #1032 (Folge aus #1018): Die 311 Ruff-Fehler in `src/` und `tests/` auf 0 bringen,
danach das CI-lint-Gate scharf schalten (`continue-on-error` entfernen). Reine
Lint-Bereinigung, keine funktionalen Änderungen.

## Baseline (verifiziert 2026-07-06, lokal)

`uv run ruff check src/ tests/` → **311 Fehler**, davon **278 auto-fixbar**:

| Regel | Anzahl | Auto-Fix | Bewertung |
|-------|--------|----------|-----------|
| F401 unused-import | 200 | ✅ | Meist Tests; **keine `__init__.py` betroffen** → kein Re-Export-Risiko |
| F541 f-string ohne Platzhalter | 61 | ✅ | Trivial |
| F811 redefined-while-unused | 16 | ✅ (17 inkl. E401) | Fast alle in `tests/tdd/test_issue_911_mail_details.py` (Funktions-lokale Re-Imports) |
| E402 Import nicht am Dateianfang | 14 | ❌ | Nur 4 src-Dateien: `trip_report_scheduler.py` (9×), `weather_change_detection.py` (2×), `loader.py` (1×, Zeile 188 — Import mitten in der Datei) |
| E731 Lambda-Zuweisung | 7 | ❌ | Alle in Tests |
| F841 unused-variable | 6 | ❌ | `html.py` (2), `comparison_renderers.py` (2), `trip_alert.py` (2) |
| F821 undefined-name | 5 | ❌ | Siehe unten — 4× Forward-Ref-Strings, 1× echter Mini-Bug |
| E741 ambiguous-name `l` | 3 | ❌ | `alert/render.py`, `compare_html.py` (2×) |
| E401 multiple-imports | 1 | ✅ | Test-Datei |

**F821-Sichtung (die kritischen Fälle):**
- `src/services/comparison_engine.py:283` — `Optional["Settings"]` Forward-Ref ohne Import → TYPE_CHECKING-Import
- `src/services/trip_alert.py:269` — `"UnifiedWeatherDisplayConfig"` Forward-Ref → TYPE_CHECKING-Import
- `tests/.../test_issue_638_alerts_redesign.py:208` — dito (Test: echter Import möglich)
- `tests/.../test_issue_917_alert_renderer.py:69` — `"WeatherChange"` Forward-Ref
- `tests/.../test_issue_664_metrics_summary.py:350` — **echter Mini-Bug:** f-string in assert-Message referenziert nicht existierende Variable `hh` (würde bei Assert-Fehlschlag mit NameError crashen)

**Zusatzbefund:** `tests/tdd/test_issue_822_radar_nowcast_segment.py:151` hat eine
syntaktisch ungültige `# noqa`-Direktive (Ruff-Warning) → mit reparieren.

## Related Files

| File | Relevance |
|------|-----------|
| `pyproject.toml` (Z. 29–50) | Ruff-Config existiert bereits: `line-length=88` + `per-file-ignores` (Tests: E402/E741/F841/F402; einzelne src-Dateien: F821/F401-Tech-Debt mit Kommentar „chore-cleanup follows") |
| `.github/workflows/ci.yml` (Z. 106–120) | lint-Job mit `continue-on-error: true`; `deploy` hat `needs: [test, lint]` — nach Scharfschaltung blockt rotes Lint den Deploy-Job |
| ~60 Python-Dateien | Mechanische Fix-Ziele (überwiegend `tests/tdd/`) |

## Existing Patterns

- `per-file-ignores` in `pyproject.toml` ist das etablierte Muster für bewusste Ausnahmen (dokumentiert mit Kommentar) — Issue #1032 verlangt genau das statt `# noqa`-Flut.
- Die bestehenden Tech-Debt-Ignores (Z. 44–50, „dedicated workflow PR") bleiben in diesem Workflow **unangetastet** — sie sind nicht Teil der 311 sichtbaren Fehler. Abbau = separates Folge-Issue.

## Dependencies

- **Upstream:** ruff ≥0.8.0 (dev-dependency, bereits vorhanden); CI nutzt `uv sync --dev`.
- **Downstream:** CI-`deploy`-Job hängt via `needs` am lint-Job. Nach Scharfschaltung: rotes Lint = kein CI-Deploy-Smoke — gewollt.

## Geplanter Ansatz (Analyse, Standard Track kombiniert)

1. `uv run ruff check --fix src/ tests/` → 278 Fehler weg (sicherer Autofix, kein Re-Export-Risiko da keine `__init__.py`).
2. Manuell (33 Fälle):
   - **F821:** TYPE_CHECKING-Imports in `comparison_engine.py` + `trip_alert.py`; Tests: echte Imports; `hh`-Bug in test_664 reparieren (Variable aus Kontext ableiten oder Message korrigieren).
   - **E402:** pro Datei sichten — wenn Import-Reihenfolge beabsichtigt (z. B. nach `sys.path`/Bootstrap), gezielt per-file-ignore mit Begründung; sonst Imports nach oben.
   - **E731 (nur Tests):** `E731` in bestehende `tests/**`-per-file-ignores aufnehmen (passt zum Muster: Lambdas in Test-Helpern sind idiomatisch).
   - **F841 (6× src):** ungenutzte Zuweisungen entfernen (je Fall prüfen: rechter Ausdruck ohne Seiteneffekt).
   - **E741 (3× src):** `l` → sprechender Name (rein lokal).
   - Ungültige noqa-Direktive in test_822 korrigieren.
3. Verifikation: `ruff check src/ tests/` Exit 0 **+ voller `uv run pytest`** (Offline-Default) — beweist, dass die Import-Entfernungen nichts brechen.
4. `ci.yml`: `continue-on-error: true` beim lint-Job entfernen.
5. Push → CI muss grün sein (lint jetzt Pflicht).

## Risks & Considerations

- **LoC-Limit 250:** Bulk-Autofix über ~60 Dateien überschreitet das Workflow-LoC-Limit sicher → Override nötig (**nur mit User-Freigabe**, wird in der Spec explizit beantragt).
- **F401-Entfernung kann theoretisch benutzte Namen treffen** (z. B. Import mit Seiteneffekt): abgesichert durch vollen pytest-Lauf danach.
- **CI-Gate-Scharfschaltung:** Ab dann blockt jeder neue Ruff-Fehler den Push-Deploy-Pfad — gewollt, aber alle künftigen Workflows müssen lint-sauber liefern.
- Live/E-Mail-Tests sind vom Default-pytest ausgeschlossen (`-m 'not email and not live and not staging'`) — Änderungen in solchen Testdateien werden nur per Import-/Collection-Check abgedeckt. Zusätzlich `--collect-only` über die volle Suite als Import-Beweis.
