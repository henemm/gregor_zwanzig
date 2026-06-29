# Context: fix-911-mail-details (#911 — E-Mail Details)

## Request Summary
12 visuelle Detail-Korrekturen an der **Trip-Briefing-Mail**, gemessen an der
importierten Design-Vorlage „Gregor 20 — Mail Vorschau.html" (Claude-Design-Projekt
`019dfcf4…`). **Nur die 12 Punkte aus #911** — kein Wholesale-Replace des Renderers.
Die Vorlage dient als Referenz für Styling/Werte je Punkt.

## Vorlage (Referenz, im Repo gesichert)
- `docs/design-requests/issue_911_mail_vorschau/screen-output-preview.jsx` — `EmailPreview`
  (JSX = Wahrheit): Header, Tageslage+Vortag, Segment-Tabellen, Ausblick-Tabelle, RiskLegend, Footer.
- `docs/design-requests/issue_911_mail_vorschau/tokens.css` — Farb-/Spacing-Tokens.

## Betroffene Datei (einzige Code-Datei)
`src/output/renderers/email/html.py` (1331 Zeilen) — der HTML-Briefing-Renderer.
Tokens in `src/output/renderers/email/design_tokens.py`.

## IST → SOLL-Kartierung der 12 Punkte

| # | Bereich | IST (html.py) | SOLL (Vorlage) |
|---|---------|---------------|----------------|
| 1 | Vortagesvergleich-Headline Farbe | `_eyebrow("… VORTAGESVERGLEICH")` (L1178) → grau `#9a978d` | gleiche Farbe wie TAGESLAGE → Akzent-Orange `#c45a2a` (`accent=True`). **Hinweis:** Vorlage nutzt graues „vs. Gestern"; #911 verlangt aber explizit *gleiche Farbe wie TAGESLAGE* → Orange. Issue-Text gewinnt. |
| 2 | Indikator-Position | `f"{_trend_glyph} VORTAGESVERGLEICH"` (L1178) → Glyph **vor** Text | Glyph **hinter** die Headline: `f"VORTAGESVERGLEICH {_trend_glyph}"` (Vorlage `EmailVortag`: Label → Symbol → Text) |
| 3 | Spalten-Reihenfolge Segment-Tabelle | `visible_cols(rows)` (L459) — Reihenfolge folgt NICHT der Trip-Editor-Konfig | Spalten links→rechts = im Trip-Editor konfigurierte Metrik-Reihenfolge (`dc.metrics`-Order). Backend-Screenshot „Reihenfolge · links→rechts in der Email-Tabelle" ist die Autorität, **nicht** die feste Vorlage-Demo-Reihenfolge. ⚠️ Klären in Analyse: ob `visible_cols` Konfig-Order bereits respektiert. |
| 4 | Tabellen-Styling | `_render_html_table` (L447): `<th>`/`<td data-label>` mager, Grid via `G_INK_FAINT` `#9c9a90` + CSS-Block | Vorlage `EmailDataTable`: Header weiß `#fff`, Header-Text `#3a3835` 11px 600, Header-borderBottom `#e6e1d3`, Zell-Linien `#f0ece1`, Daten 13px mono. Inline-Styles (Outlook-fest). |
| 5 | Letzte Spalte umbenennen | Header-`<th>…>·</th>` (L468) | „Risk" (Vorlage `hCellStyle("center")`). **Mechanismus:** per-Stunde-Risiko-Dot aus Schwellwerten (`_row_risk`, L121: thunder/gust/wind/precip/pop/vis) → Ampel-Dot. |
| 6 | Space über DISTANZ/AUFSTIEG | Stats-Grid `<table style="border-top…padding:14px 0">` (L744) — `_render_email_stat` td hat `padding:0 12px 0 0` (kein top) → Labels stoßen an Linie | Top-Abstand zwischen border-top und Labels (z.B. `padding-top` auf td; Tabellen-`padding` greift in Mail-Clients unzuverlässig) |
| 7 | METRIKEN-ÜBERBLICK Spacing (Desktop) | `metrics_summary_html` (L1128): `padding:8px 16px`, Pills via `" ".join(...)` ohne Flex-Gap | Vorlage `EmailMetricsSummary`: `padding:14px 28px 18px`, bg `#fdfcf8`, borderBottom `#e6e1d3`, Pills in `flex; gap:6; flex-wrap; margin-top:10` |
| 8 | Prognose-Genauigkeit (ACC) fehlt | Ausblick als Chip-Liste, Konfidenz nur als kleiner Dot „Prognose" inline (L1064) | ACC-Spalte in der Ausblick-**Tabelle** (Vorlage `OutlookTable`: letzte Spalte „ACC" = RiskDot je Tag) |
| 9 | Headline „AUSBLICK · NÄCHSTE 3 TAGE" fehlt | Eyebrow in #899 entfernt (L1103) | Eyebrow „Ausblick · nächste 3 Tage" wieder einsetzen |
| 10 | Zellen-Hintergrund = Warn-Level | Highlighting nur als Text-Farbe im `<span>` (L539-540) | Getönter **Zell-Hintergrund** je Schweregrad (Vorlage `RISK_CELL`: caution `#fbeeb8`, warn `#fad6b8`, danger `#f6c5bf`) auf den Schweregrad-Spalten (Wind/Gust/Rain/Rain%/Thndr%/Visib) |
| 11 | Footer-Dots-Format | RISK-Legende mit **Emoji**-Kreisen (🟢🟡🟠🔴) auf dunklem Footer | Flache CSS-Dots (4-Stufen, `_risk_dot`) mit „RISK"-Präfix auf hellem Section-Hintergrund **über** dem dunklen Footer (Vorlage `RiskLegend`) |
| 12 | Ausblick-Tabelle übernehmen | Chip-basierter Ausblick | Vorlage `OutlookTable`: Zeile/Tag, Spalten Tag·N·D·R·PR·Wind·Böen·Gew·ACC, Inhalte analog SMS-Tokens, Zell-bg = Warn-Level, Code-Legende darunter |

## Bestehende Patterns (wiederverwendbar)
- `_risk_dot(color)` (L98) — flache CSS-Dots; aktuell 3 Ring-Farben → für 4-Stufen erweitern.
- `_RISK_DOT_COLORS` / `_row_risk` (L121-142) — 3-Stufen (ok/watch/risk). Vorlage = 4-Stufen
  (ok/caution/warn/danger). Issues 10/11/12 verlangen 4-Stufen-Tönung (`RISK_CELL`/sev-Funktionen).
- `_eyebrow(text, accent)` (L90) — Eyebrow-Headlines; `accent=True` = Orange.
- `pill_html`, `build_metrics_summary_pills` — Metriken-Überblick-Pills.

## Risiken & Überlegungen
- **4-Stufen-Severity-Migration:** Issues 4/10/11/12 ziehen die Vorlage-4-Stufen-Skala
  (caution/warn/danger + getönte Zellen) nach. Bewusst auf Tabellen-Rendering begrenzen —
  keine Änderung an Risk-Engine/Alert-Logik.
- **Issue 1 vs. Vorlage-Konflikt:** Vorlage = graues „vs. Gestern", #911 = „gleiche Farbe wie
  TAGESLAGE". Issue-Text ist Autorität → Orange. Beim AC-Approval bestätigen lassen.
- **Issue 3 Interpretation:** Spalten-Order = Konfig-Order (nicht feste Vorlage-Order).
  In Analyse prüfen, wie `visible_cols` ordnet.
- **Mail-Gates:** `renderer_mail_gate.py` blockt Commit bis (1) `test_issue_811_mode_matrix.py`
  grün + (2) `briefing_mail_validator.py` gegen echte Staging-Mail grün.
- **Mobile-Pfad** (`_render_mobile_hour_list`, L164) ggf. mitziehen wo sinnvoll (Issue 10/11).

## Existing Specs
- `docs/specs/modules/briefing_mail_validator.md`
- `docs/reference/mail_validators.md`
- Letzte Mail-Layout-Iterationen: #898–901 (Gitter/Head/Trend-Chips/Footer), #906/#907 (Render-Bugs).
