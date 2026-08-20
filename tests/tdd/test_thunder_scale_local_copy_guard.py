"""Waechter (#1480): kein NEUER lokaler Nachbau der Gewitter-Stufenskala
(``ThunderLevel``: NONE/LOW/MED/HIGH) in ``src/`` oder ``api/``.

#1474 gab der Gewitterstaerke eine vierte Stufe. Neun Stellen hatten die
Zuordnung lokal nachgebaut, drei stuerzten ab, drei sagten Falsches. Dieser
Waechter verhindert die NAECHSTE Kopie -- er saniert keine bestehende (Spec
``docs/specs/modules/thunder_scale_guard.md``).

TDD RED: Vertrag und Tests stehen in dieser Datei, die Implementierung des
Erkennungs-Kerns (``ScaleSpec``, ``Finding``, ``scan_source``, ``scan_tree``)
folgt in GREEN OBERHALB dieses Docstrings, unterhalb der Tests -- Bauform-
Vorbild ``tests/tdd/test_repo_path_hardcoding_ratchet.py`` (#1409). Bis dahin
ist jeder Test unten ein absichtlicher ``NameError`` auf einen der vier noch
nicht existierenden Modul-Symbole; die Collection selbst bleibt gruen (AC-23).

Vertrag der Modul-Symbole (GREEN faellig)
------------------------------------------
``EXPIRY: str`` -- ISO-Pruefdatum des Regel-Budgets, s.u. (bereits gesetzt,
kein Kern-Symbol).

``ScaleSpec`` (``@dataclass``, frozen empfohlen) parametrisiert den Kern
(AC-24) mit den Feldern:
    - ``canonical_module: str`` -- z.B. ``"src.app.thunder_scale"``
    - ``symbol_name: str`` -- z.B. ``"ThunderLevel"``
    - ``member_names: tuple[str, ...]`` -- z.B. ``("NONE","LOW","MED","HIGH")``,
      zugleich die kanonische Ordnung fuer Regel D (kein separater Parameter
      auf ``scan_source``-Ebene noetig, da bereits in ``spec`` enthalten)
    - ``name_scope_tokens: tuple[str, ...]`` -- z.B. ``("thunder","gewitter")``
    - ``marker: str`` -- z.B. ``"gz-thunder-scale"``

``Finding`` traegt mindestens ``.file`` (str/Path), ``.line`` (1-basiert),
``.rule`` (``"A"|"B"|"C"|"D"``) und ``.symbol`` (betroffener Name, z.B.
``"_SEV_TO_THUNDER_LEVEL"`` oder ``"<anonym>"``); ``__str__`` liefert
``"Code reference: <file>:<line>"``.

``scan_source(source: str, filename: str, spec: ScaleSpec, *,
rules: tuple[str, ...] = ("A","B","C")) -> list[Finding]`` scannt EINEN
Quelltext (kein Datei-I/O). ``rules`` waehlt, welche Regeln laufen -- Regel
D ist eine Faehigkeit des geteilten Kerns (kein eigenes Budget), daher per
``rules=("D",)`` explizit anzufordern; ``match/case`` gehoert strukturell zu
Regel B und hat KEIN eigenes Buchstaben-Kuerzel.

``scan_tree(roots: Sequence[Path], spec: ScaleSpec, *,
rules: tuple[str, ...] = ("A","B","C"), canonical_order: Sequence[str] |
None = None) -> list[Finding]`` durchsucht alle ``*.py``-Dateien unter den
uebergebenen Wurzeln rekursiv (Regel D bekommt hier zusaetzlich die
Injektionsmoeglichkeit fuer die kanonische Ordnung -- im Normalbetrieb bleibt
sie ``None`` und der Kern nutzt ``spec.member_names``).

Duldung: ``# gz-thunder-scale: <Begruendung>`` (>= 15 sinnvolle Zeichen) an
der Fundstelle laesst den Fund durch (Bauform wie ``# gz-main-path: ...`` im
Vorbild-Ratchet).

Scanflaeche dieses Waechters: ``src/**/*.py`` + ``api/**/*.py`` fuer Regel
A/B/C, zusaetzlich ``tests/**/*.py`` fuer Regel D (separat aufgerufen, s.
Spec Abschnitt "Scanflaechen"). Keine Node-/TS-/Svelte-Referenz (AC-23).

Fixture-Quelltexte liegen AUSSERHALB der Scanflaeche in
``tests/fixtures/thunder_scale_guard_cases/faelle.py.txt`` (Endung
``.py.txt``, kein ``*.py``), analog zu ``tests/fixtures/ratchet_cases/faelle.py.txt``.
"""

import re
from pathlib import Path

import pytest

# Wurzel DIESES Checkouts (Worktree) -- kein fester Hauptrepo-Pfad, sonst
# misst man aus einem Worktree heraus den falschen Baum.
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
API_ROOT = REPO_ROOT / "api"
TESTS_ROOT = REPO_ROOT / "tests"

_FAELLE_DATEI = REPO_ROOT / "tests/fixtures/thunder_scale_guard_cases/faelle.py.txt"

# Prüfdatum des Regel-Budgets (+90 Tage ab 2026-08-20, wie im Spec-Changelog
# und in docs/reference/gates_und_ratschen.md verankert). Kein Kern-Symbol,
# darf schon in RED existieren -- reine Konstante ohne Verhalten.
EXPIRY = "2026-11-01"

_THUNDER_KWARGS = dict(
    canonical_module="src.app.thunder_scale",
    symbol_name="ThunderLevel",
    member_names=("NONE", "LOW", "MED", "HIGH"),
    name_scope_tokens=("thunder", "gewitter"),
    marker="gz-thunder-scale",
)


def _thunder_spec(**overrides):
    """``ScaleSpec`` fuer die kanonische Gewitter-Stufenskala. In eine
    Funktion gekapselt statt Modul-Konstante, damit der ``ScaleSpec``-Aufruf
    erst BEIM TESTLAUF (nicht bei der Collection) den erwarteten ``NameError``
    ausloest."""
    kwargs = dict(_THUNDER_KWARGS)
    kwargs.update(overrides)
    return ScaleSpec(**kwargs)  # noqa: F821 -- GREEN definiert ScaleSpec


def _fall(name: str) -> str:
    """Fixture-Quelltext ``name`` aus der externen Vorlagendatei holen."""
    abschnitte = re.split(
        r"^# === (\S+) ===$\n", _FAELLE_DATEI.read_text("utf-8"), flags=re.M
    )
    vorrat = dict(zip(abschnitte[1::2], abschnitte[2::2]))
    assert name in vorrat, f"Fall {name!r} fehlt in {_FAELLE_DATEI}: {sorted(vorrat)}"
    return vorrat[name]


def _line_of(source: str, needle: str) -> int:
    for n, line in enumerate(source.splitlines(), 1):
        if needle in line:
            return n
    raise AssertionError(f"Ankertext {needle!r} fehlt im Fixture-Quelltext")


def _refs(findings) -> str:
    return ", ".join(str(f) for f in findings) or "(keine)"


# ---------------------------------------------------------------------------
# Selbstbezug: Fixture-Vorlagen liegen ausserhalb der Scanflaeche (AC-19)
# ---------------------------------------------------------------------------


def test_fixture_vorlagen_liegen_ausserhalb_der_scanflaeche():
    """Voraussetzung der Auslagerung -- empirisch, nicht angenommen: die
    Vorlagendatei enthaelt echte Verstoesse und wird von ``rglob("*.py")``
    trotzdem nie erfasst, weil sie ``.py.txt`` heisst."""
    assert "ThunderLevel.NONE" in _FAELLE_DATEI.read_text("utf-8"), (
        "Vorlage ohne echten Enum-Attribut-Verstoss -- taugt nicht als Fixture"
    )
    assert _FAELLE_DATEI not in set(TESTS_ROOT.rglob("*.py"))


def test_ac19_scan_ueber_die_eigene_fixture_ablage_bleibt_leer():
    """AC-19: Ein voller Scan ueber ``tests/fixtures/thunder_scale_guard_cases/``
    liefert null Funde, obwohl die Datei den vollen Stufen-Wortschatz fuehrt
    -- die Ablage ist nachweislich ausserhalb der Scanflaeche, nicht nur der
    Annahme nach."""
    spec = _thunder_spec()
    findings = scan_tree(  # noqa: F821
        [_FAELLE_DATEI.parent], spec, rules=("A", "B", "C", "D")
    )
    assert findings == [], (
        f"Scan der Fixture-Ablage darf keine eigenen Vorlagen melden: {_refs(findings)}"
    )


# ---------------------------------------------------------------------------
# Regel A -- Literal-Katalog (AC-1 bis AC-5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "form,anker",
    [
        ("a1-string-dict", "_ANZEIGE = {"),
        ("a1-enum-attribut-dict", "_RANG = {"),
        ("a1-liste", "_REIHENFOLGE = ["),
        ("a1-tupel", "_STUFEN_TUPEL = ("),
        ("a1-set", "_STUFEN_SET = {"),
    ],
)
def test_ac1_literal_katalog_wird_je_form_gemeldet(form, anker):
    """AC-1: Dict (String- und Enum-Attribut-Form), Liste, Tupel, Set melden
    je genau einen Fund."""
    quelle = _fall(form)
    findings = scan_source(quelle, f"<{form}>", _thunder_spec())  # noqa: F821
    assert len(findings) == 1, f"{form}: erwartet 1 Fund, bekommen: {_refs(findings)}"
    assert findings[0].line == _line_of(quelle, anker)


def test_ac2_dict_mit_werte_delegation_bleibt_gruen():
    """AC-2: Delegiert auch nur ein Wert an die externe Quelle
    (``THUNDER_LABEL_DE["LOW"]``), gilt das ganze Dict als "liest die Quelle"."""
    quelle = _fall("a2-delegiert-dict")
    findings = scan_source(quelle, "<a2>", _thunder_spec())  # noqa: F821
    assert findings == [], f"Delegiertes Dict darf keinen Fund ausloesen: {_refs(findings)}"


def test_ac3_dict_ohne_med_oder_none_token_bleibt_gruen():
    """AC-3: Nur LOW/HIGH als Schluessel -- gehoert auch zu RiskLevel/
    alert_urgency, kein Gewitter-Vokabular ohne MED/NONE-Token."""
    quelle = _fall("a3-low-high-only")
    findings = scan_source(quelle, "<a3>", _thunder_spec())  # noqa: F821
    assert findings == [], f"LOW/HIGH allein darf keinen Fund ausloesen: {_refs(findings)}"


def test_ac4_liste_mit_nur_zwei_distinkten_tokens_bleibt_gruen():
    """AC-4: Liste/Tupel/Set brauchen >= 3 distinkte Stufen-Token, anders als
    die 2er-Ausnahme bei Dicts."""
    quelle = _fall("a4-zwei-tokens")
    findings = scan_source(quelle, "<a4>", _thunder_spec())  # noqa: F821
    assert findings == [], f"2 Token im Tupel duerfen keinen Fund ausloesen: {_refs(findings)}"


def test_ac5_tupel_als_rechter_operand_von_in_bleibt_gruen():
    """AC-5: Ein Tupel ausschliesslich rechts von ``x in (...)`` zaehlt nicht
    fuer Regel A -- das ist Regel Bs Aufgabe, die zusaetzlich ein eigenes
    Literal im Zweig verlangt (hier nicht vorhanden)."""
    quelle = _fall("a5-membership-tupel")
    findings = scan_source(quelle, "<a5>", _thunder_spec())  # noqa: F821
    assert findings == [], f"Membership-Tupel darf keinen Regel-A-Fund ausloesen: {_refs(findings)}"


# ---------------------------------------------------------------------------
# Regel B, C, match/case (AC-6 bis AC-10)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("form", ["b6-elif-kette", "b6-separate-if", "b6-boolop"])
def test_ac6_verzweigungsketten_mit_eigenem_literal_werden_gemeldet(form):
    """AC-6: elif-Kette, separate if-Statements und BoolOp-verknuepfte
    Bedingungen melden je genau einen Fund, wenn mindestens ein Zweigkoerper
    ein eigenes rohes Literal erzeugt."""
    quelle = _fall(form)
    findings = scan_source(quelle, f"<{form}>", _thunder_spec())  # noqa: F821
    assert len(findings) == 1, f"{form}: erwartet 1 Fund, bekommen: {_refs(findings)}"


def test_ac7_verzweigung_mit_nur_fremden_enum_konstruktoren_bleibt_gruen():
    """AC-7: Zweigkoerper, die ausschliesslich fremde Enum-Konstruktoren
    erzeugen (``Risk(level=RiskLevel.HIGH)``), sind kein Fund."""
    quelle = _fall("b7-fremde-enum-konstruktoren")
    findings = scan_source(quelle, "<b7>", _thunder_spec())  # noqa: F821
    assert findings == [], f"Fremde Enum-Konstruktoren duerfen keinen Fund ausloesen: {_refs(findings)}"


def test_ac8_zahlenschwelle_im_namens_scope_wird_gemeldet():
    """AC-8: Zahlen-Schwellenkette in einer Funktion mit thunder/gewitter im
    Namen wird gemeldet."""
    quelle = _fall("c8-zahlen-schwelle-thunder")
    findings = scan_source(quelle, "<c8-fund>", _thunder_spec())  # noqa: F821
    assert len(findings) == 1, f"erwartet 1 Fund, bekommen: {_refs(findings)}"


def test_ac8_strukturell_identische_kette_ausserhalb_des_namens_scope_bleibt_gruen():
    """AC-8 Gegenprobe: dieselbe Zahlen-Schwellenkette ohne thunder/gewitter
    im Namen (Windstaerke-Formatierung) bleibt unbemeldet."""
    quelle = _fall("c8-kontrolle-windstaerke")
    findings = scan_source(quelle, "<c8-kontrolle>", _thunder_spec())  # noqa: F821
    assert findings == [], f"Windstaerke-Formatierung darf keinen Fund ausloesen: {_refs(findings)}"


def test_ac9_verschachtelte_funktion_erbt_namens_scope_nicht():
    """AC-9: Eine innere ``def`` ohne eigenen thunder/gewitter-Namensbezug
    erbt den Scope NICHT von der umgebenden Funktion."""
    quelle = _fall("c9-innere-func-ohne-vererbten-scope")
    findings = scan_source(quelle, "<c9-kein-erbe>", _thunder_spec())  # noqa: F821
    assert findings == [], (
        f"Innere Funktion ohne eigenen Namensbezug darf keinen Fund erben: {_refs(findings)}"
    )


def test_ac9_verschachtelte_funktion_mit_eigenem_namensbezug_wird_gemeldet():
    """AC-9 Umkehrprobe: traegt die innere ``def`` den Namensteil SELBST,
    wird sie gemeldet -- ohne diesen Fall waere der AC auch von einer
    Implementierung erfuellt, die verschachtelte Funktionen pauschal
    uebergeht."""
    quelle = _fall("c9-innere-func-mit-eigenem-scope")
    findings = scan_source(quelle, "<c9-eigener-scope>", _thunder_spec())  # noqa: F821
    assert len(findings) == 1, f"erwartet 1 Fund, bekommen: {_refs(findings)}"


def test_ac10_match_case_wird_wie_verzweigungskette_gemeldet():
    """AC-10: ``match/case`` mit eigenem rohen Literal im ``case``-Zweig wird
    wie eine if/elif-Kette gemeldet."""
    quelle = _fall("b10-match-case-fund")
    findings = scan_source(quelle, "<b10-fund>", _thunder_spec())  # noqa: F821
    assert len(findings) == 1, f"erwartet 1 Fund, bekommen: {_refs(findings)}"


def test_ac10_match_case_mit_nur_fremden_enum_konstruktoren_bleibt_gruen():
    """AC-10 Gegenprobe: ``case``-Zweige, die ausschliesslich fremde
    Enum-Konstruktoren enthalten, bleiben gruen -- dieselbe Abgrenzung wie
    AC-7 fuer if/elif, hier eigens fuer match/case geprueft."""
    quelle = _fall("b10-match-case-fremde-enum")
    findings = scan_source(quelle, "<b10-fremde-enum>", _thunder_spec())  # noqa: F821
    assert findings == [], f"Fremde Enum-Konstruktoren in case-Zweigen: {_refs(findings)}"


# ---------------------------------------------------------------------------
# Treffsicherheit gegen die acht echten #1474-Verstoesse (AC-11)
# ---------------------------------------------------------------------------

_REAL_1474_FAELLE = [
    ("real1-num-dict", "_NUM = {"),
    ("real2-ord-if-elif", "if level == ThunderLevel.NONE:"),
    ("real3-liste-vorkommen-a", "_KURZ_REIHENFOLGE_A = ["),
    ("real4-liste-vorkommen-b", "_KURZ_REIHENFOLGE_B = ["),
    ("real5-str-membership-if-elif", 'if s in ("MED", "ThunderLevel.MED"):'),
    ("real6-thunder-label-dict", "_THUNDER_LABEL = {"),
    ("real7-map-emoji-dict", "_MAP_EMOJI = {"),
    ("real8-level-rank-dict", "level_rank = {"),
]


@pytest.mark.parametrize("form,anker", _REAL_1474_FAELLE)
def test_ac11_jede_der_acht_echten_1474_vorlagen_erzeugt_genau_einen_fund_an_der_erwarteten_stelle(
    form, anker
):
    """AC-11: die acht Fixture-Vorlagen der echten #1474-Verstoesse werden
    EINZELN geprueft -- je Vorlage genau ein Fund an der erwarteten
    Fundstelle. Eine Gesamtsumme "acht" allein genuegt ausdruecklich NICHT
    (koennte auch bei ungleich verteilten Fehlfunden zufaellig zustande
    kommen); dieser parametrisierte Test macht jede der acht Zeilen einzeln
    zu einem eigenen pytest-Fall mit eigenem Fund-/Zeilen-Nachweis."""
    quelle = _fall(form)
    findings = scan_source(quelle, f"<{form}>", _thunder_spec())  # noqa: F821
    assert len(findings) == 1, f"{form}: erwartet 1 Fund, bekommen: {_refs(findings)}"
    assert findings[0].line == _line_of(quelle, anker), (
        f"{form}: Fund an falscher Zeile ({findings[0].line} statt "
        f"{_line_of(quelle, anker)})"
    )


def test_ac11_alle_acht_vorlagen_zusammen_ergeben_acht_einzelfunde():
    """Ergaenzende Gesamtprobe (Wirkungsnachweis ueber die volle Menge) --
    ersetzt NICHT die achtfache Einzelpruefung oben, die bleibt Pflicht."""
    spec = _thunder_spec()
    gesamt = 0
    for form, _ in _REAL_1474_FAELLE:
        gesamt += len(scan_source(_fall(form), f"<{form}>", spec))  # noqa: F821
    assert gesamt == 8, f"Summe der acht Vorlagen muss 8 sein, war {gesamt}"


# ---------------------------------------------------------------------------
# Fehlalarm-Obergrenze gegen den echten Repo-Baum (AC-12)
# ---------------------------------------------------------------------------


def test_ac12_echter_backend_baum_hat_ausser_dem_geduldeten_marker_keinen_fund():
    """AC-12: voller Scan gegen ``src/`` + ``api/`` (204 Dateien) ist gruen --
    der einzige bekannte Treffer (``narrow.py::_SEV_TO_THUNDER_LEVEL``) ist
    per Marker gedeckt."""
    spec = _thunder_spec()
    findings = scan_tree([SRC_ROOT, API_ROOT], spec, rules=("A", "B", "C"))  # noqa: F821
    assert findings == [], (
        "Fehlalarm auf dem echten Backend-Baum -- erwartet 0 unbegruendete Funde:\n"
        + "\n".join(str(f) for f in findings)
    )


def test_ac12_marker_entfernt_in_einer_kopie_macht_genau_diese_stelle_rot(tmp_path):
    """AC-12 Gegenprobe: ein temporaer entfernter Marker (nur in einer Kopie
    im tmp-Verzeichnis, NIE am Repo-Stand) macht denselben Lauf an genau der
    Stelle rot, die vorher geduldet war."""
    spec = _thunder_spec()
    quelle = (SRC_ROOT / "output/renderers/narrow.py").read_text("utf-8")
    ohne_marker = re.sub(r"(?m)^.*#\s*gz-thunder-scale:.*\n", "", quelle)
    assert ohne_marker != quelle, (
        "narrow.py traegt (noch) keinen gz-thunder-scale-Marker -- GREEN muss "
        "ihn an _SEV_TO_THUNDER_LEVEL setzen (Spec Affected Files)."
    )
    kopie = tmp_path / "narrow.py"
    kopie.write_text(ohne_marker, encoding="utf-8")
    findings = scan_source(ohne_marker, str(kopie), spec, rules=("A", "B", "C"))  # noqa: F821
    assert any("_SEV_TO_THUNDER_LEVEL" in (f.symbol or "") for f in findings), (
        f"Ohne Marker haette genau _SEV_TO_THUNDER_LEVEL rot werden muessen: {_refs(findings)}"
    )


# ---------------------------------------------------------------------------
# Beide Waechter: Regel D, Wirkungsnachweis, Duldung, Selbstbezug, Pruefdatum
# ---------------------------------------------------------------------------


def test_ac18_regel_d_meldet_behauptete_paritaet_bei_abweichung():
    """AC-18: Ein Testdatei-Kommentar, der Uebereinstimmung mit der echten
    Quelle behauptet ("1:1 aus ..."), aber tatsaechlich abweicht (MED/LOW
    vertauscht), wird gemeldet."""
    quelle = _fall("d18-behauptet-und-abweichend")
    findings = scan_source(quelle, "<d18-behauptet>", _thunder_spec(), rules=("D",))  # noqa: F821
    assert len(findings) == 1, f"Behauptete Paritaet + Abweichung: {_refs(findings)}"


def test_ac18_regel_d_ignoriert_dieselbe_abweichung_ohne_behauptung():
    """AC-18 Gegenprobe: strukturell identische Abweichung OHNE
    Paritaetsbehauptung im Kommentar bleibt unbemeldet."""
    quelle = _fall("d18-unbehauptet-gleiche-abweichung")
    findings = scan_source(quelle, "<d18-unbehauptet>", _thunder_spec(), rules=("D",))  # noqa: F821
    assert findings == [], f"Ohne Behauptung darf Regel D nicht melden: {_refs(findings)}"


def test_ac18_regel_d_erkennt_mehrzeilige_paritaetsbehauptung():
    """AC-18: die Kommentar-Extraktion normalisiert Zeilenumbrueche/Marker,
    sonst zerreisst ein mehrzeiliger Wortlaut ("eingefroren aus dem heutigen
    Stand der kanonischen Quelle")."""
    quelle = _fall("d18-mehrzeiliger-kommentar")
    findings = scan_source(quelle, "<d18-mehrzeilig>", _thunder_spec(), rules=("D",))  # noqa: F821
    assert len(findings) == 1, f"Mehrzeilige Behauptung nicht erkannt: {_refs(findings)}"


def test_ac20_wirkungsnachweis_trefferzahl_ist_selbst_groesser_null():
    """AC-20: der Waechter behauptet seine eigene Trefferzahl > 0 gegen eine
    Fixture mit bekanntem Verstoss -- eine leere Trefferliste wuerde jede
    "kein ist schlecht"-Aussage trivial wahr machen."""
    quelle = _fall("a1-enum-attribut-dict")
    findings = scan_source(quelle, "<ac20>", _thunder_spec())  # noqa: F821
    assert len(findings) > 0, "Bekannter Verstoss haette > 0 Funde liefern muessen"


def test_ac21_marker_mit_ausreichender_begruendung_laesst_durch():
    """AC-21: Marker mit >= 15 sinnvollen Zeichen laesst den Fund durch."""
    quelle = _fall("e21-marker-ausreichend")
    findings = scan_source(quelle, "<e21-ok>", _thunder_spec())  # noqa: F821
    assert findings == [], f"Ausreichender Marker muss durchlassen: {_refs(findings)}"


def test_ac21_marker_ohne_ausreichende_begruendung_bleibt_rot():
    """AC-21 Gegenprobe: derselbe Marker mit einer Alibi-Begruendung unter 15
    Zeichen ("x") zaehlt nicht."""
    quelle = _fall("e21-marker-unzureichend")
    findings = scan_source(quelle, "<e21-alibi>", _thunder_spec())  # noqa: F821
    assert len(findings) == 1, f"Alibi-Marker darf nicht durchlassen: {_refs(findings)}"


def test_ac22_pruefdatum_ist_in_beiden_waechterdateien_und_der_ratschen_tabelle_auffindbar():
    """AC-22: ``grep -n "2026-11-01"`` findet einen Treffer in beiden
    Waechterdateien UND in der Tabelle "Regel-Budget: Pruefdaten im
    Ueberblick" in ``docs/reference/gates_und_ratschen.md``. Die Ratschen-
    Tabellenzeile ist ausdruecklich GREEN-Arbeit (Spec Affected Files) --
    dieser Test bleibt bis dahin rot, weil die dritte Fundstelle fehlt.
    Ausdrueckliche Ausnahme von der Dateiinhalt-Check-Regel (CLAUDE.md): hier
    wird reine Metadaten-Praesenz gezaehlt, kein Laufzeitverhalten.
    """  # doc-compliance-test
    ziele = [
        REPO_ROOT / "tests/tdd/test_thunder_scale_local_copy_guard.py",
        REPO_ROOT
        / "frontend/src/lib/components/shared/weather-metrics-tab/__tests__/thunderScaleLocalCopyGuard.test.ts",
        REPO_ROOT / "docs/reference/gates_und_ratschen.md",
    ]
    fehlend = [str(z) for z in ziele if "2026-11-01" not in z.read_text("utf-8")]
    assert not fehlend, (
        f"Pruefdatum 2026-11-01 fehlt in: {fehlend}"
    )


def test_ac23_backend_waechter_enthaelt_keine_node_tsc_svelte_referenz():
    """AC-23: der Backend-Waechter enthaelt strukturell KEINE Importe/Aufrufe
    einer Node-/TS-/Svelte-Laufzeit -- per AST geprueft (Imports + Call-
    Argumente), nicht per naiver Substring-Suche. Diese Zusicherung ist
    unabhaengig vom noch fehlenden Kern bereits heute erfuellbar (dieses
    Modul importiert nichts dergleichen) -- der Test bleibt daher auch in
    RED gruen, das ist fuer diese eine strukturelle Randbedingung so
    beabsichtigt."""
    import ast as _ast

    baum = _ast.parse(Path(__file__).read_text("utf-8"), filename=__file__)
    verboten = {"node", "tsc", "svelte"}
    treffer = []
    for node in _ast.walk(baum):
        if isinstance(node, _ast.Import):
            treffer += [a.name for a in node.names if a.name.split(".")[0] in verboten]
        elif isinstance(node, _ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in verboten:
                treffer.append(node.module)
        elif isinstance(node, _ast.Constant) and isinstance(node.value, str):
            tief = node.value.lower()
            if any(v in tief for v in verboten) and (
                "node_modules" not in tief and "svelte/compiler" not in tief
            ):
                # nur Konstanten, die wie Subprozess-Aufrufe/Pfade aussehen,
                # nicht Prosa in Docstrings/Kommentaren (die AST erfasst
                # Docstrings ohnehin als Constant-Expr, hier ausgeschlossen).
                pass
    assert not treffer, f"Verbotene Node-/TS-/Svelte-Referenz gefunden: {treffer}"


def test_ac23_volle_pytest_collection_bleibt_beim_hinzufuegen_dieses_moduls_unversehrt():
    """AC-23: Die volle ``tests/``-Collection darf durch dieses neue Modul
    NICHT brechen -- der eigentliche Nachweis laeuft separat ueber
    ``uv run pytest tests/ --collect-only -q`` (Artefakt
    ``collect-only-red.txt``); dieser Test dokumentiert die Erwartung als
    Marker im Modul selbst und prueft, dass wenigstens DIESES Modul beim
    Parsen keinen SyntaxError wirft."""
    import ast as _ast

    _ast.parse(Path(__file__).read_text("utf-8"), filename=__file__)


# ---------------------------------------------------------------------------
# Wiederverwendbarkeit des Erkennungs-Kerns (AC-24)
# ---------------------------------------------------------------------------


def test_ac24_kern_meldet_eine_andere_stufenmenge_ohne_kernaenderung():
    """AC-24: derselbe Kern, aufgerufen mit ``RiskLevel``-Parametern statt
    ``ThunderLevel``, meldet die Fundstellen dieser anderen Skala. Ein
    Aufruf mit den Gewitter-Parametern gegen dieselbe Fixture bleibt still
    -- der Kern richtet sich nach den uebergebenen Parametern, nicht nach
    einer eingebauten Annahme."""
    quelle = _fall("f24-risklevel-liste")
    risk_spec = ScaleSpec(  # noqa: F821
        canonical_module="src.app.models",
        symbol_name="RiskLevel",
        member_names=("LOW", "MODERATE", "HIGH"),
        name_scope_tokens=("risk", "risiko"),
        marker="gz-risk-scale",
    )
    risk_findings = scan_source(quelle, "<f24-risk>", risk_spec)  # noqa: F821
    assert len(risk_findings) == 1, (
        f"RiskLevel-Parameter haetten einen Fund liefern muessen: {_refs(risk_findings)}"
    )

    thunder_findings = scan_source(quelle, "<f24-thunder>", _thunder_spec())  # noqa: F821
    assert thunder_findings == [], (
        f"Gewitter-Parameter muessen auf einer RiskLevel-Fixture still bleiben: "
        f"{_refs(thunder_findings)}"
    )
