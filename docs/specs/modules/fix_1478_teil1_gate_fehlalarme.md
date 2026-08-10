---
entity_id: fix_1478_teil1_gate_fehlalarme
type: module
created: 2026-08-09
updated: 2026-08-09
status: draft
version: "1.0"
tags: [gates, tooling, issue-1478]
---

# Fix: broad_test_run_gate erkennt "pytest" nur noch in Kommando-Position

## Approval

- [ ] Approved

## Purpose

`broad_test_run_gate.py` soll breite `pytest`-Läufe ohne benannte Testdateien
blockieren (Schutz gegen den Vorfall vom 2026-08-03, echte Telegram-
Nachrichten an Prod). Aktuell hält `_pytest_invocations()` JEDES Token mit
dem Wortlaut "pytest" für einen Aufrufbeginn — auch wenn es nur ein
Argumentwert eines ANDEREN Kommandos ist (`grep -n "pytest" datei`,
`pgrep -af "pytest"`). Das blockiert reine Lesebefehle fälschlich. Dieses
Modul beschränkt die Erkennung auf echte Kommando-Position.

## Source

- **File:** `.claude/hooks/broad_test_run_gate.py`
- **Identifier:** `def _pytest_invocations`, `def _args_after` (seit Runde 5)

Python-Core / Tooling (`.claude/hooks/`) — kein Frontend-, Go-API- oder
Domain-Backend-Code betroffen.

## Estimated Scope

- **LoC:** ~25 (Produktivcode) + ~75 (Tests)
- **Files:** 2 (1 Produktivdatei, 1 neue Testdatei)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_tokens()` | function (unverändert) | shlex-Tokenisierung, liefert die Eingabe für `_pytest_invocations` |
| `_args_after()` | function (**geändert Runde 5**, siehe F-ADV1) | begrenzt die Argumentliste eines erkannten Aufrufs; nutzte bis Runde 5 ein eigenes, unsynchronisiertes Trenner-Set |

## Implementation Details

**Runde 1 → BROKEN (F001/F002):** Positions-Allowlist (Segmentanfang / nach
`run`) erkannte Launcher-Präfixe (`env`, `nice`, `timeout N`, `sudo`,
`xargs`) nicht als Kommando-Position — Regression. Siehe
`docs/artifacts/fix-1478-teil1-gate-fehlalarme/adversary-dialog-round1-broken.md`.

**Runde 2 → BROKEN (F005, siehe Session-Verlauf des Orchestrators):** die
daraufhin gebaute Fail-safe-Fassung (Default "ist ein Aufruf", Ausnahme nur
bei bekanntem Text-Suchkommando als nächstem Nicht-Flag-Vorgänger) hatte
einen eigenen, unconditionellen `-m`-Sonderzweig, der JEDES `<kommando> -m
pytest` als Aufruf registrierte — unabhängig davon, ob `<kommando>`
überhaupt Python ist. Live reproduziert: `git commit -m pytest`, `git log
--grep pytest`, `grep -m pytest file` wurden fälschlich blockiert. Gerade
`git commit -m` ist im eigenen PR-Liefer-Workflow dieses Projekts
allgegenwärtig — ein deutlich breiterer, häufigerer Fehlalarm als die
ursprünglich gemeldeten Fälle.

**Runde 3 → BROKEN (F006/F007, siehe Session-Verlauf des Orchestrators):**
"jedes Flag vor pytest schliesst aus, ausser -m+Python" war selbst zu
pauschal — EIN Flag zwischen einem echten Launcher und `pytest` (z.B.
`sudo -E pytest tests/`, `nice -n10 pytest tests/`, `xargs -I{} pytest {}`,
`env -S pytest tests/`) hebelte die AC-6-Erkennung wieder aus (F006, dieselbe
Bug-Klasse wie F001, nur eine Flag-Stufe tiefer). Zusaetzlich matchte
`_PYTHON_LAUNCHER_RE` nur den nackten Interpreter-Namen, nicht
pfad-qualifizierte Formen wie `/usr/bin/python3`/`.venv/bin/python3` (F007).

**Runde 4 (aktuell):** Prioritaet umgedreht (Vorschlag des Adversary-Agenten
uebernommen). Statt "Flag davor -> ausgenommen, ausser -m+Python" gilt jetzt:
"Flag davor -> Launcher-Erkennung PRUEFEN (Vorgaenger hinter allen Flags),
ausgenommen NUR wenn der Launcher weder ein bekannter Prozess-Launcher noch
ein Python-Interpreter ist". Die Launcher-/Python-Erkennung arbeitet auf dem
**Basename** (`rsplit("/", 1)[-1]`), damit pfad-qualifizierte Formen
(`/usr/bin/python3`) erkannt werden. Text-Suchkommando-Ausnahme (Runde 2)
bleibt fuer den flag-losen Fall unveraendert bestehen.

```python
_SEGMENT_SEPARATORS = {"&&", "||", ";", "|", "&"}
_TEXT_MATCH_COMMANDS = {
    "grep", "egrep", "fgrep", "rgrep", "zgrep", "pgrep", "rg", "ag", "ack",
}
_LAUNCHER_COMMANDS = {
    "env", "nice", "nohup", "sudo", "doas", "setsid", "timeout", "xargs",
    "time", "ionice", "chrt",
}
_PYTHON_LAUNCHER_RE = re.compile(r"^python3?(\.\d+)?$")


def _basename(token: str) -> str:
    """Letztes Pfadsegment -- 'pytest'-Erkennung soll pfad-qualifizierte
    Launcher (/usr/bin/python3, .venv/bin/python3) genauso treffen wie
    nackte Namen (Issue #1478 Teil 1, Adversary-Runde 3, Finding F007)."""
    return token.rsplit("/", 1)[-1]


def _nearest_non_flag_predecessor(tokens: list[str], index: int) -> "str | None":
    """Naechstes Token VOR `index` im selben Segment, das keine Flag
    (fuehrendes '-') ist. None am Segmentanfang (Trenner erreicht oder
    Listenanfang)."""
    j = index - 1
    while j >= 0:
        tok = tokens[j]
        if tok in _SEGMENT_SEPARATORS:
            return None
        if not tok.startswith("-"):
            return tok
        j -= 1
    return None


def _pytest_invocations(tokens: list[str]) -> list[int]:
    """Indizes, an denen ein pytest-Lauf beginnt.

    Default: JEDES 'pytest'-/'*/pytest'-Token zaehlt als Aufrufbeginn.
    Zwei Faelle:

    1. Unmittelbar vorangehendes Flag-Token (fuehrendes '-'): der Vorgaenger
       HINTER ALLEN Flags wird ermittelt (`_nearest_non_flag_predecessor`
       ueberspringt beliebig viele Flags). Ist dieser Vorgaenger ein
       bekannter Prozess-Launcher (`_LAUNCHER_COMMANDS`) oder ein
       Python-Interpreter (`_PYTHON_LAUNCHER_RE` auf den Basename) ->
       'pytest' IST ein Aufruf, egal wie viele Flags dazwischen liegen
       (Issue #1478 Teil 1, Adversary-Runde 3, Finding F006: 'sudo -E
       pytest', 'nice -n10 pytest', 'xargs -I{} pytest' MUESSEN weiterhin
       blockiert werden). Sonst (Vorgaenger ist ein gewoehnliches Wort wie
       'commit', 'log', 'grep') ist 'pytest' dessen Freitext-Flag-Wert,
       kein eigener Aufruf (Finding F005: 'git commit -m pytest', 'git log
       --grep pytest', 'grep -m pytest').
    2. Kein vorangehendes Flag: der naechste Nicht-Flag-Vorgaenger im
       selben Segment wird direkt gegen `_TEXT_MATCH_COMMANDS` geprueft
       (Basename) -- 'pytest' ist dessen Suchmuster (grep -n "pytest"
       datei, pgrep -af "pytest"), sonst Default "ist ein Aufruf" (z.B.
       jeder bare Launcher: 'sudo pytest tests/', F001/AC-6).
    """
    hits: list[int] = []
    for i, tok in enumerate(tokens):
        if tok != "pytest" and not tok.endswith("/pytest"):
            continue
        if i > 0 and tokens[i - 1].startswith("-"):
            launcher = _nearest_non_flag_predecessor(tokens, i)
            launcher_base = _basename(launcher) if launcher is not None else None
            if launcher_base in _LAUNCHER_COMMANDS or (
                launcher_base is not None and _PYTHON_LAUNCHER_RE.match(launcher_base)
            ):
                hits.append(i)
            continue
        predecessor = _nearest_non_flag_predecessor(tokens, i)
        predecessor_base = _basename(predecessor) if predecessor is not None else None
        if predecessor_base in _TEXT_MATCH_COMMANDS:
            continue
        hits.append(i)
    return hits
```

`re` ist bereits am Dateianfang von `broad_test_run_gate.py` importiert
(`import re`) — kein neuer Import nötig.

**Runde 5 (aktuell) → Fund F-ADV1 (Adversary-Runde 4, außerhalb von
`_pytest_invocations()`):** `_args_after()` begrenzt die Argumentliste eines
erkannten Aufrufs mit einem EIGENEN, nie synchronisierten Trenner-Set
(`{"&&", "||", ";", "|", ">", ">>"}`), dem das einfache `&` fehlt — obwohl
`_SEGMENT_SEPARATORS` es seit Runde 2/AC-7 enthält. Erkennung
(`_pytest_invocations`) und Begrenzung (`_args_after`) nutzten dadurch zwei
verschiedene Vorstellungen von "Segmentende". Live reproduziert:
`pytest tests/ & x.py` — `_pytest_invocations` erkennt den Aufruf an
Index 0 korrekt, aber `_args_after` sammelt Tokens ÜBER den `&`-Trenner
hinweg ein, findet `x.py` aus dem NÄCHSTEN, unabhängigen Segment und hält
den Aufruf fälschlich für "konkrete Datei benannt" — ein voller,
ungemarkerter Testlauf (der 2026-08-03-Vorfall) läuft unblockiert durch.

Fix: `_args_after()` verwendet dieselbe Trenner-Menge wie
`_nearest_non_flag_predecessor()`, ergänzt um die Redirect-Operatoren
`>`/`>>`, die dort keine Rolle spielen (schließen aber ihrerseits die
Argumentliste ab — unverändertes Bestandsverhalten):

```python
def _args_after(tokens: list[str], start: int) -> list[str]:
    """Argumente nach dem pytest-Token bis zum naechsten Kommando-Trenner.

    Nutzt dieselbe Trenner-Menge wie `_nearest_non_flag_predecessor()`
    (`_SEGMENT_SEPARATORS`, seit Runde 2 inkl. '&') statt eines eigenen,
    unsynchronisierten Sets -- sonst erkennt `_pytest_invocations()` einen
    Aufruf korrekt an einer Segmentgrenze, aber `_args_after()` sammelt
    Tokens ueber genau diese Grenze hinweg ein (Issue #1478 Teil 1,
    Adversary-Runde 4, Finding F-ADV1: 'pytest tests/ & x.py' lief
    unblockiert durch, weil 'x.py' aus dem NAECHSTEN Segment faelschlich
    als benannte Testdatei des ERSTEN Aufrufs galt)."""
    stop = _SEGMENT_SEPARATORS | {">", ">>"}
    out = []
    for tok in tokens[start + 1:]:
        if tok in stop:
            break
        out.append(tok)
    return out
```

## Expected Behavior

- **Input:** Bash-Kommandozeile (roher String, bereits durch `_tokens()`
  tokenisiert)
- **Output:** Liste der Token-Indizes, an denen ein ECHTER pytest-Aufruf
  beginnt (leer, wenn keiner)
- **Side effects:** keine (reine Berechnung)

## Acceptance Criteria

- **AC-1:** Given ein Kommando `uv run pytest tests/tdd/x.py` / When
  `_pytest_invocations()` aufgerufen wird / Then der Index des `pytest`-Tokens
  wird erkannt (unverändertes Verhalten für das im Projekt tatsächlich
  genutzte Aufrufmuster).
  - Test: bestätigt anhand des bestehenden, im Projekt üblichen Musters.

- **AC-2:** Given ein reiner Lesebefehl `grep -n "pytest" .github/workflows/*.yml`
  / When `_pytest_invocations()` aufgerufen wird / Then die Liste ist leer
  (kein Fehlalarm) — der reale, im Issue gemeldete Fall.
  - Test: `broad_test_run_gate`-Hauptfunktion (End-to-End über Payload)
    blockiert diesen Befehl NICHT mehr.

- **AC-3:** Given `pgrep -af "pytest"` / When geprüft wird / Then kein
  Fehlalarm — der zweite im Issue gemeldete Fall.
  - Test: analog AC-2.

- **AC-4:** Given `cmd1 && pytest tests/tdd/x.py` / When geprüft wird / Then
  der pytest-Aufruf NACH dem Trenner `&&` wird weiterhin erkannt
  (Regressionswächter: Segmentanfang nach Shell-Trenner bleibt gültige
  Kommando-Position).
  - Test: `_pytest_invocations()` direkt.

- **AC-5:** Given `pytest tests/` (echter breiter Lauf ohne benannte Datei,
  bares Kommando) / When das volle Gate geprüft wird / Then bleibt der
  Befehl BLOCKIERT — die eigentliche Schutzwirkung darf nicht schwächer
  werden.
  - Test: End-to-End über Payload, `BLOCKED` in stderr.

- **AC-6 (Adversary-Fund F001, PFLICHT):** Given ein breiter Lauf hinter
  einem Launcher-Präfix (`env`, `nice`, `timeout 60`, `sudo`, `xargs`,
  jeweils gefolgt von `pytest tests/` ohne benannte Datei) / When das volle
  Gate geprüft wird / Then bleibt der Befehl BLOCKIERT für JEDEN dieser
  Launcher — vor dieser Korrektur erkannte der Alt-Code jeden davon
  positionsunabhängig, die erste Fix-Fassung (Positions-Allowlist) erkannte
  KEINEN davon mehr (Regression).
  - Test: End-to-End über Payload, je Launcher-Variante, `BLOCKED` in stderr.

- **AC-7 (Adversary-Fund F002):** Given `sleep 1 & pytest tests/`
  (Hintergrund-Trenner `&`, kein `&&`) / When geprüft wird / Then bleibt der
  Befehl BLOCKIERT.
  - Test: End-to-End über Payload.
  - **Korrigierte Ursache (Entwickler-Agent-Nebenbefund, Fix-Loop Runde 2):**
    `&` wurde zwar zu `_SEGMENT_SEPARATORS` hinzugefügt, ist dort aber
    faktisch wirkungslos — `_nearest_non_flag_predecessor()` gibt für ein
    Trenner-Token entweder `None` zurück (mit Trenner-Prüfung) oder das
    Trenner-Token selbst als gewöhnlichen Vorgänger (ohne Prüfung); beide
    Fälle sind ausserhalb von `_TEXT_MATCH_COMMANDS` und führen zum
    identischen Ergebnis. AC-7 besteht durch den Fail-safe-Default ("ist
    ein Aufruf, ausser ein bekanntes Suchkommando steht direkt davor") —
    nicht durch `_SEGMENT_SEPARATORS`. Die Konstante bleibt als
    dokumentierte Segment-Grenze für `_nearest_non_flag_predecessor()`
    bestehen (Invariante "nur innerhalb desselben Segments suchen"), auch
    wenn sie unter der aktuellen `_TEXT_MATCH_COMMANDS`-Liste keinen
    beobachtbaren Unterschied macht.

- **AC-8 (Adversary-Fund F005, Runde 2, PFLICHT):** Given ein Kommando, bei
  dem "pytest" unmittelbar hinter einem Freitext-Flag eines NICHT-Python-
  Kommandos steht (`git commit -m pytest`, `git log --grep pytest`,
  `grep -m pytest datei`) / When das volle Gate geprüft wird / Then wird
  der Befehl NICHT blockiert — "pytest" ist erkennbar der Flag-Wert, kein
  eigener Aufruf. Live am unmutierten Runde-2-Code reproduziert (RC=2 statt
  0 für alle drei Beispiele).
  - Test: End-to-End über Payload, je Beispiel.

- **AC-9 (Regressionswächter zu AC-8):** Given `python3 -m pytest
  tests/tdd/x.py` (der einzige legitime `-m`-Fall) / When geprüft wird /
  Then bleibt der Aufruf weiterhin erkannt — die AC-8-Korrektur darf
  `python -m pytest` nicht mit ausschließen.
  - Test: `_pytest_invocations()` direkt + End-to-End.

- **AC-10 (Adversary-Fund F006, Runde 3, PFLICHT):** Given ein bekannter
  Prozess-Launcher mit EINEM Flag zwischen ihm und `pytest`
  (`sudo -E pytest tests/`, `nice -n10 pytest tests/`,
  `xargs -I{} pytest {} tests/`, `xargs -n1 pytest tests/`,
  `env -S pytest tests/`) / When das volle Gate geprüft wird / Then bleibt
  der Befehl BLOCKIERT — ein einzelnes Flag zwischen Launcher und `pytest`
  darf die AC-6-Erkennung nicht aushebeln. Live am unmutierten Runde-3-Code
  reproduziert (RC=0 statt 2 für alle fünf Beispiele).
  - Test: End-to-End über Payload, je Beispiel.

- **AC-11 (Adversary-Fund F007, Runde 3):** Given ein pfad-qualifizierter
  Python-Interpreter (`/usr/bin/python3 -m pytest tests/`,
  `.venv/bin/python3 -m pytest tests/`, `/usr/bin/python3.12 -m pytest
  tests/`) / When geprüft wird / Then bleibt der Befehl BLOCKIERT — die
  Python-Erkennung muss auf dem Basename arbeiten, nicht nur auf dem
  nackten Namen.
  - Test: End-to-End über Payload, je Beispiel + Unit gegen
    `_pytest_invocations()`.

- **AC-12 (Adversary-Fund F-ADV1, Runde 4, KRITISCH, PFLICHT):** Given ein
  erkannter breiter pytest-Aufruf, gefolgt von einem Hintergrund-Trenner
  `&` und einem beliebigen weiteren Token mit `.py`-Endung
  (`pytest tests/ & x.py`, `pytest tests/ & echo x.py`) / When das volle
  Gate geprüft wird / Then bleibt der Befehl BLOCKIERT — das `.py`-Token
  aus dem NÄCHSTEN Segment darf nicht als benannte Testdatei des ERSTEN
  Aufrufs zählen. Live am unmutierten Runde-4-Code reproduziert (RC=0 statt
  2). Kontrollprobe mit `&&` statt `&` an derselben Stelle: RC=2 (isoliert
  die Ursache eindeutig auf `_args_after()`s fehlendes `&`).
  - Test: End-to-End über Payload, je Beispiel.

## Known Limitations

- **Bewusst nicht behoben (Formprüfung ist bodenlos, vgl. Projekt-Prinzip
  "invertiere die Frage statt jeden Fall aufzuzählen"):** ein Launcher mit
  MEHREREN Flags, von denen eines einen eigenen Wert-Token traegt UND
  dieser Wert-Token unmittelbar vor `pytest` steht, wird falsch eingeordnet
  — z.B. `sudo -u root -E pytest tests/`: der Rueckwaerts-Scan haelt
  `root` (den Wert von `-u`) faelschlich fuer den Launcher-Namen, da er
  keine Flag-Aritaet pro Kommando kennt (unbeschraenkt komplex, siehe
  `reference_command_parsing_is_bottomless_invert_the_question`). Bewusste
  Grenze dieser schmalen Korrektur — vollstaendige Argument-Semantik pro
  Launcher ist nicht das Ziel. `sudo -E pytest` (EIN wertloses Flag,
  AC-10) bleibt dagegen korrekt erkannt.
- **Bekannt, akzeptiert, kein Fix (Adversary-Runde 4, F-ADV2, LOW,
  Überblockierungs-Richtung):** `sudo -u pytest whoami` (ein System-User
  namens "pytest" als Flag-Wert von `-u`) wird fälschlich BLOCKIERT, weil
  der Rückwärts-Scan "pytest" selbst für den Vorgänger hält, bevor er
  "sudo" erreicht. Sicherheitsrichtung stimmt (fail-safe blockiert lieber
  einmal zu viel), kein reales Sicherheitsrisiko — Sammel-Eintrag statt
  eigener Korrektur (PO-Konvention Nebenbefund-Triage).
- **Bekannt, akzeptiert, kein Fix (Adversary-Runde 4, F-ADV3, LOW,
  Struktur-Hinweis):** `_TEXT_MATCH_COMMANDS` wird im Flag-Zweig von
  `_pytest_invocations()` nie konsultiert (strukturell unerreichbar, da der
  Zweig-Default "kein Launcher erkannt → nicht blockiert" für
  Text-Suchkommandos ohnehin dasselbe Ergebnis liefert) — mutations-belegt
  (Prioritäts-Umkehr fängt kein Test). Kein Verhaltensfehler, laut
  Docstring beabsichtigte Trennung der beiden Zweige.
- **Bekannt, akzeptiert, kein Fix (Adversary-Runde 5, F-ADV4, LOW,
  Überblockierungs-Richtung):** `_nearest_non_flag_predecessor()` kennt
  `>`/`>>` nicht als Segmentgrenze (im Unterschied zu `_args_after()`, das
  sie seit Runde 5 explizit berücksichtigt) — ein Redirect-Ziel, das
  zufällig `pytest` heißt (`echo x > pytest`), wird dadurch fälschlich als
  Aufruf-Kandidat gewertet. Kein AC verletzt, kein Fall gefunden, in dem
  ein ECHTER breiter Aufruf dadurch durchrutscht (`>` unmittelbar vor
  einem echten Aufruf-Token ist in gültiger Bash-Syntax nicht möglich —
  ein Redirect-Ziel ist per Definition ein Dateiname, kein Kommandostart).
  Sammel-Eintrag statt eigener Korrektur (PO-Konvention
  Nebenbefund-Triage).
- Ein text-suchendes Kommando außerhalb der festen Liste
  `_TEXT_MATCH_COMMANDS` (z.B. `find . -name "pytest"`, `awk`, `sed -n`)
  kann weiterhin einen Fehlalarm auslösen, wenn "pytest" darin als reiner
  Text vorkommt — nicht behoben, da nicht belegt (nur die tatsächlich
  gemeldeten Fälle `grep`/`pgrep`-Familie sind in der Liste). Eine
  vollständige Kommando-Semantik-Erkennung ist außerhalb des Scopes dieser
  schmalen Korrektur.
- Ändert nichts an `_tokens()`s Fallback-Verhalten bei verschachtelter
  Shell (`sh -c`, `eval`) — dort liefert `_tokens()` bereits `None` und das
  Gate greift über einen anderen, unveränderten Pfad.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Korrektur einer bestehenden Erkennungsfunktion, keine
  neue Architektur-Entscheidung nötig. Folgt demselben Prinzip wie die
  bereits im Plugin-Repo behobenen `bash_gate.py`-Fälle (Issue #1478,
  PR henemm/agent-os-openspec#92).

## Changelog

- 2026-08-09: Initial spec created
