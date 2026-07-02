# Context: fix-972-974-975-tooling

## Request Summary

Bündel dreier Tooling-Bugs (kein Produktionscode): (a) #974/#915 — der Tagesfenster-Check
des Briefing-Mail-Validators lehnt legitime „🌙 Nacht am Ziel"-Stunden 00/02/04 ab;
(b) #972 — drei E2E-Hooks prüfen gegen das Prod- statt das Test-Postfach, weil
`test_imap_user` nicht priorisiert wird; (c) #975 — die Frontend-Vitest-Suite meldet
alle 284 Testdateien als FAIL (Exit 1), obwohl die Tests real bestehen.

## Issue-Verhältnis

- **#915 ist ein Duplikat von #974** (gleicher Fehler, #974 hat die korrekte Root Cause:
  „Nacht am Ziel"-Sektion, nicht Folgetag-Forecast). Beide werden mit einem Fix geschlossen.
- **#972 ist zu 1/4 erledigt:** Commit `552598c4` fixte nur
  `tests/e2e/test_e2e_friendly_format_config.py`. Die drei Hooks sind noch offen.

## Related Files

| File | Relevance |
|------|-----------|
| `.claude/hooks/briefing_mail_validator.py:379-394` | `_check_plausibility()` — Tagesfenster-Check 06–22 (#974); Zeile 540: IMAP-Creds ohne Test-Priorität (#972) |
| `.claude/hooks/briefing_mail_validator.py:51-90` | `_distinct_hours()` — Hour-Extraktion (data-label="Time"-Anker, #928-Logik) |
| `.claude/hooks/email_spec_validator.py:87-88` | IMAP-Creds ohne Test-Priorität (#972) |
| `.claude/hooks/e2e_browser_test.py:132-133` | IMAP-Creds ohne Test-Priorität (#972) |
| `.claude/hooks/radar_alert_mail_validator.py:170-171` | **Referenz-Pattern** (korrekt): `settings.test_imap_user or settings.imap_user or settings.smtp_user` |
| `src/app/config.py:99-100` | `Settings.test_imap_user/test_imap_pass` existieren bereits (GZ_TEST_IMAP_*) |
| `src/output/renderers/email/html.py:998-1022` | Nacht-Sektion: Header `🌙 Nacht am Ziel ({elev}m)` wird ZWEIMAL gerendert (Desktop `<h3>` + Mobile-Block) |
| `src/formatters/trip_report.py::_get_night_weather` | `night_dps`-Fenster: `(same_day and h >= arrival_hour) or (next_day and h <= 6)` — nur evening-Reports |
| `frontend/package.json` | **vitest fehlt komplett** (kein devDependency, kein `test`-Script, kein Binary in node_modules/.bin) — Kern von #975 |
| `frontend/vite.config.ts` | Einzige Vite-Config; keine vitest.config.*, kein Workspace-File |
| `tests/tdd/test_issue_733_briefing_mail_validator.py` | Vorbild für Validator-Selbsttests (TDD-Pattern) |
| `docs/reference/mail_validators.md` | Doku der Plausibilitäts-Schwellen — muss nach Fix aktualisiert werden |

## Existing Patterns

- **IMAP-Creds-Priorität:** `radar_alert_mail_validator.py:170f` ist das PO-bestätigte Muster
  (Memory: Test-Creds priorisieren). Alle drei Hooks laden dieselbe `Settings`-Klasse —
  der Fix ist je 2 Zeilen, identisch.
- **Validator-Plausibilität „weit kalibriert gegen False-Positives"**
  (`briefing_mail_validator.py:380`, `docs/reference/mail_validators.md:59`): der
  Nacht-Fix darf tolerant sein, solange er die Prüfschärfe der regulären Tagestabelle erhält.
- **Nacht-Sektion:** kommt nur bei evening-Full-Mails vor; Marker-String `Nacht am Ziel`
  taucht 2× im HTML auf (Desktop + Mobile). Reines Abschneiden am ersten Auftreten ist
  möglich (Nacht-Sektion + Gewitter-Ausblick + Footer folgen danach); Alternative:
  Fenster 00–06 zusätzlich erlauben, wenn `Nacht am Ziel` im HTML vorhanden ist.

## #975 Vitest — Root Cause (Explore-Agent, verifiziert)

**Das Projekt nutzt kein Vitest.** Die Issue-Vermutung „Versions-Inkompatibilität" ist widerlegt:

- `vitest` kommt in `frontend/package.json` und `package-lock.json` **0-mal** vor;
  die „4.1.9" ist nur das, was `npx` ad-hoc herunterlädt.
- Die 284 „Test-Dateien" = **163 Unit-Tests** (`src/**/*.test.ts`, alle
  `import { test } from 'node:test'` — 0 Dateien importieren `vitest`) + **121
  Playwright-E2E-Specs** (`e2e/**/*.spec.ts`). Vitests Default-Glob matcht beide.
- Symptom-Erklärung: Vitest importiert jede Datei; die `test()`-Aufrufe registrieren
  sich beim `node:test`-Runner statt bei Vitest → „No test suite found" ×284, Exit 1.
  Gleichzeitig führt `node:test` die Tests beim Import selbst aus → die grünen
  TAP-Zeilen (`# tests 61 / # pass 61`) im verbose-Output stammen von node:test.
- Vorgesehener Runner ist dokumentiert, z.B. `frontend/src/lib/contrast-audit.test.ts:17-23`
  und `docs/specs/tests/issue_377_contrast_audit_tests.md:60`:
  `node --experimental-strip-types --test src/...`
- **Minimaler Fix:** `"test"`-Script in `frontend/package.json` auf den node:test-Runner
  (z.B. `node --experimental-strip-types --test 'src/**/*.test.ts'`), Issue-Doku
  korrigieren. KEINE Vitest-Installation, KEIN Umschreiben der 163 Tests.
- Nebenbefund: `node_modules` fehlt im Worktree (nur für E2E/Build relevant, nicht
  für node:test-Unit-Läufe — die brauchen kein node_modules).

## Dependencies

- Upstream: `Settings` (pydantic, `src/app/config.py`); IMAP Stalwart `mail.henemm.com:993`
  (Test-Konto `gregor-test@henemm.com` / Prod-Konto `gregor_zwanzig@henemm.com`).
- Downstream: `briefing_mail_validator` ist Teil des Renderer-Commit-Gates (#811) und
  des Post-Push-E2E-Pfads → jede Änderung an ihm ändert das Deploy-Gate-Verhalten.
  `email_spec_validator` gated Compare-Mails; `e2e_browser_test` wird von E2E-Skills genutzt.

## Existing Specs

- `docs/reference/mail_validators.md` — Single Source für Validator-Verhalten (Update nötig).
- Kein `docs/specs/modules/*.md` für die Hooks selbst.

## Risks & Considerations

- **Gate-Aufweichung:** Der Nacht-Fix darf nicht pauschal 00–06 überall erlauben —
  sonst würde eine kaputte Tagestabelle mit Nachtstunden unbemerkt bleiben. Toleranz nur
  bei nachweislich vorhandener Nacht-Sektion bzw. nur für Stunden nach deren Beginn.
- **Kein Selbst-Gate-Fix-Konflikt:** Diese Fixes laufen über einen eigenen, regulären
  Workflow (nicht als Beifang eines blockierten Workflows) — Regel „kein Gate-Aufweichen
  für eigenen Blocker" ist eingehalten.
- **#975:** Dependency-Installation ändert `package-lock.json` (zählt nicht ins LoC-Limit,
  generiert). Version muss zu vite 8 / svelte 5 passen (Peer-Deps prüfen).
- E2E-Nachweis für #974: Validator gegen echte evening-Staging-Mail (Exit 0) UND
  Beweis, dass eine echte Verletzung (Nachtstunde in Tagestabelle) weiter Exit 1 gibt.
