---
entity_id: issue_729_render_compact_empty_guard
type: module
created: 2026-06-11
updated: 2026-06-11
status: approved
version: "1.0"
tags: [bug, email, compact, renderer, defensive-guard, issue-729]
---

<!-- Issue #729 — render_compact(segments=[]) wirft IndexError -->

# Issue #729 — Defensiver Guard für leere Segmente in render_compact

## Approval

- [x] Approved (2026-06-11)

## Purpose

`render_compact()` (Issue #722) greift dreimal `segments[0]` ohne Leer-Prüfung
(Report-Datum Z.87, Modellname Z.150, Provider Z.151). Bei `segments=[]` wirft die
Funktion `IndexError`. In Produktion aktuell harmlos, weil der Scheduler leere
Segmente vorher abfängt (`trip_report_scheduler.py:371`) — aber der Renderer ist als
Pure-Function bei direktem Aufruf nicht robust (Defense-in-Depth fehlt).

Diese Härtung ergänzt einen defensiven Guard am Anfang von `render_compact`: bei leerer
Segment-Liste wird ein **minimaler ASCII-Body** (Kopf + Footer, ohne segment-abhängige
Daten) zurückgegeben statt einer Exception. Der bestehende Nicht-Leer-Pfad bleibt
**byte-identisch unberührt** (Backward Compatibility zu #722).

## Source

- **File:** `src/output/renderers/email/compact.py`
- **Identifier:** `render_compact()` — Guard am Funktionsanfang

## Acceptance Criteria

**AC-1:** Given eine leere Segment-Liste (`segments=[]`) mit ansonsten gültigen
Parametern / When `render_compact(...)` aufgerufen wird / Then wirft die Funktion
**keine** Exception (insbesondere keinen `IndexError`), sondern liefert einen String
zurück.

**AC-2:** Given `segments=[]` / When `render_compact(...)` gerendert wird / Then ist der
zurückgegebene Body reines ASCII (`str.isascii() == True`) und enthält den `trip_name`
sowie den Report-Typ in der Kopfzeile (ein minimaler, nicht-leerer Body).

**AC-3:** Given eine nicht-leere Segment-Liste mit denselben Parametern wie vor diesem
Fix / When `render_compact(...)` gerendert wird / Then ist der erzeugte Body
**byte-identisch** zum Ergebnis vor dem Fix (der reguläre Pfad mit Metriken-Überblick,
Ausblick, Datum und Provider bleibt unverändert — keine Regression an #722).

## Out of Scope

- Änderungen am Scheduler-Guard (`trip_report_scheduler.py`) — der bleibt unberührt.
- Änderungen am `full`/HTML-Pfad (`render_html`/`render_plain`).
- Schema-/Persistenz-Änderungen.

## Changelog

- 2026-06-11: Initiale Spec (v1.0).
