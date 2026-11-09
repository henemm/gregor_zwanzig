# Context: feature-2371-ink4-kontrast

## Request Summary
Issue #2371 (Epic #2508, Strang B): `--g-ink-4` (#9a958a, 2,71:1 auf Papier / 2,85:1 auf Weiß) trägt Feld-Labels, Fortschritt, Hilfetexte, deaktivierte Aktionen und gesperrte Tabs in den Anlege-Editoren und im Archiv. Soll: lesbare Tokens (`--g-ink-3`, 5,0:1), gesperrte Tabs ohne Zusatz-Opacity, plus ein Wächter-Test, der `color: var(--g-ink-4)` außerhalb Placeholder/Disabled rot meldet.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/app.css:205-206` | Token-Definition `--g-ink-3 #6b675c`, `--g-ink-4 #9a958a` (Hell; Dunkel ist #2400, nicht Teil hier) |
| `components/trip-new/TripNewEditor.svelte` | 22 Fundstellen (Eyebrow, Hilfetext, Stage-Köpfe, Speichern deaktiviert, gesperrte Tabs mit Opacity) |
| `components/compare-new/CompareNewEditor.svelte` | 10 Fundstellen (Feld-Labels, Fortschritt, gesperrte Tabs) |
| `components/compare/steps/Step2Orte.svelte` | 11 (Orte-Organismus im Anlegen) |
| `components/shared/anlege-rahmen/AnlegeRahmen.svelte:150`, `AnlegeFortschritt.svelte:56` | geteilter Anlege-Rahmen, Fortschritt „0/6" |
| `components/shared/corridor-editor/CorridorEditor(.Mobile).svelte` | 10 + 12 |
| `routes/archiv/+page.svelte` | 3 (Fußzeile „0 von 0 Einträgen") |
| weitere (Liste per Grep) | `compare/LocationNewModal` 7, `hub-uebersicht/HubUebersicht` 4, `WeatherV2Reihenfolge` 4, Listen/Karten-Organismen je 1–3 |
| `components/organisms/PresetRail.svelte:102` | trägt bereits Marker `audit:exempt: --g-ink-4` (Vorbild für Ausnahmeliste) |
| `routes/_design/+page.svelte:29` | Design-Seite zeigt Ratio 2,98 statt 2,85 (Anschlussthema #1831/#2508) |

## Existing Patterns
- Kontrast-Fixes per Ticket schon gemacht: AppFooter, VTBriefingChannels, WeatherV2Reihenfolge, DetailRow (Kommentare „nicht --g-ink-4"); Muster = `--g-ink-3` oder `--g-ink-muted`.
- Kontrast-Tests als Kern-Test: `shared/__tests__/app_footer_kontrast_und_tippflaeche.test.ts`, `molecules/begriff_erklaerung_kontrast_und_tippflaeche.test.ts`, `_home/__tests__/onboarding_kontrast_und_katalogtreue.test.ts`. Frontend-Tests laufen über `node --test`.
- `scripts/contrast_audit.py` (Issue #377) liefert `contrast_ratio()`; Test `tests/tdd/test_issue_377_contrast_audit.py`.
- Ratschen-Muster mit Ausnahmeliste für Bestand: `docs/reference/gates_und_ratschen.md` (z. B. i18n-Ratschen `i18n_s4_ratsche_frontend_2649`).
- Inline-Marker `audit:exempt:` existiert bereits an einer Stelle.

## Dependencies
- Upstream: Design-Tokens in `app.css`; ADR-0008 „Kontrast vor Optik" (`--g-ink-4` nur Placeholder/Disabled); `docs/reference/design_system.md:25`.
- Downstream: Golden-HTML-Fixtures unter `tests/golden/f3_home_listen/*`, `f10_vergleich_flaechen/*` und `frontend/src/routes/__tests__/fixtures/auth/*.html` enthalten `ink-4` — Farbänderungen können Golden-Vergleiche rot machen (Fixtures nachziehen). Test `routes/compare/__tests__/issue_582_compare_design_fidelity.test.ts` und `molecules/issue_578_molecules_organisms.test.ts` erwähnen `ink-4` (prüfen, ob sie die alte Farbe festschreiben). E2E `kuerzel-legende-lesbar.staging.spec.ts`.

## Existing Specs
- Noch keine Spec für #2371. Verwandt: `docs/specs/modules/issue_377_contrast_audit.md`, `docs/adr/0008-kontrast-vor-optik.md`.

## Risks & Considerations
- Umfang: 84 Fundstellen in ~45 Dateien; Issue nennt konkret nur Anlege-Editoren + Archiv (AC-1 gilt für `/compare/new`, `/trips/new`, `/archiv`). Wächter (AC-4) trifft aber ganz `frontend/src` → Bestand außerhalb dieser Seiten braucht Ausnahmeliste („Ratsche", Abbau im Epic #368/#2508).
- Gesperrte Tabs: Opacity 0.34/0.35 muss weg, Sperre über Schloss-Marker; Layout/Optik-Test mit Fresh-Eyes.
- Deaktivierter Speichern-Button: `--g-ink-3` + `aria-disabled="true"` (heute vermutlich nur `disabled`) — Verhalten/Klickbarkeit darf sich nicht ändern.
- Trip/Ortsvergleich-Parität: Änderungen an `TripNewEditor` und `CompareNewEditor` müssen gleich ausfallen (Pendant-Sperre); geteilter `AnlegeRahmen` zuerst.
- Golden-Fixtures und Tests, die die alte Farbe festschreiben, müssen mit angepasst werden.
- Nicht Teil: Dark-Mode-Wert von `--g-ink-3` (#2400), Danger-Rot (#1831).

## Analysis

### Type
Bug (Kontrast, Leitprinzip „Hoher Kontrast = Lesbarkeit", ADR-0008). Gegen den Code nachgeprüft: 90 Vorkommen `color: var(--g-ink-4)` in 27 Svelte-Dateien (ohne Placeholder); alle im Issue genannten Fundstellen bestätigt.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `shared/anlege-rahmen/AnlegeFortschritt.svelte`, `AnlegeRahmen.svelte` | MODIFY | Fortschritt „0/6", Rahmen-Hilfetext → `--g-ink-3` (zuerst: geteilt) |
| `trip-new/TripNewEditor.svelte` | MODIFY | Eyebrow, Hilfetexte, Stage-Köpfe, Hinweise, gesperrte Tabs (Opacity 0.34/0.35 raus, ⊘ bleibt, Text `--g-ink-3`), Speichern deaktiviert (≥4,5:1 + `aria-disabled="true"`) |
| `compare-new/CompareNewEditor.svelte` | MODIFY | Feld-Labels, Gruppen-Überschriften, Hinweise, gesperrte Tabs wie oben (Parität zum Trip-Editor) |
| `routes/archiv/+page.svelte` | MODIFY | Fußzeile Zeile 198 → `--g-ink-3` |
| `compare/steps/Step2Orte.svelte`, `corridor-editor/*` u. a. im Anlege-Pfad | MODIFY | Fundstellen, die auf `/compare/new` und `/trips/new` sichtbar sind (AC-1) |
| Wächter-Test `ink4_waechter` (neu, `node --test`) | CREATE | AC-4: scannt `frontend/src`, meldet `color: var(--g-ink-4)` außerhalb Placeholder/Disabled/`audit:exempt`; Bestand außerhalb des Scopes in Ausnahmeliste (Ratsche: darf nur schrumpfen) |
| Kontrast-Messtest (Playwright, Alpha-Blending, Logik wie `contrast_audit.contrast_ratio`) | CREATE | AC-1/2/3 auf 390×844 gegen Staging |
| Golden-Fixtures / `issue_582`, `issue_578`-Tests mit `ink-4` | MODIFY | nur wenn sie betroffene Stellen festschreiben |

### Scope Assessment
- Files: ca. 8–12 produktiv + 2 Tests (Rest des Bestands in Ausnahmeliste)
- Estimated LoC: +150/-60 (überwiegend Einzeilen-Ersetzungen; Wächter ~80)
- Risk Level: MEDIUM — viele Inline-Styles, Trip/Vergleich-Parität (Gate), Golden-Fixtures; keine Logik- oder Datenänderung.

### Technical Approach
1. Wächter zuerst (rot): Ausnahmeliste = heutige Bestandsdateien außerhalb des Scopes; Scope-Dateien (Anlege-Editoren, Anlege-Rahmen, Archiv) müssen sauber sein.
2. Geteilte Teile zuerst (`AnlegeRahmen`/`AnlegeFortschritt`), dann Trip- und Compare-Editor in identischer Form (Pendant-Sperre).
3. Gesperrte Tabs: `--g-ink-3` ohne Opacity; „gesperrt" bleibt über ⊘, `cursor:not-allowed` und fehlendes Gewicht erkennbar, nicht über Kontrast.
4. Speichern-Button deaktiviert (heute Hintergrund `--g-ink-4` + Opacity 0.45, Zeile 822 bzw. Kopfaktion): Text ≥4,5:1, `aria-disabled="true"`, Klickverhalten unverändert.
5. Nur Text ändern; rein dekorative Symbole (SVG-Strokes) als `audit:exempt` markieren; ×-Buttons tragen Aktion → `--g-ink-3`.
6. Kontrast-Messtest als Playwright-Staging-Test; Wächter als `node --test`.

### Dependencies
- Tokens in `app.css:205-206` unverändert (Dark-Mode #2400, Danger-Rot #1831 nicht Teil).
- Golden-Fixtures und `issue_582/578`-Tests prüfen; `routes/_design/+page.svelte` (Ratio 2,98 statt 2,85) nicht Teil (Anschluss #1831/#2508).

### Open Questions
- [x] Ausnahmeliste auf Datei-Ebene mit Zähler je Datei, darf nur sinken (Tech-Entscheidung).
- [x] Dekorative Symbole: `audit:exempt` statt ändern (Tech-Entscheidung).
