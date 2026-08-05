# Context: fix-1307b-gates (#1307 Scheibe B — Befunde 2 bis 5)

## Request Summary

Issue #1307 listet fünf Gate-/Tooling-Befunde. Befund 1 ist mit Scheibe A erledigt
(`cf33590a`). Scheibe B soll die verbleibenden Befunde 2 bis 5 abarbeiten — jeweils
**mit gemessenem Ausgangsstand**, weil die schriftliche Diagnose im Issue sich bereits
zweimal als falsch erwiesen hat.

## Gemessener Ausgangsstand (2026-08-05, HEAD `584fa6de`)

Lauf: `uv run pytest --runxfail --color=no -q --disable-socket --allow-hosts=127.0.0.1`
über die vier genannten Testdateien. `--runxfail` schaltet die „bekannt offen"-Maskierung
ab und zeigt das echte Ergebnis.

| Befund | Testfall | Ergebnis |
|---|---|---|
| 2 | `test_issue_603_design_fidelity_gate.py::…::test_gate_allows_close_with_pass_artefact` | rot |
| 3 | `test_issue_668_head_sha_dedup.py::test_ac1_head_sha_called_once_without_override` | rot |
| 3 | `test_issue_668_head_sha_dedup.py::test_ac3_override_path_still_works` | rot |
| 4 | `test_e2e_path_helper.py::TestPathLogicConsolidated::test_path_logic_only_in_shared_module` | rot |
| 5 | `test_issue_816_alert_deviation.py::test_ac7_header_set_and_validator_noop` | rot |

Damit ist der Issue-Kommentar vom 2026-08-04 früh („3+4 im Code behoben, 5 via #1282
adressiert") zum dritten Mal widerlegt. Er war aus dem Code gelesen, nicht gemessen.

## Kernbefund: nur EINER der vier ist ein Code-Fehler

Die Recherche zeigt, dass „vier kaputte Wächter" die falsche Beschreibung ist.

| Befund | Was wirklich vorliegt | Klasse |
|---|---|---|
| 2 | Test setzt eine Umgebungsvariable, die es nicht mehr gibt | **veralteter Test** |
| 3 | `write_verdict()` fragt den Commit-Stand dreimal statt einmal ab | **echter Code-Fehler** |
| 4 | Test sucht per Textsuche nach `rev-parse` und trifft eine legitime Zeile | **untauglicher Test** |
| 5 | Zwei Tests fordern gegenteiliges Verhalten voneinander | **Spec-Widerspruch** |

## Befund 2 — Design-Gate

**Wurzel:** `.claude/hooks/pre_issue_close_design_gate.py:50` liest
`OPENSPEC_ACTIVE_WORKFLOW`. Der Test setzt `GZ_ACTIVE_WORKFLOW`
(`tests/tdd/test_issue_603_design_fidelity_gate.py:228`). Commit `93ef0741`
(„GZ_ACTIVE_WORKFLOW → OPENSPEC_ACTIVE_WORKFLOW in Projekt-Hooks") stellte acht
Hook-Dateien um — den Test aber nicht.

Folge: Das Gate löst den Workflow-Namen aus der ambient gesetzten Variable auf, sucht das
Pass-Artefakt im falschen Ordner, findet keines und beendet mit Exit 2
(`pre_issue_close_design_gate.py:72`). Der Test legt das Artefakt korrekt an — er redet
nur mit einer Variable, auf die niemand mehr hört.

Andere Gates (`prod_send_gate.py:307`, `staging_gate.py:285`, `prod_selftest.py:857`)
akzeptieren **beide** Namen mit Fallback-Kette. Das Design-Gate ist der einzige Ausreißer.

**Zusätzlicher, schwererer Befund — steht nicht im Issue:**
`pre_issue_close_design_gate.py` ist in **keiner** Settings-Datei verdrahtet
(selbst nachgemessen: `.claude/settings.json`, `.claude/settings.local.json`,
`~/.claude/settings.json` — kein Treffer). Es existiert nur als Skript und läuft
ausschließlich im Testkontext. Der Wächter, der das Schließen von Design-Issues bewachen
soll, ist seit seiner Einführung (#603) nie gelaufen.

Das ist exakt die Krankheit aus Scheibe A: eine Regel, die dasteht und nicht beißt.

## Befund 3 — Commit-Stand wird dreifach abgefragt

**Wurzel:** `write_verdict()` in `.claude/hooks/staging_gate.py` löst pro Lauf drei
`git rev-parse HEAD`-Aufrufe aus (gemessen per PATH-Shim, der echte Subprozesse zählt —
kein Mock):

1. `staging_gate.py:252` — `sha = _head_sha()` direkt in `write_verdict()`
2. `staging_gate.py:174` — via `_detect_committed_scope()`
3. `staging_gate.py:135` — via `_scope_diff_base()`, das aus (2) heraus aufgerufen wird

`_head_sha()` selbst (`staging_gate.py:95-96`) delegiert korrekt an
`_e2e_paths.head_sha()`, und dort steht genau **ein** Aufruf (`_e2e_paths.py:222-227`).
Der Fehler liegt nicht im Helfer, sondern in der Zahl seiner Aufrufe.

**Rückfall, kein Neubefund:** #668 hat genau das im Juni behoben (`3ef67003`,
Adversary VERIFIED, 22 grün). Der Commit steckt nachweislich noch in HEAD
(`git merge-base --is-ancestor` → ja). Seitdem kamen über #916/#988, #1084, #1096 und
#1428 neue Aufrufpfade dazu, die den Stand erneut selbst abfragen. Aus 1 wurden 3.

Der zugehörige Test war die ganze Zeit als „bekannt offen" markiert und damit grün —
niemand hat den Rückfall bemerkt. Dieselbe Mechanik, die in Scheibe A aus 5 unbemerkt 8
gemacht hat.

## Befund 4 — Struktur-Test prüft Text statt Verhalten

`tests/tdd/test_e2e_path_helper.py:182` prüft:

```python
assert "rev-parse" not in src
```

über den kompletten Quelltext von `staging_gate.py` und `prod_selftest.py`.

**Warum er rot ist:** Er trifft `staging_gate.py:399-401` —
`git rev-parse --verify --quiet <expected_commit>^{commit}`. Das ist eine
Existenzprüfung für einen übergebenen Commit, **keine** duplizierte Pfad-Logik. Der Test
schlägt also über eine Zeile an, die er nicht meint.

**Warum er trotzdem nichts taugt:**
- Trivial umgehbar durch `"rev-" + "parse"` oder implizite String-Verkettung
- Er übersieht vier weitere direkte git-Aufrufe, die das gemeinsame Modul genauso
  umgehen: `cat-file -e` (`:138`, `:147`), `diff --name-only` (`:226`),
  `merge-base --is-ancestor` (`:465`)
- Er würde bei einer harmlosen Erwähnung von `rev-parse` in einem Kommentar ebenfalls rot
- Ein Umbau, der den Text entfernt aber weiter dreimal abfragt, macht ihn grün, ohne
  Befund 3 zu lösen

Das ist die Klasse „Formprüfung ist bodenlos" — im Projekt bereits dreimal aufgetreten
(#1431 Kommandozeilen, #1471 AST, #1307 Scheibe A Hook-Einträge). Jedes Mal war die
Lösung, **die Frage umzudrehen**: nicht „erkenne ich eine verbotene Form?", sondern
„ist die Zusicherung an der Stelle erfüllt, an der sie wirkt?".

## Befund 5 — zwei Tests fordern Gegenteiliges

`.claude/hooks/briefing_mail_validator.py:505-512` liefert für
`X-GZ-Mail-Type: compare` und `deviation-alert` bewusst `ok=False` mit dem Fehlertext
`"… — falscher Validator, uebersprungen"`.

Das ist **Absicht aus #1282**: Der Marker `uebersprungen` wird in
`_write_validation_log()` (`:638-648`) ausgewertet. Gäbe der Validator `ok=True` zurück,
würde `passed: true` ins Protokoll geschrieben, und das Renderer-Commit-Gate (#811)
könnte diesen No-Op als echten Erfolgsnachweis akzeptieren — obwohl nichts geprüft wurde.
Genau diese Gate-Erosion sollte #1282 verhindern.

Abgesichert ist das durch `tests/tdd/test_briefing_validator_noop_not_pass.py`
(`test_compare_mail_type_noop_is_not_a_pass`, `test_deviation_alert_mail_type_noop_is_not_a_pass`,
beide `assert success is False`).

`tests/tdd/test_issue_816_alert_deviation.py:611-628` (AC-7) fordert für denselben Header
`ok=True`.

**Beide Tests können nicht gleichzeitig gelten.** Einer von beiden muss weichen.

## Related Files

| Datei | Relevanz |
|---|---|
| `.claude/hooks/pre_issue_close_design_gate.py` | Befund 2 — Prüfling; liest nur `OPENSPEC_ACTIVE_WORKFLOW` (`:50`); nirgends verdrahtet |
| `.claude/hooks/staging_gate.py` | Befund 3+4 — Prüfling; `_head_sha()` `:95`, Aufrufer `:135`/`:174`/`:252`; direkte git-Aufrufe `:138`/`:147`/`:226`/`:400`/`:465` |
| `.claude/hooks/_e2e_paths.py` | gemeinsames Modul; `head_sha()` `:220-230` mit genau einem Aufruf |
| `.claude/hooks/briefing_mail_validator.py` | Befund 5 — Prüfling; Typ-Weiche `:493-523`, Protokoll-Marker `:638-648` |
| `tests/tdd/test_issue_603_design_fidelity_gate.py` | Befund 2 — setzt veraltete Variable `:228` |
| `tests/tdd/test_issue_668_head_sha_dedup.py` | Befund 3 — zählt echte Subprozesse per PATH-Shim `:61-74` |
| `tests/tdd/test_e2e_path_helper.py` | Befund 4 — Substring-Test `:182` |
| `tests/tdd/test_issue_816_alert_deviation.py` | Befund 5 — AC-7 `:611-628`, xfail `:598` |
| `tests/tdd/test_briefing_validator_noop_not_pass.py` | Befund 5 — Gegentest aus #1282 |
| `.claude/settings.json` | Verdrahtung der Hooks; Design-Gate fehlt dort |

## Existing Patterns

- **Fallback-Kette für den Workflow-Namen:** `prod_send_gate.py:307-308`,
  `staging_gate.py:285-286`, `prod_selftest.py:857-858` akzeptieren beide Variablennamen.
  Vorbild für Befund 2.
- **Zuständigkeit strukturell lösen statt quittieren:** `email_spec_validator.py:241-258`
  filtert schon bei der Mail-Auswahl per IMAP-Scan auf den eigenen Typ, statt einen
  fremden Typ in `validate_message()` mit `True` durchzuwinken.
- **Zählnachweis ohne Mock:** `test_issue_668_head_sha_dedup.py:61-74` — PATH-Shim, das
  echte Subprozessaufrufe in eine Datei zählt und dann echtes `git` ausführt. Der saubere
  Weg, eine Aufrufzahl zu belegen.
- **Fail-open-Form für Hook-Einträge:** `if [ -f "…" ]; then python3 "…"; fi`
  (nie `&&`/`||`, die verschlucken den Rückgabewert) — aus Scheibe A.

## Dependencies

- **Upstream:** `staging_gate.py` und `prod_selftest.py` hängen an `_e2e_paths.py`.
  `briefing_mail_validator.py` hängt an `_validator_log.py`.
- **Downstream:** `renderer_mail_gate.py` liest die Protokolle des Mail-Prüfers und
  entscheidet daran über Commits. `deploy-gregor-prod.sh` und der Post-Deploy-Selbsttest
  hängen am Urteil von `staging_gate.py`. Eine Änderung an der Rückgabe des Mail-Prüfers
  wirkt direkt auf die Commit-Fähigkeit.

## Existing Specs

- `docs/specs/modules/rework_1211b_rot_triage.md` — Herkunft aller fünf Befunde
- `docs/specs/_archive/modules/issue_603_design_fidelity_gate.md` — Design-Gate,
  nennt `:116` einen `PreToolUse:Bash`-Hook, der nie eingetragen wurde
- `docs/specs/modules/fix_1409_worktree_test_paths.md` — Pfadregel; führt das Design-Gate
  `:61` ausdrücklich als unbedenklich
- `docs/reference/mail_validators.md` — Zuständigkeit der beiden Mail-Prüfer

## Risks & Considerations

1. **Befund 4 verleitet zum falschen Fix.** Die Zeile `rev-parse --verify` zu
   umschreiben, macht den Test grün und ändert fachlich nichts. Der Test muss ersetzt
   werden, nicht der Code angepasst.
2. **Befund 5 ist eine Entscheidung, kein Fix.** Wer den Validator auf `ok=True` umstellt,
   öffnet das Renderer-Gate für falsche Erfolgsnachweise. Der Beschluss aus #1282 ist der
   jüngere und der besser begründete.
3. **Das Design-Gate zu verdrahten ist eine Verhaltensänderung**, keine Reparatur — es
   würde erstmals echte `gh issue close`-Aufrufe blockieren können. Getrennt zu
   entscheiden.
4. **Befund 3 kann zurückkommen.** Er ist schon einmal zurückgekommen, weil der Test als
   „bekannt offen" markiert war. Ohne Entfernen dieser Markierung ist der Fix wertlos —
   die Lehre aus Scheibe A.
5. **`tests/tdd/conftest.py:37`** hält einen festen Hauptrepo-Pfad. Die drei hier
   betroffenen Tests nutzen ihn nicht, andere Fixtures schon — beim Ändern nicht
   versehentlich anfassen.
6. **Nur `.claude/`, `tests/`, `docs/` betroffen** → kein Produktions-Runtime-Code →
   Doku-/Tooling-Ausnahme greift, Staging- und Prod-Schritt entfallen (wie Scheibe A).

---

# Analysis

## Type

Bug (vier Wächter-/Prüfungsfehler), Tooling-Ebene. Kein Produktions-Runtime-Code.

## PO-Entscheidungen (2026-08-05)

1. **Design-Wächter wird eingehängt und scharf geschaltet**, mit Prüfdatum nach Regel-Budget.
2. **Beim Mail-Prüfer gilt #1282** — „übersprungen ist kein bestanden" bleibt. Der
   widersprechende AC-7-Test aus #816 wird korrigiert.
3. **Der Bildvergleich wird in dieser Scheibe wirklich gefahren**, nicht umgangen
   (PO-Einwand: Playwright und Staging sind vorhanden — nutzen).

## Nachgemessen nach der PO-Entscheidung: Befund 2 ist dreiteilig

Der Versuch, das Gate scharf zu schalten, deckte auf, dass es gar nicht bestehbar wäre.
Belegt durch einen echten Lauf
(`design_fidelity_diff.py --screen G-compare-uebersicht-kacheln`):

| Teil | Belegter Fehler | Beleg |
|---|---|---|
| 2a | Werkzeug legt den Bericht unter `GZ_ACTIVE_WORKFLOW` ab (`design_fidelity_diff.py:271`), Gate sucht unter `OPENSPEC_ACTIVE_WORKFLOW` (`pre_issue_close_design_gate.py:50`) | zwei verschiedene Ordner — Gate findet den frischen Bericht nie |
| 2b | Werkzeug reicht die Zugangsdaten nur ans Anmeldeformular, nicht an den vorgeschalteten Schutz (`design_fidelity_diff.py:174-186`, `new_context()` ohne `http_credentials`) | Staging `/login` → **401**, `WWW-Authenticate: Basic realm="Staging"`; mit Basic-Auth → **200** und Formular vorhanden. Lauf ergab `diff_pct=33.44%`, weil die Sperrseite fotografiert wurde |
| 2c | Gate in keiner Settings-Datei verdrahtet | grep über `.claude/settings.json`, `.claude/settings.local.json`, `~/.claude/settings.json` → kein Treffer |
| 2d | Test setzt `GZ_ACTIVE_WORKFLOW` (`test_issue_603_design_fidelity_gate.py:228`) und lässt die ambient gesetzte `OPENSPEC_ACTIVE_WORKFLOW` durch `**os.environ` mitlaufen | Test misst nicht, was er zu messen glaubt |

Vorhanden und nutzbar: 29 Soll-Bilder unter `claude-code-handoff/current/soll/`,
Python-Playwright installiert, `.claude/validator.env` mit `GZ_VALIDATION_URL`,
`GZ_VALIDATOR_USER`, `GZ_VALIDATOR_PASS`.

## Befund 3 — Ansatz: SHA durchreichen, kein Cache

**Vierter Aufrufpfad gefunden:** `staging_gate.py:146`
(`if marker_sha and marker_sha != _head_sha():`) feuert nur, wenn
`read_last_gate_scope()` einen Wert liefert. Im Testrepo ohne Marker-Datei bleibt er
stumm — im echten Betrieb mit vorhandener `.claude/last_gate_scope.json` zählt er mit.
**Der Test misst also weniger als der Fehler groß ist.** Ein Fix, der nur die gemessenen
drei erfasst, behebt den Befund nicht.

**Ansatz (a): SHA einmal ermitteln, als Parameter durchreichen.**
`_scope_diff_base(head: str | None = None)` und
`_detect_committed_scope(expected_commit=None, head=None)`, jeweils
`head = head if head is not None else _head_sha()` am Funktionsanfang; alle internen
Aufrufe inklusive `:146` durch die lokale Variable ersetzen. `write_verdict()` reicht
`head=sha` durch. Default `None` hält Direktaufrufe ohne Argument lauffähig
(`test_fix_1428_preflight_scope_base.py:130,153`, `test_scope_tests_neutral.py:131`).

**Ansatz (b) Cache ist am Code widerlegt, nicht nur riskant:**
`tests/tdd/test_e2e_commit_namespacing.py:104-111` lädt `staging_gate` einmal und ruft
`write_verdict()` zweimal im selben Prozess auf, mit `git checkout` auf einen anderen
Commit dazwischen — und erwartet zwei verschiedene, je korrekte Attestationen. Jeder
Cache über Aufrufgrenzen hinweg bricht diesen Test. Innerhalb **eines**
`write_verdict()`-Laufs ändert sich HEAD nie; genau so weit trägt Ansatz (a).

**Wichtig:** Der Preflight-Zweig (`gate_check():422`) ruft `_detect_committed_scope(expected_commit)`
positional ohne `head` und muss weiterhin frisch rechnen — kein Override.

## Befund 4 — Delegations-Nachweis statt Textsuche

Der Substring-Test bleibt fachlich nötig (er deckt auch `prod_selftest.py` ab, was der
668er-Test nicht tut), muss aber umgebaut werden. Bewertung der fünf direkten
git-Aufrufe einzeln:

| Aufruf | Fundstellen | Urteil |
|---|---|---|
| `cat-file -e` | `staging_gate.py:139,148`, `prod_selftest.py:620,629,638` | **echte Duplikation, 5× über zwei Dateien** → nach `_e2e_paths.commit_exists(sha, repo_dir)` extrahieren |
| `diff --name-only HEAD~1 HEAD` | `staging_gate.py:226-229` | reimplementiert `_e2e_paths._git_diff_names()` (`:147-162`), das dieselbe Datei bei `:480` schon nutzt → **migrieren** |
| `merge-base --is-ancestor` | `staging_gate.py:465` | einzige Fundstelle im Hook-Baum, kein Gegenstück → **bleibt** |
| `rev-parse --verify --quiet <ref>^{commit}` | `staging_gate.py:400` | liefert die volle SHA im stdout (`cat-file -e` kann das nicht), nötig für die #1382-Normalisierung → **bleibt** |

**Ersatztest — Delegations-Zähler:** `_e2e_paths.commit_exists` und
`_e2e_paths._git_diff_names` werden in beiden geladenen Modulen mit einem zählenden
Wrapper versehen (echte Funktion bleibt aktiv, kein Mock), dann die Abläufe gegen ein
reales Temp-Repo gefahren. Behauptung: jede beobachtete `cat-file -e`- bzw.
`diff --name-only`-Ausführung lief über den Zähler. Die Zusicherung wirkt damit an der
Stelle, an der sie gemeint ist (Delegation), statt an einer Textform.
`merge-base`/`rev-parse --verify` bleiben ausdrücklich außerhalb — als Kommentar im Test,
nicht als Verbotsliste.

## Rückfall-Sicherung — kein neues Gate nötig

`.github/workflows/ci.yml:44-50` fährt `tests/tdd/` bei jedem Push/PR gegen `main`.
`test_issue_668_head_sha_dedup.py` steht **nicht** in `.github/ci_tdd_excludes.txt`.
Der `deploy`-Job hängt an `needs: [test, lint]` (`ci.yml:157`) — ein roter Testfall
blockiert also den automatischen Prod-Deploy, nicht nur eine Anzeige. Das reicht als
Ratsche; es genügt, die `xfail`-Decorator zu entfernen.

`touched_tests_gate.py` kann das **nicht** leisten — es prüft bewusst nur `tests/unit/`
(`:126-136`), `tests/tdd/` bleibt dort ausgenommen.

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `.claude/hooks/design_fidelity_diff.py` | MODIFY | Zugangsdaten an den vorgeschalteten Schutz durchreichen; Ordnername aus beiden Variablen auflösen |
| `.claude/hooks/pre_issue_close_design_gate.py` | MODIFY | Workflow-Namen aus beiden Variablen auflösen (wie die Geschwister-Gates) |
| `.claude/settings.json` | MODIFY | Gate als `PreToolUse:Bash` einhängen, in der Fail-open-Form aus Scheibe A |
| `.claude/hooks/staging_gate.py` | MODIFY | SHA durchreichen (4 Aufrufe → 1); `cat-file`/`diff` an gemeinsames Modul delegieren |
| `.claude/hooks/_e2e_paths.py` | MODIFY | `commit_exists(sha, repo_dir)` ergänzen |
| `.claude/hooks/prod_selftest.py` | MODIFY | 3× `cat-file -e` an `commit_exists` delegieren |
| `tests/tdd/test_issue_603_design_fidelity_gate.py` | MODIFY | Umgebung isolieren; beide Variablennamen prüfen; xfail raus |
| `tests/tdd/test_issue_668_head_sha_dedup.py` | MODIFY | xfail raus; Fall mit vorhandenem Marker ergänzen (vierter Pfad) |
| `tests/tdd/test_e2e_path_helper.py` | MODIFY | Substring-Test durch Delegations-Zähler ersetzen |
| `tests/tdd/test_issue_816_alert_deviation.py` | MODIFY | AC-7 auf `ok=False` + Marker „uebersprungen" korrigieren; xfail raus |

## Scope Assessment

- Dateien: 10
- Geschätzte Zeilen: ~180–200 (Limit 250; Doku zählt nicht)
- Risiko: **MEDIUM-HIGH** — `staging_gate.py` entscheidet über Prod-Deploys

## Risks

**Teuerste Regression:** `gate_check()` fällt fälschlich auf `docs-only` oder überspringt
die Attestationsprüfung → Prod deployt ungeprüften Code. Gegenmaßnahme: vor Abschluss
gezielt die bestehenden mockfreien Scope-Tests fahren —
`test_issue_916_gate_scope_marker.py`, `test_issue_1084_gate_scope_cache.py`,
`test_issue_1096_gate_scope_selfpoison.py`, `test_issue_1109_prod_deploy_marker.py`,
`test_issue_1121_git_diff_returncode.py`, `test_fix_1428_preflight_scope_base.py`,
`test_staging_gate.py`, `test_e2e_commit_namespacing.py`,
`test_e2e_verified_retention.py`, `test_staging_gate_verdict_merge.py`.

**Zweitgrößtes Risiko:** Das Scharfschalten des Design-Gates kann das Schließen von
Issues blockieren. Ausweg ohne Lockout: Label `design-compliance` entfernen. Zusätzlich
greift die Fail-open-Form — fehlt die Datei, läuft das Gate still nicht.

**Umsetzungshürde:** `.claude/settings.json` ist Orchestrator-Domäne
(`edit_gate.py:324-334`) — Developer-Agent UND Orchestrierer werden blockiert. Der Eintrag
verlangt ein vom **User getipptes** `override`. Das ist beim Bauen einzuplanen, nicht zu
umgehen.

## Reihenfolge

1. Befund 3 (legt die `head`-Signatur fest)
2. Befund 4 (baut in denselben Funktionen die `cat-file`-Zeilen um)
3. Befund 5 (unabhängig, klein)
4. Befund 2a/2b (Werkzeug reparieren), dann echter Vergleichslauf als Nachweis
5. Befund 2c (einhängen — braucht `override` vom User)
