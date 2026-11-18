"""Issue #2967: Staging-Pruefkonto mit den Mockup-Beispieldaten (Seed-Skript).

Spec: docs/specs/modules/feat_2967_pruefkonto_mockupdaten.md (AC-1..AC-7, AC-10..AC-15)

Kern-Schicht, kein Netz. ``scripts/staging_pruefkonto_mockupdaten.py`` laeuft mit
``main(argv, transport=...)`` gegen einen zustandsbehafteten Fake-Server, der den
beobachtbaren Vertrag der Go-Routen nachbildet (Muster
``tests/tdd/test_staging_e2e_nutzer_en.py``). Transport-Vertrag wie
``.claude/tools/staging_befehl_pruefen.py``: ``transport(methode, url, headers, body)
-> (status, json)``; EIN Transport fuer oeffentliche Routen (Staging-URL) und interne
Routen (``http://localhost:8091``), der Fake verteilt nach Host.

Festgelegte Aufrufschnittstelle (Tech-Lead-Entscheidung in RED):
  --basis-url  (Default https://staging.gregor20.henemm.com)
  --intern-url (Default http://localhost:8091)
  --env-datei  (Default Staging-.env; Schluessel GZ_AUTH_USER, GZ_AUTH_PASS,
                CORE_SHARED_SECRET wie internal/config/config.go)

Nachgebildetes Go-Verhalten: requireLocalOnly (X-Forwarded-*/X-Real-IP => 403),
coreAuth (Header X-GZ-Core-Auth), telegram-connect 409 ``chat_id_already_linked``
bei fremder Chat-ID, premium-sms-learn mit ``dry_run`` (outcome would_learn /
would_skip) und Ratebremse (nur scharfe Aufrufe zaehlen), staging-code ohne Versand,
sms/verify bindet die Nummer, telegram-link liefert ``link`` mit ``?start=<token>``.

E-Mail-Entscheidung: ``mail_to`` des Pruefkontos wird NICHT umgeschrieben (es
liefert die Staging-Pruefmails ins Test-Postfach; eine Adressaenderung verlangt
ausserdem Re-Auth). Die „2 Empfaenger" des Mockups stehen im Orts-Vergleich
(``empfaenger``): Konto-Adresse plus fiktive ``.invalid``-Adresse(n).
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import secrets
from pathlib import Path

import pytest

SKRIPT = Path(__file__).resolve().parents[2] / "scripts" / "staging_pruefkonto_mockupdaten.py"
STAGING = "https://staging.gregor20.henemm.com"
INTERN = "http://localhost:8091"
SECRET = "kern-geheimnis-XYZ-2967-erkennbar"
PRUEF = {"user": "pruefkonto", "pass": "pruef-pw-geheim", "mail": "gregor-test@henemm.com"}

TRIP_AN = {"temperature", "temperature_night", "wind_chill", "wind", "gust", "precipitation",
           "thunder", "rain_probability", "visibility", "cloud_low", "uv_index",
           "freezing_level", "snowfall_limit"}
TRIP_AUS = {"cloud_total", "sunshine", "fresh_snow", "snow_depth", "dewpoint", "humidity",
            "pressure"}
ETAPPEN_KM = [7.8, 8.4, 6.9, 8.4]
ETAPPEN_TAGE = ["2026-02-23", "2026-02-24", "2026-02-25", "2026-02-26"]
ETAPPEN_ORTE = [("Port d'Andratx", "Estellencs"), ("Estellencs", "Esporles"),
                ("Esporles", "Valldemossa"), ("Valldemossa", "Deià")]
ORTE = {"Münster": 60, "Telgte": 52, "Tecklenburg": 235}
PROXY_KOEPFE = ("x-forwarded-for", "x-forwarded-proto", "x-forwarded-host", "x-real-ip")


def _modul():
    spec = importlib.util.spec_from_file_location("staging_pruefkonto_mockupdaten_2967", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _leeres_konto(mail):
    return {"daten": {"trips": {}, "locations": {}, "compare": {}, "presets": {}},
            "profil": {"email": mail, "mail_to": mail, "email_verified": True, "sms_to": "",
                       "sms_verified_number": "", "telegram_chat_id": "", "tier": "free",
                       "premium_sms_reply_to": "", "premium_sms_reply_at": None},
            "zaehler": {"sms": 7, "premium_sms": 3}}


class _Fake:
    """Zustand je Nutzer + Protokoll aller Aufrufe; fluechtige Tokens/Codes getrennt."""

    def __init__(self):
        self.passwoerter = {PRUEF["user"]: PRUEF["pass"]}
        self.konten = {PRUEF["user"]: _leeres_konto(PRUEF["mail"])}
        self.aufrufe: list[dict] = []
        self.tg_tokens: dict[str, str] = {}
        self.sms_codes: dict[str, tuple[str, str]] = {}
        self.link_codes: dict[str, str] = {}
        self.bremse = 0
        self.bremse_max = 5
        self.stoerung: dict[tuple[str, str], tuple[int, dict]] = {}

    def neues_konto(self, uid, mail):
        self.passwoerter[uid] = "pw-" + uid
        self.konten[uid] = _leeres_konto(mail)
        return self.konten[uid]

    def zustand(self, uid=None):
        quelle = self.konten if uid is None else self.konten[uid]
        return json.dumps(quelle, sort_keys=True, ensure_ascii=False, default=str)

    def transport(self):
        sitzung = {"nutzer": None}

        def rufe(methode, url, headers, body):
            headers = {k.lower(): v for k, v in (headers or {}).items()}
            host, _, rest = url.partition("//")[2].partition("/")
            pfad, _, query = ("/" + rest).partition("?")
            self.aufrufe.append({"methode": methode, "host": host, "pfad": pfad,
                                 "headers": headers, "body": copy.deepcopy(body)})
            if (methode, pfad) in self.stoerung:
                return self.stoerung[(methode, pfad)]
            if host in ("localhost:8091", "127.0.0.1:8091"):
                return self._intern(methode, pfad, headers, body or {})
            if host != "staging.gregor20.henemm.com":
                return 599, {"error": "fremder_host_im_fake"}
            return self._oeffentlich(sitzung, methode, pfad, body or {})

        return rufe

    # --- interne Routen (requireLocalOnly + coreAuth) -------------------------
    def _intern(self, methode, pfad, headers, body):
        if any(k in headers for k in PROXY_KOEPFE):
            return 403, {"error": "forbidden"}
        if headers.get("x-gz-core-auth") != SECRET:
            return 401, {"error": "unauthorized"}
        if (methode, pfad) == ("POST", "/api/internal/telegram-connect"):
            uid = self.tg_tokens.pop(body.get("token", ""), None)
            if not uid or not body.get("chat_id"):
                return 422, {"error": "token invalid or expired"}
            for anderer, k in self.konten.items():
                if anderer != uid and k["profil"]["telegram_chat_id"] == body["chat_id"]:
                    return 409, {"error": "chat_id_already_linked"}
            self.konten[uid]["profil"]["telegram_chat_id"] = body["chat_id"]
            return 200, {"status": "ok"}
        if (methode, pfad) == ("POST", "/api/internal/premium-sms-learn"):
            ziel = next((u for u, c in self.link_codes.items()
                         if c and c == body.get("code") and self.konten[u]["profil"]["tier"] == "premium"),
                        None)
            if body.get("dry_run"):
                if ziel is None:
                    return 200, {"status": "dry_run", "outcome": "would_skip",
                                 "reason": "link_code_invalid"}
                return 200, {"status": "dry_run", "outcome": "would_learn", "user_id": ziel,
                             "masked_from": "+***"}
            if self.bremse >= self.bremse_max:
                return 429, {"status": "skipped", "reason": "link_code_rate_limited"}
            self.bremse += 1
            if ziel is None:
                return 409, {"status": "skipped", "reason": "link_code_invalid"}
            p = self.konten[ziel]["profil"]
            p["premium_sms_reply_to"], p["premium_sms_reply_at"] = body["from"], "LAUFZEIT"
            return 200, {"status": "ok", "user_id": ziel}
        return 404, {"error": "not_found"}

    # --- oeffentliche Routen (Sitzung) ----------------------------------------
    def _oeffentlich(self, s, methode, pfad, body):
        if (methode, pfad) == ("POST", "/api/auth/login"):
            if self.passwoerter.get(body.get("username")) != body.get("password"):
                return 401, {"error": "invalid_credentials"}
            s["nutzer"] = body["username"]
            return 200, {"id": body["username"]}
        uid = s["nutzer"]
        if uid is None:
            return 401, {"error": "unauthorized"}
        konto = self.konten[uid]
        p, d = konto["profil"], konto["daten"]
        teile = pfad.strip("/").split("/")
        if pfad == "/api/auth/profile":
            if methode == "PUT":
                if "mail_to" in body and body["mail_to"] != p["mail_to"]:
                    return 403, {"error": "reauth_required"}
                if "sms_to" in body and body["sms_to"] != p["sms_to"]:
                    p["sms_to"], p["sms_verified_number"] = body["sms_to"], ""
            return 200, self._profil(uid)
        if (methode, pfad) == ("POST", "/api/auth/sms/staging-code"):
            if not p["sms_to"]:
                return 404, {"error": "no_number"}
            code = secrets.token_hex(3)
            self.sms_codes[uid] = (code, p["sms_to"])
            return 200, {"code": code}
        if (methode, pfad) == ("POST", "/api/auth/sms/verify"):
            code, nummer = self.sms_codes.pop(uid, (None, None))
            if code is None or code != body.get("code") or nummer != p["sms_to"]:
                return 400, {"error": "invalid_code"}
            p["sms_verified_number"] = nummer
            return 200, {"status": "ok"}
        if (methode, pfad) == ("POST", "/api/auth/staging-seed"):
            if "tier" in body:
                p["tier"] = body["tier"]
            for k in ("sms", "premium_sms"):
                if k in body:
                    konto["zaehler"][k] = body[k]
            return 200, {"tier": p["tier"], **konto["zaehler"]}
        if (methode, pfad) == ("GET", "/api/auth/telegram-link"):
            tok = secrets.token_hex(8)
            self.tg_tokens[tok] = uid
            chat = p["telegram_chat_id"]
            return 200, {"link": f"https://t.me/gregor_bot?start={tok}", "connected": bool(chat),
                         "chat_id_suffix": ("..." + chat[-3:]) if chat else ""}
        if (methode, pfad) == ("POST", "/api/auth/premium-sms-link-code"):
            self.link_codes[uid] = code = secrets.token_hex(4)
            return 200, {"code": code}
        sammlung = {"trips": "trips", "locations": "locations", "metric-presets": "presets"}
        if teile[:2] == ["api", "compare"] and len(teile) >= 3 and teile[2] == "presets":
            return self._crud(d["compare"], methode, teile[3:], body, uid)
        if len(teile) >= 2 and teile[1] in sammlung:
            ablage = d[sammlung[teile[1]]]
            if teile[1] == "trips" and len(teile) == 4 and teile[3] == "weather-config":
                trip = ablage.get(teile[2])
                if trip is None:
                    return 404, {"error": "not_found"}
                dc = trip.setdefault("display_config", {})
                if methode == "PUT":
                    dc.update(copy.deepcopy(body))
                return 200, copy.deepcopy(dc)
            if teile[1] == "metric-presets" and methode == "POST":
                if any(v["name"] == body.get("name") for v in ablage.values()):
                    return 409, {"error": "name_exists"}
                body = {**body, "id": body.get("id") or "mp-" + secrets.token_hex(3)}
            return self._crud(ablage, methode, teile[2:], body, uid)
        return 404, {"error": "not_found"}

    def _crud(self, ablage, methode, rest, body, uid):
        if not rest:
            if methode == "GET":
                return 200, [copy.deepcopy(v) for v in ablage.values()]
            if methode == "POST":
                rid = body.get("id") or secrets.token_hex(4)
                if rid in ablage:
                    return 409, {"error": "already_exists"}
                ablage[rid] = {**copy.deepcopy(body), "id": rid}
                return 201, copy.deepcopy(ablage[rid])
        rid = rest[0]
        if rid not in ablage:
            return 404, {"error": "not_found"}
        if methode == "GET":
            return 200, copy.deepcopy(ablage[rid])
        if methode in ("PUT", "PATCH"):
            ablage[rid] = {**copy.deepcopy(body), "id": rid}  # PUT ersetzt: RMW ist Client-Pflicht
            return 200, copy.deepcopy(ablage[rid])
        return 405, {"error": "method_not_allowed"}

    def _profil(self, uid):
        p = self.konten[uid]["profil"]
        stand = "fresh" if p["premium_sms_reply_to"] else "none"
        return {"id": uid, "email": p["email"], "mail_to": p["mail_to"],
                "email_verified": p["email_verified"], "sms_to": p["sms_to"],
                "sms_verified": bool(p["sms_to"]) and p["sms_verified_number"] == p["sms_to"],
                "telegram_chat_id": p["telegram_chat_id"], "tier": p["tier"],
                "premium_sms_reply_to": p["premium_sms_reply_to"],
                "premium_sms_reply_state": stand}

    # --- Auswertehilfen -------------------------------------------------------
    def zaehle(self, pfad, *, scharf=None):
        treffer = [a for a in self.aufrufe if a["pfad"] == pfad]
        if scharf is not None:
            treffer = [a for a in treffer if bool((a["body"] or {}).get("dry_run")) != scharf]
        return len(treffer)


@pytest.fixture
def fake(tmp_path, monkeypatch):
    for k in ("GZ_AUTH_USER", "GZ_AUTH_PASS", "CORE_SHARED_SECRET"):
        monkeypatch.delenv(k, raising=False)
    env = tmp_path / "staging.env"
    env.write_text(f"GZ_ENV=staging\nGZ_AUTH_USER={PRUEF['user']}\nGZ_AUTH_PASS={PRUEF['pass']}\n"
                   f"CORE_SHARED_SECRET={SECRET}\n")
    return _Fake(), env


def _lauf(mod, server, env, *extra):
    return mod.main(["--env-datei", str(env), *extra], transport=server.transport())


def _ausgabe_ids(out):
    werte = dict(z.split("=", 1) for z in out.splitlines() if z.startswith("ELEMENTLISTE_"))
    return werte.get("ELEMENTLISTE_TRIP_ID"), werte.get("ELEMENTLISTE_ORTE_ID")


def _hav(a, b):
    r = math.radians
    x = (math.sin(r(b["lat"] - a["lat"]) / 2) ** 2
         + math.cos(r(a["lat"])) * math.cos(r(b["lat"])) * math.sin(r(b["lon"] - a["lon"]) / 2) ** 2)
    return 2 * 6371.0 * math.asin(min(1, math.sqrt(x)))


def _etappen_km(etappe):
    wp = etappe["waypoints"]
    return sum(_hav(wp[i - 1], wp[i]) for i in range(1, len(wp)))


def _flags(container):
    """metrics als Liste [{metric_id, enabled}] oder Map {id: {enabled}} -> {id: bool}."""
    if isinstance(container, dict):
        return {k: bool(v.get("enabled")) for k, v in container.items()}
    return {m["metric_id"]: bool(m.get("enabled")) for m in container or []}


def _seed_daten(server):
    return server.konten[PRUEF["user"]]["daten"]


def _seed_trip(server, trip_id):
    return _seed_daten(server)["trips"][trip_id]


# --- AC-1 / AC-2 / AC-3 ----------------------------------------------------------

def test_ac1_trip_gr221_mit_mockup_etappen_und_flags(fake, capsys):
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    trip_id, _ = _ausgabe_ids(capsys.readouterr().out)
    trip = _seed_trip(server, trip_id)
    assert trip["name"] == "GR221 Mallorca"
    etappen = trip["stages"]
    assert [e["date"] for e in etappen] == ETAPPEN_TAGE
    for e, (von, bis), km in zip(etappen, ETAPPEN_ORTE, ETAPPEN_KM):
        assert von in e["name"] and bis in e["name"], e["name"]
        assert abs(_etappen_km(e) - km) <= 0.05, (e["name"], round(_etappen_km(e), 2), km)
    assert abs(sum(_etappen_km(e) for e in etappen) - 31.5) <= 0.1
    dc = trip["display_config"]
    assert dc["ampel"]["template"] == "alpen-trekking"
    for quelle in (_flags(dc["metrics"]), _flags(dc["ampel"]["metrics"])):
        assert {k for k, an in quelle.items() if an} == TRIP_AN, quelle
        for aus in TRIP_AUS | {"wind_direction"}:
            assert not quelle.get(aus, False), aus


def test_ac2_genau_eine_eigene_vorlage_mallorca_fruehling(fake, capsys):
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    trip_id, _ = _ausgabe_ids(capsys.readouterr().out)
    vorlagen = [v for v in _seed_daten(server)["presets"].values() if v["name"] == "Mallorca Frühling"]
    assert len(vorlagen) == 1
    an = {k for k, v in _flags(vorlagen[0]["metrics"]).items() if v}
    assert an == TRIP_AN
    assert vorlagen[0]["ampel"] == _seed_trip(server, trip_id)["display_config"]["ampel"]


def test_ac3_ortsvergleich_muensterland(fake, capsys):
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    _, orte_id = _ausgabe_ids(capsys.readouterr().out)
    daten = _seed_daten(server)
    vgl = daten["compare"][orte_id]
    assert vgl["name"] == "Münsterland"
    orte = {daten["locations"][i]["name"]: daten["locations"][i]["elevation_m"]
            for i in vgl["location_ids"]}
    assert orte == ORTE
    assert "allgemein" in (str(vgl.get("profil", "")).lower(),
                           str(vgl.get("display_config", {}).get("ampel", {}).get("template", "")))
    assert vgl.get("morning_time") == "07:00" and vgl.get("morning_enabled") is True
    aktiv = vgl["display_config"]["active_metrics"]
    assert aktiv and all(isinstance(m, dict) for m in aktiv), "active_metrics nur Objektform"


# --- AC-4 / AC-5 / AC-10 ---------------------------------------------------------

def test_ac4_zweiter_lauf_aendert_nichts(fake, capsys):
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    vorher = server.zustand()
    assert _lauf(mod, server, env) == 0
    assert server.zustand() == vorher
    d = _seed_daten(server)
    assert (len(d["trips"]), len(d["compare"]), len(d["locations"]), len(d["presets"])) == (1, 1, 3, 1)


def test_ac5_fremde_datensaetze_bleiben_und_rmw_erhaelt_zusatzfeld(fake, capsys):
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    trip_id, _ = _ausgabe_ids(capsys.readouterr().out)
    d = _seed_daten(server)
    d["trips"][trip_id]["shortcode"] = "GZ#ZUSATZ"
    d["trips"][trip_id]["name"] = "verstellt"
    d["trips"]["fremd-1"] = {"id": "fremd-1", "name": "Fremder Trip", "stages": []}
    d["locations"]["fremd-ort"] = {"id": "fremd-ort", "name": "Fremdort", "lat": 1, "lon": 2}
    d["compare"]["fremd-vgl"] = {"id": "fremd-vgl", "name": "Fremdvergleich", "location_ids": []}
    d["presets"]["fremd-mp"] = {"id": "fremd-mp", "name": "Fremdvorlage", "metrics": []}
    fremde = json.dumps({k: {i: v for i, v in d[k].items() if i.startswith("fremd")} for k in d},
                        sort_keys=True)
    assert _lauf(mod, server, env) == 0
    nachher = json.dumps({k: {i: v for i, v in d[k].items() if i.startswith("fremd")} for k in d},
                         sort_keys=True)
    assert nachher == fremde
    assert d["trips"][trip_id]["shortcode"] == "GZ#ZUSATZ", "RMW: Zusatzfeld muss bleiben"
    assert d["trips"][trip_id]["name"] == "GR221 Mallorca", "Soll-Feld wird zurueckgesetzt"


def test_ac10_zweiter_nutzer_bleibt_unveraendert(fake):
    mod = _modul()
    server, env = fake
    b = server.neues_konto("nutzer-b", "b@example.invalid")
    b["daten"]["trips"]["b-trip"] = {"id": "b-trip", "name": "B", "stages": []}
    vorher = server.zustand("nutzer-b")
    assert _lauf(mod, server, env) == 0
    assert server.zustand("nutzer-b") == vorher
    assert "default" not in server.konten


# --- AC-6 / AC-7 / AC-12 / AC-13 -------------------------------------------------

@pytest.mark.parametrize("url", ["https://gregor20.henemm.com", "https://example.org",
                                 "http://localhost:8090"])
def test_ac6_prod_oder_fremde_basis_url_exit2_ohne_aufruf(fake, url):
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env, "--basis-url", url) == 2
    assert server.aufrufe == []


@pytest.mark.parametrize("intern", ["http://localhost:8090", "https://gregor20.henemm.com",
                                    "http://10.0.0.5:8091", "https://staging.gregor20.henemm.com"])
def test_ac12_unzulaessiges_loopback_ziel_exit2_ohne_aufruf(fake, intern):
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env, "--intern-url", intern) == 2
    assert server.aufrufe == []


def test_ac7_erfolg_gibt_beide_ids_aus_die_existieren(fake, capsys):
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    trip_id, orte_id = _ausgabe_ids(capsys.readouterr().out)
    assert trip_id in _seed_daten(server)["trips"]
    assert orte_id in _seed_daten(server)["compare"]


def test_ac7_login_abgelehnt_exit1_ohne_ids(fake, capsys):
    mod = _modul()
    server, env = fake
    server.passwoerter[PRUEF["user"]] = "anderes"
    assert _lauf(mod, server, env) == 1
    assert _ausgabe_ids(capsys.readouterr().out) == (None, None)


def test_ac7_serverfehler_beim_anlegen_exit1(fake, capsys):
    mod = _modul()
    server, env = fake
    server.stoerung[("POST", "/api/trips")] = (500, {"error": "internal_error"})
    assert _lauf(mod, server, env) == 1
    assert _ausgabe_ids(capsys.readouterr().out) == (None, None)


@pytest.mark.parametrize("fehlt", ["GZ_AUTH_USER", "GZ_AUTH_PASS", "CORE_SHARED_SECRET"])
def test_ac7_ac13_fehlender_env_schluessel_exit2(fake, fehlt):
    mod = _modul()
    server, env = fake
    env.write_text("\n".join(z for z in env.read_text().splitlines()
                             if not z.startswith(fehlt + "=")) + "\n")
    assert _lauf(mod, server, env) == 2
    assert not [a for a in server.aufrufe if a["host"].endswith(":8091")]
    if fehlt != "CORE_SHARED_SECRET":
        assert server.aufrufe == []


@pytest.mark.parametrize("stoerung", [None, (401, {"error": "unauthorized"}),
                                      (409, {"error": "chat_id_already_linked"}),
                                      (500, {"error": f"boom {SECRET}"})])
def test_ac13_secret_erscheint_nie_in_ausgabe(fake, capsys, caplog, stoerung):
    mod = _modul()
    server, env = fake
    if stoerung:
        server.stoerung[("POST", "/api/internal/telegram-connect")] = stoerung
    code = _lauf(mod, server, env)
    assert code == (0 if stoerung is None else 1)
    aus = capsys.readouterr()
    assert SECRET not in aus.out + aus.err + caplog.text
    assert server.zaehle("/api/internal/telegram-connect") == 1


# --- AC-11 / AC-14 / AC-15 -------------------------------------------------------

def test_ac11_alle_vier_kanaele_wie_mockup(fake, capsys):
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    _, orte_id = _ausgabe_ids(capsys.readouterr().out)
    prof = server._profil(PRUEF["user"])
    konto = server.konten[PRUEF["user"]]
    # E-Mail: bestaetigt, Kontoadresse unveraendert, 2 Empfaenger im Vergleich
    assert prof["email_verified"] and prof["mail_to"] == PRUEF["mail"]
    empf = _seed_daten(server)["compare"][orte_id]["empfaenger"]
    assert len(set(empf)) == 2
    assert all(a == PRUEF["mail"] or a.endswith(".invalid") for a in empf), empf
    # SMS bestaetigt, Telegram verbunden, Premium-SMS frisch
    assert prof["sms_to"] and prof["sms_verified"]
    assert prof["telegram_chat_id"]
    assert prof["premium_sms_reply_state"] == "fresh" and prof["premium_sms_reply_to"]
    assert prof["tier"] == "premium" and konto["zaehler"] == {"sms": 0, "premium_sms": 0}
    intern = [a for a in server.aufrufe if a["host"] in ("localhost:8091", "127.0.0.1:8091")]
    assert {a["pfad"] for a in intern} == {"/api/internal/telegram-connect",
                                           "/api/internal/premium-sms-learn"}
    for a in intern:
        assert a["headers"].get("x-gz-core-auth") == SECRET
        assert not any(k in a["headers"] for k in PROXY_KOEPFE)
    scharf = [a for a in intern if a["pfad"].endswith("premium-sms-learn")]
    assert [bool(a["body"].get("dry_run")) for a in scharf] == [True, False], "erst Trockenlauf"


def test_ac14_zweiter_lauf_kein_scharfer_kanalaufruf(fake):
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    vorher, bremse = server.zustand(), server.bremse
    server.aufrufe.clear()
    assert _lauf(mod, server, env) == 0
    assert server.zustand() == vorher
    assert server.zaehle("/api/internal/telegram-connect") == 0
    assert server.zaehle("/api/internal/premium-sms-learn", scharf=True) == 0
    assert server.zaehle("/api/auth/sms/verify") == 0
    assert server.bremse == bremse


def test_ac14_ratebremse_429_exit1_ohne_wiederholung(fake):
    mod = _modul()
    server, env = fake
    server.bremse = server.bremse_max
    assert _lauf(mod, server, env) == 1
    assert server.zaehle("/api/internal/premium-sms-learn", scharf=True) == 1


def test_ac15a_zweiter_nutzer_ohne_kanaele_bleibt_unverbunden(fake):
    mod = _modul()
    server, env = fake
    server.neues_konto("nutzer-b", "b@example.invalid")
    vorher = server.zustand("nutzer-b")
    assert _lauf(mod, server, env) == 0
    assert server.zustand("nutzer-b") == vorher


def test_ac15b_chat_id_kollision_exit1_nichts_ueberschrieben(fake):
    mod = _modul()
    server, env = fake
    erst = _Fake()
    assert _lauf(mod, erst, env) == 0
    chat_id = erst.konten[PRUEF["user"]]["profil"]["telegram_chat_id"]
    b = server.neues_konto("nutzer-b", "b@example.invalid")
    b["profil"]["telegram_chat_id"] = chat_id
    vorher_b = server.zustand("nutzer-b")
    assert _lauf(mod, server, env) == 1
    assert server.zustand("nutzer-b") == vorher_b
    assert server.konten[PRUEF["user"]]["profil"]["telegram_chat_id"] == ""
