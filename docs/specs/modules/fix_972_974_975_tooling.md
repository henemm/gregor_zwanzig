---
entity_id: fix_972_974_975_tooling
type: module
created: 2026-07-02
updated: 2026-07-02
status: draft
version: "1.0"
tags: [tooling, validator, hooks, frontend-tests]
---

# Fix 972/974/975 — Tooling-Bugs (Validator-Tagesfenster, IMAP-Test-Creds, Frontend-Testbefehl)

## Approval

- [ ] Approved

## Purpose

Bündelfix für drei unabhängige Tooling-Defekte, die keinen Produktionscode berühren, aber
Validator- und Testinfrastruktur verlässlich machen: (A) der Tagesfenster-Check des
Briefing-Mail-Validators lehnt legitime Nachtstunden in der „Nacht am Ziel"-Sektion ab
(#974, Duplikat #915), (B) drei E2E-Hooks priorisieren die Test-IMAP-Credentials nicht und
prüfen dadurch versehentlich gegen das Produktiv-Postfach (#972), (C) der dokumentierte
Frontend-Testbefehl ruft ein nicht installiertes Tool (vitest) auf und meldet dadurch
fälschlich alle 284 „Testdateien" als fehlgeschlagen, obwohl 163 echte Unit-Tests real
bestehen (#975).

## Source

- **File:** `.claude/hooks/briefing_mail_validator.py`
  **Identifier:** `_check_plausibility()` (Zeile ~379-394), `fetch_latest_message()` (Zeile ~524-543, IMAP-Creds Zeile 540-541)
- **File:** `.claude/hooks/email_spec_validator.py`
  **Identifier:** `fetch_latest_email()` (IMAP-Creds Zeile 87-88)
- **File:** `.claude/hooks/e2e_browser_test.py`
  **Identifier:** (IMAP-Creds Zeile 132-133, in der Funktion die Playwright-Versand + IMAP-Fetch orchestriert)
- **File:** `frontend/package.json`
  **Identifier:** `scripts.test` (fehlt aktuell komplett)

> **Schicht-Hinweis:** Alle drei Teile sind **Tooling** (`.claude/hooks/`, Workflow-Gates,
> `frontend/package.json`-Scripts) — **kein** Produktionscode in `src/`, `api/`, `internal/`
> oder `frontend/src/`. Kein Konflikt mit der Frontend/Go-API/Python-Backend-Schicht-Regel.

## Estimated Scope

- **LoC:** ~55 (Teil A: ~15, Teil B: ~6, Teil C: ~4 in package.json + ggf. Doku-Zeilen in
  `docs/reference/mail_validators.md`, die nicht mitzählen)
- **Files:** 4 Code-/Config-Dateien (`briefing_mail_validator.py`, `email_spec_validator.py`,
  `e2e_browser_test.py`, `frontend/package.json`) + 1 optionale Doku-Aktualisierung
  (`docs/reference/mail_validators.md`, zählt nicht ins LoC-Limit)
- **Effort:** low

### Scope-Erweiterung Teil C (PO-Entscheid 2026-07-02, während TDD-RED)

Der Diagnose-Lauf des node:test-Runners deckte auf: **128 von 2017 Tests in 54 Testdateien
schlagen fehl** — überwiegend verrottete Design-Fidelity-/Dateiinhalt-Tests alter Issues
(nach heutiger CLAUDE.md-Regel ohnehin verboten), die nie routinemäßig liefen. Der PO hat
entschieden, die Alt-Tests **in diesem Bündel mit aufzuräumen**, damit AC-3 (Exit 0) ehrlich
erfüllt wird. Triage-Regeln:

1. **Test prüft Quellcode als Text** (grep/String-Assertions gegen `.svelte`/`.ts`-Dateiinhalt,
   alte Design-Fidelity-Checks) → **löschen** (regelwidrig nach „Dateiinhalt-Checks sind
   VERBOTEN", CLAUDE.md; Präzedenz: #893 verwaiste Tests entfernt).
2. **Test prüft echtes Verhalten** (reine Funktionen/Helpers) und scheitert an **veralteter
   Erwartung** (z.B. „METRIC_MAP hat genau 9 Einträge" bei inzwischen legitim mehr Metriken)
   → Erwartung an den heutigen, korrekten Stand anpassen — NUR wenn der heutige Stand
   nachweislich gewollt ist (Issue-/Commit-Referenz), sonst wie 3. behandeln.
3. **Test deckt eine echte Regression auf** → NICHT im Bündel fixen; als eigenes
   `type:bug`-Issue melden (Test bleibt dann vorerst rot → Datei einzeln ausweisen und
   PO informieren, bevor AC-3 als erfüllt gilt).
4. `frontend/test-lib-hooks.mjs` + `test-lib-loader.mjs` (Repo-Wurzel, aus #300): laufen
   grün mit — bleiben unangetastet.

Gelöschte Test-LoC zählen nicht als Feature-Code; das LoC-Limit bemisst sich am
Produktiv-/Tooling-Code (Teil A–C unverändert ~55 LoC).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src.app.config.Settings` (`src/app/config.py:99-100`) | Upstream | Stellt `test_imap_user`/`test_imap_pass` bereits bereit (GZ_TEST_IMAP_*), wird von allen drei Hooks importiert |
| `radar_alert_mail_validator.py:170-171` | Referenz-Pattern | Zeigt das korrekte Creds-Priorisierungsmuster (`test_imap_user or imap_user or smtp_user`), 1:1 auf die drei Hooks zu übertragen |
| Stalwart IMAP (`mail.henemm.com:993`) | Upstream (Infra) | Test-Postfach `gregor-test@henemm.com` — Ziel der korrigierten Creds-Priorität |
| `src/output/renderers/email/html.py:998-1022` | Upstream (gelesen, nicht geändert) | Rendert `🌙 Nacht am Ziel ({elev}m)` 2× (Desktop `<h3>` + Mobile-Block) — Marker-String für den Abschneide-Fix in Teil A |
| Renderer-Commit-Gate (#811) | Downstream | `briefing_mail_validator.py` ist Teil des Commit-Gates — jede Änderung an `_check_plausibility()` ändert Gate-Verhalten für künftige Commits |
| Post-Push-E2E-Pfad | Downstream | Alle drei Hooks laufen im Post-Push-Workflow gegen Staging; Teil B ändert, gegen welches Postfach geprüft wird |

## Implementation Details

### Teil A — Tagesfenster-Check ignoriert „Nacht am Ziel"-Sektion

In `_check_plausibility()` (`.claude/hooks/briefing_mail_validator.py:379-394`) wird der
Tagesfenster-Check (06–22 Uhr) nur noch auf den Teil des HTML angewendet, der **vor** dem
ersten Auftreten des Markers `Nacht am Ziel` liegt:

```
def _check_plausibility(html: str) -> list[str]:
    errors: list[str] = []
    ranges = _TEMP_RANGE_RE.findall(html)
    for lo_s, hi_s in ranges:
        lo, hi = int(lo_s), int(hi_s)
        if lo > hi:
            errors.append(f"FULL: Temperatur-Range unplausibel ({lo}°C > {hi}°C)")

    night_marker = html.find("Nacht am Ziel")
    day_html = html[:night_marker] if night_marker != -1 else html

    hours = _distinct_hours(day_html, html=True)
    for hour in hours:
        h = int(hour.split(":")[0])
        if h < 6 or h > 22:
            errors.append(f"FULL: Stunde {hour} ausserhalb Tagesfenster 06–22")

    return errors
```

Alle anderen Aufrufer von `_check_plausibility()` (Temperatur-Range-Check) bleiben auf dem
vollen HTML — nur die Stunden-Extraktion für den Fenster-Check wird auf `day_html`
umgestellt. `_has_hourly_table()`, `_check_rendered()` (AC-1), `_check_layer_consistency()`
(AC-3) und `_check_metric_plausibility()` (AC-4) in `_validate_full()` bleiben unverändert
auf dem vollen `html` — nur der Fenster-Check selbst wird eingeschränkt.

Fehlt der Marker (z.B. Trip ohne konfigurierte Nacht-Sektion oder Format ohne Nacht-Block),
bleibt `day_html == html` — Verhalten unverändert (kein Regressionsrisiko für Mails ohne
Nacht-Sektion).

### Teil B — IMAP-Test-Creds-Priorität in drei Hooks

Identische 2-Zeilen-Änderung an drei Stellen, exakt nach dem Referenz-Pattern aus
`radar_alert_mail_validator.py:170-171`:

```
imap_user = settings.test_imap_user or settings.imap_user or settings.smtp_user
imap_pass = settings.test_imap_pass or settings.imap_pass or settings.smtp_pass
if not imap_user or not imap_pass:
    raise ValueError("IMAP nicht konfiguriert (GZ_TEST_IMAP_USER/GZ_IMAP_USER)")
```

Betroffene Stellen:
- `.claude/hooks/briefing_mail_validator.py:540-541` (in `fetch_latest_message()`)
- `.claude/hooks/email_spec_validator.py:87-88` (in `fetch_latest_email()`)
- `.claude/hooks/e2e_browser_test.py:132-133`

Die Fehlermeldungstexte (aktuell `"IMAP nicht konfiguriert (GZ_IMAP_USER/GZ_IMAP_PASS)"` bzw.
in `e2e_browser_test.py` zusätzlich `"...oder GZ_SMTP_USER/GZ_SMTP_PASS"`) werden um
`GZ_TEST_IMAP_USER` ergänzt, damit ein Konfigurationsfehler in der neuen Priorität sofort
erkennbar ist.

### Teil C — Frontend-Testbefehl auf node:test umstellen

Root Cause verifiziert (siehe Context-Doc + eigener Check in dieser Spec-Phase, Node
`v22.22.2` installiert): Das Projekt hat **kein** vitest installiert (0 Treffer in
`package.json`/`package-lock.json`). Alle 163 Unit-Tests importieren `node:test`. `npx vitest`
matcht mit seinem Default-Glob sowohl `src/**/*.test.ts` (Unit) als auch `e2e/**/*.spec.ts`
(Playwright) — vitest kann aber keine `node:test`-Registrierungen einsammeln → „No test suite
found" pro Datei, während `node:test` die Tests beim reinen Modul-Import bereits selbst
ausführt (daher die scheinbar grünen TAP-Zeilen im verbose-Output trotz Exit 1).

Verifiziert in dieser Spec-Phase (Scratch-Reproduktion, zwei Dateien `src/foo.test.ts`
`node:test`-Import und `e2e/bar.spec.ts` `@playwright/test`-Import):
`node --experimental-strip-types --test` **ohne** Pfad-Argument, ausgeführt mit
`cwd=frontend/`, durchsucht rekursiv nach Node-Test-Runner-Default-Patterns
(`**/*.test.{js,mjs,cjs,ts,mts,cts}` u.ä.) und **matcht dabei `*.spec.ts` nicht** — die
Playwright-Specs unter `e2e/` werden also automatisch ausgeschlossen, ganz ohne
expliziten Glob oder Ausschlussliste. Exit-Code-Verhalten verifiziert: 0 bei
ausschließlich bestehenden Tests, 1 sobald ein Test real fehlschlägt (`assert.equal(1,2)`
in einer zusätzlichen Testdatei).

Fix — Ergänzung in `frontend/package.json` unter `"scripts"`:

```json
"test": "node --experimental-strip-types --test"
```

Kein `vitest`-Eintrag in `devDependencies`, kein Umschreiben der 163 bestehenden Testdateien,
kein `package-lock.json`-Diff nötig (keine neue Dependency).

## Expected Behavior

- **Input (Teil A):** Eine echte evening-Full-HTML-Mail mit Tages-Stundentabelle (06–22 Uhr)
  gefolgt von einer „Nacht am Ziel"-Sektion mit Stunden außerhalb 06–22 (z.B. 00, 02, 04).
  **Output:** `_check_plausibility()` liefert keinen Tagesfenster-Fehler mehr für die
  Nachtstunden. Eine Nachtstunde, die fälschlich **vor** dem Marker in der Tagestabelle
  steht, erzeugt weiterhin einen Fehler.
- **Input (Teil B):** `GZ_TEST_IMAP_USER`/`GZ_TEST_IMAP_PASS` und `GZ_IMAP_USER`/`GZ_IMAP_PASS`
  sind beide gesetzt (unterschiedliche Postfächer). **Output:** Alle drei Hooks verbinden sich
  mit dem Test-Postfach (`gregor-test@henemm.com`), nicht dem Prod-Postfach.
- **Input (Teil C):** `npm test` in `frontend/`. **Output:** Exit 0 bei bestehenden Tests,
  reale Pass-Anzahl > 0 in der TAP-Ausgabe, keine Playwright-Specs werden importiert/versucht.
- **Side effects:** Keine Laufzeit-Änderung an Produktionscode. Teil A/B ändern das Verhalten
  von Commit-/Deploy-Gates (strenger bzw. korrekter, nicht lockerer). Teil C ändert kein
  CI-Verhalten außerhalb des `frontend/`-Testbefehls.

## Acceptance Criteria

- **AC-1:** Given eine echte, frisch generierte evening-Full-Mail mit „Nacht am Ziel"-Sektion
  (Nachtstunden außerhalb 06–22) / When `briefing_mail_validator.py` gegen diese Mail läuft /
  Then meldet der Validator keinen „ausserhalb Tagesfenster"-Fehler für die Nachtstunden UND
  eine bewusst in die Tagestabelle vor dem Marker eingefügte Nachtstunde (z.B. 03:00) löst
  weiterhin genau diesen Fehler aus.
  - Test: Zwei Validator-Läufe gegen echtes HTML (einmal Original-Mail = Exit 0 für den
    Fenster-Check, einmal mit einer synthetisch vor den Marker verschobenen Nachtstunde =
    Fehler in der Fehlerliste) — kein Mock, echte HTML-Fixture aus dem Renderer-Output oder
    einer real zugestellten Mail.

- **AC-2:** Given `GZ_TEST_IMAP_USER`/`GZ_TEST_IMAP_PASS` und `GZ_IMAP_USER`/`GZ_IMAP_PASS`
  sind beide als Umgebungsvariablen gesetzt (unterschiedliche Werte) / When einer der drei
  Hooks (`briefing_mail_validator.py`, `email_spec_validator.py`, `e2e_browser_test.py`)
  seine IMAP-Verbindung aufbaut / Then wählt er die Test-Credentials, verbindet sich
  erfolgreich per echtem IMAP-Login gegen `mail.henemm.com:993` und selektiert `INBOX` des
  Test-Postfachs `gregor-test@henemm.com`.
  - Test: Echter IMAP-Login-Versuch (keine Mocks) mit den vom Hook ausgewählten Credentials;
    Login-Erfolg + `imap.select("INBOX")` ohne Fehler beweist, dass das richtige Konto
    getroffen wurde (verifizierbar z.B. über eine zuvor gezielt ins Test-Postfach gesendete
    Marker-Mail, die der Hook findet).

- **AC-3:** Given der ergänzte `"test"`-Befehl in `frontend/package.json` / When `npm test`
  (bzw. `npm run test`) im Verzeichnis `frontend/` ausgeführt wird / Then endet der Lauf mit
  Exit 0 und die TAP-Ausgabe weist eine reale Pass-Anzahl > 0 aus, ohne dass Playwright-Specs
  aus `e2e/` als Suiten importiert oder gemeldet werden.
  - Test: Echter `npm test`-Lauf im Terminal, Exit-Code-Prüfung (`$?`) plus Zählung der
    `# pass`-Zeile in der Runner-Ausgabe — kein Dateiinhalt-Check, sondern echtes
    Prozess-Exit-Verhalten.

- **AC-4:** Given eine echte, frisch versendete evening-Staging-Mail mit Nacht-Sektion /
  When `briefing_mail_validator.py --mail-type trip-briefing` gegen das Staging-Test-Postfach
  läuft (End-to-End, nach Deployment aller drei Teile) / Then endet der Validator-Lauf mit
  Exit 0.
  - Test: Realer Validator-Aufruf gegen die zugestellte Staging-Mail über IMAP (Test-Creds
    aus AC-2, Fensterlogik aus AC-1) — End-to-End-Nachweis, dass beide Fixes zusammen
    greifen.

## Known Limitations

- Teil A schneidet am **ersten** Auftreten von „Nacht am Ziel" ab — sollte der Marker-Text
  jemals umbenannt werden (Design-Änderung am Renderer), muss der Validator-String
  synchron mitgepflegt werden. Kein automatischer Kopplungstest zwischen Renderer-String und
  Validator-Marker in diesem Fix-Umfang.
- Teil A deckt nur den `_validate_full()`-Pfad ab (evening Full-Format); `compact`-Format hat
  keine Nacht-Sektion und ist nicht betroffen.
- Teil C behebt nur den fehlenden `test`-Befehl. Der bereits bekannte Nebenbefund „fehlendes
  `node_modules` im Worktree" (nur für E2E/Build relevant) wird hier **nicht** behoben — für
  reine `node:test`-Unit-Läufe nicht erforderlich.
- Teil B ändert nicht, wohin *Versand*-Läufe (SMTP) adressieren — nur die *Lese*-Seite (IMAP)
  der drei Validator-Hooks. Versand-seitige Test/Prod-Trennung ist bereits an anderer Stelle
  gelöst (Commit `552598c4`, `tests/e2e/test_e2e_friendly_format_config.py`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** Teil A/B: keine (isolierte Bugfixes ohne Richtungsentscheidung). Teil C:
  neues ADR `docs/adr/0013-node-test-frontend-unit-runner.md` wird in der
  Implementierungsphase angelegt (nicht Teil dieser Spec-Phase).
- **Rationale:** Teil C legt fest, dass `node --experimental-strip-types --test` der
  kanonische Frontend-Unit-Test-Runner ist und **kein** vitest verwendet wird — eine
  projektweite Richtungsentscheidung (verhindert künftige „vitest nachrüsten"-Vorschläge),
  die laut Projektkonvention ein ADR verdient. Teile A und B sind lokale Korrekturen an
  bestehendem Validator-/Hook-Verhalten ohne neue Architekturentscheidung.

## Changelog

- 2026-07-02: Initial spec created (Bündel #972/#974/#915/#975, Workflow
  `fix-972-974-975-tooling`)
