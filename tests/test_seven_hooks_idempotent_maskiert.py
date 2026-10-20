"""Kern: `scripts/seven_hooks.sh` -- idempotentes `set`, `list`, `delete`, nie Secrets in
der Ausgabe (#2439, AC-2).

Spec: docs/specs/modules/feat_2439_push_eingang_prod_scharf.md

Das Skript laeuft ECHT (bash + curl) gegen ein lokales Antwort-Double der seven.io
Hooks-API. Das Double liefert fuer `GET /hooks` die echte Antwortform
(``tests/fixtures/seven_hooks/hooks_liste_2026-10-20.json``, Mitschnitt 20.10., Secret und
Servicenummer durch Platzhalter ersetzt) und merkt sich angelegte Hooks, damit der
zweite `set` sie sieht. Fuer `POST /hooks` ist die Antwortform NICHT mitgeschnitten
(es wird vor gruenen Kern-Tests kein echter Hook angelegt); das Double antwortet
`{"success": true, "id": <neu>}` und die Tests pruefen die beim Double EINGEGANGENEN
Requests, nicht die Antwort.

Vertrag (Umgebung des Skripts):
  GZ_SEVEN_API_KEY            Pflicht; geht als Header `X-Api-Key`
  SEVEN_API_BASE              Basis der Hooks-API, Default https://gateway.seven.io/api
  GZ_PUBLIC_HOST              (set) Basis-URL der Zielumgebung, z. B. https://gregor20.henemm.com
  SEVEN_WEBHOOK_PATH_SECRET   (set) Pfad-Secret -> Ziel <GZ_PUBLIC_HOST>/api/webhooks/sms/<secret>
  SEVEN_SERVICE_NUMBER        (set) Servicenummer; als `event_filter` OHNE "+"
Aufrufe: `list` | `set` | `delete <id>`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SKRIPT = _REPO / "scripts" / "seven_hooks.sh"
_FIXTURE = _REPO / "tests" / "fixtures" / "seven_hooks" / "hooks_liste_2026-10-20.json"

API_KEY = "SENTINEL-APIKEY-7f3a91"
PFAD_SECRET = "SENTINELPFAD0c4e2b9d71"
STAGING_SECRET = "SENTINELSTAGING5a8d"
SIGNING_KEY = "SENTINEL-SIGNING-91bb"
SERVICENUMMER = "+4915790000123"
PROD = "https://gregor20.henemm.com"

pytestmark = pytest.mark.skipif(shutil.which("curl") is None, reason="curl fehlt")


@pytest.fixture
def double():
    liste = json.loads(_FIXTURE.read_text("utf-8").replace(
        "<STAGING_PFAD_SECRET>", STAGING_SECRET).replace(
        "<SERVICENUMMER>", SERVICENUMMER.lstrip("+")))
    zustand = {"hooks": liste["hooks"], "requests": [], "naechste_id": 4751}

    class _Handler(BaseHTTPRequestHandler):
        def _antwort(self, daten):
            body = json.dumps(daten).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _merke(self):
            laenge = int(self.headers.get("Content-Length") or 0)
            roh = self.rfile.read(laenge).decode("utf-8") if laenge else ""
            if "json" in (self.headers.get("Content-Type") or ""):
                felder = json.loads(roh or "{}")
            else:
                felder = {k: v[0] for k, v in parse_qs(roh).items()}
            url = urlparse(self.path)
            felder.update({k: v[0] for k, v in parse_qs(url.query).items()})
            zustand["requests"].append({
                "methode": self.command, "pfad": url.path, "felder": felder,
                "api_key": self.headers.get("X-Api-Key"),
            })
            return felder

        def do_GET(self):  # noqa: N802
            self._merke()
            self._antwort({"success": True, "code": None, "hooks": zustand["hooks"]})

        def do_POST(self):  # noqa: N802
            felder = self._merke()
            neu = {"id": str(zustand["naechste_id"]), "headers": "", "enabled": True,
                   "created": "2026-10-20 12:00:00",
                   **{k: felder.get(k) for k in
                      ("target_url", "event_type", "event_filter", "request_method")}}
            zustand["naechste_id"] += 1
            zustand["hooks"].append(neu)
            self._antwort({"success": True, "id": int(neu["id"])})

        def do_DELETE(self):  # noqa: N802
            felder = self._merke()
            zustand["hooks"] = [h for h in zustand["hooks"] if h["id"] != str(felder.get("id"))]
            self._antwort({"success": True})

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    zustand["base"] = "http://%s:%d" % srv.server_address
    yield zustand
    srv.shutdown()


def _lauf(double, *args, mit_set_env=True):
    assert _SKRIPT.is_file(), f"{_SKRIPT} fehlt"
    env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent",
           "GZ_SEVEN_API_KEY": API_KEY, "SEVEN_API_BASE": double["base"],
           "SEVEN_WEBHOOK_SIGNING_KEY": SIGNING_KEY}
    if mit_set_env:
        env.update(GZ_PUBLIC_HOST=PROD, SEVEN_WEBHOOK_PATH_SECRET=PFAD_SECRET,
                   SEVEN_SERVICE_NUMBER=SERVICENUMMER)
    erg = subprocess.run(["bash", str(_SKRIPT), *args], env=env, capture_output=True,
                         text=True, timeout=30)
    return erg


def _ohne_secrets(erg):
    ausgabe = erg.stdout + erg.stderr
    for geheim in (API_KEY, PFAD_SECRET, STAGING_SECRET, SIGNING_KEY):
        assert geheim not in ausgabe, f"Secret im Klartext in der Ausgabe: {ausgabe!r}"


def _posts(double):
    return [r for r in double["requests"] if r["methode"] == "POST"]


def test_ac2_zweimal_set_legt_genau_einen_prod_hook_an(double):
    erste = _lauf(double, "set")
    assert erste.returncode == 0, erste.stderr
    zweite = _lauf(double, "set")
    assert zweite.returncode == 0, zweite.stderr

    posts = _posts(double)
    assert len(posts) == 1, f"{len(posts)} POSTs statt genau einem: {posts}"
    felder = posts[0]["felder"]
    assert felder["event_type"] == "sms_mo"
    assert felder["event_filter"] == SERVICENUMMER.lstrip("+")
    assert felder["request_method"] == "POST"
    assert felder["target_url"] == f"{PROD}/api/webhooks/sms/{PFAD_SECRET}"
    assert "bersprungen" in zweite.stdout, f"zweiter Lauf meldet kein 'übersprungen': {zweite.stdout!r}"
    assert "4751" in zweite.stdout, "zweiter Lauf nennt die ID des vorhandenen Hooks nicht"

    ids = [h["id"] for h in double["hooks"]]
    assert ids == ["4750", "4751"], f"Staging-Hook 4750 nicht unberuehrt oder Doppel: {ids}"
    assert not [r for r in double["requests"] if r["methode"] == "DELETE"]
    _ohne_secrets(erste)
    _ohne_secrets(zweite)


def test_ac2_api_schluessel_geht_nur_als_header(double):
    _lauf(double, "set")
    assert double["requests"], "Skript hat die API nicht gefragt"
    assert all(r["api_key"] == API_KEY for r in double["requests"])
    assert all(API_KEY not in json.dumps(r["felder"]) for r in double["requests"])


def test_ac2_staging_hook_mit_anderer_ziel_url_gilt_nicht_als_vorhanden(double):
    """Der vorhandene Hook 4750 hat dasselbe Event und denselben Filter, aber die
    Staging-URL -- `set` fuer Prod darf ihn nicht als 'schon da' werten."""
    erg = _lauf(double, "set")
    assert erg.returncode == 0, erg.stderr
    assert len(_posts(double)) == 1


def test_ac2_gleiche_ziel_url_mit_anderem_event_gilt_nicht_als_vorhanden(double):
    """Uebersprungen wird nur bei gleicher Ziel-URL UND gleichem Event (`sms_mo`)."""
    double["hooks"].append({
        "id": "4700", "target_url": f"{PROD}/api/webhooks/sms/{PFAD_SECRET}",
        "headers": "", "event_type": "dlr", "event_filter": "", "request_method": "POST",
        "enabled": True, "created": "2026-10-01 10:00:00"})
    erg = _lauf(double, "set")
    assert erg.returncode == 0, erg.stderr
    posts = _posts(double)
    assert len(posts) == 1 and posts[0]["felder"]["event_type"] == "sms_mo", posts
    _ohne_secrets(erg)


def test_ac2_list_zeigt_hooks_maskiert(double):
    erg = _lauf(double, "list", mit_set_env=False)
    assert erg.returncode == 0, erg.stderr
    for erwartet in ("4750", "sms_mo", "2026-10-14 19:12:23",
                     "https://staging.gregor20.henemm.com/api/webhooks/sms/****"):
        assert erwartet in erg.stdout, f"{erwartet!r} fehlt in list: {erg.stdout!r}"
    _ohne_secrets(erg)
    assert not _posts(double)


def test_f005_list_maskiert_jedes_secret_vorkommen_in_einer_zeile(double):
    """Eine Ziel-URL mit dem Pfad-Secret zweimal (z. B. als Rueckgabe-Parameter): beide Stellen
    werden maskiert, nicht nur die erste."""
    double["hooks"].append({
        "id": "4800", "headers": "", "event_type": "sms_mo", "event_filter": "x",
        "request_method": "POST", "enabled": True, "created": "2026-10-20 12:00:00",
        "target_url": (f"{PROD}/api/webhooks/sms/{PFAD_SECRET}"
                       f"?weiter={PROD}/api/webhooks/sms/{STAGING_SECRET}")})
    erg = _lauf(double, "list", mit_set_env=False)
    assert erg.returncode == 0, erg.stderr
    zeile = next(z for z in erg.stdout.splitlines() if "4800" in z)
    assert zeile.count("/api/webhooks/sms/****") == 2, zeile
    _ohne_secrets(erg)


def test_ac2_set_meldet_angelegten_hook_maskiert(double):
    erg = _lauf(double, "set")
    assert f"{PROD}/api/webhooks/sms/****" in erg.stdout, erg.stdout
    _ohne_secrets(erg)


def test_ac2_delete_entfernt_genau_diesen_hook(double):
    _lauf(double, "set")
    erg = _lauf(double, "delete", "4751", mit_set_env=False)
    assert erg.returncode == 0, erg.stderr
    deletes = [r for r in double["requests"] if r["methode"] == "DELETE"]
    assert len(deletes) == 1 and str(deletes[0]["felder"].get("id")) == "4751", deletes
    assert [h["id"] for h in double["hooks"]] == ["4750"]
    _ohne_secrets(erg)


@pytest.mark.parametrize("fehlt", ["GZ_PUBLIC_HOST", "SEVEN_WEBHOOK_PATH_SECRET",
                                   "SEVEN_SERVICE_NUMBER"])
def test_ac2_set_ohne_pflichtwert_bricht_ohne_anlage_ab(double, fehlt):
    env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent",
           "GZ_SEVEN_API_KEY": API_KEY, "SEVEN_API_BASE": double["base"],
           "GZ_PUBLIC_HOST": PROD, "SEVEN_WEBHOOK_PATH_SECRET": PFAD_SECRET,
           "SEVEN_SERVICE_NUMBER": SERVICENUMMER}
    del env[fehlt]
    assert _SKRIPT.is_file(), f"{_SKRIPT} fehlt"
    erg = subprocess.run(["bash", str(_SKRIPT), "set"], env=env, capture_output=True,
                         text=True, timeout=30)
    assert erg.returncode != 0
    assert fehlt in erg.stderr
    assert not _posts(double)
