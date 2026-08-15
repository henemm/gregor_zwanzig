---
entity_id: fix_1866_claim_gate_freigabeweg
type: bugfix
created: 2026-08-15
updated: 2026-08-15
status: draft
workflow: fix-1866-claim-freigabeweg
---

# Datei-Claim-Gate: wirksamer Freigabeweg (`--release`) + Aktivitäts-Verfall

## Approval

- [ ] Approved

## Purpose

Das Datei-Claim-Gate (`.claude/hooks/file_claim_gate.py`) blockiert Edit/Write bei
Kollision mit einer anderen aktiven Session und wirbt in seiner Blockade-Meldung für
`export GZ_FILE_CLAIM_OVERRIDE=1` als Notausgang. Dieser Notausgang ist strukturell
unerreichbar: der Hook läuft als eigener Kindprozess pro `PreToolUse`-Aufruf, ein `export`
in einem Bash-Tool-Aufruf setzt die Variable nur für den Bash-Prozess, nicht für den
nächsten Hook-Lauf. Der einzige tatsächlich wirksame Ort — `.claude/settings.local.json` —
ist durch `edit_gate.py` (Plugin `agent-os-openspec`, nicht dieses Repo) gesperrt. Issue
#1866 dokumentiert den konkreten Auslöser: eine Datei war im belegenden Worktree seit über
einer Stunde bitgleich mit `origin/main` gemergt, der Claim blockierte trotzdem weiter,
weil die reine Zeit-/Worktree-Verfallslogik das nicht erkennt, und der beworbene
Notausgang griff nicht.

Dieser Fix schafft einen tatsächlich wirksamen, nachvollziehbaren Freigabeweg
(`--release`/`--release-session` als CLI-Aufruf außerhalb des Hook-Pfads) und lässt
Claims zusätzlich automatisch verfallen, wenn die beanspruchte Datei im belegenden
Worktree nachweislich unverändert und deckungsgleich mit `origin/main` ist — exakt der im
Issue beschriebene Fall.

## Source

- **File:** `.claude/hooks/file_claim_gate.py`
- **Identifier:** `def main`, neu: `def _handle_release`, `def _handle_release_session`,
  `def _claim_expired_by_activity`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `hook_utils.find_project_root` (Plugin `agent-os-openspec`, `/home/hem/agent-os-openspec/core/hooks`) | Funktion | Hauptrepo-Auflösung — bereits genutzt, keine Änderung |
| `.claude/settings.json` (`PreToolUse`-Hook-Registrierung, Zeilen 109-117) | Konfiguration | Ruft `file_claim_gate.py` ohne Argumente über stdin-JSON auf; der neue `--release`-Pfad läuft davon unabhängig als normaler Bash-Befehl — keine Änderung an dieser Registrierung nötig |
| `bash_gate.py` (Plugin) | Wächter | Bereits geprüft (siehe Kontext-Dokument): ein reiner Skriptaufruf `python3 .claude/hooks/file_claim_gate.py --release <pfad>` ohne `-c`/Redirect hat keinen Schreib-Indikator und läuft ungeblockt durch — keine Änderung nötig |
| `.claude/file_claims.json` | Datei (Registry) | Geteilte Belegungs-Registry im Hauptrepo, worktree-übergreifend sichtbar — Ziel der Lösch-Operation |
| `git worktree list --porcelain`, `git diff`, `git status --porcelain`, `git show origin/main:<pfad>` | externe Befehle | Neu benötigt für den Aktivitäts-Verfall-Check |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `.claude/hooks/file_claim_gate.py` | MODIFY | CLI-Argument-Parsing (`--release <pfad>`, `--release-session <name>`), Release-Logik mit gleichem Locking wie der Hook-Pfad, Aktivitäts-Verfall-Check (`_claim_expired_by_activity`), Einbindung in die bestehende Kollisions-Prüfung, neue Blockade-Meldung |
| `tests/unit/test_file_claim_gate_release.py` | CREATE | Kern-Schicht-Tests für `--release`, `--release-session`, Fehlerfälle (nicht belegt, Registry defekt) |
| `tests/unit/test_file_claim_gate_activity_expiry.py` | CREATE | Kern-Schicht-Tests für den Aktivitäts-Verfall (echtes Temp-Git-Repo + echter `git worktree add`), inkl. Gegenprobe (abweichender Inhalt / lokale Änderung blockiert weiterhin) |

### Estimated Changes
- Files: 3 (1 modifiziert, 2 neu)
- LoC: ca. +90/-10 in `file_claim_gate.py` (CLI-Parsing, Release-Funktionen, Aktivitäts-Check, neue Meldung); Test-LoC zusätzlich, zählt gegen das separate 500er-Test-Budget (CLAUDE.md, Workflow-Tools v3), nicht gegen die 250 Prod-LoC

## Implementation Details

**1. `--release <pfad>` (repo-relativ):**
- Lock auf `file_claims.json.lock` wie im bestehenden Hook-Pfad (`_acquire_lock`), Lock-Timeout unverändert.
- Existiert im geladenen Registry-Dict kein Eintrag für `<pfad>`: klare Meldung auf stdout/stderr ("kein aktiver Claim für `<pfad>`"), Exit-Code so gewählt, dass das Aufrufer-Skript den Fall von einem echten Fehler unterscheiden kann (kein Crash, kein irreführendes "gelöscht").
- Existiert ein Eintrag: vor dem Löschen dessen Inhalt (Session, Branch, `claimed_at`) merken, Eintrag aus dem Dict entfernen, Registry atomar speichern (bestehendes `_save_registry`-Muster: `.tmp` + `replace`), danach die gemerkten Details ausgeben.
- Jeder Fehler (Registry nicht lesbar, kein Lock zu bekommen, Schreibfehler) darf nicht crashen und darf keinen Erfolg vortäuschen — klare Fehlermeldung, von der "kein Claim vorhanden"-Meldung unterscheidbar.

**2. `--release-session <name>`:** gleiches Lock-/Lade-/Speicher-Muster; entfernt alle Registry-Einträge, deren `session`-Feld `<name>` entspricht; meldet die Anzahl und die betroffenen Pfade. Kein Treffer → klare "nichts zu tun"-Meldung, kein Fehler.

**3. Aktivitäts-Verfall (`_claim_expired_by_activity`):** wird zusätzlich zur bestehenden
Prüfung (`still_fresh`, `other_still_active`) in den Kollisionspfad von `main()` eingebaut.
Ein Claim gilt als beendet, wenn ALLE folgenden Bedingungen im belegenden Worktree
(`entry["session"]` als Worktree-Ordnername, aufgelöst über `git worktree list
--porcelain`, analog zu `_worktree_still_exists`) zutreffen:
  - Der aktuelle Inhalt der Datei im belegenden Worktree ist byte-identisch mit dem
    Inhalt derselben Datei in `origin/main` (`git show origin/main:<pfad>` im
    Worktree-Kontext, verglichen gegen die lokale Datei — nicht nur "kein Diff zu HEAD",
    weil ein lokaler Commit ohne Push denselben Effekt hätte).
  - `git status --porcelain -- <pfad>` im belegenden Worktree meldet für genau diesen
    Pfad nichts (kein staged/unstaged/untracked Zustand).

  Sicherheitsrichtung: Jeder Fehler bei diesem Zusatz-Check (Worktree-Pfad nicht
  auflösbar, Git-Befehl schlägt fehl, Timeout, `origin/main` nicht auflösbar) liefert
  `False` (nicht verfallen) — die bestehende Zeit-/Worktree-Logik bleibt dann unverändert
  maßgeblich. Der Check wird NUR ausgewertet, wenn die bestehende Logik den Claim ohnehin
  als aktiv und blockierend einstufen würde (`not same_session and still_fresh and
  other_still_active`) — er lockert nur zusätzlich, verschärft nie.

**4. Neue Blockade-Meldung:** Der bestehende Text ab `"DATEI-CLAIM-GATE ..."` in `main()`
ersetzt den Absatz zu `export GZ_FILE_CLAIM_OVERRIDE=1` durch einen Hinweis auf den
tatsächlich wirksamen Weg: den `--release`-Befehl direkt aufrufen (mit Pfad-Platzhalter,
analog zum bisherigen Stil). Die `OVERRIDE_ENV`-Prüfung im Code (`os.environ.get(...) ==
"1"`) bleibt unverändert bestehen (schadet nicht) — nur die Meldung darf sie nicht mehr
als DEN Ausweg bewerben.

## Expected Behavior

- **Input:** CLI-Aufruf `python3 .claude/hooks/file_claim_gate.py --release <pfad>` bzw.
  `--release-session <name>`, ausgeführt aus einer beliebigen Session/einem beliebigen
  Worktree heraus; alternativ der bestehende stdin-JSON-Hook-Aufruf ohne Argumente.
- **Output:** Bei `--release`/`--release-session`: Klartext-Meldung mit den Details der
  gelöschten Belegung (oder klare "nichts zu tun"-Meldung). Bei blockierendem Kollisions-Fall:
  neue Meldung mit `--release`-Hinweis statt `export`-Hinweis.
- **Side effects:** `.claude/file_claims.json` wird bei `--release`/`--release-session`
  verändert (Eintrag/Einträge entfernt); bei Aktivitäts-Verfall wird der bestehende
  Kollisions-Eintrag NICHT automatisch aus der Registry gelöscht (nur die Blockade
  entfällt für diesen Aufruf) — die nächste `main()`-Ausführung schreibt ohnehin einen
  frischen Eintrag für die aufrufende Session.

## Acceptance Criteria

- **AC-1:** Given ein Registry-Eintrag für `<pfad>` existiert (Session A, Branch B,
  `claimed_at` T) / When `python3 .claude/hooks/file_claim_gate.py --release <pfad>`
  aufgerufen wird / Then ist der Eintrag aus `file_claims.json` entfernt UND die Ausgabe
  nennt Session A, Branch B und `claimed_at` T.
  - Test: `tests/unit/test_file_claim_gate_release.py` — echte temporäre
    `file_claims.json` mit einem vorbereiteten Eintrag anlegen, Skript per `subprocess.run`
    mit `--release <pfad>` aufrufen (nicht die interne Funktion importieren und mocken),
    danach die Registry-Datei erneut laden und prüfen, dass der Schlüssel fehlt, UND die
    stdout/stderr-Ausgabe auf die drei Detail-Werte prüfen.

- **AC-2:** Given `<pfad>` hat KEINEN Registry-Eintrag / When `--release <pfad>`
  aufgerufen wird / Then bricht der Aufruf nicht mit Exception/Traceback ab UND die
  Ausgabe unterscheidet sich erkennbar von der Erfolgsmeldung aus AC-1 (kein
  irreführendes "gelöscht").
  - Test: `tests/unit/test_file_claim_gate_release.py` — Aufruf gegen eine leere bzw.
    Registry ohne den fraglichen Schlüssel, Exit-Code und Ausgabetext prüfen.

- **AC-3:** Given zwei Registry-Einträge mit `session=X` und ein dritter mit
  `session=Y` / When `--release-session X` aufgerufen wird / Then sind genau die beiden
  `X`-Einträge aus `file_claims.json` entfernt UND der `Y`-Eintrag ist unverändert
  vorhanden.
  - Test: `tests/unit/test_file_claim_gate_release.py` — Registry mit drei Einträgen
    vorbereiten, Aufruf, Registry danach laden und Schlüsselmenge vergleichen.

- **AC-4:** Given ein Hauptrepo mit Commit auf `origin/main`, ein per `git worktree add`
  angelegter Worktree (Session-Name = Worktree-Ordnername) mit einem Registry-Eintrag für
  eine Datei, deren Inhalt im Worktree byte-identisch mit `origin/main` ist und für die
  `git status --porcelain` im Worktree nichts meldet, UND der Eintrag ist nach der
  bestehenden Zeit-/Worktree-Logik noch "frisch" und der Worktree existiert noch / When
  eine andere Session denselben Pfad editiert (stdin-JSON-Hook-Aufruf ohne Argumente) /
  Then blockiert der Aufruf NICHT (Exit 0, keine Kollisionsmeldung) — Reproduktion des
  Auslöser-Falls aus Issue #1866.
  - Test: `tests/unit/test_file_claim_gate_activity_expiry.py` — echtes Temp-Git-Repo,
    echter Commit, echter `git worktree add`-Linked-Worktree (Vorbild:
    `tests/tdd/test_validator_log_shared_repo_path.py`, Funktion
    `_setup_main_with_worktree`); KEIN Mock von Git-Befehlen oder der Registry-Datei.

- **AC-5 (Gegenprobe zu AC-4):** Given denselben Aufbau wie AC-4, ABER die Datei im
  belegenden Worktree weicht entweder inhaltlich von `origin/main` ab ODER hat eine
  lokale (unstaged/staged/untracked) Änderung für genau diesen Pfad / When eine andere
  Session denselben Pfad editiert / Then blockiert der Aufruf weiterhin (Exit 2,
  bestehende Kollisionsmeldung) — belegt, dass der Aktivitäts-Check nicht zu weit greift.
  - Test: `tests/unit/test_file_claim_gate_activity_expiry.py` — zwei Varianten: (a)
    Datei im Worktree lokal verändert und nicht committet, (b) Datei im Worktree
    committet, aber `origin/main` zeigt eine ältere/andere Fassung (kein Push).

- **AC-6:** Given die bestehende Kollision (Session A blockiert Session B, weder
  zeitlich noch per Aktivität verfallen) / When die Blockade-Meldung ausgegeben wird /
  Then enthält sie einen konkreten Hinweis auf `--release <pfad>` als Ausweg UND wirbt
  NICHT mehr für `export GZ_FILE_CLAIM_OVERRIDE=1` als DEN wirksamen Weg (die Env-Var
  darf im Code weiter geprüft werden, aber die Meldung darf sie nicht mehr als
  Haupt-Ausweg nennen).
  - Test: `tests/unit/test_file_claim_gate_release.py` — echten Kollisionsfall (zwei
    unterschiedliche Sessions, frischer Claim, Worktree existiert) über stdin-JSON
    auslösen, stderr-Text auf Vorkommen von `--release` UND auf Nicht-Vorkommen von
    `GZ_FILE_CLAIM_OVERRIDE` als beworbenem Ausweg prüfen (Text-Assertion auf
    Verhaltens-Output des Prozesses, kein Dateiinhalt-Check des Quellcodes).

## Known Limitations

- **`edit_gate.py` (Vorschlag 3 aus Issue #1866) wird bewusst NICHT angefasst.** Das
  liegt im Plugin-Repo `agent-os-openspec`, nicht in `gregor_zwanzig` — Änderungen dort
  würden alle Repos betreffen, die dieses Plugin nutzen, und liegen außerhalb des
  Zuschnitts dieses Fixes. Zusätzlich wird die Differenzierung durch Vorschlag 1
  überflüssig: der Freigabeweg führt nach diesem Fix über `--release`, nicht mehr über
  eine Änderung an `.claude/settings.local.json`, die `edit_gate.py` ohnehin sperrt.
- **`--release` hat keinen Zugriffsschutz:** jede Session kann jede fremde Belegung
  lösen. Das ist beabsichtigt (Zweck ist genau die Behebung von Fehlbelegungen), die
  Nachvollziehbarkeit entsteht ausschließlich über die ausführliche Ausgabe (Session,
  Branch, Zeitpunkt) — es gibt keine Protokollierung darüber hinaus (kein Audit-Log).
- **Aktivitäts-Verfall prüft nur den EINEN beanspruchten Pfad**, nicht den gesamten
  Worktree-Zustand — eine Datei kann verfallen, während der Worktree insgesamt noch
  aktiv an anderen Dateien arbeitet. Das ist beabsichtigt: die Granularität des Gates
  ist ohnehin "eine Datei" (siehe Docstring des bestehenden Codes), der Verfall folgt
  derselben Granularität.
- **`git show origin/main:<pfad>` setzt einen aktuellen `origin/main`-Stand voraus** (d.h.
  ein vorheriges `git fetch`); ist der lokale `origin/main`-Tracking-Branch veraltet, kann
  der Aktivitäts-Check fälschlich "nicht identisch" ergeben (fail-closed, also die
  sicherere Richtung) statt fälschlich freizugeben — das ist im Sinne der geforderten
  Sicherheitsrichtung akzeptabel, aber ein bekanntes Verhalten, kein Fehler.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Das Datei-Claim-Gate ist ein internes Tooling-Gate (Workflow-Absicherung
  zwischen parallelen Claude-Sessions), keine der in `docs/adr/README.md` genannten
  Entscheidungsflächen (Kanal/Provider/Framework, Datenmodell/Persistenz-Prinzip,
  Test-/Deploy-Strategie, bewusste Produktgrenze). Es handelt sich um eine lokale
  Implementierungsentscheidung im Sinne des ADR-Leitfadens ("Kleine, lokale
  Implementierungsentscheidungen gehören nicht hierher"). Das Gate selbst trägt bereits
  ein eigenes Regel-Budget-Prüfdatum (2026-11-11, unverändert durch diesen Fix).

## Changelog

- 2026-08-15: Initial spec created
