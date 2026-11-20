---
entity_id: e2e_seriell_haupt_suite
type: bugfix
created: 2026-11-20
updated: 2026-11-20
status: draft
version: "1.0"
workflow: fix-3137-e2e-sprache-isolieren
tags: [e2e, playwright, testinfrastruktur, "#3137", "#1196"]
---

# E2E-Haupt-Suite immer seriell (Sprach-/Zustandsisolation)

## Approval

- [ ] Approved

## Purpose

Die Playwright-Haupt-Suite soll in jeder Umgebung (lokal wie CI) mit genau einem Worker laufen. Ein lokaler Lauf ohne `CI=1` startet sonst zwei Worker, die dasselbe Admin-Konto teilen; ein Sprach-Umschalter auf `en` in einem Worker kippt dann die Anzeige eines gleichzeitig laufenden Falls (Issue #3137, DS-2 zeigte `01/08/2027` statt `01.08.2027`). Ein Wächter im Setup verhindert, dass ein Parallel-Lauf per `--workers=N` unbemerkt wieder dieselbe Klasse von Wacklern erzeugt.

## Source

- **File:** `frontend/playwright.config.ts`
- **Identifier:** Konfigurationsschlüssel `workers`; Wächter in `frontend/e2e/global.setup.ts`

> Schicht: Test-Infrastruktur im Frontend-Verzeichnis (`frontend/`), kein Produktcode in Go-API oder Python-Core.
> Trip/Ortsvergleich-Teilung, Mandantentrennung, Kanäle: nicht betroffen (keine Produktänderung, keine Nutzerdaten, keine Briefing-Inhalte).

## Estimated Scope

- **LoC:** ca. +15/-2
- **Files:** 3 (plus Test-Nachweis im Rahmen von /40-tdd-red)
- **Effort:** low

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/playwright.config.ts` | MODIFY | `workers: 1` unbedingt statt `process.env.CI ? 1 : undefined`; Kommentar mit Verweis #3137 |
| `frontend/e2e/global.setup.ts` | MODIFY | Wächter: bricht bei `testInfo.config.workers > 1` mit klarer Meldung ab (fängt auch `--workers=N`) |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Ein Satz: Haupt-Suite läuft immer seriell, Grund |

### Nicht-Ziele

- Keine Änderung an Produktcode (Go-API, Python-Core, SvelteKit-Seiten) und keine Änderung an einzelnen Testfällen.
- Kein Wegwerf-Konto je Sprach-Test, keine Umstellung der 26 Sprach-Umschalter-Dateien.
- Staging-Einzel-Configs (`playwright.*.staging.config.ts`) mit eigenem `workers`-Wert bleiben unverändert.
- CI-Ablauf (`ci.yml`) und Fallzahl-Ratsche `E2E_MIN_EXECUTED_HAUPT` bleiben unverändert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/playwright.config.ts` | config | Quelle der Worker-Anzahl |
| `frontend/e2e/global.setup.ts` | Setup-Projekt | läuft vor allen Projekten (`tests`, `pwa`), Ort des Wächters |
| `.github/workflows/ci.yml` | CI | setzt `CI: "1"`; Verhalten bleibt unverändert (war schon seriell) |
| `E2E_MIN_EXECUTED_HAUPT` (Fallzahl-Ratsche) | Ratsche | zählt `global.setup` mit; Wächter im selben Setup-Fall, Zahl bleibt unverändert |
| `frontend/e2e/ci-stack.sh`, `run-passkey-login.sh` | Skripte | nutzen die Haupt-Config, werden lokal seriell |

## Implementation Details

1. `playwright.config.ts`: `workers: 1` ohne Bedingung. Kommentar benennt Ursache (geteiltes Admin-Konto, Seed-IDs `e2e-loc-*`, gemeinsame Datenwurzel; #1771 S2, #3137).
2. `global.setup.ts`: Im bestehenden Setup-Fall zu Beginn prüfen, ob `testInfo.config.workers > 1`. Wenn ja: Abbruch mit Fehlermeldung, die (a) den Grund nennt (Tests teilen Admin-Konto und Datenwurzel, ein Parallel-Lauf verfälscht z. B. die Sprache) und (b) die Abhilfe nennt (ohne `--workers` starten bzw. `--workers=1`). Der Wächter ist kein eigener Testfall, damit die Fallzahl-Ratsche nicht berührt wird.
3. Doku: ein Satz in `docs/reference/gates_und_ratschen.md`.

Verworfene Alternativen: Wegwerf-Konto je Sprach-Test (26 Dateien betroffen, Ratenbremse 429 nach 5 Registrierungen je IP, Seed-IDs blieben trotzdem geteilt); `test.describe.configure({mode:'serial'})` (wirkt nur innerhalb einer Datei, nicht zwischen Workern).

Nicht im Scope: Staging-Einzel-Configs (`playwright.*.staging.config.ts`) mit eigenem `workers`-Wert, insbesondere `playwright.1743-f002` und `playwright.2794-s3a2` mit `workers: 2`; sie haben eigene Konfiguration und eigenen Datenbestand.

## Expected Behavior

- **Input:** Aufruf der Haupt-Suite (`npx playwright test ...`) mit oder ohne `CI`-Variable, mit oder ohne `--workers=N`.
- **Output:** Ohne Override genau ein Worker; mit `--workers>1` Abbruch im Setup mit erklärender Meldung, bevor ein fachlicher Test läuft.
- **Side effects:** Lokale Volläufe werden langsamer; CI unverändert.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1 (AC-1): GIVEN `CI` nicht gesetzt / WHEN `npx playwright test --project=setup` ohne Override / THEN Lauf meldet 1 Worker und das Setup ist grün (heute auf diesem 4-Kern-Server 2 Worker).
- [ ] Test 2 (AC-2): GIVEN `CI` nicht gesetzt / WHEN `npx playwright test --project=setup --workers=2` / THEN Lauf ist rot mit Meldung zu Grund und Abhilfe (heute grün, kein Schutz).
- [ ] Test 3 (AC-3): GIVEN `CI=1` / WHEN `npx playwright test --project=setup` / THEN grün, 1 Worker, Fallzahl unverändert.
- [ ] Test 4 (AC-4): GIVEN Haupt-Suite mit DS-2 und einem `en`-Umschalter / WHEN lokal ohne `CI` gestartet / THEN DS-2 bleibt grün (kein Parallelbetrieb mehr).

## Acceptance Criteria

- **AC-1:** Given die Haupt-Suite wird ohne gesetzte CI-Variable gestartet und ohne `--workers`-Angabe / When der Setup-Lauf (`--project=setup`) ausgeführt wird / Then läuft er mit genau einem Worker und ist grün.
  - Test: Playwright-Lauf ohne `CI`, Ausgabe zeigt "1 worker" (vorher "2 workers" auf dem 4-Kern-Server).

- **AC-2:** Given die Haupt-Suite wird mit `--workers=2` gestartet / When das Setup-Projekt läuft / Then bricht der Lauf sofort ab und die Fehlermeldung nennt verständlich den Grund (geteiltes Admin-Konto und Datenwurzel, Parallel-Läufe verfälschen z. B. die Sprache) und die Abhilfe (ohne `--workers` bzw. mit `--workers=1` starten).
  - Test: Playwright-Lauf `--project=setup --workers=2` ist rot, die Meldung enthält Grund und Abhilfe; derselbe Lauf ohne Override ist grün.

- **AC-3:** Given ein CI-artiger Lauf mit gesetzter CI-Variable / When die Haupt-Suite oder das Setup-Projekt läuft / Then bleibt das Verhalten unverändert (ein Worker, grün) und die Fallzahl-Ratsche `E2E_MIN_EXECUTED_HAUPT` bleibt ohne Änderung ihres Werts erfüllt.
  - Test: Playwright-Lauf mit `CI=1` zeigt 1 Worker und dieselbe Fallzahl wie vorher; `E2E_MIN_EXECUTED_HAUPT` in `ci.yml` ist unverändert.

- **AC-4:** Given ein lokaler Lauf ohne CI-Variable auf dem isolierten E2E-Stack / When der Fall DS-2 "Rückkehr ins fertige Segment" zusammen mit den Sprach-Umschaltern der übrigen Dateien läuft / Then zeigt DS-2 das Datum deutsch (`01.08.2027`) und bleibt grün.
  - Test: Playwright-Lauf von `design-system-trip-vergleich.spec.ts` plus mindestens einem `en`-Umschalter (z. B. `sprachwechsel`) ohne `CI`, ohne Override, ist grün.

- **AC-5:** Given ein Entwickler liest die Test-Doku / When er die Regeln zur Haupt-Suite nachschlägt / Then steht in `docs/reference/gates_und_ratschen.md` ein Satz, dass die Haupt-Suite immer seriell läuft und warum (geteiltes Konto, Seed-IDs, Datenwurzel).
  - Test: doc-compliance-test mit Marker `# doc-compliance-test` (reine Doku-Zusicherung, kein Verhaltensnachweis).

## Definition of Done

- `workers: 1` gilt in der Haupt-Config unbedingt; der Wächter im Setup bricht Parallel-Läufe mit verständlicher Meldung ab.
- AC-1 bis AC-4 durch echte Playwright-Läufe belegt (vorher rot bzw. 2 Worker, nachher wie gefordert), AC-5 per doc-compliance-test.
- CI-Job `e2e` grün mit unveränderter Fallzahl-Ratsche.

## Known Limitations

- Lokale Volläufe sind langsamer (ein Worker statt zwei).
- Staging-Einzel-Configs mit eigenem `workers`-Wert (u. a. zwei mit `workers: 2`) sind ausdrücklich nicht Teil dieser Änderung.
- Der Wächter greift nur im Setup-Projekt; Läufe, die das Setup-Projekt nicht auslösen, sind nicht geschützt (alle Haupt-Projekte hängen davon ab).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Konfigurationsangleichung lokal an CI (#1771 S2 galt dort schon); keine neue Entscheidungsfläche, keine Abweichung von einem bestehenden ADR.

## Changelog

- 2026-11-20: Initial spec created (Issue #3137, Epic #1196)
- 2026-11-20: Pflicht-Sektionen Scope (mit Nicht-Zielen) und Definition of Done ergänzt
