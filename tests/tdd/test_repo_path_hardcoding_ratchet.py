"""Waechter (#1409 Lieferung B): kein Test laedt seinen Pruefling ueber einen
fest verdrahteten Hauptrepo-Pfad.

Wer `/home/hem/gregor_zwanzig/...` fest verdrahtet, prueft aus einem Worktree
heraus die unveraenderte Hauptrepo-Kopie und meldet falsches Gruen. Lieferung A
hat fuenf solche Faelle repariert; diese Datei verhindert ihre Rueckkehr.

Vertrag und Implementierung stehen in dieser Datei (Spec:
`docs/specs/modules/fix_1409b_repo_path_ratchet.md`, Bauform-Vorbild:
`.claude/hooks/test_naming_gate.py`); die Fixture-Quelltexte liegen in
`tests/fixtures/ratchet_cases/faelle.py.txt`.

Vertrag der Modul-Symbole
-------------------------
`EXPIRY: datetime.date` — Pruefdatum des Regel-Budgets (Vorbild `EXPIRY` in
test_naming_gate.py); das ISO-Datum steht zusaetzlich als Text in der Datei.

`scan_for_hardcoded_repo_paths(tests_root: Path, repo_root: Path) -> list[Finding]`
durchsucht `tests_root` rekursiv nach `*.py` und meldet jede Codestelle, die
einen Pfad unter `/home/hem/gregor_zwanzig` auf eine Datei aufloest, die
`git ls-files` (ausgefuehrt in `repo_root`) als getrackt fuehrt. Aufgeloest wird
nach Regel R2+: String-Literale, `KONSTANTE / "rel/pfad"`-Joins ueber eine im
selben Modul zugewiesene Konstante (auch aus Tupel-Entpackung), f-Strings,
`+`-Verkettung, `os.path.join`, `.joinpath()`, `str.format()`,
`%`-Formatierung sowie Index-Zugriffe auf konstante Listen/Tupel/Dicts.
Ausgewertet werden nur AST-Codeliterale, keine Docstrings/Kommentare. Ein Ziel,
das kein getracktes File ist (Verzeichnis, Suchmuster), ist NIE ein Fund; ein
Praefixvergleich gegen den Index findet nicht statt. Ein blosses String-Literal
als Operand eines Vergleichs (`assert "<pfad>" not in inhalt`) ist ein
Suchmuster und laedt nichts — es wird nie gemeldet. Ausnahme:
`# gz-main-path: <Begruendung>` von der Zeile vor dem Fund bis zum Ende der
Anweisung, in der er steht — eine Begruendung mit weniger als
`_MIN_BEGRUENDUNG` sinnvollen Zeichen zaehlt nicht.

`Finding` traegt mindestens `.path` (Path der geprueften Datei), `.line`
(1-basierte Zeile des aufloesenden Ausdrucks) und `.target` (repo-relatives Ziel).
"""

import ast
import os
import re
import subprocess
import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

# Wurzel DIESES Checkouts (Worktree) — bewusst nicht das Hauptrepo: der
# Waechter muss den Baum pruefen, in dem gerade gearbeitet wird.
REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = REPO_ROOT / "tests"

# Fixture-Quelltexte liegen AUSSERHALB dieses Moduls (Endung .py.txt, deshalb
# ausserhalb der Scanflaeche `tests/**/*.py`). Damit setzt dieses Modul selbst
# keinen einzigen Pfad mehr zusammen und braucht keine Ruecksicht mehr auf die
# eigene Erkennungsregel — der frueher dafuer benutzte str.format()-Umweg war
# genau die Luecke, die der Waechter schliessen soll.
_FAELLE_DATEI = REPO_ROOT / "tests/fixtures/ratchet_cases/faelle.py.txt"

# `_MAIN` ist ein VERZEICHNIS-Literal und per Konstruktion nie ein Fund;
# `_HOOK_B` ist repo-relativ, ohne Praefix.
_MAIN = "/home/hem/gregor_zwanzig"
_HOOK_B = ".claude/hooks/design_fidelity_diff.py"


def _fall(name: str) -> str:
    """Fixture-Quelltext `name` aus der externen Vorlagendatei holen."""
    abschnitte = re.split(
        r"^# === (\S+) ===$\n", _FAELLE_DATEI.read_text("utf-8"), flags=re.M
    )
    vorrat = dict(zip(abschnitte[1::2], abschnitte[2::2]))
    assert name in vorrat, f"Fall {name!r} fehlt in {_FAELLE_DATEI}: {sorted(vorrat)}"
    return vorrat[name].replace("@WS@", "   ")


def _fixture(tmp_path: Path, source: str) -> Path:
    """Echte Testdatei-Attrappe auf die Platte schreiben (kein Mock)."""
    f = tmp_path / "test_attrappe.py"
    f.write_text(source, encoding="utf-8")
    return f


def _scan(tests_root: Path):
    return scan_for_hardcoded_repo_paths(tests_root, REPO_ROOT)  # noqa: F821


def _line_of(source: str, needle: str) -> int:
    for n, line in enumerate(source.splitlines(), 1):
        if needle in line:
            return n
    raise AssertionError(f"Ankertext {needle!r} fehlt im Fixture-Quelltext")


def _refs(findings) -> str:
    return ", ".join(f"{f.path}:{f.line}" for f in findings) or "(keine)"


def test_fixture_vorlagen_liegen_ausserhalb_der_scanflaeche():
    """Voraussetzung der Auslagerung — empirisch, nicht angenommen: die
    Vorlagendatei enthaelt echte Verstoesse und darf trotzdem nie mitgescannt
    werden, sonst meldete der Waechter seine eigenen Fixtures."""
    assert _MAIN in _FAELLE_DATEI.read_text("utf-8"), "Vorlage ohne echten Verstoss"
    assert _FAELLE_DATEI not in set(TESTS_ROOT.rglob("*.py"))
    assert not _scan(_FAELLE_DATEI.parent), (
        "Der Scanner sammelt die Vorlagendatei ein — dann meldet der Waechter "
        "seine eigenen Fixtures."
    )


def test_ac1_ausgeschriebener_hauptrepo_pfad_wird_gemeldet(tmp_path):
    src = _fall("literal")
    datei = _fixture(tmp_path, src)
    findings = _scan(tmp_path)
    assert len(findings) == 1, f"erwartet 1 Fund, bekommen: {_refs(findings)}"
    assert findings[0].line == _line_of(src, "PRUEFLING =")
    assert Path(findings[0].path) == datei


def test_ac2_konstanten_join_wird_gemeldet(tmp_path):
    """Wichtigster Fall: genau an dieser Form sind test_issue_603 und test_622
    einer reinen Textsuche entgangen — das Literal ist nur das Verzeichnis,
    der Verstoss entsteht erst im Join der Folgezeile."""
    src = _fall("konstanten-join")
    _fixture(tmp_path, src)
    findings = _scan(tmp_path)
    assert len(findings) == 1, f"erwartet 1 Fund, bekommen: {_refs(findings)}"
    assert findings[0].line == _line_of(src, "DIFF ="), (
        "Fund gehoert an den Join, nicht an die Verzeichnis-Konstante"
    )
    assert findings[0].target == _HOOK_B


def test_ac3_echter_testbaum_ohne_fehlalarm():
    kandidaten = [
        f"{p}:{n}"
        for p in sorted(TESTS_ROOT.rglob("*.py"))
        for n, zeile in enumerate(
            p.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        )
        if _MAIN in zeile
    ]
    assert len(kandidaten) >= 20, (
        f"Nur {len(kandidaten)} Kandidatenzeilen im Testbaum (heute 33) — "
        "ein leeres Scan-Ergebnis waere dann auch bei kaputtem Scanner gruen."
    )
    findings = _scan(TESTS_ROOT)
    assert not findings, (
        "Fehlalarm auf dem Bestand. Diese Durchlaesser MUESSEN gruen bleiben:\n"
        "  test_issue_348_parallel_workspaces.py — Suchmuster, kein Ladepfad\n"
        "  test_issue_1004_startzeit_ssot.py — Fallback NACH dem Worktree-Pfad\n"
        "  REPO_DIR / MAIN_REPO — Verzeichnis-Konstanten, kein getracktes File\n"
        + "\n".join(f"Code reference: {f.path}:{f.line}" for f in findings)
    )


def test_ac4_pfad_nur_in_docstring_oder_kommentar_ist_kein_fund(tmp_path):
    _fixture(tmp_path, _fall("docstring-und-kommentar"))
    findings = _scan(tmp_path)
    assert not findings, f"Docstring/Kommentar darf nicht melden: {_refs(findings)}"


def test_ac5_marker_mit_begruendung_laesst_durch(tmp_path):
    _fixture(tmp_path, _fall("marker-mit-begruendung"))
    findings = _scan(tmp_path)
    assert not findings, (
        f"Marker (vorausgehende UND gleiche Zeile) muss durchlassen: {_refs(findings)}"
    )


def test_ac5_marker_ohne_begruendung_bleibt_rot(tmp_path):
    _fixture(tmp_path, _fall("marker-ohne-begruendung"))
    findings = _scan(tmp_path)
    assert len(findings) == 2, (
        f"Marker ohne Begruendungstext ist keine Ausnahme: {_refs(findings)}"
    )


def test_ac8_alibi_begruendung_zaehlt_nicht(tmp_path):
    """Ein Zeichen oder ein Emoji ist keine bewusste Entscheidung, sondern das
    billigste Mittel, jeden echten Fund verschwinden zu lassen (Adversary F007)."""
    _fixture(tmp_path, _fall("marker-zu-kurz"))
    findings = _scan(tmp_path)
    assert len(findings) == 2, (
        f"'x' und '👍' sind keine Begruendung (>= {_MIN_BEGRUENDUNG} sinnvolle "
        f"Zeichen noetig): {_refs(findings)}"
    )


def test_ac9_marker_am_ende_eines_mehrzeiligen_ausdrucks_laesst_durch(tmp_path):
    """Bei umbrochenen Ausdruecken steht der Marker natuerlicherweise hinter der
    schliessenden Klammer — dort muss er gelten, sonst ist eine berechtigte
    Ausnahme praktisch nicht anbringbar (Adversary F008)."""
    _fixture(tmp_path, _fall("marker-mehrzeilig"))
    findings = _scan(tmp_path)
    assert not findings, f"Marker auf der Schlusszeile muss gelten: {_refs(findings)}"


def test_ac9_marker_zwei_zeilen_vor_dem_fund_gilt_nicht(tmp_path):
    """Gegenprobe zur Fensteraufweitung: das Fenster endet vor der Anweisung."""
    _fixture(tmp_path, _fall("marker-zwei-zeilen-davor"))
    findings = _scan(tmp_path)
    assert len(findings) == 1, (
        f"Marker ausserhalb der Anweisung darf nicht gelten: {_refs(findings)}"
    )


def test_ac6_pruefdatum_ist_maschinell_auffindbar():
    assert EXPIRY == date(2026, 10, 27), (  # noqa: F821
        "Pruefdatum des Regel-Budgets (+90 Tage), Vorbild EXPIRY in test_naming_gate.py"
    )
    text = Path(__file__).read_text(encoding="utf-8").splitlines()
    treffer = [n for n, z in enumerate(text, 1) if EXPIRY.isoformat() in z]  # noqa: F821
    assert treffer, (
        "Das ISO-Pruefdatum muss als Text in dieser Datei stehen, damit das "
        "Gate-Audit es per grep findet (Vorbild test_naming_gate.py)."
    )


@pytest.mark.parametrize("form", ["f-string", "plus-verkettung", "os-path-join"])
def test_ac7_weitere_aufloesungsformen_werden_erkannt(tmp_path, form):
    _fixture(tmp_path, _fall(form))
    findings = _scan(tmp_path)
    assert len(findings) == 1, f"{form}: erwartet 1 Fund, bekommen: {_refs(findings)}"


@pytest.mark.parametrize(
    "form",
    [
        "joinpath",
        "format",
        "str-join",
        "prozent-formatierung",
        "listen-index",
        "dict-index",
        "tupel-entpackung",
    ],
)
def test_ac10_statisch_aufloesbare_umgehungsformen_werden_erkannt(tmp_path, form):
    """Adversary F001-F005: sechs Schreibweisen, die den Pfad zur Scan-Zeit
    vollstaendig festlegen — keine faellt unter die Known Limitations (nichts
    davon ist laufzeitgebaut, tot oder ungetrackt). Wer sie durchlaesst,
    verkauft truegerische Sicherheit."""
    _fixture(tmp_path, _fall(form))
    findings = _scan(tmp_path)
    assert len(findings) == 1, f"{form}: erwartet 1 Fund, bekommen: {_refs(findings)}"


@pytest.mark.parametrize(
    "form",
    [
        "kettenzuweisung",
        "kettenzuweisung-drei-ziele",
        "kettenzuweisung-pfad-objekt",
        "kettenzuweisung-mischform",
        "restentpackung",
        "restentpackung-ueberzaehlig",
    ],
)
def test_ac13_mehrfachzuweisung_bindet_alle_ziele(tmp_path, form):
    """Adversary F009: `A = B = "..."` ist gewoehnliches Python, keine
    Verschleierung. Wer nur das erste Ziel bindet, laesst jeden Join ueber den
    zweiten Namen unbemerkt durch — inklusive der Restform `A, *REST = ...`,
    bei der Ziel- und Wertanzahl auseinanderfallen duerfen."""
    _fixture(tmp_path, _fall(form))
    findings = _scan(tmp_path)
    assert len(findings) == 1, f"{form}: erwartet 1 Fund, bekommen: {_refs(findings)}"


def test_ac14_tausch_folgt_der_gleichzeitigen_auswertung(tmp_path):
    """Adversary F010, Fehlalarm-Richtung: nach `OTHER, MAIN = MAIN, OTHER`
    traegt MAIN zur Laufzeit den harmlosen Wert — es wird nichts aus dem
    Hauptrepo geladen, also darf hier nichts gemeldet werden."""
    _fixture(tmp_path, _fall("tausch-kein-ladepfad"))
    findings = _scan(tmp_path)
    assert not findings, (
        f"Der Tausch hat den Hauptrepo-Pfad wegbewegt: {_refs(findings)}"
    )


def test_ac14_tausch_verschiebt_den_verstoss_auf_den_anderen_namen(tmp_path):
    """Adversary F010, Durchlaesser-Richtung — die teurere Haelfte: nach
    `A, B = B, A` traegt B den Hauptrepo-Pfad. Wer die Ziele nacheinander statt
    gleichzeitig bindet, sieht hier gar nichts."""
    src = _fall("tausch-echter-verstoss")
    _fixture(tmp_path, src)
    findings = _scan(tmp_path)
    assert len(findings) == 1, f"erwartet 1 Fund, bekommen: {_refs(findings)}"
    assert findings[0].line == _line_of(src, "ECHT_VERSTOSS =")


def test_ac15_aliaskette_bis_zur_obergrenze_wird_erkannt(tmp_path):
    """Adversary F011: die Reichweite des Waechters haengt an `_MAX_ROUNDS` —
    eine rueckwaerts referenzierende Aliaskette braucht so viele Runden, wie sie
    Glieder hat. Die Fixture ist genau so tief wie die Obergrenze: wer die
    Grenze spaeter senkt, macht diesen Test rot statt still die Reichweite zu
    kuerzen. Tiefere Ketten bleiben unerkannt (Known Limitation 10)."""
    src = _fall("aliaskette-bis-obergrenze")
    kette = [z for z in src.splitlines() if re.fullmatch(r"A\d+ = .+", z)]
    assert len(kette) == _MAX_ROUNDS, (
        f"Fixture-Kette ({len(kette)} Glieder) und Obergrenze ({_MAX_ROUNDS}) "
        "muessen zusammenpassen, sonst prueft der Test die Grenze nicht mehr."
    )
    _fixture(tmp_path, src)
    findings = _scan(tmp_path)
    assert len(findings) == 1, f"erwartet 1 Fund, bekommen: {_refs(findings)}"
    assert findings[0].line == _line_of(src, "PRUEFLING =")


def test_ac11_suchmuster_im_vergleich_ist_kein_ladepfad(tmp_path):
    """Adversary F006: `assert "<pfad>" not in inhalt` laedt nichts — ein blosses
    String-Literal als Vergleichsoperand kann per Konstruktion nichts oeffnen.
    Der heutige Bestand (test_issue_348) entkam nur, weil sein Suchmuster
    zufaellig ein Verzeichnis ist; bei einer Einzeldatei war es ein Fehlalarm."""
    _fixture(tmp_path, _fall("suchmuster-assert"))
    findings = _scan(tmp_path)
    assert not findings, f"Suchmuster ist kein Ladepfad: {_refs(findings)}"


def test_verzeichnis_literal_allein_ist_nie_ein_fund(tmp_path):
    """Randbedingung: nur ein aufgeloestes, per `git ls-files` getracktes FILE
    ist ein Fund. Ein Praefixvergleich gegen den Index wuerde den gesamten
    Bestand (REPO_DIR, MAIN_REPO, HARDCODED_PREFIX) rot faerben."""
    _fixture(tmp_path, _fall("nur-verzeichnisse"))
    findings = _scan(tmp_path)
    assert not findings, f"Verzeichnisse sind keine Fundstellen: {_refs(findings)}"


# ---------------------------------------------------------------------------
# Implementierung der Scan-Logik (Regel R2+, Spec
# docs/specs/modules/fix_1409b_repo_path_ratchet.md)
# ---------------------------------------------------------------------------

# Regel-Budget (CLAUDE.md): ersetzt keine bestehende Regel, traegt daher ein
# Pruefdatum von +90 Tagen — 2026-10-27. Faengt der Waechter bis dahin keinen
# echten Verstoss, wird er im Gate-Audit (#1197) zurueckgebaut. Bauform-Vorbild
# fuer die Konstante: .claude/hooks/test_naming_gate.py.
EXPIRY = date(2026, 10, 27)

# Praefix eines Hauptrepo-Pfads. Der abschliessende Schraegstrich haelt
# /home/hem/gregor_zwanzig_staging/... bewusst draussen.
_MAIN_PREFIX = _MAIN + "/"

# Ausnahme an der Fundzeile; ohne Begruendungstext greift sie nicht.
_MARKER = re.compile(r"#\s*gz-main-path:(.*)$")

# Mindestlaenge der Begruendung, gemessen in Buchstaben/Ziffern (Vorbild:
# 30-Zeichen-Regel fuer Acceptance Criteria, CLAUDE.md). Haelt Alibi-Marker
# wie ": x" oder ": 👍" draussen — eine Ausnahme soll Arbeit kosten.
_MIN_BEGRUENDUNG = 15
_UNWORT = re.compile(r"[\W_]+")

# Aufloesbare Konstruktoren. os.path.join/join wird wie ein Pfad-Join behandelt.
_PATH_CALLS = frozenset(
    {"Path", "PurePath", "PosixPath", "PurePosixPath"}
    | {f"pathlib.{n}" for n in ("Path", "PurePath", "PosixPath", "PurePosixPath")}
)
_JOIN_CALLS = frozenset({"os.path.join", "path.join", "join", "posixpath.join"})
_METHODEN = frozenset({"joinpath", "format", "join"})
# Trennzeichen-Konstanten, damit `os.sep.join([...])` aufloesbar bleibt.
_ATTRIBUT_KONSTANTEN = {"os.sep": "/", "os.path.sep": "/", "posixpath.sep": "/"}

# Fixpunkt-Runden fuer voneinander abhaengige Konstanten. Eine rueckwaerts
# referenzierende Aliaskette (`G = F` ... `A = "..."`) braucht so viele Runden,
# wie sie Glieder hat; tiefer verkettete Ketten bleiben unerkannt (Known
# Limitation 10). Die Obergrenze deckelt den Aufwand bei pathologischen
# Dateien — seit der Abbruch am echten Fixpunkt haengt, kostet sie im Bestand
# nichts mehr (Voll-Scan ~2,0 s bei 5 wie bei 50 Runden).
_MAX_ROUNDS = 25
_MAX_DEPTH = 12
_TRACKED_CACHE: dict[str, frozenset] = {}


@dataclass(frozen=True)
class Finding:
    """Eine Fundstelle: Datei, 1-basierte Zeile, repo-relatives Ziel."""

    path: Path
    line: int
    target: str


def _tracked_files(repo_root: Path) -> frozenset:
    """Alle per `git ls-files` getrackten DATEIEN — einmal pro Lauf, nicht je Datei."""
    key = str(repo_root)
    if key not in _TRACKED_CACHE:
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=key,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        _TRACKED_CACHE[key] = frozenset(p for p in out.split("\0") if p)
    return _TRACKED_CACHE[key]


def _dotted(node) -> str:
    """`os.path.join` aus einem Attribute/Name-Ausdruck als Text."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        vorher = _dotted(node.value)
        return f"{vorher}.{node.attr}" if vorher else node.attr
    return ""


def _join(links: str, rechts: str) -> str:
    if rechts.startswith("/"):
        return rechts
    return links.rstrip("/") + "/" + rechts


def _resolve(node, consts: dict, tiefe: int = 0):
    """Statischer Pfad-Wert eines Ausdrucks oder None, wenn nicht aufloesbar."""
    wert = _value(node, consts, tiefe)
    return wert if isinstance(wert, str) else None


def _value(node, consts: dict, tiefe: int = 0):
    """Statischer Wert (Text, Zahl, Folge, Zuordnung) oder None.

    Breiter als `_resolve`, weil ein Pfad auch aus einem Container stammen kann
    (`PATHS[0] / "rel"`); die Pfadpruefung filtert danach auf Text.
    """
    if tiefe > _MAX_DEPTH:
        return None
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, (str, int)) else None
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    if isinstance(node, ast.Attribute):
        return _ATTRIBUT_KONSTANTEN.get(_dotted(node))
    if isinstance(node, (ast.Tuple, ast.List)):
        return tuple(_value(e, consts, tiefe + 1) for e in node.elts)
    if isinstance(node, ast.Dict):
        return {
            schluessel.value: _value(wert, consts, tiefe + 1)
            for schluessel, wert in zip(node.keys, node.values)
            if isinstance(schluessel, ast.Constant)
        }
    if isinstance(node, ast.Subscript):
        return _subscript(node, consts, tiefe)
    if isinstance(node, ast.JoinedStr):  # f-String
        teile = []
        for wert in node.values:
            if isinstance(wert, ast.Constant) and isinstance(wert.value, str):
                teile.append(wert.value)
            elif isinstance(wert, ast.FormattedValue) and wert.format_spec is None:
                aufgeloest = _resolve(wert.value, consts, tiefe + 1)
                if aufgeloest is None:
                    return None
                teile.append(aufgeloest)
            else:
                return None
        return "".join(teile)
    if isinstance(node, ast.BinOp):
        return _binop(node, consts, tiefe)
    if isinstance(node, ast.Call):
        return _call(node, consts, tiefe)
    return None


def _subscript(node, consts: dict, tiefe: int):
    """`PATHS[0]` / `D["main"]` — nur bei vollstaendig konstantem Container."""
    basis = _value(node.value, consts, tiefe + 1)
    schluessel = _value(node.slice, consts, tiefe + 1)
    if isinstance(basis, tuple) and isinstance(schluessel, int):
        return basis[schluessel] if -len(basis) <= schluessel < len(basis) else None
    if isinstance(basis, dict) and isinstance(schluessel, str):
        return basis.get(schluessel)
    return None


def _binop(node, consts: dict, tiefe: int):
    links = _resolve(node.left, consts, tiefe + 1)
    if links is None:
        return None
    if isinstance(node.op, ast.Mod):  # "%s/rel" % KONSTANTE
        rechts = _value(node.right, consts, tiefe + 1)
        argumente = rechts if isinstance(rechts, (tuple, dict)) else (rechts,)
        if any(a is None for a in argumente):
            return None
        try:
            return links % argumente
        except (TypeError, ValueError):
            return None
    if not isinstance(node.op, (ast.Div, ast.Add)):
        return None
    rechts = _resolve(node.right, consts, tiefe + 1)
    if rechts is None:
        return None
    return _join(links, rechts) if isinstance(node.op, ast.Div) else links + rechts


def _call(node, consts: dict, tiefe: int):
    """Path()/os.path.join() sowie .joinpath(), .format() und "sep".join()."""
    name = _dotted(node.func)
    if (name in _PATH_CALLS or name in _JOIN_CALLS) and not node.keywords:
        teile = [_resolve(a, consts, tiefe + 1) for a in node.args]
        if teile and not any(t is None for t in teile):
            ergebnis = teile[0]
            for weiter in teile[1:]:
                ergebnis = _join(ergebnis, weiter)
            return ergebnis
    if not isinstance(node.func, ast.Attribute) or node.func.attr not in _METHODEN:
        return None
    basis = _resolve(node.func.value, consts, tiefe + 1)
    if basis is None:
        return None
    if node.func.attr == "join":  # "/".join([KONSTANTE, "rel/pfad"])
        folge = _value(node.args[0], consts, tiefe + 1) if len(node.args) == 1 else None
        if not isinstance(folge, tuple) or not all(isinstance(t, str) for t in folge):
            return None
        return basis.join(folge)
    teile = [_resolve(a, consts, tiefe + 1) for a in node.args]
    if any(t is None for t in teile):
        return None
    if node.func.attr == "joinpath":
        if node.keywords:
            return None
        for weiter in teile:
            basis = _join(basis, weiter)
        return basis
    benannt = {}
    for schluesselwort in node.keywords:  # "{x}/rel".format(x=KONSTANTE)
        wert = _resolve(schluesselwort.value, consts, tiefe + 1)
        if schluesselwort.arg is None or wert is None:
            return None
        benannt[schluesselwort.arg] = wert
    try:
        return basis.format(*teile, **benannt)
    except (IndexError, KeyError, ValueError, TypeError, AttributeError):
        return None


def _module_constants(tree) -> dict:
    """Namen -> statischer Wert, bis zum Fixpunkt aufgeloest.

    Traegt den Kern der Regel: erst dadurch wird aus `REPO = Path("...")` plus
    `REPO / "rel/pfad"` ein erkennbares Ziel (real belegt in test_issue_603
    und test_622).
    """
    consts: dict = {}
    for _ in range(_MAX_ROUNDS):
        vorher = dict(consts)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # ALLE Ziele: `A = B = "..."` bindet beide Namen, ebenso die
                # Mischform `A = B, C = "x", "y"`.
                ziele, wert = node.targets, node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                ziele, wert = [node.target], node.value
            else:
                continue
            # Erst ALLE Werte gegen den Stand VOR der Anweisung aufloesen, dann
            # binden — Python wertet die rechte Seite vollstaendig aus, bevor es
            # zuweist. Schrittweises Schreiben machte aus `A, B = B, A` sonst
            # `A, B = B, B`: Fehlalarm auf der einen, Durchlaesser auf der
            # anderen Seite des Tauschs.
            neu = {}
            for ziel in ziele:
                for name, ausdruck in _paare(ziel, wert):
                    aufgeloest = _value(ausdruck, consts)
                    if aufgeloest is not None:
                        neu[name] = aufgeloest
            consts.update(neu)
        # Abbruch am ECHTEN Fixpunkt: gleicher Stand am Rundenende wie am
        # Rundenanfang. Der Rundendurchlauf ist deterministisch, eine weitere
        # Runde koennte also nichts mehr aendern. Der frueher benutzte Test
        # „in dieser Runde wurde nichts geschrieben" greift bei Umbindung
        # (`x = "a"` ... `x = "b"`) nie — 127 der 668 Testdateien schoepften
        # dadurch stets alle Runden aus, was die Obergrenze teuer machte.
        if consts == vorher:
            break
    return consts


def _paare(ziel, wert) -> list:
    """Ein Zuweisungsziel auf Werte abbilden.

    Deckt `A = "..."`, die Entpackung `A, B = "...", "..."` und die Restform
    `A, *REST = ...` ab; bei letzterer binden die Namen vor dem Stern von
    vorn, die dahinter von hinten.
    """
    if isinstance(ziel, ast.Name):
        return [(ziel.id, wert)]
    if not isinstance(ziel, (ast.Tuple, ast.List)) or not isinstance(
        wert, (ast.Tuple, ast.List)
    ):
        return []
    elts, werte = ziel.elts, wert.elts
    sterne = [i for i, z in enumerate(elts) if isinstance(z, ast.Starred)]
    if len(sterne) > 1 or len(werte) < len(elts) - len(sterne):
        return []
    if not sterne:
        zuordnung = list(zip(elts, werte)) if len(elts) == len(werte) else []
    else:
        stern = sterne[0]
        danach = len(elts) - stern - 1
        zuordnung = list(zip(elts[:stern], werte[:stern]))
        if danach:
            zuordnung += list(zip(elts[stern + 1 :], werte[-danach:]))
    return [(z.id, w) for z, w in zuordnung if isinstance(z, ast.Name)]


def _relatives_ziel(wert, tracked: frozenset):
    """Repo-relatives Ziel, wenn der Pfad eine getrackte DATEI benennt.

    Kein Praefixvergleich gegen den Index: ein Verzeichnis (REPO_DIR,
    HARDCODED_PREFIX) ist nie ein Fund.
    """
    if not wert or not wert.startswith(_MAIN_PREFIX):
        return None
    rel = os.path.normpath(wert[len(_MAIN_PREFIX) :])
    return rel if rel in tracked else None


def _entschuldigt(zeilen: list, von: int, bis: int) -> bool:
    """Marker von der Zeile vor dem Fund bis zum Ende seiner Anweisung.

    Das Fenster endet nicht an der Fundzeile, weil `node.lineno` bei einem
    umbrochenen Ausdruck auf dessen ERSTE Zeile zeigt — der Marker steht dort
    aber hinter der schliessenden Klammer.
    """
    for nummer in range(von - 1, bis + 1):
        if 1 <= nummer <= len(zeilen):
            treffer = _MARKER.search(zeilen[nummer - 1])
            if treffer and len(_UNWORT.sub("", treffer.group(1))) >= _MIN_BEGRUENDUNG:
                return True
    return False


def _sammle(node, datei, zeilen, consts, tracked, funde, gesehen, ende=0) -> None:
    """Top-down; Docstrings bleiben aussen vor, ein Treffer stoppt den Abstieg."""
    if (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ):
        return  # freistehendes Stringliteral = Prosa, kein Ladepfad
    if isinstance(node, ast.stmt):
        # Fenster fuer den Ausnahme-Marker: nur einfache Anweisungen, sonst
        # entschuldigte ein Marker irgendwo im Rumpf die ganze Funktion.
        ende = 0 if hasattr(node, "body") else (node.end_lineno or node.lineno)
    # Ein blosser Namensverweis ist kein Fundort — gemeldet wird die Stelle,
    # an der der Pfad entsteht (der Join, nicht jede spaetere Verwendung).
    if isinstance(node, ast.expr) and not isinstance(node, ast.Name):
        ziel = _relatives_ziel(_resolve(node, consts), tracked)
        if ziel is not None:
            bis = max(node.end_lineno or node.lineno, ende)
            if (node.lineno, ziel) not in gesehen and not _entschuldigt(
                zeilen, node.lineno, bis
            ):
                gesehen.add((node.lineno, ziel))
                funde.append(Finding(path=datei, line=node.lineno, target=ziel))
            return
    for kind in ast.iter_child_nodes(node):
        # Ein blosses String-Literal als Vergleichsoperand ist ein Suchmuster
        # und kann per Konstruktion nichts laden — nie ein Fund.
        if isinstance(node, ast.Compare) and isinstance(kind, ast.Constant):
            continue
        _sammle(kind, datei, zeilen, consts, tracked, funde, gesehen, ende)


def scan_for_hardcoded_repo_paths(tests_root, repo_root) -> list:
    """Siehe Modul-Docstring: Vertrag der Scan-Funktion."""
    tracked = _tracked_files(Path(repo_root))
    funde: list = []
    for datei in sorted(Path(tests_root).rglob("*.py")):
        try:
            quelltext = datei.read_text(encoding="utf-8")
            baum = ast.parse(quelltext, filename=str(datei))
        except (OSError, SyntaxError, UnicodeDecodeError) as fehler:
            # Nicht verschlucken: eine unlesbare Datei ist eine Luecke im Schutz.
            warnings.warn(
                f"Pfad-Waechter konnte {datei} nicht pruefen: {fehler!r}",
                stacklevel=2,
            )
            continue
        _sammle(
            baum,
            datei,
            quelltext.splitlines(),
            _module_constants(baum),
            tracked,
            funde,
            set(),
        )
    return funde
