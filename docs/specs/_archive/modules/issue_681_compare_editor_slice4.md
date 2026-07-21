---
entity_id: issue_681_compare_editor_slice4
type: module
created: 2026-06-09
updated: 2026-06-09
status: draft
version: "1.0"
tags: [frontend, compare, editor, design-compliance, epic-677]
---

# Compare-Editor Slice 4 — Fidelity-Tabs „Layout" + „Versand" (CE_)

## Approval

- [ ] Approved

## Purpose

Bringt die Tab-Inhalte **„Layout"** und **„Versand"** des Compare-Editors (Epic #677) vollständig auf
CE_-Fidelity: Step4Layout erhält das `∞/8/—`-Badge je Kanal, die ↳ Detail-Pill für Spalten jenseits
Telegram-Limit und eine Live-Vorschau (`CE_LayoutPreview` als neue Svelte-Komponente), die
kanalspezifisch entweder Empfehlung-Banner + Monospace-Tabelle (Email/Telegram) oder SMS-Fließtext
≤ 140 Zeichen rendert. Step5Versand wird auf das 3-Kacheln-Grid (Versand/Zeitfenster/Horizont) plus
ChannelRow mit Sub-Label umgebaut; der Aktivierungs-Banner wechselt von grün (bereit) zu dunkel
(noch nicht bereit) je nach `versandVisited && canActivate`. Im Create-Modus-Header von
CompareEditor.svelte kommt ein „Briefing aktivieren"-Button hinzu, der disabled ist bis der
Versand-Tab besucht wurde und dann `wiz.saveComparePreset()` aufruft.

> **Design-Quelle (bindend):** `claude-code-handoff/current/jsx/screen-compare-editor.jsx` —
> `CE_LayoutTab` (Z. 363–438), `CE_LayoutPreview` (Z. 440–517), `CE_VersandTab` (Z. 519–577),
> `ScreenCompareEditor`-Header (Z. 666–674).

## Source

- **Datei A (ergänzt):** `frontend/src/lib/components/compare/steps/Step4Layout.svelte`
- **Datei B (neu):** `frontend/src/lib/components/compare/LayoutPreview.svelte`
- **Datei C (Rework):** `frontend/src/lib/components/compare/steps/Step5Versand.svelte`
- **Datei D (ergänzt):** `frontend/src/lib/components/compare/CompareEditor.svelte`

> Schicht: **Frontend / User-UI** → `frontend/src/...` (SvelteKit, gregor20.henemm.com).
> `compareEditorSave.ts` braucht keine Änderung — `channel_layouts`-RMW ist bereits implementiert.

## Estimated Scope

- **LoC:** ~300–380
- **Files:** 4 (1 neu, 3 ergänzt/reworked)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareWizardState` | reuse | `schedule`, `timeWindowStart`, `timeWindowEnd`, `forecastHours`, `pickedIds`, `saveComparePreset()` |
| `compareEditorSave.ts` | reuse | `channel_layouts`-RMW (unverändert, kein Änderungsbedarf) |
| `compareEditorLogic` | reuse | `doneTabs()`, `versandVisited`-Flag |
| `CompareEditor.svelte` | ergänzt | Header-Button „Briefing aktivieren" + `versandVisited`-Prop |
| `Step4Layout.svelte` | ergänzt | Badge-Spalte, ↳ Detail-Pill, `LayoutPreview`-Import |
| `LayoutPreview.svelte` | neu | Kanalspezifische Live-Vorschau mit statischen Dummy-Daten |
| `Step5Versand.svelte` | Rework | 3-Kacheln + ChannelRow sub-label + Aktivierungs-Banner-Logik |
| `OutputLayoutEditor` | reuse | Spalten-Editor (bestehendes Verhalten bleibt unverändert) |
| `Eyebrow`, `Btn`, `GCard` | reuse | Atom-Bausteine |
| `CE_CHANNELS` | reuse | Kanaldefinitionen (∞/8/0 maxCols) als lokale Konstante in Step4Layout |

---

## Acceptance Criteria

**AC-1:** Kanalwechsel aktualisiert Spalten-Limit-Hinweis und Live-Vorschau
Given: Tab „Layout" ist geöffnet, beliebiger Kanal aktiv.
When: Nutzer klickt einen anderen Kanal-Button (Email / Telegram / SMS).
Then: Das Badge rechts im Kanal-Button zeigt `∞` (Email), `8` (Telegram) oder `—` (SMS). Der
Hinweis-Text unter der Spalten-Liste wechselt auf den kanalspezifischen Text (JSX Z. 419). Die
rechte Vorschau-Spalte (`data-testid="compare-step4-layout-preview"`) rendert neu: Email →
Empfehlung-Banner + Tabelle mit Sonne-Spalte; Telegram → gleiche Tabelle ohne Sonne-Spalte (max 5
Spalten); SMS → Fließtext-Block.

**AC-2:** ↳ Detail-Pill für Telegram-Überlauf
Given: Kanal Telegram aktiv, in der Spalten-Liste sind mehr als 8 aktivierte Spalten vorhanden.
When: Nutzer schaut auf die Spalten-Liste.
Then: Jede Zeile an Position > 8 (index >= 8, 0-basiert) mit aktivierter Spalte zeigt rechts
eine Pill mit Text `↳ Detail` in Farbe `var(--g-warn)`, font-weight 600, Mono-Font; die Zeile
selbst hat opacity 0.55 und einen orange-getönten Hintergrund (`rgba(192,138,26,0.05)`). Die
Pill fehlt bei Email und SMS (keine Begrenzung / keine Tabelle). Testid:
`compare-step4-detail-pill-<index>`.

**AC-3:** SMS-Vorschau zeigt Fließtext ≤ 140 Zeichen
Given: Kanal SMS aktiv in Tab „Layout".
When: Nutzer betrachtet die rechte Vorschau-Spalte.
Then: Ein Monospace-Block (`data-testid="compare-step4-preview-sms"`) zeigt Fließtext in der Form
`MO DD.MM · Ortsvergleich / #1 <Ortsname> · <Score>p / Schnee …` mit statischen Dummy-Werten.
Ein Hinweis-Text darunter lautet „SMS hat keine Tabelle — Fließtext." Der gesamte sichtbare Text
des Blocks ist ≤ 140 Zeichen. Es gibt keine Tabellen-Elemente (`<table>`, `<tr>`, `<td>`).

**AC-4:** „Briefing aktivieren" disabled bis Versand-Tab besucht; danach echter Persistenz-Pfad
Given: Compare-Editor im Create-Modus (`mode="create"`), Nutzer hat den Versand-Tab noch nicht
besucht (`versandVisited === false`).
When: Nutzer schaut auf den Header-Bereich.
Then: Ein Button `data-testid="compare-editor-activate"` mit Label „Briefing aktivieren" ist
sichtbar und hat `disabled` (oder `aria-disabled="true"`) sowie optisch gedimmte Darstellung
(opacity 0.4, cursor not-allowed). Ein Mono-Hinweis „Versand einrichten zum Aktivieren" ist
daneben sichtbar.
Given: Nutzer besucht den Versand-Tab (versandVisited wird true, `done.has('versand')` true).
When: Nutzer klickt „Briefing aktivieren".
Then: `wiz.saveComparePreset()` wird aufgerufen (echter Persistenz-Pfad, user_id aus Auth-Kontext,
kein `"default"`-Fallback). Der Button-Klick schreibt die Daten des eingeloggten Nutzers A — nicht
eines anderen Nutzers.

**AC-5:** Spalten-Reihenfolge pro Kanal erhalten
Given: Nutzer sortiert im Kanal Email Spalten um, wechselt dann auf Telegram, sortiert dort
anders, wechselt zurück auf Email.
When: Kanal-Wechsel.
Then: Jeder Kanal zeigt seine eigene zuletzt eingestellte Spalten-Reihenfolge (aus
`wizard.channelLayouts[channel]`). Der `$effect`-Sync in Step4Layout schreibt alle drei Kanäle
nach `wizard.channelLayouts` sobald sich ein Bucket ändert. `compareEditorSave.ts` liest
`channelLayouts` per RMW (bestehende Felder in `display_config` bleiben erhalten).

---

## Implementation Details

### LayoutPreview.svelte (neu)

Reine UI-Komponente ohne Store-Abhängigkeit. Empfängt `channel: ChannelId` und `pickedIds: string[]`.

```
Props: { channel: 'email' | 'telegram' | 'sms', pickedIds: string[] }

Statische Dummy-Daten (keine API-Calls):
  DUMMY_LOCATIONS = [
    { id: 'loc-01', name: 'Hintertux', score: 87, snow: 180, newSnow: 22,
      wind: 18, gust: 31, dir: 'NW', feels: -3, sun: 4.5 },
    { id: 'loc-07', name: 'Ischgl',    score: 74, snow: 140, newSnow: 12,
      wind: 24, gust: 40, dir: 'W',  feels: -5, sun: 2.1 },
    { id: 'loc-08', name: 'Zermatt',   score: 71, snow: 210, newSnow: 8,
      wind: 31, gust: 55, dir: 'SW', feels: -7, sun: 5.8 },
  ]
  rows = pickedIds.length > 0
    ? DUMMY_LOCATIONS.filter(d => pickedIds.includes(d.id)).slice(0, 5)
    : DUMMY_LOCATIONS.slice(0, 3)   // Fallback: alle 3 zeigen wenn keine pickedIds

Leer-State: rows.length === 0 (unmöglich durch Fallback) → Hinweis-Div

SMS-Branch (channel === 'sms'):
  Zeige Monospace-Block:
    "MO 09.06 · Ortsvergleich
     #1 {rows[0].name.slice(0,22)} · {rows[0].score}p
     Schnee {rows[0].snow}cm +{rows[0].newSnow} · {rows[0].feels>0?'+':''}{rows[0].feels}° · {rows[0].wind}/{rows[0].gust}{rows[0].dir}"
  data-testid="compare-step4-preview-sms"
  Hinweis: "SMS hat keine Tabelle — Fließtext."

Email/Telegram-Branch:
  cols = channel === 'email'
    ? ['Score', 'Schnee', 'Neuschnee', 'Wind/Böen', 'Temp', 'Sonne']
    : ['Score', 'Schnee', 'Neuschnee', 'Wind', 'Temp']
  Empfehlung-Banner: grüner linker Border + Gradient-Hintergrund, Eyebrow „Empfehlung · Mo 09.06.",
    Ortsname fett, weil-Begründung (Schnee/Wind/Temp aus rows[0])
  Tabelle: Mono-Font, tabular-nums, th-Header (Ort + cols), tbody rows; Zeile 0 hat leicht
    grünen Hintergrund + fette Schrift
  Footer-Label: 'Email · alle Spalten + Detail-Block je Ort' oder 'Telegram · {cols.length} Spalten'
  data-testid="compare-step4-layout-preview"
```

### Step4Layout.svelte — Badge + Detail-Pill + Preview (ergänzen)

```
1. Lokale Konstante CE_CHANNELS (statt bestehender CHANNELS):
   CE_CHANNELS = [
     { id: 'email',    label: 'Email',    maxCols: Infinity, hint: 'alles · Empfehlung + Tabelle + Detail' },
     { id: 'telegram', label: 'Telegram', maxCols: 8,        hint: 'max 8 Spalten' },
     { id: 'sms',      label: 'SMS',      maxCols: 0,        hint: 'flach · ≤ 140 Zeichen' },
   ]
   → ersetzt bestehende CHANNELS-Konstante (war: constraint-String, ohne maxCols)

2. Badge in Kanal-Button:
   Rechts neben Kanal-Label:
     <span class="mono" ...>{chDef.maxCols === Infinity ? '∞' : chDef.maxCols === 0 ? '—' : chDef.maxCols}</span>
   Farbe: activeChannel === c.id ? 'var(--g-accent-deep)' : 'var(--g-ink-4)'

3. ↳ Detail-Pill in Spalten-Liste (OutputLayoutEditor-Slot oder eigene Spalten-Liste):
   Die bestehende Spalten-Liste in OutputLayoutEditor ist nicht direkt manipulierbar.
   Stattdessen: eine eigene `primaryCols`-abgeleitete Liste rendern (abgeleitet aus
   `channelBuckets[activeChannel].primary`) neben oder unterhalb des OutputLayoutEditor,
   die nur dann sichtbar ist wenn activeChannel === 'telegram':
     {#each channelBuckets[activeChannel].primary as id, i}
       {@const overLimit = chDef.maxCols !== Infinity && chDef.maxCols !== 0 && i >= chDef.maxCols}
       {#if overLimit}
         <span data-testid="compare-step4-detail-pill-{i}" class="mono detail-pill">↳ Detail</span>
       {/if}
     {/each}
   Alternativ: Overlay-div absolut positioniert über den Zeilen des OutputLayoutEditor
   mit pointer-events: none. Implementierungsentscheidung dem Developer überlassen —
   Testid-Vertrag ist bindend.

4. Hinweis-Text unter Spalten-Liste:
   Bereits vorhanden (constraint-String), ersetzen durch:
     chDef.maxCols === Infinity
       ? 'Email zeigt alles · keine Begrenzung'
       : chDef.maxCols === 0
       ? 'SMS hat keine Tabelle — nur Empfehlung + Fließtext'
       : `Max ${chDef.maxCols} Spalten für ${chDef.label}`

5. Rechte Spalte: LayoutPreview einbinden (statt ChannelPreviewBlock):
   <import LayoutPreview from '../LayoutPreview.svelte'>
   <LayoutPreview channel={activeChannel} pickedIds={[...wizard.pickedIds]} />
   data-testid="compare-step4-layout-preview" auf dem Wrapper-div
```

### Step5Versand.svelte — Rework

Kompletter Umbau des Markup (Script-Logik bleibt erhalten, nur ergänzt):

```
Neue Struktur:

Section 1: 3-Kacheln-Grid (Versandzeit / Zeitfenster / Horizont)
  <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; margin-bottom:28px">
  Kachel 1 „Versand":
    Mono-Label „VERSAND", Wert aus state.schedule
      ('daily_morning' → '07:00 Uhr', 'daily_evening' → '18:00 Uhr')
    Sub-Label 'täglich'
    data-testid="compare-step5-schedule-tile"
  Kachel 2 „Zeitfenster":
    Mono-Label „ZEITFENSTER"
    Wert: '{state.timeWindowStart}–{state.timeWindowEnd} Uhr'
    Sub-Label 'bewertet'
    data-testid="compare-step5-timewindow-tile"
  Kachel 3 „Horizont":
    Mono-Label „HORIZONT"
    Wert: '+{state.forecastHours} h'
    Sub-Label aus forecastHours:
      24 → 'heute', 48 → 'morgen + übermorgen', 72 → 'übermorgen + Folgetag'
    data-testid="compare-step5-horizon-tile"
  Kacheln sind klickbare Buttons (onclick öffnet bestehende Eingabe-Sektionen, die darunter bleiben)

Section 2: Versand-Kanäle (ChannelRow mit Sub-Label)
  Eyebrow „Versand-Kanäle"
  Je Kanal: bestehende ChannelToggle-Komponente PLUS Sub-Label darunter:
    Email:    sub="Layout · alle Spalten + Detail"
    Telegram: sub="Layout · max 8 Spalten"
    SMS:      sub="Layout · flach, ≤ 140 Z."
  Sub-Label als <span class="mono" style="font-size:10.5px; color:var(--g-ink-4)">
  data-testid: bestehende compare-step5-channel-{email,telegram,sms} erhalten

Section 3: Aktivierungs-Banner (nur Create-Modus, !state.isEditMode)
  isReady = versandVisited && canActivate  (canActivate = Prop aus CompareEditor)
  Bereit-State (isReady = true):
    Hintergrund var(--g-good), Farbe #fff
    Kreis-Icon mit ✓, Label „Bereit zum Aktivieren" (Mono-Eyebrow)
    Zeile: „{state.name || 'Neuer Vergleich'} · {pickedIds.length} Orte · täglich {scheduleTime}"
    data-testid="compare-step5-activation-banner" data-ready="true"
  Nicht-Bereit-State (isReady = false):
    Hintergrund var(--g-ink), Farbe #fff, gedimmt (0.55 Opacity-Text)
    Label „Bereit zum Aktivieren" (Mono-Eyebrow, gedimmt)
    Zeile: „{state.name || 'Neuer Vergleich'} · {pickedIds.length} Orte"
    data-testid="compare-step5-activation-banner" data-ready="false"

  Fehlende Props für isReady: Step5Versand bekommt neue Props:
    { versandVisited: boolean, canActivate: boolean, pickedIds: string[] }
  CompareEditor übergibt diese beim Rendern:
    <Step5Versand {versandVisited} canActivate={done.has('versand')} pickedIds={[...wiz.pickedIds]} />
```

### CompareEditor.svelte — „Briefing aktivieren"-Button (ergänzen)

```
Im !isEdit-Zweig des Headers (JSX Z. 666–674), nach bestehenden Abbrechen/Continue-Elementen:

Platzierung: rechts im Header-Div (parallel zu Edit-Aktionsleiste, aber für !isEdit)

{#if !isEdit}
  <div style:display="flex" style:gap="8px" style:align-items="center">
    {#if !done.has('versand')}
      <span class="mono" style:font-size="10.5px" style:color="var(--g-ink-4)">
        Versand einrichten zum Aktivieren
      </span>
    {/if}
    <Btn
      data-testid="compare-editor-activate"
      variant={done.has('versand') ? 'primary' : 'quiet'}
      size="sm"
      disabled={!done.has('versand')}
      style={!done.has('versand') ? 'opacity:0.4; cursor:not-allowed' : ''}
      onclick={handleActivate}
    >Briefing aktivieren</Btn>
  </div>
{/if}

handleActivate():
  if (!done.has('versand')) return;
  void wiz.saveComparePreset(preset);  // preset als Prop durchreichen (bereits vorhanden)
  // Hinweis: saveComparePreset nutzt user_id aus Auth-Kontext — kein default-Fallback
```

### Testid-Vertrag (additiv — bestehende Testids bleiben)

Neue Testids:
- `compare-step4-layout-preview` — Wrapper der LayoutPreview-Komponente
- `compare-step4-preview-sms` — Monospace-Block im SMS-Branch
- `compare-step4-detail-pill-<index>` — ↳ Detail-Pill für Spalte an Position `<index>`
- `compare-step5-schedule-tile` — Versand-Kachel
- `compare-step5-timewindow-tile` — Zeitfenster-Kachel
- `compare-step5-horizon-tile` — Horizont-Kachel
- `compare-step5-activation-banner` — Aktivierungs-Banner (data-ready="true|false")
- `compare-editor-activate` — „Briefing aktivieren"-Button

---

## Expected Behavior

- **Input:** Kanalwahl in Step4, `wizard.channelLayouts`, `wizard.pickedIds`, `versandVisited`-Flag,
  `state.schedule/timeWindowStart/timeWindowEnd/forecastHours`
- **Output:** Visuell korrekte, kanalspezifische Layout-Vorschau; 3-Kacheln-Versand-Übersicht;
  State-abhängiger Aktivierungs-Banner; aktivierbarer Header-Button mit echtem Save-Aufruf
- **Side effects:** Bei Klick „Briefing aktivieren" wird `wiz.saveComparePreset(preset)` aufgerufen
  → PATCH an Backend mit `user_id` aus Auth-Kontext. Kein Schreiben auf `"default"`.

## Known Limitations

- **Drag-Sort-Persistenz:** Out-of-Scope für V1 — Spalten-Reihenfolge wird per bestehenden
  Up/Down-Buttons oder DnD-Handler (OutputLayoutEditor) geändert; die angezeigte Reihenfolge
  in der Vorschau reflektiert `channelBuckets[channel].primary` (read-only Vorschau).
- **Live-Daten in Vorschau:** LayoutPreview nutzt statische Dummy-Daten ohne echte API-Calls.
  Die angezeigten Werte (Schnee, Wind, Score) sind fixe Beispielwerte. Echte Werte kommen erst
  in einem späteren Slice/Epic.
- **Aktivierungs-Flow nach Save:** Nach erfolgreichem `saveComparePreset()` gibt es keinen
  expliziten Redirect — das ist Aufgabe des Callers (bleibt in CompareEditor unverändert).

---

## Out-of-Scope / Folge-Issues

| CE_-Funktion | Status |
|---|---|
| Drag-Sort der Spalten | Out-of-Scope V1 (Up/Down-Buttons bleiben) |
| Echte Wetterdaten in LayoutPreview | Out-of-Scope (Dummy-Daten reichen für CE_-Fidelity) |
| Gewicht-Konfiguration pro Metrik | Out-of-Scope (Slice 5/6) |
| Mobile-Parität Layout/Versand-Tab | Out-of-Scope (Folge-Issue) |

---

## Changelog

- 2026-06-09: Initiale Spec (Slice 4/6, Epic #677). CE_LayoutPreview als neue Svelte-Komponente,
  Step5Versand Rework mit 3-Kacheln + ChannelRow Sub-Label + isReady-Banner,
  CompareEditor „Briefing aktivieren"-Button mit echter Persistenz.
