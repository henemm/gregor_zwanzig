# Atomic-Design-Inventur · Gregor Zwanzig

**Status:** Migration abgeschlossen für Desktop-Kern und Mobile-Detail (Sessions 1–7). `organisms.jsx` repariert und produktiv. HTML-Pages auf drei finale Dateien konsolidiert. Doku aktuell zum Stand 25. Mai 2026.
**Scope:** alle JSX-Komponenten + die 9 HTML-Pages im Projekt-Root.
**Ziel:** Single-Source-of-Truth pro Komponente, dokumentierte Drift, Entscheidungs­vorlage mit Empfehlung.

---

## 0 · Migrations-Verlauf

| Session | Inhalt                                                                                  | Outcome                                                                                  |
|---------|-----------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| 1       | Audit + Inventur + Entscheidungs­vorlage + CLAUDE.md-Regel                              | Diese Datei. `logo-marks.jsx` + `Logo.html` archiviert.                                  |
| 2       | `BrandIcon` + `BrandIconSquare` neu. `BrandWordmark` → Lockup. `Input` + `Switch` Atome | Berg+Blitz wieder im Wordmark; 2 neue Atome im Showcase                                  |
| 3       | `molecules.jsx` mit 8 Molecules angelegt + ins HTML-Loader geschaltet                   | `Field`, `DetailRow`, `StagePill`, `ChannelRow`, `ChannelChip`, `BriefingTimelineRow`, `BriefingScheduleRow`, `ThresholdRow` |
| 4       | `screen-home` + `screen-trip-wizard` auf Molecules migriert                             | 6 Inline-Defs entfernt, 66 Zeilen weniger Drift-Code                                     |
| 5a      | `Stat` + `AlertRow` zu Molecules promovert                                              | 5 Inline-Defs entfernt (Stat × 2, AlertRow × 3 Pfade)                                    |
| 6       | Mobile-Pendants über Props (`dense`, `last`, `compact`, `size`) auf gleiche Molecules   | 7 weitere Inline-Defs entfernt; Mobile + Desktop nutzen jetzt **dieselben** Molecules    |
| 7       | `organisms.jsx` repariert (`MetricEditorRow`, `ChannelLimitChip`, `ChannelPreviewCard`, `applyChannel` + Helper). Showcase um Sektionen Organisms (06) und Templates (07) erweitert. | Organisms produktiv ladbar; D9 abgehakt. |
| 8       | HTML-Pages konsolidiert: `Gregor 20 - Komponenten.html` (neu, Atomic-Showcase), `Gregor 20 - Desktop.html`, `Gregor 20 - Mobile.html`. Alte Dateien (`Redesign v2`, `Mobile v1`, `Signal Layout`, `Wetter-Editor Konsolidierung` + zugehörige JSX) gelöscht. | Drei klare Eintrittspunkte statt fünf gemischter. |

**Bilanz:** 19 Inline-Komponenten-Definitionen aus den Screen-Dateien entfernt. Drift zwischen Home / Trip-Wizard / Trip-Detail (Desktop + Mobile) aufgelöst. `organisms.jsx` produktiv. HTML-Pages auf drei finale Dateien (Komponenten / Desktop / Mobile) konsolidiert. Keine bekannte Drift mehr in Atoms/Molecules/Organisms-Ebene.

---

## 1 · Aktueller Komponenten-Katalog

### Brand (`brand-kit.jsx`)

| Name                  | Beschreibung                                                                       |
|-----------------------|------------------------------------------------------------------------------------|
| `BrandIcon`           | Berg+Blitz-Glyph. Drei Sizes (sm/md/lg) oder px-Override.                          |
| `BrandIconSquare`     | Quadratische Variante mit Nebenkante + Horizont (Favicon, Avatar, App-Icon).      |
| `BrandWordmark`       | Lockup: BrandIcon + Mono-Typo. Prop `icon="left"|"only"|"none"`.                   |
| `BrandUserBadge`      | Avatar + Name + Sekundärzeile (Sidebar-Footer).                                    |
| `BrandSidebarHeader`  | Standard-Spacing-Block für Wordmark im Sidebar-Header.                             |
| `BrandSidebar`        | App-Navigation (Home / Touren / Vergleich / Archiv).                               |
| `BrandShell`          | Desktop-Template: Sidebar + Main.                                                  |
| `BRAND_NAV_ITEMS`     | Konstante mit Nav-Items.                                                           |

### Atoms (`atoms.jsx`)

| Name             | Beschreibung                                                                                  |
|------------------|-----------------------------------------------------------------------------------------------|
| `TopoBg`         | Höhenlinien-Hintergrund-SVG.                                                                  |
| `Eyebrow`        | Mono-Caps-Label.                                                                              |
| `Pill`           | Tag/Badge in 6 Tones.                                                                         |
| `Card`           | Padding + Border + Schatten.                                                                  |
| `ElevSparkline`  | Höhenprofil-Sparkline.                                                                        |
| `KV`             | Key-Value-Zeile mit Dashed-Border.                                                            |
| `Btn`            | Button in 4 Variants × 4 Sizes.                                                               |
| **`Input`** *neu*     | Text-Input in 3 Sizes. lg = 16px (no iOS-Zoom). Optional `leftIcon`, `error`, `mono`.    |
| **`Switch`** *neu*    | Toggle in 3 Sizes mit 5 Tones.                                                            |
| `Logo`           | Backward-compat-Alias → delegiert an `BrandWordmark`.                                         |
| `WIcon`          | Wetter-Line-Icons (sun, cloud, rain, thunder, snow, wind, moon, headlamp).                    |
| `Dot`            | Status-Punkt in 5 Tones.                                                                      |
| `SectionH`       | Section-Header (Eyebrow + Titel + Kicker + Right-Slot).                                       |
| `AvatarStack`    | Überlappende Avatare.                                                                         |

### Molecules (`molecules.jsx`)

| Name                    | Schlüssel-Props                                              | Beschreibung                                              |
|-------------------------|--------------------------------------------------------------|-----------------------------------------------------------|
| `Field`                 | label, hint, error, side, dense                              | Form-Field-Wrapper. Drop-in für Wizard/Auth/Mobile.       |
| `DetailRow`             | label, value, sub, icon, right, mono, divider                | KV-Verallgemeinerung mit Icon-/Right-Slots.               |
| `StagePill`              | stage, state="active|done|future|muted"                      | Etappen-Streifen-Kachel mit Risk-Bar.                     |
| `ChannelRow`            | kind, target, active, sub, onToggle, **dense**, **last**     | Kanal-Zeile. dense=true: Reihen-Layout (Mobile).          |
| `ChannelChip`           | kind, active, **compact**                                    | Tag-Anzeige; compact=true: 24×24 Tile (Mobile-Liste).     |
| `BriefingTimelineRow`   | report, **dense**                                            | Status-getrieben (Home).                                  |
| `BriefingScheduleRow`   | label, sub, time, enabled, onToggle, **last**                | Toggle-getrieben (Wizard).                                |
| `ThresholdRow`          | label, value, **divider**, **last**, editable, onEdit        | Schwellen-Anzeige.                                        |
| **`Stat`** *neu (5a)*   | label, value, sub, unit, tone, layout="stack|inline", **size**, **mono** | Statistik-Tile in 3 Sizes × 2 Layouts.       |
| **`AlertRow`** *neu (5a)* | alert, variant="icon|dot|plain", divider, last             | Alert-Zeile in 3 Varianten.                               |

Fett markierte Props wurden in Session 6 (Mobile-Pendant-Unification) hinzugefügt.

### Mobile-Atoms (`mobile-shell.jsx`)

Unverändert in dieser Migration. Enthält `PhoneFrame`, `TopAppBar`, `IconBtn`, `MIcon`, `BottomNav`, `Drawer`, `Sheet`, `Toast`, `MInput`, `MField`, `MBtn`, `MSwitch`, `MTab`, `ScreenScroll`, `MobileShell`.

**Hinweis:** Mobile-Screens nutzen nun zwei Komplemente:
- **Mobile-Touch-Atome** (M*) aus `mobile-shell.jsx` für Inputs, Buttons, Sheets, Drawer — alles, was eine andere Touch-Geometrie braucht.
- **Universelle Molecules** aus `molecules.jsx` mit `dense`/`compact`/`last`-Props für Listen-Items, die sich nur in Spacing unterscheiden.

### Organisms (`organisms.jsx`)

**Status:** Produktiv (Session 7). Geladen in allen drei HTML-Pages. Repariert: `MetricEditorRow`, `ChannelLimitChip`, `ChannelPreviewCard` plus lokale ME*-Helper (`MEModeToggle`, `METextBtn`, `MEIconArrow`, `MEHorizonChip`) und `applyChannel`-Helper ergänzt.

| Name                          | Zweck                                                                |
|-------------------------------|----------------------------------------------------------------------|
| `PresetRail`                  | Linke Spalte des Metrics-Editors: Profile + Save-as-eigen            |
| `MetricBucket`                | Block-Sektion mit Header + MetricEditorRow-Liste (Spalten / Detail)  |
| `MetricEditorRow`             | Eine Zeile pro Metrik: Index · Label · Horizont-Chips · Mode · Move · Reorder |
| `MetricOffShelf`              | Aufklappbarer »Nicht im Briefing«-Block                              |
| `ChannelPreviewStrip`         | 4-Karten-Vorschau pro Kanal (Email/Telegram/Signal/SMS)              |
| `ChannelPreviewCard`          | Einzel-Karte im Strip mit Mini-Tabelle + Detail-Zeile                |
| `ChannelLimitChip`            | Pill „Signal 7/6“ im Bucket-Header, warnt orange bei Überschreitung   |
| `MetricsEditorContextBar`     | Header mit Profil-Name + Counts (Spalten / Detail / Horizont-Slots) |
| `MetricsEditor`               | DIE konsolidierte Editor-Organism (Tour / Ort / Abo Kontexte)         |

**Daten-Konstanten und Helpers:** `WETTER_METRICS_CATALOG`, `WETTER_METRIC_BY_ID`, `WETTER_PRESETS`, `WETTER_CHANNELS`, `applyChannel`, `wetterAutoAssign`, `wetterDefaultHorizons`, `wetterDefaultScore`, `sampleWetterValue`.

**Hinweis:** `screen-metrics-editor.jsx` enthält noch eigene Inline-Versionen derselben Sub-Komponenten (historisch). Beim nächsten Touch des Screens: durch die Organism-API ersetzen. Bis dahin koexistieren beide — dank ME*-Prefix-Disziplin keine Babel-Scope-Kollision.

### Organisms (alt) — ERLEDIGT

| Name                          | Zweck                                                                |
|-------------------------------|----------------------------------------------------------------------|
| `PresetRail`                  | Linke Spalte des Metrics-Editors: Profile + Save-as-eigen            |
| `MetricBucket`                | Block-Sektion mit Header + MetricEditorRow-Liste (Spalten / Detail)  |
| `MetricOffShelf`              | Aufklappbarer »Nicht im Briefing«-Block                              |
| `ChannelPreviewStrip`         | 4-Karten-Vorschau pro Kanal (Email/Telegram/Signal/SMS)              |
| `MetricsEditorContextBar`     | Header mit Profil-Name + Counts                                       |
| `MetricsEditor`               | DIE konsolidierte Editor-Organism (Tour / Ort / Abo Kontexte)         |

**Plus Daten-Konstanten:** `WETTER_METRICS_CATALOG`, `WETTER_PRESETS`, `WETTER_CHANNELS`, Helpers `wetterAutoAssign` / `wetterDefaultHorizons` / `wetterDefaultScore` / `sampleWetterValue`.

**Nächster Schritt (Folge-Session):** Bei nächstem Touch des `screen-metrics-editor.jsx` die fehlenden Sub-Komponenten ergänzen (`MetricEditorRow`, `ChannelLimitChip`, `ChannelPreviewCard`) und `organisms.jsx` in `Gregor 20 - Redesign v2.html` einbinden. Bis dahin: NICHT laden, sonst Crash.

---

## 2 · Quellen-Inventur (historisch, vor Migration)

*Dieser Abschnitt ist Geschichts-Dokumentation. Der aktuelle Stand steht in §1. Mehrere genannte Dateien wurden mittlerweile gelöscht (Logo.html + logo-marks.jsx in v1_archiv → Session 7 final entsorgt; Briefing.html, Soll-Mockups.html, _soll-render.html, soll-mockups/, github-issues/, Issue Submitter.html, Issue 343 - Horizont Layouts.html alle in Mai 2026 nach Abschluss-Audit gelöscht). Verweise unten beziehen sich auf den Stand bei Audit-Erstellung.*

### 2.1 Bestehende Atom-Module

| Datei                | Komponenten / Exports                                                                                                                                       |
|----------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `brand-kit.jsx`      | `BrandWordmark`, `BrandUserBadge`, `BrandSidebarHeader`, `BrandSidebar`, `BrandShell`, `BRAND_NAV_ITEMS`                                                     |
| `atoms.jsx`          | `TopoBg`, `Eyebrow`, `Pill`, `Card`, `ElevSparkline`, `KV`, `Btn`, `Logo`, `WIcon`, `Dot`, `SectionH`, `AvatarStack`                                         |
| `mobile-shell.jsx`   | `PhoneFrame`, `TopAppBar`, `IconBtn`, `MIcon`, `BottomNav`, `Drawer`, `Sheet`, `Toast`, `MInput`, `MField`, `MBtn`, `MSwitch`, `MTab`, `ScreenScroll`, `MobileShell` |
| `sidebar.jsx`        | `Sidebar` — *delegiert an `BrandSidebar`* ✅                                                                                                                |
| `design-canvas.jsx`  | `DesignCanvas`, `DCSection`, `DCArtboard`, `DCPostIt` — Hosting-Tooling, kein Produkt-Atom                                                                   |
| `logo-marks.jsx`     | 12 Logo-Explorationen — **veraltet** (siehe Drift §3.1)                                                                                                      |

### 2.2 Pages (Root-HTML) und ihre Composition

| HTML                                | importiert (Auszug)                                                          | Page-Inhalt                                                  |
|-------------------------------------|------------------------------------------------------------------------------|--------------------------------------------------------------|
| `Gregor 20 - Komponenten.html`      | brand-kit, atoms, molecules, organisms, mobile-shell, screen-design-system(-mobile) | Atomic-Showcase — alle finalen Komponenten Desktop + Mobile |
| `Gregor 20 - Desktop.html`          | brand-kit, atoms, molecules, organisms, sidebar, alle `screen-*.jsx` (16), `ios-frame.jsx` | Design-Canvas mit allen Desktop-Flows (ohne DS-Artboard)     |
| `Gregor 20 - Mobile.html`           | brand-kit, atoms, molecules, organisms, mobile-shell, alle `screen-*-mobile.jsx` | Mobile-Pendant (ohne DS-Artboard)                            |
| `Briefing.html`                     | atoms                                                                        | Static-Email-Briefing-Render                                 |
| `Logo.html`                         | brand-kit, atoms, `logo-marks.jsx`                                            | **Veraltet** — zeigt »01 · Mountain · FINAL«, widerspricht brand-kit |
| `Soll-Mockups.html`                 | `soll-mockups/*.jsx`                                                          | Vorgegebene Soll-Flows                                       |
| `Issue 343 - Horizont Layouts.html` | atoms                                                                        | Issue-spezifische Layout-Studie                              |
| `Issue Submitter.html`              | —                                                                            | Tooling                                                      |
| `_soll-render.html`                 | —                                                                            | Render-Helper                                                |

---

## 3 · Drift- und Doppeldefinitions-Katalog

### 3.1 Logo

| Quelle                                       | Aussage                                                                                                          |
|----------------------------------------------|------------------------------------------------------------------------------------------------------------------|
| `brand-kit.jsx::BrandWordmark`               | **Kanonisch.** Mono-Schrift, lowercase, `gregor · zwanzig`, Caption »V0.20 · WETTER-BRIEFING«. PO-bestätigt.     |
| `atoms.jsx::Logo`                            | ✅ Delegiert an `BrandWordmark`.                                                                                  |
| `logo-marks.jsx::LogoMountain`               | ⚠️ Berg-Silhouette + Blitz. Mixed-Case, Subhead »Wetter-Briefings · Headless«. Steht in `Logo.html` als »FINAL«.   |
| `logo-marks.jsx::LogoStrikeV2` etc.          | ⚠️ 11 weitere Explorationen, keine als finale Wahl markiert.                                                       |

**Drift-Grund:** `Logo.html` wurde nach der PO-Entscheidung (Wordmark Variante B) nicht aktualisiert. Konzept 01 trägt noch das alte »FINAL«-Label.

### 3.2 Form-Felder

| Komponente                              | Datei                          | Form                                                          |
|-----------------------------------------|--------------------------------|---------------------------------------------------------------|
| `Field({label, sub, children})`         | `screen-trip-wizard.jsx`       | Desktop, Label in mono-caps                                   |
| `MField({label, sub, children})`        | `mobile-shell.jsx`             | Mobile, Label gleiches Mono-Caps-Pattern                      |
| `AuthField({label, hint, error, side})` | `soll-mockups/flow-9-auth.jsx` | Auth-Flow, Label + Hint + Error + Side-Link                   |

### 3.3 Inputs

| Komponente                              | Datei                          | Form                                                          |
|-----------------------------------------|--------------------------------|---------------------------------------------------------------|
| `Input({defaultValue, placeholder, small})` | `screen-trip-wizard.jsx`   | Desktop, `small`-Flag                                          |
| `MInput({value, type, leftIcon})`       | `mobile-shell.jsx`             | Mobile, mit Icon-Slot                                          |
| `AuthInput({type, placeholder, error, mono})` | `soll-mockups/flow-9-auth.jsx` | Auth, mit Error-State + Mono-Variante                          |

### 3.4 List-Rows / Detail-Rows

| Komponente                                          | Datei                          | Use                                                  |
|-----------------------------------------------------|--------------------------------|------------------------------------------------------|
| `KV({label, value, mono})`                          | `atoms.jsx`                    | Detail-Zeile, dashed bottom border                   |
| `ReportRow({report})` *(home variant)*              | `screen-home.jsx`              | Briefing-Plan-Zeile                                   |
| `ReportRow({label, sub, time, enabled})` *(wizard)* | `screen-trip-wizard.jsx`       | **Kollision!** Anderer Prop-Vertrag                   |
| `AlertRow`                                          | `screen-home.jsx`              | Alert-Zeile mit Tone                                  |
| `ChannelLine({kind, target, active, sub})`          | `screen-trip-wizard.jsx`       | Email/Signal/etc. + Toggle                            |
| `ThresholdRow({label, value})`                      | `screen-trip-wizard.jsx`       | Label + Mono-Value                                    |
| `PresetRow`, `ActiveMetricRow`                      | `screen-metrics-editor.jsx`    | Spezial-Rows für Metrics-Editor                       |
| `DSRow`, `DSTypeRow`                                | `screen-design-system-mobile.jsx` | Showcase-Rows (OK, showcase-eigen)                  |

### 3.5 Toggles / Switches

| Komponente                              | Datei                          | Form                                                          |
|-----------------------------------------|--------------------------------|---------------------------------------------------------------|
| `MSwitch({checked, onChange, label})`   | `mobile-shell.jsx`             | Touch, 44px Hit-Area                                          |
| Inline-Switch in `ChannelLine`           | `screen-trip-wizard.jsx`       | 32×18, kein eigener Name                                       |
| Inline-Switch in `ReportRow` (wizard)    | `screen-trip-wizard.jsx`       | 36×20, dito                                                    |

### 3.6 Buttons

| Komponente                              | Datei                          | Form                                                          |
|-----------------------------------------|--------------------------------|---------------------------------------------------------------|
| `Btn({variant, size, icon})`            | `atoms.jsx`                    | Desktop, 4 Varianten × 4 Sizes                                |
| `MBtn({variant, size, block, icon})`    | `mobile-shell.jsx`             | Mobile, +`danger`-Variante, +`block`                          |
| `TextBtn`, `IconArrow`                   | `screen-metrics-editor.jsx`    | Spezial-Inline-Buttons                                         |

### 3.7 Dubletten auf Dateiebene

| Pfad                                              | Status                                                                       |
|---------------------------------------------------|------------------------------------------------------------------------------|
| `mobile-shell.jsx` ↔ `gregor-zwanzig-mobile/project/mobile-shell.jsx` | **Duplikat** (vollständige Kopie)                              |
| `design-canvas.jsx` ↔ `v1_archiv/design-canvas.jsx`                   | Archiv-Kopie, OK                                                |
| `screen-trip-wizard.jsx` ↔ `screen-trip-wizard-mobile.jsx`            | Bewusst getrennt (Desktop vs. Mobile), OK                       |

---

## 4 · Vorgeschlagene Zielstruktur

Files am Projekt-Root, jeweils mit `Object.assign(window, {...})` exportierend.
SvelteKit-Pendant in Klammern für späteren Handoff.

```
brand-kit.jsx        ← bleibt: Wordmark + Sidebar + UserBadge       (lib/brand/)
atoms.jsx            ← erweitert: + Input, Field, Switch, Toggle    (lib/components/atoms/)
molecules.jsx        ← NEU: DetailRow, ToggleRow, ChannelRow,
                       ReportRow, AlertRow, ThresholdRow,
                       MetricChip, FormField                         (lib/components/molecules/)
organisms.jsx        ← NEU: BriefingCard, AlertList, StagePill-List,
                       ChannelEditor, MetricsEditor-Sub-Parts        (lib/components/organisms/)
mobile-shell.jsx     ← bleibt: Mobile Templates + Mobile-Atoms       (lib/components/templates/Mobile*/)
templates.jsx        ← NEU klein: DesktopShell, EditorLayout         (lib/components/templates/)
screen-*.jsx         ← werden dünner: nur noch Page-Komposition     (routes/*/+page.svelte)
```

### Naming-Konvention

| Layer       | Prefix    | Beispiel                                      |
|-------------|-----------|-----------------------------------------------|
| Atom        | *(keiner)*  | `Btn`, `Pill`, `Input`, `Switch`              |
| Molecule    | *(keiner, sprechender Name)* | `DetailRow`, `ChannelRow`, `ThresholdRow` |
| Organism    | *(keiner, sprechender Name)* | `BriefingCard`, `AlertList`, `MetricsTable` |
| Template    | `*Layout` oder `*Shell` | `DesktopShell`, `EditorLayout`         |
| Brand-only  | `Brand*`  | `BrandWordmark`, `BrandSidebar`               |
| Mobile-only | `M*`      | `MBtn`, `MInput`, `MField`, `MSwitch`         |

---

## 5 · Entscheidungs­vorlage (zur Klärung durch User)

Format: **Frage → Empfehlung Claude → User-Entscheidung**

### D1 · Logo-Drift in `Logo.html` ✅ entschieden

**Entscheidung:** Archivieren. `logo-marks.jsx` und `Logo.html` zunächst nach `v1_archiv/` verschoben, später (Session 9) komplett gelöscht — alte »01 · Mountain · FINAL«-Variante widersprach Brand-Kanonik und stiftete Verwirrung beim Wiederfinden.

---

### D2 · Favicon + Lockup ✅ entschieden

**Entscheidung:** Berg+Blitz wird zurückgeholt — **nicht nur** als Icon-Mark, sondern auch **im Wordmark als Lockup** (Glyph links + Mono-lowercase »gregor · zwanzig« rechts).

**Konsequenz für `brand-kit.jsx`:**
- Neu: `BrandIcon` — Berg+Blitz-Glyph (Geometrie aus `logo-marks.jsx::MountainSquare` **V1, mit Blitz**, nicht V2 mit Sonne). Kanonisches SVG, drei Größen (sm/md/lg).
- `BrandWordmark` wird zum **Lockup**: `<BrandIcon/>` + bestehender Mono-Typo-Text. Caption »V0.20 · WETTER-BRIEFING« bleibt erhalten.
- Neu: `BrandIconOnly` (oder eine Prop `<BrandWordmark icon="only"/>`) für quadratische Kontexte (Favicon, Avatar, App-Icon).
- Sidebar zeigt damit ab jetzt wieder den Berg+Blitz neben dem Typo-Wordmark — das ist der Punkt der Entscheidung.

**Favicon** wird aus `BrandIconOnly` abgeleitet: SVG (light/dark via media-query), PNG-Set 16/32/48/96/180/192/512, `favicon.ico` (Multi-Size), `apple-touch-icon`, `site.webmanifest`.

**Kollisions-Hinweis:** Der bisherige `brand-kit.jsx`-Kommentar sagt *»KEIN Bergmark-Glyph mehr im Sidebar-Kontext«*. Dieser Satz wird mit der Migration entfernt — die Begründung war die alte Berg-Variante mit Sonne (Wetter-Cliché). Berg+Blitz (Gewitter-DNA) ist jetzt **zurück** und gilt projektweit.

---

### D3 · `Field` / `MField` / `AuthField` zusammenführen?

**Frage:** Drei Field-Varianten. Eine vereinheitlichen oder bewusst getrennt lassen?

**Empfehlung:** **Ein** `Field` als Molecule mit Optional-Props (`hint`, `error`, `side`, `dense`). `MField` bleibt als Mobile-Alias mit anderem Spacing (44px Touch-Target). `AuthField` löschen.

**Begründung:** Field-Label + Sub + Error sind universell. Mobile-Touch-Target ist der einzige echte Unterschied — den decken wir mit `dense={false}` oder mit `MField` als Alias ab.

**Entscheidung D3 ✅:** Empfehlung übernommen. Ein `Field`-Molecule mit allen Optional-Props; `MField`-Alias bleibt für Mobile-Touch-Spacing; `AuthField` löschen.

---

### D4 · `Input` / `MInput` / `AuthInput` zusammenführen? ✅ entschieden

**Entscheidung:** Ein `Input`-Atom mit Props `{type, value, defaultValue, placeholder, leftIcon, error, mono, size}`. `MInput`-Alias mit `size="lg"` Default. `AuthInput` löschen.

---

### D5 · Zwei `ReportRow`-Definitionen 🚨

**Frage:** `screen-home.jsx::ReportRow({report})` vs. `screen-trip-wizard.jsx::ReportRow({label, sub, time, enabled})` — gleicher Name, inkompatible Signatur.

**Empfehlung:** Beide ins `molecules.jsx` heben mit **getrennten Namen**:
- `BriefingTimelineRow({report})` → für die Home-Übersicht (vergangenheits-/zukunfts-orientiert, Status-getrieben)
- `BriefingScheduleRow({label, sub, time, enabled})` → für den Wizard (Konfiguration, Toggle)

**Begründung:** Trotz Namensgleichheit sind das semantisch zwei verschiedene Sachen — ein vergangener/geplanter Versand vs. eine Konfigurations-Zeile. Ein generisches `ReportRow` wäre eine künstliche Verschmelzung.

**Entscheidung D5 ✅:** Empfehlung übernommen. Zwei getrennte Molecules: `BriefingTimelineRow` (Home, Status-getrieben) + `BriefingScheduleRow` (Wizard, Toggle-getrieben).

---

### D6 · `ChannelLine` (Wizard) vs. künftige Channel-Anzeige ✅ entschieden

**Entscheidung:** Empfehlung übernommen. `ChannelRow({kind, target, active, sub, onToggle})` als Molecule + `ChannelChip({kind, active})` für kompakte Anzeige.

---

### D7 · `StagePill` (Home) als Atom oder Organism?

**Frage:** Wird in `screen-home.jsx` definiert. Trip-Detail und Compare zeigen dasselbe Etappen-Streifen-Muster.

**Empfehlung:** Molecule, weil es eine Mini-Komposition aus Pill + Eyebrow + Risk-Indikator ist. Als `<StagePill stage={s} state="active|done|future|muted"/>`.

**Entscheidung D7 ✅:** `StagePill` als Molecule.

---

### D8 · Duplikat `gregor-zwanzig-mobile/project/mobile-shell.jsx` ✅ entschieden (revidiert)

**Befund nach genauerer Prüfung:** `gregor-zwanzig-mobile/` ist laut eigenem `README.md` ein **bewusstes Handoff-Paket** für die SvelteKit-Migration mit eigenem `mobile-patterns.md`, allen Mobile-Screens und eigener `tokens.css`. Es ist kein versehentliches Duplikat.

**Revidierte Empfehlung (User-bestätigt):** **Nicht löschen.** Stattdessen als Spec-Layer dokumentieren mit klarer Sync-Regel:

> *Die Wurzel-Dateien (`mobile-shell.jsx`, `screen-*-mobile.jsx`, `tokens.css`) sind kanonisch. `gregor-zwanzig-mobile/project/` ist der Handoff-Spiegel — wird vor jeder Handoff-Übergabe mit den Wurzel-Versionen synchronisiert.*

→ Eintrag in CLAUDE.md, plus optionales `sync-handoff.sh`-Skript in Folge-Session.

---

### D9 · `screen-design-system.jsx` als Showcase weiterverwenden?

**Frage:** Es gibt bereits einen Design-System-Screen mit Typografie, Farben, Bausteinen, Voice. Soll der zur kanonischen Komponenten-Showcase ausgebaut werden?

**Empfehlung:** **Ja, ausbauen.** Neue Sektionen anhängen: »Molecules« (DetailRow, ChannelRow, …), »Organisms« (BriefingCard, AlertList, …), »Templates« (DesktopShell, MobileShell). Damit gibt es **eine** Seite, die alles zeigt — auch perfekt als Handoff-Referenz für Claude Code.

**Entscheidung D9 ✅:** Showcase in `screen-design-system.jsx` ausbauen mit Sektionen »Molecules«, »Organisms«, »Templates«.

---

### D10 · CLAUDE.md erweitern um Komponenten-Regel? ✅ entschieden

**Empfehlung:** Folgenden Block in `CLAUDE.md` ergänzen:

```markdown
## Komponenten-Disziplin (Atomic Design)

Vor JEDER neuen UI-Arbeit:

1. Lies `brand-kit.jsx`, `atoms.jsx`, `molecules.jsx`, `organisms.jsx`
   und (falls Mobile) `mobile-shell.jsx` vollständig.
2. Existiert das Element bereits → verwende es. Keine Inline-Variante.
3. Existiert es nicht → erst dort hinzufügen, dann verwenden.
4. Brauchst du eine Variante, die das Atom nicht abdeckt → FRAGE den User,
   ob das eine neue Prop wird oder eine bewusste Ausnahme.

Naming-Konvention:
- Atoms / Molecules / Organisms / Templates: sprechender Name, kein Prefix
- Brand-only:   Brand*  (BrandWordmark, BrandSidebar)
- Mobile-only:  M*      (MBtn, MInput, MField)
- Templates:    *Shell oder *Layout

Single-Source-of-Truth: brand-kit.jsx = Markenwahrheit, atoms.jsx = Bausteine.
Bei Konflikt: brand-kit.jsx gewinnt.
```

**Entscheidung:** Empfehlung übernommen. Wird in dieser Session in `CLAUDE.md` ergänzt.

---

## 6 · Migrations-Reihenfolge (Vorschlag)

Nach Klärung der D1–D10 oben:

1. **Session 2:** Atoms-Lücken schließen (Input, Field, Switch) — wenig Risiko.
2. **Session 3:** `molecules.jsx` anlegen mit den 6 Molecules aus §3.4–3.6.
3. **Session 4:** `screen-home.jsx` und `screen-trip-wizard.jsx` migrieren — beide aufräumen, eigene Defs entfernen.
4. **Session 5:** Restliche Desktop-Screens nachziehen.
5. **Session 6:** Mobile-Screens (sind kürzer).
6. **Session 7:** Showcase in `screen-design-system.jsx` erweitern, `Logo.html` archivieren, CLAUDE.md ergänzen.
7. **Session 8:** Handoff-Issue für Claude Code mit der Spec aus diesem Dokument.

Jede Session ist abbrechbar — der vorherige Stand bleibt funktional.

---

## 7 · Was NICHT migriert wird

- `claude-code-handoff/` — Output-Artefakte, kein Source-Code.
- Email-themed Stats (`EmailStat`, `SumStat`, `CEStat`) — bewusst hardcoded Hex-Farben + Mono-Stack, simulieren Email-Client-Rendering.
- Interaktiver Stepper-Editor (`ThresholdRowM` in alert-config-mobile) — andere Domäne als die read-only ThresholdRow-Molecule.

---

## 8 · Verbleibende Promotion-Kandidaten (für spätere Sessions)

Keine akute Drift mehr, aber wenn der Screen das nächste Mal angefasst wird:

| Aktuell (lokal)                                         | Vorschlag                                                  | Hebel |
|---------------------------------------------------------|------------------------------------------------------------|-------|
| `screen-trips::TripRow`, `screen-trips-mobile::TripCardM` | `TripRow` Molecule + `TripCardM`-Variante mit `dense` Prop | mittel |
| `screen-trip-detail::Tab`                                | `Tab` Atom (Desktop-Pendant zu `MTab`)                     | mittel |
| `screen-trip-detail::StatusBadge`                        | Pill-Atom mit `tone="status"` erweitern                    | klein |
| `screen-trip-detail-mobile::ReportLineM`                  | Wenn weitere Briefing-Display-Varianten kommen → eigene Molecule | klein |

---

## 9 · Lessons aus dem Refactor

- **Babel-Scope-Falle:** Top-level `function X()` in `<script type="text/babel">` landet auf `window.X`. Lokale Helper in Pages MÜSSEN Page-Prefix tragen (jetzt in CLAUDE.md fixiert).
- **Backward-compatible Props:** Wenn Molecules erweitert werden, müssen Default-Werte das bisherige Verhalten erhalten (`dense=false`, `last=false`, `size="md"` etc.). So bricht keine Migration.
- **Implizite globale Abhängigkeiten:** `screen-trip-wizard-mobile.jsx` hat `ChannelLineM` aus `screen-trip-detail-mobile.jsx` global benutzt, ohne sie zu importieren. Solche Verkettungen sind unsichtbar bis zur ersten Löschung. Bei Cleanup IMMER projektweit grep.
