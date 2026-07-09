---
entity_id: gate_1148_prod_send_deny
type: module
created: 2026-07-09
updated: 2026-07-09
status: draft
version: "1.0"
tags: [hooks, infrastructure, gate, safety, prod-protection]
---

<!-- Issue #1148 — Gate: Claude-Sessions duerfen keine Send-Trigger gegen Prod ausloesen (Baustein C aus #1147) -->

# Gate #1148 — Prod-Send-Deny (Baustein C aus #1147)

## Approval

- [ ] Approved

## Purpose

Ein neuer projektlokaler `PreToolUse:Bash`-Hook (`prod_send_gate.py`) verhindert, dass eine Claude-Session per Bash-Kommando einen echten Mail-Versand gegen das Produktivsystem ausloest — weder ueber Prod-Send-Endpoints (Scheduler-/Send-Routen auf Python-Port 8000 bzw. Go-Port 8090 / `gregor20.henemm.com`) noch ueber eine direkte SMTP-Verbindung zu `smtp.resend.com`. Staging (Port 8001/8091, `staging.gregor20.henemm.com`) und reine GET-/Lese-Kommandos bleiben unbeeinflusst. Das schliesst Baustein C aus Issue #1147 (Empfaenger-Invariante) auf Werkzeug-Ebene: statt sich auf Verifikations-Disziplin nach dem Fakt zu verlassen, wird der Versand-Trigger selbst verhindert.

## Source

- **File:** `.claude/hooks/prod_send_gate.py` (NEU) — PreToolUse:Bash-Hook, stdin-JSON `{"tool_input":{"command":...}}`, Exit 0 = erlaubt, Exit 2 = blockiert
- **Identifier:** `def main()`, `def _is_send_endpoint_path(command)`, `def _targets_prod(command)`, `def _is_provably_get(command)`, `def _is_smtp_connection(command)`, `def _has_valid_override(workflow_name)`

## Estimated Scope

- **LoC:** ~200-250
- **Files:** 3 (2 neu, 1 Edit)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `hook_utils.py` (Projekt-Shim → Plugin) | intern | `get_tool_input()` fuer stdin/JSON-Parsing, `block()`/`allow()` fuer Exit-Handling — identisches Muster wie `renderer_mail_gate.py` |
| `.claude/user_override_token.json` | Datei | Override-Token-Speicher (v2-Format: `{"version":2,"tokens":{"<workflow>":{"created":ISO,"granted_by":...}}}`), erzeugt ausschliesslich durch den Plugin-Hook `phase_listener.py` wenn der User woertlich "override" tippt |
| `.claude/hooks/renderer_mail_gate.py` | Vorbild | Referenz-Implementierung fuer einen projektlokalen PreToolUse:Bash-Hook (stdin-JSON, Exit-Konventionen, `sys.path.insert` fuer `hook_utils`) |
| Plugin `core/hooks/bash_gate.py` | Vorbild | Obfuskations-Fallback-Muster: bei `sh -c`/`eval` im Kommando faellt die Pruefung auf einen Roh-String-Scan ueber den Gesamtstring zurueck (`_has_real_redirect`/`_is_sensitive` als Vorlage) |
| `.claude/settings.json` | Config | Registrierung als zusaetzlicher Eintrag unter `hooks.PreToolUse` mit `matcher: "Bash"`, analog zum bestehenden `renderer_mail_gate.py`-Eintrag |

## Implementation Details

### Blockregel (alle drei Bedingungen zusammen muessen zutreffen)

**1. Send-Trigger-Pfad im Kommando** — Pfadsegment endet auf `/send` ODER ist einer der drei Scheduler-Batch-Pfade:

```
/api/scheduler/(trip-reports|alert-checks|radar-alert-checks)
/api/scheduler/subscriptions/{id}/send
/api/scheduler/trips/{id}/send
/api/scheduler/compare-presets/{id}/send
/api/subscriptions/{id}/send        (Go)
/api/trips/{id}/send                (Go)
/api/compare/presets/{id}/send      (Go)
```

Generisches Matching: Regex auf Pfadsegment `.../send(\b|$|\?)` ODER `/api/scheduler/(trip-reports|alert-checks|radar-alert-checks)(\b|$|\?)`.

**2. Prod-Ziel im Kommando** (Port-Korrektur gegenueber Issue-Text, journal-verifiziert am 2026-07-09):

| Ziel | Prod (blockieren) | Staging (durchlassen) |
|---|---|---|
| Python (uvicorn) | `localhost:8000` / `127.0.0.1:8000` / `:8000` | `:8001` |
| Go-API | `:8090` | `:8091` |
| Extern | `gregor20.henemm.com` (ohne `staging.`-Praefix) | `staging.gregor20.henemm.com` |

Die negative Abgrenzung bei `gregor20.henemm.com` ist zwingend: ein Regex-Treffer auf `gregor20\.henemm\.com` darf nur zaehlen, wenn ihm nicht unmittelbar `staging.` vorausgeht.

**3. Nicht beweisbar GET** — folgende Indikatoren zaehlen als "nicht GET" und machen das Kommando blockierbar: `curl -X POST` (oder `-XPOST`), `curl --request POST` (curls Alias-Schreibweise, Adversary-Fix-Runde 1 / F001), `curl -F`/`--form` (Multipart-Upload, impliziert POST, F002), `curl --json` (impliziert POST, F003), `--data`/`-d`/`--data-raw`/`--data-binary`, `http POST` (HTTPie), `wget --post-data`, `wget --method=POST`/`--method POST` (F004), Python `requests.post(...)`. Ein Kommando ohne einen dieser Indikatoren (z.B. reines `curl <url>` oder `curl -X GET`) gilt als beweisbar GET und wird durchgelassen, selbst wenn der Pfad formal auf `/send` matcht — GET gegen einen Send-Endpoint loest fachlich keinen Versand aus.

### SMTP-Regel (unabhaengig von der Send-Endpoint-Regel)

Kommando referenziert `smtp.resend.com` UND enthaelt einen Verbindungs-Indikator (`openssl s_client`, `swaks`, `nc `, `ncat`, `socat` (beide Adversary-Fix-Runde 1 / F005), `telnet`, `python`/`python3 -c`, `smtplib`, `curl smtp://`) → blocken. Reine Erwaehnung ohne Verbindungs-Indikator (z.B. `grep -r smtp.resend.com src/`, Doku-Referenz, `cat`/`Read` auf eine Datei die den String enthaelt) → erlauben. Diese Trennung verhindert den in der Kontext-Analyse dokumentierten False-Positive (Code-Suche nach dem Hostnamen ist legitim).

### Freitext-Ausnahme fuer `gh`/`git`-Kommandos (F006, Adversary-Fix-Runde 1)

Vor der Send-Endpoint- und SMTP-Pruefung durchlaeuft der rohe Kommando-String `_sanitize_freetext()`: bei Kommandos, deren FUEHRENDES Token `gh` oder `git` ist, werden die Werte hinter den Flags `--body`/`--body=`/`-m`/`--message`/`--title`/`-F`/`--form` (Freitext-Argumente wie Issue-/PR-Kommentare oder Commit-Messages) aus dem Scan-String entfernt, bevor Send-Pfad-/Prod-Ziel-/POST-Indikator-Pruefung laufen — ein woertliches Zitat eines Reproduktionskommandos in einem Bug-Report ist keine echte Ausfuehrung. Die Ausnahme greift NUR fuer `gh`/`git` als fuehrendes Kommando (loest den Konflikt, dass `-F` bei curl ein POST-Indikator, bei `gh` aber ein Feld-Flag ist).

Fail-closed in drei Faellen faellt die Ausnahme weg (roher String wird ungefiltert gescannt, identisch zum Vor-Fix-Verhalten):
1. Das Kommando enthaelt eine verschachtelte Shell (`sh -c`/`eval`, gleiches Muster wie der Obfuskations-Fallback).
2. `shlex.split()` scheitert am Quoting (nicht parsbar).
3. Der Freitext-Wert selbst enthaelt Command-Substitution (`$(` oder Backtick) — diese wird von der Shell tatsaechlich ausgefuehrt und darf nicht als reines Zitat behandelt werden (Beispiel: `gh issue comment 1148 --body "$(curl -X POST localhost:8000/api/scheduler/trips/1/send)"` bleibt blockiert).

### `${IFS}`-Normalisierung + Metazeichen-Fail-Closed (F007/F008, Adversary-Fix-Runde 2)

Vor jedem weiteren Schritt (auch vor `_sanitize_freetext()`) durchlaeuft der rohe Kommando-String `_normalize_ifs()`: alle `${IFS}`-Obfuskationsvarianten (`${IFS}`, `${IFS%??}`, `$IFS`, `$IFS$9`) werden durch ein echtes Leerzeichen ersetzt. Grund: Bash expandiert `${IFS}` (die Standard-Feldtrenner-Variable) zur Laufzeit selbst zu Leerzeichen — ein Kommando wie `curl${IFS}-XPOST${IFS}localhost:8000/api/scheduler/trips/1/send` fuehrt Bash exakt so aus wie mit echten Leerzeichen, waehrend mehrere Indikator-Regexe (`\bnc\s`, `openssl\s+s_client`, `\bpython3?\s+-c\b`, `--request[\s=]+POST`, `-d\s`, `wget\s+--post-data`, `\bhttp\s+POST\b`) ein literales `\s`-Zeichen verlangen und dadurch komplett ins Leere liefen (F008) — obwohl Host, Port und Pfad dabei zu 100% literal und unobfuskiert sichtbar bleiben. Diese Luecke ist NICHT durch die Known-Limitation "Variablen-Obfuskation von Host/Port" gedeckt.

Zusaetzlich prueft `_sanitize_freetext()` vor dem shlex-Split, ob das (bereits IFS-normalisierte) Kommando ein Shell-Metazeichen (`&&`, `;`, `|`, Newline — Regex `[;&|\n]`) enthaelt. Grund: `shlex.split()` kennt keine Shell-Metazeichen und splittet ausschliesslich auf echtem Whitespace — ein an einen Freitext-Wert direkt angehaengtes, IFS-obfuskiertes Folgekommando (`gh issue comment 1148 --body "note"&&curl${IFS}-XPOST${IFS}localhost:8000/api/scheduler/trips/1/send`) wurde als EIN Freitext-Token erkannt und komplett aus dem Scan entfernt, obwohl die Shell bei echter Ausfuehrung das `curl -XPOST ...` tatsaechlich als eigenstaendiges, ausgefuehrtes Kommando behandelt (F007). Enthaelt das Kommando ein solches Metazeichen, greift die gh/git-Freitext-Ausnahme gar nicht mehr — es faellt komplett auf den Roh-Scan zurueck (identisch zum Verhalten ohne die Ausnahme).

Bewusste Abwaegung: ein legitimer `gh`/`git`-Freitext-Wert KANN `;`/`&` enthalten (z.B. eine Commit-Message "Fix bug; improve perf") und wuerde dann faelschlich dem Roh-Scan unterzogen — im Regelfall folgenlos, im seltenen Fall eines False-Positive-Treffers muss der User einmalig "override" tippen. Diese seltene zusaetzliche Reibung wird bewusst in Kauf genommen, weil die Alternative (Metazeichen ignorieren) einen CRITICAL-Bypass des zentralen Sicherheitsversprechens bedeutet.

### `-F`/`--form` nur bei curl/wget (F009, Adversary-Fix-Runde 2)

Der in Fix-Runde 1 (F002) ergaenzte `-F`/`--form`-Indikator ist aus der generischen `_POST_INDICATOR_PATTERNS`-Liste entfernt und in eine eigene Funktion `_has_form_post_indicator()` ausgelagert: sie zaehlt nur dann als POST-Indikator, wenn das FUEHRENDE Kommando-Token `curl` oder `wget` ist (identische Tool-Kontext-Logik wie bei der gh/git-Freitext-Ausnahme). Zuvor blockierte der toolunabhaengige Scan faelschlich reine Lese-/Diagnose-Kommandos wie `grep -F` (Fixed-String-Suche), `awk -F` (Feldtrenner) und `tail -F` (Follow-Retry) — insbesondere das im Projekt etablierte Deploy-Verifikationsmuster `strings <binary> | grep -F "<pfad>"` (siehe `reference_go_deploy_proof_binary_strings_grep`), was dem Purpose-Absatz ("reine GET-/Lese-Kommandos bleiben unbeeinflusst") woertlich widersprach. Fail-closed bei verschachtelter Shell oder nicht bestimmbarem fuehrenden Token (nicht parsbares Quoting): dann bleibt `-F`/`--form` weiterhin ein POST-Indikator, da sich das ausfuehrende Tool nicht sicher ausschliessen laesst.

### Zeilenfortsetzungs-Normalisierung (F010, Adversary-Fix-Runde 3)

Vor `_normalize_ifs()` durchlaeuft der rohe Kommando-String zusaetzlich `_normalize_line_continuation()`: jede Backslash-Newline-Sequenz (`\` unmittelbar gefolgt von einem Zeilenumbruch, Regex `\\\r?\n`) wird durch ein echtes Leerzeichen ersetzt. Grund: Bash entfernt diese Standard-Zeilenfortsetzungssyntax beim Parsen vollstaendig und fuehrt das Kommando zusammenhaengend aus (`curl -X\`+Newline+`POST ...` laeuft real als `curl -XPOST ...`) — mehrere `\s`-verankerte Indikator-Regexe (u.a. `-X\s*POST`, `-d\s`, `--request[\s=]+POST`, `openssl\s+s_client`) sahen den Backslash als Nicht-Whitespace-Zeichen und matchten daher nicht, obwohl Host/Port/Pfad literal sichtbar blieben. Ein echter Zeilenumbruch OHNE vorangehenden Backslash (tatsaechliche Kommando-Verkettung) bleibt von dieser Normalisierung unberuehrt und wird weiterhin von `_SHELL_METACHAR_RE` als Metazeichen erfasst.

### Wrapper-Praefix-robuste Fuehrungstoken-Bestimmung (F012, Adversary-Fix-Runde 3)

`_leading_token()` (genutzt von `_has_form_post_indicator()`) ueberspringt beim Bestimmen des tatsaechlich ausgefuehrten Kommandos alltaegliche Wrapper-Praefixe (`sudo`, `env`, `command`, `nice`, `nohup`, `time`, `stdbuf`, `timeout`, `doas`) sowie Umgebungsvariablen-Zuweisungs-Token (Regex `^\w+=`, z.B. `VAR=1`) und wendet auf das verbleibende Token `Path(...).name` an, um Absolutpfade (`/usr/bin/curl` → `curl`) auf den reinen Toolnamen abzubilden. Zuvor verglich die Funktion das shlex-fuehrende Token EXAKT gegen `{"curl","wget"}` — `sudo curl -F ...`, `env curl -F ...`, `/usr/bin/curl -F ...` und `VAR=1 curl -F ...` liessen den `-F`/`--form`-POST-Indikator dadurch faelschlich durch, obwohl in jedem Fall tatsaechlich curl (Multipart-POST) ausgefuehrt wird. Faellt weiterhin fail-closed zurueck (`_has_form_post_indicator()` blockt), wenn nach dem Ueberspringen aller Wrapper-/Zuweisungs-Token kein Kommando-Token mehr uebrig bleibt oder das Quoting nicht parsbar ist.

Bewusst NICHT auf `_sanitize_freetext()`s gh/git-Erkennung ausgedehnt: dort bleibt der Vergleich `tokens[0] in {"gh","git"}` strikt (keine Wrapper-/Basename-Aufloesung). Ein wrapper-praefigiertes `sudo gh issue comment ...` erfuellt die Freitext-Ausnahme daher weiterhin NICHT und faellt komplett auf den Roh-Scan zurueck — das ist die sichere Richtung (mehr Pruefung statt weniger) und fuehrt zu keinem neuen Bypass, anders als eine unueberlegte Ausdehnung der Ausnahme selbst.

### Obfuskations-Fallback (fail-closed)

Analog `bash_gate.py`: enthaelt das Kommando `sh -c`/`eval` (Regex `\b(?:ba|z|da|k)?sh\s+-c\b|\beval\b`), wird die gesamte Pruefung (Send-Pfad-Erkennung, Prod-Ziel-Erkennung, GET-Beweis, SMTP-Erkennung) auf den rohen Kommando-String angewendet statt auf geshlext-e Tokens — ein in Anfuehrungszeichen verstecktes Prod-Send-Kommando (`bash -c "curl -X POST localhost:8000/api/scheduler/trips/1/send"`) wird dadurch trotzdem erkannt.

### Override-Mechanik

Der Hook liest `.claude/user_override_token.json` mit einem eigenen, kleinen Reader (kein Import aus dem Plugin) — Format ist stabil dokumentiert (v2, `tokens.<workflow_name>.created` als ISO-8601, TTL 1h wie im Plugin-`override_token.py`). Ablauf bei einem sonst blockierten Kommando:

1. Aktiven Workflow-Namen ermitteln (`GZ_ACTIVE_WORKFLOW` bzw. `OPENSPEC_ACTIVE_WORKFLOW`, identisch zu bestehenden Hooks).
2. Token-Datei lesen, Eintrag fuer den aktiven Workflow suchen, Alter gegen TTL 1h pruefen.
3. Gueltiges, nicht abgelaufenes Token vorhanden → Kommando einmalig durchlassen (Exit 0) UND den Token-Eintrag fuer diesen Workflow aus der Datei entfernen (atomarer Write wie in `renderer_mail_gate.py`/`workflow.py` — `tempfile.mkstemp` + `os.rename`).
4. Kein gueltiges Token → blockieren mit Exit 2, Meldung verweist auf Issue #1148 und den Weg ("User tippt woertlich 'override'").

Der Verbrauch ist an einen tatsaechlich abgewendeten Block-Treffer gekoppelt, nicht an die blosse Existenz des Tokens — ein Token, das nie gebraucht wird, bleibt bis TTL-Ablauf gueltig und kann fuer andere (nicht-blockierte) Kommandos in derselben Session verwendet werden, ohne verbraucht zu werden.

### Registrierung in `.claude/settings.json`

Neuer Eintrag unter `hooks.PreToolUse` (Array-Element, matcher `"Bash"`), analog zum bestehenden `renderer_mail_gate.py`-Eintrag:

```json
{
  "matcher": "Bash",
  "hooks": [
    {
      "type": "command",
      "command": "python3 \"${CLAUDE_PROJECT_DIR}/.claude/hooks/prod_send_gate.py\"",
      "timeout": 60
    }
  ]
}
```

Da `PreToolUse`/`Bash` bereits ein Array-Element fuer `renderer_mail_gate.py` enthaelt, wird ein zweites Element mit demselben Matcher ergaenzt (beide Hooks laufen unabhaengig, beide muessen Exit 0 liefern, damit das Kommando durchgeht) — kein Umbau des bestehenden Eintrags.

## Expected Behavior

- **Input:** stdin-JSON `{"tool_input":{"command":"<bash-kommando>"}}` bei jedem Bash-Tool-Aufruf jeder Claude-Session in diesem Repo (inkl. Worktrees, da `.claude/settings.json` im Hauptrepo liegt und fuer Worktrees gilt).
- **Output:** Exit 0 (stdout leer, Kommando laeuft) oder Exit 2 (stderr-Meldung mit Issue-#1148-Verweis, Kommando wird nicht ausgefuehrt).
- **Side effects:** Bei erfolgreichem Override-Verbrauch wird `.claude/user_override_token.json` atomar umgeschrieben (Token-Eintrag fuer den aktiven Workflow entfernt). Kein anderer Zustand wird veraendert.

## Acceptance Criteria

- **AC-1:** Given ein Bash-Kommando mit `curl -X POST` gegen `localhost:8000` bzw. `127.0.0.1:8000` auf einen Send-Endpoint (z.B. `/api/scheduler/trips/1/send`) / When der Hook `prod_send_gate.py` das Kommando prueft / Then blockiert er mit Exit 2 und einer stderr-Meldung, die auf Issue #1148 verweist.
  - Test: stdin-JSON mit diesem Kommando an den Hook geben, Exit-Code und stderr-Inhalt pruefen.

- **AC-2:** Given ein inhaltlich identisches POST-Send-Kommando aber gegen `localhost:8001` bzw. `127.0.0.1:8001` (Staging-Python-Port) / When der Hook prueft / Then laesst er das Kommando mit Exit 0 durch, weil Staging kein Blockziel ist.
  - Test: gleicher Aufbau wie AC-1 mit Port 8001 statt 8000, Exit-Code 0 erwarten.

- **AC-3:** Given ein zuvor durch `phase_listener` erzeugtes gueltiges Override-Token fuer den aktiven Workflow in `.claude/user_override_token.json` / When ein sonst blockiertes Prod-Send-Kommando ausgefuehrt wird / Then laesst der Hook den Aufruf einmalig durch (Exit 0) und entfernt danach den Token-Eintrag, sodass ein zweiter identischer Aufruf wieder blockiert wird.
  - Test: Token-Datei mit gueltigem Eintrag vorbereiten, Hook zweimal mit identischem Prod-Send-Kommando aufrufen, ersten Exit-Code 0 und zweiten Exit-Code 2 pruefen sowie die Token-Datei danach auf fehlenden Eintrag kontrollieren.

- **AC-4:** Given ein reines GET-Kommando gegen einen Health-/Status-Endpoint auf Prod (`localhost:8000`, `:8090` oder `gregor20.henemm.com`) ohne POST-Flags oder Body / When der Hook prueft / Then laesst er das Kommando durch (Exit 0), weil GET-Requests nicht als Send-Trigger gelten.
  - Test: `curl gregor20.henemm.com/api/health` (ohne `-X POST`/`-d`) an den Hook geben, Exit-Code 0 erwarten.

- **AC-5:** Given ein Kommando, das eine direkte SMTP-Verbindung zu `smtp.resend.com` aufbaut (z.B. `openssl s_client -connect smtp.resend.com:587`) / When der Hook prueft / Then blockiert er mit Exit 2 und Verweis auf Issue #1148.
  - Test: dieses Kommando an den Hook geben, Exit-Code 2 und Meldungsinhalt pruefen.

- **AC-6:** Given ein reines Code-Such-Kommando, das `smtp.resend.com` nur als Textmuster referenziert (z.B. `grep -r smtp.resend.com src/`) ohne Verbindungs-Indikator / When der Hook prueft / Then laesst er das Kommando durch (Exit 0), weil keine echte Verbindung aufgebaut wird.
  - Test: dieses Kommando an den Hook geben, Exit-Code 0 erwarten.

- **AC-7:** Given ein ueber `sh -c "..."` bzw. `eval "..."` verschachteltes Kommando, dessen innerer String einen Prod-Send-Aufruf enthaelt / When der Hook prueft / Then greift der Roh-String-Scan-Fallback (analog `bash_gate.py`) und blockiert das Kommando mit Exit 2.
  - Test: `bash -c "curl -X POST localhost:8000/api/scheduler/trips/1/send"` an den Hook geben, Exit-Code 2 erwarten.

- **AC-8:** Given ein POST-Send-Kommando gegen den Hostnamen `gregor20.henemm.com` ohne `staging.`-Praefix / When der Hook prueft / Then blockiert er mit Exit 2, weil der Hostname eindeutig Prod referenziert.
  - Test: `curl -X POST https://gregor20.henemm.com/api/scheduler/trip-reports` an den Hook geben, Exit-Code 2 erwarten.

- **AC-9:** Given ein inhaltlich identisches POST-Send-Kommando aber gegen `staging.gregor20.henemm.com` / When der Hook prueft / Then laesst er das Kommando durch (Exit 0), weil die negative Abgrenzung (Praefix `staging.`) greift.
  - Test: gleicher Aufbau wie AC-8 mit `staging.gregor20.henemm.com` statt `gregor20.henemm.com`, Exit-Code 0 erwarten.

## Known Limitations

- Variablen-Obfuskation (`P=8000; curl :$P/api/scheduler/trips/1/send`) ist durch den Roh-String-Scan-Fallback nicht vollstaendig fangbar, weil weder der Port noch der Host als literaler String im Kommando auftaucht — dokumentierte Restluecke gemaess Kontext-Analyse zu Issue #1148, konsistent mit der bekannten Grenze von `bash_gate.py`. **Abgrenzung (Adversary-Fix-Runde 2):** die `${IFS}`-Obfuskation von Trennzeichen (nicht von Host/Port selbst) ist seit F007/F008 explizit abgedeckt — nur die Obfuskation von Host/Port/Pfad SELBST (z.B. durch Variablen-Substitution) bleibt eine Restluecke.
- Der Hook ist ausschliesslich an `PreToolUse:Bash` registriert und deckt keine anderen Tool-Typen ab; ein hypothetisches Nicht-Bash-Werkzeug mit direktem HTTP-Zugriff wuerde nicht geprueft (in diesem Repo derzeit nicht existent).
- Das Override-Token wird pro tatsaechlich abgewendetem Block-Treffer verbraucht, nicht pro Zeiteinheit — bei mehreren unabhaengigen Prod-Send-Versuchen in derselben Session muss der User pro Versuch erneut "override" tippen.
- Die dritte Blockbedingung ("nicht beweisbar GET") pruefft eine feste Indikator-Liste; ein noch nicht bekanntes HTTP-Tool mit abweichender POST-Syntax koennte faelschlich als GET durchgelassen werden, bis die Liste erweitert wird.
- **Brace-Expansion (F011, Adversary-Fix-Runde 3):** Bash-Brace-Expansion (z.B. `-X{,}POST`, expandiert real zu `-XPOST`) wird NICHT erkannt und bleibt eine bewusst nicht gefixte Luecke. Anders als F010 (Zeilenfortsetzung — eine gewoehnliche, nicht-adversariale Formatierungstechnik) erfordert dieses Muster bewusste Umgehungsabsicht: niemand schreibt `-X{,}POST` versehentlich oder aus Formatierungsgruenden. Das faellt ausserhalb des Bedrohungsmodells dieses Gates (versehentlicher/gewohnheitsmaessiger Prod-Send aus einer Claude-Session), das explizit keine gezielte Sicherheitsforschungs-Obfuskation abdecken soll — analog zur bereits dokumentierten Variablen-Obfuskations-Restluecke oben. Kein Code-Fix, kein Test.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der Hook folgt dem etablierten Muster projektlokaler `PreToolUse:Bash`-Gates (`renderer_mail_gate.py`) und dem Obfuskations-Schutz-Muster aus dem Plugin (`bash_gate.py`). Es handelt sich um eine additive Sicherheitsmassnahme ohne Aenderung an Domain-Architektur, Datenmodell oder Provider-Schicht — keine architektonische Grundsatzentscheidung im ADR-Sinne noetig.

## Test Coverage

Tests in `tests/tdd/test_issue_1148_prod_send_gate.py` (stdin-JSON rein, Exit-Code raus — `# doc-compliance-test`-Kategorie, kein Mock-Verbot verletzt, da der Hook selbst als deterministisches Kommandozeilen-Artefakt getestet wird, nicht das Verhalten eines externen Systems):

- `test_prod_python_port_post_send_blocked` (AC-1)
- `test_staging_python_port_post_send_allowed` (AC-2)
- `test_valid_override_token_allows_once_then_consumed` (AC-3)
- `test_get_health_against_prod_allowed` (AC-4)
- `test_smtp_direct_connection_blocked` (AC-5)
- `test_smtp_grep_reference_allowed` (AC-6)
- `test_sh_c_obfuscated_prod_send_blocked` (AC-7)
- `test_gregor20_hostname_post_send_blocked` (AC-8)
- `test_staging_hostname_post_send_allowed` (AC-9)
- `test_ifs_obfuscated_post_send_blocked` (Adversary-Fix-Runde 2, F008)
- `test_ifs_obfuscated_smtp_blocked` (Adversary-Fix-Runde 2, F008)
- `test_gh_body_then_chained_ifs_command_blocked` (Adversary-Fix-Runde 2, F007)
- `test_grep_dash_F_and_tail_F_allowed` (Adversary-Fix-Runde 2, F009)
- `test_curl_dash_F_form_still_blocked` (Adversary-Fix-Runde 2, F009-Regressionsgegenprobe)
- `test_line_continuation_post_send_blocked` (Adversary-Fix-Runde 3, F010)
- `test_wrapper_prefix_curl_form_blocked` (Adversary-Fix-Runde 3, F012)
- `test_grep_dash_F_and_tail_F_still_allowed_round3` (Adversary-Fix-Runde 3, F009-Regressionsgegenprobe)
- `test_line_continuation_inside_keyword_blocked` (Adversary-Fix-Runde 4, F013)

## Changelog

- 2026-07-09: Initial spec erstellt — Issue #1148, Baustein C aus #1147
- 2026-07-09: Adversary-Fix-Runde 1 — F001-F006. POST-Indikatoren um `curl --request POST` (F001), `curl -F`/`--form` (F002), `curl --json` (F003), `wget --method=POST` (F004) ergaenzt; SMTP-Verbindungs-Indikatoren um `ncat`/`socat` ergaenzt (F005); neue Freitext-Ausnahme `_sanitize_freetext()` fuer `gh`/`git`-Kommandos verhindert False-Positive bei woertlichem Zitat eines Block-Beispiels im Issue-/PR-Kommentar, faellt aber fail-closed auf Roh-Scan zurueck bei verschachtelter Shell oder Command-Substitution im Freitext-Wert (F006). ACs unveraendert.
- 2026-07-09: Adversary-Fix-Runde 2 — F007-F009. Neue Funktion `_normalize_ifs()` ersetzt alle `${IFS}`-Obfuskationsvarianten durch echte Leerzeichen VOR jedem weiteren Scan (F008 — mehrere `\s`-verankerte Indikator-Regexe waren dadurch komplett umgehbar, obwohl Host/Port/Pfad literal sichtbar blieben); `_sanitize_freetext()` faellt zusaetzlich bei Shell-Metazeichen (`;`/`&`/`|`/Newline) auf den Roh-Scan zurueck, da `shlex.split()` diese nicht kennt und ein an einen Freitext-Wert angehaengtes, IFS-obfuskiertes Folgekommando sonst als ein einziges Freitext-Token verschluckt wurde (F007); `-F`/`--form` ist aus der generischen POST-Indikator-Liste entfernt und in `_has_form_post_indicator()` ausgelagert, die nur bei fuehrendem Kommando-Token `curl`/`wget` greift (F009 — verhinderte False Positives bei `grep -F`/`awk -F`/`tail -F`/`strings | grep -F`). ACs unveraendert. Known Limitations praezisiert: `${IFS}`-Trennzeichen-Obfuskation ist jetzt abgedeckt, Obfuskation von Host/Port SELBST bleibt Restluecke.
- 2026-07-09: Adversary-Fix-Runde 3 — F010/F012 gefixt, F011 als Known Limitation. Neue Funktion `_normalize_line_continuation()` ersetzt Backslash-Newline-Zeilenfortsetzungen durch echte Leerzeichen VOR `_normalize_ifs()` (F010 — Standard-Bash-Formatierungstechnik fuer lange Kommandos umging mehrere `\s`-verankerte Indikatoren wie `-X\s*POST`, obwohl Bash das Kommando real zusammenhaengend ausfuehrt); `_leading_token()` ueberspringt jetzt Wrapper-Praefixe (`sudo`/`env`/`command`/`nice`/`nohup`/`time`/`stdbuf`/`timeout`/`doas`) und Env-Var-Zuweisungs-Token (`VAR=wert`) und wendet `Path(...).name` an, um Absolutpfade auf den reinen Toolnamen abzubilden (F012 — alltaegliche Praefixe liessen `curl -F`/`wget -F` faelschlich als GET durchgehen, weil das exakte Token-Match `{"curl","wget"}` nicht mehr griff). Brace-Expansion (`-X{,}POST`, F011) bleibt bewusst ungefixt und ist als Known Limitation dokumentiert — erfordert Umgehungsabsicht, ausserhalb des Bedrohungsmodells "versehentlicher/gewohnheitsmaessiger Prod-Send". ACs unveraendert.
- 2026-07-09: F013 — Zeilenfortsetzung wird ganz entfernt (Leerstring statt Leerzeichen), fängt Umbruch mitten im Keyword.
