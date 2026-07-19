---
entity_id: fix_1323_compare_outlook_placement
type: bugfix
created: 2026-07-19
updated: 2026-07-19
status: draft
version: "1.0"
workflow: fix-1323-outlook-placement
tags: [compare, email, plain-text, outlook, placement, epic-1301]
---

# Ortsvergleich-Mail: 3-Tage-Ausblick je Ort platzieren

## Approval

- [x] Approved (PO-Freigabe 2026-07-19)

## Purpose

Der 3-Tage-Ausblick je Ort (Epic #1301 B4) erscheint in der Ortsvergleich-Mail
heute als **ein gesammelter Block am Ende** — hinter *allen* Stundentabellen.
Der Nutzer erwartet den Ausblick eines Ortes **direkt unter dessen eigener
Stundentabelle**, damit er Ort für Ort zusammenhängend „jetzt → nächste Tage"
liest, statt am Mail-Ende einen losgelösten Ausblick-Stapel zu suchen. Diese
Arbeit ändert **nur die Platzierung** im Compare-Renderer (HTML + Klartext);
der geteilte Ausblick-Tabellen-Renderer bleibt unangetastet.

## Source

- **File:** `src/output/renderers/email/compare_html.py`
- **Identifier:** `render_comparison_html` — Body-Zusammenbau Z.1024–1051
  (`hourly_sections_html` + `outlook_sections_html` getrennt gejoint), je Ort:
  `_render_location_section` (Z.613) und `_render_location_outlook` (Z.685).
- **File:** `src/output/renderers/comparison.py`
- **Identifier:** Klartext-Ausblick-Block Z.186–198 (`if outlook_enabled:` —
  sammelt alle Orts-Ausblicke nach den Stundentabellen).

> Schicht: **Python-Core / Domain-Backend** (Mail-Renderer). Kein Frontend, kein Go.

## Estimated Scope

- **LoC:** ~+50 / −30
- **Files:** 2 Quelldateien + 1 Testdatei
- **Effort:** low–medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/outlook.py` | module | Geteilter Ausblick-Renderer (`render_outlook_table`/`render_outlook_plain`) — **bleibt unverändert** |
| `comparison_engine.py` (`LocationResult.outlook_hourly_data`) | data | Datenquelle je Ort; unverändert |
| Renderer-Commit-Gate #811 | gate | Test-Mails + `briefing_mail_validator.py` vor Commit |

## Implementation Details

```
render_comparison_html (compare_html.py):
  ALT: hourly_sections_html = "".join(_render_location_section(loc,i) ...)
       outlook_sections_html = "".join(_render_location_outlook(loc,i) ...)
       body = ...hourly_head, hourly_sections, outlook_head, outlook_sections...

  NEU: EINE Per-Ort-Schleife über locations (Reihenfolge = Übersichts-Spalten):
       je Ort: [Stundentabelle falls hourly_enabled] + [Ausblick falls outlook_enabled]
       -> per_location_html = "".join(block(loc,i) for i,loc in enumerate(locations))
       Sammel-Head "AUSBLICK · alle Orte" entfällt; Ausblick behält seine
       Per-Ort-Kopfzeile aus _render_location_outlook.
       Anti-Erosion-Filter (if part) + fail-soft (leeres outlook_hourly_data -> "")
       bleiben erhalten.

comparison.py (Klartext): dieselbe Verschachtelung — Ausblick je Ort direkt
       nach dessen Stundenblock statt gesammelt am Ende.
```

## Expected Behavior

- **Input:** `ComparisonResult` mit ≥1 Ort, `hourly_enabled`/`outlook_enabled` (unabhängige Bools), je Ort `outlook_hourly_data`.
- **Output:** HTML- und Klartext-Mail, in der jeder Ort-Block aus Stundentabelle (falls aktiv) **und unmittelbar darunter** dessen 3-Tage-Ausblick (falls aktiv) besteht — bevor der nächste Ort beginnt.
- **Side effects:** keine (reiner Renderer).

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich mit mindestens zwei Orten und aktivem Stundenverlauf und aktivem Ausblick, When die HTML-Mail gerendert wird, Then folgt auf die Stundentabelle jedes Orts unmittelbar dessen 3-Tage-Ausblick, bevor der nächste Ort im HTML beginnt.
  - Test: HTML rendern, Positionen prüfen — für jeden Ort liegt der Index seines Ausblick-Markers zwischen seiner Stundentabelle und der Stundentabelle des nächsten Orts.

- **AC-2:** Given dieselbe Mail, When sie gerendert wird, Then existiert **kein** separater gesammelter Ausblick-Abschnitt (Sammel-Head „AUSBLICK · alle Orte") hinter allen Stundentabellen am Mail-Ende.
  - Test: Der gerenderte HTML enthält keinen Sammel-Ausblick-Head; die Anzahl Ausblick-Tabellen entspricht der Zahl der Orte mit Ausblick-Daten, jeweils inline.

- **AC-3:** Given die Klartext-Variante derselben Mail, When sie gerendert wird, Then steht der Ausblick jedes Orts direkt nach dessen Stundenblock, in derselben Orte-Reihenfolge wie im HTML.
  - Test: Klartext rendern, Zeilen-Reihenfolge prüfen — je Ort erscheint der Ausblock direkt nach dessen Stundenblock, nicht gebündelt am Textende.

- **AC-4:** Given `outlook_enabled=True` und `hourly_enabled=False`, When die Mail gerendert wird, Then erscheint der Ausblick je Ort gruppiert (ohne Stundentabelle darüber) und der Renderer wirft keinen Fehler.
  - Test: Mit hourly aus / outlook an rendern — je Ort genau ein Ausblick-Block vorhanden, kein Crash, keine leeren Sammel-Heads.

- **AC-5:** Given ein Ort ohne `outlook_hourly_data` in einem sonst vollständigen Vergleich, When die Mail gerendert wird, Then entfällt fail-soft nur dessen Ausblick, während die übrigen Orte samt unveränderter Reihenfolge korrekt gerendert werden.
  - Test: Ein Ort mit leeren Ausblick-Daten — dessen Ausblick fehlt, alle anderen Orte + Spaltenreihenfolge unverändert, kein Fehler.

- **AC-6:** Given der Trip-Briefing-Pfad und der geteilte Ausblick-Renderer, When die Trip-Mail gerendert wird, Then bleibt sie unverändert (keine Änderung an `outlook.py`; die geteilten Renderer-Tests bleiben grün).
  - Test: `tests/tdd/test_shared_outlook_renderer.py` läuft unverändert grün; Trip-Ausblock byte-stabil.

## Known Limitations

- Der Ausblick-Horizont (bis 3 Kalendertage, 96h-Fetch) und die Ausblick-Daten selbst ändern sich nicht — ausschließlich die **Platzierung**.
- Es gibt weiterhin **keinen** Nutzer-Schalter für den Ausblick (per Default an); das ist bewusst so und nicht Teil dieser Arbeit.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Platzierungs-/Orchestrierungskorrektur im bestehenden Compare-Renderer. Die tragende Architektur-Entscheidung (geteilter Ausblick-Renderer Trip/Compare) fiel bereits in der B4-Spec (Epic #1301). Keine neue Schnittstelle, kein neues Datenfeld.

## Changelog

- 2026-07-19: Initial spec created (Issue #1323)
