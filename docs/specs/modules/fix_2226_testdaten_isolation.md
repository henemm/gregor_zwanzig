---
entity_id: fix_2226_testdaten_isolation
type: module
created: 2026-09-11
updated: 2026-09-11
status: draft
version: "1.0"
tags: [tests, isolation, e2e, datenverlust]
---

# fix_2226_testdaten_isolation

## Approval

- [ ] Approved

## Purpose

Drei Defekte lassen Tests in echte Bestände statt in Wegwerf-Kulissen schreiben. **Defekt 1:**
`tests/conftest.py` schaltet die Datenwurzel-Isolation fälschlich auch beim `live`-Marker ab, obwohl
`live` laut `pyproject.toml` nur Netz-Egress bedeutet, nicht „echter Dateibaum nötig". **Defekt 3**
(der schwerere, markerunabhängige): module-/class-/session-weite Fixtures laufen vor der
funktionsweiten Isolations-Fixture `_isolate_data_root` und schreiben deshalb unbemerkt in den
echten Baum — weder Umleitung noch Snapshot-Wächter greifen, weil beide erst danach ansetzen.
**Defekt 2:** Die E2E-Suite liest denselben Testnutzer aus zwei verschiedenen Umgebungsvariablen
(`E2E_USER` vs. `GZ_E2E_USER`), sodass wer nur eine setzt, die Suite nur zur Hälfte umbiegt.

## Source

- **File:** `tests/conftest.py` (Fixtures `_isolate_data_root`, `_materialize_real_data_root_fixtures`,
  neue session-weite Redirect- und Wächter-Fixture); `frontend/e2e/helpers.ts`,
  `frontend/e2e/global.setup.ts`, neues Resolver-Modul `frontend/e2e/`
- **Identifier:** `_isolate_data_root`, neue session-weite autouse-Redirect-Fixture,
  `login()` (`helpers.ts`), neuer E2E-Testnutzer-Resolver

> Schicht: Testinfrastruktur (`tests/`, Python-Core-Ebene) und E2E-Tooling (`frontend/e2e/`,
> Playwright-Ebene) — kein Produktivcode in `src/`, `api/`, `internal/`, `frontend/src/`.

## Estimated Scope

- **LoC:** ~250–400 (voraussichtlich über dem 250-LoC-Workflow-Limit — dokumentierter Weg:
  `workflow.py set-field loc_limit_override 500`)
- **Files:** `tests/conftest.py`, `tests/tdd/test_issue_1013_telegram_test_isolation.py` (Stellvertreter-
  Wächter reparieren), `frontend/e2e/helpers.ts`, `frontend/e2e/global.setup.ts`, neues Resolver-Modul
  unter `frontend/e2e/`, neue Sondentests (Kern, Python) für AC-1 bis AC-6, neue Vitest-Unit-Tests für
  AC-7 bis AC-10
- **Effort:** high

## Non-Goals

- **Kein Aufräum-Skript für Altbestand.** Die 15 verirrten Testnutzer im Hauptcheckout wurden am
  11.09. bereits manuell entfernt (Sicherung `verirrte-testnutzer-2226.tar.gz`). Dieses Ticket
  behebt nur die Ursache, nicht historische Folgen.
- **Kein fail-closed beim `'admin'`-Default in Rolle C.** Der CI-e2e-Job (`ci-stack.sh:12-16,66`)
  verlässt sich bewusst darauf und seedet denselben Account serverseitig; ein fail-closed Credential
  bräche ihn ohne Begleitänderung. Der wirksame Schutz gegen echte Konten ist der Ziel-Guard
  `frontend/e2e/prodUrlGuard.ts`, nicht der Kontoname.
- **Rollen A (`GZ_VALIDATOR_USER`, nginx-Basic-Auth) und B (`GZ_AUTH_USER`, Staging-App-Login)
  werden nicht angetastet.** Sie mit Rolle C zusammenzuführen wäre eine eigenständige Regression
  gegen Staging-Verhalten, kein Teil dieses Befunds.
- **Kein Marker-Nachzug an bestehenden `live`-Tests.** Die Enumeration über alle 75 `live`-markierten
  Dateien (2026-09-11) ergab eine leere Kategorie-A-Liste — kein Test braucht zusätzlich
  `real_data_root`, um nach dem Fix weiter zu funktionieren.
- **Zwei Nebenbefunde gehören NICHT in dieses Ticket**, sondern als Sammeleinträge nach #1196/#1199:
  die `os.walk`-Zählung des Snapshot-Wächters sieht neu angelegte **leere** Verzeichnisse nicht
  (Fingerprint auf Dateizahl/mtime/Größe); `tests/tdd/test_issue_338_go_geosphere_counter.py` spawnt
  einen pytest-Subprozess, der die Isolation strukturell nicht erbt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/conftest.py:_isolate_data_root` (#1133) | Upstream | Bestehende funktionsweite Isolations-Fixture, wird um eine session-weite Vorstufe ergänzt |
| `tests/conftest.py:_materialize_real_data_root_fixtures` (#1265 Teil C) | Upstream | Session-weit autouse, kopiert legitime Referenz-Fixtures (`default`, `validator-issue110`) gegen den ECHTEN Baum — Reihenfolge zur neuen Redirect-Fixture muss explizit gepinnt werden |
| `tests/conftest.py`-Wächter (#1265 Teil C) | Upstream | Snapshot-Vergleich vor/nach dem Testlauf, braucht eine session-weite Entsprechung |
| `tests/tdd/test_issue_1013_telegram_test_isolation.py` (#1013) | Sibling | Bestehender Stellvertreter-Wächter zu `tg-live-e2e`, prüft heute die falsche Wurzel — wird in diesem Ticket repariert |
| `frontend/e2e/prodUrlGuard.ts` (#1284) | Sibling | Wirksamer Ziel-Guard gegen Prod, bleibt unverändert der primäre Schutz gegen Rolle-C-Credentials |
| `docs/specs/modules/fix_1329_e2e_data_hygiene.md` | Sibling | Playwright-Staging-Wegwerfdaten — angrenzend, nicht überlappend mit der Python-Datenwurzel |
| `pyproject.toml` (Marker-Registrierung `live`, `real_data_root`) | Upstream | Definiert die beiden Marker unterschiedlich — Beleg für Defekt 1 |

## Implementation Details

```
# Defekt 1 + 3: Vorzeichen umkehren — "per Default isoliert, Opt-in per Marker"

@pytest.fixture(scope="session", autouse=True)
def _redirect_data_root_session(tmp_path_factory):
    # läuft VOR jeder module-/class-/function-weiten Fixture (pytest-Scope-Rang:
    # session > package > module > class > function)
    session_root = tmp_path_factory.mktemp("gz-data-root-session")
    loader._DATA_ROOT = session_root
    before = _snapshot_repo_data_users()          # session-weites Gegenstück zum
    yield                                          # bestehenden Wächter — nimmt den
    after = _snapshot_repo_data_users()            # Schnappschuss VOR jeder höher
    if before != after:                            # gescopten Fixture
        pytest.fail("...")
    loader._DATA_ROOT = _ORIGINAL_DATA_ROOT

# _materialize_real_data_root_fixtures (session-weit, #1265 Teil C) MUSS trotzdem
# gegen den ECHTEN Baum kopieren. Reihenfolge NICHT der Definitionsreihenfolge
# überlassen — explizit pinnen:
@pytest.fixture(scope="session", autouse=True)
def _materialize_real_data_root_fixtures(_redirect_data_root_session):
    ...  # unverändert im Körper, kopiert gegen loader._ORIGINAL_DATA_ROOT

# _isolate_data_root (funktionsweit, bestehend) verengt nur noch:
@pytest.fixture(autouse=True)
def _isolate_data_root(request, tmp_path):
    if request.node.get_closest_marker("real_data_root"):
        loader._DATA_ROOT = _ORIGINAL_DATA_ROOT   # Opt-in: echte Wurzel wiederherstellen
        yield
        loader._DATA_ROOT = <session_root>
        return
    # "live" allein schaltet NICHTS mehr ab — kein Early-Return mehr dafür
    loader._DATA_ROOT = tmp_path / "data"
    yield
```

```
# Defekt 2: EIN Resolver für Rolle C, aus global.setup.ts UND helpers.ts genutzt

// frontend/e2e/testUser.ts (neu)
export function resolveE2EUser() {
  return {
    user: process.env.E2E_USER ?? process.env.GZ_E2E_USER ?? 'admin',
    pass: process.env.E2E_PASS ?? process.env.GZ_E2E_PASS ?? 'test1234',
  };
}
```

`global.setup.ts:36` und `helpers.ts:100` (`login()`) rufen beide `resolveE2EUser()` statt eigener
`??`-Ketten. Rollen A/B bleiben strukturell getrennt und unverändert.

**Bindende Regel für alle Sondentests (AC-1 bis AC-6):** Der **äußere** Kern-Test — der den inneren
pytest-Subprozess startet und danach den echten Baum prüft — darf `<repo>/data/users` **niemals**
über `app.loader`/`get_data_root()` auflösen (dessen `_DATA_ROOT` zeigt zur Testzeit selbst auf die
Session-Wurzel, nicht auf den echten Baum). Die Auflösung muss **strukturell relativ zur eigenen
Testdatei** erfolgen (`Path(__file__).parent.parent.parent / "data" / "users"` o. ä.), analog zur
projektweiten Regel „Ein Test löst seinen Prüfling relativ zur eigenen Testdatei auf, nie über den
festen Hauptrepo-Pfad". Eine Auflösung über `app.loader` würde denselben Stellvertreter-Fehler neu
einführen, den AC-6 gerade repariert.

## Expected Behavior

- **Input:** Ein Testlauf (`uv run pytest ...`), der Fixtures beliebigen Scopes enthält, die Daten
  über `app.loader`/`get_data_dir()` schreiben oder lesen.
- **Output:** Der echte `<repo>/data/users`-Baum bleibt während des gesamten Laufs unverändert —
  weder Inhalt noch Verzeichnis-mtime —, es sei denn, ein Test trägt explizit den Marker
  `real_data_root`. `live` allein bewirkt das nicht mehr.
- **Side effects:** Ein Test, der außerhalb von `app.loader` (hartkodierter Pfad) in den echten Baum
  schreibt, lässt den Testlauf mit `pytest.fail` scheitern statt lautlos durchzulaufen.

## Acceptance Criteria

- **AC-1:** Given ein Testmodul mit einer `scope="module"`-Fixture, die ohne jeden Marker über
  `get_data_dir()` in den Datenbaum schreibt / When dieses Modul per pytest läuft / Then bleibt der
  echte `<repo>/data/users` **inhaltlich unverändert** und auch seine **mtime unverändert** — auch
  nicht vorübergehend während des Laufs.
  - Test: Ein Kern-Test startet per Subprozess einen inneren pytest-Lauf über eine synthetische Sonde
    B innerhalb von `tests/` (damit `tests/conftest.py` geladen wird), die eine `scope="module"`-Fixture
    ohne Marker über `get_data_dir()` schreiben lässt. Der äußere Test löst `<repo>/data/users`
    strukturell relativ zur eigenen Testdatei auf (nicht über `app.loader`) und prüft Inhalt UND mtime
    vor/nach dem inneren Lauf auf Gleichheit.

- **AC-2:** Given dieselbe Sonde B, zusätzlich mit `real_data_root` markiert / When der innere Lauf
  läuft / Then erreicht sie weiterhin den echten Baum — das Opt-in funktioniert unverändert.
  - Test: Derselbe innere Lauf, diesmal mit `real_data_root` auf der Sonde, muss im echten Baum eine
    nachweisbare Spur hinterlassen (vom Kern-Test danach wieder entfernt); bleibt der Baum
    unverändert, ist das Opt-in kaputt.

- **AC-3:** Given ein `live`-markiertes Testmodul ohne `real_data_root`, das `save_trip` aufruft /
  When es per pytest läuft / Then schreibt es **nicht** in den echten `<repo>/data/users`-Baum —
  `live` allein schaltet die Isolation nicht mehr ab.
  - Test: Ein Kern-Test startet per Subprozess einen inneren pytest-Lauf über Sonde A (`live`-Marker,
    ruft `save_trip` auf, innerhalb von `tests/`) und prüft den echten Baum danach unverändert, mit
    derselben strukturellen Pfadauflösung wie AC-1.

- **AC-4:** Given dieselbe Sonde A, zusätzlich mit `real_data_root` markiert / When der innere Lauf
  läuft / Then erreicht sie weiterhin den echten Baum.
  - Test: Derselbe innere Lauf mit `live` + `real_data_root` muss im echten Baum eine nachweisbare
    Spur hinterlassen; bleibt der Baum unverändert, ist das Opt-in kaputt.

- **AC-5:** Given ein Testmodul, dessen `scope="module"`-Fixture über einen **hartkodierten** Pfad
  (nicht über `app.loader`) eine **Datei** unter dem echten `<repo>/data/users`-Baum anlegt / When es
  per pytest läuft / Then **scheitert der Lauf** — der session-weite Wächter fängt, was die
  funktionsweite Prüfung strukturell nicht sehen kann.
  - Test: Ein Kern-Test startet den inneren Lauf über eine Sonde, deren `scope="module"`-Fixture eine
    Datei (nicht nur ein Verzeichnis — der bestehende Wächter fingerprintet über Dateizahl/mtime/
    Größe und sieht leere neu angelegte Verzeichnisse nicht) unter einem hartkodierten Pfad in
    `<repo>/data/users` schreibt, und prüft den `returncode` des inneren pytest-Laufs auf ungleich 0.

- **AC-6:** Given `tests/tdd/test_issue_1013_telegram_test_isolation.py:46` behauptet heute
  `not (tmp_path / "data" / "users" / "tg-live-e2e").exists()` — geprüft wird die Wegwerf-Wurzel /
  When derselbe Test nach dem Fix läuft / Then ist die Zusicherung gegen den **echten**
  `<repo>/data/users` gerichtet, strukturell relativ zur Testdatei aufgelöst (nicht über
  `app.loader`).
  - Test: Der reparierte Test prüft `not (<strukturell aufgelöster echter Baum> / "tg-live-e2e").exists()`.
    Als Mutations-Gegenprobe: eine Verfälschung, die die zugrundeliegende Fixture wieder auf den
    echten Baum zeigen lässt (die Regression, die dieses Ticket behebt), MUSS diesen Test rot machen —
    eine Fassung, die weiterhin nur `tmp_path` prüft, tut das nicht und ist damit selbst der Fehler,
    den dieser AC ausschließt.

- **AC-7:** Given nur `E2E_USER`/`E2E_PASS` ist gesetzt / When `login()` (`helpers.ts`) bzw.
  `global.setup.ts` den Testnutzer auflösen / Then wird **dieser** Nutzer verwendet.
  - Test: Ein Vitest-Unit-Test für den neuen Resolver setzt `E2E_USER='sonde-a'` in der
    Prozessumgebung, ruft `login()` mit einem Stub-`page`-Objekt auf, das `fill()`-Aufrufe
    mitschreibt, und prüft, dass `'sonde-a'` tatsächlich in den Formular-`fill()`-Aufruf für das
    Username-Feld eingeht — nicht nur, dass der Resolver den Wert zurückgibt.

- **AC-8:** Given nur `GZ_E2E_USER`/`GZ_E2E_PASS` ist gesetzt (kein `E2E_USER`) / When derselbe
  Resolver aufgelöst wird / Then wird dieser Wert genutzt — kein bestehender Aufruf aus den 60
  importierenden Spec-Dateien bricht.
  - Test: Derselbe Vitest-Aufbau mit `GZ_E2E_USER='sonde-b'` gesetzt (kein `E2E_USER`), prüft den
    `fill()`-Aufruf auf `'sonde-b'`.

- **AC-9:** Given weder `E2E_USER` noch `GZ_E2E_USER` ist gesetzt / When derselbe Resolver aufgelöst
  wird / Then bleibt es bei `'admin'`/`'test1234'` — der CI-e2e-Job verlässt sich bewusst darauf.
  - Test: Derselbe Vitest-Aufbau mit beiden Variablen ungesetzt prüft den `fill()`-Aufruf auf
    `'admin'`/`'test1234'`.

- **AC-10:** Given die Auflösung von Rolle A (`GZ_VALIDATOR_USER`) und Rolle B (`GZ_AUTH_USER`) /
  When der neue Resolver eingeführt wird / Then bleibt ihr Verhalten unverändert — sie werden nicht
  eingeschmolzen.
  - Test: Bestehende Tests/Nutzungsstellen zu `GZ_VALIDATOR_USER` (nginx-Basic-Auth,
    `httpCredentials`) und `GZ_AUTH_USER` (Staging-App-Login) laufen unverändert weiter; ein
    zusätzlicher Vitest-Test prüft, dass der neue Rolle-C-Resolver `GZ_VALIDATOR_USER`/`GZ_AUTH_USER`
    an keiner Stelle liest.

Für AC-7 bis AC-10 gilt: **kein** Dateiinhalt-Check. Der Nachweis läuft über den tatsächlich in die
`fill()`-Aufrufe eingehenden Wert, nicht über das bloße Vorhandensein einer Zeile im Quelltext.

## Known Limitations

- ~~**Enumeration-Lücke bei Defekt 3**~~ — **am 2026-09-11 geschlossen, Ergebnis: kein
  Kollateralschaden.** Die erste Prüfung („Kategorie-A-Liste ist leer", 75 `live`-markierte Dateien)
  deckte tatsächlich nur Defekt 1 ab. Defekt 3 ist markerunabhängig, deshalb wurde die Population
  der höher gescopten Fixtures gesondert enumeriert: **46 Fixtures in 28 Dateien** (40× `module`,
  3× `session`, 3× `class`, 0× `package`). **Keine** davon liest Bestand aus dem echten
  `data/users`-Baum, den sie nicht selbst vorher anlegt. Gründe, nach Zugriffsmuster:
  - Der größte Teil läuft per Playwright/httpx/curl gegen einen **separaten Prozess** (Go-API,
    SvelteKit, Staging) — ein `_DATA_ROOT`-Patch im pytest-Prozess wirkt dort ohnehin nicht, vor wie
    nach dem Fix (u.a. `test_account_page.py:36`, `test_change_password.py:28`,
    `test_issue_692_telegram_disabled_unconfigured.py:138`).
  - Ein weiterer Teil lädt nur Hilfsmodule per `importlib` (Validatoren, Skripte) oder scannt
    Quelltext — Zugriffe außerhalb von `data/users`.
  - Die einzigen Fixtures, die über `app.loader` Nutzerdaten anfassen, **schreiben zuerst und lesen
    danach zurück** (Kategorie B): `test_alarm_messluecke_ausdehnung_wortebene.py:208` und
    `test_alarm_gewitterpruefung_ungeprueft_wortebene.py:145` — genau die beiden bekannten
    Verursacher. Der Fix leitet sie künftig korrekt in die Wegwerf-Wurzel um.
  - `test_issue_1068_tier_model_display.py:146` greift per `sudo` auf einen absoluten Pfad des
    Staging-Hosts zu — außerhalb jeder lokalen Isolation.
  Die Methode wurde an den beiden bekannten Verursachern kalibriert (beide korrekt als B erkannt).
  Alle 46 Fixtures konnten statisch entschieden werden; keine offenen Unsicherheiten.
- **Vereinfachung für die Umsetzung (aus derselben Enumeration):**
  `_materialize_real_data_root_fixtures` (`tests/conftest.py:179`) schreibt über einen
  **hartkodierten** `root/"data"/"users"`-Pfad, **nicht** über `loader._DATA_ROOT`. Die Fixture ist
  damit vom Redirect unabhängig, und die befürchtete Reihenfolge-Kopplung zur neuen session-weiten
  Redirect-Fixture entfällt weitgehend. Was bleibt: `real_data_root`-Tests müssen die echte Wurzel
  sehen, **nachdem** materialisiert wurde — die Abhängigkeit ist also weiterhin explizit zu pinnen,
  aber nicht mehr, weil der Kopiervorgang selbst umgeleitet werden könnte.
- **Mtime-Flake-Risiko in AC-1/AC-3:** Da `tests/conftest.py` stark geteilt ist und parallele
  Sessions denselben Hauptcheckout teilen können, kann die mtime-Prüfung theoretisch flackern, wenn
  eine andere aktive Session zeitgleich in denselben echten `data/users`-Baum schreibt. Bei Flake:
  Retry, erst reproduzierbares Scheitern ist ein Befund.
- Der Ist-Bestand der 15 verirrten Testnutzer wurde manuell bereinigt (s. Non-Goals) — ohne diesen
  Fix läuft der Baum beim nächsten unvollständigen Lauf wieder voll.
- `global.setup.ts` und `helpers.ts` müssen **beide** auf denselben Resolver umgestellt werden, sonst
  bleibt die Suite bei nur einer gesetzten Variable weiterhin gespalten (der ursprüngliche Befund
  B1-56 selbst).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der Fix kehrt die Default-Richtung der Datenwurzel-Isolation um (Opt-out per Marker
  → Opt-in per Marker) und berührt damit die Entscheidungsfläche Test-Strategie. Es existiert jedoch
  **keine** Spec und **keine** ADR zur ursprünglichen Isolations-Fixture (#1133/#1265 Teil C) — ihre
  Mechanik lebt bislang nur im Docstring von `tests/conftest.py`. Da nichts Dokumentiertes abgelöst
  wird, ist kein „Status: Abgelöst durch" nötig; die neue Fail-closed-Richtung ist zudem im Haus
  bereits etabliertes Muster (z. B. `.claude/hooks/e2e_frontend_browser_gate.py`), kein Novum, das
  eine eigene ADR rechtfertigt.

## Changelog

- 2026-09-11: Initial spec created
- 2026-09-11: Enumeration-Lücke bei Defekt 3 geschlossen (46 höher gescopte Fixtures in 28 Dateien
  geprüft, Kategorie-A-Liste leer); Reihenfolge-Falle relativiert, weil
  `_materialize_real_data_root_fixtures` über einen hartkodierten Pfad arbeitet
