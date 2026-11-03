"""Issue #2681 (A2): ``X-GZ-Lang`` ist Pflicht; Auswahl nach Sprache UND Empfaenger.

Spec: docs/specs/modules/i18n_a2_e2e_zweisprachig_2681.md (AC-2, AC-6)

Kern-Schicht, kein Netz. Die Mails sind die echt gerenderten Fixtures
``tests/fixtures/mail/*.eml`` (Renderer + ``build_mime_message``). Die Validatoren
laufen als echter Prozess (``--eml``) bzw. ihre echten Auswahlfunktionen gegen ein
Postfach mit beiden Mails. Das Postfach ist eine IMAP-Gegenstelle mit genau den
Befehlen, die die Validatoren benutzen (select/search/fetch), Muster des
injizierbaren Transports in ``.claude/tools/staging_befehl_pruefen.py``.
"""
from __future__ import annotations

import email
import importlib.util
import imaplib
import sys
import time
from email import policy
from pathlib import Path

import pytest

from tests.helpers.mail_lang_fixture import lade, mit_kopf, validator_lauf

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_2681", HOOKS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PFADE = _load("_e2e_paths")

# (Validator, deutsche Fixture, englische Fixture)
FAELLE = [
    ("briefing_mail_validator", "briefing_full_de.eml", "briefing_full_en.eml"),
    ("email_spec_validator", "compare_de.eml", "compare_en.eml"),
    ("official_alert_mail_validator", "official_alert_de.eml", "official_alert_mail_en.eml"),
    ("radar_alert_mail_validator", "radar_alert_de.eml", "radar_alert_en.eml"),
]
IDS = [f[0] for f in FAELLE]
BASIS = "gregor-test@henemm.com"
SUB_EN = "gregor-test+en@henemm.com"


def _an(eml: bytes, to: str) -> bytes:
    msg = email.message_from_bytes(eml, policy=policy.compat32)
    msg.replace_header("To", to)
    return msg.as_bytes()


def _kopf(eml: bytes):
    return email.message_from_bytes(eml)


# --------------------------------------------------------------------------- AC-2
@pytest.mark.parametrize("validator,de,en", FAELLE, ids=IDS)
def test_ac2_mit_kopf_besteht_ohne_kopf_scheitert(tmp_path, validator, de, en):
    for fixture in (de, en):
        mit, _ = validator_lauf(tmp_path, validator, lade(fixture))
        assert mit.returncode == 0, f"{fixture}: {mit.stdout}{mit.stderr}"
        ohne, log_dir = validator_lauf(tmp_path, validator, mit_kopf(lade(fixture), None))
        assert ohne.returncode == 1, f"{fixture} ohne Kopf: {ohne.stdout}{ohne.stderr}"
        assert "X-GZ-Lang fehlt" in ohne.stdout + ohne.stderr
        assert "WARNUNG: X-GZ-Lang" not in ohne.stderr, "keine Uebergangs-Warnung mehr"


# --------------------------------------------------------------------------- AC-6 Praedikat
def test_ac6_praedikat_sprache_und_adresse():
    de_basis = _kopf(_an(lade("compare_de.eml"), BASIS))
    en_sub = _kopf(_an(lade("compare_en.eml"), SUB_EN))
    en_basis = _kopf(_an(lade("compare_en.eml"), BASIS))
    de_sub = _kopf(_an(lade("compare_de.eml"), SUB_EN))
    assert PFADE.mail_sprache(en_sub) == "en"
    assert PFADE.mail_sprache(_kopf(mit_kopf(lade("compare_de.eml"), None))) is None
    assert PFADE.mail_passt_zu_sprache(de_basis, "de")
    assert PFADE.mail_passt_zu_sprache(en_sub, "en")
    assert not PFADE.mail_passt_zu_sprache(de_basis, "en")
    assert not PFADE.mail_passt_zu_sprache(en_sub, "de")
    # Gegenprobe: richtiger Kopf, falsche Adresse
    assert not PFADE.mail_passt_zu_sprache(en_basis, "en")
    assert not PFADE.mail_passt_zu_sprache(de_sub, "de")


# --------------------------------------------------------------------------- AC-6 Auswahl
class _Postfach:
    """IMAP-Gegenstelle: Mails in Zustellreihenfolge (aelteste zuerst)."""

    def __init__(self, mails: list[bytes]):
        self.mails = mails

    def select(self, _box="INBOX"):
        return "OK", [str(len(self.mails)).encode()]

    def search(self, _charset, *_kriterien):
        return "OK", [b" ".join(str(i + 1).encode() for i in range(len(self.mails)))]

    def fetch(self, mid, _was):
        nr = int(mid)
        zeit = imaplib.Time2Internaldate(time.time()).encode()
        praefix = b"%d (INTERNALDATE %s BODY[] {%d}" % (nr, zeit, len(self.mails[nr - 1]))
        return "OK", [(praefix, self.mails[nr - 1]), b")"]

    def close(self):
        pass

    def logout(self):
        pass


def _waehle(validator: str, postfach: _Postfach, lang: str, to_contains=None):
    mod = _load(validator)
    if validator == "email_spec_validator":
        return mod._fetch_latest_message(imap=postfach, lang=lang, to_contains=to_contains)
    return mod.fetch_latest_message(lang=lang, to_contains=to_contains, imap=postfach)


@pytest.mark.parametrize("validator,de,en", FAELLE, ids=IDS)
def test_ac6_zwei_nutzer_im_selben_postfach(validator, de, en):
    de_mail, en_mail = _an(lade(de), BASIS), _an(lade(en), SUB_EN)
    for reihenfolge in ([de_mail, en_mail], [en_mail, de_mail]):
        postfach = _Postfach(reihenfolge)
        gewaehlt_de = _waehle(validator, postfach, "de")
        gewaehlt_en = _waehle(validator, postfach, "en")
        assert gewaehlt_de["X-GZ-Lang"] == "de" and gewaehlt_de["To"] == BASIS
        assert gewaehlt_en["X-GZ-Lang"] == "en" and gewaehlt_en["To"] == SUB_EN
    assert _waehle(validator, _Postfach([de_mail, en_mail]), "en", "+en@")["To"] == SUB_EN


@pytest.mark.parametrize("validator,de,en", FAELLE, ids=IDS)
def test_ac6_fremde_mail_erfuellt_den_lauf_nie(validator, de, en):
    # richtige Sprache, aber an die Adresse des anderen Nutzers
    with pytest.raises(ValueError):
        _waehle(validator, _Postfach([_an(lade(en), BASIS)]), "en")
    with pytest.raises(ValueError):
        _waehle(validator, _Postfach([_an(lade(de), SUB_EN)]), "de")
    # Mail des anderen Nutzers (andere Sprache, andere Adresse)
    with pytest.raises(ValueError):
        _waehle(validator, _Postfach([_an(lade(en), SUB_EN)]), "de")
    with pytest.raises(ValueError):
        _waehle(validator, _Postfach([_an(lade(de), BASIS)]), "en")


@pytest.mark.parametrize("validator,de,en", FAELLE, ids=IDS)
def test_ac6_juengste_mail_ohne_kopf_wird_nicht_uebersprungen(validator, de, en):
    """Fail-closed: fehlt der Kopf an der juengsten Mail des Nutzers, prueft der
    Validator GENAU diese (und scheitert an der Pflicht) statt still auf eine
    aeltere Mail mit Kopf auszuweichen."""
    alt = _an(lade(de), BASIS)
    neu = _an(mit_kopf(lade(de), None), BASIS)
    gewaehlt = _waehle(validator, _Postfach([alt, neu]), "de")
    assert gewaehlt["X-GZ-Lang"] is None


@pytest.mark.parametrize("validator,de,en", FAELLE, ids=IDS)
def test_ac6_cli_lang_und_to_contains_im_eml_modus(tmp_path, validator, de, en):
    en_sub = _an(lade(en), SUB_EN)
    gut, _ = validator_lauf(tmp_path, validator, en_sub, "--lang", "en", "--to-contains", "+en@")
    assert gut.returncode == 0, gut.stdout + gut.stderr
    falsche_sprache, _ = validator_lauf(tmp_path, validator, en_sub, "--lang", "de")
    assert falsche_sprache.returncode == 1, falsche_sprache.stdout + falsche_sprache.stderr
    falsche_adresse, _ = validator_lauf(tmp_path, validator, _an(lade(en), BASIS), "--lang", "en")
    assert falsche_adresse.returncode == 1, falsche_adresse.stdout + falsche_adresse.stderr
