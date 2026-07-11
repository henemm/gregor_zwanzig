<!-- gregor-zwanzig-handoff: stable_id=ortsvergleich-wizard -->
> **⚠️ Reconciliation (2026-06-01, Issue #504 + #20 · canonical-ia-navigation).**
> Die **Detail-Seite** dieses Issues ist inzwischen zum **Ortsvergleich-Hub mit
> 6 Tabs** weiterentwickelt (`Übersicht · Orte · Idealwerte · Layout · Versand ·
> Vorschau`, `?tab=`-gesteuert) — analog zum Trip-Hub. Konsequenzen, die die
> untenstehenden Abschnitte **„Detail-Seite"** und **„Wizard (Edit-Mode)"**
> überschreiben:
> - **Bearbeiten passiert in den Hub-Tabs**, nicht über `/compare/[id]/edit`.
>   Die Wizard-**Edit**-Route + der Edit-Mode-Stepper sind **verworfen**;
>   `/compare/[id]/edit` leitet auf `/compare/[id]?tab=locations` um.
>   `screen-compare-wizard.jsx (mode="edit")` bleibt nur Komfort-Direktsprung
>   beim *Erst*-Setup, kein Edit-Surface eines bestehenden Vergleichs.
> - Die **Briefing-Vorschau** wird zum eigenen Hub-Tab „Vorschau" (Verifikation),
>   gerendert aus `CompareEmail` (Profil-Map via `ceProfileFor`).
> - **Unverändert gültig** bleiben: Startseite-Kacheln, Übersicht (Kachel-Grid),
>   `CompareTile`, **Wizard im Create-Mode**, Mobile-Liste.
> Maßgeblich ist das kanonische Compare-Hub-Tab-Set in **#20**
> (`body-20-canonical-ia-navigation.md`).

## Problem

Die ursprüngliche `/compare`-Spec (Master-Detail mit Gruppen-Sidebar + Auto-Reports-Übersicht) hat sich in der PO-Review **2026-05-28** als zu komplex erwiesen — das Setup eines neuen Vergleichs war über mehrere lose gekoppelte Modale verteilt. Die User-Story dahinter ist linear: **„Ich richte vor dem Urlaub einen Vergleich ein → ab dann läuft das täglich automatisch."**

> **Grundverständnis (gilt für die ganze Spec).** Die Web-App ist ein **Einrichtungs- und Monitoring-Werkzeug**, KEIN Lese-Medium. Das tägliche Briefing wird in den **Kanälen** (Email/Signal/Telegram/SMS) konsumiert, nicht im Browser. Jeder Screen hier zeigt darum *was konfiguriert ist* und *ob es läuft* — nicht das Tages-Briefing.

Diese Spec ersetzt den Master-Detail-Ansatz durch vier klare Surfaces:

1. **Startseite-Einstieg** — Sektion „Aktive Orts-Vergleiche" als Kachel-Grid auf `/` (Cockpit/Status, kein Briefing-Reader).
2. **Übersicht** — **Kachel-Grid** aller Vergleiche auf `/compare` (Charter §3 v1.1 — *keine* Tabelle).
3. **Detail-Seite** — `/compare/[id]`: Setup + Monitoring-Status + Aktionen. **Klick-Ziel jeder Kachel.**
4. **Wizard (Create/Edit)** — 5 Schritte: Vergleich → Orte → Idealwerte → Layout → Versand. Parallel-Struktur zum Trip-Wizard (#407).

Die alten Routen `/locations` und `/subscriptions` sind **ersatzlos** in dieses Modell integriert: Locations werden im Wizard-Schritt 2 angelegt/gewählt, Subscriptions sind die Kacheln der Übersicht.

> **Charter-Bezug.** Charter §3 wurde am **2026-05-31 auf v1.1** angehoben: neues Pattern **Detail-Seite** ergänzt, Orts-Vergleich von *Master-Detail* auf *Liste (Kachel-Grid) → Detail → Wizard* umgestellt. Master-Detail bleibt nur noch für **Konto** gültig. Diese Issue ist die Code-Umsetzung dieser Charter-Änderung.

## Files

```
src/routes/+page.svelte                              ← Startseite: Sektion "Aktive Orts-Vergleiche" (Kachel-Grid) ergänzen
src/routes/compare/+page.svelte                      ← Übersicht: Kachel-Grid (Umbau von Tabelle)
src/routes/compare/[id]/+page.svelte                 ← NEU: Detail-Seite (Klick-Ziel der Kachel)
src/routes/compare/new/+page.svelte                  ← Wizard im Create-Mode
src/routes/compare/[id]/edit/+page.svelte            ← Wizard im Edit-Mode
src/lib/components/compare/CompareGrid.svelte        ← NEU: Kachel-Grid (ersetzt CompareList/Tabelle)
src/lib/components/compare/CompareTile.svelte        ← NEU: eine Kachel + Kebab-Menü (ersetzt CompareRow)
src/lib/components/compare/CompareDetail.svelte      ← NEU: Detail-Inhalt (Setup + Monitoring + Aktionen)
src/lib/components/compare/CompareWizard.svelte      ← Stepper-Shell, kapselt 5 Steps
src/lib/components/compare/steps/Step1Vergleich.svelte
src/lib/components/compare/steps/Step2Orte.svelte
src/lib/components/compare/steps/Step3Idealwerte.svelte
src/lib/components/compare/steps/Step4Layout.svelte  ← teilt Logik mit Trip-Wizard #407 Step 4
src/lib/components/compare/steps/Step5Versand.svelte
```

Routen, die wegfallen:
- `/locations` — Smart-Import-Modal jetzt in Step 2 inline
- `/subscriptions` — sind die Kacheln der Übersicht

Komponenten, die wegfallen:
- `CompareList.svelte` / `CompareRow.svelte` (Tabelle) → ersetzt durch `CompareGrid` / `CompareTile`.

## Atomic-Design-Bausteine (verbindlich — keine Inline-Varianten)

Die Sandbox hat die Compare-UI bereits **vollständig atomar** zerlegt. Diese
Bauteile sind die Single-Source-of-Truth — Desktop **und** Mobile teilen sie über
`dense`/`compact`-Props (etabliertes Muster, vgl. `StagePill`, `ChannelRow`).
Beim SvelteKit-Bau 1:1 als Komponenten übernehmen, **nicht** pro Screen neu inline bauen.

| Sandbox-Molecule (`molecules.jsx`) | Props | Zweck |
|---|---|---|
| `CompareTile` | `sub`, **`dense`**, **`compact`**, `accent`, `trailing`, `onClick` | Vergleichs-Kachel für **Liste + Home, Desktop + Mobile**. `dense` = Mobile-Spacing, `compact` = Home-Kachel ohne Kanal-Pills. `trailing` = injizierte Affordanz (Kebab/Chevron/Stift) — das Bauteil selbst hat **keine** Icon-Abhängigkeit. |
| `CompareStatusPill` | `status="active\|paused\|draft"` | Status-Badge (grün gefüllt / Outline). |
| `CompareKebab` | `items`, `onSelect`, `align`, `defaultOpen` | Desktop-Dropdown für Sekundäraktionen. |
| `CompareLocationRow` | `loc`, `index`, **`dense`**, `alt` | Gerankte Orts-Zeile in der Detail-Card. |
| `CompareIdealRow` | `item`, **`dense`**, `last` | Metrik · Idealwert · Gewicht-Pill. |
| `CompareLayoutRow` | `channel`, `cols`, **`dense`** | Spalten pro Kanal; `dense` stapelt (Mobile-Card). |
| Helper `compareActions(status)` | — | Render-agnostische Aktionsliste; Desktop-Dropdown **und** Mobile-Sheet teilen sie (Charter §6). |

Wiederverwendete bestehende Atome/Molecules: `Stat` (layout=`inline` für die Aktiv/Pausiert/Drafts-Zähler), `DetailRow` (Versand-KV-Zeilen), `Pill`, `Card`, `Btn`, `Eyebrow`, `Dot`, `Sidebar`/`MobileShell`, `Sheet` (Mobile-Aktionen).

> Begründung: Vor diesem Refactor existierte die Kachel **viermal** inline (Desktop-Liste, Desktop-Home, Mobile-Liste, Mobile-Home). Das wurde auf eine Quelle konsolidiert (Inventur §0 Session 9, `docs/atomic-design-inventory.md`). Bitte diese Disziplin im SvelteKit-Port halten.

## Übersicht (`/compare`) — Kachel-Grid

**Pattern: Kachel-Grid** (Charter §3 — „Für Trips, Vergleiche, Archiv, Templates: Kachel-Grid, keine Tabelle"). Die frühere Tabellen-Spec ist hiermit ersetzt.

Header der Seite (unverändert):
- Eyebrow `WORKSPACE · ORTS-VERGLEICHE`
- H1 „Orts-Vergleiche"
- Intro-Subtext (kurz erklären, was die Seite ist)
- Primary-Btn `+ Neuer Vergleich` rechts → `/compare/new`
- darunter Search-Pill + Stats-Row (Aktiv · Pausiert · Drafts)

**Grid:** `grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: var(--g-s-…)`. Fließend — 2 Spalten auf schmalen, 3+ auf breiten Viewports. Keine feste Spaltenzahl.

**Kachel (`CompareTile`):**

| Zone | Inhalt |
|---|---|
| Kopf | Status-`<Dot>` · Name (ellipsis) · `<Kebab ⋯>` rechts |
| Sub | Status-Label (mono, caps) `aktiv`/`pausiert`/`draft` · Region |
| Meta | `N Orte · Profil-Label` (mono) |
| Kanäle | Pills pro Kanal (Email · Signal · Telegram · SMS); leer → „noch keine Kanäle" |
| Fuß | Versand-Schedule (mono) · rechts „zuletzt …" mit Status-Dot; bei Draft „Setup unvollständig" |

- **Aktive Kachel** trägt `border-left: 3px solid var(--g-accent)`. Pausiert/Draft normaler Rahmen.
- **Hover:** `border-color: var(--g-ink-3)`, `box-shadow` von `--g-shadow-1` → `--g-shadow-2`. Cursor pointer.
- **Ganze Kachel klickbar** → `/compare/{id}` (Detail). Charter §6: „Klick auf den Namen öffnet Detail."
- **Kebab ⋯** (Charter §6, Sekundäraktionen aus dem Dropdown): `e.stopPropagation()`, dann Menü:
  - aktiv/pausiert: `Pausieren`/`Aktivieren` · `Briefing jetzt senden` · `Vorschau öffnen` · `Bearbeiten` · `—` · `Löschen` (danger)
  - draft: `Setup fortsetzen` · `—` · `Löschen` (danger)
- **Keine Icon-Soup** mehr pro Kachel (Charter §6) — alle Aktionen liegen im Kebab.

**Status-Map:**
```ts
const STATUS_MAP = {
  active: { label: "aktiv",    dot: "good",    accentBorder: true  },
  paused: { label: "pausiert", dot: "neutral", accentBorder: false },
  draft:  { label: "draft",    dot: "neutral", accentBorder: false },
};
```

## Detail-Seite (`/compare/[id]`) — NEU

**Pattern: Detail-Seite** (Charter §3 v1.1). Klick-Ziel jeder Kachel. Zeigt, **was konfiguriert ist + ob es läuft + Aktionen** — NICHT das Tages-Briefing.

**Topbar:**
- Breadcrumb `ORTS-VERGLEICHE / DETAIL`
- H1 = Name + Status-Pill (`aktiv` grün-bg / `pausiert` outline)
- Sub: `Region · Profil-Label · N Orte`
- **Primäraktion (Charter §6: genau eine):** `Bearbeiten` (primary) → `/compare/{id}/edit`
- **Kebab ⋯** daneben: `Pausieren`/`Aktivieren` · `Briefing jetzt senden` · `Vorschau öffnen` · `Löschen` (danger)

**Monitoring-Streifen** (Cockpit-Logik, kein Briefing-Reader) — 4 Felder:
`Status` (Dot + „Läuft automatisch"/„Pausiert") · `Nächster Versand` · `Zuletzt raus` · `Kanäle` (Dot-ok + Kanal-Liste).

**Body — 2 Spalten (`1.7fr / 1fr`):**

*Links (was konfiguriert ist):*
1. **Verglichene Orte** — Card mit gerankter Orts-Liste (`01`, `02`, … · Name · Gruppe · Höhe m). Reihenfolge = Ranking-Reihenfolge im Briefing.
2. **Idealwerte** — Card; pro Metrik Zeile `Metrik · Idealwert (mono) · Gewicht-Pill` (`hoch`=accent, `mittel`=neutral, `niedrig`=ghost). Kicker: „Bestimmt das tägliche Ranking."
3. **Layout pro Kanal** — Card; pro aktivem Kanal Zeile `Kanal + Constraint-Hint` links, Spalten-Chips rechts (erstes Chip accent-getönt). SMS → „flach · ohne Spalten". Constraints identisch zu #14 (Email ∞ · Telegram 8 · Signal 6 · SMS 0).

*Rechts:*
4. **Versand** — Card: `Rhythmus` · `Vorausschau` · `Nächster` (KV-Zeilen) + Kanal-Pills.
5. **Vorschau · Prüfung** — Card mit `border-left: 3px accent`. Mail-Thumbnail (dekorativ) + Text „So sieht dein Briefing in der Mail aus. Zum **Prüfen** der Konfiguration — gelesen wird es unterwegs im Postfach, nicht hier." + Button `Vorschau öffnen`. **Wichtig:** Das ist ein **Verifikations-Tool**, kein Konsum-Surface und kein eigenständiges Klick-Ziel.
6. Quiet-Action `Test-Briefing jetzt senden`.

**Draft-Sonderfall:** Detail einer Draft zeigt leere/teilbefüllte Setup-Cards; Primäraktion heißt sinngemäß weiter „Bearbeiten" (führt in den Wizard, wo das Setup vervollständigt wird).

## Startseite-Einstieg (`/`)

Auf der Startseite (Cockpit) eine Sektion **„Aktive Orts-Vergleiche"** als Kachel-Grid:
- `SectionH` mit Eyebrow `WORKSPACE`, Titel „Aktive Orts-Vergleiche", Kicker „Laufen automatisch — Briefing kommt in die Kanäle, nicht hierher", rechts `Alle anzeigen` (quiet) → `/compare`.
- Grid `repeat(3, 1fr)` (Home-Kontext ist enger als die Listenseite), nur Vergleiche mit `status === "active"`.
- Kachel = schlanke Variante der `CompareTile` mit **Monitoring-Fokus** (Versand-Schedule + „zuletzt … ✓"), Stift-Icon = Bearbeiten als sichtbare Sekundär-Affordanz, ganze Kachel → Detail.
- **Kein Tages-Briefing** auf der Kachel (CLAUDE.md-Grundprinzip).

## Wizard (Create + Edit)

Parallel zum Trip-Wizard (#407), gleiche Stepper-, Footer-, Intro-Komponenten.

**5 Schritte:**

| # | Label | Sub | Inhalt |
|---|---|---|---|
| 1 | Vergleich | Name & Profil | Name (required), Region (optional), Aktivitätsprofil-Tile-Picker |
| 2 | Orte | 3–5 Kandidaten | Smart-Import (links) + Library (rechts) + ausgewählte Orte (Counter mit Empfehlung) |
| 3 | Idealwerte | Was ist gut? | Pro Metrik: Range-Slider mit zwei Knobs + Notes + Skala-Endpunkte. Defaults pro Profil. |
| 4 | Layout | Was steht im Briefing | Kanal-Tabs (Email · Telegram · Signal · SMS) + Spalten-Liste mit Switch + Live-Preview. Hartes Limit: Email ∞ · Telegram 8 · Signal 6 · SMS 0 |
| 5 | Versand | Kanäle & Aktivierung | Versandzeit + Zeitfenster + Horizont · Channel-Liste mit On/Off · Aktivierungs-Banner |

### Wizard-Kontextmodi

- **Create** (`/compare/new`):
  - Stepper: nur passierte + aktueller + nächster klickbar.
  - Eyebrow: `SCHRITT N VON 5 · NEUER ORTS-VERGLEICH`
  - H1: Step-spezifisch (`„Vergleich — wie heißt dein Briefing?"` etc.)
  - Footer-CTA rechts: `Abbrechen` · `Weiter →` (oder `Briefing aktivieren →` in Schritt 5)

- **Edit** (`/compare/{id}/edit`):
  - **Stepper: ALLE Schritte frei klickbar.** Kein ✓-Häkchen — Schritte sind Konfigurations-Tabs, kein Fortschritt.
  - Header **statt** Eyebrow+Step-Titel:
    - Eyebrow `ORTS-VERGLEICH · BEARBEITEN`
    - H1 = Name des Vergleichs + Status-Pill (aktiv/pausiert)
    - Secondary-Btns rechts: `Briefing-Vorschau` + `Pausieren`/`Aktivieren`
  - H2 unter Stepper: Step-spezifisch (gleicher Text wie Create-H1)
  - Footer-CTA rechts: `Verwerfen` · `Speichern`
  - Footer-Hint zentriert: „Änderungen werden beim Speichern übernommen"
  - Footer-Links: `← Zurück` UND `Weiter →` parallel (Stepper-Sprung möglich)
  - Schritt 5 hat **keinen** Aktivierungs-Banner mehr — Status ist im Header.
  - **Einstieg:** aus der Detail-Seite (Primär `Bearbeiten`) und aus dem Kachel-Kebab (`Bearbeiten`).

### Constraint-Begründungen pro Schritt

**Schritt 2 — min. 2 Orte:**
```ts
canAdvance = pickedIds.length >= 2;  // ein Vergleich mit 1 Ort ergibt keinen Vergleich
```
Empfehlungs-Heuristik (nicht hart):
```
< 2 Orte  → "min. 2"
2–5 Orte  → "passt"
> 5 Orte  → "viel — Empfehlung 3–5"
```

**Schritt 4 — Kanal-Constraints** (identisch zu Trip-Wizard #407 Step 4, Issue #14):
```ts
const CHANNELS = [
  { id: "email",    maxCols: Infinity },
  { id: "telegram", maxCols: 8 },
  { id: "signal",   maxCols: 6 },
  { id: "sms",      maxCols: 0 },  // SMS hat keine Tabelle, nur Fließtext
];
```
Spalten über dem Kanal-Limit werden in der Liste **dimmed** (opacity 0.55, warn-tint) mit Badge `↳ Detail`.

## Mobile (im Scope dieser Issue)

Mobile ist **Teil dieser Issue** (nicht mehr V1.5). Die Sandbox liefert die
Mobile-Pendants fertig; sie teilen die Atomic-Bauteile oben über `dense`.

**Files (Mobile):**
```
src/routes/compare/+page.svelte           ← responsive: Kachel-Grid → vertikaler Stack (mobil)
src/routes/compare/[id]/+page.svelte      ← responsive Detail
src/lib/components/compare/CompareTile.svelte     ← dense-Variante (Mobile-Stack)
src/lib/components/mobile/MCompareActionSheet.svelte ← Bottom-Sheet (compareActions)
```

**Übersicht (Mobile):** vertikaler **Kachel-Stack** statt Grid. `CompareTile dense`,
Tap → Detail, Chevron rechts als Affordanz. Header mit Such-Pill + Stat-Zähler.

**Detail (Mobile):**
- TopBar: Back · Name · Stift (Bearbeiten) · ⋯ (öffnet Bottom-Sheet `compareActions`).
- `CompareStatusPill` + Kontextzeile (Profil · N Orte · Region).
- **Monitoring als 2×2-Grid** (Status · Nächster Versand · Zuletzt · Kanäle).
- Setup-Cards: Verglichene Orte (`CompareLocationRow dense`), Idealwerte
  (`CompareIdealRow dense`), Layout pro Kanal (`CompareLayoutRow dense` → gestapelt),
  Versand (`DetailRow`), Vorschau·Prüfung (Verifikations-Card).
- **Kein Tages-Briefing** im Browser (CLAUDE.md-Grundprinzip gilt mobil identisch).

**Home (Mobile):** Sektion „Aktive Orts-Vergleiche" als kompakte `CompareTile dense compact`,
Tap → Detail, Chevron-Affordanz. Kein Tages-Briefing.

**Touch:** Tap-Targets ≥ 44 px (Kachel selbst, Sheet-Zeilen 52 px). Aktionen, die
Desktop im Kebab-Dropdown zeigt, liegen mobil im Bottom-Sheet — identische `compareActions`-Liste.

> Mobile-Mockups + Patterns liegen zusätzlich im Spec-Spiegel
> `gregor-zwanzig-mobile/` (kanonische Wurzel-Dateien + `mobile-patterns.md`).

## Acceptance criteria

### Startseite-Einstieg
- [ ] `/` zeigt Sektion „Aktive Orts-Vergleiche" als Kachel-Grid, nur `status === "active"`
- [ ] Kachel zeigt Monitoring-Fuß (Schedule + „zuletzt …"), **kein** Tages-Briefing
- [ ] Ganze Kachel → `/compare/{id}`; Stift-Icon → `/compare/{id}/edit`
- [ ] `Alle anzeigen` → `/compare`

### Übersicht (Kachel-Grid)
- [ ] `/compare` rendert ein **Kachel-Grid** (`repeat(auto-fill, minmax(300px, 1fr))`), **keine Tabelle**
- [ ] Header: Eyebrow, H1, Intro, primary `+ Neuer Vergleich` rechts → `/compare/new`
- [ ] Search-Pill filtert nach Name (case-insensitive); Empty-State „Keine Vergleiche für »$query« gefunden."
- [ ] Stats-Row: Aktiv (accent) · Pausiert · Drafts
- [ ] Aktive Kachel hat `border-left: 3px accent`; Hover hebt Border + Shadow
- [ ] Ganze Kachel klickbar → `/compare/{id}`
- [ ] Kebab ⋯ öffnet Sekundär-Menü (stopPropagation); Inhalt je nach Status (draft = Setup fortsetzen/Löschen)
- [ ] Keine Per-Zeilen-Icon-Soup mehr

### Detail-Seite
- [ ] `/compare/{id}` zeigt Breadcrumb, H1 + Status-Pill, Sub `Region · Profil · N Orte`
- [ ] Primäraktion `Bearbeiten` → `/compare/{id}/edit`; Kebab mit Sekundäraktionen
- [ ] Monitoring-Streifen: Status · Nächster Versand · Zuletzt · Kanäle
- [ ] Card „Verglichene Orte" listet Orte gerankt mit Höhe
- [ ] Card „Idealwerte" zeigt Metrik · Idealwert · Gewicht-Pill
- [ ] Card „Layout pro Kanal" zeigt Spalten-Chips pro aktivem Kanal + Constraint-Hint
- [ ] Card „Versand": Rhythmus/Vorausschau/Nächster + Kanal-Pills
- [ ] Card „Vorschau · Prüfung": Thumbnail + Verifikations-Text + `Vorschau öffnen` — als Prüf-Tool ausgewiesen, kein Konsum-Surface
- [ ] Detail rendert das Tages-Briefing **nicht** im Browser

### Wizard Create-Mode
- [ ] `/compare/new` startet auf Step 1 mit leerem State
- [ ] Stepper-Sprung: nur Steps ≤ aktueller + 1 klickbar
- [ ] `Weiter →` disabled wenn `canAdvance === false`
- [ ] Step 1 Name required, Profil-Tile single; Step 2 Smart-Import + Index-Badges; Step 3 Range-Slider mit zwei Knobs + Profil-Defaults (#14); Step 4 Kanal-Tabs mit Spalten-Limits + Preview; Step 5 Aktivierungs-Banner wenn `activated`

### Wizard Edit-Mode
- [ ] `/compare/{id}/edit` lädt persistierten State, prefilled alle Felder
- [ ] Header zeigt Name + Status-Pill
- [ ] **Alle 5 Stepper-Punkte klickbar**, kein ✓-Häkchen, current orange-umrandet
- [ ] Step-Titel als H2 unter Stepper
- [ ] Footer: `Verwerfen` · `Speichern`, beide jederzeit; Hint „Änderungen werden beim Speichern übernommen"
- [ ] Schritt 5 zeigt **keinen** Aktivierungs-Banner mehr (Status oben)
- [ ] „Briefing-Vorschau"-Btn im Header öffnet dasselbe Modal wie `Vorschau öffnen`
- [ ] Pausieren/Aktivieren togglet `status` ohne Speichern

### Mobile
- [ ] `/compare` rendert mobil als **vertikaler Kachel-Stack** (`CompareTile dense`), Tap → Detail, Chevron-Affordanz
- [ ] `/compare/{id}` mobil: Back/Stift/⋯-TopBar, `CompareStatusPill`, **2×2-Monitoring-Grid**, Setup-Cards (Orte/Idealwerte/Layout/Versand/Vorschau)
- [ ] ⋯ öffnet Bottom-Sheet mit `compareActions` (gleiche Liste wie Desktop-Kebab)
- [ ] Home mobil zeigt „Aktive Orts-Vergleiche" als `CompareTile dense compact`
- [ ] **Dieselben** Atomic-Bauteile wie Desktop via `dense`/`compact` — keine Mobile-eigene Kachel-Logik
- [ ] Tap-Targets ≥ 44 px; **kein** Tages-Briefing im Browser

## Edge Cases

| Fall | Verhalten |
|---|---|
| Vergleich ohne Kanäle | Kachel zeigt „noch keine Kanäle", Schedule `—`, `status: "draft"` |
| Klick auf Draft-Kachel | öffnet Detail (teilbefüllt); Primär `Bearbeiten` → Wizard zum Vervollständigen |
| Wizard verlassen ohne Speichern (Create) | Confirm: „Vergleich verwerfen?" |
| Wizard verlassen mit Änderungen (Edit) | Confirm: „Ungespeicherte Änderungen verwerfen?" |
| Ort aus Library entfernt nach Auswahl | Picked-Liste zeigt Hinweis, Auto-Cleanup auf Speichern |
| Profil-Wechsel in Edit Step 1 | Confirm: „Idealwerte werden auf Defaults zurückgesetzt — fortfahren?" |
| Aktiv, alle Kanäle deaktiviert in Edit-Step 5 | Speichern blockt: „Mindestens ein Kanal nötig" |

## 📎 Screenshots

**Desktop · Übersicht — Kachel-Grid aller Vergleiche**

![Desktop Übersicht Kacheln](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-ortsvergleich-uebersicht-kacheln.png)

*(Fließendes Grid `repeat(auto-fill, minmax(300px, 1fr))` — schmaler Viewport 2 Spalten, produktiv 3+.)*

**Desktop · Detail-Seite — Klick-Ziel einer Kachel (Setup + Monitoring + Aktionen)**

![Desktop Detail](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-ortsvergleich-detail.png)

*(Linke Spalte: Verglichene Orte · Idealwerte · Layout pro Kanal. Rechte Spalte (hier angeschnitten): Versand + Vorschau·Prüfung als Verifikations-Tool.)*

**Mobile · Übersicht — vertikaler Kachel-Stack (`CompareTile dense`)**

![Mobile Liste](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-ortsvergleich-mobile-liste.png)

**Mobile · Detail — Monitoring-Grid + gerankte Orte (`CompareLocationRow dense`)**

![Mobile Detail](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-ortsvergleich-mobile-detail.png)

**Wizard Schritt 1 (Create-Mode) — Vergleich benennen**

![Wizard Step 1](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-ortsvergleich-wizard-step1.png)

**Wizard Schritt 1 (Edit-Mode) — Header mit Name + Status-Pill, Stepper frei navigierbar**

![Edit Step 1](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-ortsvergleich-edit-step1.png)

## Abhängigkeiten

- **#407 (Trip-Wizard)** — Step 4 (Layout-Editor) teilt Logik/Komponenten. Idealerweise nach #407 angehen.
- **#14 (Output-Layout-System)** — definiert die Kanal-Constraints + `METRIC_PRIORITY`-Heuristik (auch für die Detail-Card „Layout pro Kanal").
- **#17 (Surface-Stack-Migration)** — weiße Cards auf warmer Off-White-Page (PO-Leitprinzip „hoher Kontrast = Lesbarkeit").
- **Charter §3 v1.1** (2026-05-31) — diese Issue ist die Code-Umsetzung der Pattern-Änderung (Detail-Seite neu, Orts-Vergleich von Master-Detail entkoppelt).

## Out of Scope

- Briefing-Vorschau-**Modal**-Inhalt (eigenes Folge-Issue) — hier nur der Einstiegspunkt (`Vorschau öffnen`) als Verifikations-Tool.
- Kollaboration / geteilte Vergleiche (kein V1)
- AutoReportsOverview / Master-Detail-Layout für Compare — **explizit verworfen** (PO-Review 2026-05-28, Charter §3 v1.1)
