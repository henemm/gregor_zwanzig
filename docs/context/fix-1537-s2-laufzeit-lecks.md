# Context: fix-1537-s2-laufzeit-lecks

**Issue:** #1537 (Scheibe 2) · verwandt: #1535, #1380, henemm-security #199
**Erstellt:** 2026-08-07

## Request Summary

Scheibe 1 von #1537 schützt nur einen einzigen Austrittsweg: vorgemerkte Dateien beim
Einchecken. Scheibe 2 schließt die beiden bewusst offen gelassenen Wege — **Stufe A**:
Werte, die erst zur Laufzeit aus der `.env` in eine andere Datei wandern (ein Skript liest,
ein Skript schreibt; im Werkzeug-Aufruf steht der Wert nie). **Stufe B**: Werte, die in einer
Werkzeug-**Ausgabe** zurückkommen (`PreToolUse` prüft vor der Ausführung und sieht sie nicht).
Dazu die Nebenbefunde F008/F009 am bestehenden Wächter.

## Ausgangslage (gemessen 2026-08-07, nicht übernommen)

| Zugang | Treffer des **heutigen** Werts in der öffentlichen Historie |
|---|---|
| `GZ_AUTH_PASS` | 0 — erneuert |
| `GZ_SMTP_PASS` | 3 Commits — unverändert kompromittiert |
| `GZ_TEST_SMTP_PASS` | 3 Commits — unverändert kompromittiert |
| `GZ_TEST_IMAP_PASS` | 3 Commits — unverändert kompromittiert |

Die Erneuerung läuft außerhalb dieses Workflows (PO: Resend · `infra`: Stalwart-Postfach,
MQ 60308 offen, Erinnerung 60711).

## Related Files

| Datei | Relevanz |
|---|---|
| `.claude/hooks/secret_in_repo_gate.py` (421 Z.) | Scheibe 1. Vorbild für Aufbau, Ausgänge, Meldungsform. F008/F009 sitzen hier. |
| `tests/unit/test_secret_in_repo_gate.py` (21 Tests) | Vorbild: echter Subprozess + stdin-Payload, keine Mocks; `GZ_SECRET_GATE_PATH` macht den Prüfling austauschbar (Mutationsprobe ohne Freigabe) |
| `.claude/hooks/hook_utils.py` (56 Z.) | **Shim** — enthält keine Logik, lädt das Plugin-Modul per `importlib` und re-exportiert |
| `.claude/settings.json:138-149` | einziger projekteigener `PostToolUse`-Block (`auto_restart_server.py`, Matcher `Bash`) |
| `.claude/hooks/auto_restart_server.py:52,57-62` | einziger Präzedenzfall: liest `tool_response`, meldet auf stderr, Exit 0 |
| `tests/tdd/test_issue_384_hook_fail_open.py:129-136,181` | erzwingt die Verdrahtungsform — macht einen falsch geschriebenen Eintrag sofort rot |
| `tests/tdd/test_issue_348_parallel_workspaces.py:110,123,242` | verlangt `${CLAUDE_PROJECT_DIR}` und Zeichengleichheit Worktree ↔ Hauptordner |

### Außerhalb dieses Repos (Plugin `agent-os-openspec` 3.10.2)

| Datei | Relevanz |
|---|---|
| `core/hooks/secret_egress_guard.py` (322 Z.) | **Der eigentliche Baukasten für Stufe B.** `collect_secrets:184`, `_is_secret_key:165`, `_is_secret_value:174`, Platzhalter-Filter `:78-97` |
| `core/hooks/hook_utils.py` (786 Z.) | `is_git_subcommand:281`, `get_tool_input:405`, `find_project_root:593`, `strip_heredoc_bodies:498` |
| `hooks/hooks.json:86-107` | Plugin hat bereits zwei `PostToolUse`-Hooks (`post_bash.py`, `edit_verify.py`) |

## Existing Patterns

- **Verdrahtungsform (unverhandelbar, testgeprüft):**
  `if [ -f "${CLAUDE_PROJECT_DIR}/.claude/hooks/<name>.py" ]; then python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/<name>.py"; fi`
  `&&`/`|| exit 0` ist ausdrücklich verboten (verschluckt den Rückgabewert 2).
- **Ein Hook = eine Gruppe** im `PreToolUse`-Array (9 Gruppen, alle mit Matcher `Bash`).
  Nur `Stop` bündelt drei Hooks in einer Liste.
- **Dateiname nur `[A-Za-z0-9_]`** — Bindestriche macht `_HOOK_RE` unsichtbar.
- **Meldung nennt nie den Wert**, nur Datei + Schlüsselname (`secret_in_repo_gate.py:55-57,396`).
- **Kein `.env`-Cache** in beiden Wächtern — ausdrücklich wegen Rotation.
- **Tests fahren den Hook als echten Subprozess** mit stdin-JSON gegen synthetische `.env`-Werte
  in `tmp_path`. Plugin-Sonde am Modulkopf: fehlt das Plugin, `skip` statt strukturellem Rot.

## Dependencies

- **Upstream:** Plugin `agent-os-openspec ≥ 3.10.0` (via Shim). Fehlt es, geht jeder Wächter
  fail-open — die Tests überspringen dann, statt falsch rot zu werden.
- **Downstream:** `.claude/settings.json` — wirkt auf **jede** Sitzung in diesem Projekt,
  auch auf fremde Worktrees.

## Risks & Considerations

### R1 — `PostToolUse` kann nicht blockieren (Doku selbst gelesen, nicht vermutet)

Belegt in der Hook-Doku: Exit 2 bei `PostToolUse` „shows stderr to Claude; **the tool already
ran**". `FileChanged` ebenso wenig. **Folge für Stufe A:** Eine Sperre ist technisch nicht
möglich; nur Nachsorge — Datei auf `600` setzen oder entfernen und melden. Gegen den
tatsächlichen Schadensfall (#1380: weltlesbare `/tmp`-Datei) wirkt das, aber die ACs dürfen
keine Sperre versprechen, die es nicht gibt.

`updatedToolOutput` **existiert** und Redaction ist ausdrücklich als Anwendungsfall genannt
(„intercept at `PreToolUse` for outbound tool inputs and `PostToolUse` for inbound tool
results"). Struktur: `{"hookSpecificOutput": {"hookEventName": "PostToolUse",
"updatedToolOutput": "…"}}`. Stufe B ist damit tragfähig.

### R2 — Es gibt bereits ZWEI verschiedene Begriffe von „Geheimnis". Ein dritter wäre der Fehler.

| | `secret_in_repo_gate` (Projekt) | `secret_egress_guard` (Plugin) |
|---|---|---|
| Schlüssel | Suffix-Allowlist, 4 Einträge | Regex-Denylist, 18 Muster |
| Mindestlänge | 10 | 8 |
| Platzhalter-Filter | keiner | 26 Werte + 6 Regex + URL/Pfad |
| Störungsverhalten | drei Ausgänge, teils fail-closed | durchgehend fail-open |

Stufe B braucht genau die Erkennung, die das Plugin schon hat — die liegt aber in einem
**anderen Repository**. Zu entscheiden in der Analyse: Wiederverwendung über den
`hook_utils`-Shim (dann muss das Plugin die Funktionen exportieren — Fremd-Repo-Änderung)
oder bewusste Kopie im Projekt (dann drei Begriffe). **Nicht in der Implementierung
nebenbei entscheiden.**

### R3 — Verdrahtung legt potenziell ALLE Sitzungen lahm

`CLAUDE_PROJECT_DIR` zeigt auf den **Hauptordner**, nicht auf den Arbeitsordner. Ist der
Hauptordner nach dem Merge nicht nachgezogen, scheitert der Hook in **jeder** Sitzung
(am 2026-08-04 eine Stunde Totalblockade). Die geschützte `if [ -f … ]`-Form verhindert genau
das — deshalb ist sie hier Pflicht, nicht Kosmetik.

Zusätzlich: `.claude/settings.json` wird **beim Sitzungsstart** eingelesen. Der Hook ist erst
ab der nächsten Sitzung scharf; das gehört in die Abschlussmeldung.

### R4 — `.claude/settings.json` ist orchestrator-geschützt

`edit_gate.py` blockiert Edits daran; nur der **User** kann per getipptem `override` freigeben,
**TTL 1 Stunde**. Die Verdrahtung braucht also einen PO-Eingriff und muss in einem Zug
erledigt werden. Zusätzlich verlangt `test_issue_348_parallel_workspaces.py:242`
Zeichengleichheit zwischen Hauptordner und Worktree.

### R5 — Mutations-Gegenprobe darf `.claude/**` nicht anfassen

Bei Scheibe 1 lief der Freigabe-Token mitten in der Gegenprobe ab und die Datei blieb
**mutiert** liegen (Sicherheitsblockade stand offen, PO musste 4× freigeben). Richtig:
Mutationen auf einer Kopie im Scratchpad, Prüflingspfad per Env-Var umstellbar — das Muster
`GZ_SECRET_GATE_PATH` (`test_secret_in_repo_gate.py:32`) existiert schon und ist zu übernehmen.

### R6 — LoC-Limit

Scheibe 1 war allein 421 Zeilen Hook. Stufe A und Stufe B zusammen plus Tests sprengen das
Limit von 250 sicher. **Empfehlung: zwei getrennte Workflows** (Stufe B zuerst — sie schließt
den Weg, über den #1535 tatsächlich Werte ausgegeben hat) statt eines LoC-Overrides.

### R7 — Reichweite von Stufe B ist zu bestimmen, nicht anzunehmen

`PostToolUse` bekommt `tool_name`, `tool_input`, `tool_response`. Welche Werkzeuge maskiert
werden sollen (nur `Bash`? auch `Read`? auch MCP-Werkzeuge?) ist eine Spec-Frage: Der
Egress-Guard arbeitet mit einer Negativliste, in der `Read` und `Grep` **übersprungen** werden —
für Ausgaben ist gerade `Read` aber ein realistischer Austrittsweg.

## Existing Specs

Für Scheibe 1 wurde **keine** Spec unter `docs/specs/modules/` abgelegt (geprüft: kein Treffer
auf `1537` oder `secret`). Verwandte Specs betreffen den namensgleichen, aber thematisch
anderen Netzwerk-Egress (`docs/specs/modules/egress_guard*.md`) — **nicht** verwechseln.
Beste vorhandene Gate-Übersicht: `docs/context/fix-1307b-gates.md`.

## Offene Nebenbefunde aus Scheibe 1

- **F008** (MEDIUM, Fehlalarm): Die `cd`-Erkennung prüft nicht, ob das Segment zu einem
  git-Aufruf gehört. Ein unquotiertes `git commit -F - <<'EOF'` mit einer Nachrichtenzeile,
  die mit „cd" beginnt, blockiert fälschlich. `strip_heredoc_bodies` (`hook_utils:498`)
  existiert bereits und wird hier offenbar nicht genutzt.
- **F009** (MEDIUM, Testlücke): Bei kaputten Anführungszeichen verhält sich der Code korrekt
  (blockiert), aber kein Test bewacht das.

## Analysis (Phase 2, 2026-08-07)

### Type

**Feature** — neuer Wächter. Ausgelöst durch einen Sicherheitsbefund, aber es wird kein
fehlerhaftes Verhalten repariert, sondern ein bisher unbewachter Weg geschlossen.

### Zuschnitt-Entscheidung

Dieser Workflow deckt **nur Stufe B** ab (Maskierung in Werkzeug-Ausgaben). Begründung:
Scheibe 1 war allein 421 Zeilen Hook; Stufe A + B + Tests sprengen das 250-Zeilen-Limit
sicher, und ein LoC-Override wäre die Regel umgehen statt die Arbeit schneiden. Stufe B
zuerst, weil sie den Weg schließt, über den in #1535 nachweislich ein aktiver Zugang
ausgetreten ist. Stufe A und F008/F009 folgen als eigene Workflows.

### A1 — Wiederverwendung statt drittem Geheimnis-Begriff (löst R2)

Das Plugin-Repo `henemm/agent-os-openspec` gehört uns (Eigentümer `henemm`, öffentlich);
Quelle `/home/hem/agent-os-openspec` und ausgelieferte Kopie
`~/.claude/plugins/cache/henemm-private/agent-os-openspec/3.10.2` sind deckungsgleich,
HEAD == installierter `gitCommitSha`.

**Eine Plugin-Änderung ist trotzdem der falsche Weg.** Sie verlangt Versions-Bump in
`.claude-plugin/plugin.json` + `claude plugin update`, und das Plugin ist auf **allen sechs**
Claude-Instanzen dieses Servers aktiv. Ein Sicherheitsfix in einem Projekt würde die
Werkzeugbasis aller anderen anfassen.

**Stattdessen:** `secret_egress_guard.py` ist importierbar — der ausführende Code steht
vollständig hinter `if __name__ == "__main__"` (`:317-322`). `collect_secrets:184`,
`_is_secret_key:165`, `_is_secret_value:174`, `_PLACEHOLDER_VALUES:78` sind normale
Modulsymbole. Der Ladeweg existiert bereits als erprobtes Muster: `.claude/hooks/hook_utils.py`
lädt das Plugin-Modul per `importlib` über `installed_plugins.json`.

Preis, der in der Spec stehen muss: Wir importieren **private** (unterstrich-präfigierte)
Funktionen aus einem fremden Repo. Absicherung wie in `secret_in_repo_gate.py:96-123` — zwei
getrennte `try`-Blöcke, damit eine ältere Plugin-Fassung den Wächter nicht lahmlegt, sondern
nur fail-open werden lässt. Nebeneffekt beim Import: `_setup()` läuft auf Modulebene und
verändert `sys.path` (`:43-51`) — per `importlib` mit direktem Dateipfad umgehbar.

### A2 — Gestalt der Nutzlast (empirisch, ~46.000 echte Werkzeug-Ergebnisse)

`tool_response` ist **kein einheitlicher Typ**:

| Fall | Gestalt |
|---|---|
| Bash, Erfolg (33.681 Fälle) | dict: `stdout`, `stderr`, `interrupted`, `isImage`, `noOutputExpected` (+ optional `gitOperation`, `persistedOutputPath`, …) |
| Bash, **Fehlschlag** (2.576) | **reiner String**: `"Error: Exit code 1\n…"` — die Exit-Code-Information steht nur dort |
| `Read` (3.468) | `{"type":"text","file":{"filePath":…,"content":…}}` — Inhalt **verschachtelt** unter `file.content` |
| `Write` (1.916) | `{"type":"create","filePath",…,"content": …}` — Inhalt auf oberster Ebene |
| `Edit` (2.739) | `oldString`, `newString`, `originalFile`, `structuredPatch` — **kein** `stdout`/`content` |

Es gibt **kein** `exit_code`-Feld. Ein `content`-Feld existiert bei Bash **nicht** — der
Fallback in `auto_restart_server.py:62` greift dort ins Leere (kein Fehler, nur tote Zeile).

**Folge:** Eine Maskierung, die nur `stdout` anfasst, verfehlt `Read` (verschachtelt) und
jeden Fehlschlag (String). Genau diese beiden sind die realistischen Austrittswege.

### A3 — Der entscheidende Unbekannte: die Ausgabeform ist im Haus unerprobt

**Kein einziger Hook** im Projekt oder im Plugin gibt JSON auf stdout aus — 0 Treffer auf
`hookSpecificOutput` in beiden Repos. Alle 20+ Hooks melden über stderr und Exit-Code.
Stufe B wäre der erste. Unbeantwortet und **nicht durch Code-Lesen beantwortbar**:

- Erwartet `updatedToolOutput` einen **String**, oder darf/muss es die ursprüngliche
  **Struktur** (dict) tragen?
- Was passiert, wenn ein dict-förmiges Bash-Ergebnis durch einen String ersetzt wird —
  bricht das nachgelagerte Verarbeitung?
- Wirkt es überhaupt in dieser Claude-Code-Fassung?

**Deshalb Pflicht vor der Implementierung: ein Vorab-Experiment** mit einem
Wegwerf-Hook gegen einen harmlosen Marker-String. Ohne diesen Nachweis wäre die gesamte
Implementierung auf einer Vermutung gebaut — genau das Muster, das in diesem Projekt
wiederholt in falsches Grün geführt hat.

### A4 — Risiko-Bewertung

**HIGH.** Der Hook läuft nach **jedem** Werkzeugaufruf in **jeder** Sitzung dieses Projekts.
Ein Fehler verfälscht nicht ein Feature, sondern jedes Werkzeug-Ergebnis.

Daraus abgeleitete, nicht verhandelbare Bauvorgaben:

1. **Stumm im Normalfall.** Kein Fund ⇒ **keinerlei** stdout, Exit 0. Nur bei einem echten
   Treffer wird überhaupt etwas ausgegeben.
2. **Durchgehend fail-open.** Jede eigene Störung (Plugin fehlt, `.env` unlesbar, unerwartete
   Nutzlast, Ausnahme) ⇒ Exit 0, unverändertes Ergebnis. Anders als Scheibe 1, wo fail-closed
   richtig war: dort kostet ein Irrtum einen blockierten Commit, hier ein zerstörtes
   Werkzeug-Ergebnis in jeder Sitzung.
3. **Zeitbudget klein** (Vorbild Egress-Guard: 5 s), damit der Wächter nicht jede Aktion bremst.
4. **Die Meldung nennt nie den Wert** — nur Werkzeug + Schlüsselname (Regel aus Scheibe 1).

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `.claude/hooks/secret_output_gate.py` | CREATE | der Wächter (Name nur `[A-Za-z0-9_]`) |
| `tests/unit/test_secret_output_gate.py` | CREATE | Subprozess + stdin-Payload, synthetische `.env` in `tmp_path`, Prüflingspfad per Env-Var austauschbar |
| `.claude/settings.json` | MODIFY | neue `PostToolUse`-Gruppe in der geschützten `if [ -f … ]`-Form — **orchestrator-geschützt, braucht PO-`override`** |
| `docs/specs/modules/fix_1537_s2b_secret_output_gate.md` | CREATE | Spec (zählt nicht gegen LoC) |

### Scope Assessment

- Dateien: 4 (2 neu Code, 1 Änderung, 1 Doku)
- Geschätzt: ~200 Zeilen Hook + ~150 Zeilen Test. **Test-Zeilen zählen mit** — das LoC-Limit
  von 250 wird voraussichtlich gerissen. Vor einem Override wird geprüft, ob der Hook durch
  konsequente Wiederverwendung der Plugin-Funktionen deutlich unter 200 Zeilen bleibt.
- Risiko: **HIGH** (siehe A4)

### Open Questions

- [x] **Q1 (technisch, geklärt wie sie zu behandeln ist):** Nimmt `updatedToolOutput` einen
      String oder die Originalstruktur? — **Nicht vor der Spec zu beantworten und auch nicht
      nötig.** Eine AC darf den Mechanismus nicht voraussetzen; zugesichert wird die
      *Wirkung* („der Wert erscheint nicht mehr im Klartext im Werkzeug-Ergebnis"). Das
      Experiment ist der **erste Schritt der Implementierungsphase** (Wegwerf-Hook, eigenes
      Projekt im Scratchpad, Marker-String statt echtem Geheimnis). Die Spec benennt den
      **Rückfall**, falls `updatedToolOutput` in dieser Claude-Code-Fassung nicht trägt: der
      Wächter meldet den Fund dann auf stderr mit Werkzeug + Schlüsselname — schlechter als
      Maskierung, aber immer noch ein Fund statt eines stillen Lecks.
- [ ] **Q2 (Spec-Frage):** Welche Werkzeuge werden maskiert? Der Egress-Guard überspringt
      `Read`/`Grep` für **ausgehende** Eingaben — für **Ausgaben** ist gerade `Read` der
      realistischste Austrittsweg. Vorschlag: alle Werkzeuge, kein Ausschluss.
- [ ] **Q3 (Spec-Frage):** Was tun, wenn ein Wert im Ergebnis steht — vollständig ersetzen
      (`***`) oder mit Schlüsselnamen kenntlich machen (`***GZ_SMTP_PASS***`)? Letzteres hilft
      beim Verstehen, verrät aber, welcher Schlüssel wo auftaucht.

## Verwandtes Issue #1535

`tests/tdd/test_issue_1014_live_optin.py:89` vergleicht `os.environ`-Abbilder und druckt bei
Fehlschlag den **Wert** von `GZ_TELEGRAM_TEST_BOT_TOKEN` in die Testausgabe. Das ist genau die
Klasse, die Stufe B abfangen würde — der richtige Fix bleibt trotzdem im Test (Zusicherung auf
Schlüsselnamen umstellen). Stufe B ist das Netz, nicht der Ersatz.
