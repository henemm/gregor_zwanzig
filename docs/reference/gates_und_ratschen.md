# Gates & Ratschen — Detailmechanik

Ausgelagert aus `CLAUDE.md` (2026-08-15), damit die Detailmechanik nicht in **jeder** Modell-Anfrage
mitgeladen wird. In `CLAUDE.md` steht je Gate nur noch der Merksatz und der Verweis hierher.
**Hier nachsehen, wenn ein Gate blockiert und die Meldung nicht selbsterklärend ist.**

## CI-Prod-Gate `ci_prod_gate.sh` (#2047 S2, seit 2026-10-06)

Der CI-Job `deploy` (needs: alle sechs Ampel-Checks) schreibt **kein** Staging-Verdict mehr und
führt **kein** `git reset` aus. `scripts/ci_prod_gate.sh` läuft auf dem Server-Checkout: `git fetch`,
dann `staging_gate.py --check --expected-commit origin/main` (dieselbe Prüfung wie der Preflight von
`deploy-gregor-prod.sh`), Ausgabe `PROD_GATE=open|closed`. Es schreibt nie in `.claude/e2e_verified/`.
Prod-Deploy und Erfolgs-Telegram nur bei `open`; bei `closed` bleibt der Job grün, der Deploy-Schritt
übersprungen, die Job-Summary verweist auf `/70-deploy` Schritt 4. `git fetch` scheitert oder fehlt
der `PROD_GATE`-Satz ⇒ Job rot.

**Ergänzung S2b (ADR-0085):** `deploy-gregor-prod.sh` hat einen Idempotenz-Kurzschluss. Ist
`deployed_commit` gleich `origin/main`, gibt es „bereits ausgeliefert" und Exit 0, ohne Neustart.
**Notausgang:** `GZ_FORCE_REDEPLOY=1 bash …/deploy-gregor-prod.sh` liefert trotzdem aus und
protokolliert das in `.claude/deploy-overrides.log`. Nach dem Deploy läuft im CI-Pfad
`prod_selftest.py` (Exit ≠ 0 ⇒ Job rot). Job `deploy` hat `concurrency: prod-deploy` ohne Abbruch.
**Telegram-Ausschluss:** je Lauf höchstens eine Meldung, entweder „deployed", „bereits
ausgeliefert" oder „FEHLGESCHLAGEN" (nur bei `failure()`). Bei `closed` gibt es keine Meldung.

## Frontend-Browser-Gate (#1558, seit 2026-08-08)

Berührt der committete Scope `frontend-only` oder `full-stack`, lädt `staging_gate.py --write-verdict`
**selbst** sechs Kernseiten (`/`, `/trips`, `/trips/new`, `/compare`, `/compare/new`, `/locations`) in
einem echten Chromium gegen Staging und sammelt `console(type=error)` sowie `pageerror` — Warnungen
zählen nicht. Schlägt das fehl, entsteht **keine** Attestation, der Prod-Deploy bleibt blockiert.

**Fail-Grenze:** Lässt sich das Gate-Modul selbst nicht laden (Import-/Syntaxfehler), läuft der Aufruf
mit Warnung durch — ein kaputter Wächter darf nie die Ursache sein, dass niemand mehr ausliefert.
Fehlt dagegen Playwright, ist Staging nicht erreichbar, scheitert die Anmeldung oder fehlen
Zugangsdaten, wird **blockiert** — das ist „Nachweis nicht erbringbar", nicht „Gate kaputt".

**Notausgang: `GZ_SKIP_FRONTEND_BROWSER_GATE=1`** (exakt `1`, laut auf stderr).
**`GZ_SKIP_E2E_GATE` wirkt hier NICHT** — das sitzt in `gate_check()` (Deploy-Check, Mode B), der
Browserlauf hängt in `write_verdict()` (Mode A). Zwei Schalter mit Absicht: der Deploy-Skip ist
flüchtig, der Browserlauf-Skip erzeugt ein **dauerhaftes** Artefakt. Bei bestandenem Lauf trägt die
Attestation `frontend_pages_checked`; wurde übersprungen oder war das Gate-Modul nicht ladbar, trägt
sie stattdessen `frontend_browser_gate: "UEBERSPRUNGEN via …"` bzw. `"NICHT GELAUFEN …"` — das
Artefakt darf keinen Nachweis behaupten, den es nie gab.

*Regel-Budget: Prüfdatum 2026-11-05. Fang-Beleg: #1552 (Kernseite auf Staging unbedienbar bei 5837
grünen Tests, Adversary VERIFIED, alle CI-Checks grün). (`ui_screenshot_gate.py`, früher hier zur
Mitbewertung genannt, war nie verdrahtet und ist mit dem Gate-Rückbau Stufe 1 entfernt, #1197.)*

## Zugangsdaten: DREI Quellen, nicht zwei (2026-08-08)

Bei einer Blockade **zuerst hier** nachsehen, nicht in der `.env` des Arbeitsordners.

| Zweck | Variablen | Quelle |
|---|---|---|
| nginx-Schranke | `GZ_VALIDATOR_*` | `.claude/validator.env` |
| App-Anmeldung (Staging-Ziel) | `GZ_AUTH_*` | `/home/hem/gregor_zwanzig_staging/.env` |
| App-Anmeldung (lokal) | `GZ_AUTH_*` | lokale `.env` |

Die Staging-Instanz hat **eigene** Anmeldedaten — gleicher Benutzername, **anderes Passwort**;
gemessen an `POST /api/auth/login`: Arbeitsordner-`.env` → **401**, Staging-`.env` → **200**. Genau
daran blockierte das frisch ausgelieferte Gate jede Frontend-Auslieferung. Modul-Attribut
`STAGING_ENV_PATH`, überschreibbar per `GZ_STAGING_ENV_PATH`.

**„Anmeldung abgelehnt" ≠ „zurückgeleitet auf die Anmeldemaske"** — wer beides gleichsetzt, hält
einen generell kaputten Anmeldeweg für den Beleg, dass ein falsches Passwort erkannt wurde. Die
Ablehnung kommt als `POST 401` auf **`/login`** (SvelteKit-Form-Action), nicht auf
`/api/auth/login`. Die Tests bewachen die **Quelle** der Anmeldedaten, nicht ihre **Gültigkeit** —
ein gedrehtes Staging-Passwort lässt die Kern-Suite grün und blockiert trotzdem.
Meldungs-Tabelle: `docs/reference/operations_playbook.md`.

## E2E-Nachweis-Ablage (seit #1382)

**Eine Datei je Stand** unter `.claude/e2e_verified/<sha>.json` — geschrieben und gelesen über
dieselbe Auflösung. Die frühere einzelne Sammeldatei wird **nicht mehr gelesen**; fehlt der Nachweis
für den Zielstand, blockiert das Gate und sagt genau das, statt einen fremden Stand zu nennen.
Dieselbe Bedingung gilt für Deploy-Gate und Post-Deploy-Selftest: exakter Treffer ODER ein Vorgänger,
der bestanden **und** frisch ist **und** dessen Zuwachs reine Doku ist. Ein ausdrücklich übergebener
`--e2e-path` ist maßgeblich (keine Vorgänger-Suche).

Meldet ein Lauf `verified_commit (<fremder Stand>) != expected-commit`, ist das der **alte** Wortlaut
— dann läuft dort noch Code vor #1382.

## Renderer-Commit-Gate (#811)

`renderer_mail_gate.py` blockiert jeden Commit, der eine Mail-Inhalts-Datei staged
(`src/output/renderers/email/*.py`, `src/output/renderers/{trip_report,sms_trip,compact_summary}.py`,
`src/output/renderers/alert/*.py`, `src/output/channels/email.py`), bis im aktiven Workflow **beide**
frisch vorliegen: (1) `tests/tdd/test_issue_811_mode_matrix.py` grün, (2) erfolgreicher
`briefing_mail_validator.py`-Lauf. Abhilfe bei Blockade: den Test ausführen, dann Validator grün
bekommen.

**„Un-überspringbar" gilt erst seit #1431 (2026-08-04) wirklich.** Davor entschied dieses Gate — wie
vier weitere — per Teilstring `"git commit"`, ob es überhaupt prüft; `git -C /pfad commit`,
`git -c k=v commit` und `git --no-pager commit` umgingen es **still**. Seit #1431 entscheidet
`hook_utils.is_git_subcommand` tokenbasiert (agent-os-openspec ≥ 3.10.0) mit umgedrehter Frage: nicht
„erkenne ich einen Aufruf?", sondern „bin ich sicher, dass hier keiner drinsteckt?".
**Merksatz für jede solche Zusicherung: nachmessen, nicht glauben.**

## Pendant-Sperre (#1481 B, seit 2026-08-04)

`pendant_gate.py` blockiert jeden Commit, der eine **neu angelegte** Datei in einem einseitigen
Bereich enthält — `frontend/src/lib/components/{compare,compare-new,trip-detail,trip-new}/**` und
`src/output/renderers/**/{compare_*,trip_*}.py` (rekursiv).

Zwei Auswege, beide ohne Rückfrage: die Datei unter `frontend/src/lib/components/shared/**` bzw. als
Renderer **ohne** `compare_`/`trip_`-Präfix ablegen — **oder** eine Kopfzeile
`gz-eigenstaendig: <fachlicher Grund>` in die ersten 20 Zeilen setzen (mind. 15 sinnvolle Zeichen).
**Der Ausweg verhindert nichts — er macht die Entscheidung im Änderungssatz zitierbar.**

**Namens-Erkennung (Spec #2346 S1, seit 2026-10-23):** Daneben prüft `_namenspendant()` Neuanlagen
(`A`, Umbenennung unter 95 % Ähnlichkeit) unter `frontend/src/lib/components/**`,
`frontend/src/routes/**`, `src/services/**` und `internal/handler/**` (Endungen `.svelte`, `.ts`,
`.py`, `.go`). Steht `compare`/`trip` am Anfang oder Ende des Dateinamens (CamelCase, lowerCamel,
snake_case), ist der Rest der Kernname; existiert im Repo (inkl. laufendem Änderungssatz) eine Datei
gleicher Endung mit dem Gegen-Präfix/-Suffix oder neutral mit dem Kernnamen, blockiert der Commit und
die Meldung nennt den Partner. Ein neues **neutrales** `Foo` neben `CompareFoo`/`TripFoo` ist
Konvergenz und löst nichts aus. Gleiche Auswege wie oben (nach `shared/` bzw. neutral benennen
**oder** `gz-eigenstaendig:`). Eine Störung der Namens-Erkennung lässt durch und meldet sich, ohne
die Ordner-Erkennung mitzureißen.

**Ausnahmeliste `BEKANNTE_PAARE`:** die Bestandspaare bei Einführung, fest im Hook. Sie darf nur
schrumpfen (Schrumpf-Test `tests/tdd/test_pendant_gate_bekannte_paare.py`); S2 streicht die
HomeHero*- und Kachel-Paare mit dem Löschen der Dateien. S3 hat nichts mehr zu streichen: es
ersetzt die Inline-Heros durch das neutrale `routes/_home/HomeHero.svelte`, benennt
`shared/CompareOutlookLayoutControls` neutral in `shared/OutlookLayoutControls` um und verschiebt
die compare-eigene Stundenverlauf-Steuerung nach `compare/CompareHourlyLayoutControls.svelte`
(mit `gz-eigenstaendig:`-Kopfzeile) — `shared/` enthält keine `Compare*`-Komponente mehr.

**Beleg:** 8 Paare außerhalb der alten Reichweite (Aufmaß 2026-10-23, nachgemessen Adversary F003),
die die Ordner-Erkennung nicht fangen konnte.
Das erste Aufmaß hatte 7 Paare außerhalb gezählt; `trip_forecast.py`/`forecast.py` war übersehen.

**Umlaut-Pfade (F007, 2026-10-24):** Der Wächter liest den Vormerk-Stand mit
`core.quotePath=false`. Vorher meldete git Umlaut-Pfade in Anführungszeichen, und **beide**
Erkennungen ließen sie still durch — auch die Ordner-Erkennung ist dadurch strenger geworden
(z. B. `compare/Übersicht.svelte` blockiert jetzt).

**Bewusste Grenzen** (Specs `docs/specs/modules/feat_1481b_pendant_gate.md`,
`docs/specs/modules/feat_2346_cockpit_paritaet.md`): ein neues `CompareFoo` **ohne** vorhandenen
Partner wird nicht erkannt; ähnliche, aber nicht namensgleiche Paare (z. B.
`compare_slot_scheduler.py`/`trip_report_scheduler.py`) bleiben unerkennbar; die Begründung wird auf
Länge geprüft (nicht auf Substanz), und ein Commit in ein **anderes** Verzeichnis wird nicht geprüft.
Eine reine Umbenennung (≥ 95 % Ähnlichkeit) einer neutralen Datei in einen Compare-/Trip-Namen neben
vorhandenem Partner (`Foo.svelte` → `CompareFoo.svelte` neben `TripFoo.svelte`) wird nicht erkannt
(Adversary F008, spec-konform).
Ausgenommen: Testdateien (Namens-Erkennung zusätzlich `*_test.go` und `test_*.py`) und der gesamte
Bestand — nur Neuanlagen greifen.
Prüfdatum 2027-01-21 (verlängert 2026-10-23, PO (Spec #2346); vorher 2026-11-03).

## Commit-Gate „Tests der berührten Dateien" (#1481 A, seit 2026-08-04)

`touched_tests_gate.py` blockiert jeden Commit, der einen Test rot macht, der zu einer der geänderten
Dateien gehört (Python/Go/Frontend). Vorbestehend rote Tests blockieren nicht — der Vorzustand wird an
einem Wegwerf-Abzug des letzten Commits **gemessen**, nicht gepflegt. Geprüft wird nur `tests/unit/`;
was ungeprüft blieb, nennt die Meldung. Abhilfe: den genannten Test reparieren oder löschen — nicht
drumherum arbeiten. Prüfdatum 2026-11-03.

## Test-Pfadregel-Ratsche (#1409, ab 2026-07-29)

Ein Test löst seinen **Prüfling** relativ zur eigenen Testdatei auf
(`Path(__file__).resolve().parents[2]`), NIE über den festen Hauptrepo-Pfad — sonst prüft er aus einem
Worktree die unveränderte Hauptrepo-Kopie und meldet **falsches Grün**. Bewusst fest bleibt die
**geteilte Ablage**: HEAD-Ermittlung, Attestation, `docs/artifacts`, `cwd` und Daten, die der Prüfling
über sein `cwd` liest (z. B. Soll-Bilder).

Durchgesetzt via `tests/tdd/test_repo_path_hardcoding_ratchet.py` (AST-Auflösung inkl.
Konstanten-Joins; Fund = Ziel liegt per `git ls-files` als Datei im Repo; Prüfdatum 2026-10-27).
Begründete Ausnahme als Kommentar **an der Zeile**: `# gz-main-path: <Begründung>` (mind. 15 sinnvolle
Zeichen). Grenzen — u. a. tote Pfade und Ketten ab 26 Gliedern — in
`docs/specs/modules/fix_1409b_repo_path_ratchet.md` unter „Known Limitations".

## Testnamens-Gate

Testdateien nach Verhalten benennen (`test_alert_throttle.py`), NICHT nach Issue-Nummer. Durchgesetzt
via `test_naming_gate.py`; Prüfdatum 2027-01-19 (verlängert 2026-10-21, PO). Bestand: 262 issue-nummerierte Dateien, Sanierung
läuft unter #1196.

Das Gate hatte sich am ursprünglichen Prüfdatum 2026-10-09 selbst abgeschaltet; der PO hat es am
2026-10-21 um 90 Tage verlängert (`EXPIRY = date(2027, 1, 19)` in `.claude/hooks/test_naming_gate.py`,
PR `tooling/hooks-pruefdaten`). Entscheidung behalten/entfernen am neuen Prüfdatum im Gate-Audit #1197.

**Kein Big-Bang-Reorg des Bestands (Tech-Lead-Entscheid 2026-08-08):** Testpfade sind hart verdrahtet
in `.github/ci_tdd_excludes.txt`, den Collection-Meta-Tests und den Ratschen — Massen-Umbenennung
bricht diese Wächter. Bestand nur opportunistisch (Datei ohnehin angefasst) oder themenweise mit
eigenem PR konsolidieren, in dem alle Referenzen mitgezogen werden.

## Breiter Testlauf gesperrt (ab 2026-08-03)

`uv run pytest` **ohne konkret benannte Testdateien** ist blockiert — voller Suite-Lauf und
Verzeichnis-Lauf. Grund: eine ungemarkerte Testdatei genügt, um echten Versand auszulösen; am
2026-08-03 gingen so echte Telegram-Nachrichten an den **Produktiv-Chat des PO** (#1477 —
`Settings(...)` fällt bei fehlenden Feldern still auf die Prod-`.env` im Worktree zurück, und ein
`mail_sink` schützt nur Mail). Durchgesetzt via `.claude/hooks/broad_test_run_gate.py`.

**Erlaubt:** Dateien benennen · `--collect-only` · `--disable-socket` (pytest-socket) · Einmal-Freigabe,
die **nur der User** durch Tippen von `override` erzeugt. Prüfdatum 2026-11-01.

## CI-Ratschen

### tdd-Ratsche
`.github/ci_tdd_excludes.txt` listet die offline-roten `tests/tdd/`-Dateien. Nur ENTFERNEN erlaubt
(Datei grün gemacht → Zeile raus); neue tdd-Dateien laufen automatisch auf CI. Ergänzen einer Zeile
nur mit Begründung im PR.

### e2e-Ratsche (umgekehrte Richtung)
`.github/ci_e2e_specs.txt` ist eine **Positivliste** und darf nur WACHSEN — eine Ausschlussliste würde
eine grüne Grundmenge voraussetzen, die eine Stichprobenmessung (30,6 % rot) widerlegt hat.
Stand nach #1771 S3 (2026-08-14): 45 Dateien / 224 Testfälle; **Stand 2026-10-26 (#2347 S1) laut `.github/workflows/ci.yml`: `E2E_MIN_SPECS: 64` Dateien, `E2E_MIN_EXECUTED_HAUPT: 369` Testfälle** (dort ist jeder Zuwachs einzeln kommentiert).

Aufnahme nur nach **Filter A** (strukturell) + **Filter B** (3× hintereinander grün) + **Filter C**
(die Datei darf beim Laufen keine *versionierte* Datei verändern — 3 Specs schrieben Screenshots ohne
`../` nach `frontend/docs/artifacts/`, das die Ignore-Regel `docs/artifacts/` nicht abdeckt).

🔴 **Filter B MUSS im ZIELVERBUND gemessen werden**, nie im Kandidatenverbund. Genau daran hing #1771
S3: zwei Dateien waren im 51er-Verbund grün und in der echten Positivliste **rot** —
`bug-703-login-ratelimit.spec.ts` feuert absichtlich 32 Anmeldungen gegen das IP-Limit von 30/Stunde
(`internal/router/router.go`) und verbrennt das Kontingent des **ganzen Jobs**; Playwright sortiert
**alphabetisch**, die CLI-Reihenfolge ist wirkungslos. Deshalb läuft die Datei in `ci.yml` als eigener,
nachgelagerter Aufruf. Bestandsdateien merken nichts davon (sie nutzen `storageState`) — es trifft nur
Dateien mit **eigenem** Login, also ausgerechnet Mandantentrennungs-Tests. **Der Split behandelt das
Symptom; beim nächsten Wachstum um Login-Tests neu bewerten.**

**Beide Schwellen exakt nachziehen, kein Puffer** (F006): `E2E_MIN_SPECS` ist mechanisch an die
Listenlänge gebunden (`tests/unit/test_e2e_positivliste_ratschen_bindung.py`, prüft auch Filter C);
`E2E_MIN_EXECUTED_HAUPT`/`_RATELIMIT`/`_PWA` bleiben **Handpflege** — ohne echten Browserlauf nicht
statisch ableitbar, als Known Limitation benannt statt als gelöst behauptet.

**Der rote Restbestand ist veraltet, nicht kaputt:** #1771 S3 hat 200 rote Testfälle diagnostiziert —
**0 echte Produktfehler**, dafür 22 gesuchte Testids, die es im Frontend nicht mehr gibt. Es gibt
**keinen gemeinsamen Hebel** (dreifach belegt, ADR-0054-Nachtrag) ⇒ jede weitere Aufnahme ist
Einzelfallarbeit. **Diese Messung nicht wiederholen.**

Specs: `fix_1771_s2_playwright_ci_ampel.md` (Lane), `fix_1771_s3_e2e_listen_wachstum.md` (Wachstum,
Verfahren, Abbruchgrenze).

### Compare-Paritäts-Wächter (#2347 S1, seit 2026-10-26)

`tests/unit/test_e2e_compare_paritaet_waechter.py` (Kern-Schicht, liest nur `frontend/e2e/*.spec.ts`)
setzt die Trip/Ortsvergleich-Teilung für E2E-Specs durch, die die Pendant-Sperre nicht erfasst:

- **Regel 1:** jede `*compare*.spec.ts` hat eine kind-Schleife (`HUB_KINDS` aus `frontend/e2e/helpers.ts`
  bzw. das Altmuster `for (const … of ['Trip', 'Vergleich'])`) oder in den ersten 30 Zeilen einen Kopf
  `gz-eigenstaendig: <Begründung, mind. 15 Zeichen>` (Themen laut Epic #2345: Orte-Tab, transponierte
  Übersicht, Compare-Mail; andere Gründe zulässig, aber begründet).
- **Regel 2 (gegen Umgehung per Dateiname):** jede andere Spec, die `compare-detail-tab` ansteuert und
  weder `trip-detail-tab` noch `/trips/` noch eine kind-Schleife noch einen Kopf enthält, ist ein Verstoß.
- **Ratschenmodus:** Altbestand steht als explizite Dateinamensliste `ALTLAST` (bei Einführung 48:
  46 × Regel 1, 2 × Regel 2; S2: 41 — 39 × Regel 1, 2 × Regel 2; S3a: 34 — 32 × Regel 1,
  2 × Regel 2), `ALTLAST_MAX` = jeweiliger
  Scheibenstand (Literal). Rot bei neuem Verstoß außerhalb der
  Liste, bei totem oder inzwischen konformem Eintrag („Eintrag entfernen") und bei Wachstum über
  `ALTLAST_MAX`. Fällt eine Spec weg (z. B. Löschscheibe #2243), muss ihr Eintrag im selben PR raus.
  #2347 S2–S4 leeren die Liste.

Neue Paritäts-Specs nutzen die dünnen Helfer `HubKind`/`HUB_KINDS`/`seedHub`/`openHub`/`hubApiPath`
(`frontend/e2e/helpers.ts`); Selektor-Unterschiede stehen als `HUB_SEL[kind]` im Spec, nicht im Helfer.
Bekannte Grenze: der Wächter erkennt die Schleife am Textmuster, nicht ob sie fachlich beide kinds prüft.

*Regel-Budget: Prüfdatum 2027-01-24, siehe Tabelle unten. Spec:
`docs/specs/modules/feat_2347_s1_paritaets_e2e.md`.*

### Dritter Playwright-Lauf: PWA-Strecke (`--project=pwa`, ab #2128)

Die PWA-Nachweise (`pwa-grundausstattung.spec.ts`, `pwa-update-und-abmelden.spec.ts`,
`pwa-offline-ansicht-mit-stand.spec.ts`, `pwa-offline-sperre-und-mandant.spec.ts`,
`pwa-update-erkennung.spec.ts` — Issue #2316, neu) laufen **nicht** über die Positivliste, sondern
über die feste Projektzuordnung in `frontend/playwright.config.ts`
(`testMatch: /pwa-.*\.spec\.ts/`, `testIgnore` schließt sie im Standardprojekt `tests` aus). Zwei
unabhängige Gründe, beide zwingend:

1. **Filter A schließt sie aus:** Die Dateien enthalten `waitForTimeout` als Nachweis für ein
   *Ausbleiben* (z. B. „die Seite hat NICHT neu geladen", „der wartende Worker hat NICHT
   übernommen") — ein Ausbleiben lässt sich nicht per Warte-Assertion erzwingen, nur abwarten.
   Aufnahme in `.github/ci_e2e_specs.txt` wäre ein Ratschen-Verstoß.
2. **Eigene Projekt-Einstellung nötig:** Alle fünf Dateien brauchen `serviceWorkers: 'allow'`; die
   Bestandsstrecke läuft bewusst mit `'block'` (Spec-AC-16), damit der seit #2128 auf jeder Seite
   registrierte Service Worker ihr Verhalten nicht verändert. Das ist eine Playwright-Projekt-
   Einstellung, keine Datei-Option — daher eigener CI-Schritt statt Aufnahme in eine der
   bestehenden Dateilisten.

Schutz gegen stilles Verschwinden einer Datei hängt hier **nicht** an einer Listenlänge, sondern an
`E2E_MIN_EXECUTED_PWA` (aktuell 61 = 60 Testfälle in 5 Dateien + `global.setup`, Issue #2316 auf den
Stand vom 2026-09-13 gehoben, Issue #2317 um den Fall AC-6 in `pwa-update-erkennung.spec.ts`
ergänzt): fällt eine Datei weg, sinkt `expected` darunter und das Gate wird rot.

**Die Reihenfolge ist kritisch: PWA-Lauf VOR dem bug-703-Ratelimit-Lauf** (gemessen 2026-09-06).
Die frühere Begründung — „unkritisch, weil `global.setup.ts` nur einloggt, wenn
`playwright/.auth/admin.json` fehlt/abgelaufen ist" — beschreibt nur `global.setup` und übersieht
den datei-eigenen `test.afterAll` in `pwa-update-und-abmelden.spec.ts`: der Nachweis „AC-11: Auf
allen Geräten abmelden" widerruft absichtlich **alle** Sitzungen inklusive der in `admin.json`, und
der Hook stellt sie mit **einem echten Login** wieder her. Lief bug-703 davor, war das IP-Kontingent
(30/Stunde, `internal/router/router.go:45`) leer, dieser Login lief in 429 und die Ampel wurde rot
(Playwright hängt den Hook-Fehler an das zuletzt gelaufene Ergebnis desselben Workers — gemeldet
wurde ein roter Testfall, der selbst nichts damit zu tun hatte). Innerhalb einer Stunde füllt sich
das Kontingent nicht wieder auf, ein Retry hilft nicht. bug-703 selbst braucht keinen Vorlauf und
läuft deshalb zuletzt. Details und Begründung ausführlich kommentiert in
`.github/workflows/ci.yml` (env-Block + Step „Playwright-Specs ausführen (Zweitlauf, PWA-Strecke
--project=pwa)").

## Thunder-Scale-Wächter (#1480, seit 2026-08-20)

Zwei Tests blockieren jede **neue** lokale Kopie der Gewitter-Stufenskala (`NONE`/`LOW`/`MED`/
`HIGH`) — egal ob als Dict/Liste/Tupel, als if/elif-Kette, als `match/case` oder als Zahlen-
Schwellenwert-Kette. Hintergrund: #1474 fand **neun** Stellen, die diese Zuordnung selbst
nachgebaut hatten, statt sie aus der kanonischen Quelle (`src/app/thunder_scale.py`) zu lesen —
drei stürzten ab, drei sagten Falsches, eine hatte die Reihenfolge vertauscht.

| Sprachraum | Wächter-Datei | Scanfläche |
|---|---|---|
| Backend | `tests/tdd/test_thunder_scale_local_copy_guard.py` | `src/**/*.py` + `api/**/*.py` (Produktivcode), zusätzlich `tests/**/*.py` (nur Paritäts-Behauptungen) |
| Frontend | `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/thunderScaleLocalCopyGuard.test.ts` | `frontend/src/**/*.{ts,svelte}` (Produktivcode), zusätzlich `frontend/**/*.test.ts` (nur Paritäts-Behauptungen) |

Schlägt einer der beiden Tests fehl, meldet er `Code reference: <Datei>:<Zeile>` — an genau der
Stelle, die eine eigene Kopie der Stufenskala anlegt.

**Was tun bei einem roten Fund:** Der saubere Weg ist fast immer, den Wert **aus der kanonischen
Quelle zu lesen** statt ihn selbst zu benennen (`src/app/thunder_scale.py` im Backend,
`frontend/src/lib/types.ts::ThunderLevel` im Frontend). Erst wenn das aus einem echten fachlichen
Grund nicht geht, kommt eine der drei Duldungsstufen infrage:

| Stufe | Wofür | Wer trägt sie ein |
|---|---|---|
| 1. Whitelist kanonischer Quellen (`ScaleSpec.canonical_symbols` / `CANONICAL_SYMBOLS`) | Ausschließlich für die kanonischen Quell-Dateien selbst (z. B. `thunder_scale.py`), symbolscharf, nicht dateiweit | Bereits gepflegt — im Alltag nicht anzufassen |
| 2. Benannte Altlasten-Basislinie (`ALTLASTEN`, nur Backend) | Ausschließlich die neun bekannten #1474-Fundstellen, symbolgeschlüsselt, darf nur **schrumpfen** | Bereits gepflegt — nie neue Einträge hinzufügen, nur sanieren und entfernen |
| 3. Marker-Kommentar an der Fundstelle | Der **einzig normale Weg für neuen Code**: eine bewusste, begründete Ausnahme | Wer die Zeile schreibt |

**Duldung per Marker-Kommentar** (Stufe 3, der einzige Weg für neue Fundstellen):

```python
# gz-thunder-scale: <mindestens 15 sinnvolle, mindestens 5 verschiedene Zeichen Begründung>
```
bzw. im Frontend `// gz-thunder-scale: <Begründung>`. „Sinnvolle Zeichen" sind Buchstaben und
Ziffern (Umlaute zählen mit), Leerzeichen/Satzzeichen/Unterstriche nicht. Eine zu kurze oder aus
Wiederholungen bestehende Begründung (`...............` oder `aaaaaaaaaaaaaaa`) bleibt rot. Der
einzige heutige Produktivcode-Fall: `src/output/renderers/narrow.py::_SEV_TO_THUNDER_LEVEL`.

**Regel D (Paritäts-Behauptung):** In Testdateien greift der Wächter nur, wenn eine Fixture per
Kommentar behauptet, mit der echten Quelle übereinzustimmen („1:1 aus …", „identische Reihenfolge"
u. Ä.) und dabei tatsächlich abweicht — eine bewusst vereinfachte Fixture ohne solche Behauptung
ist erlaubt.

*Regel-Budget: Prüfdatum 2026-11-01, siehe Tabelle unten. Detailmechanik, alle 24 Acceptance
Criteria und bekannte Grenzen: `docs/specs/modules/thunder_scale_guard.md`.*

## Store-Scope-Call-Guard (#2156, seit 2026-09-20)

Zwei Wächter setzen ADR-0003 (Mandantentrennung) strukturell durch, statt sie wie bisher allein
der Review-Disziplin zu überlassen:

| Sprachraum | Wächter-Datei | Scanfläche | Befundtyp |
|---|---|---|---|
| Go | `internal/handler/store_scope_call_guard_test.go` | `internal/handler/*.go` und `internal/store/*.go`, je ohne `_test.go` | Aufruf einer nutzergebundenen `*Store`-Methode **vor** der `WithUser`-Bindung; unklassifizierte oder fehlerhaft markierte Store-Methode |
| Python | `tests/test_router_user_id_required.py` | `api/routers/*.py` | Endpunkt mit `user_id`-Parameter, der einen Default trägt statt Pflichtparameter zu sein |

Die Auslösermenge des Go-Wächters ist **nirgends im Testcode kodiert**: Sie wird zur Testzeit per
`go/ast` aus `internal/store/*.go` abgeleitet (Methoden, deren Körper strukturell
`s.requireUser()` aufruft) und um die im Quelltext markierten Methoden ergänzt. Jede Abweichung
vom Regelfall steht damit begründet dort, wo sie wirkt — nicht als stille Positivliste im
Testcode (PO-Entscheid zur Spec v2.0).

### Marker-Syntax

Alle vier Marker folgen derselben Bauform: Markername, Doppelpunkt, **mindestens 15 sinnvolle
Zeichen** Begründung (Buchstaben und Ziffern zählen, Leer- und Satzzeichen nicht).

| Marker | Wo | Bedeutung |
|---|---|---|
| `// gz-store-scope-exempt: <Begründung>` | Doc-Kommentar der Methode in `internal/store/*.go` | Die Methode braucht **keine** `WithUser`-Bindung — sie nimmt die Kennung als Parameter, sucht kontoübergreifend, oder ist selbst der Bindungsmechanismus (`WithUser`). Heute **23** Stück. |
| `// gz-store-scope-required: <Begründung>` | ebenda | Die Methode ist nutzergebunden, obwohl sie `requireUser()` **nicht** ruft (baut Pfad oder Schlüssel direkt aus `s.UserID`). Heute **1** Stück: `LockBriefing`. |
| `// gz-store-scope-call: <Begründung>` | Kommentarzeile unmittelbar über der Aufrufzeile in `internal/handler/*.go` | Unterdrückt **genau diesen** Fund, wenn ein Handler eine Auslöser-Methode bewusst ohne Bindung ruft (etwa ein `requireLocalOnly`-Endpunkt). Heute **0** Stück. |
| `# gz-user-id-optional: <Begründung>` | Kommentarzeile über der Endpunkt-Funktion in `api/routers/*.py` | Erlaubt dort ausnahmsweise ein optionales `user_id`. Heute **0** Stück. |

**Der Marker muss in der Kommentargruppe stehen, die unmittelbar an die Deklaration grenzt.** Eine
Leerzeile dazwischen macht ihn zum *verwaisten* Marker und den Wächter rot. Trägt die Methode
bereits einen godoc-Kommentar, gehört der Marker als **letzte** Zeile dieser Gruppe direkt über
`func` — als erste Zeile würde er die godoc-Zusammenfassung verdrängen.

**Vier Wege, sich mit einem Marker rot zu machen** (Marker-Hygiene): doppelte Markierung (beide
Store-Marker an derselben Methode), Widerspruch (`exempt` an einer Methode, die `requireUser()`
ruft), Verwaisung (Marker an einem Namen, den es nicht gibt, oder an einer Stelle, die die Regel
ohnehin erfüllt) und eine Begründung unter 15 Zeichen. Auch ein `gz-store-scope-call`-Marker an
einer ohnehin gebundenen Aufrufstelle gilt als verwaist — sonst verrotten Marker zur stillen
Ausnahme, genau der Zustand, den die Marker-Konvention ablösen sollte.

**Marker sind Selbstauskunft, kein Beweis.** Ein falsch begründeter `gz-store-scope-exempt` an
einer tatsächlich nutzergebundenen Methode bleibt für den Wächter unsichtbar; dagegen hilft nur
Review. Die Marker machen die Ausnahme sichtbar und begründungspflichtig, sie belegen sie nicht.

*Regel-Budget: Prüfdatum 2026-12-20, siehe Tabelle unten. Alle acht Acceptance Criteria und die
bekannten Grenzen (kein interprozeduraler Fluss, keine Zweig-Analyse):
`docs/specs/modules/store_scope_call_guard.md`.*

## HERKUNFT-Zweig-Ratsche (#2276 Scheibe S6a, seit 2026-09-20)

**Ursprünglich als befristetes Messwerkzeug angelegt, seit Abschluss von S6h (2026-09-25) Dauer-Gate** für die 14 final akzeptierten HERKUNFT-Einträge (siehe Prüfdatum-Absatz unten). `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts`
hält eine **eingefrorene** `Datei:Zeile`-Liste (47 Einträge — unverändert seit S6d, auch nach
S6e; der Spec-Anhang misst noch 69 auf dem Vor-S6a-Stand `73f504c9`, eine davon,
`WeatherMetricsTab.svelte:577`, ist die per S6a AC-1 entfernte tote Bedingung,
`WeatherMetricsTab.svelte:1273` wurde per S6b AC-4/AC-5 **bewusst gestrichen**, nachdem der Guard
dort zeilentreu auf `if (!vergleichSpeicherung) return;` verkürzt war, S6c hat 14 der 18
`AlarmeTab.svelte`-Einträge gestrichen (`:256`, `:514`, `:533`, `:566` bleiben, Zeilennummern nach
dem Umbau), S6d hat 6 der 28 `CorridorEditor.svelte`/`CorridorEditorMobile.svelte`-Einträge
gestrichen (3 Zeilen-Paare; die übrigen 22 auf neue Zeilennummern nachgeführt, in
`BLEIBT_MIT_INHALT` inhaltlich gefesselt), und **S6e (GREEN `9d151ded`) hat 0 der drei
`VersandTab.svelte`-Einträge gestrichen** (alle drei sind Darstellungs-Zweige der
Route/Vergleich-Markup-Weiche, kein `wiz`-Symptom) — die drei wurden von `:284`/`:294`/`:330` auf
die neu gemessenen Zeilen `:348`/`:358`/`:394` nachgeführt und in `BLEIBT_MIT_INHALT` inhaltlich
gefesselt; `versandVergleichSpeicherung.ts:221` blieb dabei unverändert an Position, ohne neue
Fesselung (alter, positionsbasierter Vertrag), und **S6g (GREEN `3042b211`) hat ebenfalls 0 der
fünf `WeatherMetricsTab.svelte`-Einträge gestrichen** — sie wurden von `:545`/`:560`/`:589`/
`:602`/`:1323` auf die neu gemessenen Zeilen `:590`/`:605`/`:634`/`:647`/`:1439` nachgeführt und in
`BLEIBT_MIT_INHALT` inhaltlich gefesselt; `weatherMetricsCompareSave.ts:534` blieb dabei
unverändert an Position, ohne neue Fesselung (alter, positionsbasierter Vertrag, wie bei
`versandVergleichSpeicherung.ts:221` in S6e)) aller produktiven
`context ===`/`context !==`-Verzweigungen unter `shared/` und vergleicht sie zur Testlaufzeit
gegen den eingefrorenen Zählbefehl (`grep -rn 'context ===\|context !=='`, ohne Tests und
Kommentare). Die Liste ist **nicht** aus dem Verzeichnis abgeleitet, sondern als Array im
Testcode hinterlegt — sonst würde ein versehentliches Leeren der Ist-Menge den Test
vakuum-grün statt rot machen (Memory `ratsche_leeren_macht_den_abhaengigen_test_vakuum_gruen`).

**Zweck: Bezugsgröße für S6b–S6h.** Issue #2276s AC-2 verlangt am Ende von S6 keine
HERKUNFT-Verzweigung mehr in `shared/` (nur noch FACHLICH oder DARSTELLEND, siehe
`docs/specs/modules/rework_2276_s6a_totcode_und_ratsche.md`, Abschnitt „Abweichung vom
Ticket-AC-2"). Ohne benannte Soll-Liste ließe sich „entfernt" nicht von „verschoben"
unterscheiden. Jede Folgescheibe (S6b Wetter-Metriken/Layout, S6c Alarme, S6d Wertebereiche,
S6e Versand, S6f Bridge-Abbau, S6g WMT-Wertprops) muss die von ihr beseitigten Zeilen **bewusst**
aus der eingefrorenen Liste streichen — ein automatischer Nachzug beim Ändern von Code unter
`shared/` ist **kein** Bugfix, sondern zerstört die Schutzwirkung, weil er jede Verschiebung
stillschweigend als „gefangen" durchwinkt statt sie erneut zu benennen. 🔴 Stand S6g (Re-Cut
gegenüber dem ursprünglichen Schnitt): S6f hat entgegen der ursprünglichen Planung **nicht** alle
HERKUNFT-Zeilen entfernt — die AC-2-Endbilanz der verbleibenden Einträge (u. a. die fünf
`WeatherMetricsTab.svelte`-Positionen, die S6g nur nachführt, nicht streicht) geht an die
Folgescheibe **S6h**, die #2276 schließt (`rework_2276_s6g_wetter_metriken_wertprops.md`,
Abschnitt „Nicht in dieser Scheibe").

**S6h hat AC-2 nicht durch vollständige Entfernung erfüllt, sondern durch finale
Kategorisierung der 47 Einträge:** 27 FACHLICH, 6 DARSTELLUNG (beide unproblematisch für AC-2)
und 14 HERKUNFT. Anders als ursprünglich geplant werden diese 14 HERKUNFT-Einträge **nicht**
entfernt, sondern vom PO als dauerhafte Abweichung von AC-2 akzeptiert — die Auflösung bräuchte
eine neue Architekturentscheidung, deren Aufwand nicht im Verhältnis zum Nutzen steht
(`docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md`).

**Regel-Budget: Prüfdatum 2026-12-19, Ratsche bleibt nach S6h dauerhaft bestehen.** Kein Ersatz
für eine bestehende Regel — ursprünglich war sie von Anfang an auf Abschaltung nach S6f angelegt;
nach dem Re-Cut in S6g verschob sich das Ende auf S6h. Da S6h 14 HERKUNFT-Einträge dauerhaft
akzeptiert statt sie zu entfernen, entfällt die geplante Abschaltung: Die Ratsche bewacht diese 14
Einträge weiter als Drift-Schutz gegen unbeabsichtigtes Verschieben oder Entfernen und wird **zum
Prüfdatum nicht zurückgebaut** — abweichend von der generischen Regel-Budget-Regel (Fließtext
oben in diesem Abschnitt), weil der Fang (Schutz der PO-freigegebenen Abweichung) mit Abschluss
von S6h dauerhaft feststeht statt weiter offen zu sein. `EINGEFROREN_SOLL_ANZAHL` bleibt
unverändert 47.

## Trip-Schema-Drift-Gate `trip_schema_drift` (#2058, seit 2026-10-05)

Test-Paar `tests/test_trip_schema_drift.py` (Python) + `internal/model/trip_schema_drift_test.go`
(Go) auf der gemeinsamen, voll besetzten Fixture `tests/fixtures/trip_schema_full.json`. Beide
Seiten fahren einen echten Roundtrip (Python `_parse_trip` → `_trip_to_dict`, Go
`json.Unmarshal` → `json.Marshal`) und vergleichen die Schlüsselmengen auf Trip-, Etappen- und
Wegpunkt-Ebene mit der Fixture — in beide Richtungen. Hintergrund: Der Speicher-Merge ersetzt
Listen als Ganzes; ein nur einseitig bekanntes Feld ginge beim Speichern still verloren
(Präzedenzfall `suggestion_reason`). Entscheidung: Gate statt schlüsselbasiertem Listen-Merge.

**Benannte Allowlist** (identisch in beiden Tests): `send_premium_sms` (Trip, nur Go, aus
`report_config.send_premium_sms` abgeleitet) und `trip` (Trip, Python-Legacy-Wrapper, wird nie
geschrieben). Ein Allowlist-Eintrag, der in keinem Modell mehr vorkommt, macht den Test rot.

**Neues Trip-/Etappen-/Wegpunkt-Feld ⇒ in beiden Modellen + Fixture anlegen.** Ein Feld, das in
keinem Modell und nicht in der Fixture steht, fängt das Gate nicht — nur den einseitigen Fall.

*Regel-Budget: trip_schema_drift — Prüfdatum 2027-01-03, siehe Tabelle unten. Spec:
`docs/specs/modules/trip_schema_drift_gate.md`.*

## Aktive Hooks in `.claude/settings.json` — Kurzreferenz (Stand 2026-10-21)

Vollständige Liste der im Repo verdrahteten Hooks. Alle stehen in der geschützten Form
`if [ -f … ]; then python3 … ; fi` — **fehlt die Datei, läuft der Hook still als No-op.** Die
Workflow-Hooks (`workflow.py`, `workflow_gate`, Edit-Gate, `secret_egress_guard.py` u. a.) kommen
aus dem Plugin `agent-os-openspec` (`.claude/framework_version.json`: `plugin_mode: true`) und
liegen **nicht** in `.claude/hooks/`.

| Ereignis | Hook | Wirkung | Abschnitt / Beleg |
|---|---|---|---|
| PreToolUse Bash | `renderer_mail_gate.py` | blockt Commit an Mail-Inhalts-Dateien ohne frischen Matrix-Test + Validator | oben „Renderer-Commit-Gate" |
| PreToolUse Bash | `prod_send_gate.py` | blockt Bash-Kommandos, die einen echten Versand gegen Prod auslösen (Send-Pfad + Prod-Ziel Port 8000/8090 bzw. `gregor20.henemm.com` ohne `staging.` + kein reines GET) oder direkt `smtp.resend.com` ansprechen; Override `.claude/user_override_token.json` (TTL 1 h) | #1148, Spec `gate_1148_prod_send_deny.md` |
| PreToolUse Bash | `broad_test_run_gate.py` | blockt `uv run pytest` ohne benannte Testdateien | oben „Breiter Testlauf gesperrt" |
| PreToolUse Bash | `touched_tests_gate.py` | blockt Commit, der einen Test der berührten Dateien rot macht | oben „#1481 A" |
| PreToolUse Bash | `pendant_gate.py` | blockt Neuanlage einseitiger Trip-/Compare-Dateien | oben „Pendant-Sperre" |
| PreToolUse Bash | `pre_issue_close_design_gate.py` | blockt `gh issue close` bei Label `design-compliance` ohne bestandenes Design-Diff-Artefakt im aktiven Workflow | #603 |
| PreToolUse Bash | `secret_in_repo_gate.py` | blockt `git commit`, wenn eine vorgemerkte Datei den Klartextwert eines `.env`-Geheimnisses (`*_PASS`/`_TOKEN`/`_KEY`/`_SECRET`, ≥ 10 Zeichen) enthält; schaltet sich **nicht** automatisch ab, Wirksamkeitsprüfung 2026-11-04 | #1537 S1 |
| PreToolUse Write\|Edit | `test_naming_gate.py` | blockt neue issue-nummerierte Testdateien; Prüfdatum 2027-01-19 | oben „Testnamens-Gate" |
| PreToolUse Write\|Edit | `data_schema_backup.py` | Snapshot von `data/users/` nach `.backups/data-pre-rework-<ts>.tar.gz` vor Edit/Write an Schema-Dateien (Retention 20, übersprungen bei Snapshot < 5 Min) | CLAUDE.md „Daten-Schema-Reworks“, #102 |
| PreToolUse Write\|Edit | `file_claim_gate.py` | trägt jede bearbeitete Datei in `.claude/file_claims.json` (Hauptrepo) ein und blockt Edit/Write bei Belegung durch eine andere aktive Session; deaktiviert sich selbst ab 2026-11-11 | PO-go 2026-08-13 |
| PostToolUse * | `secret_output_gate.py` | ersetzt Klartextwerte von `.env`-Geheimnissen in **Tool-Ergebnissen** durch `***<SCHLÜSSEL>***` | #1537 S2 |
| UserPromptSubmit | `context_budget_guard.py` | `⚑`-Zeile ab 180k Kontext, Aufforderung zu `/clear` ab 260k; blockiert nie | CLAUDE.md „Parallele Sessions & Token-Budget" |
| Stop | `terminology_gate.py` | weist eine Antwort mit „Tour"/„Touren" zurück (Exit 2; Zitatzeilen `>` ausgenommen; fail-open) | Produktbegriffe Trip/Etappe/Ortsvergleich/Briefing |
| Stop | `track_token_usage.py` | schreibt Token-Verbrauch ins Workflow-State-JSON (`token_usage`); immer Exit 0 | #829 |
| Stop | `notify_sound.py` | Benachrichtigungston | — |
| SessionStart | `/home/hem/claude-mq/check-messages.sh` | MQ-Posteingang prüfen (Pfad außerhalb des Repos) | `~/.claude/CLAUDE.md` |

**Nicht in `settings.json` verdrahtet**, aber in `.claude/hooks/` vorhanden und manuell bzw. von
Skripten/Skills aufgerufen: `staging_gate.py`, `prod_selftest.py`, `briefing_mail_validator.py`,
`email_spec_validator.py`, `official_alert_mail_validator.py`, `radar_alert_mail_validator.py`,
`e2e_frontend_browser_gate.py`, `e2e_browser_test.py`, `e2e_telegram_live.py`, `design_fidelity_diff.py`,
`e2e_commit_gate.py` (blockiert seit #339 nichts mehr, nur Hinweis + `detect_scope()`).
`data_schema_backup.py` ist seit PR `tooling/hooks-pruefdaten` (2026-10-21) als PreToolUse `Write|Edit` verdrahtet (Tabelle oben); vorher fehlte der Eintrag trotz gegenteiliger Doku.

## Regel-Budget: Prüfdaten im Überblick

| Regel / Gate | Prüfdatum | Fang-Beleg bei Einführung |
|---|---|---|
| Mutations-Gegenprobe | 2026-11-01 | #1448 (2 von 3 Scheiben), #1457 (6 Findings) |
| Breiter Testlauf gesperrt | 2026-11-01 | #1477 (echter Telegram-Versand an Prod-Chat) |
| CI-Ampel (eingeführt mit 5 Checks; seit #1771 S2 sechs, s. eigene Zeile `e2e`) | 2026-11-02 | 6 wochenlang unbemerkte test-Rote + ~5000 unbewachte tdd-Tests (#1196) |
| Pendant-Sperre (#1481 B, erweitert #2346) | 2027-01-21 (verlängert 2026-10-23, PO (Spec #2346)) | 8 Paare außerhalb der alten Reichweite (Aufmaß 2026-10-23, nachgemessen Adversary F003; Spec #2346) |
| Touched-Tests-Gate (#1481 A) | 2026-11-03 | — |
| Testnamens-Gate | 2027-01-19 (verlängert 2026-10-21, PO) | — |
| Test-Pfadregel-Ratsche (#1409) | 2026-10-27 | — |
| Datei-Claim-Gate `file_claim_gate.py` | 2026-11-11 (Selbstabschaltung im Hook) | — |
| Secret-in-Repo-Sperre `secret_in_repo_gate.py` (#1537 S1) | 2026-11-04 (Wirksamkeitsprüfung, **keine** Selbstabschaltung) | #1537 (`GZ_AUTH_PASS` im Klartext im öffentlichen Repo) |
| Frontend-Browser-Gate (#1558) | 2026-11-05 | #1552 (Kernseite unbedienbar bei grüner Ampel) |
| 6. Check `e2e` (#1771 S2) | 2026-11-11 | offen — Kriterium: eine Regression, die die anderen fünf durchlassen |
| staging_gate — `frontend/e2e/` nicht als Code klassifiziert (#1197) | 2026-11-15 | Live erlebt 2026-08-15 (PR-Stack #1736/#1852/#1881/#1882), Fix folgt |
| Thunder-Scale-Wächter — keine neue lokale Kopie der Gewitter-Stufenskala (#1480, Backend + Frontend) | 2026-11-01 | 8 von 8 Python-Verstößen aus #1474 (`860a3baf^`) gefangen; Frontend 8 von 8 SYNTH-Formen inkl. der neunten Stelle (`['NONE','MED','HIGH','LOW']`) |
| `_SELF_EXEMPT`-Eintrag `test_gehzeit_metriken_bleiben_trip_exklusiv.py` in `test_765_backend_hygiene_compliance.py` (#1848 C) | 2026-11-17 | Kommentar-Wächter liest `src/app/metric_catalog.py` als DATEN für eine AST-Prüfung (sind in Kommentaren genannte Funktionsnamen auflösbar?) — kein Verhaltensnachweis auf Code-Strings; Freigabe Tech-Lead 2026-08-19 |
| Gestellte-Uhr-Ratsche make_trip+save_trip (#2242) | 2026-12-08 | 3 Dateien in 3 Wochen nach #2050 ungeschützt (#2242) |
| `user_id="default"`-Wächter — keine Defaults in `api/`, fixierte Bestandsliste in `src/` (#2151 Scheibe A); erweitert um Aufrufstellen-Prüfung (kein Literal `"default"` als `user_id`-Argument, `tests/test_user_id_default_guard.py`) und Test-Inventar `tests/test_test_suite_passes_user_id_explicitly.py` (#2151 Scheibe C) | 2026-12-18 | — |
| Store-Scope-Call-Guard — Store-Aufruf ohne vorherige `WithUser`-Bindung (Go, `internal/handler/store_scope_call_guard_test.go`) und `user_id` als Pflichtparameter in `api/routers/` (Python, `tests/test_router_user_id_required.py`); Ausnahmen nur als begründeter Marker im Quelltext (#2156) | 2026-12-20 | offen — startet bewusst bei 0 Befunden (24 Marker gesetzt). Kriterium: ein Handler oder Endpunkt, der ohne Bindung bzw. mit optionalem `user_id` ausgeliefert worden wäre |
| HERKUNFT-Zweig-Ratsche `context_herkunft_zweige_eingefroren.test.ts` (#2276 Scheibe S6a) — seit S6h (2026-09-25) dauerhaftes Drift-Schutz-Gate für die final 14 akzeptierten HERKUNFT-Einträge, **kein Rückbau zum Prüfdatum** (Ausnahme von der generischen Regel-Budget-Regel, siehe Fließtext oben) | 2026-12-19 | offen — startet bei 68 Fundstellen (Stand `a789b4b5`, nach S6a), 67 nach dem S6b-Rückbau von `WeatherMetricsTab.svelte:1273`, 53 nach dem S6c-Rückbau von 14 der 18 `AlarmeTab.svelte`-Einträge, 47 nach dem S6d-Rückbau von 6 der 28 `CorridorEditor.svelte`/`CorridorEditorMobile.svelte`-Einträge, unverändert 47 durch S6e, S6g und S6h (S6h kategorisiert final: 27 FACHLICH, 6 DARSTELLUNG, 14 HERKUNFT dauerhaft akzeptiert). Kriterium: eine unbeabsichtigt **verschobene** oder entfernte der 14 dauerhaften HERKUNFT-Verzweigungen, die ohne die eingefrorene Liste unbemerkt bliebe |
| Invarianten-Test Einstellung = Auslieferung (#2422 S1) | 2026-12-25 | KHW 403 (#2422): B1/B2/B3/B5 als Register-Einträge sichtbar |
| ADR-0049-Kanallisten-Ratsche `tests/test_adr0049_kanalliste_ratsche.py` — Dreier-Kanalliste ohne `premium_sms` nur mit Marke `ADR-0049` (#2229) | 2026-12-30 | — (bei Einführung 8 bewusst dreistellige Listen markiert; echter Fang offen) |
| Trip-Schema-Drift-Gate `trip_schema_drift` — Test-Paar `tests/test_trip_schema_drift.py` + `internal/model/trip_schema_drift_test.go`, Allowlist `send_premium_sms`/`trip` (#2058) | 2027-01-03 | `suggestion_reason` nur in Python (Go-Editor-Save verwarf es still), bei Einführung geschlossen |
| Egress-Struktur-Wächter `tests/tdd/test_egress_single_dial_point.py` — `smtplib` (#1412 S3a) und `httpx`-POST (#1412 S3b) nur an den erlaubten Ausgängen (`TelegramOutput._post`, `SevenIoChannelBase._post`), Deckel 3 localhost-Ausnahmen | 2027-01-04 | `seven_io_base.py:171` (`httpx.post` direkt in `SevenIoChannelBase.send`) bei Einführung gefangen und in `_post` verlegt |
| Compare-Paritäts-Wächter `tests/unit/test_e2e_compare_paritaet_waechter.py` — jede `*compare*.spec.ts` bzw. Compare-Hub-Spec ohne Trip-Gegenstück braucht kind-Schleife oder `gz-eigenstaendig:`-Kopf; Altlastliste nur schrumpfend (#2347 S1, Epic #2345 P6) | 2027-01-24 | Regel 2 fand bei Einführung 2 Specs außerhalb der Compare-Dateinamen (`kanal-grenzen-ortsvergleich.staging.spec.ts`, `versand-tab-vergleich.spec.ts`); fehlende Trip-Cross-User-Schreibprüfung (geschlossen durch `hub-cross-user-write-block.spec.ts`) |

**Weitere Prüfdaten, die nur im Code stehen** (Abgleich 2026-10-21 per
`grep -rn "Prüfdatum\|Pruefdatum" tests .claude/hooks`; Fang-Beleg hier nicht erhoben):

| Wächter-Datei | Prüfdatum |
|---|---|
| `tests/test_adr_index_drift.py` (ADR-Index ↔ Dateien, in CLAUDE.md genannt) | 2027-01-19 (verlängert 2026-10-21, PO: Doku-Audit fand reale Drift) |
| `tests/test_api_contract_drift.py` (Routen + Kern-Struct-Tags ↔ `api_contract.md`) | 2027-01-19 (verlängert 2026-10-21, PO: Doku-Audit fand reale Drift) |
| `tests/test_resolution_loss_guard.py` | 2026-10-26 |
| `tests/test_success_status_guard.py` | 2026-10-26 |
| `tests/unit/test_compare_hourly_vocabulary_single_source.py` | 2026-10-30 |
| `tests/unit/test_sms_token_symbol_register_ratchet.py` | 2026-10-30 |
| `tests/tdd/test_data_root_hardcoding_ratchet.py` | 2026-11-07 |
| `tests/tdd/test_fixture_wallclock_ratchet.py` | 2026-11-08 |
| `tests/unit/test_metrik_listen_register_ratchet.py` (+ `tests/helpers/metrik_listen_scan.py`) | 2026-11-15 |
| `tests/test_output_timezone_guard.py` | 2026-11-18 |
| `tests/test_pii_log_guard.py` | 2026-12-26 |

Am Prüfdatum gilt: kein nachweisbarer Fang → **Rückbau**. Wirkmodell:
`docs/analysis/backlog-spirale-2026-07.md`.

## Grundprinzip aller Wächter

Beide Commit-Gates aus #1481 — und das Frontend-Browser-Gate — lassen bei **eigener** Störung immer
durch und sagen es. Ein defektes Gate darf nie die Ursache sein, dass nicht mehr gearbeitet werden
kann. Umgekehrt gilt: „Nachweis nicht erbringbar" ist **kein** Gate-Defekt und blockiert.
