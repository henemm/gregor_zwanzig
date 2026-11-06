#!/usr/bin/env python3
"""Staging-Mailweg: Trip- und Compare-Mail auf Staging zustellen und pruefen (#2774).

Spec: docs/specs/modules/fix_2774_staging_mailweg.md

Legt einen Wegwerf-Nutzer mit Plus-Adresse ``gregor-test+<tag>@henemm.com`` an
(Bestaetigung ueber das Helfer-Konto), loest je Pfad einen Einzelversand am Kern
(Port 8001, Header ``X-GZ-Core-Auth``) aus und laesst den pfadrichtigen,
unveraenderten Validator mit ``--subject-contains <Tag-Betreff>`` gegen genau
diese Mail laufen. Aufraeumen (Preset, Orte, Trip, Nutzer) im ``finally``.
Aendert keinen Produktcode und beruehrt keine Daten bestehender Nutzer.

``--lang en`` (#2830): statt des Wegwerf-Nutzers wird der feste Staging-Nutzer ``en``
(GZ_E2E_EN_USER/GZ_E2E_EN_PASS) angemeldet, der Validator laeuft mit
``--lang en --to-contains +en@``; geloescht werden nur die eigenen Objekte, nie der Nutzer.

Aufruf:  python3 .claude/tools/staging_mail_pruefen.py --typ trip|compare|beide [--lang de|en]
             [--report-type morning|evening] [--format full|compact] [--timeout 300] [--ohne-cleanup]
Exit:    0 = alle gewaehlten Pfade bestanden (Validator Exit 0),
         1 = Mail nicht zugestellt, Versand abgelehnt oder Validator-Befund,
         2 = Aufruf-/Umgebungsfehler (Zugangsdaten, Core 401, Registrierung, Aufraeumen)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from email import message_from_bytes
from pathlib import Path
from urllib.parse import quote, urlencode

_HIER = Path(__file__).resolve().parent
REPO_ROOT = _HIER.parents[1]
HOOKS = REPO_ROOT / ".claude" / "hooks"


def _lade_modul(name: str, datei: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _HIER / datei)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # vor exec_module: @dataclass braucht das registrierte Modul
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return mod


pw = _lade_modul("_gz_staging_befehl_pruefen", "staging_befehl_pruefen.py")

StagingFehler = pw.StagingFehler
baue_plus_adresse = pw.baue_plus_adresse

EINZELVERSAND_TIMEOUT_S = 300
STANDARD_BASIS = "https://staging.gregor20.henemm.com"
STANDARD_KERN = "http://127.0.0.1:8001"
PFLICHT = ("GZ_CORE_SHARED_SECRET", "GZ_AUTH_USER", "GZ_AUTH_PASS")
PFLICHT_EN = ("GZ_CORE_SHARED_SECRET", "GZ_E2E_EN_USER", "GZ_E2E_EN_PASS")
PFLICHT_IMAP = ("GZ_TEST_IMAP_USER", "GZ_TEST_IMAP_PASS")
EN_SUBADRESSE = "+en@"
_VALIDATOREN = {"trip": ("briefing_mail_validator.py", "trip-briefing"),
                "compare": ("email_spec_validator.py", "compare")}
_EXIT_2 = {"core_401", "zugangsdaten_fehlen", "registrierung_abgelehnt", "login_abgelehnt",
           "umgebung", "aufraeumen_fehlgeschlagen"}


class KernAuthFehler(StagingFehler):
    """Kern lehnt den Core-Auth-Header ab (HTTP 401) - Umgebungsfehler."""


# ---------------------------------------------------------------------------
# Reine Funktionen
# ---------------------------------------------------------------------------

def baue_mail_tag() -> str:
    return pw.baue_tag()


def baue_trip_name(tag: str) -> str:
    """Kurz halten: der Betreff kuerzt den Trip-Praefix zuletzt, aber er kuerzt ihn."""
    return f"GZM {tag}"


def baue_orte(tag: str) -> list[dict]:
    basis = ((47.27, 11.39), (47.42, 10.98), (47.07, 12.69))  # Innsbruck, Zugspitze, Grossglockner
    return [{"id": f"gzm-{tag}-ort{i + 1}", "name": f"GZM {tag} Ort {i + 1}", "lat": lat, "lon": lon}
            for i, (lat, lon) in enumerate(basis)]


def baue_preset(tag: str, location_ids: list[str]) -> dict:
    """Mindestfelder nach validateComparePreset (internal/handler/compare_preset.go)."""
    return {"name": f"GZM {tag} Vergleich", "schedule": "manual", "profil": "ALLGEMEIN",
            "forecast_hours": 48, "hour_from": 6, "hour_to": 20,
            "location_ids": list(location_ids)}


def baue_trip_fuer_mail(tag: str, heute: date, email_format: str = "full") -> dict:
    """Szenario B des Vorbilds: Etappen ab heute mit kurzen Namen (Betreff-Laenge)."""
    trip = pw.baue_trip("B", tag, heute)
    trip["id"], trip["name"] = f"gzm-{tag}-trip", baue_trip_name(tag)
    if email_format != "full":
        trip["report_config"] = {"email_format": email_format}
    return trip


def waehle_validator(pfad: str) -> tuple[str, str]:
    if pfad not in _VALIDATOREN:
        raise ValueError(f"Unbekannter Pfad: {pfad!r}")
    return _VALIDATOREN[pfad]


def baue_validator_aufruf(pfad: str, betreff: str, lang: str = "de") -> list[str]:
    skript, mail_type = waehle_validator(pfad)
    aufruf = ["uv", "run", "python3", str(HOOKS / skript),
              "--mail-type", mail_type, "--subject-contains", betreff]
    if lang == "en":
        aufruf += ["--lang", "en", "--to-contains", EN_SUBADRESSE]
    return aufruf


def bestimme_exit(ausgaenge) -> int:
    """0 nur bei lauter Validator-Exit 0; Umgebungsfehler 2; sonst 1; der hoechste Code gewinnt."""
    if not ausgaenge:
        return 2
    rc = 0
    for art, wert in ausgaenge:
        if art == "validator":
            code = 0 if wert == 0 else (2 if wert == 2 else 1)
        else:
            code = 2 if art in _EXIT_2 else 1
        rc = max(rc, code)
    return rc


# ---------------------------------------------------------------------------
# Netzrand
# ---------------------------------------------------------------------------

def kern_transport(timeout: int = EINZELVERSAND_TIMEOUT_S):
    """HTTP-Rand fuer den Kern ohne Cookies, mit langem Zeitlimit (Versand dauert Minuten)."""
    def transport(methode, url, headers, body):
        daten = json.dumps(body).encode() if body is not None else (b"{}" if methode == "POST" else None)
        req = urllib.request.Request(url, data=daten, method=methode,
                                     headers={"Content-Type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                status, roh = r.status, r.read()
        except urllib.error.HTTPError as exc:
            status, roh = exc.code, exc.read()
        try:
            return status, json.loads(roh or b"{}")
        except ValueError:
            return status, {}
    return transport


def _kennung(antwort) -> str:
    if not isinstance(antwort, dict):
        return ""
    k = antwort.get("code") or antwort.get("error") or antwort.get("status")
    return k if isinstance(k, str) and k.replace("_", "").replace("-", "").isalnum() and len(k) <= 60 else ""


class MailApi(pw.StagingApi):
    """StagingApi plus Orte, Compare-Presets und Einzelversand am Kern."""

    def __init__(self, basis_url, kern_url, kern_secret, transport, *, helfer_transport=None,
                 helfer_zugang=None, kern_timeout=EINZELVERSAND_TIMEOUT_S):
        super().__init__(basis_url, kern_url, kern_secret, transport,
                         helfer_transport=helfer_transport, helfer_zugang=helfer_zugang)
        self._kern_transport = kern_transport(max(kern_timeout, EINZELVERSAND_TIMEOUT_S))

    def __repr__(self) -> str:
        return f"MailApi(basis={self._basis!r}, nutzer={self._username!r})"

    def lege_ort_an(self, ort: dict) -> str:
        self._rufe("POST", f"{self._basis}/api/locations", ort)
        return ort["id"]

    def lege_preset_an(self, preset: dict) -> str:
        antwort = self._rufe("POST", f"{self._basis}/api/compare/presets", preset)
        preset_id = antwort.get("id") if isinstance(antwort, dict) else None
        if not isinstance(preset_id, str) or not preset_id:
            raise StagingFehler("Preset-Antwort ohne id")
        return preset_id

    def loesche_ort(self, ort_id: str) -> None:
        self._rufe("DELETE", f"{self._basis}/api/locations/{quote(ort_id, safe='')}")

    def loesche_preset(self, preset_id: str) -> None:
        self._rufe("DELETE", f"{self._basis}/api/compare/presets/{quote(preset_id, safe='')}")

    def sende_einzelversand(self, pfad: str, objekt_id: str, report_type: str = "morning") -> dict:
        if not self._username or self._username == "default":
            raise StagingFehler("Einzelversand ohne Wegwerf-Nutzer verweigert")
        query = {"user_id": self._username}
        if pfad == "trip":
            pfad_url = f"/api/scheduler/trips/{quote(objekt_id, safe='')}/send"
            query["report_type"] = report_type
        else:
            pfad_url = f"/api/scheduler/compare-presets/{quote(objekt_id, safe='')}/send"
        url = f"{self._kern}{pfad_url}?{urlencode(query)}"
        status, antwort = self._kern_transport("POST", url, {"X-GZ-Core-Auth": self._secret}, None)
        if status == 401:
            raise KernAuthFehler(f"POST {pfad_url} -> HTTP 401 (X-GZ-Core-Auth abgelehnt)")
        if not 200 <= status < 300:
            zusatz = _kennung(antwort)
            raise StagingFehler(f"POST {pfad_url} -> HTTP {status}{f' ({zusatz})' if zusatz else ''}")
        return antwort if isinstance(antwort, dict) else {}


class EnMailApi(MailApi):
    """Fester Staging-Nutzer ``en`` (#2830): Login statt Registrierung, Nutzer wird nie geloescht."""

    def __repr__(self) -> str:
        return f"EnMailApi(basis={self._basis!r}, nutzer={self._username!r})"

    def melde_an(self, nutzer: str, passwort: str) -> str:
        antwort = self._rufe("POST", f"{self._basis}/api/auth/login",
                             {"username": nutzer, "password": passwort})
        # AC-21: die Kontokennung kommt aus der Login-Antwort (Go-API: {"id": uid}), nicht
        # ungeprueft aus GZ_E2E_EN_USER. Fehlt sie, ist sie "default" oder weicht sie von der
        # konfigurierten Kennung ab, gilt der Login als abgelehnt (keine Werte in der Meldung).
        uid = antwort.get("id") if isinstance(antwort, dict) else None
        if not isinstance(uid, str) or not uid.strip():
            raise StagingFehler("Login-Antwort ohne Kontokennung - Nutzer en nicht bestaetigt")
        if uid == "default" or uid != nutzer:
            raise StagingFehler("Login-Kennung weicht von GZ_E2E_EN_USER ab - Nutzer en nicht bestaetigt")
        self._username, self._passwort = uid, passwort
        return self._username

    def loesche_nutzer(self) -> None:
        """Strukturell No-op: der feste Nutzer ``en`` bleibt immer bestehen."""
        return None


# ---------------------------------------------------------------------------
# Lauf
# ---------------------------------------------------------------------------

def _bereite_trip(api, tag, heute, angelegt, email_format) -> tuple[str, str]:
    trip = baue_trip_fuer_mail(tag, heute, email_format)
    api.lege_trip_an(trip)
    angelegt["trip"].append(trip["id"])
    return trip["id"], trip["name"]


def _bereite_compare(api, tag, angelegt) -> tuple[str, str]:
    ids = []
    for ort in baue_orte(tag):
        ids.append(api.lege_ort_an(ort))
        angelegt["orte"].append(ort["id"])
    preset = baue_preset(tag, ids)
    preset_id = api.lege_preset_an(preset)
    angelegt["preset"].append(preset_id)
    return preset_id, preset["name"]


def _fahre_pfad(pfad, *, api, runner, tag, report_type, heute, angelegt, email_format,
                lang="de") -> tuple:
    try:
        if pfad == "trip":
            oid, betreff = _bereite_trip(api, tag, heute, angelegt, email_format)
        else:
            oid, betreff = _bereite_compare(api, tag, angelegt)
    except (StagingFehler, OSError) as exc:
        print(f"FAIL {pfad}: Anlegen gescheitert - {exc}", file=sys.stderr)
        return ("umgebung", None)
    try:
        antwort = api.sende_einzelversand(pfad, oid, report_type)
    except KernAuthFehler as exc:
        print(f"FAIL {pfad}: {exc}", file=sys.stderr)
        return ("core_401", None)
    except (StagingFehler, OSError) as exc:
        print(f"FAIL {pfad}: Versand abgelehnt - {exc}", file=sys.stderr)
        return ("versand_abgelehnt", None)
    if antwort.get("sent") is not True:
        print(f"FAIL {pfad}: Versand nicht erfolgt (status={_kennung(antwort) or '?'})", file=sys.stderr)
        return ("versand_abgelehnt", None)
    code = runner(baue_validator_aufruf(pfad, betreff, lang))
    print(f"{'PASS' if code == 0 else 'FAIL'} {pfad}: Betreff-Marker '{betreff}', Validator Exit {code}")
    return ("validator", code)


def _loesche(funktion, art, oid) -> bool:
    try:
        funktion(oid)
        return True
    except Exception as exc:  # Aufraeumen darf nicht abbrechen
        print(f"WARNUNG: {art} {oid} nicht geloescht ({type(exc).__name__})", file=sys.stderr)
        return False


def _raeume_auf_en(api, angelegt) -> bool:
    """en-Pfad (#2830): nur die selbst angelegten Objekte weg, der Nutzer ``en`` bleibt bestehen."""
    uebrig = {art: [oid for oid in angelegt[art] if not _loesche(funktion, name, oid)]
              for art, name, funktion in (("preset", "Preset", api.loesche_preset),
                                          ("orte", "Ort", api.loesche_ort),
                                          ("trip", "Trip", api.loesche_trip))}
    print(f"Nutzer en ({api.nutzer_id or 'nicht angemeldet'}) bleibt bestehen, er wird nie geloescht")
    if any(uebrig.values()):
        print(f"WARNUNG: eigene Objekte beim Nutzer en uebrig geblieben, von Hand entfernen - "
              f"Trip: {uebrig['trip']}, Orte: {uebrig['orte']}, Preset: {uebrig['preset']}",
              file=sys.stderr)
        return False
    return True


def _raeume_auf(api, angelegt, aufraeumen=True, lang="de") -> bool:
    kennung = getattr(api, "nutzer_id", None)
    if not aufraeumen:
        print(f"--ohne-cleanup: nichts geloescht. Nutzer-Kennung: {kennung}, Objekte: {angelegt}")
        return True
    if lang == "en":
        return _raeume_auf_en(api, angelegt)
    ok = all([_loesche(api.loesche_preset, "Preset", p) for p in angelegt["preset"]]
             + [_loesche(api.loesche_ort, "Ort", o) for o in angelegt["orte"]]
             + [_loesche(api.loesche_trip, "Trip", t) for t in angelegt["trip"]])
    try:
        api.loesche_nutzer()
    except Exception as exc:
        print(f"WARNUNG: Wegwerf-Nutzer nicht geloescht ({type(exc).__name__}) - "
              f"uebrig geblieben: {kennung or 'unbekannt'}", file=sys.stderr)
        return False
    if kennung is not None:
        print(f"Wegwerf-Nutzer geloescht: {kennung}")
    if not ok:
        print(f"WARNUNG: Reste beim Nutzer {kennung} (Nutzer selbst geloescht)", file=sys.stderr)
    return ok


def _melde_nutzer_an(api, tag, lang, en_zugang):
    """de: Wegwerf-Nutzer registrieren; en: festen Nutzer anmelden. None = ok, sonst Abbruch-Ausgang."""
    try:
        if lang == "en":
            nutzer = api.melde_an(*en_zugang)
            print(f"Nutzer en {nutzer} angemeldet (keine Registrierung)")
        else:
            nutzer = api.registriere(baue_plus_adresse(tag))
            print(f"Wegwerf-Nutzer {nutzer} ({baue_plus_adresse(tag)}) angelegt und bestaetigt")
    except (StagingFehler, OSError) as exc:
        if lang == "en":
            print(f"Abbruch: Login des Nutzers en abgelehnt - {exc}", file=sys.stderr)
            return ("login_abgelehnt", None)
        print(f"Abbruch: Registrierung abgelehnt - {exc}", file=sys.stderr)
        return ("registrierung_abgelehnt", None)
    return None


def fuehre_lauf(pfade, *, api, validator_runner, tag, report_type="morning", heute=None,
                email_format="full", aufraeumen=True, lang="de", en_zugang=None) -> int:
    heute = heute or date.today()
    angelegt = {"preset": [], "orte": [], "trip": []}
    ausgaenge = []
    try:
        abbruch = _melde_nutzer_an(api, tag, lang, en_zugang)
        if abbruch is not None:
            ausgaenge.append(abbruch)
        else:
            for pfad in pfade:
                ausgaenge.append(_fahre_pfad(pfad, api=api, runner=validator_runner, tag=tag,
                                             report_type=report_type, heute=heute,
                                             angelegt=angelegt, email_format=email_format,
                                             lang=lang))
    finally:
        if not _raeume_auf(api, angelegt, aufraeumen, lang):
            ausgaenge.append(("aufraeumen_fehlgeschlagen", None))
    return bestimme_exit(ausgaenge)


# ---------------------------------------------------------------------------
# Echter Validator-Rand: auf die Mail warten, dann Validator-Unterprozess
# ---------------------------------------------------------------------------

def _mail_da(imap, marker: str, mail_type: str, letzte: int = 40) -> bool:
    for uid in reversed(pw._alle_uids(imap)[-letzte:]):
        _, d = imap.uid("FETCH", str(uid), "(BODY.PEEK[HEADER.FIELDS (SUBJECT X-GZ-MAIL-TYPE)])")
        kopf = message_from_bytes(next((t[1] for t in d if isinstance(t, tuple)), b""))
        typ = (kopf.get("X-GZ-Mail-Type") or "").strip().lower()
        if marker in pw._betreff(kopf) and typ == mail_type:
            return True
    return False


def echter_validator_runner(env: dict, timeout: int, schlaf=time.sleep, imap_factory=None):
    """Pollt das Test-Postfach bis die Mail mit dem Betreff-Marker da ist, dann EIN Validator-Lauf."""
    imap_factory = imap_factory or pw._imap_factory(env)
    kind_env = {**os.environ, **{k: v for k, v in env.items()
                                 if k.startswith(("GZ_TEST_IMAP_", "GZ_IMAP_HOST", "GZ_IMAP_PORT"))}}

    def runner(argv) -> int:
        marker = argv[argv.index("--subject-contains") + 1]
        mail_type = argv[argv.index("--mail-type") + 1]
        gewartet = 0
        while not pw._mit_imap(imap_factory, lambda im: _mail_da(im, marker, mail_type)):
            if gewartet >= timeout:
                print(f"Mail mit Betreff-Marker '{marker}' nach {timeout} s nicht im Postfach",
                      file=sys.stderr)
                return 1
            schlaf(pw.INTERVALL_S)
            gewartet += pw.INTERVALL_S
        sys.stdout.flush()
        return subprocess.run(argv, cwd=REPO_ROOT, env=kind_env).returncode
    return runner


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def _argumente(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--typ", choices=("trip", "compare", "beide"), required=True)
    p.add_argument("--report-type", choices=("morning", "evening"), default="morning")
    p.add_argument("--format", choices=("full", "compact"), default="full", dest="email_format")
    p.add_argument("--timeout", type=int, default=EINZELVERSAND_TIMEOUT_S)
    p.add_argument("--ohne-cleanup", action="store_true", help="nur Fehlersuche: nichts loeschen")
    p.add_argument("--lang", choices=("de", "en"), default="de",
                   help="eine Sprache je Aufruf; en = fester Staging-Nutzer en (#2830)")
    return p.parse_args(argv)


def main(argv=None, *, transport=None, helfer_transport=None, validator_runner=None) -> int:
    """Netzrand injizierbar (Tests); ohne Angaben gelten echtes HTTP, IMAP und Validator."""
    try:
        args = _argumente(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    env = pw._lade_env()
    en = args.lang == "en"
    pflicht = (PFLICHT_EN if en else PFLICHT) + (PFLICHT_IMAP if validator_runner is None else ())
    fehlend = [k for k in pflicht if not env.get(k)]
    if fehlend:
        print(f"Zugangsdaten fehlen: {', '.join(fehlend)}", file=sys.stderr)
        return 2
    basis = (env.get("GZ_STAGING_BASE_URL", STANDARD_BASIS), env.get("GZ_STAGING_CORE_URL", STANDARD_KERN),
             env["GZ_CORE_SHARED_SECRET"], transport or pw.http_transport())
    if en:
        api = EnMailApi(*basis, kern_timeout=args.timeout)
    else:
        api = MailApi(*basis, helfer_transport=helfer_transport or pw.http_transport(),
                      helfer_zugang=(env["GZ_AUTH_USER"], env["GZ_AUTH_PASS"]),
                      kern_timeout=args.timeout)
    en_zugang = (env["GZ_E2E_EN_USER"], env["GZ_E2E_EN_PASS"]) if en else None
    runner = validator_runner or echter_validator_runner(env, max(args.timeout, EINZELVERSAND_TIMEOUT_S))
    pfade = ["trip", "compare"] if args.typ == "beide" else [args.typ]
    from zoneinfo import ZoneInfo
    return fuehre_lauf(pfade, api=api, validator_runner=runner, tag=baue_mail_tag(),
                       report_type=args.report_type, heute=datetime.now(ZoneInfo("Europe/Vienna")).date(),
                       email_format=args.email_format, aufraeumen=not args.ohne_cleanup,
                       lang=args.lang, en_zugang=en_zugang)


if __name__ == "__main__":
    sys.exit(main())
