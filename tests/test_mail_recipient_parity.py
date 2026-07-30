"""Empfaenger-Regelwerk-Paritaet Python <-> Go (Issue #1412, Scheibe S2a).

Spec: docs/specs/modules/fix_1412_s2a_regelwerk_paritaet.md
Analyse: docs/context/fix-1412-s2-regelwerk-paritaet.md, Abschnitt "Analysis (S2a)"

Python (`src/output/channels/email.py`) und Go (`internal/mail/sender.go`)
beurteilen denselben Mail-Empfaenger heute mit zwei getrennten, handgepflegten
Regelwerken -- nachweislich mit unterschiedlichem Ergebnis in mehreren
Faellen. Dieser Laeufer prueft die PYTHON-Seite gegen eine geteilte
Falltabelle (`tests/fixtures/mail_recipient_parity/faelle.json`); das
Go-Pendant ist `internal/mail/recipient_parity_test.go` (Phase 6 -- das
Renderer-Commit-Gate #811 blockt .go-Edits in der RED-Phase).

WICHTIG: Dieser Laeufer aendert und ruft NICHTS an `src/output/channels/
email.py` oder `internal/mail/sender.go` -- reines Pruefwerkzeug (AC-10).
Kein Netz, keine echte Mail: der SMTP-Transport wird durch eine
Sentinel-Ausnahme ersetzt, die den Guard-Entscheidungspunkt misst, ohne
jemals zu senden.

ERWARTUNG in dieser Phase (TDD RED, `ausnahmen: []`): die python-seitig
gemessenen Divergenzen D3, D5 und N1 werden NAMENTLICH gemeldet. D1, D2 und
D4 sind reine GO-seitige Divergenzen (Analyse S2a, "Ehrliche Grenze des
Mechanismus" -- Entscheidungs-Paritaet misst je eine Seite) und fuer DIESEN
Laeufer strukturell unsichtbar; sie werden erst mit dem Go-Laeufer (Phase 6)
rot.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from output.channels.base import OutputConfigError
from output.channels import email as email_module

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "mail_recipient_parity"
FALLTABELLE = FIXTURE_DIR / "faelle.json"
EMAIL_PY = REPO_ROOT / "src" / "output" / "channels" / "email.py"
GO_SENDER = REPO_ROOT / "internal" / "mail" / "sender.go"

# Regel-Budget (CLAUDE.md): ersetzt keine bestehende Regel, traegt daher ein
# Pruefdatum von +90 Tagen ab 2026-07-30 -- 2026-10-28. Bauform-Vorbild:
# EXPIRY in tests/tdd/test_repo_path_hardcoding_ratchet.py:339. Zusaetzlich
# traegt jede EINZELNE Ausnahme in der Falltabelle ihre eigene Frist.
EXPIRY = date(2026, 10, 28)

# Mindestlaenge einer Ausnahme-Begruendung, gemessen in Buchstaben/Ziffern
# (Vorbild: _MIN_BEGRUENDUNG in test_repo_path_hardcoding_ratchet.py:351).
_MIN_BEGRUENDUNG = 15
_UNWORT = re.compile(r"[\W_]+")

# OutputConfigError-Marker, die eine tatsaechliche Guard-Blockade von jedem
# anderen Fehlertyp unterscheiden (email.py:490, :530 -- Issue #1147/#1219
# bzw. #1235). Ohne Marker: lauter Abbruch, NIE still als "block" gebucht.
_BLOCK_MARKERS = ("#1147", "#1219", "#1235")


# -----------------------------------------------------------------------
# Ausnahmen
# -----------------------------------------------------------------------


@dataclass(frozen=True)
class Ausnahme:
    """Eine festgenagelte, befristete Divergenz-Behauptung ueber eine Seite
    (Analyse S2a, Abschnitt "Falltabelle"). `ist` ist eine Behauptung ueber
    die WIRKLICHKEIT, keine Abschaltung -- weicht das gemessene Ergebnis von
    `ist` ab, ist die Ausnahme entweder aufgeloest (gemessen == soll) oder
    schlicht falsch und muss aktualisiert werden."""

    fall: str
    seite: str  # "python" | "go" | "beide"
    ist: str  # "allow" | "block"
    scheibe: str
    frist: date
    grund: str


def _lade_ausnahmen(roh: list[dict]) -> list[Ausnahme]:
    return [
        Ausnahme(
            fall=eintrag["fall"],
            seite=eintrag["seite"],
            ist=eintrag["ist"],
            scheibe=eintrag["scheibe"],
            frist=date.fromisoformat(eintrag["frist"]),
            grund=eintrag["grund"],
        )
        for eintrag in roh
    ]


def _bewerte_fall(
    fall_id: str,
    soll: str,
    gemessen: str,
    ausnahmen_fuer_fall: list[Ausnahme],
    heute: date,
) -> str | None:
    """Vergleicht Sollwert und gemessenes Ergebnis eines Falls gegen die
    zugehoerigen Ausnahme-Eintraege (AC-2/AC-3/AC-5/AC-6). Liefert eine
    benannte Fehlermeldung oder None (Fall in Ordnung)."""
    for ausnahme in ausnahmen_fuer_fall:
        laenge_grund = len(_UNWORT.sub("", ausnahme.grund))
        if laenge_grund < _MIN_BEGRUENDUNG:
            # AC-5: zaehlt NICHT als gueltige Ausnahme -- wie fehlend behandeln.
            continue
        if ausnahme.frist < heute:
            return (
                f"{fall_id}: Ausnahme ({ausnahme.seite}) ist am "
                f"{ausnahme.frist.isoformat()} abgelaufen (Frist ueberschritten) "
                "-- Ausnahme erneuern oder entfernen (AC-6)."
            )
        if gemessen == soll:
            return (
                f"{fall_id}: Ausnahme ({ausnahme.seite}) behauptet ist="
                f"{ausnahme.ist!r}, gemessen wird aber bereits soll={soll!r} "
                "-- Divergenz aufgeloest, Ausnahme entfernen (AC-3)."
            )
        if ausnahme.ist == gemessen:
            return None  # gedeckte, weiterhin zutreffende Divergenz
        return (
            f"{fall_id}: Ausnahme ({ausnahme.seite}) behauptet ist="
            f"{ausnahme.ist!r}, gemessen wurde aber {gemessen!r} -- Ausnahme "
            "stimmt nicht mehr mit der Wirklichkeit ueberein, pruefen (AC-3)."
        )
    if gemessen != soll:
        return (
            f"{fall_id}: soll={soll!r}, gemessen={gemessen!r} -- unentschuldigte "
            "Divergenz ohne gueltige Ausnahme (AC-2)."
        )
    return None


def _deckel_ueberschritten(daten: dict) -> bool:
    """AC-4: der Ausnahmen-Deckel zaehlt ALLE eingetragenen Ausnahmen (auch
    abgelaufene/zu kurz begruendete) -- eine unaufgeloeste Divergenz, die
    per neuer Ausnahme "versteckt" wird, reisst den Deckel trotzdem."""
    return len(daten.get("ausnahmen", [])) > daten["ausnahmen_hoechstzahl"]


# -----------------------------------------------------------------------
# Falltabelle laden
# -----------------------------------------------------------------------


def _lade_falltabelle(pfad: Path = FALLTABELLE) -> dict:
    assert pfad.exists(), (
        f"Falltabelle fehlt: {pfad} -- der Laeufer haette dann keine Faelle "
        "zu pruefen und wuerde 'nichts gefunden, alles gruen' still "
        "durchwinken (AC-7)."
    )
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    assert daten.get("faelle"), (
        f"Falltabelle {pfad.name} enthaelt keine Faelle -- eine leere "
        "Fallliste waere ein stilles Gruen ohne echte Pruefung (AC-7)."
    )
    return daten


def _baue_datenwurzel(tmp_path: Path, profile: dict) -> Path:
    """Schreibt jeden Profil-Eintrag WOERTLICH nach <tmp>/data/users/<id>/
    user.json -- kein Feld-Mapping, keine Default-Regel (Analyse S2a,
    Abschnitt "Falltabelle"). Noetig, weil D3/D4/D5/N1 in der
    Allowlist-BEFUELLUNG sitzen, nicht in der Pruefung selbst."""
    data_root = tmp_path / "data"
    for user_id, inhalt in profile.items():
        user_dir = data_root / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "user.json").write_text(json.dumps(inhalt), encoding="utf-8")
    return data_root


# -----------------------------------------------------------------------
# Python-Entscheidung messen
# -----------------------------------------------------------------------


class _TransportSentinel(Exception):
    """Ersetzt smtplib.SMTP() am Transport. Erbt bewusst WEDER von
    smtplib.SMTPException NOCH von OSError, damit sie durch alle vier
    except-Zweige in EmailOutput.send() OHNE Retry durchfaellt (Analyse
    S2a, Abschnitt "Wie jede Seite an ihre Entscheidung kommt") -- eine
    gefangene Sentinel bedeutet: der Guard hat NICHT geblockt."""


def _raise_sentinel(*_args, **_kwargs):
    raise _TransportSentinel("Transport erreicht -- Guard hat nicht geblockt")


def _python_entscheidung(host: str, to: str, data_root: Path) -> str:
    """Baut EmailOutput UNTER UMGEHUNG von Settings (__new__ + Attribute
    direkt) und fuehrt send() gegen den Sentinel-Transport, um NUR die
    Guard-Entscheidung zu messen.

    Zwei zwingende Konstruktionsdetails (Analyse S2a):
    1. Objekt NICHT ueber Settings bauen -- _resend_default_deny
       (config.py:195-215) lenkt unter pytest jeden Resend-Host auf
       Stalwart um und wuerde den falschen Zweig messen.
    2. Datenwurzel ueber app.loader._DATA_ROOT setzen, NICHT ueber
       GZ_DATA_DIR -- _DATA_ROOT hat Vorrang (loader.py:1054) und
       tests/conftest.py setzt es bereits autouse.
    """
    from app import loader

    output = email_module.EmailOutput.__new__(email_module.EmailOutput)
    output._host = host
    output._port = 587
    output._user = "paritaet-test-user"
    output._password = "paritaet-test-pass"
    output._to = "fallback@henemm.com"
    output._from = "fallback@henemm.com"
    output._reply_to = None
    output._fallback_host = None
    output._fallback_user = None
    output._fallback_pass = None

    zuvor = getattr(loader, "_DATA_ROOT", None)
    echtes_smtp = email_module.smtplib.SMTP
    loader._DATA_ROOT = str(data_root)
    email_module.smtplib.SMTP = _raise_sentinel
    try:
        output.send("Paritaets-Pruefung", "Testkoerper", html=False, to=[to])
    except _TransportSentinel:
        return "allow"
    except OutputConfigError as exc:
        if any(marker in str(exc) for marker in _BLOCK_MARKERS):
            return "block"
        pytest.fail(
            f"OutputConfigError OHNE Guard-Marker fuer to={to!r} host={host!r}: "
            f"{exc} -- niemals still als 'block' buchen."
        )
    except Exception as exc:  # pragma: no cover - lauter Abbruch, kein stilles Gruen
        pytest.fail(
            f"Unerwarteter Fehlertyp {type(exc).__name__} fuer to={to!r} "
            f"host={host!r}: {exc}"
        )
    else:
        pytest.fail(
            f"send() kehrte OHNE Sentinel zurueck fuer to={to!r} host={host!r} "
            "-- Transport wurde erreicht, ohne dass die Sentinel griff "
            "(Sentinel-Pflicht verletzt)."
        )
    finally:
        email_module.smtplib.SMTP = echtes_smtp
        loader._DATA_ROOT = zuvor


def _pruefe_falltabelle(daten: dict, tmp_path: Path) -> tuple[list[str], dict[str, str]]:
    """Fuehrt jeden Fall aus `daten` gegen den Python-Laeufer und liefert
    (benannte Befunde, gemessene Ergebnisse je Fall-ID)."""
    ausnahmen = _lade_ausnahmen(daten.get("ausnahmen", []))
    data_root = _baue_datenwurzel(tmp_path, daten.get("profile", {}))

    befunde: list[str] = []
    ergebnisse: dict[str, str] = {}
    for fall in daten["faelle"]:
        gemessen = _python_entscheidung(fall["host"], fall["to"], data_root)
        ergebnisse[fall["id"]] = gemessen
        zugehoerige = [
            a for a in ausnahmen if a.fall == fall["id"] and a.seite in ("python", "beide")
        ]
        befund = _bewerte_fall(fall["id"], fall["soll"], gemessen, zugehoerige, date.today())
        if befund:
            befunde.append(befund)
    return befunde, ergebnisse


# -----------------------------------------------------------------------
# Tests: Entscheidungs-Paritaet + Ausnahmen-Mechanik (AC-1..AC-7)
# -----------------------------------------------------------------------


def test_entscheidungsparitaet(tmp_path):
    """AC-1/AC-2/AC-3/AC-5/AC-6 gegen den ausgelieferten Stand. Erwartung
    RED (ausnahmen: []): D3, D5, N1 werden namentlich gemeldet -- D1, D2, D4
    sind reine Go-Divergenzen und fuer diesen Laeufer strukturell unsichtbar
    (siehe Modul-Docstring)."""
    daten = _lade_falltabelle()
    befunde, ergebnisse = _pruefe_falltabelle(daten, tmp_path)

    assert not befunde, "Python-Laeufer meldet Abweichungen:\n" + "\n".join(befunde)

    # Selbstnachweis 2: Sentinel-Pflicht -- der Gesamtlauf muss beide
    # Entscheidungsarten tatsaechlich gemessen haben.
    werte = set(ergebnisse.values())
    assert "allow" in werte and "block" in werte, (
        f"Laeufer hat keine Bandbreite an Entscheidungen gemessen ({werte}) "
        "-- Sentinel-Pflicht verletzt (Selbstnachweis 2)."
    )


def test_ausnahmen_deckel_im_ausgelieferten_stand_nicht_ueberschritten():
    daten = _lade_falltabelle()
    assert not _deckel_ueberschritten(daten), (
        f"{len(daten['ausnahmen'])} Ausnahmen ueberschreiten den Deckel "
        f"({daten['ausnahmen_hoechstzahl']})."
    )


def test_ac4_deckel_ueberschreitung_wird_erkannt():
    """AC-4: eine siebte, nicht gedeckte Divergenz bei unveraendertem Deckel
    (6) laesst die Pruefung rot werden -- unabhaengig vom Inhalt der neuen
    Ausnahme. Synthetische Fixture, ruehrt die ausgelieferte Datei nicht an."""
    daten = {
        "ausnahmen_hoechstzahl": 6,
        "ausnahmen": [
            {
                "fall": f"F{i}",
                "seite": "python",
                "ist": "block",
                "scheibe": "S2b",
                "frist": "2026-10-28",
                "grund": f"ausreichend lange Begruendung Nummer {i}",
            }
            for i in range(7)
        ],
    }
    assert _deckel_ueberschritten(daten), (
        "7 Ausnahmen bei Deckel 6 haetten als Ueberschreitung erkannt werden muessen."
    )


def test_ac2_unentschuldigte_divergenz_wird_benannt():
    befund = _bewerte_fall("F-TEST", "allow", "block", [], date(2026, 7, 30))
    assert befund is not None and "F-TEST" in befund, (
        f"Unentschuldigte Divergenz wurde nicht benannt: {befund!r}"
    )


def test_ac3_aufgeloeste_ausnahme_verlangt_entfernen():
    ausnahme = Ausnahme(
        fall="F-TEST", seite="python", ist="block", scheibe="S2b",
        frist=date(2026, 10, 28), grund="ausreichend lange Begruendung fuer den Test",
    )
    befund = _bewerte_fall("F-TEST", "allow", "allow", [ausnahme], date(2026, 7, 30))
    assert befund is not None and "entfernen" in befund.lower(), (
        f"Aufgeloeste Ausnahme haette 'entfernen' verlangen muessen: {befund!r}"
    )


def test_ac5_zu_kurze_begruendung_zaehlt_nicht():
    ausnahme = Ausnahme(
        fall="F-TEST", seite="python", ist="block", scheibe="S2b",
        frist=date(2026, 10, 28), grund="zu kurz",
    )
    befund = _bewerte_fall("F-TEST", "allow", "block", [ausnahme], date(2026, 7, 30))
    assert befund is not None and "F-TEST" in befund, (
        f"Zu kurze Begruendung haette wie eine fehlende Ausnahme behandelt "
        f"werden muessen: {befund!r}"
    )


def test_ac6_abgelaufene_frist_bricht_ab():
    ausnahme = Ausnahme(
        fall="F-TEST", seite="python", ist="block", scheibe="S2b",
        frist=date(2026, 1, 1), grund="ausreichend lange Begruendung fuer den Test",
    )
    befund = _bewerte_fall("F-TEST", "allow", "block", [ausnahme], date(2026, 7, 30))
    assert befund is not None and "abgelaufen" in befund.lower(), (
        f"Abgelaufene Frist haette benannt werden muessen: {befund!r}"
    )


def test_ac7_fehlende_falltabelle_bricht_laut_ab(tmp_path):
    pfad = tmp_path / "nicht-vorhanden.json"
    with pytest.raises(AssertionError, match="fehlt"):
        _lade_falltabelle(pfad)


def test_ac7_leere_fallliste_bricht_laut_ab(tmp_path):
    pfad = tmp_path / "faelle.json"
    pfad.write_text(
        json.dumps({"faelle": [], "profile": {}, "ausnahmen": []}), encoding="utf-8"
    )
    with pytest.raises(AssertionError, match="keine Faelle"):
        _lade_falltabelle(pfad)


def test_ac7_fixture_datenwurzel_fehlt_wird_erkannt(tmp_path):
    """Negativkontrolle zum Selbstnachweis 1 ('Fixture-Erreichbarkeit'): OHNE
    den Fixture-Nutzer im Datenverzeichnis wird die nur-im-Fixture
    existierende Adresse korrekt BLOCKIERT -- der positive Nachweis in
    test_entscheidungsparitaet (Fall 'fixture-erreichbarkeit') ist also
    nicht zufaellig gruen."""
    data_root = _baue_datenwurzel(tmp_path, {})  # kein paritaet-fixture-nutzer
    ergebnis = _python_entscheidung(
        "smtp.resend-fixture.test", "paritaet-fixture@henemm.com", data_root
    )
    assert ergebnis == "block", (
        f"Ohne geladene Fixture-Datenwurzel haette dieser Fall 'block' liefern "
        f"muessen, gemessen wurde aber {ergebnis!r} -- der Selbstnachweis waere "
        "wirkungslos."
    )


# -----------------------------------------------------------------------
# Konstanten-Paritaet (AC-8) -- Go-Quelle als Text, Python ueber Import.
# LOCAL_MAIL_DOMAINS (nur Python) und reservedTestDomainSuffixes (nur Go,
# das ist exakt die Ursache von D3) haben KEIN Pendant in der jeweils
# anderen Sprache und sind daher NICHT Teil dieses Vergleichs -- eine
# Konstante ohne Gegenstueck kann nicht semantisch verglichen werden, nur
# die Entscheidungs-Paritaet faengt diese Klasse von Drift.
# -----------------------------------------------------------------------

_CONTROL_ESCAPE_ALIASES = {"r": "\r", "n": "\n", "v": "\x0b", "f": "\x0c", "0": "\x00", "t": "\t"}


def _go_quelltext() -> str:
    assert GO_SENDER.exists(), f"Go-Quelle fehlt: {GO_SENDER}"
    return GO_SENDER.read_text(encoding="utf-8")


def _go_ohne_kommentare(text: str) -> str:
    """F002-Vorbild (test_egress_inventory_drift.py:40-51): jede Zeile wird
    am ERSTEN '//' abgeschnitten, nur der Teil davor zaehlt -- eine
    auskommentierte Deklaration zaehlt NICHT."""
    return "\n".join(zeile.split("//", 1)[0] for zeile in text.splitlines())


def _go_map_keys(text: str, name: str) -> frozenset[str]:
    """Extrahiert die string-Schluessel aus `name = map[string]bool{...}`."""
    muster = re.compile(rf"{re.escape(name)}\s*=\s*map\[string\]bool\{{(.*?)\}}", re.DOTALL)
    treffer = muster.search(_go_ohne_kommentare(text))
    assert treffer, f"Go-Konstante {name!r} nicht gefunden in {GO_SENDER.name}."
    return frozenset(re.findall(r'"([^"]*)"', treffer.group(1)))


def _go_string_slice(text: str, name: str) -> tuple[str, ...]:
    muster = re.compile(rf"{re.escape(name)}\s*=\s*\[\]string\{{(.*?)\}}", re.DOTALL)
    treffer = muster.search(_go_ohne_kommentare(text))
    assert treffer, f"Go-Konstante {name!r} nicht gefunden in {GO_SENDER.name}."
    return tuple(re.findall(r'"([^"]*)"', treffer.group(1)))


def _go_regex_literal(text: str, name: str) -> str:
    muster = re.compile(rf"{re.escape(name)}\s*=\s*regexp\.MustCompile\(`([^`]*)`\)")
    treffer = muster.search(text)
    assert treffer, f"Go-Regex {name!r} nicht gefunden in {GO_SENDER.name}."
    return treffer.group(1)


def _codepoints_aus_zeichenklasse(muster: str) -> frozenset[str]:
    """Normalisiert eine Regex-Zeichenklasse wie r'[\\r\\n\\x0b\\x0c\\x00]'
    auf die Menge ihrer Codepunkte -- Python- und Go-Escapes fuer dasselbe
    Zeichen (\\v vs. \\x0b, \\f vs. \\x0c) sind textuell verschieden, aber
    bedeutungsgleich (Analyse S2a)."""
    treffer = re.search(r"\[(.*?)\]", muster)
    assert treffer, f"Keine Zeichenklasse in Muster erkennbar: {muster!r}"
    tokens = re.findall(r"\\x[0-9a-fA-F]{2}|\\.", treffer.group(1))
    codepoints: set[str] = set()
    for tok in tokens:
        if tok.startswith("\\x"):
            codepoints.add(chr(int(tok[2:], 16)))
        else:
            zeichen = tok[1]
            codepoints.add(_CONTROL_ESCAPE_ALIASES.get(zeichen, zeichen))
    return frozenset(codepoints)


def _go_inline_ignorecase(muster: str) -> tuple[str, bool]:
    """Trennt Go's Inline-Modifikator (?i) vom restlichen Regex-Text --
    Python nutzt stattdessen das re.IGNORECASE-Flag (bedeutungsgleich)."""
    if muster.startswith("(?i)"):
        return muster[4:], True
    return muster, False


def test_konstantenparitaet():
    """AC-8: reservierte Test-Domains, Bare-TLDs, TLD-Suffixe sowie die
    zwei Steuerzeichen-Regexe stimmen zwischen Python und Go SEMANTISCH
    ueberein, auch wenn sie unterschiedlich geschrieben sind."""
    text = _go_quelltext()

    go_domains = _go_map_keys(text, "reservedTestDomains")
    assert email_module._RESERVED_TEST_DOMAINS == go_domains, (
        f"Reservierte Test-Domains driften: "
        f"python={sorted(email_module._RESERVED_TEST_DOMAINS)} go={sorted(go_domains)}"
    )

    go_bare_tlds = _go_map_keys(text, "reservedBareTLDs")
    assert frozenset(email_module._RESERVED_BARE_TLDS) == go_bare_tlds, (
        f"Reservierte Bare-TLDs driften: "
        f"python={sorted(email_module._RESERVED_BARE_TLDS)} go={sorted(go_bare_tlds)}"
    )

    go_tlds = _go_string_slice(text, "reservedTestTLDs")
    assert frozenset(email_module._RESERVED_TEST_TLDS) == frozenset(go_tlds), (
        f"Reservierte Test-TLDs driften: "
        f"python={email_module._RESERVED_TEST_TLDS} go={go_tlds}"
    )

    py_control = _codepoints_aus_zeichenklasse(email_module._CONTROL_CHARS_RE.pattern)
    go_control = _codepoints_aus_zeichenklasse(_go_regex_literal(text, "controlCharsRe"))
    assert py_control == go_control, (
        f"Steuerzeichen-Regex driftet: python={py_control!r} go={go_control!r}"
    )

    py_muster = email_module._TEST_MAILBOX_RAW_PATTERN.pattern
    py_ignorecase = bool(email_module._TEST_MAILBOX_RAW_PATTERN.flags & re.IGNORECASE)
    go_muster_roh = _go_regex_literal(text, "testMailboxRawRe")
    go_muster, go_ignorecase = _go_inline_ignorecase(go_muster_roh)
    assert py_muster == go_muster, (
        f"Test-Postfach-Regex driftet (Textteil): python={py_muster!r} go={go_muster!r}"
    )
    assert py_ignorecase == go_ignorecase, (
        f"IGNORECASE-Flag driftet: python={py_ignorecase} go={go_ignorecase} (Go Inline (?i))"
    )


def test_konstantenparitaet_erkennt_drift():
    """AC-8 zweite Haelfte: ein synthetisch veraenderter Konstantenwert (NICHT
    die echte Go-Datei) laesst den Vergleich rot werden -- sonst waere
    test_konstantenparitaet nur zufaellig gruen."""
    synth = (
        'var (\n'
        '\treservedTestDomains = map[string]bool{\n'
        '\t\t"example.com": true,\n'
        '\t\t"example.net": true,\n'
        '\t\t"example.org": true,\n'
        '\t\t"gedriftet.example": true,\n'
        '\t}\n'
        ')\n'
    )
    go_domains = _go_map_keys(synth, "reservedTestDomains")
    assert email_module._RESERVED_TEST_DOMAINS != go_domains, (
        "Synthetisch veraenderter Konstantenwert wurde NICHT als Drift "
        "erkannt -- der Vergleich haette diese Aenderung fangen muessen."
    )


def test_go_konstanten_parser_ignoriert_kommentare():
    """Selbstnachweis 4a (Vorbild test_egress_inventory_drift.py:85-104):
    eine auskommentierte Zeile zaehlt NICHT als Deklaration, ein legitimer
    Inline-Kommentar hinter einem echten Eintrag stoert nicht."""
    synth = (
        'var (\n'
        '\treservedBareTLDs = map[string]bool{\n'
        '\t\t// "auskommentiert": true,\n'
        '\t\t"echt": true, // Notiz hinter echtem Eintrag\n'
        '\t}\n'
        ')\n'
    )
    ergebnis = _go_map_keys(synth, "reservedBareTLDs")
    assert "auskommentiert" not in ergebnis, (
        "Auskommentierte Zeile wurde faelschlich als Deklaration gezaehlt."
    )
    assert "echt" in ergebnis, "Eintrag mit legitimem Inline-Kommentar wurde nicht erkannt."


# -----------------------------------------------------------------------
# Verzweigungs-Ratsche Python-Seite (AC-9), Baustein 4 der Analyse.
# -----------------------------------------------------------------------


def _finde_guard_if(baum: ast.Module) -> ast.If | None:
    """Findet die If-Anweisung im Rumpf von EmailOutput.send(), deren
    Bedingung das String-Literal 'resend' enthaelt -- NICHT ueber
    Zeilennummern oder Marker-Kommentare, also ohne Zeichenwechsel an der
    geschuetzten Datei (Analyse S2a, Baustein 4)."""
    for klasse in ast.walk(baum):
        if isinstance(klasse, ast.ClassDef) and klasse.name == "EmailOutput":
            for methode in klasse.body:
                if isinstance(methode, ast.FunctionDef) and methode.name == "send":
                    for anweisung in methode.body:
                        if isinstance(anweisung, ast.If):
                            for teil in ast.walk(anweisung.test):
                                if isinstance(teil, ast.Constant) and teil.value == "resend":
                                    return anweisung
    return None


def _zaehle_entscheidungspunkte(knoten: ast.AST) -> int:
    """Entscheidungspunkte in einem AST-Teilbaum: jedes If, jeder
    BoolOp-Operand ab dem zweiten (and/or-Verkettung), jede IfExp (Ternary)
    und jedes Comprehension-if. Eigene, dokumentierte Zaehlregel -- die Zahl
    ist NICHT mit der Go-Zahl vergleichbar (Analyse S2a: unterschiedliche
    Zaehlregeln je Sprache, jede Seite ratscht nur gegen sich selbst)."""
    anzahl = 0
    for n in ast.walk(knoten):
        if isinstance(n, ast.If):
            anzahl += 1
        elif isinstance(n, ast.BoolOp):
            anzahl += len(n.values) - 1
        elif isinstance(n, ast.IfExp):
            anzahl += 1
        elif isinstance(n, ast.comprehension):
            anzahl += len(n.ifs)
    return anzahl


def test_verzweigungsratsche_python_region_gefunden_und_zahl_stimmt():
    baum = ast.parse(EMAIL_PY.read_text(encoding="utf-8"))
    guard_if = _finde_guard_if(baum)
    assert guard_if is not None, (
        "Selbstnachweis 4b: die Guard-If-Anweisung mit dem Literal 'resend' "
        "wurde in EmailOutput.send() nicht gefunden -- Region verloren, die "
        "Ratsche prueft nichts mehr (AC-7)."
    )
    gezaehlt = _zaehle_entscheidungspunkte(guard_if)
    daten = _lade_falltabelle()
    erwartet = daten["verzweigungen_python"]
    assert gezaehlt == erwartet, (
        f"Python-Guard-Region hat jetzt {gezaehlt} Entscheidungspunkte "
        f"(Fixture: {erwartet}) -- neue Verzweigung ohne abdeckenden Fall? "
        "Fixture-Zahl nach Pruefung anpassen (AC-9)."
    )


def test_verzweigungsratsche_erkennt_wachstum():
    """AC-9: ein synthetisch um eine Bedingung erweiterter Guard-Codeabschnitt
    laesst die Ratsche rot werden -- unabhaengig von echtem Code."""
    quelle_alt = 'if "resend" in host:\n    if a:\n        pass\n'
    quelle_neu = 'if "resend" in host:\n    if a and b:\n        pass\n'
    alt = _zaehle_entscheidungspunkte(ast.parse(quelle_alt).body[0])
    neu = _zaehle_entscheidungspunkte(ast.parse(quelle_neu).body[0])
    assert neu > alt, "Eine zusaetzliche Bedingung wurde nicht als Wachstum erkannt."


def test_ac7_fehlende_ast_region_bricht_laut_ab():
    """AC-7, Szenario 3: entfernt man das Literal 'resend' aus der
    Bedingung, darf KEINE Region gefunden werden -- sonst waere die Ratsche
    gegen einen falschen Codeabschnitt blind."""
    quelle = (
        'class EmailOutput:\n'
        '    def send(self, to):\n'
        '        if "anderes-literal" in self._host:\n'
        '            pass\n'
    )
    baum = ast.parse(quelle)
    guard_if = _finde_guard_if(baum)
    assert guard_if is None, (
        "Ohne das Literal 'resend' in der Bedingung darf keine Region "
        "gefunden werden."
    )


# -----------------------------------------------------------------------
# Regel-Budget + AC-10 (keine Produktivzeile geaendert)
# -----------------------------------------------------------------------


def test_regelbudget_pruefdatum_ist_maschinell_auffindbar():
    assert EXPIRY == date(2026, 10, 28), (
        "Pruefdatum des Regel-Budgets (+90 Tage ab 2026-07-30), Vorbild EXPIRY "
        "in test_repo_path_hardcoding_ratchet.py:339."
    )
    text = Path(__file__).read_text(encoding="utf-8")
    treffer = [n for n, zeile in enumerate(text.splitlines(), 1) if EXPIRY.isoformat() in zeile]
    assert treffer, (
        "Das ISO-Datum des Pruefdatums muss zusaetzlich als Text in der Datei "
        "stehen, damit es maschinell auffindbar bleibt (Regel-Budget, CLAUDE.md)."
    )


def test_ac10_keine_produktivzeile_geaendert():
    """AC-10: git diff zeigt keine Aenderung an email.py/sender.go gegenueber
    HEAD -- diese Scheibe ist ein reines Pruefwerkzeug ohne Produktivaenderung."""
    for pfad in (EMAIL_PY, GO_SENDER):
        ergebnis = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", str(pfad)],
            cwd=REPO_ROOT,
            check=False,
        )
        assert ergebnis.returncode == 0, (
            f"{pfad.relative_to(REPO_ROOT)} weicht von HEAD ab -- diese Scheibe "
            "darf KEINE Produktivzeile aendern (Spec-Vorgabe S2a, AC-10)."
        )
