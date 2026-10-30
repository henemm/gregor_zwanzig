---
entity_id: i18n_f12_frontend_abschluss_2661
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2661, frontend, e2e, model-sonnet]
---

# i18n F12: Frontend-Abschluss — Allowlist leer, Playwright-E2E Sprachwechsel, Screenshot-Paare DE/EN

**Issue:** #2661 · **Epic:** #2644 · **Modell:** Sonnet · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitte 1, 3 (Ratsche Frontend), 6 (Playwright)

## Approval

- [ ] Approved

## Purpose

Phase 1 (Web-UI) ist erst fertig, wenn belegt ist, dass ein Nutzer die Sprache wechseln kann und danach keine Fläche mehr zwischen Deutsch und Englisch mischt. Dieses Paket schließt die Frontend-Ratsche (keine Allowlist-Einträge mehr), prüft den Sprachwechsel mit zwei Nutzern im Browser und erzeugt Screenshot-Paare DE/EN der sechs Hauptflächen, die ein unabhängiger Beobachter (`fresh-eyes-inspector`) auf Sprach-Mischung und abgeschnittene Texte ansieht. Gefundene Layout-Brüche werden als Nebenbefunde gemeldet, nicht hier behoben.

## Source

- **File:** `frontend/src/lib/i18n/hardcode_allowlist.json`, `frontend/e2e/sprachwechsel.spec.ts` (neu), `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml`
- **Identifier:** Testfälle der Spec `sprachwechsel.spec.ts` (Besucher-Wechsel, zwei Nutzer, Konto-Wechsel, Sprach-Mischung, Screenshot-Paare)

> **Schicht-Hinweis:** Frontend-Tests und Test-Konfiguration (`frontend/e2e`, `frontend/src/lib/i18n`, `.github`). Kein Produktivcode, kein Go-, kein Python-Code. Falls der Umschalter keinen stabilen Selektor hat, ist die einzige erlaubte Produktivänderung ein zusätzliches Attribut `data-testid="sprach-umschalter"` an `frontend/src/lib/components/ui/SprachUmschalter.svelte` (S3), kein Text.
>
> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Der Hub-Test läuft für beide Arten in einer Schleife über `HUB_KINDS` (`route`, `vergleich`) aus `frontend/e2e/helpers.ts`; es entsteht keine Spec je Hub. Reiter-Namen werden gegen dasselbe Glossar geprüft.
> - **Mandantentrennung:** Zwei echte Konten (`de` und `en`) mit echter Anmeldung; keine Annahme eines Standardnutzers, nie `default`. Nutzer A wechselt die Sprache, Nutzer B bleibt unverändert.
> - **Kanäle:** Berührt keine Briefing- oder Alarm-Inhalte; die Mail- und Telegram-Sprache beweist Paket A2 (#2681) auf Staging.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `frontend/src/lib/i18n/hardcode_allowlist.json` | MODIFY | Inhalt wird `[]` |
| `frontend/src/lib/i18n/__tests__/hardcode_allowlist_leer.test.ts` | CREATE | hält fest, dass die Allowlist leer bleibt (`# doc-compliance-test`) |
| `frontend/e2e/sprachwechsel.spec.ts` | CREATE | Besucher-Wechsel, zwei Nutzer, Konto-Wechsel, Sprach-Mischungs-Prüfung, Screenshot-Paare |
| `.github/ci_e2e_specs.txt` | MODIFY | Zeile `e2e/sprachwechsel.spec.ts` ergänzen (Positivliste, nur wachsend) |
| `.github/workflows/ci.yml` | MODIFY | `E2E_MIN_SPECS` um 1, `E2E_MIN_EXECUTED_HAUPT` um die gemessene Fallzahl erhöhen |
| `frontend/src/lib/components/ui/SprachUmschalter.svelte` | MODIFY | nur falls nötig: `data-testid="sprach-umschalter"` |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Zeile der Ratschen-Tabelle: Frontend-Allowlist ist leer |

## Estimated Scope

- **LoC:** ca. 230 Testcode (Spec ~190, Allowlist-Test ~25, Konfiguration ~15), kein Produktivcode
- **Files:** 6 (7 mit Umschalter-Attribut)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2650–#2660 (F1–F11) | Pakete | Alle Frontend-Migrationspakete sind gemergt; erst dann ist die Allowlist leerbar |
| #2648 S3 | Paket | Umschalter für Deutsch und Englisch (Besucher) und Konto-Auswahl „Sprache / Language“ |
| #2646 S1 | Paket | `language` am Nutzer; Registrierung nimmt `language` an, Go setzt Cookie `gz_lang` |
| `frontend/e2e/helpers.ts` | module | `createTestTrip`, `createTestLocation`, `createTestComparePreset`, `HUB_KINDS`, `HUB_SEL` |
| `frontend/e2e/passkey-angebot.spec.ts` | Vorbild | `legeKontoAn()` (Registrierung + Bestätigung), Kontingent 5 Registrierungen je IP und Stunde |
| `.claude/agents/fresh-eyes-inspector.md` | Agent | beurteilt Screenshots ohne Bug-Kontext |
| `docs/reference/i18n_glossar.md` | doc | Reiter-Namen: Wertebereiche = target ranges, Versand = delivery |
| ADR-0104 | adr | Sprache am Nutzer, Cookie für Besucher |

## Implementation Details

**1. Allowlist leer.** `frontend/src/lib/i18n/hardcode_allowlist.json` enthält nach F1–F11 nur noch Reste. Jeder Rest wird nicht gelöscht, sondern erst migriert (Ratschen-Meldung `Datei:Zeile` abarbeiten); am Ende steht exakt `[]`. Der neue Test `hardcode_allowlist_leer.test.ts` liest die Datei und verlangt `[]`. Ein Eintrag, der sich nicht entfernen lässt, ist ein Nebenbefund (#1199), nicht ein Grund, die Allowlist zu behalten. `npm run check` (svelte-check) muss grün sein.

**2. Spec `frontend/e2e/sprachwechsel.spec.ts`.** Läuft im Projekt `tests` der CI-Lane (`frontend/playwright.config.ts`, isolierter Stack, Port 8091), also ohne Suffix `.staging.`. Aufbau:

- `test.describe.serial`; im `beforeAll` genau **zwei** Konten über `POST /api/auth/register` mit Feld `language` (`de` bzw. `en`), Benutzernamen `e2e-gz-sprache-de` und `e2e-gz-sprache-en`, Passwort wie in `passkey-angebot.spec.ts`, Bestätigung nach dem Muster `legeKontoAn()` (lokal kopieren, nicht in `helpers.ts` auslagern, weil das fremde Specs berührt). Kontingent: 5 Registrierungen je IP und Stunde, diese Spec braucht 2.
- Anmeldung im Browser über das Formular `/login` (wie `global.setup.ts`), je Nutzer ein eigener `browser.newContext({ storageState: { cookies: [], origins: [] } })` mit `serviceWorkers: 'block'`.
- Je Nutzer legt die Spec über `createTestTrip` (mit einer Etappe), `createTestLocation` und `createTestComparePreset` Daten mit englisch-neutralen Namen an (`E2E-GZ-Sprache …`), damit Nutzertexte die Sprachprüfung nicht stören.
- **Sprach-Prüfung** (Hilfsfunktion `sichtbareZeilen(page)`): `document.body.innerText` zeilenweise, ohne Zeilen, die einen Nutzernamen oder `E2E-GZ-` enthalten. `DEUTSCH_WOERTER` (für englische Flächen): `Speichern`, `Abbrechen`, `Löschen`, `Anmelden`, `Registrieren`, `Einstellungen`, `Wertebereiche`, `Versand`, `Alarme`, `Vorschau`, `Zurück`, `Weiter`, `bitte`, `nicht`. `ENGLISCH_WOERTER` (für deutsche Flächen): `Cancel`, `Delete`, `Sign in`, `Settings`, `Save`, `Target ranges`, `Delivery`. Ein Wort, das die deutsche Oberfläche heute legitim enthält, wird vor dem Einchecken aus der Liste genommen (Messung am deutschen Ist-Stand), nie umgekehrt.
- **Positiv-Prüfung** über Spiegel-Prinzip: `enTextZu(deText)` lädt `frontend/src/lib/i18n/messages/de/*.json` und `en/*.json`, sucht den Schlüssel mit dem deutschen Text und liefert den englischen Wert. So bleibt die Spec unabhängig von Schlüsselnamen der F-Pakete. Zusätzlich fest nach Glossar: Hub-Reiter heißen auf Englisch `Target ranges` und `Delivery`.

**3. Testfälle.**

1. Besucher ohne Anmeldung öffnet `/login`, wählt `EN` am Umschalter: `html[lang="en"]`, der Anmelde-Knopf trägt `enTextZu('Anmelden')`, Cookie `gz_lang=en`, nach `page.reload()` weiterhin englisch; mit Wahl `DE` zurück zu deutsch.
2. Nutzer `en` meldet sich an: Cockpit (`/`) englisch, `html[lang="en"]`. In einem **zweiten, getrennten** Kontext meldet sich Nutzer `de` an: Cockpit deutsch. Beide Kontexte bleiben nebeneinander offen; danach lädt der erste neu und ist weiter englisch (kein Übertrag zwischen Nutzern).
3. Nutzer `en` öffnet `/account`, wählt unter „Sprache / Language“ `Deutsch`: Seite wird ohne Neuladen deutsch (`html[lang]` wird `de`, Navigation deutsch), nach Neuladen weiterhin deutsch; ein Gegenwechsel auf `English` stellt sie wieder her. Nutzer `de` in seinem Kontext bleibt die ganze Zeit deutsch.
4. Sprach-Mischung: Für beide Nutzer, beide Hubs (`for (const kind of HUB_KINDS)`) und die Flächen Start (ausgeloggt), Login, Cockpit, Trip-Hub, Compare-Hub, Konto gilt: englische Flächen enthalten kein Wort aus `DEUTSCH_WOERTER`, deutsche keines aus `ENGLISCH_WOERTER`.
5. Screenshot-Paare: je Fläche und Sprache zwei Bilder (375 px und 1280 px Breite), also 6 × 2 × 2 = 24 Dateien nach `../docs/artifacts/i18n-f12-frontend-abschluss/<flaeche>.<de|en>.<375|1280>.png` (Pfad mit `../`, sonst liegt das Bild unter `frontend/docs/artifacts/` und verletzt Filter C der Positivlisten-Aufnahme). Der Fall prüft nur, dass alle 24 Dateien existieren und nicht leer sind, und hängt eine Liste auffälliger Elemente (`scrollWidth > clientWidth` bei Knöpfen, Pillen, Reitern) als Anhang an den Testbericht. Er schlägt **nicht** an Layout-Brüchen an.

**4. Fresh-Eyes-Abnahme (Orchestrator, `/60-validate`).** Der `fresh-eyes-inspector` bekommt jedes der 24 Bilder einzeln, ohne Anlass, mit der Frage nach Sprache(n), gemischten Zeilen und abgeschnittenen Texten. Ergebnis: Tabelle Fläche × Sprache × Breite mit Urteil; keine deutsche Zeile in `en`-Bildern ist Abnahmebedingung. Layout-Brüche (längere englische Wörter) kommen als Kommentar in das Sammel-Issue #1199 und in den Epic #2644, ohne Korrektur hier.

**5. Positivliste und Zähler.** Aufnahme nur nach Filter A (kein `waitForTimeout`, kein `test.skip`, kein `.staging.`), Filter B (drei grüne Läufe im Zielverbund der Positivliste, nicht allein) und Filter C (die Spec schreibt keine versionierte Datei). `.github/ci_e2e_specs.txt` bekommt die Zeile `e2e/sprachwechsel.spec.ts`; in `ci.yml` steigt `E2E_MIN_SPECS` um 1 (Stand 2026-10-30: 73) und `E2E_MIN_EXECUTED_HAUPT` um die per `npx playwright test --list` gemessene Fallzahl der Spec (Stand 2026-10-30: 549; nicht addiert, sondern am zusammengeführten Stand nachgemessen).

## Expected Behavior

- **Input:** Browser-Läufe gegen den isolierten CI-Stack mit zwei frisch registrierten Konten (`language` `de` bzw. `en`), ein ausgeloggter Besucher, ein Wechsel am Umschalter und in den Konto-Einstellungen.
- **Output:** Grüne Spec; 24 Screenshot-Dateien unter `docs/artifacts/i18n-f12-frontend-abschluss/`; Allowlist `[]`; Fresh-Eyes-Tabelle ohne deutsche Zeile in englischen Bildern.
- **Side effects:** Zwei Testkonten und deren Testdaten in der flüchtigen Datenwurzel des CI-Stacks (kein Eingriff in Staging oder Produktion). Kein Schreiben in versionierte Dateien außer den oben genannten Konfigurationen.

## Acceptance Criteria

- **AC-1:** Given alle Frontend-Pakete F1–F11 sind gemergt / When die Frontend-Tests laufen / Then ist die Ratsche ohne Allowlist-Eintrag grün, die Allowlist-Datei lautet exakt `[]`, und `svelte-check` meldet keinen Fehler.
  - Test: `frontend/src/lib/i18n/__tests__/hardcode_allowlist_leer.test.ts` zusammen mit `keine_hartkodierten_nutzertexte.test.ts` und `npm run check` (`# doc-compliance-test`: Ratschen-Test, kein Verhaltensnachweis).

- **AC-2:** Given ein Besucher ohne Anmeldung auf `/login` / When er am Umschalter `EN` wählt und die Seite neu lädt / Then ist die Seite englisch (`html[lang="en"]`, Anmelde-Knopf mit dem englischen Katalogtext), das Cookie `gz_lang` steht auf `en`, und die Wahl `DE` stellt Deutsch wieder her.
  - Test: `frontend/e2e/sprachwechsel.spec.ts` Fall 1 — echter Browser gegen den CI-Stack, Erwartungswert über das Spiegel-Prinzip aus den Katalogdateien.

- **AC-3:** Given Nutzer `en` und Nutzer `de` sind in zwei getrennten Browser-Kontexten gleichzeitig angemeldet / When beide das Cockpit öffnen und einer neu lädt / Then sieht `en` Englisch und `de` Deutsch, und kein Kontext übernimmt die Sprache des anderen.
  - Test: `frontend/e2e/sprachwechsel.spec.ts` Fall 2 — zwei echte Konten, zwei Kontexte, Prüfung von `html[lang]` und sichtbaren Zeilen.

- **AC-4:** Given Nutzer `en` ist angemeldet auf `/account` / When er die Sprache auf Deutsch stellt / Then wird die Seite sofort deutsch (ohne Neuladen), bleibt nach dem Neuladen deutsch, der Gegenwechsel stellt Englisch wieder her, und Nutzer `de` bleibt unberührt.
  - Test: `frontend/e2e/sprachwechsel.spec.ts` Fall 3 — Wechsel über die Konto-Auswahl „Sprache / Language“, danach `page.reload()`, zweiter Kontext bleibt deutsch.

- **AC-5:** Given die sechs Flächen Start, Login, Cockpit, Trip-Hub, Compare-Hub und Konto in beiden Sprachen / When ihre sichtbaren Zeilen (ohne Nutzernamen und Testdaten) gelesen werden / Then enthalten englische Flächen kein deutsches Signalwort, deutsche kein englisches, und die Hub-Reiter heißen auf Englisch `Target ranges` und `Delivery`.
  - Test: `frontend/e2e/sprachwechsel.spec.ts` Fall 4 — Schleife über beide Hub-Arten (`HUB_KINDS`) und beide Nutzer, Prüfung gegen `DEUTSCH_WOERTER` und `ENGLISCH_WOERTER`.

- **AC-6:** Given die 24 Screenshot-Dateien (6 Flächen × 2 Sprachen × 375 und 1280 px) / When der `fresh-eyes-inspector` jedes Bild ohne Kontext beurteilt / Then meldet er in keinem englischen Bild eine deutsche Zeile, und abgeschnittene oder umgebrochene Texte stehen als Nebenbefund in #1199, nicht als Fehler dieses Pakets.
  - Test: `frontend/e2e/sprachwechsel.spec.ts` Fall 5 (alle 24 Dateien vorhanden und nicht leer) plus Fresh-Eyes-Verdict im Kommentar zu #2661; kein Dateiinhalts-Check.

- **AC-7:** Given die gemergte Positivliste / When der CI-Check `e2e` läuft / Then führt er `sprachwechsel.spec.ts` mit aus, die Zähler `E2E_MIN_SPECS` und `E2E_MIN_EXECUTED_HAUPT` stimmen exakt mit der Messung überein, und die Spec ist in drei aufeinanderfolgenden Läufen grün.
  - Test: CI-Check `e2e` (Hauptlauf) und die Ratschen-Schritte der Positivliste in `.github/workflows/ci.yml` (`# doc-compliance-test`: Zählratsche).

## Known Limitations

- Annahme: Die Spec läuft in der CI-Lane gegen den lokalen Stack; der Nachweis gegen Staging und die Mail- und Telegram-Sprache liefert A2 (#2681), das dieselbe Spec in `/e2e-verify` aufnimmt.
- Annahme: Der Umschalter ist per Rolle und Name `EN`/`DE` erreichbar; fehlt ein stabiler Selektor, ergänzt F12 nur `data-testid="sprach-umschalter"`.
- Annahme: Die Wortlisten `DEUTSCH_WOERTER` und `ENGLISCH_WOERTER` sind absichtlich kurz und eindeutig; sie beweisen Mischung, nicht Vollständigkeit der Übersetzung. Die Vollständigkeit sichern Ratsche und Paritätstest, das Gesamtbild das Fresh-Eyes.
- Die Registrierung ist auf 5 Versuche je IP und Stunde begrenzt; eine andere Spec im selben Job, die Konten anlegt, kann das Kontingent aufbrauchen (Filter B im Zielverbund misst das).
- Layout-Brüche durch längere englische Wörter werden nur gemeldet. Das Behebungs-Issue entsteht aus der Triage von #1199.
- Screenshots unter `docs/artifacts/` sind nicht versioniert; der Nachweis ist der Kommentar mit der Verdict-Tabelle.
- Die Frontend-Tests laufen mit `node --test` (`npm test` in `frontend/`), nicht mit Vitest; die Konventionen sprechen von „Vitest“ und meinen diesen Testläufer.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Die Sprache gehört dem Nutzer, der Besucher-Umschalter ist nur das Vorfeld; der Abschluss muss beides und die Trennung zweier Nutzer aus Nutzersicht belegen.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
