"""Issue #3232 (Nachzug #3228, Epic #3222): Windrichtungs-Pruefung der beiden
Mail-Validatoren. Spec: docs/specs/modules/feat_3232_validator_windrichtung.md.

Kern-Schicht, kein Netz, kein Mock: die Mails entstehen ueber die echten
Renderer in ``scripts/send_gate_test_mails.py`` (dieselben, die an das
Staging-Testpostfach gehen), werden mit der echten Produktfunktion
``build_mime_message`` zu MIME-Nachrichten und vom echten Validator
(``validate_message`` bzw. CLI per Subprozess) geprueft. Das Soll stammt aus
demselben Skript (``windrichtung_soll``/``compare_windrichtung_soll``) und
ist dort explizit hinterlegt. Gegenprobe: dieselbe Mail mit gezielt
verfaelschter Zelltoenung bzw. entferntem Ampelpunkt (String-Ersetzung) ->
genau die erwartete Meldung; ohne Soll meldet der Validator nichts Neues.
"""
from __future__ import annotations

import email
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from output.channels.email import build_mime_message
from output.renderers.email.design_tokens import tone_css

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
BRIEFING_CLI = HOOKS / "briefing_mail_validator.py"
VERGLEICH_CLI = HOOKS / "email_spec_validator.py"
E2E_VERIFY_DOC = ROOT / ".claude" / "commands" / "e2e-verify.md"

_PUNKT_RE = re.compile(r'<span style="[^"]*border-radius:\s*50%[^"]*"></span>\s*')
_UNGUELTIG_RE = re.compile(r"FEHLER: --windrichtung ung(?:ü|ue)ltig: \S")


def _lade(pfad: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(pfad))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def skript():
    return _lade(ROOT / "scripts" / "send_gate_test_mails.py", "send_gate_test_mails_3232")


def _msg(subject: str, html: str, plain: str, mail_type: str, mail_format: str = "full"):
    m = build_mime_message(subject=subject, body=html, from_addr="gregor@example.invalid",
                           to_header="gregor-test@henemm.com", reply_to=None, html=True,
                           plain_text_body=plain, mail_type=mail_type, mail_format=mail_format)
    return email.message_from_bytes(m.as_bytes())


def _windrichtung(fehler: list[str]) -> list[str]:
    return [f for f in fehler if f.startswith("SOLL: Windrichtung")]


# --------------------------------------------------------------------------- #
# Briefing (Rad-Trip, Vorlage radtour)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def briefing(skript):
    return _lade(BRIEFING_CLI, "briefing_mail_validator_3232"), \
        skript.build_briefing_mail("t3232"), skript.windrichtung_soll()


def _etappen_block(v, html: str, sid: int) -> str:
    """Stundentabelle von Segment ``sid`` (N-te Etappen-Stundentabelle)."""
    return [b for b in v._table_blocks(html) if (v._th_tokens(b) or [""])[0] == "Zeit"][sid - 1]


def _etappe_umfaerben(v, html: str, sid: int, von: str, nach: str) -> str:
    """Toenung ``von`` -> ``nach`` nur in der Stundentabelle von Segment ``sid``."""
    block = _etappen_block(v, html, sid)
    ziel = f"background:{tone_css(nach)[0]};" if nach != "green" else ""
    neu = block.replace(f"background:{tone_css(von)[0]};", ziel)
    assert neu != block
    return html.replace(block, neu)


def test_briefing_korrekte_mail_besteht_mit_soll(briefing):
    """AC-1: korrekte Mail + Soll -> keine Meldung."""
    v, (subject, html, plain), soll = briefing
    ok, fehler = v.validate_message(_msg(subject, html, plain, "trip-briefing"), windrichtung=soll)
    assert ok, fehler


@pytest.mark.parametrize("sid, von, nach", [
    (2, "orange", "green"),   # Gegenwind 25 km/h verliert Orange
    (3, "yellow", "orange"),  # Rueck-/Seitenwind faelschlich nach Gegenwind gefaerbt
    (4, "orange", "red"),     # Rundkurs faelschlich mit Gegenwind gefaerbt
    (5, "red", "orange"),     # Nachbarsegment mit Gegenwind verliert Rot
])
def test_briefing_verfaelschte_toenung_genau_eine_meldung(briefing, sid, von, nach):
    """AC-2: verfaelschte Toenung -> genau eine Meldung mit Segment und Soll je Stunde."""
    v, (subject, html, plain), soll = briefing
    falsch = _etappe_umfaerben(v, html, sid, von, nach)
    _ok, fehler = v.validate_message(_msg(subject, falsch, plain, "trip-briefing"), windrichtung=soll)
    treffer = _windrichtung(fehler)
    assert len(treffer) == 1 and f"Segment {sid}:" in treffer[0], fehler
    assert f"statt {soll['wind_zellen'][str(sid)]}" in treffer[0]


def test_briefing_ohne_soll_keine_neue_meldung(briefing):
    """AC-4: ohne --windrichtung keine Windrichtungs-Meldung, auch bei verfaelschter Zelle."""
    v, (subject, html, plain), _soll = briefing
    falsch = _etappe_umfaerben(v, html, 2, "orange", "green")
    _ok, fehler = v.validate_message(_msg(subject, falsch, plain, "trip-briefing"))
    assert _windrichtung(fehler) == []


def test_briefing_format_compact_mit_soll_meldet_laut(briefing):
    """AC-6: Soll + X-GZ-Format != full -> Meldung statt stiller Nicht-Pruefung."""
    v, (subject, html, plain), soll = briefing
    _ok, fehler = v.validate_message(_msg(subject, html, plain, "trip-briefing", "compact"),
                                     windrichtung=soll)
    assert any("Windrichtung nur im Format full pr" in f for f in fehler), fehler


@pytest.mark.parametrize("sid", ["0", "N+1"])
def test_briefing_segment_id_ausserhalb_meldet(briefing, skript, sid):
    """AC-7: Segment-ID 0 bzw. > Zahl der Etappen-Stundentabellen -> Meldung,
    nie still eine falsche Tabelle (``tabellen[-1]``) pruefen."""
    v, (subject, html, plain), _soll = briefing
    anzahl = len(skript.RAD_ETAPPEN) + 1  # Segment 1 + Rad-Segmente
    sid = str(anzahl + 1) if sid == "N+1" else sid
    # Soll der letzten Tabelle -- wuerde bei tabellen[-1] still passen.
    letzte = skript.windrichtung_soll()["wind_zellen"][str(anzahl)]
    _ok, fehler = v.validate_message(_msg(subject, html, plain, "trip-briefing"),
                                     windrichtung={"wind_zellen": {sid: letzte}})
    treffer = _windrichtung(fehler)
    assert len(treffer) == 1 and f"Segment {sid}" in treffer[0], fehler


def test_briefing_getoente_zelle_ohne_punkt_meldet_punkt_fehlt(briefing):
    """AC-8: getoente Wind-Zelle (orange), Ampelpunkt entfernt -> 'Punkt fehlt',
    nicht still 'Punkt = Toenung'."""
    v, (subject, html, plain), soll = briefing
    block = _etappen_block(v, html, 2)
    zelle = next(z for z in re.findall(r'<td[^>]*data-label="Wind"[^>]*>.*?</td>', block, re.S)
                 if f"background:{tone_css('orange')[0]};" in z and _PUNKT_RE.search(z))
    ohne = _PUNKT_RE.sub("", zelle, count=1)
    falsch = html.replace(block, block.replace(zelle, ohne, 1))
    assert falsch != html
    _ok, fehler = v.validate_message(_msg(subject, falsch, plain, "trip-briefing"), windrichtung=soll)
    treffer = _windrichtung(fehler)
    assert len(treffer) == 1 and "Segment 2:" in treffer[0] and "Punkt fehlt" in treffer[0], fehler


# --------------------------------------------------------------------------- #
# Ortsvergleich (Sektor N)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def vergleich(skript):
    return _lade(VERGLEICH_CLI, "email_spec_validator_3232"), \
        skript.build_compare_mail("t3232"), skript.compare_windrichtung_soll()


def _zelle_umfaerben(html: str, inhalt: str, von: str, nach: str) -> str:
    """Toenung aller ``<td>`` mit sichtbarem Inhalt ``inhalt``: ``von`` -> ``nach``
    (``transparent`` = ungetoent)."""
    hex_ = {s: s if s == "transparent" else tone_css(s)[0] for s in (von, nach)}
    neu, n = re.subn(rf"(<td[^>]*?)background:{hex_[von]};([^>]*>{re.escape(inhalt)}</td>)",
                     rf"\1background:{hex_[nach]};\2", html)
    assert n > 0
    return neu


def test_vergleich_korrekte_mail_besteht_mit_soll(vergleich):
    """AC-3: Soll erfuellt -> keine Meldung."""
    v, (subject, html, plain), soll = vergleich
    ok, fehler = v.validate_message(_msg(subject, html, plain, "compare"), windrichtung=soll)
    assert ok, fehler


@pytest.mark.parametrize("inhalt, von, nach, meldung", [
    ("0 °", "orange", "transparent", "Vergleichstabelle Ort 'Gatehausen Nord'"),
    ("180 °", "transparent", "orange", "Vergleichstabelle Ort 'Gatehausen Mitte'"),
    ("30 N", "orange", "yellow", "Stundenverlauf Ort 'Gatehausen Nord'"),
])
def test_vergleich_verfaelschte_toenung_genau_eine_meldung(vergleich, inhalt, von, nach, meldung):
    """AC-3: verfaelschte Zelle eines Orts -> genau eine Meldung mit Ort."""
    v, (subject, html, plain), soll = vergleich
    falsch = _zelle_umfaerben(html, inhalt, von, nach)
    _ok, fehler = v.validate_message(_msg(subject, falsch, plain, "compare"), windrichtung=soll)
    treffer = _windrichtung(fehler)
    assert len(treffer) == 1 and meldung in treffer[0], fehler


def test_vergleich_ohne_soll_keine_neue_meldung(vergleich):
    """AC-4: ohne --windrichtung keine Windrichtungs-Meldung."""
    v, (subject, html, plain), _soll = vergleich
    falsch = _zelle_umfaerben(html, "0 °", "orange", "transparent")
    _ok, fehler = v.validate_message(_msg(subject, falsch, plain, "compare"))
    assert _windrichtung(fehler) == []


# --------------------------------------------------------------------------- #
# AC-5: CLI-Eingabepruefung (Exit 2, klare Meldung, kein Traceback)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def emls(skript, tmp_path_factory):
    d = tmp_path_factory.mktemp("eml_3232")
    pfade = {}
    for art, (subject, html, plain), mail_type in (
            ("briefing", skript.build_briefing_mail("t3232"), "trip-briefing"),
            ("vergleich", skript.build_compare_mail("t3232"), "compare")):
        p = d / f"{art}.eml"
        p.write_bytes(_msg(subject, html, plain, mail_type).as_bytes())
        pfade[art] = p
    return pfade


_KAPUTT = {
    "kein_json": "{kein json",
    "kein_objekt": "[1, 2]",
    "schluessel_fehlt": '{"ampel": {}}',
    "segment_nicht_numerisch": '{"wind_zellen": {"zwei": ["orange"]}, "orte": {"x": ["green", "green"]}}',
}


@pytest.mark.parametrize("cli, art", [(BRIEFING_CLI, "briefing"), (VERGLEICH_CLI, "vergleich")],
                         ids=["briefing", "vergleich"])
@pytest.mark.parametrize("fall", sorted(_KAPUTT))
def test_cli_ungueltiges_soll_exit_2_klare_meldung(emls, cli, art, fall):
    if fall == "segment_nicht_numerisch" and art == "vergleich":
        pytest.skip("Segment-IDs gibt es nur im Briefing-Soll")
    r = subprocess.run([sys.executable, str(cli), "--lang", "de", "--eml", str(emls[art]),
                        "--windrichtung", _KAPUTT[fall]],
                       cwd=ROOT, capture_output=True, text=True, timeout=120)
    ausgabe = r.stdout + r.stderr
    assert r.returncode == 2, ausgabe
    assert _UNGUELTIG_RE.search(ausgabe), ausgabe
    assert "Traceback" not in ausgabe, ausgabe


# --------------------------------------------------------------------------- #
# AC-10: explizites Soll im Sendeskript (nicht aus der Mail abgeleitet)
# --------------------------------------------------------------------------- #
def test_sendeskript_briefing_soll_explizit(skript):
    assert skript.windrichtung_soll()["wind_zellen"] == {
        "2": ["orange", "orange"],
        "3": ["yellow", "yellow", "green"],
        "4": ["orange", "orange"],
        "5": ["red", "red"],
    }


def test_sendeskript_vergleich_soll_explizit(skript):
    assert skript.compare_windrichtung_soll()["orte"] == {
        "Gatehausen Nord": ["orange", "orange"],
        "Gatehausen Mitte": ["green", "yellow"],
        "Gatehausen Sued": ["green", "green"],
    }


def test_sendeskript_soll_ist_json_tauglich(skript):
    """Die Zeile 'Soll Windrichtung:' wird per json.dumps gedruckt und per
    --windrichtung zurueckgelesen: Rundweg ohne Verlust."""
    for soll in (skript.windrichtung_soll(), skript.compare_windrichtung_soll()):
        assert json.loads(json.dumps(soll)) == soll


# --------------------------------------------------------------------------- #
# AC-11: /e2e-verify uebergibt das Soll an beide Validatoren (DE und EN)
# --------------------------------------------------------------------------- #
def test_e2e_verify_ruft_validatoren_mit_windrichtung():  # doc-compliance-test
    zeilen = E2E_VERIFY_DOC.read_text(encoding="utf-8").splitlines()
    aufrufe = [z for z in zeilen
               if z.startswith("uv run python3 .claude/hooks/")
               and ("briefing_mail_validator.py" in z or "email_spec_validator.py" in z)]
    mit_soll = [z for z in aufrufe if "--windrichtung" in z]
    for validator in ("briefing_mail_validator.py", "email_spec_validator.py"):
        for lang in ("de", "en"):
            passend = [z for z in mit_soll if validator in z and f"--lang {lang}" in z]
            assert passend, (validator, lang, mit_soll)
    # Das Soll gilt nur fuer die Gate-Mails des Sendeskripts (Token), nie fuer Tag-Betreff-Mails.
    for z in mit_soll:
        assert "--subject-contains <token>" in z and "<Tag-Betreff>" not in z, z


# --------------------------------------------------------------------------- #
# Adversary F003 (#3232): Segment-ID nur ASCII-Ziffern ("²" ist isdigit, int() scheitert)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("sid", ["²", "٣", "-1", " 2"])
def test_cli_segment_id_nicht_ascii_ziffer_exit_2(emls, sid):
    r = subprocess.run([sys.executable, str(BRIEFING_CLI), "--lang", "de", "--eml", str(emls["briefing"]),
                        "--windrichtung", json.dumps({"wind_zellen": {sid: ["green"]}})],
                       cwd=ROOT, capture_output=True, text=True, timeout=120)
    ausgabe = r.stdout + r.stderr
    assert r.returncode == 2, ausgabe
    assert _UNGUELTIG_RE.search(ausgabe), ausgabe
    assert "Traceback" not in ausgabe, ausgabe


# --------------------------------------------------------------------------- #
# Adversary F002 (#3232): zellstufe -- fehlende Wind-Spalte, Punkt widerspricht Toenung
# --------------------------------------------------------------------------- #
def test_briefing_fehlende_wind_spalte_meldet_fehlt(briefing):
    """Wind-Spalte in Segment 3 umbenannt, Soll ueberall green -> Meldung 'fehlt',
    nie still als green gewertet."""
    v, (subject, html, plain), _soll = briefing
    block = _etappen_block(v, html, 3)
    neu = block.replace(">Wind</th>", ">Wynd</th>")
    assert neu != block
    zeilen = len([z for z in re.findall(r"<tr.*?</tr>", block, re.S) if "<td" in z])
    _ok, fehler = v.validate_message(_msg(subject, html.replace(block, neu), plain, "trip-briefing"),
                                     windrichtung={"wind_zellen": {"3": ["green"] * zeilen}})
    treffer = _windrichtung(fehler)
    assert len(treffer) == 1 and "Segment 3:" in treffer[0] and "fehlt" in treffer[0], fehler


def test_briefing_punktfarbe_widerspricht_toenung(briefing):
    """Toenung orange bleibt, Ampelpunkt einer Zelle wird rot -> genau eine Meldung
    'Toenung orange/Punkt red' (Widerspruch nie still als Toenung gewertet)."""
    from output.renderers.email.helpers import _AMPEL_DOT_COLORS

    v, (subject, html, plain), soll = briefing
    block = _etappen_block(v, html, 2)
    zelle = next(z for z in re.findall(r'<td[^>]*data-label="Wind"[^>]*>.*?</td>', block, re.S)
                 if f"background:{tone_css('orange')[0]};" in z and _PUNKT_RE.search(z))
    orange, rot = _AMPEL_DOT_COLORS["orange"][0], _AMPEL_DOT_COLORS["red"][0]
    assert orange in zelle
    falsch = html.replace(block, block.replace(zelle, zelle.replace(orange, rot), 1))
    _ok, fehler = v.validate_message(_msg(subject, falsch, plain, "trip-briefing"), windrichtung=soll)
    treffer = _windrichtung(fehler)
    assert len(treffer) == 1 and "Segment 2:" in treffer[0], fehler
    assert "Toenung orange/Punkt red" in treffer[0], fehler


# --------------------------------------------------------------------------- #
# Adversary F004 (#3232): Meldung nennt je abweichender Zelle Stunde, gefunden, erwartet
# --------------------------------------------------------------------------- #
def test_briefing_meldung_nennt_stunde_je_zelle(briefing):
    v, (subject, html, plain), soll = briefing
    block = _etappen_block(v, html, 3)
    zeilen = [z for z in re.findall(r"<tr.*?</tr>", block, re.S) if "<td" in z]
    stunden = [re.sub(r"<[^>]+>", "", re.findall(r"<td[^>]*>(.*?)</td>", z, re.S)[0]).strip()
               for z in zeilen]
    gelb, rot = (f"background:{tone_css(s)[0]};" for s in ("yellow", "red"))
    erste = zeilen[0]
    assert gelb in erste
    falsch = html.replace(block, block.replace(erste, erste.replace(gelb, rot), 1))
    _ok, fehler = v.validate_message(_msg(subject, falsch, plain, "trip-briefing"), windrichtung=soll)
    treffer = _windrichtung(fehler)
    assert len(treffer) == 1, fehler
    assert f"{stunden[0]} Toenung red/Punkt yellow statt yellow" in treffer[0], fehler
    assert f"{stunden[1]} " not in treffer[0].split("(je Stunde")[0], fehler


def test_briefing_genau_eine_wind_zelle_verfaelscht_genau_eine_meldung(briefing):
    """AC-2 (Befund 2): in Segment 2 (Soll orange, orange) wird NUR die Wind-Zelle der
    ersten Stunde per String-Ersetzung auf red gefaerbt (Toenung im <td>-Attribut und
    Ampelpunkt derselben Zelle) -> genau eine Meldung mit Segment, Stunde und
    'red statt orange'; die zweite Stunde taucht nicht als Abweichung auf."""
    from output.renderers.email.helpers import _AMPEL_DOT_COLORS

    v, (subject, html, plain), soll = briefing
    assert soll["wind_zellen"]["2"] == ["orange", "orange"]
    block = _etappen_block(v, html, 2)
    zeilen = [z for z in re.findall(r"<tr.*?</tr>", block, re.S) if "<td" in z]
    stunden = [re.sub(r"<[^>]+>", "", re.findall(r"<td[^>]*>(.*?)</td>", z, re.S)[0]).strip()
               for z in zeilen]
    erste_zelle = re.findall(r'<td[^>]*data-label="Wind"[^>]*>.*?</td>', zeilen[0], re.S)[0]
    orange_ton = f"background:{tone_css('orange')[0]};"
    rot_ton = f"background:{tone_css('red')[0]};"
    orange_punkt, rot_punkt = _AMPEL_DOT_COLORS["orange"][0], _AMPEL_DOT_COLORS["red"][0]
    assert orange_ton in erste_zelle and orange_punkt in erste_zelle
    neue_zelle = erste_zelle.replace(orange_ton, rot_ton, 1).replace(orange_punkt, rot_punkt, 1)
    assert neue_zelle != erste_zelle
    # Die zweite Stunde traegt dieselbe Zelle woertlich: ersetzt wird nur das ERSTE Vorkommen,
    # und das liegt in der ersten Zeile (Stunde 1).
    # Der Renderer stellt jede Stundentabelle zweimal ins HTML (Desktop/Handy, byte-gleich,
    # #1432); der Validator liest die dedupte Tabelle, beide Fassungen werden gleich veraendert.
    assert block.count(erste_zelle) == 2 and html.count(block) == 2
    assert block.index(erste_zelle) == block.index(zeilen[0]) + zeilen[0].index(erste_zelle)
    neuer_block = block.replace(erste_zelle, neue_zelle, 1)
    assert neuer_block.count(neue_zelle) == 1 and neuer_block.count(erste_zelle) == 1
    falsch = html.replace(block, neuer_block)
    assert falsch != html
    _ok, fehler = v.validate_message(_msg(subject, falsch, plain, "trip-briefing"), windrichtung=soll)
    treffer = _windrichtung(fehler)
    assert len(treffer) == 1, fehler
    abweichungen = treffer[0].split("(je Stunde")[0]
    assert "Segment 2:" in abweichungen and stunden[0] in abweichungen, treffer
    assert "red statt orange" in abweichungen, treffer
    assert abweichungen.count("statt") == 1, treffer  # nur eine Zelle weicht ab
    assert stunden[0] != stunden[1]


# --------------------------------------------------------------------------- #
# Adversary F001 (#3232): --windrichtung kommt auf jedem Weg im Validator an
# (CLI --eml, run_validation, CLI-IMAP-Weg). Nur der IMAP-Abruf wird durch die
# lokale Mail ersetzt (Modul-Attribut), alles andere ist der echte Code.
# --------------------------------------------------------------------------- #
_SOLL_FUNK = {"briefing": "windrichtung_soll", "vergleich": "compare_windrichtung_soll"}
_CLI = {"briefing": BRIEFING_CLI, "vergleich": VERGLEICH_CLI}


@pytest.fixture(scope="module")
def falsche_emls(skript, briefing, tmp_path_factory):
    d = tmp_path_factory.mktemp("eml_3232_falsch")
    subject, html, plain = skript.build_briefing_mail("t3232")
    cs, ch, cp = skript.build_compare_mail("t3232")
    pfade = {"briefing": d / "b_falsch.eml", "vergleich": d / "v_falsch.eml"}
    pfade["briefing"].write_bytes(_msg(subject, _etappe_umfaerben(briefing[0], html, 2, "orange", "green"),
                                       plain, "trip-briefing").as_bytes())
    pfade["vergleich"].write_bytes(_msg(cs, _zelle_umfaerben(ch, "0 °", "orange", "transparent"),
                                        cp, "compare").as_bytes())
    return pfade


@pytest.mark.parametrize("art", ["briefing", "vergleich"])
def test_cli_eml_reicht_windrichtung_durch(skript, emls, falsche_emls, art):
    soll = json.dumps(getattr(skript, _SOLL_FUNK[art])())

    def lauf(pfad):
        return subprocess.run([sys.executable, str(_CLI[art]), "--lang", "de", "--eml", str(pfad),
                               "--windrichtung", soll],
                              cwd=ROOT, capture_output=True, text=True, timeout=120)

    gut, schlecht = lauf(emls[art]), lauf(falsche_emls[art])
    assert "SOLL: Windrichtung" not in gut.stdout + gut.stderr, gut.stdout
    assert schlecht.returncode == 1, schlecht.stdout + schlecht.stderr
    assert "SOLL: Windrichtung" in schlecht.stdout, schlecht.stdout


def _abruf_aus_datei(monkeypatch, mod, art, pfad):
    msg = email.message_from_bytes(pfad.read_bytes())
    name = "fetch_latest_message" if art == "briefing" else "_fetch_latest_message"
    assert callable(getattr(mod, name))
    monkeypatch.setattr(mod, name, lambda *a, **kw: msg)


@pytest.mark.parametrize("art", ["briefing", "vergleich"])
def test_run_validation_reicht_windrichtung_durch(skript, briefing, vergleich, falsche_emls,
                                                  monkeypatch, art):
    mod = briefing[0] if art == "briefing" else vergleich[0]
    _abruf_aus_datei(monkeypatch, mod, art, falsche_emls[art])
    soll = getattr(skript, _SOLL_FUNK[art])()
    if art == "briefing":
        _ok, fehler = mod.run_validation(mail_type="trip-briefing", lang="de", windrichtung=soll)
    else:
        _ok, fehler = mod.run_validation(3, lang="de", windrichtung=soll)
    assert len(_windrichtung(fehler)) == 1, fehler


@pytest.mark.parametrize("art", ["briefing", "vergleich"])
def test_cli_imap_weg_reicht_windrichtung_durch(skript, briefing, vergleich, falsche_emls,
                                                monkeypatch, capsys, art):
    mod = briefing[0] if art == "briefing" else vergleich[0]
    _abruf_aus_datei(monkeypatch, mod, art, falsche_emls[art])
    # Kein Validator-Log aus dem Test ins geteilte Repo.
    monkeypatch.setattr(mod, "_write_validation_log", lambda *a, **kw: None)
    soll = json.dumps(getattr(skript, _SOLL_FUNK[art])())
    monkeypatch.setattr(sys, "argv", [str(_CLI[art]), "--lang", "de", "--subject-contains", "t3232",
                                      "--windrichtung", soll])
    with pytest.raises(SystemExit) as ende:
        mod.main()
    ausgabe = capsys.readouterr().out
    assert ende.value.code == 1, ausgabe
    assert "SOLL: Windrichtung" in ausgabe, ausgabe
