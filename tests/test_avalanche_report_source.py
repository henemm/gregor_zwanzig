"""Quelle `AvalancheReportSource` end-to-end auf aufgezeichneten Bulletins (AC-1).

SPEC: docs/specs/modules/avalanche_report_bulletin.md -- AC-1
VERTRAG: docs/artifacts/feat-1441-s1-lawinenlagebericht/red-contract.md

Die echte Quelle laeuft ueber die echte Abrufschicht (`warn_egress.cached_fetch`); nur der
HTTP-Transport ist ein Fixture-Transport mit den AUFGEZEICHNETEN Bytes (Redirect 301 inklusive).
Kein Netz, keine Mocks. Importe der Prueflinge stehen in den Funktionen (RED: pro Test rot).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.helpers.avalanche_report_support import (
    P_BORDER, P_KAERNTEN_AT_02_05_02, P_MUENCHEN, P_SUEDTIROL_BZ_16, P_TIROL_AT_07_28,
    P_TRENTINO_TN_09, FakeClock, FixtureTransport, alerts_with_status, call_log, day_file,
    make_source, ok, only_source,
)

UTC = timezone.utc
_REPO = Path(__file__).resolve().parents[1]
WINTER_NOW = datetime(2026, 1, 30, 8, 0, tzinfo=UTC)


def _tirol_setup():
    transport = FixtureTransport({"AT-07": ok(day_file("2026-01-30"))})
    clock = FakeClock(WINTER_NOW)
    return transport, clock, make_source(transport, clock)


def _assert_pruefling_aus_diesem_baum() -> None:
    """#1409: der Pruefling stammt aus dem Baum DIESER Testdatei, nicht aus dem Hauptrepo."""
    from services.official_alerts import avalanche_report

    assert Path(avalanche_report.__file__).resolve().is_relative_to(_REPO), (
        f"Pruefling {avalanche_report.__file__} liegt ausserhalb von {_REPO}"
    )


def test_ac1_tirol_punkt_liefert_genau_einen_alert_mit_stufe_3_oberhalb_2200():
    _assert_pruefling_aus_diesem_baum()
    transport, clock, source = _tirol_setup()

    alerts = source.fetch(*P_TIROL_AT_07_28)

    assert len(alerts) == 1, f"genau ein Alert erwartet: {alerts!r}"
    a = alerts[0]
    assert a.hazard == "avalanche_bulletin"
    assert a.native_level == 3 and a.level == 3 and a.scale == "eaws"
    assert (a.elevation_value, a.elevation_direction) == ("2200", "above")
    assert "persistent_weak_layers" in a.problems
    assert a.url == "https://avalanche.report/bulletin/2026-01-30?region=AT-07-28"
    assert a.source == "avalanche_report:AT-07"
    assert a.region_label == "Schobergruppe West"
    assert a.dedup_id == "avalanche_bulletin:AT-07-28"


def test_ac1_redirect_von_static_host_wird_gefolgt_und_nur_die_region_wird_geladen():
    """Der echte Dienst antwortet auf `static.avalanche.report` mit 301. Ohne gefolgten Redirect
    wuerde die Quelle in Produktion IMMER "nicht abrufbar" melden. Ausserdem darf der Punkt
    (liegt auch in der Bounding-Box von AT-02) nur die AT-07-Datei laden -- nicht jede
    Bounding-Box-Zeile."""
    transport, clock, source = _tirol_setup()
    transport.set("AT-02", ok(day_file("2026-03-01", "AT-02")))

    alerts = source.fetch(*P_TIROL_AT_07_28)

    assert len(alerts) == 1
    assert ("static.avalanche.report", "AT-07") in transport.requests, transport.requests
    assert transport.served("AT-07") == 1, transport.requests
    assert transport.served("AT-02") == 0, "AT-02 darf fuer einen AT-07-Punkt nie geladen werden"
    assert transport.served() == 1, transport.requests


def test_ac1_ergebnis_ist_ueber_den_registry_pfad_identisch_und_nicht_abrufbar_false(monkeypatch):
    transport, clock, source = _tirol_setup()
    only_source(monkeypatch, source)

    alerts, unavailable = alerts_with_status(*P_TIROL_AT_07_28, WINTER_NOW)

    assert unavailable is False
    assert [(a.hazard, a.native_level, a.elevation_value) for a in alerts] == [
        ("avalanche_bulletin", 3, "2200")
    ]


def test_ac1_zweiter_abruf_im_ttl_trifft_den_cache(monkeypatch):
    transport, clock, source = _tirol_setup()

    source.fetch(*P_TIROL_AT_07_28)
    clock.advance(600)
    again = source.fetch(*P_TIROL_AT_07_28)

    assert len(again) == 1
    assert transport.served("AT-07") == 1, "innerhalb der 1800-s-TTL darf kein zweiter Abruf stattfinden"


def test_ac1_abruf_steht_im_call_log_unter_dem_servicenamen_avalanche_report(monkeypatch, tmp_path):
    from services.official_alerts import warn_egress

    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "calls.jsonl")
    transport, clock, source = _tirol_setup()

    source.fetch(*P_TIROL_AT_07_28)

    log = call_log()
    assert log, "kein Call-Log-Eintrag"
    assert {row["service"] for row in log} == {"avalanche_report"}
    real = [row for row in log if row["cache_hit"] is False]
    assert len(real) == 1 and real[0]["ok"] is True and real[0]["status"] == 200


def test_ac1_name_und_covers_arbeiten_nur_mit_den_boundingboxen():
    transport, clock, source = _tirol_setup()

    assert source.name == "avalanche_report"
    assert source.covers(*P_TIROL_AT_07_28) is True
    assert source.covers(*P_MUENCHEN) is False
    assert transport.requests == [], "covers() darf nie das Netz beruehren"


@pytest.mark.parametrize(
    "key, day, point, native, level, elev, direction, region, label",
    [
        ("AT-02", "2026-03-01", P_KAERNTEN_AT_02_05_02, 1, 1, None, None, "AT-02-05-02",
         "Lawinenwarndienst Kärnten, avalanche.report"),
        ("IT-32-BZ", "2026-03-01", P_SUEDTIROL_BZ_16, 2, 2, "Waldgrenze", "above", "IT-32-BZ-16",
         "Lawinenwarndienst Südtirol, avalanche.report"),
        ("IT-32-TN", "2026-03-01", P_TRENTINO_TN_09, 3, 3, "Waldgrenze", "above", "IT-32-TN-09",
         "Lawinenwarndienst Trentino, avalanche.report"),
    ],
)
def test_ac1_alle_vier_tabellenzeilen_liefern_ihren_lagebericht(
    key, day, point, native, level, elev, direction, region, label,
):
    """Euregio (Tirol/Suedtirol/Trentino) und Kaernten: jede Zeile der Konfigurationstabelle
    wird abgerufen, ausgewertet und traegt den Namen ihres Lawinenwarndienstes."""
    from output.renderers.alert.official_alerts import official_alert_source_label

    transport = FixtureTransport({key: ok(day_file(day, key))})
    clock = FakeClock(datetime(2026, 3, 1, 8, 0, tzinfo=UTC))
    source = make_source(transport, clock)

    alerts = source.fetch(*point)

    assert len(alerts) == 1, alerts
    a = alerts[0]
    assert (a.native_level, a.level, a.elevation_value, a.elevation_direction) == (
        native, level, elev, direction)
    assert a.source == f"avalanche_report:{key}"
    assert a.url == f"https://avalanche.report/bulletin/2026-03-01?region={region}"
    assert official_alert_source_label(a.source) == label
    assert transport.served() == 1


def test_ac1_grenzpunkt_liefert_trotz_zwei_regionen_genau_einen_alert():
    transport = FixtureTransport({"AT-07": ok(day_file("2026-02-20"))})
    clock = FakeClock(datetime(2026, 2, 20, 8, 0, tzinfo=UTC))
    source = make_source(transport, clock)

    alerts = source.fetch(*P_BORDER)

    assert len(alerts) == 1, alerts
    assert alerts[0].native_level == 4
