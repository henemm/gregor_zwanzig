"""Waechter (#1412 Scheibe S3a): eine SMTP-Verbindung entsteht in `src/` und
`api/` ausschliesslich innerhalb von `EmailOutput._dial_and_send`.

Spec: docs/specs/modules/fix_1412_s3a_transport_kapselung_mail.md (AC-5, AC-6)
Analyse: docs/context/fix-1412-s3-transport-kapselung.md

Heute gibt es VIER Verbindungsstellen (email.py:589 Primaerweg, :638/:682 die
beiden Ersatzwege, core.py:20 der tote, ungeschuetzte Sendeweg) und keine
Methode `_dial_and_send` -- dieser Waechter ist deshalb in der RED-Phase rot
und meldet alle vier namentlich.

Vertrag der Modul-Symbole
-------------------------
`EXPIRY: datetime.date` -- Pruefdatum des Regel-Budgets (CLAUDE.md); das
ISO-Datum steht zusaetzlich als Text in dieser Datei, damit das Gate-Audit es
per grep findet. Vorbild: `EXPIRY` in test_repo_path_hardcoding_ratchet.py:339.

`scan_smtp_verbindungen(basis: Path) -> list[Fund]` durchsucht die
Unterordner `src/` und `api/` unterhalb von `basis` rekursiv nach `*.py` und
meldet jede Codestelle, die eine SMTP-Verbindung AUFBAUT. Erkannt wird per
AST -- nicht per Textsuche -- in jeder Konstruktionsform: `smtplib.SMTP(...)`,
`smtplib.SMTP_SSL(...)`, `smtplib.LMTP(...)`, auch ueber Modul-Alias
(`import smtplib as s` -> `s.SMTP(...)`) und ueber Direktimport
(`from smtplib import SMTP` -> `SMTP(...)`). Alias und Direktimport werden je
Datei aus dem AST aufgeloest, nicht geraten.

NICHT erfasst wird die blosse Erwaehnung von `smtplib`: Ausnahme-Klassen
(`smtplib.SMTPException`, `SMTPAuthenticationError`, `SMTPResponseException`)
bleiben in `send()` und in der Einfassung stehen und sind KEINE Fundstellen.
Ein Waechter, der sie mitzaehlt, waere am ersten Tag rot und wuerde prompt
entschaerft -- genau der Erosionsweg, den S2a beschreibt.

`Fund` traegt `.datei` (Pfad relativ zu `basis`, POSIX), `.zeile`, `.form`
(die im Quelltext benutzte Schreibweise) und `.ort` (umschliessende
Klasse/Funktion, punktverbunden, sonst `<modulebene>`).

`bewerte_funde(funde, ausnahmen, hoechstzahl, heute) -> list[str]` liefert je
Befund eine benannte Meldung; leere Liste = in Ordnung.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

# Wurzel DIESES Checkouts (Worktree) -- bewusst nicht das Hauptrepo: der
# Waechter muss den Baum pruefen, in dem gerade gearbeitet wird (Pfadregel
# #1409, Vorbild test_repo_path_hardcoding_ratchet.py:52).
REPO_ROOT = Path(__file__).resolve().parents[2]

# Regel-Budget (CLAUDE.md): dieser Waechter ersetzt keine bestehende Regel und
# traegt daher ein Pruefdatum von +90 Tagen ab 2026-07-30 -- 2026-10-28.
EXPIRY = date(2026, 10, 28)

SCAN_UNTERORDNER = ("src", "api")

# Die EINE erlaubte Stelle.
ERLAUBTE_DATEI = "src/output/channels/email.py"
ERLAUBTER_ORT = "EmailOutput._dial_and_send"

# S3a braucht null Ausnahmen: nach dem Loeschen von src/app/core.py ist
# email.py die einzige Datei in src/+api/, die ueberhaupt eine SMTP-Verbindung
# aufbaut. Die Mechanik wird trotzdem vollstaendig gebaut und ueber
# Selbstnachweise geprueft, damit S3b den httpx-Teil rein additiv ergaenzen
# kann (dort werden zwei Ausnahmen gebraucht).
AUSNAHMEN_HOECHSTZAHL = 0

# Mindestlaenge einer Ausnahme-Begruendung, gemessen in Buchstaben/Ziffern
# (gleiche Zaehlregel wie _MIN_BEGRUENDUNG in test_mail_recipient_parity.py:55).
_MIN_BEGRUENDUNG = 15
_UNWORT = re.compile(r"[\W_]+")

_VERBINDUNGSKLASSEN = ("SMTP", "SMTP_SSL", "LMTP")
_MODULEBENE = "<modulebene>"


@dataclass(frozen=True)
class Ausnahme:
    """Eine festgenagelte, befristete Verbindungsstelle ausserhalb des
    erlaubten Orts. `fundstelle` ist `<datei>:<zeile>`. Eine Ausnahme, deren
    Fundstelle es nicht mehr gibt, wird ROT mit dem Hinweis "entfernen" --
    sie darf nicht still veralten."""

    fundstelle: str
    grund: str
    frist: date


AUSNAHMEN: list[Ausnahme] = []


@dataclass(frozen=True)
class Fund:
    datei: str
    zeile: int
    form: str
    ort: str

    @property
    def fundstelle(self) -> str:
        return f"{self.datei}:{self.zeile}"

    def __str__(self) -> str:  # pragma: no cover - reine Meldungsform
        return f"{self.fundstelle} ({self.form}(...) in {self.ort})"


# -----------------------------------------------------------------------
# AST-Erkennung
# -----------------------------------------------------------------------


def _importierte_namen(baum: ast.AST) -> tuple[set[str], dict[str, str]]:
    """Loest je Datei auf, unter welchen Namen `smtplib` bzw. seine
    Verbindungsklassen erreichbar sind -- geraten wird nichts."""
    modul_aliase: set[str] = set()
    direktimporte: dict[str, str] = {}
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            for name in knoten.names:
                if name.name == "smtplib":
                    modul_aliase.add(name.asname or name.name)
        elif isinstance(knoten, ast.ImportFrom):
            if knoten.module == "smtplib" and not knoten.level:
                for name in knoten.names:
                    if name.name in _VERBINDUNGSKLASSEN:
                        direktimporte[name.asname or name.name] = name.name
    return modul_aliase, direktimporte


def _verbindungsform(
    funktion: ast.expr, modul_aliase: set[str], direktimporte: dict[str, str]
) -> str | None:
    """Liefert die Schreibweise, wenn `funktion` eine SMTP-Verbindungsklasse
    bezeichnet -- sonst None. `smtplib.SMTPException(...)` oder
    `smtplib.SMTP.connect(...)` sind KEINE Verbindungsaufbauten."""
    if (
        isinstance(funktion, ast.Attribute)
        and isinstance(funktion.value, ast.Name)
        and funktion.value.id in modul_aliase
        and funktion.attr in _VERBINDUNGSKLASSEN
    ):
        return f"{funktion.value.id}.{funktion.attr}"
    if isinstance(funktion, ast.Name) and funktion.id in direktimporte:
        return funktion.id
    return None


def _funde_in_quelltext(quelltext: str, datei: str) -> list[Fund]:
    baum = ast.parse(quelltext, filename=datei)
    modul_aliase, direktimporte = _importierte_namen(baum)
    if not modul_aliase and not direktimporte:
        return []

    funde: list[Fund] = []

    def besuche(knoten: ast.AST, stapel: list[str]) -> None:
        for kind in ast.iter_child_nodes(knoten):
            if isinstance(kind, ast.Call):
                form = _verbindungsform(kind.func, modul_aliase, direktimporte)
                if form:
                    funde.append(
                        Fund(
                            datei=datei,
                            zeile=kind.lineno,
                            form=form,
                            ort=".".join(stapel) or _MODULEBENE,
                        )
                    )
            if isinstance(
                kind, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                besuche(kind, stapel + [kind.name])
            else:
                besuche(kind, stapel)

    besuche(baum, [])
    return funde


def scan_smtp_verbindungen(basis: Path) -> list[Fund]:
    """Alle SMTP-Verbindungsstellen unter `basis/src` und `basis/api`."""
    funde: list[Fund] = []
    for unterordner in SCAN_UNTERORDNER:
        wurzel = basis / unterordner
        if not wurzel.is_dir():
            continue
        for pfad in sorted(wurzel.rglob("*.py")):
            relativ = pfad.relative_to(basis).as_posix()
            funde.extend(
                _funde_in_quelltext(pfad.read_text(encoding="utf-8"), relativ)
            )
    return funde


def ist_erlaubt(fund: Fund) -> bool:
    return fund.datei == ERLAUBTE_DATEI and fund.ort == ERLAUBTER_ORT


# -----------------------------------------------------------------------
# Ausnahmen-Mechanik
# -----------------------------------------------------------------------


def bewerte_funde(
    funde: list[Fund],
    ausnahmen: list[Ausnahme],
    hoechstzahl: int,
    heute: date,
) -> list[str]:
    befunde: list[str] = []
    if len(ausnahmen) > hoechstzahl:
        befunde.append(
            f"{len(ausnahmen)} Ausnahmen ueberschreiten die Hoechstzahl "
            f"{hoechstzahl} -- der Deckel zaehlt ALLE Eintraege, auch "
            "abgelaufene und zu kurz begruendete."
        )

    offen = {f.fundstelle: f for f in funde if not ist_erlaubt(f)}
    gedeckt: set[str] = set()
    for ausnahme in ausnahmen:
        if len(_UNWORT.sub("", ausnahme.grund)) < _MIN_BEGRUENDUNG:
            befunde.append(
                f"{ausnahme.fundstelle}: Begruendung hat weniger als "
                f"{_MIN_BEGRUENDUNG} sinnvolle Zeichen -- zaehlt nicht als "
                "gueltige Ausnahme."
            )
            continue
        if ausnahme.frist < heute:
            befunde.append(
                f"{ausnahme.fundstelle}: Ausnahme ist am "
                f"{ausnahme.frist.isoformat()} abgelaufen -- erneuern oder "
                "entfernen."
            )
            continue
        if ausnahme.fundstelle not in offen:
            befunde.append(
                f"{ausnahme.fundstelle}: Ausnahme deckt keine Verbindungsstelle "
                "mehr -- Divergenz aufgeloest, Ausnahme entfernen."
            )
            continue
        gedeckt.add(ausnahme.fundstelle)

    for fundstelle, fund in sorted(offen.items()):
        if fundstelle not in gedeckt:
            befunde.append(
                f"{fund} -- SMTP-Verbindung ausserhalb von {ERLAUBTER_ORT} "
                "ohne gueltige Ausnahme."
            )
    return befunde


# -----------------------------------------------------------------------
# Attrappen (echte Dateien auf der Platte, kein Mock)
# -----------------------------------------------------------------------


def _attrappe(basis: Path, relativer_pfad: str, quelltext: str) -> Path:
    ziel = basis / relativer_pfad
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(quelltext, encoding="utf-8")
    return ziel


_ERLAUBTE_ATTRAPPE = '''\
import smtplib


class EmailOutput:
    def _dial_and_send(self, host, port, user, password, recipients, msg,
                       from_addr, isolate_per_recipient):
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            try:
                server.sendmail(from_addr, recipients, msg)
            except smtplib.SMTPException as exc:
                raise smtplib.SMTPException(str(exc))

    def send(self, subject, body):
        try:
            self._dial_and_send("h", 587, "u", "p", [], body, "f", True)
        except smtplib.SMTPAuthenticationError as e:
            raise RuntimeError(str(e))
        except smtplib.SMTPResponseException as e:
            raise RuntimeError(str(e))
'''

_VIERTE_STELLE = '''\
import smtplib


def melde_per_mail(host, port, empfaenger, text):
    with smtplib.SMTP(host, port) as server:
        server.sendmail("gregor_zwanzig@henemm.com", [empfaenger], text)
'''

_ALIAS_FORM = '''\
import smtplib as s


def dial_ueber_alias(host, port):
    return s.SMTP(host, port)
'''

_DIREKTIMPORT_FORM = '''\
from smtplib import SMTP


def dial_ueber_direktimport(host, port):
    return SMTP(host, port)
'''

_SSL_FORM = '''\
import smtplib


class Versender:
    def zustellen(self, host):
        return smtplib.SMTP_SSL(host, 465)
'''

_NUR_AUSNAHMEN = '''\
import smtplib


def bewerte(fehler):
    if isinstance(fehler, smtplib.SMTPResponseException):
        raise smtplib.SMTPException("weitergereicht")
    if isinstance(fehler, smtplib.SMTPAuthenticationError):
        return "auth"
    return smtplib.SMTP.connect.__name__
'''


# -----------------------------------------------------------------------
# AC-5: der ausgelieferte Stand
# -----------------------------------------------------------------------


def test_ac5_genau_eine_verbindungsstelle_im_ausgelieferten_stand():
    """AC-5: `src/` + `api/` bauen eine SMTP-Verbindung nur noch in
    `EmailOutput._dial_and_send` auf.

    RED-Erwartung: heute meldet der Waechter VIER Stellen namentlich --
    email.py:589 (Primaerweg), :638 und :682 (Ersatzwege) sowie
    src/app/core.py:20 (toter, ungeschuetzter Sendeweg)."""
    funde = scan_smtp_verbindungen(REPO_ROOT)
    befunde = bewerte_funde(funde, AUSNAHMEN, AUSNAHMEN_HOECHSTZAHL, date.today())
    assert not befunde, "SMTP-Verbindungen ausserhalb des einen Ausgangs:\n" + "\n".join(
        befunde
    )


def test_ac5_der_eine_erlaubte_ausgang_existiert_wirklich():
    """Gegenprobe zum Waechter selbst: "keine unerlaubte Stelle" waere auch
    dann gruen, wenn es UEBERHAUPT keine Verbindungsstelle mehr gaebe (z.B.
    weil der Scanner nichts mehr erkennt). Es muss genau eine geben, und zwar
    die erlaubte."""
    erlaubte = [f for f in scan_smtp_verbindungen(REPO_ROOT) if ist_erlaubt(f)]
    assert len(erlaubte) == 1, (
        f"erwartet genau eine Verbindungsstelle in {ERLAUBTE_DATEI} / "
        f"{ERLAUBTER_ORT}, gefunden: {[str(f) for f in erlaubte]}"
    )


def test_ausnahmenliste_ist_im_ausgelieferten_stand_leer():
    """S3a braucht null Ausnahmen (Spec, AC-5)."""
    assert AUSNAHMEN_HOECHSTZAHL == 0
    assert AUSNAHMEN == []


# -----------------------------------------------------------------------
# AC-6: Selbstnachweise gegen Attrappen
# -----------------------------------------------------------------------


def test_ac6_verbindung_ausserhalb_des_erlaubten_orts_wird_namentlich_gemeldet(
    tmp_path,
):
    """AC-6 (a): eine kuenstlich eingefuegte Verbindungsstelle wird gefunden
    UND in der Meldung mit Datei, Zeile und Ort benannt -- das Werkzeug
    beweist, dass es etwas faengt."""
    _attrappe(tmp_path, ERLAUBTE_DATEI, _ERLAUBTE_ATTRAPPE)
    datei = _attrappe(tmp_path, "src/services/eigenmaechtig.py", _VIERTE_STELLE)
    zeile = [
        n
        for n, z in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1)
        if "smtplib.SMTP(" in z
    ][0]

    funde = scan_smtp_verbindungen(tmp_path)
    unerlaubt = [f for f in funde if not ist_erlaubt(f)]
    assert len(unerlaubt) == 1, f"erwartet 1 unerlaubte Stelle: {[str(f) for f in funde]}"
    assert unerlaubt[0].datei == "src/services/eigenmaechtig.py"
    assert unerlaubt[0].zeile == zeile
    assert unerlaubt[0].ort == "melde_per_mail"

    befunde = bewerte_funde(funde, [], AUSNAHMEN_HOECHSTZAHL, date.today())
    assert len(befunde) == 1
    assert "src/services/eigenmaechtig.py:%d" % zeile in befunde[0]
    assert "melde_per_mail" in befunde[0]


def test_ac6_erlaubte_stelle_in_der_attrappe_wird_nicht_gemeldet(tmp_path):
    """Gegenprobe: die Stelle IN `_dial_and_send` ist erlaubt -- der Waechter
    meldet nicht einfach alles."""
    _attrappe(tmp_path, ERLAUBTE_DATEI, _ERLAUBTE_ATTRAPPE)
    funde = scan_smtp_verbindungen(tmp_path)
    assert len(funde) == 1 and ist_erlaubt(funde[0]), [str(f) for f in funde]
    assert not bewerte_funde(funde, [], AUSNAHMEN_HOECHSTZAHL, date.today())


@pytest.mark.parametrize(
    "name, quelltext, erwartete_form, erwarteter_ort",
    [
        ("alias", _ALIAS_FORM, "s.SMTP", "dial_ueber_alias"),
        ("direktimport", _DIREKTIMPORT_FORM, "SMTP", "dial_ueber_direktimport"),
        ("ssl", _SSL_FORM, "smtplib.SMTP_SSL", "Versender.zustellen"),
    ],
)
def test_ac6_umgehungsformen_werden_erkannt(
    tmp_path, name, quelltext, erwartete_form, erwarteter_ort
):
    """AC-6 (b): Modul-Alias, Direktimport und SMTP_SSL -- eine reine
    Textsuche nach `smtplib.SMTP(` ist in einer Zeile umgangen."""
    _attrappe(tmp_path, f"src/services/{name}.py", quelltext)
    funde = scan_smtp_verbindungen(tmp_path)
    assert len(funde) == 1, f"{name}: {[str(f) for f in funde]}"
    assert funde[0].form == erwartete_form
    assert funde[0].ort == erwarteter_ort


def test_ac6_ausnahme_klassen_sind_keine_fundstellen(tmp_path):
    """AC-6 (c): `smtplib.SMTPException` & Co. bleiben in `send()` und in der
    Einfassung stehen. Ein Waechter, der sie mitzaehlt, waere am ersten Tag rot
    und wuerde prompt entschaerft."""
    _attrappe(tmp_path, "src/services/nur_ausnahmen.py", _NUR_AUSNAHMEN)
    assert not scan_smtp_verbindungen(tmp_path)


def test_ac6_zu_viele_ausnahmen_werden_rot(tmp_path):
    """AC-6 (d): mehr Ausnahmen als die Hoechstzahl reissen den Deckel --
    unabhaengig davon, ob die einzelne Ausnahme inhaltlich gedeckt waere."""
    datei = _attrappe(tmp_path, "src/services/eigenmaechtig.py", _VIERTE_STELLE)
    funde = scan_smtp_verbindungen(tmp_path)
    stelle = funde[0].fundstelle
    ausnahme = Ausnahme(
        fundstelle=stelle,
        grund="localhost-Zustellung ohne Endnutzer-Empfaenger, prozessintern",
        frist=date(2026, 10, 28),
    )
    assert datei.exists()

    assert not bewerte_funde(funde, [ausnahme], 1, date(2026, 8, 1)), (
        "eine gueltige, gedeckte Ausnahme unter dem Deckel darf nicht rot sein"
    )
    befunde = bewerte_funde(funde, [ausnahme], 0, date(2026, 8, 1))
    assert befunde and any("Hoechstzahl" in b for b in befunde), befunde


def test_ac6_abgelaufene_frist_wird_rot(tmp_path):
    """AC-6 (e): eine abgelaufene Ausnahme deckt nichts mehr."""
    _attrappe(tmp_path, "src/services/eigenmaechtig.py", _VIERTE_STELLE)
    funde = scan_smtp_verbindungen(tmp_path)
    ausnahme = Ausnahme(
        fundstelle=funde[0].fundstelle,
        grund="localhost-Zustellung ohne Endnutzer-Empfaenger, prozessintern",
        frist=date(2026, 8, 1),
    )
    befunde = bewerte_funde(funde, [ausnahme], 1, date(2026, 8, 2))
    assert any("abgelaufen" in b for b in befunde), befunde
    assert any("ohne gueltige Ausnahme" in b for b in befunde), befunde


def test_ac6_zu_kurze_begruendung_zaehlt_nicht(tmp_path):
    _attrappe(tmp_path, "src/services/eigenmaechtig.py", _VIERTE_STELLE)
    funde = scan_smtp_verbindungen(tmp_path)
    ausnahme = Ausnahme(fundstelle=funde[0].fundstelle, grund="egal", frist=date(2026, 10, 28))
    befunde = bewerte_funde(funde, [ausnahme], 1, date(2026, 8, 1))
    assert any("sinnvolle Zeichen" in b for b in befunde), befunde
    assert any("ohne gueltige Ausnahme" in b for b in befunde), befunde


def test_ac6_aufgeloeste_ausnahme_muss_entfernt_werden(tmp_path):
    """Eine Ausnahme, deren Verbindungsstelle es nicht mehr gibt, wird ROT mit
    dem Hinweis "entfernen" -- sie darf nicht still veralten."""
    _attrappe(tmp_path, ERLAUBTE_DATEI, _ERLAUBTE_ATTRAPPE)
    ausnahme = Ausnahme(
        fundstelle="src/services/eigenmaechtig.py:5",
        grund="localhost-Zustellung ohne Endnutzer-Empfaenger, prozessintern",
        frist=date(2026, 10, 28),
    )
    befunde = bewerte_funde(
        scan_smtp_verbindungen(tmp_path), [ausnahme], 1, date(2026, 8, 1)
    )
    assert any("entfernen" in b for b in befunde), befunde


def test_ac6_pruefdatum_ist_maschinell_auffindbar():
    """AC-6 (f): Regel-Budget -- das Pruefdatum steht als Text in der Datei,
    damit das Gate-Audit es per grep findet."""
    assert EXPIRY == date(2026, 10, 28), "+90 Tage ab 2026-07-30"
    zeilen = Path(__file__).read_text(encoding="utf-8").splitlines()
    assert [n for n, z in enumerate(zeilen, 1) if EXPIRY.isoformat() in z]


def test_ac6_repo_wurzel_ist_der_eigene_baum():
    """AC-6 (g): der Waechter misst den Baum, in dem er selbst liegt -- nicht
    eine fremde Checkout-Kopie (Pfadregel #1409). Nachweis ueber die Identitaet
    der Datei, nicht ueber einen Pfad-Vergleich gegen ein festes Verzeichnis."""
    eigen = Path(__file__).resolve()
    assert eigen.is_relative_to(REPO_ROOT)
    ueber_wurzel = REPO_ROOT / "tests" / "tdd" / eigen.name
    assert ueber_wurzel.exists(), f"{ueber_wurzel} fehlt -- falsche Repo-Wurzel"
    assert ueber_wurzel.stat().st_ino == eigen.stat().st_ino, (
        "Die ueber REPO_ROOT aufgeloeste Kopie dieser Datei ist eine ANDERE "
        "Datei -- der Waechter pruefte einen fremden Checkout und meldete "
        "falsches Gruen."
    )
    assert (REPO_ROOT / ERLAUBTE_DATEI).exists()
