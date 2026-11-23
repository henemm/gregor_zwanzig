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
  --env-datei  (Default Staging-.env; Schluessel GZ_PRUEFKONTO_USER, GZ_PRUEFKONTO_PASS
                (eigenes Pruefkonto, nicht das geteilte GZ_AUTH_*-Konto "default"),
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
import os
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


# Mengen-Quoten je Tarif wie internal/model/tier.go (quotaTable) und
# internal/handler/quota.go (Trips/Vergleiche nur nicht archivierte, Orte alle).
_QUOTE = {"free": {"trips": 3, "compare": 2, "locations": 10},
          "standard": {"trips": 15, "compare": 10, "locations": 50},
          "premium": {"trips": 50, "compare": 30, "locations": 200}}
# model.SmsAllowed: Code-Versand bei PUT sms_to nur in diesen Tarifen (auth.go sendSmsCode).
_SMS_TARIFE = ("standard", "premium")


def _quote_voll(konto, art):
    grenze = _QUOTE.get(konto["profil"]["tier"], _QUOTE["free"])[art]
    aktiv = [v for v in konto["daten"][art].values()
             if art == "locations" or not v.get("archived")]
    return len(aktiv) >= grenze


def _vergleich_wie_go(body):
    """Schreibpfad wie internal/handler/compare_preset.go: schedule daily|weekly|manual
    Pflicht (validateComparePreset), Slot-Zeiten "HH:MM" -> "HH:MM:SS"
    (store.ValidateQuarterHourSlotTime). Ungueltig => None (400)."""
    if body.get("schedule") not in ("daily", "weekly", "manual"):
        return None
    body = copy.deepcopy(body)
    for feld in ("morning_time", "evening_time"):
        wert = body.get(feld)
        if isinstance(wert, str) and len(wert) == 5:
            body[feld] = wert + ":00"
    # #3151: materializeAlertChannels (internal/store/compare_preset.go:55-71): fehlt
    # alert_channels, leitet der Store es aus den Flachfeldern ab (E-Mail immer an).
    if body.get("alert_channels") is None:
        body["alert_channels"] = {"email": True,
                                  "telegram": bool(body.get("send_telegram")),
                                  "sms": bool(body.get("send_sms")),
                                  "premium_sms": bool(body.get("send_premium_sms"))}
    return body


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
        # SMS-Code-Versaende (auth.go dispatchSmsVerificationCode -> sms_verify.go).
        self.sms_versand = 0
        self.stoerung: dict[tuple[str, str], tuple[int, dict]] = {}
        # Fehlzuordnung des Link-Codes zu einem anderen Konto (Trockenlauf UND scharf).
        self.code_besitzer: str | None = None

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
            self.aufrufe.append({"methode": methode, "host": host, "pfad": pfad, "query": query,
                                 "headers": headers, "body": copy.deepcopy(body)})
            if (methode, pfad) in self.stoerung:
                return self.stoerung[(methode, pfad)]
            if host in ("localhost:8091", "127.0.0.1:8091"):
                return self._intern(methode, pfad, headers, body or {})
            if host != "staging.gregor20.henemm.com":
                return 599, {"error": "fremder_host_im_fake"}
            return self._oeffentlich(sitzung, methode, pfad, body or {}, query)

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
            ziel = self.code_besitzer or ziel
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
    def _oeffentlich(self, s, methode, pfad, body, query=""):
        if (methode, pfad) == ("POST", "/api/auth/login"):
            if self.passwoerter.get(body.get("username")) != body.get("password"):
                return 401, {"error": "invalid_credentials"}
            s["nutzer"] = body["username"]
            return 200, {"id": body["username"]}
        uid = s["nutzer"]
        if uid is None:
            return 401, {"error": "unauthorized"}
        if pfad.startswith("/api/auth/"):
            return self._auth(uid, methode, pfad, body)
        if pfad.startswith("/api/briefings/") and pfad.endswith("/placements"):
            return self._placements(uid, methode, pfad, query, body)
        return self._daten(uid, methode, pfad, body)

    def _placements(self, uid, methode, pfad, query, body):
        """#3154: GET/PUT /api/briefings/{id}/placements?kind=route|vergleich
        (internal/handler/placements.go): Abo dieses Nutzers der genannten Art, sonst 404;
        PUT ersetzt nur display_config.placements (Read-Modify-Write)."""
        kind = dict(t.split("=", 1) for t in query.split("&") if "=" in t).get("kind")
        bid = pfad.strip("/").split("/")[2]
        ablage = {"route": "trips", "vergleich": "compare"}.get(kind)
        if ablage is None:
            return 400, {"error": "kind_required"}
        abo = self.konten[uid]["daten"][ablage].get(bid)
        if abo is None:
            return 404, {"error": "not_found"}
        dc = abo.get("display_config") or {}
        if methode == "GET":
            if isinstance(dc.get("placements"), dict):
                return 200, {"kind": kind, "stored": True,
                             "placements": copy.deepcopy(dc["placements"])}
            return 200, {"kind": kind, "stored": False,
                         "placements": {"version": 1, "rows": [], "outlook_reports": ["morning"]}}
        if methode == "PUT":
            abo.setdefault("display_config", {})["placements"] = copy.deepcopy(body)
            return 200, {"placements": copy.deepcopy(body)}
        return 405, {"error": "method_not_allowed"}

    def _auth(self, uid, methode, pfad, body):
        konto = self.konten[uid]
        p = konto["profil"]
        if pfad == "/api/auth/profile":
            if methode == "PUT":
                if "mail_to" in body and body["mail_to"] != p["mail_to"]:
                    return 403, {"error": "reauth_required"}
                if "sms_to" in body and body["sms_to"] != p["sms_to"]:
                    p["sms_to"], p["sms_verified_number"] = body["sms_to"], ""
                    if p["tier"] in _SMS_TARIFE:
                        self.sms_versand += 1
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
        return 404, {"error": "not_found"}

    def _daten(self, uid, methode, pfad, body):
        konto = self.konten[uid]
        d = konto["daten"]
        teile = pfad.strip("/").split("/")
        sammlung ={"trips": "trips", "locations": "locations", "metric-presets": "presets"}
        if teile[:2] == ["api", "compare"] and len(teile) >= 3 and teile[2] == "presets":
            if methode in ("POST", "PUT"):
                body = _vergleich_wie_go(body)
                if body is None:
                    return 400, {"error": "validation_error"}
            if methode == "POST" and len(teile) == 3 and _quote_voll(konto, "compare"):
                return 409, {"error": "quota_exceeded"}
            return self._crud(d["compare"], methode, teile[3:], body, uid)
        if (methode == "POST" and len(teile) == 2 and teile[1] in ("trips", "locations")
                and _quote_voll(konto, teile[1])):
            return 409, {"error": "quota_exceeded"}
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
                # Go: Name eindeutig je Art (kind route|vergleich, Lese-Default route),
                # ohne Gross-/Kleinschreibung (metric_preset_art_standard_test.go).
                art = body.get("kind") or "route"
                if any(v["name"].lower() == str(body.get("name", "")).lower()
                       and (v.get("kind") or "route") == art for v in ablage.values()):
                    return 409, {"error": "name_exists"}
                body = {**body, "id": body.get("id") or "mp-" + secrets.token_hex(3)}
            if (teile[1] == "trips" and methode in ("PUT", "PATCH") and len(teile) == 3
                    and teile[2] in ablage):
                body = self._trip_merge_wie_go(ablage[teile[2]], body)
            return self._crud(ablage, methode, teile[2:], body, uid)
        return 404, {"error": "not_found"}

    @staticmethod
    def _trip_merge_wie_go(ist, body):
        """#3151: internal/handler/trip.go:437-535: report_config, alert_channels und
        alert_channel_thresholds werden je Schluessel gemerged (fehlender Schluessel bleibt)."""
        body = copy.deepcopy(body)
        for feld in ("report_config", "alert_channels", "alert_channel_thresholds"):
            if isinstance(body.get(feld), dict):
                body[feld] = {**copy.deepcopy(ist.get(feld) or {}), **body[feld]}
        return body

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
        # Stempel "ALT" bildet die abgelaufene 30-Tage-Frist nach (model/premium_sms.go).
        stand = ("none" if not p["premium_sms_reply_to"]
                 else "stale" if p["premium_sms_reply_at"] == "ALT" else "fresh")
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
    for k in ("GZ_AUTH_USER", "GZ_AUTH_PASS", "GZ_PRUEFKONTO_USER", "GZ_PRUEFKONTO_PASS",
              "CORE_SHARED_SECRET"):
        monkeypatch.delenv(k, raising=False)
    env = tmp_path / "staging.env"
    # Wie die echte Staging-.env: GZ_AUTH_* ist das geteilte E2E-Konto "default" (von
    # anderen Staging-E2E-Tests genutzt); der Seed nimmt nur das eigene Pruefkonto.
    env.write_text(f"GZ_ENV=staging\nGZ_AUTH_USER=default\nGZ_AUTH_PASS=pw-default\n"
                   f"GZ_PRUEFKONTO_USER={PRUEF['user']}\nGZ_PRUEFKONTO_PASS=\"{PRUEF['pass']}\"\n"
                   f"CORE_SHARED_SECRET={SECRET}\n")
    server = _Fake()
    server.passwoerter["default"] = "pw-default"
    server.konten["default"] = _leeres_konto("default@example.invalid")
    return server, env


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
        # Fix-Loop 3 F002b: jedes Aus-Flag steht ausdruecklich als "aus" da (fehlend
        # zaehlt nicht), wind_direction ist nicht im Briefing.
        for aus in TRIP_AUS | {"wind_direction"}:
            assert quelle.get(aus) is False, (aus, quelle.get(aus))


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
    # Fix-Loop 3 F003: Vorlage Allgemein steht im gespeicherten Profil UND in der Ampel.
    assert vgl.get("profil") == "allgemein"
    assert vgl.get("display_config", {}).get("ampel", {}).get("template") == "allgemein"
    # Go speichert "HH:MM:SS" (der Fake normalisiert wie Go).
    assert vgl.get("morning_time") == "07:00:00" and vgl.get("morning_enabled") is True
    # F003d: gespeicherter Wert, nicht nur "vom Fake angenommen" (manual waere auch gueltig).
    assert vgl.get("schedule") == "daily"
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


def _datenschreiber(server):
    """Schreibende Aufrufe auf Trip/Orte/Vergleich/Vorlage (inkl. weather-config)."""
    return [(a["methode"], a["pfad"]) for a in server.aufrufe
            if a["methode"] in ("POST", "PUT", "PATCH")
            and a["pfad"].startswith(("/api/trips", "/api/locations", "/api/compare",
                                      "/api/metric-presets"))]


def test_ac4_f001_zweiter_lauf_ohne_schreibzugriff_trotz_go_normalisierung(fake):
    """F001: Go speichert morning_time als "07:00:00"; der Soll-Vergleich muss trotzdem
    greifen, sonst schreibt jeder Lauf den Vergleich per PUT neu."""
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    assert any(p.startswith("/api/compare") for _, p in _datenschreiber(server))
    server.aufrufe.clear()
    assert _lauf(mod, server, env) == 0
    assert _datenschreiber(server) == []


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
    vorher_default = server.zustand("default")
    assert _lauf(mod, server, env) == 0
    assert server.zustand("nutzer-b") == vorher
    # Das geteilte E2E-Konto "default" (GZ_AUTH_USER) bleibt unberuehrt.
    assert server.zustand("default") == vorher_default


# --- AC-6 / AC-7 / AC-12 / AC-13 -------------------------------------------------

@pytest.mark.parametrize("url", ["https://gregor20.henemm.com", "https://example.org",
                                 "http://localhost:8090",
                                 # F004: richtiger Host, aber ohne TLS
                                 "http://staging.gregor20.henemm.com",
                                 # Fix-Loop 3 F003: richtiger Host, aber fremder Port
                                 "https://staging.gregor20.henemm.com:8443"])
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


@pytest.mark.parametrize("fehlt", ["GZ_PRUEFKONTO_USER", "GZ_PRUEFKONTO_PASS", "CORE_SHARED_SECRET"])
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
    assert sorted(empf) == sorted([PRUEF["mail"], mod.ZWEIT_EMPFAENGER]), empf
    # SMS bestaetigt, Telegram verbunden, Premium-SMS frisch (exakte Sollwerte)
    assert prof["sms_to"] == mod.SMS_NUMMER and prof["sms_verified"] is True
    assert prof["telegram_chat_id"] == mod.TELEGRAM_CHAT_ID
    assert prof["premium_sms_reply_to"] == mod.INREACH_FROM
    assert prof["premium_sms_reply_state"] == "fresh"
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
    vorher, bremse, versand = server.zustand(), server.bremse, server.sms_versand
    server.aufrufe.clear()
    assert _lauf(mod, server, env) == 0
    assert server.zustand() == vorher
    assert server.sms_versand == versand, "zweiter Lauf darf keinen SMS-Code versenden"
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


def test_ac15c_trockenlauf_meldet_fremden_nutzer_kein_scharfer_lernaufruf(fake, capsys):
    """F003/M3: nennt der Trockenlauf ein anderes Konto, darf nichts gelernt werden."""
    mod = _modul()
    server, env = fake
    b = server.neues_konto("nutzer-b", "b@example.invalid")
    b["profil"]["tier"] = "premium"
    server.code_besitzer = "nutzer-b"
    vorher_b = server.zustand("nutzer-b")
    assert _lauf(mod, server, env) == 1
    assert server.zaehle("/api/internal/premium-sms-learn", scharf=True) == 0
    assert server.zustand("nutzer-b") == vorher_b
    assert _ausgabe_ids(capsys.readouterr().out) == (None, None)


# --- Fix-Loop 1: F002 / F003 -----------------------------------------------------

def _schreibaufrufe(server):
    return [a for a in server.aufrufe
            if a["methode"] in ("POST", "PUT", "PATCH") and a["pfad"] != "/api/auth/login"]


def test_ac11_f002_konto_ohne_mailadresse_exit1_kein_leerer_empfaenger(fake, capsys):
    """F002: leere Konto-Adresse nie als Empfaenger; 2 Empfaenger unerreichbar => Exit 1."""
    mod = _modul()
    server, env = fake
    p = server.konten[PRUEF["user"]]["profil"]
    p["email"] = p["mail_to"] = ""
    assert _lauf(mod, server, env) == 1
    aus = capsys.readouterr()
    assert _ausgabe_ids(aus.out) == (None, None)
    assert "Empfaenger" in aus.err
    assert _schreibaufrufe(server) == []
    assert _seed_daten(server)["compare"] == {}


def test_ac11_e_mail_unbestaetigt_exit1_ohne_schreibzugriff(fake, capsys):
    """AC-11 „E-Mail bestaetigt": auf Staging gibt es keinen versandfreien Weg zur
    Bestaetigung; ein unbestaetigtes Konto endet mit Exit 1 vor jedem Schreibzugriff."""
    mod = _modul()
    server, env = fake
    server.konten[PRUEF["user"]]["profil"]["email_verified"] = False
    vorher = server.zustand()
    assert _lauf(mod, server, env) == 1
    aus = capsys.readouterr()
    assert _ausgabe_ids(aus.out) == (None, None)
    assert "nicht bestätigt" in aus.err or "nicht bestaetigt" in aus.err, aus.err
    assert "E-Mail" in aus.err
    assert _schreibaufrufe(server) == []
    assert server.zustand() == vorher


def test_ac13_f003_env_nur_mit_gz_praefix_laeuft_mit_core_header(fake):
    """F003/M1: die Staging-.env fuehrt nur GZ_CORE_SHARED_SECRET."""
    mod = _modul()
    server, env = fake
    env.write_text(env.read_text().replace("CORE_SHARED_SECRET=", "GZ_CORE_SHARED_SECRET="))
    assert "\nCORE_SHARED_SECRET=" not in env.read_text()
    assert _lauf(mod, server, env) == 0
    intern = [a for a in server.aufrufe if a["host"] == "localhost:8091"]
    assert intern and all(a["headers"].get("x-gz-core-auth") == SECRET for a in intern)


def test_ac10_f003_login_mit_nutzer_default_exit1_ohne_schreibzugriff(fake):
    """F003/M2: liefert das Profil die id "default", bricht der Lauf vor jedem Schreiben ab."""
    mod = _modul()
    server, env = fake
    env.write_text(env.read_text()
                   .replace(f"GZ_PRUEFKONTO_USER={PRUEF['user']}", "GZ_PRUEFKONTO_USER=default")
                   .replace(f"GZ_PRUEFKONTO_PASS=\"{PRUEF['pass']}\"", "GZ_PRUEFKONTO_PASS=pw-default"))
    assert "GZ_PRUEFKONTO_USER=default" in env.read_text()
    assert "GZ_PRUEFKONTO_PASS=pw-default" in env.read_text()
    vorher = server.zustand()
    assert _lauf(mod, server, env) == 1
    assert _schreibaufrufe(server) == []
    assert server.zustand() == vorher


def test_ac13_f003_transportfehler_mit_secret_im_text_wird_bereinigt(fake, capsys, caplog):
    """F003/M4: ein Transportfehler, dessen Text das Secret traegt, verraet es nicht."""
    mod = _modul()
    server, env = fake
    innen = server.transport()

    def transport(methode, url, headers, body):
        if url.startswith(INTERN):
            raise ConnectionError(f"Verbindung abgelehnt, Kopfzeilen {headers}")
        return innen(methode, url, headers, body)

    code = mod.main(["--env-datei", str(env)], transport=transport)
    aus = capsys.readouterr()
    assert code == 1
    assert "ConnectionError" in aus.err
    assert SECRET not in aus.out + aus.err + caplog.text


def test_ac5_f003_vergleich_rmw_erhaelt_display_config_zusatzfeld(fake, capsys):
    """F003/M14: Merge statt Replace auch innerhalb display_config des Vergleichs."""
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    _, orte_id = _ausgabe_ids(capsys.readouterr().out)
    dc = _seed_daten(server)["compare"][orte_id]["display_config"]
    dc["zusatz_2967"] = {"bleibt": True}
    dc["region"] = "verstellt"
    assert _lauf(mod, server, env) == 0
    dc = _seed_daten(server)["compare"][orte_id]["display_config"]
    assert dc["region"] == "Westfalen", "Soll-Feld wird zurueckgesetzt"
    assert dc.get("zusatz_2967") == {"bleibt": True}, "RMW: Zusatzfeld muss bleiben"


def test_ac13_f003_fehlerkennung_mit_sonderzeichen_wird_nicht_ausgegeben(fake, capsys):
    """F003/M15: nur unverdaechtige Kennungen; freier Text der API erscheint nicht."""
    mod = _modul()
    server, env = fake
    leck = "Bearer tok=LECK-2967 <script>; rm -rf"
    server.stoerung[("POST", "/api/trips")] = (500, {"error": leck})
    assert _lauf(mod, server, env) == 1
    aus = capsys.readouterr()
    assert "HTTP 500" in aus.err
    assert "LECK-2967" not in aus.out + aus.err


# --- Fix-Loop 2: F001 / F002 / F003 / F004 ---------------------------------------

def test_ac5_f001_free_konto_mit_voller_quote_laeuft_durch(fake, capsys):
    """F001: Tarif Premium VOR dem Anlegen; ein Free-Konto mit 3 fremden Trips und
    2 fremden Vergleichen (Free-Quote ausgeschoepft) laeuft trotzdem mit Exit 0."""
    mod = _modul()
    server, env = fake
    d = _seed_daten(server)
    for i in range(3):
        d["trips"][f"fremd-t{i}"] = {"id": f"fremd-t{i}", "name": f"Fremd {i}", "stages": []}
    for i in range(2):
        d["compare"][f"fremd-v{i}"] = {"id": f"fremd-v{i}", "name": f"FremdV {i}",
                                       "location_ids": []}
    assert server.konten[PRUEF["user"]]["profil"]["tier"] == "free"
    fremde = json.dumps({k: dict(d[k]) for k in d}, sort_keys=True)
    assert _lauf(mod, server, env) == 0
    trip_id, orte_id = _ausgabe_ids(capsys.readouterr().out)
    assert trip_id in d["trips"] and orte_id in d["compare"]
    nachher = json.dumps({k: {i: v for i, v in d[k].items() if i.startswith("fremd")} for k in d},
                         sort_keys=True)
    assert nachher == fremde
    pfade = [a["pfad"] for a in server.aufrufe]
    assert pfade.index("/api/auth/staging-seed") < pfade.index("/api/trips")


def _ohne_seven_umgebung(monkeypatch):
    """Prozess-Umgebung darf den .env-Massstab nicht verfaelschen."""
    for k in list(os.environ):
        if k.upper() in ("GZ_SEVEN_API_KEY", "GZ_SEVEN_SANDBOX_KEY"):
            monkeypatch.delenv(k)


@pytest.mark.parametrize("zeile,erwartet", [("GZ_SEVEN_API_KEY=live-schluessel-2967", 2),
                                            ("GZ_SEVEN_API_KEY='live-schluessel-2967'", 2),
                                            # Fix-Loop 3 F001: Schreibweisen, die
                                            # python-dotenv/pydantic-settings als aktiv lesen
                                            ("export GZ_SEVEN_API_KEY=live-schluessel-2967", 2),
                                            ("gz_seven_api_key=live-schluessel-2967", 2),
                                            (" GZ_SEVEN_API_KEY = live-schluessel-2967", 2),
                                            ("export\tGz_Seven_Api_Key=live-schluessel-2967", 2),
                                            ("# GZ_SEVEN_API_KEY=live-schluessel-2967", 0),
                                            ("GZ_SEVEN_API_KEY=", 0)])
def test_ac7_f002_aktiver_live_sms_schluessel_exit2_ohne_aufruf(fake, capsys, monkeypatch,
                                                                zeile, erwartet):
    """F002: aktiver Live-Schluessel => Exit 2 vor jedem Aufruf, Wert nie ausgegeben;
    auskommentiert oder leer zaehlt nicht."""
    mod = _modul()
    server, env = fake
    env.write_text(env.read_text() + zeile + "\n")
    # Fix-Loop 3 F001: Massstab ist der echte Leser des Python-Core (pydantic-settings
    # mit python-dotenv): jede gesperrte Schreibweise wuerde dort live senden.
    _ohne_seven_umgebung(monkeypatch)
    from app.config import Settings
    live = Settings(_env_file=str(env)).seven_api_key
    assert bool(live) == (erwartet == 2), (zeile, live)
    assert _lauf(mod, server, env) == erwartet
    aus = capsys.readouterr()
    assert "live-schluessel-2967" not in aus.out + aus.err
    if erwartet == 2:
        assert server.aufrufe == []
        assert server.sms_versand == 0
    else:
        assert server.konten[PRUEF["user"]]["profil"]["sms_to"]


def test_ac13_f003a_core_secret_nie_an_oeffentliche_basis_url(fake):
    """F003a: der Core-Header geht nur an den Loopback, nie an die Staging-Basis-URL."""
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    oeffentlich = [a for a in server.aufrufe if a["host"] == "staging.gregor20.henemm.com"]
    assert oeffentlich
    for a in oeffentlich:
        assert "x-gz-core-auth" not in a["headers"], a["pfad"]
        assert SECRET not in json.dumps(a["headers"]), a["pfad"]


def test_ac14_f003b_veraltete_rueckadresse_wird_neu_gelernt(fake):
    """F003b: gleiche Nummer, aber Zustand "stale" => genau ein scharfer Lernaufruf."""
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    p = server.konten[PRUEF["user"]]["profil"]
    p["premium_sms_reply_at"] = "ALT"
    assert server._profil(PRUEF["user"])["premium_sms_reply_state"] == "stale"
    server.aufrufe.clear()
    assert _lauf(mod, server, env) == 0
    assert server.zaehle("/api/internal/premium-sms-learn", scharf=True) == 1
    assert server._profil(PRUEF["user"])["premium_sms_reply_state"] == "fresh"


def test_ac2_f003c_abweichende_vorlage_wird_per_merge_korrigiert(fake):
    """F003c: bestehende Vorlage mit abweichendem Metrik-Stand => PATCH mit Merge,
    Zusatzfeld bleibt, keine zweite Vorlage."""
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    vorlagen = _seed_daten(server)["presets"]
    (vid, vorlage), = [(i, v) for i, v in vorlagen.items() if v["name"] == "Mallorca Frühling"]
    for m in vorlage["metrics"]:
        m["enabled"] = m["metric_id"] == "temperature"
    vorlage["zusatz_2967"] = "bleibt"
    assert _lauf(mod, server, env) == 0
    nachher = [v for v in vorlagen.values() if v["name"] == "Mallorca Frühling"]
    assert len(nachher) == 1 and nachher[0]["id"] == vid
    assert {k for k, an in _flags(nachher[0]["metrics"]).items() if an} == TRIP_AN
    assert nachher[0].get("zusatz_2967") == "bleibt", "RMW: Zusatzfeld muss bleiben"


# --- Fix-Loop 3: F002 / F003 -----------------------------------------------------

def test_ac5_fl3_vergleich_rmw_erhaelt_top_level_zusatzfeld(fake, capsys):
    """F002a: Merge statt Replace auch auf oberster Ebene des Vergleichs."""
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    _, orte_id = _ausgabe_ids(capsys.readouterr().out)
    vgl = _seed_daten(server)["compare"][orte_id]
    vgl["zusatz_2967"] = {"bleibt": True}
    vgl["morning_time"] = "08:30:00"
    assert _lauf(mod, server, env) == 0
    vgl = _seed_daten(server)["compare"][orte_id]
    assert vgl["morning_time"] == "07:00:00", "Soll-Feld wird zurueckgesetzt"
    assert vgl.get("zusatz_2967") == {"bleibt": True}, "RMW: Zusatzfeld muss bleiben"


def test_ac11_fl3_gleiche_nummer_unbestaetigt_wird_bestaetigt(fake):
    """F002c: Nummer stimmt, ist aber unbestaetigt => staging-code + verify, Ende bestaetigt."""
    mod = _modul()
    server, env = fake
    p = server.konten[PRUEF["user"]]["profil"]
    p["sms_to"], p["sms_verified_number"] = mod.SMS_NUMMER, ""
    assert server._profil(PRUEF["user"])["sms_verified"] is False
    assert _lauf(mod, server, env) == 0
    assert server.zaehle("/api/auth/sms/staging-code") == 1
    assert server.zaehle("/api/auth/sms/verify") == 1
    prof = server._profil(PRUEF["user"])
    assert prof["sms_to"] == mod.SMS_NUMMER and prof["sms_verified"] is True


def test_ac4_fl3_zusaetzliche_etappe_wird_auf_vier_korrigiert(fake, capsys):
    """F002d: eine fuenfte Etappe am Seed-Trip wird auf genau die vier Mockup-Etappen
    zurueckgesetzt (Listenlaenge zaehlt beim Soll-Vergleich)."""
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    trip_id, _ = _ausgabe_ids(capsys.readouterr().out)
    trip = _seed_trip(server, trip_id)
    soll_ids = [e["id"] for e in trip["stages"]]
    trip["stages"].append({**copy.deepcopy(trip["stages"][-1]), "id": "zusatz-e5",
                           "date": "2026-02-27"})
    assert _lauf(mod, server, env) == 0
    etappen = _seed_trip(server, trip_id)["stages"]
    assert [e["id"] for e in etappen] == soll_ids
    assert [e["date"] for e in etappen] == ETAPPEN_TAGE


def _anstieg(etappe):
    hoehen = [w["elevation_m"] for w in etappe["waypoints"]]
    return sum(max(0, b - a) for a, b in zip(hoehen, hoehen[1:]))


def test_ac1_fl3_wegpunkthoehen_ergeben_mockup_anstieg(fake, capsys):
    """F003: Spec Schritt 3: Anstieg je Etappe 520/610/380/227 Hm (Summe 1.737 m),
    Etappen schliessen nahtlos aneinander an."""
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    trip_id, _ = _ausgabe_ids(capsys.readouterr().out)
    etappen = _seed_trip(server, trip_id)["stages"]
    assert [_anstieg(e) for e in etappen] == [520, 610, 380, 227]
    for vor, nach in zip(etappen, etappen[1:]):
        assert vor["waypoints"][-1]["elevation_m"] == nach["waypoints"][0]["elevation_m"]


# --- Live-Lauf-Nachzug: eigenes Pruefkonto statt geteiltem "default" -------------

def test_zugang_nur_aus_pruefkonto_schluesseln_gz_auth_allein_reicht_nicht(fake, capsys):
    """Die Staging-.env fuehrt GZ_AUTH_* fuer das geteilte E2E-Konto; fehlen die
    GZ_PRUEFKONTO_*-Schluessel, endet der Lauf mit Exit 2 vor jedem Aufruf, auch wenn
    GZ_AUTH_* auf ein gueltiges Konto zeigt."""
    mod = _modul()
    server, env = fake
    env.write_text(f"GZ_ENV=staging\nGZ_AUTH_USER={PRUEF['user']}\nGZ_AUTH_PASS={PRUEF['pass']}\n"
                   f"CORE_SHARED_SECRET={SECRET}\n")
    assert _lauf(mod, server, env) == 2
    assert server.aufrufe == []
    aus = capsys.readouterr()
    assert "GZ_PRUEFKONTO_USER" in aus.err and "GZ_PRUEFKONTO_PASS" in aus.err
    assert PRUEF["pass"] not in aus.out + aus.err


def test_login_laeuft_mit_pruefkonto_nicht_mit_gz_auth(fake):
    """Login traegt die GZ_PRUEFKONTO_*-Werte (Anfuehrungszeichen entfernt), nie default."""
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    logins = [a["body"] for a in server.aufrufe if a["pfad"] == "/api/auth/login"]
    assert logins == [{"username": PRUEF["user"], "password": PRUEF["pass"]}]


# --- F-R4-1: Skip nur beim Sollwert, nicht bei beliebigem verbundenem Wert --------

def test_fr41_andere_bestaetigte_sms_nummer_wird_auf_sollnummer_gesetzt(fake):
    mod = _modul()
    server, env = fake
    p = server.konten[PRUEF["user"]]["profil"]
    p["sms_to"] = p["sms_verified_number"] = "+491700000001"
    assert server._profil(PRUEF["user"])["sms_verified"] is True
    assert _lauf(mod, server, env) == 0
    prof = server._profil(PRUEF["user"])
    assert prof["sms_to"] == mod.SMS_NUMMER and prof["sms_verified"] is True
    assert server.zaehle("/api/auth/sms/verify") == 1


def test_fr41_andere_frische_rueckadresse_wird_neu_gelernt(fake):
    mod = _modul()
    server, env = fake
    p = server.konten[PRUEF["user"]]["profil"]
    p["premium_sms_reply_to"], p["premium_sms_reply_at"] = "+491700000002", "LAUFZEIT"
    assert server._profil(PRUEF["user"])["premium_sms_reply_state"] == "fresh"
    assert _lauf(mod, server, env) == 0
    assert server.zaehle("/api/internal/premium-sms-learn", scharf=True) == 1
    prof = server._profil(PRUEF["user"])
    assert prof["premium_sms_reply_to"] == mod.INREACH_FROM
    assert prof["premium_sms_reply_state"] == "fresh"


def test_fr41_andere_telegram_chat_id_wird_auf_soll_verbunden(fake):
    mod = _modul()
    server, env = fake
    server.konten[PRUEF["user"]]["profil"]["telegram_chat_id"] = "111"
    assert _lauf(mod, server, env) == 0
    assert server.zaehle("/api/internal/telegram-connect") == 1
    assert server.konten[PRUEF["user"]]["profil"]["telegram_chat_id"] == mod.TELEGRAM_CHAT_ID


# --- F-R4-2: Vorlagen-Art und Aggregation der Orte-Metriken ----------------------

def test_fr42_gleichnamige_vergleichsvorlage_bleibt_route_vorlage_wird_angelegt(fake):
    """Eine Vorlage „Mallorca Frühling“ der Art vergleich ist nicht die Seed-Vorlage:
    sie bleibt unveraendert, die Route-Vorlage entsteht daneben."""
    mod = _modul()
    server, env = fake
    fremd = {"id": "mp-vgl", "name": "Mallorca Frühling", "kind": "vergleich",
             "metrics": [{"metric_id": "wind", "enabled": True}]}
    _seed_daten(server)["presets"]["mp-vgl"] = copy.deepcopy(fremd)
    assert _lauf(mod, server, env) == 0
    vorlagen = _seed_daten(server)["presets"]
    assert vorlagen["mp-vgl"] == fremd
    route = [v for v in vorlagen.values() if v["name"] == "Mallorca Frühling"
             and (v.get("kind") or "route") == "route"]
    assert len(route) == 1
    assert {k for k, an in _flags(route[0]["metrics"]).items() if an} == TRIP_AN


# Mockup ORTE_METRICS mit der Aggregation der Go-Grundauswahl
# (internal/handler/vergleich_grundauswahl.go).
ORTE_SOLL = [{"metric_id": "temperature", "aggregation": "max"},
             # #3154 (AC-2): Mockup zeigt Max und Min („13°C / 4°C“).
             {"metric_id": "temperature", "aggregation": "min"},
             {"metric_id": "wind", "aggregation": "max"},
             {"metric_id": "gust", "aggregation": "max"},
             {"metric_id": "precipitation", "aggregation": "sum"},
             {"metric_id": "thunder", "aggregation": "max"},
             {"metric_id": "rain_probability", "aggregation": "max"},
             {"metric_id": "cloud_total", "aggregation": "avg"},
             {"metric_id": "sunshine", "aggregation": "sum"}]


def test_fr42_orte_metriken_mit_sollaggregation(fake, capsys):
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    _, orte_id = _ausgabe_ids(capsys.readouterr().out)
    aktiv = _seed_daten(server)["compare"][orte_id]["display_config"]["active_metrics"]
    assert aktiv == ORTE_SOLL


# --- Fix-Loop 5: F001 / F002 / F003 / F004 ---------------------------------------

def _profil_ohne_email_verified(server):
    """Transport, dessen Profil-Antwort das Feld ``email_verified`` nicht traegt."""
    innen = server.transport()

    def transport(methode, url, headers, body):
        status, antwort = innen(methode, url, headers, body)
        if url.endswith("/api/auth/profile") and isinstance(antwort, dict):
            antwort = {k: v for k, v in antwort.items() if k != "email_verified"}
        return status, antwort

    return transport


@pytest.mark.parametrize("fall", ["fehlt", "none"])
def test_ac11_fl5_email_verified_fehlt_oder_none_exit1_ohne_schreibzugriff(fake, capsys, fall):
    """F001: nur ausdruecklich ``true`` gilt als bestaetigt; fehlendes Feld oder None
    endet mit Exit 1 vor jedem Schreibzugriff."""
    mod = _modul()
    server, env = fake
    if fall == "none":
        server.konten[PRUEF["user"]]["profil"]["email_verified"] = None
        transport = server.transport()
    else:
        transport = _profil_ohne_email_verified(server)
    vorher = server.zustand()
    assert mod.main(["--env-datei", str(env)], transport=transport) == 1
    aus = capsys.readouterr()
    assert _ausgabe_ids(aus.out) == (None, None)
    assert "nicht bestätigt" in aus.err, aus.err
    assert _schreibaufrufe(server) == []
    assert server.zustand() == vorher


def test_ac11_fl5_fiktive_kanalwerte_sind_fest_und_erkennbar_fiktiv(fake):
    """F002: Festwerte statt Selbstvergleich gegen ``mod.<KONST>``. Die Werte sind die
    Identitaet des Pruefkontos auf Staging (Idempotenz: ein anderer Wert wuerde jeden
    Kanal neu verbinden); Spec: fiktive, eindeutige Testwerte, Zweitadresse ``.invalid``,
    SMS in der Form „+49 171 …“."""
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    soll = {"sms": "+491713920967", "inreach": "+491713920968",
            "telegram": "2967000001", "zweit": "pruefkonto-2967@gregor-test.invalid"}
    assert soll["zweit"].endswith(".invalid") and soll["sms"].startswith("+49171")
    assert len(set(soll.values())) == 4, "Kanalwerte muessen eindeutig sein"
    prof = server._profil(PRUEF["user"])
    assert prof["sms_to"] == soll["sms"] and prof["sms_verified"] is True
    assert prof["telegram_chat_id"] == soll["telegram"]
    assert prof["premium_sms_reply_to"] == soll["inreach"]
    (vgl,) = _seed_daten(server)["compare"].values()
    assert sorted(vgl["empfaenger"]) == sorted([PRUEF["mail"], soll["zweit"]])


@pytest.mark.parametrize("outcome", ["rate_limited", "already_linked", "would_skip", None])
def test_ac15_fl5_trockenlauf_ohne_would_learn_kein_scharfer_aufruf(fake, capsys, outcome):
    """F003: Trockenlauf nennt den eigenen Nutzer, aber nicht ``would_learn`` =>
    Exit 1 und kein scharfer Lernaufruf."""
    mod = _modul()
    server, env = fake
    innen = server.transport()

    def transport(methode, url, headers, body):
        status, antwort = innen(methode, url, headers, body)
        if url.endswith("/api/internal/premium-sms-learn") and (body or {}).get("dry_run"):
            antwort = {"status": "dry_run", "user_id": PRUEF["user"]}
            if outcome is not None:
                antwort["outcome"] = outcome
        return status, antwort

    assert mod.main(["--env-datei", str(env)], transport=transport) == 1
    assert server.zaehle("/api/internal/premium-sms-learn", scharf=False) == 1
    assert server.zaehle("/api/internal/premium-sms-learn", scharf=True) == 0
    assert server.konten[PRUEF["user"]]["profil"]["premium_sms_reply_to"] == ""
    assert _ausgabe_ids(capsys.readouterr().out) == (None, None)


@pytest.mark.parametrize("antwort", [{"code": ""}, {"code": None}, {}])
def test_ac11_fl5_link_code_leer_exit1_ohne_lernaufruf(fake, capsys, antwort):
    """F004: leerer Verknuepfungscode => Exit 1 mit Meldung, kein Aufruf an
    /api/internal/premium-sms-learn (auch kein Trockenlauf)."""
    mod = _modul()
    server, env = fake
    server.stoerung[("POST", "/api/auth/premium-sms-link-code")] = (200, antwort)
    assert _lauf(mod, server, env) == 1
    aus = capsys.readouterr()
    assert "premium-sms-link-code ohne Code" in aus.err, aus.err
    assert server.zaehle("/api/internal/premium-sms-learn") == 0
    assert _ausgabe_ids(aus.out) == (None, None)


# --- #3151: Kanalauswahl, Alarm-Kanaele und Schwellen laut Mockup ------------------
# Festgelegte Schnittstelle (Tech-Lead-Entscheidung in RED), Modul-Ebene im Seed-Skript:
#   ALARM_SCHWELLEN: dict {"email": "LOW", "telegram": "LOW", "sms": "MODERATE",
#                          "premium_sms": "HIGH"}
#   soll_kanalauswahl_trip() -> {"report_config": {send_email/telegram/sms/premium_sms},
#       "alert_channels": {4 Kanaele True}, "alert_channel_thresholds": ALARM_SCHWELLEN-Kopie}
#   soll_kanalauswahl_vergleich() -> {"send_email", "send_telegram", "send_sms",
#       "send_premium_sms" (top-level), "alert_channels" (alle 4 explizit),
#       "alert_channel_thresholds"}
# Beide ohne Argumente, rein, geben bei jedem Aufruf frische Kopien zurueck.

SCHWELLEN_3151 = {"email": "LOW", "telegram": "LOW", "sms": "MODERATE", "premium_sms": "HIGH"}
BRIEFING_3151 = {"send_email": True, "send_telegram": True, "send_sms": False,
                 "send_premium_sms": False}
ALARM_ALLE_3151 = {"email": True, "telegram": True, "sms": True, "premium_sms": True}


def test_3151_ac1_soll_funktionen_liefern_exakte_werte_ohne_netz():
    mod = _modul()
    assert mod.ALARM_SCHWELLEN == SCHWELLEN_3151
    assert mod.soll_kanalauswahl_trip() == {"report_config": BRIEFING_3151,
                                            "alert_channels": ALARM_ALLE_3151,
                                            "alert_channel_thresholds": SCHWELLEN_3151}
    assert mod.soll_kanalauswahl_vergleich() == {**BRIEFING_3151,
                                                 "alert_channels": ALARM_ALLE_3151,
                                                 "alert_channel_thresholds": SCHWELLEN_3151}
    # frische Kopien: Aufrufer duerfen nichts Geteiltes veraendern
    mod.soll_kanalauswahl_trip()["alert_channels"]["email"] = False
    mod.soll_kanalauswahl_vergleich()["alert_channel_thresholds"]["sms"] = "X"
    assert mod.soll_kanalauswahl_trip()["alert_channels"]["email"] is True
    assert mod.soll_kanalauswahl_vergleich()["alert_channel_thresholds"]["sms"] == "MODERATE"


def _kanal_ist(daten, trip):
    kern = {"alert_channels": daten.get("alert_channels"),
            "alert_channel_thresholds": daten.get("alert_channel_thresholds")}
    if trip:
        return {"report_config": {k: (daten.get("report_config") or {}).get(k)
                                  for k in BRIEFING_3151}, **kern}
    return {**{k: daten.get(k) for k in BRIEFING_3151}, **kern}


def test_3151_ac1_seed_setzt_kanalauswahl_an_trip_und_vergleich(fake, capsys):
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    trip_id, orte_id = _ausgabe_ids(capsys.readouterr().out)
    assert _kanal_ist(_seed_trip(server, trip_id), True) == {
        "report_config": BRIEFING_3151, "alert_channels": ALARM_ALLE_3151,
        "alert_channel_thresholds": SCHWELLEN_3151}
    assert _kanal_ist(_seed_daten(server)["compare"][orte_id], False) == {
        **BRIEFING_3151, "alert_channels": ALARM_ALLE_3151,
        "alert_channel_thresholds": SCHWELLEN_3151}


def test_3151_ac2_fremdfelder_und_fremder_kanal_bleiben_nur_soll_wird_gesetzt(fake, capsys):
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    trip_id, orte_id = _ausgabe_ids(capsys.readouterr().out)
    trip = _seed_trip(server, trip_id)
    vgl = _seed_daten(server)["compare"][orte_id]
    # Fremdes + verstellte Sollwerte in Trip und Vergleich
    trip.setdefault("report_config", {}).update({"morning_time": "06:30:00", "send_telegram": False,
                                                 "zusatz_kanal": "bleibt"})
    trip["alert_channels"] = {**(trip.get("alert_channels") or {}), "sms": False, "zusatz_kanal": True}
    trip["alert_channel_thresholds"] = {**(trip.get("alert_channel_thresholds") or {}),
                                        "sms": "LOW", "zusatz_kanal": "HIGH"}
    vgl.update({"send_telegram": False, "zusatz_3151": {"bleibt": True}})
    vgl["alert_channels"] = {**(vgl.get("alert_channels") or {}), "premium_sms": False,
                             "zusatz_kanal": True}
    vgl["alert_channel_thresholds"] = {**(vgl.get("alert_channel_thresholds") or {}),
                                       "premium_sms": "LOW", "zusatz_kanal": "HIGH"}
    assert _lauf(mod, server, env) == 0
    trip = _seed_trip(server, trip_id)
    vgl = _seed_daten(server)["compare"][orte_id]
    assert trip["report_config"].get("send_telegram") is True
    assert trip.get("alert_channels", {}).get("sms") is True
    assert trip.get("alert_channel_thresholds", {}).get("sms") == "MODERATE"
    assert trip["report_config"]["morning_time"] == "06:30:00"
    assert trip["report_config"]["zusatz_kanal"] == "bleibt"
    assert trip["alert_channels"]["zusatz_kanal"] is True
    assert trip["alert_channel_thresholds"]["zusatz_kanal"] == "HIGH"
    assert vgl["send_telegram"] is True
    assert vgl["alert_channels"]["premium_sms"] is True
    assert vgl.get("alert_channel_thresholds", {}).get("premium_sms") == "HIGH"
    assert vgl["zusatz_3151"] == {"bleibt": True}
    assert vgl["alert_channels"]["zusatz_kanal"] is True
    assert vgl["alert_channel_thresholds"]["zusatz_kanal"] == "HIGH"


def test_3151_ac3_zweiter_lauf_schreibfrei_trotz_go_ableitung_von_alert_channels(fake):
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    (trip,) = _seed_daten(server)["trips"].values()
    (vgl,) = _seed_daten(server)["compare"].values()
    # Voraussetzung: Kanalauswahl steht (sonst waere "schreibfrei" trivial)
    assert vgl.get("alert_channel_thresholds") == SCHWELLEN_3151
    assert trip.get("alert_channels") == ALARM_ALLE_3151
    vorher = server.zustand()
    server.aufrufe.clear()
    assert _lauf(mod, server, env) == 0
    assert _datenschreiber(server) == []
    assert server.zustand() == vorher


def test_3151_ac4_zweiter_nutzer_mit_kanalfeldern_bleibt_byte_gleich(fake):
    mod = _modul()
    server, env = fake
    b = server.neues_konto("nutzer-b", "b@example.invalid")
    b["daten"]["trips"]["b-trip"] = {
        "id": "b-trip", "name": "B", "stages": [],
        "report_config": {"send_email": True, "send_telegram": False, "send_sms": True,
                          "send_premium_sms": False},
        "alert_channels": {"email": True, "telegram": False, "sms": False, "premium_sms": False},
        "alert_channel_thresholds": {"email": "HIGH", "sms": "HIGH"}}
    b["daten"]["compare"]["b-vgl"] = {
        "id": "b-vgl", "name": "BV", "location_ids": [], "schedule": "daily",
        "send_email": True, "send_telegram": False, "send_sms": False, "send_premium_sms": False,
        "alert_channels": {"email": True, "telegram": False, "sms": False, "premium_sms": False},
        "alert_channel_thresholds": {"email": "HIGH"}}
    vorher = server.zustand("nutzer-b")
    vorher_default = server.zustand("default")
    assert _lauf(mod, server, env) == 0
    # Seed hat die Kanalauswahl beim Pruefkonto gesetzt (nicht trivial)
    (vgl,) = _seed_daten(server)["compare"].values()
    assert vgl.get("alert_channel_thresholds") == SCHWELLEN_3151
    assert server.zustand("nutzer-b") == vorher
    assert server.zustand("default") == vorher_default


# --- #3154 Fix-Loop 1: Tabelle „Was steht wo“ im Gesamtlauf (F001, F003) -----------

def _tabellen_puts(server):
    return [a for a in server.aufrufe
            if a["methode"] == "PUT" and a["pfad"].startswith("/api/briefings/")
            and a["pfad"].endswith("/placements")]


def test_3154_f001_seed_schreibt_beide_tabellen_genau_einmal(fake, capsys):
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    trip_id, orte_id = _ausgabe_ids(capsys.readouterr().out)
    puts = _tabellen_puts(server)
    assert [(a["pfad"], a["query"]) for a in puts] == [
        (f"/api/briefings/{trip_id}/placements", "kind=route"),
        (f"/api/briefings/{orte_id}/placements", "kind=vergleich")]
    assert puts[0]["body"] == mod.tabelle_trip_soll()
    assert puts[1]["body"] == mod.tabelle_orte_soll()
    d = _seed_daten(server)
    assert d["trips"][trip_id]["display_config"]["placements"] == mod.tabelle_trip_soll()
    assert d["compare"][orte_id]["display_config"]["placements"] == mod.tabelle_orte_soll()
    server.aufrufe.clear()
    assert _lauf(mod, server, env) == 0
    assert _tabellen_puts(server) == [], "zweiter Lauf schreibt die Tabelle erneut"


def test_3154_f003_tabelle_nur_ueber_den_tabellen_endpunkt(fake):
    """Kein anderer Schreibweg traegt ``placements``; der Tabellen-PUT traegt nur die Tabelle."""
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    for a in server.aufrufe:
        if a["methode"] in ("POST", "PUT", "PATCH") and a not in _tabellen_puts(server):
            assert "placements" not in json.dumps(a["body"] or {}), (a["methode"], a["pfad"])
    for a in _tabellen_puts(server):
        assert set(a["body"]) == {"version", "rows", "outlook_reports"}


def test_3154_f003_gespeicherte_tabelle_mit_abwahl_und_zusatzschluessel(fake, capsys):
    """Gespeicherte Tabelle mit abgewaehltem Haken: der Seed stellt das Soll her (alle Haken
    an), behaelt aber unbekannte Schluessel oben (Merge) und die uebrigen Abo-Felder."""
    mod = _modul()
    server, env = fake
    assert _lauf(mod, server, env) == 0
    trip_id, _ = _ausgabe_ids(capsys.readouterr().out)
    trip = _seed_daten(server)["trips"][trip_id]
    alt = mod.tabelle_trip_soll()
    alt["rows"][0]["places"] = {"email": False}
    alt["zukunft"] = {"x": 1}
    trip["display_config"]["placements"] = alt
    vorher_rest = {k: v for k, v in trip["display_config"].items() if k != "placements"}
    server.aufrufe.clear()
    assert _lauf(mod, server, env) == 0
    puts = _tabellen_puts(server)
    assert len(puts) == 1 and puts[0]["query"] == "kind=route"
    neu = trip["display_config"]["placements"]
    assert neu == {**mod.tabelle_trip_soll(), "zukunft": {"x": 1}}
    assert {k: v for k, v in trip["display_config"].items() if k != "placements"} == vorher_rest
