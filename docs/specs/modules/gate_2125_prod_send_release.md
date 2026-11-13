---
entity_id: gate_2125_prod_send_release
type: module
created: 2026-11-12
updated: 2026-11-12
status: draft
version: "1.0"
tags: [hooks, infrastructure, gate, safety, prod-protection, override]
---

<!-- Issue #2125 — Eigener Notausgang des Prod-Send-Gates (Bezug #1148, #2227) -->

# Gate #2125 — Prod-Versand-Freigabe (eigener Notausgang des Prod-Send-Gates)

## Approval

- [ ] Approved

## Purpose

Der Notausgang des Prod-Send-Gates (#1148) ist wirkungslos: Der Plugin-Befehl `override` schreibt eine Freigabe, die das Gate nie findet (Schreiber loest Worktree auf das Haupt-Repo auf, Leser nicht; Leser schluesselt nach einem Workflow-Namen, der in Hook-Prozessen praktisch nie gesetzt ist). Ausserdem oeffnet das allgemeine `override` zugleich LoC-/Plugin-Gates und den Prod-Versand (Kreuzbindung, #2227). Diese Spec fuehrt einen **eigenen, nur fuer den Prod-Versand geltenden Freigabe-Weg** ein: Der PO tippt die allein stehende Phrase `prod-versand freigeben`; ein projekt-lokaler `UserPromptSubmit`-Hook schreibt eine einmalig gueltige Freigabe, gebunden an die tippende Sitzung (`session_id`), die nur das Prod-Send-Gate liest. Das allgemeine `override` oeffnet das Prod-Send-Gate danach nicht mehr.

## Scope

- **Drin:** eigener Freigabe-Weg nur fuer den Prod-Versand (Phrase `prod-versand freigeben`, projekt-lokaler UserPromptSubmit-Hook, eigene Freigabe-Datei im Haupt-Repo, Bindung an `session_id`, einmalig, 1 h gueltig), Umstellung des Lesers im Prod-Send-Gate, Block-Text, Nachzug Spec #1148 und Gate-Doku.
- **Nicht drin:** siehe `## Nicht-Ziele` (Plugin, LoC-/Plugin-Gates, Blockregel #1148, Testlauf-Gate #2227).

## Source

- **File:** `.claude/hooks/prod_send_release.py` (NEU, UserPromptSubmit-Hook), `.claude/hooks/prod_send_gate.py` (Leser, geaendert), `.claude/hooks/hook_utils.py` (gemeinsame Wurzel-Funktion)
- **Identifier:** `main()` in `prod_send_release.py`; `_has_valid_override(session_id)` und `_block(...)` in `prod_send_gate.py`; gemeinsame Haupt-Repo-Wurzel und Release-Dateipfad in `hook_utils.py`

## Estimated Scope

- **LoC:** ca. +220 / -50
- **Files:** 9 (3 Code, 2 Tests, 4 Konfig/Doku)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Claude-Code-Hook-Eingabe | extern | stdin-JSON: `session_id` + `prompt` (UserPromptSubmit), `session_id` + `tool_input.command` (PreToolUse). Die `session_id` ist beiden Hook-Arten gemeinsam und ersetzt die Workflow-Bindung |
| `.claude/hooks/prod_send_gate.py` | intern | Leser der Freigabe; Blockregel selbst (Spec #1148) bleibt unveraendert |
| `.claude/hooks/hook_utils.py` | intern | Gemeinsame Wurzel-Funktion Worktree -> Haupt-Repo (`.git` ist Datei mit `gitdir:` auf `<main>/.git/worktrees/<n>`), genutzt von Schreiber UND Leser |
| `.claude/prod_send_release.json` | Datei (NEU) | Freigabe-Speicher, nur vom Prod-Send-Gate gelesen; im Haupt-Repo, in `.gitignore` |
| `.claude/settings.json` | Config | Registrierung des neuen Hooks unter `hooks.UserPromptSubmit` neben `context_budget_guard.py` |
| Plugin `agent-os-openspec` | extern | **Keine Abhaengigkeit, kein Import, keine Aenderung.** `user_override_token.json` wird vom Gate nicht mehr gelesen |

## Implementation Details

### Freigabe-Phrase

- Wortlaut: `prod-versand freigeben` (PO-sichtbare Festlegung, Teil dieser Spec-Freigabe).
- Erkennung im Hook `prod_send_release.py`: Prompt trimmen, Kleinschreibung, dann **exakter Vergleich** mit der Phrase. Keine Zusatzwoerter (analog Plugin `OVERRIDE_EXTRA_WORDS = 0`). Ein Satz, der die Phrase enthaelt (`bitte prod-versand freigeben, danke`), oeffnet nichts. Von der Harness eingespeiste Turns (z. B. Hintergrund-Benachrichtigungen, System-Erinnerungen, Task-Meldungen) enthalten die Phrase nicht allein und oeffnen deshalb nichts; Prompts, die mit einem Harness-Marker (`<`-Tag wie `<task-notification>`, `<system-reminder>`) beginnen, werden ausdruecklich ignoriert.
- Einmal erkannt, schreibt der Hook einen Eintrag unter der `session_id` der tippenden Sitzung.

### Freigabe-Datei

- Pfad: `<Haupt-Repo>/.claude/prod_send_release.json`, Format `{"version":1,"releases":{"<session_id>":{"created":"<ISO-8601 UTC mit Zeitzone, z. B. 2026-11-12T20:15:00+00:00>"}}}`.
- Haupt-Repo-Wurzel: eine gemeinsame Funktion in `hook_utils.py` (Worktree -> Haupt-Repo ueber `.git`-Datei/`gitdir:`), von Schreiber UND Leser verwendet. Damit ist die Pfad-Divergenz aus #2125 strukturell ausgeschlossen.
- Atomares Schreiben (`tempfile.mkstemp` + `os.rename`), Rechte 0600.
- Haertung: Ist die Zieldatei ein Symlink (oder wird ein Symlink beim Oeffnen angetroffen, `O_NOFOLLOW`), wird weder geschrieben noch gelesen; der Hook meldet den Fehler sichtbar, das Gate bleibt zu.
- Datei steht in `.gitignore`.

### Leser im Gate

- `_has_valid_override(session_id)` liest nur noch `prod_send_release.json` und nur den Eintrag der eigenen `session_id`. `GZ_ACTIVE_WORKFLOW`/`OPENSPEC_ACTIVE_WORKFLOW`, `user_override_token.json` und die alte Workflow-Auflosung entfallen.
- Gueltig = Eintrag vorhanden, Alter <= 1 h (TTL), Zeitstempel zeitzonenbehaftet gelesen (naive Werte gelten als ungueltig). Bei einem sonst blockierten Prod-Send-Kommando wird der Eintrag atomar entfernt und das Kommando einmalig durchgelassen (Exit 0). Verbrauch nur bei tatsaechlich abgewendetem Block-Treffer (wie Spec #1148).
- Fehlt `session_id` im Hook-Input, gibt es keine gueltige Freigabe (fail-closed).

### Sichtbare Rueckmeldung

- Erfolg: Der Hook antwortet auf stdout mit `{"systemMessage": "..."}` (sichtbar fuer den PO): Prod-Versand ist fuer einen Aufruf in dieser Sitzung bis `<Uhrzeit>` freigegeben.
- Fehler (Schreiben gescheitert, Symlink, Wurzel nicht ermittelbar): sichtbare `systemMessage` mit Fehlertext; keine Freigabe wird geschrieben.
- Der Block-Text des Gates nennt den Weg: Phrase `prod-versand freigeben` allein tippen (nicht mehr "override").

### Registrierung

Neuer Eintrag unter `hooks.UserPromptSubmit` in `.claude/settings.json`: `python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/prod_send_release.py"`, bestehender `context_budget_guard.py`-Eintrag bleibt unberuehrt.

## Expected Behavior

- **Input:** (a) UserPromptSubmit-JSON `{"session_id": ..., "prompt": ...}`; (b) PreToolUse-Bash-JSON `{"session_id": ..., "tool_input": {"command": ...}}`.
- **Output:** (a) Exit 0, bei Phrase/Fehler eine sichtbare `systemMessage` auf stdout; (b) Exit 0 (erlaubt) oder Exit 2 (blockiert, stderr mit Issue-Verweis und neuer Phrase).
- **Side effects:** Beim Tippen der Phrase wird `.claude/prod_send_release.json` im Haupt-Repo atomar um den Eintrag der Sitzung ergaenzt; beim Verbrauch durch das Gate wird der Eintrag atomar entfernt. Sonst keine Zustandsaenderung. Der echte Prod-Versand wird durch Hook oder Tests nie ausgeloest.

## Acceptance Criteria

- **AC-1:** Given eine Sitzung in einem Worktree des Projekts, in der der PO allein die Phrase `prod-versand freigeben` getippt hat / When die gleiche Sitzung danach ein sonst blockiertes Prod-Send-Kommando (z. B. `curl -X POST localhost:8000/api/scheduler/trips/1/send`) ausloest / Then laesst das Prod-Send-Gate genau diesen einen Aufruf durch (Exit 0), und die Freigabe liegt im Haupt-Repo unter `.claude/prod_send_release.json`, nicht im Worktree.
  - Test: Fake-Worktree auf `tmp_path` (`.git`-Datei mit `gitdir:` auf ein Fake-Haupt-Repo), Release-Hook und Gate als Subprozess mit gleicher `session_id`; Exit 0 und Dateiort pruefen.

- **AC-2:** Given eine bereits verbrauchte Freigabe (ein Prod-Send-Aufruf wurde durchgelassen) / When dieselbe Sitzung ein zweites identisches Prod-Send-Kommando ausloest / Then blockiert das Gate wieder mit Exit 2, weil die Freigabe nur fuer genau einen Versand-Aufruf gilt.
  - Test: Phrase einmal, Gate zweimal mit identischem Kommando; erster Exit 0, zweiter Exit 2, Eintrag der Sitzung danach aus der Datei entfernt.

- **AC-3:** Given eine Freigabe, die in Sitzung A getippt wurde / When Sitzung B (andere `session_id`) ein Prod-Send-Kommando ausloest / Then bleibt das Gate fuer B zu (Exit 2) und die Freigabe von A ist danach noch unverbraucht und fuer A weiterhin nutzbar.
  - Test: Eintrag fuer `session_id` A schreiben, Gate mit `session_id` B aufrufen (Exit 2), danach mit A (Exit 0).

- **AC-4:** Given eine Freigabe, deren Zeitstempel aelter als eine Stunde ist / When die tippende Sitzung ein Prod-Send-Kommando ausloest / Then blockiert das Gate mit Exit 2, weil die Freigabe abgelaufen ist.
  - Test: Datei mit `created` = jetzt minus 61 Minuten (UTC, mit Zeitzone) praeparieren, Gate aufrufen, Exit 2 erwarten; Gegenprobe mit minus 59 Minuten Exit 0.

- **AC-5:** Given ein gueltiges allgemeines Plugin-Override in `.claude/user_override_token.json` (fuer beliebigen Workflow-Namen und fuer `__global__`) und gesetzte Workflow-Umgebungsvariablen, aber keine Prod-Versand-Freigabe / When ein sonst blockiertes Prod-Send-Kommando ausgeloest wird / Then bleibt das Gate zu (Exit 2), und die Token-Datei bleibt vom Gate unveraendert.
  - Test: Token wie das Plugin es schreibt (v2-Format) vorbereiten, Gate aufrufen, Exit 2 und unveraenderte Token-Datei pruefen.

- **AC-6:** Given ein Prompt, der die Phrase nur enthaelt, aber nicht allein steht (z. B. `bitte prod-versand freigeben danke`, `prod-versand freigeben und dann senden`, Phrase in einem Satz oder Zitat), oder ein von der Harness eingespeister Turn (beginnt mit `<task-notification>`/`<system-reminder>`) / When der UserPromptSubmit-Hook den Prompt verarbeitet / Then wird keine Freigabe geschrieben und ein folgendes Prod-Send-Kommando derselben Sitzung bleibt blockiert (Exit 2).
  - Test: je Prompt-Variante Release-Hook aufrufen, Datei darf nicht entstehen bzw. keinen Eintrag enthalten; anschliessend Gate Exit 2. Gegenprobe: Gross-/Kleinschreibung und umgebende Leerzeichen der allein stehenden Phrase werden akzeptiert.

- **AC-7:** Given der PO tippt die Phrase / When der Hook die Freigabe schreibt bzw. das Schreiben scheitert (z. B. Zielordner nicht beschreibbar) / Then gibt der Hook im Erfolgsfall eine sichtbare Bestaetigung (`systemMessage` mit Hinweis auf einen freigegebenen Aufruf und die Gueltigkeitsdauer) aus, im Fehlerfall eine sichtbare Fehlermeldung, und im Fehlerfall ist keine Freigabe geschrieben (Gate bleibt zu).
  - Test: Erfolgsfall: stdout-JSON enthaelt `systemMessage` mit Bestaetigung. Fehlerfall: Zielverzeichnis schreibgeschuetzt (oder Wurzel nicht ermittelbar), stdout-JSON enthaelt Fehlertext, Gate danach Exit 2.

- **AC-8:** Given die Freigabe-Datei `.claude/prod_send_release.json` ist ein Symlink auf eine andere Datei / When der Hook die Phrase verarbeitet und wenn das Gate eine Freigabe lesen will / Then schreibt der Hook nichts ueber den Symlink (Ziel der Umlenkung bleibt unveraendert), meldet den Fehler sichtbar, und das Gate bleibt zu (Exit 2), auch wenn das Umlenkungsziel einen gueltigen Eintrag enthaelt.
  - Test: Symlink auf eine Ziel-Datei mit gueltigem Eintrag in `tmp_path` anlegen; Release-Hook aufrufen (Ziel byte-identisch, Fehlermeldung sichtbar), Gate aufrufen (Exit 2).

- **AC-9:** Given ein blockiertes Prod-Send-Kommando ohne Freigabe / When das Gate blockiert / Then nennt der Block-Text auf stderr die neue Phrase `prod-versand freigeben` und verweist weiter auf Issue #1148, und er nennt nicht mehr "override" als Weg.
  - Test: stderr des Gate-Subprozesses auf die Phrase und `#1148` pruefen; Wort "override" als Handlungsanweisung darf nicht enthalten sein.

- **AC-10:** Given eine geschriebene Freigabe / When die Datei gelesen wird / Then traegt der Zeitstempel `created` das Format ISO-8601 in UTC mit ausdruecklicher Zeitzone (`+00:00`), und das Gate wertet ihn zeitzonenbewusst aus; ein Eintrag ohne Zeitzone (naiver Zeitstempel) gilt als ungueltig und oeffnet nichts.
  - Test: Hook-Ausgabe parsen und `datetime.fromisoformat(...).utcoffset() == timedelta(0)` pruefen; Gate mit naivem Zeitstempel im Eintrag aufrufen, Exit 2 erwarten.

- **AC-11:** Given eine Sitzung ohne `session_id` im Hook-Input (leer oder fehlend) / When die Phrase getippt wird oder ein Prod-Send-Kommando ausgeloest wird / Then wird keine Freigabe geschrieben bzw. keine gelesen, und das Prod-Send-Kommando bleibt blockiert (Exit 2), weil eine Freigabe ohne Sitzungsbindung nie gilt.
  - Test: Release-Hook und Gate ohne `session_id` aufrufen; keine Datei-Aenderung, Gate Exit 2.

## Definition of Done

- AC-1 bis AC-11 sind durch die Subprozess-Tests in `tests/tdd/test_issue_2125_prod_send_release.py` nachgewiesen und gruen; der umgestellte Override-Test in `tests/tdd/test_issue_1148_prod_send_gate.py` ist gruen.
- Die Mutations-Gegenprobe des `implementation-validator` findet keine unbewachte Verfaelschung (insbesondere: Wurzel-Aufloesung, `session_id`-Vergleich, Einmal-Verbrauch, TTL, Symlink-Abwehr, Ignorieren von `user_override_token.json`).
- Hook in `.claude/settings.json` registriert, Freigabe-Datei in `.gitignore`, Spec #1148 und `docs/reference/gates_und_ratschen.md` beschreiben den neuen Weg.
- Nach Auslieferung: In einer echten Sitzung bestaetigt die getippte Phrase sichtbar, und ein Gate-Probelauf mit einem nur als Text uebergebenen Prod-Send-Kommando wird einmal durchgelassen und danach wieder blockiert (kein echter Versand).

## Test Plan

Neue Datei `tests/tdd/test_issue_2125_prod_send_release.py`. Alle Tests laufen als **Subprozess** (`python3 .claude/hooks/prod_send_release.py` bzw. `prod_send_gate.py`, stdin-JSON rein, Exit-Code/stdout/stderr raus) mit isoliertem `CLAUDE_PROJECT_DIR` bzw. einem Fake-Worktree auf `tmp_path` (Haupt-Repo mit `.git/worktrees/<n>`, Worktree mit `.git`-Datei `gitdir: ...`). Keine Mocks, kein `patch()`, nie ein echter Prod-Versand: Die Prod-Send-Kommandos werden nur als Text an das Gate gegeben, das nichts ausfuehrt. Zuordnung: AC-1 Worktree-Lage, AC-2 Einmaligkeit, AC-3 fremde Sitzung, AC-4 Ablauf (beide Seiten der Grenze), AC-5 Plugin-Token oeffnet nicht, AC-6 beiläufiger Text/Harness-Turn, AC-7 sichtbare Rueckmeldung, AC-8 Symlink, AC-9 Block-Text, AC-10 Zeitstempel, AC-11 fehlende `session_id`.

Der bestehende Override-Test in `tests/tdd/test_issue_1148_prod_send_gate.py` (AC-3 dort) wird auf den neuen Weg umgestellt (Freigabe per Release-Hook statt Plugin-Token, `session_id` statt Workflow-Env).

## Betroffene Dateien

| Datei | Aenderung | Beschreibung |
|-------|-----------|--------------|
| `.claude/hooks/prod_send_release.py` | CREATE | UserPromptSubmit: Phrase erkennen, Eintrag je `session_id` schreiben, sichtbare Rueckmeldung |
| `.claude/hooks/hook_utils.py` | MODIFY | Gemeinsame Haupt-Repo-Wurzel und Release-Dateipfad |
| `.claude/hooks/prod_send_gate.py` | MODIFY | Override-Leser auf neue Datei/`session_id`, alter Workflow-Reader entfaellt, Block-Text |
| `.claude/settings.json` | MODIFY | Hook-Registrierung UserPromptSubmit |
| `.gitignore` | MODIFY | `.claude/prod_send_release.json` ignorieren |
| `tests/tdd/test_issue_2125_prod_send_release.py` | CREATE | Subprozess-Tests zu AC-1 bis AC-11 |
| `tests/tdd/test_issue_1148_prod_send_gate.py` | MODIFY | Override-Test auf neuen Weg |
| `docs/specs/modules/gate_1148_prod_send_deny.md` | MODIFY | Abschnitt "Override-Mechanik", AC-3, Side effects, Dependencies nachziehen (verweist auf diese Spec) |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Gate-Tabelle (Zeile zum Prod-Send-Gate): neuer Freigabe-Weg statt `override` |

## Nicht-Ziele

- Das Plugin `agent-os-openspec` (Schreiber `phase_listener`, `override_token.py`) wird **nicht** geaendert; Aenderungen dort betreffen alle Projekte.
- LoC-Gate und Plugin-Gates (`edit_gate`, `bash_gate`, `evidence_gate` usw.) lesen weiter `user_override_token.json` und bleiben **unveraendert**; das allgemeine `override` behaelt dort seine Wirkung.
- Die Blockregel des Prod-Send-Gates (Send-Pfade, Prod-Ziele, POST-Indikatoren, SMTP, Obfuskations-Schutz aus Spec #1148) bleibt unveraendert.
- Keine Freigabe per Mehrfachnutzung oder Zeitfenster: genau ein Versand-Aufruf je getippter Phrase.
- Das Testlauf-Gate (#2227) hat keinen Override mehr und ist nicht Teil dieser Aenderung.

## Known Limitations

- Eine Freigabe gilt nur in der Sitzung, in der sie getippt wurde. Wechselt der PO die Sitzung, muss er die Phrase dort erneut tippen.
- Pro getippter Phrase genau ein Versand; bei mehreren unabhaengigen Prod-Versaenden muss die Phrase jeweils neu getippt werden.
- Die Erkennung harness-injizierter Turns stuetzt sich auf den exakten Phrasen-Vergleich (Zusatztext schliesst Treffer aus) plus Marker-Praefix; ein Prompt, der woertlich nur aus der Phrase besteht, gilt als bewusste PO-Eingabe.
- Eine bereits bestehende Datei `.claude/user_override_token.json` bleibt unberuehrt liegen (wird weiter von Plugin-Gates gebraucht).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive Sicherheits-Hook-Aenderung nach dem etablierten Muster projekt-lokaler Hooks (eigener kleiner Reader/Writer, kein Plugin-Import, atomares Schreiben). Keine Aenderung an Domain-Architektur, Datenmodell oder Provider-Schicht. Verworfene Alternativen: (a) nur den Leser reparieren (Wurzel plus Workflow-Name aus Plugin-Zustand) laesst die Kreuzbindung aus #2227 scharf und koppelt an Plugin-Interna; (b) das Plugin aendern (fremdes Repo, betrifft alle Projekte, loest die Sperrenbindung nicht).

## Changelog

- 2026-11-12: Pflicht-Sektionen Scope, Definition of Done, Test Plan ergaenzt (CI-Spec-Gate).
- 2026-11-12: Initial spec erstellt — Issue #2125 (Bezug #1148, #2227). Nachzuziehen: Spec #1148 (Override-Mechanik, AC-3) und `docs/reference/gates_und_ratschen.md`.
- 2026-11-13: Validierung — die Testdatei heißt tatsächlich `tests/tdd/test_prod_send_release.py`; der freigegebene Text nennt noch den Planungsnamen (bewusst nicht geändert, Freigabe-Bindung).
