---
entity_id: fix_1284_admin_prod_testdata
type: bugfix
created: 2026-07-16
updated: 2026-07-16
status: draft
workflow: fix-1284-e2e-leichen-prod
---

# Issue #1284 — `admin`-Testdaten-Sammelbecken im Prod-Baum entfernen + E2E-Prod-Leck an der Netzwerk-Wurzel schließen

## Approval

- [x] Approved — PO-„go" 2026-07-16 (inkl. wörtlich vorgelegter Known Limitations)

## Purpose

Das Konto `admin` im Produktiv-Datenbaum (`/home/hem/gregor_zwanzig/data/users/admin/`)
ist über Monate zum E2E-Testleichen-Sammelbecken geworden: 153 Vergleichs-Abos, davon
149 mit `@example.com`-Empfängern, 133 täglich um 06:00 fällig. Ursache ist kein
Domain-Leck (der Empfänger-Guard blockt `example.com` lückenlos), sondern verbrannte
Rechenzeit — und ab dem nächsten 06:00-Lauf ein echter Timeout, weil die 2s-Inter-Mail-Pause
(seit `9c8fb30c`) für 132 Presets in einem einzigen HTTP-Request gegen das 120s-Timeout des
Go-Schedulers läuft. Dieses Modul (a) entfernt den gesamten `admin`-Baum aus dem
Produktiv-Datenbaum mit Backup, und (b) schließt die Netzwerk-Wurzel des Lecks —
Playwright-Läufe proxyen künftig standardmäßig gegen Staging statt Prod, unabhängig von
Spec-Auswahl oder Login-Konto.

## Source

- **File:** `scripts/cleanup_1284_admin_prod.py` (neu)
- **Identifier:** `run_cleanup` (Kernfunktion, Muster analog `scripts/cleanup_1265_prod_testdata.py`)
- **Weitere Kernstellen:** `frontend/vite.config.ts:7-14` (Proxy-Ziel), `frontend/e2e/prodUrlGuard.ts:18-31`
  (bestehender Guard), `src/services/dispatch_orchestrator.py:179-185` (Inter-Mail-Pause),
  `internal/scheduler/scheduler.go:82` (120s-Timeout), `internal/store/user.go` (`ListUserIDs`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `scripts/cleanup_1265_prod_testdata.py` | Vorbild-Skript | Muster für Dry-Run/Execute, tar.gz-Backup, Idempotenz, Fail-Fast auf fehlende echte Konten |
| `ListUserIDs` (`internal/store/user.go`) | Funktion | Erkennt Nutzer über Verzeichnis-Präsenz + `user.json` — Grund, warum das Löschen des gesamten Baums `admin` aus dem Scheduler-Lauf entfernt |
| `runForAllUsers` (`internal/scheduler/scheduler.go:148-183`) | Funktion | Ruft `compare-presets-daily` pro User einzeln auf; nach dem Cleanup entfällt der Aufruf für `admin` komplett |
| `prodUrlGuard.ts` (#1265 Teil D) | Guard | Bestehender E2E-Prod-Schutz, wird um `assertNotProdApiProxyTarget` erweitert |
| `dispatch_orchestrator.py:179-185` (`run_briefing_dispatch`) | Funktion | Quelle der 2s-Pause pro Preset — bleibt unverändert (PO-Entscheid #1207), betroffen ist nur die Anzahl der Presets |
| `data_schema_backup.py` / `.backups/` | Hook/Ablage | Backup-Konvention, analog #1265 |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `scripts/cleanup_1284_admin_prod.py` | CREATE | Purge von `data/users/admin/` (Backup, Fail-Fast, idempotent) |
| `tests/test_cleanup_admin_prod_purge.py` | CREATE | Kern-Test gegen tmp-Fixture-Baum (verhaltensbasierter Name, nicht issue-nummeriert) |
| `frontend/e2e/apiProxyTarget.ts` | CREATE | Geteilte Konstante (Single Source of Truth für das Proxy-Ziel) |
| `frontend/vite.config.ts` | MODIFY | Proxy-Ziel importiert die geteilte Konstante statt Literal `8090` |
| `frontend/e2e/prodUrlGuard.ts` | MODIFY | Neue Funktion `assertNotProdApiProxyTarget` |
| `frontend/e2e/global.setup.ts` | MODIFY | Ruft die neue Guard-Funktion zusätzlich zum bestehenden Hostname-Check auf |
| `frontend/src/lib/__tests__/e2e_prod_url_guard.test.ts` | MODIFY | Testfälle für `assertNotProdApiProxyTarget` (wirft bei 8090, nicht bei 8091) |
| `frontend/src/lib/__tests__/vite_proxy_target.test.ts` | CREATE | Prüft das aufgelöste Proxy-Ziel der Vite-Konfiguration gegen die geteilte Konstante (kein Dateiinhalt-Grep) |

### Estimated Changes
- Files: 8
- LoC: ~175-215 (Limit 250, wenig Puffer)

## Implementation Details

### AC-1 — Aufräumen: ganzer `admin`-Baum, nicht nur `briefings/`

`ListUserIDs()` erkennt Nutzer über Verzeichnis-Präsenz plus `user.json` — kein globaler
Index. Fällt `data/users/admin/` ganz weg, taucht `admin` in `ListUserIDs()` nicht mehr auf,
und `runForAllUsers` ruft für `admin` keinen Endpoint mehr auf. Das ist strukturell stärker
als „nur `briefings/` leeren" (das würde `admin` als 0-Presets-Konto weiterschleppen und
bliebe von der `IsTestUserID`-Heuristik abhängig, die den Namen nicht erkennt).

Neues, eigenständiges Skript `scripts/cleanup_1284_admin_prod.py` (nicht das 1265er
erweitern — das würde dessen `NEVER_DELETE`-Semantik für alle Aufrufer verwässern):
- Hartkodiertes Ziel `users_root / "admin"` — kein generischer `--user`-Parameter
  (Fehlbedienungs-Schutz)
- Fail-Fast: `default`, `henning`, `steffi`, `validator-issue110` müssen unter `--root`
  existieren (analog `_missing_real_accounts` aus #1265) — sonst Abbruch ohne Löschung
- Backup `data/.backups/cleanup-1284-<timestamp>.tar.gz` nur von `data/users/admin/`
- `shutil.rmtree`, idempotent (zweiter Lauf: 0 Aktionen, kein Leer-Backup)
- Läuft auf dem Prod-Host als `claude-gregor` gegen den absoluten Pfad
  `/home/hem/gregor_zwanzig/data` — reiner Host-Schritt, **kein Teil des Code-Deploys**.
  `data/` im Worktree ist ein anderer Baum (andere Inode) und darf nicht mit dem Prod-Pfad
  verwechselt werden.

### AC-2/AC-4 — Wurzel-Fix: Proxy-Ziel + Guard-Erweiterung + Staging-Login-Konto

Der Bug sitzt im Proxy-Ziel, nicht in der baseURL und nicht in der Spec-Auswahl:
- `frontend/vite.config.ts`: Proxy-Ziel für `/api` wechselt von `8090` (Prod) auf `8091`
  (Staging-Go, läuft dauerhaft). Damit trifft jeder `npx playwright test`-Lauf Staging,
  unabhängig von Spec-Auswahl oder Login-Konto.
- `prodUrlGuard.ts` bekommt `assertNotProdApiProxyTarget`. Das Ziel liegt in einer
  geteilten Konstante (`frontend/e2e/apiProxyTarget.ts`), die `vite.config.ts` **und** der
  Guard importieren — damit prüft der Guard nicht gegen eine Kopie des Werts. Override
  über `GZ_E2E_API_PROXY_TARGET`, Default `http://localhost:8091`.
- `global.setup.ts` ruft die neue Guard-Funktion (`await`, s.u.) zusätzlich zum bestehenden
  Hostname-Check auf.

**Guard-Mechanik — Nachtrag 2026-07-17, nach drei Adversary-Runden (F004/F011/F012):**
Die ursprünglich hier beschriebene **Namensprüfung** ist gescheitert und wurde ersetzt. Chronik,
weil die Fehlerklasse lehrreich ist:

| Runde | Mechanik | Bypass, real belegt |
|---|---|---|
| 1 | exakter String-Vergleich gegen `http://localhost:8090` | `http://127.0.0.1:8090` — derselbe Socket |
| 4 | Sperrliste bekannter Loopback-Hostnamen | `http://localhost.:8090` — DNS-Trailing-Dot, HTTP 200 vom Prod-Server |
| 5 | Positivliste gegen `EXPECTED_ORIGIN` | tautologisch: `global.setup.ts` übergab denselben Wert, aus dem `EXPECTED_ORIGIN` berechnet wurde → konnte nie ablehnen. `http://localtest.me:8090` (öffentlicher Loopback-Alias) durch |

**Endstand (PO-Entscheid 2026-07-17):** keine Namensprüfung mehr, sondern eine
**wirkungsbezogene** Prüfung — Hostname via `dns.promises.lookup(h, {all:true})` auflösen;
liegt **irgendeine** aufgelöste Adresse im Loopback-Bereich (`127.0.0.0/8`, `::1`, `::`,
`0.0.0.0`, IPv4-mapped in beiden Notationen) **und** ist der Port der Prod-Port 8090 → wirf.
Fail-closed bei nicht parsebarer URL und bei nicht auflösbarem Hostnamen. Die Funktion ist
dadurch `async`; `global.setup.ts:27` `await`et sie, `playwright.config.ts:13-19` verkettet
das Setup als `dependencies`, sodass ein Wurf nachgelagerte Projekte blockiert.

Grund für den Wechsel: Eine Liste verbotener Schreibweisen ist endlich, die Menge der
Schreibweisen derselben Adresse ist es nicht. Die Auflösungs-Prüfung stellt die einzig
belastbare Frage — *landet dieses Ziel auf dem Prod-Socket?* — und erledigt damit auch jeden
künftigen Alias.
- `start-preview.sh` bleibt unangetastet (setzt keine Variable, die das neue Ziel
  überschreiben würde) — der sichere Default gilt unabhängig von der gesourceten `.env`.
- `testMatch` in `playwright.config.ts` bleibt unverändert — sobald Prod netzwerkseitig
  unerreichbar ist, ist irrelevant, welche Specs ein blankes `npx playwright test` einzieht.

**Zusätzlicher Schritt — E2E-Login-Konto auf Staging anlegen (Nachprüfungs-Befund):**
Empirisch bestätigt (curl gegen die laufenden Server, Feldname `username`): Prod-Go 8090
akzeptiert `admin`/`test1234` (200), Staging-Go 8091 lehnt dasselbe Login ab (401) — im
Staging-Datenbaum (`/home/hem/gregor_zwanzig_staging/data/users/`) existiert `admin` schlicht
nicht. `frontend/e2e/helpers.ts:11-12` und `global.setup.ts:26-27` loggen per Default als
`admin`/`test1234` ein. Ohne Gegenmaßnahme macht der Proxy-Wechsel jeden Standard-Playwright-Lauf
lauffähig-tot (401 beim Login). Deshalb wird als Teil dieses Moduls ein Konto
`admin`/`test1234` im **Staging**-Baum angelegt — per-Host-Schritt (über den bestehenden
Registrierungs-Mechanismus, z.B. `POST /api/auth/register` gegen den Staging-Server), als der
Nutzer, dem die Staging-Daten gehören, analog zum Prod-Cleanup-Schritt, **nicht** Teil des
Code-Deploys und ohne neue Quelldatei. Testdaten auf Staging sind erwünscht — genau dorthin
sollen die 13 teardown-losen Specs künftig schreiben.

**Reihenfolge:** Das Staging-Login-Konto muss angelegt sein, **bevor** der Proxy-Wechsel
(`vite.config.ts`) deployt wird — sonst ist die Suite zwischen den beiden Schritten rot.

Wiederholbarer Check als Erweiterung der bestehenden CI-TS-Gates (`npm test`,
`.github/workflows/ci.yml:66`) — kein neues Pflicht-Gate: `e2e_prod_url_guard.test.ts`
bekommt Fälle für `assertNotProdApiProxyTarget`; ein neuer Test (`vite_proxy_target.test.ts`)
importiert die Vite-Konfiguration und prüft das aufgelöste Proxy-Ziel für `/api`
(`server.proxy['/api'].target`) gegen die geteilte Konstante — kein Dateiinhalt-Grep auf das
Literal `8090`.

### AC-3 — Zeitbudget: Folge von AC-1, kein eigener Mechanismus

Nach AC-1 existiert `data/users/admin/` nicht mehr, `admin` fällt aus `ListUserIDs()`,
der Endpoint wird für dieses Konto nie mehr gerufen. Die 264s-Pause (132 × 2s) verschwindet,
weil die zugrundeliegenden Presets verschwinden — nicht weil der Pause-Mechanismus selbst
geändert wird. `henning` mit 9 Abos bleibt bei maximal 8×2s = 16s zzgl. Rendering, weit unter
dem 120s-Timeout. Der 2s-Delay in `dispatch_orchestrator.py:179-185` wird nicht angefasst
(PO-Entscheid #1207); dass er auch bei sofort scheiternden Presets läuft, ist eine bekannte,
hier nicht behobene Robustheits-Schwäche (siehe „Nicht Teil dieser Spec").

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1 (Python, Kern, tmp-Fixture): GIVEN ein tmp-Baum mit `admin/` (inkl. `user.json`,
      `briefings/*.json`) sowie den vier echten Konten `default`/`henning`/`steffi`/
      `validator-issue110` WHEN `run_cleanup(..., execute=True)` läuft THEN existiert vorher
      ein tar.gz-Backup von `admin/`, danach ist `admin/` vollständig entfernt, und die vier
      echten Konten sind byte-identisch unverändert.
- [ ] Test 2 (Python, Kern, tmp-Fixture): GIVEN ein tmp-Baum ohne eines der vier echten Konten
      (z.B. `steffi` fehlt) WHEN das Skript mit `--execute` läuft THEN bricht es ohne Backup
      und ohne Löschung ab (Fail-Fast-Schutz gegen falschen `--root`).
- [ ] Test 3 (Python, Kern, tmp-Fixture): GIVEN ein bereits bereinigter tmp-Baum (kein
      `admin/` mehr vorhanden) WHEN das Skript ein zweites Mal mit `--execute` läuft THEN
      werden 0 Aktionen ausgeführt und kein neues Backup geschrieben (Idempotenz).
- [ ] Test 4 (TS, `e2e_prod_url_guard.test.ts`): GIVEN das Proxy-Ziel `http://localhost:8090`
      WHEN `assertNotProdApiProxyTarget` aufgerufen wird THEN wirft die Funktion; GIVEN
      `http://localhost:8091` THEN läuft sie ohne Fehler durch.
- [ ] Test 5 (TS, `vite_proxy_target.test.ts`, Verhaltens-Check statt Dateiinhalt-Grep):
      GIVEN die tatsächliche Vite-Konfiguration (importiert, nicht als Text gelesen) WHEN
      der Test das aufgelöste Proxy-Ziel für `/api` ausliest (`server.proxy['/api'].target`)
      THEN entspricht dieser Wert der geteilten Konstante aus `apiProxyTarget.ts` und ist
      **nicht** `http://localhost:8090` — geprüft wird der Wert, der tatsächlich proxyt, nicht
      eine Zeichenkette im Quelltext. Zeigt sich beim Umsetzen, dass `vite.config.ts` wegen
      der Funktions-Form von `defineConfig` nicht direkt importierbar ist, ist das ein
      TDD-Befund; Rückfallebene ist dann ein als Doku-Compliance-Test markierter Source-Scan
      (Äquivalent zu `# doc-compliance-test`), zusammen mit einem entsprechenden Eintrag in
      den Known Limitations.

## Acceptance Criteria

- **AC-1:** Given der Produktiv-Datenbaum mit dem vollständigen `admin`-Testdaten-Sammelbecken
  (inkl. `user.json` und aller Vergleichs-Abos) / When das Bereinigungs-Skript mit `--execute`
  gegen `/home/hem/gregor_zwanzig/data` läuft / Then existiert vorher ein tar.gz-Backup, danach
  ist `data/users/admin/` vollständig verschwunden (kein Login mehr unter `admin`/`test1234`
  im Prod-Baum möglich), und die vier echten Konten `default`, `henning`, `steffi`,
  `validator-issue110` sind byte-identisch unangetastet.
  - Test: Test 1 + Test 3 (Idempotenz) gegen tmp-Fixture; Prod-Nachweis nach Ausführung per
    `ls data/users/` (kein `admin` mehr) und Backup-Datei unter `data/.backups/`.

- **AC-2:** Given ein Standard-Playwright-Lauf mit lokalem `webServer` (`localhost:4173`) /
  When irgendeine Spec eine HTTP-Anfrage über den `/api`-Proxy stellt / Then landet diese
  Anfrage beim Staging-Go-Server (Port 8091), nicht beim Produktiv-Go-Server (Port 8090) —
  unabhängig davon, unter welchem Login-Konto oder welcher Spec-Auswahl der Lauf gestartet
  wurde — UND der Standard-Login (`admin`/`test1234`) kommt durch, weil dieses Konto zuvor im
  Staging-Datenbaum angelegt wurde, sodass die Testsuite lauffähig bleibt und ihre Daten im
  Staging-Baum statt im Prod-Baum landen. Ein Fix, der Prod schützt, aber die Suite durch
  einen fehlschlagenden Login lahmlegt, erfüllt dieses AC nicht.
  - Test: Test 4 (Guard wirft bei 8090, läuft durch bei 8091) + Test 5 (aufgelöstes
    Proxy-Ziel geprüft, kein Dateiinhalt-Grep); manueller Nachweis via Netzwerk-Log eines
    lokalen Testlaufs plus erfolgreicher Login-Check gegen Staging nach Anlage des Kontos.

- **AC-3:** Given der bereinigte Produktiv-Datenbaum nach AC-1 (kein `admin`-Konto mehr in
  `ListUserIDs()`) / When der Go-Scheduler den nächsten `compare-presets-daily`-Cron-Tick
  ausführt / Then bleibt die HTTP-Anfrage für das verbleibende Compare-Konto (`henning`,
  9 Abos) deutlich unter dem 120s-Timeout, weil die für `admin` zuvor nötige 264s-Pause
  durch das Verschwinden der zugrundeliegenden Presets entfällt — nicht durch eine Änderung
  am Pause-Mechanismus selbst.
  - Test: Kein separater Kern-Test — Nachweis **sofort nach dem Cleanup**, ohne auf 06:00 zu
    warten: `POST /api/scheduler/compare-presets-daily?user_id=henning&hour=6` gegen die
    interne Python-API (Port 8000) mit Zeitmessung; erwartet < 120s. Zusätzlich muss der
    Aufruf mit `user_id=admin` fehlschlagen bzw. 0 Presets liefern (Konto existiert nicht
    mehr). Der Scheduler-Status-Endpoint (`last_run`) wird nach dem folgenden Cron-Tick
    bestätigend nachgelesen, ist aber nicht der primäre Nachweis.

- **AC-4:** Given die bestehenden CI-TS-Gates für den E2E-Prod-Schutz (#1265 Teil D) / When
  ein Entwickler künftig `vite.config.ts` oder `prodUrlGuard.ts` so ändert, dass das
  Proxy-Ziel wieder auf Prod zeigen könnte / Then schlägt mindestens einer der erweiterten
  Tests (`e2e_prod_url_guard.test.ts`, `vite_proxy_target.test.ts`) in der bestehenden
  `npm test`-CI-Pipeline fehl, bevor der Code gemergt wird — kein neues Pflicht-Gate, nur
  Erweiterung des bestehenden.
  - Test: Test 4 + Test 5, ausgeführt über die bestehende CI-Pipeline (`.github/workflows/ci.yml:66`).

## Known Limitations

- Go's `IsTestUserID` (`internal/model/test_user.go:30-34`) liest bewusst NICHT das
  Profil-Flag `is_test_user` — nach dem Löschen von `admin` irrelevant für diese Runde,
  aber ein künftig neu angelegtes Konto namens `admin` wäre wieder ungeschützt.
- Der Wurzel-Fix schützt nur den Playwright-Pfad. Neun Python-Tests zeigen weiterhin per
  Default auf Prod-Ports (→ #1196).
- `frontend/e2e/start-preview.sh:4` lädt weiterhin die Prod-`.env` samt Live-Secrets in den
  Testprozess (→ eigenes Issue, nicht Teil dieser Spec).
- Die 13 Specs ohne Teardown (u.a. `compare-editor-slice4`, `issue-718-idealwert-validation`,
  `layout-tab-vergleich`) bleiben ohne Teardown — sie verschmutzen künftig den
  Staging-Datenbaum statt Prod. Das ist bewusst akzeptiert (PO-Entscheid: kein
  pro-Spec-Teardown, s. ADR-0025).
- **Guard-Restlücken (Nachtrag 2026-07-17, beide real unerreichbar):** `assertNotProdApiProxyTarget`
  erkennt die veraltete IPv4-kompatible IPv6-Notation `::a.b.c.d` (ohne `ffff`-Präfix) nicht als
  Loopback (F014, `prodUrlGuard.ts:78-87`). Der Adversary hat empirisch belegt, dass der Kernel
  diese Notation nicht auf Loopback routet (`curl http://[::127.0.0.1]:8090/` läuft in den
  Timeout, kein `ECONNREFUSED`) — kein realer Prod-Treffer. → #1199.
- **Der Guard prüft einmalig beim Setup**, das aufgelöste Ziel gilt danach für den ganzen Lauf
  (theoretische TOCTOU-/DNS-Rebinding-Lücke). Nicht demonstriert; setzt Kontrolle über
  autoritatives DNS voraus und liegt außerhalb des Bedrohungsmodells (Fehlkonfiguration/Alias,
  kein aktiver Angreifer auf dem Entwicklungsrechner).

## Nicht Teil dieser Spec

| Befund | Zielort |
|---|---|
| Telegram ohne Empfänger-Guard (`telegram.py:134-199`); `admin` entging `force_test` | eigenes Issue (Triage b, Sicherheitsrisiko) |
| Prod-Secrets in `start-preview.sh:4` (SMTP, Telegram-Token, MeteoFrance-Key, Session-Secret) im Testprozess | eigenes Issue (Triage b) |
| Verschlucktes „ok": `CompareDispatchStrategy` meldet `status:"ok"` auch bei vollständigem Fehlschlag, kein `failed`-Feld | eigenes Issue (Triage a, Querverweis #1207) |
| `E2E_USER` vs. `GZ_E2E_USER` — zwei Variablennamen, `.env.test` toter Code | #1199 |
| 9 Python-Tests mit Default auf Prod-Ports (`GO_BASE=localhost:8090`, `test_scheduler_triggers.py:14`) | #1196 |
| `scheduler_dispatch_service.py:141` `data_root="data"` hartkodiert, ignoriert `GZ_DATA_DIR` | `docs/specs/modules/fix_1265_data_root_migration_services.md` (vierter Eintrag) |
| 2s-Pause läuft auch bei Early-Return (`dispatch_orchestrator.py:179-185`) | #1199 |

## Deployment-Hinweis

Zwei per-Host-Schritte, beide idempotent, beide vor dem Frontend-Deploy (Proxy-Wechsel)
wirksam:

1. **Prod:** Cleanup-Skript (AC-1), ausgeführt als User `claude-gregor` gegen den absoluten
   Pfad `/home/hem/gregor_zwanzig/data` — **nicht** Teil des Code-Deploys über
   `deploy-gregor-prod.sh`. Der `data/`-Ordner im Worktree/Repo-Checkout ist ein anderer
   Baum (andere Inode) und darf nicht als Ziel verwendet werden.
2. **Staging:** Login-Konto `admin`/`test1234` anlegen (AC-2-Zusatzschritt), ausgeführt als
   der Nutzer, dem die Staging-Daten gehören, gegen den Staging-Datenbaum
   (`/home/hem/gregor_zwanzig_staging/data/users/`) — über den bestehenden
   Registrierungs-Mechanismus, keine neue Quelldatei.

**Reihenfolge:** Schritt 2 (Staging-Konto anlegen) muss **vor** dem Deploy des
Proxy-Wechsels (`vite.config.ts`) abgeschlossen sein, sonst ist die Testsuite zwischen den
beiden Schritten rot. Schritt 1 (Prod-Cleanup) ist davon unabhängig und dringlich
(Zeitdruck bis zum nächsten 06:00-Lauf).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0025
- **Rationale:** Neues Architekturmuster für den E2E-Prod-Schutz (Netzwerk-Wurzel-Fix statt
  pro-Spec-Teardown) und eine Abweichung von einer bestehenden Schutzregel (`admin` verliert
  den `NEVER_DELETE`-Status aus #1265) — beides ADR-würdig. Details, verworfene Alternativen
  und Konsequenzen: `docs/adr/0025-e2e-prod-network-unreachable-admin-loses-never-delete.md`.

## Changelog

- 2026-07-16: Initial spec erstellt — Issue #1284, Befund-Korrekturen und Adversary-Ergebnisse
  aus `docs/context/fix-1284-e2e-leichen-prod.md` übernommen, Issue-ACs auf beobachtbares
  Verhalten umformuliert (AC-1 ganzer Baum statt nur example.com-Filter, AC-2 Netzwerk-Wurzel
  statt Teardown/Datenbaum-Isolation, AC-3 als Folge von AC-1, AC-4 als Gate-Erweiterung).
- 2026-07-16: Nachprüfungs-Korrekturen — (1) AC-2 um Staging-Login-Konto-Schritt und
  beobachtbare Lauffähigkeits-Bedingung erweitert, Deployment-Hinweis auf zwei per-Host-
  Schritte mit Reihenfolge erweitert; (2) Test 5 von Dateiinhalt-Grep auf Prüfung des
  aufgelösten Proxy-Ziel-Werts umgestellt (Test-Politik-Konformität).
- 2026-07-17: **Guard-Mechanik ersetzt** (Implementation Details AC-2/AC-4 + Known Limitations).
  Die ACs bleiben unverändert — sie beschreiben beobachtbares Verhalten, das weiterhin gilt.
  Geändert hat sich der Weg dorthin: Namensprüfung (String → Sperrliste → tautologische
  Positivliste) scheiterte in drei Adversary-Runden an real belegten Bypässen
  (F004 `127.0.0.1:8090`, F011 `localhost.:8090`, F012 `localtest.me:8090`); Endstand ist eine
  DNS-Auflösungs-Prüfung (Loopback-Adresse + Prod-Port → wirf, fail-closed). Restlücken F013
  (gefixt) und F014 (real unerreichbar, → #1199) in den Known Limitations ergänzt.
  LoC-Rahmen dafür in zwei Schritten von 250 auf 850 angehoben (PO-Freigaben 2026-07-16/17);
  der Zuwachs ist vollständig adversary-getrieben, kein Scope-Zuwachs.
- 2026-07-17: **AC-1 und AC-3 in Produktion vollzogen und belegt.** Cleanup-Lauf 03:37 UTC:
  `data/users/admin/` entfernt, Backup `data/.backups/cleanup-1284-20260717T033714Z.tar.gz`
  (395 Einträge, 166 Abos, `user.json`); Prod-Login `admin`/`test1234` → 401 (vorher 200);
  Laufzeit `compare-presets-daily?user_id=henning&hour=6` = 4,4s (Budget 120s, vorher 72s
  ohne Sendepause und auf ~340s zulaufend). Staging-Login-Konto `admin` angelegt (Login → 200).
