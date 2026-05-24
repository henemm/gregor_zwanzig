# Anforderung an Claude Design — Pro-Metrik-Horizont, fehlende Layouts

**Zugehöriges Issue:** #343 (Sub-Issue 2 von #304)
**Erstellt:** 2026-05-23
**Status:** offen — wartet auf Mockups

## Kontext

Wir bauen Klammer-Epic #304 ("Pro-Metrik-Zeithorizont"). Backend (#342) ist live:
jede Metrik im Trip-Wetter-Editor kann pro Tag (heute/morgen/übermorgen) ein-/ausgeschaltet
werden; der Server filtert die Mail-Briefings pro Etappen-Startdatum entsprechend.

Sub-Issue #343 ist der Frontend-Teil im **Trip-Detail-Wetter-Tab**
(`WeatherMetricsTab.svelte` — heute Stand Epic #138). Für die Metrik-Zeile selbst
existiert bereits ein Soll-Mockup:

**`claude-code-handoff/screenshots/soll-flow1D-wizard-step3-wetter.png`**

Es zeigt die drei `HEUTE / MORGEN / ÜBERMORGEN` Pill-Chips zwischen Metrik-Name und
Roh/Indikator-Label. Optik: aktiv = schwarz gefüllt + weiße Schrift, inaktiv = outline
mit grauem Text. Diese Optik wird übernommen.

## Was fehlt — drei Layouts

### 1. TablePreview mit Horizonten (Desktop)

Heute zeigt `TablePreview.svelte` eine einzige Vorschau-Tabelle:
- Spalten = aktivierte Metriken
- Zeilen = vier Beispiel-Stundenwerte (Mo 09/12/15/18 Uhr)

Mit Horizonten soll die Vorschau **drei separate Mini-Tabellen** pro Tag zeigen
(Entscheidung des Product Owners):

```
Heute              Morgen             Übermorgen
┌────┬────┬────┐  ┌────┬────┬────┐  ┌────┬────┬────┐
│Zeit│Temp│Wind│  │Zeit│Temp│ UV │  │Zeit│Wind│ UV │
├────┼────┼────┤  ├────┼────┼────┤  ├────┼────┼────┤
│ … │ … │ … │  │ … │ … │ … │  │ … │ … │ … │
└────┴────┴────┘  └────┴────┴────┘  └────┴────┴────┘
```

Pro Tag erscheinen nur die Metriken, deren `horizons[tag]==true`. Wenn alle
Metriken für einen Tag gleich gewählt sind, sehen alle drei Tabellen gleich aus.

**Offene Design-Fragen:**
- Layout: nebeneinander (drei Spalten) oder untereinander (vertikal gestapelt)?
- Tag-Header-Styling (Eyebrow „HEUTE" wie im Mockup, oder Pill, oder schlichte H4)?
- Was wenn eine Tabelle leer ist (alle Metriken haben Tag X = aus)? Empty-State-Hinweis?
- Sample-Stundenwerte: gleiche vier Slots pro Tag (Mo/Di/Mi 09/12/15/18) oder pro Tag andere Zeiten?

### 2. Mobile-Layout der Metrik-Zeile (< 600px)

Die Desktop-Zeile hat fünf interaktive Elemente:

```
[✓] Temperatur (min/max)   [HEUTE][MORGEN][ÜBERMORGEN]   Roh + Indikator   …
```

Auf Mobile (< 600px) ist das zu eng. Brand-Token verlangt min. 44×44px Touch-Target
für interaktive Elemente.

**Vorschlag (zu validieren):**

```
[✓] Temperatur (min/max)              Roh + Indikator   …
    [HEUTE]  [MORGEN]  [ÜBERMORGEN]
```

Drei Chips brechen in eine eigene Zeile unter dem Metrik-Namen um, voll Touch-Target-tauglich.

**Offene Design-Fragen:**
- Ist dieser Umbruch akzeptabel oder lieber Bottom-Sheet-Drawer („Tippe für Horizont-Einstellungen")?
- Soll Roh/Indikator und „…"-Menü auf Mobile auch umbrechen oder auf eigener Zeile bleiben?
- Visuelle Trennung der gebrochenen Zeile (Indent? Border?)

### 3. SavePresetDialog mit Horizonten

`SavePresetDialog.svelte` zeigt heute beim Speichern eines User-Presets:

```
Name *: [_________________]
Beschreibung: [_________________]
8 Metriken aktiv · 3 Rohwert · 5 Indikator
[ ] Als Standard für neue Trips

[Abbrechen]  [Speichern]
```

Mit Horizonten muss das Preset auch die Horizon-Auswahl persistieren (passiert im
Hintergrund). Frage ist nur: zeigt der Dialog dem User eine **Horizon-Zusammenfassung**?

**Vorschlag (zu validieren):**

```
... (wie heute) ...
8 Metriken aktiv · 3 Rohwert · 5 Indikator
2 Metriken nur heute · 5 alle drei Tage · 1 nur heute+morgen
```

**Offene Design-Fragen:**
- Ist diese Zusatz-Zeile sinnvoll oder Information-Overload?
- Alternativ: keine Erwähnung, Horizonte werden still mitgespeichert?
- Falls erwähnt: Wording-Vorschlag?

## Out of Scope für diese Anfrage

- HorizonChip-Optik selbst (existiert bereits im Mockup `soll-flow1D…`)
- Backend-Verhalten (#342 ist live)
- /account-Verwaltungs-Karte (kommt in #344, eigenes Mockup-Set)
- Konsolidierung der alten Wetter-Editoren (#345, eigenes Mockup-Set)

## Deliverables

Drei Mockups (Desktop, Mobile wo relevant) als PNG im Stil von
`soll-flow1D-wizard-step3-wetter.png`. Bevorzugter Format-Output:
- `soll-issue343-table-preview.png`
- `soll-issue343-mobile-metric-row.png`
- `soll-issue343-save-preset-dialog.png`

Plus kurze Begründung der Design-Entscheidungen (1-2 Sätze pro Layout), insbesondere
bei den drei offenen Fragen je Block.
