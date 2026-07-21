---
entity_id: issue_831_mobile_einfach_stundenraster
type: module
created: 2026-06-15
updated: 2026-06-15
status: implemented
version: "1.0"
tags: [email, mobile, rendering, ampel, einfach-modus, briefing]
---

<!-- Issue #831 — Einfach-Darstellung wirkt nicht auf Mobile (Stundenraster) -->

# Issue 831 — Mobile Stundenraster: Ampel-Emojis im Einfach-Modus

## Approval

- [ ] Approved

## Purpose

`_render_mobile_compact_rows` in `src/output/renderers/email/html.py` rendert das
Mobile-Stundenraster (`.mobile-compact`, ≤600px) unabhängig vom gewählten
Darstellungsmodus immer als Zahlen — weil es `fmt_val(html=False)` aufruft und
`indicator_keys` nicht weitergibt. Dieser Fix stellt sicher, dass das Mobile-Raster
im Einfach-Modus dieselben Ampel-Emojis (🟢🟡🟠🔴) zeigt wie die Desktop-Tabelle,
während der Roh-Modus weiterhin den Monospace-`<pre>`-Block aus Issue #636 liefert.

## Source

- **File:** `src/output/renderers/email/html.py`
- **Identifier:** `_render_mobile_compact_rows` (ab Zeile 116)
- **Hilfs-Funktion:** `src/output/renderers/email/helpers.py` — `fmt_val` (ab Zeile 408)

## Estimated Scope

- **LoC:** ~25 (html.py: ~20, helpers.py: 0 — kein Eingriff nötig)
- **Files:** 3 geändert (html.py), 2 Tests erweitert (test_issue_811_mode_matrix.py, test_bug_636_mobile_email_monospace_grid.py)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_render_html_table` | intern (`html.py:82`) | Desktop-Pendant; liefert HTML-Tabelle mit `html=True` und `indicator_keys` — wird für mobilen Einfach-Modus wiederverwendet |
| `fmt_val` | intern (`helpers.py:408`) | Gibt Ampel-Emoji zurück wenn `html=True AND key in indicator_keys`; gibt Zahl zurück wenn `html=False` oder Schlüssel nicht in `indicator_keys` |
| `build_html_indicator_keys` | intern (`helpers.py:813`) | Liefert das autoritative Set der Ampel-fähigen Metriken (wind, gust, precip, pop, cape) — bestimmt, ob Einfach-Modus aktiv ist |
| `build_format_modes` | intern (`helpers.py`) | Liefert `indicator_keys` aus Trip-`display_config` |
| `test_issue_811_mode_matrix.py` | test | Modus-Matrix-Vertragstest; erhält neuen Mobile-Einfach-Check (AC-1 + AC-3) |
| `test_bug_636_mobile_email_monospace_grid.py` | test | #636-Roh-Modus-Sicherung; muss nach Fix weiterhin grün bleiben (AC-2) |

## Implementation Details

### Kern-Änderung in `_render_mobile_compact_rows` (`html.py:116`)

Die Funktion erhält einen neuen optionalen Parameter `indicator_keys: set[str] | None = None`.

**Verzweigungslogik:**

```python
def _render_mobile_compact_rows(rows, cols, indicator_keys=None):
    if indicator_keys:
        # Einfach-Modus: HTML-Tabelle (identisch zum Desktop)
        return _render_html_table(rows, cols, html=True, indicator_keys=indicator_keys)
    else:
        # Roh-Modus: Monospace-<pre>-Block (unverändertes #636-Verhalten)
        ...  # bestehender <pre>-Block-Code bleibt unverändert
```

Wenn `indicator_keys` gesetzt und nicht leer ist, delegiert die Funktion direkt an
`_render_html_table` mit `html=True` und dem durchgereichten `indicator_keys`-Set.
Damit wird die Desktop-Rendering-Logik exakt wiederverwendet — kein neues
Rendering-Konzept, keine Duplikation der `fmt_val`-Aufrufe.

### Aufrufstelle anpassen (`html.py:339`)

Im Segment-Loop, der `desktop_div` + `mobile_div` rendert, wird `indicator_keys`
beim `_render_mobile_compact_rows`-Aufruf durchgereicht:

```python
mobile_div = _render_mobile_compact_rows(rows, cols, indicator_keys=indicator_keys)
```

`indicator_keys` ist an dieser Stelle bereits vorhanden (es wird auch für
`_render_html_table` des Desktop-Blocks verwendet).

### Keine Änderung an `fmt_val` oder `helpers.py`

`fmt_val` funktioniert bereits korrekt — es gibt Ampel-Emojis zurück wenn
`html=True AND key in indicator_keys`. Das Problem lag ausschließlich darin, dass
`_render_mobile_compact_rows` diesen Pfad nie aktiviert hat. `helpers.py` bleibt
unverändert.

### CSS-Schalter bleibt unverändert

`.desktop-only { display:none }` / `.mobile-compact { display:block }` + das
@media-Flip bei ≥601px bleiben unberührt. Nur der Inhalt des `mobile-compact`-Divs
ändert sich im Einfach-Modus von `<pre>` zu einer HTML-Tabelle.

## Expected Behavior

- **Input:** `_render_mobile_compact_rows(rows, cols, indicator_keys={"wind", "gust", "precip", "pop"})` — Einfach-Modus mit Ampel-Metriken
- **Output:** HTML-Tabelle (identisch zur Desktop-Ausgabe von `_render_html_table`) mit Ampel-Emojis (🟢🟡🟠🔴) für die übergebenen Metriken
- **Input (Roh):** `_render_mobile_compact_rows(rows, cols, indicator_keys=None)` oder `indicator_keys=set()`
- **Output (Roh):** Unveränderter Monospace-`<pre>`-Block (ASCII-Zahlen, #636-Verhalten)
- **Side effects:** Keine — rein rendererseitige Änderung, kein API-Vertrag, keine Persistenz

## Acceptance Criteria

- **AC-1:** Given ein Trip mit `use_friendly_format=true` für mind. eine Ampel-Metrik (z.B. Wind) / When das HTML-Briefing bei mobiler Viewport-Breite (≤600px via `.mobile-compact`) gerendert wird / Then zeigt das Stundenraster für diese Metrik ein Ampel-Emoji (🟢/🟡/🟠/🔴), nicht die bloße Zahl — nachgewiesen durch einen echten `render_full_briefing`-Aufruf, dessen HTML-Output das `.mobile-compact`-div auf Ampel-Emojis geprüft wird.
  - Test: `test_issue_811_mode_matrix.py` — neuer Testfall `test_mobile_compact_einfach_shows_ampel`

- **AC-2:** Given derselbe Trip mit `use_friendly_format=false` für alle Metriken (Roh-Modus) / When mobil gerendert / Then zeigt das Stundenraster weiterhin ASCII-Zahlen im Monospace-`<pre>`-Block (unverändertes #636-Verhalten) — das `.mobile-compact`-div enthält `<pre>` und keine HTML-Tabelle.
  - Test: `test_bug_636_mobile_email_monospace_grid.py` — bestehende Tests müssen nach Fix weiterhin grün sein; optional neuer Roh-Modus-Assertion

- **AC-3:** Given dasselbe Briefing / When die Desktop-Tabelle (≥601px via `.desktop-only`) und die Mobile-Ansicht (≤600px via `.mobile-compact`) verglichen werden / Then zeigen beide im Einfach-Modus Ampel-Emojis für Wind/Böen/Regen/Regenwahrsch., und beide zeigen im Roh-Modus ASCII-Zahlen — kein Modus-Mismatch zwischen Viewport-Klassen.
  - Test: `test_issue_811_mode_matrix.py` — Modus-Matrix-Assertion prüft Desktop-div und Mobile-div auf identischen Modus-Ausdruck

## Known Limitations

- Im Einfach-Modus verliert das Mobile-Raster die feste Spaltenausrichtung (die `<pre>`-Monospace-Ausrichtung aus #636 war ein Tradeoff für den Roh-Modus — Einfach-Modus profitierte nie zuverlässig davon, da Emojis unterschiedliche Breiten haben). Dies ist ein akzeptierter Tradeoff: Ampel-Lesbarkeit hat Vorrang vor ASCII-Ausrichtung im Einfach-Modus (Design-Prinzip: Lesbarkeit > Optik, PO bestätigt 2026-05-25).
- Die Änderung betrifft nur den Python-HTML-Renderer (`src/output/renderers/email/html.py`). Telegram- und SMS-Kanäle sind nicht betroffen.

## Changelog

- 2026-06-15: Implementation abgeschlossen — `_render_mobile_compact_rows` delegiert an `_render_html_table` im Einfach-Modus
- 2026-06-15: Initial spec erstellt — Issue #831
