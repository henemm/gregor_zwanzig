# Context: #831 — Einfach-Darstellung wirkt nicht auf Mobile (Stundenraster) — IMPLEMENTIERT 2026-06-15

## Request Summary
Das Mobile-Stundenraster (.mobile-compact, ≤600px) rendert in **beiden** Modi (Einfach und Roh) immer Zahlen. Nur die Desktop-Tabelle zeigt im Einfach-Modus Ampel-Punkte (🟢🟡🟠🔴). Auf dem Hauptgerät der Zielgruppe (Handy) greift die #814-Einfach-Darstellung nicht.

## Root Cause
`_render_mobile_compact_rows` in `src/output/renderers/email/html.py:116` ruft intern `fmt_val(html=False)` auf. Mit `html=False` gibt `fmt_val` für Ampel-fähige Metriken (wind, gust, precip, pop, cape) **immer Zahlen** zurück — unabhängig von `indicator_keys`. Die Funktion akzeptiert `indicator_keys` gar nicht als Parameter.

## Related Files
| Datei | Relevanz |
|-------|----------|
| `src/output/renderers/email/html.py:116` | `_render_mobile_compact_rows` — zu fixende Funktion |
| `src/output/renderers/email/html.py:82` | `_render_html_table` — Desktop-Pendant (verwendet `html=True`, kennt `indicator_keys`) |
| `src/output/renderers/email/html.py:339` | Aufrufstelle: Segment-Loop rendert `desktop_div` + `mobile_div` |
| `src/output/renderers/email/helpers.py:408` | `fmt_val` — bestimmt Einfach vs. Roh; Ampel nur wenn `html=True AND key in indicator_keys` |
| `src/output/renderers/email/helpers.py:813` | `build_html_indicator_keys` — liefert Set der Ampel-fähigen Metriken |
| `tests/tdd/test_issue_811_mode_matrix.py` | Modus-Matrix-Vertragstest: hat AC-3-Sicherung für Plain-ASCII, aber KEIN Mobile-HTML-Check |
| `tests/tdd/test_bug_636_mobile_email_monospace_grid.py` | #636-Tests: prüfen Monospace-Ausrichtung, immer `friendly_keys=set()` (Roh) |

## Existing Patterns
- **Desktop (≥601px):** `_render_html_table(html=True, indicator_keys=...)` → Ampel ✓
- **Mobile (≤600px):** `_render_mobile_compact_rows(html=False)` → immer Zahlen ✗
- CSS-Schalter: `.desktop-only { display:none }` / `.mobile-compact { display:block }` → @media(min-width:601px) dreht das um
- `indicator_keys` ist das authoritative Set für "diese Metrik zeigt Ampel" (seit #814)

## Fix-Optionen (technische Entscheidung)

**Empfehlung (Option 1): HTML-Tabelle für mobile Einfach-Modus**
Wenn `indicator_keys` gesetzt ist → `mobile-compact` div bekommt statt `<pre>`-Block die gleiche `_render_html_table`-Ausgabe (mit `html=True`, `indicator_keys` durchgereicht). Monospace-Pre bleibt für Roh-Modus bestehen.

- Vorteile: kein Alignment-Hack, kein neues Rendering-Konzept, wiederverwendet getesteten Code
- Nachteil: Verliert die feste Spaltenausrichtung im Einfach-Modus (war #636-Tradeoff für Roh, nicht Einfach)
- Umsetzung: ~20 LoC Delta in html.py + indicator_keys-Parameter an _render_mobile_compact_rows

**Option 3: Kompakte Einzel-Zeichen-Symbole**
Für Ampel: G/Y/O/R statt 🟢🟡🟠🔴 in der monospace Pre — hält Ausrichtung.
- Nachteile: unbekannte Darstellung, neue Symbol-Semantik einführen, schlechtere Lesbarkeit

## Dependencies
- Upstream: `build_html_indicator_keys`, `build_format_modes`, `build_friendly_keys`
- Downstream: `render_full_briefing`, Preview-Service, Scheduler

## Tests die geändert/erweitert werden müssen
- `tests/tdd/test_issue_811_mode_matrix.py`: neuer Mobile-AC prüft dass `.mobile-compact` Ampel zeigt ✅
- `tests/tdd/test_bug_636_mobile_email_monospace_grid.py`: sicherstellen dass Roh-Modus weiterhin Monospace rendert ✅

## Implementation Summary (2026-06-15)

**Was wurde geändert:**
- `_render_mobile_compact_rows()` erhält neuen Parameter `indicator_keys: set[str] | None = None`
- Im Einfach-Modus (wenn `indicator_keys` gesetzt): delegiert an `_render_html_table(html=True, indicator_keys=...)`
- Im Roh-Modus (wenn `indicator_keys` leer): behält den klassischen `<pre>`-Monospace-Block

**Aufrufstelle aktualisiert:**
- `src/output/renderers/email/html.py:339` reicht `indicator_keys` beim Mobile-Aufruf durch

**Tests:** Alle AC-Tests (AC-1/AC-2/AC-3) grün
