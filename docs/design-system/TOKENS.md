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

| Token | Wert | Verwendung |
|---|---|---|
| `--g-ink` | `#1a1a18` | Primärtext (Titel, Body) |
| `--g-ink-2` | `#45433d` | Sekundärtext (Body in Cards) |
| `--g-ink-3` | `#6b675c` | Tertiärtext (Labels, Eyebrows) |
| `--g-ink-4` | `#9a958a` | Hint, Placeholder, Captions |

---

## 3. Accent — Burnt Orange

| Token | Wert | Verwendung |
|---|---|---|
| `--g-accent` | `#c45a2a` | Primäraktion, aktiver Nav-Item, ein Hervorhebungs-Element |
| `--g-accent-deep` | `#8c3e1a` | Text auf hellem Accent-Hintergrund |
| `--g-accent-soft` | `#f3d9c8` | Borders um Accent-Tinted-Container |
| `--g-accent-tint` | `rgba(196, 90, 42, 0.08)` | Sehr dezenter Accent-Hintergrund |

---

## 4. Semantic — Status-Farben

| Token | Wert | Verwendung |
|---|---|---|
| `--g-good` | `#3d6b3a` | Aktiv, verbunden, OK |
| `--g-warn` | `#c08a1a` | Warnung, Schwellwert nahe |
| `--g-bad` | `#a83232` | Alarm, Fehler, kritisch, destruktiv |
| `--g-info` | `#2c5a8c` | Neutrale Daten-Highlights |

---

## 5. Wetter — Domain-spezifische Farben

| Token | Wert | Verwendung |
|---|---|---|
| `--g-weather-rain` | `#4a7ab8` | Niederschlag, Regen-Werte |
| `--g-weather-snow` | `#8aa4c0` | Schnee |
| `--g-weather-thunder` | `#c43a2a` | Gewitter |
| `--g-weather-sun` | `#d99a2a` | Sonne, klar |
| `--g-weather-cloud` | `#9a958a` | Bewölkt |

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

---

## 12. Special-Effects

### `.g-topo`
CSS-Klasse mit gestapelten radial-gradients als Höhenlinien-Pattern. Verwendung: Auth-Screens, Empty-States, optional Login-Hero.

### `.mono`
Aktiviert Mono-Font mit `"tnum", "zero"` Feature-Flags.

### `.tnum`
Aktiviert `font-variant-numeric: tabular-nums` ohne Font-Wechsel — für gemischte Zahlen-Zellen.

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
