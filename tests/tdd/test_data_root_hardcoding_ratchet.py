"""Waechter (#1633 AC-5): kein repo-relativer ``data/...``-Pfad in src/ oder api/.

Wer `Path("data/diagnostics/...")` als Modul-Konstante bindet, umgeht
`app.loader.get_data_root()` und schreibt in den Programmordner statt an die
Produktiv-Datenwurzel (`GZ_DATA_DIR`, seit #1595 `/var/lib/gregor`). Drittes
Auftreten desselben Musters nach #1265 und #1595.

Bauform-Vorbild: `tests/tdd/test_repo_path_hardcoding_ratchet.py` (#1409), aber
schmaler. Gemeldet wird ein Ausdruck nur, wenn er statisch auf einen mit `data/`
beginnenden Pfad aufloest UND dabei durch einen Pfad-Aufruf oder `/`-Join
gelaufen ist. Eine blosse Zeichenkette (`logger.info("data/quota ...")`) ist KEIN
Fund — ein Waechter, der legitime Arbeit blockiert, wird abgeschaltet und
schuetzt danach gar nichts. AST statt Textsuche, weil Kommentare mit
`"data/users/..."` sonst Fehlalarm gaeben und der Join-Fall einer Textsuche
entginge. Aufrufnamen loest der Waechter ueber die Import-Bindungen der Datei
auf, nicht ueber den Quelltext-Namen — sonst hebelt `import Path as P` ihn aus.
`Path("data")` allein (kanonische Rueckfallwurzel in `app/loader.py`) und
paketrelative Ressourcen (`Path(__file__).parent / "data" / ...`) sind nie ein
Fund. Ausnahme: `# gz-data-path: <Begruendung>` mit >= `_MIN_BEGRUENDUNG`
Zeichen, gueltig nur im betroffenen Statement selbst.

Known Limitations, gemessen statt vermutet (in `src/`+`api/` nirgends vorhanden;
eine dokumentierte Grenze ist kein Mangel, ein undokumentierter blinder Fleck
schon): `%`-/`.format()`-Pfadbau, `os.sep.join([...])`, `Path(*teile)`,
indirekte Aufrufe (`getattr(pathlib, "Path")`, `functools.partial(Path,
"data")`), `open("data/...")` ohne Pfad-Aufruf, Zuweisungen in
Modul-ebenen-`if`-Bloecken, Wiederexport ueber ein Zwischenmodul (`from helper
import DATA_ROOT` — die dateiweise Pruefung sieht die Herkunft nicht),
Ternaer (`X = Path("data") if c else Y`), Tupel-Mehrfachzuweisung
(`A, B = Path("data"), 1`), Dict-Literal (`{"root": Path("data")}`) und
Walross-Operator (`(W := Path("data")) / "diagnostics"`).

Einziger bekannter FEHLALARM (wiegt schwerer als die Luecken oben, denn er
blockiert echte Arbeit): JEDER Name aus `_PFAD_KLASSEN` zaehlt, gleich woher —
der Preis dafuer, dass `pathlib2` & Co. nicht durchrutschen. Betroffen sind eine
im Modul SELBST definierte `class Path` (`ROUTE = Path("data/api/v1")`) und
`from fastapi import Path` — unser eigenes Framework in `api/`, dort aber nur im
positionalen Vorgabewert-Stil (`file_id: str = Path("data/x.json")`); der
uebliche Schluesselwort-Stil (`Path(..., description=...)`) loest NICHTS aus,
weil `_resolve` Aufrufe mit `keywords` nicht aufloest — dort nicht suchen.
Gemessen: beide Formen 0-mal in `src/`+`api/`, darum nicht behoben; Ausweg ist
der regulaere Marker `# gz-data-path: FastAPI-Parameter, kein Dateipfad`.

Regel-Budget (CLAUDE.md): neuer Waechter, Pruefdatum 2026-11-07. Fang-Beleg bei
Einfuehrung: die vier Fundstellen von #1633. Ohne neuen Fang -> Rueckbau.
"""

import ast
import re
import warnings
from datetime import date
from pathlib import Path
from typing import NamedTuple

import pytest

# Wurzel DIESES Checkouts (Worktree), nie das Hauptrepo — sonst prueft der
# Waechter aus einem Worktree heraus die unveraenderte Kopie (#1409).
REPO_ROOT = Path(__file__).resolve().parents[2]
QUELL_WURZELN = (REPO_ROOT / "src", REPO_ROOT / "api")

EXPIRY = date(2026, 11, 7)

_MARKER = re.compile(r"#\s*gz-data-path:(.*)$")
_MIN_BEGRUENDUNG = 15
_UNWORT = re.compile(r"[\W_]+")
_VERBOTEN = ("data/", "./data/")
_UNBEKANNT = "?"  # Platzhalter fuer ein nicht aufloesbares Pfad-Segment
_PFAD_KLASSEN = frozenset({"Path", "PurePath", "PosixPath", "PurePosixPath"})
_PFAD_AUFRUFE = frozenset(
    {f"pathlib.{n}" for n in _PFAD_KLASSEN} | {"os.path.join", "posixpath.join"}
)
_PFAD_METHODEN = frozenset({"joinpath"})
_MAX_ROUNDS = 5
_MAX_DEPTH = 12


# Statischer Wert eines Ausdrucks. `ist_pfad` = durch Pfad-Aufruf oder `/`-Join
# gelaufen; nur solche Werte koennen ueberhaupt ein Fund sein.
_Wert = NamedTuple("_Wert", [("text", str), ("ist_pfad", bool)])
# consts: Name -> _Wert je Scope-Ebene. binds: lokaler Import-Name -> kanonisch.
_Ctx = NamedTuple("_Ctx", [("consts", dict), ("binds", dict)])
# Eine Fundstelle: Datei, 1-basierte Zeile, aufgeloester Pfad.
Finding = NamedTuple("Finding", [("path", Path), ("line", int), ("target", str)])


def _dotted(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        vorher = _dotted(node.value)
        return f"{vorher}.{node.attr}" if vorher else ""
    return ""


def _import_bindings(tree) -> dict:
    """Lokaler Name -> MENGE kanonischer Namen (`from pathlib import Path as P`
    ergibt `P` -> {`pathlib.Path`}). Ohne diese Aufloesung haengt der Waechter am
    Quelltext-Namen und jeder Alias hebelt ihn aus. Menge statt einzelner Wert,
    weil `ast.walk` keinen Kontrollfluss kennt: bei `try/except`- oder
    `if/else`-Import mit gleichem lokalen Namen ueberschriebe sonst der zuletzt
    besuchte Zweig den ersten und `P` gaelte als Nicht-Pfad."""
    binds: dict = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                kopf = alias.name.split(".")[0]
                ziel = alias.name if alias.asname else kopf
                binds.setdefault(alias.asname or kopf, set()).add(ziel)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                # Auch relativ (`from .m import Path as P`): der Modulteil ist dann
                # kein absoluter Name, aber der Klassenname traegt die Aussage.
                voll = f"{node.module or '.'}.{alias.name}"
                binds.setdefault(alias.asname or alias.name, set()).add(voll)
    return binds


def _ist_pfad_aufruf(func, binds: dict) -> bool:
    roh = _dotted(func)
    if not roh:
        return False
    kopf, punkt, rest = roh.partition(".")
    # JEDE Bindung des Kopfes zaehlt, und jede nach derselben Regel: `ast.walk`
    # kennt keinen Kontrollfluss, bei try/except- oder if/else-Import darf nicht
    # die zuletzt besuchte gewinnen. Ohne Bindung (Re-Export) bleibt der
    # Quelltext-Name. Der Klassenname-Rueckfall gilt ueberall gleich — sonst
    # waere der seltene mehrdeutige Fall besser bewacht als der haeufige.
    namen = [k + punkt + rest for k in binds.get(kopf, {kopf})]
    return any(
        n in _PFAD_AUFRUFE or n.rpartition(".")[2] in _PFAD_KLASSEN for n in namen
    )


def _join(links: str, rechts: str) -> str:
    return rechts if rechts.startswith("/") else links.rstrip("/") + "/" + rechts


def _resolve(node, ctx: _Ctx, tiefe: int = 0):
    """Statischer Wert eines Ausdrucks als `_Wert` oder None (nicht aufloesbar)."""
    if tiefe > _MAX_DEPTH:
        return None
    if isinstance(node, ast.Constant):
        return _Wert(node.value, False) if isinstance(node.value, str) else None
    if isinstance(node, ast.Name):
        return ctx.consts.get(node.id)
    if isinstance(node, ast.JoinedStr):  # f-String
        teile, pfad = [], False
        for wert in node.values:
            if isinstance(wert, ast.Constant) and isinstance(wert.value, str):
                teile.append(wert.value)
                continue
            innen = (
                _resolve(wert.value, ctx, tiefe + 1)
                if isinstance(wert, ast.FormattedValue)
                else None
            )
            teile.append(_UNBEKANNT if innen is None else innen.text)
            pfad = pfad or (innen is not None and innen.ist_pfad)
        return _Wert("".join(teile), pfad)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Add)):
        links = _resolve(node.left, ctx, tiefe + 1)
        rechts = _resolve(node.right, ctx, tiefe + 1)
        if links is None:
            return None
        if rechts is None:
            # `WURZEL / nutzer_id` bleibt ein Verstoss — nur der Rest ist unbekannt.
            if not links.ist_pfad:
                return None
            rechts = _Wert(_UNBEKANNT, False)
        if isinstance(node.op, ast.Div):  # `/` gibt es nur auf Path-Objekten
            return _Wert(_join(links.text, rechts.text), True)
        return _Wert(links.text + rechts.text, links.ist_pfad or rechts.ist_pfad)
    if isinstance(node, ast.Call) and not node.keywords:
        args = [_resolve(a, ctx, tiefe + 1) for a in node.args]
        if _ist_pfad_aufruf(node.func, ctx.binds):
            basis = args.pop(0) if args else None
        elif isinstance(node.func, ast.Attribute) and node.func.attr in _PFAD_METHODEN:
            basis = _resolve(node.func.value, ctx, tiefe + 1)  # `Path(x).joinpath(y)`
            basis = basis if basis is not None and basis.ist_pfad else None
        else:
            return None
        if basis is None:
            return None
        text = basis.text
        for weiter in args:
            text = _join(text, _UNBEKANNT if weiter is None else weiter.text)
        return _Wert(text, True)
    return None


def _zuweisungen(body, binds: dict, geerbt: dict) -> dict:
    """Namen -> `_Wert` EINER Scope-Ebene, bis zum Fixpunkt. Nur `body`, nie
    `ast.walk`: sonst landen Funktions-Lokale im Modul-Dict und gleichnamige
    Variablen unabhaengiger Funktionen ueberschreiben sich gegenseitig."""
    consts = dict(geerbt)
    for _ in range(_MAX_ROUNDS):
        neu = dict(geerbt)
        for node in body:
            if isinstance(node, ast.Assign):
                ziele, quelle = node.targets, node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                ziele, quelle = [node.target], node.value  # `WURZEL: Path = ...`
            else:
                continue
            wert = _resolve(quelle, _Ctx(consts, binds))
            for ziel in ziele:
                if not isinstance(ziel, ast.Name):
                    continue
                if wert is None:
                    neu.pop(ziel.id, None)  # lokale Neubindung verdeckt das Modul
                else:
                    neu[ziel.id] = wert
        if neu == consts:
            break
        consts = neu
    return consts


def _entschuldigt(zeilen: list, von: int, bis: int) -> bool:
    """Marker gilt nur INNERHALB des betroffenen Statements — sonst deckt eine
    beliebige begruendete Nachbarzeile fremde Verstoesse mit ab."""
    for nummer in range(von, bis + 1):
        if 1 <= nummer <= len(zeilen):
            treffer = _MARKER.search(zeilen[nummer - 1])
            if treffer and len(_UNWORT.sub("", treffer.group(1))) >= _MIN_BEGRUENDUNG:
                return True
    return False


def _spanne(node) -> tuple:
    return (node.lineno, node.end_lineno or node.lineno)


def _sammle(node, datei, zeilen, ctx: _Ctx, funde, gesehen, stmt=None) -> None:
    """Top-down; ein Treffer stoppt den Abstieg."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        ctx = _Ctx(_zuweisungen(node.body, ctx.binds, ctx.consts), ctx.binds)
    if isinstance(node, ast.stmt):
        # Zusammengesetzte Statements (Rumpf) bekommen kein Marker-Fenster.
        stmt = None if hasattr(node, "body") else _spanne(node)
    if isinstance(node, ast.expr) and not isinstance(node, ast.Name):
        wert = _resolve(node, ctx)
        if wert is not None and wert.ist_pfad and wert.text.startswith(_VERBOTEN):
            von, bis = stmt or _spanne(node)
            if (node.lineno, wert.text) not in gesehen and not _entschuldigt(
                zeilen, von, bis
            ):
                gesehen.add((node.lineno, wert.text))
                funde.append(Finding(path=datei, line=node.lineno, target=wert.text))
            return
    for kind in ast.iter_child_nodes(node):
        _sammle(kind, datei, zeilen, ctx, funde, gesehen, stmt)


def scan_for_hardcoded_data_paths(roots) -> list:
    """Siehe Modul-Docstring: Vertrag der Scan-Funktion."""
    funde: list = []
    for wurzel in roots:
        for datei in sorted(Path(wurzel).rglob("*.py")):
            try:
                quelltext = datei.read_text(encoding="utf-8")
                baum = ast.parse(quelltext, filename=str(datei))
            except (OSError, SyntaxError, UnicodeDecodeError) as fehler:
                # Nicht verschlucken: eine unlesbare Datei ist eine Schutzluecke.
                warnings.warn(
                    f"Datenwurzel-Waechter konnte {datei} nicht pruefen: {fehler!r}",
                    stacklevel=2,
                )
                continue
            binds = _import_bindings(baum)
            ctx = _Ctx(_zuweisungen(baum.body, binds, {}), binds)
            _sammle(baum, datei, quelltext.splitlines(), ctx, funde, set())
    return funde


def _attrappe(tmp_path: Path, quelltext: str) -> Path:
    """Echte Modul-Attrappe auf die Platte schreiben (kein Mock)."""
    datei = tmp_path / "modul.py"
    datei.write_text(quelltext, encoding="utf-8")
    return datei


def _refs(funde) -> str:
    return ", ".join(f"{f.path}:{f.line} -> {f.target}" for f in funde) or "(keine)"


def test_ac5_bestand_ohne_repo_relative_datenpfade():
    """Der eigentliche Waechter. Rot bis die vier Fundstellen aus #1633 auf
    `get_data_root()` umgestellt sind."""
    funde = scan_for_hardcoded_data_paths(QUELL_WURZELN)
    assert not funde, (
        "Repo-relative Datenpfade im Python-Kern — sie umgehen "
        "app.loader.get_data_root() und schreiben in den Programmordner statt an "
        "die Produktiv-Datenwurzel:\n"
        + "\n".join(f"Code reference: {f.path}:{f.line} -> {f.target}" for f in funde)
    )


@pytest.mark.parametrize("anfuehrung", ['"', "'"])
def test_ac5_konstante_wird_bei_beiden_anfuehrungszeichen_gemeldet(tmp_path, anfuehrung):
    q = anfuehrung
    _attrappe(tmp_path, f"from pathlib import Path\nZIEL = Path({q}data/x.jsonl{q})\n")
    funde = scan_for_hardcoded_data_paths([tmp_path])
    assert len(funde) == 1, f"erwartet 1 Fund, bekommen: {_refs(funde)}"
    assert funde[0].line == 2 and funde[0].target == "data/x.jsonl"


def test_ac5_join_ueber_konstante_wird_gemeldet(tmp_path):
    """Wichtigster Fall: das Literal allein ist harmlos, der Verstoss entsteht
    erst im Join der Folgezeile — eine reine Textsuche uebersieht ihn."""
    quelltext = 'WURZEL = Path("data")\nZIEL = WURZEL / "cache/m.json"\n'
    _attrappe(tmp_path, "from pathlib import Path\n" + quelltext)
    funde = scan_for_hardcoded_data_paths([tmp_path])
    assert len(funde) == 1, f"erwartet 1 Fund, bekommen: {_refs(funde)}"
    assert funde[0].line == 3, "Fund gehoert an den Join, nicht an die Konstante"


# Umgehungen, die vor dem Fix-Loop zu #1633 still durchrutschten: die ersten
# drei aus dem Adversary-Lauf (Alias, Direktimport, Typannotation), die uebrigen
# aus eigenen Angriffsversuchen gegen den bereits reparierten Waechter.
_UMGEHUNGEN = {
    "import-alias": "from pathlib import Path as P\n"
    "W = P('data')\nZ = W / 'diagnostics' / 'x.jsonl'\n",
    "join-direktimport": "from os.path import join\n"
    "Z = join('data', 'diagnostics', 'x.jsonl')\n",
    "typannotiert": "from pathlib import Path\n"
    "W: Path = Path('data')\nZ = W / 'diagnostics/x.jsonl'\n",
    "unbekanntes-segment": "from pathlib import Path\nW = Path('data')\n"
    "def schreibe(nutzer):\n    return W / f'users/{nutzer}.json'\n",
    "punkt-slash-praefix": "from pathlib import Path\n"
    "Z = Path('./data/diagnostics/x.jsonl')\n",
    "joinpath-methode": "from pathlib import Path\n"
    "Z = Path('data').joinpath('diagnostics', 'x.jsonl')\n",
    # Wurzel UND Join in derselben Funktion: faellt der Scope-Reste in `_sammle`
    # weg, kennt der Waechter `wurzel` nicht und uebersieht genau das Muster,
    # das die Spec vorschreibt. Modul-Konstanten decken diesen Fall NICHT ab.
    "funktions-lokale-wurzel": "from pathlib import Path\ndef diagnostics_path():\n"
    "    wurzel = Path('data')\n    return wurzel / 'diagnostics' / 'x.jsonl'\n",
    # Marker im Rumpf darf den Verstoss in der Kopfzeile nicht entschuldigen.
    "marker-im-schleifenrumpf": "from pathlib import Path\n"
    "for eintrag in Path('data') / 'diagnostics' / 'x.jsonl':\n"
    "    print(eintrag)  # gz-data-path: Begruendung die zu dieser Zeile gehoert\n",
    # `ast.walk` sieht beide Zweige; die zuletzt besuchte Bindung darf nicht
    # gewinnen, sonst gilt `J` nur als `myshim.join` und der Aufruf rutscht durch.
    # `join` statt `Path`, sonst traegt der Klassenname-Rueckfall den Fund und der
    # Test bewacht die Mengen-Bindung NICHT mehr (nicht auf `Path` zurueckdrehen).
    "mehrdeutiger-import": "try:\n    from posixpath import join as J\n"
    "except ImportError:\n    from myshim import join as J\n"
    "Z = J('data', 'diagnostics/x.jsonl')\n",
    # Eindeutig gebunden, aber Fremdmodul: nur der Klassenname-Rueckfall faengt es.
    "einzelimport-fremdes-modul": "from pathlib2 import Path\nW = Path('data')\n"
    "Z = W / 'diagnostics' / 'x.jsonl'\n",
    # Schwesterzeile dazu, aber plain `import ... as` (andere Codezeile).
    "mehrdeutiger-plain-import": "try:\n    import posixpath as P\n"
    "except ImportError:\n    import myshim as P\n"
    "Z = P.join('data', 'diagnostics/x.jsonl')\n",
    # Relativer Import: ohne Registrierung faellt die Pruefung auf den Alias `P`.
    "relativer-import-alias": "from .helfer import Path as P\n"
    "Z = P('data') / 'diagnostics' / 'x.jsonl'\n",
}


@pytest.mark.parametrize("quelltext", _UMGEHUNGEN.values(), ids=list(_UMGEHUNGEN))
def test_ac5_umgehungsform_wird_gefunden(tmp_path, quelltext):
    _attrappe(tmp_path, quelltext)
    funde = scan_for_hardcoded_data_paths([tmp_path])
    assert len(funde) == 1, f"Umgehung durchgerutscht: {_refs(funde)}"
    assert funde[0].target.startswith(_VERBOTEN), _refs(funde)


# Legitimer Code, den der Waechter vor dem Fix-Loop faelschlich gemeldet hat.
_LEGITIM = {
    "prosa-und-praefix": "import logging\n"
    "logging.info('data/quota erschoepft fuer heute')\nROUTE = 'data/diagnostics'\n",
    "funktions-lokal": "from pathlib import Path\n"
    "def a():\n    W = Path('data')\n    return W\n"
    "def b(wurzel):\n    W = Path(wurzel)\n    return W / 'cache/x.json'\n",
}


@pytest.mark.parametrize("quelltext", _LEGITIM.values(), ids=list(_LEGITIM))
def test_ac5_legitimer_code_ist_kein_fund(tmp_path, quelltext):
    """Fehlalarm-Gegenprobe: ein Waechter, der legitime Arbeit blockiert, wird
    abgeschaltet und schuetzt danach gar nichts."""
    _attrappe(tmp_path, quelltext)
    funde = scan_for_hardcoded_data_paths([tmp_path])
    assert not funde, f"Fehlalarm auf legitimem Code: {_refs(funde)}"


def test_ac5_paketrelative_ressource_ist_kein_fund(tmp_path):
    """Gegenprobe Fehlalarm: `Path(__file__).parent / "data" / ...` (vier reale
    Stellen in `services/official_alerts/`) laedt eingecheckte Geometrien aus dem
    Paket — kein Datenwurzel-Pfad."""
    ressource = 'Z = Path(__file__).resolve().parent / "data" / "dpc_zones.json"\n'
    _attrappe(tmp_path, "from pathlib import Path\n" + ressource)
    funde = scan_for_hardcoded_data_paths([tmp_path])
    assert not funde, f"paketrelative Ressource ist kein Fund: {_refs(funde)}"


def test_ac5_kanonische_rueckfallwurzel_ist_kein_fund(tmp_path):
    """`Path("data")` in `get_data_root()` IST die kanonische Aufloesung — wer
    sie meldet, macht den Waechter unbenutzbar."""
    _attrappe(tmp_path, 'from pathlib import Path\nDEFAULT = Path("data")\n')
    funde = scan_for_hardcoded_data_paths([tmp_path])
    assert not funde, f"Rueckfallwurzel darf nicht melden: {_refs(funde)}"


def test_ac5_marker_mit_begruendung_laesst_durch(tmp_path):
    verstoss = 'Z = Path("data/legacy/alt.json")  # gz-data-path: Altbestand, nur lesen\n'
    _attrappe(tmp_path, "from pathlib import Path\n" + verstoss)
    funde = scan_for_hardcoded_data_paths([tmp_path])
    assert not funde, f"begruendeter Marker muss durchlassen: {_refs(funde)}"


def test_ac5_marker_ohne_begruendung_bleibt_rot(tmp_path):
    """Ein Zeichen ist keine Entscheidung, sondern das billigste Mittel, jeden
    Fund verschwinden zu lassen."""
    verstoss = 'Z = Path("data/legacy/alt.json")  # gz-data-path: x\n'
    _attrappe(tmp_path, "from pathlib import Path\n" + verstoss)
    funde = scan_for_hardcoded_data_paths([tmp_path])
    assert len(funde) == 1, f"Alibi-Marker ist keine Ausnahme: {_refs(funde)}"


def test_ac5_marker_eines_fremden_statements_entschuldigt_nicht(tmp_path):
    """Der Marker gehoert zu SEINEM Statement. Sonst entschuldigt eine beliebige
    begruendete Nachbarzeile den Verstoss in der Folgezeile mit."""
    fremd = 'F = "x"  # gz-data-path: Begruendung die zu F gehoert\n'
    _attrappe(tmp_path, "from pathlib import Path\n" + fremd + 'Z = Path("data/x")\n')
    funde = scan_for_hardcoded_data_paths([tmp_path])
    assert len(funde) == 1, f"fremder Marker darf nicht entschuldigen: {_refs(funde)}"
    assert funde[0].line == 3


def test_ac5_unlesbare_datei_warnt_laut(tmp_path):
    """Fail-loud-Pfad: eine nicht parsbare Datei ist eine Schutzluecke, kein
    stiller Uebersprung — sonst genuegt ein Syntaxfehler zum Umgehen."""
    (tmp_path / "kaputt.py").write_text("def (:\n", encoding="utf-8")
    with pytest.warns(UserWarning, match="konnte .* nicht pruefen"):
        funde = scan_for_hardcoded_data_paths([tmp_path])
    assert not funde, f"unlesbare Datei liefert keine Funde: {_refs(funde)}"


def test_ac5_pruefdatum_ist_maschinell_auffindbar():
    assert EXPIRY == date(2026, 11, 7), "Pruefdatum des Regel-Budgets (+90 Tage)"
    text = Path(__file__).read_text(encoding="utf-8")
    assert EXPIRY.isoformat() in text, (
        "Das ISO-Pruefdatum muss als Text in dieser Datei stehen, damit das "
        "Gate-Audit (#1197) es per grep findet."
    )
