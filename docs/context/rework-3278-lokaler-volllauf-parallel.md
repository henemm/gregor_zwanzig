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
