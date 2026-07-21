---
entity_id: bug_636_mobile_email_table
type: module
created: 2026-06-08
updated: 2026-06-08
status: draft
version: "1.0"
tags: [email, mobile, output, bug]
---

# Bug #636 — Mobile-E-Mail: Wetter-Tabelle als ausgerichtetes Monospace-Raster

## Approval

- [x] Approved

## Purpose

Die mobile E-Mail-Ansicht (`.mobile-compact`, ≤600px) zeigt Stunden-Wetterwerte
als frei umbrechende `·`-getrennte Textzeile, sodass kein Wert unter seiner
Spaltenüberschrift steht. Diese Spec stellt ein echtes Festbreiten-Monospace-Raster
her: jede Spalte zeichengenau ausgerichtet (führende Null, erzwungene Dezimalstelle),
leere Zellen als Platzhalter statt gelöscht, Header und Daten fluchten, horizontal
scrollbar bei vielen Spalten. PO-Entscheidung #636: Monospace-Raster mit
horizontalem Scrollen.

## Source

- **File:** `src/output/renderers/email/html.py`
- **Identifier:** `_render_mobile_compact_rows` (Zeile 184–238)
- **Hilfs-Formatierung:** `src/output/renderers/email/helpers.py::fmt_val`, `visible_cols`

Schicht: **Python-Backend** (Server-seitiges HTML-E-Mail-Rendering, kein SvelteKit).

## Estimated Scope

- **LoC:** ~120 (Renderer-Umbau + feste Spaltenbreiten-Helfer)
- **Files:** 1–2 (`html.py`, ggf. ein neuer Format-Helfer)
- **Effort:** medium

## Dependencies

- `fmt_val` / `visible_cols` aus `helpers.py` (Werte-Formatierung pro Spalte)
- `format_email`-Pipeline (`src/output/renderers/email/`) für E2E-Verifikation
- CSS-Block in `render_html` (`@media (max-width:600px)`, `.mobile-compact`)

## Behaviour

Statt zwei freier Text-Spans (Header-Labels + `' · '.join(vals)`) erzeugt
`_render_mobile_compact_rows` einen Monospace-Block, in dem jede Spalte eine feste
Zeichenbreite hat. Die Breite je Spalte = max(Label-Länge, breitester Wert dieser
Spalte über alle Zeilen). Werte werden auf diese Breite gepaddet, sodass Header
und alle Datenzeilen vertikal fluchten. Leere/`None`-Zellen werden als Platzhalter
(`–`) auf Spaltenbreite gerendert — **nicht** gelöscht (Behebung des Spalten-Shift).
Der Block ist in einen horizontal scrollbaren Container (`overflow-x:auto`,
`white-space:nowrap`) gehüllt, damit viele Spalten auf schmalem Display nicht
umbrechen.

Zahlen-Formatierung für feste Breite: führende Null bei Stunden (`08` statt `8`),
erzwungene Dezimalstelle bleibt (`fmt_val` liefert bereits `:.1f`), Padding über
String-Ausrichtung in der festen Spaltenbreite. Die Desktop-Tabelle
(`_render_html_table`, `.desktop-only`) bleibt **vollständig unberührt**.

## Acceptance Criteria

- **AC-1:** Given eine mobile E-Mail (`_render_mobile_compact_rows`, `include_header=True`)
  mit ≥2 enabled Metriken und ≥2 Stunden-Zeilen / When der HTML-Block gerendert wird
  / Then steht in jeder Datenzeile der Wert jeder Spalte zeichengenau (gleiche
  Start-Spaltenposition im Monospace-Block) unter dem zugehörigen Header-Label —
  geprüft an der Zeichen-Offset-Gleichheit von Header-Label-Start und Wert-Start je Spalte.

- **AC-2:** Given eine Stunden-Zeile, bei der mindestens eine Metrik-Zelle leer ist
  (`None` / `–`) / When die Zeile gerendert wird / Then wird die leere Zelle als
  Platzhalter auf voller Spaltenbreite ausgegeben und **nicht** gelöscht; alle
  nachfolgenden Spalten dieser Zeile bleiben mit dem Header und den anderen Zeilen
  ausgerichtet (kein Links-Shift).

- **AC-3:** Given mehrere Stunden-Zeilen mit unterschiedlich breiten Rohwerten
  (z.B. Temp `8.1` vs `14.4`, Wind `4 NE` vs `11`) / When der Block gerendert wird
  / Then hat jede Spalte über alle Zeilen dieselbe feste Zeichenbreite (= max aus
  Label und breitestem Wert), sodass die Spaltengrenzen über alle Zeilen identisch sind.

- **AC-4:** Given der gerenderte Mobile-Block / When er im HTML eingebettet ist
  / Then ist er in einen horizontal scrollbaren Container (`overflow-x:auto`)
  mit Monospace-Schrift gehüllt, sodass bei vielen Spalten kein Umbruch innerhalb
  einer Zeile entsteht (Zeile bleibt einzeilig pro Stunde).

- **AC-5:** Given dieselben Eingabedaten / When die **Desktop**-Tabelle
  (`_render_html_table`) gerendert wird / Then ist deren HTML-Ausgabe byte-identisch
  zum Stand vor diesem Fix (Desktop-Ansicht unverändert).

- **AC-6:** Given die vollständige `format_email`-Pipeline für einen realen Test-Trip
  / When die E-Mail erzeugt und via IMAP abgerufen wird / Then enthält der Mobile-Block
  ein ausgerichtetes Monospace-Raster mit plausiblen Werten (E-Mail-Spec-Validator
  Exit 0), und die Stundenzeit erscheint zweistellig mit führender Null.

## Out of Scope

- Reduktion der Spaltenanzahl / Auswahl „Kern-Metriken" (PO wählte volles Raster mit Scroll)
- Gestapeltes „Label: Wert"-Layout (vom PO abgelehnt)
- Desktop-Tabelle, Telegram-/SMS-Renderer, Vergleichs-Mail
- Änderung der Metrik-Werte selbst (nur Darstellungsbreite/Padding)
