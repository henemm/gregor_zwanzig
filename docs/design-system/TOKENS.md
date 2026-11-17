# TOKENS · Design-Token-Referenz

> Single Source of Truth: **`tokens.css`** (Repo-Root). Dieses Dokument ist die menschen- und LLM-lesbare Spiegel-Referenz.
>
> Wenn `tokens.css` sich ändert, MUSS dieses Dokument in derselben Änderungs-Welle aktualisiert werden — sonst ist es out-of-sync und Claude Code rät.

---

## 1. Surface — Paper-Palette

| Token | Wert | Verwendung |
|---|---|---|
| `--g-paper` | `#f6f4ee` | App-Hintergrund — warmes Off-White |
| `--g-paper-deep` | `#ecead9` | Sidebar, Sektions-Hintergrund, Hover-State |
| `--g-card` | `#ffffff` | Karten, Tabellen-Zellen |
| `--g-card-alt` | `#faf8f1` | Zebra-Streifen, sekundäre Karten |
| `--g-rule` | `#d8d3c2` | Standard-Linien zwischen Elementen |
| `--g-rule-soft` | `#e7e2d3` | Sanfte Trennlinien |

> **Code-Namen-Mapping (`app.css`, seit #378 Surface-Stack-Migration):** Die produktiven `--g-surface-*`-Tokens tragen jetzt diese Werte:
> `--g-surface-0` (`#f6f4ee`, = `--g-paper`) · `--g-surface-1` (`#ffffff`, = `--g-card`, weiße Karten) · `--g-surface-2` (`#ecead9`, entspricht dem **Sandbox-Wert** von `--g-paper-deep`) · `--g-surface-raised` (`#faf8f1`, = `--g-card-alt`) · `--g-rule` (`#d8d3c2`) · `--g-rule-soft` (`#e7e2d3`).
> **Wichtig:** Das eigenständige Token `--g-paper-deep` in `app.css` bleibt bei `#ede9df` (außerhalb #378-Scope, Constraint C1) — es ist **nicht identisch** mit `--g-surface-2` (`#ecead9`), auch wenn beide einen sehr ähnlichen Beige-Ton tragen.

---

## 2. Ink — Typografie-Farben

| Token | Wert | Verwendung | Freigabe (auf weißer Card, #377) |
|---|---|---|---|
| `--g-ink` | `#1a1a18` | Primärtext (Titel, Body) | **AAA-text** |
| `--g-ink-2` | `#45433d` | Sekundärtext (Body in Cards) | **AAA-text** |
| `--g-ink-3` | `#6b675c` | Tertiärtext (Labels, Eyebrows) | **AA-text** |
| `--g-ink-muted` | `#5c5a52` | Sekundärtext, Captions, Hints, Daten-Labels | **AA-text** |
| `--g-ink-4` | `#9a958a` | Hint, Placeholder, Disabled, dekorative/Logo-Glyphen — **kein Lesetext** | **decorative only** (FAIL für Text) |

---

## 3. Accent — Burnt Orange

| Token | Wert | Verwendung | Freigabe (auf weißer Card, #377) |
|---|---|---|---|
| `--g-accent` | `#c45a2a` | Primäraktion, aktiver Nav-Item, Hervorhebung; als Textfarbe nur Large-Text oder mit Underline/`font-weight ≥ 600` | **AA-large** (Body-Text → `--g-accent-deep`) |
| `--g-accent-deep` | `#8c3e1a` | Text auf hellem Hintergrund, Accent-Body-Text | **AAA-text** (paper: AA-text) |
| `--g-accent-soft` | `#f3d9c8` | Borders um Accent-Tinted-Container | — (Surface) |
| `--g-accent-tint` | `rgba(196, 90, 42, 0.08)` | Sehr dezenter Accent-Hintergrund | — (Surface) |

---

## 4. Semantic — Status-Farben

| Token | Wert | Verwendung | Freigabe (auf weißer Card, #377) |
|---|---|---|---|
| `--g-good` | `#3d6b3a` | Aktiv, verbunden, OK | **AA-text** |
| `--g-warn` | `#c08a1a` | Warnung, Schwellwert nahe — nur als Hintergrund/Icon, **nicht** als Body-Textfarbe | **AA-large** (card), FAIL card-alt/paper |
| `--g-bad` | `#a83232` | Alarm, Fehler, kritisch, destruktiv | **AA-text** |
| `--g-info` | `#2a6cb3` | Neutrale Daten-Highlights | **AA-text** |

> Hinweis (#377): `--g-info` ist real `#2a6cb3` (5.39:1 AA), nicht `#2c5a8c` — frühere Doku korrigiert.

---

## 5. Wetter — Domain-spezifische Farben

| Token | Wert | Verwendung |
|---|---|---|
| `--g-weather-rain` | `#4a7ab8` | Niederschlag, Regen-Werte |
| `--g-weather-snow` | `#8aa4c0` | Schnee |
| `--g-weather-thunder` | `#c43a2a` | Gewitter |
| `--g-weather-sun` | `#d99a2a` | Sonne, klar |
| `--g-weather-cloud` | `#9a958a` | Bewölkt |

### 5a. Ampel — Wetter-Reiter (#2913)

Grafische Farben der Ampelstufen (Ampel-Leiste, Input-Unterkante, Segment-Farbpunkt). Nahe am Mockup Fassung 3, jede mindestens **3:1 gegen `--g-card`** in Hell und Dunkel (eigener Dark-Block). Abweichung vom Mockup nur, wo WCAG es verlangt. Farbe ist nie alleiniger Informationsträger. Prüfung: `ampel_tokens_kontrast.test.ts`.

| Token | Hell | Dunkel | Mockup |
|---|---|---|---|
| `--g-ampel-gruen` | `#15803d` | `#15803d` | `#15803d` |
| `--g-ampel-gelb` | `#b98100` (abgedunkelt) | `#d69500` | `#d69500` |
| `--g-ampel-orange` | `#d4530a` | `#d4530a` | `#d4530a` |
| `--g-ampel-rot` | `#a8104a` | `#d43a76` (aufgehellt) | `#a8104a` |

---

## 6. Typography — Schriften

| Token | Wert | Verwendung |
|---|---|---|
| `--g-font-sans` | `"Inter Tight", "Inter", system-ui, …` | Default Body, UI-Elemente |
| `--g-font-mono` | `"JetBrains Mono", "SF Mono", …` | Zahlen, Labels, Eyebrows, Mono-Strings |

**Featureflags global:** `font-feature-settings: "ss01", "cv11";` für sans, `"tnum", "zero";` für mono via `.mono`-Klasse.

---

## 7. Type-Scale

| Token | Größe | Verwendung |
|---|---|---|
| `--g-text-xs` | 11 px | Eyebrows, Captions in Mono |
| `--g-text-sm` | 13 px | Body-Text in Cards, Meta-Info |
| `--g-text-md` | 15 px | Default Body |
| `--g-text-lg` | 17 px | Mobile Page-Titles, große Body |
| `--g-text-xl` | 20 px | Sektion-Titles |
| `--g-text-2xl` | 24 px | Page-Titles |
| `--g-text-3xl` | 32 px | Page-Titles auf großen Headern |
| `--g-text-4xl` | 44 px | Display-Headlines (Auth-Screens) |
| `--g-text-5xl` | 60 px | Display-Hero |

**Mobile-Minimum für Form-Inputs:** 16 px (verhindert iOS Auto-Zoom). Falls 16 px nicht im Scale ist, dann hard-coded mit Kommentar.

---

## 8. Tracking — Letter-Spacing

| Token | Wert | Verwendung |
|---|---|---|
| `--g-track-tight` | `-0.02em` | Display-Headlines |
| `--g-track-normal` | `0` | Body |
| `--g-track-wide` | `0.06em` | Mono-Labels |
| `--g-track-caps` | `0.12em` | Eyebrows, Mono-Caps |

---

## 9. Spacing — 4 px Grid

| Token | Wert | Häufige Verwendung |
|---|---|---|
| `--g-s-1` | 4 px | Mini-Gaps |
| `--g-s-2` | 8 px | Inline-Gaps, Pill-Padding |
| `--g-s-3` | 12 px | Card-Body-Gap, Form-Field-Margin |
| `--g-s-4` | 16 px | Standard-Container-Padding (Mobile) |
| `--g-s-5` | 20 px | Card-Padding-Y |
| `--g-s-6` | 24 px | Sektion-Trennung |
| `--g-s-8` | 32 px | Page-Padding-X (Desktop) |
| `--g-s-10` | 40 px | Page-Padding-Y (Desktop), Hero-Gap |
| `--g-s-12` | 48 px | Sektion-Gap (groß) |
| `--g-s-16` | 64 px | Hero-Margin |
| `--g-s-20` | 80 px | Page-Top-Margin auf Auth-Screens |

### 9a. Maß-Tokens (#2913)

Reine Maße, **Light = Dark** (kein Wert im Dark-Block). Regel: Ein Maß im 4px-Raster nimmt `--g-s-*`, eine Schriftgröße der Skala `--g-text-*`, ein Radius `--g-r-*`. Nur was dort keinen exakten Wert hat, bekommt ein `--g-size-*`. **Nie runden** — so blieb der Wetter-Reiter beim Umzug in die Organismen pixelgleich. Der Name nennt den Wert: `--g-size-10px` ist 10 px (nicht Rasterstufe 10 wie `--g-s-10` = 40 px). Ein `--g-size-*` mit Rasterwert ist verboten (`tokens_masse.test.ts`).

| Token | Wert | Verwendung |
|---|---|---|
| `--g-tap-min` | 44 px | Mindest-Touch-Ziel bei Fingerbedienung (min-height/min-width von Knöpfen, Tap-Spalte; unsichtbare Trefferfläche des `Switch` mit `tap`, Höhe des `Aufklapper`-Kopfs — #2913 Scheibe (c)). Bei Mausbedienung gilt die Mockup-Höhe des Vorlagen-Wählers (#3003) |
| `--g-size-2px` | 2 px | kleinste Abstände, Fokusring-Versatz |
| `--g-size-3px` | 3 px | Ampel-Unterkante am Input (#2913 Teil 2) |
| `--g-size-10-5px` | 10.5 px | Grenzzahlen der Ampel-Leiste (#2913 Fix Metrik-Liste) |
| `--g-size-11-5px` | 11.5 px | Schrift der kompakten Segmented-Variante („Alarm ab“) |
| `--g-size-130px` | 130 px | Spalten-Mindestbreite Metrik-Name (Mockup `.mr`) |
| `--g-size-160px` | 160 px | Mindestbreite Mittelspalte (Ampel-Leiste + Erklärung) |
| `--g-size-190px` | 190 px | Spalten-Höchstbreite Metrik-Name (Mockup `.mr`) |
| `--g-size-5px` | 5 px | Radius halbhoher Balken (Ampel-Leiste) |
| `--g-size-6px` | 6 px | enge Abstände/Polster |
| `--g-size-10px` | 10 px | Abstände/Polster, Balkenhöhe |
| `--g-size-12-5px` | 12.5 px | Hilfs- und Erklärtext (Wetter-Reiter) |
| `--g-size-13px` | 13 px | Radius Schalter-Bahn |
| `--g-size-14px` | 14 px | Fließtext/Knopftext, Abstände |
| `--g-size-18px` | 18 px | Symbol-Knopf (Entfernen) |
| `--g-size-22px` | 22 px | Reiter-Überschrift, Schalter-Knopf |
| `--g-size-26px` | 26 px | Schalter-Bahn-Höhe |
| `--g-size-28px` | 28 px | Seiten-Polster oben |
| `--g-size-56px` | 56 px | Mindestbreite Schalter-Fläche |
| `--g-size-60px` | 60 px | Seiten-Polster unten |
| `--g-size-72px` | 72 px | Zahlenfeld-Breite (Grenzen-Editor) |
| `--g-size-120px` | 120 px | Spalten-Mindestbreite (Metrik-Name) |
| `--g-size-180px` | 180 px | Spalten-Höchstbreite (Metrik-Name) |
| `--g-size-420px` | 420 px | Menübreite (Vorlagen-Auswahl) |
| `--g-size-1100px` | 1100 px | Höchstbreite Reiter-Inhalt |
| `--g-size-0-08em` | 0.08 em | Laufweite Menü-Eyebrow |
| `--g-size-0-1em` | 0.1 em | Laufweite Gruppen-Eyebrow |

---

## 10. Radii

| Token | Wert | Verwendung |
|---|---|---|
| `--g-r-1` | 2 px | Sehr kleine Elemente (Mini-Bars, Score-Striche) |
| `--g-r-2` | 4 px | Buttons, Inputs |
| `--g-r-3` | 6 px | **Default für Cards** |
| `--g-r-4` | 10 px | Größere Cards, Hero-Container |
| `--g-r-pill` | 999 px | Pills, runde Buttons, Counter |

---

## 11. Elevation

| Token | Verwendung |
|---|---|
| `--g-shadow-1` | Default für Cards in Ruhe |
| `--g-shadow-2` | Hover auf Cards, Dropdown-Trigger aktiv |
| `--g-shadow-3` | Dropdown-Menü, Toast, Modal |

Dezent. Kein Material-Lifting.

### 11a. Schwebende Tabbar (Mobile-Shell)

Einzige erlaubte Glas-Fläche im Produkt. Konsumenten: `BottomNav.svelte`, `.mobile-scroll-pad`, Toast-/SaveIndicator-Anker.

| Token | Wert | Verwendung |
|---|---|---|
| `--g-nav-h` | 64 px | Höhe der Leiste |
| `--g-nav-gap` | 6 px | Abstand Leiste ↔ Home-Indicator-Zone |
| `--g-nav-inset` | 16 px | seitlicher Rand |
| `--g-nav-konto-gap` | 10 px | Luft zwischen Leiste und Konto-Kreis (Mobile-Shell S2) |
| `--g-nav-glass` | paper, 86 % Deckung | Fläche der Leiste (über `backdrop-filter`) |
| `--g-nav-blur` | 24 px | Blur-Radius des Glases |
| `--g-nav-hairline` | ink, 10 % | 1-px-Rahmen |
| `--g-nav-highlight` | weiß, 65 % | innere Oberkanten-Linie |
| `--g-nav-active` | accent, 12 % | Kapsel des aktiven Ziels |
| `--g-nav-clearance` | `h + gap + safe-area` | Oberkante der Leiste ab Viewport-Unterkante — **damit** rechnen, nie mit 64 px hart |

Fallback ohne `backdrop-filter` und bei `prefers-reduced-transparency`: opak `--g-paper-deep`.

---

## 12. Special-Effects

### `.g-topo`
CSS-Klasse mit gestapelten radial-gradients als Höhenlinien-Pattern. Verwendung: Auth-Screens, Empty-States, optional Login-Hero.

### `.mono`
Aktiviert Mono-Font mit `"tnum", "zero"` Feature-Flags.

### `.tnum`
Aktiviert `font-variant-numeric: tabular-nums` ohne Font-Wechsel — für gemischte Zahlen-Zellen.

---

## 12a. Dunkles Design (#2400)

Alle Dark-Werte stehen als `:root[data-theme="dark"]` in `frontend/src/app.css` (direkt hinter dem hellen `:root`). Geschaltet über `<html data-theme="dark">`: Kopf-Skript in `app.html` vor dem ersten Paint (aus `localStorage gz-dark`), zur Laufzeit `applyDarkMode()` in `frontend/src/lib/darkMode.ts`. Mechanik und Begründung: `docs/reference/design_system.md`, Abschnitt „Dunkles Design".

| Token | Hell | Dunkel |
|---|---|---|
| `--g-paper` / `--g-surface-0` | `#f6f4ee` | `#141412` |
| `--g-card` / `--g-surface-1` | `#ffffff` | `#1d1d1a` |
| `--g-card-alt` | `#faf8f1` | `#252522` |
| `--g-surface-raised` | `#faf8f1` | `#222220` |
| `--g-surface-2` / `--g-paper-deep` | `#ecead9` | `#2a2a26` |
| `--g-rule` / `--g-rule-soft` | `#d8d3c2` / `#e7e2d3` | `#3a3a35` / `#2c2c28` |
| `--g-ink` | `#1a1a18` | `#f1efe8` |
| `--g-ink-2` | `#45433d` | `#d2cfc4` |
| `--g-ink-3` / `--g-ink-muted` | `#6b675c` / `#5c5a52` | `#aaa699` |
| `--g-ink-4` (nur Placeholder/Disabled) | `#9a958a` | `#6f6c63` |
| `--g-ink-faint` (Linien) | `#9c9a90` | `#7a776d` |
| `--g-accent` / `--g-accent-deep` | `#c45a2a` / `#8c3e1a` | `#e07a4a` |
| `--g-accent-text` | `var(--g-accent)` | `#e07a4a` |
| `--g-on-accent` | `#ffffff` | `#141412` |
| `--g-accent-soft` / `--g-accent-tint` | `#f3d9c8` / `rgba(196,90,42,0.08)` | `#4a2c1e` / `rgba(224,122,74,0.14)` |
| `--g-success` / `--g-good` | `#3d6b3a` | `#6fbf6a` |
| `--g-warn` / `--g-warning` / `--g-warn-deep` | `#c08a1a` / `#c08a1a` / `#8a6210` | `#e0a83a` |
| `--g-danger` / `--g-bad` | `#a83232` | `#ee7a7a` |
| `--g-info` / `--g-info-deep` | `#2c5a8c` / `#1a4a7a` | `#7aa9dc` / `#9cc0e6` |
| `--g-ok-bg` / `--g-ok-fg` | `#f0fdf4` / `#166534` | `#16281a` / `#6fbf6a` |
| `--g-warn-bg` / `--g-warn-fg` | `#fffbeb` / `#92400e` | `#2b2312` / `#e0a83a` |
| `--g-danger-bg` / `--g-danger-fg` | `#fef2f2` / `#991b1b` | `#2e1a1a` / `#ee7a7a` |
| `--g-nav-glass` | `rgba(246,244,238,0.86)` | `rgba(20,20,18,0.86)` |
| `--g-nav-hairline` / `--g-nav-highlight` | `rgba(26,26,24,0.10)` / `rgba(255,255,255,0.65)` | `rgba(246,244,238,0.12)` / `rgba(255,255,255,0.06)` |
| `--g-nav-active` | `rgba(196,90,42,0.12)` | `rgba(224,122,74,0.18)` |
| `--g-elev-*`, `--g-shadow-*` | Ink-Schatten 4–16 % | Schwarz 35–50 % |

---

## 13. Anti-Pattern in `tokens.css` selbst

Im Token-File selbst gelten:

- Keine `!important`.
- Kein Selektor jenseits von `:root`, `.dark` (falls implementiert), `.g-topo`, `.mono`, `.tnum`.
- Kommentar-Block über jeder Sektion erklärt Verwendung.
- Reihenfolge der Sektionen entspricht diesem Dokument.

---

## 14. Erweiterung

Neue Tokens werden hinzugefügt, **wenn** ein neuer Use-Case sie wirklich verlangt — nicht prophylaktisch.

**Wenn ein neues Token benötigt wird:**
1. In `tokens.css` einfügen, mit Kommentar.
2. In diese TOKENS.md aufnehmen, mit Verwendungs-Beschreibung.
3. Bei der Komponente, die es nutzt, in `COMPONENTS.md` erwähnen.

---

## Versionierung

| Version | Datum | Anmerkung |
|---|---|---|
| v1.0 | 2026-05-21 | Initiale Token-Referenz — Runde 1 |
