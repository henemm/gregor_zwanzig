# Spec: #586 — Alert-Config Design-Fidelity Close-Gate

- **Issue:** #586 (type:rework, design-compliance, frontend)
- **Created:** 2026-06-07
- **Workflow:** issue-586-fidelity-gate
- **Scope:** frontend-only (Verifikation + Close-Gate; **kein neuer Produktiv-Code** erwartet)

## Kontext / Ausgangslage

Die 1:1-Umsetzung der Alert-Config nach `screen-alert-config.jsx` ist **bereits seit 2026-06-04
live** (Commit `75aed1f0`, Komponenten unter `frontend/src/lib/components/alerts-tab/`,
Adversary VERIFIED, seitdem unverändert → auf Prod aktiv). Das Issue wurde am selben Tag im Rahmen
der Epic-#575-Drift-Korrektur **wieder geöffnet**, um das verpflichtende Pixel-Diff-Close-Gate
nachzuholen (`pre_issue_close_design_gate.py` blockt den Close ohne PASS-Artefakt).

**Zentraler Befund dieser Analyse:** Das offizielle SOLL-PNG
`claude-code-handoff/current/soll/K-alert-config-list.png` (1540×1434) zeigt **einen anderen
Screen** als der bindende JSX `screen-alert-config.jsx`:

- JSX = **Alert-Schwellwert-Konfigurator** (Δ-/Absolut-Modus, 9 Metriken, Schwellwert-Tabelle).
- SOLL-PNG = **Reports-/Kanäle-Konfiguration** (Morgen-/Abend-Report, Kanäle E-Mail/**Signal**/Telegram,
  „Erweitert ausblenden"). Enthält den per PO-Entscheidung **#610 app-weit entfernten Signal-Kanal**.

Das SOLL-PNG ist damit **doppelt unbrauchbar** als Vergleichsreferenz: falscher Screen **und**
veralteter (entfernter) Kanal. Ein literaler Pixel-Diff der Live-Alarm-Config gegen dieses PNG ist
strukturell sinnlos. Projekt-Regel: **JSX ist die bindende Wahrheit** (Memory
`feedback_jsx_always_truth`) — die Implementierung wird gegen die JSX verifiziert, die SOLL-Korrektur
läuft als separater Design-Request.

## Acceptance Criteria

**AC-1:** Given die Live-Alarm-Config (Trip-Detail → Tab „Alerts") auf Staging,
When sie bei 1440px Breite gegen den bindenden JSX `screen-alert-config.jsx` geprüft wird
(staging-validator/fresh-eyes, semantisch + Layout),
Then bestätigt die Prüfung Übereinstimmung mit der JSX (Eyebrow „Alert-Briefings · Sofort-
Benachrichtigung", Δ/Absolut/Beide-Modus-Wahl, Schwellwert-Tabelle der 9 Metriken) ohne Layout-Drift.

**AC-2:** Given die bindende JSX als Wahrheits-Referenz und das als falscher Screen erkannte
offizielle SOLL-PNG, When eine Vergleichsreferenz **aus der JSX gerendert** wird (eigenständiges
Wegwerf-Skript unter `docs/artifacts/`, das geteilte `design_fidelity_diff.py` bleibt unangetastet),
Then entsteht ein Referenz-Screenshot, der den tatsächlich spezifizierten Alert-Konfigurator zeigt.

**AC-3:** Given die JSX-gerenderte Referenz und der Live-Screenshot der Alarm-Config,
When beide per Pixel-Diff verglichen werden, Then liegt die Differenz unter der 10%-Schwelle und es
entsteht ein Artefakt `docs/artifacts/issue-586-fidelity-gate/design-diff-K-alert-config-list.json`
mit `"passed": true`, das die Referenzquelle (JSX-Render) und den SOLL-Fehler transparent dokumentiert.

**AC-4:** Given der dokumentierte SOLL-Fehler (falscher Screen + entfernter Signal-Kanal),
When der Abschluss erfolgt, Then existiert ein **frischer Design-Request** (GitHub-Issue), der eine
korrigierte `K-alert-config-list.png` aus `screen-alert-config.jsx` anfordert und auf #586/#610 verweist.

**AC-5:** Given das PASS-Artefakt (AC-3) und der Design-Request (AC-4),
When `gh issue close 586` aufgerufen wird, Then blockt der `pre_issue_close_design_gate.py`-Hook
**nicht** und das Issue wird mit einem erklärenden Abschluss-Kommentar geschlossen (Code 1:1 live seit
2026-06-04, gegen JSX verifiziert, offizielles SOLL als fehlerhaft an Design zurückgegeben).

## Nicht-Ziele

- Keine Änderung an `frontend/src/lib/components/alerts-tab/*` (Code ist 1:1 zur JSX & live).
- Kein Umbau des geteilten `design_fidelity_diff.py` und keine hart-codierten Trip-IDs darin
  (Memory `feedback_shared_fidelity_tool`).
- Keine Threshold-Manipulation zum „Durchdrücken" — der PASS beruht auf einer echten Messung gegen
  die bindende JSX, nicht auf einem aufgeweichten Schwellwert (Memory `feedback_no_threshold_manipulation`).

## Test-Plan (TDD)

Test-Datei: `tests/tdd/test_issue_586_alert_config_fidelity.py` — behaviorale Pixel-Diff-Prüfung
(keine Mocks, keine String-Checks; vergleicht echte gerenderte Bilder).

| Test-Entity | AC | Prüft |
|-------------|----|-------|
| `live_and_reference_screenshots_exist` | AC-1/AC-2 | Live-Screenshot (Alarme-Tab @1440px) und JSX-gerenderte Referenz liegen vor und sind nicht leer |
| `live_matches_binding_jsx_under_threshold` | AC-3 | Eigenständig berechneter Pixel-Diff Live vs. JSX-Referenz `< 10 %` |
| `gate_artifact_passed` | AC-3/AC-5 | Close-Gate-Artefakt `design-diff-K-alert-config-list.json` existiert mit `passed: true` und `diff_pct < 10` |

## Risiken

- Sollte die Live-Verifikation (AC-1) wider Erwarten echten Drift gegen die JSX zeigen, wird
  `AlertsTab.svelte` gezielt nachgezogen (dann doch src/-Edit) — unwahrscheinlich, da Code seit dem
  VERIFIED-Commit unverändert.
