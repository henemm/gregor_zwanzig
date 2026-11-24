#!/usr/bin/env python3
"""Staging-Pruefkonto mit den Mockup-Beispieldaten fuellen (Issue #2967, Epic #2913).

Spec:    docs/specs/modules/feat_2967_pruefkonto_mockupdaten.md
Runbook: docs/runbooks/staging_pruefkonto_seed.md

Legt im Staging-Pruefkonto (``GZ_PRUEFKONTO_USER``/``GZ_PRUEFKONTO_PASS`` aus der
Staging-``.env``; nicht ``GZ_AUTH_*``, das ist das geteilte E2E-Konto ``default``)
idempotent an bzw. gleicht ab: Trip „GR221 Mallorca" mit Wetterkonfiguration
(Vorlage ``alpen-trekking``, Flags wie ``TRIP_METRICS``/``TRIP_OFF`` im Mockup),
eigene Vorlage „Mallorca Frühling", drei Orte und den Orts-Vergleich „Münsterland",
dazu die vier Kanaele (E-Mail, SMS, Telegram, Premium-SMS) wie ``konto()`` im
Mockup und (#3154) die Tabelle „Was steht wo“ von Trip und Orts-Vergleich in
Mockup-Reihenfolge und -Formaten (``PUT /api/briefings/{id}/placements``). Telegram und Premium-SMS laufen ueber die internen Routen direkt am
Loopback der Staging-Go-API (``http://localhost:8091``) mit Core-Auth-Header.

Aufruf:  uv run python scripts/staging_pruefkonto_mockupdaten.py
         [--basis-url URL] [--intern-url URL] [--env-datei PFAD]
Exit:    0 = Soll-Zustand erreicht; stdout: ELEMENTLISTE_TRIP_ID=…, ELEMENTLISTE_ORTE_ID=…
         1 = API-/Datenfehler (Login, E-Mail des Kontos unbestaetigt, Statuscode,
             409 fremde Chat-ID, 429 Ratebremse)
         2 = Aufruf-/Schutzfehler (Prod-/fremde URL, unzulaessiges Loopback-Ziel,
             fehlende .env-Schluessel inkl. Core-Secret, aktiver Live-SMS-Schluessel
             GZ_SEVEN_API_KEY in der .env)

Reihenfolge: Tarif Premium VOR dem Anlegen der Datensaetze (sonst greift die
Free-Quote der Go-API: 3 Trips, 2 Vergleiche, 10 Orte => 409 quota_exceeded). Im
Premium-Tarif loest ``PUT sms_to`` einen Code-Versand aus; darum bricht das Skript
ab, bevor es irgendetwas schreibt, wenn die Staging-.env einen aktiven Live-Schluessel
fuehrt (Staging versendet nur ueber den Sandbox-Schluessel).

Schreibt nur Read-Modify-Write auf eigene Seed-Datensaetze (nie Replace, nie fremde
Datensaetze). Das Core-Secret bleibt im Speicher und erscheint in keiner Ausgabe.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

STAGING_ENV = Path("/home/hem/gregor_zwanzig_staging/.env")
BASIS_URL = "https://staging.gregor20.henemm.com"
INTERN_URL = "http://localhost:8091"
_STAGING_HOST = "staging.gregor20.henemm.com"
_INTERN_HOSTS = ("localhost", "127.0.0.1")
_INTERN_PORT = 8091
_CORE_HEADER = "X-GZ-Core-Auth"
# Staging-.env fuehrt das Secret als GZ_CORE_SHARED_SECRET (envconfig-Praefix GZ),
# CORE_SHARED_SECRET wird ebenfalls angenommen.
_SECRET_SCHLUESSEL = ("GZ_CORE_SHARED_SECRET", "CORE_SHARED_SECRET")
# Eigenes Pruefkonto (Muster GZ_E2E_EN_*, scripts/staging_e2e_user_en.py).
_ZUGANG_SCHLUESSEL = ("GZ_PRUEFKONTO_USER", "GZ_PRUEFKONTO_PASS")
# Live-Schluessel von seven.io (src/app/config.py: seven_api_key); Staging nur Sandbox.
_LIVE_SMS_SCHLUESSEL = "GZ_SEVEN_API_KEY"

TRIP_ID = "gz2967-gr221-mallorca"
TRIP_NAME = "GR221 Mallorca"
# #3327: zweiter, frei erfundener Trip, der archiviert im Pruefkonto liegt (Archiv-Bild).
ARCHIV_TRIP_ID = "gz2967-archiv-kuestenpfad"
ARCHIV_TRIP_NAME = "Küstenpfad Probelauf"
VORLAGE_NAME = "Mallorca Frühling"
VERGLEICH_NAME = "Münsterland"
# Fiktive, eindeutige Kanalwerte des Pruefkontos (kein Versand an echte Geraete).
SMS_NUMMER = "+491713920967"
TELEGRAM_CHAT_ID = "2967000001"
INREACH_FROM = "+491713920968"
ZWEIT_EMPFAENGER = "pruefkonto-2967@gregor-test.invalid"

# Mockup TRIP_METRICS (Reihenfolge) + TRIP_OFF; wind_direction nur Anzeige (aus).
_TRIP_REIHE = ("temperature", "temperature_night", "wind_chill", "wind", "gust", "wind_direction",
            "precipitation", "thunder", "rain_probability", "visibility", "cloud_low",
            "uv_index", "freezing_level", "snowfall_limit")
_TRIP_AUS = ("cloud_total", "sunshine", "fresh_snow", "snow_depth", "dewpoint", "humidity",
             "pressure")
# Mockup ORTE_METRICS mit Aggregation wie internal/handler/vergleich_grundauswahl.go.
# #3154: Temperatur mit Max UND Min wie das Mockup („13°C / 4°C“, „D 13C L 4C“).
_ORTE_METRIKEN = (("temperature", "max"), ("temperature", "min"), ("wind", "max"), ("gust", "max"),
                  ("precipitation", "sum"), ("thunder", "max"), ("rain_probability", "max"),
                  ("cloud_total", "avg"), ("sunshine", "sum"))

# #3154: Tabelle „Was steht wo“ (display_config.placements, api_contract.md) wie das
# Mockup Fassung 4. Trip-Folge = TRIP_METRICS ohne die ausgeschaltete Windrichtung
# (18 Zeilen inkl. der fuenf Nur-Anzeige-Zeilen), Orte-Folge = ORTE_METRICS ohne sie.
_TABELLE_TRIP = ("temperature", "temperature_night", "temperature_day_low",
                 "temperature_day_high", "wind_chill", "wind_chill_night", "wind_chill_day_low",
                 "wind_chill_day_high", "wind", "gust", "precipitation", "thunder",
                 "rain_probability", "visibility", "cloud_low", "uv_index", "freezing_level",
                 "snowfall_limit")
_TABELLE_ORTE = ("temperature", "wind", "gust", "precipitation", "thunder", "rain_probability",
                 "cloud_total", "sunshine")
# Stellen mit zwei Formen (metric_catalog.STELLEN_ZWEI_FORMEN; Gewitter nur E-Mail, AC-5).
_ALLE_FORMSTELLEN = ("email", "telegram", "hourly", "outlook")
_ZWEI_FORMEN = {"wind": _ALLE_FORMSTELLEN, "gust": _ALLE_FORMSTELLEN,
                "precipitation": _ALLE_FORMSTELLEN, "rain_probability": _ALLE_FORMSTELLEN,
                "thunder": ("email",),
                "cloud_low": _ALLE_FORMSTELLEN, "cloud_total": _ALLE_FORMSTELLEN,
                "sunshine": ("email", "telegram", "outlook")}
# Mockup ``defFmt``: Einfach fuer Windrichtung, Gewitter, Bewoelkung, Sonne; sonst Roh.
_EINFACH = ("wind_direction", "thunder", "cloud_total", "cloud_low", "cloud_mid", "cloud_high",
            "sunshine")
# Mockup ``outM:false, outA:true``: Ausblick nur im Abend-Briefing.
_AUSBLICK = ("evening",)

# Etappen: Wegpunkte auf einer Linie Port d'Andratx -> Deià; Strecke je Etappe wie im
# Mockup (7,8/8,4/6,9/8,4 km), Anstieg ueber den Mittelpunkt (520/610/380/227 Hm).
_ETAPPEN = (
    ("2026-02-23", ("Port d'Andratx", 39.5436, 2.388, 5), (39.56869, 2.41979, 525),
     ("Estellencs", 39.59377, 2.4516, 150)),
    ("2026-02-24", ("Estellencs", 39.59377, 2.4516, 150), (39.62079, 2.48586, 760),
     ("Esporles", 39.64779, 2.52015, 200)),
    ("2026-02-25", ("Esporles", 39.64779, 2.52015, 200), (39.66998, 2.54831, 580),
     ("Valldemossa", 39.69217, 2.57649, 420)),
    ("2026-02-26", ("Valldemossa", 39.69217, 2.57649, 420), (39.71919, 2.6108, 647),
     ("Deià", 39.74619, 2.64514, 150)),
)
# #3327: fiktive Etappen in der Vergangenheit (Datum, Start, Ziel).
_ARCHIV_ETAPPEN = (
    ("2026-06-12", ("Dünenhof", 54.1012, 8.6034, 4), ("Leuchtturm", 54.1265, 8.6511, 12)),
    ("2026-06-13", ("Leuchtturm", 54.1265, 8.6511, 12), ("Deichkrug", 54.1508, 8.7023, 6)),
    ("2026-06-14", ("Deichkrug", 54.1508, 8.7023, 6), ("Fährhafen", 54.1741, 8.7489, 3)),
)
_ORTE = (("gz2967-muenster", "Münster", 51.9607, 7.6261, 60),
         ("gz2967-telgte", "Telgte", 51.9819, 7.7856, 52),
         ("gz2967-tecklenburg", "Tecklenburg", 52.2196, 7.8126, 235))

# #3151: Kanalauswahl laut Mockup (mockup-hub-fassung4.html Z.373-374, ``st[ctx].sw.ch``):
# Briefing E-Mail + Telegram, Alarme auf allen vier Kanaelen; Dringlichkeit
# „gering/mittel/hoch" = LOW/MODERATE/HIGH (src/services/alert_urgency.py).
ALARM_SCHWELLEN = {"email": "LOW", "telegram": "LOW", "sms": "MODERATE", "premium_sms": "HIGH"}
_BRIEFING_KANAELE = {"send_email": True, "send_telegram": True, "send_sms": False,
                     "send_premium_sms": False}
_ALARM_KANAELE = ("email", "telegram", "sms", "premium_sms")
# Unterobjekte, die feldweise (je Kanalschluessel) gemerged werden; Fremdschluessel bleiben.
_KANAL_UNTEROBJEKTE = ("report_config", "alert_channels", "alert_channel_thresholds")

_WERKZEUG = Path(__file__).resolve().parents[1] / ".claude" / "tools" / "staging_befehl_pruefen.py"


class AufrufFehler(RuntimeError):
    """Schutz- oder Aufruffehler (Exit 2): vor jedem Netzaufruf."""


class SeedFehler(RuntimeError):
    """API- oder Datenfehler (Exit 1)."""


def _http_transport():
    """Echter HTTP-Rand mit Cookie-Sitzung (aus dem gemeinsamen Staging-Werkzeug)."""
    spec = importlib.util.spec_from_file_location("_staging_befehl_pruefen", _WERKZEUG)
    werkzeug = sys.modules.setdefault(spec.name, importlib.util.module_from_spec(spec))
    spec.loader.exec_module(werkzeug)
    return werkzeug.http_transport()


def lade_env(pfad: Path) -> dict[str, str]:
    """``KEY=VALUE``-Zeilen der Datei (Kommentare/Leerzeilen ignoriert).

    Wie python-dotenv: ein fuehrendes ``export `` gehoert nicht zum Schluesselnamen,
    Leerzeichen um ``=`` zaehlen nicht. Die Gross-/Kleinschreibung bleibt erhalten.
    """
    werte: dict[str, str] = {}
    try:
        zeilen = Path(pfad).read_text(encoding="utf-8").splitlines()
    except OSError:
        return werte
    for z in zeilen:
        if "=" in z and not z.lstrip().startswith("#"):
            k, v = z.split("=", 1)
            werte[re.sub(r"^export\s+", "", k.strip())] = v.strip().strip("'\"")
    return werte


def pruefe_basis_url(url: str) -> str:
    """Nur die Staging-URL (https, ohne Port); Produktion und fremde Hosts => Exit 2."""
    teile = urlsplit(url)
    if teile.scheme != "https" or teile.hostname != _STAGING_HOST or teile.port is not None:
        raise AufrufFehler("Basis-URL ist nicht Staging (https://staging.gregor20.henemm.com) "
                           "- Abbruch vor dem Login")
    return f"https://{_STAGING_HOST}"


def pruefe_intern_url(url: str) -> str:
    """Nur der Loopback der Staging-Go-API (http://localhost:8091 bzw. 127.0.0.1:8091)."""
    teile = urlsplit(url)
    if (teile.scheme != "http" or teile.hostname not in _INTERN_HOSTS
            or teile.port != _INTERN_PORT or teile.path not in ("", "/")):
        raise AufrufFehler("Loopback-Ziel muss http://localhost:8091 sein - Abbruch vor jedem Aufruf")
    return f"http://{teile.hostname}:{_INTERN_PORT}"


def zugang_aus_env(env: dict) -> tuple[str, str, str]:
    """(Nutzer, Passwort, Core-Secret); fehlt ein Schluessel => Exit 2 (Wert nie genannt).

    Zugang ist das eigene Pruefkonto (``GZ_PRUEFKONTO_*``), nie ``GZ_AUTH_*``: das ist
    das geteilte Konto ``default`` der uebrigen Staging-E2E-Tests (Premium-Tarif und
    verbundene Kanaele wuerden sie beeinflussen).
    """
    secret = next((env[k] for k in _SECRET_SCHLUESSEL if env.get(k)), "")
    fehlend = [k for k in _ZUGANG_SCHLUESSEL if not env.get(k)]
    if not secret:
        fehlend.append("GZ_CORE_SHARED_SECRET")
    if fehlend:
        raise AufrufFehler(f".env-Schluessel fehlen: {', '.join(fehlend)}")
    return env[_ZUGANG_SCHLUESSEL[0]], env[_ZUGANG_SCHLUESSEL[1]], secret


def pruefe_kein_live_versand(env: dict) -> None:
    """Aktiver ``GZ_SEVEN_API_KEY`` (nicht auskommentiert, nicht leer) => Exit 2.

    Der Tarif steht vor dem SMS-Schritt auf Premium, ``PUT sms_to`` loest dann einen
    Code-Versand aus; der darf nur in die Sandbox gehen. Der Wert wird nie genannt.
    pydantic-settings liest Schluessel ohne Ruecksicht auf Gross-/Kleinschreibung,
    darum zaehlt jede Schreibweise (``gz_seven_api_key`` ebenso).
    """
    if any(k.upper() == _LIVE_SMS_SCHLUESSEL and v for k, v in env.items()):
        raise AufrufFehler(f"{_LIVE_SMS_SCHLUESSEL} ist in der .env aktiv - SMS-Schritt "
                           "wuerde echt versenden, Abbruch vor jedem Schreibzugriff")


def _enthaelt(ist, soll) -> bool:
    """True, wenn ``ist`` alle Soll-Felder traegt (vom Server ergaenzte Felder zaehlen nicht)."""
    if isinstance(soll, dict):
        return isinstance(ist, dict) and all(k in ist and _enthaelt(ist[k], v)
                                             for k, v in soll.items())
    if isinstance(soll, list):
        return (isinstance(ist, list) and len(ist) == len(soll)
                and all(_enthaelt(i, s) for i, s in zip(ist, soll)))
    return ist == soll


def _merge(ist: dict, soll: dict) -> dict:
    """Read-Modify-Write: Soll-Felder ueber ``ist``; die Kanal-Unterobjekte werden je
    Schluessel gemerged (fremde Kanalschluessel und Fremdfelder bleiben, nie Replace)."""
    neu = {**ist, **soll}
    for feld in _KANAL_UNTEROBJEKTE:
        if isinstance(soll.get(feld), dict):
            neu[feld] = {**(ist.get(feld) or {}), **soll[feld]}
    return neu


def _kennung(antwort) -> str:
    """Nur unverdaechtige Fehlerkennungen der API (z. B. ``chat_id_already_linked``)."""
    if not isinstance(antwort, dict):
        return ""
    for feld in ("error", "reason", "outcome"):
        wert = antwort.get(feld)
        if isinstance(wert, str) and re.fullmatch(r"[\w.\-]{1,60}", wert):
            return f" ({wert})"
    return ""


# --- Soll-Daten ------------------------------------------------------------------

def _wegpunkt(sid: str, i: int, name: str, lat: float, lon: float, hoehe: int) -> dict:
    return {"id": f"{sid}-w{i}", "name": name, "lat": lat, "lon": lon, "elevation_m": hoehe}


def soll_trip() -> dict:
    etappen = []
    for n, (datum, von, mitte, bis) in enumerate(_ETAPPEN, start=1):
        sid = f"{TRIP_ID}-e{n}"
        etappen.append({"id": sid, "name": f"{von[0]} → {bis[0]}", "date": datum, "waypoints": [
            _wegpunkt(sid, 1, *von), _wegpunkt(sid, 2, f"Anstieg {von[0]}", *mitte),
            _wegpunkt(sid, 3, *bis)]})
    return {"id": TRIP_ID, "name": TRIP_NAME, "region": "Mallorca", "stages": etappen}


def soll_archiv_trip() -> dict:
    """#3327: fiktiver Archiv-Trip ohne Kanal-/Wetter-/Tabellenkonfiguration. Nie
    ``archived_at`` im Soll: ``_merge`` uebernimmt es aus dem Ist-Stand (PUT reaktiviert nicht)."""
    etappen = []
    for n, (datum, von, bis) in enumerate(_ARCHIV_ETAPPEN, start=1):
        sid = f"{ARCHIV_TRIP_ID}-e{n}"
        etappen.append({"id": sid, "name": f"{von[0]} → {bis[0]}", "date": datum,
                        "waypoints": [_wegpunkt(sid, 1, *von), _wegpunkt(sid, 2, *bis)]})
    return {"id": ARCHIV_TRIP_ID, "name": ARCHIV_TRIP_NAME, "region": "Nordsee (fiktiv)",
            "stages": etappen}


def soll_kanalauswahl_trip() -> dict:
    """#3151: nur die Soll-Teilobjekte; Flachfelder (send_*) leitet der Go-Store ab."""
    return {"report_config": dict(_BRIEFING_KANAELE),
            "alert_channels": {k: True for k in _ALARM_KANAELE},
            "alert_channel_thresholds": dict(ALARM_SCHWELLEN)}


def soll_kanalauswahl_vergleich() -> dict:
    """#3151: send_* top-level, ``alert_channels`` explizit (sonst leitet der Store es
    aus den Flags ab: SMS/Premium waeren aus)."""
    return {**_BRIEFING_KANAELE,
            "alert_channels": {k: True for k in _ALARM_KANAELE},
            "alert_channel_thresholds": dict(ALARM_SCHWELLEN)}


def soll_wetter() -> dict:
    ids = list(_TRIP_REIHE) + list(_TRIP_AUS)
    an = {m: m in _TRIP_REIHE and m != "wind_direction" for m in ids}
    return {"metrics": [{"metric_id": m, "enabled": an[m]} for m in ids],
            "ampel": {"template": "alpen-trekking",
                      "metrics": {m: {"enabled": an[m]} for m in ids}}}


def soll_empfaenger(profil: dict) -> list[str]:
    """Konto-Adresse + fiktive Zweitadresse; leere Adresse nie, weniger als 2 => Exit 1."""
    konto = str(profil.get("mail_to") or profil.get("email") or "").strip()
    empfaenger = [a for a in (konto, ZWEIT_EMPFAENGER) if a]
    if len(empfaenger) != 2:
        raise SeedFehler("Konto ohne Mail-Adresse - 2 Empfaenger nicht erreichbar, Abbruch")
    return empfaenger


def pruefe_email_bestaetigt(profil: dict) -> None:
    """AC-11: Konto-Adresse muss bestaetigt sein; ein versandfreier Weg zur Bestaetigung
    fehlt auf Staging, darum nur pruefen (nicht bestaetigt => Exit 1, vor jedem Schreiben)."""
    if profil.get("email_verified") is not True:
        raise SeedFehler("E-Mail des Pruefkontos nicht bestätigt - einmal über den "
                         "Bestätigungslink im Test-Postfach bestätigen, dann erneut starten")


def soll_vergleich(location_ids: list[str], empfaenger: list[str]) -> dict:
    # Go speichert Briefing-Zeiten als "HH:MM:SS" (ValidateQuarterHourSlotTime) und
    # verlangt schedule daily|weekly|manual (validateComparePreset).
    # schedule daily ist versandsicher (#3151 AC-5): auf Staging (GZ_ENV=staging) leitet
    # Settings.with_user_profile jeden Versand ueber for_testing() (src/app/config.py):
    # Mail ueber Stalwart statt Resend an Test-Postfach bzw. .invalid, SMS/Premium-SMS
    # nur mit GZ_SEVEN_SANDBOX_KEY (seven_io_base._guard_test_mode_sandbox_key),
    # Telegram nur Test-Bot und nur Test-Chat (telegram._guard_test_mode_*); die
    # Kanalziele des Seeds sind fiktiv. pruefe_kein_live_versand bricht sonst ab.
    return {"name": VERGLEICH_NAME, "location_ids": location_ids, "profil": "allgemein",
            "schedule": "daily", "morning_enabled": True, "morning_time": "07:00:00",
            "empfaenger": empfaenger,
            "display_config": {"region": "Westfalen", "ampel": {"template": "allgemein"},
                               "active_metrics": [{"metric_id": m, "aggregation": a}
                                                  for m, a in _ORTE_METRIKEN]},
            **soll_kanalauswahl_vergleich()}


def _tabelle(folge: tuple[str, ...], stellen: tuple[str, ...]) -> dict:
    """``placements`` (version 1): alle Haken an (``places`` fehlt), Formate wie Mockup."""
    zeilen = []
    for mid in folge:
        zeile: dict = {"metric_id": mid}
        formstellen = [s for s in _ZWEI_FORMEN.get(mid, ()) if s in stellen]
        if formstellen:
            form = "simplified" if mid in _EINFACH else "raw"
            zeile["formats"] = {s: form for s in formstellen}
        zeilen.append(zeile)
    return {"version": 1, "rows": zeilen, "outlook_reports": list(_AUSBLICK)}


def tabelle_trip_soll() -> dict:
    """#3154 AC-1: Tabelle des Trips (``kind=route``; ohne Stundenverlauf)."""
    return _tabelle(_TABELLE_TRIP, ("email", "telegram", "outlook"))


def tabelle_orte_soll() -> dict:
    """#3154 AC-2: Tabelle des Orts-Vergleichs (``kind=vergleich``)."""
    return _tabelle(_TABELLE_ORTE, _ALLE_FORMSTELLEN)


def tabelle_braucht_put(get_antwort: dict, soll: dict) -> bool:
    """False nur, wenn eine gespeicherte Tabelle das Soll schon enthaelt (gleiche Folge,
    gleiche Formate); eine blosse Umrechnung (``stored: false``) braucht immer den PUT."""
    if not isinstance(get_antwort, dict) or get_antwort.get("stored") is not True:
        return True
    ist = get_antwort.get("placements")
    if not isinstance(ist, dict) or not isinstance(ist.get("rows"), list):
        return True
    gleich = (ist.get("version") == soll["version"]
              and ist.get("outlook_reports") == soll["outlook_reports"]
              and [_zeile_kern(r) for r in ist["rows"]] == [_zeile_kern(r) for r in soll["rows"]])
    return not gleich


def _zeile_kern(zeile) -> tuple:
    """Vergleichskern einer Tabellenzeile: Metrik, abgewaehlte Stellen (``places`` != True;
    fehlt = angehakt) und Formate. Ein gespeicherter Haken ``false`` weicht damit vom Soll
    „alle Haken an“ ab; vom Server ergaenzte, unbekannte Schluessel zaehlen nicht."""
    if not isinstance(zeile, dict):
        return (None, {}, {})
    places = zeile.get("places") if isinstance(zeile.get("places"), dict) else {}
    formats = zeile.get("formats") if isinstance(zeile.get("formats"), dict) else {}
    return (zeile.get("metric_id"), {k: v for k, v in places.items() if v is not True}, dict(formats))


class PruefkontoSeed:
    """Seed gegen die Staging-Go-API; ``transport(methode, url, headers, body) -> (status, json)``."""

    def __init__(self, basis: str, intern: str, secret: str, transport):
        self._basis, self._intern, self._transport = basis, intern, transport
        self._secret = secret
        self.uid: str | None = None

    def __repr__(self) -> str:  # nie das Secret zeigen
        return f"PruefkontoSeed(basis={self._basis!r}, uid={self.uid!r})"

    def _rufe(self, methode, pfad, body=None, *, intern=False, erlaubt=()):
        url = (self._intern if intern else self._basis) + pfad
        headers = {_CORE_HEADER: self._secret} if intern else {}
        status, antwort = self._transport(methode, url, headers, body)
        if 200 <= status < 300 or status in erlaubt:
            return status, antwort
        raise SeedFehler(f"{methode} {pfad} -> HTTP {status}{_kennung(antwort)}")

    def anmelden(self, nutzer: str, passwort: str) -> dict:
        self._rufe("POST", "/api/auth/login", {"username": nutzer, "password": passwort})
        profil = self.profil()
        uid = profil.get("id") if isinstance(profil, dict) else None
        if not isinstance(uid, str) or not uid.strip() or uid == "default":
            raise SeedFehler("Profil ohne echte Nutzer-id - Abbruch (nie 'default')")
        self.uid = uid
        return profil

    def profil(self) -> dict:
        return self._rufe("GET", "/api/auth/profile")[1]

    # --- Datensaetze (GET, dann POST oder Read-Modify-Write) -----------------------

    def sichere_datensatz(self, sammlung: str, soll: dict) -> dict:
        """Feste eigene ID: fehlt => POST; vorhanden => nur Soll-Felder ueberschreiben."""
        status, ist = self._rufe("GET", f"{sammlung}/{soll['id']}", erlaubt=(404,))
        if status == 404:
            return self._rufe("POST", sammlung, soll)[1]
        if _enthaelt(ist, soll):
            return ist
        return self._rufe("PUT", f"{sammlung}/{soll['id']}", _merge(ist, soll))[1]

    def sichere_archiviert(self, trip: dict) -> None:
        """#3327: nur ohne Archivdatum archivieren (Body ``archived``, nicht ``state``)."""
        if trip.get("archived_at"):
            return
        self._rufe("PATCH", f"/api/trips/{trip['id']}/state", {"archived": True})

    def sichere_wetter(self, trip: dict) -> dict:
        ist = trip.get("display_config") or {}
        soll = soll_wetter()
        if _enthaelt(ist, soll):
            return ist
        return self._rufe("PUT", f"/api/trips/{TRIP_ID}/weather-config", soll)[1]

    def sichere_vorlage(self, wetter: dict) -> None:
        """Eigene Vorlage aus dem GR221-Stand; GET vor POST, nie ein zweites Anlegen."""
        soll = {"name": VORLAGE_NAME, "kind": "route", "description": "aus GR221 gespeichert",
                "metrics": wetter["metrics"], "ampel": wetter["ampel"]}
        liste = self._rufe("GET", "/api/metric-presets")[1] or []
        ist = next((v for v in liste if v.get("name") == VORLAGE_NAME
                    and v.get("kind") in ("route", "", None)), None)
        if ist is None:
            self._rufe("POST", "/api/metric-presets", soll)
        elif not _enthaelt(ist, soll):
            self._rufe("PATCH", f"/api/metric-presets/{ist['id']}", {**ist, **soll})

    def sichere_vergleich(self, location_ids: list[str], empfaenger: list[str]) -> str:
        """Server vergibt die ID: Treffer per Name, sonst Neuanlage; RMW mit Merge."""
        soll = soll_vergleich(location_ids, empfaenger)
        liste = self._rufe("GET", "/api/compare/presets")[1] or []
        treffer = next((v for v in liste if v.get("name") == VERGLEICH_NAME), None)
        if treffer is None:
            angelegt = self._rufe("POST", "/api/compare/presets", soll)[1]
            return angelegt["id"]
        vid = treffer["id"]
        ist = self._rufe("GET", f"/api/compare/presets/{vid}")[1]
        if not _enthaelt(ist, soll):
            dc = {**(ist.get("display_config") or {}), **soll["display_config"]}
            self._rufe("PUT", f"/api/compare/presets/{vid}",
                       {**_merge(ist, soll), "display_config": dc})
        return vid

    # --- Tabelle „Was steht wo“ (#3154) ------------------------------------------

    def sichere_tabelle(self, briefing_id: str, kind: str, soll: dict) -> bool:
        """GET, vergleichen, nur bei Abweichung PUT; True = geschrieben.

        Der PUT ersetzt nur ``display_config.placements`` (Read-Modify-Write in Go, alle
        anderen Felder des Abos bleiben). Rumpf = vollstaendige Tabelle (api_contract.md):
        ``version``, ``rows``, ``outlook_reports`` aus dem Soll; unbekannte Schluessel oben
        einer GESPEICHERTEN Tabelle bleiben erhalten (Merge). Eine Umrechnung
        (``stored: false``) ist kein gespeicherter Stand und wird nicht uebernommen."""
        if not isinstance(self.uid, str) or not self.uid.strip() or self.uid == "default":
            raise SeedFehler("Tabelle ohne angemeldeten Nutzer - Abbruch (nie 'default')")
        pfad = f"/api/briefings/{briefing_id}/placements?kind={kind}"
        ist = self._rufe("GET", pfad)[1]
        if not tabelle_braucht_put(ist, soll):
            return False
        gespeichert = ist.get("placements") if isinstance(ist, dict) and ist.get("stored") else None
        body = {**gespeichert, **soll} if isinstance(gespeichert, dict) else soll
        self._rufe("PUT", pfad, body)
        return True

    # --- Kanaele ----------------------------------------------------------------

    def sichere_tarif(self) -> None:
        """Tarif premium, Zaehler sms/premium_sms auf 0 (Staging-Route, setzt Werte)."""
        self._rufe("POST", "/api/auth/staging-seed", {"tier": "premium", "sms": 0, "premium_sms": 0})

    def sichere_sms(self, profil: dict) -> None:
        if profil.get("sms_to") == SMS_NUMMER and profil.get("sms_verified"):
            return
        self._rufe("PUT", "/api/auth/profile", {"sms_to": SMS_NUMMER})
        code = self._rufe("POST", "/api/auth/sms/staging-code")[1].get("code")
        if not code:
            raise SeedFehler("staging-code ohne Code")
        self._rufe("POST", "/api/auth/sms/verify", {"code": code})

    def sichere_telegram(self, profil: dict) -> None:
        if profil.get("telegram_chat_id") == TELEGRAM_CHAT_ID:
            return
        link = self._rufe("GET", "/api/auth/telegram-link")[1].get("link", "")
        token = (parse_qs(urlsplit(link).query).get("start") or [""])[0]
        if not token:
            raise SeedFehler("telegram-link ohne Token")
        self._rufe("POST", "/api/internal/telegram-connect",
                   {"token": token, "chat_id": TELEGRAM_CHAT_ID}, intern=True)

    def sichere_premium_sms(self, profil: dict) -> None:
        """Erst Trockenlauf, nur bei would_learn fuer DIESEN Nutzer ein scharfer Aufruf."""
        if (profil.get("premium_sms_reply_to") == INREACH_FROM
                and profil.get("premium_sms_reply_state") == "fresh"):
            return
        code = self._rufe("POST", "/api/auth/premium-sms-link-code")[1].get("code")
        if not code:
            raise SeedFehler("premium-sms-link-code ohne Code")
        pfad = "/api/internal/premium-sms-learn"
        probe = self._rufe("POST", pfad, {"from": INREACH_FROM, "code": code, "dry_run": True},
                           intern=True)[1]
        if probe.get("outcome") != "would_learn" or probe.get("user_id") != self.uid:
            raise SeedFehler(f"premium-sms-learn Trockenlauf ohne would_learn{_kennung(probe)}")
        self._rufe("POST", pfad, {"from": INREACH_FROM, "code": code, "dry_run": False}, intern=True)


def fuehre_seed(seed: PruefkontoSeed, nutzer: str, passwort: str) -> tuple[str, str]:
    """Gesamtlauf; liefert (Trip-ID, Orts-Vergleich-ID)."""
    profil = seed.anmelden(nutzer, passwort)
    pruefe_email_bestaetigt(profil)  # vor jedem Schreibzugriff
    empfaenger = soll_empfaenger(profil)  # vor jedem Schreibzugriff
    seed.sichere_tarif()  # vor den Datensaetzen: sonst Free-Quote (409 quota_exceeded)
    trip = seed.sichere_datensatz("/api/trips", {**soll_trip(), **soll_kanalauswahl_trip()})
    seed.sichere_archiviert(seed.sichere_datensatz("/api/trips", soll_archiv_trip()))
    seed.sichere_vorlage(seed.sichere_wetter(trip))
    orte = [seed.sichere_datensatz("/api/locations", {
        "id": oid, "name": name, "lat": lat, "lon": lon, "elevation_m": hoehe,
        "region": "Westfalen"})["id"] for oid, name, lat, lon, hoehe in _ORTE]
    vergleich_id = seed.sichere_vergleich(orte, empfaenger)
    seed.sichere_tabelle(TRIP_ID, "route", tabelle_trip_soll())
    seed.sichere_tabelle(vergleich_id, "vergleich", tabelle_orte_soll())
    profil = seed.profil()
    seed.sichere_sms(profil)
    seed.sichere_telegram(profil)
    seed.sichere_premium_sms(profil)
    return TRIP_ID, vergleich_id


def _bereinigt(text: str, secret: str) -> str:
    return text.replace(secret, "***") if secret else text


def main(argv=None, *, transport=None) -> int:
    """Netzrand injizierbar (Tests); ohne Angabe gilt echtes HTTP."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--basis-url", default=BASIS_URL)
    p.add_argument("--intern-url", default=INTERN_URL)
    p.add_argument("--env-datei", type=Path, default=STAGING_ENV)
    args = p.parse_args(argv)
    secret = ""
    try:
        basis, intern = pruefe_basis_url(args.basis_url), pruefe_intern_url(args.intern_url)
        env = lade_env(args.env_datei)
        nutzer, passwort, secret = zugang_aus_env(env)
        pruefe_kein_live_versand(env)
        seed = PruefkontoSeed(basis, intern, secret, transport or _http_transport())
        trip_id, orte_id = fuehre_seed(seed, nutzer, passwort)
    except AufrufFehler as exc:
        print(f"FEHLER: {_bereinigt(str(exc), secret)}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - jeder API-/Datenfehler => Exit 1, bereinigt
        print(f"FEHLER: {_bereinigt(f'{type(exc).__name__}: {exc}', secret)}", file=sys.stderr)
        return 1
    print(f"ELEMENTLISTE_TRIP_ID={trip_id}")
    print(f"ELEMENTLISTE_ORTE_ID={orte_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
