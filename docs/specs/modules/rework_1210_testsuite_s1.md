---
entity_id: rework_1210_testsuite_s1
type: module
created: 2026-07-17
updated: 2026-07-17
status: draft
version: "1.0"
tags: [testing, pytest, infrastructure, live-leak-guard]
---

<!-- Issue #1210 — Sammelprojekt #1196 (Test-Aufräum-Programm), Scheibe 1 von 2 (Scheibe 2: #1211) -->

# Testsuite Scheibe 1 — Suite terminiert zuverlässig, Live-Lecks geschlossen (Issue #1210)

## Approval

- [ ] Approved

## Purpose

Die pytest-Suite so absichern, dass sie im Standardlauf (`uv run pytest`, ohne
explizite Marker-Optionen) **immer terminiert** — auch wenn ein Test unerwartet
hängt — und **keine echten Netz-/Mail-Seiteneffekte** auslöst. Diese Scheibe
macht die in CLAUDE.md festgelegte Zwei-Schichten-Politik (Kern deterministisch
vs. Live-E2E hinter Marken) mechanisch wirksam, statt sie nur als Konvention zu
dokumentieren. Ziel ist **nicht** "alle Tests grün" (das ist Scheibe 2, #1211),
sondern: die Suite läuft im Standardlauf zu Ende, ohne Netz zu berühren, und
sammelt korrekt.

## Source

> Test-Infrastruktur/Tooling — kein Frontend-, Go-API- oder Python-Core-Domain-Code
> betroffen. Ausnahme bewusst NICHT in dieser Scheibe: `src/output/channels/email.py`
> (siehe Known Limitations).

- **File:** `pyproject.toml` — `[dependency-groups].dev` (neue Dev-Dependency
  `pytest-timeout`), `[tool.pytest.ini_options]` (neuer `timeout`-Ini-Default)
- **File:** `uv.lock` — Lockfile-Folgeänderung (generiert, zählt nicht ins
  LoC-Limit)
- **Files (B1 — Live-Leck, Marker + Connect-Timeout):** 11 Dateien unter
  `tests/tdd/` — das Analyse-Dokument (`docs/context/rework-1210-testsuite-s1.md`)
  beziffert die Gruppe als "10 Dateien", die zugehörige Aufzählung listet jedoch
  11 Pfade; diese Spec übernimmt die vollständige Aufzählung (11), nicht die
  Kopfzahl:
  - `tests/tdd/test_issue_1113_partial_outage_guard.py` (komplett ungegatet)
  - `tests/tdd/test_issue_1007_heute_voll_briefing.py` (komplett ungegatet)
  - `tests/tdd/test_issue_1012_no_data_guard.py` (komplett ungegatet; bekannter
    Echt-Versender inkl. Live-MeteoAlarm-Aufruf)
  - `tests/tdd/test_issue_1009_1019_inbound_robustness.py` (Credential-Skip;
    `imaplib.IMAP4_SSL` Z. 145–146, Poll-`while True`/`sleep(8)` Z. 184–202,
    echter SMTP-Versand Z. 170–173 — der bekannte 39-%-Hänger)
  - `tests/tdd/test_773_alert_e2e.py` (Credential-Skip)
  - `tests/tdd/test_952_onset_alert_e2e.py` (Credential-Skip)
  - `tests/tdd/test_issue_684_alert_email_guard.py` (Credential-Skip)
  - `tests/tdd/test_issue_1087_trip_official_alerts.py` (Credential-Skip)
  - `tests/tdd/test_issue_1169_compare_alert_consumer.py` (Credential-Skip)
  - `tests/tdd/test_issue_972_974_975_tooling.py` (autouse-Fixture mit `assert`
    statt `skip` — schärfste Form des Credential-Skip-Fehlmusters)
  - `tests/tdd/test_issue_1147_resend_recipient_invariant.py` (dialt echten
    `smtp.resend.com`)
- **File:** `tests/e2e/test_e2e_friendly_format_config.py` — Footgun: wird trotz
  Docstring-Hinweis "NICHT als pytest" (Z. 1–15) im Standardlauf gesammelt und
  mutiert `data/users/default/trips/*.json` ohne Restore
- **File:** `tests/tdd/test_issue_811_renderer_gate.py` — lädt
  `.claude/hooks/renderer_mail_gate.py` per `importlib.util.spec_from_file_location`
  (Z. 30–43) ohne Existenzprüfung; fehlt der Hook im Ausführungskontext
  (z. B. Plugin unter anderem OS-Nutzer nicht sichtbar), bricht die Collection
  mit Fehler statt Skip ab
- **Files:** `tests/test_geosphere.py`, `tests/test_providers_base.py` —
  modul-weiter `pytest.mark.live`, obwohl alle Tests nachweislich offline laufen
  (HTTP gemockt bzw. kein HTTP)
- **File (NEU):** `tests/tdd/test_pytest_collection_and_timeout_safety.py` —
  Meta-Test-Modul, das die o. g. Verhaltensweisen per echter
  Collection-/Subprozess-Probe nachweist (siehe Testplan)

## Estimated Scope

- **LoC:** ~60–90 (Granular-Feinschnitt der 21 teilbaren live-Module bleibt
  draußen, sonst Limit gerissen)
- **Files:** ~15–17 (siehe Source)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `pytest-timeout` (PyPI, dev-group) | extern | Sicherheitsnetz gegen unerwartete Hänger; ini-Default statt Vertrauen auf Einzeldatei-Disziplin |
| `pyproject.toml` Marker-Registry (`email`/`live`/`staging`) | intern | Einzige addopts-wirksame Ausschlussmechanik für den Standardlauf |
| CLAUDE.md „Test-Politik: Zwei Schichten" (PO-go 2026-07-09) | Policy | Definiert Kern vs. Live-E2E; diese Scheibe stellt die Trennung mechanisch her |
| Issue #1210 | GitHub Issue | Ursprungs-Issue dieser Scheibe |
| Sammelprojekt #1196 | GitHub Issue | Übergeordnetes Test-Aufräum-Programm |
| Scheibe 2 — Issue #1211 | GitHub Issue | Folge-Scheibe: Rot-Triage der zurückgeholten Tests + Granular-Feinschnitt der 21 teilbaren live-Module |
| Issue #1301-A2 (parallele Session) | GitHub Issue | Entfernt `_select_provider_for_location` — Grund, warum `test_compare_provider_routing.py` in dieser Scheibe unangetastet bleibt |
| Issue #1301 / fix-1296 (parallele Sessions) | GitHub Issue | Fassen `test_model_metric_fallback.py`, `test_provider_merge_contract.py`, Compare-Tests gerade an → hier ausgelassen, um Merge-Konflikte zu vermeiden |

## Implementation Details

```
1. pyproject.toml
   - [dependency-groups].dev: "pytest-timeout>=2.3.0" ergänzen (Reihenfolge:
     alphabetisch neben bestehenden dev-Deps)
   - [tool.pytest.ini_options]: neuer Schlüssel `timeout = <N>` (Sekunden) als
     globales Sicherheitsnetz für ALLE Tests im Standardlauf. N so wählen,
     dass legitime deterministische Tests (Fixtures, kein Netz) sicher
     darunter bleiben, aber ein hängender Connect zuverlässig gekillt wird.
   - uv.lock: Folgeänderung von `uv lock` (generiert)

2. B1 — 11 Dateien (siehe Source):
   - Modul- oder klassenweiter `pytestmark = pytest.mark.email` (oder
     funktionsweise dort, wo eine Datei gemischte netzfreie/netzbehaftete
     Tests enthält) — macht die Live-Leck-Dateien addopts-wirksam ausschließbar.
   - Bestehende Credential-Skips/`can_send_email()`-Checks BLEIBEN als
     Defense-in-Depth (nicht entfernen) — der Marker ist die neue primäre
     Ausschlussmechanik, der Skip fängt den Rest-Fall "Marker versehentlich
     aufgehoben, Creds fehlen trotzdem" ab.
   - An jedem `imaplib.IMAP4_SSL(...)`- und `smtplib.SMTP(...)`-Aufruf
     innerhalb dieser Testdateien einen `timeout=`-Parameter ergänzen (Sekunden,
     deutlich unter dem globalen pytest-timeout-Default), damit der
     TCP/TLS-Connect selbst nicht unbegrenzt blockieren kann — insbesondere
     `_imap()` (Z. 145–146) und `_deliver_mail()` (Z. 170) in
     `test_issue_1009_1019_inbound_robustness.py`, wo der bestehende
     Deadline-Check (Z. 184–202) NACH dem Connect liegt und ihn daher nicht
     schützt.

3. tests/e2e/test_e2e_friendly_format_config.py:
   - Aus der Standard-Collection nehmen. Empfohlener Weg: modul-weiter
     `pytestmark = pytest.mark.email` (konsistent mit B1, kein Dateiname-Bruch
     der im Docstring dokumentierten manuellen Ausführung
     `uv run python tests/e2e/test_e2e_friendly_format_config.py`).
     Alternative (falls im Adversary-Dialog bevorzugt): Umbenennung außerhalb
     des `test_*.py`-Collection-Musters — dann muss die
     Ausführungsanleitung im Docstring entsprechend nachgeführt werden.

4. tests/tdd/test_issue_811_renderer_gate.py:
   - `importorskip`-Guard vor `_load_gate_module()`-Aufruf (Z. 43):
     Existenzprüfung von `_GATE_SRC`, bei Fehlen `pytest.skip(reason=...,
     allow_module_level=True)` statt ImportError/FileNotFoundError während
     der Collection.

5. tests/test_geosphere.py, tests/test_providers_base.py:
   - Modul-weiten `pytest.mark.live`-Marker entfernen — NUR nachdem beide
     Dateien gezielt einzeln (`uv run pytest tests/test_geosphere.py
     tests/test_providers_base.py -v`, mit `timeout=`) grün verifiziert
     wurden (Einzel-Grün-Probe, kein Blindvertrauen auf die Analyse).
```

## Expected Behavior

- **Input:** `uv run pytest` (Standardlauf, keine expliziten Marker-Optionen)
  bzw. `uv run pytest -m email` / `-m live` / `-m staging` (expliziter Lauf)
- **Output:**
  - Standardlauf terminiert immer mit einem Exit-Code (0 oder Testfehler),
    nie unbegrenztem Hängen; kein Test aus den 11 B1-Dateien und keiner aus
    `test_e2e_friendly_format_config.py` wird gesammelt/ausgeführt
  - `tests/test_geosphere.py` und `tests/test_providers_base.py` werden im
    Standardlauf wieder ausgeführt (grün)
  - `-m email` sammelt weiterhin die 11 B1-Dateien (Marker verschiebt, löscht
    nicht)
- **Side effects:** Keine Mutation von `data/users/default/trips/*.json` mehr
  durch einen versehentlichen pytest-Sammellauf; kein echter SMTP-/IMAP-Connect
  mehr im Standardlauf

## Acceptance Criteria

- **AC-1:** Given ein Test in der Standard-Suite hängt unerwartet (z. B. weil ein Netzdienst nicht antwortet) / When der Standardlauf `uv run pytest` ausgeführt wird / Then bricht der betroffene Test spätestens nach einer festen, kurzen Zeitschranke automatisch mit einem sichtbaren Fehlschlag ab, statt den gesamten Lauf unbegrenzt zu blockieren.
  - Test: Meta-Test erzeugt einen synthetischen, garantiert hängenden Testfall (z. B. `time.sleep()` weit über der Zeitschranke) in einer isolierten Scratch-Umgebung und misst, dass der Subprozesslauf innerhalb einer klar bemessenen oberen Wallclock-Schranke terminiert — kein Warten auf die echte Suite nötig.

- **AC-2:** Given die 11 identifizierten Testdateien mit echtem SMTP-/IMAP-Zugriff / When der Standardlauf ohne explizite Marker-Optionen ausgeführt wird / Then wird kein **real sendender/pollender** Test aus diesen Dateien gesammelt oder ausgeführt — die tatsächlich Netz berührenden Testfälle erscheinen ausschließlich unter `-m email`. Enthält eine Datei laut eigenem Docstring auch rein netzfreie Guard-/Struktur-Tests (nachweislich #1147: Cross-User-Mail-Leck-Schutz; #684: unkonfiguriertes SMTP + lokaler 127.0.0.1-Socket), so bleiben genau diese im Standardlauf erhalten — der Marker wird dann **funktions-/klassenweise** statt datei-weit gesetzt (Implementation Details Schritt 2). (Präzisiert nach Adversary-Befund F001/F002, PO-Freigabe 2026-07-17.)
  - Test: Echte `pytest --collect-only`-Subprozessläufe (Standardselektion vs. `-m email`) je Datei vergleichen die Zahl gesammelter Tests: für die 9 voll-markierten Dateien Standard=0 und `-m email`>0; für die 2 gemischten Dateien Standard>0 (Guard-Tests laufen) **und** `-m email`>Standard (sendende Tests kommen zusätzlich hinzu) — kein Mock, reine Collection-Introspektion.

- **AC-3:** Given `tests/e2e/test_e2e_friendly_format_config.py`, im Docstring als "NICHT als pytest auszuführen" markiert / When der Standardlauf pytest sammelt / Then liefert diese Datei keinen ausführbaren Test in der Standardselektion, insbesondere mutiert kein Sammellauf mehr `data/users/default/trips/*.json`.
  - Test: `pytest --collect-only -q` (Standardselektion) enthält keine Test-ID aus dieser Datei; ergänzend Dateimodifikationszeit von `data/users/default/trips/*.json` vor/nach einem Collection-Lauf unverändert.

- **AC-4:** Given die Gate-Hook-Infrastruktur (`.claude/hooks/renderer_mail_gate.py`) ist im aktuellen Ausführungskontext nicht auffindbar (z. B. Plugin unter einem anderen Betriebssystem-Nutzer unsichtbar) / When `tests/tdd/test_issue_811_renderer_gate.py` gesammelt wird / Then bricht die Collection nicht mit einem Fehler ab, sondern die betroffenen Tests werden mit erkennbarem Grund übersprungen (skip).
  - Test: Subprozess-Collection-Probe in einer temporären Repo-Kopie, in der der Hook-Pfad absichtlich fehlt — Exit-Code der Collection bleibt 0/skip statt Error; Vergleichsprobe mit vorhandenem Hook zeigt reguläre Collection.

- **AC-5:** Given `tests/test_geosphere.py` und `tests/test_providers_base.py`, deren Tests nachweislich ohne echten Netzzugriff auskommen / When der Standardlauf ausgeführt wird / Then werden alle ihre Tests ausgeführt (nicht mehr pauschal als `live` übersprungen) und laufen grün durch.
  - Test: `uv run pytest tests/test_geosphere.py tests/test_providers_base.py -v` (mit `timeout=`) zeigt alle Tests als `PASSED`, keiner als `SKIPPED`/`DESELECTED`.

- **AC-6:** Given ein Test versucht, eine IMAP-/SMTP-Verbindung zu einem nicht erreichbaren Mail-Host aufzubauen / When der explizite `-m email`-Lauf diesen Test ausführt / Then bricht der Verbindungsaufbau selbst nach einer festen, kurzen Zeitschranke ab (nicht erst durch den globalen Sicherheitsnetz-Timeout nach der vollen Testdauer), sodass der Fehlschlag schnell und mit einer aussagekräftigen Verbindungsfehlermeldung sichtbar wird.
  - Test: Gezielter Verbindungsversuch gegen eine nicht routbare Adresse (z. B. `10.255.255.1`) mit dem im Code ergänzten `timeout=`-Wert zeigt eine `socket.timeout`/`TimeoutError` deutlich unterhalb des globalen pytest-timeout-Defaults.

- **AC-7:** Given ein Entwickler will bewusst die Live-/E-Mail-Tests laufen lassen (z. B. vor `/e2e-verify`) / When `pytest -m email` explizit aufgerufen wird / Then werden die zuvor markierten Tests weiterhin vollständig gesammelt und ausführbar — die Marker-Vergabe schließt Tests nur aus der Standardselektion aus, löscht sie nicht.
  - Test: `pytest -m email --collect-only -q` liefert alle 11 B1-Dateien (bzw. deren markierte Testfälle) als gesammelte Test-IDs.

- **AC-8:** Given die Marker-Registry in `pyproject.toml` (`tdd`/`email`/`live`/`staging`/`real_data_root`) / When `uv run pytest --collect-only -q` (Standardselektion, gesamte Suite) ausgeführt wird / Then terminiert die Collection weiterhin mit Exit 0 über alle ~577 Testdateien hinweg (keine Regression gegenüber dem heutigen collection-fähigen Stand).
  - Test: Vollständiger `pytest --collect-only -q`-Subprozesslauf über `tests/` mit `timeout=`, Exit-Code-Prüfung 0, keine `ERROR`-Zeilen im Output.

## Known Limitations

- **`src/output/channels/email.py`-Timeout nicht Teil dieser Scheibe:** Der
  Produktivcode für den echten Mail-Versand-Pfad bekommt hier bewusst KEINEN
  Timeout — dieser Code ist an das un-überspringbare Renderer-Mail-Gate #811
  gekoppelt (jede Änderung an Mail-Renderer-/Channel-Dateien erzwingt einen
  frischen Mail-Validator-Lauf). Das gehört in einen eigenen Workflow, nicht
  in eine reine Test-Infrastruktur-Scheibe.
- **Granular-Feinschnitt der 21 teilbaren `live`-Module bleibt draußen:** ~85
  Tests darin sind vermutlich deterministisch (z. B. `test_multi_day_trend.py`
  21/21, `test_forecast_confidence_backend.py` 16/18,
  `test_openmeteo_endpoint_routing.py` 9/11), aber jede Datei enthält auch
  echte netzbehaftete Teile — Datei-für-Datei-Auftrennung mit Rot-Risiko für
  das Commit-Gate aller parallelen Sessions. Dokumentierte Vorarbeit,
  Umsetzung in Scheibe 2 (#1211).
- **Keine Rot-Triage:** Kein zurückgeholter Test wird hier "grün gemacht",
  wenn er tatsächlich fehlschlägt — das ist explizit Scheibe 2 (#1211). Diese
  Scheibe holt `tests/test_geosphere.py`/`tests/test_providers_base.py` nur
  zurück, weil sie vorab gezielt einzeln grün verifiziert wurden.
- **`tests/unit/test_model_metric_fallback.py`, `test_provider_merge_contract.py`,
  Compare-Tests unangetastet:** Parallele Sessions (#1301, fix-1296) fassen
  diese Dateien gerade an; ein Umtaggen hier würde Merge-Konflikte riskieren.
  Nachziehen in Scheibe 2.
- **`test_compare_provider_routing.py` unangetastet:** Issue #1301-A2 entfernt
  gerade `_select_provider_for_location`, das dieser Test prüft — jede
  Marker-Änderung hier wäre sofort hinfällig.
- **`addopts` selbst bleibt unverändert:** Diese Scheibe verschiebt Tests
  zwischen Marker-Kategorien und ergänzt ein Zeit-Sicherheitsnetz, senkt aber
  keine Test-Schwellen und lockert kein Gate.
- **Der ini-`timeout`-Wert ist ein grobes Sicherheitsnetz, kein Ersatz für
  AC-6:** Ein zu hoch gewählter globaler Timeout lässt einen hängenden Connect
  immer noch für die volle Dauer blockieren, bevor er greift — deshalb bleibt
  der gezielte `timeout=`-Parameter an den einzelnen IMAP-/SMTP-Aufrufen
  (AC-6) eine eigenständige, nicht redundante Maßnahme.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine neue nummerierte ADR-Datei in `docs/adr/` — die
  Entscheidungen hier sind lokale Test-Infrastruktur-Konventionen im Sinne der
  ADR-README-Abgrenzung ("Kleine, lokale Implementierungsentscheidungen
  gehören nicht hierher"), nicht produktseitige Architektur. Sie werden hier
  dennoch explizit festgehalten, weil sie präzedenzbildend für alle künftigen
  Testdateien sind:
  - **(a) Sicherheitsnetz `pytest-timeout` ist dev-only mit ini-Default, kein
    Vertrauen auf Einzeldatei-Disziplin.** Bisher hing die Terminierung der
    Suite davon ab, dass jede Testdatei selbst brav ihre Poll-Schleifen
    begrenzt (siehe der bekannte 39-%-Hänger). Die Entscheidung: ein globaler
    ini-Default in `pyproject.toml` ist die Grundabsicherung; einzelne Dateien
    dürfen zusätzlich enger begrenzen, aber die Suite darf sich nie wieder
    allein auf diszipliniertes Testdatei-Verhalten verlassen.
  - **(b) Live-Gating läuft ausschließlich über addopts-wirksame Marker
    (`email`/`live`/`staging`); Credential-Skips sind nur Defense-in-Depth,
    nie die primäre Ausschlussmechanik.** Genau das Fehlen dieser Regel war
    die Ursache von B1: `pytest.skip` bei fehlenden Creds wirkt nur, solange
    die `.env` leer ist — sobald echte Credentials vorhanden sind (wie
    aktuell), sendet der Standardlauf echte Mails. Diese Entscheidung ist
    bewusst hart und rückwirkend auf alle 11 B1-Dateien angewendet, damit sie
    nicht in Scheibe 2 oder von neuen Testdateien wiederholt wird.
  - **(c) Rückholung deterministischer Tests aus einem `live`-Marker nur nach
    Einzel-Grün-Probe, nie nach reiner Code-Inspektion.** `tests/test_geosphere.py`
    und `tests/test_providers_base.py` werden nur entmarkert, nachdem sie
    gezielt isoliert grün gelaufen sind — jede Rot-Triage größerer,
    teilbarer Module (die 21 Kandidaten) bleibt bewusst in Scheibe 2, weil ein
    fälschlich zurückgeholter roter Test das Commit-Gate aller parallelen
    Sessions blockieren würde.

## Testplan

**Grundsatz (Test-Politik Zwei Schichten, CLAUDE.md):** Alle Nachweise dieser
Scheibe laufen im **Kern** (deterministisch, kein Netz) über echte
`pytest`-Subprozess-Collection-Läufe — kein Mock-Theater, kein
Dateiinhalt-Check als Verhaltensnachweis. Ein Subprozess, der nur `pytest
--collect-only` ausführt oder einen synthetischen, garantiert
netzfreien Hänger erzeugt, ist kein Live-Zugriff und gehört in die Kern-Schicht.

Neues Meta-Test-Modul `tests/tdd/test_pytest_collection_and_timeout_safety.py`
(Name nach Verhalten, nicht nach Issue-Nummer — Test-Naming-Gate):

- `test_timeout_ini_default_kills_hanging_test` — legt in einer Scratch-Umgebung
  eine Minimal-`pyproject.toml`/`pytest.ini` mit kurzem `timeout`-Wert und eine
  einzelne Testdatei mit garantiertem `time.sleep()`-Hänger an, ruft
  `subprocess.run(["uv","run","pytest",...], timeout=<Wallclock-Obergrenze>)`
  auf und prüft, dass der Subprozess selbst innerhalb der Obergrenze terminiert
  und der einzelne Test als Fehlschlag (Timeout) markiert ist → Nachweis AC-1.
- `test_default_selection_excludes_b1_live_leak_files` — führt
  `pytest --collect-only -q` (Standardselektion) als Subprozess im Projekt aus
  und prüft, dass keine Test-ID einer der 11 B1-Dateien im Output erscheint →
  Nachweis AC-2.
- `test_email_marker_run_still_collects_b1_files` — führt
  `pytest -m email --collect-only -q` aus und prüft, dass die 11 B1-Dateien
  (bzw. ihre markierten Testfälle) dort erscheinen → Nachweis AC-7 (Marker
  verschiebt, löscht nicht).
- `test_friendly_format_footgun_not_collected_by_default` — prüft, dass
  `tests/e2e/test_e2e_friendly_format_config.py` keine Test-ID in der
  Standardselektion liefert → Nachweis AC-3 (Collection-Teil).
- `test_811_gate_test_skips_when_hook_missing` — baut (analog zum bestehenden
  Muster in `test_issue_811_renderer_gate.py::_setup_repo`) eine temporäre
  Repo-Kopie OHNE `.claude/hooks/renderer_mail_gate.py` auf, sammelt darin und
  prüft Skip statt Error; Gegenprobe mit vorhandenem Hook zeigt reguläre
  Collection → Nachweis AC-4.
- `test_geosphere_and_providers_base_pass_in_default_selection` — führt
  `pytest tests/test_geosphere.py tests/test_providers_base.py -v` aus und
  prüft `16 passed`, `0 skipped`, `0 deselected` → Nachweis AC-5.
- `test_imap_connect_timeout_fails_fast_on_unreachable_host` — verbindet mit
  dem im Code ergänzten `timeout=`-Wert gegen eine nicht routbare Testadresse
  und misst, dass der Fehlschlag deutlich unter dem globalen
  pytest-timeout-Default liegt → Nachweis AC-6.
- `test_full_suite_collection_still_exits_zero` — voller
  `pytest --collect-only -q`-Lauf über `tests/`, Exit-Code 0, keine
  `ERROR`-Zeilen → Nachweis AC-8 (keine Regression ggü. heutigem Stand).

Alle Subprozessaufrufe selbst nutzen `subprocess.run(..., timeout=<N>)`, damit
ein Meta-Test-Fehlschlag (statt eines echten Hängers) nicht seinerseits die
CI/den Testlauf blockiert.

## Changelog

- 2026-07-17: Initial spec erstellt — Issue #1210, Sammelprojekt #1196,
  Scheibe 1 von 2 (Scheibe 2: #1211)
