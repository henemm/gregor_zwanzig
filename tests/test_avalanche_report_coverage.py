"""Geo-Scope, Konfigurationstabelle und Egress-Inventar (AC-7, AC-8, AC-20).

SPEC: docs/specs/modules/avalanche_report_bulletin.md -- AC-7, AC-8, AC-20
VERTRAG: docs/artifacts/feat-1441-s1-lawinenlagebericht/red-contract.md Abschnitte 1, 8

Die Zusicherung "kein Abruf" wird am Transport GEZAEHLT (jeder Zugriff, auch auf den
Redirect-Host, steht in `transport.requests`), nicht aus dem Code gelesen.
Der Go-Teil von AC-20 steht in `test_avalanche_report_docs.py` (Dateiinhalt-Lesung, Doku-Test).
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.helpers.avalanche_report_support import (
    P_MUENCHEN, P_SALZBURG, P_TIROL_AT_07_28, P_ZELL_AM_SEE, P_ZUERICH, REGIONS, FakeClock,
    FixtureTransport, alerts_with_status, call_log, day_file, doc, fixture_table, make_source, ok,
    only_source,
)

UTC = timezone.utc
NOW = datetime(2026, 1, 30, 8, 0, tzinfo=UTC)
ALLE = {"AT-07": ok(day_file("2026-01-30")), "AT-02": ok(day_file("2026-03-01", "AT-02")),
        "IT-32-BZ": ok(day_file("2026-03-01", "IT-32-BZ")), "IT-32-TN": ok(day_file("2026-03-01", "IT-32-TN"))}


# ---------------------------------------------------------------- AC-7: kein Abruf ausserhalb
@pytest.mark.parametrize("punkt", [P_MUENCHEN, P_ZUERICH, P_SALZBURG],
                         ids=["muenchen", "zuerich", "salzburg"])
def test_ac7_punkt_ausserhalb_loest_keinen_abruf_und_keinen_hinweis_aus(monkeypatch, tmp_path, punkt):
    from services.official_alerts import warn_egress

    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "calls.jsonl")
    transport = FixtureTransport(dict(ALLE))
    source = make_source(transport, FakeClock(NOW))
    only_source(monkeypatch, source)

    alerts, unavailable = alerts_with_status(*punkt, NOW)

    assert alerts == [] and unavailable is False
    assert transport.requests == [], f"es darf KEIN Zugriff stattfinden: {transport.requests}"
    assert not [r for r in call_log() if r["service"] == "avalanche_report"]


def test_ac7_bounding_box_treffer_ohne_region_ist_leer_und_ohne_hinweis(monkeypatch):
    """Zell am See liegt in der Bounding-Box von AT-07, aber in keiner Mikroregion (Salzburg)."""
    transport = FixtureTransport(dict(ALLE))
    source = make_source(transport, FakeClock(NOW))
    only_source(monkeypatch, source)

    alerts, unavailable = alerts_with_status(*P_ZELL_AM_SEE, NOW)

    assert alerts == [] and unavailable is False


def test_ac7_covers_kennt_nur_die_vier_gebiete():
    source = make_source(FixtureTransport(), FakeClock(NOW))

    assert source.covers(*P_TIROL_AT_07_28) is True
    for punkt in (P_MUENCHEN, P_ZUERICH, P_SALZBURG):
        assert source.covers(*punkt) is False


def test_ac7_standardtabelle_hat_genau_die_vier_belegten_zeilen_mit_eingecheckter_geometrie():
    """Die Produktions-Tabelle: Tirol, Suedtirol, Trentino, Kaernten -- Salzburg/Bayern nicht
    (Lizenz ungeklaert). Die Regionsdateien liegen im Paket und sind byte-identisch zur
    aufgezeichneten Quelle (/50 kopiert, aendert nichts)."""
    from services.official_alerts.avalanche_report import AVALANCHE_REGION_TABLE

    assert [row.key for row in AVALANCHE_REGION_TABLE] == ["AT-07", "IT-32-BZ", "IT-32-TN", "AT-02"]
    for row in AVALANCHE_REGION_TABLE:
        assert "{X}" in row.url_pattern and row.url_pattern.startswith("https://static.avalanche.report/")
        assert Path(row.regions_file).is_file(), f"Regionsdatei fehlt: {row.regions_file}"
        assert Path(row.regions_file).read_bytes() == (REGIONS / f"{row.key}_micro-regions.geojson.json").read_bytes()
        assert row.display_name.startswith("Lawinenwarndienst ")


def test_ac7_standardquelle_deckt_tirol_aber_nicht_muenchen_ohne_netz():
    from services.official_alerts.avalanche_report import AvalancheReportSource

    source = AvalancheReportSource()

    assert source.covers(*P_TIROL_AT_07_28) is True
    assert source.covers(*P_MUENCHEN) is False


# ---------------------------------------------------------------- AC-8: Tabelle als Parameter
def _salzburg_test_zeile(tmp_path):
    """SYNTHETISCH (nicht aufgezeichnet, keine Salzburger Daten): eine zusaetzliche Tabellenzeile `AT-05`
    mit einer kleinen Testflaeche um Salzburg und einem Bulletin, das aus einem echten Tirol-Bulletin
    durch Umbenennen der Region entsteht. Beweist nur: neue Zeile + Regionsdatei genuegen."""
    from services.official_alerts.avalanche_report import AvalancheRegionConfig

    geo = tmp_path / "AT-05_micro-regions.geojson.json"
    quadrat = [[[12.9, 47.7], [13.2, 47.7], [13.2, 47.9], [12.9, 47.9], [12.9, 47.7]]]
    geo.write_text(json.dumps({"type": "FeatureCollection", "features": [{
        "type": "Feature", "properties": {"id": "AT-05-01"},
        "geometry": {"type": "MultiPolygon", "coordinates": [quadrat]},
    }]}), encoding="utf-8")
    zeile = AvalancheRegionConfig(
        key="AT-05", url_pattern="https://static.avalanche.report/bulletins/latest/{X}_de_CAAMLv6.json",
        regions_file=geo, display_name="Lawinenwarndienst Testland",
    )
    d = copy.deepcopy(doc(day_file("2026-01-30")))
    bulletin = next(b for b in d["bulletins"] if any(r["regionID"] == "AT-07-28" for r in b["regions"]))
    bulletin["regions"] = [{"regionID": "AT-05-01", "name": "Testgebiet"}]
    d["bulletins"] = [bulletin]
    return zeile, json.dumps(d).encode()


def test_ac8_zusaetzliche_tabellenzeile_wird_abgerufen_und_ausgewertet(tmp_path):
    from output.renderers.alert.official_alerts import avalanche_bulletin_text
    from tests.helpers.avalanche_report_support import Reply

    zeile, body = _salzburg_test_zeile(tmp_path)
    transport = FixtureTransport({**ALLE, "AT-05": Reply(200, body)})
    source = make_source(transport, FakeClock(NOW), table=fixture_table(extra=(zeile,)))

    alerts = source.fetch(*P_SALZBURG)

    assert len(alerts) == 1
    assert alerts[0].native_level == 3 and alerts[0].source == "avalanche_report:AT-05"
    assert alerts[0].dedup_id == "avalanche_bulletin:AT-05-01"
    assert avalanche_bulletin_text(alerts[0]).startswith("Lawinenstufe 3 (erheblich) oberhalb 2200 m")
    assert source.covers(*P_SALZBURG) is True
    assert transport.served("AT-05") == 1 and transport.served("AT-07") == 0


def test_ac8_ohne_die_zeile_bleibt_salzburg_unberuehrt(tmp_path):
    from tests.helpers.avalanche_report_support import Reply

    zeile, body = _salzburg_test_zeile(tmp_path)
    transport = FixtureTransport({**ALLE, "AT-05": Reply(200, body)})
    source = make_source(transport, FakeClock(NOW), table=fixture_table())

    assert source.fetch(*P_SALZBURG) == []
    assert source.covers(*P_SALZBURG) is False
    assert transport.requests == []


# ---------------------------------------------------------------- AC-20: Egress-Inventar (Python)
def test_ac20_python_inventar_fuehrt_genau_die_zwei_neuen_hosts_als_gesperrt_wie_alle_warn_hosts():
    """BLOCKED (wie feeds.meteoalarm.org, warnungen.zamg.at, ...): der netzfreie Kern darf nie real
    bei avalanche.report anfragen, und ein fehlschlagender zusaetzlicher Warn-Dienst laesst die
    `unavailable`-Bilanz der uebrigen Quellen unveraendert (TEST_ACCESS wuerde sie verfaelschen)."""
    from app.egress_guard import INVENTORY, IsolationKind

    assert INVENTORY.get("static.avalanche.report") is IsolationKind.BLOCKED
    assert INVENTORY.get("avalanche.report") is IsolationKind.BLOCKED


def test_ac20_weder_lawinen_warnung_eu_noch_ein_eu_sammelfeed_im_inventar():
    from app.egress_guard import INVENTORY

    verdaechtig = [h for h in INVENTORY if "lawinen-warnung" in h or "eaws" in h]
    assert verdaechtig == [], f"nicht beantragte Hosts im Inventar: {verdaechtig}"
    neu = [h for h in INVENTORY if "avalanche" in h]
    assert sorted(neu) == ["avalanche.report", "static.avalanche.report"]


def test_ac20_egress_waechter_sperrt_im_testlauf_beide_hosts_und_den_nicht_beantragten_spiegel():
    from app import egress_guard

    for host in ("static.avalanche.report", "avalanche.report"):
        assert host in egress_guard.INVENTORY, f"{host} muss DEKLARIERT sein (gesperrt, nicht unbekannt)"
        assert egress_guard._is_allowed(host) is False
    assert "static.lawinen-warnung.eu" not in egress_guard.INVENTORY
    assert egress_guard._is_allowed("static.lawinen-warnung.eu") is False


def test_ac20_standardquelle_macht_im_kern_keinen_echten_abruf_und_meldet_dann_nicht_abrufbar(monkeypatch):
    """Die ECHTE Standardquelle (echter Transport, aktiver Egress-Waechter): der Abruf wird gesperrt,
    das Ergebnis ist ein sichtbarer Ausfall -- nie ein stiller Netzzugriff aus dem Kern."""
    from services.official_alerts.avalanche_report import AvalancheReportSource

    only_source(monkeypatch, AvalancheReportSource())

    alerts, unavailable = alerts_with_status(*P_TIROL_AT_07_28, NOW)

    assert alerts == [] and unavailable is True


# ---------------------------------------------------------------- Registrierung (ADR-0016)
def test_quelle_ist_im_register_eingetragen_und_deckt_tirol_aber_nicht_muenchen():
    """Alle anderen Registry-Tests tauschen `_REGISTERED_SOURCES` aus -- ohne diesen Test bliebe
    eine vergessene Registrierung in `official_alerts/__init__.py` unbemerkt (Produktion riefe nie ab)."""
    import services.official_alerts  # noqa: F401  (loest die Registrierung beim Import aus)
    from services.official_alerts import base

    registriert = [s for s in base._REGISTERED_SOURCES if s.name == "avalanche_report"]

    assert len(registriert) == 1, [s.name for s in base._REGISTERED_SOURCES]
    assert registriert[0].covers(47.2692, 11.4041) is True       # Innsbruck
    assert registriert[0].covers(*P_MUENCHEN) is False


# ---------------------------------------------------------------- Ortsvergleich-Quellenfilter
def _filter_ergebnis(monkeypatch, sources):
    """`official_warnings.sources` des Ortsvergleich-Alarms (#1258): echter Service, echter Parser.
    Der Gueltigkeitszeitraum des aufgezeichneten Alerts wird auf "jetzt" gelegt, weil der Service
    mit der echten Uhr abfragt."""
    from dataclasses import replace
    from datetime import timedelta

    from app.config import Settings
    from app.user import SavedLocation
    from services.compare_official_alert import CompareOfficialAlertService
    from tests.helpers.avalanche_report_support import RecordedSource, parse_alert

    jetzt = datetime.now(UTC)
    alert = replace(
        parse_alert("2026-01-30_AT-07_de_CAAMLv6.json", "AT-07-28", source="avalanche_report:AT-07"),
        valid_from=jetzt - timedelta(hours=1), valid_to=jetzt + timedelta(hours=10),
    )
    only_source(monkeypatch, RecordedSource("avalanche_report", [alert]))
    ort = SavedLocation(id="loc-a", name="Tirol-Hütte", lat=46.9394, lon=12.6844, elevation_m=2300)
    service = CompareOfficialAlertService(
        settings=Settings(smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy", mail_to="d@example.com"),
        user_id="tdd-1441-quellenfilter", mail_sink=lambda subject, body: None,
    )
    tagged, _pro_ort = service._detect("p1", [ort], sources)
    return [a.hazard for a, _ids in tagged]


def test_ortsvergleich_quellenfilter_avalanche_report_laesst_den_lagebericht_durch(monkeypatch):
    """Das Nutzer-Vokabular der Quelle ist `avalanche_report` (= `AvalancheReportSource.name`); der Filter
    vergleicht den Teil VOR dem ':' des Alert-Schluessels (`avalanche_report:AT-07`) -- sonst
    verschwindet der Lagebericht bei jedem Nutzer mit Quellenfilter still aus dem Alarm."""
    assert _filter_ergebnis(monkeypatch, ["avalanche_report"]) == ["avalanche_bulletin"]


def test_ortsvergleich_quellenfilter_ohne_filter_oder_mit_anderer_quelle(monkeypatch):
    assert _filter_ergebnis(monkeypatch, None) == ["avalanche_bulletin"]
    assert _filter_ergebnis(monkeypatch, ["meteoalarm"]) == []
