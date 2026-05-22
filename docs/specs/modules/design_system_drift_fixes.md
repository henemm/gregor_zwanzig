# Spec: Design-System Drift-Fixes (AP-001 + AP-009)

**Issue:** Design-System-Audit (nach Einpflegen der Claude-Design-Dokumente)  
**Status:** draft

---

## Kontext

Beim Drift-Audit mit den ANTI-PATTERNS.md-Befehlen wurden in bestehenden Komponenten
zwei Klassen von Verletzungen gefunden. Diese Spec beschreibt die Korrekturen.

---

## Acceptance Criteria

**AC-1:** Given `AlertRuleRow.svelte` enthält zwei native `<select>`-Tags (AP-001),  
When die Datei gespeichert wird,  
Then sind beide durch `<Select>` aus `$lib/components/ui/select` ersetzt (der Import ist bereits vorhanden).

**AC-2:** Given `PreviewCard.svelte` enthält die Emoji `📧` und `💬` (AP-009),  
When die Datei gespeichert wird,  
Then sind die Emoji durch Plaintext ersetzt: `E-Mail-Vorschau →` und `SMS-Vorschau →`.

**AC-3:** Given `PresetRow.svelte` enthält das Zeichen `✓` als Active-Marker (AP-009),  
When die Datei gespeichert wird,  
Then ist das Zeichen entfernt; der aktive Zustand bleibt allein über `.preset-row.active`-CSS sichtbar.

**AC-4:** Given `WeatherMetricsTab.svelte` enthält `Gespeichert ✓` (AP-009),  
When die Datei gespeichert wird,  
Then ist der String auf `Gespeichert` reduziert (ohne Sonderzeichen).

**AC-5:** Given alle vier Dateien geändert sind,  
When `grep -rnP '✓|📧|💬' frontend/src/lib/` läuft,  
Then gibt der Befehl keine Treffer mehr aus (außer in `.md`-Dateien).

---

## Nicht im Scope

- `weatherEmoji.ts` wird NICHT geändert — die Datei liefert Wetter-Symbole für
  den E-Mail-Renderer, nicht für die UI. Sie liegt außerhalb der Browser-UI
  (nur serverseitig genutzt). AP-009 gilt nur für Produkt-UI, nicht für
  E-Mail-Template-Helfer.
- Keine Tests nötig: reine Text-/Tag-Substitution ohne Verhaltensänderung.

---

## Betroffene Dateien

- `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte`
- `frontend/src/lib/components/trip-detail/PreviewCard.svelte`
- `frontend/src/lib/components/trip-detail/PresetRow.svelte`
- `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
