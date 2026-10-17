"""Nutzer-Testmail an die bestaetigte Profiladresse (Onboarding S2, AC-8/9/10).

Spec: docs/specs/modules/onboarding_willkommen_checkliste.md (AC-8, AC-9, AC-10)
ADR-0092 (loest die #198-Regel "Testmail nie ueber den echten Postausgang"
fuer echte Nutzer ab).

Nachweisform wie ``test_telegram_inbound_reply_contract.py`` (AC-11-E-Mail-
Zweig): ``smtplib.SMTP`` ist durch einen echten Aufzeichner ersetzt (kein
``Mock()``/``patch()``), der Verbindungshost, Login-Nutzer, Absender und
Empfaenger festhaelt. Die Entscheidung, WOHIN gewaehlt wird, faellt
vollstaendig im Produktivcode (``send_test_message`` -> ``Settings`` ->
``EmailOutput``).

Warum der Produktions-Host hier KEIN "resend" enthaelt: der Resend-Default-
Deny (#1122, ``config.py::_resend_default_deny``) lenkt in jedem pytest-Lauf
einen Resend-Host auf ``test_smtp_host`` um -- es gibt bewusst keinen
Testlauf-Bypass. Mit einem Resend-Host waeren normale Versandkette und
``for_testing()`` am Draht ununterscheidbar. Ein lokal zustellbarer
Produktions-Host trennt beide sauber; dafuer greift auf diesem Weg der
Lokal-Guard (#1235), weshalb alle Adressen, die zugestellt werden SOLLEN,
``@henemm.com`` sind. Der Resend-Allowlist-Zweig selbst ist unter pytest
nicht beobachtbar -- er wird auf Staging (Wegwerf-Nutzer, IMAP) belegt.

Zweiter, unabhaengiger Unterscheider: ``for_testing()`` tauscht bei gesetzten
Test-Zugangsdaten auch Login-Nutzer und Absender aus (``gregor-test``); die
normale Kette meldet sich mit ``GZ_SMTP_USER`` an.

``GZ_MAIL_TO`` ist eine lokal zustellbare Betreiber-Adresse: nur so geht die
Mail heute in den Sperrfaellen tatsaechlich an den Betreiber (Aufzeichnung
nicht leer). Ohne globale Adresse endete der Versand schon heute in
"kein Empfaenger" und die Sperrtests waeren aus dem falschen Grund gruen.

Nutzerkennungen ohne "test"/"tdd"; Testnutzer werden ueber das Profilfeld
``is_test_user`` markiert (``is_test_user_id``, #2152).
"""
from __future__ import annotations

import json

import pytest

from app.config import Settings
from app.loader import get_data_dir

PROD_SMTP_HOST = "versandkette-pruefung.henemm.com"
PROD_SMTP_USER = "versandkette"
TEST_SMTP_HOST = "stalwart-pruefung.henemm.com"
TEST_SMTP_USER = "gregor-test"
BETREIBER = "betreiber-rueckfall@henemm.com"

#: Interne Bezeichner, die in einer Fehlermeldung an den Nutzer nichts zu
#: suchen haben (Textvertrag AC-10: "klarer deutscher Fehlertext").
_TECHNISCHE_BEZEICHNER = (
    "invalid", "user_id", "mail_to", "settings", "email_verified_at",
    "Error", "Exception", "Issue #", "None",
)


class _SmtpMitschrift:
    """Was am SMTP-Rand tatsaechlich passiert waere."""

    def __init__(self) -> None:
        self.verbindungen: list[str] = []
        self.logins: list[str] = []
        self.sendungen: list[dict] = []

    @property
    def empfaenger(self) -> list[str]:
        return [a for s in self.sendungen for a in s["to"]]

    def __repr__(self) -> str:
        return (
            f"SmtpMitschrift(verbindungen={self.verbindungen!r}, "
            f"logins={self.logins!r}, sendungen={self.sendungen!r})"
        )


@pytest.fixture
def smtp(monkeypatch) -> _SmtpMitschrift:
    """Hermetische, produktionsnahe Umgebung plus Aufzeichner am SMTP-Rand.

    ``Settings()`` wird in ``channel_test_service`` intern gebaut, daher per
    ``GZ_``-Umgebung; die Projekt-``.env`` ist abgeschaltet.
    """
    from output.channels import email as email_mod

    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for key in ("GZ_IS_TEST_MODE", "GZ_RESEND_ALLOWED", "GZ_TEST_MAIL_FROM"):
        monkeypatch.delenv(key, raising=False)
    for key, wert in {
        "GZ_ENV": "production",
        "GZ_IS_TEST_MODE": "false",
        "GZ_SMTP_HOST": PROD_SMTP_HOST,
        "GZ_SMTP_USER": PROD_SMTP_USER,
        "GZ_SMTP_PASS": "kein-echtes-passwort",
        "GZ_MAIL_FROM": "gregor_zwanzig@henemm.com",
        "GZ_MAIL_TO": BETREIBER,
        "GZ_TEST_SMTP_HOST": TEST_SMTP_HOST,
        "GZ_TEST_SMTP_USER": TEST_SMTP_USER,
        "GZ_TEST_SMTP_PASS": "kein-echtes-passwort",
    }.items():
        monkeypatch.setenv(key, wert)

    mit = _SmtpMitschrift()

    class _SmtpAufzeichner:
        def __init__(self, host, port, timeout=None):
            mit.verbindungen.append(host)

            class _Sock:
                def settimeout(self, t):
                    pass

            self.sock = _Sock()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            pass

        def login(self, user, password):
            mit.logins.append(user)

        def sendmail(self, from_addr, to_addrs, msg):
            mit.sendungen.append({"from": from_addr, "to": list(to_addrs)})

    monkeypatch.setattr(email_mod.smtplib, "SMTP", _SmtpAufzeichner)
    # Herkunftssperre (#1476) aus: sonst wuerde jeder Empfaenger auf
    # gregor-test@henemm.com umgeschrieben und "nur an A" waere wertlos.
    monkeypatch.setattr(email_mod, "running_origin", lambda module_file: "production")
    return mit


def _profil(user_id: str, **felder) -> None:
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({"id": user_id, **felder}))


def _bestaetigt(user_id: str, adresse: str, **weitere) -> None:
    _profil(
        user_id, email=adresse, mail_to=adresse,
        email_verified_at="2026-10-01T08:00:00Z", **weitere,
    )


def _klarer_deutscher_fehlertext(ergebnis: dict) -> None:
    assert "status" not in ergebnis and isinstance(ergebnis.get("error"), str), (
        f"AC-10: erwartet {{'error': <Text>}} ohne status, gesehen {ergebnis!r}"
    )
    text = ergebnis["error"]
    assert len(text.strip()) >= 10, f"AC-10: Fehlertext zu knapp: {text!r}"
    assert "E-Mail" in text or "Adresse" in text, (
        f"AC-10: der Nutzer muss erfahren, dass es um seine E-Mail-Adresse geht: {text!r}"
    )
    treffer = [b for b in _TECHNISCHE_BEZEICHNER if b in text]
    assert not treffer, f"AC-10: technische Bezeichner im Nutzertext {treffer}: {text!r}"


# ═══════════════════════════ AC-8 ════════════════════════════════════════════


def test_echter_nutzer_bekommt_testmail_ueber_die_normale_versandkette(smtp):
    """AC-8.

    GIVEN ein echter Nutzer (kein Testkonto) mit bestaetigter Adresse und
          ohne einen einzigen Trip.
    WHEN  er "Testmail senden" drueckt.
    THEN  Erfolg; genau EINE Verbindung zum Produktions-Postausgang (nicht zum
          Test-Postausgang), angemeldet als Produktions-Nutzer, Empfaenger ist
          genau seine bestaetigte Profiladresse.

    RED heute: ``.for_testing()`` (#198) lenkt Host und Login auf Stalwart.
    """
    from services.channel_test_service import send_test_message

    _bestaetigt("nutzer-a-onboarding", "nutzer-a-onboarding@henemm.com")

    ergebnis = send_test_message("email", "nutzer-a-onboarding")

    assert ergebnis == {"status": "ok"}, f"AC-8: gesehen {ergebnis!r} ({smtp!r})"
    assert smtp.verbindungen == [PROD_SMTP_HOST], (
        f"AC-8: die Testmail eines echten Nutzers muss ueber die normale "
        f"Versandkette gehen, nicht ueber test_smtp_host: {smtp!r}"
    )
    assert smtp.logins == [PROD_SMTP_USER], f"AC-8: Login {smtp!r}"
    assert smtp.empfaenger == ["nutzer-a-onboarding@henemm.com"], f"AC-8: {smtp!r}"


def test_testnutzer_bekommt_testmail_weiter_ueber_den_test_postausgang(smtp):
    """AC-8 (Testnutzer) -- Waechter, heute GRUEN.

    GIVEN ein Testkonto (``is_test_user: true``) mit bestaetigter Adresse.
    WHEN  "Testmail senden".
    THEN  die Verbindung geht weiter an Stalwart (``force_test``), nie an den
          Produktions-Postausgang.
    """
    from services.channel_test_service import send_test_message

    _bestaetigt("wegwerf-onboarding", "gregor-test+onboarding@henemm.com", is_test_user=True)

    ergebnis = send_test_message("email", "wegwerf-onboarding")

    assert ergebnis == {"status": "ok"}, f"AC-8: gesehen {ergebnis!r} ({smtp!r})"
    assert smtp.verbindungen == [TEST_SMTP_HOST], f"AC-8: Testnutzer {smtp!r}"
    assert smtp.logins == [TEST_SMTP_USER], f"AC-8: Testnutzer {smtp!r}"


# ═══════════════════════════ AC-9 ════════════════════════════════════════════


def test_testmail_von_a_geht_nur_an_a_nie_an_b_oder_betreiber(smtp):
    """AC-9.

    GIVEN zwei echte Nutzer A und B mit verschiedenen bestaetigten Adressen
          und ein vollstaendiges ``default``-Profil mit eigener Adresse.
    WHEN  A die Testmail ausloest.
    THEN  genau eine Sendung an As Adresse, ueber die normale Kette; weder B
          noch die Betreiber-Adresse noch die ``default``-Adresse taucht auf.

    Die Empfaengerzusicherung allein waere heute schon gruen; rot macht den
    Test der Host-/Login-Unterscheider (wie AC-8).
    """
    from services.channel_test_service import send_test_message

    _bestaetigt("nutzer-a-zwei", "nutzer-a-zwei@henemm.com")
    _bestaetigt("nutzer-b-zwei", "nutzer-b-zwei@henemm.com")
    _bestaetigt("default", "default-profil@henemm.com")

    ergebnis = send_test_message("email", "nutzer-a-zwei")

    assert ergebnis == {"status": "ok"}, f"AC-9: gesehen {ergebnis!r} ({smtp!r})"
    assert smtp.empfaenger == ["nutzer-a-zwei@henemm.com"], f"AC-9: {smtp!r}"
    for fremd in ("nutzer-b-zwei@henemm.com", BETREIBER, "default-profil@henemm.com"):
        assert fremd not in smtp.empfaenger, f"AC-9: {fremd} erreicht: {smtp!r}"
    assert smtp.verbindungen == [PROD_SMTP_HOST], f"AC-9: {smtp!r}"


def test_testmail_von_b_geht_nur_an_b(smtp):
    """AC-9 (Gegenrichtung): dieselbe Ablage, B loest aus -- nur B."""
    from services.channel_test_service import send_test_message

    _bestaetigt("nutzer-a-zwei", "nutzer-a-zwei@henemm.com")
    _bestaetigt("nutzer-b-zwei", "nutzer-b-zwei@henemm.com")

    ergebnis = send_test_message("email", "nutzer-b-zwei")

    assert ergebnis == {"status": "ok"}, f"AC-9: gesehen {ergebnis!r} ({smtp!r})"
    assert smtp.empfaenger == ["nutzer-b-zwei@henemm.com"], f"AC-9: {smtp!r}"
    assert smtp.verbindungen == [PROD_SMTP_HOST], f"AC-9: {smtp!r}"


# ═══════════════════════════ AC-10 ═══════════════════════════════════════════


def test_default_kennung_sendet_nichts_auch_mit_vollstaendigem_profil(smtp):
    """AC-10 (``"default"``).

    GIVEN ein vollstaendiges, bestaetigtes Profil unter ``default``.
    WHEN  die Testmail mit ``user_id="default"`` ausgeloest wird.
    THEN  keine Verbindung, deutscher Fehlertext.

    RED heute: es geht eine Mail an die ``default``-Adresse.
    """
    from services.channel_test_service import send_test_message

    _bestaetigt("default", "default-profil@henemm.com")

    ergebnis = send_test_message("email", "default")

    assert smtp.verbindungen == [] and smtp.sendungen == [], f"AC-10: {smtp!r}"
    _klarer_deutscher_fehlertext(ergebnis)


def test_leere_kennung_sendet_nichts_und_meldet_klaren_text(smtp):
    """AC-10 (leere Kennung).

    RED heute: nichts wird gesendet (``get_data_dir`` wirft), aber der Nutzer
    sieht ``invalid user_id: ''`` statt eines deutschen Textes.
    """
    from services.channel_test_service import send_test_message

    ergebnis = send_test_message("email", "")

    assert smtp.verbindungen == [] and smtp.sendungen == [], f"AC-10: {smtp!r}"
    _klarer_deutscher_fehlertext(ergebnis)


def test_fehlende_user_json_sendet_nichts_und_nie_an_den_betreiber(smtp):
    """AC-10 (``user.json`` fehlt).

    GIVEN ein Nutzerverzeichnis OHNE ``user.json``, globale Betreiber-Adresse
          gesetzt.
    WHEN  die Testmail ausgeloest wird.
    THEN  keine Verbindung, kein Betreiber-Empfang, deutscher Fehlertext.

    RED heute: ``with_user_profile`` faellt auf die globale ``mail_to`` zurueck,
    die Mail geht an den Betreiber. Gegenprobe zur Sperre "user.json fehlt".
    """
    from services.channel_test_service import send_test_message

    get_data_dir("nutzer-ohne-profil").mkdir(parents=True, exist_ok=True)

    ergebnis = send_test_message("email", "nutzer-ohne-profil")

    assert BETREIBER not in smtp.empfaenger, f"AC-10: Betreiber erreicht: {smtp!r}"
    assert smtp.verbindungen == [] and smtp.sendungen == [], f"AC-10: {smtp!r}"
    _klarer_deutscher_fehlertext(ergebnis)


def test_unbestaetigte_adresse_sendet_nichts(smtp):
    """AC-10 (``email_verified_at`` fehlt).

    GIVEN ein Profil mit lokal zustellbarer ``mail_to``, aber ohne Bestaetigung.
    WHEN  die Testmail ausgeloest wird.
    THEN  keine Verbindung, deutscher Fehlertext.

    RED heute: die Mail geht hinaus (der Lokal-Guard laesst ``@henemm.com``
    durch, eine Bestaetigung prueft niemand).
    """
    from services.channel_test_service import send_test_message

    _profil(
        "nutzer-unbestaetigt",
        email="nutzer-unbestaetigt@henemm.com",
        mail_to="nutzer-unbestaetigt@henemm.com",
    )

    ergebnis = send_test_message("email", "nutzer-unbestaetigt")

    assert smtp.verbindungen == [] and smtp.sendungen == [], f"AC-10: {smtp!r}"
    _klarer_deutscher_fehlertext(ergebnis)


def test_leere_profiladresse_sendet_nichts_und_nie_an_den_betreiber(smtp):
    """AC-10 (Profil-``mail_to`` leer).

    GIVEN ein bestaetigtes Profil mit leerer ``mail_to``, globale
          Betreiber-Adresse gesetzt.
    WHEN  die Testmail ausgeloest wird.
    THEN  keine Verbindung, kein Betreiber-Empfang, deutscher Fehlertext.

    RED heute: gesendet wird zwar nichts ("kein Empfaenger"), aber der Text
    nennt interne Bezeichner (``settings.mail_to``).
    """
    from services.channel_test_service import send_test_message

    _profil(
        "nutzer-ohne-adresse", mail_to="",
        email_verified_at="2026-10-01T08:00:00Z",
    )

    ergebnis = send_test_message("email", "nutzer-ohne-adresse")

    assert BETREIBER not in smtp.empfaenger, f"AC-10: Betreiber erreicht: {smtp!r}"
    assert smtp.verbindungen == [] and smtp.sendungen == [], f"AC-10: {smtp!r}"
    _klarer_deutscher_fehlertext(ergebnis)


def test_profiladresse_nur_aus_leerzeichen_sendet_nichts(smtp):
    """AC-10 (Profil-``mail_to`` besteht nur aus Leerzeichen) -- Waechter.

    GIVEN ein bestaetigtes Profil, dessen ``mail_to`` nur Leerzeichen enthaelt
          (truthy, aber keine Adresse), globale Betreiber-Adresse gesetzt.
    WHEN  die Testmail ausgeloest wird.
    THEN  keine Verbindung, kein Betreiber-Empfang, deutscher Fehlertext --
          die Sperre muss die Adresse trimmen, nicht nur auf Truthiness pruefen.
    """
    from services.channel_test_service import send_test_message

    _profil(
        "nutzer-leerzeichen-adresse", mail_to="   ",
        email_verified_at="2026-10-01T08:00:00Z",
    )

    ergebnis = send_test_message("email", "nutzer-leerzeichen-adresse")

    assert BETREIBER not in smtp.empfaenger, f"AC-10: Betreiber erreicht: {smtp!r}"
    assert smtp.verbindungen == [] and smtp.sendungen == [], f"AC-10: {smtp!r}"
    _klarer_deutscher_fehlertext(ergebnis)
