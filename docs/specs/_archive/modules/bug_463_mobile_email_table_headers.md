---
entity_id: bug_463_mobile_email_table_headers
type: bugfix
created: 2026-05-30
updated: 2026-05-30
status: draft
version: "1.0"
tags: [bugfix, mobile, email, table-headers, html-renderer, issue-463]
---

<!-- Issue #463 — In der mobilen E-Mail-Ansicht fehlen Tabellenköpfe für Segment- und Nacht-Rows -->

# Issue #463 — Bug-Fix: Fehlende Spalten-Header im mobilen E-Mail-Layout

## Approval

- [ ] Approved

## Zweck

`_render_mobile_compact_rows()` in `src/output/renderers/email/html.py` erzeugt das
mobile Kompakt-Layout (≤ 600 px) ohne Kopfzeile — der Nutzer sieht Zeilen wie
`09:00 · 14°C · 23 km/h · SW` ohne zu wissen, welche Spalte welchen Wert enthält.
Der Fix ergänzt die Funktion um einen optionalen `include_header`-Parameter, der eine
kompakte Label-Zeile (`Zeit · Temp · Wind · …`) vor die Daten-Rows stellt, und setzt
diesen Parameter an beiden Aufruforten (Segment-Rows, Nacht-Rows) auf `True`.

## Quelle / Source

- **Datei:** `src/output/renderers/email/html.py`
- **Identifier:** `_render_mobile_compact_rows`
- **Schicht:** Python-Backend — E-Mail-Renderer

```python
# Vorher (buggy) — kein Header:
def _render_mobile_compact_rows(
    rows: list[dict],
    *,
    friendly_keys: set[str],
    allowed_col_keys: Optional[set[str]] = None,
    format_modes: Optional[dict[str, str]] = None,
) -> str:
    cols = visible_cols(rows) if rows else []
    ...

# Nachher (korrekt) — optionaler Header:
def _render_mobile_compact_rows(
    rows: list[dict],
    *,
    friendly_keys: set[str],
    allowed_col_keys: Optional[set[str]] = None,
    format_modes: Optional[dict[str, str]] = None,
    include_header: bool = False,
) -> str:
    cols = visible_cols(rows) if rows else []
    ...
    # Wenn include_header=True: Header-Div vor parts_html prependen
```

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/helpers.py` — `visible_cols(rows)` | Hilfsfunktion | Liefert `[(col_key, label), ...]` für die sichtbaren Spalten einer Row-Liste; wird bereits in der Funktion aufgerufen, kein Änderungsbedarf |
| `src/output/renderers/email/html.py` — `G_INK`, `G_INK_MUTED`, `G_INK_FAINT`, `FONT_DATA` | Modul-Konstanten | Farb- und Font-Tokens für konsistentes HTML-Styling des Headers |
| `tests/tdd/test_bug305_mobile_email.py` | Testdatei | Bestehende AC-7–AC-10 dürfen durch den Fix nicht brechen; neue Testfälle werden in derselben Datei ergänzt |

## Implementation Details

```
1. Signatur von _render_mobile_compact_rows erweitern:
   - Neuer keyword-only Parameter: include_header: bool = False

2. Header-Block generieren (direkt nach der cols-Berechnung, vor der Row-Schleife):
   - Wenn include_header=True UND cols nicht leer:
     - Label-Liste: [label for (_, label) in cols]  (Zeit ist bereits in cols[0])
     - Header-HTML:
         <div style="display:flex;gap:8px;padding:5px 0;
                     border-bottom:1px solid {G_INK_FAINT};font-size:11px;
                     font-weight:600;color:{G_INK_MUTED}">
           <span style="font-family:{FONT_DATA};min-width:34px;flex-shrink:0">Zeit</span>
           <span>{' · '.join(label for (_, label) in cols)}</span>
         </div>
     - Diesen Header-String als erstes Element in parts_html einfügen
       (nicht append, sondern prepend / parts_html = [header_html] + parts_html)
     - Alternativ: header_html separat aufbauen, am Ende return header_html + "".join(parts_html)

3. Aufrufstelle 1 — Segment-Rows (Zeile ~266):
   compact_rows = _render_mobile_compact_rows(
       rows,
       friendly_keys=friendly_keys,
       allowed_col_keys=allowed_keys,
       format_modes=format_modes,
       include_header=True,   # NEU
   )

4. Aufrufstelle 2 — Nacht-Rows (Zeile ~286):
   night_compact = _render_mobile_compact_rows(
       night_rows,
       friendly_keys=friendly_keys,
       format_modes=format_modes,
       include_header=True,   # NEU
   )

5. Keine weiteren Änderungen — visible_cols() und alle anderen Hilfsfunktionen bleiben unverändert.
```

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `src/output/renderers/email/html.py` | ~10 (Signatur + Header-Block + 2 Aufruforte) | ja |
| `tests/tdd/test_bug305_mobile_email.py` | ~30 (2 neue Testfälle) | ja |
| **Gesamt** | **~40** | **weit unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** `_render_mobile_compact_rows(rows, ..., include_header=True)` mit einer nicht-leeren
  Row-Liste (mind. 1 sichtbare Spalte)
- **Output:** HTML-String beginnt mit einem Header-Div, dessen Inhalt die Spalten-Labels enthält
  (z.B. `Temp · Wind · Böen · Regen`), gefolgt von den Daten-Rows im bisherigen Format
- **Input (leer):** `rows=[]` oder `cols=[]` — kein Header, leerer String wie bisher
- **Input (`include_header=False`, Default):** Verhalten identisch zur bisherigen Implementierung —
  kein Header, keine Regression an bestehenden Call-Sites außerhalb dieser Datei
- **Side effects:** Keine. Bestehende AC-7–AC-10 in `test_bug305_mobile_email.py` prüfen nur
  das Vorhandensein von Daten-Rows, nicht die Abwesenheit eines Headers — kein Konflikt.

## Acceptance Criteria

- **AC-1:** Given eine E-Mail mit mindestens einem Segment und sichtbaren Spalten (Temp, Wind) / When die mobile Ansicht (≤ 600 px) gerendert wird / Then enthält der `.mobile-compact`-Bereich für dieses Segment eine Header-Zeile mit den Spalten-Labels, die vor den Daten-Rows erscheint
  - Test: (populated after /tdd-red)

- **AC-2:** Given eine E-Mail mit einem Nacht-Block und sichtbaren Spalten / When die mobile Ansicht gerendert wird / Then enthält der `.mobile-compact`-Nacht-Bereich ebenfalls eine Header-Zeile mit den Spalten-Labels direkt nach dem Nacht-Abschnitts-Titel
  - Test: (populated after /tdd-red)

- **AC-3:** Given eine leere Row-Liste wird an `_render_mobile_compact_rows` mit `include_header=True` übergeben / When die Funktion aufgerufen wird / Then gibt die Funktion einen leeren String zurück und erzeugt keine Header-Zeile
  - Test: (populated after /tdd-red)

- **AC-4:** Given `_render_mobile_compact_rows` wird mit `include_header=False` (Default) aufgerufen / When der HTML-Output ausgewertet wird / Then enthält der Output keine Header-Div und entspricht dem bisherigen Verhalten (Regressions-Schutz)
  - Test: (populated after /tdd-red)

- **AC-5:** Given eine E-Mail mit Segment-Rows und aktiven Format-Modi (z.B. `wind` im Symbol-Modus) / When die mobile Ansicht gerendert wird / Then zeigt der Header die konfigurierten Spalten-Labels der tatsächlich sichtbaren Spalten — keine Labels für ausgeblendete Spalten
  - Test: (populated after /tdd-red)

## Known Limitations

- Der Fix korrigiert nur das mobile Kompakt-Layout (`_render_mobile_compact_rows`). Die
  Desktop-Tabelle (`_render_html_table`) hat bereits Spalten-Header via `<thead>` und
  ist nicht betroffen.
- Die Header-Zeile zeigt reine Text-Labels ohne Einheit oder Erläuterung. Einheiten
  werden weiterhin nur in den Datenwerten codiert (z.B. `14°C`, `23 km/h`).

## Out of Scope

- Änderungen an `src/output/renderers/email/helpers.py` oder `visible_cols()`
- Änderungen am Desktop-Layout (`_render_html_table`, `.desktop-only`)
- Sortierung oder Filterung von Spalten im mobilen Header
- Styling-Änderungen am bestehenden mobilen Row-Format

## Changelog

- 2026-05-30: Initial spec erstellt. Ergänzt `_render_mobile_compact_rows()` um `include_header`-Parameter und setzt ihn an beiden Aufruforten auf `True`. Behebt fehlende Tabellenköpfe in der mobilen E-Mail-Ansicht (Issue #463).
