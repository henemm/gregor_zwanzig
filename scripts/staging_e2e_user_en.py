#!/usr/bin/env python3
"""Zweiter Staging-Nutzer ``en`` fuer die zweisprachigen E2E-Laeufe (Issue #2681).

Spec:    docs/specs/modules/i18n_a2_e2e_zweisprachig_2681.md
Runbook: docs/runbooks/staging_e2e_nutzer_en.md

Legt idempotent EINEN bestaetigten Staging-Nutzer mit ``language=en`` an, dessen
Mails an die Subadresse ``<GZ_TEST_IMAP_USER-Lokalteil>+en@<Domain>`` gehen
(Stalwart liefert ``user+tag`` ins Basispostfach). Registrierung ueber die echte
API mit Helfer-Konto (``GZ_AUTH_USER``/``GZ_AUTH_PASS``: ``staging-token``,
``verify-email``), Muster ``.claude/tools/staging_befehl_pruefen.py``.

Aufruf:  python3 scripts/staging_e2e_user_en.py [--basis-url URL] [--env-datei PFAD]
Exit:    0 = Nutzer vorhanden, language=en, E-Mail bestaetigt
         1 = Zustand nicht herstellbar (Sprache laesst sich nicht setzen)
         2 = Aufruf-/Umgebungsfehler (Zugangsdaten fehlen, Registrierung
             abgelehnt, 409 email_taken, 429 Rate-Limit, veraltete Schluessel)

Geheimnisse (``GZ_E2E_EN_PASS``) stehen nur in der Staging-``.env`` und werden
nie ausgegeben; Schluessel werden nur ANGEHAENGT, nie ueberschrieben.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import secrets
import sys
from pathlib import Path

STAGING_ENV = Path("/home/hem/gregor_zwanzig_staging/.env")
BASIS_URL = "https://staging.gregor20.henemm.com"
NAME = "gzp-e2e-en"
SCHLUESSEL = ("GZ_E2E_EN_USER", "GZ_E2E_EN_PASS", "GZ_E2E_EN_MAIL")
_ENV_SCHLUESSEL = ("GZ_AUTH_USER", "GZ_AUTH_PASS", "GZ_TEST_IMAP_USER", *SCHLUESSEL)
_RUNBOOK = "docs/runbooks/staging_e2e_nutzer_en.md"

_WERKZEUG = Path(__file__).resolve().parents[1] / ".claude" / "tools" / "staging_befehl_pruefen.py"
_spec = importlib.util.spec_from_file_location("_staging_befehl_pruefen", _WERKZEUG)
_werkzeug = sys.modules.setdefault(_spec.name, importlib.util.module_from_spec(_spec))
_spec.loader.exec_module(_werkzeug)  # @dataclass braucht den Eintrag in sys.modules
StagingApi, StagingFehler, http_transport = (
    _werkzeug.StagingApi, _werkzeug.StagingFehler, _werkzeug.http_transport)


def adresse_en(test_imap_user: str) -> str:
    """'gregor-test@henemm.com' -> 'gregor-test+en@henemm.com'."""
    lokal, domain = test_imap_user.strip().split("@", 1)
    return f"{lokal}+en@{domain}"


def lade_env(pfad: Path) -> dict[str, str]:
    """``KEY=VALUE``-Zeilen der Datei (Kommentare/Leerzeilen ignoriert)."""
    werte: dict[str, str] = {}
    try:
        zeilen = Path(pfad).read_text(encoding="utf-8").splitlines()
    except OSError:
        return werte
    for z in zeilen:
        if "=" in z and not z.lstrip().startswith("#"):
            k, v = z.split("=", 1)
            werte[k.strip()] = v.strip().strip("'\"")
    return werte


def schreibe_fehlende_schluessel(pfad: Path, werte: dict) -> None:
    """Haengt nur Schluessel an, die in der Datei noch fehlen; nie ueberschreiben."""
    pfad = Path(pfad)
    vorhanden = lade_env(pfad)
    neu = [f"{k}={v}" for k, v in werte.items() if k not in vorhanden]
    if not neu:
        return
    alt = pfad.read_text(encoding="utf-8") if pfad.exists() else ""
    praefix = "" if not alt or alt.endswith("\n") else "\n"
    with pfad.open("a", encoding="utf-8") as f:
        f.write(praefix + "\n".join(neu) + "\n")
    os.chmod(pfad, 0o600)


class EnApi(StagingApi):
    """StagingApi um Anmeldung, Profil und die Registrierung mit Sprache erweitert."""

    def anmelden(self, nutzer: str, passwort: str) -> None:
        self._rufe("POST", f"{self._basis}/api/auth/login",
                   {"username": nutzer, "password": passwort})
        self._username, self._passwort = nutzer, passwort

    def profil(self) -> dict:
        return self._rufe("GET", f"{self._basis}/api/auth/profile")

    def setze_sprache(self, lang: str) -> dict:
        return self._rufe("PUT", f"{self._basis}/api/auth/profile", {"language": lang})

    def registriere_en(self, email_adresse: str, passwort: str) -> str:
        """Genau EIN Registrierungsversuch; Helfer zuerst (kein verbrauchter Versuch)."""
        b = self._basis
        if self._helfer_transport is None or not self._helfer_zugang:
            raise StagingFehler("Helfer-Konto (GZ_AUTH_USER/GZ_AUTH_PASS) fehlt - nichts registriert")
        self._rufe("POST", f"{b}/api/auth/login", {"username": self._helfer_zugang[0],
                   "password": self._helfer_zugang[1]}, transport=self._helfer_transport)
        antwort = self._rufe("POST", f"{b}/api/auth/register", {
            "username": NAME, "password": passwort, "email": email_adresse, "language": "en"})
        uid = antwort.get("id") if isinstance(antwort, dict) else None
        if not isinstance(uid, str) or not uid.strip():
            raise StagingFehler("Register-Antwort ohne Nutzer-id - Konto-Kennung unbekannt")
        tok = self._rufe("POST", f"{b}/api/auth/verify-email/staging-token",
                         {"username": uid}, transport=self._helfer_transport)["token"]
        self._rufe("POST", f"{b}/api/auth/verify-email", {"user": uid, "token": tok})
        self.anmelden(uid, passwort)
        return uid


class VeralteteSchluessel(RuntimeError):
    """GZ_E2E_EN_* vorhanden, Anmeldung scheitert: nie ueberschreiben, Runbook."""


def _stelle_sprache_sicher(api: EnApi) -> bool:
    """True, wenn korrigiert werden musste; RuntimeError, wenn es nicht gelingt."""
    if api.profil().get("language") == "en":
        return False
    api.setze_sprache("en")
    if api.profil().get("language") != "en":
        raise RuntimeError("Profil-Update auf language=en ohne Wirkung")
    return True


def sichere_nutzer_en(api: EnApi, env: dict, env_pfad: Path = STAGING_ENV) -> str:
    """'vorhanden' | 'angelegt' | 'korrigiert' (idempotent, hoechstens EINE Registrierung)."""
    if all(env.get(k) for k in SCHLUESSEL):
        try:
            api.anmelden(env["GZ_E2E_EN_USER"], env["GZ_E2E_EN_PASS"])
        except StagingFehler as exc:
            raise VeralteteSchluessel(
                f"Anmeldung des Nutzers en scheitert ({exc}); GZ_E2E_EN_* werden nie "
                f"ueberschrieben - Wiederherstellung siehe {_RUNBOOK}") from exc
        return "korrigiert" if _stelle_sprache_sicher(api) else "vorhanden"
    if not env.get("GZ_TEST_IMAP_USER"):
        raise StagingFehler("GZ_TEST_IMAP_USER fehlt - Subadresse nicht ableitbar")
    mail, passwort = adresse_en(env["GZ_TEST_IMAP_USER"]), secrets.token_urlsafe(24)
    uid = api.registriere_en(mail, passwort)
    schreibe_fehlende_schluessel(env_pfad, {"GZ_E2E_EN_USER": uid, "GZ_E2E_EN_PASS": passwort,
                                            "GZ_E2E_EN_MAIL": mail})
    _stelle_sprache_sicher(api)
    return "angelegt"


def main(argv=None, *, transport=None, helfer_transport=None) -> int:
    """Netzrand injizierbar (Tests); ohne Angaben gilt echtes HTTP."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--basis-url", default=BASIS_URL)
    p.add_argument("--env-datei", type=Path, default=STAGING_ENV)
    args = p.parse_args(argv)
    env = {**lade_env(args.env_datei),
           **{k: os.environ[k] for k in _ENV_SCHLUESSEL if os.environ.get(k)}}
    helfer = (env["GZ_AUTH_USER"], env["GZ_AUTH_PASS"]) if env.get("GZ_AUTH_USER") and \
        env.get("GZ_AUTH_PASS") else None
    api = EnApi(args.basis_url, "", "", transport or http_transport(),
                helfer_transport=helfer_transport or http_transport(), helfer_zugang=helfer)
    try:
        ergebnis = sichere_nutzer_en(api, env, args.env_datei)
    except (StagingFehler, VeralteteSchluessel) as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"FEHLER: Zustand nicht herstellbar: {exc}", file=sys.stderr)
        return 1
    print(f"Staging-Nutzer en {ergebnis}: {api.nutzer_id} (language=en, bestaetigt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
