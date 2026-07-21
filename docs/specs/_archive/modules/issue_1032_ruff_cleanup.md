---
entity_id: issue_1032_ruff_cleanup
type: module
created: 2026-07-06
updated: 2026-07-06
status: draft
version: "1.0"
tags: [chore, ci, lint, ruff]
---

# Ruff-Bereinigung + CI-Lint-Gate scharf schalten (Issue #1032)

## Approval

- [ ] Approved

## Purpose

Einmalige Bereinigung aller 311 Ruff-Fehler in `src/` und `tests/` (Folge aus Issue #1018),
damit das bestehende `lint`-Gate in der CI-Pipeline von informativ (`continue-on-error: true`)
auf hart (blockierend) umgestellt werden kann. Reine Lint-Bereinigung ohne funktionale
Code-Änderungen — Ziel ist ein sauberer, dauerhaft erzwingbarer Qualitäts-Gate für alle
künftigen Workflows.

## Source

- **File:** `pyproject.toml` (Ruff-Konfiguration, Z. 29–50), `.github/workflows/ci.yml` (lint-Job, Z. 106–120)
- **Identifier:** `[tool.ruff]` / `[tool.ruff.lint.per-file-ignores]`, CI-Job `lint`

> **Schicht-Hinweis:** Diese Spec betrifft ausschließlich Python-Core-Backend (`src/`) und
> Tests (`tests/`) sowie die CI-Konfiguration (`.github/workflows/ci.yml`, `pyproject.toml`).
> Keine Berührung von Frontend (SvelteKit), Go-API oder Server-Templates.

## Estimated Scope

- **LoC:** Bulk-Autofix über ~60 Dateien (überwiegend `tests/tdd/`) + ~10 manuelle Änderungen
  in `src/` und einzelnen Testdateien + 1 Zeile CI-Änderung + wenige Zeilen `pyproject.toml`.
  **Überschreitet das Standard-LoC-Limit von 250** — Override nötig, **nur mit expliziter
  User-Freigabe** einzuholen (siehe Risiken).
- **Files:** ~60+ Dateien (Autofix) + 6 gezielt manuell bearbeitete Dateien
  (`src/services/comparison_engine.py`, `src/services/trip_alert.py`, `src/output/renderers/...`,
  `tests/tdd/test_issue_664_metrics_summary.py`, `tests/tdd/test_issue_822_radar_nowcast_segment.py`,
  `pyproject.toml`, `.github/workflows/ci.yml`) + evtl. E402-Kandidaten
  (`src/app/trip_report_scheduler.py`, `src/services/weather_change_detection.py`, `src/app/loader.py`).
- **Effort:** medium (mechanisch, aber breite Diff-Fläche + sorgfältige Verifikation nötig).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ruff` (dev-dependency, ≥0.8.0) | Tool | Führt Lint-Check + Autofix aus |
| `.github/workflows/ci.yml` → `lint`-Job | CI-Gate | Wird nach Bereinigung scharf geschaltet; `deploy`-Job hängt via `needs: [test, lint]` daran |
| `pyproject.toml` → `[tool.ruff.lint.per-file-ignores]` (Z. 32–50) | Config | Bestehende Ausnahmen bleiben unangetastet; neue Ausnahme (E731 für `tests/**`) wird ergänzt |

## Implementation Details

**Schritt A — Sicherer Autofix (278 Fehler):**
```
uv run ruff check --fix src/ tests/
```
Behebt automatisch: F401 (unused-import, 200×), F541 (f-string ohne Platzhalter, 61×),
F811 (redefined-while-unused, 16×, fast alle in `tests/tdd/test_issue_911_mail_details.py`),
E401 (multiple-imports, 1×). Kein Re-Export-Risiko, da keine `__init__.py` betroffen ist.

**Schritt B — Manuelle Fälle (33 Fehler):**

1. **F821 undefined-name (5×):**
   - `src/services/comparison_engine.py:283` — `Optional["Settings"]` Forward-Ref ohne Import
     → TYPE_CHECKING-Import ergänzen (`from typing import TYPE_CHECKING`, `if TYPE_CHECKING: from ... import Settings`).
   - `src/services/trip_alert.py:269` — `"UnifiedWeatherDisplayConfig"` Forward-Ref
     → analog TYPE_CHECKING-Import.
   - `tests/.../test_issue_638_alerts_redesign.py:208` — echter Import ergänzen (kein Forward-Ref nötig, da Testdatei).
   - `tests/.../test_issue_917_alert_renderer.py:69` — `"WeatherChange"` Forward-Ref → echter Import ergänzen.
   - `tests/tdd/test_issue_664_metrics_summary.py:350` — **echter Mini-Bug:** f-string in
     Assert-Message referenziert nicht existierende Variable `hh` → Variable aus Kontext ableiten
     oder Message korrigieren (kein funktionaler Testinhalt betroffen, nur die Fehlermeldung selbst).

2. **E402 Import nicht am Dateianfang (4×, ausschließlich `src/`):**
   `src/app/trip_report_scheduler.py` (9 Vorkommen — Achtung: pro Zeile zählt jeweils als ein
   Ruff-Fund, hier als eine Datei mit mehreren Fundstellen zusammengefasst),
   `src/services/weather_change_detection.py` (2×), `src/app/loader.py` (1×, Zeile 188).
   Pro Datei sichten: wenn die Import-Position beabsichtigt ist (z. B. nach Bootstrap-Code),
   gezielter per-file-ignore-Eintrag mit Kommentar-Begründung in `pyproject.toml`; sonst
   Imports an den Dateianfang ziehen.

3. **E731 Lambda-Zuweisung (7×, ausschließlich Tests):** Kein Code-Umbau — stattdessen `E731`
   zur bestehenden `"tests/**"`-per-file-ignore-Liste in `pyproject.toml` (Z. 34–39) hinzufügen,
   mit kurzem Begründungs-Kommentar (Lambdas in Test-Helpern sind idiomatisch, analog zu den
   bereits dort dokumentierten Ausnahmen).

4. **F841 unused-variable (6×, ausschließlich `src/`):** `html.py` (2), `comparison_renderers.py`
   (2), `trip_alert.py` (2). Je Fundstelle prüfen, ob der rechte Ausdruck einen Seiteneffekt hat
   (dann Zuweisung durch bloßen Ausdruck ersetzen oder `_ = ...`), sonst Zuweisung ersatzlos
   entfernen.

5. **E741 ambiguous-name `l` (3×, ausschließlich `src/`):** `src/services/alert/render.py` (1×),
   `src/.../compare_html.py` (2×). Rein lokale Umbenennung auf sprechenden Namen, keine
   Verhaltensänderung.

6. **Ungültige `# noqa`-Direktive:** `tests/tdd/test_issue_822_radar_nowcast_segment.py:151` —
   Ruff meldet eine syntaktisch fehlerhafte noqa-Zeile → korrigieren (richtiges Format
   `# noqa: <CODE>`).

**Schritt C — CI-Gate scharf schalten:**
In `.github/workflows/ci.yml` Zeile 108 `continue-on-error: true` aus dem `lint`-Job entfernen.
Der `deploy`-Job (Zeile 123, `needs: [test, lint]`) blockiert damit ab sofort bei rotem Lint.

## Expected Behavior

- **Input:** Vollständiger `src/`- und `tests/`-Baum wie zum Zeitpunkt der Baseline-Messung
  (2026-07-06, 311 Fehler).
- **Output:** `uv run ruff check src/ tests/` liefert Exit 0. CI-`lint`-Job läuft ohne
  `continue-on-error` und ist damit ein echtes Gate für den `deploy`-Job.
- **Side effects:** Keine funktionalen Verhaltensänderungen an Produktionscode. Entfernte/
  ergänzte Imports dürfen keine Laufzeit-Semantik ändern (abgesichert durch vollen Testlauf,
  siehe Test-Plan). Neue per-file-ignore-Einträge in `pyproject.toml` sind dokumentierte,
  bewusste Ausnahmen — keine stillen `# noqa`.

## Nicht-Ziele

- Keine funktionalen Änderungen an Produktionslogik — ausschließlich Lint-Fixes (Imports,
  Variablennamen, tote Zuweisungen, f-strings).
- Die bestehenden per-file-ignores in `pyproject.toml` (Z. 41–50, „chore-cleanup follows in
  dedicated workflow PR") bleiben **unangetastet** — deren Abbau ist ein separates Folge-Issue,
  nicht Teil von #1032.
- Keine Änderungen an den CI-Jobs `test` (go-test), `frontend-test` oder `svelte-check` — nur
  der `lint`-Job wird verändert.
- Keine Einführung neuer Ruff-Regeln oder Änderung von `line-length`/Regelset — nur Bereinigung
  gegen die bereits aktive Konfiguration.

## Acceptance Criteria

**AC-1:** Given der bereinigte Code-Stand nach Schritt A+B / When `uv run ruff check src/ tests/`
lokal ausgeführt wird / Then der Befehl terminiert mit Exit-Code 0 und meldet keine Fehler mehr
(Baseline war 311).

**AC-2:** Given die bereinigten Test- und Quelldateien / When der volle Offline-Default-Testlauf
`uv run pytest` (Marker `not email and not live and not staging`) sowie zusätzlich
`uv run pytest --collect-only` über die gesamte Suite ausgeführt werden / Then beide Läufe
fehlerfrei durchlaufen (pytest grün, Collect-Phase ohne Import-/Collection-Fehler) — als Beweis,
dass die Import-Entfernungen/-Ergänzungen keine funktionale Regression verursacht haben, auch
für die vom Default-Lauf ausgeschlossenen Live-/E-Mail-Testdateien.

**AC-3:** Given die Zeile `continue-on-error: true` ist aus dem `lint`-Job in
`.github/workflows/ci.yml` entfernt / When der nächste Push auf `main` die CI-Pipeline auslöst /
Then der `lint`-Job läuft als echtes (nicht mehr informatives) Gate und die gesamte Pipeline
(inkl. `lint`) ist auf `main` grün.

**AC-4:** Given neu deaktivierte Ruff-Regeln (mindestens `E731` für `tests/**`, ggf. gezielte
E402-Ausnahmen für einzelne `src/`-Dateien) / When man in `pyproject.toml` die
`[tool.ruff.lint.per-file-ignores]`-Sektion betrachtet / Then jede neu hinzugefügte Ausnahme
steht dort mit einer kurzen erklärenden Kommentarzeile (Begründung), analog zum bestehenden
Muster (Z. 33, „Tests: relax conventions...").

**AC-5:** Given die bestehende per-file-ignores-Sektion in `pyproject.toml` (Zeilen 41–50,
Tech-Debt-Ausnahmen „chore-cleanup follows...") / When man den Diff dieses Workflows gegen den
Stand vor Beginn vergleicht / Then diese Zeilen sind unverändert, und es gibt keinen einzigen
Diff-Hunk, der Produktionslogik (Kontrollfluss, Rückgabewerte, Berechnungen) verändert — jeder
Hunk ist auf Import/Naming/Dead-Code/noqa/CI-Config beschränkt.

## Risiken

- **F401-Autofix entfernt einen tatsächlich genutzten Import** (z. B. Import mit Seiteneffekt
  oder nur zur Laufzeit referenziert): Abgesichert durch vollen `pytest`-Lauf plus
  `--collect-only` über die komplette Suite (AC-2); keine `__init__.py` betroffen, daher kein
  Re-Export-Risiko.
- **LoC-Limit 250 wird sicher überschritten** (Bulk-Fix über ~60 Dateien): Ohne freigegebenen
  Override blockt der Workflow-Hook die Implementierung → Override wird vorab beim User
  beantragt, nicht eigenmächtig gesetzt.
- **CI-Gate-Scharfschaltung blockt künftige rote Pushes:** Nach Entfernen von
  `continue-on-error` verhindert jeder neue Ruff-Fehler den CI-`deploy`-Job (`needs: [test,
  lint]`). Gewollt, aber alle Folge-Workflows müssen ab dann lint-sauber liefern.
- **F841-/E741-Fixes in Produktions-Renderern** (`html.py`, `compare_html.py`,
  `alert/render.py`, `trip_alert.py`): Eine versehentliche Verhaltensänderung wäre hier
  nutzersichtbar (Mail-/Alert-Inhalte). Abgesichert durch Einzelfall-Sichtung auf
  Seiteneffekte + Regressions-Testlauf.

## Known Limitations

- Live-/E-Mail-/Staging-markierte Testdateien werden vom Default-`pytest`-Lauf ausgeschlossen
  (Projekt-Konvention) — für diese Dateien liefert nur `--collect-only` einen Nachweis
  (Import-Korrektheit), keine Ausführungs-Verifikation. Das ist konsistent mit der bestehenden
  Projekt-Policy und wird nicht durch diesen Workflow erweitert.
- E402-Fälle in `trip_report_scheduler.py` können je nach Sichtungsergebnis entweder durch
  Import-Umsortierung oder durch eine neue per-file-ignore gelöst werden — die konkrete Wahl
  erfolgt erst bei der Implementierung nach Einzelfallprüfung (bewusst offen gelassen, um keine
  vorschnelle Strukturänderung an einem produktiven Scheduler zu erzwingen).
- LoC-Limit-Override ist erforderlich (Bulk-Autofix über ~60 Dateien) — muss vor Implementierung
  vom User freigegeben werden (`workflow.py set-field loc_limit_override <N>`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Lint-/CI-Konfigurationsänderung ohne architektonische Auswirkung — kein
  neues Muster, keine neue Abhängigkeit, keine Schnittstellenänderung. Fällt unter `[no-adr]`.

## Test-Plan

1. **Vor Implementierung (RED-Referenz):** `uv run ruff check src/ tests/` dokumentiert die
   Baseline (311 Fehler) — dient als Vergleichspunkt, kein klassischer TDD-RED-Test nötig, da es
   sich um ein Tooling-Gate handelt, nicht um Anwendungsverhalten.
2. **Nach Schritt A (Autofix):** `uv run ruff check src/ tests/` erneut ausführen → erwartete
   Reduktion auf 33 verbleibende Fehler (F821, E402, E731, F841, E741 + noqa-Fehler).
3. **Nach Schritt B (manuelle Fixes):** `uv run ruff check src/ tests/` → Exit 0 (AC-1).
4. **Regressions-Nachweis:** `uv run pytest` (voller Offline-Default-Lauf) grün + zusätzlich
   `uv run pytest --collect-only` über die komplette Suite ohne Collection-Fehler (AC-2) —
   beweist insbesondere, dass entfernte F401-Imports und die F821-Fixes keine Laufzeit- oder
   Importfehler verursachen.
5. **Nach Schritt C (CI-Gate):** Push auf `main`, CI-Lauf abwarten, `lint`-Job-Status prüfen
   (muss grün sein, nicht nur „continue-on-error grau") (AC-3).
6. **Diff-Review:** `git diff pyproject.toml` zeigt nur neue, kommentierte per-file-ignore-
   Einträge; bestehende Zeilen 41–50 unverändert (AC-4, AC-5). `git diff src/` enthält
   ausschließlich Import-/Naming-/Dead-Code-Änderungen, keine Kontrollfluss- oder
   Berechnungsänderungen (stichprobenartige manuelle Durchsicht der ~10 manuell bearbeiteten
   Dateien).

## Changelog

- 2026-07-06: Initial spec created (Issue #1032, Folge aus #1018).
