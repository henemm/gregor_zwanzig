"""Die drei Zustaende: nicht abrufbar / kein aktueller Bericht / Stufe 1 (AC-4, AC-5, AC-6).

SPEC: docs/specs/modules/avalanche_report_bulletin.md -- AC-4, AC-5, AC-6
VERTRAG: docs/artifacts/feat-1441-s1-lawinenlagebericht/red-contract.md Abschnitt 1

Echte Quelle + echte Abrufschicht; der Fixture-Transport liefert aufgezeichnete Bytes
(Mai-Bulletin, echte 404-Antwort) oder injiziert Fehler (5xx, Verbindungsabbruch). Die Uhr ist
steuerbar (`FakeClock`): sie treibt sowohl die Cache-TTL als auch die Gueltigkeitspruefung.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from tests.helpers.avalanche_report_support import (
    FIXTURES, P_TIROL_AT_07_05, FakeClock, FixtureTransport, Reply, alerts_with_status, day_file,
    make_source, ok, only_source,
)

UTC = timezone.utc
HEUTE = datetime(2026, 10, 13, 10, 0, tzinfo=UTC)          # Aufzeichnungstag: ausser Saison
MAI_ENDE = datetime(2026, 5, 2, 15, 0, tzinfo=UTC)
MAI = "2026-05-02_AT-07_de_CAAMLv6.json"
WINTER = day_file("2026-03-01")


def _setup(reply: Reply, now: datetime):
    transport = FixtureTransport({"AT-07": reply})
    clock = FakeClock(now)
    return transport, clock, make_source(transport, clock)


# ---------------------------------------------------------------- AC-4: veraltetes Bulletin
def test_ac4_mai_bulletin_im_oktober_ist_leer_und_nicht_abrufbar_false(monkeypatch):
    """HTTP 200 mit dem Bulletin vom 2026-05-02: weder Stufe noch Hinweis (Haftungsfalle)."""
    transport, clock, source = _setup(ok(MAI), HEUTE)
    only_source(monkeypatch, source)

    alerts, unavailable = alerts_with_status(*P_TIROL_AT_07_05, HEUTE)

    assert alerts == []
    assert unavailable is False
    assert transport.served("AT-07") == 1, "Voraussetzung: das Bulletin wurde wirklich geliefert"


def test_ac4_die_quelle_selbst_filtert_das_abgelaufene_bulletin():
    """Ohne die Gueltigkeitspruefung in der Quelle faende erst der spaetere Zeitfenster-Filter des
    Registry-Pfads den Fehler -- die Zusicherung gilt aber an der Quelle."""
    transport, clock, source = _setup(ok(MAI), HEUTE)

    assert source.fetch(*P_TIROL_AT_07_05) == []


def test_ac4_dieselbe_datei_ist_am_gueltigkeitstag_eine_stufe_1():
    """Gegenprobe: die Datei ist nicht "immer leer" -- am 2026-05-02 vormittags gilt sie."""
    transport, clock, source = _setup(ok(MAI), datetime(2026, 5, 2, 8, 0, tzinfo=UTC))

    alerts = source.fetch(*P_TIROL_AT_07_05)

    assert [(a.native_level, a.level) for a in alerts] == [(1, 1)], "Stufe 1 ist ein sichtbarer Alert"


def test_ac4_gueltigkeitsgrenze_gleichheit_gilt_noch_eine_sekunde_danach_nicht_mehr():
    _t, _c, source_vor = _setup(ok(MAI), MAI_ENDE)
    _t, _c, source_nach = _setup(ok(MAI), MAI_ENDE + timedelta(seconds=1))

    assert len(source_vor.fetch(*P_TIROL_AT_07_05)) == 1
    assert source_nach.fetch(*P_TIROL_AT_07_05) == []


def test_ac4_echte_latest_antwort_des_aufzeichnungstages_ist_ebenfalls_veraltet():
    """Die echte `latest/`-Antwort vom 2026-10-13 endet am 2026-05-03 (nicht 05-02)."""
    transport, clock, source = _setup(ok("latest_AT-07_recorded_2026-10-13.json"), HEUTE)

    assert source.fetch(*P_TIROL_AT_07_05) == []


# ---------------------------------------------------------------- AC-5: 404 / 5xx / Netz
def _echte_404() -> Reply:
    rec = json.loads((FIXTURES / "404_latest_AT-02.json").read_text(encoding="utf-8"))
    assert rec["status"] == 404 and rec["body"] == ""
    return Reply(rec["status"], rec["body"].encode())


def test_ac5_404_ist_leer_und_kein_nicht_abrufbar(monkeypatch):
    transport, clock, source = _setup(_echte_404(), HEUTE)
    only_source(monkeypatch, source)

    alerts, unavailable = alerts_with_status(*P_TIROL_AT_07_05, HEUTE)

    assert alerts == [] and unavailable is False
    assert transport.served("AT-07") == 1


@pytest.mark.parametrize("fehler", [
    Reply(503, b"Service Unavailable"),
    Reply(500, b""),
    Reply(error=httpx.ConnectError("Verbindung verweigert")),
    Reply(error=httpx.ReadTimeout("Zeitueberschreitung")),
], ids=["503", "500", "connect-error", "timeout"])
def test_ac5_5xx_und_netzfehler_melden_nicht_abrufbar(monkeypatch, fehler):
    transport, clock, source = _setup(fehler, datetime(2026, 3, 1, 8, 0, tzinfo=UTC))
    only_source(monkeypatch, source)

    alerts, unavailable = alerts_with_status(*P_TIROL_AT_07_05, datetime(2026, 3, 1, 8, 0, tzinfo=UTC))

    assert alerts == []
    assert unavailable is True, "ein echter Ausfall MUSS als 'nicht abrufbar' sichtbar werden (ADR-0018)"


def test_ac5_kaputtes_json_ist_ein_ausfall_und_keine_stille_leere(monkeypatch):
    transport, clock, source = _setup(Reply(200, b"<html>kein json</html>"), HEUTE)
    only_source(monkeypatch, source)

    alerts, unavailable = alerts_with_status(*P_TIROL_AT_07_05, HEUTE)

    assert alerts == [] and unavailable is True


# ---------------------------------------------------------------- AC-6: kurze Cache-Dauer
SPAET = 1800 + 200      # > 1800 s (ok-TTL) und weit < 86400 s (24 h "nicht zustaendig")


def test_ac6_nach_404_erscheint_ein_neues_bulletin_nach_ueber_1800_sekunden():
    """Mutation `not_covered_ttl` 1800 -> 86400 s (oder 404 in der 24-h-Menge) macht diesen Test rot."""
    now = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    transport, clock, source = _setup(_echte_404(), now)

    assert source.fetch(*P_TIROL_AT_07_05) == []
    transport.set("AT-07", ok(WINTER))
    clock.advance(SPAET)
    nach = source.fetch(*P_TIROL_AT_07_05)

    assert [(a.native_level, a.elevation_value) for a in nach] == [(3, "Waldgrenze")]
    assert transport.served("AT-07") == 2, "die leere Antwort darf nicht 24 h im Cache bleiben"


def test_ac6_nach_abgelaufenem_bulletin_erscheint_das_neue_nach_ueber_1800_sekunden():
    """Euregio-Fall: HTTP 200 mit dem Bulletin vom 20.02. (um 17:30Z abgelaufen). Die taegliche
    Neuausgabe (17:00 Ortszeit) liefert wenig spaeter das Bulletin vom 21.02."""
    start = datetime(2026, 2, 20, 17, 30, tzinfo=UTC)     # nach Ende (16:00Z) des Bulletins 2026-02-20
    transport, clock, source = _setup(ok(day_file("2026-02-20")), start)
    punkt = (46.9599, 12.4007)                             # AT-07-25, an beiden Tagen Stufe 4

    assert source.fetch(*punkt) == [], "Voraussetzung: das Bulletin vom 20.02. ist abgelaufen"
    transport.set("AT-07", ok(day_file("2026-02-21")))
    clock.advance(SPAET)
    neu = source.fetch(*punkt)

    assert len(neu) == 1 and neu[0].native_level == 4
    assert neu[0].url == "https://avalanche.report/bulletin/2026-02-21?region=AT-07-25"
    assert transport.served("AT-07") == 2


def test_ac6_innerhalb_von_1800_sekunden_wird_nicht_erneut_abgerufen():
    now = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    transport, clock, source = _setup(ok(WINTER), now)

    source.fetch(*P_TIROL_AT_07_05)
    clock.advance(900)
    source.fetch(*P_TIROL_AT_07_05)

    assert transport.served("AT-07") == 1


def test_ac6_nach_einem_ausfall_wird_binnen_kurzer_zeit_neu_versucht():
    """Fehler-TTL 60 s: kein 30-Minuten-Blindflug nach einem kurzen 5xx."""
    now = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    transport, clock, source = _setup(Reply(503, b""), now)

    assert source.fetch(*P_TIROL_AT_07_05) == []
    transport.set("AT-07", ok(WINTER))
    clock.advance(120)
    nach = source.fetch(*P_TIROL_AT_07_05)

    assert len(nach) == 1
    assert transport.served("AT-07") == 2


def test_ac6_ablauf_waehrend_der_cache_dauer_wird_trotz_cache_erkannt():
    """Die Gueltigkeit wird bei JEDEM fetch gegen die aktuelle Zeit geprueft, nicht nur beim
    Abruf: das gecachte Bulletin laeuft innerhalb der 1800 s ab."""
    transport, clock, source = _setup(ok(MAI), MAI_ENDE - timedelta(seconds=600))

    assert len(source.fetch(*P_TIROL_AT_07_05)) == 1
    clock.advance(900)           # jetzt 5 min NACH Ende, aber noch im 1800-s-Cache
    assert source.fetch(*P_TIROL_AT_07_05) == []
    assert transport.served("AT-07") == 1
