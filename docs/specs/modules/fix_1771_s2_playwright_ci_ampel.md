---
entity_id: fix_1771_s2_playwright_ci_ampel
type: feature
created: 2026-08-13
updated: 2026-08-13
status: draft
workflow: fix-1771-s2-playwright-ci-ampel
tags: [testing, e2e, playwright, ci, infrastructure]
---

# Playwright-E2E-Specs in die CI-Ampel einhängen (#1771 Scheibe 2)

- **Issue:** #1771 (Titel: „E2E-Klickpfade sind unbewacht: Ziehhelfer flackert, und kein
  Playwright-Spec laeuft in der CI-Ampel") · Scheibe 2 von mehreren
- **Scope dieser Scheibe:** Punkt 2 des Issues — kein Playwright-Spec läuft in der CI-Ampel —
  sowie der zweite Issue-Kommentar (157/16-Bestandsmessung, dort widerlegt). Scheibe 1
  (Ziehhelfer-Flake, `dragDndZoneItem`) ist bereits LIVE (`559a6757`) und NICHT Teil dieser
  Scheibe.
- **Typ:** Feature/Infrastruktur an der CI-Pipeline — kein Produktcode betroffen
  (`frontend/src/`, `internal/`, `api/`, `src/` bleiben unverändert), reine
  Testinfrastruktur (`.github/`, `frontend/e2e/`, `frontend/playwright.config.ts`) plus
  Dokumentation (ADR, CLAUDE.md).

## Approval

- [x] Approved — PO-Freigabe 2026-08-13 („freigabe")

## Purpose

Der Issue-Kommentar vom 2026-08-12 schlägt vor, die „141/157 lokal lauffähigen" Specs ohne
Staging-Zugangsdaten in die CI-Ampel zu hängen. **Das ist am laufenden System widerlegt:**
Der „lokale" Playwright-Lauf ist tatsächlich lokales Frontend gegen den geteilten,
dauerhaft laufenden Staging-Go-Server (`GZ_API_BASE=http://localhost:8091` proxied auf
`gregor-api-staging.service`) — auf einem GitHub-Runner (`ubuntu-latest`) existiert davon
nichts. Gemessen sind außerdem **921 Testfälle in 159 Dateien** (inkl. der 16
`.staging.spec.ts`), nicht die vom Issue genannten „158 Specs" — `playwright.config.ts`
unterscheidet Staging- und lokale Specs strukturell überhaupt nicht.

Diese Scheibe baut stattdessen einen **parallelen, isolierten** CI-Job `e2e`, der einen
eigenen, im Runner selbst hochgefahrenen Stack (Python-Core + Go-Server, beide offline über
Fixtures) gegen eine **wachstumsbeschränkte Positivliste** von Playwright-Specs fährt. Der
Job entscheidet über drei Bedingungen (keine Roten, kein Skip-Budget, Mindestzahl
tatsächlich ausgeführter Tests) statt nur über „keine Roten" — sonst wäre ein Lauf grün, der
nichts beweist (35 gemessene konditionale Laufzeit-Skips + leere CI-Datenwurzel). Grund für
die Positivliste statt einer Ausschlussliste: eine Stichprobenmessung (72 Testfälle, 15
Dateien) gegen Staging im Normalbetrieb ergab **22 rote Fälle (30,6 %)** — fast jeder dritte
Test ist heute rot, ohne dass jemand etwas geändert hätte. Eine Ausschlussliste würde diese
unbekannte Rote als Verpflichtung erben; eine Positivliste, die nur wachsen darf, nicht.

## Source

- **Files:**
  - `.github/workflows/ci.yml` — MODIFY (neuer Job `e2e` + `workflow_dispatch`-Variante)
  - `frontend/e2e/ci-stack.sh` — CREATE (Stack-Start/-Stop mit Health-Warteschleifen)
  - `.github/ci_e2e_specs.txt` — CREATE (Positivliste, wachstumsbeschränkte Ratsche)
  - `frontend/playwright.config.ts` — MODIFY (CI-Zweig, kein neues Config-File)
  - `docs/adr/0053-*.md` — CREATE (Grundsatzentscheidung, fortschreibend zu ADR-0006/ADR-0028)
  - `docs/adr/README.md` — MODIFY (Index-Eintrag für ADR-0053)
  - `CLAUDE.md` — MODIFY (Merge-Regel „5 Checks" → „6 Checks")
- **Identifier:** neuer Job `e2e:` in `.github/workflows/ci.yml` (parallel zu `test` ·
  `go-test` · `frontend-test` · `svelte-check` · `lint`); Skript
  `frontend/e2e/ci-stack.sh {start|stop}`; Liste `.github/ci_e2e_specs.txt`

> **Schicht-Hinweis:** Alle Code-Änderungen liegen in der CI-/Testinfrastruktur
> (`.github/`, `frontend/e2e/`, `frontend/playwright.config.ts`) — kein Frontend-, Go-API-
> oder Python-Core-Produktcode wird geändert. Go-Server (`internal/config/config.go`,
> `cmd/server/main.go`) und Python-Core (`api/routers/internal.py`) werden nur **gelesen**
> zur Bestätigung der Defaults/Fixture-Anbindung, nicht verändert.

## Estimated Scope

- **LoC:** ≈165 (Code) — unter dem 250er-Limit, kein Override nötig; `.md`-Dateien
  (ADR, README, CLAUDE.md) zählen nicht
- **Files:** 4 Code-Dateien (`ci.yml`, `ci-stack.sh`, `ci_e2e_specs.txt`,
  `playwright.config.ts`) + 3 Doku-Dateien (ADR-0053, ADR-README, CLAUDE.md)
- **Effort:** medium — kein Produktcode, aber eine neue Grundsatzentscheidung (ADR) und ein
  Pflicht-Check, der die Merge-Regel erweitert

### Affected Files (Scope)

| Datei | Änderungstyp | ~LoC |
|---|---|---|
| `.github/workflows/ci.yml` | MODIFY | ~70 |
| `frontend/e2e/ci-stack.sh` | CREATE | ~35 |
| `.github/ci_e2e_specs.txt` | CREATE | ~30 |
| `frontend/playwright.config.ts` | MODIFY | ~10 |
| `docs/adr/0053-*.md`, `docs/adr/README.md`, `CLAUDE.md` | CREATE/MODIFY | 0 (zählt nicht) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.github/ci_tdd_excludes.txt` | Vorbild (nur strukturell) | Kopfkommentar-Stil einer Ratsche-Liste — Richtung ist hier **umgekehrt**: die neue Liste darf nur wachsen, nicht schrumpfen |
| `frontend/e2e/global.setup.ts` | test infra | Login (`E2E_USER`/`E2E_PASS`) + Seed der drei Fixture-Orte (`e2e-loc-*`) — Voraussetzung für jeden Lauf im isolierten Stack |
| `frontend/e2e/global.teardown.ts` | test infra | Präfix-Sweep `E2E-GZ-` (#1329) — in CI entbehrlich (Stack ist flüchtig), muss aber vor dem Stack-Stop laufen dürfen |
| `frontend/e2e/apiProxyTarget.ts` · `prodUrlGuard.ts` | test infra | Fail-closed-Schutz gegen Prod (ADR-0028) — bestimmt `GZ_PORT=8091` als Pflichtwert für den isolierten Stack |
| `internal/config/config.go` | Go-API (nur gelesen) | Server-Defaults: Port 8090 (`:8`), Session-Secret `dev-secret-change-me` (`:16`) — beide Defaults tragen den isolierten Stack |
| `cmd/server/main.go` | Go-API (nur gelesen) | `FixtureProvider` bei `GZ_TEST_FIXTURE_DIR` (`:52-54`), Selbst-Seed des Testnutzers aus `GZ_AUTH_PASS` (`:41-48`) |
| `api/routers/internal.py` | Python-Core (nur gelesen) | `FixtureProvider` (#346) — Offline-Wetter für den Python-Core im isolierten Stack |
| `fixtures/openmeteo/{innsbruck,stubai,zillertal}.json` | Testdaten | Deckt nur **heute + 2 Tage**; muss zu den drei von `global.setup.ts` geseedeten Orten passen |
| `frontend/playwright.config.ts` (Bestand) | test infra | `webServer`, Projekte `setup`/`tests`, `storageState` — bekommt einen CI-Zweig, **kein** neues Config-File (Gegenmaßnahme zum gemessenen Wildwuchs von 50 Configs) |
| ADR-0006, ADR-0028 | ADR (Bestand) | Diese Scheibe schreibt beide fort (ADR-0053); ADR-0028s Begründung „`GZ_DATA_DIR` technisch nicht tragfähig" ist verjährt (siehe unten) |
| CLAUDE.md „CI-Ampel & Merge-Regel" | Regel (Bestand) | Ein neuer Pflicht-Check ändert „5 Checks" auf „6 Checks" — Downstream-Wirkung auf die GitHub-Branch-Protection |

## Implementation Details

### 1. Neuer, paralleler Job `e2e` statt Erweiterung von `frontend-test`

`frontend-test` kostet heute 64 s und ist der schnelle Signalgeber für Node-Unit-Tests — ein
E2E-Anhängsel würde das zerstören. Der neue Job `e2e` läuft **parallel** zu `test` · `go-test`
· `frontend-test` · `svelte-check` · `lint`; die Ampel-Wanduhrzeit bleibt bei ~10 min
(bestimmt vom `test`-Job mit 561 s), der `e2e`-Job braucht ~4–4,5 min und passt darunter.

Ablauf im Job (illustrativ, finale Reihenfolge entsteht in der Umsetzung):

```yaml
e2e:
  runs-on: ubuntu-latest
  env:
    E2E_MIN_SPECS: 10        # Ratsche-Wächter: Zahl der DATEIEN auf der Positivliste
    E2E_MIN_EXECUTED: 50     # Mindestzahl tatsächlich AUSGEFÜHRTER Testfälle
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-go@v5
      with: { go-version-file: go.mod }
    - run: go build -o /tmp/gregor-server ./cmd/server
    - uses: astral-sh/setup-uv@v4
    - run: uv python install 3.12 && uv sync
    - uses: actions/setup-node@v4
      with: { node-version: 22, cache: npm }
    - working-directory: frontend
      run: npm ci && npx playwright install --with-deps chromium
    - run: bash frontend/e2e/ci-stack.sh start   # Health-Warteschleifen statt sleep
    - working-directory: frontend
      run: npx playwright test $(grep -v '^#' ../.github/ci_e2e_specs.txt)
      env: { CI: "1" }
    - run: python3 -c "<Drei-Bedingungen-Auswertung, s. u.>"
    - if: always()
      run: bash frontend/e2e/ci-stack.sh stop
```

`npx playwright install --with-deps chromium` in `frontend/` ist **neu** — die vorhandene
`playwright install`-Zeile in `ci.yml:22` installiert das *Python*-Playwright für
`tests/visual` (Pixel-Diff), nicht die Node-Variante.

### 2. `frontend/e2e/ci-stack.sh` — isolierter Stack, Health-Warteschleifen statt Fristen

Startet Python-Core (`uvicorn api.main:app`) und den gebauten Go-Server als
Hintergrundprozesse, beide offline über `GZ_TEST_FIXTURE_DIR=fixtures/openmeteo` und einem
eigenen, leeren `GZ_DATA_DIR` (kein Zugriff auf Produktiv- oder Staging-Daten). Zwei
Details entscheiden über Funktionieren vs. stilles Scheitern (beide lokal nachgemessen):

- **`GZ_PORT=8091` ist PFLICHT.** Der Go-Default ist `8090` (`config.go:8`), und
  `prodUrlGuard.ts` lehnt fail-closed jedes Loopback-Ziel auf 8090 ab — ein unkonfigurierter
  Stack würde von der eigenen Prod-Sperre erschlagen. Mit `8091` braucht die Frontend-Seite
  **keine** Overrides (bereits Default von `GZ_API_BASE`).
- **`GZ_SESSION_SECRET` bleibt UNGESETZT** — nicht halb, nicht ganz. `config.go:16` und
  `hooks.server.ts:16` defaulten beide auf `dev-secret-change-me`; im Runner gibt es keine
  `.env`. Wird es nur auf einer Seite gesetzt, brechen die Cookie-Signaturen und jeder
  API-Ruf liefert `401` — selbst als Messfehler erlebt (Diagnose in
  `docs/context/fix-1771-s2-playwright-ci-ampel.md`, Abschnitt „Eigener Messfehler").
- `GZ_AUTH_PASS=test1234` — der Go-Server seedet den Testnutzer beim ersten Start selbst
  (`main.go:41-48`), kein manueller Seed-Schritt nötig.

Wartelogik: `curl`-Retry-Schleife gegen `/health` (Python, Port 8005 o.ä.) und `/api/health`
(Go, Port 8091) statt eines festen `sleep N` — ein zu kurzer `sleep` würde den Job selbst
mit derselben Fristen-Krankheit infizieren, die Scheibe 1 an der Ziehgeste behoben hat.
`ci-stack.sh stop` läuft **nach** dem Playwright-Exit (nicht vorher), damit
`global.teardown.ts` noch gegen einen laufenden Server sweepen kann.

### 3. `.github/ci_e2e_specs.txt` — Positivliste, Richtungsumkehr zur Ratsche

`ci_tdd_excludes.txt` ist nur **strukturell** Vorbild (Kopfkommentar-Stil, eine Zeile pro
Datei, Begründung im Kommentarblock) — nicht in der Richtung. Eine Ausschlussliste setzt
eine grüne Grundmenge voraus; hier ist sie es nachweislich nicht (30,6 % rot in der
Stichprobe). **Die neue Liste darf nur wachsen**, nie schrumpfen — was nicht drauf steht,
verpflichtet zu nichts.

Auswahl in zwei Filtern, beide belegt:

- **Filter A (strukturell, gemessen):** keine konditionalen `test.skip()`, keine
  `waitForTimeout`, keine permanenten Skips ⇒ Kandidatenpool **106 Dateien / 618
  Testfälle**. Zusätzlich raus: Specs, die Wetter*werte* prüfen (Fixtures decken nur heute +
  2 Tage), und die 16 `.staging.spec.ts` (brauchen Remote + Zugangsdaten, gehören nicht in
  eine Offline-Lane).
- **Filter B (gemessen im Runner, nicht lokal):** aufgenommen wird nur, was im
  Vermessungslauf (s. Punkt 6) **3× hintereinander grün** ist.

Startgröße ~10–15 Dateien / ~50 Testfälle — passt in das ~4,5-min-Budget bei `workers: 1`.
Die finale Startliste entsteht aus dem ersten `workflow_dispatch`-Vermessungslauf im Runner,
nicht aus lokalen Zahlen (lokale Läufe im Haupt-Checkout sind laut `ci_tdd_excludes.txt`-
Lektion kein Beleg für CI-Grün).

### 4. `frontend/playwright.config.ts` — CI-Zweig, kein neues Config-File

Ergänzung statt neuer Datei (Gegenmaßnahme zum gemessenen Wildwuchs: 50 Configs, 31 davon
allein im Juli 2026):

- `workers: process.env.CI ? 1 : undefined` — **Pflicht**, nicht optional: mehrere Worker
  teilen sich dieselbe Datenwurzel und dieselben Seed-IDs (`e2e-loc-*`); ohne `workers: 1`
  stören sich parallele Tests auf gemeinsamen Zustand.
- `retries: process.env.CI ? 0 : undefined` — ein Retry würde genau die Flake-Klasse
  verstecken, die diese Lane sichtbar machen soll.
- `reuseExistingServer: !process.env.CI` — außerhalb CI bleibt das bestehende
  Lokal-Verhalten (geteilter Preview-Server) unverändert.
- `trace: 'retain-on-failure'` in CI — Diagnose im Runner ist sonst nicht möglich; Artefakt
  wird nur bei `if: failure()` hochgeladen.

### 5. Auswertung: drei Bedingungen statt einer

Playwright liefert über den JSON-Reporter `stats` (`expected`, `unexpected`, `skipped`).
Der Job wertet **alle drei** aus, nicht nur „keine Roten":

1. `unexpected == 0` — das prüft ein naiver Lauf bereits.
2. `skipped == 0` — Filter A macht konditionale/permanente Skips in der Positivliste
   baulich ausgeschlossen; taucht dennoch einer auf, ist das ein Regelbruch, kein
   Kavaliersdelikt.
3. **`expected >= E2E_MIN_EXECUTED`** — trägt die eigentliche Last: Scheitert der Seed, kommt
   der Stack nicht hoch oder zeigt die Liste ins Leere, ist `expected == 0` und der Job
   **muss rot werden**, nicht grün mit „0 Tests, 0 rot".

**🔴 Zwei getrennte Zahlen, nicht eine.** `E2E_MIN_SPECS` zählt **Dateien** auf der Liste,
`E2E_MIN_EXECUTED` zählt **ausgeführte Testfälle**. Sie dürfen nicht zu einer Variable
verschmolzen werden: Bei 10 Listen-Dateien mit zusammen ~50 Testfällen wäre eine Prüfung
`expected >= 10` bereits erfüllt, wenn nur 11 Tests laufen — 39 könnten still ausfallen und
der Job bliebe grün. Das wäre exakt das „grün ohne Aussage", das diese Bedingung verhindern
soll. Beide stehen als `env:` im Job (Muster: `BASELINE_ERRORS` im `svelte-check`-Job,
`ci.yml:122`); `E2E_MIN_SPECS` verhindert stilles Schrumpfen der Liste,
`E2E_MIN_EXECUTED` stilles Ausfallen von Tests.

Ohne Bedingung 3 wäre die Lane exakt der Bericht, den sie ersetzen soll — ein Lauf, der bei
jedem denkbaren Fehlschlag des Stacks selbst grün bleibt.

### 6. Vermessungslauf als `workflow_dispatch`-Variante desselben Jobs

Derselbe Job bekommt einen zweiten Trigger `workflow_dispatch`. Im manuellen Modus fährt er
statt der Positivliste den Filter-A-Kandidatenpool (106 Dateien) und protokolliert das
Ergebnis — das ist die Grundlage, auf der künftige Scheiben Zeilen zu
`.github/ci_e2e_specs.txt` hinzufügen (Filter B: 3× hintereinander grün). Der vom Issue
geforderte Volllauf über die volle Suite wird damit **Wachstumsmaschine statt
Vorbedingung** — er ist per Knopfdruck verfügbar, ohne dass diese Scheibe ihn selbst
auswerten und alle 921 Tests sanieren müsste.

### 7. Merge-Regel: 5 → 6 Checks

CLAUDE.md nennt an mehreren Stellen „die 5 GitHub-Actions-Checks" als vollständige Ampel
(Abschnitt „CI-Ampel & Merge-Regel", Liefer-Workflow Schritt 1b). Beide Stellen werden auf
„6 Checks" (inkl. `e2e`) aktualisiert. Formal eine **Erweiterung** der bestehenden
Merge-Regel, kein neues Gate — Regel-Budget-Eintrag mit eigenem Prüfdatum **2026-11-11**,
Fang-Kriterium: „mindestens ein PR, in dem die Lane eine Regression fängt, die die anderen
fünf Checks durchlassen".

### 8. ADR-0053

Neue Grundsatzentscheidung zur Teststrategie, fortschreibend zu ADR-0006 („keine gemockten
Tests, echte E2E") und ADR-0028 (Proxy-Ziel auf Staging als Default-Override). Der ADR-Text
MUSS explizit benennen, dass ADR-0028s Verwerfung von „Isolation über `GZ_DATA_DIR`" als
*technisch nicht tragfähig* **verjährt** ist: Der damals zitierte Hartkodierungs-Fund
(`scheduler_dispatch_service.py:141`, `data_root = "data"`) ist mit #1133 behoben —
`get_data_root()` respektiert `GZ_DATA_DIR` heute (`src/app/loader.py:1088-1107`,
Priorität `_DATA_ROOT` > `GZ_DATA_DIR` > `"data"`). Ohne diese Klarstellung würde eine
dokumentierte Entscheidung still umgangen. Die Nutzung von `GZ_E2E_API_PROXY_TARGET` ist
dagegen **kein** Abweichen von ADR-0028 — der Override ist dort ausdrücklich vorgesehen.

## Nicht in dieser Scheibe

- **Volllauf über alle 921 Tests** — die Positivliste macht ihn für diese Scheibe
  entbehrlich; per `workflow_dispatch` bleibt er für Folge-Scheiben per Knopfdruck verfügbar.
- **Sanierung der 78–81 `waitForTimeout`** — eigene Scheibe, sprengt allein das LoC-Limit.
- **Sanierung der 35 konditionalen Skips** — die Startmenge (Filter A) umgeht sie
  strukturell, statt sie zu reparieren.
- **Toter/kaputter Bestand:** `issue-264-stage-sort.spec.ts` (de facto kaputt — nutzt
  Testids des am 2026-07-11 gelöschten 5-Schritt-Trip-Wizards), `issue-407`-Grabstein (12
  Tests `test.skip`, absichtlich historisch belassen), tote `fillStep2/3/4` in `helpers.ts`
  inkl. eines am 2026-06-06 entfernten `signal`-Kanal-Toggles ⇒ **Nebenbefund-Triage:
  Checkbox-Zeilen in #1196** (Test-/Gate-Befunde, solange offen — nicht #1199), keine
  eigenen Issues. **Bereits gebucht am 2026-08-13**, zusammen mit der gemessenen Grün-Quote,
  dem Config-Wildwuchs und der Parallellauf-Falle (Port 4173 geteilt).
- **Config-Wildwuchs** (50 Playwright-Configs, 31 allein im Juli 2026) — eigene Scheibe;
  diese Scheibe legt bewusst **keine** neue Config an, um den Wildwuchs nicht fortzusetzen.
- **Sharding** — erst wenn die Positivliste das Zeitbudget sprengt.
- **Die 16 `.staging.spec.ts`** — brauchen Remote-Zugriff + Zugangsdaten, gehören nicht in
  eine Offline-Lane.

## Expected Behavior

- **Input:** Ein PR gegen `main` wird gepusht (regulärer Trigger) oder der Job wird manuell
  über `workflow_dispatch` mit dem Vermessungsmodus gestartet.
- **Output:**
  - Regulärer PR-Lauf: Der `e2e`-Job startet einen eigenen, isolierten Stack
    (Python-Core + Go-Server, Fixtures, leere Datenwurzel), fährt die Positivliste aus
    `.github/ci_e2e_specs.txt` mit `workers: 1` und wertet drei Bedingungen aus
    (`unexpected == 0`, `skipped == 0`, `expected >= E2E_MIN_SPECS`). Sind alle drei erfüllt,
    ist der Check grün; sonst rot — inklusive des Falls, dass der Stack selbst nicht
    hochkommt (dann `expected == 0`).
  - `workflow_dispatch`-Lauf: fährt statt der Positivliste den Filter-A-Kandidatenpool
    (106 Dateien) und protokolliert das Ergebnis als Grundlage für künftige
    Listenerweiterungen.
  - Die Ampel-Wanduhrzeit bleibt unverändert bei ~10 min (paralleler Job).
- **Side effects:** CLAUDE.md nennt ab dieser Scheibe „6 Checks" statt „5 Checks" als
  vollständige Ampel; ein neuer PR wird erst gemergt, wenn auch `e2e` grün ist. Kein
  Produktcode wird verändert, keine Prod- oder Staging-Datenwurzel wird vom Job berührt.

## Acceptance Criteria

- **AC-1:** Given der neue Job `e2e` läuft parallel zu `test` · `go-test` · `frontend-test` ·
  `svelte-check` · `lint` in `ci.yml` / When ein PR gepusht wird / Then addiert der `e2e`-Job
  keine zusätzliche Wanduhrzeit zur Gesamtampel, weil er zeitgleich mit dem
  langlaufendsten Job (`test`, 561 s) startet, nicht seriell nach dessen Ende.
  - Test: GitHub-Actions-Run-Log zeigt die Startzeitstempel von `e2e` und `test` als
    zeitgleich (beide direkt nach Job-Anlauf), nicht `e2e`-Start nach `test`-Ende.

- **AC-2:** Given `frontend/e2e/ci-stack.sh` startet Python-Core und Go-Server mit
  `GZ_TEST_FIXTURE_DIR=fixtures/openmeteo` und eigenem `GZ_DATA_DIR`, ohne
  `GZ_SESSION_SECRET` zu setzen / When `global.setup.ts` gegen den frisch gestarteten
  Stack einloggt / Then liefert der Login HTTP 200 — kein halbseitig gesetztes Secret bricht
  die Cookie-Signatur und erzeugt ein stilles `401`.
  - Test: CI-Run-Log des `e2e`-Jobs zeigt einen erfolgreichen `global.setup`-Durchlauf ohne
    `401`-Fehlermeldung in der Playwright-Konsolenausgabe.

- **AC-3:** Given `ci-stack.sh` wartet mit `curl`-Health-Retry-Schleifen gegen `/health`
  (Python-Core) und `/api/health` (Go-Server) statt mit einem festen `sleep` / When einer der
  beiden Server im Runner langsamer hochfährt als im lokalen Vorlauf gemessen / Then bricht
  der Job nicht durch einen zu kurzen `sleep` vorzeitig ab, sondern wartet bis zur
  Health-Antwort oder einem expliziten Timeout mit klarer Fehlermeldung.
  - Test: CI-Run-Log zeigt eine variable Wartezeit zwischen Server-Start und erstem grünen
    Healthcheck (kein fixer, in jedem Lauf identischer Sekundenwert) — Nachweis über
    tatsächliches Laufverhalten, nicht über einen Quelltext-Inhalts-Check.

- **AC-4:** Given der Auswertungsblock im `e2e`-Job liest `expected`, `unexpected` und
  `skipped` aus dem Playwright-JSON-Reporter / When der Stack-Start oder Seed fehlschlägt,
  sodass kein Test der Positivliste tatsächlich ausgeführt wird (`expected == 0`) / Then
  schlägt der Job fehl — obwohl `unexpected == 0` wäre, verhindert die Bedingung
  `expected >= E2E_MIN_EXECUTED` ein falsches Grün. `E2E_MIN_EXECUTED` zählt ausgeführte
  Testfälle und ist von `E2E_MIN_SPECS` (Zahl der Listen-Dateien) getrennt zu halten.
  - Test: Mutations-Gegenprobe — den Health-Check in `ci-stack.sh` gezielt auf einen
    falschen Port verfälschen (externe Sicherungskopie vorher anlegen, kein `git
    checkout`/`stash`/`reset`), Job laufen lassen: Ergebnis muss ROT sein, nicht grün mit
    „0 Tests, 0 rot"; danach Rückbau der Verfälschung.

- **AC-5:** Given ein `data-testid` in einer von der Positivliste abgedeckten Komponente wird
  gezielt umbenannt (z. B. `trip-detail-tab-weather`) / When der `e2e`-Job auf diesem
  verfälschten Stand läuft / Then wird mindestens der Testfall rot, der diesen Selektor
  nutzt — die Lane deckt die Mutation auf statt sie durchzulassen.
  - Test: String-Ersetzung des Test-IDs mit externer Sicherungskopie, `e2e`-Job (lokal
    nachgebaut oder im Runner) ausführen, roten Testfall im JSON-Report belegen, danach
    Rückbau der Verfälschung. Ohne diesen Beleg gilt der Job selbst nur als Bericht, nicht
    als Absicherung (CLAUDE.md-Pflicht „Mutations-Gegenprobe").

- **AC-6:** Given `frontend/playwright.config.ts` bekommt einen CI-Zweig mit `workers: 1` /
  When zwei Tests aus der Positivliste dieselbe Seed-Daten-ID (`e2e-loc-*`) lesen oder
  verändern / Then laufen sie nacheinander statt parallel und beeinflussen sich nicht
  gegenseitig — kein Test schlägt durch eine Race Condition auf gemeinsamem Seed-Zustand
  fehl.
  - Test: CI-Run-Log bzw. Playwright-Konfigurationsausgabe zeigt genau einen aktiven
    Worker-Prozess während des `e2e`-Jobs (`workers: 1` wirksam, nicht der lokale
    Kerne/2-Default).

- **AC-7:** Given `.github/ci_e2e_specs.txt` enthält beim ersten Merge eine Startmenge von
  10–15 Dateien, ausgewählt über Filter A (strukturell) und Filter B (3× hintereinander grün
  im Vermessungslauf) / When ein Test diese beiden Filter nicht erfüllt (z. B. einer der 22
  von 72 in der Stichprobe gemessenen roten Fälle) / Then steht dieser Test NICHT auf der
  Liste und wird vom regulären `e2e`-Lauf nicht ausgeführt.
  - Test: Abgleich der committeten Liste gegen das Vermessungsprotokoll des
    `workflow_dispatch`-Laufs — jede gelistete Datei hat einen Beleg von 3 aufeinanderfolgend
    grünen JSON-Reports.

- **AC-8:** Given derselbe Job ist zusätzlich über `workflow_dispatch` auslösbar / When er
  manuell im Vermessungsmodus gestartet wird / Then fährt er den Filter-A-Kandidatenpool
  (106 Dateien statt der ~10–15 der Positivliste) und protokolliert das Ergebnis, ohne dass
  dafür ein Volllauf über alle 921 Tests nötig ist.
  - Test: Manueller `workflow_dispatch`-Trigger im Actions-Tab mit dem Vermessungs-Input;
    das Run-Log zeigt eine deutlich größere Testmenge als der reguläre PR-Lauf.

- **AC-9:** Given CLAUDE.md nennt an mehreren Stellen „die 5 GitHub-Actions-Checks" als
  vollständige CI-Ampel / When diese Scheibe live ist / Then sind alle betroffenen Stellen
  auf „6 Checks" (inkl. `e2e`) aktualisiert, und ein neuer PR wird erst gemergt, wenn auch
  der `e2e`-Check grün ist.
  - Test: `grep -n "5 GitHub-Actions-Checks\|alle 5 Checks" CLAUDE.md` liefert nach der
    Änderung keine Treffer mehr auf die alte Zahl; der nächste PR nach Live-Gang zeigt in der
    GitHub-UI 6 Status-Checks statt 5.

## Known Limitations

- **KL-1 · Fixture-Fenster nur heute + 2 Tage:** Beide `FixtureProvider` (Go und Python)
  rebasen auf „heute" — die „Gestern"-Etappe des Seed-Trips und Mehrtagesansichten sind im
  isolierten Stack datenlos. Auswahlkriterium (Filter A schließt wertprüfende Specs aus),
  keine Reparatur in dieser Scheibe.
- **KL-2 · Verbleibender 401 im SvelteKit-Weiterleitungspfad:** Im lokalen Nachbau blieb ein
  `401` auf dem Weg über den SvelteKit-Preview-Proxy bestehen, während der direkte Weg zum
  Go-Server (Login 200, Anlegen 201) einwandfrei funktionierte. Lokal schwer zu isolieren,
  weil dieser Rechner eine `.env` hat, die der Runner nicht hat — muss im Runner selbst
  (`workflow_dispatch`-Vermessungslauf) erneut geprüft werden, bevor die finale Positivliste
  feststeht.
- **KL-3 · Grün-Quote an einer Stichprobe gemessen:** Die 30,6-%-Rot-Quote (22 von 72
  Testfällen) wurde an einer 15-Datei-Stichprobe gegen die geteilte Staging-Instanz
  gemessen, auf der parallele Sessions arbeiten — einzelne Fehlschläge können
  Fremdeinwirkung sein. Die Größenordnung (rund ein Drittel rot) ist davon unberührt und
  bleibt die Begründung für die Positivliste statt einer Ausschlussliste.
- **KL-4 · Scope-Grenze:** Diese Scheibe saniert keine Testinhalte (`waitForTimeout`,
  konditionale Skips, toter Bestand) und räumt den Config-Wildwuchs nicht auf — sie baut nur
  den Mechanismus, der eine belegt-stabile Teilmenge bewacht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0053 (neu, fortschreibend zu ADR-0006 „keine gemockten Tests, echte E2E"
  und ADR-0028 „Proxy-Ziel auf Staging als Default")
- **Rationale:** Die Einhängung von Playwright-E2E-Klickpfaden in die CI-Ampel ist eine
  Grundsatzentscheidung zur Teststrategie (Entscheidungsfläche „Test-/Deploy-Strategie" laut
  CLAUDE.md) — insbesondere die Richtungsumkehr „Positivliste statt Ausschlussliste" und die
  Feststellung, dass ADR-0028s Begründung „`GZ_DATA_DIR`-Isolation technisch nicht
  tragfähig" durch #1133 verjährt ist, gehören dokumentiert, sonst wird eine bestehende
  Entscheidung still umgangen. Die Nutzung von `GZ_E2E_API_PROXY_TARGET` weicht dagegen
  nicht von ADR-0028 ab — der Override ist dort vorgesehen.

## Changelog

- 2026-08-13: Initial spec created
