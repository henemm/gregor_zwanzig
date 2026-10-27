# Context: fix-2226-testdaten-isolation

Issue: [#2226](https://github.com/henemm/gregor_zwanzig/issues/2226) · Label `bug`, `priority:high`
Abgespalten aus #1199 (Volltriage 2026-09-08), Kriterium **(b) Datenverlust-/Sicherheitsrisiko**.

## Request Summary

Zwei Befunde, die beide dazu führen, dass Tests in echte Bestände schreiben statt in Wegwerf-Kulissen:

- **C4-17** — `tests/conftest.py` schaltet die Datenwurzel-Isolation still ab, sobald ein Test den
  Marker `live` trägt. Live-markierte Tests mit `save_trip` & Co. schreiben dadurch in den echten
  `data/users/`-Baum.
- **B1-56** — Die E2E-Suite liest den Testnutzer aus zwei verschiedenen Umgebungsvariablen
  (`E2E_USER` vs. `GZ_E2E_USER`). Wer eine davon setzt, biegt nur die Hälfte der Suite um; dass dabei
  keine echten Konten getroffen wurden, war Zufall des gemeinsam getroffenen `'admin'`-Defaults.

## Befund C4-17: Isolation wird vom falschen Marker abgeschaltet

### Fundstelle

`tests/conftest.py:250-300`, Fixture `_isolate_data_root` (autouse, function-scoped). Early-Return:

```python
if request.node.get_closest_marker(
    "real_data_root"
) or request.node.get_closest_marker("live"):
    yield
    return
```

### Der Early-Return schaltet ZWEI Mechanismen ab, nicht einen

Das ist für die Spec entscheidend — wer nur an einen denkt, lässt den anderen liegen:

1. **Umleitung:** `loader._DATA_ROOT` wird auf eine `tmp_path_factory`-Wurzel gebogen (`conftest.py:279-281`).
   Schützt alles, was über `app.loader` läuft.
2. **Snapshot-Wächter:** `_snapshot_repo_data_users()` vor und nach dem Test; bei Abweichung
   `pytest.fail` mit Klartext-Hinweis (`conftest.py:283-299`). Fängt zusätzlich Code-Pfade, die
   `<repo>/data/users` direkt ansprechen und an der Umleitung vorbeilaufen (Verursacher-Befund
   #1265 Teil C).

### Warum das ein Bug und keine Absicht ist — Beleg aus dem Projekt selbst

Die Marker-Registrierung in `pyproject.toml:73-79` definiert die beiden Marker **unterschiedlich**:

| Marker | Definition laut `pyproject.toml` |
|---|---|
| `live` | „Tests that hit the real external weather **API** (excluded from default offline fixture mode)" |
| `real_data_root` | „Tests that deliberately read/write the real `data/users/` **tree** (opt out of the #1133 data-root isolation fixture)" |

`live` bedeutet also **Netz-Egress erlaubt**, `real_data_root` bedeutet **echter Dateibaum nötig**.
Der Early-Return wirft beides in einen Topf. Dieselbe Trennung steht im Nachbar-Docstring der
`_egress_guard`-Fixture (`conftest.py:318-330`), die `live` ausdrücklich als „Schichten, in denen
echte **externe Aufrufe** gewollt sind" beschreibt.

Fix-Richtung daraus: Early-Return **nur** bei `real_data_root`. `live` ohne `real_data_root` bekommt
Umleitung *und* Wächter.

### Der Schaden ist real und wächst weiter

Ist-Bestand im echten Baum des Hauptcheckouts (`/home/hem/gregor_zwanzig/data/users/`), gemessen
2026-09-11:

| Verzeichnis | Bewertung |
|---|---|
| `default` | legitim (Referenz-Fixture, aus `tests/fixtures/data_root/` materialisiert) |
| `validator-issue110` | legitim (dito) |
| `tdd-2050-s4b2-p1-lauf-*` (7×) | **verirrte Testnutzer** |
| `tdd-2050-s4b2-p2-mit_luecke-*` (7×) | **verirrte Testnutzer** |
| `tg-live-e2e` | **verirrter Testnutzer** |

Das Issue nennt 7 — es sind inzwischen **15**. Der Befund läuft also noch.

Verursacher der `tdd-2050-s4b2-*`-Nutzer sind mindestens fünf Testdateien aus dem #2050-Umfeld
(`test_alarm_messluecke_ausdehnung_wortebene.py`, `test_alarm_gewitterpruefung_ungeprueft_wortebene.py`,
`test_compare_official_alert_event_identity.py`, `test_alert_state_briefing_reset.py`,
`test_compare_radar_alert_event_identity.py`) — kein Einzelfall aus einer Datei.

### Nebenbefund: der bestehende Wächter zu `tg-live-e2e` misst über einen Stellvertreter

Zu genau diesem Nutzer existiert bereits ein Isolations-Ticket (#1013) mit einem Test, der das
verbietet — `tests/tdd/test_issue_1013_telegram_test_isolation.py:46`:

```python
assert not (tmp_path / "data" / "users" / "tg-live-e2e").exists()
```

Geprüft wird unter `tmp_path`, also unter der Wegwerf-Wurzel, wo ohnehin nichts entsteht. Im
**echten** Baum liegt das Verzeichnis trotzdem. Grüner Test, ungeschützte Zusicherung — dasselbe
Muster, das dieses Ticket insgesamt behandelt. Gehört als Fundstelle in die Spec, weil ein Fix, der
diesen Test unangetastet lässt, die Lücke nur verschiebt.

### ZWEITER, UNABHÄNGIGER DEFEKT: höher gescopte Fixtures entkommen der Isolation UND dem Wächter

Gefunden beim Gegenprüfen des Ist-Schadens — die 14 `tdd-2050-s4b2-*`-Nutzer stammen **nicht** von
`live`-Tests. Die beiden Verursacher tragen **keinen** Marker (weder `live` noch `real_data_root`):

- `tests/tdd/test_alarm_gewitterpruefung_ungeprueft_wortebene.py` → Präfix `tdd-2050-s4b2-p1-lauf-*`
  (`_uid()` Z. 102), schreibt aus der **modul-weiten** Fixture `laeufe` (Z. 145-158)
- `tests/tdd/test_alarm_messluecke_ausdehnung_wortebene.py` → Präfix `tdd-2050-s4b2-p2-mit_luecke-*`
  (Z. 101), ebenfalls modul-weite Fixture (Z. 208-230)

Beide schreiben **korrekt** über `get_data_dir(uid)` (also über `app.loader`, nicht über einen
hartkodierten Pfad) — siehe `tests/tdd/test_alarm_pruefstrecke_selbstschutz.py:85-93`
(`_write_premium_profile`) und `tests/tdd/test_952_onset_alert_fidelity.py:189-193` (`_clean_user`).
Sie tun also alles richtig und landen trotzdem im echten Baum.

**Mechanik:** pytest instanziiert Fixtures nach Scope-Rang — session > package > module > class >
function. Eine modul-weite Fixture wird daher **vor** der funktionsweiten autouse-Fixture
`_isolate_data_root` aufgebaut. Zum Zeitpunkt des Schreibens ist `loader._DATA_ROOT` noch der echte
Baum. Folge, doppelt:

1. **Umleitung wirkungslos** — der Schreibvorgang passiert vor dem Patch.
2. **Wächter blind** — `before_snapshot` wird ebenfalls erst danach genommen
   (`conftest.py:283`), also *nach* der Wirkung. `before == after` ⇒ kein `pytest.fail`.
   Muster: „Wächter läuft ERST NACH der Wirkung".

Warum es trotzdem meist unsichtbar bleibt: beide Fixtures räumen im Teardown per `_clean_user(uid)`
auf. Bricht ein Lauf vorher ab (Interrupt, Fehler in einem anderen Test, `TaskStop`), bleibt der
Nutzer liegen — genau das Bild der Fundstücke, verteilt über den 6. und 7. September.

#### Gemessen, nicht hergeleitet (2026-09-11)

Voraussetzungen geprüft: `get_data_dir` löst über `get_data_root()` (`src/app/loader.py:1139`) per
`getattr(_sys.modules[__name__], "_DATA_ROOT", None)` auf — also **zur Aufrufzeit**, nicht zur
Importzeit; `from … import _DATA_ROOT`-Kopien existieren nirgends (`src/`, `api/`, `tests/`,
`internal/` durchsucht, kein Treffer). Die Alternativerklärung „Import-Zeit-Bindung" ist damit
ausgeschlossen; es bleibt die Fixture-Reihenfolge.

Messung im Worktree `intake-2220`:

| Schritt | Beobachtung |
|---|---|
| vorher | `data/users/` enthält nur `default`, `validator-issue110` |
| `uv run pytest tests/tdd/test_alarm_gewitterpruefung_ungeprueft_wortebene.py -q` | **10 passed**, grün |
| nachher, Inhalt | unverändert `default`, `validator-issue110` (Teardown hat aufgeräumt) |
| nachher, **mtime von `data/users`** | **auf die Laufzeit gesetzt** (06:30:15), während `default`/`validator-issue110` unverändert auf dem 09.09. stehen |

Die geänderte mtime des Elternverzeichnisses beweist, dass unter dem **echten** `data/users`
Verzeichnisse angelegt und wieder entfernt wurden. Der Lauf war dabei grün — der Snapshot-Wächter
hat nichts gemeldet.

Warum der Wächter auch nicht melden kann, in der Reihenfolge:

1. Modul-Fixture legt die Nutzer im echten Baum an (vor jeder funktionsweiten Fixture).
2. Erster Test: `_isolate_data_root` nimmt `before_snapshot` — die Nutzer sind **schon drin**.
3. Letzter Test: `after_snapshot` — die Nutzer sind **noch drin** (das Modul-Teardown läuft erst
   nach dem Funktions-Teardown). `before == after` ⇒ kein `pytest.fail`.
4. Danach räumt das Modul-Teardown auf.

Der Wächter sieht das Fenster, in dem geschrieben wurde, strukturell nie.

**Tragweite:** Dieser Defekt ist **markerunabhängig** und betrifft jeden Test, der aus einer
module-/class-/session-weiten Fixture Daten schreibt — also potenziell viel mehr Tests als C4-17.
Er erklärt 14 der 15 Fundstücke; C4-17 (`live`) erklärt das fünfzehnte (`tg-live-e2e`).

Konsequenz für die Spec: Ein Fix, der nur den `live`-Early-Return korrigiert, schließt die Lücke
**nicht** — er beseitigt 1 von 15 beobachteten Fällen. Beide Defekte müssen zusammen adressiert
werden, sonst läuft der Baum weiter voll und das Ticket gilt fälschlich als erledigt.

### Kollateral-Risiko: die Leser-Seite

Nach dem Fix bekommen `live`-Tests eine **leere** tmp-Wurzel. Tests, die dort vorhandene
Echtbaum-Daten nur **lesen** (`load_trip`, `load_all_trips`, `get_briefings_dir`, …), scheitern dann
mit „Trip … nicht gefunden" / 404 — genau der Effekt, den der `_isolate_data_root`-Docstring für
`real_data_root` schon dokumentiert (`conftest.py:154-160`). Diese Tests brauchen `real_data_root`
zusätzlich zum `live`-Marker.

Eine Enumeration nach Schreibern (`save_*`) findet diese Tests **nicht**.

**Ergebnis der Enumeration (2026-09-11): die Kategorie-A-Liste ist LEER.** Das erwartete
Kollateralrisiko existiert nicht.

- **75** Dateien tragen `live` — bestätigt über zwei unabhängige Wege (`pytest --collect-only -m live -q`
  und ein Skript über die Rohdatei-Inhalte, beide 75). Davon **38** modulweit, **37** funktionsweise.
- **Kein** einziger dieser Tests braucht zusätzlich `real_data_root`. Die große Mehrheit berührt den
  Datenbaum gar nicht (Provider-/Netz-Dialer: DWD, Geosphere, Météo-France, Meteoalarm, Radar,
  Snowgrid, UV, Open-Meteo, Warn-Services). Die restlichen bringen ihre Daten selbst mit
  (synthetische UUID-Nutzer, eigene `save_*`-Aufrufe vor dem Lesen, Cleanup danach) — u.a.
  `test_914_slice4_alert_sms_dispatch.py` (`_clean_user_dir` autouse),
  `test_compare_alert_channel_delivery.py`, `test_dispatch_orchestrator.py`,
  `test_e2e_story3_reports.py`.
- **Ein** Grenzfall, der sich beim Hinsehen auflöst:
  `tests/tdd/test_issue_1004_startzeit_ssot.py` liest hartkodiert
  `data/users/henning/trips/74de939c.json` (Z. 50), aber über eine eigene
  `_reference_trip_path()` (Z. 53-59), die `_DATA_ROOT` nie konsultiert — der Fix erreicht sie also
  weder vorher noch nachher. Zudem fehlt die Referenzdatei laut Datei-Doku (Z. 90-95, Bezug #1633)
  inzwischen auch im Hauptrepo; der Test scheitert schon heute unabhängig davon.
- `test_issue_686_telegram_functional_live.py` zeigt die saubere Bauform bereits: modulweit `live`,
  und genau die 2 von 6 Funktionen, die wirklich `data/users/{TEST_USER_ID}` lesen, tragen
  zusätzlich `real_data_root`.
- `real_data_root` ist heute in ~22 Dateien im Einsatz — das Muster ist etabliert, nicht neu.

**Folge:** Der Marker-Nachzug, den ich als Hauptrisiko erwartet hatte, entfällt. Der Fix an
Defekt 1 ist kollateralarm. Das Gewicht des Tickets liegt bei Defekt 3.

### Nachweisform — der Punkt, an dem es sonst unbewacht bleibt

Ein Test, der den Bug naiv reproduziert, müsste selbst `live` tragen — und liefe damit **nicht im
deterministischen Kern**, also nicht in der Commit-Ampel. Die Zusicherung wäre gebaut, aber
unbewacht.

Tragfähige Form (Hausmuster vorhanden): ein Kern-Test startet per Subprozess einen **inneren
pytest-Lauf** über eine synthetisch erzeugte, `live`-markierte Sondendatei, die `save_trip` aufruft,
und behauptet, dass unter dem echten `<repo>/data/users` nichts entstanden ist bzw. dass der innere
Lauf am Snapshot-Wächter gescheitert ist. Deterministisch, kein Netz, läuft im Kern.

Vorbilder im Bestand:
- `tests/tdd/test_pytest_collection_and_timeout_safety.py:630-643` — Sondendatei erzeugen,
  `[sys.executable, "-m", "pytest", "-c", str(_PYPROJECT), str(datei), "-q"]` aus `_REPO_ROOT`,
  Assertion auf `returncode`.
- `tests/tdd/test_worktree_path_resolution_effect.py:94` — innerer Lauf über eine `nodeid`.
- `tests/tdd/test_issue_1014_live_optin.py:129` — innerer Lauf über live-markierte Dateien.

**Falle, die den Nachweis sonst leer laufen lässt:** pytest sammelt `conftest.py`-Dateien nur
entlang des Pfads zur Testdatei. Liegt die Sonde unter `tmp_path` (außerhalb des Repos), wird
`tests/conftest.py` **gar nicht geladen** — die Fixture, die geprüft werden soll, läuft dann nie.
Die Sonde muss innerhalb von `tests/` liegen und danach aufgeräumt werden.

**Positivkontrolle mitnehmen:** derselbe innere Lauf **mit** `real_data_root` muss durchgehen —
sonst prüft der Test nur, dass irgendetwas fehlschlägt.

## Befund B1-56: zwei Variablennamen für denselben Testnutzer

### Fundstellen

- `frontend/e2e/global.setup.ts:36-37` → `process.env.E2E_USER ?? 'admin'` / `E2E_PASS ?? 'test1234'`
- `frontend/e2e/helpers.ts:100-101` → `process.env.GZ_E2E_USER ?? 'admin'` / `GZ_E2E_PASS ?? 'test1234'`

### Drei Rollen — nur eine ist betroffen

| Rolle | Variablenkette | authentifiziert | Fundstellen |
|---|---|---|---|
| **A** | `GZ_VALIDATOR_USER`/`PASS` | nginx-Basic-Auth **vor** Staging (`httpCredentials`) | ~130 |
| **B** | `GZ_AUTH_USER`/`PASS` | App-Login gegen echtes Staging, eigenes Konto | ~70 |
| **C** | `E2E_USER` **bzw.** `GZ_E2E_USER` | Formular-Login gegen lokalen/CI-Stack | die 2 Befundstellen |

Die beiden Befundstellen sind **dieselbe Rolle C**: gleiches Formular
(`input[name="username"]`/`password`), identischer Default `'admin'`/`'test1234'`, kein Staging-,
kein nginx-Bezug. Deshalb blieb der Doppelname bisher folgenlos.

**Harte Scope-Grenze:** Rollen A und B dürfen NICHT mit eingeschmolzen werden. Sie sind strukturell
getrennte Zugangsdaten (nginx-Schranke vs. App-Login gegen Staging; belegt in
`.claude/hooks/e2e_frontend_browser_gate.py:39-44` — Prod-`.env` → 401, Staging-`.env` → 200). Ein
gemeinsamer Resolver über A/B hinweg würde Staging-Verhalten verändern. Das ist nicht der Befund,
sondern ein Aufräum-Impuls, der eine Regression erzeugt. Vorsicht speziell bei den älteren Configs,
die `E2E_USER` als *Fallback für Rolle A* mitbenutzen.

### `E2E_USER` ist der de-facto gültige Name

- CI setzt **keine** der Variablen direkt.
- `frontend/e2e/ci-stack.sh:12-16,66` seedet den Testnutzer serverseitig
  (`GZ_USER_ID=admin GZ_AUTH_PASS=test1234`) und erklärt im Kommentar ausdrücklich:
  „global.setup.ts meldet sich als `E2E_USER ?? 'admin'` an". `GZ_E2E_USER` wird dort **nie**
  referenziert — es trifft nur zufällig denselben Default.
- Kommentar-Rezepte in ca. 6 Spec-Dateien nutzen die bare Form (`bug-626-compare-menu-actions.spec.ts:19`
  u.a.); **genau eine** Stelle nutzt `GZ_E2E_USER` (`issue-1071-tier-change-request.spec.ts:16`).
- `helpers.ts:login()` wird aus **60** Spec-Dateien importiert — die hängen alle am abweichenden Namen.

### Entscheidung zum `'admin'`-Default: kein fail-closed

Als Tech-Lead-Entscheidung festgehalten, nicht als offene Frage:

- Der CI-e2e-Job verlässt sich **bewusst** auf diesen Default — `ci-stack.sh` setzt die Variable
  absichtlich nicht, sondern seedet dasselbe Konto serverseitig. Fail-closed bräche ihn ohne
  Begleitänderung.
- Der wirksame Schutz gegen echte Konten ist nicht der Kontoname, sondern der **Ziel**-Guard
  `frontend/e2e/prodUrlGuard.ts` (`assertNotProdBaseURL`, `assertNotProdApiProxyTarget`), der in
  `global.setup.ts:25,27,34` **vor** jeder Datenanlage hart abbricht. Ein fail-closed Credential
  würde daneben nichts zusätzlich verhindern.
- Also: eine Auflösung an einer Stelle, `GZ_E2E_USER`/`GZ_E2E_PASS` als anerkanntes Alias in der
  Kette, damit kein bestehender Aufruf bricht.

## Related Files

| Datei | Relevanz |
|---|---|
| `tests/conftest.py:250-300` | `_isolate_data_root` — Early-Return, Umleitung, Snapshot-Wächter |
| `tests/conftest.py:179-240` | `_materialize_real_data_root_fixtures` — legt die legitimen Referenz-Fixtures im echten Baum an |
| `pyproject.toml:73-79` | Marker-Registrierung — die Definitionen, die den Befund belegen |
| `tests/tdd/test_issue_1013_telegram_test_isolation.py:46` | bestehender Stellvertreter-Wächter zu `tg-live-e2e` |
| `frontend/e2e/global.setup.ts:36-37` | Rolle C, `E2E_USER` |
| `frontend/e2e/helpers.ts:100-101` | Rolle C, `GZ_E2E_USER` — 60 importierende Spec-Dateien |
| `frontend/e2e/ci-stack.sh:12-16,66` | belegt, welcher Name gilt, und die Default-Abhängigkeit des CI |
| `frontend/e2e/prodUrlGuard.ts` | vorhandener Ziel-Guard — der wirksame Schutz |

## Existing Patterns

- **Innerer pytest-Lauf als Nachweis** (s.o.) — `test_pytest_collection_and_timeout_safety.py`,
  `test_worktree_path_resolution_effect.py`, `test_issue_1014_live_optin.py`.
- **Fail-closed Konfigurationslesung** — `.claude/hooks/e2e_frontend_browser_gate.py:36-38,229-232`
  (`REQUIRED_CREDENTIALS`, bricht statt Default). Python-seitig; ein TS-Pendant für Credentials
  existiert nicht.
- **Ziel-Guard statt Namens-Guard** — `frontend/e2e/prodUrlGuard.ts`, nach mehreren
  Umgehungs-Findings (F004/F011/F012/F013) auf DNS-Auflösung + Loopback-Check gehärtet.

## Existing Specs

- `docs/specs/modules/fix_1329_e2e_data_hygiene.md` — selbsträumende Playwright-Suites, reservierter
  Präfix; betrifft Staging-Wegwerfdaten, nicht die Python-Datenwurzel. Angrenzend, nicht überlappend.
- `docs/specs/modules/egress_guard.md` — definiert `live` als Netz-Schicht; stützt die
  Marker-Trennung.
- Keine Spec zur Isolations-Fixture selbst (#1133/#1265 haben keine) — die Mechanik lebt nur im
  Docstring.

## Risks & Considerations

1. ~~**Kollateral bei `live`-Lesern**~~ — **erledigt, Risiko existiert nicht.** Kategorie-A-Liste
   leer (s.o.). Neues Hauptrisiko ist stattdessen die **Fixture-Reihenfolge**: ein falscher Fix an
   Defekt 3 bricht nicht einen Test, sondern den gesamten Testlauf.
2. **`tests/conftest.py` ist stark geteilt** und es laufen parallele Sessions. Fremder Datei-Claim
   möglich → Eigentümer über `workflow.py sessions` + `ListAgents` ermitteln, per `SendMessage`
   klären, **nie** selbst `--release`n.
3. **Kein `data_schema_backup.py`-Halt** — der Pre-Snapshot-Hook hängt an
   `models.py`/`trip.py`/`loader.py`/`internal/model`/`store.go`, nicht an `conftest.py`.
4. **Aufräumen des Ist-Bestands** (die 15 verirrten Nutzer) ist eine eigene Frage: Der echte Baum
   ist gitignored Laufzeitdaten; ein Löschlauf gehört nur nach expliziter Abgrenzung in den Scope,
   damit nicht versehentlich `default`/`validator-issue110` getroffen werden.
5. **Marker-Semantik nicht nur im Docstring festhalten** — sonst erodiert dieselbe Vermischung
   erneut. Die Registrierung in `pyproject.toml` ist der Ort, an dem die Trennung schon korrekt
   steht.

## Fix-Richtung (Vorschlag für die Spec, nicht freigegeben)

Defekt 3 lässt sich **nicht** als weiterer Patch an der funktionsweiten Fixture lösen — eine
funktionsweite Fixture kann Schreibvorgänge, die vor ihr passieren, prinzipiell nicht schützen.
Nötig ist eine Umkehrung der Vorzeichen:

- Eine **session-weite** autouse-Fixture setzt `_DATA_ROOT` auf eine Session-tmp-Wurzel, **bevor**
  irgendeine module-/class-weite Fixture laufen kann. Der echte Baum ist damit während eines
  Testlaufs per Default unerreichbar.
- Die funktionsweite Fixture verengt pro Test und stellt für `real_data_root`-markierte Tests die
  echte Wurzel wieder her. Aus „per Default echt, Opt-out per Marker" wird „per Default isoliert,
  Opt-in per Marker" — die fail-closed-Richtung, die im Haus ohnehin Muster ist.
- Der Snapshot-Wächter braucht eine **session-weite** Entsprechung, sonst bleibt genau das Fenster
  offen, in dem hier geschrieben wurde.

Zwei Implementierungsfallen:

1. `_materialize_real_data_root_fixtures` (`conftest.py:179`) ist selbst session-weit autouse und
   **muss** gegen den echten Baum kopieren. **Entschärft:** Die Fixture schreibt über einen
   hartkodierten `root/"data"/"users"`-Pfad, **nicht** über `loader._DATA_ROOT` — sie ist vom
   Redirect also unabhängig. Zu pinnen bleibt nur, dass `real_data_root`-Tests die echte Wurzel
   *nach* der Materialisierung sehen.

**Kollateral-Prüfung für Defekt 3 nachgeholt (2026-09-11):** Die erste Enumeration lief über die
`live`-Marker und deckte damit nur Defekt 1 ab — Defekt 3 ist markerunabhängig. Gesondert geprüft:
**46 höher gescopte Fixtures in 28 Dateien** (40× `module`, 3× `session`, 3× `class`, 0× `package`).
**Kategorie-A-Liste ebenfalls leer.** Der größte Teil läuft gegen separate Prozesse (Playwright,
httpx, Staging), wo der Redirect ohnehin nicht wirkt; der Rest fasst den Baum nicht an oder schreibt
vor dem Lesen. Die einzigen `app.loader`-Berührungen sind die zwei bekannten Verursacher — beide
Kategorie B, also durch den Fix korrekt umgeleitet. Methode an ihnen kalibriert, alle 46 statisch
entschieden, keine offenen Unsicherheiten.
2. Defekt 1 und Defekt 3 laufen über verschiedene Mechanismen und brauchen **zwei** Sonden:
   - Sonde A: synthetisches Modul **mit** `live`-Marker, `save_trip` — deckt Defekt 1.
   - Sonde B: synthetisches Modul **ohne** Marker, mit `scope="module"`-Fixture, die über
     `get_data_dir` schreibt — deckt Defekt 3.
   Beide innerhalb `tests/` ablegen (conftest-Ladepfad, s.o.), je mit Positivkontrolle.

`tests/tdd/test_issue_1013_telegram_test_isolation.py:46` (Stellvertreter-Wächter) gehört **in**
dieses Ticket — ein Fix, der ihn unangetastet lässt, verschiebt die Lücke nur.

## Nebenbefunde → Sammel-Issues, nicht dieses Ticket

- Die `os.walk`-Zählung in `_snapshot_repo_data_users` sieht neu angelegte **leere** Verzeichnisse
  nicht (Fingerprint aus Dateizahl/mtime/Größe). Eigene Schwäche des Wächters → #1196/#1199.
- `tests/tdd/test_issue_338_go_geosphere_counter.py` spawnt `uv run pytest` als Subprozess, der die
  Isolation nicht erbt. Nur statisch geprüft, Restrisiko in Schreibrichtung → Sammeleintrag.

## Ist-Bestand aufgeräumt (2026-09-11)

Die 15 verirrten Nutzer im Hauptcheckout wurden auf PO-Anweisung entfernt (explizite Namensliste,
Sicherung als `verirrte-testnutzer-2226.tar.gz`, 63 Einträge; `default`/`validator-issue110`
gegengeprüft unverändert bei 22 Dateien). In der Arbeitskopie `issue-2200` liegt noch ein
`tg-live-e2e` — fremder Worktree, nicht angetastet.

Das beseitigt die Folgen, nicht die Ursache: ohne Fix läuft der Baum beim nächsten Lauf wieder voll.
