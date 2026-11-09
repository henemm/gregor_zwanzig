# Adversary-Dialog #2879 (fix-2879-kontrast)

Basis: Branch claude/vigilant-babbage-ebij4r, HEAD ddac688a2. Baseline `kontrast-trip-vergleich.spec.ts`: 12 passed (1 Setup + KO-1..KO-6), siehe adversary-test-output.txt.

## Runde 1: Basislauf und Spec-Pflichtmutationen
- (a) app.css Accent-Knopf auf --g-accent (P1): rot KO-1 de/en, KO-3 Desktop de/en, KO-5.
- (b) ListNameCell-Status ink-4 (P2): rot KO-1 de/en, KO-4.
- (c) Aktiver Handy-Reiter --g-accent (P3): rot KO-2 de/en.
- (d) Helfer ohne Mischung transparenter Schichten (P4): rot KO-6 (+KO-1/KO-3 durch Fehlalarme). KO-2 bleibt gruen (K2 wird nur durch den Selbsttest KO-6 bewacht, wie die Spec es vorsieht).

## Runde 2: Wirkungsort-Mutationen (Produkt und Helfer)
Siehe Tabelle im Abschlussbericht. Ergebnisse (Run-Logs im Scratchpad adv-out/):

| Mutation | Ergebnis |
|---|---|
| P5 EtappenStrip-Eyebrow ink-4 | gefangen KO-1, KO-3 |
| P6 StageCardM .meta ink-4 (nur Handy) | gefangen KO-2, KO-3 mobil |
| P7 Rangnummer Accent (Orte-Reiter) | gefangen KO-1, KO-2 |
| P8 Hover-Fläche hell | gefangen KO-5 |
| P9 Helfer ohne Opacity-Kette | NICHT GEFANGEN |
| P10 Helfer Grossschwelle 24 -> 20 px | NICHT GEFANGEN |
| P11 Helfer 18,66/700 -> 14/600 | NICHT GEFANGEN |
| P12 Helfer SVG fill -> color | NICHT GEFANGEN |
| P13 Status aria-hidden + ink-4 | gefangen NUR durch KO-4 (statusspezifisch, nicht exemptionsbewusst) |
| P14 ink-4 nur im :hover | NICHT GEFANGEN (Hover/Focus nicht gemessen) |
| P15 Text ink auf background-image schwarz | NICHT GEFANGEN (Verlauf/Bild ignoriert) |
| P16 ::after ink-4 an Status | rot, aber nur zufaellig (Setup: Playwright findet Namen nicht); kein Kontrastbefund |
| P21 body::after Text ink-4 (Pseudoelement) | NICHT GEFANGEN |
| P19 Status + data-testid=brand-wordmark | gefangen nur KO-4 (statusspezifisch) |
| P22 EtappenStrip-Eyebrow aria-hidden + ink-4 | NICHT GEFANGEN (Ausnahme zu breit) |
| P23 EtappenStrip-Eyebrow brand-wordmark + ink-4 | NICHT GEFANGEN (Ausnahme zu breit) |
| P20 Eingabewerte (input color paper-deep) | NICHT GEFANGEN (Eingabewerte sind keine Textknoten) |
| P18 [aria-hidden="true"] -> [aria-hidden] | aequivalent, nicht gefangen (unbedeutend) |

## Runde 3: Census der Ausnahmen auf echten Seiten (Probe, Scratchpad probe2879/out.txt)
- 94 ausgenommene Textknoten: 41 gesperrt, 25 aria-hidden, 28 logo.
- Gesperrt unter Schwelle: nur echte Disabled-Knoepfe (Weiter, Standardwerte): korrekt.
- aria-hidden unter Schwelle: Konto-Kreis-Avatar "AD" (weiss auf Accent, 4,34:1, 13px/600) auf JEDER Handy-Seite (bottom-shell > konto-kreis__avatar). Sichtbarer Text, durch aria-hidden-Ausnahme verdeckt. aria-hidden ist keine WCAG-Ausnahme fuer sichtbaren Text.
- logo-Ausnahme umfasst auch die Unterzeile "V0.20 · WETTER-BRIEFING" (5,7:1, haelt AA, wird aber nicht geprueft).
- Eingabewerte (Datum, Uhrzeit, Name) werden nie gemessen.

Git-Stand nach allen Mutationen: sauber (jede Mutation per diff gegen Sicherung identisch zurueckgenommen, Ausgabe "diff 0").

## Fix-Loop (Developer, Tech-Lead-Entscheidungen F001-F006)

Basis HEAD 53d5c8785. Geaendert: `frontend/e2e/helpers.ts` (Messhelfer), `frontend/e2e/kontrast-trip-vergleich.spec.ts` (KO-5 Hover, KO-6, Logo-Pruefung je Seite), `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` + `KontoSheet.svelte` (Avatar-Flaeche `--g-accent-deep`), `.github/workflows/ci.yml` (E2E_MIN_EXECUTED_HAUPT 661 -> 663), Spec Known Limitations „Messumfang" + Changelog.

- **F001** aria-hidden-Ausnahme nur noch fuer Text ohne Buchstabe/Ziffer (`/[\p{L}\p{N}]/u`). Realer Verstoss behoben: Konto-Initialen „AD" weiss auf `--g-accent` (4,34:1, 13px/600) in der Handy-Huelle -> `--g-accent-deep` (7,45:1); der Avatar im Konto-Blatt (gleiches Muster) mitgezogen. Census der echten Seiten nach der Verschaerfung: verbleibende aria-hidden-Ausnahmen nur der Pflicht-Stern „*" (6,03:1, haelt ohnehin AA).
- **F002** Logo-Ausnahme nur `.typo-row` innerhalb `[data-testid="brand-wordmark"]`; Unterzeile „V0.20 · WETTER-BRIEFING" wird jetzt gemessen (haelt AA). `pruefe()` sichert je Seite: Logo-Ausnahmen aus hoechstens einer Wortmarke (`logoInstanz`) und nur mit den Texten „gregor", „.", „zwanzig".
- **F003** Gemessen werden zusaetzlich `input`/`textarea`-Werte (nicht Platzhalter) und `::before`/`::after`-Inhalte mit Buchstaben/Ziffern; `background-image` vor dem ersten deckenden Grund = Verstoss „nicht berechenbar". Auf den geprueften Seiten kein solcher Fall (Census), daher keine Freigabeliste. Zusaetzlich: Farben in anderen Farbraeumen (`color-mix()` -> `oklab(...)`) werden ueber eine 1x1-Leinwand nach sRGB uebersetzt (vorher still als „kein Grund" uebergangen; im Hover der Accent-Knoepfe relevant).
- **F004** KO-6 erweitert: Opacity-Kette, SVG `fill` vs. `color`, 23/24 px, 18,65/18,66 px fett, Eingabewert, Platzhalter (nicht gemessen), gesperrter Eingabewert, `::after`-Text, Pseudo-Glyphe (nicht gemessen), Bild-Grund / ueberdeckter Bild-Grund, `color-mix`-Grund, aria-hidden Buchstaben (gemeldet) / Glyphen (Ausnahme), Logo-Schriftzug (Ausnahme) / Unterzeile (gemeldet) / fremde testid (gemeldet).
- **F005** Neue Faelle „KO-5 (1280 × 900)" und „KO-5 (390 × 844)": in jedem erreichten Anlege-Zustand (Trip: Route ohne/mit Namen, Etappen leer/mit GPX, Wegpunkte; Vergleich: ohne/mit Namen, Orte leer, Bibliothek, Orte gewaehlt) wird jeder sichtbare, nicht gesperrte und nicht verdeckte Accent-Knopf (`[data-slot="btn"][data-variant="accent"]`, MBtn `button[data-variant="accent"][data-size]`) ueberfahren und sein Text im Hover gemessen; leer-gruen ausgeschlossen (Computer >= 2 Bausteinknoepfe, Handy >= 1 MBtn).
- **F006** unveraendert.

### Mutationen (String-Ersetzung, Sicherung im Scratchpad bak-fl2879/, nach jedem Lauf per Dateivergleich identisch zurueck)

| Mutation | Ort | Ergebnis |
|---|---|---|
| P9 Opacity-Kette entfernt | helpers.ts | ROT KO-6 (`opazitaet-kette` fehlt) |
| P10 Grossschwelle 24 -> 20 px | helpers.ts | ROT KO-6 (`fast-gross`) |
| P11 18,66/700 -> 14/600 | helpers.ts | ROT KO-6 (`fett-fast-gross`) |
| P12 SVG fill -> color | helpers.ts | ROT KO-6 (`svg-fuellung-schwach`) |
| P20 Name-Eingabe Trip anlegen Schrift `--g-paper-deep` | TripNewEditor.svelte | ROT KO-3 1280 de (1,21:1 am input) |
| P21 `body::after` „Stand 2026" in `--g-ink-4` | app.css | ROT KO-1 1280 de (2,71:1 @ ::after, alle Seiten) |
| P22 Etappen-Eyebrow `aria-hidden` + `--g-ink-4` | EtappenStrip.svelte | ROT KO-1 1280 de (2,82:1) |
| P23 Etappen-Eyebrow `data-testid="brand-wordmark"` + `--g-ink-4` | EtappenStrip.svelte | ROT KO-1 1280 de (2,82:1) |
| P24 Konto-Initialen zurueck auf `--g-accent` | BottomNav.svelte | ROT KO-2 390 de („AD" 4,34:1) |
| H1 Hover „Wetter-Metriken →" (Vergleich, Orte gewaehlt) auf `--g-accent` | app.css | ROT KO-5 1280 (3,94:1) — der alte KO-5 (nur erster Weiter) haette das nicht gesehen |
| H2 Hover Accent-MBtn auf `--g-accent` | app.css | ROT KO-5 390 (4,34:1, vier Knoepfe) |
| P25 Farbraum-Uebersetzung (oklab) entfernt | helpers.ts | ROT KO-6 (`mischfarbe-grund`) |
| P26 Logo-Ausnahme wieder an jeder testid | helpers.ts | ROT KO-6 (`fremd-testid`, `logo-unterzeile`) |
| P27 aria-hidden wieder pauschal | helpers.ts | ROT KO-6 (`versteckt-buchstaben`) |
| P28 background-image-Pruefung entfernt | helpers.ts | ROT KO-6 (`bild-grund`) |
| P29 Eingabewerte nicht gemessen | helpers.ts | ROT KO-6 (`eingabe-schwach`) |
| P30 = P26 + P23 (breite Logo-Ausnahme UND fremde testid auf echter Seite) | helpers.ts + EtappenStrip | ROT KO-1 1280 de durch die Spec-Pruefung „Logo-Ausnahme an Text ausserhalb des Schriftzugs" (Unterzeile) — Schutz unabhaengig vom Helfer |

Erster Versuch H1 zielte auf „Wertebereiche festlegen →" (Trip) — dieser Knopf liegt im Reiter Wetter-Metriken, der laut Spec nicht geprueft wird; Mutation verworfen und auf einen Knopf eines geprueften Zustands umgelegt (kein Befund).

### Abschlusslauf
- `kontrast-trip-vergleich.spec.ts`: 14 passed (1 Setup + KO-1 x2, KO-2 x2, KO-3 x4, KO-4, KO-5, KO-5 Hover x2, KO-6), siehe fixloop-test-output.txt.
- `kuerzel-legende-lesbar.staging.spec.ts`: `--list` 7 Faelle, `tsc` (strict, e2e) ohne Fehler.
- `npm test` (frontend): 8183 Tests, 8177 pass, 0 fail, 6 skipped; keine Golden-Aenderung noetig (Avatar-Farbe steht im Komponenten-CSS, nicht im SSR-Markup der f9/f10-Pruefstaende).
- `svelte-check`: 27 Errors (Grenze 27).
- `uv run pytest tests/unit/test_hub_kopf_doku_2837.py tests/test_adr_index_drift.py`: gruen.
