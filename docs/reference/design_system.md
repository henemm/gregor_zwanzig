# Design-System Gregor 20 — Referenz

**Stand:** 2026-05-16 · **Quelle:** Anthropic-Artifact „Gregor 20 — Redesign v2.html" · **Status:** Referenz, synchron mit `frontend/src/app.css` (Issue #213)

Single Source of Truth für visuelle Sprache, Tokens und Komponenten-Verträge. Das Begleit-CSS liegt unter `design_system_tokens.css` und kann 1:1 in `frontend/src/app.css` übernommen werden (siehe Drift-Hinweise am Ende).

---

## Haltung in einem Satz

Alpin, präzise, datenehrlich. Paper-Off-White als Bühne, Burnt-Orange als einziger Markenakzent, Topo-Linien als ruhige Hintergrundstimmung.

**Voice — Tun:** „Heute 18:00 geht ein Abend-Briefing an Email + Signal." · „Böen bis 47 km/h ab 17:00."
**Voice — Lassen:** „Wir kümmern uns um dein Wetter!" · „Aktiviere jetzt deinen Premium-Schutz" · Werbefloskeln.

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
| `--g-rule-soft` | `rgba(26,26,24,0.08)` | Soft Border/Divider (TopAppBar, BottomNav, Issue #267) |

**Design-Vision (nicht in `app.css` implementiert):** `--g-card`, `--g-card-alt`, `--g-rule` — wenn benötigt,
eigener Issue.

### Ink (Typografie)
| Token | Hex | Verwendung |
|---|---|---|
| `--g-ink` | `#1a1a18` | Primärtext, Button-Hintergründe |
| `--g-ink-muted` | `#5c5a52` | Sekundärtext, Body |
| `--g-ink-faint` | `#9c9a90` | Tertiär, Labels, Placeholder, Borders |

**Design-Vision (nicht implementiert):** vierte Stufe (`--g-ink-4`) für Hint/Placeholder
— `--g-ink-faint` deckt beide ab.

**Deprecated (entfernt Issue #277):** 
- `--g-primary` — existiert nicht, nutze stattdessen `--g-ink` für Button-Hintergründe oder `--g-accent` für Active/Selected-States
- `--g-border` — existiert nicht, nutze stattdessen `--g-ink-faint` für Borders und Trennlinien

### Accent — Burnt Orange (alpin, markant)
| Token | Hex | Verwendung |
|---|---|---|
| `--g-accent` | `#c45a2a` | Primär-Akzent (CTA, KI-Vorschlag, Logo-Blitz) |

**Design-Vision (nicht implementiert):** `--g-accent-deep` (Akzent-Text auf Tint),
`--g-accent-soft` (Hintergrund-Badge), `--g-accent-tint` (subtiler Fond) —
wenn benötigt, eigener Issue.

### Semantic
| Token | Hex | Bedeutung |
|---|---|---|
| `--g-success` | `#3a7d44` | Wetter OK, low risk |
| `--g-warning` | `#c8882a` | Achtung, Schwellwert nahe |
| `--g-danger` | `#b33a2a` | Alarm, kritisch |
| `--g-info` | `#2a6cb3` | Neutrale Daten-Highlight |

**Status (2026-06-02):** Alte Namen `--g-good`/`--g-warn`/`--g-bad` wurden vollständig durch Tailwind-konforme Namen ersetzt (Issue #541, #543, #544). Alle Komponenten und `app.css` verwenden die kanonischen Token.

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
- **Sizes:** `xs`, `sm`, `md` (default), `lg`, `icon`, `icon-xs`, `icon-sm`, `icon-lg`
- **Tag-Switch:** Render als `<a>` wenn `href` gesetzt, sonst `<button>`
- **Disabled-State:** ARIA-konform (`aria-disabled="true"`; bei Links zusätzlich `role="link"`, `tabindex={-1}`)
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
- `--g-accent-deep`, `--g-accent-soft`, `--g-accent-tint`
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
