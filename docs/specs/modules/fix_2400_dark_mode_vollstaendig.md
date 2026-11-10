---
entity_id: fix_2400_dark_mode_vollstaendig
type: module
created: 2026-11-09
updated: 2026-11-09
status: draft
version: "1.0"
tags: [frontend, dark-mode, kontrast, design-system, wcag-aa, adr-0008, theme]
---

# Vollständiger Dark Mode (Symptom #2400: `--g-ink-3` im Dark unter WCAG-AA)

## Approval

- [ ] Approved

## Purpose

Der dunkle Modus ist heute nur zur Hälfte gebaut. `applyDarkMode()` in `frontend/src/routes/+layout.svelte` überschreibt allein 18 shadcn-Tokens (`--color-*`) per Inline-Style auf `<html>`. Die gesamte Gregor-Palette (`--g-paper`, `--g-card`, `--g-surface-*`, `--g-ink`, `--g-ink-2..4`, `--g-rule*`, Nav-/Schatten-Tokens in `app.css`) bleibt hell. Folge (Messung Staging 2026-11-09, 1280 px, `gz-dark=1`): Body dunkel, Karten weiß, Wortmarke/Überschrift/Anmelden-Button 1,20:1, Untertitel 2,12:1, Eyebrow (`--g-ink-3`) 3,72:1, 10 von 30 Textelementen unter 4,5:1. Das Issue #2400 (Footer-Links/Eyebrow 3,51:1) ist nur ein Symptom.

PO-Entscheidung 2026-11-09 (Henning): „Ganz fertig bauen". Die Spec liefert eine vollständige Dark-Palette für alle Gregor-Tokens an einer zentralen Stelle, bindet den Schalter an ein Attribut statt an Inline-Styles, beseitigt den Hell-Blitz beim Laden und prüft jede Route im Dark. Nicht gewählt: Umschalter ausblenden; nur `--g-ink-3` ändern (würde Text auf den weiß bleibenden Karten verschlechtern).

Leitprinzip: „Hoher Kontrast = Lesbarkeit" (`docs/reference/design_system.md`, PO-bestätigt 2026-05-25), ADR-0008 „Kontrast vor Optik".

## Source

- **File:** `frontend/src/app.css` (Tokens `:root` Zeilen ~181-240, `@theme` Zeilen ~53-90), `frontend/src/app.html`, `frontend/src/routes/+layout.svelte` (Zeilen ~111-152, 166, 220), `frontend/static/offline.html`
- **Identifier:** `darkVars`, `applyDarkMode`, `localStorage gz-dark`, `:root[data-theme="dark"]` (neu), `@custom-variant dark` (neu)

> **Schicht:** ausschließlich Frontend (SvelteKit, `frontend/...`) und eine statische Seite. Keine Go-API-, keine Python-Änderung, keine Datenänderung, keine Änderung am Speicherort der Wahl (weiter `localStorage gz-dark`).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Es entsteht keine neue Komponente. Die Palette wirkt zentral über Tokens, damit automatisch gleich auf Trip-Editor (`context="route"`) und Compare-Editor (`context="vergleich"`) und auf die geteilten Bausteine in `frontend/src/lib/components/shared/`. Harte Farben in Komponenten mit Trip-/Compare-Pendant (z. B. `CorridorEditor` und `CorridorEditorMobile`) werden in beiden Varianten gleich auf Tokens gezogen (ein Muster, keine Auseinanderentwicklung, #1170). Der e2e-Durchlauf deckt `/trips/*` und `/compare/*` paarweise ab (AC-3).
> - **Mandantentrennung:** nicht betroffen. Die Wahl ist eine reine Geräte-Einstellung im Browser (`localStorage`), keine Nutzerdaten, kein Endpoint. Keine `user_id`-Logik.
> - **Kanäle:** nicht betroffen. Betrifft nur die Web-Oberfläche; E-Mail, Telegram, SMS und Premium-SMS bleiben unverändert (Mail-Renderer ist ein eigener Pfad, siehe Out of Scope).

## Scope

**Im Scope**

1. **Mechanik (Variante A, Tech-Lead-Entscheidung):** Dark-Werte als CSS-Block `:root[data-theme="dark"]` in `app.css`, direkt hinter dem hellen `:root`-Block (Reihenfolge wichtig: bestehende Kontrasttests lesen per Regex den ersten, hellen Treffer). `darkVars` in `+layout.svelte` entfällt; `applyDarkMode` setzt nur noch `data-theme`, `color-scheme` und `<meta name="theme-color">`. `--color-*` folgen automatisch über `@theme` → `var(--g-*)`. Bewusst im Dark-Block gesetzt: `--color-border` und `--color-input` (Linien-Token, siehe Palette).
2. **Hell-Blitz-Schutz:** Inline-Skript in `app.html` vor dem ersten Paint: liest `localStorage gz-dark`, setzt `data-theme`, `color-scheme` und `theme-color`. Keine CSP vorhanden (geprüft: `svelte.config.js`, `hooks.server.ts`, nginx), Inline-Skript zulässig. Kommt später eine CSP, wird `kit.csp` mit Hash/Nonce nötig (Hinweis, kein Teil dieser Spec).
3. **`dark:`-Varianten:** `@custom-variant dark` in `app.css`, gebunden an `:root[data-theme="dark"]`. Damit folgen `dark:`-Klassen (`ui/input`, `ui/badge`) dem Schalter statt dem Betriebssystem.
4. **Vollständige Dark-Palette** aller Flächen-, Ink-, Rule-, Nav-, Schatten-, Akzent- und Status-Tokens (Tabelle unten).
5. **Akzent-Rollen trennen:** neue Tokens `--g-accent-text` (Akzent als Textfarbe) und `--g-on-accent` (Schrift auf Akzentfläche). Flächen mit Text darauf nutzen `--g-accent-deep` (siehe Entscheidung Akzentfläche).
6. **Status-Token-Paare** `--g-ok-bg/-fg`, `--g-warn-bg/-fg`, `--g-danger-bg/-fg` (hell + dunkel) als Ersatz für die Tailwind-Statusboxen (`bg-green-50`, `bg-amber-50`, `text-*-800` usw.).
7. **Harte Farben auf Tokens:** `background:#fff` in `CorridorEditor.svelte` (~616) und `CorridorEditorMobile.svelte` (~538), `bg-white/40` in `ProfileEditor.svelte` (~117), `#8a1f1f` in `OfflineSperre.svelte` (~165), 9 Hex in `SaveIndicator.svelte`, Tailwind-Statusboxen (~91 Treffer in 13 Dateien: `account`, `login`, `register`, `verify-email`, `magic-link`, `reset-password`, `forgot-password`, `gpx-upload`), Akzentflächen-Stellen (8× `background: var(--g-accent)`, 4 Dateien mit `bg-accent`/`text-accent`).
8. **`static/offline.html`:** Mini-Skript und Dark-Variablen mit denselben Werten wie `app.css` (nachts relevant, kleiner Aufwand).
9. **Ratsche** gegen neue harte Farben im Quelltext (Ausnahmeliste darf nur sinken).
10. **e2e-Durchlauf** aller Routen im Dark bei 1280 px und 390 px (Textkontrast, keine weißen Karten, kein Hell-Blitz).
11. **Bestehende Tests anpassen**, die den Inline-Style prüfen: `frontend/e2e/theme-bridge.spec.ts` (AC-5), `frontend/e2e/mobile-konto-sheet.spec.ts` (Zeilen ~85-95); `frontend/e2e/helpers.ts` (Dark-Tokens/Messung).
12. `scripts/contrast_audit.py` und `frontend/src/routes/_design/+page.svelte` führen Dark mit (Werte aus `app.css` lesen oder gespiegelt prüfen).
13. Doku: `docs/reference/design_system.md`, `docs/design-system/TOKENS.md` (Dark-Palette).

**Nicht im Scope (Out of Scope)**

- **Mails** (eigener Renderer, keine Web-Tokens), Telegram-/SMS-Texte.
- **Leaflet-Kacheln** (externe Kacheln) bleiben hell; nur das umgebende Bedienelement (Zoom-Knöpfe, Attribution, Legenden außerhalb der Kachel) wird geprüft.
- **`prefers-color-scheme` als Startwert** ohne gespeicherte Wahl: nein, nicht verlangt. Der Schalter bleibt die einzige Quelle, Standard ist Hell.
- Wetter-/Risikofarben (Gewitter, Regen, Wind usw.): bleiben fachlich fix, nur Kontrastprüfung im Dark.
- Gewollt fix bleiben: weiße Schrift auf Akzent-/Statusflächen, Switch-Knöpfe, Scrims, SVG-Häkchen.
- Neue Schriften, Layout, Größen, Umbenennung des Umschalters („Dunkles Design"), Position im Konto-Menü.
- Systemweites Umbauen von `--g-accent` für Nicht-Text-Verwendungen (Ring, Zierpunkte, Tint).

## Entscheidung Akzentfläche (Abgleich mit #2896 und #2879)

`app.css` kennt bereits `--g-accent-deep: #8c3e1a` und nutzt es seit #2879 (ADR-0110-Nachtrag) für `[data-slot="btn"][data-variant="accent"]`; #2896 legt Avatar-Initialen darauf (Weiß auf `#8c3e1a` = 7,45:1). Die Analyse schlug für Flächen mit weißer Schrift zunächst einen neuen Wert `#b5521f` (5,01:1) vor. Die Spec bleibt **konsistent mit dem bestehenden Muster**: Flächen mit Text darauf gehen auf `--g-accent-deep` (hell und dunkel gleich, Weiß darauf 7,45:1, kontrastreicher als 5,01). Ein zweiter, hellerer Flächenton `#b5521f` würde zwei Stufen derselben Rolle erzeugen. `--g-accent` (`#c45a2a`) bleibt unverändert für Nicht-Text (Fokusring, Zierpunkte, Tint, Akzentkapsel). Der Altbefund (Weiß auf `#c45a2a` = 4,34:1) wird behoben, indem die 8 Flächenstellen mit Text auf `--g-accent-deep` umgestellt werden. Die Rolle „Akzent als Textfarbe" wird über `--g-accent-text` getrennt: hell = `var(--g-accent)` (Ist-Zustand; siehe Known Limitations), dunkel = `#e07a4a`.

## Estimated Scope

- **LoC:** Quellcode ca. +300 / -150 (app.css ~90, Komponenten ~200, Layout/Skript ~30), Tests ca. +250
- **Files:** ca. 25-35 (1 CSS, 2 HTML, 1 Layout, ca. 15-27 Svelte-Dateien, 3-4 e2e/Test-Helfer, 3 neue Tests, 2 Doku, 1 Skript)
- **Effort:** high (Blast Radius: jede Seite optisch; technisch zentral an einer Stelle). Ein Workflow, ein PR (Epic themenweise abschließen).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | Design-Tokens | `@theme`-Mapping `--color-*` → `--g-*`, helle `--g-*`, `--g-accent-deep`, Dark-Block (neu) |
| `frontend/src/routes/+layout.svelte` | Mechanik | `applyDarkMode`, Persistenz `gz-dark`, Umschalter-Callback |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte`, `KontoSheet.svelte` | Umschalter „Dunkles Design" | nur Callback, unverändert |
| `docs/adr/0008-kontrast-vor-optik.md` | ADR | Text ≥ 4,5:1; `--g-ink-4` nur Placeholder/Disabled |
| `docs/specs/modules/ink4_kontrast_2371.md`, `fix_2896_kontrast_zierpunkt_avatar.md`, `design_optimierungen.md` | Vorgänger-Specs | Messlogik, Akzentfläche, Umschalter (#70) |
| Service Worker | Auslieferung | liefert `offline.html`; Hinweis: Cache-Version prüfen, damit die neue `offline.html` ausgeliefert wird |
| `frontend/src/routes/_design/+page.svelte`, `scripts/contrast_audit.py` | Anzeige/Audit | bisher nur hell |

## Implementation Details

### Dark-Palette (Startwerte, WCAG nachgerechnet; Feinjustierung nur nach oben im Kontrast)

Flächen: `--g-paper`/`--g-surface-0` `#141412` · `--g-card`/`--g-surface-1` `#1d1d1a` · card-alt `#252522` · `--g-surface-raised` `#222220` · `--g-surface-2`/`--g-paper-deep` `#2a2a26` · `--g-rule` `#3a3a35` · `--g-rule-soft` `#2c2c28`.

| Text-Token | Hex | auf paper | auf card | auf card-alt | auf surface-2 |
|---|---|---|---|---|---|
| ink | `#f1efe8` | 16,03 | 14,68 | 13,36 | 12,52 |
| ink-2 | `#d2cfc4` | 11,82 | 10,83 | 9,85 | 9,24 |
| ink-3 / ink-muted | `#aaa699` | 7,57 | 6,94 | 6,31 | 5,92 |
| ink-4 (nur Placeholder/Disabled, ADR-0008) | `#6f6c63` | 3,51 | 3,22 | 2,93 | 2,74 |
| accent-text | `#e07a4a` | 6,19 | 5,67 | 5,16 | 4,84 |
| success | `#6fbf6a` | 8,20 | 7,51 | 6,83 | 6,41 |
| warn | `#e0a83a` | 8,64 | 7,91 | 7,20 | 6,74 |
| danger | `#ee7a7a` | 6,76 | 6,20 | 5,64 | 5,28 |
| info | `#7aa9dc` | 7,50 | 6,87 | 6,25 | 5,86 |

Weitere Dark-Werte:

- `--g-accent-deep` hell `#8c3e1a` mit `--g-on-accent` `#ffffff` (7,45:1); dunkel `--g-accent-deep` `#e07a4a` mit `--g-on-accent` `#141412` (6,19:1). Stand nach Validierung, Begründung: `--g-accent-deep` dient im Bestand auch als Textfarbe (Pills, Links) auf dunklem Grund; ein dunkles `#8c3e1a` wäre dort unlesbar (ca. 1,7:1). AC-7 bleibt erfüllt (mindestens 4,5:1 in beiden Modi).
- Mechanik zur Laufzeit liegt in `frontend/src/lib/darkMode.ts` (`applyDarkMode()`: `data-theme`, `color-scheme`, `theme-color`), nicht als Inline-Style in `+layout.svelte`; das Skript vor dem ersten Paint steht in `app.html`.
- `--g-ink-faint` dunkel `#7a776d` (Startwert `#6f6c63` angehoben, 3,22:1 auf `--g-surface-2`).
- Nicht-Text-Akzent `--g-accent` im Dark `#e07a4a` (Fokusring, Zierpunkte); Tint/Kapsel `rgba(224,122,74,…)` analog.
- `--g-ink-faint` (Linien, `--color-border`/`--color-input`) im Dark so, dass Rand-/Eingabelinien gegen den angrenzenden Grund ≥ 3:1 liegen (WCAG 1.4.11). Startwert `#6f6c63` (3,51:1 auf paper, 3,22:1 auf card), im Test nachzurechnen und bei Bedarf anzuheben.
- Status-Paare (Box-Hintergrund/Schrift) hell und dunkel jeweils ≥ 4,5:1 (Schrift auf Box), z. B. dunkel Schrift in Status-Hex der Tabelle auf einem dunklen, leicht getönten Box-Grund.
- Nav-Glas `rgba(20,20,18,0.86)`, Hairline hell-auf-dunkel `rgba(246,244,238,0.12)`, Highlight `rgba(255,255,255,0.06)`, Schatten schwarz mit höherer Deckung (`rgba(0,0,0,0.35..0.5)`).
- `color-scheme: dark` im Dark-Block; `theme-color` dunkel `#141412`, hell wie bisher `#f6f4ee`.

### Reihenfolge der Umsetzung (TDD)

1. **Palette als roter Unit-Test** (`node --test`): liest den Dark-Block aus `app.css`, rechnet alle Text/Grund-Paare der Tabelle, Rand-Paare ≥ 3:1, Weiß auf `--g-accent-deep` hell und dunkel, Status-Paare. Rot, solange kein Dark-Block existiert.
2. **Mechanik:** Dark-Block, `@custom-variant dark`, `app.html`-Skript, `+layout.svelte` (`darkVars` raus). e2e `theme-bridge.spec.ts`/`mobile-konto-sheet.spec.ts` von Inline-Style auf `data-theme` und berechnete Werte umstellen.
3. **Messlauf** aller Routen im Dark (e2e) liefert die Verstoßliste (Startpunkt für Schritt 4).
4. **Rollen-Tokens und harte Farben:** Akzent/Status-Tokens, Komponenten auf Tokens, `offline.html`.
5. **Ratsche scharf**, sobald die Verstoßliste leer ist; Ausnahmeliste darf nur sinken.

### Mechanik-Details

- Das Skript in `app.html` setzt das Attribut synchron im `<head>`, vor dem ersten Paint; `applyDarkMode()` bleibt für den Umschalter zur Laufzeit zuständig und schreibt dieselben drei Dinge (Attribut, `color-scheme`, `theme-color`) und die Persistenz `gz-dark`.
- Ist `gz-dark` nicht gesetzt oder `0`, bleibt es hell (kein `prefers-color-scheme`).
- Bestehende Kontrasttests, die `token()`-Regex auf `app.css` nutzen, behalten den ersten (hellen) Treffer; der Dark-Block steht deshalb hinter `:root`.

## Expected Behavior

- **Input:** Nutzer schaltet „Dunkles Design" im Konto-Menü ein (Desktop-Sidebar oder Mobil-Konto-Blatt) und navigiert durch die App; später lädt er die Seite neu.
- **Output:** Alle Seiten zeigen dunkle Flächen mit hellem Text; Karten sind dunkel, Text auf jeder Fläche ≥ 4,5:1. Footer-Links und Eyebrow (`--g-ink-3`) ≥ 4,5:1. Beim Neuladen mit gespeicherter Wahl erscheint nie ein heller Zwischenzustand. Der Hellmodus sieht aus wie bisher, nur Flächen mit weißer Schrift auf Orange sind dunkler (`--g-accent-deep`).
- **Side effects:** Keine Datenänderung. `localStorage gz-dark` bleibt die einzige Quelle. Leaflet-Karten bleiben hell (Kacheln).

## Acceptance Criteria

- **AC-1:** Given die Startseite ausgeloggt und `localStorage gz-dark=1` bei 1280 px / When der Kontrast von Footer-Links, Eyebrow (`--g-ink-3`) und Versionszeile (`--g-ink-muted`) gegen den effektiven Hintergrund gemessen wird / Then beträgt er jeweils mindestens 4,5:1 (vorher Eyebrow 3,72:1, Versionszeile 3,04:1).
  - Test: Playwright-Messlauf gegen Staging (Viewport 1280x800), `getComputedStyle(...).color` und effektiver Hintergrund, WCAG-Formel wie `messeKontrast`; vorher rot, nachher >= 4,5. Zusätzlich Kern-Test: `--g-ink-3`/`--g-ink-muted` aus dem Dark-Block gegen paper, card, card-alt und surface-2 >= 4,5.

- **AC-2:** Given der Dark-Block in `app.css` / When für jedes Text-Token (`--g-ink`, `--g-ink-2`, `--g-ink-3`, `--g-ink-muted`, `--g-accent-text`, `--g-success`, `--g-warn`, `--g-danger`, `--g-info`) der Kontrast gegen `--g-paper`, `--g-card`, `--g-surface-2` und card-alt berechnet wird / Then liegt jeder Wert bei mindestens 4,5:1; `--g-ink-4` ist die einzige Ausnahme und ausschließlich für Placeholder und Disabled zugelassen (ADR-0008).
  - Test: Kern-Test (`node --test`), liest Hex-Werte aus dem Dark-Block von `app.css`, rechnet WCAG-Kontrast; die Verfälschung „`--g-ink-3` im Dark auf `#6b675c` (hell)" muss rot werden.

- **AC-3:** Given jede Route der App (aus dem Routenbaum abgeleitet, ausgeloggt und eingeloggt, Trip- und Ortsvergleich-Seiten paarweise) bei 1280 px und 390x844 mit `gz-dark=1` / When jeder sichtbare Textknoten gegen seinen effektiven Hintergrund gemessen wird / Then liegt keiner unter 4,5:1 (Ausnahme: `::placeholder` und `:disabled` mit `--g-ink-4` nach ADR-0008) und es gibt keine Karte oder Fläche mit hellem Hintergrund (Luminanz > 0,5) auf dunklem Seitengrund.
  - Test: neuer Playwright-Durchlauf (`frontend/e2e/dark-mode-alle-routen.staging.spec.ts`) gegen Staging; Messung am gerenderten DOM (`messeTextknotenImBrowser`), Routenliste aus dem Routenbaum, Verstöße werden mit Route, Selektor und Wert ausgegeben; Screenshot je Route (Fresh-Eyes).

- **AC-4:** Given eine gespeicherte Dunkel-Wahl (`gz-dark=1`) / When die Seite neu geladen wird / Then trägt `<html>` das Attribut `data-theme="dark"` schon vor dem ersten Paint, und der erste gerenderte Frame hat keinen hellen Seitengrund (kein Hell-Blitz).
  - Test: Playwright mit `addInitScript` für `localStorage`, Messung von `document.documentElement.dataset.theme` und `getComputedStyle(body).backgroundColor` bei `DOMContentLoaded` (vor Hydrierung, JavaScript des Frameworks gedrosselt bzw. `page.route` verzögert) sowie `theme-color` und `color-scheme`; vorher rot (Attribut fehlt, Seitengrund hell).

- **AC-5:** Given die App im Hellmodus / When der Nutzer „Dunkles Design" einschaltet, wieder ausschaltet und die Seite jeweils neu lädt / Then wechselt die Darstellung sofort bei jedem Klick (ohne Neuladen), und der Zustand bleibt nach Neuladen erhalten (dunkel bleibt dunkel, hell bleibt hell); `data-theme`, `color-scheme` und `theme-color` wechseln konsistent mit.
  - Test: Playwright gegen Staging an Desktop (Sidebar-Umschalter, 1280 px) und Mobil (Konto-Blatt, 390 px): Klick, Messung von `--g-paper` (berechnet) und Body-Hintergrund, Reload, erneute Messung; angepasste Tests `theme-bridge.spec.ts` AC-5 und `mobile-konto-sheet.spec.ts` prüfen jetzt `data-theme` und berechnete Werte statt Inline-Style.

- **AC-6:** Given der Hellmodus (kein `gz-dark`) / When die Kerntokens (`--g-paper`, `--g-card`, `--g-ink`, `--g-ink-2`, `--g-ink-3`, `--g-ink-4`, `--g-rule`) und die bestehenden Kontrasttests (#2371, #2896) geprüft werden / Then sind Werte und Ergebnisse unverändert; als einzige Hell-Änderung stehen Flächen mit weißer Schrift auf Orange auf `--g-accent-deep` (Weiß darauf mindestens 4,5:1).
  - Test: bestehende Kern-Tests (`ink4_kontrast`, `zierpunkt_avatar_kontrast`, `ink4_waechter`) laufen unverändert grün; Kern-Test vergleicht die hellen Token-Hex-Werte gegen die Liste (nur-lesen-Snapshot im Test, kein Dateiinhalt-Check als Verhaltensnachweis), Gegenprobe: Änderung an `--g-ink-3` hell muss rot werden.

- **AC-7:** Given jede Akzentfläche mit Text (Buttons `data-variant="accent"`, Avatar, Chips, Badges, die bisher `background: var(--g-accent)` nutzten) / When die Schrift gegen den Flächengrund gemessen wird, im Hell- und im Dunkelmodus / Then beträgt der Kontrast mindestens 4,5:1 (erwartet 7,45:1 für Weiß auf `--g-accent-deep`).
  - Test: Kern-Test rechnet `--g-on-accent` gegen `--g-accent-deep` aus dem hellen und dem Dark-Block; Playwright-Messlauf über die Akzentflächen (Button, Konto-Kreis, Konto-Blatt) in beiden Modi; Gegenprobe „Fläche zurück auf `--g-accent` `#c45a2a`" muss rot werden (4,34).

- **AC-8:** Given der Dunkelmodus und eine `dark:`-Klasse (z. B. in `ui/input` und `ui/badge`) / When das Betriebssystem auf Hell steht, aber der Schalter auf Dunkel, sowie umgekehrt (OS dunkel, Schalter hell) / Then folgen die `dark:`-Varianten ausschließlich dem Schalter, nicht dem Betriebssystem.
  - Test: Playwright mit `colorScheme: 'light'` und `gz-dark=1` (Input hat dunkle Variante) sowie `colorScheme: 'dark'` und `gz-dark=0` (Input hat helle Variante), Messung von `getComputedStyle` an Input und Badge.

- **AC-9:** Given Statusboxen (Erfolg, Warnung, Fehler) auf `account`, `login`, `register`, `verify-email`, `magic-link`, `reset-password`, `forgot-password` und `gpx-upload` / When die Schrift gegen den Boxen-Hintergrund gemessen wird, im Hell- und im Dunkelmodus / Then beträgt der Kontrast mindestens 4,5:1 in beiden Modi, und die Box ist als Status erkennbar (Rand oder Tönung mit Rand-Kontrast ≥ 3:1 gegen den Seitengrund).
  - Test: Kern-Test rechnet die Token-Paare `--g-ok-*`, `--g-warn-*`, `--g-danger-*` aus beiden Blöcken; Playwright erzeugt je Seite eine Statusbox (Fehlerfall/Erfolgsfall im echten Ablauf) und misst im DOM, hell und dunkel.

- **AC-10:** Given `static/offline.html` (Offline-Seite des Service Workers) / When sie mit `gz-dark=1` aufgerufen wird / Then ist Seitengrund dunkel, Text und Link jeweils mindestens 4,5:1 und es gibt keinen hellen Blitz; ohne `gz-dark` bleibt sie hell wie bisher.
  - Test: Playwright öffnet `/offline.html` direkt mit und ohne gesetztem `localStorage`, misst Hintergrund und Textkontrast; Kern-Test prüft, dass die Dark-Hex-Werte in `offline.html` mit dem Dark-Block der `app.css` übereinstimmen (Werte-Gleichheit, damit sie nicht auseinanderlaufen).

- **AC-11:** Given der Quelltext unter `frontend/src` / When die Ratsche läuft / Then enthält er keine neuen harten Farben außerhalb der Token-Definitionen (`#fff`/`#ffffff` als Fläche, `bg-white`, `bg-<farbe>-NN`, `text-<farbe>-NNN`, `rgba(26,26,24,…)`), und die Ausnahmeliste ist gegenüber dem Stand dieser Spec nicht gewachsen (sie darf nur sinken, am Ende dieser Arbeit leer bis auf die in Scope genannten gewollten Festfarben).
  - Test: neuer Ratschen-Test (`node --test`) scannt `frontend/src/**/*.{svelte,css,ts}` mit Ausnahmeliste (Datei, Zahl, Begründung); die Verfälschung „`bg-white` in einer Komponente neu einfügen" muss rot werden.

- **AC-12:** Given Eingabefelder, Karten- und Trennlinien, Fokusring, Umschalter-Kanten im Dunkelmodus / When der Kontrast der Linie gegen den angrenzenden Grund gemessen wird / Then beträgt er mindestens 3:1 für Linien, die ein Bedienelement erkennbar machen (Eingabe-Rand, Checkbox, Schalter, Fokusring; WCAG 1.4.11); rein dekorative Trennlinien (`--g-rule-soft`) sind ausgenommen.
  - Test: Kern-Test rechnet `--color-border`/`--color-input` (= `--g-ink-faint` im Dark) und `--g-accent` (Fokusring) gegen paper, card und surface-2; Playwright misst `border-color` eines Eingabefelds im Dark gegen den Kartengrund.

- **AC-13:** Given die Wetter-/Risikofarben, SaveIndicator, OfflineSperre und die Editor-Flächen (Corridor-Editor Desktop und Mobil, ProfileEditor) im Dunkelmodus / When sie in `/trips/*`, `/compare/*` und den Einstellungen gerendert werden / Then stehen dort keine weißen oder hellen Flächen auf dunklem Grund, und Text darauf ist ≥ 4,5:1; Trip- und Compare-Variante verhalten sich gleich.
  - Test: Playwright misst die genannten Komponenten in Trip-Editor (`context="route"`) und Compare-Editor (`context="vergleich"`), Kontrast und Flächenluminanz paarweise; Ergänzung im Durchlauf aus AC-3.

- **AC-14:** Given die Leaflet-Karten in Trip-Editor und Ortsvergleich im Dunkelmodus / When die Seite gerendert wird / Then bleiben die Kacheln hell (bewusst), aber alle Bedienelemente und Beschriftungen um die Karte (Zoom-Knöpfe, Legende, Überschriften) sind lesbar (≥ 4,5:1) und die Karte hat einen erkennbaren Rand (≥ 3:1) gegen den dunklen Grund.
  - Test: Playwright misst Textknoten und Rand im Karten-Container auf Staging im Dunkelmodus; Kachelinhalt wird nicht gemessen.

## Geplante Tests

| Schicht | Test | Nachweis |
|---------|------|----------|
| Kern (deterministisch, ohne Netz) | `frontend/src/lib/__tests__/dark_palette_kontrast.test.ts` (neu, `node --test`, `node --import ./test-lib-loader.mjs --experimental-strip-types --test`): liest Dark-Block und helle Tokens aus `app.css`, rechnet WCAG; prüft Weiß auf `--g-accent-deep`, Status-Paare, Linien ≥ 3:1, `offline.html`-Werte = Dark-Block | AC-1 (Token-Teil), AC-2, AC-6, AC-7, AC-9, AC-10, AC-12 |
| Kern (Ratsche) | `frontend/src/lib/__tests__/harte_farben_waechter.test.ts` (neu): scannt Quelltext, Ausnahmeliste darf nur sinken | AC-11 |
| Kern (Mechanik am gerenderten Markup) | `frontend/src/lib/__tests__/dark_mechanik.test.ts` (neu): wertet `app.html`-Skript in einer DOM-Umgebung aus (`localStorage` gesetzt/nicht gesetzt: Attribut, `color-scheme`, `theme-color`), kein Mock der eigenen Annahme | AC-4 (Logik), AC-5 (Logik) |
| Live-E2E (nur in `/e2e-verify`, Staging) | `frontend/e2e/dark-mode-alle-routen.staging.spec.ts` (neu): alle Routen aus dem Routenbaum, 1280 und 390 px, Textkontrast, keine hellen Flächen, kein Hell-Blitz, Schalter hin und zurück, `dark:`-Entkopplung vom OS, Statusboxen, Offline-Seite, Karten-Rahmen | AC-1, AC-3, AC-4, AC-5, AC-7, AC-8, AC-9, AC-10, AC-13, AC-14 |
| Bestehende e2e angepasst | `theme-bridge.spec.ts` (AC-5), `mobile-konto-sheet.spec.ts` (~85-95), `helpers.ts` | AC-5 |
| Bestandstests | `ink4_waechter.test.ts`, `zierpunkt_avatar_kontrast.test.ts`, Golden-Dateien (`frontend/src/routes/__tests__/fixtures/auth/*`, `tests/golden/*`) mit Token-/Klassenänderungen | AC-6; Golden gezielt nachziehen, nur wo Klassen sich ändern |
| Fresh-Eyes | Screenshots je Route Dark (Desktop und Mobil) | Wirkt dunkel stimmig, keine Fremdkörper, Hell weiterhin unverändert |

Verbotenes Mock-Theater (`Mock()`/`patch()`, die nur die eigene Annahme spiegeln) und Dateiinhalt-Checks als Verhaltensnachweis werden nicht verwendet; der Werte-Abgleich `offline.html` ↔ Dark-Block ist eine Konsistenzprüfung zweier Quellen der Wahrheit und trägt `# doc-compliance-test`-Kennzeichnung, ersetzt nicht den Browser-Nachweis aus AC-10. Der Staging-Messlauf braucht eine eingeloggte Staging-Sitzung (Staging-`.env`).

## Dateiliste (geplant)

| Datei | Änderung |
|-------|----------|
| `frontend/src/app.css` | MODIFY (Dark-Block, `@custom-variant dark`, `--g-accent-text`, `--g-on-accent`, Status-Paare) |
| `frontend/src/app.html` | MODIFY (Inline-Skript) |
| `frontend/src/routes/+layout.svelte` | MODIFY (`darkVars` raus, `applyDarkMode` schlank) |
| `CorridorEditor.svelte`, `CorridorEditorMobile.svelte`, `ProfileEditor.svelte`, `OfflineSperre.svelte`, `SaveIndicator.svelte` | MODIFY (harte Farben auf Tokens) |
| `account`, `login`, `register`, `verify-email`, `magic-link`, `reset-password`, `forgot-password`, `gpx-upload` (Svelte-Routen) | MODIFY (Statusboxen auf Token-Paare) |
| Svelte-Dateien mit `background: var(--g-accent)` und Text (8 Stellen, 4 Dateien mit `bg-accent`/`text-accent`) | MODIFY (Fläche auf `--g-accent-deep`, Text auf `--g-accent-text`) |
| `frontend/static/offline.html` | MODIFY |
| `frontend/e2e/theme-bridge.spec.ts`, `mobile-konto-sheet.spec.ts`, `helpers.ts` | MODIFY |
| `frontend/e2e/dark-mode-alle-routen.staging.spec.ts` | CREATE |
| `frontend/src/lib/__tests__/dark_palette_kontrast.test.ts`, `harte_farben_waechter.test.ts`, `dark_mechanik.test.ts` | CREATE |
| `scripts/contrast_audit.py`, `frontend/src/routes/_design/+page.svelte` | MODIFY |
| `docs/reference/design_system.md`, `docs/design-system/TOKENS.md` | MODIFY |
| Golden-Dateien | MODIFY (nur falls betroffen) |

## Test Plan

Siehe `## Geplante Tests`: Palette-Kern-Test zuerst rot schreiben (kein Dark-Block vorhanden), dann Mechanik und Palette, dann Messlauf aller Routen als Verstoßliste, dann Rollen-Tokens und harte Farben bis die Liste leer ist, dann Ratsche scharf. Staging-Messlauf in `/e2e-verify`. Hellmodus-Regression über bestehende Kontrasttests (AC-6) und Fresh-Eyes-Screenshots.

## Definition of Done

- AC-1 bis AC-14 erfüllt und nachgewiesen (Kern-Schicht grün, Staging-Durchlauf grün).
- Keine Route im Dark mit Textelement unter 4,5:1 (Ausnahme ink-4 nur Placeholder/Disabled), keine weißen Karten auf dunklem Grund, kein Hell-Blitz.
- Hellmodus optisch unverändert bis auf Akzentflächen; bestehende Kontrasttests und Golden-Dateien konsistent.
- Ratsche scharf, Ausnahmeliste leer bis auf gewollte Festfarben.
- Doku (`design_system.md`, `TOKENS.md`) nachgezogen.
- Alle 6 CI-Checks grün, Deploy und Selftest ohne Befund; Issue #2400 und Folgeticket-Hinweise geschlossen bzw. verlinkt.

## Risks

- **Blast Radius hoch:** Jede Seite verändert sich im Dark optisch. Mitigation: zentrale Token-Lösung, Ganzseiten-Messlauf als Gate, Screenshots je Route, Hellmodus-Regression durch Bestandstests.
- **Versteckte harte Farben** (Inline-Styles, SVG-Fills, Tailwind-Paletten): Ratsche und Verstoßliste aus dem Messlauf, Schritt 3 der Reihenfolge.
- **Regex-Tests lesen den falschen Treffer:** Dark-Block steht hinter `:root`; Kern-Test sichert die Reihenfolge ab.
- **Inline-Skript und spätere CSP:** heute keine CSP; bei Einführung `kit.csp` mit Hash/Nonce.
- **Service-Worker-Cache** liefert alte `offline.html`: Cache-Version/Precache beim Anpassen prüfen (AC-10 misst die ausgelieferte Seite auf Staging).
- **Zwei Wahrheiten für Werte** (`app.css` und `offline.html`): Konsistenztest in AC-10.
- **Hell-Änderung Akzentfläche:** Flächen werden dunkler (`#c45a2a` → `#8c3e1a`), sichtbar im Hellmodus (Buttons, Avatar). Bewusst nach ADR-0008 und Leitprinzip; Button und Avatar sind bereits dort (#2879, #2896).
- **Leaflet bleibt hell:** heller Block auf dunkler Seite, bewusst hingenommen (externe Kacheln).

## Known Limitations

- `--g-accent-text` hell = `--g-accent` (`#c45a2a`) entspricht dem Ist-Zustand und liegt als Text auf Papier unter 4,5:1 (4,34:1 auf `--g-paper-deep`). Das ist der Altbefund der Markenfarbe, bereits in #2896 als eigene Markenentscheidung ausgeklammert; eine Anhebung ist ein eigenes Ticket. Im Dunkelmodus gilt `#e07a4a` mit ≥ 4,84:1.
- Mails und Telegram-/SMS-Text haben kein Dark; die Mail-Darstellung im Postfach des Empfängers steuert der Mail-Client.
- Ohne gespeicherte Wahl startet die App immer hell, auch wenn das Betriebssystem dunkel ist (PO-Entscheidung offen gelassen; nicht verlangt).
- Der Staging-Messlauf braucht eine eingeloggte Staging-Sitzung (Staging-`.env`); lokaler Nachweis ersetzt ihn nicht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (Anwendung von ADR-0008 „Kontrast vor Optik" und Design-Leitprinzip). Mechanik-Entscheidung (Attribut + CSS-Block statt TS-Map) ist implementierungsnah und in dieser Spec begründet. Tech-Lead-Entscheidung 2026-11-09: kein eigenes ADR; die Mechanik (Variante A, `:root[data-theme="dark"]`, eine SSOT in CSS) wird in `docs/reference/design_system.md` dokumentiert.
- **Rationale Variante A gegen B (`darkVars` um `--g-*` erweitern):** A hält die Werte neben den hellen Tokens in einer Quelle (B: ca. 60 TS-Einträge mit Drift zu `app.css`), behebt den Hell-Blitz (Attribut vor erstem Paint), setzt `theme-color`/`color-scheme` früh, bindet `dark:`-Varianten an den Schalter und ist per Regex unit-testbar.

## Changelog

- 2026-11-09: Initial spec created (Issue #2400, Epic #2508; PO-Entscheidung „Ganz fertig bauen"; Analyse in `docs/context/fix-2400-darkmode-ink3.md`).
- 2026-11-09: Abweichung von der Analyse bewusst und zur Prüfung markiert: Akzentflächen mit Text gehen auf das bereits vorhandene `--g-accent-deep` (`#8c3e1a`, 7,45:1, Muster #2879/#2896) statt auf einen neuen Wert `#b5521f` (5,01:1); Begründung siehe Abschnitt „Entscheidung Akzentfläche".
- 2026-11-09 (TDD RED): Werte-Abgleich `offline.html` ↔ Dark-Block steht in eigener Datei `frontend/src/lib/__tests__/offline_dark_konsistenz.test.ts` (Kennzeichnung `doc-compliance-test` nur dort, nicht auf dem Paletten-Test). Skript-Logik von `offline.html` prüft `dark_mechanik.test.ts` mit. AC-8 wird im Kern zusätzlich mit dem echten Tailwind-Compiler geprüft (`dark:`-Selektor hängt an `data-theme`). `PremiumSmsLinkCard.svelte` (`text-red-600`, Fehlertext) gehört in den Ratschen-Scope (Statusfarbe auf Token). Staging-Config: `frontend/e2e/playwright.dark-mode.staging.config.ts`.
- 2026-11-09 (Validierung): Dark-Akzentwerte final `--g-accent-deep` `#e07a4a` und `--g-on-accent` `#141412` (6,19:1; hell unverändert `#8c3e1a` mit Weiß 7,45:1), weil `--g-accent-deep` auch Textfarbe auf dunklem Grund ist; AC-7 bleibt erfüllt. `--g-ink-faint` dunkel `#7a776d`. Ausnahmeliste der Ratsche um `atoms/Switch.svelte` und `mobile/MSwitch.svelte` (je 1, weißer Knopf) als in Scope erlaubte Festfarbe ergänzt (Fix-Loop F002). Neue Datei `frontend/src/lib/darkMode.ts` als Ort der Umschalt-Mechanik. Staging-Spec `dark-mode-alle-routen.staging.spec.ts` um AC-9, AC-13, AC-14 erweitert; `LocationPreviewMap` ist in keiner Route eingebunden, daher wird der Ortsvergleichsteil von AC-14 auf Staging ggf. übersprungen, der Kern-Test `karten_dark` deckt sie ab.
- 2026-11-10 (Staging-Messlauf): Auslegung AC-3 festgehalten: „Karte oder Fläche" meint Container (Karten, Panels, Blätter, Dialoge, Listenzeilen), nicht Bedienelemente. Invertiert gefüllte Bedienelemente (Primärknopf, Link-Knopf, aktiver Sprachknopf; `button`, `a`, `input`, `select`, `textarea`, Steuerelement-Label, ARIA-Rollen `button`/`switch`/`tab` u. ä., höchstens 64 px hoch) sind gewollt (hoher Kontrast, Leitprinzip) und zählen nicht als helle Fläche; ihr Text wird weiter gegen 4,5:1 gemessen. Höhere klickbare Kacheln und alle Vorfahren-Container bleiben in der Flächenprüfung. Messskript zusätzlich: Schalter-Startzustand nur beim ersten Laden gesetzt (Neuladen prüft echte Persistenz), Desktop-Schalter über das Benutzermenü der Seitenleiste, Testdaten (ein Trip, zwei Orte, ein Ortsvergleich mit Präfix `E2E-GZ-2400`) legt die Spec selbst an und löscht nur diese wieder.
- 2026-11-10 (Staging-Messlauf, Befund): Aktiver Eintrag der Desktop-Seitenleiste lag im Dunkelmodus bei 4,38:1 (hart kodierte Hell-Tönung `rgba(196,90,42,0.10)` im Inline-Style). Neue Tokens `--g-sidebar-active-bg`/`--g-sidebar-active-fg` (hell unverändert, 5,48:1; dunkel `rgba(224,122,74,0.12)` + `#ec9468`, 5,19:1), Kern-Test `sidebar_aktiv_kontrast.test.ts`. Ratsche `harte_farben_waechter` zählt jetzt auch Hell-Akzent-rgba (`rgba(196,90,42,…)`), Bestand als Ausnahmen mit Begründung. AC-14 (Trip) misst die Karte im Reiter Etappen.
- 2026-11-10 (Staging-Messlauf 2): Speicheranzeige „Gespeichert" (Trip-Seite, dunkel) lag bei 2,9:1 — das Idle-Abblenden aus #880 (`opacity: 0.5` nach 3 s) ließ `--g-good` unter die Grenze fallen, hell ebenso. Entscheidung (Tech Lead): Das PO-bestätigte Leitprinzip „Hoher Kontrast = Lesbarkeit" (`docs/reference/design_system.md`, WCAG-AA) hat Vorrang vor der 50-%-Abblendung aus #880. Der Ruhezustand tritt weiter zurück, aber ohne Deckkraftverlust: Tönung fällt weg (transparent), Schrift wechselt auf `--g-ink-3`, Deckkraft bleibt 1; nie `display:none`/`visibility:hidden` (#880). Endbild auf Seite/Karte/`--g-surface-2`: hell 5,13/5,65/4,66:1, dunkel 7,57/6,94/5,92:1. Zustandsflächen auf Status-Paare statt Hell-rgba: gespeichert `--g-ok-bg`/`--g-ok-fg` (6,81/6,90:1), ungespeichert `--g-warn-bg`/`--g-warn-fg` (6,84/7,27:1), Fehler/Konflikt `--g-danger-bg`/`--g-danger-fg` (7,60/6,02:1); Zeitstempel ohne Zusatz-`opacity`. Kern-Test `speicheranzeige_ruhe_kontrast.test.ts`; `e2e/feat-880-autosave-overlay.spec.ts` AC-3 sichert Zurücktreten bei Deckkraft 1.
