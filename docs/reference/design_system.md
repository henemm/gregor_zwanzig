# Design-System Gregor 20 — Referenz

**Stand:** 2026-05-12 · **Quelle:** Anthropic-Artifact „Gregor 20 — Redesign v2.html" · **Status:** Referenz (read-only)

Single Source of Truth für visuelle Sprache, Tokens und Komponenten-Verträge. Das Begleit-CSS liegt unter `design_system_tokens.css` und kann 1:1 in `frontend/src/app.css` übernommen werden (siehe Drift-Hinweise am Ende).

---

## Haltung in einem Satz

Alpin, präzise, datenehrlich. Paper-Off-White als Bühne, Burnt-Orange als einziger Markenakzent, Topo-Linien als ruhige Hintergrundstimmung.

**Voice — Tun:** „Heute 18:00 geht ein Abend-Briefing an Email + Signal." · „Böen bis 47 km/h ab 17:00."
**Voice — Lassen:** „Wir kümmern uns um dein Wetter!" · „Aktiviere jetzt deinen Premium-Schutz" · Werbefloskeln.

---

## 1 · Farben

### Surfaces (Paper-Palette)
| Token | Hex | Verwendung |
|---|---|---|
| `--g-paper` | `#f6f4ee` | App-Hintergrund — leicht warmes Off-White |
| `--g-paper-deep` | `#ecead9` | gedämpfter Akzent für Sektionen |
| `--g-card` | `#ffffff` | Karten, Tabellen |
| `--g-card-alt` | `#faf8f1` | Zebra, sekundäre Karten |
| `--g-rule` | `#d8d3c2` | Standard-Linien |
| `--g-rule-soft` | `#e7e2d3` | sanfte Trennlinien |

### Ink (Typografie)
| Token | Hex | Verwendung |
|---|---|---|
| `--g-ink` | `#1a1a18` | Primärtext |
| `--g-ink-2` | `#45433d` | Sekundärtext, Body |
| `--g-ink-3` | `#6b675c` | Tertiär, Labels |
| `--g-ink-4` | `#9a958a` | Hint, Placeholder |

### Accent — Burnt Orange (alpin, markant)
| Token | Hex | Verwendung |
|---|---|---|
| `--g-accent` | `#c45a2a` | Primär-Akzent (CTA, KI-Vorschlag, Logo-Blitz) |
| `--g-accent-deep` | `#8c3e1a` | Akzent-Text auf hellem Akzent-Tint |
| `--g-accent-soft` | `#f3d9c8` | Akzent-Hintergrund (Badge, Hover) |
| `--g-accent-tint` | `rgba(196,90,42,0.08)` | Subtiler Akzent-Fond |

### Semantic
| Token | Hex | Bedeutung |
|---|---|---|
| `--g-good` | `#3d6b3a` | Wetter OK, low risk |
| `--g-warn` | `#c08a1a` | Achtung, Schwellwert nahe |
| `--g-bad` | `#a83232` | Alarm, kritisch |
| `--g-info` | `#2c5a8c` | Neutrale Daten-Highlight |

### Wetter (aus echten Email-Reports abgeleitet)
| Token | Hex | Bedeutung |
|---|---|---|
| `--g-weather-rain` | `#4a7ab8` | Regen |
| `--g-weather-snow` | `#8aa4c0` | Schnee |
| `--g-weather-thunder` | `#c43a2a` | Gewitter |
| `--g-weather-sun` | `#d99a2a` | Sonne |
| `--g-weather-cloud` | `#9a958a` | Bewölkung |

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
| `--g-r-1` | 2 px | Inline-Marker |
| `--g-r-2` | 4 px | Buttons |
| `--g-r-3` | 6 px | Cards, Inputs |
| `--g-r-4` | 10 px | Großflächige Container |
| `--g-r-pill` | 999 px | Pills, Badges |

---

## 5 · Elevation — sehr dezent

```
--g-shadow-1: 0 1px 0 rgba(26,26,24,.04), 0 1px 2px  rgba(26,26,24,.04);
--g-shadow-2: 0 1px 0 rgba(26,26,24,.04), 0 4px 14px rgba(26,26,24,.06);
--g-shadow-3: 0 2px 0 rgba(26,26,24,.04), 0 12px 32px rgba(26,26,24,.08);
```

`shadow-1` für Default-Karten, `shadow-2` für gehobene (Modal, Sticky), `shadow-3` für Floating (Popover).

---

## 6 · Komponenten-Verträge

### Button (`Btn`)
- **Variants:** `primary` (Ink-Hintergrund, Paper-Text), `accent` (Burnt-Orange-Hintergrund, Weiß-Text), `ghost` (transparent, Ink-Rahmen `--g-rule`), `quiet` (transparent, kein Rahmen, Ink-2-Text)
- **Sizes:** `xs` 8/4 px · 11 px · `sm` 10/6 · 12 · `md` 14/9 · 13 · `lg` 20/12 · 14
- **Shape:** `border-radius: var(--g-r-2)` (4 px) · `font-weight: 500` · `letter-spacing: -0.005em`
- **Transition:** `all 120ms`
- **Focus:** `outline: 2px solid var(--g-accent); outline-offset: 2px`

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
8. **Trip-Wizard** — 4 Schritte: Profil → GPX-Import (Multi-Upload + Pause-Markierung) → Wegpunkte (KI-Vorschläge) → Briefings & Kanäle
9. **Compare** + **Location-New** — Ad-hoc-POI-Vergleich (1680 breit)
10. **Output-Preview** — Email (760) + SMS/Signal (420), pixelnahe Vorschau

Die JSX-Quellen liegen im Anthropic-Artifact-Tarball; sind nicht in das Repo eingecheckt, weil Frontend-Stack hier SvelteKit (kein React) ist. Die Files sind Konzept-Vorlagen, keine Code-Quelle.

---

## 10 · Drift zur aktuellen `frontend/src/app.css` (Stand 2026-05-12)

In `app.css` existiert bereits ein älterer `--g-*`-Token-Block aus Issue #143/#144. Werte weichen ab — eine Konsolidierung sollte als eigener Workflow gefahren werden (Schema-relevante Pflicht: nichts blind überschreiben).

| Kategorie | `app.css` heute | Tokens v2 (diese Referenz) | Empfehlung |
|---|---|---|---|
| Ink-Stufen | `--g-ink-muted`, `--g-ink-faint` | `--g-ink-2`, `--g-ink-3`, `--g-ink-4` | v2 übernehmen, 4 Stufen statt 3 |
| Surfaces | `--g-surface-0/1/2` | `--g-paper`, `--g-paper-deep`, `--g-card`, `--g-card-alt`, `--g-rule`, `--g-rule-soft` | v2 übernehmen, semantisch klarer |
| Semantic-Naming | `--g-success/warning/danger` | `--g-good/warn/bad` | v2 ist Designer-Naming, beibehalten — und Aliase legen für Migrations-Phase |
| Wetter-Naming | `--g-wx-*` | `--g-weather-*` | v2 übernehmen |
| Wetter-Werte | rain `#4a7fb5`, sun `#e8a820`, thunder `#5a3a7a`, fog `#9a9a8a` | rain `#4a7ab8`, sun `#d99a2a`, thunder `#c43a2a`, cloud `#9a958a` | v2 übernehmen — abgeleitet aus echten Email-Reports |
| Radii | `0.125 / 0.25 / 0.5 / 0.75 rem`, `99rem` | `2 / 4 / 6 / 10 px`, `999 px` | v2 in px übernehmen — die Skala ist enger |
| Elevation | flach (3 Stufen, jeweils ein Schatten) | zweiteilig (Hairline + Drop), 3 Stufen | v2 übernehmen — sieht wertiger aus |
| Buttons | `data-slot="btn"` mit `accent/ghost/outline` | `primary/accent/ghost/quiet` | v2 — „primary" (Ink) fehlt heute, „quiet" ebenfalls |

**Wenn migriert wird:** Pre-Snapshot über `data_schema_backup.py` ist nicht nötig (CSS, kein Datenmodell), aber Atom-Komponenten (`<Btn>`, `<Pill>`, `<Card>` etc. — heute als `[data-slot="*"]`) müssen synchron umgebaut werden, sonst zerfällt das UI.

---

## 11 · Begleit-Dateien

- `design_system_tokens.css` — 1:1 Drop-in-CSS aus dem Artifact. Diese Datei ist die maschinell verlässliche Quelle der Werte; die Markdown-Tabelle oben ist die lesbare Übersetzung.
- `frontend_components.md` — bestehende SvelteKit-Komponenten-Karte (nicht überschrieben).
- `sveltekit_best_practices.md` — Frontend-Architektur, ergänzt diese Design-Referenz technisch.

---

*Abgelegt von Claude (Tech-Lead-Rolle) am 2026-05-12 auf Anfrage des Users. Quelle: Anthropic-Design-Artifact `puP0zvL3b8eR2dsEqc3R9Q`.*
