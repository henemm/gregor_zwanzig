# Context: rework-3375-wsw-browserpruefungen

## Request Summary
Issue #3375 (Epic #3122, aus #3164): Zwei Zusicherungen der Karte „Was steht wo“ bekommen wieder Browser-Fälle gegen den echten Server:
(a) Telegram-Spalte zeigt beim Trip ab der 8. Metrik „nur Tageswert“ (früher kanal-grenzen AC-3);
(b) Kürzel-Marken der Karte werden bei keiner Breite 320–1440 px abgeschnitten (früher kuerzel-marken AC-10..13, 14 Auflösungen).

## Related Files
| File | Relevance |
|------|-----------|
| frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte | Karte (`data-testid="was-steht-wo"`, Tabelle `was-steht-wo-tabelle`, Legende `was-steht-wo-legende`) |
| frontend/src/lib/components/molecules/EinstellTabelle.svelte:134 | Marke `em.et-marke[data-slot="et-marke"][data-ton]`; Zeilen `[data-slot="et-zeile"][data-metrik]`, Zellen `[data-slot="et-zelle"][data-stelle]` |
| frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts:43 | `nur_tageswert` → Text `wetter.wsw.marke.nur_tageswert`, Ton `leise` |
| src/services/placements_view_service.py:613 | `_trip_nur_tageswert` (Server berechnet `mark`) |
| src/output/renderers/channel_layout.py:50 | Telegram `max_table_cols: 8` inkl. Zeitspalte ⇒ 7 Metriken stündlich, ab 8. nur Tageswert; Wind-Richtung + VISIBILITY_GATE_IDS ausgenommen; nur Trips |
| frontend/e2e/was-steht-wo.helpers.ts | `seedAbo`, `oeffneKarte`, `zeile`, `zelle`, `tabelle`, `aufraeumen` |
| frontend/e2e/kanal-grenzen-und-hinweise.staging.spec.ts | Vorbild; Kopfkommentar „AC-3 gestrichen“ |
| frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts (+ .staging.setup.ts, playwright.*.staging.config.ts) | Vorbild; AC-10..13 gestrichen in f62019a64 (#3154) |
| frontend/e2e/was-steht-wo-karte.spec.ts:689 | WS-8: nur 390 px, Spaltenköpfe, keine Marken gemessen |
| frontend/e2e/kuerzel-legende-lesbar.staging.spec.ts:51 | Legende 320/390/600/899 |
| frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts:254–264 | Render-Test „neun Zeilen: Marke ab der achten“ (9 Metrik-IDs, letzte `uv_index`, `sunshine`) |

## Existing Patterns
- Staging-Spec: eigene Playwright-Config je Datei, Setup per `POST /api/auth/login` (Rate-Limit #703), storageState.
- Lokal: `npx playwright test --project=tests e2e/<datei>.staging.spec.ts` gegen ci-stack (Preview 4173, API 8091).
- Seed per API, Aufräumen im afterEach.
- Abschneiden messen (alte Fassung `git show f62019a64^:frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts`, Z. 54–69, 225–260): Ausdehnung > 0, `scrollWidth > clientWidth + 1` = beschnitten, Marke innerhalb Zeilen-Rect, Sichtfenster, Seiten-`scrollWidth <= innerWidth`.

## Dependencies
- Upstream: Server-Endpoint Placements-Tabelle (liefert `mark`), Seed-API Trip mit `display_config.metrics`.
- Downstream: keine (reine Testergänzung).

## Existing Specs
- docs/specs/modules/feat_3122_was_steht_wo.md (Karten-Spec)
- docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md AC-3 (Z. 220)
- docs/specs/modules/fix_1719_s4_kuerzel_vereinheitlichung.md AC-10..13 (Z. 308–328)
- docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md Z. 74, 180 (#3375 offen)

## Risks & Considerations
- Kein Produktcode-Änderung geplant; falls ein Fall rot wird, ist das ein echter Fund (Bug), kein Test-Anpassungsgrund.
- Mutations-Gegenprobe: Grenze in channel_layout.py (8→9) muss Fall (a) rot machen; CSS der Marke (z. B. `white-space`/`overflow`) muss Fall (b) rot machen.
- Testdauer: 14 Breiten × Trip+Vergleich; ein Seed, Viewport-Wechsel statt neuer Seiten.
- Doku-Kopfkommentare „gestrichen“ in beiden Altdateien aktualisieren; Rückverweis in rework_3020-Spec.

## Analysis

### Type
Feature (Testlücke schließen, kein Produktcode)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/e2e/kanal-grenzen-und-hinweise.staging.spec.ts | MODIFY | neuer Fall: Trip mit 9 Metriken (`temperature, gust, wind, precipitation, rain_probability, cloud_cover, humidity, uv_index, sunshine`), Telegram-Zelle zeigt „nur Tageswert“ genau in Zeilen 8 und 9, sichtbar im Browser; Gegenfall 7 Metriken ohne Marke; Kopfkommentar „AC-3 gestrichen“ ersetzen |
| frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts | MODIFY | neue Fälle: Marken `[data-slot="et-marke"]` der Karte (Trip mit 9 Metriken: „nur Tageswert“ + „passt nicht mehr“; Vergleich mit 3 Orten) über 14 Auflösungen 320–1920 nicht beschnitten (Ausdehnung>0, scrollWidth≤clientWidth+1, im Zeilen- und Sichtfenster-Rechteck, Seite ohne seitlichen Überlauf); Kopfkommentar anpassen |
| docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md | MODIFY | Verweis „Browser-Fall folgt mit #3375“ → erledigt |

### Scope Assessment
- Files: 3 (+ neue Spec)
- Estimated LoC: +~170/-~10
- Risk Level: LOW (nur Tests und Doku)

### Technical Approach
Helfer aus `was-steht-wo.helpers.ts` (`seedAbo`, `oeffneKarte`, `zelle`, `tabelle`) wiederverwenden. Ein Seed je Abo, Viewport-Schleife in einem Test (Breitenwechsel ohne Neuseed, Warten bis Layout steht). Messfunktion aus der alten Fassung (Commit f62019a64^, Z. 225–260) auf neue Selektoren umstellen. Telegram-Fall prüft sowohl die API-Marke (`mark: nur_tageswert`) als auch den sichtbaren Text in der Zelle — die Zusicherung wirkt im Browser. Mutations-Gegenproben: `max_table_cols` Telegram 8→9 (Fall a rot), `.et-marke` mit `white-space: nowrap; overflow:hidden; max-width:2ch` (Fall b rot).

### Dependencies
ci-stack lokal bzw. Staging; Seed-API; Login-Setup der Staging-Configs.

### Befunde aus Phase 5 (Testdaten weichen von der Spec-Annahme ab, ACs unverändert)
1. `cloud_cover` gibt es im Katalog nicht (richtig `cloud_total`); der Server verwirft unbekannte IDs still. Ohne gespeicherte Tabelle ordnet der Server nach Katalog statt Seed-Folge — der Seed legt daher `display_config.placements` in Seed-Folge an, dann tragen uv_index/sunshine die Marke (AC-1 wörtlich).
2. Trip mit 9 Metriken hat kein „passt nicht mehr“ (SMS 92/160) — Marken-Trip nutzt 18 Metriken (158 Zeichen), beide Marken vorhanden.
3. Vergleich mit 4 Standardmetriken hat keine Marke — Fall nutzt 15 Metriken (Zweig „passt nicht mehr“).
4. Mutation b (Abschneide-CSS) trifft nur ≥1280 px, weil das enge Raster (<1200) `max-width`/`white-space` überschreibt — „mindestens eine Auflösung rot“ erfüllt.
5. Lokaler Lauf: Stack auf freien Ports (Go 8191, Py 8101), `GZ_REPO_ENV_FILE` auf nicht vorhandene Datei, `GZ_API_BASE`/`GZ_E2E_API_PROXY_TARGET=http://localhost:8191`.

### Open Questions
- keine (Produktverhalten ist durch ADR-0124 Nr. 3 und feat_3122 festgelegt)
