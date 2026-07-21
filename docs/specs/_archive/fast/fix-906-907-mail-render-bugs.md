# Mini-Spec: fix-906-907-mail-render-bugs

Issues: #906 (reopen) + #907 · Workflow: fix-906-907-mail-render-bugs (isolierter Worktree)

## Hintergrund
Bei der E2E-Sichtprüfung der echten Briefing-Mail (nach #898-901) zwei live-Bugs gefunden.
#906 war zuvor scheinbar gefixt, der Fix ging aber durch ein Parallel-Session-Index-Race
verloren (Commit ab1f5583 enthielt ihn nicht). Daher hier im isolierten Worktree.

## Was ändert sich (2 Fixes in src/output/renderers/email/html.py)
- **#906 (Trend-Chip-Entities):** `temp_range` wird als Klartext aus `tok["temp_str"]`
  gebaut (echtes `–`, Leerzeichen vor `°C`) statt aus dem entity-haltigen `temp_html`.
  `temp_range` geht durch `pill_html`/`html.escape` → darf KEINE HTML-Entities enthalten,
  sonst doppelt-escaped → `10&#8211;18&thinsp;°C` sichtbar.
- **#907 (nonepadding):** In `_render_email_stat` (Z. 147) im last-Fall `border = ""`
  statt `"none"`. Sonst entsteht `style="nonepadding:..."` (ungültiges CSS) in der
  letzten Stats-Zelle (Segmente).

## Was darf sich nicht ändern
- Stundentabelle / `temp_html`-Pfad (dort werden Entities korrekt als HTML interpretiert).
- Alle #898-901-Punkte, Genauigkeits-Kreis, Deep-Links, Gitter.
- `test_issue_811_mode_matrix.py` (Renderer-Gate) bleibt grün.

## Manuelle Test-Schritte
1. Echte Briefing-Mail mit 3-Tages-Trend + Stats-Grid gegen Staging rendern (`/api/preview`).
2. Trend-Chips: Temperatur lesbar (`10–18 °C`), keine `&#`/`thinsp`.
3. Stats-Grid: letzte Zelle (Segmente) hat gültiges `style` (kein `nonepadding`).

## Inline-Tests (während Implementierung)
- [ ] #906: render_html mit multi_day_trend (temp_lo/temp_hi) → kein `&#`/`thinsp` im Trend-Chip, lesbare Range
- [ ] #907: render_html mit stage_stats → kein `nonepadding` im HTML; letzte Stat-Zelle hat valides `padding:`-Style

## Acceptance Criteria

**AC-1:** Given eine HTML-Briefing-Mail mit mehrtägigem Trend (Felder `temp_lo`/`temp_hi` wie vom Scheduler) / When `render_html()` rendert / Then enthalten die Trend-Chips KEINE rohen oder doppelt-escapten HTML-Entities (`&#`, `&amp;#`, literales `thinsp`) und die Temperatur erscheint lesbar (z.B. `10–18 °C`)

**AC-2:** Given eine HTML-Briefing-Mail mit Stage-Stats / When das Header-Stats-Grid gerendert wird / Then enthält keine Stat-Zelle das ungültige CSS-Präfix `nonepadding:` — die letzte Zelle (Segmente) hat ein valides `style`, das mit `padding:` beginnt
