# Context: fix-1284-e2e-leichen-prod

**Issue:** #1284 — „133 E2E-Testleichen im Prod-Datenbaum senden taeglich 06:00 an @example.com"
**Erstellt:** 2026-07-16
**Track:** Full Process

## Request Summary

Im Produktiv-Datenbaum liegen 149 Vergleichs-Abos des Kontos `admin` mit `@example.com`-Empfaengern — Rueckstaende aus E2E-Laeufen. Sie sollen entfernt und ihre Wiederkehr verhindert werden.

## Befund-Korrekturen gegenueber dem Issue-Text

Drei Annahmen des Issues halten der Pruefung nicht stand. Sie muessen in die Spec einfliessen, sonst spezifizieren wir gegen ein Phantom.

### 1. Es werden KEINE Mails versendet — der Empfaenger-Guard blockt

Der Guard in `src/output/channels/email.py:415-512` (#1219 Resend-Allowlist, #1235 Stalwart-Zweig) blockiert `example.com` bedingungslos ueber `_is_reserved_test_domain` (`email.py:148-173`).

Empirisch belegt, Prod-Journal 2026-07-16 04:00 UTC (= 06:00 Europe/Vienna):

```
Compare preset cp-b64ae1f2da2fc922 failed: [email] 1 Empfaenger nicht in der
Resend-Allowlist ... Betroffene Domains: ['***@example.com']
```

30 solcher Zeilen im Lauf. **Der Schaden ist nicht Zustellung, sondern verbrannte Rechenzeit:** die ComparisonEngine laeuft pro Preset vollstaendig durch (Wetter-Fetch + Rendering), der Guard sitzt erst in der letzten Meile.

Damit entfaellt die Issue-These „verbrennt Resend-Kontingent und Zustell-Reputation". Die im Issue erwaehnten `452 Rate limit`-Fehler vom Testlauf `test_issue_1012_no_data_guard.py` haben eine andere Ursache (s. Memory `reference_tdd_tests_send_real_mail_ratelimit`).

### 2. Nicht 133 sendefaehige Abos, sondern 28

Gezaehlt ueber `data/users/admin/briefings/*.json` (kind=vergleich):

| | Anzahl |
|---|---|
| Vergleichs-Abos gesamt | 153 |
| `morning_enabled` + `morning_time` 06:xx | 133 |
| mit >= 1 Ort (`location_ids`) | 44 |
| **06:00 UND >= 1 Ort (= echt sendefaehig)** | **28** |
| mit `@example.com`-Empfaenger | 149 |

105 der 133 faelligen Abos haben eine leere Ortsliste und brechen frueh ab (billig). Fuer das Zeitbudget zaehlt trotzdem die volle 133 — s. Punkt 3.

### 3. Das Timeout-Risiko ist REAL und ab morgen 06:00 aktiv

`run_briefing_dispatch` (`src/services/dispatch_orchestrator.py:179-185`) schlaeft **unabhaengig vom Ergebnis** von `dispatch_one`:

```python
for i, item in enumerate(due):
    strategy.dispatch_one(item)
    if i < len(due) - 1:
        time_module.sleep(strategy.inter_mail_delay)   # 2.0s seit 9c8fb30c
```

Also 132 x 2s = **264s reine Pause**, auch fuer die 105 Abos, die sofort scheitern. Der Go-Client hat 120s Timeout (`internal/scheduler/scheduler.go:82`).

Messung des letzten Laufs (2026-07-16 04:00 UTC, **noch mit `inter_mail_delay = 0`**):

```
04:00:00 -> 04:01:12  POST /api/scheduler/compare-presets-daily?user_id=admin  = ~72s
```

72s ohne Pause, unter 120s. Der Prod-Dienst wurde am 2026-07-16 16:02 UTC neugestartet und faehrt seither `9c8fb30c` mit 2.0s. **Der naechste 06:00-Lauf laeuft in den Timeout.** AC-3 beschreibt also kein hypothetisches, sondern ein ab morgen eintretendes Verhalten.

## Ursache (belegt)

Die Kette ist vollstaendig rekonstruiert:

1. `frontend/playwright.config.ts:8` — `baseURL: 'http://localhost:4173'`
2. `frontend/playwright.config.ts:25-30` — `webServer.command: 'bash e2e/start-preview.sh'`
3. `frontend/e2e/start-preview.sh:4` — sourcet die **Prod**-`.env` des Repo-Roots (inkl. Live-Secrets)
4. `frontend/vite.config.ts:7-14` — `server.proxy['/api'].target = 'http://localhost:8090'`; Vites `preview.proxy` erbt `server.proxy`
5. Port 8090 = **Prod**-Go-Server (`/home/hem/gregor_zwanzig/gregor-api`, cwd `/home/hem/gregor_zwanzig`). Staging laeuft auf 8091.
6. `internal/config/config.go:9` — `DataDir` default `"data"`, relativ zu cwd → `/home/hem/gregor_zwanzig/data`

**Login:** `frontend/e2e/helpers.ts:11-12` und `frontend/e2e/global.setup.ts:26-27` defaulten beide auf `admin` / `test1234`. Das erklaert, warum genau `admin` das Sammelbecken ist.

**Warum der bestehende Guard nicht greift:** `frontend/e2e/prodUrlGuard.ts:18-31` prueft nur den **Hostname der baseURL**. `localhost:4173` besteht die Pruefung und proxyt dann in Prod. Der Guard stammt aus #1265 und hat den Domain-Fall gefangen, den Proxy-Fall verfehlt. Zudem wird er nur aus `global.setup.ts:24` gerufen — keine Durchsetzung pro Spec.

**Verschaerfend:** `frontend/playwright.config.ts:16-19` — Projekt `tests` hat nur `testIgnore: /global\.setup\.ts/`, **kein `testMatch`**. Ein blankes `npx playwright test` in `frontend/` zieht damit auch alle staging-gedachten Specs ein und spielt sie gegen Prod.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/playwright.config.ts` | **Leck-Quelle**: baseURL 4173 → Proxy → Prod-8090; kein `testMatch` |
| `frontend/e2e/start-preview.sh` | sourcet Prod-`.env` mit Live-Secrets in den Test-Prozess |
| `frontend/vite.config.ts:7-14` | Proxy `/api` → 8090 (Prod) |
| `frontend/e2e/prodUrlGuard.ts:18-31` | bestehender Guard — prueft nur Hostname, blind fuer Proxy |
| `frontend/e2e/helpers.ts:11-12` | Login-Default `admin`/`test1234` |
| `frontend/e2e/global.setup.ts:26-27` | dito (`E2E_USER`) |
| `src/services/scheduler_dispatch_service.py:141-142` | **`data_root = "data"` hartkodiert** — ignoriert `GZ_DATA_DIR` |
| `api/routers/scheduler.py:137` | reicht kein `data_root` durch |
| `src/services/dispatch_orchestrator.py:179-185` | 2s-Pause laeuft auch bei Fehlschlag |
| `src/services/compare_slot_scheduler.py:38-58` | 06:00-Migrations-Fallback bei fehlendem `morning_time` |
| `internal/scheduler/scheduler.go:82` | 120s HTTP-Timeout |
| `internal/scheduler/scheduler.go:148-182` | `runForAllUsers` + Test-User-Skip (#1265) |
| `internal/model/test_user.go:36-38` | `IsTestUserID` — Substring „test"/„tdd"; **`admin` faellt durch** |
| `src/output/channels/email.py:415-512` | Empfaenger-Guard, blockt `example.com` |
| `tests/conftest.py:67-111` | autouse-Isolations-Fixture + Snapshot-Waechter (#1265 Teil C) |
| `internal/model/compare_preset.go:15-107` | Schema-SSoT der Abo-Datei |

## 13 Specs ohne jedes Cleanup

Erzeugen Compare-Presets mit `@example.com`, haben **kein** `afterAll`/`afterEach`:

`bug-626-compare-menu-actions`, `compare-editor-autosave-user-isolation`, `compare-editor-slice3`, `compare-alarm-config`, `compare-hub-briefing-times`, `compare-editor-edit`, `compare-legacy-fields-survive-save`, `compare-editor-slice4`, `compare-radar-toggle`, `issue-682-compare-editor-mobile`, `issue-718-idealwert-validation`, `layout-tab-vergleich`, `save-status-indicator-honesty`

Namens-Zuordnung der gefundenen Leichen:

| Name im Datenbaum | Quelle | Cleanup |
|---|---|---|
| `Slice4 E2E <ts>` | `frontend/e2e/compare-editor-slice4.spec.ts:46` | keins |
| `Valid Ranges 718 <ts>` | `frontend/e2e/issue-718-idealwert-validation.spec.ts:151` | keins |
| `LayoutTab E2E <ts>` | `frontend/e2e/layout-tab-vergleich.spec.ts:30` | keins |
| `Zeitfenster-E2E 1134 <ts>` | Spec in `d32bd0a5` (#1268) geloescht | Datei weg, Daten bleiben |
| `Issue 223 e2e-issue-223-acN` | `frontend/e2e/alert-rules-editor.spec.ts:14` | nur Trips (`DELETE /api/trips`), nicht Briefings |
| `EditView-Seed-Trip` | `frontend/e2e/trip-edit.spec.ts:4` | keins |
| `Probe4`, `Diag <ts>` | nicht im Repo/Git — ad-hoc curl | — |

## Existing Patterns

- **Test-Konten-Erkennung:** `model.IsTestUserID` (Go) / `is_test_user_id()` (`src/app/config.py:30`) — Substring „test"/„tdd" + Fixture `tg-live-e2e`. Go-Variante liest bewusst **nicht** das Profil-Flag `user.json: is_test_user` (Known Limitation, dokumentiert).
- **Scheduler-Skip:** `runForAllUsers` (`scheduler.go:148`) filtert Test-Konten — Defense-in-Depth aus #1265, **im Prod-Binary vorhanden** (`strings`-Nachweis).
- **Test-Isolation:** `tests/conftest.py:67` autouse-Fixture + Snapshot-Waechter ueber `<repo>/data/users` — greift aber nur in-process unter pytest, nicht bei HTTP-Laeufen gegen einen separaten Server.
- **Datenpfad:** `loader.get_data_root()` — Prioritaet `_DATA_ROOT` > `GZ_DATA_DIR` > `"data"`. Go: `GZ_DATA_DIR` → `cfg.DataDir` → DI in `store.New`.

## Dependencies

- **Upstream:** Go-Cron `briefingDispatch` (stuendlich `0 * * * *`) → `runForAllUsers` → `POST /api/scheduler/compare-presets-daily?user_id=<uid>`
- **Downstream:** `run_compare_presets_daily` → `run_briefing_dispatch("vergleich")` → `CompareDispatchStrategy` → ComparisonEngine → `NotificationService.send_compare_report` → `EmailOutput.send` (Guard)

## Existing Specs

- `docs/specs/modules/issue_1133_testdata_cleanup.md` — `status: implemented`; historisch Prod 124/139 Verzeichnisse Test-Residuen
- `docs/specs/modules/issue_1265_prod_testdata_cleanup.md` — Cleanup-Teil #1265
- `docs/specs/modules/fix_1265_data_root_migration_services.md` — **created 2026-07-16**, Restschuld: `user_tier.py`, `compare_radar_alert.py`, `compare_weather_snapshot.py`
- `docs/specs/modules/compare_preset_zeitplan.md` — #1232 Slot-Modell

**Wichtig:** Der `scheduler_dispatch_service.py`-`"data"`-Default steht in **keiner** dieser Specs — Luecke jenseits der bekannten drei Services.

## Offene Frage aus dem Issue: Ist `admin` legitim?

**Antwort: nein, es ist das E2E-Sammelbecken.** Belege:

- `helpers.ts` und `global.setup.ts` defaulten beide auf `admin`/`test1234`
- Von 17 Abos ohne `@example.com` tragen 16 Testnamen (`Issue 223 e2e-...`, `E2E Cockpit Test Trip`, `Diag <ts>`, `Probe4`, `EditView-Seed-Trip`)
- Einziger Kandidat fuer echte Nutzung: **`Ski Tirol`** (kind=vergleich) — vor Loeschung PO-Rueckfrage
- Echter Nutzer ist `henning` (9 Abos, 0 mit example.com)

`admin` faellt durch `IsTestUserID` (kein „test"/„tdd" im Namen) — deshalb hat es die #1265-Aufraeumung ueberlebt, waehrend `tdd-1007-*` & Co. entfernt wurden.

## Risks & Considerations

1. **Datenverlust (hoch).** 149 Loeschungen im Produktiv-Baum. `tar.gz` nach `data/.backups/` ist Pflicht (CLAUDE.md, BUG-DATALOSS-GR221). `Ski Tirol` und `validator-issue110` (8 Abos, 0 example.com — Validator-Konto, wird gebraucht) nicht mittreissen.
2. **Zeitdruck.** Ab dem naechsten 06:00-Lauf meldet `compare_presets_daily` `error` durch Timeout. Der Aufraeum-Teil (AC-1) beseitigt das sofort; die Struktur-Teile (AC-2/AC-4) duerfen nicht darauf warten.
3. **Loch bleibt offen ohne Struktur-Fix.** Reines Loeschen fuellt sich beim naechsten `npx playwright test` neu.
4. **Isolation via `GZ_DATA_DIR` funktioniert heute nicht** fuer den Compare-Dispatch (`scheduler_dispatch_service.py:141`). AC-2s Variante „isolierter Datenbaum" setzt diesen Fix voraus — sonst ist nur der Weg „nicht gegen Prod zeigen" gangbar.
5. **`start-preview.sh` leakt Prod-Secrets** (SMTP, Telegram-Token, MeteoFrance-Key, Session-Secret) in den Test-Prozess. Eigener Befund, ausserhalb der ACs — Sicherheitsrisiko, gehoert als eigenes Issue erfasst (Triage-Kriterium b).
6. **Falsches „ok" im Scheduler-Status.** `CompareDispatchStrategy` schluckt Fehler (`scheduler_dispatch_service.py:115-117`), der Endpoint liefert `{"status":"ok","count":0}` ohne `failed`-Feld (anders als `/api/scheduler/trip-reports`, #1012). Ein Lauf, in dem alle Presets scheitern, meldet `status:"ok"`. Deckt sich mit dem offenen Punkt „verschluckte Fehler" aus #1207.
7. **Regel-Budget.** AC-4 fordert einen „wiederholbaren Check" — neue Pflicht-Regel. Braucht Ersatz einer bestehenden Regel oder Pruefdatum (+90 Tage).
8. **9 Python-Tests zeigen per Default auf Prod** (`GO_BASE = "http://localhost:8090"`, `test_scheduler_triggers.py:14` auf `127.0.0.1:8000`). Gleiche Gefahrenklasse, nicht Quelle der 149 — Kandidat fuer #1196.

---

# Analysis

**Type:** Bug
**Adversary-Lauf (analysis-challenger):** 3 von 4 Thesen HALTEN, These 1 teilweise gebrochen (s.u.)

## Adversary-Befunde

### These 1 „Kein Versand, Guard blockt" — TEILWEISE GEBROCHEN, aber ohne aktuellen Schaden

Der **E-Mail**-Guard haelt lueckenlos: beide Zweige (`email.py:428-475` Resend, `:476-514` Stalwart) blocken `example.com` unconditional via `_is_reserved_test_domain` (`:148-166`) — **auch bei gesetztem `GZ_RESEND_ALLOWED`** (das entscheidet nur Resend-vs-Stalwart-Host, nicht ob der Guard laeuft).

**Aber Telegram hat keinen aequivalenten Schutz:** `src/output/channels/telegram.py:134-199` postet `chat_id` ohne jede Pruefung an die Bot-API. Der Schutzmechanismus waere `Settings.with_user_profile()` (`src/app/config.py:245-260`): `force_test = env==staging OR is_test_user_id(user_id)`. Fuer `admin` ist beides False (kein „test"/„tdd" im Namen, kein `is_test_user`-Flag in `user.json`) → echte Prod-Settings, `can_send_telegram()` (`config.py:295-297`) prueft nur „Token+Chat-ID nicht leer" → True.

**Empirisch geprueft (2026-07-16):** Von 153 Vergleichs-Abos in `data/users/admin/briefings/` hat **kein einziges** `send_telegram` oder `send_sms` gesetzt (0/0). **Kein aktueller Schaden.** Die Luecke ist latent — ein Test-Spec, der den Telegram-Schalter umlegt (`versand-tab-vergleich.spec.ts` tut genau das), wuerde taeglich echte Nachrichten in den Prod-Chat schicken. → eigenes Issue (s. Nebenbefunde).

SMS ist strukturell sicher: `sms_allowed("admin")` (`src/services/user_tier.py:6-14`) liest `tier` aus `user.json`, fehlt → Default `"free"` → SMS aus.

Dead Code, irrelevant: `src/app/core.py:5-23` `send_mail()` ist ungeguardeter Roh-SMTP — einziger Aufrufer ist `tests/test_core.py:7`.

### These 2 „28 sendefaehig, 105 brechen billig ab" — HAELT

`send_one_compare_preset` (`scheduler_dispatch_service.py:293-404`): Empfaenger-Check (`:327-334`), dann `locations`-Filter (`:338`), leere Liste → `raise ValueError` (`:339-340`) — **vor** `ComparisonEngine.run()` (`:347`). Kein Wetter-Fetch fuer die 105.

### These 3 „Timeout ab morgen 06:00" — HAELT, praeziser als gedacht

`runForAllUsers` (`scheduler.go:148-183`) ruft `triggerEndpointForUser` **pro User einzeln** — die 120s gelten **pro HTTP-Call**, nicht als Gesamtbudget. Alle 133 faelligen Presets gehoeren zu **einem** User (`admin`) → die volle 264s-Pause trifft genau diesen einen Request. `tripReports()` laeuft im selben Cron-Tick vorher (`scheduler.go:188-191`), aber als separater Call mit eigenem 120s-Budget — frisst nicht mit.

### These 4 „admin = reines Testkonto, loeschbar" — HAELT

Keine Sonderrolle in `src/` oder `internal/`. Einziger Nicht-Test-Treffer: `internal/config/config.go:17` (`AuthUser default:"admin"`) — unbenutztes Legacy-Feld ohne Consumer, in Prod ohnehin auf `GZ_AUTH_USER="default"` ueberschrieben. Namens-Zufall, keine Rolle.
`data_write_selftest` (`scheduler.go:235-274`) prueft nur `store.DataDir` global, nicht pro User → Loeschen gefaehrdet den Job nicht. `admin/groups.json` ist user-lokal, keine Cross-User-Referenz.

## Weitere Adversary-Befunde (in die Spec zu uebernehmen)

1. **`steffi` ist ein vierter echter Nutzer** (`data/users/steffi/user.json`, `mail_to: steffi.emmrich@gmail.com`, `email_verified_at` gesetzt, 0 Briefings). Die „echte Nutzer"-Inventur oben war unvollstaendig. Ein Cleanup darf **nicht** naiv „alles ausser henning" annehmen.
2. **Die Sicherheit von `default` ist Zufall, keine Struktur.** `frontend/.env.test` (`E2E_USER=default`) ist **toter Code** — `start-preview.sh:4-5` sourcet nur Root-`.env` + optional `.env.e2e`; kein dotenv-Import im Frontend. `global.setup.ts:26` liest `E2E_USER`, `helpers.ts:11` liest `GZ_E2E_USER` — **zwei verschiedene Variablennamen**. `default` blieb sauber, weil niemand die Variable exportiert hat → beide fielen auf den Hardcode `'admin'` zurueck. Ein Lauf mit gesetzter Shell-Variable vergiftet einen **anderen echten Account**.
3. **Staging-Baum bestaetigt NICHT betroffen:** `/home/hem/gregor_zwanzig_staging/data/users/` = `validator-issue110`, `default`, `tg-live-e2e` — kein `admin`, 0 `briefings/*.json`. Korrekt ausserhalb des Scope.
4. **Praezedenz-Konflikt:** `scripts/cleanup_1265_prod_testdata.py:65` fuehrt `admin` in `NEVER_DELETE`, `:75` in `REAL_ACCOUNTS` — als „echtes Konto" **geschuetzt**; `SIGHTING_ONLY_DIRS` (`:69`) schliesst `briefings` aus. **Genau dieser Schutz ist die Luecke.** PO-Entscheid 2026-07-16 hebt ihn fuer `admin` auf. Muss im neuen Skript als „supersedes #1265 NEVER_DELETE fuer admin" dokumentiert werden.

## PO-Entscheidungen (2026-07-16, bindend)

1. **Der gesamte `admin`-Baum ist Testmuell** — auch „Ski Tirol" („Ich hab das nicht angelegt, das warst du"). Nichts erhaltenswert.
2. **Absicherung an der Wurzel:** Der Standard-Playwright-Lauf darf Prod nicht mehr erreichen. Aufraeum-Hooks in den 13 Specs sind **nicht** gewuenscht (zu zerbrechlich: abgebrochener Lauf raeumt nicht auf, naechstes Spec vergisst es).

## Technical Approach

### AC-1 — Aufraeumen: ganzes Verzeichnis, nicht nur `briefings/`

`ListUserIDs()` erkennt Nutzer ueber Verzeichnis-Praesenz + `user.json` — kein globaler Index. Faellt `data/users/admin/` ganz weg, taucht `admin` in `ListUserIDs()` nicht mehr auf → `runForAllUsers` ruft fuer `admin` **gar keinen** Endpoint mehr auf. Strukturell staerker als „nur briefings leeren" (das schleppt `admin` als 0-Presets-Konto weiter mit und bleibt von `IsTestUserID`-Heuristik abhaengig). Mit `user.json` weg kann sich auch niemand mehr versehentlich als `admin`/`test1234` gegen Prod einloggen — erwuenscht, nicht Kollateralschaden.

**Skript, keine Go-Migration.** `migrate_1257.go`/`migrate_1258.go` sind Schema-Upgrades beim Start — falsches Vorbild fuer einen Einmal-Purge. Vorbild ist `scripts/cleanup_1265_prod_testdata.py` (gleiches Problem, gleiche Woche): `--dry-run`-Default/`--execute`, tar.gz vor Loeschung, idempotent, laeuft als `claude-gregor` auf dem Prod-Host.

Neues, eigenstaendiges `scripts/cleanup_1284_admin_prod.py` (nicht das 1265er erweitern — das wuerde dessen `NEVER_DELETE`-Semantik fuer alle Aufrufer verwaessern):
- Hartkodiertes Ziel `users_root / "admin"` — kein generischer `--user`-Parameter (Fehlbedienungs-Schutz)
- Fail-Fast: `default`, `henning`, `steffi`, `validator-issue110` muessen existieren (falsches `--root` → Abbruch, analog `_missing_real_accounts`)
- Backup `data/.backups/cleanup-1284-<ts>.tar.gz` nur von `data/users/admin/`
- `shutil.rmtree`, idempotent (zweiter Lauf: 0 Aktionen, kein Leer-Backup)
- Kern-Test gegen tmp-Fixture: Backup entsteht · `admin` weg · die vier echten Konten byte-identisch · zweiter Lauf idempotent

**Achtung Pfad-Falle:** `data/` im Worktree ist **nicht** der Prod-Baum (andere Inode). Das Skript muss gegen den absoluten Host-Pfad `/home/hem/gregor_zwanzig/data` laufen.

### AC-2/AC-4 — Wurzel-Fix: (b) + (c), nicht (a), nicht (d), nicht (e)

Der Bug sitzt im Proxy-Ziel, nicht in der baseURL und nicht in der Spec-Auswahl.

- **(b) `frontend/vite.config.ts`:** Proxy-Ziel `8090` (Prod) → `8091` (Staging-Go, laeuft dauerhaft auf `127.0.0.1:8091` — verifiziert via `ss -tlnp`). Damit trifft **jeder** `npx playwright test`-Lauf Staging, unabhaengig von der Spec-Auswahl.
- **(c) `prodUrlGuard.ts` erweitern** um `assertNotProdApiProxyTarget`. Damit der Guard nicht gegen eine Kopie prueft: Ziel in **eine** geteilte Konstante `frontend/e2e/apiProxyTarget.ts` legen, die `vite.config.ts` **und** der Guard importieren. Env-Override `GZ_E2E_API_PROXY_TARGET ?? 'http://localhost:8091'` — nur der *Default* wird sicher, nichts hart verriegelt.
- **(a) verworfen:** `playwright.config.ts` ganz auf Remote-Staging umstellen wuerde den lokalen `webServer`/Build kappen — der Default-Lauf teste dann nicht mehr den lokal gebauten Stand. Groesserer Verhaltensbruch, unnoetig.
- **(d) `start-preview.sh` unangetastet:** setzt keine Variable, die das neue Ziel ueberschriebe; der sichere Default gilt unabhaengig von der gesourcten `.env`. Der Secrets-Leak wird separat behandelt.
- **(e) `testMatch` ausgelassen:** Sobald Prod netzwerkseitig unerreichbar ist, ist egal welche Specs ein blankes `npx playwright test` einzieht — sie schreiben nach Staging. 13 Dateien klassifizieren = mehr Aufwand, kein Zusatzgewinn.

**Was bricht fuer Entwickler:** Wer lokal testet, sieht ab jetzt den Staging-Datenstand statt Prod (was der Bug war). Wer bewusst gegen einen anderen Port will, setzt `GZ_E2E_API_PROXY_TARGET`.

### AC-4 — wiederholbarer Check: bestehende Gates erweitern

`tests/conftest.py:67-111` scheidet aus — autouse-Pytest-Fixture, wirkt nur in-process, blind fuer einen externen Playwright-Prozess gegen systemd-Server.

Stattdessen die **bereits in CI laufenden** TS-Gates (`npm test`, `.github/workflows/ci.yml:66`) erweitern:
- `frontend/src/lib/__tests__/e2e_prod_url_guard.test.ts` — Faelle fuer `assertNotProdApiProxyTarget` (wirft bei 8090, nicht bei 8091)
- Source-Scan-Test nach Muster `e2e_setup_guard_coverage.test.ts` — scheitert, wenn `vite.config.ts` das Literal `8090` enthaelt oder die geteilte Konstante nicht importiert

**Regel-Budget:** Erweiterung des bestehenden Gates aus #1265 Teil D (`prodUrlGuard.ts`), **kein neues Pflicht-Gate** → kein Ersatz, kein neues Pruefdatum noetig. Fallback bei strenger Auslegung: Pruefdatum 2026-10-14.

### AC-3 — Zeitbudget: automatisch erfuellt

Nach AC-1 existiert `data/users/admin/` nicht mehr → `admin` faellt aus `ListUserIDs()` → der Endpoint wird fuer ihn nie gerufen. Die 264s-Pause verschwindet, weil die 132 Eintraege verschwinden — nicht weil der Pause-Mechanismus geaendert wird. `henning` mit 9 Abos: max 8x2s = 16s + Rendering, weit unter 120s. **Der 2s-Delay wird nicht angefasst** (PO-Entscheid #1207).

Dass die Pause auch fuer sofort scheiternde Presets laeuft (`dispatch_orchestrator.py:179-185`), bleibt eine echte Robustheits-Schwaeche — nach AC-1 aber kein akutes Risiko. Zurueckstellen, nicht in dieses Fenster pressen.

## Affected Files

| Datei | Aenderung | Beschreibung |
|---|---|---|
| `scripts/cleanup_1284_admin_prod.py` | CREATE | Purge `data/users/admin/` mit tar.gz-Backup, idempotent, Fail-Fast |
| `tests/test_cleanup_1284_admin_prod.py` | CREATE | Kern-Test gegen tmp-Fixture |
| `frontend/e2e/apiProxyTarget.ts` | CREATE | geteilte Konstante (SSoT Proxy-Ziel) |
| `frontend/vite.config.ts` | MODIFY | Import statt Literal `8090` |
| `frontend/e2e/prodUrlGuard.ts` | MODIFY | `assertNotProdApiProxyTarget` |
| `frontend/e2e/global.setup.ts` | MODIFY | Guard-Aufruf ergaenzen |
| `frontend/src/lib/__tests__/e2e_prod_url_guard.test.ts` | MODIFY | Faelle fuer neuen Guard |
| `frontend/src/lib/__tests__/vite_proxy_target.test.ts` | CREATE | Source-Scan: kein `8090`-Literal |

## Scope Assessment

- **Dateien:** ~8
- **LoC:** ~175-215 (Limit 250, wenig Puffer — Unsicherheit im Cleanup-Skript)
- **Risk Level:** HIGH (Loeschung im Produktiv-Datenbaum)

Bei Ueberschreitung: erst Test-Tiefe beim Skript straffen (ein kombinierter Idempotenz+Backup-Test), **erst dann** `loc_limit_override` — und der braucht PO-Freigabe.

## Reihenfolge

1. **Sofort (12h Zeitdruck bis 06:00):** AC-1-Skript schreiben, gegen tmp-Fixture verifizieren, auf dem Prod-Host als `claude-gregor` ausfuehren (`--dry-run`, dann `--execute`). Reiner Host-Schritt, kein Code-Deploy. Erledigt AC-1 **und** AC-3 in einem Zug.
2. **Danach, normaler Takt:** AC-2 + AC-4. Kein Zeitdruck mehr, aber noetig, damit sich das Loch nicht neu fuellt.
3. Innerhalb 2: geteilte Konstante zuerst, dann `vite.config.ts` + Guard/`global.setup.ts`, Tests zuletzt.

## Nebenbefunde — NICHT in diesem Workflow

| Befund | Wohin | Begruendung |
|---|---|---|
| **Telegram ohne Empfaenger-Guard** (`telegram.py:134-199`); Prod-Bot-Token gesetzt; `admin` entgeht `force_test` | **eigenes Issue** | Triage (b) Sicherheitsrisiko. Aktuell 0 Presets betroffen, aber ein Toggle in `versand-tab-vergleich.spec.ts` genuegt |
| **Prod-Secrets in `start-preview.sh:4`** (SMTP, Telegram-Token, MeteoFrance-Key, Session-Secret) in den Testprozess | **eigenes Issue** | Triage (b). Kein Sammel-Eintrag — #1199 ist fuer nicht-blockierende Gate-Befunde |
| **Verschlucktes „ok"**: `CompareDispatchStrategy` meldet `status:"ok"` auch wenn alle Presets scheitern, kein `failed`-Feld (anders als `/api/scheduler/trip-reports`, #1012) | **eigenes Issue** | Triage (a). Querverweis #1207 „verschluckte Fehler" |
| **`E2E_USER` vs. `GZ_E2E_USER`** — zwei Namen, `.env.test` toter Code; Sicherheit von `default` ist Zufall | **#1199** | kosmetisch/strukturell, blockiert nichts |
| **9 Python-Tests default auf Prod-Ports** (`GO_BASE=localhost:8090`, `test_scheduler_triggers.py:14` auf `127.0.0.1:8000`) | **#1196** | Test-Suite-Hygiene, bestehende Heimat |
| **`scheduler_dispatch_service.py:141`** `data_root="data"` hartkodiert, ignoriert `GZ_DATA_DIR` | **`fix_1265_data_root_migration_services.md`** | vierter Eintrag der bestehenden Restschuld-Spec |
| **2s-Pause laeuft auch bei Early-Return** (`dispatch_orchestrator.py:179-185`) | **#1199** | nach AC-1 kein akutes Risiko |

## Open Questions

- [ ] Keine offenen Fragen — beide PO-Entscheidungen liegen vor.
