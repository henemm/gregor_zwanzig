---
entity_id: feat_2347_s3a_paritaets_e2e
type: feature
created: 2026-10-27
updated: 2026-10-27
status: draft
version: "1.0"
workflow: feat-2347-s3a-paritaets-e2e
tags: [epic-2345, etappe-p6, ratsche, e2e, playwright, trip-compare-teilung, mandantentrennung]
---

# Paritäts-E2E, Scheibe S3a: Alarme, Wertebereiche, Wetter-Metriken, Wertprops, Autosave-Isolation (#2347)

## Approval

- [ ] Approved

## Purpose

S1 (Helfer, Versand-Autosave, Cross-User-Sperre) und S2 (Reiterleiste, Kopf, Listen-Menü, Speicher-Chip, Sende-Dialog) sind live. S3a räumt den nächsten Block der Compare-only-Altlast: sechs Playwright-Specs zu **Alarme-Reiter, Wertebereiche-Reiter, Wetter-Metriken-Reiter und Autosave-Nutzertrennung** werden zu sechs geteilten `hub-*`-Specs, in denen **eine** Zusicherung per Schleife (`for (const kind of HUB_KINDS)`) für Trip UND Ortsvergleich geprüft wird. Danach gilt für diese Reiter: Was für den Ortsvergleich bewiesen ist, ist für den Trip bewiesen — und umgekehrt.

Die Produktanalyse (2026-10-27) zeigt: `AlarmeTab`, `CorridorEditor` und `WetterMetrikenVersandPanel` sind im Produkt bereits geteilte Bausteine, im Trip-Hub verdrahtet mit demselben `saveController`. Es fehlt allein der Beweis für den Trip. Die Alt-Specs sind zudem das Regressionsnetz für #2276/#2277 (Compare-Speicherweg); **keine einzige Zusicherung darf beim Zusammenführen verloren gehen** — das ist das Hauptrisiko dieser Scheibe und wird per Zuordnungstabelle und Mutations-Gegenprobe bewacht.

Reine Testschicht. Produktcode wird **nicht** geplant. Wird ein Trip-Fall beim Zusammenführen rot, ist das eine Produktlücke, die **im selben Ticket** behoben wird (AC-13, Muster aus S2); abgeschwächt wird nie.

## Source

- **File:** neue Specs `frontend/e2e/hub-alarme-speichert-selbst.spec.ts`, `hub-alarme-wertprops.spec.ts`, `hub-wertebereiche-speichert-selbst.spec.ts`, `hub-wertebereiche-wertprops.spec.ts`, `hub-wetter-metriken-speichert-selbst.spec.ts`, `hub-editor-autosave-user-isolation.spec.ts`; Helfer `frontend/e2e/helpers.ts` (nur falls nötig, keine Assertions); Wächter `tests/unit/test_e2e_compare_paritaet_waechter.py`; Ratsche `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml`
- **Identifier:** `HUB_KINDS`, `seedHub`, `openHub`, `HUB_SEL` · `ALTLAST`, `ALTLAST_MAX` · `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`
- **Produktcode:** keiner (Regel für Trip-Rot-Fälle: AC-13).

**Schicht und Querschnitts-Prüfpunkte:**
- **Schicht:** ausschließlich Testschicht (Playwright gegen den CI-Stack, Python-Unit-Wächter, CI-Ratsche, Gate-Doku). Kein Code in `frontend/src/`, `internal/`, `cmd/`, `api/`, `src/` — außer AC-13.
- **Trip/Ortsvergleich-Teilung:** Kern der Spec. Compare-eigen bleiben nur: Radar-Toggle / `radar_alert_enabled`, Telegram-Kurzstil / `send_telegram` (beide Vergleichs-Preset, `alarmeTabSections.ts:11`, `compare_preset.go:60`), Stundenverlauf-Schalter `compare-layout-hourly-enabled-toggle`, die Orte-Geste in der Autosave-Isolation — jeweils als `if (kind === 'vergleich')`-Zweig mit Begründungskommentar, in der Zuordnung als compare-eigen geführt. Trip bekommt zu jedem dieser Zweige einen **eigenen Auslöser** für dieselbe Chip-/PUT-Zusicherung (z. B. `alert-cooldown-input`, Etappen-Datum).
- **Mandantentrennung:** `hub-editor-autosave-user-isolation` ist die einzige Spec mit zweitem Nutzer: genau **eine** Registrierung (`registriereBestaetigtenZweitnutzer`, Bremse 5/h/IP) für beide kinds, `serial` + `beforeAll` nach Vorbild `hub-cross-user-write-block`. Alle anderen Specs arbeiten mit Wegwerf-Daten des Admin-Testnutzers (Präfix `E2E-GZ-`, Aufräumen im `finally`). Es wird kein neuer Endpunkt eingeführt; kein Zugriff auf Konfiguration oder Trips des PO.
- **Kanäle:** nicht betroffen — es wird nichts versendet; Alarm-Specs ändern nur Einstellungen des Wegwerf-Objekts.

## Gesamtschnitt #2347 (Stand)

| Scheibe | Inhalt | Status |
|---|---|---|
| S1 | Helfer; Versand-Autosave + Chip; Cross-User-Sperre; Wächter (ALTLAST 48) | live |
| S2 | Reiterleiste, Kopf, Listen-Menü, Speicher-Chip, Sende-Dialog (ALTLAST 48 → 41) | live (819ea0f60) |
| **S3a (diese Spec)** | 6 Compare-Altdateien → 6 `hub-*`-Specs; `compare-hub-inline-edit` (Wertebereich-Teil) wandert; `compare-editor-slice3` bleibt Vergleich-only mit `gz-eigenstaendig:`-Kopf | diese Spec |
| S3b | Versand-Trio, `versand-tab-vergleich`, Konflikt-412, Radar-Toggle-Reste, Stundenverlauf-Reste, `compare-editor-autosave`, `issue-682` ↔ `issue-661`, `.staging`-Specs, Rest `compare-hub-inline-edit` (Z. 1-172) | folgt |
| S4 | Gruppe ohne Trip-Pendant mit `gz-eigenstaendig:`-Kopf; #2243-Leichen (u. a. Löschung `compare-editor-slice3`); ALTLAST leer; Ratsche final | folgt |

Ticket #2347 und Epic #2345 bleiben offen bis S4. Scheiben werden strikt nacheinander gemergt (`ci_e2e_specs.txt` ist Konfliktpunkt).

## Befunde (am Code gemessen, 2026-10-27)

1. **Produkt ist geteilt verdrahtet.** Der Trip-Hub mountet `WetterMetrikenVersandPanel context="route"`, `CorridorEditor`/`CorridorEditorMobile` und `AlarmeScheduleTab` → geteilter `AlarmeTab context="route"`, jeweils mit `saveController` (`TripTabs.svelte:196-205`). Trip-Pendants sind prüfbar.
2. **Selektoren unterscheiden sich nur im Präfix bzw. Reiter-Testid:** `trip-detail-tab-<id>` / `compare-detail-tab-<id>`; `corridor-editor-{route|vergleich}`; Wetter-Metriken Vergleich `weather-metrics-tab-vergleich` (+ `weather-metrics-vergleich-row-*`, eigener Zweig `WeatherMetricsTab.svelte:1429`), Trip `weather-metrics-tab` (+ `weather-metrics-tab-save`, `:1648-1662`). Die Specs führen eine **kind-Selektor-Tabelle** (lokal, wie `HUB_SEL`), keine zwei Dateien.
3. **Alt-Dateien stehen in der Ratsche** (`ci_e2e_specs.txt` Z. 358-372): ihr Grün-Stand ist CI-belegt, wird aber im RED gegen den aktuellen CI-Stack neu gemessen. Rote Altfälle sind Befund, nie Abschwächungsgrund.
4. **Schulden:** `waitForTimeout` in `compare-wertebereiche-speichert-selbst` (Z. 129, 158), `-wertprops` (165, 204, 249, 273), `compare-wetter-metriken-speichert-selbst` (145, 169) → `expect.poll`. Datenabhängige `.first()` (erster Pool-Eintrag/erste Zeile) in `compare-wertebereiche-speichert-selbst`, `compare-hub-inline-edit`, `compare-editor-slice3` → Eigen-Seed je kind. Kein UI-`login()` in den acht Dateien (Anmeldung über `storageState`).
5. **`compare-editor-slice3`** prüft den Anlege-Wizard `/compare/new` (Alt-Bestand, fällt mit #2243/S4 ersatzlos). Hub-Variante würde die Zusicherung ändern; Trip-Wizard hat andere IDs (`tn-*`). Entscheidung (technisch, kein PO-Entscheid): Datei bleibt in S3a **Vergleich-only** mit `gz-eigenstaendig:`-Kopf (≥ 15 Zeichen, erste 30 Zeilen) und Verweis auf die Löschung in S4. Ihre Wertebereich-Zusicherungen AC-4..9 sind durch `hub-wertebereiche-*` je kind zusätzlich abgedeckt; die Deckung wird im RED gelesen.
6. **Wächter-Rechnung (Abweichung zum Briefing „41 → 35"):** `compare-editor-slice3` und `compare-hub-inline-edit` stehen beide in `ALTLAST` (Wächter Z. 50, 56). Sechs Altdateien werden gelöscht (−6); `slice3` wird durch den `gz-eigenstaendig:`-Kopf konform und **muss** gestrichen werden (−1, sonst rot); `compare-hub-inline-edit` bleibt Altlast, weil sein Rest (Z. 1-172) compare-only bleibt (S3b). Ergebnis **41 → 34**, `ALTLAST_MAX = 34`. Der Wächter-Test entscheidet; die Zahl wird in `/50` gegen ihn gemessen.
7. **Quota:** Vergleiche sind pro Nutzer auf 2 aktive begrenzt (409). `seedHub('vergleich')` räumt strikt im `finally` auf; Fälle mit zwei Vergleichen laufen nie parallel (`workers: 1`).
8. **Keine Parallel-Lieferung:** Suche in `origin/main` nach „2347" ergibt nichts über S2 hinaus.

## Abgrenzung

Nicht in S3a: alles aus S3b und S4 (siehe Gesamtschnitt), `compare-hub-inline-edit` Z. 1-172, die Wizard-Löschung `compare-editor-slice3`, `hub-versand-*`. Trip-Dateien, die Dopplungen enthalten (z. B. `hub-cross-user-write-block`), bleiben unverändert — Bereinigen von Dopplungen ist kein Zusicherungsverlust-Risiko wert (Sammelposten S4).

## Estimated Scope

- **LoC (Testcode, netto):** ca. +1.400 / −1.700 (6 neue Specs ≈ 1.400; gelöscht 6 Altdateien = 1.727 Zeilen, plus Wertebereich-Teil `compare-hub-inline-edit` ≈ 150). Alles Testcode/Doku — zählt nicht als produktive Spec-Datei; `loc_limit_override` nur nach `workflow.py status`.
- **Files:** ca. 16–18.
- **Effort:** high (1:1-Zuordnung, Neumessung des Altbestands, Mutations-Gegenprobe pro Zusicherung, Trip-Pendants erstmals gemessen).
- **Risiko:** MEDIUM — Zusicherungsverlust (Regressionsnetz #2276/#2277), Quota 2 Vergleiche, Registrierungsbremse, Trip-Pendants evtl. rot (Produktbefund).

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `frontend/e2e/helpers.ts` (`HubKind`, `HUB_KINDS`, `HUB_SEL`, `seedHub`, `openHub`, `hubApiPath`, `registriereBestaetigtenZweitnutzer`) | module | Basis jeder neuen Spec (S1/S2) |
| `frontend/e2e/hub-versand-autosave-chip.spec.ts`, `hub-save-chip.spec.ts`, `hub-cross-user-write-block.spec.ts` | module | Vorbilder (`zaehlePuts`, `verzoegerePuts`, `scheiternPuts`, `expect.poll`, serial/`beforeAll`) |
| `AlarmeTab`, `CorridorEditor`/`CorridorEditorMobile`, `WetterMetrikenVersandPanel`, `WeatherMetricsTab.svelte`, `TripTabs.svelte`, `CompareTabs.svelte`, `saveController` | module | geprüfte, geteilte Bausteine (unverändert) |
| `frontend/e2e/global.setup.ts` | module | Admin-`storageState`, Seed-Orte |
| `.github/ci_e2e_specs.txt`, `ci.yml` Job `e2e`, `.github/scripts/e2e_gate.py`, `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | CI | Positivliste, `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT` |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | test | `ALTLAST`, `ALTLAST_MAX` |
| `docs/reference/gates_und_ratschen.md` | doc | Wächter-/Ratschen-Doku (Fortschreibung) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/hub-alarme-speichert-selbst.spec.ts` | CREATE | kind-Schleife; ersetzt `compare-alarme-speichert-selbst` |
| `frontend/e2e/hub-alarme-wertprops.spec.ts` | CREATE | gemeinsame Props + Vergleich-only-Zweige (Radar, Telegram-Kurzstil) |
| `frontend/e2e/hub-wertebereiche-speichert-selbst.spec.ts` | CREATE | ersetzt `compare-wertebereiche-speichert-selbst` |
| `frontend/e2e/hub-wertebereiche-wertprops.spec.ts` | CREATE | inkl. AC-6/7-Kontrast und Wertebereich-Teil aus `compare-hub-inline-edit` |
| `frontend/e2e/hub-wetter-metriken-speichert-selbst.spec.ts` | CREATE | Selektor-Tabelle je kind |
| `frontend/e2e/hub-editor-autosave-user-isolation.spec.ts` | CREATE | ersetzt `compare-editor-autosave-user-isolation` |
| `frontend/e2e/compare-alarme-speichert-selbst.spec.ts`, `compare-alarme-wertprops.spec.ts`, `compare-wertebereiche-speichert-selbst.spec.ts`, `compare-wertebereiche-wertprops.spec.ts`, `compare-wetter-metriken-speichert-selbst.spec.ts`, `compare-editor-autosave-user-isolation.spec.ts` | DELETE | erst nach grünem Lauf der neuen Specs und 1:1-Abgleich |
| `frontend/e2e/compare-hub-inline-edit.spec.ts` | MODIFY | nur Wertebereich-Teil (Z. 173-324: AC-33, AC-34, F002) entfernen; Z. 1-172 unverändert |
| `frontend/e2e/compare-editor-slice3.spec.ts` | MODIFY | nur `gz-eigenstaendig:`-Kopf (Begründung + Verweis S4/#2243) |
| `frontend/e2e/helpers.ts` | MODIFY (optional) | nur Konstanten/Seed-Optionen ohne Assertions, falls mehrere Specs dasselbe brauchen |
| `.github/ci_e2e_specs.txt` | MODIFY | sechs Namen tauschen; Aufnahme-Kommentar mit Filter-A/B/C-Ergebnis |
| `.github/workflows/ci.yml` | MODIFY | `E2E_MIN_SPECS` (erwartet unverändert 68), `E2E_MIN_EXECUTED_HAUPT` neu gemessen |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | MODIFY | sechs Altnamen + `slice3` aus `ALTLAST`; `ALTLAST_MAX` 41 → 34; Docstring-Messzeile |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Wächter-Zahl „S3a: 34" |
| Staging-Config `frontend/playwright.1273-s4c.staging.config.ts` (und `frontend/playwright.1256-s6.staging.config.ts`) | MODIFY | Verweis auf `hub-editor-autosave-user-isolation` bzw. verbleibende Datei anpassen |

### Estimated Changes
- Files: ca. 17
- LoC: +1.400 / −1.700 (Testcode)

## Implementation Details

Jeder Fall läuft als `for (const kind of HUB_KINDS) test(\`<ID> (${kind}): …\`)`; Testtitel tragen `kind`. Kind-eigene Zweige (`if (kind === 'vergleich')`) tragen einen Kommentar mit Begründung. Setup immer `seedHub(request, kind, { extra })` (flaches Überlagern, `display_config` wird ersetzt, nicht gemergt — Seed-Rümpfe daher vollständig), Öffnen mit `openHub(page, kind, id, { tab })`, Aufräumen im `finally`. Wartebedingungen ausschließlich `page.waitForResponse`, `expect.poll`, `toHaveAttribute`, `toHaveCount` — kein `waitForTimeout`, kein `skip`, kein UI-`login()`.

### Fälle je neue Spec

**`hub-alarme-speichert-selbst.spec.ts` (AS)** — Autosave Alarm-Reiter
- AS-1 Eine Änderung im Alarm-Reiter löst **genau einen** PUT aus (`zaehlePuts`), Chip `saving` → `idle`, Stand nach Reload persistent
- AS-2 Reiterwechsel direkt nach der Änderung flusht den ausstehenden Speichervorgang (kein Datenverlust)
- AS-3 Pausieren direkt nach der Änderung flusht ebenfalls
- AS-4 Roundtrip-Fall #2375 (gespeicherte Werte nach Reload und weiterer Änderung unverändert; PUT-Rumpf trägt nur das Geänderte, übrige Felder bleiben)
- Auslöser je kind: Vergleich Alarm-Schalter laut Alt-Spec; Trip eigener Alarm-Auslöser (z. B. `alert-cooldown-input`), gleiche Chip-/PUT-Assertions. Reiter-Testid über kind-Tabelle.

**`hub-alarme-wertprops.spec.ts` (AW)** — vier Alt-Fälle
- AW-1 Amtliche Warnungen: Schalter speichert, persistent (je kind)
- AW-2 *(nur vergleich)* Radar-Toggle `alarme-radar-toggle` / `radar_alert_enabled` — Begründung: Radar-Alarm ist Vergleichs-Preset (`alarmeTabSections.ts:11`, `compare_preset.go:60`); Trip-Gegenstück existiert im Produkt nicht
- AW-3 Kanal je kind; *(nur vergleich)* Telegram-Kurzstil / `send_telegram` — Begründung: liegen im Vergleichs-Preset; Trip prüft stattdessen den Kanal-Teil, den der Trip-Hub tatsächlich führt
- AW-4 Empfindlichkeit, Cooldown, Stille Stunden: Wert speichert, persistent, genau ein PUT (je kind)
- AW-5 Nebenwirkungsfreiheit: Änderung eines Alarm-Werts lässt alle übrigen Felder des Objekts unberührt (je kind)

**`hub-wertebereiche-speichert-selbst.spec.ts` (WS)**
- WS-1 Metrik im Wertebereiche-Reiter hinzufügen speichert selbst, persistent (Eigen-Seed statt erstem Pool-Eintrag; gewählte Metrik aus dem Pool des Objekts bestimmt)
- WS-2 Regler/Grenzwert committen speichert genau einmal
- WS-3 Reiterwechsel flusht ausstehende Änderung
- WS-4 Server antwortet 412 ⇒ Konflikt-Meldung und „Nochmal speichern" speichert den bestätigten Stand (Trip-Verfügbarkeit im RED messen; fehlt sie, gilt AC-13)
- WS-5 Pausieren flusht
- WS-6 Roundtrip #2375
- Stabilitätsfenster per `expect.poll` statt `waitForTimeout` (Alt Z. 129, 158).

**`hub-wertebereiche-wertprops.spec.ts` (WW)**
- WW-1 Von-Grenze ändern ⇒ **ein** PUT, persistent (je kind)
- WW-2 Mobil-Band-Drag (`CorridorEditorMobile`), persistent (je kind)
- WW-3 AC-33 / AC-34 / F002 aus `compare-hub-inline-edit` Z. 173-324 (je kind; Eigen-Seed statt `.first()`)
- WW-4 **Expliziter kind-Kontrast (bewusst verschieden, nicht wegschleifen):** *(route)* offene Grenze ⇒ Fehlerbanner (Alt AC-6); *(vergleich)* offene Grenze ⇒ kein PUT (Alt AC-7). Beide Zweige bleiben, jeder prüft seine eigene Zusicherung und begründet den Unterschied im Kommentar.
- Alt-`waitForTimeout` (165, 204, 249, 273) → `expect.poll` auf Server-Stand bzw. PUT-Zähler.

**`hub-wetter-metriken-speichert-selbst.spec.ts` (MS)** — Selektor-Tabelle je kind
- MS-1 Metrik-Checkbox speichert selbst, persistent (je kind; Selektoren `weather-metrics-tab-vergleich` / `weather-metrics-tab`)
- MS-2 *(nur vergleich)* Stundenverlauf-Schalter `compare-layout-hourly-enabled-toggle` — Begründung: Layout-Option des Vergleichs-Mailtemplates
- MS-3 Amtliche Warnungen in den Wetter-Metriken, persistent (je kind)
- MS-4 Reiterwechsel flusht
- MS-5 412 + „Nochmal speichern" (je kind; Trip im RED messen, sonst AC-13)
- MS-6 Roundtrip #2375
- Alt-`waitForTimeout` (145, 169) → `expect.poll`.

**`hub-editor-autosave-user-isolation.spec.ts` (UI)** — Alt AC-12
- `test.describe.configure({ mode: 'serial' })`, **eine** Registrierung in `beforeAll` für beide kinds.
- UI-1 Nutzer A löst Autosave-PUT aus; Objekt von Nutzer B bleibt unverändert; Cross-GET von A auf B ⇒ 404 (je kind)
- Auslöser: *(vergleich)* Orte-Geste; *(route)* Etappen-Datum ändern + blur (Vorbild `hub-save-chip` SC-2). Begründung: Autosave-Geste ist kind-eigen, die Trennungs-Zusicherung gemeinsam.
- Beide Nutzer, beide kinds: je ≥ zwei verschiedene Nutzer (Projektregel „Zwei-Nutzer-Test").

### Wächter, Ratsche, CI

- **Wächter:** `ALTLAST` verliert die sechs gelöschten Namen (`compare-alarme-speichert-selbst`, `-alarme-wertprops`, `-editor-autosave-user-isolation`, `-wertebereiche-speichert-selbst`, `-wertebereiche-wertprops`, `-wetter-metriken-speichert-selbst`) und `compare-editor-slice3.spec.ts` (jetzt `gz-eigenstaendig:`-konform); `compare-hub-inline-edit.spec.ts` bleibt. `ALTLAST_MAX` Literal 41 → **34** (Literal, nicht `len(ALTLAST)`). Docstring-Messzeile und `gates_und_ratschen.md` fortschreiben; Prüfdatum 2027-01-24 unverändert.
- **Ratsche:** In `.github/ci_e2e_specs.txt` die sechs `e2e/compare-…`-Zeilen durch die sechs `e2e/hub-…`-Zeilen ersetzen (alphabetisch); `slice3` und `inline-edit` bleiben. Kommentar „Aufnahme 2026-10-27 (#2347 S3a)" mit Filter-A/B/C-Ergebnis. `E2E_MIN_SPECS` bleibt **68** (6 raus, 6 rein; muss exakt `grep -c '^e2e/'` entsprechen — der Kern-Test erzwingt Gleichheit).
- **`E2E_MIN_EXECUTED_HAUPT`:** wird in `/50` per `npx playwright test --list` über die Hauptlauf-Auswahl am Endstand **gemessen, nicht geschätzt** (Richtung: steigt, weil Schleifen die Fälle verdoppeln, abzüglich des aus `compare-hub-inline-edit` entfernten Teils). Es gilt immer die Messung; Begründung im Kommentar fortschreiben.
- **Verweis-Hygiene:** `grep -rn <alter Name> frontend .github tests` am Endstand: keine Treffer auf gelöschte Dateien außer Historie in `docs/`; Staging-Configs `playwright.1273-s4c…` (user-isolation) und `playwright.1256-s6…` (hub-inline-edit, Datei bleibt) prüfen und nachziehen; Kommentar-Verweise in Ratsche/Tests nachziehen.

### Reihenfolge in /50
1. Altbestand gegen den CI-Stack neu messen (rote Altfälle = Befund).
2. Neue Specs schreiben, dreimal grün (Filter B).
3. Mutations-Gegenprobe pro Zusicherung (Sicherungskopie, String-Ersetzung, nie `git checkout/stash/reset`).
4. **Erst bei Grün** Altdateien löschen, `compare-hub-inline-edit` kürzen, `slice3`-Kopf setzen.
5. Ratsche, Wächter, `--list`-Messung, Doku.

## Zuordnung alt → neu (Regressionsnetz, in /50 gegen `grep -c "test("` je Altdatei vervollständigt)

| Alt (Datei · Zusicherung) | Neu (Spec · Fall) | Anmerkung |
|---|---|---|
| `compare-alarme-speichert-selbst` · genau 1 PUT je Änderung | AS-1 je kind | |
| · Reiterwechsel-Flush | AS-2 je kind | |
| · Pausieren-Flush | AS-3 je kind | |
| · #2375-Roundtrip | AS-4 je kind | |
| `compare-alarme-wertprops` · amtliche Warnungen | AW-1 je kind | |
| · Radar-Toggle | AW-2 nur vergleich | compare-eigen, Begründung im Test |
| · Kanal / Telegram-Kurzstil | AW-3 je kind + vergleich-Zweig | `send_telegram` Vergleichs-Preset |
| · Empfindlichkeit / Cooldown / Stille Stunden | AW-4 je kind | |
| · Nebenwirkungsfreiheit | AW-5 je kind | |
| `compare-wertebereiche-speichert-selbst` · Metrik hinzufügen, Regler, Reiterwechsel, 412, Pausieren, #2375 | WS-1..WS-6 je kind | `waitForTimeout` + `.first()` ersetzt |
| `compare-wertebereiche-wertprops` · Von-Grenze, Mobil-Band | WW-1, WW-2 je kind | `waitForTimeout` ersetzt |
| · AC-6 (Trip, Fehlerbanner) / AC-7 (Vergleich, kein PUT) | WW-4 kind-Zweige | bewusster Kontrast |
| `compare-hub-inline-edit` Z. 173-324 · AC-33, AC-34, F002 | WW-3 je kind | Rest Z. 1-172 bleibt (S3b) |
| `compare-wetter-metriken-speichert-selbst` · Checkbox, amtl. Warnungen, Reiterwechsel, 412, #2375 | MS-1, MS-3, MS-4, MS-5, MS-6 je kind | |
| · Stundenverlauf-Schalter | MS-2 nur vergleich | compare-eigen |
| `compare-editor-autosave-user-isolation` · AC-12 | UI-1 je kind | Orte-Geste nur vergleich, Etappen-Datum route |
| `compare-editor-slice3` · AC-4..9 Wizard | bleibt Datei, `gz-eigenstaendig:` | zusätzlich durch WS/WW je kind abgedeckt |

## Expected Behavior

- **Input:** CI-Lauf `e2e` gegen den isolierten Stack; Unit-Lauf des Wächters.
- **Output:** Alarme-, Wertebereiche- und Wetter-Metriken-Reiter sowie die Autosave-Trennung werden für Trip und Ortsvergleich durch **dieselben** Specs mit denselben Zusicherungen geprüft; die CI bewacht sie. Eine neue Compare-only-Spec dieser Gruppe wäre für den Wächter wieder ein Verstoß.
- **Side effects:** Wegwerf-Daten `E2E-GZ-…` (Aufräumen im `finally`, Sicherheitsnetz `global.teardown.ts`); ein Wegwerf-Zweitnutzer in der Isolation-Spec; keine Produktdaten, kein Versand.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich WHEN eine Änderung im Alarm-Reiter gemacht wird THEN geht genau ein PUT hinaus und der Stand ist nach Reload persistent (`hub-alarme-speichert-selbst`, je kind).
- [ ] Test 2: GIVEN ein Wegwerf-Objekt im Wertebereiche-Reiter WHEN der Server mit 412 antwortet und „Nochmal speichern" gewählt wird THEN ist der bestätigte Stand gespeichert (`hub-wertebereiche-speichert-selbst`, je kind).
- [ ] Test 3: GIVEN Nutzer A und Nutzer B mit je einem Objekt WHEN A eine Autosave-Geste ausführt THEN bleibt das Objekt von B unverändert und ein Cross-GET liefert 404 (`hub-editor-autosave-user-isolation`, je kind).
- [ ] Test 4: GIVEN der Wächter WHEN der Unit-Test läuft THEN hat `ALTLAST` 34 Einträge und `ALTLAST_MAX` ist 34 (`tests/unit/test_e2e_compare_paritaet_waechter.py`).
- [ ] Test 5: GIVEN die Positivliste WHEN der Bindungstest läuft THEN entspricht `E2E_MIN_SPECS` der Listenlänge und jede Zeile verweist auf eine vorhandene Datei (`tests/unit/test_e2e_positivliste_ratschen_bindung.py`).

## Acceptance Criteria

- **AC-1:** Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich / When der Nutzer im Alarm-Reiter eine Einstellung ändert, direkt danach den Reiter wechselt bzw. pausiert und den Roundtrip (Neuladen, weitere Änderung) durchläuft / Then gilt für Trip UND Ortsvergleich: genau ein Speicher-Aufruf je Änderung, der Chip geht von „Speichere…" auf „Gespeichert", der Reiterwechsel und das Pausieren speichern den ausstehenden Stand mit, der Stand überlebt das Neuladen und der Speicher-Aufruf lässt alle übrigen Felder unberührt (#2375) — in `hub-alarme-speichert-selbst.spec.ts` per `HUB_KINDS`-Schleife.
  - Test: `hub-alarme-speichert-selbst.spec.ts` (AS-1..AS-4), Ratsche, CI-Stack.
  - Mutation (je kind getrennt): Autosave-Aufruf im geteilten `AlarmeTab` doppelt auslösen → AS-1 beider kinds rot; Flush beim Reiterwechsel entfernen → AS-2 rot; im Trip-Hub den `saveController` des Alarm-Reiters nicht verdrahten → nur Trip-Fälle rot.
- **AC-2:** Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich / When der Nutzer amtliche Warnungen, Kanal, Empfindlichkeit, Cooldown und Stille Stunden im Alarm-Reiter ändert / Then wird für Trip UND Ortsvergleich der jeweilige Wert gespeichert und bleibt nach dem Neuladen erhalten, und alle übrigen Alarm-Felder bleiben unverändert. Nur beim Ortsvergleich zusätzlich Radar-Toggle und Telegram-Kurzstil (`radar_alert_enabled`, `send_telegram`) — diese Zweige bleiben bestehen, weil sie nur im Vergleichs-Preset existieren, und tragen die Begründung im Test.
  - Test: `hub-alarme-wertprops.spec.ts` (AW-1..AW-5).
  - Mutation: Cooldown-Wert beim Speichern verwerfen → AW-4 des betroffenen kind rot; `radar_alert_enabled` nicht persistieren → nur AW-2 (vergleich) rot; ein Fremdfeld im PUT-Rumpf mitändern → AW-5 beider kinds rot.
- **AC-3:** Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich / When der Nutzer im Wertebereiche-Reiter eine Metrik hinzufügt, einen Regler bzw. eine Grenze committen lässt, den Reiter wechselt, pausiert, einen Server-Konflikt (412) mit „Nochmal speichern" auflöst und den Roundtrip durchläuft / Then gilt für Trip UND Ortsvergleich: die Änderung wird ohne Zutun gespeichert, genau einmal je Commit, Reiterwechsel und Pausieren flushen, nach dem 412 steht der bestätigte Stand, der Stand überlebt das Neuladen — ohne `waitForTimeout` und ohne Zugriff auf einen datenabhängigen ersten Pool-Eintrag (Eigen-Seed).
  - Test: `hub-wertebereiche-speichert-selbst.spec.ts` (WS-1..WS-6).
  - Mutation: 412-Behandlung („Nochmal speichern") im geteilten Speicherweg entfernen → WS-4 rot; Commit-Handler des Reglers doppelt auslösen → WS-2 rot.
- **AC-4:** Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich / When der Nutzer die Von-Grenze ändert, das Band mobil zieht, die Fälle AC-33/AC-34/F002 aus dem Hub-Inline-Edit durchläuft / Then gilt für Trip UND Ortsvergleich: ein PUT je Änderung und persistent. Der gewollte Kontrast bleibt als expliziter kind-Zweig: eine offene Grenze zeigt im Trip das Fehlerbanner, im Ortsvergleich löst sie keinen Speicher-Aufruf aus — jeder Zweig prüft seine eigene Zusicherung mit Begründung und wird nicht zu einer gemeinsamen Schleife abgeschwächt.
  - Test: `hub-wertebereiche-wertprops.spec.ts` (WW-1..WW-4); der Wertebereich-Teil (Z. 173-324) ist danach aus `compare-hub-inline-edit.spec.ts` entfernt, Z. 1-172 unverändert.
  - Mutation: Fehlerbanner für offene Grenze im Trip entfernen → nur WW-4 (route) rot; offene Grenze im Vergleich trotzdem speichern → nur WW-4 (vergleich) rot; Von-Grenze nicht persistieren → WW-1 beider kinds rot.
- **AC-5:** Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich / When der Nutzer im Wetter-Metriken-Reiter eine Metrik an- und abwählt, amtliche Warnungen umschaltet, den Reiter wechselt, einen Konflikt (412) auflöst und den Roundtrip durchläuft / Then gilt für Trip UND Ortsvergleich: gespeichert ohne Zutun, persistent, Reiterwechsel flusht, 412 mit „Nochmal speichern" löst auf. Nur beim Ortsvergleich zusätzlich der Stundenverlauf-Schalter (`compare-layout-hourly-enabled-toggle`) als begründeter Zweig. Selektoren je kind kommen aus einer Tabelle in der Spec.
  - Test: `hub-wetter-metriken-speichert-selbst.spec.ts` (MS-1..MS-6); `waitForTimeout` (Alt Z. 145, 169) durch `expect.poll` ersetzt.
  - Mutation: Metrik-Checkbox speichert nicht → MS-1 des betroffenen kind rot; Stundenverlauf-Persistenz entfernen → nur MS-2 (vergleich) rot.
- **AC-6:** Given zwei verschiedene registrierte Nutzer A und B mit je einem Trip bzw. Ortsvergleich / When A im Editor eine Autosave-Geste ausführt (Vergleich: Orte-Geste, Trip: Etappen-Datum + blur) / Then bleibt das Objekt von B für beide kinds unverändert, ein Lese-Zugriff von A auf das Objekt von B liefert 404, und es wird für beide kinds nur **eine** Registrierung verbraucht (`serial`, `beforeAll`).
  - Test: `hub-editor-autosave-user-isolation.spec.ts` (UI-1); Zwei-Nutzer-Pflicht aus CLAUDE.md erfüllt.
  - Mutation: Nutzer-Kontext im PUT-Handler des Hubs auf „default" fallen lassen → UI-1 des betroffenen kind rot; Cross-GET ohne Besitzprüfung → UI-1 rot.
- **AC-7:** Given `compare-editor-slice3.spec.ts` / When der Wächter-Test und die Ratsche laufen / Then bleibt die Datei als Vergleich-only-Spec für den Anlege-Wizard `/compare/new` mit einem `gz-eigenstaendig:`-Kopf (Begründung: Wizard hat kein Trip-Pendant mit denselben IDs und fällt mit #2243/S4 ersatzlos), ihre Fälle laufen unverändert weiter, und die Wertebereich-Zusicherungen AC-4..9 sind zusätzlich durch AC-3/AC-4 je kind abgedeckt.
  - Test: Wächter-Test (Eintrag konform und aus `ALTLAST` gestrichen), Deckung im RED gelesen.
  - Mutation: Kopf entfernen → Wächter rot; Eintrag in `ALTLAST` stehen lassen → Wächter rot („Eintrag entfernen").
- **AC-8:** Given die sechs neuen Specs / When ein Vergleich-only-Zweig (`if (kind === 'vergleich')`) in ihnen vorkommt / Then trägt jeder Zweig einen Begründungskommentar und steht in der Zuordnung als compare-eigen (Radar, Telegram-Kurzstil, Stundenverlauf, Orte-Geste); ein Zweig, der einen Fall nur für eine Art prüft, obwohl das Produkt ihn für beide kann, ist unzulässig.
  - Test: Adversary-Prüfpunkt, `grep -n "kind === " frontend/e2e/hub-*.spec.ts` gegen die Zuordnung.
  - Mutation: keine (Prozess); Findings bei Zweig ohne Kommentar.
- **AC-9:** Given die Zuordnungstabelle dieser Spec / When jeder Testfall der sechs gelöschten Altdateien und des entfernten Wertebereich-Teils von `compare-hub-inline-edit` einer Zeile zugeordnet und gegen die neuen Specs abgeglichen wird / Then gibt es für jeden Altfall genau ein benanntes Ziel (oder die ausdrückliche Feststellung „bleibt/Deckung in …"), die ausgeführten Fälle der Zielspecs sind je kind ≥ zugeordnete Altfälle (`npx playwright test --list` je Zieldatei), und die Altdateien werden **erst nach grünem Lauf** der neuen Specs gelöscht. Keine Zusicherung geht verloren.
  - Test: `grep -c "^\s*test("` je Altdatei gegen die Tabelle in `/60` und im Adversary-Dialog; `--list` je Zieldatei.
  - Mutation: einen Fall (z. B. Pausieren-Flush AS-3) weglassen → die Fallzahl-Prüfung meldet die Differenz.
- **AC-10:** Given die neuen Specs / When sie im Zielverbund (Hauptlauf der Positivliste ohne `bug-703`) dreimal hintereinander laufen / Then sind alle drei Läufe grün (frischer Stack, frische `admin.json`), und die Specs enthalten **kein** `waitForTimeout`, kein `skip`/`test.fixme`, keinen `page.screenshot({path})`, keinen Hauptrepo-Pfad und kein `__dirname`; datenabhängige `.first()` auf Pool-Einträge oder Zeilen sind durch Eigen-Seed ersetzt; keine Spec nutzt UI-`login()`.
  - Test: Filter B (3 Zyklen) + `grep -c "waitForTimeout\|\.skip(\|test\.fixme\|__dirname" frontend/e2e/hub-*.spec.ts` = 0.
  - Mutation: `waitForTimeout` in eine Datei einfügen → Filter-A-Prüfung rot.
- **AC-11:** Given die Quota von höchstens zwei aktiven Vergleichen pro Nutzer / When die neuen Specs laufen / Then räumt jeder Fall seinen `seedHub`-Vergleich im `finally` auf, kein Fall braucht mehr als zwei Vergleiche gleichzeitig, und der Lauf scheitert nicht an 409.
  - Test: Filter-B-Läufe, `global.teardown.ts` meldet keinen Restbestand `E2E-GZ-`.
  - Mutation: `finally`-Aufräumen in einem Fall entfernen → Folgefall scheitert mit 409 (Quota-Befund).
- **AC-12:** Given der Paritäts-Wächter / When der Unit-Test läuft / Then enthält `ALTLAST` nur noch **34** Einträge (die sechs gelöschten Compare-Dateien und `compare-editor-slice3.spec.ts` sind entfernt, `compare-hub-inline-edit.spec.ts` bleibt), `ALTLAST_MAX` ist das Literal **34**, und die Selbsttests der Wächter-Mutationen bleiben grün.
  - Test: `tests/unit/test_e2e_compare_paritaet_waechter.py` (benannte Datei).
  - Mutation: einen der sieben Namen in `ALTLAST` stehen lassen → rot; `ALTLAST_MAX` auf 41 lassen → rot; neue `compare-neu.spec.ts` ohne Kopf anlegen → rot.
- **AC-13:** Given ein Fall der neuen Specs wird für den Trip rot, obwohl er für den Ortsvergleich grün ist (oder umgekehrt) / When die Ursache untersucht wird / Then wird die Produktlücke im **selben Ticket** (#2347) behoben und der Test bleibt unverändert streng; Abschwächen, `test.skip`, ein kind-Zweig, der den Fall nur für eine Art prüft, oder ein „bekannte Abweichung"-Vermerk sind unzulässig. Berührte Produktdateien werden in die Spec nachgetragen (`updated`/Changelog) und das LoC-Limit bei Bedarf per `loc_limit_override` angehoben.
  - Test: Prozess-AC; Beleg im Adversary-Protokoll (Liste „rot beim Zusammenführen: ja/nein, wenn ja: Fix-Commit"). Offene Frage aus der Analyse: Trip-Pendants zu Reiterwechsel-Flush und 412 („Nochmal speichern") werden im RED gemessen.
  - Mutation: keine (Regel).
- **AC-14:** Given die CI-Ampel / When die Ratsche geprüft wird / Then enthält `.github/ci_e2e_specs.txt` die sechs `hub-*`-Namen und keinen der sechs gelöschten `compare-*`-Namen, `E2E_MIN_SPECS` entspricht exakt der Listenlänge (erwartet unverändert 68), `E2E_MIN_EXECUTED_HAUPT` ist der am Endstand per `npx playwright test --list` gemessene Wert (Richtung: steigt) mit fortgeschriebener Begründung im Kommentar, jede Listenzeile verweist auf eine vorhandene Datei, und `grep -rn` auf die gelöschten Namen über `frontend`, `.github`, `tests` findet nur Historie in `docs/` (Staging-Config-Verweise sind nachgezogen).
  - Test: `tests/unit/test_e2e_positivliste_ratschen_bindung.py`, CI-Job `e2e` (`e2e_gate.py`), `grep`-Prüfung in `/60`.
  - Mutation: Listenzeile auf nicht existierenden Namen → Existenzprüfung rot; `E2E_MIN_SPECS` um 1 verfälschen → Kern-Test rot; `E2E_MIN_EXECUTED_HAUPT` um 1 verändern → `e2e_gate.py` rot.
- **AC-15:** Given ein zusammengeführtes Verhalten aus AC-1 bis AC-6 / When die Implementierung gezielt verfälscht wird (Mutations-Gegenprobe, Sicherungskopie, nur String-Ersetzung) / Then wird für **jedes** zusammengeführte Verhalten und **beide** kinds der jeweils betroffene Test rot, und es wird protokolliert, **welcher** Test rot wurde; eine Verfälschung, die kein Test fängt, ist ein Finding, und eine kind-spezifische Verfälschung macht nur den Fall dieser Art rot.
  - Test: Adversary-Dialog in `/50` (Familien: Selektor/Testid, Zähler, Wartebedingung, PUT-Rumpf, Flush, 412, Nutzer-Kontext).
  - Mutation: siehe die Mutationszeilen in AC-1 bis AC-6.

## Definition of Done

- [ ] AC-1 bis AC-15 sind per Test und Mutations-Gegenprobe belegt (je Mutation protokolliert, welcher Test rot wurde)
- [ ] Sechs neue `hub-*`-Specs laufen für beide `kind`s grün gegen den CI-Stack; Altdateien erst danach gelöscht
- [ ] `E2E_MIN_EXECUTED_HAUPT` per `npx playwright test --list` neu gemessen, `E2E_MIN_SPECS` und Positivliste konsistent
- [ ] Wächter `ALTLAST`/`ALTLAST_MAX` auf den gemessenen Wert (erwartet 34) gesenkt, Wächter-Test grün
- [ ] CI-Ampel (6 Checks) grün, kein Produktcode geändert (oder Produktlücke nach AC-13-Muster dokumentiert)

## Known Limitations

- Trip-Verfügbarkeit von Reiterwechsel-Flush und 412 („Nochmal speichern") sowie die Zielzahlen für `E2E_MIN_EXECUTED_HAUPT` sind erst im RED/`/50` messbar.
- Quota: höchstens 2 aktive Vergleiche pro Nutzer; Registrierungsbremse 5/h/IP.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testschicht-Konsolidierung nach bestehender Vorgabe (Trip/Ortsvergleich-Code-Teilung, Epic #2345 P6); keine neue Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth).

## Changelog

- 2026-10-27: Initial spec created (S3a). Wächter-Rechnung 41 → 34 statt Briefing-Wert 35, weil `compare-editor-slice3` durch den `gz-eigenstaendig:`-Kopf konform wird und aus `ALTLAST` gestrichen werden muss (Befund 6).
