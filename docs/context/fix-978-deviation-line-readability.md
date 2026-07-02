# Context: fix-978-deviation-line-readability

## Request Summary

Issue #978: Die Multi-Metrik-Zeile des Deviation-Alerts ist ein Zahlenwurm
(`Niedersch · Schwelle 10,0 mm 6,0 mm ↑ 14,0 mm über`) — Einheit 3× wiederholt,
„,0"-Rauschen, keine optische Trennung. PO musste nachfragen, was die Zeile bedeutet
(= der Befund). PO-Auftrag 2026-07-02: „Setz #978 gleich um".

## Analysis

### Type
Bug (Lesbarkeit/Design-Fidelity, Multi-Metrik-Zweig des Deviation-Alerts).

### SOLL (Design-Vorlage, Multi-Metrik-Mockup + Betreff-Beispiele)
`docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail Vorschläge.html`
(Sektion „Mehrere Metriken", `grep -n "Schwelle 50"` für Zeilen):
- **E-Mail-Zeile:** links `Böen · Schwelle 50` (Schwelle OHNE Einheit), rechts
  `35 ↑ 52 km/h` (Einheit EINMAL, am aktuellen Wert) + gedämpftes/farbiges `über`.
- **Betreff (Top-3):** `Böen 52, Gewitter 55%, Niedersch 14` — nur Zahl; `%` klebt
  am Wert, andere Einheiten entfallen im Betreff.
- **Telegram (Zeile 2):** `Böen 35→52 · Gewitter 30→55% · Niedersch 6→14` — keine
  Einheiten außer `%`.
- Hebel 05 des Design-Dokuments: „Zahlen runden — `1230` statt `1230.0`" → glatte
  Werte ohne `,0`; echte Dezimalwerte (z. B. `0,4 mm` Niederschlag) bleiben mit 1 NK.

### IST-Ursache (code-verifiziert)
`src/output/renderers/alert/render.py`:
- `_email_line()` (Deviation-Multi, auch von `render_telegram` genutzt):
  `{_label} · Schwelle {_val(thr)} · {_val(from)} {arrow} {_val(to)} · {side_label}`
  → `_val()` hängt an JEDEN Wert die Einheit.
- `render_email()` Multi-Zweig data_rows: gleiche Dreifach-Einheit, links/rechts
  ohne klare Trennung.
- `render_subject()` Multi-Top3: `{_label(e)} {_val(e, e.value_to)}` →
  „Niedersch 14,0 mm" statt „Niedersch 14".
- `_val()` → `format_metric_value()` (metric_catalog.py:693-713): mm/°C = IMMER
  1 Nachkommastelle mit Komma → „10,0 mm" auch bei glatten Werten.

### Constraints / Fallstricke
- **`format_metric_value()` NICHT anfassen** — geteilt mit `format_change_line` u. a.
  (#952-Finding F001, dokumentierte Falle). Zahl-ohne-Einheit-Formatierung lokal im
  Alert-Renderer (neuer Helper `_num()`: Katalog-decimals, integer-Display wenn glatt,
  Dezimal-Komma, Tausender-Punkt analog `_format_de_thousand`).
- **Einzel-Metrik-Pfade NICHT ändern:** Einzel-Betreff, Einzel-Datenblock
  (`_datablock_single`), Verdikt — von #952/#957-Tests gepinnt, PO-abgenommen.
- **Onset-Zweig NICHT ändern** (frisch abgenommen, #952).
- Bestands-Assertions, die das ALTE Multi-Format pinnen (test_952_alert_mail_design_fidelity,
  test_957_alert_mail_literal_structure, test_issue_917_alert_renderer), ändern sich
  gewollt mit — Anpassung ist Teil des Scopes, KEINE Abschwächung (neue Assertions
  pinnen das neue SOLL mindestens gleich streng).
- Zweig-Paritätstest aus #952 (`test_952_onset_alert_fidelity.py::TestAC8RendererParity`)
  muss grün bleiben.

### Affected Files
| File | Change | Description |
|---|---|---|
| `src/output/renderers/alert/render.py` | MODIFY | `_num()`-Helper; `_email_line`/Multi-data_rows/Subject-Top3/Telegram-Multi auf Einheit-einmal + zahlenreine Werte |
| `tests/tdd/test_978_deviation_line_readability.py` | CREATE | RED-Tests für neues Zeilen-/Betreff-/Telegram-Format |
| `tests/tdd/test_952_alert_mail_design_fidelity.py`, `test_957_alert_mail_literal_structure.py`, `test_issue_917_alert_renderer.py` | MODIFY | Multi-Metrik-Assertions auf neues SOLL nachziehen |

### Scope Assessment
Files: 1 Produktion + ~4 Test · LoC: ~+60/−25 · Risk: MEDIUM (Versandpfad, aber eng
umrissen; Wächter-Tests vorhanden)

### Verification
- Unit: Renderer direkt (alle 3 Ausgabe-Orte, glatte + echte Dezimalwerte, %-Metrik).
- Staging/Prod: Alert-Preview-Endpoint mit Deviation-Payload (summary_fields:
  `gust_max_kmh`, `thunder_level_max`, `precip_sum_mm` — Werte 35→52/50, 30→55/40,
  6→14/10 wie Vorlage), Screenshot-Vergleich gegen Vorlagen-Mockup.

### Open Questions
- keine — SOLL ist durch Vorlage + PO-Screenshot-Rückfrage eindeutig.
