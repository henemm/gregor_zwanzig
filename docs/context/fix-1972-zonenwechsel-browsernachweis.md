# Context: fix-1972-zonenwechsel-browsernachweis

## Request Summary
Issue #1972 (Epic #2729, letzte offene Scheibe): AC-7 aus `docs/specs/modules/fix_1727_s5e_sperrcache_anzeige.md`
nachholen — im echten Browser belegen, dass die Zeile „Nächste Prüfung" auf der Konto-Seite in zwei
Browser-Zonen (Europe/Vienna, America/New_York) **verschiedene** Uhrzeiten mit dem jeweils passenden
Zonenkürzel zeigt. PO-Entscheid 2026-08-19: „später nachholen". Lösungsweg im Issue offen (3 Vorschläge).

## Ist-Stand (gemessen im Code, 2026-11-11)

Die Hürde aus August besteht unverändert:

- `internal/scheduler/scheduler_gate.go:11` — `SchedulerEnabled()` = `cfg.Env != "staging"` (#1329,
  geteiltes Open-Meteo-Kontingent). Scheduler wird gebaut, aber nicht gestartet → robfig-cron
  `e.Next` bleibt Nullzeit → `next_run: "0001-01-01T00:00:00Z"`.
- `internal/scheduler/scheduler.go:1398-1430` — `StatusForUser()` (#2155 S2) liefert für
  `/api/scheduler/status/me` nur `trip_reports_hourly`, `next_run` aus `e.Next`.
- `frontend/src/routes/account/+page.server.ts:25` — lädt `/api/scheduler/status/me` **serverseitig**
  (SSR, Node in `Etc/UTC`) → `page.route()` greift nicht.
- `frontend/src/routes/account/+page.svelte:488-490, 1064` — `imBrowser` wird in `onMount` gesetzt;
  vorher „—", danach `formatNextRun(job.next_run)` (Serverzone wird so nie gerendert).
- `frontend/src/lib/utils/schedulerTime.ts` — `formatNextRun()`: ohne `timeZone`-Option = Browserzone,
  `timeZoneName: 'short'`, Nullwert-Grenze Jahr < 2000 → „—" (AC-9), DE/EN (#2652).
- `frontend/e2e/ci-stack.sh:57-69` — lokaler E2E-Stack startet Go ebenfalls mit `GZ_ENV=staging`
  (Scheduler aus); Python-Core mit `GZ_TEST_FIXTURE_DIR` (keine Open-Meteo-Abrufe).
- `frontend/e2e/konto-naechste-pruefung.staging.spec.ts` — bestehender Staging-Test für AC-4/AC-9;
  **nutzt den echten Nullwert auf Staging als Nachweis für AC-9** (Kommentar Z. 24-25).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/routes/account/+page.server.ts` | SSR-Load des Scheduler-Status (Hürde für Browser-Stub) |
| `frontend/src/routes/account/+page.svelte` | Anzeige-Zeile, `imBrowser`-Mechanik |
| `frontend/src/lib/utils/schedulerTime.ts` | Formatierung (Unit-getestet, `__tests__/schedulerTime*.test.ts`) |
| `frontend/src/routes/account/__tests__/scheduler-status-me-render.test.ts` | Render-Test Konto-Zeile |
| `frontend/e2e/konto-naechste-pruefung.staging.spec.ts` (+ `playwright.konto-naechste-pruefung.staging.config.ts`) | Ort für den AC-7-Browsernachweis |
| `internal/scheduler/scheduler.go` (`StatusForUser`) | Quelle `next_run` |
| `internal/scheduler/scheduler_gate.go` | Staging-Gate (#1329) |
| `internal/router/router.go:105-115, 146, 332` | Muster staging-only Endpunkte |
| `internal/handler/staging_seed.go` | Muster staging-only Seed (#2423, Spec `staging_seed_endpoint.md`) |
| `frontend/e2e/ci-stack.sh` | lokaler E2E-Stack |

## Lösungswege (aus Issue + neu gefunden) — Entscheidung in /20-analyse
1. **Trockenlauf-Scheduler auf Staging** — Scheduler startet, Jobs versenden nicht. Risiko: Open-Meteo-
   Kontingent (#1329), Versand-Seiteneffekte; zerstört den echten Nullwert, auf dem AC-9 im Browser ruht.
2. **Scheduler-Status zusätzlich clientseitig laden** — `page.route()` greift, Wert setzbar.
   Produktänderung nur zur Testbarkeit (Ladeweg der Seite).
3. **Nachweis an anderer Zeitanzeige** — belegt AC-7 nicht an der Stelle, wo es wirkt (Leitfrage
   Mutations-Gegenprobe) → schwach.
4. **(neu) Staging-only Seed für den angezeigten Termin** nach Muster #2423 — echte SSR-Kette bleibt,
   Wert kommt aus einem nur auf Staging registrierten Testweg. Risiko: Testlogik im Datenpfad von
   `StatusForUser`; muss nutzergebunden (Auth-Kontext) und auf Prod nachweislich wirkungslos sein.
5. **(neu) `next_run` aus dem Cron-Plan berechnen, auch wenn nicht gestartet** — ehrlich nur dort,
   wo der Scheduler läuft; auf Staging würde ein Termin angezeigt, der nie stattfindet → widerspricht
   AC-9 („keinen Termin behaupten, den es nicht gibt"). Verworfen-Kandidat.

## Existing Patterns
- Staging-only Testwege: registriert unter `GZ_ENV=staging`, anmeldepflichtig, `user_id` nur aus Auth-Kontext.
- Browser-Zonen-Tests: `browser.newContext({ timezoneId })`, erbt `use`-Optionen nicht (Kommentar im
  bestehenden Spec-File).
- Prod-Schutz in E2E: `assertNotProdBaseURL` (`frontend/e2e/prodUrlGuard`).

## Dependencies
- Upstream: Go-Scheduler (`StatusForUser`), Auth-Kontext, SSR-Load.
- Downstream: Konto-Seite „Deine Reports", PWA-Standtext (`lib/pwa/standText.ts` nutzt Zeitformat).

## Existing Specs
- `docs/specs/modules/fix_1727_s5e_sperrcache_anzeige.md` — AC-4/5/7/9
- `docs/specs/modules/staging_seed_endpoint.md` — Seed-Muster
- Issue #2155 (Status/me), #1329 (Staging-Gate)

## Risks & Considerations
- Multi-User: jeder neue Datenweg nutzergebunden, Test mit zwei Nutzern.
- AC-9-Browsernachweis (echter Nullwert) darf nicht verloren gehen.
- Keine Versand-Seiteneffekte auf Staging, kein Open-Meteo-Verbrauch.
- Sommer-/Winterzeit: Testerwartung über Zonenkürzel, nicht über feste Stundendifferenz.

## Analysis

### Type
Bug (Nachweislücke: AC-7 aus `fix_1727_s5e_sperrcache_anzeige.md` nur unit-, nicht browserbelegt). Reine Test-Scheibe.

### Neuer Lösungsweg 6 (empfohlen): SvelteKit-Datenantwort im Browser abfangen
Die SSR-Hürde gilt nur für den **ersten** Seitenaufruf. Bei **clientseitiger Navigation** (Sidebar-Benutzermenü
→ `<a href="/account">`, `Sidebar.svelte:178`; ebenso Preload per `data-sveltekit-preload-data="hover"`,
`app.html:41`) holt der Browser die Ergebnisse von `+page.server.ts` selbst über `/account/__data.json`.
Diese Antwort ist per `page.route('**/account/__data.json*')` abfangbar: `route.fetch()` → im Antworttext den
echten Nullwert `"0001-01-01T00:00:00Z"` durch einen festen Termin (z. B. `"2026-12-15T05:00:00Z"`) ersetzen →
`route.fulfill()`. (Alternative mit gleichem Effekt: das HTML von `page.goto('/account')` abfangen und die
eingebettete Hydrationsdaten-Zeichenkette ersetzen; Navigation über `__data.json` bevorzugt, weil näher am
echten Nutzerweg und unabhängig vom HTML-Inline-Format.)

Danach rendert die **echte** Komponente mit dem **echten** `formatNextRun` in der Browserzone
(`onMount` → `imBrowser = true`, `+page.svelte:488-490, 1064`). Geprüft wird also genau dort, wo die
Zonenumrechnung wirkt. Gestellt ist nur die Datenquelle — und die ist für AC-7 nicht Prüfgegenstand.

Warum besser als 1/2/4/5:
- **keine Produktänderung**, kein Staging-only-Endpunkt, keine Testlogik im Datenpfad von `StatusForUser`
- Staging-Scheduler bleibt aus (#1329) → kein Open-Meteo-Verbrauch, kein Versand
- echter Nullwert für AC-9 bleibt unangetastet (bestehender Test unverändert gültig)
- kein Multi-User-Risiko (kein neuer Datenweg)

### Testdesign (für /30-write-spec und /40-tdd-red)
- Ort: neuer Test in `frontend/e2e/konto-naechste-pruefung.staging.spec.ts` (gleiche Config, gleicher Login),
  Kommentarblock „WAS HIER BEWUSST NICHT GEPRUEFT WIRD" anpassen.
- Ablauf je Zone (`browser.newContext({ timezoneId })`, Vienna und New_York): Route registrieren → Startseite
  laden → Benutzermenü öffnen → „Konto" klicken → Zeile „Nächste Prüfung" lesen.
- Zusicherungen: (a) Abfang hat tatsächlich gegriffen (Zähler > 0, sonst klarer Fehltext statt stillem Grün);
  (b) Wien-Zeile enthält Kürzel `MEZ`/`CET` bzw. `MESZ`/`CEST`, NY-Zeile `EST`/`EDT` bzw. `GMT-5`/`GMT-4`
  (tatsächliche Kürzel je Sprache in /40 einmal messen und fest erwarten); (c) Uhrzeiten beider Zonen
  verschieden; (d) Sollwerte aus fest gewähltem Wintertermin konkret (z. B. 05:00Z → 06:00 Wien, 00:00 NY),
  nicht nur „verschieden".
- Mutations-Gegenproben: `formatNextRun` mit `timeZone: 'UTC'` → beide Zonen gleich → rot; `timeZoneName`
  entfernt → Kürzel fehlt → rot; Ersetzung greift nicht (Route-Muster falsch) → Zusicherung (a) rot.
- Sprache: Testnutzer-Sprache festhalten (DE), Kürzel davon abhängig (#2652).

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/konto-naechste-pruefung.staging.spec.ts` | MODIFY | neuer AC-7-Browsertest (2 Zonen), Kopfkommentar aktualisiert |
| `docs/specs/modules/fix_1972_zonenwechsel_browsernachweis.md` | CREATE | Spec mit ACs |
| `docs/specs/modules/fix_1727_s5e_sperrcache_anzeige.md` | MODIFY | AC-7 Nachweisort nachtragen |

### Scope Assessment
- Files: 3 (1 Test, 2 Doku)
- Estimated LoC: +80/-15
- Risk Level: LOW — kein Produktcode, keine Staging-Konfiguration

### Risiken
- `__data.json`-Format (devalue) ändert sich mit SvelteKit-Updates → Ersetzung über exakten String, nicht
  Struktur-Parsing; Zusicherung (a) macht Bruch sichtbar.
- Preload beim Überfahren kann `__data.json` vorab holen → Route vor dem Öffnen des Menüs registrieren.
- Testnutzer ohne Trip-Report-Job: Zeile erscheint nur, wenn `jobs` den Eintrag `trip_reports_hourly` liefert —
  `StatusForUser` liefert ihn immer (Nullwert), bestehender Test belegt die Sichtbarkeit.

### Open Questions
- keine (technische Wahl, kein Produkt-Zielkonflikt)

## RED-Stand (Phase 5, 2026-11-11)
- Neuer Test in `frontend/e2e/konto-naechste-pruefung.staging.spec.ts` (describe „#1972 — … (AC-7)"),
  Kopfkommentar umgeschrieben. Ausführen aus `frontend/` mit App-Login aus `/home/hem/gregor_zwanzig_staging/.env`:
  `npx playwright test --config=e2e/playwright.konto-naechste-pruefung.staging.config.ts`
- Gemessene Kürzel (Chromium, Testnutzer DE, Termin 2026-12-15T05:00Z): Wien `06:00 MEZ`, New York `00:00 GMT-5`
  → fest im Test (`SOLL`).
- RED: Route-Muster per String-Ersetzung auf `**/account/__nicht_da.json*` → AC-7 rot mit
  „Abfang hat nicht gegriffen … Zeile: Nächste Prüfung: —"; AC-4/AC-9 grün. Mit Original: 4 passed.
  Artefakt `docs/artifacts/fix-1972-zonenwechsel-browsernachweis/test-red-output.txt` (gitignored, registriert).
- Offen für /50: kein Produktcode nötig. Noch zu tun: Nachweisort AC-7 + Known Limitations in
  `docs/specs/modules/fix_1727_s5e_sperrcache_anzeige.md` nachtragen; Mutationen AC-8
  (`timeZone: 'UTC'` in `formatNextRun`, `timeZoneName` entfernt, falsches Route-Muster) per String-Ersetzung
  mit externer Sicherungskopie gegen Staging — Achtung: die ersten beiden mutieren Produktcode, wirken also
  nur über einen lokalen Frontend-Stack mit `GZ_SVELTE_BASE` (Vite-Proxy zeigt auf Staging), nicht gegen das
  deployte Staging.
