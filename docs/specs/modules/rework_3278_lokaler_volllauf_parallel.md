---
entity_id: rework_3278_lokaler_volllauf_parallel
type: module
created: 2026-11-24
updated: 2026-11-24
status: draft
version: "1.1"
workflow: rework-3278-lokaler-volllauf-parallel
tags: [testsuite, gate, xdist, performance, sicherheit, epic-1196]
---

# Lokaler sicherer Offline-Volllauf als parallele Gate-Form

## Approval

- [ ] Approved

## Purpose

Das Gate `broad_test_run_gate.py` gibt heute nur den seriellen sicheren Offline-Volllauf frei (ca. 56 min auf dem Server). Diese Spec fügt genau eine zweite, wörtlich festgelegte parallele Form hinzu (`-n 2 --dist loadgroup`, alle Sicherheits-Flags Pflicht, `nice -n 10` als fester Bestandteil), damit der lokale Volllauf kürzer wird, ohne dass echter Versand an Nutzer (Vorfall #1477) möglich wird. Issue #3278, Teil von #1196, Folge von #3209.

## Source

- **File:** `.claude/hooks/broad_test_run_gate.py`
- **Identifier:** `_OFFLINE_BASE_CALL`, `OFFLINE_CALL`, `_OFFLINE_CALLS`, `_offline_form_is_safe`, `_block`

> **Schicht-Hinweis:** Reine Werkzeug- und Test-Infrastruktur (Hook, `tests/`, Doku, Kommentare). Keine Änderung in Frontend, Go-API oder Python-Produktcode. Keine Nutzerdaten-Bewegung, Mandantentrennung und Kanäle sind nicht berührt, ein Trip/Ortsvergleich-Pendant gibt es nicht (Querschnitts-Prüfpunkte entfallen).

## Estimated Scope

- **LoC:** ca. +350/-20 (Tests allein +329/-10). Die Grenze ±250 ist überschritten; der PO hat sie am 2026-11-24 für #3278 auf 500 angehoben.
- **Files:** 5 im Kern, dazu 3 mit nur Kommentar- oder Vermerkzeilen. Die Grenze von 4-5 Dateien ist überschritten, weil sonst Doku und Kommentare dem Gate widersprechen würden (`ci.yml`, `tests/conftest.py`, Vermerk in `perf_3209`).
- **Effort:** medium (Risiko MEDIUM: Sicherheits-Gate gegen Produktiv-Versand, die Änderung selbst ist sehr klein)

## Scope

**Enthalten:** genau eine neue parallele Form im Gate, Fang-Nachweise im Gate-Test, Nachweis der Netzsperren je Worker, Doku, Blockmeldung und Sync-Test.

**Nicht enthalten:** Änderung der Vergleichslogik des Gates, weitere Worker-Zahlen, Änderung am CI-Aufruf, Reparatur roter Server-Artefakte, Messung am Server (früheres AC-7, jetzt #3323), Gate-Lücke Großschreibung auf macOS (#3322, vorbestehend), `README.md` mit nacktem `uv run pytest`.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/broad_test_run_gate.py` | MODIFY | neues Literal `OFFLINE_PARALLEL_CALL` in `_OFFLINE_CALLS`; Docstring Regel 3; Blockmeldung nennt beide Formen; Vergleichslogik unverändert |
| `tests/tdd/test_broad_test_run_gate_offline_form.py` | MODIFY | Freigabe- und Blockfälle, Sync-Test Doku und Konstante, Blockmeldung, Override-Fall (AC-6) |
| `tests/tdd/test_xdist_worker_sicherheit.py` | MODIFY | Pflichtflag-Prüfung und Worker-Nachweis an der wörtlichen Form (per `ast` gelesen, laufen damit auch in CI); bisheriger AC-7-Test (`-n` bleibt gesperrt) wird auf "andere `-n`-Formen bleiben gesperrt" präzisiert |
| `tests/probes_xdist/` (erweiterte oder neue Sonde) | MODIFY/CREATE | Barriere-Sonde, zweifach parametrisiert, die je Aufruf alle drei Netz-Prüfungen ausführt |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Abschnitte "Breiter Testlauf gesperrt" und "Parallele Kern-Suite in CI": parallele Form, "bleibt seriell" und "sperrt `-n` lokal" ersetzt; der Hinweis auf die fehlende Laufzeitmessung verweist auf #3323 |
| `.github/workflows/ci.yml` (Z. 71), `tests/conftest.py` (Z. 555-558) | MODIFY | nur Kommentare, die "lokal seriell" bzw. "ohne xdist (lokaler Volllauf, Gate-Form)" behaupten |
| `docs/specs/modules/perf_3209_pytest_xdist_ci.md` | MODIFY | Vermerk: AC-7 (`-n` lokal gesperrt) abgelöst durch #3278 |

Unverändert: `tests/tdd/test_broad_test_run_gate_ignores_override.py` (nutzt `OFFLINE_CALL`, Name bleibt), `tests/tdd/test_loopback_port_guard_offline_lauf.py`, `tests/tdd/test_xdist_doku_3209.py` (verlangt `#3278` und `-n 4 --dist loadgroup` im CI-Abschnitt, beide Zeichenketten bleiben beim Umformulieren erhalten). Außerhalb des Scopes: `README.md` mit nacktem `uv run pytest`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `hook_utils` (Plugin agent-os-openspec) | Modul | Gate-Grundlage; fehlt in CI, daher laufen Gate-Tests nur lokal |
| `pytest-xdist` >= 3.8.0 | dev-Dependency, vorhanden | parallele Worker, `--dist loadgroup` |
| `pytest-socket` 0.8.0 | dev-Dependency, vorhanden | `--disable-socket` muss in jedem Worker greifen |
| `pytest-timeout` | bestehend | globaler `timeout = 30` je Worker |
| `tests/_loopback_port_guard.py` | bestehend | je Prozess in `pytest_configure` installiert |
| `tests/conftest.py` | bestehend | worker-feste Echtbaum-Wächter, serielle Gruppe `echtdaten` (#3209) |
| `fix_1755_offline_volllauf.md` | Spec | sichere serielle Form, Fix-Loops 1-8 |
| `perf_3209_pytest_xdist_ci.md` | Spec | CI-Parallelisierung; deren AC-7 wird abgelöst |
| `fix_2227_override_zwei_gates.md` | Spec | `override` öffnet das Gate nicht |
| ADR-0094 | ADR | bleibt unverändert |

## Implementation Details

1. **Genau ein neues Literal** als vollständiger String (per `ast.literal_eval` lesbar, keine Verkettung, kein f-String):
   `nice -n 10 uv run pytest -n 2 --dist loadgroup --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports --ignore=tests/red/`
   Keine Variante ohne `--ignore=tests/red/`. Die serielle Form bleibt frei. `nice` ist fester Bestandteil, damit die Lastgrenze nicht am Aufrufer hängt und es bei einem Literal bleibt.
2. **Vergleich unverändert:** Freigabe nur per exaktem Rohstring-Vergleich vor jeder Shell-Zerlegung (#1755, Fix-Loop 6). Kein Parser und keine Regex für `-n`. Einziger erlaubter Zusatz bleibt ` > <pfad> 2>&1`.
3. **`--dist loadgroup` ist Pflicht:** Ohne es würde die serielle Gruppe `echtdaten` auf mehrere Worker zerfallen. `-n` ohne `loadgroup` muss blocken.
4. **Worker-Zahl 2** (konservativ), nur im Literal festgelegt. Ein Wechsel auf 3 ist eine Literal- plus Doku-Änderung und braucht erneut Gate-Adversary (2 Runden), und zwar erst nach Servermessung.
5. **Pflichtflag-Prüfung im Test:** Das Literal wird per `ast` aus der Gate-Datei gelesen (läuft dadurch auch in CI), per `shlex.split` zerlegt und gegen die Liste der Pflichtflags geprüft (`-n 2`, `--dist loadgroup`, `--disable-socket`, `--allow-unix-socket`, `--allow-hosts=127.0.0.1,::1,localhost`, `--loopback-own-ports`, `--ignore=tests/red/`). Ein Tippfehler im Literal macht diesen Test rot.
6. **Sync-Test Doku und Konstante:** `gates_und_ratschen.md` muss das serielle und das parallele Literal wörtlich enthalten, gelesen aus der Konstante, nicht abgeschrieben. Die Blockmeldung nennt beide Formen.
7. **Worker-Nachweis:** Das Literal wird per `ast` aus der Gate-Datei gelesen (wirkt auch in CI, wo der Gate-Import ohne Plugin scheitert). `nice -n 10 uv run pytest` wird abgetrennt, der Rest läuft als innerer pytest-Subprozess auf den Netz-Sonden. Unter `loadgroup` läuft jeder Test nur einmal. Deshalb gibt es eine zweifach parametrisierte Sonde, deren Aufrufe je alle drei Prüfungen ausführen und vorher in einer Barriere warten, bis sich zwei verschiedene Worker eingetragen haben. Die Barriere hat ein Zeitlimit (unter dem globalen `timeout = 30`) und endet bei Ablauf mit klarem Fehler statt zu hängen. Der innere Lauf für diesen Nachweis setzt weder `-o addopts=` noch Flags, die eine Option der Form überschreiben; nur Sonden-Pfad, `--basetemp` und Ausgabeoptionen kommen hinzu. Dafür braucht `_innerer_lauf` einen Weg ohne `-o addopts=`; die bestehenden Aufrufer behalten ihr Verhalten. Geprüft wird je Worker: Egress gesperrt, fremder Loopback-Port gesperrt, eigener Port erlaubt. Der bestehende `--dist each`-Test bleibt zusätzlich.
8. **Gate-Adversary (2 Runden).** Zu blocken: `-n 3`, `-n2`, `-n auto`, `--numprocesses`, doppeltes `-n`, `--dist` fehlt oder anders, `--tx`, `-p no:xdist`, `-p no:_loopback_port_guard`, `--boxed`, fehlende oder umgestellte Flags, `nice` fehlt, andere Stufe, doppelt oder vor anderem Kommando, `ionice`/`sudo`/`env` davor, `PYTEST_ADDOPTS=`/`PYTEST_XDIST_*=` davor, `;`, `&&`, `|`, Substitution im Umleitungsziel, NBSP, `\` plus Zeilenumbruch, Mehrzeiler. Nicht Teil der Blockliste sind Zusätze, die schon heute jeden Aufruf freigeben (benannte Testdatei, `--collect-only`, `--co`, `--version`, `--help`): Regel 1 und 2 des Gates bleiben unverändert.
9. **Reihenfolge:** Gate-Tests ROT, Literal, Sync-Test, Worker-Nachweis, Doku und Kommentare, Adversary 2 Runden. Die Servermessung folgt getrennt in #3323.

## Expected Behavior

- **Input:** Ein Bash-Aufruf mit dem parallelen Literal (optional ` > pfad 2>&1`) oder der bisherigen seriellen Form.
- **Output:** Gate Exit 0 (frei). Jede Abweichung, die nicht unter Regel 1 oder 2 fällt, Exit 2 mit Blockmeldung, die die serielle und die parallele Form wörtlich nennt.
- **Side effects:** Keine im Produkt. `override` öffnet das Gate weiterhin nicht (#2227). Zwei gleichzeitige Läufe im selben Checkout werden rot (gewollte Wächter-Wirkung).

## Acceptance Criteria

- **AC-1:** Given das Gate kennt die serielle und die parallele Offline-Form / When das parallele Literal wörtlich, auch mit angehängtem ` > pfad 2>&1`, an das Gate übergeben wird, und ebenso die serielle Form / Then antwortet das Gate beide Male mit Exit 0, und die bisherigen seriellen Freigaben bleiben unverändert frei.
  - Test: Gate als Subprozess mit Hook-Payload aufrufen (Freigabefälle parallel und seriell, je mit und ohne Umleitung); erwartet Exit 0.

- **AC-2:** Given das parallele Literal ist freigegeben / When jede Abweichung aus der Adversary-Liste (`-n 3`, `-n2`, `-n auto`, `--numprocesses`, doppeltes `-n`, `--dist` fehlt oder anders, `--tx`, `-p no:xdist`, `-p no:_loopback_port_guard`, `--boxed`, fehlende oder umgestellte Flags, `nice` fehlt/andere Stufe/doppelt/vor anderem, `ionice`/`sudo`/`env` davor, `PYTEST_ADDOPTS=`/`PYTEST_XDIST_*=` davor, `;`, `&&`, `|`, Substitution im Umleitungsziel, NBSP, `\` plus Zeilenumbruch, Mehrzeiler, Zusatzflags wie `-o addopts=`, `-c`, `-p no:socket`, `--force-enable-socket`, `-m live`, `--noconftest`, `-k`, jeweils ohne benannte Testdatei) übergeben wird / Then blockt das Gate jede mit Exit 2 und Blockmeldung, auch die xdist-Form ohne Loopback-Flags.
  - Test: parametrisierter Gate-Subprozess-Test über die vollständige Liste; erwartet Exit 2 und "BLOCKED" in der Ausgabe.

- **AC-3:** Given das parallele Literal wird per `ast` aus der Gate-Datei gelesen / When es per `shlex.split` zerlegt und gegen die Pflichtflags geprüft wird / Then enthält es alle Sicherheits-Flags samt `-n 2`, `--dist loadgroup` und `--ignore=tests/red/`, und eine absichtlich verfälschte Kopie (z. B. Tippfehler in `--loopback-own-ports`) wird von derselben Prüfung als fehlerhaft erkannt.
  - Test: Prüffunktion gegen die echte Konstante (grün) und gegen verfälschte Kopien je Pflichtflag (rot); Gegenprobe zeigt, dass ein Tippfehler im Literal den Test rot macht.

- **AC-4:** Given die parallele Form, gelesen aus der Gate-Datei (nicht abgeschrieben) / When sie nach Abtrennen von `nice -n 10 uv run pytest` als echter pytest-Subprozess auf den Netz-Sonden läuft / Then wurde jede der drei Prüfungen (Egress, fremder Loopback-Port, eigener Port) in beiden Workern (`gw0`, `gw1`) ausgeführt, Egress und fremder Port sind in jedem Worker blockiert, der eigene Port ist erlaubt, und der Test schlägt fehl, wenn eine Prüfung nur in einem Worker lief oder die Barriere ihr Zeitlimit erreicht.
  - Test: Subprozesslauf mit der wörtlichen Form und Sonden mit Barriere; Auswertung des Protokolls je Worker; Gegenprobe: dieselbe Sonde mit `-n 1` statt `-n 2` endet innerhalb des Zeitlimits rot mit der Barriere-Meldung; dieselbe Form ohne `--loopback-own-ports` lässt die Auswertung für den fremden Port scheitern.

- **AC-5:** Given Doku und Gate-Konstante sind getrennte Quellen / When der Sync-Test `gates_und_ratschen.md` gegen `OFFLINE_CALL` und `OFFLINE_PARALLEL_CALL` prüft und die Blockmeldung für einen unzulässigen Aufruf ausgelöst wird / Then enthält die Doku beide Literale wörtlich, die Blockmeldung nennt beide Formen, und eine Abweichung zwischen Doku und Konstante macht den Test rot.
  - Test: Doku-Datei gegen Konstante (`# doc-compliance-test`, nur für die Auffindbarkeit); Blockmeldung aus echtem Gate-Aufruf mit unzulässiger Form gelesen.

- **AC-6:** Given der Nutzer hat `override` gesetzt / When das parallele Literal mit einer unzulässigen Abweichung (z. B. `-n auto`) aufgerufen wird / Then öffnet `override` das Gate nicht, und es bleibt bei Exit 2.
  - Test: bestehende `test_broad_test_run_gate_ignores_override.py` bleibt unverändert grün; zusätzlicher Fall mit der parallelen Abweichung und echtem Override-Token in `test_broad_test_run_gate_offline_form.py`.

## Test Plan

| AC | Nachweis | Ort | Läuft in CI |
|----|----------|-----|-------------|
| AC-1, AC-2 | echter Gate-Subprozess, Exit-Code und Meldung je Kommandozeile | `tests/tdd/test_broad_test_run_gate_offline_form.py` | nein |
| AC-3 | Pflichtflag-Prüfung am Literal (per `ast` gelesen) und an verfälschten Kopien | `tests/tdd/test_xdist_worker_sicherheit.py` | ja |
| AC-4 | innerer pytest-Lauf mit der wörtlichen Form und Barriere-Sonde, dazu Gegenproben | `tests/tdd/test_xdist_worker_sicherheit.py`, `tests/probes_xdist/` | ja |
| AC-5 | Doku gegen Konstante, Blockmeldung aus echtem Gate-Aufruf | `tests/tdd/test_broad_test_run_gate_offline_form.py` | nein |
| AC-6 | Gate-Subprozess mit echtem Override-Token | `tests/tdd/test_broad_test_run_gate_offline_form.py` | nein |

Mutations-Gegenproben (Phase 6/7): je Pflichtflag aus dem Literal entfernen ⇒ AC-3 rot; `startswith` statt exaktem Vergleich ⇒ AC-2 rot; Port-Guard in den Workern nicht installieren ⇒ AC-4 rot; Literal in der Doku ändern ⇒ AC-5 rot. Gate-Adversary mindestens 2 Runden. Weiter grün bleiben: `test_broad_test_run_gate_ignores_override.py`, `test_broad_test_run_gate_pytest_word_position.py`, `test_loopback_port_guard_offline_lauf.py`, `test_xdist_doku_3209.py`.

## Definition of Done

- AC-1 bis AC-6 durch automatische Tests belegt, Kern-Schicht und CI grün.
- Gate-Adversary 2 Runden ohne Lücke, Mutations-Gegenproben rot wie beschrieben.
- Doku, Blockmeldung, Kommentare und der Vermerk in `perf_3209` stimmen mit dem Gate überein.
- Diese Lieferung ist eine Teillieferung von #3278: Issue #3278 bleibt offen, bis die Servermessung (#3323) belegt ist.

## Known Limitations

- **Abgetrennt: die Servermessung (früheres AC-7) liegt wortgleich in #3323.** Grund: Der Serverzugang (`ssh henemm`) wurde am 2026-11-24 von der Berechtigungsprüfung der Sitzung abgelehnt und nicht umgangen; Erreichbarkeit ist ungeprüft. Solange AC-7 in dieser Spec stand, hielt es die Prüfung der fertigen Teile auf (QA-Gate verlangt alle Punkte, Verdict BROKEN). Folge: Zwei der drei Abschlusskriterien des Issues ("belegt schneller", "Prod-Dienste während des Laufs unbeeinträchtigt") sind mit dieser Lieferung NICHT belegt. Die parallele Form wird freigegeben, bevor Laufzeitgewinn und Last neben Prod gemessen sind. Mac-Messungen (10 Kerne, 16 GB, kein Prod daneben) ersetzen den Nachweis nicht.
- **Worker-Zahl 2** ist eine Vorsichtswahl ohne Messung. Die Laufzeit-Schätzung für `-n 2` (ca. 30-35 min) ist eine Extrapolation, die Schätzung für `-n 3` (22-28 min) stammt aus #3209. Beides ist nicht gemessen, ebenso die Wirkung von `nice -n 10`. Ein Wechsel auf 3 erst nach der Servermessung (#3323), mit Literal- und Doku-Änderung und erneutem Adversary.
- **Verteilung:** `--dist loadgroup` legte die zwei Sonden-Aufrufe im Direktlauf auf `gw0` und `gw1` (2026-11-24). Die Barriere macht ein Ausbleiben sichtbar (roter Test), erzwingt die Verteilung aber nicht.
- **Grün ist kein Kriterium des lokalen Laufs:** Seriell waren auf dem Server 9 Tests rot und 2 Fehler (Server-Artefakte, CI auf demselben Commit grün). Vergleichsgröße sind Laufzeit und keine zusätzlichen Roten.
- **Last:** Server 4 vCPU, 8 GB, geteilt mit Prod und Staging. Serieller Lauf: 0,9 GB RSS, 51 % eines Kerns. Unter Last können `timeout = 30` und timing-empfindliche Tests häufiger wackeln. Zusicherungen werden nicht gelockert. Die serielle Gruppe `echtdaten` läuft in einem Worker und begrenzt den Gewinn.
- **Restrisiken (wie seriell, nicht neu gelöst):** `PYTEST_ADDOPTS` aus der geerbten Umgebung ist für den Rohstring-Vergleich unsichtbar. Kindprozesse (curl, Go, Playwright) und UDP sind vom Port-Guard nicht erfasst. Die Premium-SMS-Doubles nutzen `_free_port()` mit kleinem Race-Fenster, das einen Test rot machen kann. Eine Mustersuche nach fest gebundenen Ports in `tests/` blieb ohne Treffer, ist aber kein Vollständigkeitsbeweis.
- **Gate-Tests laufen nicht in CI** (Plugin fehlt, `importorskip`): AC-1, AC-2, AC-5, AC-6 sind nur lokal belegt, eine Doku-Drift fiele erst in einer lokalen Sitzung auf. AC-3 und AC-4 laufen auch in CI.
- **Ablösung:** `perf_3209_pytest_xdist_ci.md` AC-7 ("`-n` lokal gesperrt") wird bewusst abgelöst; dort kommt ein Vermerk.
- Zwei gleichzeitige Läufe im selben Checkout werden rot (gewollte Wächter-Wirkung).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Ein weiteres wörtliches Literal im bestehenden Rohstring-Mechanismus, keine neue Entscheidung zu Kanälen, Providern, Datenmodell, Auth oder Teststrategie. ADR-0094 bleibt unverändert.

## Changelog

- 2026-11-24 (1.1): nach Umsetzung und Gate-Adversary zurück in die Spec-Phase. AC-7 (Servermessung) wortgleich nach #3323 abgetrennt, weil ohne Serverzugang nicht belegbar; Issue #3278 bleibt bis dahin offen. AC-1 bis AC-6 unverändert. Umfang (500) und Verteilungsbefund nachgetragen.
- 2026-11-24: Nach Abgleich mit dem Code präzisiert (AC-2 bis AC-4, AC-6, AC-7): Prüfungen je Worker statt Sonden je Worker, Vergleich auf demselben Commit, Regel 1 und 2 bleiben frei.
- 2026-11-24: Initial spec created (Workflow rework-3278-lokaler-volllauf-parallel, Issue #3278)
