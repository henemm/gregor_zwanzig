<!-- gregor-zwanzig-handoff: stable_id=stage-date-edit -->
## Problem

Jede Etappe hat ein Datum (`stage.date`, ISO-String z.B. `"2025-07-15"`). Es wird beim
GPX-Bulk-Upload **einmalig** gesetzt und ist danach eingefroren — es gibt keine Möglichkeit,
das Datum einer einzelnen Etappe nachträglich zu korrigieren.

Aktueller Zustand (read-only):
- `StageDetailRow.svelte` zeigt `"DD.MM."` in der linken Etappen-Liste
- `PauseStageView.svelte` zeigt `stage.date` als grauen Text unter dem Etappen-Namen

Realer Bedarf: Tourstart verschiebt sich (Flug/Permit/Wetterfenster) → der ganze Trip
muss um N Tage rücken; gelegentlich auch Einzel-Korrektur einer Etappe.

## Lösung

Ein **kompaktes, gut lesbares Datum-Control** in der Etappen-Detail-Ansicht — für normale
Etappen **und** Pausentage. Native `<input type="date">` (bereits in `EditRouteSection.svelte`
im Einsatz), gerahmt im Token-Stil + abgeleiteter **Wochentag-Chip** (Mo/Di/…) zur schnellen
Orientierung. Beim Verschieben der **ersten** Etappe erscheint ein **inline, nicht-blockierender
Kaskaden-Vorschlag** (Folge-Etappen mitverschieben).

> Mockup-Referenz (Molecules `StageDateField` + `StageCascadeNotice` im Design-Repo
> `molecules.jsx`, genutzt von Desktop- **und** Mobile-Editor). Hoher Kontrast = Lesbarkeit
> (Charter-Leitprinzip): weiße Card, mono-Datum, Wochentag-Chip in Akzent-Tint.

## Datenmodell

**Keine neuen Felder.** Die Aktion mutiert ausschließlich `stage.date` (ISO `YYYY-MM-DD`).
Die Kaskade verschiebt `stage.date` aller Folge-Etappen um dasselbe Tages-Delta.

```ts
// Δ-Berechnung (Tage)
const days = Math.round((Date.parse(newDate) - Date.parse(oldDate)) / 86_400_000);
// Kaskade auf Folge-Etappen (Index > 0)
stages.slice(1).forEach(s => { if (s.date) s.date = addDays(s.date, days); });
```

## Files

- `EditStagesPanelNew.svelte` — Etappen-Editor (Strip links, Detail rechts)
- `PauseStageView.svelte` — Pausentag-Detail
- `StageDetailRow.svelte` — read-only Datum in der Liste (zeigt künftig das editierte Datum)
- **Mobile-Pendant** des Etappen-Editors — dieselbe `StageDateField`, aber `size="lg"`
  (44px Touch-Target, 16px Font = kein iOS-Zoom), Label links, Feld volle Breite.
- neue Komponente `StageDateField` (Empfehlung, s.u.) — im Design-Mockup bereits als
  **gemeinsame Molecule** umgesetzt (`molecules.jsx::StageDateField` + `StageCascadeNotice`),
  Desktop **und** Mobile teilen sie. Bitte in der Svelte-Atomic-Bibliothek analog anlegen.

## Empfehlung · eigene Komponente vs. native

**Empfehlung: dünne Wrapper-Komponente `StageDateField.svelte`** statt rohem `<input>` an
zwei Stellen.

Begründung:
- Datum kommt an **2 Orten** vor (normale Etappe + Pausentag), perspektivisch auch im
  Trip-Wizard Schritt 2 → DRY.
- Der **Wochentag-Chip** und der „Tourstart"-Hinweis sind shared logic.
- Das native `<input type="date">` bleibt **innen** (Picker, Tastatur, A11y umsonst) — die
  Komponente liefert nur Rahmen, Mono-Font, Chip. Kein Custom-Picker (wäre Over-Engineering).

## Required changes

### 1 — `StageDateField.svelte` (neu)

```svelte
<script lang="ts">
  export let value: string;            // ISO "YYYY-MM-DD"
  export let isFirst = false;          // erste Etappe → "Tourstart"-Hinweis
  const WD = ['So','Mo','Di','Mi','Do','Fr','Sa'];
  $: wd = value ? WD[new Date(value + 'T00:00:00').getDay()] : '—';
</script>

<div class="stage-date">
  <span class="label">Datum{#if isFirst} · <em>Tourstart</em>{/if}</span>
  <label class="box">
    <span class="wd">{wd}</span>
    <input type="date" bind:value on:change />
  </label>
</div>

<style>
  .stage-date { flex-shrink: 0; min-width: 168px; }
  .label { font-family: var(--g-font-data); font-size: 10px; letter-spacing: .08em;
    text-transform: uppercase; color: var(--g-ink-muted); display:block; text-align:right; margin-bottom:6px; }
  .label em { color: var(--g-accent-deep); font-style: normal; }
  .box { display:flex; align-items:center; gap:8px; background: var(--g-card);
    border:1px solid var(--g-rule); border-radius:4px; padding:0 10px 0 8px; min-height:38px; cursor:pointer; }
  .wd { font-family: var(--g-font-data); font-size:11px; font-weight:700; color:var(--g-accent-deep);
    background: var(--g-accent-tint); border-radius:3px; padding:3px 7px; }
  .box input { border:none; outline:none; background:transparent; font-family:var(--g-font-data);
    font-size:13px; color:var(--g-ink); font-variant-numeric:tabular-nums; cursor:pointer; }
</style>
```

### 2 — Normale Etappe (`EditStagesPanelNew.svelte`, rechte Spalte oben)

Datum-Feld oben **rechts neben dem Etappen-Namen**, über der Wegpunkt-Liste — kompakt,
kein Formular-Block:

```svelte
<header class="flex items-start justify-between gap-8">
  <div class="flex-1 min-w-0">
    <Eyebrow>Etappe · {stage.code}</Eyebrow>
    <h2 class="text-3xl font-semibold tracking-tight">{stageTitle}</h2>
    <p class="…">Wegpunkte sind Wetterscheiden — …</p>
  </div>
  <StageDateField bind:value={stage.date} isFirst={idx === 0} on:change={() => onDateChange(idx)} />
</header>

{#if idx === 0 && cascade}
  <CascadeStrip {cascade} on:apply={applyCascade} on:dismiss={() => cascade = null} />
{/if}
```

### 3 — Pausentag (`PauseStageView.svelte`)

Das graue read-only-Datum **ersetzen** durch `StageDateField` (parallel zum Titel):

```svelte
<header class="flex items-start justify-between gap-8 mb-6">
  <div class="flex-1 min-w-0">
    <Eyebrow>Pausentag</Eyebrow>
    <h2 class="text-3xl font-semibold tracking-tight">{stage.title}</h2>
    <p class="…">Pausentage haben keine Wegpunkte …</p>
  </div>
  <StageDateField bind:value={stage.date} on:change={() => onDateChange(idx)} />
</header>
```

### 4 — Kaskaden-Strip (inline, nur erste Etappe)

```svelte
<!-- Zustand A · Vorschlag -->
<div class="cascade prompt">
  <p><strong>Tourstart um {sign}{abs} {dayWord} verschoben.</strong>
     Sollen die {count} Folge-Etappen um denselben Betrag mitverschoben werden?</p>
  <Btn variant="accent" size="sm" on:click={apply}>Alle mitverschieben</Btn>
  <Btn variant="outline" size="sm" on:click={dismiss}>Nur diese Etappe</Btn>
</div>
<!-- Zustand B · nach Bestätigung -->
<div class="cascade done">
  <Dot tone="success" /> <strong>{count} Folge-Etappen verschoben</strong> · alle Daten um {sign}{abs} {dayWord} angepasst.
</div>
```

## Empfehlung Kaskade — JA, aber präzise

| Trigger | Verhalten |
|---|---|
| Datum **erste** Etappe geändert | Inline-Vorschlag „Alle Folge-Etappen mitverschieben?" — Default-Empfehlung |
| Datum **mittlere/spätere** Etappe geändert | **Keine** Kaskade — reine Punkt-Korrektur |

Begründung: Etappendaten sind sequenziell. Der häufigste reale Edit ist „ganze Tour rückt um
N Tage" — genau dafür ist die Kaskade da. Eine Kaskade ab einer mittleren Etappe würde die
Sequenz zerschießen. **Kein Modal** — der Inline-Strip respektiert das Lesbarkeits-/Flow-Prinzip
und bleibt pro Aktion reversibel.

## Constraints

- **C1** Datum-Feld der normalen Etappe oben rechts in der Detail-Spalte, kompakt (kein Block).
- **C2** `PauseStageView` read-only-Datum vollständig durch das editierbare Feld ersetzt.
- **C3** Kaskaden-Vorschlag erscheint **ausschließlich** bei Änderung der Etappe mit Index 0.
- **C4** Kaskade ist nicht-blockierend (inline, kein Modal), Default-Empfehlung = „Alle mitverschieben".
- **C5** Datum < Datum der Vor-Etappe → **sanfter Hinweis**, kein Hard-Block (User darf korrigieren).
- **C6** `StageDetailRow` zeigt nach dem Edit das **neue** Datum (`DD.MM.`) ohne Reload.

## Acceptance criteria

- [ ] Normale Etappe: editierbares Datum-Feld oben rechts, Wochentag-Chip korrekt abgeleitet.
- [ ] Pausentag: graues read-only-Datum ist durch das editierbare Feld ersetzt.
- [ ] Datum-Änderung persistiert auf `stage.date` (ISO) und spiegelt sich in `StageDetailRow`.
- [ ] Ändern der ersten Etappe zeigt den Kaskaden-Strip mit korrektem Δ und Folge-Etappen-Count.
- [ ] „Alle mitverschieben" verschiebt alle Folge-Etappen um Δ; „Nur diese Etappe" tut nichts weiter.
- [ ] Mittlere Etappe ändern zeigt **keinen** Kaskaden-Strip.
- [ ] Mobile: dieselbe `StageDateField` mit `size="lg"` (≥44px Touch); editiertes Datum
      spiegelt sich im Etappen-Auswahl-Sheet.
- [ ] Bestehende Playwright `data-testid`s erhalten.

## Edge cases

| Fall | Verhalten |
|---|---|
| Δ = 0 (Datum unverändert gewählt) | Kein Kaskaden-Strip |
| Pausentag ohne Datum (`stage.date` leer) | Chip zeigt „—", Input leer; Speichern setzt Datum |
| Folge-Etappe ohne Datum bei Kaskade | Übersprungen (kein `addDays` auf `null`) |
| Datum vor Vor-Etappe | C5-Hinweis, Speichern erlaubt |

## Out of scope (Folge-Issues)

- Automatische Datum-Neuberechnung aus Reihenfolge bei Pause-Insert/Reorder.
- Zeitzone/Uhrzeit (nur Kalendertag relevant).

## 📎 Screenshots

**Soll · Normale Etappe — Datum-Feld oben rechts neben dem Namen**

![soll-stage-date-stage](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-stage-date-stage.png)

**Soll · Pausentag — read-only-Datum durch editierbares Feld ersetzt**

![soll-stage-date-pause](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-stage-date-pause.png)

**Soll · Erste Etappe verschoben — Kaskaden-Vorschlag (A: Vorschlag, B: nach Bestätigung)**

![soll-stage-date-cascade](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-stage-date-cascade.png)

**Soll · Mobile — editierbares Datum unter dem Etappen-Selector (`size="lg"`, ≥44px Touch)**

![soll-stage-date-mobile](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-stage-date-mobile.png)
