"""Issue #2681 (A2): Staging-Nutzer ``en`` idempotent anlegen/absichern (AC-4).

Spec: docs/specs/modules/i18n_a2_e2e_zweisprachig_2681.md

Kern-Schicht, kein Netz. ``scripts/staging_e2e_user_en.py`` laeuft gegen einen
Transport, der den beobachtbaren Vertrag der Go-Endpunkte nachbildet
(``/api/auth/login``, ``/register``, ``/verify-email/staging-token``,
``/verify-email``, ``GET``/``PUT /api/auth/profile``), Muster des injizierbaren
``transport`` in ``.claude/tools/staging_befehl_pruefen.py``. Je Transport eine
eigene Sitzung (Cookie), der Serverzustand ist geteilt.
"""
from __future__ import annotations

import importlib.util
import secrets
from pathlib import Path

import pytest

SKRIPT = Path(__file__).resolve().parents[2] / "scripts" / "staging_e2e_user_en.py"


def _modul():
    spec = importlib.util.spec_from_file_location("staging_e2e_user_en_2681", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Staging:
    """Serverzustand: Konten mit Passwort, E-Mail, Sprache, Bestaetigung."""

    def __init__(self):
        self.konten: dict[str, dict] = {}
        self.registrierungen: list[dict] = []
        self.profil_updates: list[dict] = []
        self.antwort_register: tuple[int, dict] | None = None
        self._tokens: dict[str, str] = {}

    def sitzung(self):
        zustand = {"nutzer": None}

        def transport(methode, url, headers, body):
            pfad = url.split("//", 1)[-1].split("/", 1)[-1]
            return self._rufe(zustand, methode, "/" + pfad, body or {})

        return transport

    def _rufe(self, s, methode, pfad, body):
        if (methode, pfad) == ("POST", "/api/auth/login"):
            k = self.konten.get(body.get("username"))
            if not k or k["passwort"] != body.get("password"):
                return 401, {"error": "invalid_credentials"}
            if not k["bestaetigt"]:
                return 403, {"error": "email_not_verified"}
            s["nutzer"] = body["username"]
            return 200, {"id": body["username"]}
        if (methode, pfad) == ("POST", "/api/auth/register"):
            self.registrierungen.append(dict(body))
            if self.antwort_register:
                return self.antwort_register
            if any(k["email"] == body["email"] for k in self.konten.values()):
                return 409, {"error": "email_taken"}
            uid = "u-" + secrets.token_hex(4)
            self.konten[uid] = {"passwort": body["password"], "email": body["email"],
                                "language": body.get("language", "de"), "bestaetigt": False}
            return 201, {"id": uid, "username": uid}
        if (methode, pfad) == ("POST", "/api/auth/verify-email/staging-token"):
            if s["nutzer"] is None:
                return 401, {"error": "unauthorized"}
            self._tokens[body["username"]] = tok = secrets.token_hex(8)
            return 200, {"token": tok}
        if (methode, pfad) == ("POST", "/api/auth/verify-email"):
            if self._tokens.get(body.get("user")) != body.get("token"):
                return 400, {"error": "invalid_token"}
            self.konten[body["user"]]["bestaetigt"] = True
            return 200, {}
        if pfad == "/api/auth/profile" and s["nutzer"] is not None:
            k = self.konten[s["nutzer"]]
            if methode == "PUT":
                self.profil_updates.append(dict(body))
                k.update({f: body[f] for f in ("language",) if f in body})
            return 200, {"id": s["nutzer"], "email": k["email"], "language": k["language"]}
        return 401, {"error": "unauthorized"}


HELFER = {"GZ_AUTH_USER": "helfer", "GZ_AUTH_PASS": "helfer-pw-geheim"}


@pytest.fixture
def staging(tmp_path, monkeypatch):
    for k in ("GZ_AUTH_USER", "GZ_AUTH_PASS", "GZ_TEST_IMAP_USER", "GZ_E2E_EN_USER",
              "GZ_E2E_EN_PASS", "GZ_E2E_EN_MAIL"):
        monkeypatch.delenv(k, raising=False)
    server = _Staging()
    server.konten["helfer"] = {"passwort": HELFER["GZ_AUTH_PASS"], "email": "h@henemm.com",
                               "language": "de", "bestaetigt": True}
    env = tmp_path / "staging.env"
    env.write_text("# Staging\nGZ_ENV=staging\nGZ_TEST_IMAP_USER=gregor-test@henemm.com\n"
                   f"GZ_AUTH_USER={HELFER['GZ_AUTH_USER']}\nGZ_AUTH_PASS={HELFER['GZ_AUTH_PASS']}\n")
    return server, env


def _lauf(mod, server, env, *extra):
    return mod.main(["--env-datei", str(env), *extra],
                    transport=server.sitzung(), helfer_transport=server.sitzung())


def test_adresse_en():
    mod = _modul()
    assert mod.adresse_en("gregor-test@henemm.com") == "gregor-test+en@henemm.com"
    assert mod.adresse_en("x.y@example.org") == "x.y+en@example.org"


def test_erstanlage_registriert_einmal_und_sichert_schluessel(staging, capsys):
    mod = _modul()
    server, env = staging
    assert _lauf(mod, server, env) == 0
    assert len(server.registrierungen) == 1
    reg = server.registrierungen[0]
    assert reg["email"] == "gregor-test+en@henemm.com"
    assert reg["language"] == "en" and reg["username"] == "gzp-e2e-en"
    werte = mod.lade_env(env)
    assert werte["GZ_E2E_EN_MAIL"] == "gregor-test+en@henemm.com"
    konto = server.konten[werte["GZ_E2E_EN_USER"]]
    assert konto["passwort"] == werte["GZ_E2E_EN_PASS"] and konto["bestaetigt"]
    assert werte["GZ_ENV"] == "staging", "bestehende Zeilen bleiben erhalten"
    ausgabe = capsys.readouterr()
    assert "angelegt" in ausgabe.out
    for geheim in (werte["GZ_E2E_EN_PASS"], HELFER["GZ_AUTH_PASS"]):
        assert geheim not in ausgabe.out + ausgabe.err, "Passwort darf nie in der Ausgabe stehen"


def test_zweiter_lauf_legt_kein_zweites_konto_an(staging, capsys):
    mod = _modul()
    server, env = staging
    assert _lauf(mod, server, env) == 0
    capsys.readouterr()
    assert _lauf(mod, server, env) == 0
    assert len(server.registrierungen) == 1, "zweiter Lauf = null Registrierungen"
    assert server.profil_updates == []
    assert "vorhanden" in capsys.readouterr().out


def test_abweichende_sprache_wird_korrigiert(staging, capsys):
    mod = _modul()
    server, env = staging
    assert _lauf(mod, server, env) == 0
    uid = mod.lade_env(env)["GZ_E2E_EN_USER"]
    server.konten[uid]["language"] = "de"
    capsys.readouterr()
    assert _lauf(mod, server, env) == 0
    assert server.profil_updates == [{"language": "en"}]
    assert server.konten[uid]["language"] == "en"
    assert len(server.registrierungen) == 1
    assert "korrigiert" in capsys.readouterr().out


def test_schreibe_fehlende_schluessel_ueberschreibt_nie(tmp_path):
    mod = _modul()
    datei = tmp_path / ".env"
    datei.write_text("A=1\nGZ_E2E_EN_USER=alt\n")
    mod.schreibe_fehlende_schluessel(datei, {"GZ_E2E_EN_USER": "neu", "GZ_E2E_EN_PASS": "p"})
    werte = mod.lade_env(datei)
    assert werte == {"A": "1", "GZ_E2E_EN_USER": "alt", "GZ_E2E_EN_PASS": "p"}
    assert datei.read_text().startswith("A=1\nGZ_E2E_EN_USER=alt\n")


def test_ohne_helfer_konto_exit_2_ohne_registrierung(staging):
    mod = _modul()
    server, env = staging
    env.write_text("GZ_TEST_IMAP_USER=gregor-test@henemm.com\n")
    assert _lauf(mod, server, env) == 2
    assert server.registrierungen == []


@pytest.mark.parametrize("antwort", [(409, {"error": "email_taken"}), (429, {"error": "rate_limited"})])
def test_abgelehnte_registrierung_exit_2_genau_ein_versuch(staging, antwort, capsys):
    mod = _modul()
    server, env = staging
    server.antwort_register = antwort
    assert _lauf(mod, server, env) == 2
    assert len(server.registrierungen) == 1
    assert "GZ_E2E_EN_USER" not in mod.lade_env(env)
    assert str(antwort[0]) in capsys.readouterr().err


def test_veraltete_zugangsdaten_401_ohne_neuanlage(staging, capsys):
    """Vorhandene, aber nicht mehr gueltige Schluessel: KEINE Registrierung (die
    neuen Werte duerften die alten nie ueberschreiben, das Konto waere verwaist),
    sondern Exit 2 mit Verweis aufs Runbook."""
    mod = _modul()
    server, env = staging
    with env.open("a") as f:
        f.write("GZ_E2E_EN_USER=u-weg\nGZ_E2E_EN_PASS=alt\nGZ_E2E_EN_MAIL=gregor-test+en@henemm.com\n")
    assert _lauf(mod, server, env) == 2
    assert server.registrierungen == []
    assert "staging_e2e_nutzer_en.md" in capsys.readouterr().err
    assert mod.lade_env(env)["GZ_E2E_EN_PASS"] == "alt"


# --- Issue #2788: Dateirechte der Staging-.env erhalten, reiner Benutzername ----
# Spec: docs/specs/bugfix/fix_2788_staging_env_rechte.md

import os  # noqa: E402
import shutil  # noqa: E402
import stat  # noqa: E402
import subprocess  # noqa: E402


def _modus(pfad: Path) -> int:
    return stat.S_IMODE(os.stat(pfad).st_mode)


@pytest.fixture
def umask_022():
    alt = os.umask(0o022)
    try:
        yield
    finally:
        os.umask(alt)


def test_adresse_en_reiner_benutzername():
    """AC-4: Stalwart-Konvention, nur Benutzername -> Domain henemm.com."""
    assert _modul().adresse_en("gregor-test") == "gregor-test+en@henemm.com"


def test_adresse_en_volle_adresse_unveraendert():
    """AC-5: volle Adresse bleibt rueckwaertskompatibel."""
    assert _modul().adresse_en("gregor-test@henemm.com") == "gregor-test+en@henemm.com"


def test_bestehende_env_behaelt_modus_640(staging):
    """AC-1: Anhaengen an eine bestehende .env aendert ihren Modus nicht."""
    mod = _modul()
    server, env = staging
    os.chmod(env, 0o640)
    assert _lauf(mod, server, env) == 0
    assert "GZ_E2E_EN_USER" in mod.lade_env(env), "Schluessel muessen angehaengt sein"
    assert _modus(env) == 0o640, f"Modus veraendert: {oct(_modus(env))}"


def test_neue_env_entsteht_mit_600(staging, umask_022, monkeypatch):
    """AC-3: fehlt die Datei, entsteht sie mit 600 (Zugang per Umgebungsvariablen)."""
    mod = _modul()
    server, env = staging
    env.unlink()
    for k, v in {**HELFER, "GZ_TEST_IMAP_USER": "gregor-test@henemm.com"}.items():
        monkeypatch.setenv(k, v)
    assert _lauf(mod, server, env) == 0
    assert env.exists()
    assert _modus(env) == 0o600, f"Modus: {oct(_modus(env))}"
    assert "GZ_E2E_EN_PASS" in mod.lade_env(env)


def test_erstanlage_mit_reinem_benutzernamen(staging):
    """AC-4: GZ_TEST_IMAP_USER=gregor-test -> Registrierung unter +en@henemm.com."""
    mod = _modul()
    server, env = staging
    env.write_text(env.read_text().replace(
        "GZ_TEST_IMAP_USER=gregor-test@henemm.com", "GZ_TEST_IMAP_USER=gregor-test"))
    assert _lauf(mod, server, env) == 0
    assert [r["email"] for r in server.registrierungen] == ["gregor-test+en@henemm.com"]
    assert mod.lade_env(env)["GZ_E2E_EN_MAIL"] == "gregor-test+en@henemm.com"


def test_erstanlage_mit_voller_adresse_identisch(staging):
    """AC-5: Erstanlage mit voller Adresse ergibt dieselbe Subadresse."""
    mod = _modul()
    server, env = staging
    assert _lauf(mod, server, env) == 0
    assert [r["email"] for r in server.registrierungen] == ["gregor-test+en@henemm.com"]


@pytest.mark.skipif(not (shutil.which("setfacl") and shutil.which("getfacl")),
                    reason="setfacl/getfacl nicht verfuegbar")
def test_acl_maske_bleibt_erhalten(staging):
    """AC-2: ACL-Eintrag und Maske r-- ueberleben das Anhaengen."""
    mod = _modul()
    server, env = staging
    os.chmod(env, 0o640)
    nutzer = subprocess.run(["id", "-un"], capture_output=True, text=True,
                            check=True).stdout.strip()
    r = subprocess.run(["setfacl", "-m", f"u:{nutzer}:r--,m::r--", str(env)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip(f"Dateisystem ohne ACL-Unterstuetzung: {r.stderr.strip()}")

    def acl():
        return subprocess.run(["getfacl", "-c", str(env)], capture_output=True,
                              text=True, check=True).stdout

    assert "mask::r--" in acl()
    assert _lauf(mod, server, env) == 0
    nachher = acl()
    assert "mask::r--" in nachher, nachher
    assert f"user:{nutzer}:r--" in nachher, nachher


def test_runbook_nennt_rechte_erhalt():  # doc-compliance-test
    """AC-6: Runbook beschreibt den Rechte-Erhalt statt 'Dateirechte 600'."""
    text = (SKRIPT.parents[1] / "docs" / "runbooks" / "staging_e2e_nutzer_en.md").read_text()
    assert "Dateirechte 600" not in text
    assert "ACL" in text and "600" in text
