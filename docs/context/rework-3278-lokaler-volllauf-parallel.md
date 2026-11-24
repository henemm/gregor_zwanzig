# Context: rework-3278-lokaler-volllauf-parallel

## Request Summary
Issue #3278 (Teil von #1196, Folge von #3209): Das Gate `broad_test_run_gate.py` soll eine zusätzliche,
wörtlich festgelegte **parallele** Form des sicheren Offline-Volllaufs freigeben (feste Worker-Zahl 2 oder 3,
kein `-n auto`, alle Sicherheits-Flags Pflicht, optional `nice`). Abschluss: belegt schneller als seriell,
Gate-Adversary 2 Runden ohne Lücke, Prod-Dienste während des Laufs unbeeinträchtigt (Selftest grün).

Intake: Score 4 (Scope 1, Blast Radius 2, Unsicherheit 1), Typ `feature`, `AUTONOMY=auto`.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/broad_test_run_gate.py` | `_OFFLINE_BASE_CALL`/`OFFLINE_CALL`/`_OFFLINE_CALLS` (L89-94), `_OFFLINE_REDIRECT_RE` (L96), `_offline_form_is_safe` (L288), Blockmeldung `_block` (L327), Modul-Docstring Regel 3 (L36-52) |
| `tests/tdd/test_broad_test_run_gate_offline_form.py` | Freigaben (L64), Blockliste (L95), Fix-Loop-2-bis-8-Fälle, Blockmeldung (L366, L472) |
| `tests/tdd/test_broad_test_run_gate_ignores_override.py` | `ALLOWED` (ca. L178) nutzt `gate.OFFLINE_CALL` |
| `tests/tdd/test_broad_test_run_gate_pytest_word_position.py` | Nachbar-Gate-Test, muss grün bleiben |
| `tests/tdd/test_xdist_worker_sicherheit.py` | `test_ac6_egress_und_loopback_guard_in_jedem_worker` (L400, `-n 2 --dist each`), `test_ac7_…_n_bleibt_gesperrt` (L439: angehängtes ` -n 4` blockt) |
| `tests/probes_xdist/` (`probe_ac6_netz.py`) | Netz-Sonden je Worker |
| `tests/_loopback_port_guard.py` | Port-Guard, je Prozess in `pytest_configure` installiert; Docstring nennt die Form (L9) |
| `tests/conftest.py` | Worker-feste Echtbaum-Wächter (#3209), `pytest_plugins = ["_loopback_port_guard"]` (L22) |
| `docs/reference/gates_und_ratschen.md` | Abschnitt „Breiter Testlauf gesperrt“ (L238-262, „bleibt seriell … #3278“) und „Parallele Kern-Suite in CI“ (L264-270, „sperrt `-n` lokal weiterhin“) |
| `.github/workflows/ci.yml` | Kommentar L71 „lokale Form bleibt seriell (#3278)“; CI-Aufruf selbst unverändert |

## Existing Patterns
- Freigabe ausschließlich per exaktem Rohstring-Vergleich VOR jeder Shell-Zerlegung (#1755, Fix-Loop 6). Neue Form
  = neues Literal in `_OFFLINE_CALLS`, keine Regex und kein Parser für `-n`.
- Einziger erlaubter Zusatz: genau ` > <pfad> 2>&1`.
- CI läuft `-n 4 --dist loadgroup`. Ohne `--dist loadgroup` zerfiele die serielle Gruppe `echtdaten`: die lokale
  Form braucht es zwingend, `-n` ohne `loadgroup` muss blocken.
- Doku-Form und Gate-Konstante sind heute nicht durch einen Test verknüpft (Sync-Test gefordert).

## Dependencies
- Upstream: `hook_utils` (Plugin agent-os-openspec), pytest-xdist >= 3.8.0 (vorhanden), pytest-socket, pytest-timeout.
- Downstream: alle Sitzungen und Agenten, die den Volllauf starten; `/60-validate`.

## Existing Specs
- `docs/specs/modules/fix_1755_offline_volllauf.md`: sichere Offline-Form (Fix-Loops 1-8).
- `docs/specs/modules/perf_3209_pytest_xdist_ci.md`: AC-7 („`-n` lokal weiterhin gesperrt“) wird durch dieses Issue bewusst abgelöst.
- `docs/specs/modules/fix_2227_override_zwei_gates.md`: `override` öffnet das Gate nicht.
- Vorläufer-Analyse und Messwerte: `docs/context/perf-3209-pytest-laufzeit.md`.

## Risks & Considerations
- **Sicherheit (hoch):** das Gate verhindert echten Versand an Nutzer (Vorfall 2026-08-03, #1477). Zu blocken u. a.:
  `-n auto`, andere Worker-Zahl, `--dist` fehlt/anders, `--tx`, `-p no:xdist`, `-p no:_loopback_port_guard`, `--boxed`,
  xdist-Form ohne Loopback-Flags, `PYTEST_ADDOPTS=`/`PYTEST_XDIST_*=`, `;`, `&&`, `|`, Substitution im Umleitungsziel,
  `nice` mit anderen Argumenten oder vor anderen Kommandos.
- **Worker-Nachweis:** Sperren gelten je Prozess. Vorhandener Test nutzt `--dist each` mit `-n 2`; der Nachweis muss an
  der WÖRTLICHEN neuen Form wirken (aus der Gate-Konstante abgeleitet, nicht abgeschrieben).
- **Gate-Tests laufen nicht in CI** (Plugin fehlt, `importorskip`): ihr Nachweis ist lokal; die Worker-Nachweise laufen in CI.
- **Last:** Server 4 vCPU, 8 GB, geteilt mit Prod und Staging; seriell 0,9 GB RSS, 51 % eines Kerns, 56:17 min (2026-11-22).
  Worker-Zahl 2 oder 3 nach Messung; Schätzung #3209: 22-28 min bei `-n 3`.
- **Grün ist kein Kriterium des lokalen Laufs:** seriell waren 9 failed / 2 errors Server-Artefakte (CI auf demselben Commit
  grün). Vergleichsgröße: Laufzeit und keine ZUSÄTZLICHEN Roten.
- `timeout = 30` und timing-empfindliche Tests können unter Last häufiger wackeln; Zusicherungen nicht lockern.
- Zwei gleichzeitige Läufe im selben Checkout werden rot (gewollte Wächter-Wirkung).

## Offen: Zugang zum Server
- Diese Sitzung läuft auf einem Mac (Darwin, 10 Kerne, 16 GB), nicht auf dem Server. Last- und Laufzeitmessung neben
  Prod/Staging verlangt den Server. Playbook-Weg ist `ssh henemm`; eine reine Lese-Abfrage (Last, Dienststatus) wurde am
  2026-11-24 von der Berechtigungsprüfung der Sitzung abgelehnt und NICHT umgangen. Erreichbarkeit daher ungeprüft.
- Mac-Messungen ersetzen den Abschlussnachweis nicht (andere Kerne, kein Prod daneben).
- Gate, Tests, Worker-Nachweis und Doku sind ohne Server machbar; offen bis zur Freigabe: Wahl 2 vs. 3 Worker per
  Messung, Abschlussmessung, Prod-Selftest während des Laufs.

## Analysis

### Type
Feature (Werkzeug/Sicherheits-Gate, keine Produktoberfläche). Kein neues ADR: ADR-0094 bleibt unverändert, Verweis in der Spec genügt.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/broad_test_run_gate.py` | MODIFY | neues Literal `OFFLINE_PARALLEL_CALL` in `_OFFLINE_CALLS`, Docstring Regel 3, Blockmeldung; Vergleichslogik unverändert |
| `tests/tdd/test_broad_test_run_gate_offline_form.py` | MODIFY | Freigabe- und Blockfälle, Pflichtflag-Prüfung, Sync-Test Doku ↔ Konstante |
| `tests/tdd/test_xdist_worker_sicherheit.py` | MODIFY | Worker-Nachweis an der wörtlichen Form; AC-7 (L439) präzisieren |
| `tests/probes_xdist/` (neue oder erweiterte Sonde) | MODIFY/CREATE | Barriere, damit jeder Worker nachweislich drankommt |
| `docs/reference/gates_und_ratschen.md` | MODIFY | L245-262 und L264-270: parallele Form, „bleibt seriell“/„sperrt `-n`“ ersetzen |
| `.github/workflows/ci.yml` L71, `tests/conftest.py` L555-558 | MODIFY | nur Kommentare, die „lokal seriell“ behaupten |
| `docs/specs/modules/perf_3209_pytest_xdist_ci.md` | MODIFY | Vermerk „AC-7 (`-n` lokal gesperrt) abgelöst durch #3278“ |

Unverändert: `test_broad_test_run_gate_ignores_override.py` (nutzt `OFFLINE_CALL`, Name bleibt), `test_loopback_port_guard_offline_lauf.py`,
`test_xdist_doku_3209.py` (verlangt `#3278` und `-n 4 --dist loadgroup` im CI-Abschnitt: beide Zeichenketten beim Umformulieren behalten).
Außerhalb des Scopes: `README.md` L11/L58 nennt weiter nacktes `uv run pytest`.

### Scope Assessment
- Files: 5 im Kern, dazu 3 mit reinen Kommentar-/Vermerkzeilen (Grenze 4-5 überschritten, weil sonst Doku und Kommentare dem Gate widersprechen)
- Estimated LoC: ca. +215/-20 (Grenze ±250)
- Risk Level: MEDIUM (Sicherheits-Gate gegen Produktiv-Versand, Änderung selbst sehr klein)

### Technical Approach
1. **Genau ein neues Literal** als ein vollständiger String (per `ast.literal_eval` lesbar, keine Verkettung, kein f-String):
   `nice -n 10 uv run pytest -n 2 --dist loadgroup --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports --ignore=tests/red/`
   Keine Variante ohne `--ignore=tests/red/`. Serielle Form bleibt frei. `nice` ist fester Bestandteil (Issue: „optional
   `nice`“), damit die Lastgrenze nicht am Aufrufer hängt und es bei einem Literal bleibt. `_offline_form_is_safe` greift
   VOR jeder Zerlegung, der Präfix ist daher unkritisch.
2. **Worker-Zahl 2** (konservativ), steht nur im Literal. Wechsel auf 3 erst nach Servermessung.
3. **Pflichtflag-Prüfung im Test** gegen Tippfehler im Literal: nach `shlex.split` müssen alle Sicherheits-Flags und
   `--dist loadgroup` vorhanden sein.
4. **Sync-Test:** Doku enthält serielles und paralleles Literal wörtlich (aus der Konstante, nicht abgeschrieben).
5. **Worker-Nachweis:** Literal per `ast` aus der Gate-Datei lesen (wirkt auch in CI, wo der Gate-Import mangels Plugin
   scheitert), `nice -n 10 uv run pytest` abtrennen, Rest an den inneren Lauf. `--dist loadgroup` garantiert keine
   Verteilung, daher warten die Sonden in einer Barriere, bis sich alle Worker eingetragen haben (Zeitlimit mit klarem
   Fehler, kein Hängen). Prüfung je Worker: Egress gesperrt, fremder Loopback-Port gesperrt, eigener Port erlaubt. Die
   `--dist each`-Prüfung bleibt zusätzlich. UNGEPRÜFT: dass loadgroup die Sonden beim Start auf beide Worker legt.
6. **Gate-Adversary (2 Runden), zu blocken:** `-n 3`, `-n2`, `-n auto`, `--numprocesses`, doppeltes `-n`, `--dist`
   fehlt/anders, `--tx`, `-p no:xdist`, `-p no:_loopback_port_guard`, `--boxed`, fehlende oder umgestellte Flags, `nice`
   fehlt/andere Stufe/doppelt/vor anderem, `ionice`/`sudo`/`env` davor, `PYTEST_ADDOPTS=`/`PYTEST_XDIST_*=` davor, `;`
   `&&` `|`, Substitution im Umleitungsziel, NBSP, `\`+Zeilenumbruch, Mehrzeiler.

### Varianten
| Variante | Laufzeit | Speicher | CPU | Status |
|---|---|---|---|---|
| seriell | 56:17 min | 0,9 GB | 51 % eines Kerns | gemessen (2026-11-22) |
| `-n 2` | ca. 30-35 min | ca. 1,8 GB plus Controller | ca. 1 Kern | geschätzt (Extrapolation) |
| `-n 3` | 22-28 min | ca. 2,7 GB plus Controller | ca. 1,5 Kerne | geschätzt (#3209) |
| `nice -n 10` | wie oben, unter Last länger | gleich | weicht Prod/Staging aus | nicht gemessen |

Die serielle Gruppe `echtdaten` läuft in einem Worker und begrenzt den Gewinn.

### Dependencies
- pytest-xdist 3.8.0 und pytest-socket 0.8.0 (beide in `dev`, im Lock). xdist reicht Optionen an jeden Worker weiter;
  `_loopback_port_guard.pytest_configure` installiert je Prozess.
- Gate in `.claude/settings.json` (PreToolUse Bash). Gate-Tests laufen nur lokal, die Worker-Nachweise in CI.
- `ci_tdd_excludes.txt` hat genau einen aktiven Eintrag (`test_issue_833_gate.py`, Chromium): läuft lokal mit, in CI nicht.
- Eine Mustersuche nach fest gebundenen Ports in `tests/` blieb ohne Treffer (kein Vollständigkeitsbeweis). Die
  Premium-SMS-Doubles nutzen `_free_port()` mit kleinem Race-Fenster (kann einen Test rot machen).

### Restrisiken (benennen, nicht neu lösen)
- `PYTEST_ADDOPTS` aus der geerbten Umgebung ist für den Rohstring unsichtbar; gilt schon für die serielle Form.
- Kindprozesse (curl, Go, Playwright) und UDP sind vom Port-Guard nicht erfasst (wie seriell).

### Reihenfolge
Gate-Tests ROT → Literal → Sync-Test → Worker-Nachweis → Doku/Kommentare → Adversary 2 Runden → Server-Abschlussnachweis.

### Open Questions
- [ ] Servermessung (2 vs. 3 Worker, „belegt schneller“, Prod-Selftest während des Laufs): ohne Serverzugang nicht
  erbringbar. Blockiert Spec und Umsetzung nicht, wohl aber den Abschluss. Das Issue bleibt bis dahin offen;
  Teillieferung sind Gate, Tests und Doku.

## Stand nach TDD RED (2026-11-24)
- RED: 112 failed, 155 passed. Ursachen: Konstante `OFFLINE_PARALLEL_CALL` fehlt, paralleles Literal wird geblockt, Blockmeldung
  nennt nur die serielle Form. Alle AC-2-Abweichungen blocken schon heute mit Exit 2, rot sind sie nur wegen der Meldung.
- Frühere Ungewissheit geklärt: `--dist loadgroup` verteilt die zwei Sonden-Aufrufe auf `gw0` und `gw1` (Direktlauf der Sonde,
  beide Gegenproben verhalten sich wie in AC-4 gefordert).
- **Umfang:** Tests allein +329/-10 Zeilen (davon ca. 85 Zeilen Blockliste), Schätzung gesamt ca. +350 Code-Zeilen statt +215.
  Die Spec-Aussage "±250 eingehalten" stimmt damit nicht mehr. Das Setzen von `loc_limit_override` wurde von der
  Berechtigungsprüfung abgelehnt und nicht umgangen; die Entscheidung liegt beim PO.
- **PO-Entscheidung 2026-11-24 (AskUserQuestion):** Umfangsgrenze fuer #3278 auf 500 angehoben, alle Pruefungen bleiben vollstaendig.

## Stand Phase 6 (2026-11-24)
- Doku, Kommentare und Vermerk umgesetzt (uncommittet). Gate-Datei NICHT geändert: Developer Agent darf sie laut Rollenvorgabe nicht,
  `edit_gate` verlangt vom PO getipptes `override` (1 h). Nicht umgangen.
- Offener Gate-Eingriff, Vergleichslogik unverändert: `OFFLINE_PARALLEL_CALL` als einzeiliges Literal, Aufnahme in `_OFFLINE_CALLS`,
  Docstring Regel 3 mit beiden Zeilen (`--ignore` darf nur seriell fehlen), Blockmeldung nennt beide Formen je eigene Zeile.
- Ohne den Eingriff nichts ausliefern (Doku beschreibt die Form schon als frei). Testlauf: 114 rot, 260 grün; 112 wie RED.
- Ungeklärt: 2 rote Fälle in `test_loopback_port_guard_offline_lauf.py` (AF_UNIX-Pfadlänge/abstrakter Socket; 30-s-Timeout).
  Vergleichslauf ohne die Änderungen fehlt.
- **Nachtrag:** PO hat `override` getippt, Gate-Eingriff umgesetzt. 358 grün. Die 2 Roten sind Mac-Artefakte: `getfqdn` braucht hier
  35 s (Zeitlimit 30 s, gemessen), AF_UNIX-Pfadlänge bzw. abstrakte Namen gibt es auf macOS nicht; CI auf main war grün.

## Stand Phase 6b (2026-11-24): Adversary-Bericht liegt vor, Protokoll NICHT geschrieben
- Prüfer (2 Runden) meldet VERIFIED für AC-1 bis AC-6, AC-7 offen/nicht belegt. Testausgabe: `adversary-test-output.txt` (358 grün).
- `adversary-dialog.md` ist noch das leere Gerüst, nicht registriert, nicht gestempelt; Verdict im State leer. Dem Prüfer wurde das Schreiben
  abgelehnt: erst Breitlauf-Gate (Wort im Heredoc), dann Berechtigungsprüfung ("Undermining Oversight") für einen Umgehungsversuch mit
  Platzhalter. Der Hauptkontext hat es deshalb nicht stellvertretend geschrieben; nötig ist das ausdrückliche Ja des PO.
- Mutationen (an Kopien): alle gefangen (je Pflichtflag, `-n 3`, nice geändert/entfernt, startswith, Zusatz-Literale, Blockmeldung, Doku,
  Port-Guard in Workern, gw1 ohne Sperre, Barriere entfernt). Entfallen: Mutation "override öffnet Gate"; Basisstand nicht ausgeführt, nur Diff
  verglichen; Gate-Mutanten über Testkopie mit umgelenktem HOOK statt am unveränderten Aufbau.
- F001 MEDIUM, vorbestehend: Gate (`broad_test_run_gate.py:383`) prüft nur Kleinschreibung; auf macOS (Dateisystem ohne Groß-/Kleinunterschied)
  startet die großgeschriebene Form dieselbe Datei (Auflösbarkeit selbst nachgeprüft). Eigenes Issue (Sicherheitsrisiko), noch anzulegen.
- F002 LOW, vorbestehend: Umleitungsziel unbegrenzt (`..`, absolut, /dev/tcp), Zeile 99. Sammel-Eintrag #1196/#1197, noch anzulegen.
- F003 bis F005 Information: AC-6 nur über `-n auto` belegt; AC-4 ohne `nice`/`uv run` (spec-konform); 2 Mac-Rote vorbestehend.

## Nachtrag Phase 6b (2026-11-24): Protokoll eingetragen, QA-Gate blockt wegen AC-7, zurück zur Spec
- PO hat die technische Entscheidung an den Tech Lead delegiert; `adversary-dialog.md` ist eingetragen (Prüferbericht samt Einschränkungen).
- QA-Gate verlangt ALLE Checklisten-Punkte; AC-7 (Servermessung) ist offen. Fehler des Hauptkontexts: AC-7 aus der Protokoll-Checkliste
  genommen, obwohl die Spec-Änderung vom Spec-Freeze abgelehnt war. Das ergab kurz ein falsches VERIFIED; zurückgenommen, Verdict ist BROKEN.
  Der erneut erzeugte Stempel-Block im Protokoll steht doppelt; vor dem nächsten Stempeln bereinigen.
- Entscheidung: regulärer Weg `phase3_spec`. AC-7 wortgleich in ein Folge-Issue "Servermessung" verschieben (Abschlussbedingung bleibt), Spec,
  Briefing und Freigabe neu, danach Protokoll gegen die neue Spec. Im neuen Briefing offen sagen, dass AC-7 abgetrennt wird und warum.
- Code, Doku und Tests sind umgesetzt und uncommittet auf der Platte (Gate-Datei, gates_und_ratschen, ci.yml, conftest, perf_3209).

## Stand Phase 3, Spec 1.1 (2026-11-24)
- Folge-Issue #3323 (Servermessung) angelegt, AC-7 wortgleich übernommen; F001/F002 stehen in #3322. Spec 1.1 enthält AC-1 bis AC-6 unverändert.
- Issue #3278 bleibt offen, bis #3323 belegt ist (Workflow-Abschluss ist nicht Issue-Abschluss).
- Nach der Freigabe noch zu tun: in `gates_und_ratschen.md` "(#3278 AC-7)" durch "(#3323)" ersetzen; im Adversary-Protokoll die Checkliste an
  Spec 1.1 angleichen (AC-7-Zeile entfällt wegen der neuen Spec, nicht stillschweigend), doppelten Stempel-Block bereinigen, neu stempeln.
- Umsetzung und Tests liegen schon vor: `/40-tdd-red` darf keine neuen Tests erfinden, der RED-Nachweis ist `test-red-output.txt`.
- **Freigabe Spec 1.1 (2026-11-24):** Briefing-Ampel rot (Messung abgetrennt), auto-approve = human; der PO hat nach Lesen des Briefings
  `approved` getippt. Spec-Prüfung: VALID. Nicht übernommene Hinweise des Prüfers: Barriere-Zeitlimit ohne Zahl, Blockliste in Detail 8
  kürzer als in AC-2 (AC-2 gilt).

## Stand Phase 5, zweiter Durchgang (2026-11-24)
- RED übernommen, nicht neu gelaufen: `test-red-output.txt` (112 failed, 155 passed) entstand vor der Umsetzung; Testdateien und Sonde seit
  RED-Commit 0944dce1e (vor Rebase 3ab8a5605) unverändert (git diff leer), Gate-Datei dort ohne `OFFLINE_PARALLEL_CALL`, AC-1 bis AC-6 in Spec 1.1 unverändert.
- `/50-implement` baut nichts neu: Umsetzung liegt uncommittet vor. Offen: `gates_und_ratschen.md` Z. 268 "(#3278 AC-7)" durch "(#3323)"
  ersetzen, benannte Tests erneut laufen lassen, Protokoll-Checkliste an Spec 1.1 angleichen, doppelten Stempel bereinigen, neu stempeln.
- `workflow.py status` listet als Spec-Freigabe nur `auto` 07:56 (Spec 1.0); die vom PO getippte Freigabe von 1.1 erscheint dort nicht.
