# Mini-Spec: #1125 — Plain-Text-Teil der Compare-Mail filtert enabled_metrics

## Problem
`render_compare_email()` reicht `enabled_metrics` nur an den HTML-Renderer durch, nicht
an `render_comparison_text()`. Wählt ein Nutzer im Editor eine Übersichts-Metrik ab
(z.B. Schneehöhe), verschwindet die Zeile aus der HTML-Übersicht, bleibt aber im
Plain-Text-Teil derselben Mail sichtbar → HTML und Text widersprechen sich.

Vorbestehend (galt schon für temp_max/wind_max/sunny_hours/cloud_avg), nicht durch
#1105 verursacht.

## Was ändert sich
- `render_comparison_text()` bekommt einen Parameter `enabled_metrics: set | None = None`.
- Die sechs Übersichts-Zeilen je Ort (Temp max, Wind, Sonne, Wolken, Schneehöhe,
  Neuschnee) werden nur gerendert, wenn `enabled_metrics is None` **oder** die
  zugehörige Renderer-Metrik-ID im Set enthalten ist — exakt die Semantik von
  `_visible_metrics()` im HTML-Pfad (`src/output/renderers/email/compare_html.py:242`).
  ID-Zuordnung: Temp max→`temp_max`, Wind→`wind_max`, Sonne→`sunny_hours`,
  Wolken→`cloud_avg`, Schneehöhe→`snow_depth_cm`, Neuschnee→`snow_new_cm`.
- `render_compare_email()` reicht sein `enabled_metrics` an `render_comparison_text()`
  durch (analog HTML-Aufruf).

## Was darf sich nicht ändern
- `enabled_metrics=None` → **alle** sechs Zeilen sichtbar (rückwärtskompatibler Default,
  wie HTML).
- Amtliche Warnungen (`⚠️`-Zeilen aus `render_official_alerts_plain()`) bleiben **immer**
  sichtbar, unabhängig von `enabled_metrics` (wie die "warn"-Zeile im HTML).
- Die `STUNDENVERLAUF`-Sektion des Plain-Text bleibt in diesem Slice **unverändert**
  (hourly_metrics/hourly_enabled = eigener Scope #1106/#1107, hier bewusst nicht
  angefasst → keine Gate-Erosion).
- Kopfzeilen, Sortierung (alphabetisch), Footer unverändert.

## Manuelle Test-Schritte
1. Compare-Subscription mit Teilmenge der Metriken (z.B. nur Temp + Wind) auf Staging
   konfigurieren, Briefing auslösen.
2. Echt zugestellte Staging-Compare-Mail (`gregor-test@henemm.com`) via IMAP abrufen.
3. Prüfen: HTML-Übersicht **und** Plain-Text-Teil zeigen genau dieselbe Metrik-Teilmenge.
4. Amtliche Warnungen (falls vorhanden) im Plain-Text weiterhin sichtbar.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Test: `render_comparison_text(result, enabled_metrics={"temp_max"})` enthält
      Temp-max-Zeile, aber **nicht** Wind/Sonne/Wolken/Schneehöhe/Neuschnee.
- [ ] Test: `enabled_metrics=None` → alle sechs Zeilen vorhanden (Default).
- [ ] Test: amtliche Warn-Zeile bleibt bei gefiltertem `enabled_metrics` sichtbar.
