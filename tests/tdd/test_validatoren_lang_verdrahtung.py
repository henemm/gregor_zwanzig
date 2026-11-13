"""Issue #2681 (A2): die Sprachauswahl wirkt dort, wo der Nutzer sie erreicht.

Spec: docs/specs/modules/i18n_a2_e2e_zweisprachig_2681.md (AC-1, AC-6, AC-8)
Adversary-Bericht: docs/artifacts/i18n-a2-e2e-2681/adversary-report.md (F001-F003)

Kern-Schicht, kein Netz. Statt der Pruef- bzw. Auswahlfunktion mit direkt
uebergebenem ``lang`` laeuft hier der Weg des Nutzers:

- F001: ``main()`` jedes der vier Validatoren mit ``--lang en --to-contains
  "+en@"``. Das Postfach ist eine IMAP-Gegenstelle (select/search/fetch, wie in
  ``test_validatoren_lang_pflicht.py``), die an die Stelle des Netz-Transports
  ``imaplib.IMAP4_SSL`` tritt; Settings, Anmeldung, Auswahl, Pruefung und
  Exit-Code sind echt. Die Gegenstelle merkt sich, welche Mail voll geholt
  wurde -- das ist die Mail, die der Validator geprueft hat.
- F002: Gegenproben richtige Adresse, falscher ``X-GZ-Lang``.
- F003: ``run_email_test`` (``e2e_browser_test.py email --lang``) mit einem
  Postfach aus zwei Mails.

Die Validatoren werden aus einer Kopie der Hooks in einem eigenen Git-Repo
geladen (Muster ``tests/helpers/mail_lang_fixture.validator_lauf``), damit ihr
YAML-Log in ``tmp_path`` landet und nie als Nachweis im echten Repo zaehlt.
"""
from __future__ import annotations

import email
import importlib.util
import imaplib
import shutil
import subprocess
import sys
import time
import types
from email import policy
from pathlib import Path

import pytest

from tests.helpers.mail_lang_fixture import lade

REPO = Path(__file__).resolve().parents[2]
HOOKS = REPO / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

FAELLE = [
    ("briefing_mail_validator", "briefing_full_de.eml", "briefing_full_en.eml"),
    ("email_spec_validator", "compare_de.eml", "compare_en.eml"),
    ("official_alert_mail_validator", "official_alert_de.eml", "official_alert_mail_en.eml"),
    ("radar_alert_mail_validator", "radar_alert_de.eml", "radar_alert_en.eml"),
]
IDS = [f[0] for f in FAELLE]
BASIS = "gregor-test@henemm.com"
SUB_EN = "gregor-test+en@henemm.com"
FREMD_EN = "anderer-test+en@henemm.com"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PFADE = _load(HOOKS / "_e2e_paths.py", "_e2e_paths_verdrahtung_2681")


def _an(eml: bytes, to: str) -> bytes:
    msg = email.message_from_bytes(eml, policy=policy.compat32)
    msg.replace_header("To", to)
    return msg.as_bytes()


def _sprache(eml: bytes, lang: str) -> bytes:
    msg = email.message_from_bytes(eml, policy=policy.compat32)
    msg.replace_header("X-GZ-Lang", lang)
    return msg.as_bytes()


def _kopf(eml: bytes):
    return email.message_from_bytes(eml)


# --------------------------------------------------------------------------- Gegenstelle
class _Postfach:
    """IMAP-Gegenstelle: Mails in Zustellreihenfolge (aelteste zuerst).

    ``voll_geholt`` sammelt die Nummern der Mails, deren ganzer Inhalt (nicht
    nur der Kopf) abgeholt wurde."""

    def __init__(self, mails: list[bytes]):
        self.mails = mails
        self.voll_geholt: list[int] = []
        self.angemeldet = False

    # Konstruktor-Ersatz fuer imaplib.IMAP4_SSL(host, port)
    def verbindung(self, *_args, **_kwargs):
        return self

    def login(self, _user, _pass):
        self.angemeldet = True
        return "OK", [b"LOGIN completed"]

    def select(self, _box="INBOX"):
        return "OK", [str(len(self.mails)).encode()]

    def search(self, _charset, *_kriterien):
        return "OK", [b" ".join(str(i + 1).encode() for i in range(len(self.mails)))]

    def fetch(self, mid, was):
        nr = int(mid)
        if "HEADER" not in str(was):
            self.voll_geholt.append(nr)
        zeit = imaplib.Time2Internaldate(time.time()).encode()
        praefix = b"%d (INTERNALDATE %s BODY[] {%d}" % (nr, zeit, len(self.mails[nr - 1]))
        return "OK", [(praefix, self.mails[nr - 1]), b")"]

    def close(self):
        pass

    def logout(self):
        pass


@pytest.fixture
def hooks_kopie(tmp_path, monkeypatch):
    """Hooks-Kopie in eigenem Git-Repo; Test-Postfach-Zugang per Umgebung."""
    kopie = tmp_path / "repo"
    (kopie / ".claude").mkdir(parents=True)
    shutil.copytree(HOOKS, kopie / ".claude" / "hooks",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (kopie / "src").symlink_to(REPO / "src")
    subprocess.run(["git", "init", "-q", str(kopie)], check=True)
    monkeypatch.setenv("GZ_TEST_IMAP_USER", "gregor-test")
    monkeypatch.setenv("GZ_TEST_IMAP_PASS", "kein-echtes-passwort")
    # #2961: der Validator nimmt nur Mails des konfigurierten Dienst-Absenders;
    # die Golden-Fixtures tragen diesen Absender.
    monkeypatch.setenv("GZ_MAIL_FROM", "gregor_zwanzig@henemm.com")
    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "test-2681-verdrahtung")
    return kopie


def _main_lauf(kopie: Path, validator: str, postfach: _Postfach, monkeypatch, *args: str) -> int:
    """Ruft ``main()`` des Validators aus der Hooks-Kopie wie von der
    Kommandozeile; das Postfach ersetzt nur den Netz-Transport."""
    mod = _load(kopie / ".claude" / "hooks" / f"{validator}.py", f"{validator}_verdrahtung_2681")
    monkeypatch.setattr(imaplib, "IMAP4_SSL", postfach.verbindung)
    monkeypatch.setattr(sys, "argv", [f"{validator}.py", *args])
    with pytest.raises(SystemExit) as ende:
        mod.main()
    log_dir = kopie / ".claude" / "workflows" / "_log"
    assert log_dir.is_dir() and any(log_dir.iterdir()), "Validator-Log muss in der Kopie landen"
    return ende.value.code


# --------------------------------------------------------------------------- F001
@pytest.mark.parametrize("validator,de,en", FAELLE, ids=IDS)
def test_f001_main_mit_lang_en_prueft_die_englische_mail(hooks_kopie, monkeypatch, validator, de, en):
    """AC-1/AC-6: ``--lang en --to-contains +en@`` waehlt die englische Mail
    des Nutzers en, egal ob sie aelter oder juenger als die deutsche ist."""
    de_mail, en_mail = _an(lade(de), BASIS), _an(lade(en), SUB_EN)
    for mails, en_nr in (([de_mail, en_mail], 2), ([en_mail, de_mail], 1)):
        postfach = _Postfach(mails)
        code = _main_lauf(hooks_kopie, validator, postfach, monkeypatch,
                          "--lang", "en", "--to-contains", "+en@")
        assert code == 0, f"Exit {code}"
        assert postfach.angemeldet
        assert postfach.voll_geholt == [en_nr], postfach.voll_geholt


@pytest.mark.parametrize("validator,de,en", FAELLE, ids=IDS)
def test_f001_main_mit_lang_de_prueft_die_deutsche_mail(hooks_kopie, monkeypatch, validator, de, en):
    """Gegenstueck: ``--lang de`` waehlt die deutsche Mail, auch wenn die
    englische juenger ist."""
    postfach = _Postfach([_an(lade(de), BASIS), _an(lade(en), SUB_EN)])
    code = _main_lauf(hooks_kopie, validator, postfach, monkeypatch, "--lang", "de")
    assert code == 0, f"Exit {code}"
    assert postfach.voll_geholt == [1], postfach.voll_geholt


@pytest.mark.parametrize("validator,de,en", FAELLE, ids=IDS)
def test_f001_main_reicht_to_contains_an_die_auswahl(hooks_kopie, monkeypatch, validator, de, en):
    """``--to-contains`` schraenkt die Auswahl im IMAP-Lauf ein: eine juengere
    englische Mail an eine andere ``+en``-Adresse wird nicht gewaehlt."""
    postfach = _Postfach([_an(lade(en), SUB_EN), _an(lade(en), FREMD_EN)])
    code = _main_lauf(hooks_kopie, validator, postfach, monkeypatch,
                      "--lang", "en", "--to-contains", "gregor-test+en@")
    assert code == 0, f"Exit {code}"
    assert postfach.voll_geholt == [1], postfach.voll_geholt


# --------------------------------------------------------------------------- F002
def test_f002_praedikat_richtige_adresse_falsche_sprache():
    de_an_sub = _kopf(_an(lade("compare_de.eml"), SUB_EN))
    en_an_basis = _kopf(_an(lade("compare_en.eml"), BASIS))
    # Adresse passt zur Sprache des Laufs, der Kopf nicht
    assert not PFADE.mail_passt_zu_sprache(de_an_sub, "en")
    assert not PFADE.mail_passt_zu_sprache(en_an_basis, "de")
    assert not PFADE.mail_waehlbar(de_an_sub, "en", "+en@")
    assert not PFADE.mail_waehlbar(en_an_basis, "de")


def _waehle(validator: str, postfach: _Postfach, lang: str, to_contains=None):
    mod = _load(HOOKS / f"{validator}.py", f"{validator}_auswahl_2681")
    if validator == "email_spec_validator":
        return mod._fetch_latest_message(imap=postfach, lang=lang, to_contains=to_contains)
    return mod.fetch_latest_message(lang=lang, to_contains=to_contains, imap=postfach)


@pytest.mark.parametrize("validator,de,en", FAELLE, ids=IDS)
def test_f002_auswahl_richtige_adresse_falsche_sprache(validator, de, en):
    """AC-6: eine Mail der anderen Sprache erfuellt den Lauf nie -- auch nicht,
    wenn sie an der Adresse des Nutzers liegt."""
    with pytest.raises(ValueError):
        _waehle(validator, _Postfach([_an(lade(de), SUB_EN)]), "en")
    with pytest.raises(ValueError):
        _waehle(validator, _Postfach([_an(lade(en), BASIS)]), "de")
    # neben der passenden Mail: die falsch beschriftete juengere wird uebersprungen
    falsch = _an(_sprache(lade(en), "de"), SUB_EN)
    gewaehlt = _waehle(validator, _Postfach([_an(lade(en), SUB_EN), falsch]), "en", "+en@")
    assert gewaehlt["X-GZ-Lang"] == "en"


# --------------------------------------------------------------------------- F003
BROWSER = _load(HOOKS / "e2e_browser_test.py", "e2e_browser_verdrahtung_2681")


@pytest.fixture
def browser_ohne_warten(monkeypatch):
    monkeypatch.setenv("GZ_TEST_IMAP_USER", "gregor-test")
    monkeypatch.setenv("GZ_TEST_IMAP_PASS", "kein-echtes-passwort")
    # Nur das Warten auf die Zustellung entfaellt; sonst nichts.
    monkeypatch.setattr(BROWSER, "time", types.SimpleNamespace(sleep=lambda _s: None))
    return BROWSER


@pytest.mark.parametrize("lang,erwartet", [("en", 1), ("de", 1)])
def test_f003_run_email_test_filtert_nach_sprache(browser_ohne_warten, monkeypatch, lang, erwartet):
    """AC-8: ``e2e_browser_test.py email --lang`` prueft die neueste Mail
    DIESES Nutzers, nicht die neueste Mail im Postfach."""
    de_mail = _an(lade("compare_de.eml"), BASIS)
    en_mail = _an(lade("compare_en.eml"), SUB_EN)
    # die gesuchte Mail liegt jeweils UNTER der des anderen Nutzers
    mails = [en_mail, de_mail] if lang == "en" else [de_mail, en_mail]
    postfach = _Postfach(mails)
    monkeypatch.setattr(imaplib, "IMAP4_SSL", postfach.verbindung)
    ok, meldung = browser_ohne_warten.run_email_test("", lang=lang)
    assert ok, meldung
    assert postfach.voll_geholt[-1] == erwartet, postfach.voll_geholt


def test_f003_run_email_test_ohne_passende_mail_scheitert(browser_ohne_warten, monkeypatch):
    postfach = _Postfach([_an(lade("compare_de.eml"), BASIS),
                          _an(lade("compare_de.eml"), SUB_EN)])
    monkeypatch.setattr(imaplib, "IMAP4_SSL", postfach.verbindung)
    ok, meldung = browser_ohne_warten.run_email_test("", lang="en")
    assert not ok
    assert "X-GZ-Lang: en" in meldung


# --------------------------------------------------------------------------- F007/F008
def _zwei_passende_und_eine_fremde(lang: str) -> list[bytes]:
    """Zwei Mails desselben Nutzers in derselben Sprache (1 = aelter, 2 =
    juenger), darueber die juengste Mail des anderen Nutzers (3)."""
    if lang == "en":
        eigene, fremde = _an(lade("compare_en.eml"), SUB_EN), _an(lade("compare_de.eml"), BASIS)
    else:
        eigene, fremde = _an(lade("compare_de.eml"), BASIS), _an(lade("compare_en.eml"), SUB_EN)
    return [eigene, eigene, fremde]


@pytest.mark.parametrize("lang", ["en", "de"])
def test_f007_run_email_test_waehlt_die_juengere_von_zwei_passenden(browser_ohne_warten, monkeypatch, lang):
    """Runde 2 F007: bei zwei passenden Mails prueft ``run_email_test`` die
    juengere, nicht die erste im Postfach."""
    postfach = _Postfach(_zwei_passende_und_eine_fremde(lang))
    monkeypatch.setattr(imaplib, "IMAP4_SSL", postfach.verbindung)
    ok, meldung = browser_ohne_warten.run_email_test("", lang=lang)
    assert ok, meldung
    assert postfach.voll_geholt[-1] == 2, postfach.voll_geholt


@pytest.mark.parametrize("lang", ["en", "de"])
def test_f008_compare_auswahl_waehlt_die_juengere_von_zwei_passenden(lang):
    """Runde 2 F008: die Kandidatenschleife in ``_fetch_latest_message`` des
    Orts-Vergleich-Validators waehlt die juengere von zwei passenden Mails."""
    postfach = _Postfach(_zwei_passende_und_eine_fremde(lang))
    gewaehlt = _waehle("email_spec_validator", postfach, lang)
    assert gewaehlt["X-GZ-Lang"] == lang
    assert postfach.voll_geholt == [2], postfach.voll_geholt
