---
entity_id: fix_1307b_gates
type: module
created: 2026-08-05
updated: 2026-08-05
status: draft
version: "1.0"
tags: [gate, tooling, staging-gate, design-gate, mail-validator]
---

# Spec: #1307 Scheibe B — vier Wächter, die nicht tun was sie behaupten

- **Issue:** #1307, Befunde 2 bis 5
- **Workflow:** `fix-1307b-gates`
- **Kontext & Messungen:** `docs/context/fix-1307b-gates.md`

## Approval

- [x] Approved

Status: **Freigegeben durch PO am 2026-08-05** („go" auf alle 17 Acceptance Criteria).

## Purpose

Vier Prüfungen, die heute etwas anderes behaupten als sie leisten, sagen danach die
Wahrheit: eine misst wieder den echten Fehler, eine prüft Verhalten statt Text, eine
widerspricht sich nicht länger selbst, und eine läuft überhaupt zum ersten Mal.

## Warum

Der schriftliche Stand dieses Issues war dreimal falsch, weil er aus dem Code gelesen
statt gemessen wurde. Gemessen (`--runxfail`, 2026-08-05) sind alle vier Befunde offen.

Der gemeinsame Nenner ist nicht „vier kaputte Wächter", sondern **eine Regel, die dasteht
und nicht beißt** — dieselbe Krankheit wie in Scheibe A, wo aus fünf ungeschützten
Einträgen unbemerkt acht wurden. Befund 3 belegt das am härtesten: Er war im Juni bereits
behoben (#668, `3ef67003`, Adversary VERIFIED) und ist zurückgekommen, weil der
zugehörige Test als „bekannt offen" markiert und deshalb grün war.

## Source

| Datei | Rolle | Änderung |
|---|---|---|
| `.claude/hooks/staging_gate.py` | Prüfling Befund 3+4 | `_head_sha()` `:95`; Aufrufer `:135`, `:146`, `:174`, `:252`; direkte git-Aufrufe `:139`, `:148`, `:226`, `:400`, `:465` |
| `.claude/hooks/_e2e_paths.py` | gemeinsames Modul | `head_sha()` `:220-230`; neu: `commit_exists(sha, repo_dir)` |
| `.claude/hooks/prod_selftest.py` | Prüfling Befund 4 | `cat-file -e` bei `:620`, `:629`, `:638` |
| `.claude/hooks/briefing_mail_validator.py` | Prüfling Befund 5 | Typ-Weiche `:493-523`, Protokoll-Marker `:638-648` |
| `.claude/hooks/pre_issue_close_design_gate.py` | Prüfling Befund 2 | Workflow-Auflösung `:50`, Blockade `:72` |
| `.claude/hooks/design_fidelity_diff.py` | Werkzeug Befund 2 | Ordnername `:271`, Playwright-Kontext `:174-186` |
| `.claude/settings.json` | Verdrahtung | neuer `PreToolUse:Bash`-Eintrag |
| `tests/tdd/test_issue_603_design_fidelity_gate.py` | Prüfung Befund 2 | veraltete Variable `:228`, xfail `:173` |
| `tests/tdd/test_issue_668_head_sha_dedup.py` | Prüfung Befund 3 | PATH-Shim `:61-74`, xfail `:103`, `:122` |
| `tests/tdd/test_e2e_path_helper.py` | Prüfung Befund 4 | Substring-Test `:182` |
| `tests/tdd/test_issue_816_alert_deviation.py` | Prüfung Befund 5 | AC-7 `:611-628`, xfail `:598` |

**Unverändert, aber maßgeblich:** `tests/tdd/test_briefing_validator_noop_not_pass.py`
(hält den Beschluss aus #1282), `tests/tdd/test_e2e_commit_namespacing.py:104-111`
(widerlegt die Zwischenspeicher-Variante).

## Estimated Scope

- Dateien: 11
- Geschätzte Zeilen: ~180–200 (Limit 250; Dokumentation zählt nicht)
- Risiko: **MEDIUM-HIGH** — `staging_gate.py` entscheidet über Prod-Deploys
- Kein Produktions-Runtime-Code → Doku-/Tooling-Ausnahme, kein Staging-/Prod-Schritt
  (der Vergleichslauf gegen Staging ist ein **Lesezugriff**, kein Deploy)

## Dependencies

**Woran die geänderten Teile hängen (upstream):**
- `staging_gate.py` und `prod_selftest.py` beziehen Pfad- und Stand-Ermittlung aus
  `_e2e_paths.py`.
- `briefing_mail_validator.py` schreibt sein Protokoll über `_validator_log.py`.
- `design_fidelity_diff.py` braucht Python-Playwright, die 29 Soll-Bilder unter
  `claude-code-handoff/current/soll/` und die Zugangsdaten aus `.claude/validator.env`.

**Was von den geänderten Teilen abhängt (downstream):**
- `renderer_mail_gate.py` liest die Protokolle des Mail-Prüfers und entscheidet daran
  über Commits.
- `deploy-gregor-prod.sh` und der Post-Deploy-Selbsttest hängen am Urteil des
  Staging-Wächters. Eine Fehlentscheidung dort deployt ungeprüften Code nach Produktion.
- Die Nachweis-Ablage `.claude/e2e_verified/<sha>.json` wird von Deploy-Gate und
  Selbsttest gelesen.
- Der Prüflauf bei jeder Änderung (`.github/workflows/ci.yml:44-50`) fährt `tests/tdd/`;
  der Deploy-Schritt hängt an dessen Ergebnis (`ci.yml:157`).

## PO-Entscheidungen (2026-08-05)

1. Der Design-Wächter wird **eingehängt und scharf geschaltet** — nicht nur die Prüfung
   nachgezogen.
2. Beim Mail-Prüfer gilt **#1282**: „übersprungen ist kein bestanden" bleibt. Der
   widersprechende AC-7-Test aus #816 wird korrigiert.
3. Der Bildvergleich wird **wirklich gefahren**, nicht umgangen.

## Ausgangsstand (gemessen, nicht gelesen)

| Befund | Testfall | heute |
|---|---|---|
| 2 | `test_issue_603_design_fidelity_gate.py::…::test_gate_allows_close_with_pass_artefact` | rot |
| 3 | `test_issue_668_head_sha_dedup.py::test_ac1_head_sha_called_once_without_override` | rot |
| 3 | `test_issue_668_head_sha_dedup.py::test_ac3_override_path_still_works` | rot |
| 4 | `test_e2e_path_helper.py::…::test_path_logic_only_in_shared_module` | rot |
| 5 | `test_issue_816_alert_deviation.py::test_ac7_header_set_and_validator_noop` | rot |

Zusätzlich gemessen: `git rev-parse HEAD` läuft **3×** statt 1× pro `write_verdict()`;
ein **vierter** Aufrufpfad (`staging_gate.py:146`) schweigt im Test nur, weil das Testrepo
keine Marker-Datei hat. Der Design-Wächter ist in **keiner** Settings-Datei verdrahtet.
Das Vergleichswerkzeug scheitert am vorgeschalteten Staging-Zugangsschutz
(`/login` → 401, `WWW-Authenticate: Basic realm="Staging"`) und fotografiert die
Sperrseite (`diff_pct=33.44%`).

## Implementation Details

**Befund 3 — Stand einmal ermitteln, durchreichen.**
`_scope_diff_base(head: str | None = None)` und
`_detect_committed_scope(expected_commit=None, head=None)`; jeweils am Funktionsanfang
`head = head if head is not None else _head_sha()`, danach **alle** internen Aufrufe
inklusive `:146` durch die lokale Variable ersetzen. `write_verdict()` reicht `head=sha`
durch. Default `None` hält Direktaufrufe ohne Argument lauffähig.

**Zwischenspeicher ist ausgeschlossen, nicht bloß unerwünscht:**
`tests/tdd/test_e2e_commit_namespacing.py:104-111` lädt das Modul einmal, ruft
`write_verdict()` zweimal auf und stellt dazwischen per `git checkout` einen anderen
Commit ein — beide Aufrufe müssen je den eigenen Stand schreiben. Jeder Speicher über
Aufrufgrenzen bricht das.

**Befund 4 — gemeinsame Stelle statt Wiederholung.**
Neue Funktion `_e2e_paths.commit_exists(sha, repo_dir) -> bool`, eingesetzt an allen fünf
Fundstellen (`staging_gate.py:139`, `:148`; `prod_selftest.py:620`, `:629`, `:638`).
`_telegram_live_gate()` (`staging_gate.py:226-229`) wechselt auf
`_e2e_paths._git_diff_names()` — dieselbe Datei nutzt das bei `:480` bereits.

**Befund 5 — Erwartung an den Beschluss angleichen.**
AC-7 in `test_issue_816_alert_deviation.py` prüft künftig „kein Bestehen, begründet als
unzuständig" statt „Bestehen". Der Produktivcode bleibt unverändert.

**Befund 2 — drei Reparaturen, dann scharf schalten.**
(a) `design_fidelity_diff.py:271` löst den Ordnernamen aus **beiden** Variablennamen auf;
(b) `new_context()` bekommt die Zugangsdaten für den vorgeschalteten Schutz mit;
(c) `pre_issue_close_design_gate.py:50` bekommt dieselbe Fallback-Kette wie seine
Geschwister (`prod_send_gate.py:305-309`); (d) Eintrag in `.claude/settings.json` in der
abgesicherten Form.

## Expected Behavior

**Vorher → Nachher:**

| Vorgang | heute | danach |
|---|---|---|
| `write_verdict()` einmal ausführen | 3–4 Abfragen des Commit-Stands | genau 1 |
| Doppelte Logik aufspüren | Wortsuche, trifft eine harmlose Zeile, umgehbar | Mitzählen an der gemeinsamen Stelle |
| Mail-Prüfer sieht `deviation-alert` | zwei Prüfungen fordern Gegenteiliges | eine klare Aussage: kein Bestehen, als unzuständig begründet |
| Design-Issue schließen | Wächter läuft nie | blockiert ohne Nachweis, lässt mit Nachweis durch |
| Vergleichswerkzeug | fotografiert die Zugangssperre | nimmt die angeforderte Seite auf |

## Test Plan

Zuordnung der Kriterien zu Prüfungen. Alle deterministisch (Kern-Schicht), kein Netz außer
dem ausdrücklich benannten Staging-Lesezugriff bei AC-11.

| AC | Prüfung | Art |
|---|---|---|
| AC-1, AC-2 | `tests/tdd/test_issue_668_head_sha_dedup.py` | Zählung echter Subprozesse per Ersatzskript im Suchpfad; AC-1 **neu** mit vorhandener Marker-Datei (deckt den vierten Pfad) |
| AC-3 | `tests/tdd/test_e2e_commit_namespacing.py` (bestehend) | zwei Aufrufe im selben Prozess mit Stand-Wechsel |
| AC-4 | `tests/tdd/test_fix_1428_preflight_scope_base.py` (bestehend) | Preflight rechnet frisch |
| AC-5, AC-7 | `tests/tdd/test_e2e_path_helper.py` | **Ersatz** des Substring-Tests durch Delegations-Zähler gegen echtes Temp-Repo |
| AC-6 | Mutations-Gegenprobe im Adversary-Lauf | direkter Aufruf wieder eingebaut ⇒ Prüfung muss rot werden; Umbenennung allein darf nicht grün lassen |
| AC-8, AC-9 | `tests/tdd/test_issue_816_alert_deviation.py` (AC-7 korrigiert) | Rückgabe und Protokoll-Marker |
| AC-10 | `tests/tdd/test_briefing_validator_noop_not_pass.py` (bestehend) | bleibt grün |
| AC-11, AC-12 | echter Lauf `design_fidelity_diff.py --screen …` gegen Staging | Nachweis am Lauf, keine Nachbildung; Bericht im erwarteten Ordner |
| AC-13, AC-14 | `tests/tdd/test_issue_603_design_fidelity_gate.py` | beide Richtungen; Umgebung im Test selbst gesetzt und bereinigt |
| AC-15 | `tests/tdd/test_issue_384_hook_fail_open.py` (bestehend, seit Scheibe A scharf) | der neue Eintrag muss die abgesicherte Form tragen |
| AC-16 | Lauf ohne `--runxfail` über alle vier Dateien | alle grün, keine Markierungen mehr vorhanden |
| AC-17 | Regressionsumfang (s.u.) | Umfangs-Erkennung unverändert |

**Regressionsumfang vor Abschluss (mockfrei, bestehend):**
`test_issue_916_gate_scope_marker.py`, `test_issue_1084_gate_scope_cache.py`,
`test_issue_1096_gate_scope_selfpoison.py`, `test_issue_1109_prod_deploy_marker.py`,
`test_issue_1121_git_diff_returncode.py`, `test_fix_1428_preflight_scope_base.py`,
`test_staging_gate.py`, `test_e2e_commit_namespacing.py`,
`test_e2e_verified_retention.py`, `test_staging_gate_verdict_merge.py`.

## Acceptance Criteria

### Befund 3 — der Commit-Stand wird einmal ermittelt

**AC-1:** Given ein echtes Repo, in dem eine Marker-Datei `.claude/last_gate_scope.json`
bereits vorliegt, When `staging_gate.write_verdict()` ohne Pfad-Übergabe läuft, Then wird
`git rev-parse HEAD` **genau einmal** als echter Subprozess ausgeführt, gezählt über ein
vorgeschaltetes `git`-Ersatzskript im Suchpfad — nicht über einen Mock.

**AC-2:** Given dasselbe Repo, When `write_verdict()` mit ausdrücklich übergebenem
Nachweis-Pfad läuft, Then wird `git rev-parse HEAD` ebenfalls genau einmal ausgeführt.

**AC-3:** Given ein Prozess, der `write_verdict()` zweimal aufruft und zwischen den beiden
Aufrufen den Stand des Repos auf einen anderen Commit umstellt, When beide Aufrufe
durchlaufen, Then schreibt jeder Aufruf den Nachweis für **seinen eigenen** Commit — ein
zwischengespeicherter Wert aus dem ersten Aufruf darf den zweiten nicht verfälschen.

**AC-4:** Given der Preflight-Zweig mit vorgegebenem Ziel-Commit, When er läuft, Then
ermittelt er den Umfang weiterhin frisch und übernimmt **keinen** von außen gereichten
Commit-Stand — die bisherige Bedeutung bleibt unverändert.

### Befund 4 — Delegation wird an ihrer Wirkung geprüft, nicht am Wortlaut

**AC-5:** Given `staging_gate` und `prod_selftest` laufen gegen ein echtes Repo im
Temp-Verzeichnis, When einer ihrer Abläufe prüft, ob ein Commit existiert, oder ermittelt,
welche Dateien sich zwischen zwei Ständen geändert haben, Then läuft **jede** dieser
Ermittlungen über die gemeinsame Stelle — nachgewiesen durch Mitzählen an der gemeinsamen
Funktion, während die echte Funktion weiterarbeitet.

**AC-6:** Given jemand baut an einer der bisherigen Stellen wieder einen direkten
`git cat-file -e`-Aufruf ein, statt die gemeinsame Stelle zu benutzen, When die Prüfung
läuft, Then wird sie rot. Ein Umbau, der lediglich die Schreibweise ändert (etwa den
Kommandonamen aus Teilstücken zusammensetzt), darf sie **nicht** grün lassen.

**AC-7:** Given die beiden Aufrufe, die bewusst eigenständig bleiben
(`merge-base --is-ancestor` und `rev-parse --verify` zur Auflösung eines übergebenen
Verweises), When die Prüfung läuft, Then schlägt sie deswegen **nicht** an, und der Grund
steht als Kommentar an der Stelle.

### Befund 5 — „übersprungen" bleibt vom „bestanden" unterscheidbar

**AC-8:** Given eine Mail mit der Kennzeichnung `X-GZ-Mail-Type: deviation-alert`, When
der Briefing-Mail-Prüfer sie bewertet, Then meldet er **kein** Bestehen und begründet es
mit einem Eintrag, der ihn als unzuständig ausweist — damit kein nachgelagertes Gate
diesen Leerlauf als echten Nachweis wertet.

**AC-9:** Given derselbe Vorgang, When das Prüfprotokoll geschrieben wird, Then trägt es
„nicht bestanden" **und** „übersprungen" — die beiden Zustände bleiben getrennt lesbar.

**AC-10:** Given die bestehenden Prüfungen aus #1282, When sie nach der Änderung laufen,
Then bleiben sie grün — die neue Formulierung ersetzt den Widerspruch, sie dreht ihn nicht
auf die andere Seite.

### Befund 2 — der Design-Wächter läuft, und er ist bestehbar

**AC-11:** Given das Vergleichswerkzeug läuft gegen Staging, When es die angeforderte
Seite aufnimmt, Then kommt es am vorgeschalteten Zugangsschutz vorbei und meldet **keinen**
Anmeldefehler mehr — nachgewiesen an einem echten Lauf, nicht an einer Nachbildung.

**AC-12:** Given dasselbe Werkzeug, When es seinen Bericht ablegt, Then landet dieser in
genau dem Ordner, in dem der Wächter danach sucht — auch wenn nur die ältere Schreibweise
der Workflow-Kennung gesetzt ist.

**AC-13:** Given ein Issue mit dem Design-Kennzeichen und ein bestandener Bericht im
zugehörigen Ordner, When das Schließen des Issues versucht wird, Then lässt der Wächter es
durch. Given derselbe Fall **ohne** bestandenen Bericht, Then blockiert er und benennt,
was fehlt.

**AC-14:** Given die Prüfung zu AC-13, When sie läuft, Then setzt sie ihre Umgebung selbst
und lässt keine von außen gesetzte Workflow-Kennung durchschlagen — sie muss messen, was
sie zu messen behauptet.

**AC-15:** Given der Wächter ist in der Hook-Verdrahtung eingetragen, When die Datei
einmal fehlt (etwa weil ein anderer Arbeitsordner hinterherhängt), Then blockiert er
**nichts**, sondern läuft still nicht — die abgesicherte Form aus Scheibe A
(`if [ -f … ]; then …; fi`, niemals `&&`/`||`).

### Übergreifend

**AC-16:** Given alle fünf eingangs roten Testfälle, When sie ohne die „bekannt
offen"-Markierung laufen, Then sind sie grün, und die Markierungen sind aus den Dateien
entfernt — eine Regel, die weiterhin nicht beißt, gilt als nicht erfüllt.

**AC-17:** Given die bestehenden Prüfungen rund um die Umfangs-Erkennung des
Staging-Wächters, When sie nach der Änderung laufen, Then bleiben sie grün — insbesondere
darf der Wächter nicht fälschlich auf „nur Dokumentation" fallen oder die Nachweisprüfung
überspringen.

## Was sich NICHT ändern darf

- Die Bedeutung des Staging-Wächters bei der Entscheidung über einen Prod-Deploy. Die
  teuerste denkbare Regression ist ein Wächter, der ungeprüften Code durchlässt.
- Der Beschluss aus #1282: ein Leerlauf des Mail-Prüfers darf nie als Nachweis zählen.
- Die Nachweis-Ablage `.claude/e2e_verified/<sha>.json` und ihr Format.
- Direktaufrufe der geänderten Funktionen ohne Argumente müssen weiter laufen
  (bestehende Prüfungen rufen sie so auf).

## Known Limitations

**Nicht in dieser Scheibe:**
- **Ob der Bildvergleich fachlich besteht.** Diese Scheibe stellt sicher, dass das
  Werkzeug die richtige Seite aufnimmt und der Wächter den Bericht findet. Ob das aktuelle
  Design nah genug am Soll-Bild liegt, ist eine Design-Frage, keine Werkzeug-Frage.
- **Die anderen 28 Soll-Bilder.** Ein Bildschirm als Nachweis genügt.
- **Befund 1** — mit Scheibe A erledigt (`cf33590a`).
- **#1478** (Scheibe C) — liegt im Fremd-Repo `agent-os-openspec`.
- Die Nutzer-Ebene `~/.claude/settings.json` und `.claude/settings.local.json` — in #1196
  gebucht.

**Bewusste Grenzen des Delegations-Zählers (AC-5):** Er deckt Commit-Existenz und
Datei-Diff ab. `merge-base --is-ancestor` und `rev-parse --verify` bleiben außerhalb, weil
es dafür kein Gegenstück im gemeinsamen Modul gibt. Ein künftiger dritter Aufrufer, der
eine ganz neue git-Operation dupliziert, wird von dieser Prüfung nicht gefangen.

## Regel-Budget

Das Scharfschalten des Design-Wächters führt eine **wirksame** Pflicht neu ein (bisher lief
sie nie). Nach der Regel-Budget-Vorgabe trägt sie ein **Prüfdatum: 2026-11-03**. Bis dahin
muss ein belegter Fang vorliegen — ein Fall, in dem der Wächter ein Schließen ohne
Design-Nachweis verhindert hat. Sonst Rückbau.

Ausweg ohne Steckenbleiben: das Design-Kennzeichen von der Aufgabe nehmen. Zusätzlich
greift die Fail-open-Form.

Der Ersatz des Substring-Tests (Befund 4) ist **keine neue Regel**, sondern die Reparatur
einer bestehenden — kein zusätzliches Prüfdatum nötig.

## Architektur-Entscheidung (ADR)

**Kein neues ADR erforderlich.** Die beiden Richtungsentscheidungen wenden bestehende,
dokumentierte Muster an:

- „Frage umdrehen statt Formen jagen" (Befund 4) — belegt in #1431, #1471 und
  #1307 Scheibe A, festgehalten in `CLAUDE.md` und
  `docs/context/fix-1307b-gates.md`.
- „No-Op ist kein Pass" (Befund 5) — Beschluss aus #1282, hier bestätigt statt geändert.

Berührt wird die Entscheidungsfläche **Teststrategie**; da die Scheibe das dokumentierte
Muster anwendet und nicht davon abweicht, entsteht kein ADR-Pflichtfall.

## Umsetzungshürde

`.claude/settings.json` ist Orchestrator-Domäne (`edit_gate.py:324-334`) — sowohl der
Developer-Agent als auch der Orchestrierer werden dort blockiert. Der Eintrag verlangt ein
vom **User getipptes** `override`. Das ist einzuplanen, nicht zu umgehen.

## Reihenfolge

1. Befund 3 — legt die Signatur fest, über die der Commit-Stand durchgereicht wird
2. Befund 4 — baut in denselben Funktionen die Existenzprüfungen um
3. Befund 5 — unabhängig, klein
4. Befund 2a/2b — Werkzeug reparieren, dann echter Vergleichslauf als Nachweis
5. Befund 2c — einhängen (braucht `override`)

## Changelog

| Datum | Version | Änderung |
|---|---|---|
| 2026-08-05 | 1.0 | Erstfassung. Ausgangsstand aller vier Befunde gemessen statt gelesen (`--runxfail`). Befund 2 dabei als dreiteilig erkannt (Ordner-Bruch, Zugangsschutz, fehlende Verdrahtung), vierter Abfragepfad bei Befund 3 gefunden, Zwischenspeicher-Variante am Code widerlegt. PO-Entscheidungen: Design-Wächter scharf schalten, #1282 gilt beim Mail-Prüfer, Bildvergleich wirklich fahren. |
