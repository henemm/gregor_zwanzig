---
entity_id: fix_1409b_repo_path_ratchet
type: bugfix
created: 2026-07-29
updated: 2026-07-29
status: draft
version: "1.0"
tags: [tests, guard, worktree, ratchet, issue-1409]
---

<!-- Issue #1409 — Lieferung B: Wächter gegen neue Hauptrepo-Pfad-Verdrahtung in Tests -->

# Fix #1409 (Lieferung B) — Wächter gegen fest verdrahtete Hauptrepo-Pfade in Tests

## Approval

- [ ] Approved

## Purpose

Lieferung A hat die fünf real gefundenen Fälle behoben, in denen ein Test
seinen Prüfling über den festen Pfad `/home/hem/gregor_zwanzig/...` statt
worktree-relativ lädt und dadurch aus einem Git-Worktree heraus die
unveränderte Hauptrepo-Kopie prüft (falsches Grün). Diese Lieferung stellt
sicher, dass diese Fehlerart nicht wieder unbemerkt zurückkehrt: eine neue
pytest-Datei scannt `tests/**/*.py` und meldet jeden neuen Treffer, bei dem
ein Test seinen Prüfling über einen festen Hauptrepo-Pfad auflöst — auch
dann, wenn der Pfad nicht als ausgeschriebenes Literal, sondern als Join
über eine zuvor zugewiesene Konstante entsteht. Die 33 heute bekannten,
bewusst festen Fundstellen (Umgebungsdateien, geteilte Ablage, Suchmuster,
Fallback-Reihenfolge) bleiben unangetastet grün.

## Source

- **File:** `tests/tdd/test_repo_path_hardcoding_ratchet.py` (NEU)
- **Identifier:** Modul-Ebene — kein Produktivcode-Symbol, sondern ein
  Test-Wächter mit AST-Scan über `tests/**/*.py`, Auflösungslogik für
  Pfad-Ausdrücke sowie einer Ausnahmeprüfung über Marker-Kommentare an der
  Fundstelle.

> **Schicht-Hinweis:** reines Test-Infrastruktur-Artefakt (`tests/tdd/`).
> Scanfläche ist ausschließlich `tests/**/*.py`. Kein Frontend-, Go-API-
> oder Python-Core-Produktivcode betroffen.

## Estimated Scope

- **LoC:** ~90 (Vorgabe aus dem Kontextdokument, gemessene Kandidatenregel
  R2+; Laufzeit ~2 s). Nach Fix-Loop 1: ~250 im Wächtermodul zzgl.
  Fixture-Vorlagen; Laufzeit unverändert ~2,4 s für den vollen Testbaum.
- **Files:** 2 CREATE (`tests/tdd/test_repo_path_hardcoding_ratchet.py`,
  `tests/fixtures/ratchet_cases/faelle.py.txt`) + Marker-Kommentare in
  `test_622_fidelity_pre_actions.py` (2×) und
  `test_issue_603_design_fidelity_gate.py` (1×)
- **Effort:** low

**Regel-Budget (CLAUDE.md):** Ersetzt keine bestehende Regel → Prüfdatum
**2026-10-27** (+90 Tage) in der Datei hinterlegt, Mechanik nach dem
Vorbild `.claude/hooks/test_naming_gate.py` (dortige Konstante `EXPIRY`,
Selbstabschaltung nach Ablauf).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/fix-1409b-pfad-waechter.md` | Faktenbasis | Empirische Messung von fünf Kandidatenregeln (R1/R2/R2j/R2+/R4) gegen drei Korpora (IST, VORHER, SYNTH); Begründung der Entscheidung für R2+ mit Marker-Kommentar statt zentraler Allowlist |
| `docs/context/fix-1409-worktree-pfade.md` | Faktenbasis | Klassifikation A/B/C des heutigen Bestands (33 Treffer in 29 Dateien: 19× Klasse B, 14× Klasse C, 0× Klasse A) |
| `docs/specs/modules/fix_1409_worktree_test_paths.md` | Vorgänger-Spec | Lieferung A — Pfadfix der fünf Klasse-A-Stellen, Begründungskommentare für Klasse B/C, auf denen diese Lieferung aufbaut |
| `.claude/hooks/test_naming_gate.py` | Bauform-Vorbild | Prüfdatum-Mechanik (`EXPIRY`-Konstante, Selbstabschaltung, Fail-open bei Parse-Fehlern), Kommentarform der Regel-Budget-Begründung |
| `tests/tdd/test_code_gate_allowed_dirs.py` | Bauform-Vorbild | „Repo-Garantie als pytest-Datei" statt Hook — ein Wächter, der nur eine feste Eigenschaft des Repo-Zustands prüft, gehört als eigenständige Testdatei nach `tests/tdd/`, nicht als Pre-Edit-Hook |
| `tests/tdd/test_issue_603_design_fidelity_gate.py:23-26` | Realer Belegfall | `REPO = Path("/home/hem/gregor_zwanzig")` + `REPO / "design_fidelity_diff.py"` — der Fall, an dem eine reine Textsuche (R1) scheitert und der die Konstantenauflösung (R2j) notwendig macht |
| `tests/tdd/test_622_fidelity_pre_actions.py:34` | Realer Belegfall | Zweiter Beleg desselben Konstanten-Join-Musters |
| `tests/tdd/test_issue_348_parallel_workspaces.py:31` | Gegenprobe (Klasse C) | `HARDCODED_PREFIX` ist ein Suchmuster, kein Ladepfad — MUSS grün bleiben |
| `tests/tdd/test_issue_1004_startzeit_ssot.py:37` | Gegenprobe (Klasse C) | `_MAIN_REPO` ist Fallback **nach** `_REPO_ROOT` (Worktree gewinnt bereits) — MUSS grün bleiben |
| `.claude/hooks/prod_selftest.py:56` | Gegenprobe (Klasse B) | `REPO_DIR` als Verzeichniskonstante — zeigt auf kein `git ls-files`-Ziel, muss ohne Präfix-Vergleich automatisch durchgelassen werden |
| `ast` (stdlib) | Parser | Strukturelle Erkennung von Codeliteralen, Docstrings/Kommentare bleiben ausgeschlossen |
| `git ls-files` | Referenzquelle | Entscheidet, ob ein aufgelöstes Ziel eine getrackte **Datei** ist (kein Präfix-/Verzeichnisvergleich) |

## Implementation Details

### Scanfläche

`tests/**/*.py` (rekursiv). Kein Zugriff auf `src/`, `api/`, `internal/`,
`frontend/` oder `.claude/`.

### Erkennungsregel (Variante „R2+", empirisch begründet in
`docs/context/fix-1409b-pfad-waechter.md`)

1. Es werden ausschließlich **AST-Codeliterale** ausgewertet — String-
   Literale, die als Ausdruck im Code stehen. Docstrings und Kommentare
   fließen nicht in die Auswertung ein.
2. Pfad-Ausdrücke werden aufgelöst:
   - ausgeschriebene String-Literale mit `/home/hem/gregor_zwanzig`-Präfix,
   - **Joins über eine zuvor im selben Modul zugewiesene Konstante**
     (`KONSTANTE / "rel/pfad"`, wobei `KONSTANTE` selbst auf
     `/home/hem/gregor_zwanzig` aufgelöst wurde) — dies ist der Kern der
     Regel, ohne den die Hälfte der real belegten Verstöße unentdeckt
     bliebe (`test_issue_603`, `test_622`),
   - f-Strings mit demselben Präfix,
   - `+`-Verkettung von String-Literalen/Konstanten mit demselben Präfix,
   - `os.path.join(...)`-Aufrufe mit demselben Präfix als erstem Argument,
   - **(Fix-Loop 1, nach Adversary-Verdict BROKEN)** zusätzlich alle
     weiteren Schreibweisen, die den Pfad **zur Scan-Zeit vollständig
     festlegen** — sie sind keine „laufzeitgebauten Pfade" im Sinne der
     Known Limitations und dürfen deshalb nicht durchfallen:
     `Path(...).joinpath("rel/pfad")`, `"{}/rel".format(KONSTANTE)`,
     `"sep".join([KONSTANTE, "rel"])` (inkl. `os.sep`/`os.path.sep` als
     Trennzeichen), `"%s/rel" % KONSTANTE` (Tupel- und Dict-Form),
     Index-Zugriff auf eine konstante Liste/ein konstantes Tupel
     (`PFADE[0] / "rel"`), Schlüssel-Zugriff auf ein konstantes `dict`
     (`D["main"] + "/rel"`) sowie Konstanten aus **Tupel-Entpackung**
     (`A, B = "...", "..."`). **(Fix-Loop 2, Adversary F009)** Ebenso
     bindet eine **Mehrfach-/Kettenzuweisung alle ihre Ziele**:
     `A = B = "..."`, `A = B = C = "..."`, die Mischform
     `A = B, C = "x", "y"` und die Restform `A, *REST = ...` (Namen vor
     dem Stern binden von vorn, dahinter von hinten — Ziel- und
     Wertanzahl dürfen auseinanderfallen). **(Fix-Loop 3, Adversary
     F010)** Die Ziel-Wert-Paare einer Zuweisung werden dabei
     **gleichzeitig** ausgewertet: erst alle Werte gegen den Stand *vor*
     der Anweisung auflösen, dann alle Namen binden — so, wie Python die
     rechte Seite vollständig auswertet, bevor es zuweist. Andernfalls
     würde aus `A, B = B, A` ein `A, B = B, B`, mit einem Fehlalarm auf
     der einen und einem Durchlässer auf der anderen Seite des Tauschs. Die Menge der Pfad-Konstruktoren umfasst
     `Path`/`PurePath`/`PosixPath`/`PurePosixPath`, jeweils auch
     `pathlib.`-qualifiziert.
3. Ein aufgelöstes Ziel ist nur dann ein Verstoß, wenn es per
   `git ls-files` als **Datei** (nicht als Verzeichnis-Präfix) im Repo
   verzeichnet ist. Es findet **kein Präfixvergleich gegen den Index**
   statt — Verzeichniskonstanten wie `REPO_DIR`, `MAIN_REPO`,
   `HARDCODED_PREFIX` lösen sich dadurch von selbst: sie zeigen auf kein
   einzelnes getracktes File und werden nie zu einem Treffer.
3a. **(Fix-Loop 1)** Ein **bloßes String-Literal als Operand eines
   Vergleichs** (`assert "<pfad>" not in inhalt`, `== `, `in`) ist ein
   Suchmuster und wird nie gemeldet. Begründung: ein nackter Konstanten-
   Operand eines Vergleichs kann per Konstruktion nichts laden, die
   Unterscheidung ist deshalb ohne Falsch-negativ-Risiko automatisierbar
   und braucht keinen Marker. Ausdrücke, die im Vergleich *ausgewertet*
   werden (`assert (REPO / "hooks/x.py").read_text() in inhalt`), bleiben
   Funde — dort wird tatsächlich geladen. Vorher war ein Suchmuster gegen
   eine getrackte **Einzeldatei** ein Fehlalarm; der Bestand
   (`test_issue_348`) entkam nur, weil sein Suchmuster zufällig ein
   Verzeichnis ist.
4. Ausnahmen werden **an der Zeile** eingetragen, nicht in einer
   zentralen Liste: ein Kommentar der Form
   `# gz-main-path: <Begründung>` macht den Fund grün. Das Fenster reicht
   von der Zeile **vor** dem Fund bis zum **Ende der Anweisung**, in der
   er steht — bei umbrochenen Ausdrücken zeigt die Fundzeile auf die
   *erste* Zeile des Ausdrucks, der Marker steht dort aber üblicherweise
   hinter der schließenden Klammer (Fix-Loop 1). Bei zusammengesetzten
   Anweisungen (`def`, `if`, `for`, `with`) wird das Fenster **nicht**
   auf den Rumpf ausgeweitet, sonst entschuldigte ein Marker im Rumpf die
   ganze Funktion. Ein Marker **ohne** Begründungstext (leer oder nur
   Whitespace) zählt nicht; ebensowenig eine Alibi-Begründung: verlangt
   sind mindestens **15 sinnvolle Zeichen** (Buchstaben/Ziffern, Vorbild:
   30-Zeichen-Regel für Acceptance Criteria in CLAUDE.md), damit `: x`
   oder `: 👍` keinen echten Fund verschwinden lassen.
   Eine zentrale Ausnahmeliste gibt es weiterhin nicht. Der Bestand
   braucht heute **drei** Marker im Code — `test_622_fidelity_pre_actions.py`
   (2×) und `test_issue_603_design_fidelity_gate.py` (1×, in Fix-Loop 1
   hinzugekommen, weil die erweiterte Regel dort ein drittes Soll-Bild
   über `.joinpath()` sichtbar macht). Alle drei sind derselbe Fall:
   Soll-Bilder des Bildvergleichs müssen dem cwd des Vergleichs
   (`MAIN_REPO`) folgen, nicht dem Ort der Testdatei. Alle übrigen der
   33 bekannten Fundstellen bleiben ohne Marker grün, allein durch die
   Regel (Punkt 2–3a).
5. Prüfdatum **2026-10-27** als benannte Konstante in der Datei (Vorbild
   `EXPIRY` in `test_naming_gate.py`), maschinell auffindbar (z. B. per
   `grep`), inkl. Kommentar mit Verweis auf das Regel-Budget und die
   Instanz für das spätere Gate-Audit.

### Selbstbezug: Fixture-Quelltexte liegen außerhalb des Moduls (Fix-Loop 1)

Die Fixture-Quelltexte der Wächtertests enthalten absichtlich echte
Verstöße. Lägen sie im Wächtermodul selbst, müsste dieses seine eigene
Regel umgehen, um sich nicht selbst zu melden — die erste Fassung tat das
über `str.format()` und konnte die Regel deshalb nicht um `.format()`
erweitern, ohne sich selbst rot zu färben (Adversary F002: der Wächter
lebte von genau der Lücke, die er schließen sollte).

Deshalb liegen sie in **`tests/fixtures/ratchet_cases/faelle.py.txt`**,
ein Fall je Abschnitt (`# === <fall> ===`). Die Endung ist bewusst **nicht**
`.py`, weil die Scanfläche `tests/**/*.py` ist; die Tests laden den
Abschnitt, schreiben ihn nach `tmp_path` und lassen den Scanner darauf
los. Damit setzt das Wächtermodul selbst keinen einzigen Pfad mehr
zusammen und braucht keine Rücksicht mehr auf die eigene Regel. Dass die
Ablage wirklich außerhalb der Reichweite liegt, wird **empirisch** geprüft
(AC-12), nicht angenommen.

### Verstoßmeldung

Bei jedem neuen, unbegründeten Fund schlägt der Wächtertest fehl und
meldet `Code reference: <Datei>:<Zeile>` (Format wie in den übrigen
Adversary-/Wächter-Findings dieses Projekts), damit der Fund ohne Suchen
lokalisierbar ist.

## Expected Behavior

- **Input:** der aktuelle Stand von `tests/**/*.py` beim Testlauf.
- **Output:** `pytest`-Grün, solange kein Test seinen Prüfling über einen
  unbegründeten festen Hauptrepo-Pfad lädt. Rot mit
  `Code reference: <Datei>:<Zeile>` bei jedem neuen Fund.
- **Side effects:** keine — reiner Lesezugriff auf den Quellbaum plus ein
  `git ls-files`-Aufruf.

## Acceptance Criteria

- **AC-1:** Given ein neu geschriebener Test, der ein `.claude/hooks/*.py`-Skript direkt über den ausgeschriebenen Pfad `/home/hem/gregor_zwanzig/...` lädt / When der Wächtertest läuft / Then meldet er diesen Test als Fund mit Datei- und Zeilenangabe und der Wächtertest schlägt fehl
  - Test: Synthetischer Testfall mit vollem String-Literal wird als Verstoß erkannt; Wächtertest ist rot.

- **AC-2:** Given ein neu geschriebener Test, der denselben Prüfling stattdessen über `KONSTANTE / "rel/pfad"` lädt, wobei `KONSTANTE` zuvor auf den Hauptrepo-Pfad gesetzt wurde / When der Wächtertest läuft / Then erkennt er diesen Fall ebenso zuverlässig wie den vollen Pfad-String — genau die Umgehungsform, an der eine reine Textsuche scheitert und die real in `test_issue_603` und `test_622` vorkommt
  - Test: Synthetischer Testfall mit Konstanten-Join wird als Verstoß erkannt; Wächtertest ist rot.

- **AC-3:** Given der heutige Bestand von 33 bewusst festen Fundstellen in 29 Testdateien (19 Klasse B, 14 Klasse C — u. a. `test_issue_348_parallel_workspaces.py` als Suchmuster, `test_issue_1004_startzeit_ssot.py` als Fallback nach dem Worktree-Pfad, die `.env`/`validator.env`-Tests sowie alle `REPO_DIR`/`MAIN_REPO`-Verzeichniskonstanten) / When der Wächtertest gegen den unveränderten Bestand läuft / Then bleiben alle 33 Fundstellen grün, ohne dass eine zentrale Ausnahmeliste sie einzeln aufführen muss
  - Test: Wächtertest läuft grün gegen den aktuellen Stand von `tests/`; keine der 33 bekannten Stellen erscheint in der Fehlermeldung.

- **AC-4:** Given ein Docstring oder Kommentar, der einen Hauptrepo-Pfad nennt, ohne dass der Pfad als Codeausdruck verwendet wird / When der Wächtertest läuft / Then löst diese Stelle keinen Alarm aus
  - Test: Synthetischer Testfall mit Hauptrepo-Pfad ausschließlich im Docstring wird nicht gemeldet; Wächtertest bleibt grün.

- **AC-5:** Given eine begründete Ausnahme in Form eines Kommentars `# gz-main-path: <Begründung>` direkt an der Fundstelle / When der Wächtertest läuft / Then wird dieser Fund durchgelassen — steht derselbe Marker jedoch ohne Begründungstext dahinter, bleibt der Fund rot
  - Test: Zwei synthetische Testfälle mit Marker-Kommentar (einer mit, einer ohne Begründungstext) zeigen das jeweils erwartete Ergebnis.

- **AC-6:** Given die Prüfdatum-Konstante in der Wächterdatei / When der Bestand nach dem Stichtag 2026-10-27 durchsucht wird / Then lässt sich das Prüfdatum maschinell auffinden (z. B. per `grep`), damit das spätere Gate-Audit es ohne manuelles Nachlesen lokalisieren kann
  - Test: `grep -n "2026-10-27" tests/tdd/test_repo_path_hardcoding_ratchet.py` liefert einen Treffer an der Konstantendefinition.

- **AC-7:** Given ein neu geschriebener Test, der den Prüfling über eine andere Auflösungsform (f-String, `+`-Verkettung oder `os.path.join`) mit Hauptrepo-Präfix lädt / When der Wächtertest läuft / Then wird auch diese Form erkannt, nicht nur das ausgeschriebene Literal und der Konstanten-Join
  - Test: Je ein synthetischer Testfall pro Auflösungsform (f-String, `+`-Verkettung, `os.path.join`) wird als Verstoß erkannt.

<!-- AC-8 bis AC-12 ergänzt in Fix-Loop 1 nach Adversary-Verdict BROKEN
     (Findings F001-F008). AC-1 bis AC-7 bleiben inhaltlich unverändert gültig. -->

- **AC-8:** Given ein Marker-Kommentar, dessen Begründung nur aus einem einzelnen Zeichen oder einem Emoji besteht (`# gz-main-path: x`, `# gz-main-path: 👍`) / When der Wächtertest läuft / Then bleibt der Fund rot, weil eine Ausnahme eine bewusste Entscheidung dokumentieren muss und nicht mit dem billigsten möglichen Zeichen erkauft werden darf
  - Test: Fixture mit beiden Alibi-Begründungen erzeugt zwei Funde.

- **AC-9:** Given ein berechtigter Fund in einem über mehrere Zeilen umbrochenen Klammerausdruck, dessen Marker hinter der schließenden Klammer steht / When der Wächtertest läuft / Then gilt die Ausnahme, denn sonst ist ein Marker bei der im Repo üblichen Formatierung praktisch nicht anbringbar — ein Marker zwei Zeilen vor dem Fund bzw. außerhalb der Anweisung gilt weiterhin nicht
  - Test: Fixture „mehrzeilig mit Schluss-Marker" ergibt keinen Fund, Fixture „Marker zwei Zeilen davor" ergibt einen Fund.

- **AC-10:** Given ein Test, der seinen Prüfling über eine der statisch vollständig auflösbaren Umgehungsformen lädt (`.joinpath()`, `.format()`, `"sep".join()`, `%`-Formatierung, Listen-/Tupel-Index, Dict-Schlüssel, Tupel-Entpackung) / When der Wächtertest läuft / Then wird jede dieser Formen als Fund gemeldet, denn keine von ihnen ist laufzeitgebaut, tot oder ungetrackt und fällt damit unter die Known Limitations
  - Test: Je ein synthetischer Testfall pro Form erzeugt genau einen Fund.

- **AC-11:** Given ein Suchmuster-Assert, der einen Hauptrepo-Pfad auf eine getrackte Einzeldatei als bloßes String-Literal in einem Vergleich nennt (`assert "<pfad>" not in inhalt`) / When der Wächtertest läuft / Then entsteht kein Fund, während ein im Vergleich tatsächlich ausgewerteter Ladeausdruck weiterhin gemeldet wird
  - Test: Fixture „Suchmuster-Assert" ergibt keinen Fund.

- **AC-12:** Given die ausgelagerten Fixture-Quelltexte, die absichtlich echte Verstöße enthalten / When der Wächter über den Testbaum läuft / Then wird ihre Ablage nachweislich nicht mitgescannt, sodass der Wächter weder seine eigenen Fixtures meldet noch seine Regel um seiner selbst willen einschränken muss
  - Test: Die Vorlagendatei enthält den Hauptrepo-Pfad, taucht aber nicht in `tests/**/*.py` auf, und ein Scan ihres Verzeichnisses liefert null Funde.

<!-- AC-13 ergänzt in Fix-Loop 2 nach Adversary-Finding F009. -->

- **AC-13:** Given ein Test, der den Hauptrepo-Pfad über eine Mehrfach- oder Kettenzuweisung an mehrere Namen bindet (`A = B = "..."`, `A = B = C = "..."`, `A = B, C = "x", "y"`, `A, *REST = ...`) und den Prüfling anschließend über einen der so gebundenen Namen zusammensetzt / When der Wächtertest läuft / Then wird der Fund gemeldet, unabhängig davon, welches Ziel der Zuweisung für den Join benutzt wurde — Mehrfachzuweisung ist gewöhnliches Python und keine Verschleierung
  - Test: Je ein synthetischer Testfall pro Zuweisungsform (drei Kettenformen, Mischform, Restform mit passender und mit überzähliger Wertanzahl) erzeugt genau einen Fund.

<!-- AC-14 ergänzt in Fix-Loop 3 nach Adversary-Finding F010. -->

- **AC-14:** Given ein Tausch zweier Namen in einer Anweisung (`A, B = B, A`), bei dem einer der beiden den Hauptrepo-Pfad trägt / When der Wächtertest läuft / Then folgt die Auswertung der tatsächlichen Python-Semantik: gemeldet wird ein Join über den Namen, der den Hauptrepo-Pfad **nach** dem Tausch trägt, und nicht gemeldet wird ein Join über den Namen, von dem der Pfad weggetauscht wurde
  - Test: Zwei synthetische Testfälle — „Tausch bewegt den Pfad weg" ergibt keinen Fund, „Tausch bewegt den Pfad auf den anderen Namen" ergibt genau einen Fund an der Ladezeile.

<!-- AC-15 ergänzt im Nachtrag zu Adversary-Finding F011. -->

- **AC-15:** Given eine rückwärts referenzierende Aliaskette, die genauso viele Glieder hat wie die in der Wächterdatei hinterlegte Rundenobergrenze / When der Wächtertest läuft / Then wird der Join über das oberste Kettenglied als Fund gemeldet, und die Kopplung zwischen Fixture-Tiefe und Obergrenze ist geprüft, sodass ein späteres Herabsetzen der Obergrenze auffällt statt die Reichweite still zu kürzen
  - Test: Fixture mit einer Kette in Länge der Obergrenze erzeugt genau einen Fund an der Ladezeile; der Test prüft zusätzlich, dass Kettenlänge und Obergrenze übereinstimmen.

## Test Plan

Alle Läufe erfolgen über `uv run pytest tests/tdd/test_repo_path_hardcoding_ratchet.py -v` im Sitzungs-Worktree.

- **AC-1 (volles Literal):**
  - Input: temporäre synthetische Testdatei (in `tmp_path` bzw. als
    In-Memory-AST-Fixture innerhalb des Wächtertests selbst), die
    `Path("/home/hem/gregor_zwanzig/.claude/hooks/<eine-echte-getrackte-Datei>.py")`
    als Prüfling lädt.
  - Vorgehen: Wächter-interne Scan-Funktion direkt auf diese Fixture
    anwenden (Unit-Test der Erkennungslogik, kein voller Repo-Scan
    nötig).
  - Erwarteter Output: Scan-Funktion meldet genau einen Fund mit
    korrekter Datei:Zeile-Angabe.

- **AC-2 (Konstanten-Join):**
  - Input: Fixture mit `REPO = Path("/home/hem/gregor_zwanzig")` in Zeile
    N, `REPO / ".claude/hooks/<datei>.py"` in Zeile N+1.
  - Vorgehen: Scan-Funktion auf die Fixture anwenden.
  - Erwarteter Output: Fund an Zeile N+1 (dem Join), nicht an Zeile N
    (der Verzeichniskonstante selbst).

- **AC-3 (Bestandsschutz):**
  - Input: unveränderter Stand von `tests/**/*.py`.
  - Vorgehen: `uv run pytest tests/tdd/test_repo_path_hardcoding_ratchet.py -v`
    gegen den echten Repo-Baum ausführen.
  - Erwarteter Output: Exit 0. Ergänzend: Testlauf-Log enthält keine
    Erwähnung von `test_issue_348_parallel_workspaces.py`,
    `test_issue_1004_startzeit_ssot.py` oder einer `.env`/`REPO_DIR`-Stelle.

- **AC-4 (Docstring-Ausschluss):**
  - Input: Fixture mit `"""Siehe /home/hem/gregor_zwanzig/docs/x.md"""` als
    Docstring, kein Codeausdruck mit diesem Pfad.
  - Vorgehen: Scan-Funktion auf die Fixture anwenden.
  - Erwarteter Output: Kein Fund.

- **AC-5 (Marker-Kommentar):**
  - Input: zwei Fixtures — (a) Fund-Zeile mit
    `# gz-main-path: Zugangsdaten sollen aus der produktiven .env kommen`,
    (b) identische Fund-Zeile mit `# gz-main-path:` ohne folgenden Text.
  - Vorgehen: Scan-Funktion auf beide Fixtures anwenden.
  - Erwarteter Output: (a) kein Fund, (b) ein Fund.

- **AC-6 (Prüfdatum auffindbar):**
  - Input: `tests/tdd/test_repo_path_hardcoding_ratchet.py`.
  - Vorgehen: `grep -n "2026-10-27" tests/tdd/test_repo_path_hardcoding_ratchet.py`
    ausführen.
  - Erwarteter Output: genau ein Treffer an der Konstantendefinition
    (analog `EXPIRY` in `test_naming_gate.py`).

- **AC-7 (weitere Auflösungsformen):**
  - Input: drei Fixtures — f-String
    (`f"{'/home/hem/gregor_zwanzig'}/.claude/hooks/<datei>.py"` bzw.
    gleichwertige Konstruktion), `+`-Verkettung
    (`"/home/hem/gregor_zwanzig" + "/.claude/hooks/<datei>.py"`),
    `os.path.join("/home/hem/gregor_zwanzig", ".claude/hooks/<datei>.py")`.
  - Vorgehen: Scan-Funktion auf jede Fixture einzeln anwenden.
  - Erwarteter Output: jede der drei Formen erzeugt genau einen Fund.

## Known Limitations

Übernommen aus `docs/context/fix-1409b-pfad-waechter.md`, Abschnitt „Was
der Wächter ausdrücklich nicht fängt" — bewusst nicht Teil dieser
Lieferung:

1. **Tote Pfade** (Ziel existiert weder im Repo-Index noch auf der
   Platte) werden nicht erkannt. „Nicht getrackt" ist von „gibt es nicht"
   nicht unterscheidbar. Ein Zusatzcheck wäre möglich, prüfte dann aber
   Hostzustand statt Code und schlüge auf einem Host ohne `.env` oder
   ohne gebautes `gregor-api` falsch an — bewusst nicht aufgenommen.
2. **Zur Laufzeit gebaute Pfade** (`os.environ`, Funktionsrückgaben, over
   dynamisch berechnete Strings) sind statisch nicht auflösbar und bleiben
   unentdeckt.
3. **Ungetrackte Ziele** (Dateien, die noch nicht `git add`-et sind) lösen
   keinen Fund aus, weil die Regel ausschließlich gegen `git ls-files`
   prüft.
4. **Alles außerhalb `tests/`** liegt außerhalb der Scanfläche — ebenso
   alles unter `/home/hem/gregor_zwanzig_staging/`.
5. **Prüflinge, die selbst hart auf das Hauptrepo verdrahtet sind**
   (z. B. `prod_selftest.py:56`, geteilte Attestation) werden vom Wächter
   nicht erfasst — das ist eine bewusste Produktentscheidung im
   Prüfling selbst, keine falsche Testpfadwahl, und kann durch
   Pfadwahl im Test nicht umgangen werden.

Ergänzt in **Fix-Loop 1**, Begründung in **Fix-Loop 3** geschärft. Die
Trennlinie verläuft nicht am Aufwand, sondern an der Sache: aufgelöst
werden Schreibweisen, die einen Pfad **zusammensetzen** (Erkennungsregel
Punkt 2) — das ist der Weg, auf dem ein Hauptrepo-Pfad versehentlich in
einen Test gerät. Nicht aufgelöst werden Schreibweisen, die einen fertigen
String nachträglich **verändern** oder eine Variable über mehrere
Anweisungen hinweg **umbinden**. Empirisch gegen die Scan-Funktion
geprüft, deshalb hier benannt statt stillschweigend offen gelassen:

6. **String-Chirurgie** (`"…/XX".replace("XX", …)`, `removeprefix`,
   Slicing, `rstrip`) wird nicht aufgelöst. Nicht, weil es zu aufwendig
   wäre — die Auflösungsmaschinerie könnte es inzwischen —, sondern weil
   diese Formen einen Pfad nicht zusammensetzen, sondern einen bereits
   fertigen nachträglich umbauen. Im gesamten Bestand kommt das an keiner
   Stelle vor; wer so schreibt, verschleiert absichtlich, und dagegen
   schützt kein statischer Scanner zuverlässig. Kommt die Form je real
   vor, gehört sie in Punkt 2 statt hierher.
7. **Umbindung und Akkumulation über mehrere Anweisungen** (`P += "/rel"`,
   mehrfache bedingte Zuweisung derselben Konstante) wird nicht
   modelliert: das Konstanten-Modell ist einfach-zuweisend und nicht
   ablaufsensitiv, die letzte statisch auflösbare Zuweisung gewinnt. Eine
   `+=`-Auflösung über die Fixpunkt-Iteration würde Werte mehrfach
   anhängen und ist deshalb ausgeschlossen. **Innerhalb** einer Anweisung
   ist die Auswertung dagegen korrekt (gleichzeitige Bindung, siehe
   Erkennungsregel Punkt 2 und AC-14).
8. **Nicht-konstante Ausdrücke in Vergleichen** (`assert (REPO / "hooks/x.py")
   not in liste`) werden weiterhin gemeldet, obwohl dort nichts geladen
   wird. Automatisch unterschieden wird nur der nackte Konstanten-Operand
   (Erkennungsregel 3a) — für den seltenen Rest ist der Marker der Weg.
   Die Richtung ist bewusst so gewählt: begründetes Rot kostet einen
   Kommentar, ein Falsch-negativ kostet ein falsches Grün.
9. **Marker-Fenster bei zusammengesetzten Anweisungen:** Ein Marker im
   Rumpf einer Funktion entschuldigt keinen Fund im selben Rumpf; er muss
   an der Anweisung stehen, in der der Fund entsteht.
10. **Kettentiefe der Konstantenauflösung ist endlich** (Nachtrag F011).
    Konstanten werden in Runden aufgelöst; eine rückwärts referenzierende
    Aliaskette (`G = F`, `F = E`, …, `A = "/home/hem/gregor_zwanzig"`)
    braucht so viele Runden, wie sie Glieder hat. Die Obergrenze steht als
    `_MAX_ROUNDS` in der Wächterdatei und beträgt **25**: Ketten bis 25
    Glieder werden erkannt, ab 26 Gliedern wird **nichts** gemeldet — ohne
    Hinweis, der Fund fällt schlicht weg. Eine feste Obergrenze deckelt
    den Aufwand bei pathologischen Dateien; beliebig tiefe Ketten sind
    damit grundsätzlich nicht abgedeckt. Die Zahl ist offengelegt, weil
    die Reichweite des Wächters an ihr hängt, und durch AC-15 an eine
    gleich tiefe Fixture gekoppelt: ein späteres Herabsetzen macht den
    Test rot, statt die Reichweite still zu kürzen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testinfrastruktur-Absicherung ohne Auswirkung auf
  Produktarchitektur, Datenmodell, Kanäle oder Provider — keine
  Entscheidungsfläche im Sinne der ADR-Kriterien.

## Changelog

- 2026-07-29: Initial spec erstellt — Issue #1409, Lieferung B
- 2026-07-29: Fix-Loop 1 nach Adversary-Verdict BROKEN (F001–F008) —
  Erkennungsregel um alle statisch auflösbaren Umgehungsformen erweitert,
  Suchmuster-Operanden automatisch ausgenommen (F006), Marker-Mindestlänge
  und Marker-Fenster bis zum Anweisungsende ergänzt (F007/F008),
  Fixture-Quelltexte nach `tests/fixtures/ratchet_cases/faelle.py.txt`
  ausgelagert (F002-Selbstbezug), AC-8..AC-12 und Known Limitations 6–9
  ergänzt. AC-1..AC-7 unverändert.
- 2026-07-29: Fix-Loop 2 nach Adversary-Finding F009 — Mehrfach- und
  Kettenzuweisung binden jetzt alle Ziele (inkl. Mischform und
  Restentpackung `A, *REST = ...`), AC-13 ergänzt. Known Limitations,
  Marker-Härtung und die F006-Entscheidung unverändert; keine neue
  Bestandsstelle sichtbar geworden (Testbaum weiterhin 0 Funde).
- 2026-07-29: Fix-Loop 3 nach Adversary-Finding F010 — Ziel-Wert-Paare
  einer Zuweisung werden gleichzeitig ausgewertet (Pythons Semantik),
  wodurch der in Fix-Loop 2 eingeschleppte Tausch-Fehlalarm und der
  zugehörige Durchlässer entfallen; AC-14 ergänzt, Begründung von Known
  Limitation 6 geschärft (Sache statt Aufwand), Limitation 7 auf
  „über mehrere Anweisungen" präzisiert.
- 2026-07-29: Nachtrag zu Adversary-Finding F011 (LOW) — Rundenobergrenze
  `_MAX_ROUNDS` von 5 auf 25 angehoben und der Abbruch auf den echten
  Fixpunkt umgestellt (Rundenende gleich Rundenanfang statt „nichts
  geschrieben"); dadurch ist der Voll-Scan von der Obergrenze entkoppelt
  und mit 2,1 s schneller als zuvor mit 5 Runden (2,4 s). AC-15 und Known
  Limitation 10 ergänzt.
