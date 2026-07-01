# Mini-Spec: Alert-Mail-HTML — echte Struktur der Design-Vorlage übernehmen

## Was ändert sich
`render_email()` (Deviation-Zweig, `src/output/renderers/alert/render.py`) bekommt die tatsächliche
Struktur aus `docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail Vorschläge.html`
(Zeilen 156-247, `.mail-body`), nicht mehr nur die Farben/Schrift:

- **1 Event:** Verdikt-Zeile mit Pfeil + Δ% + Schwellwert-Bezug (`↓ −50 % · jetzt unter Schwelle 800`
  statt nur `↓ CAPE`). Datenblock mit **3 Zeilen**: (1) Kürzel·Einheit / Wert-Vergleich mit Δ%,
  (2) Alarm-Schwelle X / „jetzt über/unter" mit ✓/✗, (3) „Wo & wann" / km-Spanne (+ Uhrzeit, falls
  `occurred_at` vorhanden — die Vorlage zeigt eine Zeitspanne aus dem Segment, die im
  `AlertEvent`-Modell nicht existiert; hier bewusst nur der einzelne `occurred_at`-Zeitpunkt, keine
  Spanne, da die Datengrundlage fehlt).
- **≥2 Events:** Verdikt-Zeile „N über Schwelle" (analog Betreff-Logik). Datenblock: **1 Zeile pro
  Event** (Kürzel + Schwelle / Wert-Vergleich + über/unter-Badge, gedämpft wenn unter Schwelle).
  Footer zusätzlich mit km-Spanne (wie Vorlage).
- Alle Farben/Schriften weiterhin aus `design_tokens.py` (inline Styles, kein `<style>`-Block —
  E-Mail-Client-Kompatibilität).

## Was darf sich nicht ändern
- Plain-Text-Variante bleibt wie bisher (Kürzel + gerundete Werte aus #952).
- Onset/Nowcast-Pfade, Legacy-Shim, SMS/Telegram unverändert.
- Konstante C9 (kein „halbiert"/„verdoppelt" — generische H1 bleibt).
- Bestehende 88 Tests aus #952 bleiben grün (nur `render_email`-HTML-Struktur ändert sich,
  bestehende AC-4-Tests prüfen auf Token-Werte/Abwesenheit alter Hex-Werte — bleiben gültig).

## Manuelle Test-Schritte
1. `_cape_msg()`-Fixture (1 Event) → `render_email()` → HTML enthält Verdikt-Text mit `%` und
   „Schwelle", Datenblock mit 3 separaten Zeilen.
2. Multi-Event-Fixture (≥2 Events, gemischt über/unter Schwelle) → Verdikt „N über Schwelle",
   je Event eine Zeile, gedämpfte Zeile für unter-Schwelle-Event.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Test: 1-Event-HTML enthält Δ%-Text + „Schwelle {X}" + 3 Datenzeilen-Marker
- [ ] Test: Multi-Event-HTML enthält „N über Schwelle" + 1 Zeile pro Event + km-Spanne im Footer
- [ ] Bestehende #952-Tests (`test_952_alert_mail_design_fidelity.py`, AC-4) bleiben grün
