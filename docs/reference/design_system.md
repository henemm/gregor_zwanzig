# Design-System Gregor 20 — Referenz

**Stand:** 2026-05-16 · **Quelle:** Anthropic-Artifact „Gregor 20 — Redesign v2.html" · **Status:** Referenz, synchron mit `frontend/src/app.css` (Issue #213)

Single Source of Truth für visuelle Sprache, Tokens und Komponenten-Verträge. Das Begleit-CSS liegt unter `design_system_tokens.css` und kann 1:1 in `frontend/src/app.css` übernommen werden (siehe Drift-Hinweise am Ende).

---

## Haltung in einem Satz

Alpin, präzise, datenehrlich. Paper-Off-White als Bühne, Burnt-Orange als einziger Markenakzent, Topo-Linien als ruhige Hintergrundstimmung.

**Voice — Tun:** „Heute 18:00 geht ein Abend-Briefing an Email + Telegram." · „Böen bis 47 km/h ab 17:00."
**Voice — Lassen:** „Wir kümmern uns um dein Wetter!" · „Aktiviere jetzt deinen Premium-Schutz" · Werbefloskeln.

---

## Design-Leitprinzipien (PO-bestätigt 2026-05-25)

> Aus `CLAUDE.md` ausgelagert (#2640); dort steht nur noch ein Satz mit Verweis hierher.

**Hoher Kontrast = Lesbarkeit.** Bei Konflikt zwischen „weicher Optik" und „klarer Lesbarkeit" gewinnt **Lesbarkeit** — das Produkt ist ein Briefing-Werkzeug für Wetter-/Tourenentscheidungen, Inhalt muss unter Zeitdruck lesbar sein. Steht über ästhetischen Präferenzen.

- Karten = weiß (`--g-card #ffffff`) auf warmer Off-White-Page (`--g-paper #f6f4ee`). Kein beiges Card-on-beige.
- Text-Kontrast mindestens WCAG-AA (4.5:1). `--g-ink-4` strikt nur Placeholder/Disabled, nie Captions/Help-Text/Daten-Labels (nur 2.85:1 auf Weiß).
- Akzent-Farben sparsam, nie alleiniger Lesbarkeits-Träger — Form + Position + Mono-Strecke tragen mit.

Quelle: `docs/design-requests/issue_15_atomic_design/RESPONSE-FROM-CLAUDE-DESIGN.md`. Folge-Arbeit: Surface-Stack-Migration → Token-Rename → Atom-Migration (Epic #368).

---

## 1 · Farben

### Surfaces
| Token | Hex | Verwendung |
|---|---|---|
| `--g-paper` | `#f6f4ee` | App-Hintergrund, leicht warmes Off-White |
| `--g-surface-0` | `#f6f4ee` | Alias für `--g-paper`, Surface-Basis |
| `--g-surface-1` | `#edeae1` | Erhöhte Surface (Card, gehobener Bereich) |
| `--g-surface-2` | `#e3dfd4` | Stark erhöhte Surface (Modal, Sticky-Bar) |
| `--g-paper-deep` | `#ede9df` | Bottom-Navigation Hintergrund (leicht dunkler, Issue #267) |
| `--g-rule-soft` | `rgba(26,26,24,0.08)` | Soft Border/Divider (Sticky-Footer, Sheet-Zeilen, Issue #267) |

Außerdem implementiert (`app.css`): `--g-card` `#ffffff` (Kartenfläche), `--g-card-alt` `#faf8f1`
(gedämpfte Fläche), `--g-rule` `#d8d3c2` (Linien, Grundlinie der Hub-Reiterleiste). Inline-Hex
ist auf Trip- und Vergleichsseiten durch diese Tokens ersetzt (#2881).

### Ink (Typografie)
| Token | Hex | Verwendung |
|---|---|---|
| `--g-ink` | `#1a1a18` | Primärtext, Button-Hintergründe |
| `--g-ink-muted` | `#5c5a52` | Sekundärtext, Body |
| `--g-ink-faint` | `#9c9a90` | Tertiär, Labels, Placeholder, Borders |

**Hauptaktion = Ink (`Btn primary`, `--g-ink`)** — z. B. „Senden“ im Hub-Kopf, „Trip speichern“/„Briefing aktivieren“ unten rechts im Fuß des geteilten Anlege-Rahmens (`shared/anlege-rahmen/AnlegeRahmen.svelte`, „Abbrechen“ als `Btn ghost` unten links, „Weiter“ als `Btn accent`). Ink auf Papier etwa 15:1 (Leitprinzip oben, ADR-0110, #2837). Die Fläche von `Btn accent` ist seit #2879 `--g-accent-deep` (siehe Accent).

**Design-Vision (nicht implementiert):** vierte Stufe (`--g-ink-4`) für Hint/Placeholder
— `--g-ink-faint` deckt beide ab.

**Deprecated (entfernt Issue #277):** 
- `--g-primary` — existiert nicht, nutze stattdessen `--g-ink` für Button-Hintergründe oder `--g-accent` für Active/Selected-States
- `--g-border` — existiert nicht, nutze stattdessen `--g-ink-faint` für Borders und Trennlinien

### Accent — Burnt Orange (alpin, markant)
| Token | Hex | Verwendung |
|---|---|---|
| `--g-accent` | `#c45a2a` | Akzent für „Weiter“ und Aktiv-Zustände (ADR-0110). Direkt nur ohne Text: Unterstrich des aktiven Reiters, Fortschritts-Segmente, Rahmen, Punkte, Logo-Blitz (Nicht-Text-Schwelle 3:1; auf Papier 3,94:1). Unter oder als Text immer `--g-accent-deep` |
| `--g-accent-deep` | `#8c3e1a` | Accent **unter oder als Text**: Fläche von `Btn accent`/`MBtn accent` („Weiter“), aktiver Handy-Reiter, Accent-Text (Kürzel, Rangnummern, Kennzahl „Aktiv“), Text auf `--g-accent-tint` |
| `--g-accent-tint` | `rgba(196,90,42,0.08)` | subtiler Fond hinter Accent-Text |

**Regel (#2879, ADR-0110-Nachtrag): Accent unter Text = `--g-accent-deep`.** Weiß bzw. Papier auf `--g-accent` erreicht nur 4,34:1 bzw. 3,94:1 und verfehlt WCAG-AA (4,5:1 für Text unter 24 px bzw. 18,66 px fett); auf `--g-accent-deep` sind es 7,45:1 bzw. 6,77:1. Hover dunkler: 85 % `--g-accent-deep` mit Schwarz. Dasselbe gilt sinngemäß für Warnfarbe als Text (`--g-warn-deep` statt `--g-warn`). `--g-ink-4` bleibt Platzhaltern und gesperrten Elementen vorbehalten; jeder Lesetext nutzt mindestens `--g-ink-3`. Prüftest: `frontend/e2e/kontrast-trip-vergleich.spec.ts`.

### Semantic
| Token | Hex | Bedeutung |
|---|---|---|
| `--g-success` | `#3a7d44` | Wetter OK, low risk |
| `--g-warning` | `#c8882a` | Achtung, Schwellwert nahe |
| `--g-danger` | `#a83232` | Alarm, kritisch (identisch mit `--g-bad`, 6,63:1 auf weißer Card, AA; #1831) |
| `--g-info` | `#2a6cb3` | Neutrale Daten-Highlight |

**Status (2026-06-02):** Alte Namen `--g-good`/`--g-warn`/`--g-bad` wurden vollständig durch Tailwind-konforme Namen ersetzt (Issue #541, #543, #544). Alle Komponenten und `app.css` verwenden die kanonischen Token.

### Akzent-Rollen und Status-Paare (#2400)
| Token | Hell | Dunkel | Rolle |
|---|---|---|---|
| `--g-accent-text` | `var(--g-accent)` | `#e07a4a` | Akzent als Textfarbe (aktive Reiter-Beschriftung, Preset-Link) |
| `--g-on-accent` | `#ffffff` | `#141412` | Schrift auf einer Akzentfläche (`--g-accent-deep`) |
| `--g-ok-bg` / `--g-ok-fg` | `#f0fdf4` / `#166534` | `#16281a` / `#6fbf6a` | Erfolgs-Box (Grund / Schrift und Rand) |
| `--g-warn-bg` / `--g-warn-fg` | `#fffbeb` / `#92400e` | `#2b2312` / `#e0a83a` | Hinweis-Box |
| `--g-danger-bg` / `--g-danger-fg` | `#fef2f2` / `#991b1b` | `#2e1a1a` / `#ee7a7a` | Fehler-Box |

Statusboxen tragen Grund, Schrift und Rand aus dem Paar (`border border-[var(--g-ok-fg)] bg-[var(--g-ok-bg)] text-[var(--g-ok-fg)]`); Tailwind-Palettenfarben (`bg-green-50`, `text-red-700` …) sind im Quelltext gesperrt (Ratsche `frontend/src/lib/__tests__/harte_farben_waechter.test.ts`, Ausnahmeliste darf nur sinken).

### Dunkles Design (#2400)

**Mechanik (eine Quelle):** Alle Dark-Werte stehen im Block `:root[data-theme="dark"]` in `frontend/src/app.css`, direkt hinter dem hellen `:root` (Kontrasttests lesen per Regex den ersten, hellen Treffer). `--color-*` folgen über `@theme` → `var(--g-*)` automatisch. Geschaltet wird allein über das Attribut `<html data-theme="dark">`:

- **Vor dem ersten Paint** setzt ein Inline-Skript im `<head>` von `frontend/src/app.html` (und `frontend/static/offline.html`) aus `localStorage gz-dark` das Attribut, `color-scheme` und `<meta name="theme-color">` (dunkel `#141412`, hell `#f6f4ee`). Kein Hell-Blitz beim Neuladen.
- **Zur Laufzeit** schaltet `applyDarkMode()` in `frontend/src/lib/darkMode.ts` (kein Inline-Style mehr in `+layout.svelte`) dieselben drei Dinge (Umschalter „Dunkles Design" in Sidebar und Konto-Blatt).
- Ohne gespeicherte Wahl startet die App hell; `prefers-color-scheme` wird bewusst nicht ausgewertet.
- `@custom-variant dark` bindet `dark:`-Klassen an das Attribut, nicht an das Betriebssystem.
- Kommt später eine CSP, braucht das Kopf-Skript einen Hash/Nonce (`kit.csp`).

**Palette (Text ≥ 4,5:1 auf jeder Fläche, Linien ≥ 3:1, WCAG 1.4.11):**

| Rolle | Token | Dunkel |
|---|---|---|
| Seitengrund | `--g-paper`, `--g-surface-0` | `#141412` |
| Karte | `--g-card`, `--g-surface-1` | `#1d1d1a` |
| Karte alt / erhöht | `--g-card-alt` / `--g-surface-raised` | `#252522` / `#222220` |
| Fläche 2 | `--g-surface-2`, `--g-paper-deep` | `#2a2a26` |
| Linien | `--g-rule` / `--g-rule-soft` | `#3a3a35` / `#2c2c28` |
| Text | `--g-ink` / `--g-ink-2` / `--g-ink-3`, `--g-ink-muted` | `#f1efe8` / `#d2cfc4` / `#aaa699` |
| nur Placeholder/Disabled (ADR-0008) | `--g-ink-4` | `#6f6c63` |
| Bedien-Linien (`--color-border/-input`) | `--g-ink-faint` | `#7a776d` (Startwert `#6f6c63` angehoben: 3,22:1 auf `--g-surface-2`) |
| Akzent | `--g-accent`, `--g-accent-deep`, `--g-accent-text` | `#e07a4a` |
| Status | `--g-success`/`--g-good`, `--g-warn`/`--g-warning`/`--g-warn-deep`, `--g-danger`/`--g-bad`, `--g-info` | `#6fbf6a`, `#e0a83a`, `#ee7a7a`, `#7aa9dc` |

**Akzent im Dunklen:** `--g-accent-deep` ist im Bestand zugleich Fläche (Knöpfe, Avatar) und Textfarbe (aktive Labels, Kennzahlen, Links). Ein dunkles `#8c3e1a` wäre als Text auf dunklem Grund unlesbar (≈ 1,7:1), darum wird es im Dunklen hell (`#e07a4a`) und die Schrift darauf dunkel (`--g-on-accent` = `#141412`, 6,19:1). Im Hellen bleibt Weiß auf `#8c3e1a` (7,45:1). Schrift auf Akzentflächen deshalb immer `var(--g-on-accent)`, nie `#fff`. Der Hover einer Akzentfläche hellt im Dunklen auf statt abzudunkeln.

Bewusst fest bleiben Wetter-/Risikofarben, Scrims, Leaflet-Kacheln, Mails und die weißen Knöpfe der Schalter (`atoms/Switch.svelte`, `mobile/MSwitch.svelte`; in der Ausnahmeliste der Ratsche mit je 1). Kontrast-Tabellen hell und dunkel: `python3 scripts/contrast_audit.py`, Anzeige auf `/_design`. Prüftests: `dark_palette_kontrast.test.ts`, `dark_mechanik.test.ts`, `offline_dark_konsistenz.test.ts`, Staging-Durchlauf `frontend/e2e/dark-mode-alle-routen.staging.spec.ts`.

### Wetter (aus echten Email-Reports abgeleitet)
| Token | Hex | Bedeutung |
|---|---|---|
| `--g-wx-rain` | `#4a7fb5` | Regen |
| `--g-wx-sun` | `#e8a820` | Sonne |
| `--g-wx-wind` | `#6b8a8a` | Wind |
| `--g-wx-snow` | `#a8c8e8` | Schnee |
| `--g-wx-thunder` | `#c43a2a` | Gewitter |
| `--g-wx-fog` | `#9a9a8a` | Nebel/Wolken |

**Hinweis:** Anthropic-Vision hatte `--g-weather-*`-Präfix — Ist verwendet
kürzeres `--g-wx-*` (in `app.css` seit längerem etabliert).

---

## 2 · Typografie

**UI-Font:** `Inter Tight` (400, 500, 600, 700) — über Google Fonts geladen
**Daten-Font:** `JetBrains Mono` (400, 500, 600) — für alle Zahlen, Koordinaten, Zeiten, Token

Aktive Feature-Settings im Body: `ss01`, `cv11` (Inter-Stylistic-Sets). Für Zahlen `tnum`, `zero` über Klasse `.mono`/`.tnum`.

### Skala (1.200 — Minor Third)
| Token | Größe | Anwendung |
|---|---|---|
| `--g-text-xs` | 11 px | Eyebrow, Caps-Labels |
| `--g-text-sm` | 13 px | Caption, Tabellen-Body |
| `--g-text-md` | 15 px | Body |
| `--g-text-lg` | 17 px | Body-Lead, Pull-Quote |
| `--g-text-xl` | 20 px | Heading H4 |
| `--g-text-2xl` | 24 px | Heading H3 |
| `--g-text-3xl` | 32 px | Title H2 |
| `--g-text-4xl` | 44 px | Display H1 |
| `--g-text-5xl` | 60 px | Display Hero |

### Tracking
| Token | Wert | Anwendung |
|---|---|---|
| `--g-track-tight` | `-0.02em` | Display (≥ 32 px) |
| `--g-track-normal` | `0` | Body |
| `--g-track-wide` | `0.06em` | Knappe Labels |
| `--g-track-caps` | `0.12em` | Eyebrow (uppercase, mono) |

### Heading-Regel
Headings ab 32 px erhalten `letter-spacing: var(--g-track-tight)`, `font-weight: 600`, `line-height: 1.05–1.15`.

---

## 3 · Spacing — 4-px-Grid

| Token | Wert | | Token | Wert |
|---|---|---|---|---|
| `--g-s-1` | 4 px | | `--g-s-8` | 32 px |
| `--g-s-2` | 8 px | | `--g-s-10` | 40 px |
| `--g-s-3` | 12 px | | `--g-s-12` | 48 px |
| `--g-s-4` | 16 px | | `--g-s-16` | 64 px |
| `--g-s-5` | 20 px | | `--g-s-20` | 80 px |
| `--g-s-6` | 24 px | | | |

Karten-Padding: 20–24 px. Section-Abstand: 56 px. Inner-Padding Tabs/Buttons: 6/10/14 px.

---

## 4 · Radii — zurückhaltend

| Token | Wert | Anwendung |
|---|---|---|
| `--g-radius-xs` | `0.125rem` (2px) | Inline-Marker |
| `--g-radius-sm` | `0.25rem` (4px) | Buttons |
| `--g-radius-md` | `0.5rem` (8px) | Cards, Inputs |
| `--g-radius-lg` | `0.75rem` (12px) | Großflächige Container |
| `--g-radius-pill` | `99rem` | Pills, Badges |

**Hinweis:** Anthropic-Vision hatte `--g-r-1`-bis-`--g-r-4` mit px-Werten — Ist
verwendet rem-basiertes Tailwind-Naming.

---

## 5 · Elevation — dezent

```css
--g-elev-1: 0 1px 3px  rgba(26,26,24,0.08);
--g-elev-2: 0 4px 12px rgba(26,26,24,0.12);
--g-elev-3: 0 8px 24px rgba(26,26,24,0.16);
```

`elev-1` für Default-Karten, `elev-2` für gehobene (Modal, Sticky), `elev-3`
für Floating (Popover).

**Hinweis:** Anthropic-Vision hatte zweiteilige Shadows (Hairline + Drop) — Ist
verwendet einfache, leicht erhöhte Schatten.

---

## 6 · Komponenten-Verträge

### Button (`Btn`) — implementiert in `frontend/src/lib/components/ui/btn/Btn.svelte`
- **Variants:** `primary` (default), `accent`, `outline`, `ghost`, `secondary`, `destructive`, `link`
- **`destructive`-Fläche (#1831):** per `color-mix(in oklab, var(--g-danger) 10%/18%, transparent)` aus dem Token gemischt (kein Literal `rgba(179,58,42,…)`); im Dunkelmodus dadurch aus `#ee7a7a` getönt. `@property --color-destructive` initial-value `rgb(168, 50, 50)`.
- **Sizes:** `xs`, `sm`, `md` (default), `lg`, `icon`, `icon-xs`, `icon-sm`, `icon-lg`
- **Tag-Switch:** Render als `<a>` wenn `href` gesetzt, sonst `<button>`
- **Disabled-State:** ARIA-konform (`aria-disabled="true"`; bei Links zusätzlich `role="link"`, `tabindex={-1}`)
- **Cursor-Boden-Regel (#2621):** `app.css` setzt in `@layer base` per `:where()` (Spezifität 0) `cursor: pointer` für aktive `button`, `[role="button"]`, `label[for]` und `summary` (gesperrt per `:disabled`/`aria-disabled="true"` ausgenommen), damit auch rohe Knöpfe die Hand zeigen; Btn-Atom (`not-allowed`) und Utilities wie `cursor-default` gewinnen weiter.
- **Tests:** SSR-Render-Test-Suite ist im Spec-Archiv von `issue_214_btn_feature_parity.md` (deaktiviert wegen Svelte-Loader-Limitation, Issue #228)

**Hinweis:** Anthropic-Vision hatte 4 Variants (`primary`/`accent`/`ghost`/`quiet`) —
Ist hat 7 (inkl. `outline`/`secondary`/`destructive`/`link` aus Tailwind-CVA-Erweiterung).
`quiet` aus der Vision wurde nicht implementiert; nutze `ghost` für leise Buttons.

### Pill / Badge
- Padding `3px 9px`, `border-radius: var(--g-r-pill)`, `font-size: 11px`, `font-family: mono`, `letter-spacing: 0.04em`, `text-transform: uppercase`, `font-weight: 500`, `line-height: 1.4`, `gap: 6px`
- **Tones:** `neutral` (Ink-Tint), `accent` (`--g-accent-tint` BG, `--g-accent-deep` FG), `good`, `warn`, `bad`, `ghost` (transparent, Rule-Rahmen)

### Card
- `background: var(--g-card)` · `border: 1px solid var(--g-rule)` · `border-radius: var(--g-r-3)` · `box-shadow: var(--g-shadow-1)` · Default-Padding `20 px`
- Akzent-Variante: `border-left: 3px solid var(--g-accent)`

### Eyebrow (Caps-Label)
Font Mono · 11 px · `letter-spacing: 0.12em` · `text-transform: uppercase` · `color: var(--g-ink-3)` · `font-weight: 500`. Steht über Headings als Mini-Index („01", „MORNING REPORT").

### Key-Value-Row (`KV`)
- Flex space-between · 6 px vertical padding · `border-bottom: 1px dashed var(--g-rule-soft)` · Label mono 12 px Ink-3 · Value mono/sans 13 px, `font-weight: 500/600`
- Standard-Konstrukt für Daten-Listen (Wetter-Werte, Stage-Metadaten)

### Dot (Status)
Inline-Block, Kreis, `width=height` 6/8/10 px. Tones: `good`, `warn`, `bad`, `info`, `neutral`, plus Wetter-Tones (`rain`, `sun`, `wind`, `snow`, `thunder`, `fog`, `cloud`).

### Wetter-Icons (`WIcon`)
Pure SVG, **kein Emoji**, Stroke 1.5 px, Linecap/Linejoin `round`. Set: `sun`, `cloud`, `rain`, `thunder`, `snow`, `wind`, `moon`, `headlamp`. Default-Größe 18–28 px, Default-Farbe `--g-ink-2`.

### Sparkline (Höhenprofil)
SVG, Stroke 1.5 px in `--g-accent`, Fläche `rgba(196,90,42,0.10)`. Default 280×60 px. Vertikal 85 %-Achse, 7.5 %-Padding oben/unten.

### Section-Header
Untertitel-Block: Eyebrow oben, Title 22 px / `font-weight: 600` / `letter-spacing: -0.01em`, optional Kicker 13 px Ink-3. Trennlinie unten `1px solid var(--g-rule)`, `padding-bottom: 12px`, `margin-bottom: 18px`.

### Reiterleisten, Listen, Fortschritt (ADR-0111, #2881)
- **Genau zwei Reiterleisten.** Im **Hub** `mobile/MTabBar.svelte`: am Computer kein Kasten (die globale
  Regel `[data-slot="segmented"]` wird zurückgesetzt), eine Grundlinie 1 px `--g-rule`, Reiter 13 px/500
  `--g-ink`, aktiv 600 mit 2-px-Unterstrich `--g-accent`, Zähler Mono 10 px neutral
  (`--g-paper-deep`/`--g-ink-3`, Radius 3 px); am Handy Pillen (aktiv `--g-accent-deep`). Beim **Anlegen**
  `shared/anlege-rahmen/AnlegeReiter.svelte` (Unterstrich auf allen Breiten, Zustände erledigt/gesperrt).
  Eine dritte, handgebaute Leiste ist nicht zulässig. Trip und Vergleich tragen jeweils dieselbe Leiste.
- **Listen:** Trip-Liste und Vergleichsliste sind Tabellen (`ListTable`), am Handy Karten-Zeilen; AP-003
  gilt für sie nicht mehr. Anlege-Aktion „+ Neuer Trip"/„+ Neuer Vergleich" überall `Btn primary` (Ink).
- **Fortschritt beim Anlegen** (`AnlegeFortschritt.svelte`): erledigt gefüllt `--g-accent` (3,94:1),
  offen ohne Füllung mit 1-px-Kontur `--g-ink-3` (5,13:1); der Zähler „n / 5" nennt den Stand als Text.
- **Hilfsklassen** (TOKENS.md §12, `app.css`): `.mono` = `--g-font-mono` mit `"tnum", "zero"`;
  `.tnum` = tabellarische Ziffern ohne Schriftwechsel.
- **Eingabefelder (Lieferung B):** keine nativen Datums-, Uhrzeit-, Auswahl- oder Radio-Felder auf Trip-
  und Vergleichsseiten. Datum `molecules/DatumFeld.svelte` (bits-ui DatePicker, Segmente Tag/Monat/Jahr,
  Kalender im Popover, Wochenbeginn Montag; de `19.11.2026`, en Tag zuerst `19/11/2026`), Uhrzeit
  `molecules/UhrzeitFeld.svelte` (bits-ui TimeField, immer 24 h); Werte nach außen weiter `YYYY-MM-DD`
  bzw. `HH:MM`. Auswahl `ui/select/Select.svelte` (bits-ui Select, Rolle listbox, `options: {value,label}[]`,
  `onValueChange`). Zwei bis drei feste Möglichkeiten (Mail-Format, Berichtsart im Sende-Dialog):
  `Segmented` mit `rolle="radio"` (radiogroup, Pfeiltasten).
- **Zustände ohne ✓/⊘** (ADR-0111 Punkt 7): `Dot` plus Text — erledigt `--g-good`, gesperrt
  `aria-disabled` und Punkt `--g-ink-4` (Speicher-Chip, Anlege-Reiter, Anlege-Hinweise, Startklar-Liste).
- **Tippflächen am Handy (< 900 px) mindestens 44 × 44:** Zurück-Link, „Mit Standardwerten speichern",
  Schnellwahl-Chips der Zustellung, ⓘ (unsichtbar vergrößert, negative Ränder halten die Zeile).
- **Mobil-Mindestgrößen (#2601):** Datums-/Uhrzeitsegmente (`DatumFeld`/`UhrzeitFeld`) ≥ 24 × 24 px auf Touch bzw. ≤ 899 px; Knopfboden 36 px zentral in `app.css`; Mindestschrift mobil 11 px. Einzige dokumentierte Ausnahme: Höhenprofil-Etappenwahl mit `data-tap-equivalent` (WCAG 2.5.8 „equivalent", gleichwertige Bedienung im Etappen-Tab). Mobil-Audit: Laufanleitung in `docs/specs/modules/mobile_ux_audit_2601.md`.
- Maßstab sind diese Regeln, das Mockup Fassung 3 und die Playwright-Paritäts-/Kontrasttests
  (`hub-tab-bar`, `kontrast-trip-vergleich`, `design-system-trip-vergleich`); die Soll-Bilder unter
  `claude-code-handoff/current/soll/` sind historisch.

### Topo-Hintergrund (`g-topo`, `TopoBg`)
Zwei Varianten:
1. **CSS-only** (`.g-topo`): radiale Gradients aus 5 Ellipsen — geeignet für statische Sektionen.
2. **SVG** (`TopoBg`-Atom): 22 gestapelte Polylines mit Sinus-Wellen + seeded Jitter (mulberry32, seed 42) — geeignet für Hero-Bereiche. Default `opacity: 0.18–0.5`.

---

## 7 · Layout

| Element | Spec |
|---|---|
| Max-Content-Width | 1320 px |
| Hero-Padding | 56 px |
| Artboard-Breiten (Demo) | 1280 / 1440 / 1680 / 760 / 420 (Email/SMS) |
| Email-Bühne | 760 px, BG `#e9e6dc`, Padding 24 px |
| SMS-Bühne | 420 px, BG `#e9e6dc`, Padding 24 px |

Top-Level-Hintergrund der App: `#f0eee9` (etwas wärmer als `--g-paper`, dient als Canvas zwischen Artboards).

---

## 8 · Logo

Wortmarke: „Gregor" (Ink) + „Zwanzig" (Accent) · `font-weight: 600` · `letter-spacing: -0.022em` · `line-height: 0.95`.
Bildmarke: SVG-Bergkamm in Ink (Stroke 2.6 px, `linejoin: miter`, `miterlimit: 8`) + Blitz-Glyph in Accent. Untertitel-Lockup mono 8 px Ink-3, `letter-spacing: 0.18em`, uppercase: „Wetter-Briefings · Headless".
Kontrast (#2896): Der Punkt der Wortmarke steht in `--g-ink-3` (dunkle Variante `rgba(246,244,238,0.55)`), nie in `--g-ink-4`; Avatar-Initialen (Konto-Kreis, Konto-Blatt, `BrandUserBadge accent`) liegen auf `--g-accent-deep`, damit beide mindestens 4,5:1 erreichen.

---

## 9 · Screen-Kanon (was es geben muss)

Aus dem Redesign-Canvas — diese Bühnen sind der visuelle Maßstab für alle Frontend-Arbeit:

1. **Foundation** · Design-System-Showcase (1280×1800)
2. **Heute · Startseite** (1440×1100)
3. **Trips · Übersicht** (1440×900)
4. **Trip-Detail · Hauptbühne** (1440×1500)
5. **Wetter-Metriken-Editor** (1440×1500)
6. **Alert-Konfigurator** (1440×1700)
7. **Wegpunkt-Editor** — Karte + Höhenprofil synchron, KI-Vorschläge orange gestrichelt, **keine Lat/Lon-Inputs** (1440×1100)
8. **Trip-Anlegen** — historisch als 4-Schritt-Wizard entworfen; heute progressive Tab-Anlege-Seite (`TripNewEditor`, #622)
9. **Compare** + **Location-New** — Ad-hoc-POI-Vergleich (1680 breit)
10. **Output-Preview** — Email (760) + SMS/Telegram (420), pixelnahe Vorschau (Signal entfernt, #610)

Die JSX-Quellen liegen im Anthropic-Artifact-Tarball; sind nicht in das Repo eingecheckt, weil Frontend-Stack hier SvelteKit (kein React) ist. Die Files sind Konzept-Vorlagen, keine Code-Quelle.

---

## 10 · Aktivitätsprofile — visuelle Signatur

Vier Aktivitätsprofile, je mit Akzent, Icon, Eyebrow-Label. Token-Werte sind
Aliase auf bestehende Design-Tokens — kein neuer Wert wird der Marke
hinzugefügt; nur die Verwendungsabsicht wird benannt.

| Profil | CSS-Token | Hex | Icon | Eyebrow-Label |
|---|---|---|---|---|
| Wintersport | `--g-profile-wintersport` | `#4a7fb5` (Alias `--g-wx-rain`) | `❄` | `Wintersport` |
| Wandern | `--g-profile-wandern` | `#3a7d44` (Alias `--g-success`) | `🥾` | `Wandern` |
| Summer-Trekking | `--g-profile-summer-trekking` | `#c45a2a` (Alias `--g-accent`) | `🏔` | `Sommer-Trekking` |
| Allgemein | `--g-profile-allgemein` | `#6b675c` (neutral, nahe `--g-ink-muted`) | `◯` | `Allgemein` |

**Helper:** `frontend/src/lib/utils/profileSignature.ts` —
`profileSignature(profile) → { accent, accentFallback, icon, eyebrow }`.
`accent` ist die CSS-Variable, `accentFallback` der Hex-Wert (für Inline-CSS
in Mails). Unbekannte Werte fallen auf `allgemein` zurück.

**Verwendungs-Regel:** Akzentfarbe rein dekorativ (Pin, Dot, Header-Border) —
nicht als Textfarbe verwenden; Kontrast auf hellen Surfaces ist knapp AA.
Sichtbare Profil-Identifikation immer als Eyebrow + Icon **plus** Akzent, nie
nur als Farbe (Branding-Kohärenz).

---

## 11 · Stand 2026-05-16 nach Issues #208–#212

Die in §1-§9 oben dokumentierten Tokens und Komponenten sind synchron mit
`frontend/src/app.css` (Stand `2026-05-16`). Issues #208 (Typography/Spacing),
#209 (Topo), #210 (Sidebar), #211 (Fonts), #212 (Button-Konsolidierung) sind
abgeschlossen — Naming und Werte sind hier konsolidiert.

**Bewusst nicht implementierte Anthropic-Design-Vision-Tokens:**
- `--g-paper-deep`, `--g-card`, `--g-card-alt`, `--g-rule`, `--g-rule-soft`
- `--g-ink-4` (vierte Ink-Stufe)
- `--g-accent-soft` (`--g-accent-deep` und `--g-accent-tint` sind vorhanden, siehe Accent, #2879)
- `--g-shadow-*` mit zweiteiliger Struktur (Hairline + Drop)
- Btn-Variant `quiet`

Diese sind kein Drift, sondern Pragmatik-Entscheidungen — bei Bedarf eigener Issue.

**Drift-Prävention:** Bei Token-Änderungen in `app.css` ist diese Spec mit
zu aktualisieren. Memory-Note `reference_design_system.md` warnt
explizit, vor jeder Frontend-/UI-Arbeit beide Quellen zu konsultieren.

---

## 12 · Begleit-Dateien

- `design_system_tokens.css` — Begleit-CSS aus Anthropic-Artifact. **Kann von
  `app.css` abweichen** — im Zweifel gilt `app.css`. Issue #213.
- `frontend_components.md` — bestehende SvelteKit-Komponenten-Karte.
- `sveltekit_best_practices.md` — Frontend-Architektur, ergänzt diese Design-Referenz technisch.

### Mail-Tokens: Single Source of Truth

**Entscheidung (Issue #254):** `frontend/src/app.css` ist die **verbindliche
Single Source of Truth** für alle Mail-Template-Tokens.
`src/output/renderers/email/design_tokens.py` ist die **abgeleitete Python-Kopie**
dieser Token-Werte und wird bei jeder Änderung in `app.css` mit-aktualisiert.
Die Datei `design_system_tokens.css` in diesem Verzeichnis ist eine
**Archiv-Referenz** des ursprünglichen Anthropic-Artifacts und nicht produktiv.

Hex-Werte der 11 Kern-Mail-Tokens sind aktuell 100 % konsistent zwischen
`app.css` und `design_tokens.py`. Es bestehen jedoch **Namens-Abweichungen**
zwischen der alten Anthropic-Tokens-Datei und der heutigen `app.css`:

| Alter Name (Anthropic) | Neuer Name (`app.css`) | Verwendung |
|---|---|---|
| `--g-good` | `--g-success` | Wetter OK, low risk |
| `--g-bad` | `--g-danger` | Alarm, kritisch |
| `--g-ink-2` | `--g-ink-muted` | Sekundärtext, Body |
| `--g-ink-3` | `--g-ink-muted` | (zusammengeführt mit `--g-ink-muted`) |
| `--g-ink-4` | `--g-ink-faint` | Tertiär, Labels, Placeholder |
| `--g-card` | `--g-surface-1` | Erhöhte Surface (Card) |
| `--g-weather-thunder` | `--g-wx-thunder` | Gewitter (siehe Farbkonflikt unten) |

**Farbkonflikt `--g-weather-thunder` / `--g-wx-thunder` (gelöst durch Issue #256):**
Die alte Anthropic-Tokens-Datei definierte `--g-weather-thunder` als rotes
`#c43a2a`. Bug #256 (2026-05-18) korrigiert `--g-wx-thunder` in `app.css`
von einem semantisch unpassenden Violett-Ton zu Rot (`#c43a2a`), konsistent
mit der Gefahr-Palette (`--g-danger`). Konflikt ist gelöst.

**Bewusste Divergenz — Ampel-Zellfärbung ist mail-only (Bug #1801, 2026-08-14):**
`design_tokens.py::_TONE_CSS`/`tone_css()` (Zell-Ampel gelb/orange/rot in
Trip-Stundentabelle und Ortsvergleich) sowie die neue Konstante
`G_AMPEL_TEXT_GREEN` (`#2f6b39`, WCAG-AA-Fix für den grünen Zelltext) liegen
**außerhalb** der 11 Kern-Mail-Tokens oben und haben **kein** `app.css`-Pendant
— reine Mail-Renderer-Werte ohne Frontend-Spiegelung. Der Fix hat diese
Ampel-Palette verändert (gelb `#d69500`/`#fdf4cd`, orange `#d4530a`/`#fbe3cc`,
rot `#a8104a`/`#f7d3e2` statt vormals `#ca8a04`/`#fbeeb8` bzw.
`#c2410c`/`#fad6b8` bzw. `#b91c1c`/`#f6c5bf`); `--g-success`/`--g-warning`/
`--g-danger` oben bleiben davon unberührt — sie sind ohnehin ein eigenes,
dreistufiges System, keine Spiegelung der vierstufigen Mail-Ampel. Details:
`docs/reference/renderer_email_spec.md` §„Segmente (Sektion 4)".

### Inventar: `src/output/renderers/email/html.py`

Status-Bewertung der sechs Bausteine, die EPIC 9 (Issue #236) adressiert:

| Baustein | Status | Details |
|---|---|---|
| Dunkel-Footer (`#1a1a18`) | **FEHLT** | Footer nutzt `G_PAPER` (`#f6f4ee`), kein dunkles `#1a1a18` |
| Daylight-Bar (SVG) | **FEHLT** | Kein SVG-Daylight-Rendering im lebendigen Mail-Pfad (`email/html.py`); die frühere `_format_daylight_html()`-Border-Left-Box wurde mit #1214 Scheibe 4 als toter Code entfernt |
| Tag-System ok/warn/risk/info | **FEHLT** | Box-Tints (`G_BOX_WARNING_BG`, `G_BOX_DANGER_BG`, `G_BOX_INFO_BG`) vorhanden, kein Pill/Tag-System |
| ActivityProfile-Parameter | **VORHANDEN** | `profile: Optional[ActivityProfile]`, `profile_signature()`, `sig.accent_hex` im Header |
| Inline-CSS-Only | **VORHANDEN** | `<style>`-Block + Inline-Styles, Google Fonts rein dekorativ |
| Inter Tight + JetBrains Mono | **VORHANDEN** | `FONT_UI`, `FONT_DATA`, `WEB_FONT_LINK` aus `design_tokens.py` vollständig eingebunden |

---

*Abgelegt von Claude (Tech-Lead-Rolle) am 2026-05-12, aktualisiert am 2026-05-16 (Issue #213). Quelle: Anthropic-Design-Artifact `puP0zvL3b8eR2dsEqc3R9Q`, synchronisiert mit `app.css`-Ist-Stand.*
