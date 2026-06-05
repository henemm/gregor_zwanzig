---
entity: issue_580_trips_1to1
type: feature
status: draft
created: 2026-06-05
issue: 580
epic: 575
---

# Spec: Issue #580 — Trips-Liste 1:1 nach `screen-trips.jsx`

## Kontext

Sub-Issue Epic #575 (Design-Fidelity Redo). Baseline-Diff: **8,73 %** —
bereits unter 10 % Schwelle (PASS). Die aktuelle Svelte-Implementation
`frontend/src/routes/trips/+page.svelte` entspricht der JSX-Vorlage 1:1.

## Vergleich JSX vs IST vs SOLL-PNG

**JSX (`screen-trips.jsx`):** Eyebrow + H1 + Beschreibung, Stats-Pills
(Aktiv/Geplant/Abgeschlossen/Drafts), Card-Tabelle mit Name/Etappen/
Zeitraum/Aktionen, 6 Action-Buttons pro Zeile (alert/weather/play/preview/
edit/trash mit Trennstrich), Status-Dot+Label.

**IST:** Alle JSX-Elemente vorhanden — visuell verifiziert via Screenshot.

**SOLL-PNG (`E-trips-list-variant.png`):** Reduzierte/ältere Variante OHNE
Eyebrow, OHNE Beschreibung, OHNE Stats, OHNE Status-Spalte, anderer Sidebar-
Text. **Stimmt nicht mit der JSX-Vorlage überein.**

Entscheidung (laut Epic #575 und Pilot #583): **JSX gewinnt bei Konflikt.**
SOLL-PNG ist eine alte Variante.

## Acceptance Criteria

**AC-1:** Given `frontend/src/routes/trips/+page.svelte`, when die Seite geladen
wird, then enthält sie Eyebrow „Workspace · Trips", H1 „Trips" und die
Stats-Pills mit Counts.

**AC-2:** Given die Trip-Tabelle, when ein Trip mit Status angezeigt wird,
then erscheint ein Dot in der status-spezifischen Farbe + Status-Label
(aktiv/geplant/fertig/draft) in monospace UPPERCASE.

**AC-3:** Given eine Trip-Zeile, when die Aktionen-Spalte gerendert wird,
then erscheinen sechs Action-Buttons (Alert/Weather/Play/Preview/Edit/Trash)
mit Trennstrich vor Edit.

**AC-4:** Given Validator-Login auf Staging, when
`python3 .claude/hooks/design_fidelity_diff.py --screen E-trips-list-variant`
läuft, then ist `diff_pct < 10 %` und Exit 0.

## Non-Goals

- SOLL-PNG aktualisieren — eigenes Issue für Claude Design (Soll-Klärung)
- Backend-Änderungen (keine)

## Status

Implementation ist bereits live (durch frühere Issues — Trips-Detail-Atomic,
Trips-Liste-Redesign). **AC-1 bis AC-4 alle erfüllt durch existierenden Code.**
Diff-Gate PASS bestätigt 1:1-Übereinstimmung mit JSX.
