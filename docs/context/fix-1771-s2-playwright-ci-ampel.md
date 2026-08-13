# Context: fix-1771-s2-playwright-ci-ampel

**Issue:** #1771 (Teil 2) · **Track:** Full Process · **Erstellt:** 2026-08-13
**Scheibe 1 (Ziehhelfer-Flake) ist LIVE** (`559a6757`) — diese Scheibe behandelt den
zweiten, größeren Teil des Issues.

## Request Summary

Kein einziger der 158 Playwright-E2E-Specs läuft in der CI-Ampel. Der Klickpfad-Bestand —
genau die Nachweise, die der PO für Frontend-Arbeit ausdrücklich verlangt — ist unbewacht
und verfällt still. Diese Scheibe soll entscheiden und umsetzen, **welche Specs wie in die
Ampel kommen**.

---

## 🔴 Die Prämisse des Issues ist widerlegt

Der Issue-Kommentar vom 2026-08-12 schlägt vor: *„die 141 lokal lauffähigen Specs brauchen
keine Staging-Instanz und keine Zugangsdaten"* — das ist der dort genannte „natürliche
Schnitt" 157/16.

**Am laufenden System gemessen (2026-08-13): stimmt nicht.**

| Messung | Befund |
|---|---|
| `GZ_API_BASE` Default | `http://localhost:8091` (`playwright.config.ts:12`, `start-preview.sh:17`) |
| Port 8091 | `gregor-api-staging.service`, PID-bestätigt |
| Port 8090 | `gregor-api` (Prod) |

Der „lokale" Lauf ist **lokales Frontend + geteiltes Remote-Backend**: Der Vite-Proxy leitet
jeden `/api`-Ruf an den dauerhaft laufenden Staging-Go-Server, der an den Staging-Python-Core
(8001) mit echter Staging-Datenwurzel (`/var/lib/gregor-staging`) delegiert. Auf einem
GitHub-Runner (`ubuntu-latest`, **kein** self-hosted Runner) existiert davon nichts.

**Zweiter Irrtum derselben Stelle:** `playwright.config.ts` unterscheidet Staging- und lokale
Specs **strukturell gar nicht** — kein `testIgnore`, kein eigenes Projekt. Selbst gemessen:
`npx playwright test --list` → **921 Tests in 159 Dateien**, die 16 Staging-Specs
eingeschlossen. Die 142/16-Aufteilung ist reine **Namenskonvention** plus begleitende
Einzel-Configs, keine Runner-Logik.

⇒ Die Kernfrage der Scheibe lautet nicht „welche Specs hängen wir ein?", sondern
**„woran reden sie in der CI?"**.

---

## Was die Sache LEICHTER macht als gedacht

Ein isolierter Stack im Runner ist gut vorbereitet — das war im Issue nicht bekannt:

| Baustein | Befund | Fundstelle |
|---|---|---|
| Go-Server: Pflichtvariablen | **keine** — jedes Feld hat einen Default | `internal/config/config.go:6-47` |
| Go-Server: Offline-Wetter | `FixtureProvider` bei gesetztem `GZ_TEST_FIXTURE_DIR` | `cmd/server/main.go:52-54` |
| Go-Server: Testnutzer | seedet sich beim ersten Start **selbst** (bcrypt aus `GZ_AUTH_PASS`) | `cmd/server/main.go:41-48` |
| Python-Core: Offline-Wetter | `FixtureProvider` (#346) | `api/routers/internal.py:49` |
| Python-Core: Start | `uvicorn api.main:app --port 8000` | systemd-Unit Staging |
| Fixtures vorhanden | `fixtures/openmeteo/{innsbruck,stubai,zillertal}.json` | `.env.e2e` |
| Seed passt zu Fixtures | `global.setup.ts` seedet **genau diese drei Orte** (`e2e-loc-*`) | `global.setup.ts:57-59` |
| SvelteKit-Preview | Playwright startet ihn bereits selbst (`webServer`) | `playwright.config.ts:39-44` |

**Zeitbudget:** Die Ampel braucht heute ~10 min, allein bestimmt vom Python-`test`-Job
(561 s). `frontend-test` kostet 64 s. Ein **paralleler** E2E-Job hätte damit ~9 min, ohne die
Ampel für alle zu verlangsamen.

### ADR-0028: eine Begründung ist verjährt

ADR-0028 verwarf „Isolation über `GZ_DATA_DIR`" als *technisch nicht tragfähig*, weil
`scheduler_dispatch_service.py:141` `data_root = "data"` hartkodiere. **Nachgemessen: gilt
nicht mehr.** `get_data_root()` respektiert die Variable heute (`_DATA_ROOT` > `GZ_DATA_DIR`
> `"data"`, `src/app/loader.py:1088-1107`, repariert mit #1133); die Datei heißt inzwischen
`src/services/scheduler_dispatch_service.py` und nimmt `data_root` als Parameter.

Der im ADR vorgesehene Override `GZ_E2E_API_PROXY_TARGET` bleibt ausdrücklich erlaubt — ein
CI-Job mit eigenem Stack **weicht also nicht von ADR-0028 ab**, er nutzt den dort
vorgesehenen Weg. Trotzdem ist die CI-Einhängung eine Grundsatzentscheidung zur
Teststrategie ⇒ **eigenes ADR** (fortschreibend zu ADR-0006 „keine gemockten Tests" und
ADR-0028).

---

## 🔴 Was die Sache SCHWERER macht: der Bestand trägt still

Das eigentliche Risiko ist nicht der Stack-Aufbau, sondern die **Aussagekraft** des Laufs.

### 35 konditionale Laufzeit-Skips (selbst gemessen)

| Art | Anzahl |
|---|---|
| `test.skip()` **ohne Argument** (Laufzeit, „Daten fehlen") | **35** |
| `test.skip('…')` permanent | 16 |
| `describe.skip` | 2 |
| `test.fixme` | 2 |

Die 35 sind das Muster `if (!isVisible) test.skip()` — sie greifen **still**, wenn Seed-Daten
fehlen. In einem frischen CI-Stack ist das Datenverzeichnis leer. **Ein solcher Lauf wäre
grün, ohne irgendetwas zu beweisen** — genau das Muster
„Nachweis als Bericht ist kein Schutz". Der Seed deckt drei Orte + einen Cockpit-Trip ab,
nicht die Trip-Listen-Zustände, auf die diese Skips prüfen.

**Folge für die Spec:** Die Ampel braucht eine Zusicherung über die *Zahl ausgeführter*
Tests, nicht nur über „keine roten". Ein Skip-Budget (Ratsche) gehört zur Scheibe.

### Toter und kaputter Bestand

- `issue-407-waypoint-editor-screen.spec.ts` — **alle 12 Tests** `test.skip`, absichtlich als
  historischer Grabstein belassen (#494). Läuft nie, kostet aber Kollektionszeit.
- `issue-264-stage-sort.spec.ts` — **de facto kaputt**: nutzt `fillStep1` gegen die
  Wizard-Testids des alten 5-Schritt-Trip-Wizards, der am 2026-07-11 (`d7703708`) gelöscht
  wurde. Kein einziger dieser Testids existiert noch in `frontend/src`.
- `helpers.ts` — `fillStep2`/`fillStep3`/`fillStep4` haben **null Aufrufer** (toter Code);
  `fillStep4` togglet weiterhin einen **`signal`**-Kanal, obwohl Signal am 2026-06-06 mit
  #610 app-weit entfernt wurde.
- ~11 Specs nennen in Kommentaren `CompareEditor.svelte`, das am 2026-07-19 gelöscht wurde
  (überwiegend irreführende Doku, Selektoren leben unter neuem Komponentennamen weiter).

### Config-Wildwuchs

**50** Playwright-Configs git-getrackt (41 `.staging.config.ts`, 9 lokal) für 158 Specs —
**31 davon allein im Juli 2026** entstanden, 8 im August. Jede Arbeitsscheibe legt ihre
eigene an, keine wird je aufgeräumt. Ohne Gegenmaßnahme wächst das weiter.

### 78–81 `waitForTimeout` (Fristen statt Zustände)

Scheibe 1 hat nur die Ziehgeste behoben. Spitzenreiter:
`bug-626-compare-menu-actions.spec.ts` (12), `compare-editor-autosave.spec.ts` (7),
`issue-498-stage-date-autosave.spec.ts` (6). Das ist die Flake-Quelle, die einen CI-Job
unzuverlässig und damit wertlos machen würde (der PO-Kommentar zum Issue nennt genau diesen
zweiten Fall: `weather-metrics-tab` einmal in vier Läufen nicht rechtzeitig sichtbar).

### Laufzeit ist unbelegt

**856** lokale + **53** Staging-Testfälle. Im ganzen Repo existiert **kein Beleg für einen
Gesamtlauf** — nur Einzel-Slice-Protokolle (3 Tests / 10,6 s). Eine sequenzielle Hochrechnung
landet im Bereich einer Stunde. Das Issue nennt den Volllauf selbst als Vorbedingung:
*„ein erster Volllauf gehört vor jede Entscheidung, sonst wird aus dem Einhängen unversehens
ein Sanierungsprojekt mit offenem Ende."* **Dieser Volllauf fehlt bis heute.**

---

## Related Files

| Datei | Relevanz |
|---|---|
| `.github/workflows/ci.yml` | Die Ampel. Job `frontend-test` (`:69-112`) fährt nur `npm test` (Node-Unit). Kein Job startet einen Anwendungsserver |
| `.github/ci_tdd_excludes.txt` | Vorbild für eine Schrumpf-Ratsche (30 Einträge, „darf nur schrumpfen") |
| `frontend/playwright.config.ts` | `webServer`, Projekte `setup`/`tests`, `storageState`; **keine** Staging-Trennung |
| `frontend/e2e/start-preview.sh` · `e2e-env.sh` | Preview-Start, Env-Herkunft, `GZ_API_BASE` |
| `frontend/e2e/global.setup.ts` | Login (`E2E_USER`/`E2E_PASS`, Default `admin`/`test1234`) + Seed der drei Orte |
| `frontend/e2e/global.teardown.ts` | Präfix-Sweep `E2E-GZ-` (#1329) — in CI entbehrlich, Stack ist ohnehin flüchtig |
| `frontend/e2e/apiProxyTarget.ts` · `prodUrlGuard.ts` | Fail-closed-Schutz gegen Prod (ADR-0028) |
| `frontend/e2e/helpers.ts` | Geteilter Helferblock; enthält toten Wizard-/Signal-Code |
| `internal/config/config.go` · `cmd/server/main.go` | Go-Server: alle Defaults, Fixture-Modus, Selbst-Seed |
| `api/routers/internal.py` | Python-Core Fixture-Modus |

## Existing Specs / ADRs

- `docs/adr/0006-no-mocked-tests-e2e-staging.md` — „keine gemockten Tests, echte E2E"
- `docs/adr/0028-…admin-loses-never-delete.md` — Proxy-Ziel auf Staging; **eine Begründung
  darin ist verjährt** (s.o.)
- `docs/specs/modules/fix_1771_s1_dnd_wartestrategie.md` — Scheibe 1
- `docs/specs/modules/fix_1329_e2e_data_hygiene.md` — Präfix-/Teardown-Konzept
- `docs/specs/modules/fix_1289_e2e_env_minimal.md` — Secrets-Minimierung im Preview-Start
- **Fehlt:** ein zentrales „So führst du die E2E-Suite aus"-Dokument

## Dependencies

- **Upstream:** GitHub-Actions-Runner (`ubuntu-latest`), Go-Toolchain, uv/Python 3.12,
  Node 22, Node-Playwright-Browser (bisher **nie** in CI installiert — die vorhandene
  `playwright install`-Zeile in `ci.yml:22` gehört zum *Python*-Playwright für
  `tests/visual` Pixel-Diff)
- **Downstream:** Merge-Regel (5 grüne Checks). Ein neuer Pflicht-Check ändert die
  Liefer-Regel in CLAUDE.md und ggf. die Branch-Protection

## Risks & Considerations

1. **Grün ohne Aussage** (größtes Risiko): 35 Laufzeit-Skips + leeres CI-Datenverzeichnis ⇒
   ein Lauf, der nichts prüft, aber alles freigibt. Gegenmittel: gemessenes Skip-Budget.
2. **Flake importiert Rot in jeden fremden PR**: 78+ `waitForTimeout` bei 921 Tests. Ein
   flackernder Pflicht-Check ist schlimmer als kein Check — er erodiert die Merge-Regel.
   Gegenmittel: klein anfangen, `retries` bewusst wählen, Kandidaten belegt auswählen.
3. **Unbekannter Grün-Stand**: ohne Volllauf ist jede Auswahl geraten. Der Volllauf ist
   Vorbedingung, nicht Kür — und selbst ein Arbeitspaket.
4. **Laufzeit**: 921 Tests sequenziell sprengen das 9-min-Budget deutlich. Sharding/Auswahl
   nötig.
5. **Regel-Budget (CLAUDE.md)**: Ein neuer Pflicht-Check braucht Prüfdatum (+90 Tage) oder
   muss eine bestehende Regel ersetzen.
6. **Scope-Schnitt**: Die Scheibe kann nicht zugleich den Stack bauen, 158 Specs sanieren und
   den Wildwuchs aufräumen. Sanierung gehört getrennt (#1196-Nähe).

---

# Analysis (Phase 2, 2026-08-13)

## Type

**Feature/Infrastruktur** (Issue trägt `bug`, aber die Arbeit ist der Aufbau einer neuen
CI-Lane, kein Fix an Produktivcode).

## 🔬 Machbarkeitsnachweis: der isolierte Stack läuft — experimentell belegt

Statt gegen die geteilte Staging-Instanz zu messen (stört fünf parallele Sessions, ~1 h),
habe ich den CI-Stack **lokal nachgebaut** und gemessen. Wegwerf-Aufbau im Scratchpad,
Produktivdienste unberührt.

| Prüfung | Ergebnis |
|---|---|
| Go-Server bauen | OK (24 MB) |
| Python-Core `:8005` mit `GZ_TEST_FIXTURE_DIR` | `/health` → **200** |
| Go-API `:8095`, Fixtures, eigenes `GZ_DATA_DIR` | `/api/health` → **200** |
| Selbst-Seed des Nutzers | `Seed user created` im Log, Login → **200** |
| Location anlegen (direkt gegen Go) | **201** |
| Playwright dagegen | läuft, App rendert vollständig |

**⇒ Der Stack ist machbar, offline, ohne Netz und ohne Secrets.**

### Zwei Details, die den Aufbau entscheiden

1. **`GZ_PORT` muss gesetzt werden.** Der Go-Default ist `8090` (`config.go:8`) — und
   `prodUrlGuard.ts` lehnt fail-closed jedes Loopback-Ziel auf 8090 ab. Ein unkonfigurierter
   Stack wird von der eigenen Prod-Sperre erschlagen. Mit `8091` braucht die Frontend-Seite
   **null** Overrides (ist bereits Default von `GZ_API_BASE`/`API_PROXY_TARGET`).
2. **Kein Secret setzen — aber auch nicht halb.** `config.go:16` und
   `hooks.server.ts:16` defaulten beide auf `dev-secret-change-me`. Im Runner gibt es keine
   `.env`, `e2e-env.sh` lädt nichts, beide Seiten treffen sich auf dem Default. **Setzt man
   es nur auf einer Seite, bricht die Auth still** (siehe Messfehler unten).

### 🔴 Eigener Messfehler — dokumentiert, weil er die Zahlen erklärt

Erste Stichprobe: „61 von 72 rot". **Diese Zahl war wertlos.** Ich hatte dem Go-Server ein
eigenes `GZ_SESSION_SECRET` gegeben, während der SvelteKit-Preview es aus der Haupt-`.env`
zog — Cookie-Signaturen passten nicht, Ergebnis `HTTP 401` auf jedem API-Ruf
(`createTestLocation fehlgeschlagen: HTTP 401`). Fast hätte ich daraus „der Testbestand ist
zu 96 % verrottet" geschlossen. *Merksatz: den eigenen Messaufbau validieren, bevor man dem
Prüfling die Schuld gibt.*

**Verbleibend offen:** Auch nach der Korrektur bleibt ein 401 im
SvelteKit-Weiterleitungspfad, während der direkte Weg zum Go-Server (Login 200, Anlegen 201)
einwandfrei funktioniert. Das ist ein **eingegrenzter Arbeitspunkt der Umsetzung**, kein
Machbarkeits-Killer — und lokal schwer zu isolieren, weil dieser Rechner eine `.env` hat,
die der Runner nicht hat. **Konsequenz für den Schnitt:** Der Vermessungslauf gehört in den
Runner (`workflow_dispatch`), nicht auf diese Maschine.

## 🔴 Die Grün-Quote des Bestands — gemessen, nicht geschätzt

Dieselbe 15-Datei-Stichprobe (**72 Testfälle**) gegen **Staging im Normalbetrieb**,
seriell gefahren (Port 4173 ist geteilt, `reuseExistingServer: true` — parallele Läufe
verunreinigen sich gegenseitig; ein erster Parallelversuch musste deshalb verworfen werden):

| | Anzahl | Anteil |
|---|---|---|
| **passed** | **45** | 62,5 % |
| **failed** | **22** | **30,6 %** |
| skipped | 5 | 6,9 % |
| Laufzeit | ~2 min | |

**Das ist die zentrale Zahl der Analyse.** Der Bestand ist weder verrottet noch
einsatzbereit: Fast **jeder dritte Test ist heute rot** — im Normalbetrieb, ohne dass
jemand etwas geändert hätte. Ein naives „alle 921 einhängen" färbt die Ampel sofort und
dauerhaft rot und macht die Merge-Regel unbrauchbar.

⇒ **Die Positivliste ist damit nicht eine von mehreren Optionen, sondern die einzige
tragfähige.** Eine Ausschlussliste müsste diese 31 % erst sanieren, bevor irgendetwas
bewacht wäre — genau das „Sanierungsprojekt mit offenem Ende", vor dem das Issue warnt.

*Einschränkung: gegen die geteilte Staging-Instanz gemessen, auf der fünf weitere Sessions
arbeiten; einzelne Fehlschläge können Fremdeinwirkung sein. Die Größenordnung — rund ein
Drittel rot — ist davon unberührt.*

## Technischer Ansatz (Empfehlung)

**Neuer, paralleler Job `e2e` — nicht `frontend-test` erweitern.** Der kostet heute 64 s und
ist ein schneller Signalgeber; ein E2E-Anhängsel zerstört das. Parallel kostet die Lane
**keine** zusätzliche Wanduhrzeit (Ampel = 10 min, bestimmt vom `test`-Job mit 561 s).

Ablauf im Job: checkout → Go bauen → uv/Python → Node + `npx playwright install` (**neu** —
die Zeile in `ci.yml:22` ist der *Python*-Playwright für `tests/visual`) → Python-Core und
Go-Server im Hintergrund starten → **Health-Warteschleifen statt `sleep`** (sonst importiert
der Job dieselbe Fristen-Krankheit, die er bewachen soll) → Playwright gegen die Auswahl.
Stack-Start gehört in ein Skript `frontend/e2e/ci-stack.sh` — hält `ci.yml` lesbar und
schließt zugleich die Lücke „kein zentrales E2E-Setup-Dokument".

Overhead ~4–4,5 min ⇒ **~4,5 min Testzeit** im 9-min-Budget.

### 🔴 Richtungsumkehr der Ratsche: Positivliste statt Ausschlussliste

`ci_tdd_excludes.txt` ist als Vorbild **nur strukturell** brauchbar, nicht in der Richtung:
Eine Ausschlussliste setzt voraus, dass die Grundmenge grün ist. Hier ist sie es
nachweislich nicht (A/B: dieselben 3 von 9 Tests rot in *beiden* Stacks). Eine
Ausschlussliste würde die unbekannte Rote als Verpflichtung erben.

⇒ **`.github/ci_e2e_specs.txt` — Positivliste, die nur WACHSEN darf.** Was nicht drauf
steht, verpflichtet zu nichts. Das ist das Werkzeug, das „Sanierungsprojekt mit offenem
Ende" verhindert.

Auswahl in zwei Filtern, beide belegt:
- **A (strukturell, gemessen):** keine konditionalen Skips, keine `waitForTimeout`, keine
  permanenten Skips → **106 Dateien / 618 Testfälle** Kandidatenpool. Zusätzlich raus:
  Wetter*wert*-prüfende Specs (Fixtures decken nur **heute + 2 Tage**) und die 16 Staging-Specs.
- **B (gemessen auf dem Runner):** Vermessungslauf über A; aufgenommen wird, was **3×
  hintereinander** grün ist.

### 🔴 Gegen „grün ohne Aussage": drei Bedingungen statt einer

Playwright-JSON-Reporter liefert `stats`. Die Auswertung fordert:
1. `unexpected == 0` (keine Roten) — das prüft ein naiver Lauf
2. `skipped == 0` (Filter A macht das baulich erzwingbar, nicht verhandelbar)
3. **`expected >= E2E_MIN_EXECUTED`** ← *der* Mechanismus

Bedingung 3 trägt die Last: Scheitert der Seed, kommt der Stack nicht hoch oder zeigt die
Liste ins Leere, ist `expected == 0` und der Job **rot** statt grün. Ohne sie wäre die Lane
genau der Bericht, den sie ersetzen soll.

**Mutations-Gegenprobe als Abnahme (CLAUDE.md-Pflicht):** ein `data-testid` in einer
abgedeckten Komponente verfälschen und belegen, dass die Lane rot wird. Ohne diesen Beleg
ist der Job selbst nur ein Bericht.

### Pflicht-Check: ja

Das Projekt hat den informativen Weg bei `tests/tdd/` bereits bezahlt (~5000 blinde Tests,
6 wochenlang unbemerkte Rote, #1196). Eine nicht-blockierende Klickpfad-Lane reproduziert
diesen Zustand — die teure Variante von „nichts tun". Das Flake-Risiko sitzt **nicht** im
Check-Status, sondern in der **Listengröße**, und die kontrollieren wir vollständig.
`retries: 0` — ein Retry versteckt genau die Flake-Klasse, die wir sehen wollen.

Formal eine **Erweiterung der bestehenden Merge-Regel** (Prüfdatum 2026-11-02), kein neues
Gate. Regel-Budget-Eintrag: Prüfdatum **2026-11-11**, Fang-Kriterium „mindestens ein PR, in
dem die Lane eine Regression fängt, die die anderen fünf durchlassen".

## Affected Files

| Datei | Art | ~LoC |
|---|---|---|
| `.github/workflows/ci.yml` | MODIFY — Job `e2e` + `workflow_dispatch`-Variante | ~70 |
| `frontend/e2e/ci-stack.sh` | CREATE — Stack-Start + Health-Warten | ~35 |
| `.github/ci_e2e_specs.txt` | CREATE — Positivliste + Kopfkommentar | ~30 |
| `frontend/playwright.config.ts` | MODIFY — CI-Zweig (`workers:1`, `retries:0`, `reuseExistingServer:!CI`, Trace) | ~10 |
| Auswertungsblock in `ci.yml` | MODIFY — JSON-Stats → 3 Bedingungen | ~20 |
| ADR-0053, Spec, CLAUDE.md | CREATE/MODIFY — zählen nicht (`.md`) | 0 |

**≈ 165 LoC — unter dem 250er-Limit, ohne Override.** Kein Zufall, sondern Ergebnis des
Schnitts: Jede Spec-Sanierung sprengt es sofort (allein 78 `waitForTimeout`).

**Kein 52. Config-File** — die CI-Abweichungen gehören als Zweig in die Wurzel-Config. Setzt
den Präzedenzfall gegen den Wildwuchs.

## Risk Level: **MEDIUM**

| Risiko | Schwere | Gegenmittel |
|---|---|---|
| **Parallele Worker auf gemeinsamer Datenwurzel** — Config setzt kein `workers`, Default Kerne/2; mehrere Worker teilen dieselben Seed-IDs | **hoch** | `workers: 1`; kostet Zeit, kauft Determinismus |
| Prod-Sperre trifft eigenen Stack (Port 8090) | mittel | `GZ_PORT=8091` |
| Session-Secret halb gesetzt ⇒ stiller 401 | **hoch** (selbst erlebt) | gar nicht setzen; im Runner keine `.env` |
| Fixture-Fenster nur heute + 2 Tage | mittel | Auswahlkriterium |
| Vorbestehende Rote wandern in die Liste | mittel | Filter B (3× grün) |
| `global.teardown.ts` läuft gegen beendeten Server | mittel | Server erst **nach** Playwright-Exit stoppen |
| Diagnose im Runner unmöglich | mittel | `trace: retain-on-failure` + Artefakt nur `if: failure()` |

**Was die Lane instabil macht, ist nicht der Stack — es ist die Auswahl.** Der Stack ist
deterministisch (Fixtures, leere Datenwurzel, kein Netz). Jede Instabilität kommt aus Specs,
die wir freiwillig aufnehmen. Die Aufnahmehürde ist der einzige Hebel, der zählt.

## Scheiben-Schnitt

**In dieser Scheibe:** Job `e2e` + `ci-stack.sh` · Positivliste + `E2E_MIN_*` · Drei-Bedingungs-
Auswertung · CI-Zweig in `playwright.config.ts` · Vermessungslauf als `workflow_dispatch` ·
ADR-0053 · CLAUDE.md 5→6 · Mutations-Gegenprobe.

**Bewusst NICHT:**
- **Volllauf über alle 921 Tests** — die Positivliste macht ihn für *diese* Scheibe
  entbehrlich und für Folge-Scheiben per Knopfdruck verfügbar. Er wird damit
  Wachstumsmaschine statt Vorbedingung.
- `waitForTimeout`-Sanierung (78–81) — eigene Scheibe, sprengt allein das LoC-Limit
- Skip-Sanierung (35) — Startmenge umgeht sie
- Toter Bestand (`issue-264-stage-sort.spec.ts` kaputt, `issue-407`-Grabstein, tote
  `fillStep2/3/4` mit Signal-Kanal) — **Nebenbefund-Triage ⇒ #1196**, keine eigenen Issues
- Config-Wildwuchs (50 Dateien) — eigene Scheibe; hier nur kein neues anlegen
- Sharding — erst wenn die Liste das Budget sprengt
- Die 16 Staging-Specs — brauchen Remote + Zugangsdaten, gehören nicht in eine Offline-Lane

## ADR-Pflicht

**ADR-0053** (Entscheidungsfläche Test-/Deploy-Strategie), fortschreibend zu ADR-0006 und
ADR-0028. Im Text muss stehen, dass ADR-0028s Verwerfung von „Isolation über `GZ_DATA_DIR`"
**verjährt** ist — sonst wird eine dokumentierte Entscheidung still umgangen. Die Nutzung
von `GZ_E2E_API_PROXY_TARGET` ist kein Abweichen; ADR-0028 sieht den Override vor.

## Open Questions

- [ ] Startgröße der Positivliste: ~10–15 Dateien / ~50 Tests (bei `workers: 1`) — final
      erst nach dem Vermessungslauf im Runner
- [ ] Der verbleibende 401 im Preview-Weiterleitungspfad: im Runner erneut prüfen (dort ohne
      störende `.env`)
