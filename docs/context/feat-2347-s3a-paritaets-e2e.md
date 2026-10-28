# Context: feat-2347-s3a-paritaets-e2e

## Request Summary
Scheibe S3a von #2347 (Epic #2345, Etappe P6): Compare-only-Playwright-Specs zu Alarmen, Wertebereichen, Wetter-Metriken und Wertprops auf geteilte, `kind`-parametrisierte Specs (`HUB_KINDS`) heben. Reine Testschicht, kein Produktcode (außer bei echter Produktlücke, Muster AC-13 aus S2).

## Umfang laut Gesamtschnitt (`docs/specs/modules/feat_2347_s2_paritaets_e2e.md`, Z. 46)
8 Dateien in `frontend/e2e/`, alle in `.github/ci_e2e_specs.txt` (Z. 358-372) und in ALTLAST des Wächters (`tests/unit/test_e2e_compare_paritaet_waechter.py`, 41 Einträge, `ALTLAST_MAX = 41`, Prüfdatum 2027-01-24).

| Datei | Zeilen | Inhalt | Trip-Pendant |
|---|---|---|---|
| compare-alarme-speichert-selbst | 202 | Autosave Alarm-Reiter, genau 1 PUT, Reiterwechsel-Flush, Pausieren-Flush, #2375-Roundtrip | keins |
| compare-alarme-wertprops | 399 | 4 Fälle: amtl. Warnungen/Radar, Kanal/Telegram-Kurzstil, Empfindlichkeit/Cooldown/Stille Stunden, Nebenwirkungsfreiheit | keins |
| compare-wertebereiche-speichert-selbst | 358 | Metrik hinzufügen, Regler, Reiterwechsel, 412 + „Nochmal speichern", Pausieren, #2375-Roundtrip | keins |
| compare-wertebereiche-wertprops | 280 | Von-Grenze 1 PUT; Mobil-Band-Drag; AC-6 Trip (offene Grenze → Fehlerbanner) vs. AC-7 Vergleich (kein PUT) | Trip-Fall AC-6 schon enthalten, **bewusst verschieden** |
| compare-wetter-metriken-speichert-selbst | 344 | Metrik-Checkbox, Stundenverlauf-Schalter, amtl. Warnungen, Reiterwechsel, 412, #2375 | keins |
| compare-editor-autosave-user-isolation | 124 | AC-12: Autosave-PUT von A trifft B nicht; Cross-GET 404; Orte-Geste, 2. Nutzer registriert | indirekt `hub-cross-user-write-block` (nur API, keine UI-Geste) |
| compare-editor-slice3 | 210 | AC-4..9 Wertebereich-Editor im Anlege-Wizard `/compare/new` | keins (Trip-Wizard `tn-*`-IDs) |
| compare-hub-inline-edit | 324 | Nur Wertebereich-Teil (Z. 173-324): AC-33, AC-34, F002 | keins |

## Vorhandene Helfer (`frontend/e2e/helpers.ts` ab Z. 588)
`HubKind`, `HUB_KINDS`, `HUB_SEL`, `SeededHub`, `hubApiPath`, `seedHub(request, kind, {extra})` (flaches Überlagern, `display_config` wird ersetzt, nicht gemergt), `openHub(page, kind, id, {tab, hash})`, `registriereBestaetigtenZweitnutzer`. Vorbilder: `hub-versand-autosave-chip.spec.ts` (`zaehlePuts`, `expect.poll`), `hub-save-chip.spec.ts` (`verzoegerePuts`, `scheiternPuts`), `hub-cross-user-write-block.spec.ts` (serial, `beforeAll`, eine Registrierung).

## Produkt-Teilung (gemessen vom Explore-Agenten)
- `AlarmeTab`, `CorridorEditor`, `WetterMetrikenVersandPanel` sind geteilt. Reiter-IDs unterscheiden sich nur im Präfix (`trip-detail-tab-<id>` / `compare-detail-tab-<id>`).
- `corridor-editor-{route|vergleich}`; Radar-Toggle (`alarme-radar-toggle`) und `radar_alert_enabled` sind **nur Vergleich** (`alarmeTabSections.ts:11`, `compare_preset.go:60`). Telegram-Kurzstil/`send_telegram` liegen im Vergleichs-Preset; Trip braucht eigene Auslöser (z. B. Cooldown `alert-cooldown-input`).
- Wetter-Metriken: Vergleich `weather-metrics-tab-vergleich`, `weather-metrics-vergleich-row-*`, `compare-layout-hourly-enabled-toggle`; Trip-Gegenstücke **nicht geprüft** → in der Analyse klären.

## Auffälligkeiten (Schulden, die die Umstellung mit erledigen soll)
- `waitForTimeout`: wertebereiche-speichert-selbst (Z. 129, 158), wertebereiche-wertprops (165, 204, 249, 273), wetter-metriken-speichert-selbst (145, 169). Ersatz: `expect.poll` wie im Vorbild.
- Datenabhängige `.first()` (erster Pool-Eintrag/erste Zeile): wertebereiche-speichert-selbst, compare-hub-inline-edit, compare-editor-slice3.
- Kein UI-`login()` in den 8 Dateien.

## Ratsche / Wächter / CI
- Dateinamen bleiben bei In-place-Umbau ⇒ `E2E_MIN_SPECS` (68, `ci.yml:285`, EXAKT gebunden an Zeilenzahl der Positivliste) ändert sich nicht; bei Umbenennen/Zusammenlegen schon.
- `E2E_MIN_EXECUTED_HAUPT` (451, `ci.yml:286`) muss nach Umbau per `npx playwright test --list` **neu gemessen** werden (Schleifen verdoppeln Fälle).
- Wächter: Eintrag aus ALTLAST **muss** gestrichen werden, sobald die Datei konform ist (sonst rot); `ALTLAST_MAX` Literal von 41 entsprechend senken. Konform = `HUB_KINDS`-Schleife oder `gz-eigenstaendig:`-Kopf (≥15 Zeichen, erste 30 Zeilen).
- Staging-Configs mit Verweisen: `playwright.1256-s6.staging.config.ts:24` (hub-inline-edit), `playwright.1273-s4c.staging.config.ts:33` (user-isolation) — gültig, solange Namen bleiben.

## Risiken & Entscheidungen für /20-analyse
1. **Zusicherungsverlust:** Compare-Specs sind Regressionsnetze für #2276/#2277. Jede Zusicherung muss im neuen Spec für Vergleich unverändert bleiben (Mutations-Gegenprobe!).
2. **Vergleich-only-Zusicherungen** (Radar, Telegram-Kurzstil, `send_telegram`): als `kind`-Zweig mit Begründung erhalten, nicht wegschleifen.
3. **wertebereiche-wertprops AC-6/7** ist ein gewollter Kontrast Trip↔Vergleich, keine reine Schleife.
4. **slice3 (Wizard `/compare/new`)**: Trip-Wizard hat andere IDs; Hub-Variante (`seedHub` + `openHub tab=wertebereiche`) ändert die Zusicherung → Entscheidung nötig (Wizard bleibt Vergleich-only mit `gz-eigenstaendig:` oder S4/#2243).
5. **user-isolation:** Trip-Autosave-Geste ist Etappen-Datum (wie `hub-save-chip`), nicht Orte; Registrierungsbremse 5/h/IP ⇒ eine Registrierung für beide kinds.
6. **Quota:** Vergleiche max. 2 aktiv pro Nutzer, `seedHub` strikt im `finally` aufräumen, `workers: 1`.
7. **Alt-Dateien liefen in CI bereits** (Positivliste) — grün-Stand gegen CI-Stack neu messen; rote Altfälle sind Befund, nicht abschwächen.
8. **Trip-Pendants rot?** Ist ein Trip-Fall rot, ist das ein Produktbefund (AC-13-Muster), kein Anlass zum Abschwächen.

## Existing Specs
- `docs/specs/modules/feat_2347_s1_paritaets_e2e.md`, `feat_2347_s2_paritaets_e2e.md` (Gesamtschnitt, Befund-Korrekturen, Muster)
- Prozessregeln: `docs/reference/gates_und_ratschen.md`

## Analysis

### Type
Feature (reine Testschicht; Produktcode nur bei echter Produktlücke, Muster AC-13).

### Befunde der Analyse (am Code gemessen, 2026-10-27)
1. **Produkt ist für alle drei Reiter geteilt verdrahtet.** Der Trip-Hub mountet `WetterMetrikenVersandPanel context="route"`, `CorridorEditor`/`CorridorEditorMobile` und `AlarmeScheduleTab` → geteilter `AlarmeTab context="route"`, jeweils mit `saveController` (`TripTabs.svelte:196-205`). Autosave-Pfade existieren auf beiden Seiten — Trip-Pendants sind prüfbar, keine Produktarbeit nötig.
2. **Testid-Unterschied Wetter-Metriken:** Vergleich `weather-metrics-tab-vergleich` (eigener Zweig `WeatherMetricsTab.svelte:1429`), Trip `weather-metrics-tab` (+ `weather-metrics-tab-save`, Z. 1648-1662). Die Spec braucht eine kind-Tabelle der Selektoren (wie `HUB_SEL`), keine zwei Dateien.
3. **Vergleich-only-Zusicherungen bleiben als `kind`-Zweig mit Begründung:** Radar-Toggle/`radar_alert_enabled`, Telegram-Kurzstil/`send_telegram` (Vergleichs-Preset), Stundenverlauf-Schalter `compare-layout-hourly-enabled-toggle`. Trip bekommt eigene Auslöser (z. B. `alert-cooldown-input`).
4. **`compare-editor-slice3` testet den Anlege-Wizard `/compare/new`** (Alt-Bestand, fällt laut CLAUDE.md ersatzlos mit dem Anlege-Umbau; #2243). Hub-Variante würde die Zusicherung ändern, der Trip-Wizard hat andere IDs (`tn-*`). → Datei bleibt in S3a **Vergleich-only** mit `gz-eigenstaendig:`-Kopf und Verweis auf die Löschung (S4/#2243). Ihre Wertebereich-Zusicherungen AC-4..9 sind durch die neue Hub-Wertebereich-Spec je kind abgedeckt, sobald diese grün ist (Deckung im RED lesen).
5. **`compare-hub-inline-edit`:** nur der Wertebereich-Teil (Z. 173-324) wandert in die geteilte Wertebereich-Spec; der Rest (Z. 1-172) bleibt in S3b/S4.
6. **`wertebereiche-wertprops` AC-6 (Trip, offene Grenze → Fehlerbanner) vs. AC-7 (Vergleich, kein PUT)** ist ein **gewollter Kontrast** → expliziter `kind`-Zweig, nicht weggeschleift.
7. **user-isolation:** Trip-Autosave-Geste ist ein Etappen-Datum (wie `hub-save-chip`), Vergleich eine Orte-Geste; eine Registrierung (Bremse 5/h/IP) für beide kinds, `serial` + `beforeAll` nach Vorbild `hub-cross-user-write-block`.
8. **Schulden mit erledigen:** `waitForTimeout` (wertebereiche-speichert 129/158, wertprops 165/204/249/273, metriken 145/169) → `expect.poll`; datenabhängige `.first()` → Eigen-Seed je kind.
9. **Keine Parallel-Lieferung:** Suche in `origin/main` nach „2347" seit HEAD ergibt nichts. S2 live (819ea0f60).

### Affected Files
| File | Change | Description |
|---|---|---|
| `frontend/e2e/hub-alarme-speichert-selbst.spec.ts` | CREATE | kind-Schleife; ersetzt `compare-alarme-speichert-selbst` |
| `frontend/e2e/hub-alarme-wertprops.spec.ts` | CREATE | gemeinsame Props + Vergleich-only-Zweige (Radar, Telegram-Kurzstil) |
| `frontend/e2e/hub-wertebereiche-speichert-selbst.spec.ts` | CREATE | ersetzt Compare-Pendant |
| `frontend/e2e/hub-wertebereiche-wertprops.spec.ts` | CREATE | inkl. AC-6/7-Kontrast + Wertebereich-Teil `compare-hub-inline-edit` |
| `frontend/e2e/hub-wetter-metriken-speichert-selbst.spec.ts` | CREATE | Selektor-Tabelle je kind |
| `frontend/e2e/hub-editor-autosave-user-isolation.spec.ts` | CREATE | ersetzt `compare-editor-autosave-user-isolation` |
| 6 `compare-*`-Altdateien | DELETE | Zusicherungen vorher 1:1 abgeglichen |
| `compare-hub-inline-edit.spec.ts` | MODIFY | Wertebereich-Teil entfernen |
| `compare-editor-slice3.spec.ts` | MODIFY | nur `gz-eigenstaendig:`-Kopf |
| `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml` | MODIFY | Namen tauschen; `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED_HAUPT` per `--list` neu messen |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | MODIFY | ALTLAST 41 → 35, `ALTLAST_MAX` senken |
| Staging-Config `playwright.1273-s4c…` | MODIFY | Verweis auf user-isolation anpassen |

### Scope Assessment
- Files: ca. 16–18 · Estimated LoC: +1.400 / −1.700 (Testcode, kein produktives Spec-LoC)
- Risk Level: MEDIUM — Zusicherungsverlust (Regressionsnetz für #2276/#2277), Quota 2 Vergleiche, Registrierungsbremse.

### Technical Approach
Neue Specs je Thema mit `for (const kind of HUB_KINDS)`, `seedHub`/`openHub` aus `helpers.ts`, Vorbilder `hub-versand-autosave-chip`/`hub-save-chip`. Vergleich-only-Fälle als `if (kind === 'vergleich')` mit Begründungskommentar. Reihenfolge: (1) neue Specs gegen CI-Stack, Altfälle vorher neu messen (rote Altfälle = Befund, nie abschwächen); (2) erst bei grün Altdateien löschen; (3) Ratsche, Wächter, `--list`-Messung; (4) Mutations-Gegenprobe pro Zusicherung (Autosave-PUT-Zahl, Reiterwechsel-Flush, 412-Banner, #2375-Roundtrip). Trip-Rot = Produktbefund (AC-13).

### Open Questions
- [x] Wizard-slice3: bleibt Vergleich-only mit `gz-eigenstaendig:` (technisch, kein PO-Entscheid).
- [ ] Im RED zu messen: ob Trip-Pendants zu Reiterwechsel-Flush und 412 („Nochmal speichern") im Produkt vorhanden sind.
