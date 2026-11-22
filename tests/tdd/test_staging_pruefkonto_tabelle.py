"""Issue #3154: Seed des Staging-Pruefkontos schreibt die Tabelle „Was steht wo“ (Trip und Orte).

Spec: docs/specs/modules/feat_3154_karte_abgleich.md (AC-1, AC-2, AC-3; Test Plan Seed).

Kern-Schicht, kein Netz. Erwartete Werte stammen aus dem Mockup Fassung 4
(docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html): Reihenfolge TRIP_METRICS (Z.316-336,
ohne die ausgeschaltete Windrichtung = 18 Zeilen inkl. der fuenf Nur-Anzeige-Zeilen), ORTE_METRICS
(ohne Windrichtung), Formate ``defFmt`` (Z.578: Roh, ausser Windrichtung/Gewitter/Bewoelkung/Sonne = Einfach),
Ausblick ``outM:false, outA:true`` (= nur Abend), Gewitter-Einfach nur in der E-Mail (AC-5).

FESTGELEGTE SCHNITTSTELLE (``scripts/staging_pruefkonto_mockupdaten.py``, Tech-Lead-Entscheidung in RED):

  tabelle_trip_soll() -> dict
      ``placements`` fuer ``PUT /api/briefings/{id}/placements?kind=route`` (api_contract.md Z.1448):
      ``{"version": 1, "rows": [{"metric_id", "places"?, "formats"?}, ...], "outlook_reports": [...]}``.
      Jeder Aufruf liefert ein NEUES Objekt (keine geteilte Veraenderlichkeit zwischen Konten).
  tabelle_orte_soll() -> dict
      ``placements`` fuer ``kind=vergleich`` (acht Zeilen in ORTE_METRICS-Folge).
  tabelle_braucht_put(get_antwort: dict, soll: dict) -> bool
      ``get_antwort`` = Antwort von ``GET .../placements`` (``stored``, ``placements``). False nur, wenn
      ``stored`` True ist UND ``placements`` das Soll enthaelt (Listen gleich lang und gleiche Folge).
  PruefkontoSeed.sichere_tabelle(briefing_id: str, kind: str, soll: dict) -> bool
      GET, vergleichen, nur bei Abweichung PUT (ohne If-Match, Read-Modify-Write liegt in Go);
      True = es wurde geschrieben. Nutzer ausschliesslich aus der Anmeldung (``self.uid``), nie "default".
  soll_vergleich(...)["display_config"]["active_metrics"] enthaelt zusaetzlich ("temperature", "min").
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SKRIPT = Path(__file__).resolve().parents[2] / "scripts" / "staging_pruefkonto_mockupdaten.py"

# Mockup TRIP_METRICS-Folge ohne wind_direction (aus), inkl. fuenf Nur-Anzeige-Zeilen.
TRIP_FOLGE = [
    "temperature", "temperature_night", "temperature_day_low", "temperature_day_high",
    "wind_chill", "wind_chill_night", "wind_chill_day_low", "wind_chill_day_high",
    "wind", "gust", "precipitation", "thunder", "rain_probability", "visibility",
    "cloud_low", "uv_index", "freezing_level", "snowfall_limit",
]
# Mockup ORTE_METRICS-Folge ohne wind_direction (aus).
ORTE_FOLGE = ["temperature", "wind", "gust", "precipitation", "thunder", "rain_probability",
              "cloud_total", "sunshine"]
STELLEN = {"email", "telegram", "sms", "hourly", "outlook"}


def _modul():
    spec = importlib.util.spec_from_file_location("staging_pruefkonto_tabelle_3154", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _zeilen(placements: dict) -> dict:
    return {r["metric_id"]: r for r in placements["rows"]}


def _format(zeile: dict, stelle: str):
    return (zeile.get("formats") or {}).get(stelle)


# --------------------------------------------------------------------------- AC-1 (Trip)

class TestTripPayload:
    def test_achtzehn_zeilen_in_mockup_folge(self):
        p = _modul().tabelle_trip_soll()
        assert [r["metric_id"] for r in p["rows"]] == TRIP_FOLGE
        assert p["version"] == 1

    def test_alle_haken_an(self):
        # „Alle Haken an“: places fehlt (= angehakt) oder enthaelt nur True, nur bekannte Stellen.
        for r in _modul().tabelle_trip_soll()["rows"]:
            places = r.get("places") or {}
            assert set(places) <= STELLEN, r
            assert all(v is True for v in places.values()), r

    def test_formate_wie_mockup(self):
        z = _zeilen(_modul().tabelle_trip_soll())
        assert _format(z["thunder"], "email") == "simplified"
        assert _format(z["cloud_low"], "email") == "simplified"
        for roh in ("wind", "gust", "precipitation"):
            assert _format(z[roh], "email") in (None, "raw"), roh
            assert _format(z[roh], "telegram") in (None, "raw"), roh

    def test_gewitter_einfach_nur_in_der_email(self):
        # AC-5: die zweite Form von Gewitter gibt es nur in der E-Mail.
        thunder = _zeilen(_modul().tabelle_trip_soll())["thunder"]
        assert set(thunder.get("formats") or {}) == {"email"}

    def test_ausblick_nur_abend(self):
        assert _modul().tabelle_trip_soll()["outlook_reports"] == ["evening"]


# --------------------------------------------------------------------------- AC-2 (Orte)

class TestOrtePayload:
    def test_acht_zeilen_in_mockup_folge(self):
        p = _modul().tabelle_orte_soll()
        assert [r["metric_id"] for r in p["rows"]] == ORTE_FOLGE
        assert p["version"] == 1

    def test_einfach_fuer_bewoelkung_sonne_und_gewitter_email(self):
        z = _zeilen(_modul().tabelle_orte_soll())
        assert _format(z["cloud_total"], "email") == "simplified"
        assert _format(z["sunshine"], "email") == "simplified"
        assert _format(z["thunder"], "email") == "simplified"
        for roh in ("wind", "gust", "precipitation"):
            assert _format(z[roh], "email") in (None, "raw"), roh

    def test_gewitter_einfach_nur_in_der_email(self):
        thunder = _zeilen(_modul().tabelle_orte_soll())["thunder"]
        assert set(thunder.get("formats") or {}) == {"email"}

    def test_ausblick_abend(self):
        assert _modul().tabelle_orte_soll()["outlook_reports"] == ["evening"]

    def test_temperatur_max_und_min_in_den_orte_metriken(self):
        m = _modul()
        paare = [(a["metric_id"], a["aggregation"])
                 for a in m.soll_vergleich(["a"], ["x@y.invalid"])["display_config"]["active_metrics"]]
        assert ("temperature", "max") in paare
        assert ("temperature", "min") in paare
        assert paare.count(("temperature", "max")) == 1


# --------------------------------------------------------------------------- AC-3 (idempotent, zwei Konten)

class TestBrauchtPut:
    def test_nicht_gespeichert_braucht_put_auch_bei_gleicher_umrechnung(self):
        m = _modul()
        soll = m.tabelle_trip_soll()
        assert m.tabelle_braucht_put({"stored": False, "placements": soll}, soll) is True

    def test_gleich_gespeichert_braucht_keinen_put(self):
        m = _modul()
        assert m.tabelle_braucht_put({"stored": True, "placements": m.tabelle_trip_soll()},
                                     m.tabelle_trip_soll()) is False

    def test_andere_folge_oder_format_braucht_put(self):
        m = _modul()
        soll = m.tabelle_trip_soll()
        umgestellt = m.tabelle_trip_soll()
        umgestellt["rows"][0], umgestellt["rows"][1] = umgestellt["rows"][1], umgestellt["rows"][0]
        assert m.tabelle_braucht_put({"stored": True, "placements": umgestellt}, soll) is True
        anders = m.tabelle_trip_soll()
        _zeilen(anders)["thunder"]["formats"] = {"email": "raw"}
        assert m.tabelle_braucht_put({"stored": True, "placements": anders}, soll) is True

    def test_jeder_aufruf_liefert_neues_objekt(self):
        m = _modul()
        a, b = m.tabelle_trip_soll(), m.tabelle_trip_soll()
        a["rows"].clear()
        assert len(b["rows"]) == 18


class _FakeServer:
    """Kleiner In-Memory-Server fuer GET/PUT /api/briefings/{id}/placements eines Kontos."""

    def __init__(self, ids: dict[str, str]):
        self.ids = ids                      # briefing_id -> kind
        self.gespeichert: dict[str, dict] = {}
        self.anfragen: list[tuple[str, str]] = []

    def __call__(self, methode, url, headers, body):
        pfad = url.split("staging.gregor20.henemm.com", 1)[-1]
        self.anfragen.append((methode, pfad))
        teile = pfad.split("?")
        segmente = teile[0].strip("/").split("/")
        assert segmente[:2] == ["api", "briefings"] and segmente[-1] == "placements", pfad
        bid, kind = segmente[2], teile[1].split("=", 1)[1]
        if self.ids.get(bid) != kind:
            return 404, {"error": "not_found"}
        if methode == "GET":
            if bid in self.gespeichert:
                return 200, {"stored": True, "placements": self.gespeichert[bid]}
            return 200, {"stored": False, "placements": {"version": 1, "rows": []}}
        assert methode == "PUT"
        self.gespeichert[bid] = body
        return 200, {"placements": body}

    def puts(self):
        return [a for a in self.anfragen if a[0] == "PUT"]


def _seed(m, server, uid):
    s = m.PruefkontoSeed("https://staging.gregor20.henemm.com", "http://localhost:8091", "geheim", server)
    s.uid = uid
    return s


class TestSichereTabelle:
    def test_zweiter_lauf_schreibt_nichts(self):
        m = _modul()
        server = _FakeServer({"t1": "route", "o1": "vergleich"})
        s = _seed(m, server, "konto-a")
        assert s.sichere_tabelle("t1", "route", m.tabelle_trip_soll()) is True
        assert s.sichere_tabelle("o1", "vergleich", m.tabelle_orte_soll()) is True
        assert len(server.puts()) == 2
        assert s.sichere_tabelle("t1", "route", m.tabelle_trip_soll()) is False
        assert s.sichere_tabelle("o1", "vergleich", m.tabelle_orte_soll()) is False
        assert len(server.puts()) == 2
        assert server.gespeichert["t1"] == m.tabelle_trip_soll()
        assert server.gespeichert["o1"] == m.tabelle_orte_soll()

    def test_zwei_konten_je_nur_eigene_tabelle(self):
        m = _modul()
        a, b = _FakeServer({"t1": "route"}), _FakeServer({"t1": "route"})
        sa, sb = _seed(m, a, "konto-a"), _seed(m, b, "konto-b")
        sa.sichere_tabelle("t1", "route", m.tabelle_trip_soll())
        assert b.gespeichert == {} and b.puts() == []   # Konto B unberuehrt
        sb.sichere_tabelle("t1", "route", m.tabelle_trip_soll())
        assert len(a.puts()) == 1 and len(b.puts()) == 1
        for server in (a, b):                           # nie ein Nutzer-Fallback in den Pfaden
            assert all("default" not in pfad for _, pfad in server.anfragen)

    def test_falsche_art_wird_nicht_geschrieben(self):
        m = _modul()
        server = _FakeServer({"t1": "route"})
        with pytest.raises(m.SeedFehler):
            _seed(m, server, "konto-a").sichere_tabelle("t1", "vergleich", m.tabelle_orte_soll())
        assert server.puts() == []
