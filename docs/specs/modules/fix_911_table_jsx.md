---
issue: "#911 (follow-up)"
workflow: fix-911-table-jsx
status: approved
---

# Spec: fix-911-table-jsx — Tabellen nach JSX-Vorlage

## Kontext

Workflow `fix-911-table-jsx` korrigiert den Python-Email-Renderer so, dass er der
JSX-Vorlage in `claude-code-handoff/handoff-2026-06-04-v3/…/screen-output-preview.jsx`
vollständig entspricht. Issue #911 bleibt der übergeordnete GitHub-Issue.

## Acceptance Criteria

**AC-1:** Given `_render_html_table` in `src/output/renderers/email/html.py`, When gerendert, Then sind ALLE Styles vollständig inline (kein class="resp", keine externen CSS-Abhängigkeiten für Tabellen-Layout) — analog zur JSX `EmailDataTable`.

**AC-2:** Given eine Zelle mit erhöhtem Schweregrad (z. B. Gust >45 km/h), When gerendert, Then trägt die Zelle den getönten Hintergrund (`#fbeeb8` / `#fad6b8` / `#f6c5bf`) — **ohne** `explicitly_raw`-Gate (Highlight gilt immer, unabhängig von `format_modes`).

**AC-3:** Given die Ausblick-Tabelle (OutlookTable), When gerendert, Then verwendet sie `FONT_MONO` (JetBrains Mono Stack), `borderTop: 2px solid #1d1c1a` als obere Abgrenzung, und korrekte Padding/Typo gemäß JSX-Vorlage (`_otd` / `_oh_style` inline, kein CSS-class).

**AC-4:** Given `TestAC10CellBackgroundHighlighting` in `tests/tdd/test_issue_911_mail_details.py`, When Tests laufen, Then gehen alle AC-10-Tests über den Produktionspfad `render_html` (nicht direkt `_render_html_table`) und sind grün.

## Technische Hinweise

- Referenz JSX: `EmailDataTable` (Zeile 299ff), `hCellStyle`, `dCellStyle`, `hGroupStyle` im Handoff-JSX
- `FONT_DATA` in `html.py` ist der Mono-Stack (`design_tokens.FONT_MONO`)
- Das `explicitly_raw`-Gate (Zeilen 529–537 in `html.py`) entfernen → Highlighting immer aktiv
- AC-10-Tests nutzen bereits `_render()` → `render_html` (Produktionspfad korrekt, aber Tests müssen grün sein)
- LoC-Limit: Standard 250; bei Bedarf Override anfordern
