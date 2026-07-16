# Spec: nebenbefund_gate — Trigger token-basiert + --body-file-Marker mitlesen

- **Issue:** #1197 (Sammel-Gate-Audit), Scheibe „nebenbefund_gate False-Positives"
- **Created:** 2026-07-16
- **Typ:** Gate-Fix (Kategorie c — fälschlich blockierendes Gate)
- **ADR-Nr.:** keine
- **Datei:** `.claude/hooks/nebenbefund_gate.py`
- **Prüfdatum (Regel-Budget):** keine neue Regel — Gate behält sein Prüfdatum 2026-10-09

## Problem

Zwei False-Positive-Modi: (1) `--body-file`-Marker wird nicht gelesen → blockt das
empfohlene Muster; (2) Substring-Trigger `"gh issue create" in cmd` matcht auch
in zitiertem Argument-Text → blockt Kommentare, die die Phrase zitieren.

## Lösung

Trigger token-basiert via `shlex` (drei aufeinanderfolgende Tokens `gh issue
create`); Marker-Erkennung zusätzlich aus `--body-file`/`-F`-Dateiinhalt.

## Acceptance Criteria

**AC-1:** Given ein Bash-Kommando `gh issue create --repo henemm/gregor_zwanzig`
mit `[triage:c]` direkt in der Befehlszeile, When der Gate läuft, Then Exit 0
(unverändertes Durchlassen bei Marker im Befehl).

**AC-2:** Given `gh issue create --repo henemm/gregor_zwanzig --body-file <pfad>`,
wobei die Datei den Marker `[triage:b]` enthält, der Befehl selbst aber KEINEN
Marker, When der Gate läuft, Then Exit 0 (der Body-Datei-Inhalt wird auf den
Marker mitgeprüft).

**AC-3:** Given `gh issue create --repo henemm/gregor_zwanzig --body-file <pfad>`,
wobei WEDER die Datei NOCH der Befehl einen Marker enthält, When der Gate läuft,
Then Exit 2 (blockt weiterhin korrekt — kein Aufweichen).

**AC-4:** Given ein Kommando `gh issue comment 1197 --repo henemm/gregor_zwanzig
--body "... erwähnt die Phrase gh issue create ..."`, in dem `gh issue create` nur
als zitierter Text innerhalb eines Arguments vorkommt, When der Gate läuft, Then
Exit 0 (kein False-Block — es ist kein echter create-Aufruf).

**AC-5:** Given ein echter `gh issue create --repo henemm/gregor_zwanzig`-Aufruf
OHNE jeden Marker (kein Body-File), When der Gate läuft, Then Exit 2 (Kern-Block
unverändert).

**AC-6:** Given `gh issue create --repo henemm/henemm-infra ...` ohne Marker (ein
ANDERES Repo), When der Gate läuft, Then Exit 0 (Fremd-Repo unverändert
ausgenommen).

**AC-7:** Given ein Kommando mit unbalancierten Anführungszeichen, das `shlex`
nicht parsen kann, When der Gate läuft, Then Exit 0 (fail-open — ein Parse-Fehler
blockiert nie fremde Arbeit).

**AC-8:** Given das Prüfdatum ist überschritten (Datum > EXPIRY), When der Gate
läuft, Then Exit 0 (Selbstdeaktivierung unverändert).

## Known Limitations

- `--body-file -` (stdin als Body) ist im PreToolUse-Kontext nicht lesbar → wird
  wie „keine Body-Datei" behandelt (Fallback auf Befehls-Marker-Check). Bewusst,
  da der Gate den Prozess-stdin nicht konsumieren darf.
- Der Trigger erkennt `gh issue create` als drei aufeinanderfolgende Tokens; ein
  über Shell-Variablen/`eval` verschleierter Aufruf wird nicht erkannt (fail-open,
  konsistent mit der bestehenden Gate-Philosophie).

## Test-Politik

Kern-Schicht, deterministisch: der Gate liest JSON von stdin; Tests rufen `main()`
mit echtem stdin-JSON (`tool_input.command`) auf und prüfen den Exit-Code. Für
AC-2/AC-3 wird eine echte Body-Datei in `tmp_path` geschrieben. Kein Netz, kein
Mock. Neue Datei `tests/tdd/test_nebenbefund_gate_false_positives.py`.
