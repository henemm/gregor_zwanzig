# External Validator Report

**Spec:** docs/specs/modules/epic_133_design_system_lauf_b.md
**Datum:** 2026-05-09T05:10Z
**Server:** http://localhost:4173 (Production-Build, Preview)
**Auth:** gz_session=admin.* (Cookie vom Launcher)

## Methodik

- HTML der Route `/_design` per `curl` mit Session-Cookie geladen
- Geliefertes CSS-Bundle (`/_app/immutable/assets/0.n_AAwG4V.css`) auf Selektoren und Custom Properties geprüft
- Playwright (Chromium, 1280×1024) auf `/_design` und `/`: Computed Styles via `getComputedStyle`, Polyline-Attribute via DOM, Sidebar-Hrefs via `nav a`-Scan, Console- und Page-Errors abgefangen
- Vollseiten- und Section-Screenshots in `validator-screenshots/`
- Computed-Style-/DOM-Daten in `validator-screenshots/data.json`

## Checklist

| # | Akzeptanzkriterium | Beweis | Verdict |
|---|---|---|---|
| 1 | `.g-topo`-Klasse: `background-image` (radial-gradient) + `background-size` | CSS-Bundle: `.g-topo` vorhanden; computed `backgroundImage = radial-gradient(...) , radial-gradient(...)`, `backgroundSize = "60px 60px, 60px 60px"` (data.json:topoBg) | PASS |
| 2 | `<TopoBg>` rendert `data-slot="topo-bg"` mit `--g-topo-opacity` als Custom Property | HTML: `<div data-slot="topo-bg" class="g-topo …" style="--g-topo-opacity: 0.06;">`; computed `opacity=0.06`, `pointerEvents=none`, `position=absolute` | PASS |
| 3 | `<Btn variant="accent">Speichern</Btn>` mit `data-slot="btn"`, `data-variant="accent"`, sichtbarem Text | HTML: `<button data-slot="btn" data-variant="accent" data-size="md">Speichern</button>`; computed `backgroundColor=rgb(196,90,42)` (`--g-accent`), `color=rgb(246,244,238)` (`--g-paper`), `borderRadius=8px` (`--g-radius-md`), `fontFamily="Inter Tight"` (`--g-font-ui`); 01-full-page.png zeigt orangefarbenen Button | PASS |
| 4 | `<Pill tone="success">OK</Pill>` mit `data-slot="pill"`, `data-tone="success"` | HTML: `<span data-slot="pill" data-tone="success">OK</span>`; computed `backgroundColor=rgb(58,125,68)` (`--g-success`), `color=rgb(255,255,255)` | PASS |
| 5 | `<Eyebrow>…</Eyebrow>` mit `data-slot="eyebrow"` und JetBrains-Mono | HTML: `<span data-slot="eyebrow">Wetter-Design-System</span>`; computed `fontFamily="JetBrains Mono", ui-monospace, monospace`; Screenshot zeigt UPPERCASE-Letter-Spacing | PASS |
| 6 | `<Dot tone="rain" />` mit `data-slot="dot"`, `data-tone="rain"` | HTML: `<span data-slot="dot" data-tone="rain" data-size="md">`; computed `backgroundColor=rgb(74,127,181)`, `width=10px`, `height=10px`, `borderRadius=50%` | PASS |
| 7 | `<GCard>` mit `data-slot="g-card"` | HTML: `<div data-slot="g-card">`; computed `backgroundColor=rgb(237,234,225)` (`--g-surface-1`), `borderRadius=12px` (`--g-radius-lg`), `boxShadow=rgba(26,26,24,0.08) 0px 1px 3px 0px` (`--g-elev-1`) | PASS |
| 8 | `<ElevSparkline data={[800,1200,950,1500,1100]}>` rendert `<polyline>` mit 5 Punkten | DOM: `polyline.points="0,38 50,17.428… 100,30.285… 150,2 200,22.571…"` → exakt 5 Koordinaten-Paare, alle endlich (kein NaN); SVG sichtbar (200×40) | PASS |
| 9 | `<ElevSparkline data={[]}>` rendert SVG ohne `<polyline>` — kein Crash | DOM: SVG sichtbar (120×24), `polyline=null` (Element nicht im DOM); keine Console- oder Page-Errors | PASS |
| 10 | `<ElevSparkline data={[1500]}>` rendert ohne Crash, kein NaN | DOM: SVG sichtbar (120×24), `polyline.points="0,12"` (y = height/2 = 12, kein NaN); keine Page-Errors | PASS |
| 11 | `/_design` antwortet mit HTTP 200 nach Login + Heading sichtbar | `curl` mit Cookie → HTTP 200; HTML enthält `<h1 data-testid="design-showcase-title">Design-System Showcase</h1>`; Screenshot bestätigt | PASS |
| 12 | `/_design` ist nicht in der Sidebar verlinkt | `nav a` href-Scan auf `/`: `["/", "/trips", "/compare"]` — kein `/_design`-Eintrag; visuell im Sidebar-Screenshot ebenfalls nicht vorhanden | PASS |

## Zusatzprüfungen (über Akzeptanzkriterien hinaus)

- **Browser-Errors:** keine `pageerror`, keine `console.error` während Page-Load
- **CSS-Selektoren komplett:** Alle 6 Pill-Tones (`default`, `success`, `warning`, `danger`, `info`, `accent`), alle 10 Dot-Tones (6 Wetter + 4 semantisch), alle 3 Btn-Varianten (`accent`, `ghost`, `outline`), alle 3 Btn-Größen (`sm`, `md`, `lg`), alle 3 Dot-Größen (`xs`, `sm`, `md`) im gelieferten CSS-Bundle vorhanden
- **Token-Auflösung:** Alle referenzierten Custom Properties (`--g-accent`, `--g-ink`, `--g-paper`, `--g-radius-md/lg/pill`, `--g-font-ui/data`, `--g-elev-1/2`, `--g-success`, `--g-wx-rain` etc.) werden zu konkreten Werten aufgelöst (Lauf-A-Fundament intakt)
- **TopoBg-Hover-Sicherheit:** `pointer-events: none` korrekt gesetzt — Pattern fängt keine Klicks ab
- **Sparkline Edge-Cases:** sowohl leeres Array als auch Single-Point werden ohne Exception gerendert (Spec-konformer Fallback `y = height / 2`)

## Findings

Keine Findings. Alle 12 Akzeptanzkriterien bestehen mit konkreter Evidenz (Screenshot, Computed Style, DOM-Attribut, oder HTTP-Response).

## Verdict: VERIFIED

### Begründung

Jedes der 12 Akzeptanzkriterien aus der Spec ist durch direkten DOM-/Computed-Style-Beweis oder Screenshot belegt. Die in der Spec definierten `data-slot`/`data-variant`/`data-tone`-Selektoren sind sowohl im HTML als auch im ausgelieferten CSS-Bundle vorhanden und lösen sich zu den korrekten Token-Werten auf (Akzent-Orange für Btn, Grün für Pill-Success, Blau für Dot-Rain, Inter-Tight für UI-Schrift, JetBrains-Mono für Eyebrow). Die Sparkline rendert für Normalfall, leeres Array und Single-Point ohne Exception oder NaN-Werte. `/_design` ist eingeloggt erreichbar (HTTP 200), in der Sidebar bewusst nicht verlinkt. Keine Browser-Errors während des Tests.

## Evidence Files

- `validator-screenshots/01-full-page.png` — Vollseite `/_design`
- `validator-screenshots/section-atoms-section.png` — Btn/Pill/Dot/GCard
- `validator-screenshots/section-topo-section.png` — TopoBg-Pattern
- `validator-screenshots/section-sparkline-section.png` — ElevSparkline (5-Punkt + Edge-Cases)
- `validator-screenshots/data.json` — Computed-Style-/DOM-Rohdaten
