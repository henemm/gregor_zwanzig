# Context: fix-3137-e2e-sprache-isolieren

## Request Summary
Issue #3137 (Epic #1196 Testsuite-Sanierung): Der Playwright-Fall „DS-2 Rückkehr ins fertige
Segment" (`frontend/e2e/design-system-trip-vergleich.spec.ts:849`) war in einem lokalen Lauf auf
dem isolierten CI-Stack einmal rot: erwartet `01.08.2027`, erhalten `01/08/2027` (englisches
Format), obwohl der Fall vorher `setzeSprache(page, 'de')` aufruft. Einzeln wiederholt grün.

## Befunde

### Sprachauflösung (warum ein fremder Test die Anzeige umstellen kann)
- `frontend/src/routes/+layout.server.ts:16-31`: Sprache = Profil (`/api/auth/profile`, Feld
  `language`) > `locals.lang` (Cookie/Accept-Language aus `hooks.server.ts`). Bei jedem
  Server-Load frisch aus dem Profil; kein Client-Cache.
- `setzeSprache` (`design-system-trip-vergleich.spec.ts:482`) = `PUT /api/auth/profile
  {language}` am **gemeinsamen Admin-Konto** (`storageState: playwright/.auth/admin.json`,
  `playwright.config.ts:47/63`).
- Folge: Sequenziell ist DS-2 sicher (setzt selbst `de`, alle Umschalter setzen im `finally`
  zurück). Nur ein **gleichzeitig** laufender Test, der dasselbe Konto auf `en` stellt, kann
  zwischen `setzeSprache('de')` und `openHub` die Anzeige kippen.

### Parallelität
- `frontend/playwright.config.ts:20-22`: `workers: process.env.CI ? 1 : undefined` — Kommentar
  #1771 S2: „Tests teilen dieselbe Datenwurzel und Seed-IDs, Parallel-Läufe würden sich stören".
- `.github/workflows/ci.yml:417/466/498`: CI-Schritte setzen `CI: "1"` ⇒ in der CI ein Worker,
  auch im Filter-B-Dreifachlauf (3 Zyklen **hintereinander**, ci.yml:219).
- `frontend/e2e/ci-stack.sh`: startet nur den Stack; ein lokaler Lauf ohne `CI=1` läuft mit
  Playwright-Standard (halbe Kernzahl, hier 2 Worker) — das passt zum Befund aus #3007
  („lokaler isolierter CI-Stack").
- Wahrscheinliche Ursache damit: lokaler Parallel-Lauf, nicht CI. Zu bestätigen in der Analyse
  (gezielter Paralleler Lauf DS-2 + ein `en`-Umschalter).

### Betroffene Sprach-Umschalter am gemeinsamen Konto
26 Dateien in `frontend/e2e/` stellen `language` per Profil um (u. a. `sprachwechsel`,
`s3a2794-teil3-englisch`, `s3b2795-zustellung-englisch`, `s2981-vorlage-name-en`,
`anlegen-helfer-sprachneutral`, `trip-hub-etappenliste-titel`, `was-steht-wo-karte`,
`design-system-trip-vergleich` selbst mit DS-1/DS-2/DS-3 `en`). Einzel-Isolierung aller Fälle
wäre ein großer Umbau.

## Existing Patterns
- Frisches Wegwerf-Konto je Test: DS-5 leer (`design-system-trip-vergleich.spec.ts:185ff`,
  `leeresKonto(...)` + `browser.newContext({storageState})`), `helpers.ts:235
  registriereBestaetigtenZweitnutzer`. Achtung Ratenbremse: 429 nach 5 Registrierungen je IP
  (Memory), daher Zufalls-IP-Header.
- Serielle Ausführung: `workers: 1` in CI (#1771 S2).

## Dependencies
- Upstream: Go `PUT /api/auth/profile`, SvelteKit-Layout-Load.
- Downstream: alle Playwright-Läufe (CI-Job `e2e`, lokale Läufe durch Agenten in `/50-implement`,
  `/60-validate`, Staging-Configs `playwright.*.staging.config.ts` — eigene Configs mit eigener
  `workers`-Angabe prüfen).

## Existing Specs
- Keine Modul-Spec für die Playwright-Konfiguration; ADR zur Teststrategie in `docs/adr/` prüfen.

## Risks & Considerations
- `workers: 1` auch lokal macht lokale Volläufe langsamer, beseitigt aber die ganze Klasse
  (Sprache, Seed-IDs, Datenwurzel) — konsistent mit CI.
- Per-Test-Konten für 26 Dateien: hoher Aufwand, Ratenbremse, verfehlt die übrigen geteilten
  Zustände (Seed-IDs) trotzdem.
- Nachweis muss den Fehler vorher rot zeigen (parallel provoziert), nicht nur Konfig-Text prüfen
  (Dateiinhalt-Checks sind als Verhaltensnachweis verboten).

## Analysis

### Type
Bug (Test-Infrastruktur, wackelnder E2E-Fall; kein Produktfehler)

### Ursache (bestätigt)
- Server hat `nproc=4` ⇒ Playwright-Standard ohne `CI` = 2 Worker. Der Befund aus #3007 stammt aus
  einem lokalen Lauf auf dem isolierten CI-Stack **ohne** `CI=1` ⇒ zwei Worker teilen sich das
  Admin-Konto; ein `en`-Umschalter in Worker B kippt die Anzeige von DS-2 in Worker A zwischen
  `setzeSprache('de')` und dem Seitenaufruf.
- Die CI selbst setzt `CI: "1"` ⇒ `workers: 1`; dort tritt der Fehler nicht auf (Filter B =
  drei Zyklen hintereinander, nicht parallel). Die Sorge im Issue („kann in der CI wieder
  auftreten") trifft nicht zu, solange die CI seriell läuft.
- Die 20+ Staging-Configs setzen bereits fast alle `workers: 1` ausdrücklich; nur die
  Haupt-Config macht es von `CI` abhängig. Ausnahmen mit `workers: 2`: `playwright.1743-f002`
  und `playwright.2794-s3a2` (Staging-Einzel-Configs, eigener Datenbestand — nicht im Scope,
  nur prüfen, ob sie Sprache umstellen).
- Es ist nicht nur die Sprache: dieselbe Klasse betrifft Seed-IDs und die gemeinsame
  Datenwurzel (#1771 S2). Die Lösung muss die Klasse beseitigen, nicht 26 Dateien einzeln.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/playwright.config.ts | MODIFY | `workers: 1` unbedingt (lokal = CI), Kommentar #3137 |
| frontend/e2e/global.setup.ts | MODIFY | Wächter: bricht mit klarer Meldung ab, wenn `testInfo.config.workers > 1` (fängt auch `--workers=N` auf der Kommandozeile) |
| docs/reference/gates_und_ratschen.md (oder operations_playbook) | MODIFY | ein Satz: Haupt-Suite läuft immer seriell, Grund |

### Scope Assessment
- Files: 2–3
- Estimated LoC: +15/-2
- Risk Level: LOW (nur Testlauf-Konfiguration; CI-Verhalten unverändert, lokale Volläufe langsamer)

### Technical Approach
Empfehlung: Haupt-Suite immer seriell (`workers: 1`) plus Wächter im Setup-Projekt, der jeden
Parallel-Lauf (auch per CLI-Override) sofort mit verständlicher Meldung stoppt. Begründung:
beseitigt die ganze Klasse geteilter Zustände (Sprache, Seed-IDs, Datenwurzel) mit minimalem
Eingriff, gleicht lokal und CI an (etablierte Praxis: Testumgebung = CI-Umgebung). Verworfen:
Wegwerf-Konto je Sprach-Test (26 Dateien, Ratenbremse 5 Registrierungen/IP, Seed-IDs bleiben
geteilt) und `test.describe.configure({mode:'serial'})` je Datei (wirkt nur innerhalb einer
Datei, nicht zwischen Workern).

### Nachweis (RED)
- Verhaltensnachweis über den Wächter: `npx playwright test --project=setup --workers=2`
  ⇒ heute grün (kein Schutz) → nach Fix rot mit Meldung; ohne Override grün.
- Ergänzend in /40-tdd-red: Setup-Lauf ohne `CI` muss `workers=1` melden (heute 2 auf diesem
  Server) — über den Wächter beobachtbar, kein Dateiinhalt-Check.

### Dependencies
- Lokale Läufe durch Agenten in /50-implement, /60-validate, ci-stack.sh, run-passkey-login.sh
  (nutzt die Haupt-Config) — werden seriell, sonst unverändert.
- CI-Job `e2e`: unverändert (war schon seriell); Fallzahl-Ratsche `E2E_MIN_EXECUTED_HAUPT`
  zählt global.setup mit — Wächter im selben Setup-Fall ändert die Zahl nicht.

### Open Questions
- keine (reine Testinfrastruktur, keine Produktentscheidung)
